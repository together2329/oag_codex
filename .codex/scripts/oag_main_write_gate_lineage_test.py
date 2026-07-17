#!/usr/bin/env python3
"""Regression tests for durable main-write receipt lineage."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


SCRIPTS_DIR = Path(__file__).resolve().parent
MAIN_WRITE_GATE = SCRIPTS_DIR / "oag_main_write_gate.py"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from oag_dispatch_support import dispatch_integrity  # noqa: E402


JsonObject = dict[str, Any]


def write_json(path: Path, payload: JsonObject) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def digest(path: Path) -> str:
    return f"sha256:{hashlib.sha256(path.read_bytes()).hexdigest()}"


def event(run_id: str, created_at: str, kind: str, **extra: Any) -> JsonObject:
    return {
        "schema_version": "oag_wavefront_event.v1",
        "product_name": "IP Dev Agent",
        "internal_gateway": "Ontology Agent Gateway",
        "run_id": run_id,
        "event": kind,
        "created_at": created_at,
        **extra,
    }


def write_events(path: Path, rows: list[JsonObject]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def write_receipt_lineage(
    project: Path,
    ip: Path,
    *,
    run_id: str,
    task_id: str,
    hour: int,
    output_paths: list[str],
    changed_paths: list[str],
    terminal_status: str = "handoff_pass",
    baseline_at: str | None = None,
    review_at: str | None = None,
    decision_at: str | None = None,
    task_recorded_at: str | None = None,
) -> tuple[Path, Path]:
    compact = f"20260716T{hour:02d}0000Z"
    dispatch_id = f"DISPATCH_LINEAGE_{task_id}_{compact}_ABCD1234"
    dispatch_path = ip / "knowledge" / "dispatches" / f"{dispatch_id}.json"
    receipt_path = ip / "knowledge" / "subagents" / f"{run_id}_{task_id}.json"
    decision_id = f"DEC_RTL_CONFORMANCE_{task_id}_{compact}"
    decision_path = ip / "knowledge" / "decisions" / f"{decision_id}.json"
    project_ip = ip.relative_to(project).as_posix()
    project_dispatch = dispatch_path.relative_to(project).as_posix()
    project_receipt = receipt_path.relative_to(project).as_posix()
    stage = "rtl"
    created = f"2026-07-16T{hour:02d}:00:00Z"
    claim_time = f"2026-07-16T{hour:02d}:00:01Z"
    receipt_time = f"2026-07-16T{hour:02d}:00:02Z"
    review_time = f"2026-07-16T{hour:02d}:00:03Z"
    decision_time = f"2026-07-16T{hour:02d}:00:04Z"
    terminal_time = f"2026-07-16T{hour:02d}:00:05Z"
    baseline_time = baseline_at or created
    review_time = review_at or review_time
    decision_time = decision_at or decision_time
    task_recorded_time = task_recorded_at or terminal_time
    task_paths = sorted(output_paths)
    dispatch = {
        "schema_version": "oag_dispatch.v1",
        "product_name": "IP Dev Agent",
        "internal_gateway": "Ontology Agent Gateway",
        "dispatch_id": dispatch_id,
        "dispatch_path": project_dispatch,
        "agent_type": "oag-rtl-implementation-agent",
        "role_name": "oag-rtl-implementation-agent",
        "role_kind": "core",
        "registered_id": "oag-rtl-implementation-agent",
        "ip_id": ip.name,
        "ip_dir": project_ip,
        "stage": stage,
        "owned_obligations": [],
        "contracts": [],
        "allowed_write_paths": [project_receipt, *[f"{project_ip}/{path}" for path in task_paths]],
        "allowed_tool_side_effects": [],
        "receipt_path": project_receipt,
        "may_claim_complete": False,
        "wavefront_run_id": run_id,
        "task_id": task_id,
        "ownership_mode": "exclusive_file",
        "baseline": {"created_at": baseline_time, "git_status_paths": [], "file_hashes": {}},
        "created_at": created,
    }
    dispatch["dispatch_integrity"] = dispatch_integrity(dispatch)
    write_json(dispatch_path, dispatch)

    receipt = {
        "schema_version": "oag_subagent_receipt.v1",
        "product_name": "IP Dev Agent",
        "internal_gateway": "Ontology Agent Gateway",
        "ip_id": ip.name,
        "role_name": dispatch["role_name"],
        "registered_id": dispatch["registered_id"],
        "dispatch_id": dispatch_id,
        "dispatch_path": project_dispatch,
        "wavefront_run_id": run_id,
        "task_id": task_id,
        "ownership_mode": "exclusive_file",
        "shard_scope": task_id.lower(),
        "stage": stage,
        "status": "RTL_HANDOFF_PASS",
        "owned_obligations": [],
        "contracts": [],
        "allowed_write_paths": dispatch["allowed_write_paths"],
        "changed_paths": [f"{project_ip}/{path}" for path in changed_paths],
        "generated_side_effects": [],
        "evidence_outputs": [project_receipt],
        "output_hashes": {path: digest(ip / path) for path in output_paths},
        "diagnostic_only": False,
        "covers_writes": True,
        "dispatch_verified": True,
        "implementation_evidence": True,
        "may_claim_complete": False,
        "created_at": receipt_time,
    }
    write_json(receipt_path, receipt)

    barrier = f"{task_id.lower()}_ready"
    task: JsonObject = {
        "task_id": task_id,
        "kind": "write",
        "phase": stage,
        "agent_type": dispatch["agent_type"],
        "depends_on": [],
        "barrier_inputs": [],
        "barrier_outputs": [barrier] if terminal_status == "handoff_pass" else [],
        "allowed_write_paths": task_paths,
        "shared_artifacts": [],
        "stale_if_paths_changed": [],
        "ownership_mode": "exclusive_file",
        "status": terminal_status,
        "dispatch_id": dispatch_id,
        "receipt_path": receipt_path.relative_to(ip).as_posix(),
        "claimed_at": claim_time,
        "recorded_at": task_recorded_time,
        "patience_budget_seconds": 900,
        "may_claim_complete": False,
    }
    rows = [
        event(
            run_id,
            claim_time,
            "claimed",
            task_id=task_id,
            status="claimed",
            details={"write_paths": task_paths},
        )
    ]
    if terminal_status == "handoff_pass":
        task.update(
            {
                "decision_id": decision_id,
                "decision_path": decision_path.relative_to(ip).as_posix(),
                "decision_type": "rtl_conformance",
            }
        )
        write_json(
            decision_path,
            {
                "schema_version": "oag_wavefront_decision.v1",
                "product_name": "IP Dev Agent",
                "internal_gateway": "Ontology Agent Gateway",
                "decision_id": decision_id,
                "decision_type": "rtl_conformance",
                "target": {"kind": "wavefront_task", "run_id": run_id, "task_id": task_id},
                "verdict": "approved",
                "rationale": {"summary": "approved lineage", "checked_against": [project_receipt], "blockers": []},
                "reviewer": {"kind": "ai", "id": "lineage-reviewer"},
                "unlocks": {"wavefront_status": "handoff_pass", "barrier_outputs": [barrier]},
                "created_at": decision_time,
            },
        )
        rows.extend(
            [
                event(
                    run_id,
                    review_time,
                    "recorded",
                    task_id=task_id,
                    status="review_pending",
                    details={"barrier_outputs": [], "decision": "", "receipt": str(receipt_path.resolve())},
                ),
                event(
                    run_id,
                    terminal_time,
                    "recorded",
                    task_id=task_id,
                    status="handoff_pass",
                    details={"barrier_outputs": [barrier], "decision": str(decision_path.resolve()), "receipt": ""},
                ),
            ]
        )
    else:
        task["abort_marker"] = {
            "dispatch_id": dispatch_id,
            "status": terminal_status,
            "receipt_path": receipt_path.relative_to(ip).as_posix(),
            "recorded_at": task_recorded_time,
        }
        rows.append(
            event(
                run_id,
                terminal_time,
                "recorded",
                task_id=task_id,
                status=terminal_status,
                details={"barrier_outputs": [], "decision": "", "receipt": str(receipt_path.resolve())},
            )
        )

    run_dir = ip / "ontology" / "runs" / run_id
    write_json(
        run_dir / "wavefront_task_graph.json",
        {
            "schema_version": "oag_wavefront_task_graph.v1",
            "product_name": "IP Dev Agent",
            "internal_gateway": "Ontology Agent Gateway",
            "run_id": run_id,
            "ip_id": ip.name,
            "ip_dir": project_ip,
            "tasks": [task],
            "created_at": created,
            "updated_at": terminal_time,
        },
    )
    write_json(
        run_dir / "ownership_locks.json",
        {
            "schema_version": "oag_ownership_locks.v1",
            "product_name": "IP Dev Agent",
            "internal_gateway": "Ontology Agent Gateway",
            "run_id": run_id,
            "ip_id": ip.name,
            "locks": [],
            "updated_at": terminal_time,
        },
    )
    write_events(ip / "knowledge" / "wavefront" / run_id / "events.jsonl", rows)
    return dispatch_path, receipt_path


def run_gate(project: Path, ip: Path) -> JsonObject:
    result = subprocess.run(
        [sys.executable, str(MAIN_WRITE_GATE), "--ip-dir", str(ip), "--json"],
        cwd=project,
        env={**os.environ, "OAG_PROJECT_ROOT": str(project), "OAG_DISABLE_BACKEND": "1"},
        text=True,
        capture_output=True,
        check=False,
    )
    payload = json.loads(result.stdout)
    payload["returncode"] = result.returncode
    return payload


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="oag-main-write-lineage-") as tmp:
        project = Path(tmp)
        ip = project / "ip"
        (ip / "rtl").mkdir(parents=True)
        write_json(
            ip / "ontology" / "scope_lock.json",
            {"schema_version": "oag_scope_lock.v1", "ip": ip.name, "state": "locked"},
        )
        (ip / "rtl" / "a.sv").write_text("module a_old; endmodule\n", encoding="utf-8")
        (ip / "rtl" / "b.sv").write_text("module b_old; endmodule\n", encoding="utf-8")
        subprocess.run(["git", "init"], cwd=project, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.email", "oag-lineage@example.invalid"], cwd=project, check=True)
        subprocess.run(["git", "config", "user.name", "OAG Lineage Test"], cwd=project, check=True)
        subprocess.run(["git", "add", "."], cwd=project, check=True)
        subprocess.run(["git", "commit", "-m", "baseline"], cwd=project, check=True, capture_output=True)

        (ip / "rtl" / "a.sv").write_text("module a_v1; endmodule\n", encoding="utf-8")
        (ip / "rtl" / "b.sv").write_text("module b_v1; endmodule\n", encoding="utf-8")
        write_receipt_lineage(
            project,
            ip,
            run_id="WF_LINEAGE_R1",
            task_id="RTL_SHARD_R1",
            hour=1,
            output_paths=["rtl/a.sv", "rtl/b.sv"],
            changed_paths=["rtl/a.sv"],
        )

        (ip / "rtl" / "a.sv").write_text("module a_v2; endmodule\n", encoding="utf-8")
        write_receipt_lineage(
            project,
            ip,
            run_id="WF_LINEAGE_R2",
            task_id="RTL_SHARD_R2",
            hour=2,
            output_paths=["rtl/a.sv"],
            changed_paths=["rtl/a.sv"],
        )
        malformed = ip / "knowledge" / "subagents" / "historical_missing_dispatch.json"
        write_json(
            malformed,
            {
                "schema_version": "oag_subagent_receipt.v1",
                "role_name": "oag-rtl-implementation-agent",
                "status": "RTL_HANDOFF_PASS",
                "may_claim_complete": False,
                "dispatch_path": "knowledge/dispatches/missing.json",
            },
        )
        passing = run_gate(project, ip)
        assert passing["returncode"] == 0 and passing["status"] == "pass", passing
        result = passing["results"][0]
        selected = {
            path
            for row in result["subagent_receipts"]
            if row.get("provenance_status") == "selected"
            for path in row.get("covered_paths", [])
        }
        assert {"ip/rtl/a.sv", "ip/rtl/b.sv"}.issubset(selected), passing
        assert any(row.get("provenance_status") == "ignored" for row in result["subagent_receipts"]), passing

        (ip / "rtl" / "b.sv").write_text("module b_late_failed; endmodule\n", encoding="utf-8")
        write_receipt_lineage(
            project,
            ip,
            run_id="WF_LINEAGE_ABORT",
            task_id="RTL_SHARD_ABORT",
            hour=3,
            output_paths=["rtl/b.sv"],
            changed_paths=["rtl/b.sv"],
            terminal_status="failed",
        )
        blocked = run_gate(project, ip)
        assert blocked["returncode"] != 0 and blocked["status"] == "fail", blocked
        assert any(
            item.get("code") == "MAIN_AGENT_WRITE_WITHOUT_SUBAGENT" and item.get("path") == "ip/rtl/b.sv"
            for item in blocked["issues"]
        ), blocked
        assert any(
            row.get("attestation") == "aborted" and row.get("provenance_status") == "quarantined"
            for row in blocked["results"][0]["subagent_receipts"]
        ), blocked

    print(json.dumps({"status": "pass", "tests": 3}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
