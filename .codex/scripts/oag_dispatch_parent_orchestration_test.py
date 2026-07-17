#!/usr/bin/env python3
"""Focused regression for dispatch-linked parent Action/Mission deltas."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


SCRIPTS_DIR = Path(__file__).resolve().parent
DISPATCH_CLI = SCRIPTS_DIR / "oag_dispatch.py"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from oag_dispatch_support import dispatch_integrity  # noqa: E402


JsonObject = dict[str, Any]
RUN_ID = "RUN_PARENT_LINK_TEST"
TASK_ID = "RTL_PARENT_LINK_TEST"
SIBLING_TASK_ID = "RTL_SIBLING_REVIEW"
DISPATCH_ID = "DISPATCH_PARENT_LINK_TEST_20260716T000000Z_ABCD1234"
SIBLING_BASE_DISPATCH_ID = "DISPATCH_SIBLING_BASE_20260715T235900Z_ABCD1234"
SIBLING_REPAIR1_DISPATCH_ID = "DISPATCH_SIBLING_REPAIR1_20260716T000200Z_ABCD1234"
SIBLING_REPAIR2_DISPATCH_ID = "DISPATCH_SIBLING_REPAIR2_20260716T000400Z_ABCD1234"
ACTION_ID = "ACT_RUN_20260716T000000Z_PARENT_LINK_TEST"
MISSION_ID = "MISSION_RUN_20260716T000000Z_PARENT_LINK_TEST"
DECISION_ID = "DEC_RTL_CONFORMANCE_RTL_SIBLING_REVIEW_20260716T000100Z"
APPROVED_DECISION_ID = "DEC_RTL_CONFORMANCE_RTL_SIBLING_REVIEW_20260716T000600Z"
CURRENT_DECISION_ID = "DEC_RTL_CONFORMANCE_RTL_PARENT_LINK_TEST_20260716T000005Z"
CURRENT_REPAIR_DECISION_ID = "DEC_RTL_CONFORMANCE_RTL_PARENT_LINK_TEST_REPAIR_20260716T000005Z"
REPAIR_DECISION_CASES = {
    "repair_rejection_claimed",
    "repair_rejection_bad_output_hash_format",
    "repair_rejection_future_timestamp",
    "repair_rejection_malformed",
    "repair_rejection_missing_review",
    "repair_rejection_plus_arbitrary",
    "repair_rejection_wrong_run",
    "repair_rejection_wrong_task",
}
CURRENT_REPAIR_DECISION_CASES = {
    "current_repair_rejection_claimed",
    "current_repair_rejection_future_timestamp",
    "current_repair_rejection_interim_receipt",
    "current_repair_rejection_malformed",
    "current_repair_rejection_unrecorded",
}


def write_json(path: Path, payload: JsonObject) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def relative(project: Path, path: Path) -> str:
    return path.resolve().relative_to(project.resolve()).as_posix()


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def file_hashes(project: Path, ip: Path) -> dict[str, str]:
    return {
        relative(project, path): sha256(path)
        for path in sorted(ip.rglob("*"))
        if path.is_file() and ".git" not in path.parts
    }


def action_payload(*, linked: bool, task_id: str = TASK_ID, mission_ids: list[str] | None = None) -> JsonObject:
    result: JsonObject = {"summary": "parent action baseline"}
    if linked:
        result.update(
            {
                "dispatch_ids": [DISPATCH_ID],
                "wavefront_refs": [
                    {
                        "dispatch_id": DISPATCH_ID,
                        "run_id": RUN_ID,
                        "task_id": task_id,
                        "path": "rtl/worker.sv",
                    }
                ],
            }
        )
    return {
        "schema_version": "oag_action_instance.v1",
        "id": ACTION_ID,
        "action_type": "ACT_RTL_IMPLEMENTATION",
        "mission_instance_refs": list(mission_ids if mission_ids is not None else [MISSION_ID]),
        "status": "running",
        "selected_by": {"kind": "agent", "id": "parent"},
        "selected_reason": "focused regression",
        "started_at": "2026-07-16T00:00:00Z",
        "target_objects": {},
        "result": result,
    }


def mission_payload(mission_id: str, action_ids: list[str]) -> JsonObject:
    return {
        "schema_version": "oag_mission_instance.v1",
        "id": mission_id,
        "template_id": "MISSION_RTL_READY_TO_IMPLEMENTED",
        "status": "active",
        "started_at": "2026-07-16T00:00:00Z",
        "last_observed_at": "2026-07-16T00:00:01Z",
        "target_state": {},
        "current_open_items": [],
        "current_recommended_action": {},
        "action_instance_refs": action_ids,
        "observations": [],
    }


def action_index(ip: Path, actions: list[JsonObject]) -> JsonObject:
    rows = [
        {
            "id": action["id"],
            "action_type": action.get("action_type", ""),
            "candidate_ref": action.get("candidate_ref", ""),
            "path": f"{action['id']}.json",
            "status": action["status"],
            "mission_instance_refs": action["mission_instance_refs"],
            "started_at": action.get("started_at", ""),
            "completed_at": action.get("completed_at", ""),
            "selected_reason": action.get("selected_reason", ""),
            "summary": action.get("result", {}).get("summary", ""),
        }
        for action in actions
    ]
    return {
        "schema_version": "oag_action_index.v1",
        "generated_at": "2026-07-16T00:00:02Z",
        "ip": ip.name,
        "actions": rows,
        "counts": {"total": len(rows), "open": len(rows), "terminal": 0},
    }


def mission_index(ip: Path, missions: list[JsonObject]) -> JsonObject:
    rows = [
        {
            "id": mission["id"],
            "path": f"{mission['id']}.json",
            "template_id": mission.get("template_id", ""),
            "status": mission["status"],
            "started_at": mission.get("started_at", ""),
            "last_observed_at": mission.get("last_observed_at", ""),
            "completed_at": mission.get("completed_at", ""),
            "action_count": len(mission["action_instance_refs"]),
            "current_recommended_action_type": mission.get("current_recommended_action", {}).get("action_type"),
        }
        for mission in missions
    ]
    return {
        "schema_version": "oag_mission_index.v1",
        "generated_at": "2026-07-16T00:00:02Z",
        "ip": ip.name,
        "missions": rows,
        "counts": {"total": len(rows), "active": len(rows), "terminal": 0},
    }


def wavefront_task(task_id: str, *, write_path: str) -> JsonObject:
    return {
        "task_id": task_id,
        "kind": "write",
        "phase": "rtl",
        "depends_on": [],
        "barrier_inputs": [],
        "barrier_outputs": [],
        "allowed_write_paths": [write_path],
        "shared_artifacts": [],
        "stale_if_paths_changed": [],
        "ownership_mode": "exclusive_file",
        "status": "claimed",
        "patience_budget_seconds": 900,
        "may_claim_complete": False,
    }


def decision_payload(*, decision_id: str = DECISION_ID, summary: str = "sibling review rejected") -> JsonObject:
    return {
        "schema_version": "oag_wavefront_decision.v1",
        "product_name": "IP Dev Agent",
        "internal_gateway": "Ontology Agent Gateway",
        "decision_id": decision_id,
        "decision_type": "rtl_conformance",
        "target": {
            "kind": "wavefront_task",
            "run_id": RUN_ID,
            "task_id": SIBLING_TASK_ID,
        },
        "verdict": "rejected",
        "rationale": {
            "summary": summary,
            "checked_against": ["rtl/sibling.sv"],
            "preserved": [],
            "blockers": ["repair required"],
        },
        "reviewer": {"kind": "ai", "id": "focused-test-reviewer"},
        "unlocks": {"wavefront_status": "failed", "barrier_outputs": []},
        "created_at": "2026-07-16T00:01:00Z",
    }


def repair_decision_payload() -> JsonObject:
    payload = decision_payload(summary="sibling review rejected for in-place repair")
    payload["unlocks"]["wavefront_status"] = "claimed"
    return payload


def approved_decision_payload() -> JsonObject:
    return {
        "schema_version": "oag_wavefront_decision.v1",
        "product_name": "IP Dev Agent",
        "internal_gateway": "Ontology Agent Gateway",
        "decision_id": APPROVED_DECISION_ID,
        "decision_type": "rtl_conformance",
        "target": {
            "kind": "wavefront_task",
            "run_id": RUN_ID,
            "task_id": SIBLING_TASK_ID,
        },
        "verdict": "approved",
        "rationale": {
            "summary": "sibling repair approved",
            "checked_against": ["rtl/sibling.sv"],
            "preserved": [],
            "blockers": [],
        },
        "reviewer": {"kind": "ai", "id": "focused-test-reviewer"},
        "unlocks": {"wavefront_status": "handoff_pass", "barrier_outputs": ["rtl_sibling_ready"]},
        "created_at": "2026-07-16T00:06:00Z",
    }


def wavefront_event(event: str, created_at: str, **extra: Any) -> JsonObject:
    return {
        "schema_version": "oag_wavefront_event.v1",
        "product_name": "IP Dev Agent",
        "internal_gateway": "Ontology Agent Gateway",
        "run_id": RUN_ID,
        "event": event,
        "created_at": created_at,
        **extra,
    }


def sibling_dispatch_payload(
    project: Path,
    ip: Path,
    *,
    dispatch_id: str,
    receipt_name: str,
    created_at: str,
    run_id: str = RUN_ID,
) -> JsonObject:
    dispatch_path = ip / "knowledge" / "dispatches" / f"{dispatch_id}.json"
    receipt_path = ip / "knowledge" / "subagents" / receipt_name
    payload: JsonObject = {
        "schema_version": "oag_dispatch.v1",
        "product_name": "IP Dev Agent",
        "internal_gateway": "Ontology Agent Gateway",
        "dispatch_id": dispatch_id,
        "dispatch_path": relative(project, dispatch_path),
        "agent_type": "oag-custom-worker",
        "role_name": "oag-custom-worker",
        "role_kind": "custom",
        "registered_id": "oag-custom-worker",
        "ip_id": ip.name,
        "ip_dir": relative(project, ip),
        "stage": "rtl",
        "owned_obligations": [],
        "contracts": [],
        "allowed_write_paths": [relative(project, ip / "rtl" / "sibling.sv")],
        "allowed_tool_side_effects": [],
        "receipt_path": relative(project, receipt_path),
        "may_claim_complete": False,
        "wavefront_run_id": run_id,
        "task_id": SIBLING_TASK_ID,
        "ownership_mode": "exclusive_file",
        "baseline": {
            "created_at": created_at,
            "git_status_paths": [],
            "file_hashes": {},
        },
        "created_at": created_at,
    }
    payload["dispatch_integrity"] = dispatch_integrity(payload)
    return payload


def sibling_receipt_payload(
    dispatch: JsonObject,
    *,
    created_at: str,
    dispatch_verified: bool,
) -> JsonObject:
    return {
        "schema_version": "oag_subagent_receipt.v1",
        "product_name": "IP Dev Agent",
        "internal_gateway": "Ontology Agent Gateway",
        "ip_id": dispatch["ip_id"],
        "dispatch_id": dispatch["dispatch_id"],
        "dispatch_path": dispatch["dispatch_path"],
        "role_name": dispatch["role_name"],
        "registered_id": dispatch["registered_id"],
        "shard_scope": "rtl/sibling.sv",
        "stage": dispatch["stage"],
        "status": "RTL_HANDOFF_PASS",
        "owned_obligations": [],
        "contracts": [],
        "allowed_write_paths": dispatch["allowed_write_paths"],
        "changed_paths": dispatch["allowed_write_paths"],
        "generated_side_effects": [],
        "evidence_outputs": [dispatch["receipt_path"]],
        "diagnostic_only": False,
        "covers_writes": True,
        "dispatch_verified": dispatch_verified,
        "implementation_evidence": True,
        "may_claim_complete": False,
        "wavefront_run_id": dispatch["wavefront_run_id"],
        "task_id": dispatch["task_id"],
        "ownership_mode": dispatch["ownership_mode"],
        "created_at": created_at,
    }


def append_json_line(path: Path, payload: JsonObject) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True) + "\n")


def initialize_project(project: Path) -> tuple[Path, Path, Path]:
    project.mkdir(parents=True)
    subprocess.run(["git", "init", "-q"], cwd=project, check=True)
    subprocess.run(["git", "config", "user.name", "OAG Test"], cwd=project, check=True)
    subprocess.run(["git", "config", "user.email", "oag-test@example.com"], cwd=project, check=True)
    ip = project / "parent_link_ip"
    action_path = ip / "knowledge" / "actions" / f"{ACTION_ID}.json"
    mission_path = ip / "knowledge" / "missions" / f"{MISSION_ID}.json"
    initial_action = action_payload(linked=False)
    initial_mission = mission_payload(MISSION_ID, [ACTION_ID])
    write_json(action_path, initial_action)
    write_json(ip / "knowledge" / "actions" / "_index.json", action_index(ip, [initial_action]))
    write_json(mission_path, initial_mission)
    write_json(ip / "knowledge" / "missions" / "_index.json", mission_index(ip, [initial_mission]))
    sibling_base_dispatch = sibling_dispatch_payload(
        project,
        ip,
        dispatch_id=SIBLING_BASE_DISPATCH_ID,
        receipt_name="sibling.json",
        created_at="2026-07-15T23:59:00Z",
    )
    write_json(
        ip / "knowledge" / "dispatches" / f"{SIBLING_BASE_DISPATCH_ID}.json",
        sibling_base_dispatch,
    )
    write_json(
        ip / "knowledge" / "subagents" / "sibling.json",
        sibling_receipt_payload(
            sibling_base_dispatch,
            created_at="2026-07-15T23:59:30Z",
            dispatch_verified=True,
        ),
    )
    stable_path = ip / "rtl" / "stable.sv"
    stable_path.parent.mkdir(parents=True, exist_ok=True)
    stable_path.write_text("module stable; endmodule\n", encoding="utf-8")
    write_json(
        ip / "ontology" / "runs" / RUN_ID / "wavefront_task_graph.json",
        {
            "schema_version": "oag_wavefront_task_graph.v1",
            "product_name": "IP Dev Agent",
            "internal_gateway": "Ontology Agent Gateway",
            "run_id": RUN_ID,
            "ip_id": ip.name,
            "ip_dir": relative(project, ip),
            "tasks": [wavefront_task(TASK_ID, write_path="rtl/worker.sv")],
            "created_at": "2026-07-16T00:00:00Z",
            "updated_at": "2026-07-16T00:00:00Z",
        },
    )
    write_json(
        ip / "ontology" / "runs" / RUN_ID / "ownership_locks.json",
        {
            "schema_version": "oag_ownership_locks.v1",
            "product_name": "IP Dev Agent",
            "internal_gateway": "Ontology Agent Gateway",
            "run_id": RUN_ID,
            "ip_id": ip.name,
            "locks": [
                {
                    "task_id": TASK_ID,
                    "path": "rtl/worker.sv",
                    "mode": "exclusive_file",
                    "dispatch_id": DISPATCH_ID,
                    "claimed_at": "2026-07-16T00:00:00Z",
                }
            ],
            "updated_at": "2026-07-16T00:00:00Z",
        },
    )
    append_json_line(
        ip / "knowledge" / "wavefront" / RUN_ID / "events.jsonl",
        wavefront_event("planned", "2026-07-16T00:00:00Z", details={"task_ids": [TASK_ID]}),
    )
    subprocess.run(["git", "add", "."], cwd=project, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "baseline"], cwd=project, check=True)
    return ip, action_path, mission_path


def commit_state(project: Path, message: str) -> None:
    subprocess.run(["git", "add", "-A"], cwd=project, check=True)
    subprocess.run(["git", "commit", "-q", "-m", message], cwd=project, check=True)


def write_dispatch(project: Path, ip: Path, *, wavefront: bool) -> tuple[Path, Path, JsonObject]:
    dispatch_path = ip / "knowledge" / "dispatches" / f"{DISPATCH_ID}.json"
    receipt_path = ip / "knowledge" / "subagents" / "parent_link_receipt.json"
    worker_path = ip / "rtl" / "worker.sv"
    dispatch: JsonObject = {
        "schema_version": "oag_dispatch.v1",
        "product_name": "IP Dev Agent",
        "internal_gateway": "Ontology Agent Gateway",
        "dispatch_id": DISPATCH_ID,
        "dispatch_path": relative(project, dispatch_path),
        "agent_type": "oag-custom-worker",
        "role_name": "oag-custom-worker",
        "role_kind": "custom",
        "registered_id": "oag-custom-worker",
        "ip_id": ip.name,
        "ip_dir": relative(project, ip),
        "stage": "rtl",
        "owned_obligations": [],
        "contracts": [],
        "allowed_write_paths": [relative(project, worker_path)],
        "allowed_tool_side_effects": [
            relative(project, ip / "ontology" / "runs" / RUN_ID) + "/",
            relative(project, ip / "knowledge" / "wavefront" / RUN_ID) + "/",
        ] if wavefront else [],
        "receipt_path": relative(project, receipt_path),
        "may_claim_complete": False,
        "wavefront_run_id": RUN_ID if wavefront else "",
        "task_id": TASK_ID if wavefront else "",
        "ownership_mode": "exclusive_file" if wavefront else "",
        "baseline": {
            "created_at": "2026-07-16T00:00:00Z",
            "git_status_paths": [],
            "file_hashes": file_hashes(project, ip),
        },
        "created_at": "2026-07-16T00:00:00Z",
    }
    dispatch["dispatch_integrity"] = dispatch_integrity(dispatch)
    write_json(dispatch_path, dispatch)
    return dispatch_path, receipt_path, dispatch


def write_receipt(
    project: Path,
    ip: Path,
    path: Path,
    dispatch: JsonObject,
    *,
    wavefront: bool,
    claim_parent: bool,
    claim_decision: bool,
) -> None:
    worker_path = ip / "rtl" / "worker.sv"
    changed_paths = [relative(project, worker_path)]
    if claim_parent:
        changed_paths.append(relative(project, ip / "knowledge" / "actions" / f"{ACTION_ID}.json"))
    if claim_decision:
        changed_paths.append(relative(project, ip / "knowledge" / "decisions" / f"{DECISION_ID}.json"))
    receipt: JsonObject = {
        "schema_version": "oag_subagent_receipt.v1",
        "product_name": "IP Dev Agent",
        "internal_gateway": "Ontology Agent Gateway",
        "ip_id": ip.name,
        "dispatch_id": DISPATCH_ID,
        "dispatch_path": dispatch["dispatch_path"],
        "role_name": dispatch["role_name"],
        "registered_id": dispatch["registered_id"],
        "shard_scope": "rtl/worker.sv",
        "stage": dispatch["stage"],
        "status": "RTL_HANDOFF_PASS",
        "owned_obligations": [],
        "contracts": [],
        "allowed_write_paths": dispatch["allowed_write_paths"],
        "changed_paths": changed_paths,
        "generated_side_effects": [],
        "evidence_outputs": [dispatch["receipt_path"]],
        "diagnostic_only": False,
        "covers_writes": True,
        "dispatch_verified": True,
        "implementation_evidence": True,
        "may_claim_complete": False,
        "created_at": "2026-07-16T00:00:03Z",
    }
    if wavefront:
        receipt.update(
            {
                "wavefront_run_id": RUN_ID,
                "task_id": TASK_ID,
                "ownership_mode": "exclusive_file",
            }
        )
    write_json(path, receipt)


def write_sibling_decision_state(
    project: Path,
    ip: Path,
    *,
    malformed_target: bool = False,
    omit_event: bool = False,
    duplicate_event: bool = False,
    traversal_path: bool = False,
) -> None:
    decision = decision_payload()
    if malformed_target:
        decision["target"]["task_id"] = "RTL_WRONG_TARGET"
    decision_path = ip / "knowledge" / "decisions" / f"{DECISION_ID}.json"
    write_json(decision_path, decision)

    graph_path = ip / "ontology" / "runs" / RUN_ID / "wavefront_task_graph.json"
    graph = json.loads(graph_path.read_text(encoding="utf-8"))
    sibling = wavefront_task(SIBLING_TASK_ID, write_path="rtl/sibling.sv")
    sibling.update(
        {
            "receipt_path": "knowledge/subagents/sibling.json",
            "decision_id": DECISION_ID,
            "decision_path": "../../outside/decision.json" if traversal_path else f"knowledge/decisions/{DECISION_ID}.json",
            "decision_type": "rtl_conformance",
        }
    )
    graph["tasks"].append(sibling)
    graph["updated_at"] = "2026-07-16T00:01:01Z"
    write_json(graph_path, graph)

    if omit_event:
        return
    event = wavefront_event(
        "recorded",
        "2026-07-16T00:01:01Z",
        task_id=SIBLING_TASK_ID,
        status="failed",
        details={
            "barrier_outputs": [],
            "receipt": "knowledge/subagents/sibling.json",
            "decision": f"knowledge/decisions/{DECISION_ID}.json",
        },
    )
    events_path = ip / "knowledge" / "wavefront" / RUN_ID / "events.jsonl"
    append_json_line(events_path, event)
    if duplicate_event:
        append_json_line(events_path, event)


def write_sibling_repair_decision_state(project: Path, ip: Path, *, variant: str = "") -> None:
    decision = repair_decision_payload()
    if variant == "malformed":
        decision["reviewer"].pop("id")
    elif variant == "wrong_run":
        decision["target"]["run_id"] = "RUN_WRONG"
    elif variant == "wrong_task":
        decision["target"]["task_id"] = "RTL_WRONG_TARGET"
    elif variant == "future_timestamp":
        decision["created_at"] = "2026-07-16T00:01:02Z"
    decision_path = ip / "knowledge" / "decisions" / f"{DECISION_ID}.json"
    write_json(decision_path, decision)

    graph_path = ip / "ontology" / "runs" / RUN_ID / "wavefront_task_graph.json"
    graph = json.loads(graph_path.read_text(encoding="utf-8"))
    sibling = wavefront_task(SIBLING_TASK_ID, write_path="rtl/sibling.sv")
    sibling.update(
        {
            "dispatch_id": SIBLING_BASE_DISPATCH_ID,
            "receipt_path": "knowledge/subagents/sibling.json",
            "decision_id": DECISION_ID,
            "decision_path": f"knowledge/decisions/{DECISION_ID}.json",
            "decision_type": "rtl_conformance",
            "recorded_at": "2026-07-16T00:01:01Z",
        }
    )
    graph["tasks"].append(sibling)
    graph["updated_at"] = "2026-07-16T00:01:01Z"
    write_json(graph_path, graph)

    locks_path = ip / "ontology" / "runs" / RUN_ID / "ownership_locks.json"
    locks = json.loads(locks_path.read_text(encoding="utf-8"))
    locks["locks"].append(
        {
            "task_id": SIBLING_TASK_ID,
            "path": "rtl/sibling.sv",
            "mode": "exclusive_file",
            "dispatch_id": SIBLING_BASE_DISPATCH_ID,
            "claimed_at": "2026-07-16T00:00:10Z",
        }
    )
    locks["updated_at"] = "2026-07-16T00:01:01Z"
    write_json(locks_path, locks)

    events_path = ip / "knowledge" / "wavefront" / RUN_ID / "events.jsonl"
    append_json_line(
        events_path,
        wavefront_event(
            "claimed",
            "2026-07-16T00:00:10Z",
            task_id=SIBLING_TASK_ID,
            status="claimed",
            details={"write_paths": ["rtl/sibling.sv"]},
        ),
    )
    if variant != "missing_review":
        append_json_line(
            events_path,
            wavefront_event(
                "recorded",
                "2026-07-16T00:00:40Z",
                task_id=SIBLING_TASK_ID,
                status="review_pending",
                details={
                    "barrier_outputs": [],
                    "receipt": "knowledge/subagents/sibling.json",
                    "decision": "",
                },
            ),
        )
    append_json_line(
        events_path,
        wavefront_event(
            "recorded",
            "2026-07-16T00:01:01Z",
            task_id=SIBLING_TASK_ID,
            status="claimed",
            details={
                "barrier_outputs": [],
                "receipt": "",
                "decision": f"knowledge/decisions/{DECISION_ID}.json",
            },
        ),
    )

    if variant == "plus_arbitrary":
        arbitrary_id = "DEC_RTL_CONFORMANCE_REPAIR_ARBITRARY_20260716T000102Z"
        arbitrary = repair_decision_payload()
        arbitrary["decision_id"] = arbitrary_id
        arbitrary["created_at"] = "2026-07-16T00:01:00Z"
        write_json(ip / "knowledge" / "decisions" / f"{arbitrary_id}.json", arbitrary)

    (ip / "rtl" / "sibling.sv").write_text("module sibling_repair; endmodule\n", encoding="utf-8")


def write_historical_reclaim_state(
    project: Path,
    ip: Path,
    *,
    tamper_dispatch: bool = False,
    cross_run: bool = False,
    omit_abort_event: bool = False,
    inconsistent_event: bool = False,
    index_only: bool = False,
) -> None:
    write_sibling_decision_state(project, ip)
    repair1 = sibling_dispatch_payload(
        project,
        ip,
        dispatch_id=SIBLING_REPAIR1_DISPATCH_ID,
        receipt_name="sibling_repair1.json",
        created_at="2026-07-16T00:02:00Z",
        run_id="RUN_CROSS_RUN" if cross_run else RUN_ID,
    )
    if tamper_dispatch:
        repair1["stage"] = "rtl_tampered"
    repair1_path = ip / "knowledge" / "dispatches" / f"{SIBLING_REPAIR1_DISPATCH_ID}.json"
    repair1_receipt_path = ip / "knowledge" / "subagents" / "sibling_repair1.json"
    write_json(repair1_path, repair1)
    write_json(
        repair1_receipt_path,
        sibling_receipt_payload(
            repair1,
            created_at="2026-07-16T00:02:30Z",
            dispatch_verified=False,
        ),
    )

    events_path = ip / "knowledge" / "wavefront" / RUN_ID / "events.jsonl"
    if not omit_abort_event:
        append_json_line(
            events_path,
            wavefront_event(
                "recorded",
                "2026-07-16T00:03:00Z",
                task_id=SIBLING_TASK_ID,
                status="failed",
                details={
                    "barrier_outputs": [],
                    "receipt": "knowledge/subagents/wrong.json" if inconsistent_event else "knowledge/subagents/sibling_repair1.json",
                    "decision": "",
                },
            ),
        )
    append_json_line(
        events_path,
        wavefront_event(
            "recorded",
            "2026-07-16T00:03:01Z",
            task_id=SIBLING_TASK_ID,
            status="pending",
            details={"barrier_outputs": [], "receipt": "", "decision": ""},
        ),
    )

    repair2 = sibling_dispatch_payload(
        project,
        ip,
        dispatch_id=SIBLING_REPAIR2_DISPATCH_ID,
        receipt_name="sibling_repair2.json",
        created_at="2026-07-16T00:04:00Z",
    )
    write_json(ip / "knowledge" / "dispatches" / f"{SIBLING_REPAIR2_DISPATCH_ID}.json", repair2)
    append_json_line(
        events_path,
        wavefront_event(
            "claimed",
            "2026-07-16T00:04:01Z",
            task_id=SIBLING_TASK_ID,
            status="claimed",
            details={"write_paths": ["rtl/sibling.sv"]},
        ),
    )

    graph_path = ip / "ontology" / "runs" / RUN_ID / "wavefront_task_graph.json"
    graph = json.loads(graph_path.read_text(encoding="utf-8"))
    sibling = next(task for task in graph["tasks"] if task["task_id"] == SIBLING_TASK_ID)
    sibling.update(
        {
            "status": "claimed",
            "dispatch_id": SIBLING_REPAIR2_DISPATCH_ID,
            "receipt_path": "knowledge/subagents/sibling_repair1.json",
            "abort_marker": {
                "status": "failed",
                "recorded_at": "2026-07-16T00:03:00Z",
                "dispatch_id": SIBLING_REPAIR1_DISPATCH_ID,
                "receipt_path": "knowledge/subagents/sibling_repair1.json",
                "reason": "historical repair failed",
            },
        }
    )
    graph["updated_at"] = "2026-07-16T00:04:01Z"
    write_json(graph_path, graph)

    locks_path = ip / "ontology" / "runs" / RUN_ID / "ownership_locks.json"
    locks = json.loads(locks_path.read_text(encoding="utf-8"))
    locks["locks"].append(
        {
            "task_id": SIBLING_TASK_ID,
            "path": "rtl/sibling.sv",
            "mode": "exclusive_file",
            "dispatch_id": SIBLING_REPAIR2_DISPATCH_ID,
            "claimed_at": "2026-07-16T00:04:01Z",
        }
    )
    locks["updated_at"] = "2026-07-16T00:04:01Z"
    write_json(locks_path, locks)

    if index_only:
        write_json(
            ip / "knowledge" / "dispatches" / "_index.json",
            {"dispatch_ids": [SIBLING_REPAIR1_DISPATCH_ID]},
        )


def write_approved_handoff_state(project: Path, ip: Path, *, variant: str = "") -> None:
    write_historical_reclaim_state(project, ip)
    repair2_path = ip / "knowledge" / "dispatches" / f"{SIBLING_REPAIR2_DISPATCH_ID}.json"
    repair2 = json.loads(repair2_path.read_text(encoding="utf-8"))
    write_json(
        ip / "knowledge" / "subagents" / "sibling_repair2.json",
        sibling_receipt_payload(
            repair2,
            created_at="2026-07-16T00:04:30Z",
            dispatch_verified=True,
        ),
    )
    events_path = ip / "knowledge" / "wavefront" / RUN_ID / "events.jsonl"
    append_json_line(
        events_path,
        wavefront_event(
            "recorded",
            "2026-07-16T00:05:00Z",
            task_id=SIBLING_TASK_ID,
            status="review_pending",
            details={
                "barrier_outputs": [],
                "receipt": "knowledge/subagents/missing.json" if variant == "wrong_receipt" else "knowledge/subagents/sibling_repair2.json",
                "decision": "",
            },
        ),
    )

    approved = approved_decision_payload()
    if variant == "tampered_decision":
        approved["target"]["run_id"] = "RUN_TAMPERED"
    elif variant == "decision_before_receipt":
        approved["created_at"] = "2026-07-16T00:04:20Z"
    approved_path = ip / "knowledge" / "decisions" / f"{APPROVED_DECISION_ID}.json"
    write_json(approved_path, approved)
    event_status = "closed" if variant == "wrong_status" else "handoff_pass"
    event_barriers = ["wrong_barrier"] if variant == "wrong_barrier" else ["rtl_sibling_ready"]
    event_decision = (
        "knowledge/decisions/DEC_RTL_CONFORMANCE_WRONG_20260716T000600Z.json"
        if variant == "wrong_decision"
        else f"knowledge/decisions/{APPROVED_DECISION_ID}.json"
    )
    append_json_line(
        events_path,
        wavefront_event(
            "recorded",
            "2026-07-16T00:06:01Z",
            task_id=SIBLING_TASK_ID,
            status=event_status,
            details={
                "barrier_outputs": event_barriers,
                "receipt": "",
                "decision": event_decision,
            },
        ),
    )

    graph_path = ip / "ontology" / "runs" / RUN_ID / "wavefront_task_graph.json"
    graph = json.loads(graph_path.read_text(encoding="utf-8"))
    sibling = next(task for task in graph["tasks"] if task["task_id"] == SIBLING_TASK_ID)
    sibling.update(
        {
            "status": "handoff_pass",
            "dispatch_id": "DISPATCH_WRONG_20260716T000400Z_ABCD1234" if variant == "wrong_dispatch" else SIBLING_REPAIR2_DISPATCH_ID,
            "receipt_path": "knowledge/subagents/sibling_repair2.json",
            "decision_id": APPROVED_DECISION_ID,
            "decision_path": f"knowledge/decisions/{APPROVED_DECISION_ID}.json",
            "decision_type": "rtl_conformance",
            "barrier_outputs": ["rtl_sibling_ready"],
            "recorded_at": "2026-07-16T00:06:01Z",
        }
    )
    graph["updated_at"] = "2026-07-16T00:06:01Z"
    write_json(graph_path, graph)

    locks_path = ip / "ontology" / "runs" / RUN_ID / "ownership_locks.json"
    locks = json.loads(locks_path.read_text(encoding="utf-8"))
    locks["locks"] = [lock for lock in locks["locks"] if lock["task_id"] != SIBLING_TASK_ID]
    locks["updated_at"] = "2026-07-16T00:06:01Z"
    write_json(locks_path, locks)


def write_current_terminal_state(project: Path, ip: Path, dispatch: JsonObject, *, stale_lock: bool = False) -> None:
    receipt_ref = "knowledge/subagents/parent_link_receipt.json"
    decision_ref = f"knowledge/decisions/{CURRENT_DECISION_ID}.json"
    events_path = ip / "knowledge" / "wavefront" / RUN_ID / "events.jsonl"
    append_json_line(
        events_path,
        wavefront_event(
            "claimed",
            "2026-07-16T00:00:01Z",
            task_id=TASK_ID,
            status="claimed",
            details={"write_paths": ["rtl/worker.sv"]},
        ),
    )
    append_json_line(
        events_path,
        wavefront_event(
            "recorded",
            "2026-07-16T00:00:04Z",
            task_id=TASK_ID,
            status="review_pending",
            details={"barrier_outputs": [], "receipt": receipt_ref, "decision": ""},
        ),
    )
    decision = {
        "schema_version": "oag_wavefront_decision.v1",
        "product_name": "IP Dev Agent",
        "internal_gateway": "Ontology Agent Gateway",
        "decision_id": CURRENT_DECISION_ID,
        "decision_type": "rtl_conformance",
        "target": {"kind": "wavefront_task", "run_id": RUN_ID, "task_id": TASK_ID},
        "verdict": "approved",
        "rationale": {
            "summary": "current dispatch approved",
            "checked_against": ["rtl/worker.sv"],
            "preserved": [],
            "blockers": [],
        },
        "reviewer": {"kind": "ai", "id": "focused-test-reviewer"},
        "unlocks": {"wavefront_status": "handoff_pass", "barrier_outputs": ["rtl_parent_ready"]},
        "created_at": "2026-07-16T00:00:05Z",
    }
    write_json(ip / decision_ref, decision)
    append_json_line(
        events_path,
        wavefront_event(
            "recorded",
            "2026-07-16T00:00:06Z",
            task_id=TASK_ID,
            status="handoff_pass",
            details={"barrier_outputs": ["rtl_parent_ready"], "receipt": "", "decision": decision_ref},
        ),
    )
    graph_path = ip / "ontology" / "runs" / RUN_ID / "wavefront_task_graph.json"
    graph = json.loads(graph_path.read_text(encoding="utf-8"))
    task = next(item for item in graph["tasks"] if item["task_id"] == TASK_ID)
    task.update(
        {
            "status": "handoff_pass",
            "dispatch_id": dispatch["dispatch_id"],
            "receipt_path": receipt_ref,
            "decision_id": CURRENT_DECISION_ID,
            "decision_path": decision_ref,
            "decision_type": "rtl_conformance",
            "barrier_outputs": ["rtl_parent_ready"],
            "recorded_at": "2026-07-16T00:00:06Z",
        }
    )
    graph["updated_at"] = "2026-07-16T00:00:06Z"
    write_json(graph_path, graph)
    locks_path = ip / "ontology" / "runs" / RUN_ID / "ownership_locks.json"
    locks = json.loads(locks_path.read_text(encoding="utf-8"))
    if not stale_lock:
        locks["locks"] = [lock for lock in locks["locks"] if lock["task_id"] != TASK_ID]
    locks["updated_at"] = "2026-07-16T00:00:06Z"
    write_json(locks_path, locks)


def write_current_repair_decision_state(
    project: Path,
    ip: Path,
    dispatch: JsonObject,
    receipt_path: Path,
    *,
    variant: str = "",
) -> None:
    receipt_ref = relative(project, receipt_path)
    decision_ref = f"knowledge/decisions/{CURRENT_REPAIR_DECISION_ID}.json"
    events_path = ip / "knowledge" / "wavefront" / RUN_ID / "events.jsonl"
    append_json_line(
        events_path,
        wavefront_event(
            "claimed",
            "2026-07-16T00:00:01Z",
            task_id=TASK_ID,
            status="claimed",
            details={"write_paths": ["rtl/worker.sv"]},
        ),
    )
    append_json_line(
        events_path,
        wavefront_event(
            "recorded",
            "2026-07-16T00:00:04Z",
            task_id=TASK_ID,
            status="review_pending",
            details={"barrier_outputs": [], "receipt": receipt_ref, "decision": ""},
        ),
    )
    decision = {
        "schema_version": "oag_wavefront_decision.v1",
        "product_name": "IP Dev Agent",
        "internal_gateway": "Ontology Agent Gateway",
        "decision_id": CURRENT_REPAIR_DECISION_ID,
        "decision_type": "rtl_conformance",
        "target": {"kind": "wavefront_task", "run_id": RUN_ID, "task_id": TASK_ID},
        "verdict": "rejected",
        "rationale": {
            "summary": "current dispatch rejected for in-place repair",
            "checked_against": ["rtl/worker.sv"],
            "preserved": [],
            "blockers": ["repair required"],
        },
        "reviewer": {"kind": "ai", "id": "focused-test-reviewer"},
        "unlocks": {"wavefront_status": "claimed", "barrier_outputs": []},
        "created_at": "2026-07-16T00:00:08Z" if variant == "future_timestamp" else "2026-07-16T00:00:05Z",
    }
    if variant == "malformed":
        decision["reviewer"].pop("id")
    write_json(ip / decision_ref, decision)
    if variant != "unrecorded":
        append_json_line(
            events_path,
            wavefront_event(
                "recorded",
                "2026-07-16T00:00:06Z",
                task_id=TASK_ID,
                status="claimed",
                details={"barrier_outputs": [], "receipt": "", "decision": decision_ref},
            ),
        )

    graph_path = ip / "ontology" / "runs" / RUN_ID / "wavefront_task_graph.json"
    graph = json.loads(graph_path.read_text(encoding="utf-8"))
    task = next(item for item in graph["tasks"] if item["task_id"] == TASK_ID)
    task.update(
        {
            "status": "claimed",
            "dispatch_id": dispatch["dispatch_id"],
            "receipt_path": receipt_ref,
            "decision_id": CURRENT_REPAIR_DECISION_ID,
            "decision_path": decision_ref,
            "decision_type": "rtl_conformance",
            "barrier_outputs": ["rtl_parent_ready"],
            "recorded_at": "2026-07-16T00:00:06Z",
        }
    )
    graph["updated_at"] = "2026-07-16T00:00:06Z"
    write_json(graph_path, graph)

    locks_path = ip / "ontology" / "runs" / RUN_ID / "ownership_locks.json"
    locks = json.loads(locks_path.read_text(encoding="utf-8"))
    current_lock = next(lock for lock in locks["locks"] if lock["task_id"] == TASK_ID)
    current_lock["dispatch_id"] = dispatch["dispatch_id"]
    current_lock["claimed_at"] = "2026-07-16T00:00:01Z"
    locks["updated_at"] = "2026-07-16T00:00:06Z"
    write_json(locks_path, locks)

    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    receipt["created_at"] = "2026-07-16T00:00:09Z" if variant == "future_timestamp" else "2026-07-16T00:00:07Z"
    if variant == "interim_receipt":
        receipt["dispatch_verified"] = False
    receipt["output_hashes"] = {"rtl/worker.sv": f"sha256:{sha256(ip / 'rtl' / 'worker.sv')}"}
    write_json(receipt_path, receipt)


def run_case(root: Path, name: str) -> JsonObject:
    project = root / name
    ip, action_path, mission_path = initialize_project(project)
    if name == "missing_indexes_at_baseline":
        (ip / "knowledge" / "actions" / "_index.json").unlink()
        (ip / "knowledge" / "missions" / "_index.json").unlink()
        commit_state(project, "remove indexes before dispatch")
    elif name == "duplicate_action_index_preexisting":
        initial_action = action_payload(linked=False)
        duplicate_index = action_index(ip, [initial_action])
        duplicate_index["actions"].append(dict(duplicate_index["actions"][0]))
        duplicate_index["counts"] = {"total": 2, "open": 2, "terminal": 0}
        write_json(ip / "knowledge" / "actions" / "_index.json", duplicate_index)
        commit_state(project, "duplicate action index before dispatch")
    elif name == "symlink_escape":
        actions_dir = ip / "knowledge" / "actions"
        external_actions = root / "external_actions"
        shutil.rmtree(actions_dir)
        external_actions.mkdir(parents=True)
        initial_action = action_payload(linked=False)
        write_json(external_actions / f"{ACTION_ID}.json", initial_action)
        write_json(external_actions / "_index.json", action_index(ip, [initial_action]))
        actions_dir.symlink_to(external_actions, target_is_directory=True)
        commit_state(project, "external action directory symlink")
    elif name == "mission_symlink_escape":
        missions_dir = ip / "knowledge" / "missions"
        external_missions = root / "external_missions"
        shutil.rmtree(missions_dir)
        external_missions.mkdir(parents=True)
        initial_mission = mission_payload(MISSION_ID, [ACTION_ID])
        write_json(external_missions / f"{MISSION_ID}.json", initial_mission)
        write_json(external_missions / "_index.json", mission_index(ip, [initial_mission]))
        missions_dir.symlink_to(external_missions, target_is_directory=True)
        commit_state(project, "external mission directory symlink")
    elif name == "preexisting_decision":
        write_json(
            ip / "knowledge" / "decisions" / f"{DECISION_ID}.json",
            decision_payload(summary="preexisting decision baseline"),
        )
        commit_state(project, "preexisting sibling decision")
    elif name in REPAIR_DECISION_CASES:
        sibling_path = ip / "rtl" / "sibling.sv"
        sibling_path.write_text("module sibling_reviewed; endmodule\n", encoding="utf-8")
        sibling_receipt_path = ip / "knowledge" / "subagents" / "sibling.json"
        sibling_receipt = json.loads(sibling_receipt_path.read_text(encoding="utf-8"))
        sibling_receipt["created_at"] = "2026-07-16T00:02:00Z"
        sibling_receipt["output_hashes"] = {
            "rtl/sibling.sv": (
                "sha256:not-a-digest"
                if name == "repair_rejection_bad_output_hash_format"
                else f"sha256:{sha256(sibling_path)}"
            )
        }
        write_json(sibling_receipt_path, sibling_receipt)
        commit_state(project, "reviewed sibling receipt before parent dispatch")
    wavefront = name != "non_wavefront"
    dispatch_path, receipt_path, dispatch = write_dispatch(project, ip, wavefront=wavefront)

    linked_task = "RTL_OTHER_TASK" if name == "mismatched_ref" else TASK_ID
    mission_ids = [ACTION_ID] if name == "self_link_mission" else [MISSION_ID]
    linked_action = action_payload(linked=True, task_id=linked_task, mission_ids=mission_ids)
    linked_action["result"]["summary"] = "parent linked update"
    mission_actions = [] if name == "nonreciprocal_mission" else [ACTION_ID]
    linked_mission = mission_payload(MISSION_ID, mission_actions)
    linked_mission["last_observed_at"] = "2026-07-16T00:00:04Z"
    actions = [linked_action]
    missions = [linked_mission]
    write_json(action_path, linked_action)
    write_json(mission_path, linked_mission)

    if name == "unrelated_action":
        unrelated = action_payload(linked=False)
        unrelated["id"] = "ACT_RUN_20260716T000001Z_UNRELATED"
        unrelated["mission_instance_refs"] = []
        actions.append(unrelated)
        write_json(ip / "knowledge" / "actions" / f"{unrelated['id']}.json", unrelated)
    elif name == "malformed_action":
        malformed_path = ip / "knowledge" / "actions" / "ACT_RUN_20260716T000001Z_MALFORMED.json"
        malformed_path.write_text("{not-json\n", encoding="utf-8")
    elif name == "unlinked_mission":
        unrelated_mission = mission_payload("MISSION_RUN_20260716T000001Z_UNLINKED", [])
        missions.append(unrelated_mission)
        write_json(ip / "knowledge" / "missions" / f"{unrelated_mission['id']}.json", unrelated_mission)
    elif name == "malformed_mission":
        malformed_path = ip / "knowledge" / "missions" / "MISSION_RUN_20260716T000001Z_MALFORMED.json"
        malformed_path.write_text("[]\n", encoding="utf-8")

    current_action_index = action_index(ip, actions)
    current_mission_index = mission_index(ip, missions)
    if name == "duplicate_action_index_preexisting":
        current_action_index["actions"].append(dict(current_action_index["actions"][0]))
        current_action_index["counts"] = {"total": 2, "open": 2, "terminal": 0}
    elif name == "poisoned_action_counts":
        current_action_index["counts"]["open"] = 99
    elif name == "boolean_action_count":
        current_action_index["counts"]["total"] = True
    elif name == "float_action_count":
        current_action_index["counts"]["total"] = 1.0
    elif name == "negative_action_count":
        current_action_index["counts"]["total"] = -1
    elif name == "poisoned_action_status":
        current_action_index["actions"][0]["status"] = "accepted"
    elif name == "poisoned_mission_action_count":
        current_mission_index["missions"][0]["action_count"] = 99
    elif name == "poisoned_mission_counts":
        current_mission_index["counts"]["active"] = 99
    elif name == "poisoned_mission_status":
        current_mission_index["missions"][0]["status"] = "completed"
    elif name == "boolean_mission_count":
        current_mission_index["counts"]["total"] = True
    elif name == "float_mission_count":
        current_mission_index["counts"]["total"] = 1.0
    elif name == "negative_mission_count":
        current_mission_index["counts"]["total"] = -1
    elif name == "boolean_mission_action_count":
        current_mission_index["missions"][0]["action_count"] = True
    elif name == "float_mission_action_count":
        current_mission_index["missions"][0]["action_count"] = 1.0
    elif name == "negative_mission_action_count":
        current_mission_index["missions"][0]["action_count"] = -1
    elif name == "traversal_index_row":
        current_action_index["actions"].append(
            {
                **current_action_index["actions"][0],
                "id": "ACT_RUN_20260716T000002Z_ESCAPE",
                "path": "../../escape.json",
            }
        )
        current_action_index["counts"] = {"total": 2, "open": 2, "terminal": 0}
    write_json(ip / "knowledge" / "actions" / "_index.json", current_action_index)
    write_json(ip / "knowledge" / "missions" / "_index.json", current_mission_index)
    worker_path = ip / "rtl" / "worker.sv"
    worker_path.parent.mkdir(parents=True, exist_ok=True)
    worker_path.write_text("module worker; endmodule\n", encoding="utf-8")

    if name in {
        "approved_handoff_lineage",
        "approved_tampered_decision",
        "approved_wrong_barrier",
        "approved_wrong_status",
        "approved_wrong_receipt",
        "approved_wrong_decision",
        "approved_wrong_dispatch",
        "approved_decision_before_receipt",
    }:
        variant = name.removeprefix("approved_") if name != "approved_handoff_lineage" else ""
        write_approved_handoff_state(project, ip, variant=variant)
    elif name in REPAIR_DECISION_CASES:
        variant = name.removeprefix("repair_rejection_")
        write_sibling_repair_decision_state(
            project,
            ip,
            variant="" if variant == "claimed" else variant,
        )
    elif name in {
        "historical_reclaim_lineage",
        "tampered_historical_dispatch",
        "cross_run_historical_dispatch",
        "unlinked_historical_dispatch",
        "event_inconsistent_historical_dispatch",
        "index_only_historical_dispatch",
        "wrong_graph_ip_id",
        "wrong_graph_ip_dir",
        "wrong_locks_run_id",
        "wrong_locks_ip_id",
        "wrong_active_lock_path",
        "wrong_active_lock_mode",
        "historical_receipt_missing_required",
        "historical_receipt_bad_output_hash",
        "historical_receipt_mirrored_mismatch",
        "historical_successor_baseline_hash",
        "extra_unowned_dispatch_scope",
        "active_missing_claim_event",
        "duplicate_active_lock",
        "extra_active_lock",
        "unknown_colliding_active_lock",
    }:
        write_historical_reclaim_state(
            project,
            ip,
            tamper_dispatch=name == "tampered_historical_dispatch",
            cross_run=name == "cross_run_historical_dispatch",
            omit_abort_event=name in {"unlinked_historical_dispatch", "index_only_historical_dispatch"},
            inconsistent_event=name == "event_inconsistent_historical_dispatch",
            index_only=name == "index_only_historical_dispatch",
        )
    elif name in {
        "linked_sibling_decision",
        "claimed_decision",
        "preexisting_decision",
        "valid_plus_arbitrary_decision",
        "approved_failed_decision",
        "decision_receipt_changed_outside",
    }:
        write_sibling_decision_state(project, ip)
    elif name == "unlinked_decision":
        write_json(ip / "knowledge" / "decisions" / f"{DECISION_ID}.json", decision_payload())
    elif name == "malformed_decision":
        write_sibling_decision_state(project, ip, malformed_target=True)
    elif name == "decision_missing_event":
        write_sibling_decision_state(project, ip, omit_event=True)
    elif name == "duplicate_decision_event":
        write_sibling_decision_state(project, ip, duplicate_event=True)
    elif name == "decision_traversal_path":
        write_sibling_decision_state(project, ip, traversal_path=True)

    if name == "valid_plus_arbitrary_decision":
        arbitrary_id = "DEC_RTL_CONFORMANCE_UNLINKED_20260716T000101Z"
        write_json(
            ip / "knowledge" / "decisions" / f"{arbitrary_id}.json",
            decision_payload(decision_id=arbitrary_id, summary="unlinked decision must remain visible"),
        )

    if name in {"wrong_graph_ip_id", "wrong_graph_ip_dir"}:
        graph_path = ip / "ontology" / "runs" / RUN_ID / "wavefront_task_graph.json"
        graph = json.loads(graph_path.read_text(encoding="utf-8"))
        graph["ip_id" if name == "wrong_graph_ip_id" else "ip_dir"] = "wrong_ip"
        write_json(graph_path, graph)
    if name in {"wrong_locks_run_id", "wrong_locks_ip_id", "wrong_active_lock_path", "wrong_active_lock_mode"}:
        locks_path = ip / "ontology" / "runs" / RUN_ID / "ownership_locks.json"
        locks = json.loads(locks_path.read_text(encoding="utf-8"))
        if name == "wrong_locks_run_id":
            locks["run_id"] = "RUN_WRONG"
        elif name == "wrong_locks_ip_id":
            locks["ip_id"] = "wrong_ip"
        else:
            sibling_lock = next(lock for lock in locks["locks"] if lock["task_id"] == SIBLING_TASK_ID)
            sibling_lock["path" if name == "wrong_active_lock_path" else "mode"] = (
                "rtl/wrong.sv" if name == "wrong_active_lock_path" else "integration_owner"
            )
        write_json(locks_path, locks)
    if name in {"duplicate_active_lock", "extra_active_lock", "unknown_colliding_active_lock"}:
        locks_path = ip / "ontology" / "runs" / RUN_ID / "ownership_locks.json"
        locks = json.loads(locks_path.read_text(encoding="utf-8"))
        sibling_lock = next(lock for lock in locks["locks"] if lock["task_id"] == SIBLING_TASK_ID)
        extra_lock = dict(sibling_lock)
        if name == "extra_active_lock":
            extra_lock["path"] = "rtl/extra.sv"
        elif name == "unknown_colliding_active_lock":
            extra_lock["task_id"] = "UNKNOWN_TASK"
            extra_lock["dispatch_id"] = "DISPATCH_UNKNOWN_20260716T000401Z_ABCD1234"
        locks["locks"].append(extra_lock)
        write_json(locks_path, locks)
    if name == "active_missing_claim_event":
        events_path = ip / "knowledge" / "wavefront" / RUN_ID / "events.jsonl"
        events = [json.loads(line) for line in events_path.read_text(encoding="utf-8").splitlines() if line]
        events = [
            event
            for event in events
            if not (
                event.get("event") == "claimed"
                and event.get("task_id") == SIBLING_TASK_ID
                and event.get("created_at") == "2026-07-16T00:04:01Z"
            )
        ]
        events_path.write_text("".join(json.dumps(event, sort_keys=True) + "\n" for event in events), encoding="utf-8")
    if name in {
        "historical_receipt_missing_required",
        "historical_receipt_bad_output_hash",
        "historical_receipt_mirrored_mismatch",
    }:
        historical_receipt_path = ip / "knowledge" / "subagents" / "sibling_repair1.json"
        historical_receipt = json.loads(historical_receipt_path.read_text(encoding="utf-8"))
        if name == "historical_receipt_missing_required":
            historical_receipt.pop("role_name")
        elif name == "historical_receipt_bad_output_hash":
            historical_receipt["output_hashes"] = {"rtl/stable.sv": "sha256:" + ("0" * 64)}
        else:
            historical_receipt["role_name"] = "oag-other"
        write_json(historical_receipt_path, historical_receipt)
    if name == "historical_successor_baseline_hash":
        sibling_path = ip / "rtl" / "sibling.sv"
        sibling_path.write_text("module sibling_old; endmodule\n", encoding="utf-8")
        historical_receipt_path = ip / "knowledge" / "subagents" / "sibling_repair1.json"
        historical_receipt = json.loads(historical_receipt_path.read_text(encoding="utf-8"))
        historical_receipt["output_hashes"] = {"rtl/sibling.sv": f"sha256:{sha256(sibling_path)}"}
        write_json(historical_receipt_path, historical_receipt)
        repair2_path = ip / "knowledge" / "dispatches" / f"{SIBLING_REPAIR2_DISPATCH_ID}.json"
        repair2 = json.loads(repair2_path.read_text(encoding="utf-8"))
        repair2["baseline"]["file_hashes"] = {relative(project, sibling_path): sha256(sibling_path)}
        repair2["dispatch_integrity"] = dispatch_integrity(repair2)
        write_json(repair2_path, repair2)
        sibling_path.write_text("module sibling_new; endmodule\n", encoding="utf-8")
    if name == "extra_unowned_dispatch_scope":
        repair2_path = ip / "knowledge" / "dispatches" / f"{SIBLING_REPAIR2_DISPATCH_ID}.json"
        repair2 = json.loads(repair2_path.read_text(encoding="utf-8"))
        repair2["allowed_write_paths"].append(relative(project, ip / "rtl" / "unowned.sv"))
        repair2["dispatch_integrity"] = dispatch_integrity(repair2)
        write_json(repair2_path, repair2)
    if name == "approved_failed_decision":
        failed_decision_path = ip / "knowledge" / "decisions" / f"{DECISION_ID}.json"
        failed_decision = json.loads(failed_decision_path.read_text(encoding="utf-8"))
        failed_decision["verdict"] = "approved"
        failed_decision["rationale"]["blockers"] = []
        write_json(failed_decision_path, failed_decision)
    if name == "decision_receipt_changed_outside":
        sibling_receipt_path = ip / "knowledge" / "subagents" / "sibling.json"
        sibling_receipt = json.loads(sibling_receipt_path.read_text(encoding="utf-8"))
        sibling_receipt["changed_paths"] = [relative(project, ip / "rtl" / "outside.sv")]
        write_json(sibling_receipt_path, sibling_receipt)

    write_receipt(
        project,
        ip,
        receipt_path,
        dispatch,
        wavefront=wavefront,
        claim_parent=name == "claimed_parent",
        claim_decision=name == "claimed_decision",
    )
    if name in CURRENT_REPAIR_DECISION_CASES:
        write_current_repair_decision_state(
            project,
            ip,
            dispatch,
            receipt_path,
            variant=name.removeprefix("current_repair_rejection_").replace("claimed", ""),
        )
    elif name == "unverified_receipt_without_repair":
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        receipt["dispatch_verified"] = False
        write_json(receipt_path, receipt)
    if name in {
        "current_terminal_reverify",
        "current_terminal_stale_lock",
        "current_terminal_unknown_colliding_lock",
    }:
        write_current_terminal_state(project, ip, dispatch, stale_lock=name == "current_terminal_stale_lock")
        if name == "current_terminal_unknown_colliding_lock":
            locks_path = ip / "ontology" / "runs" / RUN_ID / "ownership_locks.json"
            locks = json.loads(locks_path.read_text(encoding="utf-8"))
            locks["locks"].append(
                {
                    "task_id": "UNKNOWN_TASK",
                    "path": "rtl/worker.sv",
                    "mode": "exclusive_file",
                    "dispatch_id": "DISPATCH_UNKNOWN_20260716T000007Z_ABCD1234",
                    "claimed_at": "2026-07-16T00:00:01Z",
                }
            )
            write_json(locks_path, locks)
    if name.startswith("output_hash_"):
        receipt_payload = json.loads(receipt_path.read_text(encoding="utf-8"))
        stable_path = ip / "rtl" / "stable.sv"
        digest = f"sha256:{sha256(stable_path)}"
        output_path = "rtl/stable.sv"
        if name == "output_hash_bad_format":
            digest = digest[:-8]
        elif name == "output_hash_mismatch":
            digest = "sha256:" + ("0" * 64)
        elif name == "output_hash_missing_file":
            output_path = "rtl/missing.sv"
        elif name == "output_hash_directory":
            output_path = "rtl"
        elif name == "output_hash_traversal":
            output_path = "../outside.sv"
        elif name == "output_hash_symlink":
            output_path = "rtl/stable_link.sv"
            (ip / output_path).symlink_to("stable.sv")
        elif name == "output_hash_noncanonical":
            output_path = "rtl//stable.sv"
        receipt_payload["output_hashes"] = {output_path: digest}
        write_json(receipt_path, receipt_payload)

    env = {**os.environ, "OAG_PROJECT_ROOT": str(project), "OAG_DISABLE_BACKEND": "1"}
    proc = subprocess.run(
        [sys.executable, str(DISPATCH_CLI), "verify", "--dispatch", str(dispatch_path), "--receipt", str(receipt_path), "--json"],
        cwd=project,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    if not proc.stdout:
        raise AssertionError(f"{name}: no verifier JSON; stderr={proc.stderr}")
    return json.loads(proc.stdout)


def issue_codes(result: JsonObject) -> set[str]:
    return {str(item.get("code") or "") for item in result.get("issues", []) if isinstance(item, dict)}


def main() -> int:
    cases: dict[str, str] = {}
    with tempfile.TemporaryDirectory(prefix="oag-parent-orchestration-") as temp:
        root = Path(temp)
        positive = run_case(root, "linked")
        assert positive["status"] == "pass", positive
        expected_exemptions = {
            f"parent_link_ip/knowledge/actions/{ACTION_ID}.json",
            "parent_link_ip/knowledge/actions/_index.json",
            f"parent_link_ip/knowledge/missions/{MISSION_ID}.json",
            "parent_link_ip/knowledge/missions/_index.json",
        }
        assert set(positive["parent_orchestration_exempted_paths"]) == expected_exemptions, positive
        cases["linked_action_mission_indexes"] = "pass"

        output_hash_valid = run_case(root, "output_hash_unchanged_valid")
        assert output_hash_valid["status"] == "pass", output_hash_valid
        cases["output_hash_unchanged_valid"] = "pass"

        for name, expected_code in (
            ("output_hash_bad_format", "OUTPUT_HASH_FORMAT"),
            ("output_hash_mismatch", "OUTPUT_HASH_MISMATCH"),
            ("output_hash_missing_file", "OUTPUT_HASH_FILE"),
            ("output_hash_directory", "OUTPUT_HASH_FILE"),
            ("output_hash_traversal", "OUTPUT_HASH_PATH_UNSAFE"),
            ("output_hash_symlink", "OUTPUT_HASH_PATH_UNSAFE"),
            ("output_hash_noncanonical", "OUTPUT_HASH_PATH_UNSAFE"),
        ):
            result = run_case(root, name)
            assert result["status"] == "fail", result
            assert expected_code in issue_codes(result), result
            cases[name] = "rejected"

        linked_decision = run_case(root, "linked_sibling_decision")
        assert linked_decision["status"] == "pass", linked_decision
        expected_decision_path = f"parent_link_ip/knowledge/decisions/{DECISION_ID}.json"
        assert linked_decision["parent_wavefront_decision_exempted_paths"] == [expected_decision_path], linked_decision
        assert linked_decision["out_of_scope_paths"] == [], linked_decision
        cases["linked_sibling_decision"] = "pass"

        repair_decision = run_case(root, "repair_rejection_claimed")
        assert repair_decision["status"] == "pass", repair_decision
        assert repair_decision["parent_wavefront_decision_exempted_paths"] == [expected_decision_path], repair_decision
        assert repair_decision["out_of_scope_paths"] == [], repair_decision
        cases["repair_rejection_claimed"] = "pass"

        for name in (
            "repair_rejection_bad_output_hash_format",
            "repair_rejection_future_timestamp",
            "repair_rejection_malformed",
            "repair_rejection_missing_review",
            "repair_rejection_wrong_run",
            "repair_rejection_wrong_task",
        ):
            result = run_case(root, name)
            assert result["status"] == "fail", result
            assert result["parent_wavefront_decision_exempted_paths"] == [], result
            assert expected_decision_path in result["out_of_scope_paths"], result
            assert "ACTUAL_PATH_OUT_OF_SCOPE" in issue_codes(result), result
            assert "EXCEPTION" not in issue_codes(result), result
            cases[name] = "rejected"

        repair_arbitrary = run_case(root, "repair_rejection_plus_arbitrary")
        arbitrary_repair_path = (
            "parent_link_ip/knowledge/decisions/"
            "DEC_RTL_CONFORMANCE_REPAIR_ARBITRARY_20260716T000102Z.json"
        )
        assert repair_arbitrary["status"] == "fail", repair_arbitrary
        assert repair_arbitrary["parent_wavefront_decision_exempted_paths"] == [expected_decision_path], repair_arbitrary
        assert arbitrary_repair_path in repair_arbitrary["out_of_scope_paths"], repair_arbitrary
        assert "ACTUAL_PATH_OUT_OF_SCOPE" in issue_codes(repair_arbitrary), repair_arbitrary
        cases["repair_rejection_plus_arbitrary"] = "rejected"

        current_repair = run_case(root, "current_repair_rejection_claimed")
        expected_current_repair_path = f"parent_link_ip/knowledge/decisions/{CURRENT_REPAIR_DECISION_ID}.json"
        assert current_repair["status"] == "pass", current_repair
        assert current_repair["parent_wavefront_decision_exempted_paths"] == [expected_current_repair_path], current_repair
        assert current_repair["out_of_scope_paths"] == [], current_repair
        cases["current_repair_rejection_claimed"] = "pass"

        current_repair_interim = run_case(root, "current_repair_rejection_interim_receipt")
        assert current_repair_interim["status"] == "pass", current_repair_interim
        assert current_repair_interim["parent_wavefront_decision_exempted_paths"] == [expected_current_repair_path], current_repair_interim
        assert current_repair_interim["out_of_scope_paths"] == [], current_repair_interim
        assert not ({"RECEIPT_SCHEMA_CONST", "RECEIPT_DISPATCH_VERIFIED"} & issue_codes(current_repair_interim)), current_repair_interim
        cases["current_repair_rejection_interim_receipt"] = "pass"

        unverified_without_repair = run_case(root, "unverified_receipt_without_repair")
        assert unverified_without_repair["status"] == "fail", unverified_without_repair
        assert {"RECEIPT_SCHEMA_CONST", "RECEIPT_DISPATCH_VERIFIED"}.issubset(issue_codes(unverified_without_repair)), unverified_without_repair
        assert unverified_without_repair["parent_wavefront_decision_exempted_paths"] == [], unverified_without_repair
        cases["unverified_receipt_without_repair"] = "rejected"

        for name in (
            "current_repair_rejection_future_timestamp",
            "current_repair_rejection_malformed",
            "current_repair_rejection_unrecorded",
        ):
            result = run_case(root, name)
            assert result["status"] == "fail", result
            assert result["parent_wavefront_decision_exempted_paths"] == [], result
            assert expected_current_repair_path in result["out_of_scope_paths"], result
            assert "ACTUAL_PATH_OUT_OF_SCOPE" in issue_codes(result), result
            assert "EXCEPTION" not in issue_codes(result), result
            cases[name] = "rejected"

        current_terminal = run_case(root, "current_terminal_reverify")
        expected_current_decision_path = f"parent_link_ip/knowledge/decisions/{CURRENT_DECISION_ID}.json"
        assert current_terminal["status"] == "pass", current_terminal
        assert current_terminal["current_terminal_decision_exempted_paths"] == [expected_current_decision_path], current_terminal
        assert current_terminal["out_of_scope_paths"] == [], current_terminal
        assert not ({"WAVEFRONT_TASK_UNCLAIMED", "WAVEFRONT_CLAIM_DISPATCH_MISMATCH"} & issue_codes(current_terminal)), current_terminal
        cases["current_terminal_reverify"] = "pass"

        current_terminal_stale_lock = run_case(root, "current_terminal_stale_lock")
        assert current_terminal_stale_lock["status"] == "fail", current_terminal_stale_lock
        assert expected_current_decision_path in current_terminal_stale_lock["out_of_scope_paths"], current_terminal_stale_lock
        assert current_terminal_stale_lock["current_terminal_decision_exempted_paths"] == [], current_terminal_stale_lock
        assert "WAVEFRONT_TASK_UNCLAIMED" in issue_codes(current_terminal_stale_lock), current_terminal_stale_lock
        cases["current_terminal_stale_lock"] = "rejected"

        current_terminal_unknown_lock = run_case(root, "current_terminal_unknown_colliding_lock")
        assert current_terminal_unknown_lock["status"] == "fail", current_terminal_unknown_lock
        assert expected_current_decision_path in current_terminal_unknown_lock["out_of_scope_paths"], current_terminal_unknown_lock
        assert current_terminal_unknown_lock["current_terminal_decision_exempted_paths"] == [], current_terminal_unknown_lock
        assert "WAVEFRONT_TASK_UNCLAIMED" in issue_codes(current_terminal_unknown_lock), current_terminal_unknown_lock
        cases["current_terminal_unknown_colliding_lock"] = "rejected"

        decision_receipt_scope = run_case(root, "decision_receipt_changed_outside")
        assert decision_receipt_scope["status"] == "fail", decision_receipt_scope
        assert expected_decision_path in decision_receipt_scope["out_of_scope_paths"], decision_receipt_scope
        assert expected_decision_path not in decision_receipt_scope["parent_wavefront_decision_exempted_paths"], decision_receipt_scope
        cases["decision_receipt_changed_outside"] = "rejected"

        historical = run_case(root, "historical_reclaim_lineage")
        assert historical["status"] == "pass", historical
        expected_repair1_path = f"parent_link_ip/knowledge/dispatches/{SIBLING_REPAIR1_DISPATCH_ID}.json"
        expected_repair2_path = f"parent_link_ip/knowledge/dispatches/{SIBLING_REPAIR2_DISPATCH_ID}.json"
        assert set(historical["parent_wavefront_dispatch_exempted_paths"]) == {
            expected_repair1_path,
            expected_repair2_path,
        }, historical
        assert historical["parent_wavefront_decision_exempted_paths"] == [expected_decision_path], historical
        assert historical["out_of_scope_paths"] == [], historical
        cases["historical_reclaim_lineage"] = "pass"

        historical_hash = run_case(root, "historical_successor_baseline_hash")
        assert historical_hash["status"] == "pass", historical_hash
        assert expected_repair1_path in historical_hash["parent_wavefront_dispatch_exempted_paths"], historical_hash
        assert historical_hash["out_of_scope_paths"] == [], historical_hash
        cases["historical_successor_baseline_hash"] = "pass"

        approved = run_case(root, "approved_handoff_lineage")
        expected_approved_decision_path = f"parent_link_ip/knowledge/decisions/{APPROVED_DECISION_ID}.json"
        assert approved["status"] == "pass", approved
        assert set(approved["parent_wavefront_dispatch_exempted_paths"]) == {
            expected_repair1_path,
            expected_repair2_path,
        }, approved
        assert set(approved["parent_wavefront_decision_exempted_paths"]) == {
            expected_decision_path,
            expected_approved_decision_path,
        }, approved
        assert approved["out_of_scope_paths"] == [], approved
        cases["approved_handoff_lineage"] = "pass"

        for name in (
            "approved_tampered_decision",
            "approved_wrong_barrier",
            "approved_wrong_status",
            "approved_wrong_receipt",
            "approved_wrong_decision",
            "approved_wrong_dispatch",
            "approved_decision_before_receipt",
        ):
            result = run_case(root, name)
            assert result["status"] == "fail", result
            assert expected_repair2_path in result["out_of_scope_paths"], result
            assert expected_approved_decision_path in result["out_of_scope_paths"], result
            assert expected_repair2_path not in result["parent_wavefront_dispatch_exempted_paths"], result
            assert expected_approved_decision_path not in result["parent_wavefront_decision_exempted_paths"], result
            assert "ACTUAL_PATH_OUT_OF_SCOPE" in issue_codes(result), result
            cases[name] = "rejected"

        for name in (
            "tampered_historical_dispatch",
            "cross_run_historical_dispatch",
            "unlinked_historical_dispatch",
            "event_inconsistent_historical_dispatch",
            "index_only_historical_dispatch",
        ):
            result = run_case(root, name)
            assert result["status"] == "fail", result
            assert expected_repair1_path in result["out_of_scope_paths"], result
            assert expected_repair1_path not in result["parent_wavefront_dispatch_exempted_paths"], result
            assert expected_repair2_path in result["parent_wavefront_dispatch_exempted_paths"], result
            assert "ACTUAL_PATH_OUT_OF_SCOPE" in issue_codes(result), result
            cases[name] = "rejected"

        for name in (
            "wrong_graph_ip_id",
            "wrong_graph_ip_dir",
            "wrong_locks_run_id",
            "wrong_locks_ip_id",
            "wrong_active_lock_path",
            "wrong_active_lock_mode",
            "extra_unowned_dispatch_scope",
            "active_missing_claim_event",
            "duplicate_active_lock",
            "extra_active_lock",
            "unknown_colliding_active_lock",
        ):
            result = run_case(root, name)
            assert result["status"] == "fail", result
            assert expected_repair2_path in result["out_of_scope_paths"], result
            assert expected_repair2_path not in result["parent_wavefront_dispatch_exempted_paths"], result
            assert "ACTUAL_PATH_OUT_OF_SCOPE" in issue_codes(result), result
            cases[name] = "rejected"

        for name in (
            "historical_receipt_missing_required",
            "historical_receipt_bad_output_hash",
            "historical_receipt_mirrored_mismatch",
        ):
            result = run_case(root, name)
            assert result["status"] == "fail", result
            assert expected_repair1_path in result["out_of_scope_paths"], result
            assert expected_repair1_path not in result["parent_wavefront_dispatch_exempted_paths"], result
            assert "ACTUAL_PATH_OUT_OF_SCOPE" in issue_codes(result), result
            cases[name] = "rejected"

        approved_failed = run_case(root, "approved_failed_decision")
        assert approved_failed["status"] == "fail", approved_failed
        assert expected_decision_path in approved_failed["out_of_scope_paths"], approved_failed
        assert expected_decision_path not in approved_failed["parent_wavefront_decision_exempted_paths"], approved_failed
        cases["approved_failed_decision"] = "rejected"

        for name, expected_fragment in (
            ("unrelated_action", "UNRELATED"),
            ("malformed_action", "MALFORMED"),
            ("unlinked_mission", "UNLINKED"),
            ("malformed_mission", "MALFORMED"),
            ("mismatched_ref", ACTION_ID),
        ):
            result = run_case(root, name)
            assert result["status"] == "fail", result
            assert "ACTUAL_PATH_OUT_OF_SCOPE" in issue_codes(result), result
            assert any(expected_fragment in str(path) for path in result["out_of_scope_paths"]), result
            cases[name] = "rejected"

        for name in (
            "self_link_mission",
            "missing_indexes_at_baseline",
            "nonreciprocal_mission",
            "duplicate_action_index_preexisting",
            "poisoned_action_counts",
            "boolean_action_count",
            "float_action_count",
            "negative_action_count",
            "poisoned_action_status",
            "poisoned_mission_action_count",
            "poisoned_mission_counts",
            "poisoned_mission_status",
            "boolean_mission_count",
            "float_mission_count",
            "negative_mission_count",
            "boolean_mission_action_count",
            "float_mission_action_count",
            "negative_mission_action_count",
            "traversal_index_row",
            "symlink_escape",
            "mission_symlink_escape",
        ):
            result = run_case(root, name)
            assert result["status"] == "fail", result
            assert result["parent_orchestration_exempted_paths"] == [], result
            assert "EXCEPTION" not in issue_codes(result), result
            if name in {"symlink_escape", "mission_symlink_escape"}:
                assert "PARENT_ORCHESTRATION_PATH_ESCAPE" in issue_codes(result), result
            else:
                assert "ACTUAL_PATH_OUT_OF_SCOPE" in issue_codes(result), result
            cases[name] = "rejected"

        claimed = run_case(root, "claimed_parent")
        assert claimed["status"] == "fail", claimed
        assert "OWNED_PATH_OUT_OF_SCOPE" in issue_codes(claimed), claimed
        cases["claimed_parent_path"] = "rejected"

        for name in (
            "unlinked_decision",
            "malformed_decision",
            "decision_missing_event",
            "duplicate_decision_event",
            "decision_traversal_path",
            "preexisting_decision",
        ):
            result = run_case(root, name)
            assert result["status"] == "fail", result
            assert result["parent_wavefront_decision_exempted_paths"] == [], result
            assert "ACTUAL_PATH_OUT_OF_SCOPE" in issue_codes(result), result
            assert "EXCEPTION" not in issue_codes(result), result
            assert any(DECISION_ID in str(path) for path in result["out_of_scope_paths"]), result
            cases[name] = "rejected"

        claimed_decision = run_case(root, "claimed_decision")
        assert claimed_decision["status"] == "fail", claimed_decision
        assert claimed_decision["parent_wavefront_decision_exempted_paths"] == [expected_decision_path], claimed_decision
        assert "OWNED_PATH_OUT_OF_SCOPE" in issue_codes(claimed_decision), claimed_decision
        cases["claimed_decision_path"] = "rejected"

        arbitrary_decision = run_case(root, "valid_plus_arbitrary_decision")
        assert arbitrary_decision["status"] == "fail", arbitrary_decision
        assert arbitrary_decision["parent_wavefront_decision_exempted_paths"] == [expected_decision_path], arbitrary_decision
        assert "ACTUAL_PATH_OUT_OF_SCOPE" in issue_codes(arbitrary_decision), arbitrary_decision
        assert any("DEC_RTL_CONFORMANCE_UNLINKED" in str(path) for path in arbitrary_decision["out_of_scope_paths"]), arbitrary_decision
        cases["valid_plus_arbitrary_decision"] = "rejected"

        non_wavefront = run_case(root, "non_wavefront")
        assert non_wavefront["status"] == "fail", non_wavefront
        assert "ACTUAL_PATH_OUT_OF_SCOPE" in issue_codes(non_wavefront), non_wavefront
        assert non_wavefront["parent_orchestration_exempted_paths"] == [], non_wavefront
        cases["non_wavefront_dispatch"] = "rejected"

    print(json.dumps({"status": "pass", "cases": cases}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
