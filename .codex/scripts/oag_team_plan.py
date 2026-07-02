#!/usr/bin/env python3
"""Plan a bounded OAG Team Lead plus Worker workflow without spawning workers."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import oag_action_plan  # noqa: E402
import oag_orchestration_guard  # noqa: E402
import oag_paths  # noqa: E402
import oag_run_control_common as run_common  # noqa: E402
from oag_validate_json import contextual_schema_issues  # noqa: E402


PLAN_SCHEMA_VERSION = "oag_team_plan.v1"
RESULT_SCHEMA_VERSION = "oag_team_plan_result.v1"
TEAM_PLAN_REL = "knowledge/team_mode/team_plan.json"


JsonObject = dict[str, Any]


def _issue(code: str, message: str, path: str = "") -> dict[str, str]:
    payload = {"code": code, "message": message}
    if path:
        payload["path"] = path
    return payload


def _candidates(action_result: JsonObject) -> list[JsonObject]:
    plan = action_result.get("plan") if isinstance(action_result.get("plan"), dict) else {}
    rows = plan.get("candidates") if isinstance(plan.get("candidates"), list) else []
    return [row for row in rows if isinstance(row, dict)]


def _top_candidates(rows: list[JsonObject], limit: int = 4) -> list[JsonObject]:
    return rows[:limit]


def _text(value: Any) -> str:
    return str(value or "").strip()


def _candidate_blob(row: JsonObject) -> str:
    parts = [
        row.get("id"),
        row.get("action_type"),
        row.get("action_label"),
        row.get("owner_role"),
        row.get("recommendation_reason"),
        json.dumps(row.get("target_objects", {}), sort_keys=True),
        json.dumps(row.get("expected_effects", {}), sort_keys=True),
    ]
    return " ".join(_text(part) for part in parts).upper()


def _families(rows: list[JsonObject]) -> set[str]:
    families: set[str] = set()
    for row in rows:
        blob = _candidate_blob(row)
        for label in ("RTL", "TB", "SIM", "EVIDENCE", "VALIDATION", "GATE", "REVIEW", "DISPATCH", "WAVEFRONT"):
            if label in blob:
                families.add(label)
    return families


def _owner_roles(rows: list[JsonObject]) -> set[str]:
    return {_text(row.get("owner_role")) for row in rows if _text(row.get("owner_role"))}


def _score(rows: list[JsonObject]) -> tuple[int, list[JsonObject]]:
    top = _top_candidates(rows)
    score = 0
    reasons: list[JsonObject] = []

    if len(rows) >= 3:
        score += 2
        reasons.append({"dimension": "action_count", "points": 2, "reason": "three or more Mission/Action candidates exist"})
    elif len(rows) >= 2:
        score += 1
        reasons.append({"dimension": "action_count", "points": 1, "reason": "two Mission/Action candidates exist"})

    roles = _owner_roles(top)
    if len(roles) >= 2:
        score += 2
        reasons.append({"dimension": "role_split", "points": 2, "reason": f"multiple owner roles appear in top candidates: {sorted(roles)}"})
    elif roles and roles != {"main"}:
        score += 1
        reasons.append({"dimension": "role_split", "points": 1, "reason": f"non-main owner role appears: {sorted(roles)}"})

    families = _families(top)
    if {"RTL", "TB"}.issubset(families):
        score += 2
        reasons.append({"dimension": "write_scope_split", "points": 2, "reason": "RTL and TB work can be separated"})
    elif len(families) >= 2:
        score += 2
        reasons.append({"dimension": "write_scope_split", "points": 2, "reason": f"multiple work families appear: {sorted(families)}"})
    elif families:
        score += 1
        reasons.append({"dimension": "write_scope_split", "points": 1, "reason": f"one specialized work family appears: {sorted(families)}"})

    option_words = ("OPTION", "ARCHITECT", "RESEARCH", "EXPLORE", "REVIEW", "PARAMETER")
    if any(row.get("action_type") == oag_action_plan.SELF_EXPLORE_ACTION or any(word in _candidate_blob(row) for word in option_words) for row in top):
        score += 1
        reasons.append({"dimension": "architecture_optioning", "points": 1, "reason": "top candidates include exploration, review, optioning, or parameterization"})

    long_words = ("REGRESSION", "SIM", "COVERAGE", "FORMAL", "VALIDATION", "EVIDENCE")
    if any(any(word in _candidate_blob(row) for word in long_words) for row in top):
        score += 1
        reasons.append({"dimension": "long_running_work", "points": 1, "reason": "top candidates include simulation, coverage, validation, or evidence work"})

    return score, reasons


def _blockers(state: JsonObject, guard: JsonObject) -> list[JsonObject]:
    rows: list[JsonObject] = []
    active_lock_count = int(state.get("wavefront", {}).get("active_lock_count", 0) or 0)
    pending_gate_count = int(state.get("gates", {}).get("pending_gate_count", 0) or 0)
    if active_lock_count:
        rows.append({"code": "ACTIVE_WAVEFRONT_LOCKS", "message": "active wavefront locks must be resolved before opening worker execution", "count": active_lock_count})
    if pending_gate_count:
        rows.append({"code": "PENDING_WORKFLOW_GATES", "message": "pending workflow gates must be resolved before opening worker execution", "count": pending_gate_count})
    if guard.get("status") == "fail":
        for item in guard.get("issues", []) if isinstance(guard.get("issues"), list) else []:
            if isinstance(item, dict):
                rows.append({"code": f"ORCHESTRATION_{item.get('code', 'ISSUE')}", "message": str(item.get("message") or item), "path": item.get("path") or ""})
    return rows


def _recommendation(score: int, blockers: list[JsonObject], rows: list[JsonObject]) -> JsonObject:
    if blockers:
        return {
            "mode": "blocked",
            "score": score,
            "reason": "worker execution is blocked by active orchestration state; Team Lead must resolve blockers first",
        }
    if score >= 6:
        return {
            "mode": "team_plan_recommended",
            "score": score,
            "reason": "the next work has enough role, scope, or review complexity to justify Team Lead plus Worker planning",
        }
    if score >= 3:
        return {
            "mode": "team_plan_optional",
            "score": score,
            "reason": "team splitting may help, but the Team Lead can still execute the next step locally",
        }
    if rows:
        return {
            "mode": "default",
            "score": score,
            "reason": "the recommended next action is narrow enough for the Team Lead",
        }
    return {
        "mode": "default",
        "score": score,
        "reason": "no worker-worthy Mission/Action candidate is currently available",
    }


def _team(mode: str) -> JsonObject:
    workers: list[JsonObject] = []
    if mode in {"team_plan_optional", "team_plan_recommended"}:
        workers.append(
            {
                "role": "Worker",
                "owner": "bounded_subagent_after_approval",
                "count": 1,
                "responsibilities": [
                    "perform exactly one approved OAG task",
                    "stay inside dispatch or wavefront ownership scope",
                    "write a receipt with changed paths, commands, evidence, and blockers",
                    "never claim final completion or gate approval",
                ],
            }
        )
    return {
        "lead": {
            "role": "Team Lead",
            "owner": "main",
            "responsibilities": [
                "preserve user intent and ask at most one required question",
                "read OAG state, Mission/Action candidates, and orchestration guard output",
                "prepare dispatch or wavefront only after execution approval",
                "review Worker receipts before accepting handoff",
                "own final report and closure claims",
            ],
        },
        "workers": workers,
    }


def _tasks(mode: str, rows: list[JsonObject]) -> list[JsonObject]:
    tasks: list[JsonObject] = [
        {
            "task_id": "TEAM_LEAD_CONTEXT_AUDIT",
            "role": "Team Lead",
            "status": "planned",
            "description": "Audit current OAG state, blockers, recommended Mission/Action candidate, and whether user approval is needed.",
            "may_claim_complete": False,
        }
    ]
    recommended = next((row for row in rows if row.get("recommended") is True), rows[0] if rows else {})
    if mode in {"team_plan_optional", "team_plan_recommended"} and recommended:
        tasks.append(
            {
                "task_id": "WORKER_001",
                "role": "Worker",
                "status": "draft_not_dispatched",
                "source_candidate_id": recommended.get("id") or "",
                "action_type": recommended.get("action_type") or "",
                "owner_role": recommended.get("owner_role") or "",
                "description": recommended.get("recommendation_reason") or "Execute one bounded task after explicit dispatch approval.",
                "allowed_write_policy": "no writes until an OAG dispatch or wavefront claim exists",
                "depends_on": ["TEAM_LEAD_CONTEXT_AUDIT"],
                "may_claim_complete": False,
            }
        )
    elif recommended:
        tasks.append(
            {
                "task_id": "TEAM_LEAD_NEXT_ACTION",
                "role": "Team Lead",
                "status": "planned",
                "source_candidate_id": recommended.get("id") or "",
                "action_type": recommended.get("action_type") or "",
                "description": recommended.get("recommendation_reason") or "Handle the recommended action locally.",
                "may_claim_complete": False,
            }
        )
    return tasks


def build_team_plan(ip_dir_arg: str | Path, *, write: bool = True, quick: bool = True, stuck_seconds: int = 900) -> JsonObject:
    ip_dir = oag_paths.ip_root(ip_dir_arg)
    if not ip_dir.is_dir():
        plan = {
            "schema_version": PLAN_SCHEMA_VERSION,
            "status": "fail",
            "generated_at": run_common.utc_now(),
            "ip": ip_dir.name,
            "ip_dir": str(ip_dir),
            "recommendation": {"mode": "blocked", "score": 0, "reason": "IP directory does not exist"},
            "team": _team("blocked"),
            "tasks": [],
            "stop_conditions": ["create or select a valid IP directory first"],
            "issues": [_issue("IP_DIR_MISSING", "IP directory does not exist", str(ip_dir))],
            "no_spawn": True,
        }
        return {
            "schema_version": RESULT_SCHEMA_VERSION,
            "status": "fail",
            "ip": ip_dir.name,
            "output_path": "",
            "written": False,
            "plan": plan,
            "issues": plan["issues"],
        }

    state = run_common.collect_run_state(ip_dir)
    guard = oag_orchestration_guard.audit(ip_dir, stale_seconds=stuck_seconds)
    action_result = oag_action_plan.build_plan(ip_dir, write=False, run_semantic_checks=not quick, stuck_seconds=stuck_seconds)
    rows = _candidates(action_result)
    score, score_breakdown = _score(rows)
    blockers = _blockers(state, guard)
    recommendation = _recommendation(score, blockers, rows)
    mode = str(recommendation["mode"])
    issues: list[JsonObject] = []
    if action_result.get("status") == "fail":
        for item in action_result.get("issues", []) if isinstance(action_result.get("issues"), list) else []:
            if isinstance(item, dict):
                issues.append({"code": f"ACTION_PLAN_{item.get('code', 'ISSUE')}", "message": str(item.get("message") or item), "path": item.get("path") or ""})
    issues.extend(blockers)

    status = "blocked" if mode == "blocked" else "pass"
    if action_result.get("status") == "fail":
        status = "fail"

    plan: JsonObject = {
        "schema_version": PLAN_SCHEMA_VERSION,
        "status": status,
        "generated_at": run_common.utc_now(),
        "ip": ip_dir.name,
        "ip_dir": str(ip_dir),
        "recommendation": recommendation,
        "score_breakdown": score_breakdown,
        "team": _team(mode),
        "tasks": _tasks(mode, rows),
        "source": {
            "action_plan_status": action_result.get("status") or "",
            "action_plan_candidate_count": len(rows),
            "recommended_action": action_result.get("recommended_action") or {},
            "run_state_summary": {
                "scope_lock": state.get("scope_lock", {}).get("state"),
                "compile_manifest": state.get("compile_manifest", {}).get("status"),
                "active_lock_count": state.get("wavefront", {}).get("active_lock_count", 0),
                "pending_gate_count": state.get("gates", {}).get("pending_gate_count", 0),
                "ssot_status": state.get("ssot", {}).get("status"),
            },
            "orchestration_guard_status": guard.get("status") or "",
        },
        "stop_conditions": [
            "Team Mode v1 is plan-only; do not spawn a Worker from this plan",
            "create dispatch or wavefront claim only after explicit execution approval",
            "resolve active locks or pending gates before replacement work",
            "Worker tasks must keep may_claim_complete=false",
            "Team Lead owns final report, closure, gate, and signoff claims",
        ],
        "issues": issues,
        "no_spawn": True,
    }
    schema_issues = contextual_schema_issues(
        "oag_team_plan.schema.json",
        plan,
        code_prefix="TEAM_PLAN_SCHEMA",
        document_path=TEAM_PLAN_REL,
    )
    plan["schema_issues"] = schema_issues
    if schema_issues:
        plan["status"] = "fail"
        issues.extend(schema_issues)

    output_path = oag_paths.state_path(ip_dir, TEAM_PLAN_REL)
    if write:
        run_common.write_json(output_path, plan)
    return {
        "schema_version": RESULT_SCHEMA_VERSION,
        "status": plan["status"],
        "ip": ip_dir.name,
        "output_path": run_common.rel_to_ip(ip_dir, output_path),
        "written": write,
        "plan": plan,
        "issues": issues,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ip-dir", required=True)
    parser.add_argument("--no-write", action="store_true")
    parser.add_argument("--full", action="store_true", help="Run semantic Mission/Action checks before scoring.")
    parser.add_argument("--stuck-seconds", type=int, default=900)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    result = build_team_plan(args.ip_dir, write=not args.no_write, quick=not args.full, stuck_seconds=args.stuck_seconds)
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    elif result["status"] in {"pass", "blocked"}:
        plan = result.get("plan", {})
        rec = plan.get("recommendation", {}) if isinstance(plan, dict) else {}
        print(f"{result['status'].upper()} {RESULT_SCHEMA_VERSION}: {rec.get('mode', 'unknown')} score={rec.get('score', 0)}")
        if result.get("written"):
            print(f"Wrote {result['output_path']}")
    else:
        print(f"FAIL {RESULT_SCHEMA_VERSION}", file=sys.stderr)
        for item in result.get("issues", []):
            if isinstance(item, dict):
                print(f"- {item.get('code')}: {item.get('message')}", file=sys.stderr)
    return 1 if result["status"] == "fail" else 0


if __name__ == "__main__":
    raise SystemExit(main())
