#!/usr/bin/env python3
"""Protocol-level tests for the OAG App Server thread worker."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


SCRIPTS = Path(__file__).resolve().parent
RUNNER = SCRIPTS / "oag_thread_worker.py"
CONTROL = SCRIPTS / "oag_thread_control.py"
DISPATCH_CLI = SCRIPTS / "oag_dispatch.py"
MAIN_WRITE_GATE = SCRIPTS / "oag_main_write_gate.py"
sys.path.insert(0, str(SCRIPTS))

from oag_dispatch_prompt import build_prompt_contract  # noqa: E402
from oag_dispatch_support import dispatch_integrity  # noqa: E402
from oag_execution_efficiency import build_execution_controls  # noqa: E402
from oag_ip_git import repository_status_paths  # noqa: E402


JsonObject = dict[str, Any]


FAKE_SERVER = r'''#!/usr/bin/env python3
import json
import os
import subprocess
import sys

scenario = os.environ.get("FAKE_SCENARIO", "normal")
resumed = False
turn_id = "turn-test"

def send(value):
    sys.stdout.write(json.dumps(value, separators=(",", ":")) + "\n")
    sys.stdout.flush()

for line in sys.stdin:
    message = json.loads(line)
    method = message.get("method")
    request_id = message.get("id")
    if method == "initialize":
        send({"id": request_id, "result": {}})
    elif method == "thread/start":
        send({"id": request_id, "result": {"thread": {"id": "thread-test"}, "model": "test-model"}})
    elif method == "thread/resume":
        resumed = True
        send({"id": request_id, "result": {"thread": {"id": "thread-test"}, "model": "test-model"}})
    elif method == "thread/read":
        send({"id": request_id, "result": {"thread": {"id": "thread-test", "status": {"type": "notLoaded"}, "updatedAt": 1, "turns": [{"id": turn_id, "status": "interrupted", "error": None, "items": [{"id": "message-test", "type": "agentMessage", "text": "Waiting for an audited steering request."}]}]}}})
    elif method == "turn/start":
        turn_id = "turn-resume" if resumed else "turn-test"
        send({"id": request_id, "result": {"turn": {"id": turn_id}}})
        if scenario == "process_cleanup":
            child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"], start_new_session=True)
            with open(os.environ["FAKE_CHILD_PID_FILE"], "w", encoding="utf-8") as handle:
                handle.write(str(child.pid))
        if scenario == "transient_root_cleanup":
            with open("sm01.aig", "w", encoding="utf-8") as handle:
                handle.write("temporary unresolved miter\n")
        if scenario == "subagent":
            send({"method": "item/completed", "params": {"item": {"id": "agent-call-1", "type": "collabAgentToolCall"}}})
        else:
            total = 80000 if scenario == "warning" else (100000 if scenario in {"budget", "budget_complete"} else 1000)
            send({"method": "thread/tokenUsage/updated", "params": {"threadId": "thread-test", "turnId": turn_id, "tokenUsage": {"total": {"inputTokens": total - 100, "cachedInputTokens": 50, "outputTokens": 100, "reasoningOutputTokens": 25, "totalTokens": total}, "last": {"inputTokens": total - 100, "cachedInputTokens": 50, "outputTokens": 100, "reasoningOutputTokens": 25, "totalTokens": total}}}})
            if scenario in {
                "normal",
                "budget_complete",
                "inconclusive_receipt",
                "invalid_blocker_list",
                "misclassified_generated_path",
                "object_field_list",
                "process_cleanup",
                "string_field_list",
                "transient_root_cleanup",
            }:
                send({"method": "turn/completed", "params": {"threadId": "thread-test", "turn": {"id": turn_id, "status": "completed"}}})
            elif scenario == "failed":
                send({"method": "turn/completed", "params": {"threadId": "thread-test", "turn": {"id": turn_id, "status": "failed"}}})
    elif method == "turn/steer":
        send({"id": request_id, "result": {"turnId": turn_id}})
        send({"method": "turn/completed", "params": {"threadId": "thread-test", "turn": {"id": turn_id, "status": "completed"}}})
    elif method == "turn/interrupt":
        send({"id": request_id, "result": {}})
        send({"method": "turn/completed", "params": {"threadId": "thread-test", "turn": {"id": turn_id, "status": "interrupted"}}})
'''


def write_json(path: Path, payload: JsonObject) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def file_hashes(project: Path, ip: Path) -> dict[str, str]:
    return {
        path.relative_to(project).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(ip.rglob("*"))
        if path.is_file()
    }


def prepare_case(root: Path, scenario: str) -> tuple[Path, Path]:
    project = root / scenario
    ip = project / "ip"
    (ip / "rtl").mkdir(parents=True)
    write_json(ip / "ontology" / "scope_lock.json", {"schema_version": "oag_scope_lock.v1", "ip": "ip", "state": "locked"})
    subprocess.run(["git", "init"], cwd=project, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "thread-test@example.invalid"], cwd=project, check=True)
    subprocess.run(["git", "config", "user.name", "OAG Thread Test"], cwd=project, check=True)
    subprocess.run(["git", "add", "."], cwd=project, check=True)
    subprocess.run(["git", "commit", "-m", "baseline"], cwd=project, check=True, capture_output=True)

    dispatch_id = f"DISPATCH_THREAD_{scenario.upper()}_20260718T000000Z_ABCD1234"
    dispatch_rel = f"ip/knowledge/dispatches/{dispatch_id}.json"
    receipt_rel = f"ip/knowledge/subagents/{dispatch_id}.json"
    manifest_rel = f"ip/knowledge/executions/{dispatch_id}.thread.json"
    event_log_rel = f"ip/knowledge/executions/{dispatch_id}.events.jsonl"
    budget, context = build_execution_controls(
        agent_type="oag-custom-worker",
        stage="draft",
        complexity="simple",
        max_total_tokens=100000,
        max_review_attempts=1,
        model_tier="balanced",
    )
    dispatch: JsonObject = {
        "schema_version": "oag_dispatch.v1",
        "product_name": "IP Dev Agent",
        "internal_gateway": "Ontology Agent Gateway",
        "dispatch_id": dispatch_id,
        "dispatch_path": dispatch_rel,
        "agent_type": "oag-custom-worker",
        "role_name": "oag-custom-worker",
        "role_kind": "custom",
        "registered_id": "oag-custom-worker",
        "ip_id": "ip",
        "ip_dir": "ip",
        "stage": "draft",
        "owned_obligations": [],
        "contracts": [],
        "allowed_write_paths": ["ip/rtl/out.sv", receipt_rel],
        "allowed_tool_side_effects": [event_log_rel, manifest_rel],
        "receipt_path": receipt_rel,
        "may_claim_complete": False,
        "wavefront_run_id": "",
        "task_id": "",
        "ownership_mode": "",
        "execution_budget": budget,
        "context_contract": context,
        "execution_actor": {
            "schema_version": "oag_execution_actor.v1",
            "kind": "worker_thread",
            "isolation": "fresh_thread",
            "resume_limit": 1,
            "subagents_allowed": False,
            "manifest_path": manifest_rel,
            "event_log_path": event_log_rel,
        },
        "baseline": {
            "created_at": "2026-07-18T00:00:00Z",
            "git_status_raw": "",
            "git_status_paths": [],
            "file_hashes": file_hashes(project, ip),
        },
        "created_at": "2026-07-18T00:00:00Z",
    }
    dispatch["dispatch_integrity"] = dispatch_integrity(dispatch)
    dispatch["prompt_contract"] = build_prompt_contract(dispatch)
    dispatch_path = project / dispatch_rel
    write_json(dispatch_path, dispatch)

    output_path = ip / "rtl" / "out.sv"
    output_path.write_text("module out; endmodule\n", encoding="utf-8")
    receipt: JsonObject = {
        "schema_version": "oag_subagent_receipt.v1",
        "product_name": "IP Dev Agent",
        "internal_gateway": "Ontology Agent Gateway",
        "ip_id": "ip",
        "role_name": "oag-custom-worker",
        "registered_id": "oag-custom-worker",
        "dispatch_id": dispatch_id,
        "dispatch_path": dispatch_rel,
        "execution_kind": "worker_thread",
        "thread_id": "thread-test",
        "execution_manifest_path": manifest_rel,
        "shard_scope": scenario,
        "stage": "draft",
        "status": "HANDOFF_PASS",
        "owned_obligations": [],
        "contracts": [],
        "allowed_write_paths": dispatch["allowed_write_paths"],
        "changed_paths": ["ip/rtl/out.sv"],
        "generated_side_effects": [event_log_rel, manifest_rel],
        "evidence_outputs": [receipt_rel],
        "diagnostic_only": False,
        "covers_writes": True,
        "dispatch_verified": True,
        "implementation_evidence": True,
        "may_claim_complete": False,
        "created_at": "2026-07-18T00:00:00Z",
    }
    if scenario == "inconclusive_receipt":
        receipt = {
            "schema_version": "wrong-version",
            "role_name": "oag-custom-reviewer",
            "allowed_write_paths": ["ip/rtl/out.sv"],
            "shard_scope": scenario,
            "status": "INCONCLUSIVE",
            "changed_paths": "ip/rtl/out.sv",
            "generated_side_effects": manifest_rel,
            "evidence_outputs": receipt_rel,
            "covers_writes": True,
            "implementation_evidence": False,
            "tb_methodology_notes": {
                "formal_candidates": ["FPROP_EXAMPLE"],
                "open_methodology_blockers": "candidate-specific assertion is missing",
            },
            "blockers": ["candidate-specific assertion is missing"],
            "created_at": "not-a-timestamp",
        }
    elif scenario == "invalid_blocker_list":
        receipt["status"] = "INCONCLUSIVE"
        receipt["tb_methodology_notes"] = {
            "open_methodology_blockers": ["valid blocker", 7]
        }
        receipt["dispatch_verified"] = False
    elif scenario == "string_field_list":
        receipt["tb_methodology_notes"] = {
            "methodology_profile": ["candidate-specific proof", "nonvacuity checked"],
            "framework": ["Yosys", "Z3"],
            "formal_candidates": "FPROP_EXAMPLE",
        }
        receipt["dispatch_verified"] = False
    elif scenario == "object_field_list":
        receipt["tb_methodology_notes"] = [
            "methodology_profile=candidate-specific safety proof",
            "framework=Yosys plus Z3",
            "architecture_roles=real DUT leaf, independent contract checker",
            "stimulus_strategy=deterministic legal boot plus symbolic fields",
            "coverage_strategy=candidate-specific reachability covers",
            "assertion_hooks=state and side-effect fences",
            "formal_candidates=FPROP_EXAMPLE",
            "open_methodology_blockers=none recorded",
        ]
        receipt["dispatch_verified"] = False
    elif scenario == "misclassified_generated_path":
        receipt["changed_paths"] = []
        receipt["covers_writes"] = False
        receipt["generated_side_effects"] = [
            "ip/rtl/out.sv",
            event_log_rel,
            manifest_rel,
        ]
        receipt["dispatch_verified"] = False
    write_json(project / receipt_rel, receipt)
    return project, dispatch_path


def run_case(root: Path, fake_server: Path, scenario: str, *extra_args: str) -> JsonObject:
    project, dispatch_path = prepare_case(root, scenario)
    result = subprocess.run(
        [
            sys.executable,
            str(RUNNER),
            "--dispatch",
            str(dispatch_path),
            "--task",
            "Exercise the fake worker protocol.",
            "--app-server-command",
            f"{sys.executable} {fake_server}",
            "--timeout-seconds",
            "10",
            *extra_args,
            "--json",
        ],
        cwd=project,
        env={**os.environ, "OAG_PROJECT_ROOT": str(project), "OAG_DISABLE_BACKEND": "1", "FAKE_SCENARIO": scenario},
        text=True,
        capture_output=True,
        check=False,
    )
    payload = json.loads(result.stdout)
    payload["returncode"] = result.returncode
    payload["project"] = str(project)
    payload["dispatch_path"] = str(dispatch_path)
    return payload


def event_methods(path: Path) -> list[str]:
    methods: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        message = row.get("message") if isinstance(row.get("message"), dict) else {}
        if message.get("method"):
            methods.append(str(message["method"]))
    return methods


def event_messages(path: Path) -> list[JsonObject]:
    messages: list[JsonObject] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        message = row.get("message") if isinstance(row.get("message"), dict) else {}
        messages.append(message)
    return messages


def control_acks(path: Path) -> list[JsonObject]:
    values: list[JsonObject] = []
    if not path.is_file():
        return values
    for line in path.read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        if row.get("direction") != "worker_control_ack":
            continue
        message = row.get("message") if isinstance(row.get("message"), dict) else {}
        values.append(message)
    return values


def wait_until(predicate: Any, *, timeout: float = 10.0) -> None:
    import time

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.05)
    raise AssertionError("timed out waiting for test condition")


def test_dispatch_cli_default(root: Path) -> None:
    project = root / "default_dispatch"
    ip = project / "ip"
    (ip / "req").mkdir(parents=True)
    result = subprocess.run(
        [
            sys.executable,
            str(DISPATCH_CLI),
            "create",
            "--ip-dir",
            str(ip),
            "--agent-type",
            "oag-requirement-contract-agent",
            "--stage",
            "draft",
            "--allowed-write-path",
            str(ip / "req" / "draft.md"),
            "--receipt-path",
            str(ip / "knowledge" / "subagents" / "draft.json"),
            "--json",
        ],
        cwd=project,
        env={**os.environ, "OAG_PROJECT_ROOT": str(project), "OAG_DISABLE_BACKEND": "1"},
        text=True,
        capture_output=True,
        check=False,
    )
    payload = json.loads(result.stdout)
    assert result.returncode == 0 and payload["status"] == "pass", payload
    dispatch = payload["dispatch"]
    assert dispatch["execution_actor"]["kind"] == "worker_thread", dispatch
    assert dispatch["execution_actor"]["subagents_allowed"] is False, dispatch
    assert dispatch["execution_actor"]["manifest_path"] in dispatch["allowed_tool_side_effects"], dispatch
    assert dispatch["execution_actor"]["event_log_path"] in dispatch["allowed_tool_side_effects"], dispatch
    assert "Thread-only execution contract:" in dispatch["prompt_contract"], dispatch


def test_git_status_preserves_symlink_path(root: Path) -> None:
    project = root / "git_status_symlink"
    ip = project / "ip"
    target = ip / "rtl"
    scratch = ip / "formal" / "build" / "solver_cwd"
    target.mkdir(parents=True)
    scratch.mkdir(parents=True)
    (target / "dut.sv").write_text("module dut; endmodule\n", encoding="utf-8")
    subprocess.run(["git", "init"], cwd=project, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "thread-test@example.invalid"], cwd=project, check=True)
    subprocess.run(["git", "config", "user.name", "OAG Thread Test"], cwd=project, check=True)
    subprocess.run(["git", "add", "."], cwd=project, check=True)
    subprocess.run(["git", "commit", "-m", "baseline"], cwd=project, check=True, capture_output=True)
    (scratch / "rtl").symlink_to(target, target_is_directory=True)

    _, paths, error = repository_status_paths(ip, project)
    assert error == "", error
    assert "ip/formal/build/solver_cwd/rtl" in paths, paths
    assert "ip/rtl" not in paths, paths


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="oag-thread-worker-") as tmp:
        root = Path(tmp)
        fake_server = root / "fake_app_server.py"
        fake_server.write_text(FAKE_SERVER, encoding="utf-8")
        test_dispatch_cli_default(root)
        test_git_status_preserves_symlink_path(root)

        normal = run_case(root, fake_server, "normal")
        assert normal["returncode"] == 0 and normal["status"] == "pass", normal
        assert normal["token_usage"]["total_tokens"] == 1000, normal
        normal_project = Path(normal["project"])
        normal_events = normal_project / normal["event_log_path"]
        thread_start = next(message for message in event_messages(normal_events) if message.get("method") == "thread/start")
        assert thread_start["params"]["config"] == {
            "features.multi_agent": False,
            "features.child_agents_md": False,
        }, thread_start
        assert thread_start["params"]["model"] == "gpt-5.6-terra", thread_start
        assert thread_start["params"]["sandbox"] == "workspace-write", thread_start
        instructions = thread_start["params"]["developerInstructions"]
        assert "# OAG Agent Common Preamble" in instructions, thread_start
        assert "REGISTERED OAG ROLE PROFILE" in instructions, thread_start
        assert "Role: dynamic custom worker." in instructions, thread_start
        assert "THREAD-ONLY EXECUTION OVERRIDE" in instructions, thread_start
        assert instructions.index("Role: dynamic custom worker.") < instructions.index("THREAD-ONLY EXECUTION OVERRIDE"), thread_start
        assert "Do not load OAG skills" in thread_start["params"]["developerInstructions"], thread_start
        assert "do not open or read the dispatch JSON file" in thread_start["params"]["developerInstructions"], thread_start
        turn_start = next(message for message in event_messages(normal_events) if message.get("method") == "turn/start")
        turn_prompt = turn_start["params"]["input"][0]["text"]
        assert "RECEIPT IDENTITY CONSTANTS" in turn_prompt, turn_start
        assert "- product_name: IP Dev Agent" in turn_prompt, turn_start
        assert "- internal_gateway: Ontology Agent Gateway" in turn_prompt, turn_start
        assert "- role_name: oag-custom-worker" in turn_prompt, turn_start
        assert "RECEIPT JSON SKELETON" in turn_prompt, turn_start
        assert '"dispatch_verified": false' in turn_prompt, turn_start
        gate = subprocess.run(
            [sys.executable, str(MAIN_WRITE_GATE), "--ip-dir", str(normal_project / "ip"), "--json"],
            cwd=normal_project,
            env={**os.environ, "OAG_PROJECT_ROOT": str(normal_project), "OAG_DISABLE_BACKEND": "1"},
            text=True,
            capture_output=True,
            check=False,
        )
        gate_payload = json.loads(gate.stdout)
        assert gate.returncode == 0 and gate_payload["status"] == "pass", gate_payload
        assert gate_payload["results"][0]["executor_receipts"], gate_payload

        normal_manifest = normal_project / normal["manifest_path"]
        running_manifest = json.loads(normal_manifest.read_text(encoding="utf-8"))
        assert running_manifest["model_source"] == "role_default", running_manifest
        assert running_manifest["reasoning_effort_source"] == "role_default", running_manifest
        assert running_manifest["sandbox_source"] == "role_default", running_manifest
        assert running_manifest["budget_warning_tokens"] == 80000, running_manifest
        assert running_manifest["budget_hard_stop_tokens"] == 83334, running_manifest
        assert running_manifest["budget_configured_max_tokens"] == 100000, running_manifest
        role_definition = running_manifest["role_definition"]
        assert role_definition["id"] == "oag-custom-worker", role_definition
        assert role_definition["source_path"] == ".codex/agents/oag-custom-worker.toml", role_definition
        assert role_definition["source_sha256"].startswith("sha256:"), role_definition
        assert role_definition["default_model"] == "gpt-5.6-terra", role_definition
        running_manifest["status"] = "running"
        write_json(normal_manifest, running_manifest)
        running_env = {
            **os.environ,
            "OAG_PROJECT_ROOT": str(normal_project),
            "OAG_DISABLE_BACKEND": "1",
            "OAG_THREAD_EXECUTION_MANIFEST": normal["manifest_path"],
        }
        missing_dispatch_id = subprocess.run(
            [sys.executable, str(MAIN_WRITE_GATE), "--ip-dir", str(normal_project / "ip"), "--json"],
            cwd=normal_project,
            env=running_env,
            text=True,
            capture_output=True,
            check=False,
        )
        assert missing_dispatch_id.returncode != 0, json.loads(missing_dispatch_id.stdout)
        active_execution = subprocess.run(
            [sys.executable, str(MAIN_WRITE_GATE), "--ip-dir", str(normal_project / "ip"), "--json"],
            cwd=normal_project,
            env={**running_env, "OAG_DISPATCH_ID": running_manifest["dispatch_id"]},
            text=True,
            capture_output=True,
            check=False,
        )
        active_payload = json.loads(active_execution.stdout)
        assert active_execution.returncode == 0 and active_payload["status"] == "pass", active_payload
        running_manifest["status"] = "completed"
        write_json(normal_manifest, running_manifest)

        control_project, control_dispatch_path = prepare_case(root, "external_control")
        control_dispatch = json.loads(control_dispatch_path.read_text(encoding="utf-8"))
        control_manifest = control_project / control_dispatch["execution_actor"]["manifest_path"]
        control_events = control_project / control_dispatch["execution_actor"]["event_log_path"]
        control_worker = subprocess.Popen(
            [
                sys.executable,
                str(RUNNER),
                "--dispatch",
                str(control_dispatch_path),
                "--task",
                "Wait for audited external steering.",
                "--app-server-command",
                f"{sys.executable} {fake_server}",
                "--timeout-seconds",
                "10",
                "--json",
            ],
            cwd=control_project,
            env={
                **os.environ,
                "OAG_PROJECT_ROOT": str(control_project),
                "OAG_DISABLE_BACKEND": "1",
                "FAKE_SCENARIO": "external_control",
            },
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        wait_until(
            lambda: control_manifest.is_file()
            and json.loads(control_manifest.read_text(encoding="utf-8")).get("status") == "running"
        )

        status_result = subprocess.run(
            [
                sys.executable,
                str(CONTROL),
                "status",
                "--manifest",
                str(control_manifest),
                "--app-server-command",
                f"{sys.executable} {fake_server}",
                "--json",
            ],
            cwd=control_project,
            env={
                **os.environ,
                "OAG_PROJECT_ROOT": str(control_project),
                "OAG_DISABLE_BACKEND": "1",
                "FAKE_SCENARIO": "external_control",
            },
            text=True,
            capture_output=True,
            check=False,
        )
        status_payload = json.loads(status_result.stdout)
        assert status_result.returncode == 0 and status_payload["live_status"] == "running", status_payload
        assert status_payload["steering_supported"] is True, status_payload
        assert status_payload["control_protocol"] == "oag_thread_control.v1", status_payload
        assert status_payload["status_coherence"] == "active_turn_owned_by_another_app_server", status_payload
        assert status_payload["task"]["latest_agent_messages"][-1]["text"] == (
            "Waiting for an audited steering request."
        ), status_payload

        stale_control = subprocess.run(
            [
                sys.executable,
                str(CONTROL),
                "steer",
                "--manifest",
                str(control_manifest),
                "--message",
                "This stale request must be rejected.",
                "--expected-turn-id",
                "turn-stale",
                "--request-id",
                "STEER_STALE",
                "--json",
            ],
            cwd=control_project,
            env={**os.environ, "OAG_PROJECT_ROOT": str(control_project), "OAG_DISABLE_BACKEND": "1"},
            text=True,
            capture_output=True,
            check=False,
        )
        assert stale_control.returncode == 0 and json.loads(stale_control.stdout)["status"] == "queued", stale_control.stdout
        wait_until(lambda: any(item.get("request_id") == "STEER_STALE" for item in control_acks(control_events)))
        stale_ack = next(item for item in control_acks(control_events) if item.get("request_id") == "STEER_STALE")
        assert stale_ack["status"] == "rejected" and "expected_turn_id" in stale_ack["reason"], stale_ack

        duplicate_control = subprocess.run(
            [
                sys.executable,
                str(CONTROL),
                "steer",
                "--manifest",
                str(control_manifest),
                "--message",
                "Duplicate request.",
                "--request-id",
                "STEER_STALE",
                "--json",
            ],
            cwd=control_project,
            env={**os.environ, "OAG_PROJECT_ROOT": str(control_project), "OAG_DISABLE_BACKEND": "1"},
            text=True,
            capture_output=True,
            check=False,
        )
        assert duplicate_control.returncode != 0 and "duplicate steering request_id" in duplicate_control.stdout, duplicate_control.stdout

        applied_control = subprocess.run(
            [
                sys.executable,
                str(CONTROL),
                "steer",
                "--manifest",
                str(control_manifest),
                "--message",
                "Use the concrete blocker correction and finish the assigned task.",
                "--request-id",
                "STEER_APPLY",
                "--json",
            ],
            cwd=control_project,
            env={**os.environ, "OAG_PROJECT_ROOT": str(control_project), "OAG_DISABLE_BACKEND": "1"},
            text=True,
            capture_output=True,
            check=False,
        )
        assert applied_control.returncode == 0 and json.loads(applied_control.stdout)["status"] == "queued", applied_control.stdout
        control_stdout, control_stderr = control_worker.communicate(timeout=10)
        control_payload = json.loads(control_stdout)
        assert control_worker.returncode == 0 and control_payload["status"] == "pass", (control_payload, control_stderr)
        applied_ack = next(item for item in control_acks(control_events) if item.get("request_id") == "STEER_APPLY")
        assert applied_ack["status"] == "applied", applied_ack
        completed_control_manifest = json.loads(control_manifest.read_text(encoding="utf-8"))
        assert completed_control_manifest["steering_request_count"] == 2, completed_control_manifest
        assert completed_control_manifest["steering_applied_count"] == 1, completed_control_manifest
        assert completed_control_manifest["steering_rejected_count"] == 1, completed_control_manifest

        cleanup_pid_file = root / "process_cleanup.pid"
        cleanup_project, cleanup_dispatch_path = prepare_case(root, "process_cleanup")
        cleanup = subprocess.run(
            [
                sys.executable,
                str(RUNNER),
                "--dispatch",
                str(cleanup_dispatch_path),
                "--task",
                "Complete while a fake long-running child exists.",
                "--app-server-command",
                f"{sys.executable} {fake_server}",
                "--timeout-seconds",
                "10",
                "--json",
            ],
            cwd=cleanup_project,
            env={
                **os.environ,
                "OAG_PROJECT_ROOT": str(cleanup_project),
                "OAG_DISABLE_BACKEND": "1",
                "FAKE_SCENARIO": "process_cleanup",
                "FAKE_CHILD_PID_FILE": str(cleanup_pid_file),
            },
            text=True,
            capture_output=True,
            check=False,
        )
        cleanup_payload = json.loads(cleanup.stdout)
        assert cleanup.returncode == 0 and cleanup_payload["status"] == "pass", cleanup_payload
        cleanup_pid = int(cleanup_pid_file.read_text(encoding="utf-8"))
        try:
            os.kill(cleanup_pid, 0)
        except ProcessLookupError:
            pass
        else:
            raise AssertionError(f"App Server descendant survived close: {cleanup_pid}")

        transient = run_case(root, fake_server, "transient_root_cleanup")
        assert transient["returncode"] == 0 and transient["status"] == "pass", transient
        transient_project = Path(transient["project"])
        assert not (transient_project / "sm01.aig").exists(), transient
        transient_events = transient_project / transient["event_log_path"]
        cleanup_rows = [
            json.loads(line)
            for line in transient_events.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        cleanup_messages = [
            row["message"]
            for row in cleanup_rows
            if row.get("direction") == "worker_runtime_cleanup"
        ]
        assert cleanup_messages == [
            {
                "path": "sm01.aig",
                "reason": "yosys-abc unresolved-miter scratch output",
                "sha256": cleanup_messages[0]["sha256"],
                "size_bytes": 27,
            }
        ], cleanup_messages

        inconclusive = run_case(root, fake_server, "inconclusive_receipt")
        assert inconclusive["returncode"] == 0 and inconclusive["status"] == "pass", inconclusive
        assert inconclusive["receipt_finalization"]["status"] == "pass", inconclusive
        assert inconclusive["receipt_finalization"]["semantic_status_before"] == "INCONCLUSIVE", inconclusive
        assert inconclusive["receipt_finalization"]["semantic_status_after"] == "INCONCLUSIVE", inconclusive
        assert inconclusive["receipt_finalization"]["preverification"]["worker_receipt_preverify"] is True, inconclusive
        inconclusive_project = Path(inconclusive["project"])
        inconclusive_dispatch = json.loads(Path(inconclusive["dispatch_path"]).read_text(encoding="utf-8"))
        inconclusive_receipt = json.loads(
            (inconclusive_project / inconclusive_dispatch["receipt_path"]).read_text(encoding="utf-8")
        )
        assert inconclusive_receipt["status"] == "INCONCLUSIVE", inconclusive_receipt
        assert inconclusive_receipt["blockers"] == ["candidate-specific assertion is missing"], inconclusive_receipt
        assert inconclusive_receipt["tb_methodology_notes"]["open_methodology_blockers"] == [
            "candidate-specific assertion is missing"
        ], inconclusive_receipt
        assert inconclusive_receipt["allowed_write_paths"] == inconclusive_dispatch["allowed_write_paths"], inconclusive_receipt
        assert inconclusive_receipt["diagnostic_only"] is False, inconclusive_receipt
        assert inconclusive_receipt["dispatch_verified"] is True, inconclusive_receipt
        assert inconclusive_receipt["thread_id"] == "thread-test", inconclusive_receipt
        inconclusive_gate = subprocess.run(
            [sys.executable, str(MAIN_WRITE_GATE), "--ip-dir", str(inconclusive_project / "ip"), "--json"],
            cwd=inconclusive_project,
            env={**os.environ, "OAG_PROJECT_ROOT": str(inconclusive_project), "OAG_DISABLE_BACKEND": "1"},
            text=True,
            capture_output=True,
            check=False,
        )
        inconclusive_gate_payload = json.loads(inconclusive_gate.stdout)
        assert inconclusive_gate.returncode != 0 and inconclusive_gate_payload["status"] == "fail", inconclusive_gate_payload
        assert any(
            item.get("code") == "MAIN_AGENT_WRITE_WITHOUT_SUBAGENT"
            for item in inconclusive_gate_payload["issues"]
        ), inconclusive_gate_payload
        inconclusive_row = next(
            row
            for row in inconclusive_gate_payload["results"][0]["executor_receipts"]
            if row.get("dispatch_id") == inconclusive_dispatch["dispatch_id"]
        )
        assert inconclusive_row["dispatch_verified"] is True, inconclusive_row
        assert inconclusive_row["status"] == "INCONCLUSIVE", inconclusive_row
        assert inconclusive_row["provenance_notes"] == [], inconclusive_row
        assert inconclusive_row["covers_writes"] is False, inconclusive_row

        invalid_blocker_list = run_case(root, fake_server, "invalid_blocker_list")
        assert invalid_blocker_list["returncode"] != 0 and invalid_blocker_list["status"] == "fail", invalid_blocker_list
        assert invalid_blocker_list["receipt_finalization"]["status"] == "preverify_fail", invalid_blocker_list
        assert any(
            item.get("code") == "RECEIPT_SCHEMA_TYPE"
            for item in invalid_blocker_list["verification"]["issues"]
        ), invalid_blocker_list
        invalid_project = Path(invalid_blocker_list["project"])
        invalid_dispatch = json.loads(Path(invalid_blocker_list["dispatch_path"]).read_text(encoding="utf-8"))
        invalid_receipt = json.loads((invalid_project / invalid_dispatch["receipt_path"]).read_text(encoding="utf-8"))
        assert invalid_receipt["status"] == "INCONCLUSIVE", invalid_receipt
        assert invalid_receipt["tb_methodology_notes"]["open_methodology_blockers"] == [
            "valid blocker",
            7,
        ], invalid_receipt
        assert invalid_receipt["dispatch_verified"] is False, invalid_receipt

        string_field_list = run_case(root, fake_server, "string_field_list")
        assert string_field_list["returncode"] == 0 and string_field_list["status"] == "pass", string_field_list
        string_project = Path(string_field_list["project"])
        string_dispatch = json.loads(Path(string_field_list["dispatch_path"]).read_text(encoding="utf-8"))
        string_receipt = json.loads((string_project / string_dispatch["receipt_path"]).read_text(encoding="utf-8"))
        assert string_receipt["tb_methodology_notes"]["methodology_profile"] == (
            "candidate-specific proof\nnonvacuity checked"
        ), string_receipt
        assert string_receipt["tb_methodology_notes"]["framework"] == "Yosys\nZ3", string_receipt
        assert string_receipt["tb_methodology_notes"]["formal_candidates"] == ["FPROP_EXAMPLE"], string_receipt
        assert string_receipt["dispatch_verified"] is True, string_receipt

        object_field_list = run_case(root, fake_server, "object_field_list")
        assert object_field_list["returncode"] == 0 and object_field_list["status"] == "pass", object_field_list
        object_project = Path(object_field_list["project"])
        object_dispatch = json.loads(Path(object_field_list["dispatch_path"]).read_text(encoding="utf-8"))
        object_receipt = json.loads((object_project / object_dispatch["receipt_path"]).read_text(encoding="utf-8"))
        assert object_receipt["tb_methodology_notes"] == {
            "methodology_profile": "candidate-specific safety proof",
            "framework": "Yosys plus Z3",
            "architecture": ["real DUT leaf, independent contract checker"],
            "stimulus_strategy": ["deterministic legal boot plus symbolic fields"],
            "coverage_strategy": ["candidate-specific reachability covers"],
            "assertion_hooks": ["state and side-effect fences"],
            "formal_candidates": ["FPROP_EXAMPLE"],
            "open_methodology_blockers": ["none recorded"],
        }, object_receipt
        assert object_receipt["dispatch_verified"] is True, object_receipt

        misclassified = run_case(root, fake_server, "misclassified_generated_path")
        assert misclassified["returncode"] == 0 and misclassified["status"] == "pass", misclassified
        misclassified_project = Path(misclassified["project"])
        misclassified_dispatch = json.loads(Path(misclassified["dispatch_path"]).read_text(encoding="utf-8"))
        misclassified_receipt = json.loads(
            (misclassified_project / misclassified_dispatch["receipt_path"]).read_text(encoding="utf-8")
        )
        assert misclassified_receipt["changed_paths"] == ["ip/rtl/out.sv"], misclassified_receipt
        assert misclassified_receipt["generated_side_effects"] == [
            misclassified_dispatch["execution_actor"]["event_log_path"],
            misclassified_dispatch["execution_actor"]["manifest_path"],
        ], misclassified_receipt
        assert misclassified_receipt["dispatch_verified"] is True, misclassified_receipt
        assert misclassified_receipt["covers_writes"] is True, misclassified_receipt

        warning = run_case(root, fake_server, "warning")
        assert warning["returncode"] == 0 and warning["status"] == "pass", warning
        assert warning["warning_sent"] is True, warning
        warning_events = Path(warning["project"]) / warning["event_log_path"]
        assert "turn/steer" in event_methods(warning_events), warning

        budget = run_case(root, fake_server, "budget")
        assert budget["returncode"] != 0 and budget["budget_exceeded"] is True, budget
        budget_events = Path(budget["project"]) / budget["event_log_path"]
        assert "turn/interrupt" in event_methods(budget_events), budget

        observed = run_case(root, fake_server, "budget_complete", "--token-budget-mode", "observe")
        assert observed["returncode"] == 0 and observed["status"] == "pass", observed
        assert observed["budget_exceeded"] is False, observed
        assert observed["budget_warning_observed"] is True, observed
        assert observed["budget_max_observed"] is True, observed
        assert observed["warning_sent"] is False, observed
        observed_events = Path(observed["project"]) / observed["event_log_path"]
        assert "turn/steer" not in event_methods(observed_events), observed
        assert "turn/interrupt" not in event_methods(observed_events), observed
        observed_manifest = json.loads((Path(observed["project"]) / observed["manifest_path"]).read_text(encoding="utf-8"))
        assert observed_manifest["token_budget_mode"] == "observe", observed_manifest
        assert observed_manifest["budget_hard_stop_tokens"] == 0, observed_manifest

        subagent = run_case(root, fake_server, "subagent")
        assert subagent["returncode"] != 0 and subagent["subagent_activity_count"] == 1, subagent
        assert "subagent activity" in subagent["failure_reason"], subagent

        failed = run_case(root, fake_server, "failed")
        assert failed["returncode"] != 0 and failed["status"] == "fail", failed
        failed_project = Path(failed["project"])
        resumed = subprocess.run(
            [
                sys.executable,
                str(RUNNER),
                "--dispatch",
                failed["dispatch_path"],
                "--task",
                "Resume and finish the fake worker protocol.",
                "--app-server-command",
                f"{sys.executable} {fake_server}",
                "--timeout-seconds",
                "10",
                "--resume",
                "--json",
            ],
            cwd=failed_project,
            env={**os.environ, "OAG_PROJECT_ROOT": str(failed_project), "OAG_DISABLE_BACKEND": "1", "FAKE_SCENARIO": "normal"},
            text=True,
            capture_output=True,
            check=False,
        )
        resumed_payload = json.loads(resumed.stdout)
        assert resumed.returncode == 0 and resumed_payload["status"] == "pass", resumed_payload
        resumed_manifest = json.loads((failed_project / resumed_payload["manifest_path"]).read_text(encoding="utf-8"))
        assert resumed_manifest["resume_count"] == 1 and len(resumed_manifest["turn_ids"]) == 2, resumed_manifest
        resumed_events = failed_project / resumed_payload["event_log_path"]
        assert "thread/resume" in event_methods(resumed_events), resumed_payload

    print(json.dumps({"status": "pass", "tests": 17, "suite": "oag_thread_worker"}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
