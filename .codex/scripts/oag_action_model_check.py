#!/usr/bin/env python3
"""Validate OAG Mission/Action catalogs."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10 and older
    import tomli as tomllib  # type: ignore[no-redef]

SCRIPTS_DIR = Path(__file__).resolve().parent
CODEX_ROOT = SCRIPTS_DIR.parent
PROJECT_ROOT = CODEX_ROOT.parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from oag_validate_json import contextual_schema_issues  # noqa: E402


SCHEMA_VERSION = "oag_action_model_check.v1"
ACTION_CATALOG = CODEX_ROOT / "oag" / "operation_action_types.yaml"
MISSION_CATALOG = CODEX_ROOT / "oag" / "mission_templates.yaml"
AGENT_CATALOG = CODEX_ROOT / "oag" / "agent-catalog.toml"

NON_AGENT_ROLES = {
    "human",
    "human_via_main",
    "human_via_deep_interview",
    "main",
    "tool",
}


def issue(code: str, message: str, path: str = "") -> dict[str, str]:
    payload = {"code": code, "message": message}
    if path:
        payload["path"] = path
    return payload


def read_yaml(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {"__load_error__": f"missing file: {path}"}
    try:
        import yaml  # type: ignore

        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        return data if isinstance(data, dict) else {"__load_error__": "top-level YAML must be an object"}
    except Exception as exc:
        return {"__load_error__": str(exc)}


def read_agent_ids(path: Path) -> tuple[set[str], list[dict[str, str]]]:
    if not path.is_file():
        return set(), [issue("AGENT_CATALOG_MISSING", "agent catalog is missing", str(path))]
    try:
        with path.open("rb") as fh:
            payload = tomllib.load(fh)
    except Exception as exc:
        return set(), [issue("AGENT_CATALOG_INVALID", str(exc), str(path))]
    ids = {
        str(item.get("id") or "").strip()
        for item in payload.get("agents", [])
        if isinstance(item, dict) and str(item.get("id") or "").strip()
    }
    return ids, []


def duplicate_ids(rows: list[Any], field: str) -> list[str]:
    seen: set[str] = set()
    dup: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            continue
        value = str(row.get(field) or "").strip()
        if not value:
            continue
        if value in seen:
            dup.add(value)
        seen.add(value)
    return sorted(dup)


def check() -> dict[str, Any]:
    issues: list[dict[str, str]] = []
    actions = read_yaml(ACTION_CATALOG)
    missions = read_yaml(MISSION_CATALOG)

    if "__load_error__" in actions:
        issues.append(issue("ACTION_CATALOG_LOAD", str(actions["__load_error__"]), str(ACTION_CATALOG)))
        actions = {}
    if "__load_error__" in missions:
        issues.append(issue("MISSION_CATALOG_LOAD", str(missions["__load_error__"]), str(MISSION_CATALOG)))
        missions = {}

    if actions:
        issues.extend(
            contextual_schema_issues(
                "oag_operation_action_types.schema.json",
                actions,
                code_prefix="ACTION_CATALOG_SCHEMA",
                document_path=str(ACTION_CATALOG),
            )
        )
    if missions:
        issues.extend(
            contextual_schema_issues(
                "oag_mission_templates.schema.json",
                missions,
                code_prefix="MISSION_CATALOG_SCHEMA",
                document_path=str(MISSION_CATALOG),
            )
        )

    action_rows = [item for item in actions.get("action_types", []) if isinstance(item, dict)]
    mission_rows = [item for item in missions.get("mission_templates", []) if isinstance(item, dict)]
    action_ids = {str(item.get("id") or "").strip() for item in action_rows if str(item.get("id") or "").strip()}
    agent_ids, agent_issues = read_agent_ids(AGENT_CATALOG)
    issues.extend(agent_issues)

    for dup in duplicate_ids(action_rows, "id"):
        issues.append(issue("ACTION_ID_DUPLICATE", f"duplicate action type id: {dup}", str(ACTION_CATALOG)))
    for dup in duplicate_ids(mission_rows, "id"):
        issues.append(issue("MISSION_ID_DUPLICATE", f"duplicate mission template id: {dup}", str(MISSION_CATALOG)))

    for row in action_rows:
        aid = str(row.get("id") or "").strip()
        role = str(row.get("owner_role") or "").strip()
        if role.startswith("oag-") and role not in agent_ids:
            issues.append(issue("ACTION_OWNER_ROLE_UNKNOWN", f"{aid} owner_role is not in agent catalog: {role}", str(ACTION_CATALOG)))
        elif role and role not in NON_AGENT_ROLES and not role.startswith("oag-"):
            issues.append(issue("ACTION_OWNER_ROLE_UNKNOWN", f"{aid} owner_role is not a known non-agent role: {role}", str(ACTION_CATALOG)))
        policy = row.get("allowed_write_policy") if isinstance(row.get("allowed_write_policy"), dict) else {}
        if policy.get("required") is True and policy.get("source") not in {"dispatch"}:
            issues.append(issue("ACTION_REQUIRED_DISPATCH", f"{aid} requires write permission but source is not dispatch", str(ACTION_CATALOG)))
        fallback = row.get("fallback_policy") if isinstance(row.get("fallback_policy"), dict) else {}
        for key, value in fallback.items():
            if isinstance(value, str) and value.startswith("ACT_") and value not in action_ids and value not in {"route_inconclusive", "block_until_released", "block_replacement_dispatch", "invalid_handoff"}:
                issues.append(issue("ACTION_FALLBACK_UNKNOWN", f"{aid}.{key} references unknown action {value}", str(ACTION_CATALOG)))

    for mission in mission_rows:
        mid = str(mission.get("id") or "").strip()
        refs = []
        refs.extend(item for item in mission.get("forbidden_actions_until_target", []) if isinstance(item, str))
        refs.extend(item for item in mission.get("action_priority", []) if isinstance(item, str))
        for ref in refs:
            if ref not in action_ids:
                issues.append(issue("MISSION_ACTION_REF_UNKNOWN", f"{mid} references unknown action type {ref}", str(MISSION_CATALOG)))

    return {
        "schema_version": SCHEMA_VERSION,
        "status": "fail" if issues else "pass",
        "paths": {
            "action_catalog": str(ACTION_CATALOG),
            "mission_catalog": str(MISSION_CATALOG),
            "agent_catalog": str(AGENT_CATALOG),
        },
        "counts": {
            "action_types": len(action_rows),
            "mission_templates": len(mission_rows),
            "agent_roles": len(agent_ids),
            "issues": len(issues),
        },
        "issues": issues,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    result = check()
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    elif result["status"] == "pass":
        print(f"PASS {SCHEMA_VERSION}: {result['counts']['action_types']} actions, {result['counts']['mission_templates']} missions")
    else:
        print(f"FAIL {SCHEMA_VERSION}", file=sys.stderr)
        for item in result["issues"]:
            print(f"- {item.get('code')}: {item.get('message')}", file=sys.stderr)
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
