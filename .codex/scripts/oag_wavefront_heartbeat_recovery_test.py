#!/usr/bin/env python3
"""Focused regressions for wavefront heartbeat liveness recovery."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from typing import Callable
from unittest.mock import patch


SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import oag_wavefront_records  # noqa: E402
from oag_wavefront_core import JsonObject, WavefrontRun, graph_paths  # noqa: E402
from oag_wavefront_graph import load_barriers, load_graph, load_locks  # noqa: E402
from oag_wavefront_validation import verify_invariants  # noqa: E402


STALE_DEADLINE = "2000-01-01T00:00:00Z"
FUTURE_DEADLINE = "2999-01-01T00:00:00Z"
HEARTBEAT_AT = "2026-07-17T00:00:00Z"
RENEWED_DEADLINE = "2999-01-01T00:15:00Z"


def write_json(path: Path, payload: JsonObject) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def task(task_id: str, deadline: str | None) -> JsonObject:
    payload: JsonObject = {
        "task_id": task_id,
        "kind": "write",
        "phase": "heartbeat_test",
        "agent_type": "oag-custom-worker",
        "depends_on": [],
        "barrier_inputs": [],
        "barrier_outputs": [],
        "allowed_write_paths": [f"rtl/{task_id.lower()}.sv"],
        "shared_artifacts": [],
        "stale_if_paths_changed": [],
        "ownership_mode": "exclusive_file",
        "status": "claimed",
        "claimed_at": "2026-07-16T00:00:00Z",
        "patience_budget_seconds": 900,
        "may_claim_complete": False,
    }
    if deadline is not None:
        payload["heartbeat_deadline_at"] = deadline
    return payload


def prepare_run(root: Path, run_id: str, tasks: list[JsonObject]) -> WavefrontRun:
    ip_dir = root / run_id.lower()
    (ip_dir / "rtl").mkdir(parents=True)
    run = WavefrontRun(ip_dir, run_id)
    now = "2026-07-16T00:00:00Z"
    write_json(
        graph_paths(run)["graph"],
        {
            "schema_version": "oag_wavefront_task_graph.v1",
            "product_name": "IP Dev Agent",
            "internal_gateway": "Ontology Agent Gateway",
            "run_id": run_id,
            "ip_id": ip_dir.name,
            "ip_dir": ".",
            "tasks": tasks,
            "created_at": now,
            "updated_at": now,
        },
    )
    write_json(
        graph_paths(run)["locks"],
        {
            "schema_version": "oag_ownership_locks.v1",
            "product_name": "IP Dev Agent",
            "internal_gateway": "Ontology Agent Gateway",
            "run_id": run_id,
            "ip_id": ip_dir.name,
            "locks": [
                {
                    "task_id": item["task_id"],
                    "path": item["allowed_write_paths"][0],
                    "mode": "exclusive_file",
                    "dispatch_id": f"DISPATCH_{item['task_id']}",
                    "claimed_at": now,
                }
                for item in tasks
            ],
            "updated_at": now,
        },
    )
    write_json(
        graph_paths(run)["barriers"],
        {
            "schema_version": "oag_wavefront_barriers.v1",
            "product_name": "IP Dev Agent",
            "internal_gateway": "Ontology Agent Gateway",
            "run_id": run_id,
            "ip_id": ip_dir.name,
            "tokens": [],
            "updated_at": now,
        },
    )
    return run


def heartbeat(run: WavefrontRun, task_id: str) -> JsonObject:
    with (
        patch.object(oag_wavefront_records, "utc_now", return_value=HEARTBEAT_AT),
        patch.object(oag_wavefront_records, "utc_after", return_value=RENEWED_DEADLINE),
    ):
        return oag_wavefront_records.record_wavefront_heartbeat(
            oag_wavefront_records.HeartbeatRequest(run, task_id, f"progress:{task_id}")
        )


def current_issues(run: WavefrontRun) -> list[JsonObject]:
    return verify_invariants(load_graph(run), load_locks(run), load_barriers(run))


def test_stale_self_recovery(root: Path) -> None:
    run = prepare_run(root, "WF_HEARTBEAT_SELF", [task("TASK_STALE", STALE_DEADLINE)])
    result = heartbeat(run, "TASK_STALE")
    assert result["status"] == "pass", result
    updated = load_graph(run)["tasks"][0]
    assert updated["heartbeat_at"] == HEARTBEAT_AT, updated
    assert updated["heartbeat_deadline_at"] == RENEWED_DEADLINE, updated
    assert updated["heartbeat_message"] == "progress:TASK_STALE", updated
    assert current_issues(run) == [], current_issues(run)


def test_missing_deadline_recovery(root: Path) -> None:
    run = prepare_run(root, "WF_HEARTBEAT_MISSING", [task("TASK_MISSING", None)])
    before = current_issues(run)
    assert [item["code"] for item in before] == ["TASK_HEARTBEAT_DEADLINE_MISSING"], before
    result = heartbeat(run, "TASK_MISSING")
    assert result["status"] == "pass", result
    assert current_issues(run) == [], current_issues(run)


def test_sibling_progress_and_remaining_liveness(root: Path) -> None:
    run = prepare_run(
        root,
        "WF_HEARTBEAT_SIBLING",
        [task("TASK_STALE", STALE_DEADLINE), task("TASK_SIBLING", FUTURE_DEADLINE)],
    )
    sibling_result = heartbeat(run, "TASK_SIBLING")
    assert sibling_result["status"] == "pass", sibling_result
    graph = load_graph(run)
    task_by_id = {item["task_id"]: item for item in graph["tasks"]}
    assert task_by_id["TASK_SIBLING"]["heartbeat_at"] == HEARTBEAT_AT, task_by_id
    assert "heartbeat_at" not in task_by_id["TASK_STALE"], task_by_id
    remaining = current_issues(run)
    assert [(item["code"], item.get("path")) for item in remaining] == [
        ("TASK_HEARTBEAT_STALE", "TASK_STALE")
    ], remaining

    stale_result = heartbeat(run, "TASK_STALE")
    assert stale_result["status"] == "pass", stale_result
    assert current_issues(run) == [], current_issues(run)


def test_structural_invariants_still_reject(root: Path) -> None:
    def missing_graph_field(run: WavefrontRun) -> None:
        graph = load_graph(run)
        graph.pop("product_name")
        write_json(graph_paths(run)["graph"], graph)

    def duplicate_task(run: WavefrontRun) -> None:
        graph = load_graph(run)
        graph["tasks"].append(dict(graph["tasks"][0]))
        write_json(graph_paths(run)["graph"], graph)

    def missing_lock_task(run: WavefrontRun) -> None:
        locks = load_locks(run)
        locks["locks"].append(
            {
                "task_id": "TASK_UNKNOWN",
                "path": "rtl/unknown.sv",
                "mode": "exclusive_file",
                "dispatch_id": "DISPATCH_UNKNOWN",
                "claimed_at": "2026-07-16T00:00:00Z",
            }
        )
        write_json(graph_paths(run)["locks"], locks)

    def invalid_barriers(run: WavefrontRun) -> None:
        barriers = load_barriers(run)
        barriers["tokens"] = "not-a-list"
        write_json(graph_paths(run)["barriers"], barriers)

    mutations: list[tuple[str, Callable[[WavefrontRun], None], str]] = [
        ("SCHEMA", missing_graph_field, "GRAPH_SCHEMA_REQUIRED"),
        ("STRUCTURE", duplicate_task, "DUPLICATE_TASK_ID"),
        ("LOCK", missing_lock_task, "LOCK_TASK_MISSING"),
        ("BARRIER", invalid_barriers, "BARRIER_TOKENS"),
    ]
    for suffix, mutate, expected_code in mutations:
        run = prepare_run(root, f"WF_HEARTBEAT_{suffix}", [task("TASK_TARGET", STALE_DEADLINE)])
        mutate(run)
        result = heartbeat(run, "TASK_TARGET")
        assert result["status"] == "fail", (suffix, result)
        assert expected_code in {item["code"] for item in result["issues"]}, (suffix, result)
        current = load_graph(run)["tasks"][0]
        assert "heartbeat_at" not in current, (suffix, current)
        assert current["heartbeat_deadline_at"] == STALE_DEADLINE, (suffix, current)


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="oag-heartbeat-recovery-") as tmp:
        root = Path(tmp)
        test_stale_self_recovery(root)
        test_missing_deadline_recovery(root)
        test_sibling_progress_and_remaining_liveness(root)
        test_structural_invariants_still_reject(root)
    print(json.dumps({"status": "pass", "tests": 4}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
