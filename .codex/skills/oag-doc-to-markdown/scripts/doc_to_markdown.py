#!/usr/bin/env python3
"""Convert source documents to Markdown for agent intake."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


PASSTHROUGH_EXTENSIONS = {
    ".c",
    ".cc",
    ".cfg",
    ".cpp",
    ".csv",
    ".f",
    ".h",
    ".hpp",
    ".json",
    ".log",
    ".markdown",
    ".md",
    ".py",
    ".rpt",
    ".rst",
    ".sdc",
    ".sv",
    ".svh",
    ".tcl",
    ".tsv",
    ".txt",
    ".v",
    ".vh",
    ".xml",
    ".yaml",
    ".yml",
}

MARKITDOWN_EXTENSIONS = {
    ".doc",
    ".docx",
    ".htm",
    ".html",
    ".pdf",
    ".ppt",
    ".pptx",
    ".xls",
    ".xlsx",
}


def issue(code: str, message: str, *, path: Path | None = None) -> dict[str, str]:
    payload = {"code": code, "message": message}
    if path is not None:
        payload["path"] = str(path)
    return payload


def emit(payload: dict[str, Any], *, json_mode: bool) -> None:
    if json_mode:
        print(json.dumps(payload, indent=2, sort_keys=True))
    elif payload.get("status") != "pass":
        for item in payload.get("issues", []):
            print(f"{item.get('code', 'ISSUE')}: {item.get('message', '')}", file=sys.stderr)


def safe_output_name(path: Path) -> str:
    stem = re.sub(r"[^A-Za-z0-9._-]+", "_", path.stem).strip("._-")
    return f"{stem or 'document'}.md"


def output_path_for(input_path: Path, output: str | None, out_dir: str | None) -> Path:
    if output:
        return Path(output).expanduser().resolve()
    if out_dir:
        return Path(out_dir).expanduser().resolve() / safe_output_name(input_path)
    return input_path.with_suffix(".md").resolve()


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def convert_with_markitdown_api(path: Path) -> tuple[str | None, str | None]:
    try:
        from markitdown import MarkItDown  # type: ignore
    except Exception as exc:  # pragma: no cover - depends on local package state
        return None, f"markitdown Python package import failed: {exc}"
    try:
        result = MarkItDown().convert(str(path))
    except Exception as exc:  # pragma: no cover - depends on local package state
        return None, f"markitdown API conversion failed: {exc}"
    text = getattr(result, "text_content", None)
    if text is None:
        text = getattr(result, "markdown", None)
    if text is None:
        text = str(result)
    return str(text), None


def candidate_pythons() -> list[str]:
    values: list[str] = []
    env_python = os.environ.get("OAG_MARKITDOWN_PYTHON")
    if env_python:
        values.append(env_python)
    values.extend(
        [
            sys.executable,
            "python3.12",
            "python3.11",
            "python3.10",
            "python3",
            "/opt/homebrew/bin/python3.10",
        ]
    )
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        if value == sys.executable or Path(value).is_file() or shutil.which(value):
            result.append(value)
    return result


def convert_with_markitdown_subprocess(path: Path, *, timeout: int) -> tuple[str | None, str | None]:
    errors: list[str] = []
    for python in candidate_pythons():
        try:
            proc = subprocess.run(
                [python, "-m", "markitdown", str(path)],
                text=True,
                capture_output=True,
                check=False,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            errors.append(f"{python}: timed out after {timeout}s")
            continue
        if proc.returncode == 0 and proc.stdout:
            return proc.stdout, None
        stderr = (proc.stderr or proc.stdout or "").strip()
        errors.append(f"{python}: {stderr or f'exit {proc.returncode}'}")
    return None, "; ".join(errors) if errors else "no Python interpreter found for markitdown"


def convert_document(input_path: Path, *, backend: str, timeout: int) -> tuple[str | None, str, list[dict[str, str]]]:
    suffix = input_path.suffix.lower()
    issues: list[dict[str, str]] = []

    if backend != "markitdown" and suffix in PASSTHROUGH_EXTENSIONS:
        return read_text(input_path), "passthrough", issues

    if backend == "passthrough":
        issues.append(
            issue(
                "DOC_TO_MD_UNSUPPORTED_PASSTHROUGH",
                f"{suffix or '<none>'} is not a passthrough text extension.",
                path=input_path,
            )
        )
        return None, "passthrough", issues

    text, error = convert_with_markitdown_api(input_path)
    if text is not None:
        return text, "markitdown_api", issues

    subprocess_text, subprocess_error = convert_with_markitdown_subprocess(input_path, timeout=timeout)
    if subprocess_text is not None:
        return subprocess_text, "markitdown_subprocess", issues

    detail = "; ".join(part for part in (error, subprocess_error) if part)
    hint = "Install markitdown, for example: python3.10 -m pip install 'markitdown[all]'"
    issues.append(
        issue(
            "DOC_TO_MD_MARKITDOWN_UNAVAILABLE",
            f"Cannot convert {suffix or '<none>'} without a working markitdown backend. {hint}. {detail}",
            path=input_path,
        )
    )
    return None, "markitdown", issues


def build_payload(
    *,
    status: str,
    input_path: Path,
    output_path: Path | None,
    backend: str,
    markdown: str | None,
    issues: list[dict[str, str]],
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schema_version": "oag_doc_to_markdown_result.v1",
        "status": status,
        "input": str(input_path),
        "input_format": input_path.suffix.lower(),
        "backend": backend,
        "issues": issues,
    }
    if output_path is not None:
        payload["output"] = str(output_path)
    if markdown is not None:
        payload["char_count"] = len(markdown)
    return payload


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="Source document path.")
    parser.add_argument("--output", help="Markdown output file. Defaults to <input>.md or --out-dir/<input>.md.")
    parser.add_argument("--out-dir", help="Directory for generated Markdown.")
    parser.add_argument("--stdout", action="store_true", help="Print Markdown to stdout instead of writing a file.")
    parser.add_argument("--json", action="store_true", help="Print structured JSON result.")
    parser.add_argument("--timeout", type=int, default=60, help="Per-file markitdown timeout in seconds.")
    parser.add_argument("--backend", choices=("auto", "passthrough", "markitdown"), default="auto")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    input_path = Path(args.input).expanduser().resolve()

    if args.stdout and args.json:
        payload = build_payload(
            status="fail",
            input_path=input_path,
            output_path=None,
            backend=args.backend,
            markdown=None,
            issues=[issue("DOC_TO_MD_ARG_CONFLICT", "--stdout and --json cannot be combined.")],
        )
        emit(payload, json_mode=True)
        return 2

    if not input_path.is_file():
        payload = build_payload(
            status="fail",
            input_path=input_path,
            output_path=None,
            backend=args.backend,
            markdown=None,
            issues=[issue("DOC_TO_MD_INPUT_MISSING", "Input document does not exist.", path=input_path)],
        )
        emit(payload, json_mode=args.json)
        return 2

    markdown, backend, issues = convert_document(input_path, backend=args.backend, timeout=args.timeout)
    if markdown is None:
        payload = build_payload(
            status="fail",
            input_path=input_path,
            output_path=None,
            backend=backend,
            markdown=None,
            issues=issues,
        )
        emit(payload, json_mode=args.json)
        return 2

    if args.stdout:
        sys.stdout.write(markdown)
        return 0

    output_path = output_path_for(input_path, args.output, args.out_dir)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(markdown, encoding="utf-8")
    payload = build_payload(
        status="pass",
        input_path=input_path,
        output_path=output_path,
        backend=backend,
        markdown=markdown,
        issues=issues,
    )
    emit(payload, json_mode=args.json)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
