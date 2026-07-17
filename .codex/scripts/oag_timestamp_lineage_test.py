#!/usr/bin/env python3
"""Focused regressions for causal timestamp lineage across OAG records."""

from __future__ import annotations

import argparse
from contextlib import nullcontext
import json
from pathlib import Path
import subprocess
import tempfile
from unittest.mock import patch

import oag_dispatch_support
import oag_wavefront_core
import oag_wavefront_records
from oag_main_write_gate_lineage_test import run_gate, write_json, write_receipt_lineage


def prepare_locked_project(root: Path) -> Path:
    ip = root / "ip"
    (ip / "rtl").mkdir(parents=True)
    write_json(
        ip / "ontology" / "scope_lock.json",
        {"schema_version": "oag_scope_lock.v1", "ip": ip.name, "state": "locked"},
    )
    (ip / "rtl" / "a.sv").write_text("module a_old; endmodule\n", encoding="utf-8")
    subprocess.run(["git", "init"], cwd=root, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "oag-timestamp@example.invalid"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.name", "OAG Timestamp Test"], cwd=root, check=True)
    subprocess.run(["git", "add", "."], cwd=root, check=True)
    subprocess.run(["git", "commit", "-m", "baseline"], cwd=root, check=True, capture_output=True)
    (ip / "rtl" / "a.sv").write_text("module a_new; endmodule\n", encoding="utf-8")
    return ip


def gate_scenario(**timestamps: str) -> dict:
    with tempfile.TemporaryDirectory(prefix="oag-timestamp-lineage-") as tmp:
        project = Path(tmp)
        ip = prepare_locked_project(project)
        write_receipt_lineage(
            project,
            ip,
            run_id="WF_TIMESTAMP",
            task_id="RTL_TIMESTAMP",
            hour=4,
            output_paths=["rtl/a.sv"],
            changed_paths=["rtl/a.sv"],
            **timestamps,
        )
        return run_gate(project, ip)


def assert_gate_passed(payload: dict) -> None:
    assert payload["returncode"] == 0 and payload["status"] == "pass", payload


def assert_gate_rejected_lineage(payload: dict, note: str = "") -> None:
    assert payload["returncode"] != 0 and payload["status"] == "fail", payload
    assert any(item.get("code") == "MAIN_AGENT_WRITE_WITHOUT_SUBAGENT" for item in payload["issues"]), payload
    rows = payload["results"][0]["subagent_receipts"]
    if note:
        assert any(note in row.get("provenance_notes", []) for row in rows), payload
    else:
        assert any(row.get("attestation") in {"invalid", "terminal_invalid"} for row in rows), payload


def test_dispatch_writer_uses_one_timestamp() -> None:
    with tempfile.TemporaryDirectory(prefix="oag-dispatch-timestamp-") as tmp:
        project = Path(tmp)
        ip = project / "ip"
        ip.mkdir()
        args = argparse.Namespace(
            ip_dir=str(ip),
            agent_type="oag-tooling-maintainer",
            role_name="",
            role_kind="",
            registered_id="",
            stage="timestamp_test",
            owned_obligation=[],
            contract=[],
            allowed_write_path=[],
            allowed_tool_side_effect=[],
            receipt_path=str(ip / "knowledge" / "subagents" / "receipt.json"),
            wavefront_run_id="",
            task_id="",
            ownership_mode="",
        )
        with (
            patch.object(oag_dispatch_support, "PROJECT_ROOT", project),
            patch.object(oag_dispatch_support, "git_status_paths", return_value=("", [])),
            patch.object(oag_dispatch_support, "hash_known_paths", return_value={}),
            patch.object(
                oag_dispatch_support,
                "utc_now",
                side_effect=["2026-07-16T04:00:00Z", "2026-07-16T04:00:01Z"],
            ) as now,
        ):
            dispatch = oag_dispatch_support.create_dispatch(args)["dispatch"]
        assert now.call_count == 1, now.call_count
        assert dispatch["baseline"]["created_at"] == dispatch["created_at"] == "2026-07-16T04:00:00Z", dispatch


def test_record_writer_uses_one_timestamp() -> None:
    with tempfile.TemporaryDirectory(prefix="oag-record-timestamp-") as tmp:
        run = oag_wavefront_core.WavefrontRun(Path(tmp), "WF_RECORD_TIMESTAMP")
        graph = {"tasks": [{"task_id": "TASK", "status": "claimed", "barrier_outputs": []}]}
        locks = {"locks": []}
        barriers = {"tokens": []}
        captured: list[oag_wavefront_core.WavefrontEvent] = []
        request = oag_wavefront_records.RecordRequest(run, "TASK", "failed")
        with (
            patch.object(oag_wavefront_records, "run_state_lock", return_value=nullcontext()),
            patch.object(oag_wavefront_records, "load_graph", return_value=graph),
            patch.object(oag_wavefront_records, "load_locks", return_value=locks),
            patch.object(oag_wavefront_records, "load_barriers", return_value=barriers),
            patch.object(oag_wavefront_records, "write_graph"),
            patch.object(oag_wavefront_records, "write_locks"),
            patch.object(oag_wavefront_records, "write_barriers"),
            patch.object(oag_wavefront_records, "append_event", side_effect=captured.append),
            patch.object(
                oag_wavefront_records,
                "utc_now",
                side_effect=["2026-07-16T04:00:00Z", "2026-07-16T04:00:01Z"],
            ) as now,
        ):
            result = oag_wavefront_records.record_wavefront_task(request)
        assert result["status"] == "pass", result
        assert now.call_count == 1, now.call_count
        assert graph["tasks"][0]["recorded_at"] == captured[0].created_at == "2026-07-16T04:00:00Z"


def test_explicit_event_timestamp_is_preserved() -> None:
    with tempfile.TemporaryDirectory(prefix="oag-event-timestamp-") as tmp:
        run = oag_wavefront_core.WavefrontRun(Path(tmp), "WF_EVENT_TIMESTAMP")
        expected = "2026-07-16T04:00:00Z"
        event = oag_wavefront_core.WavefrontEvent(run, "recorded", created_at=expected)
        with patch.object(oag_wavefront_core, "utc_now", side_effect=AssertionError("unexpected utc_now")):
            oag_wavefront_core.append_event(event)
        event_path = oag_wavefront_core.graph_paths(run)["events"]
        row = json.loads(event_path.read_text(encoding="utf-8"))
        assert row["created_at"] == expected, row


def main() -> int:
    test_dispatch_writer_uses_one_timestamp()
    test_record_writer_uses_one_timestamp()
    test_explicit_event_timestamp_is_preserved()

    assert_gate_passed(gate_scenario())
    assert_gate_passed(
        gate_scenario(
            baseline_at="2026-07-16T03:59:59Z",
            task_recorded_at="2026-07-16T04:00:04Z",
        )
    )
    assert_gate_rejected_lineage(
        gate_scenario(baseline_at="2026-07-16T04:00:01Z"),
        "DISPATCH_TIMESTAMP",
    )
    assert_gate_rejected_lineage(
        gate_scenario(task_recorded_at="2026-07-16T04:00:06Z"),
        "WAVEFRONT_DECISION_ANCHOR",
    )
    assert_gate_rejected_lineage(
        gate_scenario(decision_at="2026-07-16T04:00:06Z"),
        "WAVEFRONT_TERMINAL_EVENT",
    )
    assert_gate_rejected_lineage(
        gate_scenario(review_at="2026-07-16T04:00:06Z"),
    )

    print(json.dumps({"status": "pass", "tests": 9}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
