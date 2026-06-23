#!/usr/bin/env python3
"""Validate an OAG baseline manifest against tracked files and hashes."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

SCRIPTS_DIR = Path(__file__).resolve().parent
CODEX_ROOT = SCRIPTS_DIR.parent
SCHEMAS_DIR = CODEX_ROOT / "schemas"

sys.path.insert(0, str(SCRIPTS_DIR))
from oag_validate_json import validate_document  # pylint: disable=wrong-import-position


def issue(code: str, message: str, path: str = "") -> dict[str, str]:
    payload = {"code": code, "message": message}
    if path:
        payload["path"] = path
    return payload


def read_document(path: Path) -> tuple[dict[str, Any] | None, list[dict[str, str]]]:
    try:
        if path.suffix in {".yaml", ".yml"}:
            import yaml  # type: ignore

            payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        else:
            payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return None, [issue("BASELINE_LOAD_ERROR", f"Cannot read baseline manifest: {exc}", str(path))]
    if not isinstance(payload, dict):
        return None, [issue("BASELINE_SHAPE", "Baseline manifest must be an object.", str(path))]
    return payload, []


def load_schema() -> dict[str, Any]:
    return json.loads((SCHEMAS_DIR / "oag_baseline_manifest.schema.json").read_text(encoding="utf-8"))


def schema_issues(payload: dict[str, Any]) -> list[dict[str, str]]:
    return [
        issue("BASELINE_SCHEMA", f"{item.get('code')}: {item.get('message')}", str(item.get("path") or ""))
        for item in validate_document(load_schema(), payload)
    ]


def infer_ip_dir(manifest_path: Path) -> Path:
    parent = manifest_path.resolve().parent
    if parent.name == "baselines" and parent.parent.name == "ontology":
        return parent.parent.parent
    return Path.cwd()


def rel_path(raw: str, ip_dir: Path) -> Path | None:
    if not raw or raw.startswith("/") or ".." in Path(raw).parts:
        return None
    return ip_dir / raw


def file_hash(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            size += len(chunk)
            digest.update(chunk)
    return f"sha256:{digest.hexdigest()}", size


def tracked_paths(payload: dict[str, Any]) -> tuple[list[str], list[dict[str, str]]]:
    tracked = payload.get("tracked_artifacts")
    issues: list[dict[str, str]] = []
    paths: list[str] = []
    if not isinstance(tracked, dict):
        return paths, [issue("BASELINE_TRACKED_ARTIFACTS", "tracked_artifacts must be an object.")]
    for group, value in tracked.items():
        if not isinstance(value, list):
            issues.append(issue("BASELINE_TRACKED_GROUP", f"tracked_artifacts.{group} must be a list.", str(group)))
            continue
        for item in value:
            if not isinstance(item, str) or not item.strip():
                issues.append(issue("BASELINE_TRACKED_PATH", f"tracked_artifacts.{group} contains a non-string path.", str(group)))
                continue
            paths.append(item.strip())
    return paths, issues


def check_git_policy(payload: dict[str, Any]) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    baseline = payload.get("baseline") if isinstance(payload.get("baseline"), dict) else {}
    git = payload.get("git") if isinstance(payload.get("git"), dict) else {}
    if baseline.get("class") == "golden":
        if not str(git.get("tag") or "").strip():
            issues.append(issue("BASELINE_GIT_TAG", "Golden baseline requires git.tag."))
        if git.get("tag_type") != "annotated":
            issues.append(issue("BASELINE_TAG_TYPE", "Golden baseline requires git.tag_type=annotated."))
    commit = str(git.get("commit") or "")
    if commit and commit != "resolved_by_tag":
        issues.append(issue("BASELINE_SELF_COMMIT", "Manifest must not embed a concrete self commit hash; use resolved_by_tag."))
    return issues


def check_gate_refs(payload: dict[str, Any], ip_dir: Path) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    baseline = payload.get("baseline") if isinstance(payload.get("baseline"), dict) else {}
    gate = payload.get("gate") if isinstance(payload.get("gate"), dict) else {}
    if baseline.get("class") in {"golden", "release"}:
        for field, code in (("gate_ref", "BASELINE_GATE_REF"), ("validation_ref", "BASELINE_VALIDATION_REF")):
            raw = str(gate.get(field) or "")
            path = rel_path(raw, ip_dir)
            if path is None:
                issues.append(issue(code, f"{field} must be a relative path under the IP directory.", raw))
            elif not path.is_file():
                issues.append(issue(code, f"{field} does not exist.", raw))
    return issues


def check_hashes(payload: dict[str, Any], ip_dir: Path) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    paths, track_issues = tracked_paths(payload)
    issues.extend(track_issues)
    hashes = payload.get("hashes") if isinstance(payload.get("hashes"), dict) else {}
    tracked_set = set(paths)

    for rel in paths:
        path = rel_path(rel, ip_dir)
        if path is None:
            issues.append(issue("BASELINE_TRACKED_PATH", "Tracked artifact path must be relative and stay under the IP directory.", rel))
            continue
        if not path.is_file():
            issues.append(issue("BASELINE_TRACKED_FILE_MISSING", "Tracked artifact file is missing.", rel))
            continue
        entry = hashes.get(rel)
        if not isinstance(entry, dict):
            issues.append(issue("BASELINE_HASH_MISSING", "Every tracked artifact needs a hash entry.", rel))
            continue
        if entry.get("hash_mode") != "raw_bytes":
            issues.append(issue("BASELINE_HASH_MODE", "P0 baseline hashes must use hash_mode=raw_bytes.", rel))
        expected_hash = str(entry.get("content_sha256") or "")
        expected_size = entry.get("size_bytes")
        actual_hash, actual_size = file_hash(path)
        if expected_hash != actual_hash:
            issues.append(issue("BASELINE_HASH_MISMATCH", "Tracked artifact content_sha256 does not match file bytes.", rel))
        if expected_size != actual_size:
            issues.append(issue("BASELINE_SIZE_MISMATCH", "Tracked artifact size_bytes does not match file bytes.", rel))

    for rel in sorted(str(key) for key in hashes.keys()):
        if rel not in tracked_set:
            issues.append(issue("BASELINE_HASH_UNTRACKED", "Hash entry does not correspond to a tracked artifact.", rel))
    return issues


def check_manifest(manifest_path: Path, *, ip_dir: Path | None = None) -> dict[str, Any]:
    manifest_path = manifest_path.resolve()
    ip_root = (ip_dir or infer_ip_dir(manifest_path)).resolve()
    payload, issues = read_document(manifest_path)
    if payload is None:
        payload = {}
    if payload:
        issues.extend(schema_issues(payload))
        issues.extend(check_git_policy(payload))
        issues.extend(check_gate_refs(payload, ip_root))
        issues.extend(check_hashes(payload, ip_root))

    paths, _ = tracked_paths(payload) if payload else ([], [])
    return {
        "schema_version": "oag_baseline_check.v1",
        "status": "fail" if issues else "pass",
        "manifest": str(manifest_path),
        "ip_dir": str(ip_root),
        "baseline_id": payload.get("baseline_id") if isinstance(payload, dict) else "",
        "counts": {"tracked_artifacts": len(paths), "issues": len(issues)},
        "issues": issues,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--ip-dir")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    result = check_manifest(Path(args.manifest), ip_dir=Path(args.ip_dir) if args.ip_dir else None)
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    elif result["status"] == "pass":
        print("PASS OAG baseline check")
    else:
        print("FAIL OAG baseline check", file=sys.stderr)
        for item in result["issues"]:
            suffix = f" ({item['path']})" if item.get("path") else ""
            print(f"- {item['code']}: {item['message']}{suffix}", file=sys.stderr)
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
