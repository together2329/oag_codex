#!/usr/bin/env python3
"""Generate a safe draft wavefront plan from OAG Action candidates."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import oag_action_plan  # noqa: E402
import oag_paths  # noqa: E402
import oag_run_control_common as run_common  # noqa: E402
from oag_wavefront_core import WavefrontRun  # noqa: E402
from oag_wavefront_ops import PlanRequest, create_wavefront_run  # noqa: E402
from oag_validate_json import contextual_schema_issues  # noqa: E402


SCHEMA_VERSION = "oag_action_wavefront_draft.v1"
RESULT_SCHEMA_VERSION = "oag_action_wavefront_draft_result.v1"
MATERIALIZED_TEMPLATE_SCHEMA_VERSION = "oag_wavefront_template.v1"
ACTION_CATALOG = oag_action_plan.ACTION_CATALOG

JsonObject = dict[str, Any]


def issue(code: str, message: str, path: str = "") -> dict[str, str]:
    payload = {"code": code, "message": message}
    if path:
        payload["path"] = path
    return payload


def task_suffix(value: str) -> str:
    clean = re.sub(r"[^A-Za-z0-9_]+", "_", value).strip("_").upper()
    return clean[:72] or "ACTION"


def phase_kind(action_type: str, phase: str, owner_role: str) -> str:
    if action_type in {"ACT_SIMULATION_RUN", "ACT_EVIDENCE_VALIDATION", "ACT_GATE_REVIEW", "ACT_COVERAGE_REVIEW"}:
        return "integration"
    if owner_role.startswith("oag-"):
        return "write"
    if phase in {"sim", "gate", "evidence", "closure"}:
        return "integration"
    return "decision"


def ownership_mode(kind: str, action_type: str) -> str:
    if kind == "integration":
        return "integration_owner"
    if action_type in {"ACT_RTL_IMPLEMENTATION", "ACT_TB_IMPLEMENTATION", "ACT_PROJECT_CONTRACTS", "ACT_PROJECT_OBLIGATIONS", "ACT_PROJECT_REQUIREMENT_ATOMS", "ACT_ARCHITECTURE_PROJECTION"}:
        return "exclusive_file"
    return "none"


def safe_task_id(index: int, action_type: str) -> str:
    return f"W{index:02d}_{task_suffix(action_type)}"


def build_draft(ip_dir: Path, *, max_tasks: int = 8, refresh_plan: bool = True) -> JsonObject:
    ip_dir = oag_paths.ip_root(ip_dir)
    plan_result = oag_action_plan.build_plan(ip_dir, write=refresh_plan, run_semantic_checks=False)
    plan = plan_result.get("plan") if isinstance(plan_result.get("plan"), dict) else {}
    graph = plan_result.get("dependency_graph") if isinstance(plan_result.get("dependency_graph"), dict) else {}
    action_catalog, catalog_issues = oag_action_plan.load_action_catalog()
    candidates = [item for item in plan.get("candidates", []) if isinstance(item, dict)]
    ready = [item for item in candidates if item.get("status") == "ready"]
    selected = ready[:max_tasks]
    candidate_to_task: dict[str, str] = {}
    tasks: list[JsonObject] = []
    for index, candidate in enumerate(selected, start=1):
        action_type = str(candidate.get("action_type") or "")
        catalog = action_catalog.get(action_type, {})
        phase = str(catalog.get("phase") or "planning")
        owner = str(candidate.get("owner_role") or catalog.get("owner_role") or "main")
        kind = phase_kind(action_type, phase, owner)
        task_id = safe_task_id(index, action_type)
        candidate_to_task[str(candidate.get("id") or "")] = task_id
        target_objects = candidate.get("target_objects") if isinstance(candidate.get("target_objects"), dict) else {}
        tasks.append(
            {
                "task_id": task_id,
                "kind": kind,
                "phase": phase,
                "action_candidate_id": candidate.get("id") or "",
                "action_type": action_type,
                "agent_type": owner if owner.startswith("oag-") else "",
                "owner_role": owner,
                "target_objects": target_objects,
                "priority": candidate.get("priority") or "",
                "score": candidate.get("score") if isinstance(candidate.get("score"), dict) else {},
                "depends_on": [],
                "barrier_outputs": [f"{task_id.lower()}_ready"],
                "ownership_mode": ownership_mode(kind, action_type),
                "allowed_write_paths": [],
                "shared_artifacts": [],
                "may_claim_complete": False,
                "command": candidate.get("command") or "",
                "dispatch_create_hint": (
                    f"python3 .codex/scripts/oag_dispatch.py create --ip-dir <ip> --agent-type {owner} --stage {phase} --receipt-path <ip>/knowledge/subagents/<receipt>.json --json"
                    if owner.startswith("oag-")
                    else ""
                ),
            }
        )

    task_by_id = {task["task_id"]: task for task in tasks}
    for edge in graph.get("edges", []) if isinstance(graph.get("edges"), list) else []:
        if not isinstance(edge, dict):
            continue
        from_task = candidate_to_task.get(str(edge.get("from") or ""))
        to_task = candidate_to_task.get(str(edge.get("to") or ""))
        if not from_task or not to_task or from_task == to_task:
            continue
        deps = task_by_id[to_task].setdefault("depends_on", [])
        if isinstance(deps, list) and from_task not in deps:
            deps.append(from_task)

    barriers: list[JsonObject] = []
    for task in tasks:
        for dep in task.get("depends_on", []) if isinstance(task.get("depends_on"), list) else []:
            barriers.append({"from": dep, "to": task["task_id"], "kind": "task_dependency"})

    payload: JsonObject = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": run_common.utc_now(),
        "ip": ip_dir.name,
        "mission_template": plan.get("mission_template") or plan_result.get("mission_template") or "",
        "mission_instance_id": plan.get("mission_instance_id") or plan_result.get("mission_instance_id") or "",
        "source_action_candidates": run_common.rel_to_ip(ip_dir, oag_paths.generated_path(ip_dir, "action_candidates.json")),
        "source_action_graph": run_common.rel_to_ip(ip_dir, oag_paths.generated_path(ip_dir, "action_graph.json")),
        "tasks": tasks,
        "barriers": barriers,
        "dispatch_plan": [task for task in tasks if task.get("dispatch_create_hint")],
        "summary": {
            "candidate_count": len(candidates),
            "ready_candidate_count": len(ready),
            "task_count": len(tasks),
            "dispatch_task_count": sum(1 for task in tasks if task.get("dispatch_create_hint")),
            "dependency_count": len(barriers),
        },
        "issues": catalog_issues,
    }
    schema_issues = contextual_schema_issues(
        "oag_action_wavefront_draft.schema.json",
        payload,
        code_prefix="ACTION_WAVEFRONT_DRAFT_SCHEMA",
        document_path="ontology/generated/action_wavefront_draft.json",
    )
    payload["schema_issues"] = schema_issues
    return payload


def write_draft(ip_dir: Path, payload: JsonObject) -> Path:
    path = oag_paths.generated_path(ip_dir, "action_wavefront_draft.json")
    run_common.write_json(path, payload)
    return path


def _template_task_from_draft(task: JsonObject) -> JsonObject:
    kind = str(task.get("kind") or "read_only")
    if kind == "decision":
        kind = "read_only"
    return {
        "task_id": task.get("task_id") or "",
        "kind": kind,
        "phase": task.get("phase") or kind,
        "agent_type": task.get("agent_type") or "",
        "depends_on": task.get("depends_on") if isinstance(task.get("depends_on"), list) else [],
        "barrier_outputs": task.get("barrier_outputs") if isinstance(task.get("barrier_outputs"), list) else [],
        "allowed_write_paths": task.get("allowed_write_paths") if isinstance(task.get("allowed_write_paths"), list) else [],
        "shared_artifacts": task.get("shared_artifacts") if isinstance(task.get("shared_artifacts"), list) else [],
        "ownership_mode": task.get("ownership_mode") or ("none" if kind == "read_only" else "exclusive_file"),
        "may_claim_complete": False,
        "metadata": {
            "action_candidate_id": task.get("action_candidate_id") or "",
            "action_type": task.get("action_type") or "",
            "owner_role": task.get("owner_role") or "",
            "priority": task.get("priority") or "",
            "dispatch_create_hint": task.get("dispatch_create_hint") or "",
            "materialization_note": "Generated from Action candidates for reviewable wavefront planning. Claims and dispatches still require explicit parent orchestration.",
        },
    }


def wavefront_template_from_draft(draft: JsonObject, *, run_id: str) -> JsonObject:
    tasks = [_template_task_from_draft(task) for task in draft.get("tasks", []) if isinstance(task, dict)]
    return {
        "schema_version": MATERIALIZED_TEMPLATE_SCHEMA_VERSION,
        "name": f"action_wavefront_{run_id}",
        "description": "Materialized review graph generated from OAG Mission/Action candidates. This graph is a planning surface; it does not create dispatches or approve handoffs.",
        "tasks": tasks,
    }


def materialize_wavefront(
    ip_dir: Path,
    draft: JsonObject,
    *,
    run_id: str,
    barrier_tokens: list[str] | None = None,
    template_out: Path | None = None,
) -> JsonObject:
    if not run_id.strip():
        return {"status": "fail", "issues": [issue("RUN_ID_REQUIRED", "--materialize-run-id is required")]}
    template = wavefront_template_from_draft(draft, run_id=run_id)
    if template_out is None:
        template_path = oag_paths.generated_path(ip_dir, f"action_wavefront_template_{run_id}.json")
    else:
        template_path = template_out if template_out.is_absolute() else ip_dir / template_out
    run_common.write_json(template_path, template)
    plan = create_wavefront_run(
        PlanRequest(
            run=WavefrontRun(ip_dir, run_id),
            raw_tasks=template["tasks"],
            template=run_common.rel_to_ip(ip_dir, template_path),
            barrier_tokens=barrier_tokens or [],
        )
    )
    return {
        "status": plan.get("status"),
        "template_path": run_common.rel_to_ip(ip_dir, template_path),
        "template": template,
        "plan": plan,
        "issues": plan.get("issues") if isinstance(plan.get("issues"), list) else [],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ip-dir", required=True)
    parser.add_argument("--max-tasks", type=int, default=8)
    parser.add_argument("--no-refresh-plan", action="store_true")
    parser.add_argument("--no-write", action="store_true")
    parser.add_argument("--materialize-run-id", default="", help="Also create a wavefront run from the draft tasks.")
    parser.add_argument("--materialize-template-out", default="", help="Optional IP-relative output path for the generated wavefront template.")
    parser.add_argument("--barrier", action="append", default=[], help="Initial barrier token to seed when materializing.")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    ip_dir = oag_paths.ip_root(args.ip_dir)
    payload = build_draft(ip_dir, max_tasks=args.max_tasks, refresh_plan=not args.no_refresh_plan)
    path = Path("")
    if not args.no_write:
        path = write_draft(ip_dir, payload)
    issues = payload.get("issues", []) + payload.get("schema_issues", [])
    materialized: JsonObject = {}
    if args.materialize_run_id:
        materialized = materialize_wavefront(
            ip_dir,
            payload,
            run_id=args.materialize_run_id,
            barrier_tokens=args.barrier,
            template_out=Path(args.materialize_template_out) if args.materialize_template_out else None,
        )
        issues = issues + (materialized.get("issues") if isinstance(materialized.get("issues"), list) else [])
    result = {
        "schema_version": RESULT_SCHEMA_VERSION,
        "status": "fail" if issues else "pass",
        "ip": ip_dir.name,
        "written": not args.no_write,
        "path": run_common.rel_to_ip(ip_dir, path) if path else "",
        "materialized": materialized,
        "draft": payload,
        "issues": issues,
    }
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    elif result["status"] == "pass":
        print(f"PASS {RESULT_SCHEMA_VERSION}: {payload['summary']['task_count']} draft tasks")
    else:
        print(f"FAIL {RESULT_SCHEMA_VERSION}", file=sys.stderr)
        for item in issues:
            print(f"- {item.get('code')}: {item.get('message')}", file=sys.stderr)
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
