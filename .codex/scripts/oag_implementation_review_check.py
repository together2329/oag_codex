#!/usr/bin/env python3
"""Validate OAG implementation-review evidence reports.

An implementation review report is read-only evidence: it maps current RTL or
legacy/reference artifacts against locked contracts and classifies each
contract as implemented, partial, missing, unverifiable, or not applicable. It
does not close obligations by itself.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

SCRIPTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS_DIR))

import oag_paths  # noqa: E402
from oag_validate_json import contextual_schema_issues  # noqa: E402


DEFAULT_REPORT = Path("knowledge/gap_matrix/implementation_review.json")
OPEN_STATUSES = {"partial", "missing", "unverifiable"}
PRIORITY_ORDER = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}
ONTOLOGY_ID_FILES = (
    "ontology/requirements.yaml",
    "ontology/obligations.yaml",
    "ontology/contracts.yaml",
)


def read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception as exc:
        return {"__load_error__": str(exc)}


def read_yaml(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        import yaml  # type: ignore

        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        return data if isinstance(data, dict) else {}
    except Exception as exc:
        return {"__load_error__": str(exc)}


def as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def str_items(value: Any) -> list[str]:
    return [str(item).strip() for item in as_list(value) if str(item).strip()]


def issue(code: str, message: str, path: str = "") -> dict[str, str]:
    payload = {"code": code, "message": message}
    if path:
        payload["path"] = path
    return payload


def item_id(item: dict[str, Any]) -> str:
    for key in ("id", "contract_id", "obligation_id", "requirement_id", "req_id"):
        value = str(item.get(key) or "").strip()
        if value:
            return value
    return ""


def ontology_ids(path: Path, key: str) -> set[str]:
    data = read_yaml(path)
    items = data.get(key) if isinstance(data, dict) else []
    return {item_id(item) for item in as_list(items) if isinstance(item, dict) and item_id(item)}


def report_path(ip_dir: Path, raw: str | None) -> Path:
    if raw:
        candidate = Path(raw).expanduser()
        return candidate if candidate.is_absolute() else ip_dir / candidate
    return oag_paths.legacy_or_hidden(ip_dir, DEFAULT_REPORT)


def ontology_present(ip_dir: Path) -> bool:
    return any(oag_paths.legacy_or_hidden(ip_dir, rel).is_file() for rel in ONTOLOGY_ID_FILES)


def validate_report(
    ip_dir: Path,
    report: Path,
    *,
    require_ontology: bool = False,
    legacy_no_scaffold: bool = False,
) -> dict[str, Any]:
    issues: list[dict[str, str]] = []
    payload = read_json(report)
    rel = str(report)
    has_ontology = ontology_present(ip_dir)
    mode = "legacy_no_scaffold" if legacy_no_scaffold or not has_ontology else "oag_ontology"
    ontology_note = ""
    if require_ontology and not has_ontology:
        issues.append(
            issue(
                "IMPLEMENTATION_REVIEW_ONTOLOGY_MISSING",
                "canonical ontology is required for this check but no requirements/obligations/contracts files were found",
                str(ip_dir),
            )
        )
    elif not has_ontology:
        ontology_note = (
            "No canonical ontology files were found; treating report as legacy-no-scaffold evidence and "
            "skipping unknown requirement/obligation/contract ID checks."
        )

    if not report.is_file():
        issues.append(issue("IMPLEMENTATION_REVIEW_MISSING", "implementation review report is missing", rel))
        payload = {}
    elif payload.get("__load_error__"):
        issues.append(issue("IMPLEMENTATION_REVIEW_JSON", f"cannot read report: {payload['__load_error__']}", rel))

    if payload:
        issues.extend(
            contextual_schema_issues(
                "oag_implementation_review_report.schema.json",
                payload,
                code_prefix="IMPLEMENTATION_REVIEW_SCHEMA",
                document_path=rel,
            )
        )

    requirements = ontology_ids(oag_paths.legacy_or_hidden(ip_dir, "ontology/requirements.yaml"), "requirements")
    obligations = ontology_ids(oag_paths.legacy_or_hidden(ip_dir, "ontology/obligations.yaml"), "obligations")
    contracts = ontology_ids(oag_paths.legacy_or_hidden(ip_dir, "ontology/contracts.yaml"), "contracts")

    finding_contracts: set[str] = set()
    open_contracts: set[str] = set()
    findings = [item for item in as_list(payload.get("findings")) if isinstance(item, dict)]
    for index, finding in enumerate(findings):
        prefix = f"{rel}:findings[{index}]"
        contract_id = str(finding.get("contract_id") or "").strip()
        obligation_id = str(finding.get("obligation_id") or "").strip()
        requirement_id = str(finding.get("requirement_id") or "").strip()
        status = str(finding.get("implementation_status") or "").strip()
        if contract_id:
            finding_contracts.add(contract_id)
            if contracts and contract_id not in contracts:
                issues.append(issue("IMPLEMENTATION_REVIEW_UNKNOWN_CONTRACT", f"unknown contract_id {contract_id}", prefix))
        if obligation_id and obligations and obligation_id not in obligations:
            issues.append(issue("IMPLEMENTATION_REVIEW_UNKNOWN_OBLIGATION", f"unknown obligation_id {obligation_id}", prefix))
        if requirement_id and requirements and requirement_id not in requirements:
            issues.append(issue("IMPLEMENTATION_REVIEW_UNKNOWN_REQUIREMENT", f"unknown requirement_id {requirement_id}", prefix))
        if status == "implemented" and not (str_items(finding.get("evidence_refs")) or str_items(finding.get("rtl_refs"))):
            issues.append(issue("IMPLEMENTATION_REVIEW_IMPLEMENTED_EVIDENCE", "implemented finding needs evidence_refs or rtl_refs", prefix))
        if status in OPEN_STATUSES:
            open_contracts.add(contract_id)
            if not (
                str_items(finding.get("missing"))
                or str_items(finding.get("blockers"))
                or str(finding.get("recommended_next_action") or "").strip()
            ):
                issues.append(issue("IMPLEMENTATION_REVIEW_OPEN_ACTION", f"{status} finding needs missing/blockers/recommended_next_action", prefix))

    actions = [item for item in as_list(payload.get("ranked_next_actions")) if isinstance(item, dict)]
    action_contracts = {
        str(item.get("contract_id") or "").strip()
        for item in actions
        if str(item.get("contract_id") or "").strip()
    }
    missing_actions = sorted(contract for contract in open_contracts if contract and contract not in action_contracts)
    for contract_id in missing_actions:
        issues.append(issue("IMPLEMENTATION_REVIEW_ACTION_MISSING", "open implementation finding needs a ranked_next_action", contract_id))

    if payload.get("may_claim_complete") is True:
        issues.append(issue("IMPLEMENTATION_REVIEW_COMPLETION_CLAIM", "implementation review evidence must not claim completion", rel))

    plan = build_next_wave_plan(findings, actions)

    return {
        "schema_version": "oag_implementation_review_check.v1",
        "status": "fail" if issues else "pass",
        "ip_dir": str(ip_dir),
        "report": str(report),
        "mode": mode,
        "legacy_no_scaffold": legacy_no_scaffold or not has_ontology,
        "ontology_present": has_ontology,
        "notes": [ontology_note] if ontology_note else [],
        "counts": {
            "findings": len(findings),
            "finding_contracts": len(finding_contracts),
            "open_contracts": len(open_contracts),
            "ranked_next_actions": len(action_contracts),
            "ready_actions": len(plan["ready_actions"]),
            "next_wave_actions": len(plan["next_wave"]["actions"]),
            "issues": len(issues),
        },
        "plan": plan,
        "issues": issues,
    }


def action_priority(action: dict[str, Any]) -> str:
    priority = str(action.get("priority") or "").strip()
    return priority if priority in PRIORITY_ORDER else "P3"


def build_next_wave_plan(findings: list[dict[str, Any]], actions: list[dict[str, Any]]) -> dict[str, Any]:
    implemented_contracts = {
        str(item.get("contract_id") or "").strip()
        for item in findings
        if str(item.get("implementation_status") or "").strip() in {"implemented", "not_applicable"}
        and str(item.get("contract_id") or "").strip()
    }
    open_action_ids = {
        str(item.get("id") or "").strip()
        for item in actions
        if str(item.get("id") or "").strip()
        and str(item.get("status") or "").strip() not in {"done", "closed", "waived"}
    }
    enriched: list[dict[str, Any]] = []
    for action in actions:
        action_id = str(action.get("id") or "").strip()
        if not action_id:
            continue
        blockers: list[str] = []
        for dep in str_items(action.get("depends_on")) + str_items(action.get("depends_on_actions")):
            if dep in open_action_ids:
                blockers.append(f"action:{dep}")
        for dep in str_items(action.get("depends_on_contracts")):
            if dep not in implemented_contracts:
                blockers.append(f"contract:{dep}")
        status = str(action.get("status") or "").strip()
        if status == "blocked":
            blockers.append("status:blocked")
        enriched.append(
            {
                "id": action_id,
                "priority": action_priority(action),
                "contract_id": str(action.get("contract_id") or "").strip(),
                "summary": str(action.get("summary") or "").strip(),
                "target_agent": str(action.get("target_agent") or "").strip(),
                "target_artifacts": str_items(action.get("target_artifacts")),
                "parallel_group": str(action.get("parallel_group") or "").strip(),
                "dependency_blockers": blockers,
                "ready": not blockers and status in {"ready", "planned", "deferred", ""},
            }
        )
    ready = sorted(
        [item for item in enriched if item["ready"]],
        key=lambda item: (PRIORITY_ORDER.get(item["priority"], 99), item["id"]),
    )
    next_priority = ready[0]["priority"] if ready else ""
    candidate = [item for item in ready if item["priority"] == next_priority]
    selected: list[dict[str, Any]] = []
    used_artifacts: set[str] = set()
    for item in candidate:
        artifacts = set(item["target_artifacts"])
        if artifacts and used_artifacts.intersection(artifacts):
            continue
        selected.append(item)
        used_artifacts.update(artifacts)
    return {
        "policy": "highest_priority_ready_disjoint_artifacts_first",
        "implemented_contracts": sorted(implemented_contracts),
        "ready_actions": ready,
        "deferred_actions": [item for item in enriched if not item["ready"]],
        "next_wave": {
            "priority": next_priority,
            "parallel_safe": True,
            "actions": selected,
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate OAG implementation-review evidence.")
    parser.add_argument("--ip-dir", required=True)
    parser.add_argument("--report", help=f"Report path relative to ip-dir. Default: {DEFAULT_REPORT}")
    parser.add_argument(
        "--legacy-no-scaffold",
        action="store_true",
        help="Treat the IP as an imported legacy tree: preserve existing source layout and validate the gap report without requiring an OAG scaffold.",
    )
    parser.add_argument(
        "--require-ontology",
        action="store_true",
        help="Fail when canonical requirements/obligations/contracts ontology files are absent.",
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    ip_dir = Path(args.ip_dir).expanduser().resolve()
    result = validate_report(
        ip_dir,
        report_path(ip_dir, args.report),
        require_ontology=args.require_ontology,
        legacy_no_scaffold=args.legacy_no_scaffold,
    )
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    elif result["status"] == "pass":
        print("PASS implementation review check")
    else:
        print("FAIL implementation review check", file=sys.stderr)
        for item in result["issues"]:
            suffix = f" ({item['path']})" if "path" in item else ""
            print(f"- {item['code']}: {item['message']}{suffix}", file=sys.stderr)
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
