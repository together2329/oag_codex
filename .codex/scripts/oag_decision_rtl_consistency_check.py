#!/usr/bin/env python3
# noqa: SIZE_OK - OAG consistency checker keeps parsing and CLI diagnostics together.

from __future__ import annotations

import argparse
import importlib
import json
import re
import sys
from pathlib import Path
from typing import Any, Final


SCRIPTS_DIR: Final = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

oag_paths = importlib.import_module("oag_paths")
oag_common = importlib.import_module("oag_common")

JsonObject = dict[str, Any]
PARAM_RE: Final = re.compile(
    r"\b(?:localparam|parameter)\b(?:\s+(?:integer|int|logic|bit|reg|wire|real))*"
    r"(?:\s*\[[^\]]+\])?\s+(?P<name>[A-Za-z_][A-Za-z0-9_$]*)\s*=\s*(?P<value>[^,;)\n]+)"
)
RTL_GLOBS: Final = ("*.v", "*.sv", "*.vh", "*.svh")


def read_decision_matrix(ip_dir: Path) -> JsonObject:
    return oag_common.read_yaml(oag_paths.legacy_or_hidden(ip_dir, "ontology/decision_matrix.yaml"))


def decision_rows(ip_dir: Path) -> list[JsonObject]:
    doc = read_decision_matrix(ip_dir)
    if not doc or doc.get("__load_error__"):
        return []
    return [
        item
        for item in oag_common.as_list(doc.get("decisions"))
        if isinstance(item, dict)
        and oag_common.text(item.get("status")).lower() == "decided"
        and item.get("lock_required") is True
    ]


def rtl_files(ip_dir: Path) -> list[Path]:
    root = oag_paths.legacy_or_hidden(ip_dir, "rtl")
    if not root.is_dir():
        return []
    files: list[Path] = []
    for pattern in RTL_GLOBS:
        files.extend(path for path in root.rglob(pattern) if path.is_file())
    return sorted(set(files))


def rtl_text(files: list[Path]) -> str:
    chunks: list[str] = []
    for path in files:
        try:
            chunks.append(path.read_text(encoding="utf-8", errors="ignore"))
        except OSError:
            continue
    return "\n".join(chunks)


def rtl_parameters(files: list[Path]) -> dict[str, JsonObject]:
    params: dict[str, JsonObject] = {}
    for path in files:
        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for match in PARAM_RE.finditer(content):
            name = match.group("name")
            value = match.group("value").strip()
            params[name] = {"value": normalize_literal(value), "raw_value": value, "path": str(path)}
    return params


def normalize_literal(value: Any) -> str:
    raw = oag_common.text(value).rstrip(",)")
    if "'" in raw:
        _, _, tail = raw.partition("'")
        if tail and tail[0].lower() in {"d", "h", "b", "o"}:
            digits = tail[1:].replace("_", "")
            try:
                base = {"d": 10, "h": 16, "b": 2, "o": 8}[tail[0].lower()]
                return str(int(digits, base))
            except ValueError:
                return raw
    return raw.strip('"')


def decision_value(decision: JsonObject) -> str:
    for key in ("selected_value", "value", "decision", "default_value"):
        raw = decision.get(key)
        if isinstance(raw, dict):
            if "value" in raw:
                return normalize_literal(raw.get("value"))
        elif raw is not None:
            return normalize_literal(raw)
    return ""


def parameter_name(decision: JsonObject) -> str:
    for key in ("parameter", "parameter_name", "config_parameter", "rtl_parameter"):
        value = oag_common.text(decision.get(key))
        if value:
            return value
    raw = decision.get("parameter_draft")
    if isinstance(raw, dict) and len(raw) == 1:
        return next(iter(raw))
    return ""


def selected_generate_option(decision: JsonObject) -> str:
    for key in ("selected_option", "generate_option", "option", "decision"):
        raw = decision.get(key)
        if isinstance(raw, dict):
            value = oag_common.text(raw.get("id") or raw.get("name") or raw.get("selected"))
        else:
            value = oag_common.text(raw)
        if value:
            return value
    return ""


def verification_config_ids(ip_dir: Path) -> set[str]:
    doc = oag_common.read_structured(oag_paths.legacy_or_hidden(ip_dir, "ontology/verification_plan.yaml"))
    configs = oag_common.as_list(doc.get("verification_configurations") or doc.get("configurations"))
    return {
        oag_common.text(item.get("id") or item.get("name"))
        for item in configs
        if isinstance(item, dict) and oag_common.text(item.get("id") or item.get("name"))
    }


def check_parameter_decision(decision: JsonObject, params: dict[str, JsonObject], *, base: str) -> list[dict[str, str]]:
    name = parameter_name(decision)
    if not name:
        return []
    expected = decision_value(decision)
    actual = params.get(name)
    if actual is None:
        return [oag_common.issue("DECISION_RTL_PARAMETER_MISSING", f"{base} parameter {name} is not present in RTL.", base)]
    if expected and normalize_literal(actual.get("value")) != expected:
        return [
            oag_common.issue(
                "DECISION_RTL_PARAMETER_MISMATCH",
                f"{base} parameter {name} expected {expected} but RTL has {actual.get('raw_value')}.",
                oag_common.text(actual.get("path")),
            )
        ]
    return []


def check_generate_decision(decision: JsonObject, content: str, configs: set[str], *, base: str) -> list[dict[str, str]]:
    if oag_common.text(decision.get("representation")).lower() != "generate_option":
        return []
    selected = selected_generate_option(decision)
    if not selected:
        return [oag_common.issue("DECISION_GENERATE_OPTION_MISSING", f"{base} has no selected generate option.", base)]
    issues: list[dict[str, str]] = []
    if selected not in content:
        issues.append(oag_common.issue("DECISION_RTL_GENERATE_OPTION_MISSING", f"{base} selected generate option {selected} is not visible in RTL.", base))
    if selected not in configs:
        issues.append(oag_common.issue("DECISION_VPLAN_GENERATE_OPTION_MISSING", f"{base} selected generate option {selected} has no verification configuration.", "ontology/verification_plan.yaml"))
    return issues


def check(ip_dir: Path) -> JsonObject:
    ip_dir = oag_paths.ip_root(ip_dir)
    files = rtl_files(ip_dir)
    decisions = decision_rows(ip_dir)
    params = rtl_parameters(files)
    content = rtl_text(files)
    configs = verification_config_ids(ip_dir)
    issues: list[dict[str, str]] = []
    for decision in decisions:
        did = oag_common.text(decision.get("id")) or "decision"
        base = f"decisions[{did}]"
        if oag_common.text(decision.get("representation")).lower() == "parameter" or parameter_name(decision):
            issues.extend(check_parameter_decision(decision, params, base=base))
        issues.extend(check_generate_decision(decision, content, configs, base=base))
    return {
        "schema_version": "oag_decision_rtl_consistency_check.v1",
        "status": "fail" if issues else "pass",
        "ip": ip_dir.name,
        "counts": {"decisions": len(decisions), "rtl_files": len(files), "parameters": len(params), "issues": len(issues)},
        "issues": issues,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check locked OAG decisions against authored RTL and verification configuration.")
    parser.add_argument("--ip-dir", required=True)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    payload = check(Path(args.ip_dir))
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    elif payload["status"] == "pass":
        print("PASS oag decision RTL consistency check")
    else:
        print("FAIL oag decision RTL consistency check")
        for item in payload["issues"]:
            print(f"- {item.get('code')}: {item.get('message')}")
    return 0 if payload["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
