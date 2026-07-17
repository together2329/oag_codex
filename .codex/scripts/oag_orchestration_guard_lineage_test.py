#!/usr/bin/env python3
"""Regression tests for orchestration-guard receipt and blocker lineage."""

from __future__ import annotations

import datetime as dt
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any
from unittest.mock import patch


SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from oag_orchestration_guard import (  # noqa: E402
    audit,
    detect_late_receipts,
    detect_repeated_blockers,
    gate_fallback_plan,
)


JsonObject = dict[str, Any]


def write_json(path: Path, payload: JsonObject) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[JsonObject]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def epoch(value: str) -> float:
    return dt.datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()


def write_receipt(
    ip_dir: Path,
    name: str,
    dispatch_id: str,
    created_at: str,
    *,
    status: str = "HANDOFF_PASS",
    mtime: str | None = None,
) -> Path:
    path = ip_dir / "knowledge" / "subagents" / name
    passing = status in {"HANDOFF_PASS", "STATIC_HANDOFF_PASS", "RTL_HANDOFF_PASS"}
    write_json(
        path,
        {
            "schema_version": "oag_subagent_receipt.v1",
            "product_name": "IP Dev Agent",
            "internal_gateway": "Ontology Agent Gateway",
            "ip_id": ip_dir.name,
            "role_name": "oag-lineage-test-agent",
            "registered_id": "oag-lineage-test-agent",
            "dispatch_id": dispatch_id,
            "dispatch_path": f"knowledge/dispatches/{dispatch_id}.json",
            "shard_scope": "guard-lineage-test",
            "stage": "test",
            "status": status,
            "owned_obligations": [],
            "contracts": [],
            "allowed_write_paths": [],
            "changed_paths": [],
            "generated_side_effects": [],
            "evidence_outputs": [],
            "diagnostic_only": False,
            "covers_writes": passing,
            "dispatch_verified": True,
            "implementation_evidence": False,
            "may_claim_complete": False,
            "created_at": created_at,
        },
    )
    if mtime is not None:
        timestamp = epoch(mtime)
        os.utime(path, (timestamp, timestamp))
    return path


def write_dispatch(ip_dir: Path, dispatch_id: str, agent_type: str, stage: str) -> None:
    write_json(
        ip_dir / "knowledge" / "dispatches" / f"{dispatch_id}.json",
        {
            "dispatch_id": dispatch_id,
            "agent_type": agent_type,
            "role_name": agent_type,
            "registered_id": agent_type,
            "stage": stage,
        },
    )


def write_task(
    ip_dir: Path,
    run_id: str,
    *,
    task_dispatch_id: str,
    task_status: str,
    task_receipt_path: str,
    marker_dispatch_id: str,
    marker_status: str = "failed",
    marker_receipt_path: str = "",
    abort_recorded_at: str = "2026-07-16T00:00:10Z",
) -> None:
    write_json(
        ip_dir / "ontology" / "runs" / run_id / "wavefront_task_graph.json",
        {
            "schema_version": "oag_wavefront_task_graph.v1",
            "run_id": run_id,
            "tasks": [
                {
                    "task_id": "TASK_LINEAGE",
                    "status": task_status,
                    "dispatch_id": task_dispatch_id,
                    "receipt_path": task_receipt_path,
                    "abort_marker": {
                        "status": marker_status,
                        "recorded_at": abort_recorded_at,
                        "dispatch_id": marker_dispatch_id,
                        "receipt_path": marker_receipt_path,
                    },
                }
            ],
        },
    )


def assert_no_late(ip_dir: Path, run_id: str) -> None:
    rows = detect_late_receipts(ip_dir, run_id=run_id)
    assert rows == [], rows


def blocker_event(
    run_id: str,
    task_id: str,
    created_at: str,
    *,
    status: str = "failed",
    issues: list[JsonObject] | None = None,
) -> JsonObject:
    details: JsonObject = {}
    if issues is not None:
        details["issues"] = issues
    return {
        "schema_version": "oag_wavefront_event.v1",
        "run_id": run_id,
        "event": "blocked" if issues is not None else "recorded",
        "task_id": task_id,
        "status": status,
        "created_at": created_at,
        "details": details,
    }


def write_blocker_run(
    ip_dir: Path,
    run_id: str,
    tasks: list[tuple[str, str]],
    events: list[JsonObject],
    *,
    closed_at: str = "",
) -> None:
    graph: JsonObject = {
        "schema_version": "oag_wavefront_task_graph.v1",
        "run_id": run_id,
        "tasks": [{"task_id": task_id, "status": status} for task_id, status in tasks],
    }
    if closed_at:
        graph["closed_at"] = closed_at
    write_json(ip_dir / "ontology" / "runs" / run_id / "wavefront_task_graph.json", graph)
    write_jsonl(ip_dir / "knowledge" / "wavefront" / run_id / "events.jsonl", events)


def write_liveness_run(ip_dir: Path, run_id: str) -> None:
    claimed_at = "2000-01-01T00:00:00Z"
    heartbeat_at = "2026-07-16T00:00:00Z"
    task_specs = [
        ("TASK_FRESH", "DISPATCH_FRESH", "claimed", "2999-01-01T00:00:00Z", heartbeat_at),
        ("TASK_DEADLINE_MISSING", "DISPATCH_MISSING", "claimed", None, heartbeat_at),
        ("TASK_DEADLINE_MALFORMED", "DISPATCH_MALFORMED", "claimed", "not-a-timestamp", heartbeat_at),
        ("TASK_DEADLINE_EXPIRED", "DISPATCH_EXPIRED", "claimed", "2000-01-01T00:01:00Z", heartbeat_at),
        ("TASK_SILENT", "DISPATCH_SILENT", "claimed", None, None),
        ("GATE_REVIEW_FRESH", "DISPATCH_GATE_FRESH", "claimed", "2999-01-01T00:00:00Z", heartbeat_at),
        ("GATE_REVIEW_EXPIRED", "DISPATCH_GATE_EXPIRED", "claimed", "2000-01-01T00:01:00Z", heartbeat_at),
        ("TASK_DISPATCH_MISMATCH", "DISPATCH_TASK_CURRENT", "claimed", "2999-01-01T00:00:00Z", heartbeat_at),
        ("TASK_TERMINAL", "DISPATCH_TERMINAL", "handoff_pass", "2999-01-01T00:00:00Z", heartbeat_at),
    ]
    tasks: list[JsonObject] = []
    locks: list[JsonObject] = []
    for task_id, task_dispatch, status, deadline, heartbeat in task_specs:
        task: JsonObject = {
            "task_id": task_id,
            "status": status,
            "claimed_at": claimed_at,
            "dispatch_id": task_dispatch,
        }
        if deadline is not None:
            task["heartbeat_deadline_at"] = deadline
        if heartbeat is not None:
            task["heartbeat_at"] = heartbeat
        tasks.append(task)
        lock_dispatch = "DISPATCH_LOCK_OLD" if task_id == "TASK_DISPATCH_MISMATCH" else task_dispatch
        locks.append(
            {
                "task_id": task_id,
                "path": f"work/{task_id.lower()}.txt",
                "mode": "exclusive_file",
                "dispatch_id": lock_dispatch,
                "claimed_at": claimed_at,
            }
        )
    run_dir = ip_dir / "ontology" / "runs" / run_id
    write_json(
        run_dir / "wavefront_task_graph.json",
        {"schema_version": "oag_wavefront_task_graph.v1", "run_id": run_id, "tasks": tasks},
    )
    write_json(
        run_dir / "ownership_locks.json",
        {"schema_version": "oag_ownership_locks.v1", "run_id": run_id, "locks": locks},
    )
    write_dispatch(ip_dir, "DISPATCH_GATE_FRESH", "oag-gate-reviewer", "tb")
    write_dispatch(ip_dir, "DISPATCH_GATE_EXPIRED", "oag-gate-reviewer", "tb")


def write_review_lifecycle_run(ip_dir: Path, run_id: str) -> None:
    claimed_at = "2000-01-01T00:00:00Z"
    heartbeat_at = "2026-07-16T17:59:30Z"
    task_specs: list[JsonObject] = [
        {
            "task_id": "REVIEW_FIELD_FRESH",
            "status": "review_pending",
            "dispatch_id": "DISPATCH_REVIEW_FIELD_FRESH",
            "recorded_at": "2026-07-16T17:59:30Z",
        },
        {
            "task_id": "REVIEW_EVENT_FRESH",
            "status": "review_pending",
            "dispatch_id": "DISPATCH_REVIEW_EVENT_FRESH",
            "recorded_at": "not-a-timestamp",
        },
        {
            "task_id": "REVIEW_STALE",
            "status": "review_pending",
            "dispatch_id": "DISPATCH_REVIEW_STALE",
            "recorded_at": "2026-07-16T17:50:00Z",
        },
        {
            "task_id": "REVIEW_MISSING",
            "status": "review_pending",
            "dispatch_id": "DISPATCH_REVIEW_MISSING",
        },
        {
            "task_id": "REVIEW_MALFORMED",
            "status": "review_pending",
            "dispatch_id": "DISPATCH_REVIEW_MALFORMED",
            "recorded_at": "not-a-timestamp",
        },
        {
            "task_id": "REVIEW_FUTURE",
            "status": "review_pending",
            "dispatch_id": "DISPATCH_REVIEW_FUTURE",
            "recorded_at": "2026-07-16T18:01:00Z",
        },
        {
            "task_id": "REVIEW_LINEAGE_MISMATCH",
            "status": "review_pending",
            "dispatch_id": "DISPATCH_REVIEW_CURRENT",
            "lock_dispatch_id": "DISPATCH_REVIEW_OLD",
            "recorded_at": "2026-07-16T17:59:30Z",
        },
        {
            "task_id": "TB_PROCESS_EVIDENCE_GATE",
            "status": "review_pending",
            "dispatch_id": "DISPATCH_PROCESS_IMPLEMENTATION",
            "recorded_at": "2026-07-16T17:50:00Z",
        },
        {
            "task_id": "DEDICATED_GATE_STALE",
            "status": "review_pending",
            "dispatch_id": "DISPATCH_DEDICATED_GATE_STALE",
            "recorded_at": "2026-07-16T17:50:00Z",
        },
        {
            "task_id": "DEDICATED_GATE_FRESH",
            "status": "review_pending",
            "dispatch_id": "DISPATCH_DEDICATED_GATE_FRESH",
            "recorded_at": "2026-07-16T17:59:30Z",
        },
        {
            "task_id": "CLAIMED_DEADLINE_EXPIRED",
            "status": "claimed",
            "dispatch_id": "DISPATCH_CLAIMED_EXPIRED",
            "recorded_at": "2026-07-16T17:59:30Z",
            "heartbeat_at": heartbeat_at,
            "heartbeat_deadline_at": "2026-07-16T17:59:59Z",
        },
        {
            "task_id": "CLAIMED_HEARTBEAT_LIVE",
            "status": "claimed",
            "dispatch_id": "DISPATCH_CLAIMED_LIVE",
            "recorded_at": "2026-07-16T17:00:00Z",
            "heartbeat_at": heartbeat_at,
            "heartbeat_deadline_at": "2026-07-16T18:15:00Z",
        },
        {
            "task_id": "REVIEW_DEADLINE_FUTURE_PROGRESS_STALE",
            "status": "review_pending",
            "dispatch_id": "DISPATCH_REVIEW_STALE_FUTURE_DEADLINE",
            "recorded_at": "2026-07-16T17:50:00Z",
            "heartbeat_at": heartbeat_at,
            "heartbeat_deadline_at": "2026-07-16T18:15:00Z",
        },
    ]
    tasks: list[JsonObject] = []
    locks: list[JsonObject] = []
    for spec in task_specs:
        task = {key: value for key, value in spec.items() if key != "lock_dispatch_id"}
        task["claimed_at"] = claimed_at
        tasks.append(task)
        locks.append(
            {
                "task_id": task["task_id"],
                "path": f"work/{str(task['task_id']).lower()}.txt",
                "mode": "exclusive_file",
                "dispatch_id": spec.get("lock_dispatch_id") or task["dispatch_id"],
                "claimed_at": claimed_at,
            }
        )
    run_dir = ip_dir / "ontology" / "runs" / run_id
    write_json(
        run_dir / "wavefront_task_graph.json",
        {"schema_version": "oag_wavefront_task_graph.v1", "run_id": run_id, "tasks": tasks},
    )
    write_json(
        run_dir / "ownership_locks.json",
        {"schema_version": "oag_ownership_locks.v1", "run_id": run_id, "locks": locks},
    )
    write_jsonl(
        ip_dir / "knowledge" / "wavefront" / run_id / "events.jsonl",
        [
            {
                "schema_version": "oag_wavefront_event.v1",
                "run_id": run_id,
                "event": "recorded",
                "task_id": "REVIEW_EVENT_FRESH",
                "status": "review_pending",
                "created_at": "2026-07-16T17:59:45Z",
            },
            {
                "schema_version": "oag_wavefront_event.v1",
                "run_id": run_id,
                "event": "recorded",
                "task_id": "REVIEW_STALE",
                "status": "review_pending",
                "created_at": "2026-07-16T17:50:30Z",
            },
            {
                "schema_version": "oag_wavefront_event.v1",
                "run_id": run_id,
                "event": "recorded",
                "task_id": "REVIEW_MALFORMED",
                "status": "review_pending",
                "created_at": "not-a-timestamp",
            },
            {
                "schema_version": "oag_wavefront_event.v1",
                "run_id": run_id,
                "event": "recorded",
                "task_id": "REVIEW_FUTURE",
                "status": "review_pending",
                "created_at": "2026-07-16T18:01:00Z",
            },
        ],
    )
    write_dispatch(ip_dir, "DISPATCH_PROCESS_IMPLEMENTATION", "oag-tb-implementation-agent", "tb_process_evidence")
    write_dispatch(ip_dir, "DISPATCH_DEDICATED_GATE_STALE", "oag-gate-reviewer", "tb")
    write_dispatch(ip_dir, "DISPATCH_DEDICATED_GATE_FRESH", "oag-gate-reviewer", "tb")


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="oag-guard-lineage-") as tmp:
        ip_dir = Path(tmp) / "ip"

        old_dispatch = "DISPATCH_GUARD_OLD_20260716T000000Z_AAAAAAAA"
        new_dispatch = "DISPATCH_GUARD_NEW_20260716T000000Z_BBBBBBBB"
        shared_path = "knowledge/subagents/successor_shared.json"
        write_receipt(ip_dir, "successor_shared.json", new_dispatch, "2026-07-16T00:00:20Z")
        write_task(
            ip_dir,
            "RUN_SUCCESSFUL_REDISPATCH",
            task_dispatch_id=new_dispatch,
            task_status="handoff_pass",
            task_receipt_path=shared_path,
            marker_dispatch_id=old_dispatch,
            marker_receipt_path=shared_path,
        )
        assert_no_late(ip_dir, "RUN_SUCCESSFUL_REDISPATCH")

        marker_dispatch = "DISPATCH_GUARD_MARKER_20260716T010000Z_CCCCCCCC"
        other_dispatch = "DISPATCH_GUARD_OTHER_20260716T010000Z_DDDDDDDD"
        mismatch_path = "knowledge/subagents/mismatched_dispatch.json"
        write_receipt(ip_dir, "mismatched_dispatch.json", other_dispatch, "2026-07-16T00:00:20Z")
        write_task(
            ip_dir,
            "RUN_MISMATCHED_RECEIPT",
            task_dispatch_id=marker_dispatch,
            task_status="failed",
            task_receipt_path=mismatch_path,
            marker_dispatch_id=marker_dispatch,
            marker_receipt_path=mismatch_path,
        )
        assert_no_late(ip_dir, "RUN_MISMATCHED_RECEIPT")

        late_dispatch = "DISPATCH_GUARD_LATE_20260716T020000Z_EEEEEEEE"
        late_path = "knowledge/subagents/genuine_late.json"
        write_receipt(
            ip_dir,
            "genuine_late.json",
            late_dispatch,
            "2026-07-16T00:00:20Z",
            mtime="2026-07-16T00:00:05Z",
        )
        write_task(
            ip_dir,
            "RUN_GENUINE_LATE",
            task_dispatch_id=late_dispatch,
            task_status="failed",
            task_receipt_path=late_path,
            marker_dispatch_id=late_dispatch,
            marker_receipt_path=late_path,
        )
        late_rows = detect_late_receipts(ip_dir, run_id="RUN_GENUINE_LATE")
        assert len(late_rows) == 1, late_rows
        assert late_rows[0]["dispatch_id"] == late_dispatch, late_rows
        assert late_rows[0]["receipt_created_at"] == "2026-07-16T00:00:20Z", late_rows

        predecessor_dispatch = "DISPATCH_GUARD_PRE_20260716T030000Z_FFFFFFFF"
        successor_dispatch = "DISPATCH_GUARD_SUCCESSOR_20260716T030000Z_11111111"
        predecessor_path = "knowledge/subagents/pre_abort_touched_late.json"
        successor_path = "knowledge/subagents/stale_marker_successor.json"
        write_receipt(
            ip_dir,
            "pre_abort_touched_late.json",
            predecessor_dispatch,
            "2026-07-16T00:00:05Z",
            mtime="2026-07-16T00:00:30Z",
        )
        write_receipt(ip_dir, "stale_marker_successor.json", successor_dispatch, "2026-07-16T00:00:20Z")
        write_task(
            ip_dir,
            "RUN_STALE_MARKER_PRE_ABORT",
            task_dispatch_id=successor_dispatch,
            task_status="handoff_pass",
            task_receipt_path=successor_path,
            marker_dispatch_id=predecessor_dispatch,
            marker_receipt_path=predecessor_path,
        )
        assert_no_late(ip_dir, "RUN_STALE_MARKER_PRE_ABORT")

        stale_dispatch = "DISPATCH_GUARD_STALE_20260716T040000Z_22222222"
        current_dispatch = "DISPATCH_GUARD_CURRENT_20260716T040000Z_33333333"
        stale_late_path = "knowledge/subagents/stale_dispatch_late.json"
        current_path = "knowledge/subagents/current_success.json"
        write_receipt(ip_dir, "stale_dispatch_late.json", stale_dispatch, "2026-07-16T00:00:20Z")
        write_receipt(ip_dir, "current_success.json", current_dispatch, "2026-07-16T00:00:25Z")
        write_task(
            ip_dir,
            "RUN_STALE_MARKER_MIXED",
            task_dispatch_id=current_dispatch,
            task_status="handoff_pass",
            task_receipt_path=current_path,
            marker_dispatch_id=stale_dispatch,
            marker_receipt_path=current_path,
        )
        stale_rows = detect_late_receipts(ip_dir, run_id="RUN_STALE_MARKER_MIXED")
        assert len(stale_rows) == 1, stale_rows
        assert stale_rows[0]["dispatch_id"] == stale_dispatch, stale_rows
        assert stale_rows[0]["current_dispatch_id"] == current_dispatch, stale_rows
        assert stale_rows[0]["receipt_path"] == stale_late_path, stale_rows

        invalid_dispatch = "DISPATCH_GUARD_INVALID_20260716T050000Z_44444444"
        invalid_path = "knowledge/subagents/invalid_receipt_state.json"
        write_receipt(ip_dir, "invalid_receipt_state.json", invalid_dispatch, "2026-07-16T00:00:20Z", status="WORKING")
        write_task(
            ip_dir,
            "RUN_INVALID_RECEIPT_STATE",
            task_dispatch_id=invalid_dispatch,
            task_status="failed",
            task_receipt_path=invalid_path,
            marker_dispatch_id=invalid_dispatch,
            marker_receipt_path=invalid_path,
        )
        assert_no_late(ip_dir, "RUN_INVALID_RECEIPT_STATE")

        equal_dispatch = "DISPATCH_GUARD_EQUAL_20260716T060000Z_55555555"
        equal_path = "knowledge/subagents/equal_chronology.json"
        write_receipt(ip_dir, "equal_chronology.json", equal_dispatch, "2026-07-16T00:00:10Z")
        write_task(
            ip_dir,
            "RUN_EQUAL_CHRONOLOGY",
            task_dispatch_id=equal_dispatch,
            task_status="failed",
            task_receipt_path=equal_path,
            marker_dispatch_id=equal_dispatch,
            marker_receipt_path=equal_path,
        )
        assert_no_late(ip_dir, "RUN_EQUAL_CHRONOLOGY")

        open_run = "RUN_REPEATED_OPEN"
        open_events = [
            blocker_event(open_run, "TASK_OPEN", f"2026-07-16T07:00:0{index}Z")
            for index in range(1, 4)
        ]
        write_blocker_run(ip_dir, open_run, [("TASK_OPEN", "inconclusive")], open_events)
        open_rows = detect_repeated_blockers(ip_dir, run_id=open_run)
        assert open_rows == [
            {
                "key": f"{open_run}:TASK_OPEN:failed",
                "count": 3,
                "latest_at": "2026-07-16T07:00:03Z",
            }
        ], open_rows

        duplicate_run = "RUN_REPEATED_EVENT_DEDUP"
        duplicate_issue = {"code": "CLAIM_SCOPE", "path": "TASK_DUP"}
        duplicate_events = [
            blocker_event(
                duplicate_run,
                "TASK_DUP",
                "2026-07-16T07:10:01Z",
                status="blocked",
                issues=[duplicate_issue, dict(duplicate_issue)],
            ),
            blocker_event(
                duplicate_run,
                "TASK_DUP",
                "2026-07-16T07:10:02Z",
                status="blocked",
                issues=[duplicate_issue],
            ),
        ]
        write_blocker_run(ip_dir, duplicate_run, [("TASK_DUP", "blocked")], duplicate_events)
        duplicate_rows = detect_repeated_blockers(ip_dir, run_id=duplicate_run, threshold=1)
        assert len(duplicate_rows) == 1 and duplicate_rows[0]["count"] == 2, duplicate_rows
        assert detect_repeated_blockers(ip_dir, run_id=duplicate_run) == []

        resolved_run = "RUN_REPEATED_RESOLVED"
        resolved_events = [
            blocker_event(resolved_run, "TASK_RESOLVED", f"2026-07-16T07:20:0{index}Z")
            for index in range(1, 5)
        ]
        write_blocker_run(ip_dir, resolved_run, [("TASK_RESOLVED", "handoff_pass")], resolved_events)
        assert detect_repeated_blockers(ip_dir, run_id=resolved_run) == []

        closed_run = "RUN_REPEATED_CLOSED"
        closed_events = [
            blocker_event(closed_run, "TASK_CLOSED_RUN", f"2026-07-16T07:30:0{index}Z", status="inconclusive")
            for index in range(1, 4)
        ]
        write_blocker_run(
            ip_dir,
            closed_run,
            [("TASK_CLOSED_RUN", "inconclusive")],
            closed_events,
            closed_at="2026-07-16T07:30:04Z",
        )
        assert detect_repeated_blockers(ip_dir, run_id=closed_run) == []

        retry_run = "RUN_REPEATED_RETRY_ACTIVE"
        retry_events = [
            *[
                blocker_event(retry_run, "TASK_PENDING", f"2026-07-16T07:40:0{index}Z")
                for index in range(1, 4)
            ],
            *[
                blocker_event(retry_run, "TASK_CLAIMED", f"2026-07-16T07:41:0{index}Z")
                for index in range(1, 4)
            ],
        ]
        write_blocker_run(
            ip_dir,
            retry_run,
            [("TASK_PENDING", "pending"), ("TASK_CLAIMED", "claimed")],
            retry_events,
        )
        retry_rows = detect_repeated_blockers(ip_dir, run_id=retry_run)
        assert [row["key"] for row in retry_rows] == [
            f"{retry_run}:TASK_CLAIMED:failed",
            f"{retry_run}:TASK_PENDING:failed",
        ], retry_rows

        chronology_run = "RUN_REPEATED_CHRONOLOGY"
        chronology_events = [
            blocker_event(chronology_run, "TASK_TIME", "2026-07-16T07:50:30Z"),
            blocker_event(chronology_run, "TASK_TIME", "2026-07-16T07:50:10Z"),
            blocker_event(chronology_run, "TASK_TIME", "2026-07-16T07:50:20Z"),
        ]
        write_blocker_run(ip_dir, chronology_run, [("TASK_TIME", "failed")], chronology_events)
        chronology_rows = detect_repeated_blockers(ip_dir, run_id=chronology_run)
        assert chronology_rows[0]["latest_at"] == "2026-07-16T07:50:30Z", chronology_rows

        orphan_run = "RUN_REPEATED_ORPHAN"
        orphan_events = [
            blocker_event(orphan_run, "TASK_ORPHAN", f"2026-07-16T08:00:0{index}Z")
            for index in range(1, 4)
        ]
        write_blocker_run(ip_dir, orphan_run, [("TASK_CURRENT", "failed")], orphan_events)
        assert detect_repeated_blockers(ip_dir, run_id=orphan_run) == []

        liveness_run = "RUN_HEARTBEAT_LIVENESS"
        write_liveness_run(ip_dir, liveness_run)
        liveness = audit(ip_dir, run_id=liveness_run, stale_seconds=1, progress_seconds=1)
        stale_ids = {str(row.get("task_id") or "") for row in liveness["stale_locks"]}
        assert "TASK_FRESH" not in stale_ids, liveness
        assert "GATE_REVIEW_FRESH" not in stale_ids, liveness
        assert stale_ids == {
            "TASK_DEADLINE_MISSING",
            "TASK_DEADLINE_MALFORMED",
            "TASK_DEADLINE_EXPIRED",
            "TASK_SILENT",
            "GATE_REVIEW_EXPIRED",
            "TASK_DISPATCH_MISMATCH",
            "TASK_TERMINAL",
        }, liveness
        assert [row["task_id"] for row in liveness["stale_gate_locks"]] == ["GATE_REVIEW_EXPIRED"], liveness
        assert [row["task_id"] for row in liveness["claimed_without_progress"]] == ["TASK_SILENT"], liveness
        issue_codes = [row["code"] for row in liveness["issues"]]
        assert issue_codes.count("STALE_ACTIVE_LOCK") == len(stale_ids), liveness
        assert issue_codes.count("GATE_REVIEWER_STUCK") == 1, liveness
        assert issue_codes.count("CLAIMED_TASK_NO_PROGRESS_EVIDENCE") == 1, liveness
        fallback = gate_fallback_plan(ip_dir, run_id=liveness_run, stale_seconds=1, write=False)
        assert fallback["summary"]["hung_gate_lock_count"] == 1, fallback
        assert fallback["fallback_actions"][0]["source_task_id"] == "GATE_REVIEW_EXPIRED", fallback

        review_run = "RUN_REVIEW_LIFECYCLE"
        review_ip_dir = Path(tmp) / "review_ip"
        write_review_lifecycle_run(review_ip_dir, review_run)
        with patch("oag_orchestration_guard.utc_now", return_value="2026-07-16T18:00:00Z"):
            review = audit(review_ip_dir, run_id=review_run, stale_seconds=60, progress_seconds=60)
            review_fallback = gate_fallback_plan(review_ip_dir, run_id=review_run, stale_seconds=60, write=False)
        review_stale_ids = {str(row.get("task_id") or "") for row in review["stale_locks"]}
        assert {
            "REVIEW_FIELD_FRESH",
            "REVIEW_EVENT_FRESH",
            "DEDICATED_GATE_FRESH",
            "CLAIMED_HEARTBEAT_LIVE",
        }.isdisjoint(review_stale_ids), review
        assert review_stale_ids == {
            "REVIEW_STALE",
            "REVIEW_MISSING",
            "REVIEW_MALFORMED",
            "REVIEW_FUTURE",
            "REVIEW_LINEAGE_MISMATCH",
            "TB_PROCESS_EVIDENCE_GATE",
            "DEDICATED_GATE_STALE",
            "CLAIMED_DEADLINE_EXPIRED",
            "REVIEW_DEADLINE_FUTURE_PROGRESS_STALE",
        }, review
        assert [row["task_id"] for row in review["stale_gate_locks"]] == ["DEDICATED_GATE_STALE"], review
        assert review["claimed_without_progress"] == [], review
        review_issue_codes = [row["code"] for row in review["issues"]]
        assert review_issue_codes.count("STALE_ACTIVE_LOCK") == len(review_stale_ids), review
        assert review_issue_codes.count("GATE_REVIEWER_STUCK") == 1, review
        assert review_fallback["summary"]["hung_gate_lock_count"] == 1, review_fallback
        assert review_fallback["fallback_actions"][0]["source_task_id"] == "DEDICATED_GATE_STALE", review_fallback

    print(
        json.dumps(
            {
                "heartbeat_liveness_tests": 10,
                "late_receipt_tests": 7,
                "repeated_blocker_tests": 7,
                "review_lifecycle_tests": 13,
                "status": "pass",
                "tests": 37,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
