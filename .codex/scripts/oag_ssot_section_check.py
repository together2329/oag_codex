#!/usr/bin/env python3
"""Check required OAG SSOT sections across ROCEV and IP-XACT-style metadata."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import oag_paths  # noqa: E402
from oag_run_control_common import file_info, issue  # noqa: E402


SCHEMA_VERSION = "oag_ssot_section_check.v1"

SECTION_REQUIREMENTS: tuple[dict[str, Any], ...] = (
    {"id": "features", "path": "ontology/features.yaml", "category": "product", "hard_from": "planning"},
    {"id": "source_claims", "path": "req/source_claims.yaml", "category": "intake", "hard_from": "planning"},
    {"id": "ambiguity_register", "path": "req/ambiguity_register.yaml", "category": "intake", "hard_from": "planning"},
    {"id": "decision_matrix", "path": "ontology/decision_matrix.yaml", "category": "decision", "hard_from": "planning"},
    {"id": "requirement_atoms", "path": "ontology/requirement_atoms.yaml", "category": "requirements", "hard_from": "planning"},
    {"id": "requirements", "path": "ontology/requirements.yaml", "category": "requirements", "hard_from": "planning"},
    {"id": "obligations", "path": "ontology/obligations.yaml", "category": "rocev", "hard_from": "pre-dispatch"},
    {"id": "contracts", "path": "ontology/contracts.yaml", "category": "rocev", "hard_from": "pre-dispatch"},
    {"id": "modeling", "path": "ontology/modeling.yaml", "category": "behavior_authority", "hard_from": "pre-dispatch"},
    {"id": "verification_plan", "path": "ontology/verification_plan.yaml", "category": "verification", "hard_from": "pre-dispatch"},
    {"id": "tb_methodology", "path": "ontology/tb_methodology.yaml", "category": "verification", "hard_from": "pre-dispatch"},
    {"id": "ipxact_projection", "path": "ontology/ipxact_projection.yaml", "category": "integration_metadata", "hard_from": "pre-dispatch"},
)

STAGE_ORDER = {"planning": 0, "pre-dispatch": 1, "closure": 2}


def _stage_index(stage: str) -> int:
    return STAGE_ORDER[stage]


def _hard(stage: str, hard_from: str) -> bool:
    return _stage_index(stage) >= _stage_index(hard_from)


def _dir_has_json(path: Path) -> bool:
    return path.is_dir() and any(child.is_file() and child.suffix == ".json" for child in path.iterdir())


def _gate_decision_present(ip_dir: Path) -> bool:
    candidates = [
        oag_paths.legacy_or_hidden(ip_dir, "knowledge/gate_reviews/oag_gate_decision.json"),
        oag_paths.legacy_or_hidden(ip_dir, "knowledge/decisions"),
    ]
    return candidates[0].is_file() or _dir_has_json(candidates[1])


def check(ip_dir: Path, *, stage: str) -> dict[str, Any]:
    ip_dir = oag_paths.ip_root(ip_dir)
    if not ip_dir.is_dir():
        return {"schema_version": SCHEMA_VERSION, "status": "fail", "issues": [issue("IP_DIR_MISSING", "IP directory does not exist", str(ip_dir))]}
    issues: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []
    rows: list[dict[str, Any]] = []
    for req in SECTION_REQUIREMENTS:
        info = file_info(ip_dir, req["path"])
        hard = _hard(stage, req["hard_from"])
        state = "present"
        if not info["exists"]:
            state = "missing"
            target = issues if hard else warnings
            target.append(issue("SSOT_SECTION_MISSING", f"required SSOT section is missing: {req['id']}", req["path"]))
        elif info["bytes"] == 0:
            state = "empty"
            target = issues if hard else warnings
            target.append(issue("SSOT_SECTION_EMPTY", f"required SSOT section is empty: {req['id']}", req["path"]))
        rows.append({**req, **info, "state": state, "hard": hard})

    records_dir = oag_paths.legacy_or_hidden(ip_dir, "knowledge/records")
    has_records = _dir_has_json(records_dir)
    records_hard = stage == "closure"
    if not has_records:
        target = issues if records_hard else warnings
        target.append(issue("SSOT_EVIDENCE_RECORDS_MISSING", "knowledge/records must contain validation/evidence JSON records before closure", str(records_dir)))
    rows.append(
        {
            "id": "evidence_records",
            "path": str(records_dir),
            "category": "evidence",
            "state": "present" if has_records else "missing",
            "hard": records_hard,
        }
    )

    has_gate = _gate_decision_present(ip_dir)
    gate_hard = stage == "closure"
    if not has_gate:
        target = issues if gate_hard else warnings
        target.append(issue("SSOT_GATE_DECISION_MISSING", "a gate decision record is required before closure", "knowledge/gate_reviews/oag_gate_decision.json"))
    rows.append(
        {
            "id": "gate_decisions",
            "path": "knowledge/gate_reviews/oag_gate_decision.json",
            "category": "decision",
            "state": "present" if has_gate else "missing",
            "hard": gate_hard,
        }
    )

    return {
        "schema_version": SCHEMA_VERSION,
        "status": "fail" if issues else "pass",
        "ip": ip_dir.name,
        "stage": stage,
        "counts": {
            "sections": len(rows),
            "issues": len(issues),
            "warnings": len(warnings),
            "present": sum(1 for row in rows if row["state"] == "present"),
            "missing": sum(1 for row in rows if row["state"] == "missing"),
            "empty": sum(1 for row in rows if row["state"] == "empty"),
        },
        "sections": rows,
        "issues": issues,
        "warnings": warnings,
        "next_actions": next_actions(stage, issues, warnings),
    }


def next_actions(stage: str, issues: list[dict[str, str]], warnings: list[dict[str, str]]) -> list[str]:
    if issues:
        return [
            "Repair hard-missing SSOT sections before moving to the next OAG stage.",
            "Use deep interview or decision matrix for planning gaps; use contract projection for obligation/contract gaps.",
            "Regenerate the review frame after edits so hashes match current source files.",
        ]
    if warnings:
        return [
            "Warnings are acceptable at this stage but must be resolved before closure.",
            "Keep evidence records and gate decisions separate from authored truth until validation is complete.",
        ]
    return [f"All required SSOT sections for {stage} are present."]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ip-dir", required=True)
    parser.add_argument("--stage", choices=sorted(STAGE_ORDER), default="planning")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        result = check(Path(args.ip_dir), stage=args.stage)
    except Exception as exc:
        result = {"schema_version": SCHEMA_VERSION, "status": "fail", "issues": [issue("EXCEPTION", str(exc))]}
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    elif result["status"] == "pass":
        print(f"PASS {SCHEMA_VERSION}")
    else:
        print(f"FAIL {SCHEMA_VERSION}", file=sys.stderr)
        for item in result.get("issues", []):
            print(f"- {item.get('code')}: {item.get('message')}", file=sys.stderr)
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
