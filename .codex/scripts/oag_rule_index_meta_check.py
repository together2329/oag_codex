#!/usr/bin/env python3

from __future__ import annotations

import argparse
import importlib
import json
import sys
from pathlib import Path
from typing import Any, Final


SCRIPTS_DIR: Final = Path(__file__).resolve().parent
CODEX_ROOT: Final = SCRIPTS_DIR.parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

oag_common = importlib.import_module("oag_common")

JsonObject = dict[str, Any]


def normalized_ref(path: Path) -> str:
    return f"scripts/{path.name}"


def duplicate_yaml_key_issues(path: Path) -> list[dict[str, str]]:
    try:
        import yaml  # type: ignore
    except ImportError as exc:
        return [oag_common.issue("RULE_INDEX_YAML_IMPORT", str(exc), str(path))]

    class DuplicateKeyLoader(yaml.SafeLoader):
        pass

    duplicates: list[str] = []

    def construct_mapping(loader: DuplicateKeyLoader, node: Any, deep: bool = False) -> dict[Any, Any]:
        seen: set[Any] = set()
        mapping: dict[Any, Any] = {}
        for key_node, value_node in node.value:
            key = loader.construct_object(key_node, deep=deep)
            if key in seen:
                duplicates.append(str(key))
            seen.add(key)
            mapping[key] = loader.construct_object(value_node, deep=deep)
        return mapping

    DuplicateKeyLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, construct_mapping)
    try:
        yaml.load(path.read_text(encoding="utf-8"), Loader=DuplicateKeyLoader)
    except yaml.YAMLError as exc:
        return [oag_common.issue("RULE_INDEX_YAML_INVALID", str(exc), str(path))]
    return [
        oag_common.issue("RULE_INDEX_DUPLICATE_KEY", f"duplicate YAML key: {key}", str(path))
        for key in sorted(set(duplicates))
    ]


def check() -> JsonObject:
    index_path = CODEX_ROOT / "rules" / "oag-rule-index.yaml"
    doc = oag_common.read_yaml(index_path)
    issues: list[dict[str, str]] = duplicate_yaml_key_issues(index_path)
    warnings: list[dict[str, str]] = []
    if not doc or doc.get("__load_error__"):
        return {
            "schema_version": "oag_rule_index_meta_check.v1",
            "status": "fail",
            "issues": [oag_common.issue("RULE_INDEX_LOAD_FAILED", oag_common.text(doc.get("__load_error__")), str(index_path))],
            "warnings": [],
            "counts": {"rules": 0, "checker_refs": 0, "orphan_checkers": 0},
        }
    rules = [item for item in oag_common.as_list(doc.get("rules")) if isinstance(item, dict)]
    referenced: set[str] = set()
    for rule in rules:
        rid = oag_common.text(rule.get("id")) or "<missing-id>"
        tested_by = oag_common.str_items(rule.get("tested_by"))
        if not tested_by:
            issues.append(oag_common.issue("RULE_TESTED_BY_MISSING", f"{rid} needs tested_by smoke/eval coverage refs.", str(index_path)))
        severity = rule.get("severity")
        if not isinstance(severity, dict):
            issues.append(oag_common.issue("RULE_SEVERITY_MISSING", f"{rid} needs severity draft/post_lock/closure.", str(index_path)))
        else:
            for key in ("draft", "post_lock", "closure"):
                if not oag_common.text(severity.get(key)):
                    issues.append(oag_common.issue("RULE_SEVERITY_FIELD_MISSING", f"{rid} severity.{key} is missing.", str(index_path)))
        referenced.update(oag_common.str_items(rule.get("checker_refs")))
    checkers = {normalized_ref(path) for path in SCRIPTS_DIR.glob("oag_*_check.py")}
    orphan_checkers = sorted(checkers - referenced)
    for ref in orphan_checkers:
        warnings.append(oag_common.issue("RULE_CHECKER_REF_ORPHAN", f"{ref} is not referenced by oag-rule-index.yaml.", ref))
    return {
        "schema_version": "oag_rule_index_meta_check.v1",
        "status": "fail" if issues else "pass",
        "issues": issues,
        "warnings": warnings,
        "counts": {"rules": len(rules), "checker_refs": len(referenced), "orphan_checkers": len(orphan_checkers)},
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check OAG rule-index metadata.")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    payload = check()
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    elif payload["status"] == "pass":
        print("PASS oag rule-index meta check")
    else:
        print("FAIL oag rule-index meta check")
        for item in payload["issues"]:
            print(f"- {item.get('code')}: {item.get('message')}")
    return 0 if payload["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
