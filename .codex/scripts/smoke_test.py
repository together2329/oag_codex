#!/usr/bin/env python3
"""Smoke test for the .codex ontology IP agent pack."""

from __future__ import annotations

import json
import os
import hashlib
import importlib.util
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = ROOT.parent
OAG = ROOT / "scripts" / "oag_cli.py"
LOOP_HOOK = ROOT / "scripts" / "oag_loop_hook.py"
LOOP_RUNNER = ROOT / "scripts" / "oag_loop_runner.py"
GRAPH = ROOT / "scripts" / "oag_graph.py"
MIGRATE_LAYOUT = ROOT / "scripts" / "oag_migrate_layout.py"
PORTABLE_DB = ROOT / "scripts" / "oag_portable_db.py"
OKF = ROOT / "scripts" / "oag_okf.py"
EVAL = ROOT / "scripts" / "oag_eval.py"
ANSWER_KEY_EVAL = ROOT / "scripts" / "oag_answer_key_eval.py"
DEV_VALIDATOR = ROOT / "scripts" / "oag_dev_validator.py"
SPEC_RTL_LOOP = ROOT / "scripts" / "oag_spec_to_rtl_loop.py"
EXEC_AUTO_RESEARCH = ROOT / "scripts" / "oag_exec_auto_research.py"
DISPATCH = ROOT / "scripts" / "oag_dispatch.py"
WAVEFRONT = ROOT / "scripts" / "oag_wavefront.py"
DECISION_HARNESS = ROOT / "scripts" / "oag_decision_harness.py"
MAIN_WRITE_GATE = ROOT / "scripts" / "oag_main_write_gate.py"
VALIDATE_JSON = ROOT / "scripts" / "oag_validate_json.py"
AGENT_CATALOG_CHECK = ROOT / "scripts" / "oag_agent_catalog_check.py"
CODEX_CONFIG_DOCTOR = ROOT / "scripts" / "oag_codex_config_doctor.py"
DEBUG_EVAL_METRICS = ROOT / "scripts" / "oag_debug_eval_metrics.py"
CLOSURE_CHECK = ROOT / "scripts" / "oag_closure_check.py"
PACK_RELEASE_CHECK = ROOT / "scripts" / "oag_pack_release_check.py"
DOMAIN_CROSSING_CHECK = ROOT / "scripts" / "oag_domain_crossing_check.py"
PPA_CHECK = ROOT / "scripts" / "oag_ppa_check.py"
OAG_PATHS = ROOT / "scripts" / "oag_paths.py"
PYSLANG_LINT = ROOT / "scripts" / "oag_pyslang_lint.py"
REQ_QUALITY_CHECK = ROOT / "scripts" / "oag_req_quality_check.py"
LOCK_READINESS_CHECK = ROOT / "scripts" / "oag_lock_readiness_check.py"
LOCK_PREVIEW_FRAME = ROOT / "scripts" / "oag_lock_preview_frame.py"
CONTRACT_STRENGTH_CHECK = ROOT / "scripts" / "oag_contract_strength_check.py"
AUTHORING_PACKET_CHECK = ROOT / "scripts" / "oag_authoring_packet_check.py"
DECISION_RTL_CONSISTENCY_CHECK = ROOT / "scripts" / "oag_decision_rtl_consistency_check.py"
RULE_INDEX_META_CHECK = ROOT / "scripts" / "oag_rule_index_meta_check.py"
TRACE_GRAPH_CHECK = ROOT / "scripts" / "oag_trace_graph_check.py"
DEEP_SEMANTIC_INTAKE = ROOT / "scripts" / "oag_deep_semantic_intake.py"
DEEP_INTERVIEW_ROUND = ROOT / "scripts" / "oag_deep_interview_round.py"
DECISION_MATRIX_GENERATE = ROOT / "scripts" / "oag_decision_matrix_generate.py"
LIFECYCLE_CHECK = ROOT / "scripts" / "oag_lifecycle_check.py"
BASELINE_CHECK = ROOT / "scripts" / "oag_baseline_check.py"
STALE_CHECK = ROOT / "scripts" / "oag_stale_check.py"
BASELINE_CUT = ROOT / "scripts" / "oag_baseline_cut.py"
BASELINE_VERIFY = ROOT / "scripts" / "oag_baseline_verify.py"
IP_VERSION_CHECK = ROOT / "scripts" / "oag_ip_version_check.py"
IP_GIT = ROOT / "scripts" / "oag_ip_git.py"
RUN_FRAME = ROOT / "scripts" / "oag_run_frame.py"
ACTION_MODEL_CHECK = ROOT / "scripts" / "oag_action_model_check.py"
MISSION_RUNTIME = ROOT / "scripts" / "oag_mission_runtime.py"
MISSION_LOOP = ROOT / "scripts" / "oag_mission_loop.py"
EXPLORATION_PLAN = ROOT / "scripts" / "oag_exploration_plan.py"
ACTION_PLAN = ROOT / "scripts" / "oag_action_plan.py"
ACTION_WAVEFRONT_DRAFT = ROOT / "scripts" / "oag_action_wavefront_draft.py"
TEAM_PLAN = ROOT / "scripts" / "oag_team_plan.py"
ACTION_RECORD = ROOT / "scripts" / "oag_action_record.py"
OPERATION_REVIEW_FRAME = ROOT / "scripts" / "oag_operation_review_frame.py"
ROLE_HEALTH = ROOT / "scripts" / "oag_role_health.py"
ORCHESTRATION_GUARD = ROOT / "scripts" / "oag_orchestration_guard.py"
WINDOWS_SMOKE = ROOT / "scripts" / "oag_windows_smoke.py"
REVIEW_FRAME = ROOT / "scripts" / "oag_review_frame.py"
GATE_FRAME = ROOT / "scripts" / "oag_gate_frame.py"
SSOT_SECTION_CHECK = ROOT / "scripts" / "oag_ssot_section_check.py"
AGENT_CATALOG = ROOT / "oag" / "agent-catalog.toml"
OAG_MODE_DIRECTIVE = ROOT / "oag" / "oag-mode-directive.md"
OAG_DECISION_AUTONOMY_POLICY = ROOT / "oag" / "decision-autonomy-policy.md"
SUBAGENT_WORKFLOWS = ROOT / "oag" / "subagent-workflows.md"
OAG_RULE_INDEX = ROOT / "rules" / "oag-rule-index.yaml"
OAG_DECISION_AUTONOMY_RULES = ROOT / "rules" / "oag-decision-autonomy.rules.md"
OAG_IP_WORKFLOW_SKILL = ROOT / "skills" / "oag-ip-workflow" / "SKILL.md"
OAG_DEEP_INTERVIEW_SKILL = ROOT / "skills" / "oag-deep-interview" / "SKILL.md"
OAG_DEEP_SEMANTIC_SKILL = ROOT / "skills" / "oag-deep-semantic-intake" / "SKILL.md"
OAG_DECISION_MATRIX_SKILL = ROOT / "skills" / "oag-decision-matrix" / "SKILL.md"
OAG_LOCK_PREVIEW_FRAME_SKILL = ROOT / "skills" / "oag-lock-preview-frame" / "SKILL.md"
OAG_CONTRACT_PROJECTION_SKILL = ROOT / "skills" / "oag-contract-projection" / "SKILL.md"
OAG_AUTHORING_PACKET_SKILL = ROOT / "skills" / "oag-authoring-packet" / "SKILL.md"
OAG_EVIDENCE_CLOSURE_SKILL = ROOT / "skills" / "oag-evidence-closure" / "SKILL.md"
OAG_WAVEFRONT_SKILL = ROOT / "skills" / "oag-wavefront" / "SKILL.md"
OAG_TEAM_MODE_SKILL = ROOT / "skills" / "oag-team-mode" / "SKILL.md"
OAG_WAVEFRONT_TEMPLATE = ROOT / "oag" / "wavefront-templates" / "tb_common_then_scenario_fanout.yaml"
OAG_RTL_WAVEFRONT_TEMPLATE = ROOT / "oag" / "wavefront-templates" / "rtl_module_fanout.yaml"
OAG_DATA_LIFECYCLE_POLICY = ROOT / "oag" / "data-lifecycle-policy.md"
OAG_BASELINE_GIT_POLICY = ROOT / "oag" / "baseline-git-policy.md"
OAG_IP_VERSIONING_POLICY = ROOT / "oag" / "ip-versioning-policy.md"
OAG_FEATURE_IPXACT_POLICY = ROOT / "oag" / "feature-ipxact-policy.md"
OAG_IP_VERSIONING_SKILL = ROOT / "skills" / "oag-ip-versioning" / "SKILL.md"
OAG_IP_VERSIONING_RULES = ROOT / "rules" / "oag-ip-versioning.rules.md"
STOP_GATE = ROOT / "hooks" / "codex_stop_gate.py"
SUBAGENT_START = ROOT / "hooks" / "codex_subagent_oag_start.py"
SUBAGENT_GATE = ROOT / "hooks" / "codex_subagent_oag_gate.py"
OAG_MODE_TRIGGER = ROOT / "hooks" / "codex_oag_mode_trigger.py"
NATIVE_SUBAGENT_GUARD = ROOT / "hooks" / "codex_native_subagent_guard.py"
DEEP_INTERVIEW_GUARD = ROOT / "hooks" / "codex_deep_interview_prompt_guard.py"
OAG_SESSION_START = ROOT / "hooks" / "codex_oag_session_start.py"
CONTEXT_HOOK = ROOT / "hooks" / "codex_context_inject.py"
DRAFT_HOOK = ROOT / "hooks" / "codex_draft_pressure.py"
HOOKS_JSON = ROOT / "hooks.json"
SCHEMA_FILES = [
    ROOT / "schemas" / "oag_dispatch.schema.json",
    ROOT / "schemas" / "oag_subagent_receipt.schema.json",
    ROOT / "schemas" / "oag_subagent_diagnostic_receipt.schema.json",
    ROOT / "schemas" / "oag_validation_report.schema.json",
    ROOT / "schemas" / "oag_gate_decision.schema.json",
    ROOT / "schemas" / "oag_closure_report.schema.json",
    ROOT / "schemas" / "oag_scope_lock.schema.json",
    ROOT / "schemas" / "oag_source_claims.schema.json",
    ROOT / "schemas" / "oag_ambiguity_register.schema.json",
    ROOT / "schemas" / "oag_requirement_atom.schema.json",
    ROOT / "schemas" / "oag_decision_matrix.schema.json",
    ROOT / "schemas" / "oag_verification_plan.schema.json",
    ROOT / "schemas" / "oag_contract_v2.schema.json",
    ROOT / "schemas" / "oag_rtl_authoring_packet.schema.json",
    ROOT / "schemas" / "oag_tb_authoring_packet.schema.json",
    ROOT / "schemas" / "oag_wavefront_task_graph.schema.json",
    ROOT / "schemas" / "oag_ownership_locks.schema.json",
    ROOT / "schemas" / "oag_wavefront_event.schema.json",
    ROOT / "schemas" / "oag_artifact_lifecycle.schema.json",
    ROOT / "schemas" / "oag_baseline_manifest.schema.json",
    ROOT / "schemas" / "oag_ip_version.schema.json",
    ROOT / "schemas" / "oag_exploration_plan.schema.json",
    ROOT / "schemas" / "oag_team_plan.schema.json",
]


def call(payload: dict) -> dict:
    env = {**os.environ, "OAG_DISABLE_BACKEND": "1"}
    proc = subprocess.run(
        [sys.executable, str(OAG), "call", "--json", json.dumps(payload)],
        text=True,
        capture_output=True,
        check=False,
        cwd=ROOT,
        env=env,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr or proc.stdout)
    return json.loads(proc.stdout)


def call_process(payload: dict) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "OAG_DISABLE_BACKEND": "1"}
    return subprocess.run(
        [sys.executable, str(OAG), "call", "--json", json.dumps(payload)],
        text=True,
        capture_output=True,
        check=False,
        cwd=ROOT,
        env=env,
    )


def run_loop_hook(*args: str) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "OAG_DISABLE_BACKEND": "1"}
    return subprocess.run(
        [sys.executable, str(LOOP_HOOK), *args],
        text=True,
        capture_output=True,
        check=False,
        cwd=ROOT,
        env=env,
    )


def run_loop_runner(*args: str) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "OAG_DISABLE_BACKEND": "1"}
    return subprocess.run(
        [sys.executable, str(LOOP_RUNNER), *args],
        text=True,
        capture_output=True,
        check=False,
        cwd=ROOT,
        env=env,
    )


def run_dev_validator(ip: Path) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "OAG_DISABLE_BACKEND": "1"}
    return subprocess.run(
        [
            sys.executable,
            str(DEV_VALIDATOR),
            "--ip-dir",
            str(ip),
            "--stage",
            "sim",
            "--intent",
            "smoke development validator",
            "--json",
        ],
        text=True,
        capture_output=True,
        check=False,
        cwd=ROOT,
        env=env,
    )


def run_spec_to_rtl_loop(ip: Path, spec: Path, *, metrics: bool = False) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "OAG_DISABLE_BACKEND": "1"}
    command = [
        sys.executable,
        str(SPEC_RTL_LOOP),
        "--ip-dir",
        str(ip),
        "--spec",
        str(spec),
        "--stage",
        "sim",
        "--intent",
        "smoke spec-to-RTL loop",
        "--write-static-summary",
        "--json",
    ]
    if metrics:
        command.append("--metrics")
    return subprocess.run(
        command,
        text=True,
        capture_output=True,
        check=False,
        cwd=ROOT,
        env=env,
    )


def run_dispatch(*args: str, project_root: Path | None = None) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "OAG_DISABLE_BACKEND": "1"}
    if project_root:
        env["OAG_PROJECT_ROOT"] = str(project_root)
    return subprocess.run(
        [sys.executable, str(DISPATCH), *args],
        text=True,
        capture_output=True,
        check=False,
        cwd=project_root or ROOT.parent,
        env=env,
    )


def run_wavefront(*args: str, project_root: Path | None = None) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "OAG_DISABLE_BACKEND": "1"}
    if project_root:
        env["OAG_PROJECT_ROOT"] = str(project_root)
    return subprocess.run(
        [sys.executable, str(WAVEFRONT), *args],
        text=True,
        capture_output=True,
        check=False,
        cwd=project_root or ROOT.parent,
        env=env,
    )


def run_decision_harness(*args: str, project_root: Path | None = None) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "OAG_DISABLE_BACKEND": "1"}
    if project_root:
        env["OAG_PROJECT_ROOT"] = str(project_root)
    return subprocess.run(
        [sys.executable, str(DECISION_HARNESS), *args],
        text=True,
        capture_output=True,
        check=False,
        cwd=project_root or ROOT.parent,
        env=env,
    )


def run_lock_preview_frame(ip: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "OAG_DISABLE_BACKEND": "1"}
    return subprocess.run(
        [sys.executable, str(LOCK_PREVIEW_FRAME), "--ip-dir", str(ip), *args],
        text=True,
        capture_output=True,
        check=False,
        cwd=ROOT,
        env=env,
    )


def task5_rel(project: Path, path: Path) -> str:
    return path.resolve().relative_to(project.resolve()).as_posix()


def task5_file_hashes(project: Path, ip: Path) -> dict[str, str]:
    return {
        task5_rel(project, path): sha256(path)
        for path in sorted(ip.rglob("*"))
        if path.is_file() and ".git" not in path.parts
    }


def write_task5_wavefront_state(ip: Path, run_id: str, task_id: str, dispatch_id: str, ownership_mode: str, status: str) -> None:
    run_dir = ip / "ontology" / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "wavefront_task_graph.json").write_text(
        json.dumps(
            {
                "schema_version": "oag_wavefront_task_graph.v1",
                "run_id": run_id,
                "tasks": [
                    {
                        "task_id": task_id,
                        "status": status,
                        "ownership_mode": ownership_mode,
                        "may_claim_complete": False,
                    }
                ],
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    write_task5_ownership_locks(ip, run_id, task_id, dispatch_id)


def write_task5_ownership_locks(ip: Path, run_id: str, task_id: str, dispatch_id: str) -> None:
    run_dir = ip / "ontology" / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "ownership_locks.json").write_text(
        json.dumps(
            {
                "schema_version": "oag_ownership_locks.v1",
                "run_id": run_id,
                "locks": [{"task_id": task_id, "dispatch_id": dispatch_id}],
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def write_task5_dispatch(
    project: Path,
    ip: Path,
    scenario: str,
    task_id: str,
    ownership_mode: str,
    allowed_write_paths: list[str],
    *,
    run_id: str = "RUN_TASK5",
    stage: str = "sim",
    status: str = "claimed",
    wavefront: bool = True,
) -> tuple[Path, Path, dict]:
    dispatch_id = f"DISPATCH_TASK5_{scenario.upper()}_20260101T000000Z_ABCD1234"
    if wavefront:
        write_task5_wavefront_state(ip, run_id, task_id, dispatch_id, ownership_mode, status)
    dispatch_path = ip / "knowledge" / "dispatches" / f"{scenario}.json"
    receipt_path = ip / "knowledge" / "subagents" / f"{scenario}.json"
    dispatch_path.parent.mkdir(parents=True, exist_ok=True)
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    baseline_hashes = task5_file_hashes(project, ip)
    dispatch = {
        "schema_version": "oag_dispatch.v1",
        "product_name": "IP Dev Agent",
        "internal_gateway": "Ontology Agent Gateway",
        "dispatch_id": dispatch_id,
        "dispatch_path": task5_rel(project, dispatch_path),
        "agent_type": "oag-custom-worker",
        "role_name": "oag-custom-worker",
        "role_kind": "custom",
        "registered_id": "oag-custom-worker",
        "ip_id": ip.name,
        "ip_dir": task5_rel(project, ip),
        "stage": stage,
        "owned_obligations": ["OBL_TASK5"],
        "contracts": ["CONTRACT_TASK5"],
        "allowed_write_paths": allowed_write_paths,
        "allowed_tool_side_effects": [],
        "receipt_path": task5_rel(project, receipt_path),
        "may_claim_complete": False,
        "wavefront_run_id": run_id if wavefront else "",
        "task_id": task_id if wavefront else "",
        "ownership_mode": ownership_mode if wavefront else "",
        "baseline": {
            "created_at": "2026-01-01T00:00:00Z",
            "git_status_paths": sorted(baseline_hashes),
            "file_hashes": baseline_hashes,
        },
        "created_at": "2026-01-01T00:00:00Z",
    }
    dispatch["dispatch_integrity"] = task5_dispatch_integrity(dispatch)
    dispatch_path.write_text(json.dumps(dispatch, sort_keys=True) + "\n", encoding="utf-8")
    return dispatch_path, receipt_path, dispatch


def task5_dispatch_integrity(dispatch: dict) -> dict:
    protected_fields = [
        "schema_version",
        "dispatch_id",
        "dispatch_path",
        "agent_type",
        "role_name",
        "role_kind",
        "registered_id",
        "ip_id",
        "ip_dir",
        "stage",
        "owned_obligations",
        "contracts",
        "allowed_write_paths",
        "allowed_tool_side_effects",
        "receipt_path",
        "may_claim_complete",
        "wavefront_run_id",
        "task_id",
        "ownership_mode",
        "baseline",
        "created_at",
    ]
    payload = {field: dispatch.get(field) for field in protected_fields}
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    return {
        "schema_version": "oag_dispatch_integrity.v1",
        "protected_fields": protected_fields,
        "scope_hash_algorithm": "sha256:jcs-v1",
        "scope_hash": digest,
    }


def write_wavefront_claim_dispatch(project: Path, ip: Path, run_id: str, task: dict) -> str:
    task_id = str(task["task_id"])
    safe_task_id = re.sub(r"[^A-Z0-9]+", "_", task_id.upper()).strip("_")
    dispatch_id = f"DISPATCH_{safe_task_id}_20260101T000000Z_ABCD1234"
    dispatch_path = ip / "knowledge" / "dispatches" / f"{dispatch_id}.json"
    receipt_path = ip / "knowledge" / "subagents" / f"{safe_task_id.lower()}_receipt.json"
    dispatch_path.parent.mkdir(parents=True, exist_ok=True)
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    task_paths = [task5_rel(project, ip / str(path)) for path in task.get("allowed_write_paths", [])]
    task_paths.extend(task5_rel(project, ip / str(path)) for path in task.get("shared_artifacts", []))
    task_paths.append(task5_rel(project, receipt_path.parent) + "/")
    agent_type = str(task.get("agent_type") or "oag-custom-worker")
    dispatch = {
        "schema_version": "oag_dispatch.v1",
        "product_name": "IP Dev Agent",
        "internal_gateway": "Ontology Agent Gateway",
        "dispatch_id": dispatch_id,
        "dispatch_path": task5_rel(project, dispatch_path),
        "agent_type": agent_type,
        "role_name": agent_type,
        "role_kind": "custom" if agent_type.startswith("oag-custom-") else "core",
        "registered_id": agent_type,
        "ip_id": ip.name,
        "ip_dir": task5_rel(project, ip),
        "stage": str(task.get("phase") or task.get("kind") or "wavefront"),
        "owned_obligations": list(task.get("owned_obligations") or []),
        "contracts": list(task.get("contracts") or []),
        "allowed_write_paths": sorted(set(task_paths)),
        "allowed_tool_side_effects": [],
        "receipt_path": task5_rel(project, receipt_path),
        "may_claim_complete": False,
        "wavefront_run_id": run_id,
        "task_id": task_id,
        "ownership_mode": str(task.get("ownership_mode") or ""),
        "baseline": {
            "created_at": "2026-01-01T00:00:00Z",
            "git_status_raw": "",
            "git_status_paths": [],
            "file_hashes": {},
        },
        "created_at": "2026-01-01T00:00:00Z",
    }
    dispatch["dispatch_integrity"] = task5_dispatch_integrity(dispatch)
    dispatch_path.write_text(json.dumps(dispatch, sort_keys=True) + "\n", encoding="utf-8")
    return dispatch_id


def approve_and_close_wavefront_task(
    project: Path,
    ip: Path,
    run_id: str,
    task_id: str,
    *,
    barrier_outputs: list[str] | None = None,
) -> dict:
    graph_path = ip / "ontology" / "runs" / run_id / "wavefront_task_graph.json"
    graph = json.loads(graph_path.read_text(encoding="utf-8"))
    task = next(item for item in graph["tasks"] if item["task_id"] == task_id)
    status = str(task.get("status") or "")
    if status == "pending":
        dispatch_id = ""
        if task["ownership_mode"] != "none":
            dispatch_id = write_wavefront_claim_dispatch(project, ip, run_id, task)
        claim_args = [
            "claim",
            "--ip-dir",
            str(ip),
            "--run-id",
            run_id,
            "--task-id",
            task_id,
            "--claimed-by",
            "smoke-review-flow",
            "--json",
        ]
        if dispatch_id:
            claim_args.extend(["--dispatch-id", dispatch_id])
        claim = run_wavefront(*claim_args, project_root=project)
        assert claim.returncode == 0, claim.stderr or claim.stdout
        status = "claimed"
    if status == "claimed":
        review_pending = run_wavefront(
            "record",
            "--ip-dir",
            str(ip),
            "--run-id",
            run_id,
            "--task-id",
            task_id,
            "--status",
            "review_pending",
            "--json",
            project_root=project,
        )
        assert review_pending.returncode == 0, review_pending.stderr or review_pending.stdout
        status = "review_pending"
    assert status == "review_pending", task
    outputs = list(barrier_outputs or [])
    decision_args = [
        "record",
        "--ip-dir",
        str(ip),
        "--run-id",
        run_id,
        "--task-id",
        task_id,
        "--decision-id",
        f"DEC_{re.sub(r'[^A-Z0-9]+', '_', task_id.upper())}_SMOKE_REVIEW",
        "--decision-type",
        "custom_review",
        "--verdict",
        "approved",
        "--summary",
        f"{task_id} reviewed before terminal wavefront transition.",
        "--checked-against",
        str(graph_path),
        "--preserved",
        "wavefront review boundary",
        "--wavefront-status",
        "closed",
        "--reviewer-id",
        "oag-gate-reviewer",
        "--json",
    ]
    for token in outputs:
        decision_args.extend(["--barrier-output", token])
    decision = run_decision_harness(*decision_args, project_root=project)
    assert decision.returncode == 0, decision.stderr or decision.stdout
    record_args = [
        "record",
        "--ip-dir",
        str(ip),
        "--run-id",
        run_id,
        "--task-id",
        task_id,
        "--status",
        "closed",
        "--decision",
        json.loads(decision.stdout)["path"],
        "--json",
    ]
    for token in outputs:
        record_args.extend(["--barrier-output", token])
    record = run_wavefront(*record_args, project_root=project)
    assert record.returncode == 0, record.stderr or record.stdout
    return json.loads(record.stdout)


def write_task5_receipt(
    path: Path,
    dispatch: dict,
    changed_paths: list[str],
    *,
    wavefront: bool = True,
    overrides: dict | None = None,
) -> None:
    receipt = {
        "schema_version": "oag_subagent_receipt.v1",
        "product_name": "IP Dev Agent",
        "internal_gateway": "Ontology Agent Gateway",
        "ip_id": dispatch["ip_id"],
        "dispatch_id": dispatch["dispatch_id"],
        "dispatch_path": dispatch["dispatch_path"],
        "role_name": dispatch["role_name"],
        "registered_id": dispatch["registered_id"],
        "shard_scope": "task5",
        "stage": dispatch["stage"],
        "status": "STATIC_HANDOFF_PASS",
        "owned_obligations": dispatch["owned_obligations"],
        "contracts": dispatch["contracts"],
        "allowed_write_paths": dispatch["allowed_write_paths"],
        "changed_paths": changed_paths,
        "generated_side_effects": [],
        "evidence_outputs": [dispatch["receipt_path"]],
        "diagnostic_only": False,
        "covers_writes": True,
        "dispatch_verified": True,
        "implementation_evidence": True,
        "may_claim_complete": False,
        "created_at": "2026-01-01T00:00:00Z",
    }
    if wavefront:
        receipt.update(
            {
                "wavefront_run_id": dispatch["wavefront_run_id"],
                "task_id": dispatch["task_id"],
                "ownership_mode": dispatch["ownership_mode"],
            }
        )
    if overrides:
        for key, value in overrides.items():
            if value is None:
                receipt.pop(key, None)
            else:
                receipt[key] = value
    path.write_text(json.dumps(receipt, sort_keys=True) + "\n", encoding="utf-8")


def verify_task5_dispatch(project: Path, dispatch_path: Path, receipt_path: Path) -> dict:
    result = run_dispatch("verify", "--dispatch", str(dispatch_path), "--receipt", str(receipt_path), "--json", project_root=project)
    payload = json.loads(result.stdout)
    if result.returncode != 0 and payload["status"] == "pass":
        raise AssertionError(payload)
    return payload


def test_dispatch_prompt_contract_subagent_boundary() -> None:
    scripts_dir = str(ROOT / "scripts")
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    spec = importlib.util.spec_from_file_location("oag_dispatch_prompt_smoke", ROOT / "scripts" / "oag_dispatch_prompt.py")
    assert spec is not None and spec.loader is not None
    module: Any = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    prompt = module.build_prompt_contract(
        {
            "dispatch_id": "DISPATCH_SMOKE",
            "dispatch_path": "smoke_ip/knowledge/dispatches/dispatch.json",
            "agent_type": "oag-custom-worker",
            "ip_dir": "smoke_ip",
            "stage": "sim",
            "receipt_path": "smoke_ip/knowledge/subagents/receipt.json",
            "allowed_write_paths": ["smoke_ip/scripts/run_sim.py"],
            "allowed_tool_side_effects": ["smoke_ip/ontology/generated"],
            "wavefront_run_id": "RUN_SMOKE",
            "task_id": "TASK_SMOKE",
            "ownership_mode": "exclusive_file",
        }
    )

    assert "Subagent implementation boundary:" in prompt, prompt
    assert "Do not create a new dispatch" in prompt, prompt
    assert "Do not run decision_harness record" in prompt, prompt
    assert "Do not open or claim wavefront barriers" in prompt, prompt
    assert "HANDOFF_PASS is only for the assigned deliverable" in prompt, prompt
    assert "coverage_observed=false" in prompt, prompt
    assert "Do not report coverage_percent=0" in prompt, prompt
    assert "do not fall back to the smoke subset" in prompt, prompt
    assert "within the first parent wait cycle" in prompt, prompt
    assert "answer with `WORKING:`, `BLOCKED:`, or the receipt path" in prompt, prompt
    assert "observed_source.kind=monitor" in prompt, prompt
    assert "repo schema or writer convention" in prompt, prompt
    assert "scoreboard_rows.v1-allowed fields" in prompt, prompt
    assert "scenario_count" in prompt, prompt
    assert "scenario_source" in prompt, prompt
    assert "plan_parse_success=true" in prompt, prompt
    assert "smoke_fallback_used=false" in prompt, prompt
    assert "results.xml" in prompt and "environment blocked" in prompt, prompt


def test_task5_dispatch_wavefront_matrix(tmp_root: Path) -> None:
    project = tmp_root / "task5_dispatch_project"
    project.mkdir(parents=True)
    subprocess.run(["git", "init"], cwd=project, text=True, capture_output=True, check=True)
    ip = project / "task5_ip"

    worker_allowed = [task5_rel(project, ip / "sim" / "slices"), task5_rel(project, ip / "knowledge" / "subagents")]
    worker_dispatch_path, worker_receipt_path, worker_dispatch = write_task5_dispatch(project, ip, "worker_shard", "TASK_WORKER", "exclusive_file", worker_allowed)
    worker_shard = ip / "sim" / "slices" / "OBL_TASK5" / "scoreboard_events.jsonl"
    worker_shard.parent.mkdir(parents=True, exist_ok=True)
    worker_shard.write_text("{}\n", encoding="utf-8")
    write_task5_receipt(worker_receipt_path, worker_dispatch, [task5_rel(project, worker_shard)])
    worker_result = verify_task5_dispatch(project, worker_dispatch_path, worker_receipt_path)
    assert worker_result["status"] == "pass", worker_result

    canonical_allowed = [task5_rel(project, ip / "sim" / "scoreboard_events.jsonl"), task5_rel(project, ip / "knowledge" / "subagents")]
    bad_worker_dispatch_path, bad_worker_receipt_path, bad_worker_dispatch = write_task5_dispatch(project, ip, "worker_canonical", "TASK_BAD_WORKER", "exclusive_file", canonical_allowed)
    canonical_path = ip / "sim" / "scoreboard_events.jsonl"
    canonical_path.parent.mkdir(parents=True, exist_ok=True)
    canonical_path.write_text("{}\n", encoding="utf-8")
    write_task5_receipt(bad_worker_receipt_path, bad_worker_dispatch, [task5_rel(project, canonical_path)])
    bad_worker_result = verify_task5_dispatch(project, bad_worker_dispatch_path, bad_worker_receipt_path)
    assert bad_worker_result["status"] == "fail", bad_worker_result
    assert any(item["code"] == "WORKER_CANONICAL_AGGREGATE_WRITE" for item in bad_worker_result["issues"]), bad_worker_result

    integration_dispatch_path, integration_receipt_path, integration_dispatch = write_task5_dispatch(project, ip, "integration_canonical", "TASK_INTEGRATION", "integration_owner", canonical_allowed)
    write_task5_receipt(integration_receipt_path, integration_dispatch, [task5_rel(project, canonical_path)])
    integration_result = verify_task5_dispatch(project, integration_dispatch_path, integration_receipt_path)
    assert integration_result["status"] == "pass", integration_result

    missing_dispatch_path, missing_receipt_path, missing_dispatch = write_task5_dispatch(project, ip, "missing_fields", "TASK_MISSING_FIELDS", "exclusive_file", worker_allowed)
    write_task5_receipt(missing_receipt_path, missing_dispatch, [task5_rel(project, worker_shard)], overrides={"wavefront_run_id": None, "task_id": None, "ownership_mode": None})
    missing_result = verify_task5_dispatch(project, missing_dispatch_path, missing_receipt_path)
    assert missing_result["status"] == "fail", missing_result
    assert any(item["code"] == "WAVEFRONT_FIELD_MISSING" for item in missing_result["issues"]), missing_result

    mismatch_dispatch_path, mismatch_receipt_path, mismatch_dispatch = write_task5_dispatch(project, ip, "mismatch_fields", "TASK_MISMATCH", "exclusive_file", worker_allowed)
    write_task5_receipt(mismatch_receipt_path, mismatch_dispatch, [task5_rel(project, worker_shard)], overrides={"task_id": "TASK_OTHER"})
    mismatch_result = verify_task5_dispatch(project, mismatch_dispatch_path, mismatch_receipt_path)
    assert mismatch_result["status"] == "fail", mismatch_result
    assert any(item["code"] == "WAVEFRONT_FIELD_MISMATCH" for item in mismatch_result["issues"]), mismatch_result

    unclaimed_dispatch_path, unclaimed_receipt_path, unclaimed_dispatch = write_task5_dispatch(project, ip, "unclaimed_task", "TASK_UNCLAIMED", "exclusive_file", worker_allowed, status="ready")
    write_task5_receipt(unclaimed_receipt_path, unclaimed_dispatch, [task5_rel(project, worker_shard)])
    unclaimed_result = verify_task5_dispatch(project, unclaimed_dispatch_path, unclaimed_receipt_path)
    assert unclaimed_result["status"] == "fail", unclaimed_result
    assert any(item["code"] == "WAVEFRONT_TASK_UNCLAIMED" for item in unclaimed_result["issues"]), unclaimed_result

    aborted_dispatch_path, aborted_receipt_path, aborted_dispatch = write_task5_dispatch(
        project,
        ip,
        "aborted_late_receipt",
        "TASK_ABORTED_LATE",
        "exclusive_file",
        worker_allowed,
        run_id="RUN_ABORTED_LATE",
    )
    aborted_graph_path = ip / "ontology" / "runs" / "RUN_ABORTED_LATE" / "wavefront_task_graph.json"
    aborted_graph = json.loads(aborted_graph_path.read_text(encoding="utf-8"))
    aborted_task = aborted_graph["tasks"][0]
    aborted_task["status"] = "failed"
    aborted_task["recorded_at"] = "2026-01-01T00:00:02Z"
    aborted_task["abort_marker"] = {
        "status": "failed",
        "recorded_at": "2026-01-01T00:00:02Z",
        "dispatch_id": aborted_dispatch["dispatch_id"],
        "receipt_path": "",
        "reason": "wavefront task recorded terminal without approved handoff",
    }
    aborted_graph_path.write_text(json.dumps(aborted_graph, sort_keys=True) + "\n", encoding="utf-8")
    write_task5_ownership_locks(ip, "RUN_ABORTED_LATE", "TASK_ABORTED_LATE", "DIFFERENT_REPLACEMENT_DISPATCH")
    write_task5_receipt(aborted_receipt_path, aborted_dispatch, [task5_rel(project, worker_shard)])
    aborted_result = verify_task5_dispatch(project, aborted_dispatch_path, aborted_receipt_path)
    assert aborted_result["status"] == "fail", aborted_result
    assert any(item["code"] == "WAVEFRONT_TASK_ABORTED" for item in aborted_result["issues"]), aborted_result

    compat_allowed = [task5_rel(project, ip / "knowledge" / "subagents")]
    compat_dispatch_path, compat_receipt_path, compat_dispatch = write_task5_dispatch(project, ip, "non_wavefront", "TASK_COMPAT", "none", compat_allowed, stage="draft", wavefront=False)
    write_task5_receipt(compat_receipt_path, compat_dispatch, [task5_rel(project, compat_receipt_path)], wavefront=False)
    compat_result = verify_task5_dispatch(project, compat_dispatch_path, compat_receipt_path)
    assert compat_result["status"] == "pass", compat_result

    malformed_dispatch_path = project / "malformed_dispatch_array.json"
    malformed_dispatch_path.write_text("[]\n", encoding="utf-8")
    malformed_dispatch_verify = run_dispatch("verify", "--dispatch", str(malformed_dispatch_path), "--receipt", str(worker_receipt_path), "--json", project_root=project)
    assert malformed_dispatch_verify.returncode != 0, malformed_dispatch_verify.stdout
    malformed_dispatch_result = json.loads(malformed_dispatch_verify.stdout)
    assert malformed_dispatch_result["status"] == "fail", malformed_dispatch_result
    assert any(item["code"] == "DISPATCH_LOAD_SHAPE" for item in malformed_dispatch_result["issues"]), malformed_dispatch_result

    malformed_receipt_path = project / "malformed_receipt_array.json"
    malformed_receipt_path.write_text("[]\n", encoding="utf-8")
    malformed_receipt_verify = run_dispatch("verify", "--dispatch", str(worker_dispatch_path), "--receipt", str(malformed_receipt_path), "--json", project_root=project)
    assert malformed_receipt_verify.returncode != 0, malformed_receipt_verify.stdout
    malformed_receipt_result = json.loads(malformed_receipt_verify.stdout)
    assert malformed_receipt_result["status"] == "fail", malformed_receipt_result
    assert any(item["code"] == "RECEIPT_LOAD_SHAPE" for item in malformed_receipt_result["issues"]), malformed_receipt_result


def test_dispatch_hardening_guards(tmp_root: Path) -> None:
    project = tmp_root / "dispatch_hardening_project"
    project.mkdir(parents=True)
    subprocess.run(["git", "init"], cwd=project, text=True, capture_output=True, check=True)
    ip = project / "hardening_ip"
    (ip / "ontology").mkdir(parents=True, exist_ok=True)
    (ip / "rtl").mkdir(parents=True, exist_ok=True)
    (ip / "knowledge" / "subagents").mkdir(parents=True, exist_ok=True)
    (ip / "ontology" / "scope_lock.json").write_text(
        json.dumps(
            {
                "schema_version": "oag_scope_lock.v1",
                "ip": ip.name,
                "state": "locked",
                "summary": "Dispatch hardening smoke scope.",
                "confirmed_scope": ["dispatch hardening"],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    write_minimal_rtl_dispatch_readiness(
        ip,
        module_id="smoke",
        rtl_file="rtl/smoke.sv",
        contract_id="CONTRACT_SMOKE",
        obligation_id="OBL_SMOKE",
    )
    create = run_dispatch(
        "create",
        "--ip-dir",
        str(ip),
        "--agent-type",
        "oag-custom-worker",
        "--role-kind",
        "custom",
        "--stage",
        "rtl",
        "--owned-obligation",
        "OBL_SMOKE",
        "--contract",
        "CONTRACT_SMOKE",
        "--allowed-write-path",
        str(ip / "rtl" / "smoke.sv"),
        "--allowed-write-path",
        str(ip / "knowledge" / "subagents"),
        "--allowed-tool-side-effect",
        str(ip / "ontology" / "generated"),
        "--receipt-path",
        str(ip / "knowledge" / "subagents" / "smoke.json"),
        "--json",
        project_root=project,
    )
    assert create.returncode == 0, create.stderr or create.stdout
    dispatch = json.loads(create.stdout)["dispatch"]
    assert dispatch["dispatch_integrity"]["scope_hash"], dispatch
    dispatch_path = project / dispatch["dispatch_path"]
    receipt_path = project / dispatch["receipt_path"]
    (ip / "rtl" / "smoke.sv").write_text("module smoke; endmodule\n", encoding="utf-8")
    receipt_path.write_text(
        json.dumps(
            {
                "schema_version": "oag_subagent_receipt.v1",
                "product_name": "IP Dev Agent",
                "internal_gateway": "Ontology Agent Gateway",
                "ip_id": dispatch["ip_id"],
                "dispatch_id": dispatch["dispatch_id"],
                "dispatch_path": dispatch["dispatch_path"],
                "role_name": dispatch["role_name"],
                "registered_id": dispatch["registered_id"],
                "shard_scope": "smoke",
                "stage": "rtl",
                "status": "STATIC_HANDOFF_PASS",
                "owned_obligations": ["OBL_SMOKE"],
                "contracts": ["CONTRACT_SMOKE"],
                "allowed_write_paths": dispatch["allowed_write_paths"],
                "changed_paths": [f"{ip.name}/rtl/smoke.sv"],
                "generated_side_effects": [],
                "evidence_outputs": [dispatch["receipt_path"]],
                "diagnostic_only": False,
                "covers_writes": True,
                "dispatch_verified": True,
                "implementation_evidence": True,
                "may_claim_complete": False,
                "created_at": "2026-01-01T00:00:00Z",
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    clean_verify = run_dispatch("verify", "--dispatch", str(dispatch_path), "--receipt", str(receipt_path), "--json", project_root=project)
    assert clean_verify.returncode == 0, clean_verify.stderr or clean_verify.stdout
    schema_preflight = run_dispatch(
        "verify",
        "--dispatch",
        str(dispatch_path),
        "--receipt",
        str(receipt_path),
        "--schema-only",
        "--json",
        project_root=project,
    )
    assert schema_preflight.returncode == 0, schema_preflight.stderr or schema_preflight.stdout
    schema_preflight_payload = json.loads(schema_preflight.stdout)
    assert schema_preflight_payload["schema_only"] is True, schema_preflight_payload

    mutated = json.loads(dispatch_path.read_text(encoding="utf-8"))
    mutated["allowed_tool_side_effects"].append(f"{ip.name}/nested_packet_ip/ontology/generated")
    dispatch_path.write_text(json.dumps(mutated, sort_keys=True) + "\n", encoding="utf-8")
    mutated_verify = run_dispatch("verify", "--dispatch", str(dispatch_path), "--receipt", str(receipt_path), "--json", project_root=project)
    assert mutated_verify.returncode != 0, mutated_verify.stdout
    mutated_payload = json.loads(mutated_verify.stdout)
    assert any(item["code"] == "DISPATCH_MUTATED_AFTER_CREATE" for item in mutated_payload["issues"]), mutated_payload

    nested_create = run_dispatch(
        "create",
        "--ip-dir",
        str(ip),
        "--agent-type",
        "oag-custom-worker",
        "--role-kind",
        "custom",
        "--stage",
        "draft",
        "--allowed-write-path",
        str(ip / "knowledge" / "subagents"),
        "--allowed-tool-side-effect",
        str(ip / ip.name / "ontology" / "generated"),
        "--receipt-path",
        str(ip / "knowledge" / "subagents" / "nested.json"),
        "--json",
        project_root=project,
    )
    assert nested_create.returncode != 0, nested_create.stdout
    assert "NESTED_IP_DIR_GENERATED_ARTIFACT" in (nested_create.stderr + nested_create.stdout), nested_create.stderr or nested_create.stdout
    nested_compile = subprocess.run(
        [
            sys.executable,
            str(OAG),
            "call",
            "--json",
            json.dumps({"tool": "oag.compile", "arguments": {"ip_dir": ip.name}}),
        ],
        text=True,
        capture_output=True,
        check=False,
        cwd=ip,
        env={**os.environ, "OAG_DISABLE_BACKEND": "1", "OAG_PROJECT_ROOT": ""},
    )
    assert nested_compile.returncode != 0, nested_compile.stderr or nested_compile.stdout
    nested_compile_payload = json.loads(nested_compile.stdout)
    assert nested_compile_payload["ok"] is False, nested_compile_payload
    assert "NESTED_IP_DIR_GENERATED_ARTIFACT" in " ".join(nested_compile_payload["errors"]), nested_compile_payload
    assert not (ip / ip.name / "ontology" / "generated").exists(), nested_compile_payload

    active_ip = project / "active_dispatch_ip"
    (active_ip / "ontology").mkdir(parents=True, exist_ok=True)
    (active_ip / "rtl").mkdir(parents=True, exist_ok=True)
    (active_ip / "knowledge" / "subagents").mkdir(parents=True, exist_ok=True)
    (active_ip / "ontology" / "scope_lock.json").write_text(
        json.dumps(
            {
                "schema_version": "oag_scope_lock.v1",
                "ip": active_ip.name,
                "state": "locked",
                "summary": "Active dispatch smoke scope.",
                "confirmed_scope": ["active dispatch parent write"],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    write_minimal_rtl_dispatch_readiness(
        active_ip,
        module_id="smoke",
        rtl_file="rtl/smoke.sv",
        contract_id="CONTRACT_SMOKE",
        obligation_id="OBL_SMOKE",
    )
    active_create = run_dispatch(
        "create",
        "--ip-dir",
        str(active_ip),
        "--agent-type",
        "oag-custom-worker",
        "--role-kind",
        "custom",
        "--stage",
        "rtl",
        "--owned-obligation",
        "OBL_SMOKE",
        "--contract",
        "CONTRACT_SMOKE",
        "--allowed-write-path",
        str(active_ip / "rtl" / "smoke.sv"),
        "--receipt-path",
        str(active_ip / "knowledge" / "subagents" / "active.json"),
        "--json",
        project_root=project,
    )
    assert active_create.returncode == 0, active_create.stderr or active_create.stdout
    (active_ip / "rtl" / "smoke.sv").write_text("module smoke; endmodule\n", encoding="utf-8")
    active_gate = run_main_write_gate(active_ip, project_root=project)
    assert active_gate.returncode != 0, active_gate.stdout
    active_payload = json.loads(active_gate.stdout)
    assert any(item["code"] == "PARENT_WRITE_WITH_ACTIVE_DISPATCH" for item in active_payload["issues"]), active_payload


def test_dispatch_authoring_packet_retry_classifier() -> None:
    scripts_dir = str(ROOT / "scripts")
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    spec = importlib.util.spec_from_file_location("oag_dispatch_support_smoke", ROOT / "scripts" / "oag_dispatch_support.py")
    assert spec and spec.loader, spec
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    retryable = {
        "issues": [
            {"code": "COMPILE_MANIFEST_STALE_INPUT", "message": "stale"},
            {"code": "RTL_PACKET_MISSING", "message": "missing"},
        ]
    }
    assert module.authoring_packet_gate_retryable(retryable) is True
    structural = {
        "issues": [
            {"code": "COMPILE_MANIFEST_STALE_INPUT", "message": "stale"},
            {"code": "MODULE_PACKET_INTERFACE_CONTRACT_REFS", "message": "projection missing"},
        ]
    }
    assert module.authoring_packet_gate_retryable(structural) is False
    assert module.authoring_packet_gate_retryable({"issues": []}) is False


def test_nested_ip_repository_main_write_gate(tmp_root: Path) -> None:
    project = tmp_root / "nested_ip_git_project"
    ip = project / "nested_ip"
    ip.mkdir(parents=True)
    for repo in (project, ip):
        init = subprocess.run(["git", "init"], cwd=repo, text=True, capture_output=True, check=False)
        assert init.returncode == 0, init.stderr or init.stdout
        subprocess.run(["git", "config", "user.email", "oag-smoke@example.invalid"], cwd=repo, check=True)
        subprocess.run(["git", "config", "user.name", "OAG Smoke"], cwd=repo, check=True)

    (ip / "ontology").mkdir(parents=True)
    (ip / "rtl").mkdir(parents=True)
    (ip / "ontology" / "scope_lock.json").write_text(
        json.dumps(
            {
                "schema_version": "oag_scope_lock.v1",
                "ip": ip.name,
                "state": "locked",
                "summary": "Nested IP repository smoke scope.",
                "confirmed_scope": ["nested repository main-write detection"],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    write_minimal_rtl_dispatch_readiness(
        ip,
        module_id="nested",
        rtl_file="rtl/nested.sv",
        contract_id="CONTRACT_NESTED",
        obligation_id="OBL_NESTED",
    )
    subprocess.run(["git", "add", "."], cwd=ip, check=True)
    subprocess.run(["git", "commit", "-m", "nested IP baseline"], cwd=ip, text=True, capture_output=True, check=True)

    changed = ip / "rtl" / "nested.sv"
    changed.write_text("module nested; endmodule\n", encoding="utf-8")
    gate = run_main_write_gate(ip, project_root=project)
    assert gate.returncode != 0, gate.stdout
    payload = json.loads(gate.stdout)
    assert payload["status"] == "fail", payload
    expected = "nested_ip/rtl/nested.sv"
    assert expected in payload["results"][0]["implementation_changes"], payload
    assert any(item["code"] == "MAIN_AGENT_WRITE_WITHOUT_SUBAGENT" and item.get("path") == expected for item in payload["issues"]), payload


def test_canonical_run_evidence_archive_guard(tmp_root: Path) -> None:
    ip = make_ip(tmp_root / "archive_guard")
    (ip / "sim").mkdir(parents=True, exist_ok=True)
    (ip / "sim" / "uvm_status.json").write_text(
        json.dumps({"schema_version": "uvm_status.v1", "status": "pass"}) + "\n",
        encoding="utf-8",
    )
    missing_archive = call({"tool": "oag.check", "arguments": {"ip_dir": str(ip)}})
    assert missing_archive["ok"] is True, missing_archive
    assert any(
        "canonical run evidence lacks immutable archive: sim/uvm_status.json" in issue
        for issue in missing_archive["result"]["issues"]
    ), missing_archive

    archive = ip / "sim" / "runs" / "20260101T000000Z_uvm" / "uvm_status.json"
    archive.parent.mkdir(parents=True, exist_ok=True)
    archive.write_text((ip / "sim" / "uvm_status.json").read_text(encoding="utf-8"), encoding="utf-8")
    archived = call({"tool": "oag.check", "arguments": {"ip_dir": str(ip)}})
    assert archived["ok"] is True, archived
    assert not any(
        "canonical run evidence lacks immutable archive: sim/uvm_status.json" in issue
        for issue in archived["result"]["issues"]
    ), archived


def run_lifecycle_check(*args: str) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "OAG_DISABLE_BACKEND": "1"}
    return subprocess.run(
        [sys.executable, str(LIFECYCLE_CHECK), *args],
        text=True,
        capture_output=True,
        check=False,
        cwd=ROOT,
        env=env,
    )


def test_oag_paths_resolver(tmp_root: Path) -> None:
    assert OAG_PATHS.is_file(), OAG_PATHS

    spec = importlib.util.spec_from_file_location("oag_paths_smoke", OAG_PATHS)
    assert spec and spec.loader, spec
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    legacy_ip = tmp_root / "paths_legacy"
    legacy_root = legacy_ip.resolve()
    (legacy_ip / "ontology" / "generated").mkdir(parents=True)
    (legacy_ip / "knowledge").mkdir(parents=True)
    (legacy_ip / "ontology" / "contracts.yaml").write_text("contracts: []\n", encoding="utf-8")

    assert module.state_path(legacy_ip, "knowledge/ledger.jsonl") == legacy_root / "knowledge" / "ledger.jsonl"
    assert module.legacy_or_hidden(legacy_ip, "ontology/contracts.yaml") == legacy_root / "ontology" / "contracts.yaml"
    assert module.generated_path(legacy_ip, "authoring_packets/rtl__demo.json") == legacy_root / "ontology" / "generated" / "authoring_packets" / "rtl__demo.json"

    # anti-escape / normalization guard contract (the security core of the resolver).
    def _expect_value_error(rel: str) -> None:
        try:
            module.state_path(legacy_ip, rel)
        except ValueError:
            return
        raise AssertionError(f"expected ValueError for rel={rel!r}")

    for bad in (
        "/abs/path",
        r"C:\abs\path",
        r"C:drive-relative",
        r"\\server\share\file",
        r"\rooted\path",
        "../escape",
        r"..\escape",
        "a/../b",
        r"a\..\b",
        "",
        ".",
        ".oag",
        "bad\x00path",
    ):
        _expect_value_error(bad)
    # a single '.' is normalized away (not rejected) — pin the documented subtlety.
    assert module.state_path(legacy_ip, "a/./b") == legacy_root / "a" / "b"
    assert module.state_path(legacy_ip, r"knowledge\ledger.jsonl") == legacy_root / "knowledge" / "ledger.jsonl"

    # oag_root() is public but otherwise only indirectly exercised via layout_status.
    assert module.oag_root(legacy_ip) == legacy_root / ".oag"

    # prefix-stripping idempotency: the with-prefix and without-prefix forms must agree.
    assert module.ontology_path(legacy_ip, "ontology/scope_lock.json") == module.ontology_path(legacy_ip, "scope_lock.json")
    assert module.evidence_path(legacy_ip, "evidence/sim/results.xml") == module.evidence_path(legacy_ip, "sim/results.xml")
    assert module.generated_path(legacy_ip, "generated/x") == module.generated_path(legacy_ip, "x")
    assert module.generated_path(legacy_ip, "ontology/generated/x") == module.generated_path(legacy_ip, "x")

    # legacy_or_hidden write-base fallback when neither hidden nor legacy file exists (legacy layout).
    assert module.legacy_or_hidden(legacy_ip, "knowledge/missing.txt") == legacy_root / "knowledge" / "missing.txt"

    dot_ip = tmp_root / "paths_dot_oag"
    dot_root = dot_ip.resolve()
    (dot_ip / ".oag" / "ontology" / "generated").mkdir(parents=True)
    (dot_ip / ".oag" / "knowledge").mkdir(parents=True)
    (dot_ip / "ontology").mkdir(parents=True)
    (dot_ip / ".oag" / "ontology" / "contracts.yaml").write_text("contracts: hidden\n", encoding="utf-8")
    (dot_ip / "ontology" / "contracts.yaml").write_text("contracts: legacy\n", encoding="utf-8")

    assert module.state_path(dot_ip, "knowledge/ledger.jsonl") == dot_root / ".oag" / "knowledge" / "ledger.jsonl"
    assert module.legacy_or_hidden(dot_ip, "ontology/contracts.yaml") == dot_root / ".oag" / "ontology" / "contracts.yaml"
    assert module.ontology_path(dot_ip, "scope_lock.json") == dot_root / ".oag" / "ontology" / "scope_lock.json"
    assert module.evidence_path(dot_ip, "sim/results.xml") == dot_root / ".oag" / "evidence" / "sim" / "results.xml"
    # fallback for a not-yet-existing file must resolve under .oag in the dot layout.
    assert module.legacy_or_hidden(dot_ip, "knowledge/missing.txt") == dot_root / ".oag" / "knowledge" / "missing.txt"

    legacy_cli = subprocess.run(
        [sys.executable, str(OAG_PATHS), "--ip-dir", str(legacy_ip), "--json"],
        text=True,
        capture_output=True,
        check=False,
        cwd=ROOT,
    )
    assert legacy_cli.returncode == 0, legacy_cli.stderr or legacy_cli.stdout
    legacy_result = json.loads(legacy_cli.stdout)
    assert legacy_result["layout"] == "legacy", legacy_result
    assert legacy_result["warnings"] == [], legacy_result
    # lock the layout_status output, not just the layout label.
    assert legacy_result["write_base"] == str(legacy_root), legacy_result
    assert legacy_result["hidden_state"] == [], legacy_result
    assert "knowledge" in legacy_result["legacy_state"] and "ontology" in legacy_result["legacy_state"], legacy_result

    dot_cli = subprocess.run(
        [sys.executable, str(OAG_PATHS), "--ip-dir", str(dot_ip), "--json"],
        text=True,
        capture_output=True,
        check=False,
        cwd=ROOT,
    )
    assert dot_cli.returncode == 0, dot_cli.stderr or dot_cli.stdout
    dot_result = json.loads(dot_cli.stdout)
    assert dot_result["layout"] == "dot_oag", dot_result
    assert dot_result["warnings"] == ["mixed_layout: .oag exists with legacy top-level OAG state"], dot_result
    # the dot layout must report .oag as the write base and surface hidden state.
    assert dot_result["write_base"] == str(dot_root / ".oag"), dot_result
    assert "knowledge" in dot_result["hidden_state"] and "ontology" in dot_result["hidden_state"], dot_result
    assert dot_result["legacy_state"] == ["ontology"], dot_result


def migrate_ip_to_dot_oag(ip: Path) -> None:
    """Relocate ontology/ and knowledge/ under <ip>/.oag/ to emulate a migrated layout."""
    hidden = ip / ".oag"
    hidden.mkdir(exist_ok=True)
    for sub in ("ontology", "knowledge"):
        src = ip / sub
        if src.exists():
            src.rename(hidden / sub)


def _req_quality_json(ip: Path) -> dict:
    proc = subprocess.run(
        [sys.executable, str(REQ_QUALITY_CHECK), "--ip-dir", str(ip), "--json"],
        text=True,
        capture_output=True,
        check=False,
        cwd=ROOT,
        env={**os.environ, "OAG_DISABLE_BACKEND": "1"},
    )
    return {"rc": proc.returncode, "data": json.loads(proc.stdout) if proc.stdout.strip() else {}}


def _run_check_script(script: Path, ip: Path, *extra: str) -> tuple[int, str]:
    proc = subprocess.run(
        [sys.executable, str(script), "--ip-dir", str(ip), *extra, "--json"],
        text=True,
        capture_output=True,
        check=False,
        cwd=ROOT,
        env={**os.environ, "OAG_DISABLE_BACKEND": "1"},
    )
    try:
        status = str(json.loads(proc.stdout).get("status", ""))
    except Exception:
        status = ""
    return proc.returncode, status


def _graph_build_rc(ip: Path, out: Path) -> int:
    return subprocess.run(
        [sys.executable, str(GRAPH), "build", "--ip-dir", str(ip), "--json-out", str(out)],
        text=True,
        capture_output=True,
        check=False,
        cwd=ROOT,
        env={**os.environ, "OAG_DISABLE_BACKEND": "1"},
    ).returncode


def test_dot_oag_layout_state_scripts(tmp_root: Path) -> None:
    """Wave 2 layout transparency: IP-state scripts must behave identically whether
    ontology/ and knowledge/ live at the legacy top level or under <ip>/.oag/.

    Builds a full locked IP (legacy), captures baseline behavior, relocates
    ontology/ + knowledge/ under .oag/, and asserts resolver-routed scripts read
    and write the hidden state with no behavior change. Before Wave 2 conversion
    this fails because scripts hard-code <ip>/ontology and <ip>/knowledge.
    """
    ip = make_ip(tmp_root / "dot_oag_state")

    # Baseline on the legacy layout (assert layout transparency, not closure completeness).
    legacy_check = call({"tool": "oag.check", "arguments": {"ip_dir": str(ip)}})["result"]
    legacy_ok = legacy_check["ok"]
    legacy_issue_set = sorted(legacy_check.get("issues", []))
    legacy_rq = _req_quality_json(ip)
    legacy_checks = {
        "lock_readiness": _run_check_script(LOCK_READINESS_CHECK, ip),
        "stale": _run_check_script(STALE_CHECK, ip),
    }
    legacy_graph_rc = _graph_build_rc(ip, tmp_root / "graph_legacy.json")

    # Relocate ontology/ + knowledge/ under .oag/.
    migrate_ip_to_dot_oag(ip)
    assert not (ip / "ontology").exists(), "legacy ontology/ should be relocated"
    assert not (ip / "knowledge").exists(), "legacy knowledge/ should be relocated"
    assert (ip / ".oag" / "ontology" / "scope_lock.json").is_file(), "ontology under .oag"
    assert (ip / ".oag" / "knowledge" / "ledger.jsonl").is_file(), "knowledge under .oag"

    # oag.check must produce the SAME verdict + issues under .oag; no missing-state issues (the Wave 2 RED gap).
    dot_check = call({"tool": "oag.check", "arguments": {"ip_dir": str(ip)}})["result"]
    dot_issues = dot_check.get("issues", [])
    assert dot_check["ok"] == legacy_ok, (legacy_check, dot_check)
    assert sorted(dot_issues) == legacy_issue_set, (legacy_issue_set, dot_issues)
    for needle in ("missing knowledge directory", "missing records directory", "missing index", "missing ontology"):
        assert not any(needle in issue for issue in dot_issues), (needle, dot_issues)

    # req_quality must match legacy status and requirement count across layouts.
    dot_rq = _req_quality_json(ip)
    assert dot_rq["rc"] == legacy_rq["rc"], (legacy_rq, dot_rq)
    assert dot_rq["data"].get("status") == legacy_rq["data"].get("status"), (legacy_rq, dot_rq)
    assert dot_rq["data"].get("counts", {}).get("requirements") == legacy_rq["data"].get("counts", {}).get("requirements"), (legacy_rq, dot_rq)

    # Standalone checkers (incl. requirement_atom + verification_plan via lock_readiness) match across layouts.
    for name, const in (("lock_readiness", LOCK_READINESS_CHECK), ("stale", STALE_CHECK)):
        assert _run_check_script(const, ip) == legacy_checks[name], (name, legacy_checks[name], _run_check_script(const, ip))

    # graph build must read ontology/knowledge under .oag with the same outcome as legacy.
    dot_graph_rc = _graph_build_rc(ip, tmp_root / "graph_dot.json")
    assert dot_graph_rc == legacy_graph_rc, (legacy_graph_rc, dot_graph_rc)

    # oag.inspect must read hidden ontology state.
    inspected = call({"tool": "oag.inspect", "arguments": {"ip_dir": str(ip), "stage": "rtl", "intent": "dot-oag layout inspect"}})
    assert inspected.get("result"), inspected

    # A new ROCEV record must append into .oag/knowledge and keep the ledger chain valid.
    recorded = call(
        {
            "tool": "oag.record",
            "arguments": {
                "ip_dir": str(ip),
                "stage": "sim",
                "claim": "dot-oag layout ledger append",
                "actor": {"kind": "ai", "id": "codex", "surface": "smoke"},
                "rocev": {
                    "obligation": {"id": "OBL_DOT_OAG_LEDGER", "text": "ledger append under .oag", "status": "open"},
                    "contract": {"id": "CONTRACT_DOT_OAG_LEDGER", "method": "scoreboard"},
                    "evidence": {"files": ["sim/results.xml"], "tests": [], "commit": ""},
                    "validation": {"status": "open", "verdict": "pending", "rationale": "layout transparency"},
                },
            },
        }
    )
    assert recorded["result"].get("ledger_event"), recorded
    assert (ip / ".oag" / "knowledge" / "ledger.jsonl").is_file(), recorded
    assert not (ip / "knowledge").exists(), "record must not recreate legacy knowledge/"

    # Ledger integrity (hash chain + protected snapshot) must hold under .oag.
    post_issues = call({"tool": "oag.check", "arguments": {"ip_dir": str(ip)}})["result"].get("issues", [])
    for bad in ("mismatch", "missing knowledge", "missing records", "missing ontology", "missing index", "protected fields changed"):
        assert not any(bad in issue.lower() for issue in post_issues), (bad, post_issues)


def test_dot_oag_scaffold_layout(tmp_root: Path) -> None:
    """Wave 3: oag.scaffold with layout=dot_oag creates ontology/ and knowledge/
    under <ip>/.oag/ while human-facing dirs stay top-level, and IP-state scripts
    operate on the freshly scaffolded hidden state via the resolver."""
    ip = tmp_root / "dot_oag_scaffold"
    res = call({"tool": "oag.scaffold", "arguments": {"ip_dir": str(ip), "owner": "smoke", "layout": "dot_oag"}})
    assert res["ok"] is True, res
    assert res["result"].get("layout") == "dot_oag", res

    # ontology/ + knowledge/ live under .oag/ ...
    assert (ip / ".oag" / "ontology" / "ip.yaml").is_file(), res
    assert (ip / ".oag" / "ontology" / "scope_lock.json").is_file(), res
    assert (ip / ".oag" / "ontology" / "contracts.yaml").is_file(), res
    assert (ip / ".oag" / "knowledge" / "ledger.jsonl").is_file(), res
    assert (ip / ".oag" / "knowledge" / "_index.json").is_file(), res
    # ... and not at the legacy top level.
    assert not (ip / "ontology").exists(), "no top-level ontology/ under dot_oag scaffold"
    assert not (ip / "knowledge").exists(), "no top-level knowledge/ under dot_oag scaffold"
    # human-facing surfaces stay top-level.
    for top in ("req", "rtl", "tb", "list", "scripts", "doc", "sdc", "sim"):
        assert (ip / top).is_dir(), f"{top}/ should stay top-level"

    # resolver reports a clean dot_oag layout (no mixed-layout warning).
    layout = json.loads(
        subprocess.run(
            [sys.executable, str(OAG_PATHS), "--ip-dir", str(ip), "--json"],
            text=True, capture_output=True, check=False, cwd=ROOT,
        ).stdout
    )
    assert layout["layout"] == "dot_oag", layout
    assert layout["warnings"] == [], layout

    # IP-state scripts operate on the freshly scaffolded .oag IP via the resolver.
    chk = call({"tool": "oag.check", "arguments": {"ip_dir": str(ip)}})["result"]
    assert not any("missing knowledge directory" in i for i in chk.get("issues", [])), chk
    assert not any("missing ontology" in i for i in chk.get("issues", [])), chk
    assert _req_quality_json(ip)["rc"] == 0, "req_quality runs on the .oag-scaffolded IP"


def _hash_tree(root: Path) -> dict:
    import hashlib

    return {
        p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(root.rglob("*"))
        if p.is_file()
    }


def _run_migrate(*args: str) -> tuple[int, dict]:
    proc = subprocess.run(
        [sys.executable, str(MIGRATE_LAYOUT), *args, "--json"],
        text=True,
        capture_output=True,
        check=False,
        cwd=ROOT,
        env={**os.environ, "OAG_DISABLE_BACKEND": "1"},
    )
    return proc.returncode, (json.loads(proc.stdout) if proc.stdout.strip() else {"_stderr": proc.stderr[-300:]})


def test_dot_oag_migration_tool(tmp_root: Path) -> None:
    """Wave 4: oag_migrate_layout.py moves ontology/ and knowledge/ into <ip>/.oag/
    (dry-run by default), preserves file hashes, writes a receipt, keeps IP-state
    scripts working, and rolls back losslessly."""
    ip = tmp_root / "mig_ip"
    sc = call({"tool": "oag.scaffold", "arguments": {"ip_dir": str(ip), "owner": "smoke"}})
    assert sc["ok"] is True, sc
    assert (ip / "ontology").is_dir() and (ip / "knowledge").is_dir(), "top-level OAG state scaffold expected"
    pre = {"ontology": _hash_tree(ip / "ontology"), "knowledge": _hash_tree(ip / "knowledge")}

    # dry-run must change nothing.
    rc, dry = _run_migrate("--ip-dir", str(ip), "--to-dot-oag")
    assert rc == 0 and dry.get("applied") is False, dry
    assert (ip / "ontology").is_dir() and not (ip / ".oag").exists(), "dry-run must not move"

    # apply moves into .oag, preserves hashes, writes a receipt.
    rc, ap = _run_migrate("--ip-dir", str(ip), "--to-dot-oag", "--apply")
    assert rc == 0 and ap.get("applied") is True, ap
    assert (ip / ".oag" / "ontology").is_dir() and (ip / ".oag" / "knowledge").is_dir(), ap
    assert not (ip / "ontology").exists() and not (ip / "knowledge").exists(), "top-level cleared"
    assert _hash_tree(ip / ".oag" / "ontology") == pre["ontology"], "ontology hashes preserved"
    assert _hash_tree(ip / ".oag" / "knowledge") == pre["knowledge"], "knowledge hashes preserved"
    receipt = ip / ap["receipt"]
    assert receipt.is_file(), ap

    # migrated IP still resolves via the resolver.
    chk = call({"tool": "oag.check", "arguments": {"ip_dir": str(ip)}})["result"]
    assert not any(("missing knowledge" in i) or ("missing ontology" in i) for i in chk.get("issues", [])), chk

    # rollback restores the legacy layout losslessly.
    rc, rb = _run_migrate("--rollback", str(receipt))
    assert rc == 0, rb
    assert (ip / "ontology").is_dir() and (ip / "knowledge").is_dir(), "rollback restores top-level"
    assert not (ip / ".oag" / "ontology").exists(), "rollback clears .oag ontology"
    assert _hash_tree(ip / "ontology") == pre["ontology"], "rollback preserves ontology hashes"


def test_dot_oag_mixed_layout_rejected(tmp_root: Path) -> None:
    """Wave 5 enforcement: oag.check fails on an unsafe mixed layout where
    ontology/ or knowledge/ exist both at the top level and under .oag/. Clean
    legacy and clean .oag layouts do not trip the gate."""
    ip = tmp_root / "mixed_ip"
    assert call({"tool": "oag.scaffold", "arguments": {"ip_dir": str(ip), "owner": "smoke"}})["ok"] is True

    # clean legacy layout: no mixed-layout issue.
    issues = call({"tool": "oag.check", "arguments": {"ip_dir": str(ip)}})["result"].get("issues", [])
    assert not any("mixed OAG layout" in i for i in issues), issues

    # migrate to a clean .oag layout: still no mixed-layout issue.
    rc, ap = _run_migrate("--ip-dir", str(ip), "--to-dot-oag", "--apply")
    assert rc == 0 and ap.get("applied") is True, ap
    issues = call({"tool": "oag.check", "arguments": {"ip_dir": str(ip)}})["result"].get("issues", [])
    assert not any("mixed OAG layout" in i for i in issues), issues

    # a stray legacy top-level ontology/ alongside .oag is an unsafe mixed state.
    (ip / "ontology").mkdir(parents=True, exist_ok=True)
    (ip / "ontology" / "stray.yaml").write_text("stray: true\n", encoding="utf-8")
    res = call({"tool": "oag.check", "arguments": {"ip_dir": str(ip)}})["result"]
    assert res["ok"] is False, res
    assert any(("mixed OAG layout" in i) and ("ontology" in i) for i in res.get("issues", [])), res

    # removing the stray legacy dir clears the gate.
    (ip / "ontology" / "stray.yaml").unlink()
    (ip / "ontology").rmdir()
    issues = call({"tool": "oag.check", "arguments": {"ip_dir": str(ip)}})["result"].get("issues", [])
    assert not any("mixed OAG layout" in i for i in issues), issues


def run_baseline_check(*args: str) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "OAG_DISABLE_BACKEND": "1"}
    return subprocess.run(
        [sys.executable, str(BASELINE_CHECK), *args],
        text=True,
        capture_output=True,
        check=False,
        cwd=ROOT,
        env=env,
    )


def run_authoring_packet_check(*args: str) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "OAG_DISABLE_BACKEND": "1"}
    return subprocess.run(
        [sys.executable, str(AUTHORING_PACKET_CHECK), *args],
        text=True,
        capture_output=True,
        check=False,
        cwd=ROOT,
        env=env,
    )


def run_decision_rtl_consistency_check(*args: str) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "OAG_DISABLE_BACKEND": "1"}
    return subprocess.run(
        [sys.executable, str(DECISION_RTL_CONSISTENCY_CHECK), *args],
        text=True,
        capture_output=True,
        check=False,
        cwd=ROOT,
        env=env,
    )


def run_rule_index_meta_check(*args: str) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "OAG_DISABLE_BACKEND": "1"}
    return subprocess.run(
        [sys.executable, str(RULE_INDEX_META_CHECK), *args],
        text=True,
        capture_output=True,
        check=False,
        cwd=ROOT,
        env=env,
    )


def run_stale_check(*args: str) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "OAG_DISABLE_BACKEND": "1"}
    return subprocess.run(
        [sys.executable, str(STALE_CHECK), *args],
        text=True,
        capture_output=True,
        check=False,
        cwd=ROOT,
        env=env,
    )


def run_baseline_cut(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "OAG_DISABLE_BACKEND": "1"}
    return subprocess.run(
        [sys.executable, str(BASELINE_CUT), *args],
        text=True,
        capture_output=True,
        check=False,
        cwd=cwd or ROOT,
        env=env,
    )


def run_baseline_verify(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "OAG_DISABLE_BACKEND": "1"}
    return subprocess.run(
        [sys.executable, str(BASELINE_VERIFY), *args],
        text=True,
        capture_output=True,
        check=False,
        cwd=cwd or ROOT,
        env=env,
    )


def run_ip_version_check(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "OAG_DISABLE_BACKEND": "1"}
    return subprocess.run(
        [sys.executable, str(IP_VERSION_CHECK), *args],
        text=True,
        capture_output=True,
        check=False,
        cwd=cwd or ROOT,
        env=env,
    )


def run_ip_git(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "OAG_DISABLE_BACKEND": "1"}
    return subprocess.run(
        [sys.executable, str(IP_GIT), *args],
        text=True,
        capture_output=True,
        check=False,
        cwd=cwd or ROOT,
        env=env,
    )


def run_oag_run_frame(ip: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "OAG_DISABLE_BACKEND": "1"}
    return subprocess.run(
        [sys.executable, str(RUN_FRAME), "--ip-dir", str(ip), *args],
        text=True,
        capture_output=True,
        check=False,
        cwd=ROOT,
        env=env,
    )


def run_oag_action_model_check(*args: str) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "OAG_DISABLE_BACKEND": "1"}
    return subprocess.run(
        [sys.executable, str(ACTION_MODEL_CHECK), *args],
        text=True,
        capture_output=True,
        check=False,
        cwd=ROOT,
        env=env,
    )


def run_oag_action_plan(ip: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "OAG_DISABLE_BACKEND": "1"}
    return subprocess.run(
        [sys.executable, str(ACTION_PLAN), "--ip-dir", str(ip), *args],
        text=True,
        capture_output=True,
        check=False,
        cwd=ROOT,
        env=env,
    )


def run_oag_action_wavefront_draft(ip: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "OAG_DISABLE_BACKEND": "1"}
    return subprocess.run(
        [sys.executable, str(ACTION_WAVEFRONT_DRAFT), "--ip-dir", str(ip), *args],
        text=True,
        capture_output=True,
        check=False,
        cwd=ROOT,
        env=env,
    )


def run_oag_team_plan(ip: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "OAG_DISABLE_BACKEND": "1"}
    return subprocess.run(
        [sys.executable, str(TEAM_PLAN), "--ip-dir", str(ip), *args],
        text=True,
        capture_output=True,
        check=False,
        cwd=ROOT,
        env=env,
    )


def run_oag_role_health(ip: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "OAG_DISABLE_BACKEND": "1"}
    return subprocess.run(
        [sys.executable, str(ROLE_HEALTH), "--ip-dir", str(ip), *args],
        text=True,
        capture_output=True,
        check=False,
        cwd=ROOT,
        env=env,
    )


def run_oag_action_record(command: str, ip: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "OAG_DISABLE_BACKEND": "1"}
    return subprocess.run(
        [sys.executable, str(ACTION_RECORD), command, "--ip-dir", str(ip), *args],
        text=True,
        capture_output=True,
        check=False,
        cwd=ROOT,
        env=env,
    )


def run_oag_mission_runtime(command: str, ip: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "OAG_DISABLE_BACKEND": "1"}
    return subprocess.run(
        [sys.executable, str(MISSION_RUNTIME), command, "--ip-dir", str(ip), *args],
        text=True,
        capture_output=True,
        check=False,
        cwd=ROOT,
        env=env,
    )


def run_oag_mission_loop(command: str, ip: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "OAG_DISABLE_BACKEND": "1"}
    return subprocess.run(
        [sys.executable, str(MISSION_LOOP), command, "--ip-dir", str(ip), *args],
        text=True,
        capture_output=True,
        check=False,
        cwd=ROOT,
        env=env,
    )


def run_oag_operation_review_frame(ip: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "OAG_DISABLE_BACKEND": "1"}
    return subprocess.run(
        [sys.executable, str(OPERATION_REVIEW_FRAME), "--ip-dir", str(ip), *args],
        text=True,
        capture_output=True,
        check=False,
        cwd=ROOT,
        env=env,
    )


def run_oag_review_frame(ip: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "OAG_DISABLE_BACKEND": "1"}
    return subprocess.run(
        [sys.executable, str(REVIEW_FRAME), "--ip-dir", str(ip), *args],
        text=True,
        capture_output=True,
        check=False,
        cwd=ROOT,
        env=env,
    )


def run_oag_gate_frame(*args: str) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "OAG_DISABLE_BACKEND": "1"}
    return subprocess.run(
        [sys.executable, str(GATE_FRAME), *args],
        text=True,
        capture_output=True,
        check=False,
        cwd=ROOT,
        env=env,
    )


def run_oag_ssot_section_check(ip: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "OAG_DISABLE_BACKEND": "1"}
    return subprocess.run(
        [sys.executable, str(SSOT_SECTION_CHECK), "--ip-dir", str(ip), *args],
        text=True,
        capture_output=True,
        check=False,
        cwd=ROOT,
        env=env,
    )


def run_oag_orchestration_guard(*args: str, project_root: Path | None = None) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "OAG_DISABLE_BACKEND": "1"}
    if project_root:
        env["OAG_PROJECT_ROOT"] = str(project_root)
    return subprocess.run(
        [sys.executable, str(ORCHESTRATION_GUARD), *args],
        text=True,
        capture_output=True,
        check=False,
        cwd=project_root or ROOT.parent,
        env=env,
    )


def run_oag_windows_smoke(*args: str) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "OAG_DISABLE_BACKEND": "1"}
    return subprocess.run(
        [sys.executable, str(WINDOWS_SMOKE), *args],
        text=True,
        capture_output=True,
        check=False,
        cwd=ROOT,
        env=env,
    )


def run_main_write_gate(ip: Path, *, project_root: Path | None = None) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "OAG_DISABLE_BACKEND": "1"}
    if project_root:
        env["OAG_PROJECT_ROOT"] = str(project_root)
    return subprocess.run(
        [sys.executable, str(MAIN_WRITE_GATE), "--ip-dir", str(ip), "--json"],
        text=True,
        capture_output=True,
        check=False,
        cwd=project_root or ROOT.parent,
        env=env,
    )


def run_validate_json(schema: Path, document: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(VALIDATE_JSON), "--schema", str(schema), "--document", str(document), "--json"],
        text=True,
        capture_output=True,
        check=False,
        cwd=ROOT.parent,
    )


def run_agent_catalog_check() -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(AGENT_CATALOG_CHECK), "--json"],
        text=True,
        capture_output=True,
        check=False,
        cwd=ROOT,
    )


def run_closure_check(ip: Path, *extra: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(CLOSURE_CHECK), "--ip-dir", str(ip), *extra, "--json"],
        text=True,
        capture_output=True,
        check=False,
        cwd=ROOT,
    )


def run_pack_release_check() -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(PACK_RELEASE_CHECK), "--json"],
        text=True,
        capture_output=True,
        check=False,
        cwd=ROOT,
    )


def stop_gate(payload: dict, extra_env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "OAG_DISABLE_BACKEND": "1"}
    if extra_env:
        env.update(extra_env)
    return subprocess.run(
        [sys.executable, str(STOP_GATE)],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        check=False,
        cwd=ROOT.parent,
        env=env,
    )


def subagent_gate(payload: dict, extra_env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "OAG_DISABLE_BACKEND": "1"}
    if extra_env:
        env.update(extra_env)
    return subprocess.run(
        [sys.executable, str(SUBAGENT_GATE)],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        check=False,
        cwd=ROOT.parent,
        env=env,
    )


def subagent_start(payload: dict, extra_env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "OAG_DISABLE_BACKEND": "1"}
    if extra_env:
        env.update(extra_env)
    return subprocess.run(
        [sys.executable, str(SUBAGENT_START)],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        check=False,
        cwd=ROOT.parent,
        env=env,
    )


def context_hook(payload: dict) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "OAG_DISABLE_BACKEND": "1"}
    return subprocess.run(
        [sys.executable, str(CONTEXT_HOOK)],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        check=False,
        cwd=ROOT.parent,
        env=env,
    )


def oag_mode_trigger(payload: dict) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "OAG_DISABLE_BACKEND": "1"}
    return subprocess.run(
        [sys.executable, str(OAG_MODE_TRIGGER)],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        check=False,
        cwd=ROOT.parent,
        env=env,
    )


def native_subagent_guard(payload: dict) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "OAG_DISABLE_BACKEND": "1"}
    return subprocess.run(
        [sys.executable, str(NATIVE_SUBAGENT_GUARD)],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        check=False,
        cwd=ROOT.parent,
        env=env,
    )


def deep_interview_prompt_guard(payload: dict) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "OAG_DISABLE_BACKEND": "1"}
    return subprocess.run(
        [sys.executable, str(DEEP_INTERVIEW_GUARD)],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        check=False,
        cwd=ROOT.parent,
        env=env,
    )


def session_start_hook(payload: dict, extra_env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "OAG_DISABLE_BACKEND": "1"}
    if extra_env:
        env.update(extra_env)
    return subprocess.run(
        [sys.executable, str(OAG_SESSION_START)],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        check=False,
        cwd=ROOT.parent,
        env=env,
    )


def hook_context(proc: subprocess.CompletedProcess[str]) -> str:
    if not proc.stdout.strip():
        return ""
    payload = json.loads(proc.stdout)
    output = payload.get("hookSpecificOutput") if isinstance(payload, dict) else {}
    return str(output.get("additionalContext") or "") if isinstance(output, dict) else ""


def hook_target_names(project: Path, payload: dict, *, require_signal: bool = True) -> list[str]:
    spec = importlib.util.spec_from_file_location("oag_hook_utils_smoke", ROOT / "hooks" / "oag_hook_utils.py")
    assert spec and spec.loader, spec
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.PROJECT = project
    return [path.name for path in module.target_ip_dirs(payload, require_signal=require_signal)]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_minimal_rtl_dispatch_readiness(ip: Path, *, module_id: str, rtl_file: str, contract_id: str, obligation_id: str) -> None:
    (ip / "ontology" / "generated" / "authoring_packets").mkdir(parents=True, exist_ok=True)
    (ip / "req").mkdir(parents=True, exist_ok=True)
    semantic_suffix = obligation_id[4:] if obligation_id.startswith("OBL_") else obligation_id
    req_id = f"REQ_{semantic_suffix}"
    atom_id = f"ATOM_{semantic_suffix}"
    claim_id = f"CLAIM_{obligation_id}"
    feature_id = f"FEATURE_{obligation_id}"
    decision_id = f"DEC_{obligation_id}"
    scenario_id = "SCN_SMOKE"
    scoreboard_id = "EVT_DEMO_COUNTER_CX1_RESET_DEFAULTS" if obligation_id == "OBL_DEMO_COUNTER_CX1_RESET_KNOWN" else "EVT_SMOKE"
    coverage_id = "COV_INC" if obligation_id == "OBL_DEMO_COUNTER_CX1_RESET_KNOWN" else "COV_SMOKE"
    (ip / "req" / "locked_truth.md").write_text("# Locked smoke truth\n", encoding="utf-8")
    (ip / "req" / "source_claims.yaml").write_text(
        json.dumps(
            {
                "schema_version": "oag_source_claims.v1",
                "ip": ip.name,
                "claims": [
                    {
                        "id": claim_id,
                        "source": "req/locked_truth.md",
                        "quote": "The smoke output follows the contract oracle.",
                        "summary": "Authoritative smoke fixture behavior.",
                        "status": "confirmed",
                        "normalized_meaning": "The named contract defines the smoke output behavior.",
                        "requirement_refs": [req_id],
                    }
                ],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (ip / "req" / "ambiguity_register.yaml").write_text(
        json.dumps({"schema_version": "oag_ambiguity_register.v1", "ip": ip.name, "ambiguities": []}) + "\n",
        encoding="utf-8",
    )
    (ip / "req" / "evidence_plan.yaml").write_text(
        json.dumps(
            {
                "schema": "ip_evidence_plan.v1",
                "ip": ip.name,
                "planned_scenarios": [
                    {
                        "id": scenario_id,
                        "obligations": [obligation_id],
                        "contracts": [contract_id],
                        "expected_scoreboard_rows": [scoreboard_id],
                    },
                    {
                        "id": "SC_INC_001",
                        "obligations": [obligation_id],
                        "contracts": [contract_id],
                        "expected_scoreboard_rows": ["EVT_DEMO_COUNTER_CX1_RESET_DEFAULTS"],
                    },
                    {
                        "id": "SC_INC_002",
                        "obligations": [obligation_id],
                        "contracts": [contract_id],
                        "expected_scoreboard_rows": ["EVT_DEMO_COUNTER_CX1_RESET_DEFAULTS"],
                    },
                ],
                "contracts": [
                    {
                        "id": contract_id,
                        "obligation": obligation_id,
                        "scenario_refs": [scenario_id],
                        "scoreboard_row_refs": [scoreboard_id],
                    }
                ],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (ip / "ontology" / "features.yaml").write_text(
        json.dumps(
            {
                "schema_version": "oag_features.v1",
                "ip": ip.name,
                "features": [{"id": feature_id, "name": "Smoke behavior", "status": "locked", "requirement_refs": [req_id]}],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (ip / "ontology" / "requirements.yaml").write_text(
        json.dumps(
            {
                "schema": "ontology_requirements.v1",
                "ip": ip.name,
                "requirements": [
                    {
                        "id": req_id,
                        "text": "When sampled after reset, the smoke output shall equal the contract oracle in the same cycle.",
                        "status": "locked",
                        "requirement_type": "behavioral",
                        "source": "req/locked_truth.md",
                        "source_refs": ["req/locked_truth.md"],
                        "source_claim_refs": [claim_id],
                        "feature_refs": [feature_id],
                        "verification_method": ["scoreboard"],
                        "ambiguity_status": "clear",
                    }
                ],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (ip / "ontology" / "requirement_atoms.yaml").write_text(
        json.dumps(
            {
                "schema_version": "oag_requirement_atoms.v1",
                "ip": ip.name,
                "requirement_atoms": [
                    {
                        "id": atom_id,
                        "source_requirement_id": req_id,
                        "status": "locked",
                        "normalized_text": "At the defined sample, smoke output equals the oracle.",
                        "pattern": {"trigger": "sample event", "condition": "reset released", "response": "output equals oracle", "timing": "same cycle"},
                        "boundary": {"responsible_agent": "dut", "environment_agents": ["testbench"]},
                        "assumptions": {"environment": ["clock is stable"], "dut": []},
                        "phenomena": {"dut_inputs": ["clk", "rst_n"], "observable_outputs": ["smoke_output"]},
                        "ambiguity": {"missing_terms": [], "open_questions": []},
                    }
                ],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (ip / "ontology" / "decision_matrix.yaml").write_text(
        json.dumps(
            {
                "schema_version": "oag_decision_matrix.v1",
                "ip": ip.name,
                "decisions": [
                    {
                        "id": decision_id,
                        "question": "Is the smoke fixture semantic scope ready?",
                        "status": "decided",
                        "lock_required": True,
                        "owner": "human",
                        "decision": "ready",
                        "affects": ["requirements"],
                    },
                    {
                        "id": f"{decision_id}_IMPLEMENTATION",
                        "question": "Which bounded implementation action should run next?",
                        "status": "proposed",
                        "lock_required": False,
                        "owner": "human",
                        "recommended": "implement the locked contract",
                        "affects": ["rtl"],
                    },
                ],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (ip / "ontology" / "obligations.yaml").write_text(
        json.dumps(
            {
                "schema": "ontology_obligations.v1",
                "ip": ip.name,
                "obligations": [
                    {
                        "id": obligation_id,
                        "requirement": req_id,
                        "requirement_atom_refs": [atom_id],
                        "status": "open",
                        "text": "On the sample event with reset released, smoke output equals the independent oracle in the same cycle.",
                        "trigger": "sample event",
                        "preconditions": ["reset released"],
                        "guarantee": "smoke output equals oracle",
                        "observable": ["smoke_output"],
                        "oracle_projection": "behavior_model.seed_obligations.reset_known_state",
                        "contracts": [contract_id],
                    }
                ],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (ip / "ontology" / "contracts.yaml").write_text(
        json.dumps(
            {
                "schema_version": "oag_contracts.v2",
                "contracts": [
                    {
                        "id": contract_id,
                        "status": "locked",
                        "obligation": obligation_id,
                        "contract_type": "behavioral",
                        "variables": {"inputs": ["clk", "rst_n"], "outputs": ["smoke_output"]},
                        "assume": {"clock": "stable", "reset": "released before sample"},
                        "guarantee": {"behavior": "smoke output equals oracle at the sample event"},
                        "oracle": {"behavior_refs": ["behavior_model.seed_obligations.reset_known_state"], "cycle_rule_refs": ["cycle_rules.reset.reset_observable_on"]},
                        "behavior_refs": ["behavior_model.seed_obligations.reset_known_state"],
                        "cycle_rule_refs": ["cycle_rules.reset.reset_observable_on"],
                        "verification_projection": {"scenario_refs": [scenario_id], "scoreboard_row_refs": [scoreboard_id]},
                        "scenario_refs": [scenario_id],
                        "scoreboard_row_refs": [scoreboard_id],
                        "evidence_kinds": ["simulation", "scoreboard"],
                        "pass_condition": "Passing independent scoreboard row with mismatch=false.",
                    }
                ],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (ip / "ontology" / "verification_plan.yaml").write_text(
        json.dumps(
            {
                "schema_version": "oag_verification_plan.v1",
                "ip": ip.name,
                "verification_objectives": [
                    {
                        "id": f"VOBJ_{obligation_id.replace('-', '_').upper()}",
                        "status": "ready",
                        "requirement": req_id,
                        "obligation": obligation_id,
                        "contract": contract_id,
                        "intent": "Prove the smoke output against an independent oracle.",
                        "proof_methods": ["scoreboard"],
                        "scenarios": [scenario_id],
                        "coverage_goals": [coverage_id],
                        "residual_risks": [{"id": "RISK_NONE", "risk": "No residual risk in smoke fixture.", "status": "closed"}],
                    }
                ],
                "open_strategy_blockers": [],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (ip / "ontology" / "tb_methodology.yaml").write_text(
        json.dumps(
            {
                "schema_version": "oag_tb_methodology.v1",
                "ip": ip.name,
                "methodology_policy": {
                    "profile": "simple_leaf_apb_peripheral",
                    "framework_required": False,
                    "full_uvm_required": False,
                    "default_depth": "directed_table_driven_micro_tb",
                    "random_requires_constraints": True,
                    "random_requires_coverage_goals": True,
                    "failed_tests_count_for_coverage": False,
                },
                "architecture_roles": {
                    "driver": {"status": "planned"},
                    "monitor": {"status": "planned"},
                    "predictor": {"status": "planned"},
                    "scoreboard": {"status": "planned"},
                    "coverage": {"status": "planned"},
                    "assertion_hooks": {"status": "optional"},
                    "result_writer": {"status": "planned"},
                },
                "stimulus_strategy": {
                    "directed_smoke": True,
                    "table_driven_register_tests": True,
                    "constrained_random": {
                        "enabled": False,
                        "constraints": [],
                        "seed_strategy": "fixed_seed",
                    },
                },
                "coverage_goals": [{"id": coverage_id, "requirement": req_id, "obligation": obligation_id, "contract": contract_id}],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (ip / "ontology" / "decomposition.yaml").write_text(
        "\n".join(
            [
                "schema: oag_decomposition.v1",
                f"ip: {ip.name}",
                "profile:",
                "  mode: small_leaf_single_file",
                "  rationale: Smoke fixture is intentionally one bounded leaf module.",
                "modules:",
                f"  - id: {module_id}",
                f"    name: {module_id}",
                "    role: rtl",
                "    ownership: current_ip",
                f"    file: {rtl_file}",
                f"    owned_obligations: [{obligation_id}]",
                f"    owned_contracts: [{contract_id}]",
                "    structure_refs: [SIG_SMOKE]",
                "    source_refs: [ontology/contracts.yaml]",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (ip / "ontology" / "domain_intent.yaml").write_text(
        "\n".join(
            [
                "schema_version: oag_domain_intent.v1",
                f"ip: {ip.name}",
                "clock_domains:",
                "  - id: CD_CLK",
                "    clock: clk",
                "reset_domains:",
                "  - id: RD_RST_N",
                "    reset: rst_n",
                "    clock_domain: CD_CLK",
                "    polarity: active_low",
                "    assertion: asynchronous",
                "    deassertion: synchronous",
                "cdc_crossings: []",
                "rdc_crossings:",
                "  - id: RDC_NONE",
                "    classification: no_known_rdc",
                "    basis: [single clock/reset fixture]",
                "",
            ]
        ),
        encoding="utf-8",
    )
    packet_dir = ip / "ontology" / "generated" / "authoring_packets"
    (packet_dir / f"module__{module_id}.json").write_text(
        json.dumps(
            {
                "schema_version": "oag_authoring_packet.v1",
                "generated_by": "smoke",
                "generated_at": "2026-01-01T00:00:00Z",
                "ip": ip.name,
                "module": {"id": module_id, "name": module_id, "file": rtl_file},
                "structure_profile": "small_leaf_single_file",
                "source_refs": ["ontology/contracts.yaml"],
                "structure_refs": ["SIG_SMOKE"],
                "obligations": [{"id": obligation_id}],
                "contracts": [{"id": contract_id}],
                "requirements": [],
                "execution_policy": {"edit_policy": "subagent_only"},
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    (packet_dir / f"rtl__{ip.name}.json").write_text(
        json.dumps(
            {
                "schema_version": "oag_rtl_authoring_packet.v1",
                "packet_type": "rtl_authoring_packet",
                "ip": ip.name,
                "allowed_truth_sources": ["ontology/contracts.yaml"],
                "forbidden_sources": ["tb", "sim", "dut_output"],
                "contract_refs_to_implement": [contract_id],
                "behavior_refs_implemented_target": ["behavior_model.seed_obligations.reset_known_state"],
                "ppa_notes_required": True,
                "cdc_rdc_notes_required": True,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    (packet_dir / f"tb__{ip.name}.json").write_text(
        json.dumps(
            {
                "schema_version": "oag_tb_authoring_packet.v1",
                "packet_type": "tb_authoring_packet",
                "ip": ip.name,
                "expected_source_policy": "contract_oracle_only",
                "forbidden_expected_sources": ["dut_output", "rtl_expression", "post_hoc_simulation"],
                "contract_refs": [contract_id],
                "scenario_refs": ["SCN_SMOKE"],
                "scoreboard_row_refs": ["EVT_SMOKE"],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    compile_inputs = ["ontology/contracts.yaml", "ontology/decomposition.yaml", "ontology/domain_intent.yaml"]
    (ip / "ontology" / "generated" / "compile_manifest.json").write_text(
        json.dumps(
            {
                "schema_version": "oag_compile_manifest.v1",
                "status": "pass",
                "compiled_at": "2026-01-01T00:00:00Z",
                "input_fingerprints": [{"path": rel, "sha256": sha256(ip / rel)} for rel in compile_inputs],
                "output_fingerprints": [],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def test_authoring_packets_honor_locked_decision_refs(tmp_root: Path) -> None:
    ip = tmp_root / "packet_decision_refs_ip"
    (ip / "ontology").mkdir(parents=True)
    write_minimal_rtl_dispatch_readiness(
        ip,
        module_id="demo",
        rtl_file="rtl/demo.sv",
        contract_id="CONTRACT_DEMO",
        obligation_id="OBL_DEMO",
    )
    (ip / "ontology" / "decision_matrix.yaml").write_text(
        json.dumps(
            {
                "schema_version": "oag_decision_matrix.v1",
                "ip": ip.name,
                "decisions": [
                    {
                        "id": "D_FIFO_DEPTH",
                        "question": "Which public FIFO depth must RTL/TB honor?",
                        "status": "decided",
                        "lock_required": True,
                        "owner": "human",
                        "decision_class": "parameterizable",
                        "representation": "parameter",
                        "decision": 8,
                        "affects": ["rtl", "tb"],
                        "contract_refs": ["CONTRACT_DEMO"],
                    },
                    {
                        "id": "D_MODULE_ONLY",
                        "question": "Which module-local implementation decision must packets honor?",
                        "status": "decided",
                        "lock_required": True,
                        "owner": "human",
                        "decision_class": "parameterizable",
                        "representation": "parameter",
                        "decision": 1,
                        "target_modules": ["demo"],
                    }
                ],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    missing = run_authoring_packet_check("--ip-dir", str(ip), "--require-packets", "--json")
    assert missing.returncode != 0, missing.stdout
    missing_payload = json.loads(missing.stdout)
    assert any(item["code"] == "PACKET_DECISION_REF_TO_HONOR_MISSING" for item in missing_payload["issues"]), missing_payload
    assert "D_MODULE_ONLY" in json.dumps(missing_payload), missing_payload

    packet_dir = ip / "ontology" / "generated" / "authoring_packets"
    for packet_name in (f"rtl__{ip.name}.json", f"tb__{ip.name}.json"):
        packet_path = packet_dir / packet_name
        packet = json.loads(packet_path.read_text(encoding="utf-8"))
        packet["decision_refs_to_honor"] = ["D_FIFO_DEPTH", "D_MODULE_ONLY"]
        packet_path.write_text(json.dumps(packet, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    clean = run_authoring_packet_check("--ip-dir", str(ip), "--require-packets", "--json")
    assert clean.returncode == 0, clean.stderr or clean.stdout


def test_decision_rtl_consistency_check(tmp_root: Path) -> None:
    ip = tmp_root / "decision_rtl_consistency_ip"
    (ip / "ontology").mkdir(parents=True)
    (ip / "rtl").mkdir(parents=True)
    (ip / "ontology" / "decision_matrix.yaml").write_text(
        json.dumps(
            {
                "schema_version": "oag_decision_matrix.v1",
                "ip": ip.name,
                "decisions": [
                    {
                        "id": "D_DEPTH",
                        "question": "What is the public FIFO depth?",
                        "status": "decided",
                        "lock_required": True,
                        "owner": "human",
                        "decision_class": "parameterizable",
                        "representation": "parameter",
                        "parameter": "FIFO_DEPTH",
                        "decision": 8,
                    },
                    {
                        "id": "D_ZERO",
                        "question": "Can zero-valued locked parameters mismatch?",
                        "status": "decided",
                        "lock_required": True,
                        "owner": "human",
                        "decision_class": "parameterizable",
                        "representation": "parameter",
                        "parameter": "ENABLE_FAST_PATH",
                        "decision": 0,
                    },
                    {
                        "id": "D_PIPE",
                        "question": "Is pipelining generated in RTL and vplan?",
                        "status": "decided",
                        "lock_required": True,
                        "owner": "human",
                        "decision_class": "architecture_tradeoff",
                        "representation": "generate_option",
                        "selected_option": "PIPELINED",
                    },
                ],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (ip / "ontology" / "verification_plan.yaml").write_text(
        json.dumps({"schema_version": "oag_verification_plan.v1", "ip": ip.name, "verification_configurations": [{"id": "PIPELINED"}]}, indent=2) + "\n",
        encoding="utf-8",
    )
    rtl_path = ip / "rtl" / "demo.sv"
    rtl_path.write_text("module demo; parameter FIFO_DEPTH = 4; parameter ENABLE_FAST_PATH = 1; if (PIPELINED) begin end endmodule\n", encoding="utf-8")
    bad = run_decision_rtl_consistency_check("--ip-dir", str(ip), "--json")
    assert bad.returncode != 0, bad.stdout
    bad_payload = json.loads(bad.stdout)
    assert any(item["code"] == "DECISION_RTL_PARAMETER_MISMATCH" for item in bad_payload["issues"]), bad_payload
    assert "ENABLE_FAST_PATH" in json.dumps(bad_payload), bad_payload

    rtl_path.write_text("module demo; parameter FIFO_DEPTH = 8; parameter ENABLE_FAST_PATH = 0; if (PIPELINED) begin end endmodule\n", encoding="utf-8")
    good = run_decision_rtl_consistency_check("--ip-dir", str(ip), "--json")
    assert good.returncode == 0, good.stderr or good.stdout
    assert json.loads(good.stdout)["status"] == "pass", good.stdout

    readiness_spec = importlib.util.spec_from_file_location("oag_lock_readiness_pre_rtl_smoke", LOCK_READINESS_CHECK)
    assert readiness_spec and readiness_spec.loader
    readiness_module = importlib.util.module_from_spec(readiness_spec)
    readiness_spec.loader.exec_module(readiness_module)
    pre_rtl_ip = tmp_root / "decision_rtl_pre_rtl_ip"
    (pre_rtl_ip / "ontology").mkdir(parents=True)
    (pre_rtl_ip / "ontology" / "scope_lock.json").write_text(json.dumps({"state": "locked"}) + "\n", encoding="utf-8")
    (pre_rtl_ip / "ontology" / "decision_matrix.yaml").write_text(
        json.dumps(
            {
                "schema_version": "oag_decision_matrix.v1",
                "ip": pre_rtl_ip.name,
                "decisions": [
                    {
                        "id": "D_PRE_RTL",
                        "question": "Pre-RTL parameter?",
                        "status": "decided",
                        "lock_required": True,
                        "owner": "human",
                        "decision_class": "parameterizable",
                        "representation": "parameter",
                        "parameter": "WIDTH",
                        "decision": 0,
                    }
                ],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    pre_rtl = readiness_module.check(pre_rtl_ip)
    assert pre_rtl["decision_rtl_consistency"]["status"] == "skipped", pre_rtl
    assert not any(item.get("code") == "DECISION_RTL_PARAMETER_MISSING" for item in pre_rtl["issues"]), pre_rtl


def test_loop_runner_execute_mode_writes_receipt(tmp_root: Path) -> None:
    spec = importlib.util.spec_from_file_location("oag_loop_runner_execute_smoke", LOOP_RUNNER)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    ip = make_ip(tmp_root / "loop_runner_execute")
    run_id = "RUN_EXECUTE"
    batch = {
        "schema_version": "oag_recommended_batch.v1",
        "batch_id": "batch.execute",
        "job_type": "VALIDATION_RECORD_JOB",
        "can_execute": True,
        "tasks": [{"task_id": "record.OBL_1", "can_execute": True, "required_evidence": ["sim/results.xml"]}],
    }
    result = {
        "schema_version": "oag_loop_runner.v1",
        "status": "pass",
        "run_id": run_id,
        "decision": "continue",
        "reason": "batch_available",
        "loop_policy": {"mode": "execute"},
        "recommended_batch": batch,
        "plan": {},
        "dispatch_command_candidates": [],
    }
    payload = module._execute_batch(ip, run_id, result, batch)
    assert payload["reason"] == "executed_batch", payload
    receipt_path = Path(payload["execution"]["receipt_path"])
    assert receipt_path.is_file(), payload
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert receipt["job_type"] == "VALIDATION_RECORD_JOB", receipt
    assert receipt["action"] == "bounded_execute_validation_record", receipt
    assert receipt["task_results"][0]["record_response"]["ok"] is True, receipt
    assert receipt["post_checks"]["compile"]["ok"] is True, receipt
    assert receipt["post_checks"]["check"]["ok"] is True, receipt

    blocked = module._execute_batch(ip, run_id, result, {**batch, "can_execute": False})
    assert blocked["reason"] == "execute_not_allowed", blocked
    wrong_job = module._execute_batch(ip, run_id, result, {**batch, "job_type": "RTL_IMPLEMENT_JOB"})
    assert wrong_job["reason"] == "execute_job_type_not_allowed", wrong_job


def test_rule_index_meta_check() -> None:
    meta = run_rule_index_meta_check("--json")
    assert meta.returncode == 0, meta.stderr or meta.stdout
    payload = json.loads(meta.stdout)
    assert payload["status"] == "pass", payload
    assert payload["counts"]["rules"] >= 1, payload


def make_ip(root: Path) -> Path:
    ip = root / "demo_counter_cx1"
    scaffold = call({"tool": "oag.scaffold", "arguments": {"ip_dir": str(ip), "owner": "smoke"}})
    assert scaffold["ok"] is True, scaffold
    assert scaffold["result"]["schema_version"] == "oag_scaffold_result.v1", scaffold
    ip_git = scaffold["result"].get("ip_git", {})
    assert ip_git.get("status") == "pass", scaffold
    metadata_checkpoint = scaffold["result"].get("ip_git_metadata_checkpoint", {})
    assert metadata_checkpoint.get("status") == "pass", scaffold
    assert metadata_checkpoint.get("commit", {}).get("committed") is True, scaffold
    assert (ip / ".git").exists(), "scaffold should initialize IP-local git"
    assert (ip / ".gitignore").is_file(), "scaffold should create IP-local .gitignore"
    head = subprocess.run(["git", "-C", str(ip), "rev-parse", "--verify", "HEAD"], text=True, capture_output=True, check=False)
    assert head.returncode == 0, head.stderr or head.stdout
    clean = subprocess.run(["git", "-C", str(ip), "status", "--porcelain"], text=True, capture_output=True, check=False)
    assert clean.returncode == 0 and clean.stdout == "", clean.stdout
    waves = ip / "sim" / "waves"
    waves.mkdir(parents=True, exist_ok=True)
    (waves / "debug.fst").write_text("ignored waveform dump\n", encoding="utf-8")
    ignored = subprocess.run(
        ["git", "-C", str(ip), "status", "--porcelain", "--", "sim/waves/debug.fst"],
        text=True,
        capture_output=True,
        check=False,
    )
    assert ignored.returncode == 0 and ignored.stdout == "", ignored.stdout
    (waves / "debug.fst").unlink()
    assert (ip / "req" / "deep_semantic_intake").is_dir()
    assert (ip / "req" / "source_claims.yaml").is_file()
    assert (ip / "req" / "ambiguity_register.yaml").is_file()
    assert (ip / "ontology" / "ip.yaml").is_file()
    assert (ip / "ontology" / "features.yaml").is_file()
    assert (ip / "ontology" / "requirements.yaml").is_file()
    assert (ip / "ontology" / "requirement_atoms.yaml").is_file()
    assert (ip / "ontology" / "decision_matrix.yaml").is_file()
    assert (ip / "ontology" / "obligations.yaml").is_file()
    assert (ip / "ontology" / "contracts.yaml").is_file()
    assert (ip / "ontology" / "modeling.yaml").is_file()
    assert (ip / "ontology" / "domain_intent.yaml").is_file()
    assert (ip / "ontology" / "verification_plan.yaml").is_file()
    assert (ip / "ontology" / "tb_methodology.yaml").is_file()
    assert (ip / "ontology" / "structure.yaml").is_file()
    assert (ip / "ontology" / "ipxact_projection.yaml").is_file()
    assert (ip / "ontology" / "decomposition.yaml").is_file()
    assert (ip / "ontology" / "design_rules.yaml").is_file()
    assert (ip / "ontology" / "drafts").is_dir()
    assert (ip / "ontology" / "stages.yaml").is_file()
    assert (ip / "ontology" / "policies.yaml").is_file()
    policy_text = (ip / "ontology" / "policies.yaml").read_text(encoding="utf-8")
    assert "execution_policy:" in policy_text, policy_text
    assert "hook_auto_continue_until: all" in policy_text, policy_text
    assert "graph_policy:" in policy_text, policy_text
    assert "compile_skip_when_fresh: true" in policy_text, policy_text
    assert "requirement_quality_policy:" in policy_text, policy_text
    assert "canonical_feature_file: ontology/features.yaml" in policy_text, policy_text
    assert "modeling_policy:" in policy_text, policy_text
    assert "canonical_ipxact_projection_file: ontology/ipxact_projection.yaml" in policy_text, policy_text
    assert "requirement_decomposition_policy:" in policy_text, policy_text
    assert "decision_matrix_policy:" in policy_text, policy_text
    assert "contract_strength_policy:" in policy_text, policy_text
    assert "authoring_packet_policy:" in policy_text, policy_text
    assert "traceability_policy:" in policy_text, policy_text
    assert "verification_strategy_policy:" in policy_text, policy_text
    assert "domain_crossing_policy:" in policy_text, policy_text
    assert "tb_methodology_policy:" in policy_text, policy_text
    assert (ip / "ontology" / "protection.yaml").is_file()
    assert (ip / "ontology" / "evidence" / "scoreboard_rows.v1.yaml").is_file()
    assert (ip / "ontology" / "evidence" / "stage_run_receipt.v1.yaml").is_file()
    assert (ip / "ontology" / "evidence" / "cdc_rdc_report.v1.yaml").is_file()
    assert (ip / "ontology" / "evidence" / "verification_plan_report.v1.yaml").is_file()
    assert (ip / "ontology" / "evidence" / "tb_methodology_report.v1.yaml").is_file()
    assert (ip / "ontology" / "decision_receipt.v1.yaml").is_file()
    assert (ip / "ontology" / "run_state.v1.yaml").is_file()
    assert (ip / "ontology" / "metrics").is_dir()
    assert (ip / "ontology" / "metrics" / "improvement_metrics.v1.yaml").is_file()
    assert (ip / "ontology" / "handoff_readiness.v1.yaml").is_file()
    assert (ip / "ontology" / "gates" / "gate_self_test_registry.yaml").is_file()
    assert (ip / "ontology" / "scope_lock.json").is_file()
    assert (ip / "knowledge" / "_index.json").is_file()
    assert (ip / "knowledge" / "ledger.jsonl").is_file()
    assert (ip / "list" / "rtl.f").is_file()
    run_lint_py = (ip / "scripts" / "run_lint.py").read_text(encoding="utf-8")
    run_lint_sh = (ip / "scripts" / "run_lint.sh").read_text(encoding="utf-8")
    run_sim_py = (ip / "scripts" / "run_sim.py").read_text(encoding="utf-8")
    run_sim_sh = (ip / "scripts" / "run_sim.sh").read_text(encoding="utf-8")
    assert "OAG_LINT_BACKEND" in run_lint_py, run_lint_py
    assert "oag_pyslang_lint.py" in run_lint_py, run_lint_py
    assert "subprocess.run(cmd" in run_lint_py, run_lint_py
    assert "shell=True" not in run_lint_py, run_lint_py
    assert "run_lint.py" in run_lint_sh, run_lint_sh
    assert "run_sim.py" in run_sim_sh, run_sim_sh
    assert "BASH_SOURCE" not in run_lint_sh, run_lint_sh
    assert "/bin/sh" not in run_lint_sh, run_lint_sh
    assert "Path(__file__).resolve().parents[1]" in run_sim_py, run_sim_py
    lock_status = call({"tool": "oag.lock_status", "arguments": {"ip_dir": str(ip)}})
    assert lock_status["result"]["state"] == "draft", lock_status
    write_minimal_rtl_dispatch_readiness(
        ip,
        module_id="demo_counter_cx1",
        rtl_file="rtl/demo_counter_cx1.sv",
        contract_id="CONTRACT_DEMO_COUNTER_CX1_SIM_SCOREBOARD",
        obligation_id="OBL_DEMO_COUNTER_CX1_RESET_KNOWN",
    )
    locked = call(
        {
            "tool": "oag.lock",
            "arguments": {
                "ip_dir": str(ip),
                "summary": "Smoke test locks the demo counter seed scope before implementation evidence.",
                "confirmed_scope": ["demo counter reset/count scoreboard closure"],
                "actor": {"kind": "human", "id": "smoke-owner", "surface": "smoke"},
                "approval": {
                    "kind": "human",
                    "approved": True,
                    "approved_by": "smoke-owner",
                    "reason": "Smoke owner approves the semantically ready fixture scope.",
                },
            },
        }
    )
    assert locked["result"]["locked"] is True, locked
    (ip / "rtl" / "rtl_compile.json").write_text(json.dumps({"status": "pass"}), encoding="utf-8")
    (ip / "lint" / "dut_lint.json").write_text(json.dumps({"status": "pass"}), encoding="utf-8")
    (ip / "sim" / "results.xml").write_text('<testsuite failures="0"/>\n', encoding="utf-8")
    rows = [
        {
            "event_id": "EVT_DEMO_COUNTER_CX1_RESET_DEFAULTS",
            "goal_id": "GOAL_COUNTER_INC",
            "obligation_id": "OBL_DEMO_COUNTER_CX1_RESET_KNOWN",
            "contract_id": "CONTRACT_DEMO_COUNTER_CX1_SIM_SCOREBOARD",
            "contract_refs": ["CONTRACT_DEMO_COUNTER_CX1_SIM_SCOREBOARD"],
            "scenario_id": "SC_INC_001",
            "cycle": 1,
            "stimulus": {"valid": 1},
            "expected": {"count": 1},
            "expected_source": {
                "kind": "behavior_model",
                "refs": ["behavior_model.seed_obligations.reset_known_state"],
            },
            "observed": {"count": 1},
            "observed_source": {"kind": "dut_signal", "path": "dut.count"},
            "passed": True,
            "mismatch": "",
            "coverage_refs": ["COV_INC"],
        },
        {
            "event_id": "EVT_DEMO_COUNTER_CX1_RESET_DEFAULTS",
            "goal_id": "GOAL_COUNTER_INC",
            "obligation_id": "OBL_DEMO_COUNTER_CX1_RESET_KNOWN",
            "contract_id": "CONTRACT_DEMO_COUNTER_CX1_SIM_SCOREBOARD",
            "contract_refs": ["CONTRACT_DEMO_COUNTER_CX1_SIM_SCOREBOARD"],
            "scenario_id": "SC_INC_002",
            "cycle": 2,
            "stimulus": {"valid": 1},
            "expected": {"count": 2},
            "expected_source": {
                "kind": "behavior_model",
                "refs": ["behavior_model.seed_obligations.reset_known_state"],
            },
            "observed": {"count": 2},
            "observed_source": {"kind": "monitor", "path": "counter_monitor.count"},
            "passed": True,
            "mismatch": "",
            "coverage_refs": ["COV_INC"],
        },
    ]
    (ip / "sim" / "scoreboard_events.jsonl").write_text(
        "\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n",
        encoding="utf-8",
    )
    (ip / "sim" / "scenario_mapping.json").write_text(
        json.dumps(
            {
                "schema_version": "oag_scenario_mapping.v1",
                "scenarios": [
                    {
                        "id": "SC_INC_001",
                        "contracts": ["CONTRACT_DEMO_COUNTER_CX1_SIM_SCOREBOARD"],
                        "scoreboard_rows": ["EVT_DEMO_COUNTER_CX1_RESET_DEFAULTS"],
                    },
                    {
                        "id": "SC_INC_002",
                        "contracts": ["CONTRACT_DEMO_COUNTER_CX1_SIM_SCOREBOARD"],
                        "scoreboard_rows": ["EVT_DEMO_COUNTER_CX1_RESET_DEFAULTS"],
                    },
                ],
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    (ip / "cov" / "coverage.json").write_text(json.dumps({"status": "pass"}), encoding="utf-8")
    (ip / "signoff" / "truth_coverage.json").write_text(json.dumps({"status": "pass"}), encoding="utf-8")
    return ip


def test_lock_preview_frame_preserves_verbatim_source(tmp_root: Path) -> None:
    ip = make_ip(tmp_root / "lock_preview_frame")
    marker = "# RAW_MARKER <keep & exact>\n"
    source_claims = ip / "req" / "source_claims.yaml"
    source_claims.write_text(source_claims.read_text(encoding="utf-8") + marker, encoding="utf-8")
    result = run_lock_preview_frame(ip, "--readiness-mode", "draft", "--json")
    assert result.returncode == 0, result.stderr or result.stdout
    payload = json.loads(result.stdout)
    assert payload["status"] == "pass", payload
    html_path = Path(payload["html"])
    json_path = Path(payload["json"])
    assert html_path.is_file(), payload
    assert json_path.is_file(), payload
    html_text = html_path.read_text(encoding="utf-8")
    assert "OAG Pre-Lock Review Frame" in html_text, html_text
    assert "Operation Context" in html_text, html_text
    assert "req/source_claims.yaml" in html_text, html_text
    assert "RAW_MARKER &lt;keep &amp; exact&gt;" in html_text, html_text
    assert "The block below is the file content with HTML escaping only" in html_text, html_text
    sidecar = json.loads(json_path.read_text(encoding="utf-8"))
    assert sidecar["schema_version"] == "oag_lock_preview_frame.v1", sidecar
    assert sidecar["operation_context"]["status"] in {"pass", "needs_attention", "unavailable"}, sidecar
    source_rows = {item["name"]: item for item in sidecar["sources"]}
    assert source_rows["source_claims"]["sha256"] == sha256(source_claims), source_rows["source_claims"]
    assert "raw_text" not in source_rows["source_claims"], source_rows["source_claims"]


def test_oag_team_plan_mode(tmp_root: Path) -> None:
    ip = make_ip(tmp_root / "team_plan")
    proc = run_oag_team_plan(ip, "--json")
    assert proc.returncode == 0, proc.stderr or proc.stdout
    payload = json.loads(proc.stdout)
    assert payload["schema_version"] == "oag_team_plan_result.v1", payload
    assert payload["status"] in {"pass", "blocked"}, payload
    plan = payload["plan"]
    assert plan["schema_version"] == "oag_team_plan.v1", plan
    assert plan["no_spawn"] is True, plan
    assert plan["recommendation"]["mode"] in {"default", "team_plan_optional", "team_plan_recommended", "blocked"}, plan
    assert plan["team"]["lead"]["role"] == "Team Lead", plan
    assert all(task.get("may_claim_complete") is False for task in plan["tasks"]), plan
    assert Path(ip / payload["output_path"]).is_file(), payload
    assert "Worker" not in [task.get("role") for task in plan["tasks"]] or plan["recommendation"]["mode"] != "default", plan

    no_write = run_oag_team_plan(ip, "--no-write", "--json")
    assert no_write.returncode == 0, no_write.stderr or no_write.stdout
    no_write_payload = json.loads(no_write.stdout)
    assert no_write_payload["written"] is False, no_write_payload
    assert no_write_payload["plan"]["no_spawn"] is True, no_write_payload


def test_oag_run_control_layer(tmp_root: Path) -> None:
    project = tmp_root / "run_control_project"
    ip = make_ip(project)
    ticket = call(
        {
            "tool": "oag.ticket",
            "arguments": {
                "ip_dir": str(ip),
                "stage": "rtl",
                "reason": "Run-control smoke requires one bounded implementation action candidate.",
            },
        }
    )
    assert ticket["ok"] is True, ticket
    compile_manifest = ip / "ontology" / "generated" / "compile_manifest.json"
    if compile_manifest.is_file():
        compile_manifest.unlink()

    action_model = run_oag_action_model_check("--json")
    assert action_model.returncode == 0, action_model.stderr or action_model.stdout
    assert json.loads(action_model.stdout)["status"] == "pass", action_model.stdout

    action_plan = run_oag_action_plan(ip, "--quick", "--json")
    assert action_plan.returncode == 0, action_plan.stderr or action_plan.stdout
    action_plan_payload = json.loads(action_plan.stdout)
    assert action_plan_payload["schema_version"] == "oag_action_plan_result.v1", action_plan_payload
    assert action_plan_payload["status"] == "pass", action_plan_payload
    assert Path(ip / action_plan_payload["output_path"]).is_file(), action_plan_payload
    assert Path(ip / action_plan_payload["action_graph_path"]).is_file(), action_plan_payload
    assert action_plan_payload["mission_instance_id"], action_plan_payload
    assert action_plan_payload["candidate_count"] >= 1, action_plan_payload
    assert action_plan_payload["dependency_graph"]["summary"]["node_count"] >= 1, action_plan_payload

    mission_show = run_oag_mission_runtime("show", ip, "--mission-id", "active", "--json")
    assert mission_show.returncode == 0, mission_show.stderr or mission_show.stdout
    mission_payload = json.loads(mission_show.stdout)
    assert mission_payload["status"] == "pass", mission_payload
    assert mission_payload["mission"]["id"] == action_plan_payload["mission_instance_id"], mission_payload

    mission_tick = run_oag_mission_loop("tick", ip, "--quick", "--json")
    assert mission_tick.returncode == 0, mission_tick.stderr or mission_tick.stdout
    mission_tick_payload = json.loads(mission_tick.stdout)
    assert mission_tick_payload["schema_version"] == "oag_mission_loop_result.v1", mission_tick_payload
    assert mission_tick_payload["status"] in {"pass", "blocked"}, mission_tick_payload
    assert Path(ip / mission_tick_payload["state_path"]).is_file(), mission_tick_payload
    assert Path(ip / mission_tick_payload["tick_log_path"]).is_file(), mission_tick_payload
    assert mission_tick_payload["tick"]["decision"] in {"action_started", "needs_user", "self_explore", "blocked", "idle"}, mission_tick_payload
    if mission_tick_payload["tick"]["decision"] == "action_started":
        assert mission_tick_payload["tick"]["action_record"]["status"] == "pass", mission_tick_payload
        loop_action_id = mission_tick_payload["tick"]["action_record"]["action_id"]
        loop_action_update = run_oag_action_record(
            "update",
            ip,
            "--action-id",
            loop_action_id,
            "--status",
            "accepted",
            "--summary",
            "smoke accepted mission-loop-started action",
            "--json",
        )
        assert loop_action_update.returncode == 0, loop_action_update.stderr or loop_action_update.stdout

    mission_loop_explain = run_oag_mission_loop("explain", ip, "--json")
    assert mission_loop_explain.returncode == 0, mission_loop_explain.stderr or mission_loop_explain.stdout
    mission_loop_explain_payload = json.loads(mission_loop_explain.stdout)
    assert mission_loop_explain_payload["state"]["schema_version"] == "oag_mission_loop_state.v1", mission_loop_explain_payload
    assert mission_loop_explain_payload["last_tick"], mission_loop_explain_payload

    run_frame = run_oag_run_frame(ip, "--json")
    assert run_frame.returncode == 0, run_frame.stderr or run_frame.stdout
    run_payload = json.loads(run_frame.stdout)
    assert run_payload["schema_version"] == "oag_run_frame_result.v1", run_payload
    assert run_payload["status"] == "pass", run_payload
    assert Path(run_payload["html"]).is_file(), run_payload
    assert Path(run_payload["json"]).is_file(), run_payload
    run_sidecar = json.loads(Path(run_payload["json"]).read_text(encoding="utf-8"))
    assert run_sidecar["schema_version"] == "oag_run_frame.v1", run_sidecar
    assert len(run_sidecar["next_actions"]) == 4, run_sidecar
    assert sum(1 for action in run_sidecar["next_actions"] if action.get("recommended")) == 1, run_sidecar
    assert run_sidecar["action_plan"]["candidate_count"] >= 1, run_sidecar
    assert run_sidecar["action_plan"]["mission_instance_id"], run_sidecar
    assert run_sidecar["action_plan"]["action_graph_path"], run_sidecar
    assert run_payload["recommended_action"]["id"] in {action["id"] for action in run_sidecar["next_actions"]}, run_payload

    action_start = run_oag_action_record("start", ip, "--candidate-id", "recommended", "--selected-reason", "smoke selected the recommended run-frame action", "--json")
    assert action_start.returncode == 0, action_start.stderr or action_start.stdout
    action_start_payload = json.loads(action_start.stdout)
    assert action_start_payload["status"] == "pass", action_start_payload
    assert action_start_payload["mission_instance_id"], action_start_payload
    action_update = run_oag_action_record(
        "update",
        ip,
        "--action-id",
        action_start_payload["action_id"],
        "--status",
        "accepted",
        "--summary",
        "smoke accepted action instance",
        "--auto-link-active-wavefront",
        "--deep-interview-round",
        "req/deep_interview_rounds/smoke.json",
        "--git-checkpoint",
        "--checkpoint-message",
        "OAG smoke action checkpoint",
        "--json",
    )
    assert action_update.returncode == 0, action_update.stderr or action_update.stdout
    action_update_payload = json.loads(action_update.stdout)
    assert action_update_payload["git_checkpoint"]["status"] == "pass", action_update_payload
    action_list = run_oag_action_record("list", ip, "--json")
    assert action_list.returncode == 0, action_list.stderr or action_list.stdout
    action_index = json.loads(action_list.stdout)["index"]
    assert action_index["counts"]["total"] >= 1 and action_index["counts"]["terminal"] >= 1, action_index

    mission_show_after = run_oag_mission_runtime("show", ip, "--mission-id", action_start_payload["mission_instance_id"], "--json")
    assert mission_show_after.returncode == 0, mission_show_after.stderr or mission_show_after.stdout
    mission_after_payload = json.loads(mission_show_after.stdout)
    assert action_start_payload["action_id"] in mission_after_payload["mission"]["action_instance_refs"], mission_after_payload

    operation_frame = run_oag_operation_review_frame(ip, "--json")
    assert operation_frame.returncode == 0, operation_frame.stderr or operation_frame.stdout
    operation_payload = json.loads(operation_frame.stdout)
    assert operation_payload["schema_version"] == "oag_operation_review_frame_result.v1", operation_payload
    assert Path(operation_payload["html"]).is_file(), operation_payload
    operation_sidecar = json.loads(Path(operation_payload["json"]).read_text(encoding="utf-8"))
    assert operation_sidecar["schema_version"] == "oag_operation_review_frame.v1", operation_sidecar
    assert operation_sidecar["current_mission"]["id"], operation_sidecar
    assert operation_sidecar["action_history"], operation_sidecar
    operation_html = Path(operation_payload["html"]).read_text(encoding="utf-8")
    assert "OAG Operation Review Frame" in operation_html, operation_html
    assert "Action Graph Nodes" in operation_html, operation_html
    assert "Wavefront Draft" in operation_html, operation_html
    assert "Role Health" in operation_html, operation_html
    assert "Mission Completion Criteria" in operation_html, operation_html
    assert operation_sidecar["wavefront_draft"]["summary"]["task_count"] >= 1, operation_sidecar
    assert operation_sidecar["role_health"]["summary"]["hazard_count"] == 0, operation_sidecar
    assert operation_sidecar["mission_completion"]["criteria"], operation_sidecar

    wavefront_draft = run_oag_action_wavefront_draft(ip, "--json")
    assert wavefront_draft.returncode == 0, wavefront_draft.stderr or wavefront_draft.stdout
    wavefront_payload = json.loads(wavefront_draft.stdout)
    assert wavefront_payload["status"] == "pass", wavefront_payload
    assert Path(ip / wavefront_payload["path"]).is_file(), wavefront_payload
    assert wavefront_payload["draft"]["summary"]["task_count"] >= 1, wavefront_payload
    assert all(task.get("may_claim_complete") is False for task in wavefront_payload["draft"]["tasks"]), wavefront_payload
    materialized_wavefront = run_oag_action_wavefront_draft(ip, "--no-refresh-plan", "--materialize-run-id", "ACTION_WAVEFRONT_SMOKE", "--barrier", "seed_ready", "--json")
    assert materialized_wavefront.returncode == 0, materialized_wavefront.stderr or materialized_wavefront.stdout
    materialized_payload = json.loads(materialized_wavefront.stdout)
    assert materialized_payload["status"] == "pass", materialized_payload
    assert materialized_payload["materialized"]["plan"]["status"] == "pass", materialized_payload
    assert Path(ip / materialized_payload["materialized"]["template_path"]).is_file(), materialized_payload
    assert (ip / "ontology" / "runs" / "ACTION_WAVEFRONT_SMOKE" / "wavefront_task_graph.json").is_file(), materialized_payload

    clean_health = run_oag_role_health(ip, "--json")
    assert clean_health.returncode == 0, clean_health.stderr or clean_health.stdout
    clean_health_payload = json.loads(clean_health.stdout)
    assert clean_health_payload["status"] == "pass", clean_health_payload
    assert Path(ip / clean_health_payload["path"]).is_file(), clean_health_payload
    assert clean_health_payload["role_health"]["summary"]["hazard_count"] == 0, clean_health_payload

    stuck_start = run_oag_action_record(
        "start",
        ip,
        "--candidate-id",
        "recommended",
        "--selected-reason",
        "smoke stuck action injection",
        "--json",
    )
    assert stuck_start.returncode == 0, stuck_start.stderr or stuck_start.stdout
    stuck_payload = json.loads(stuck_start.stdout)
    stuck_path = ip / stuck_payload["path"]
    stuck_doc = json.loads(stuck_path.read_text(encoding="utf-8"))
    stuck_doc["status"] = "running"
    stuck_doc["started_at"] = "2000-01-01T00:00:00Z"
    stuck_path.write_text(json.dumps(stuck_doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    stuck_health = run_oag_role_health(ip, "--stuck-seconds", "1", "--json")
    assert stuck_health.returncode == 0, stuck_health.stderr or stuck_health.stdout
    stuck_health_payload = json.loads(stuck_health.stdout)
    assert stuck_health_payload["role_health"]["summary"]["hazard_count"] >= 1, stuck_health_payload
    assert any(item["code"] == "ROLE_STUCK" for item in stuck_health_payload["role_health"]["hazards"]), stuck_health_payload

    recovery_plan = run_oag_action_plan(ip, "--quick", "--stuck-seconds", "1", "--json")
    assert recovery_plan.returncode == 0, recovery_plan.stderr or recovery_plan.stdout
    recovery_payload = json.loads(recovery_plan.stdout)
    assert recovery_payload["recommended_action"]["action_type"] == "ACT_ORCHESTRATION_RECOVERY", recovery_payload
    assert any(item["code"] == "ROLE_HEALTH_HAZARD" for item in recovery_payload["plan"]["open_items"]), recovery_payload

    stuck_abort = run_oag_action_record(
        "update",
        ip,
        "--action-id",
        stuck_payload["action_id"],
        "--status",
        "aborted",
        "--summary",
        "smoke recovered stuck action",
        "--json",
    )
    assert stuck_abort.returncode == 0, stuck_abort.stderr or stuck_abort.stdout

    mission_eval = run_oag_mission_runtime("evaluate", ip, "--mission-id", "active", "--json")
    assert mission_eval.returncode == 0, mission_eval.stderr or mission_eval.stdout
    mission_eval_payload = json.loads(mission_eval.stdout)
    assert mission_eval_payload["status"] == "pass", mission_eval_payload
    assert mission_eval_payload["evaluation"]["criteria"], mission_eval_payload

    review_frame = run_oag_review_frame(ip, "--mode", "pre-dispatch", "--readiness-mode", "draft", "--json")
    assert review_frame.returncode == 0, review_frame.stderr or review_frame.stdout
    review_payload = json.loads(review_frame.stdout)
    assert review_payload["schema_version"] == "oag_review_frame_result.v1", review_payload
    assert review_payload["frame_mode"] == "pre-dispatch", review_payload
    review_html = Path(review_payload["html"]).read_text(encoding="utf-8")
    assert "OAG Pre-Dispatch Review Frame" in review_html, review_html
    assert "verbatim" in review_html.lower(), review_html

    planning_ssot = run_oag_ssot_section_check(ip, "--stage", "planning", "--json")
    assert planning_ssot.returncode == 0, planning_ssot.stderr or planning_ssot.stdout
    planning_payload = json.loads(planning_ssot.stdout)
    assert planning_payload["status"] == "pass", planning_payload
    closure_ssot = run_oag_ssot_section_check(ip, "--stage", "closure", "--json")
    assert closure_ssot.returncode != 0, closure_ssot.stdout
    closure_payload = json.loads(closure_ssot.stdout)
    assert closure_payload["status"] == "fail", closure_payload
    assert any(item["code"] == "SSOT_GATE_DECISION_MISSING" for item in closure_payload["issues"]), closure_payload

    gate_create = run_oag_gate_frame(
        "create",
        "--ip-dir",
        str(ip),
        "--stage",
        "deep-interview",
        "--kind",
        "question",
        "--prompt",
        "Which implementation boundary should the smoke IP use?",
        "--option",
        "recommended|Recommended boundary|Use the smallest concrete RTL-ready scope.",
        "--option",
        "narrow|Narrow boundary|Reduce scope until all implementation-facing details are explicit.",
        "--option",
        "defer|Defer boundary|Keep the decision visible and block dispatch.",
        "--option",
        "custom|Other / custom|User supplies the exact correction.",
        "--json",
    )
    assert gate_create.returncode == 0, gate_create.stderr or gate_create.stdout
    gate_payload = json.loads(gate_create.stdout)
    assert gate_payload["status"] == "pass", gate_payload
    gate_id = gate_payload["gate_id"]
    assert Path(gate_payload["gate_path"]).is_file(), gate_payload
    assert Path(gate_payload["markdown"]).is_file(), gate_payload

    gate_list = run_oag_gate_frame("list", "--ip-dir", str(ip), "--json")
    assert gate_list.returncode == 0, gate_list.stderr or gate_list.stdout
    gate_list_payload = json.loads(gate_list.stdout)
    assert gate_list_payload["pending_gate_count"] == 1, gate_list_payload
    gated_frame = run_oag_run_frame(ip, "--json")
    assert gated_frame.returncode == 0, gated_frame.stderr or gated_frame.stdout
    gated_payload = json.loads(gated_frame.stdout)
    assert gated_payload["run_status"] == "blocked", gated_payload
    assert gated_payload["recommended_action"]["action_type"] == "ACT_RESOLVE_PENDING_GATE", gated_payload

    gate_render = run_oag_gate_frame("render", "--ip-dir", str(ip), "--gate-id", gate_id, "--json")
    assert gate_render.returncode == 0, gate_render.stderr or gate_render.stdout
    assert "A. Recommended boundary (Recommended)" in json.loads(gate_render.stdout)["markdown"], gate_render.stdout
    gate_answer = run_oag_gate_frame("answer", "--ip-dir", str(ip), "--gate-id", gate_id, "--answer", "recommended", "--json")
    assert gate_answer.returncode == 0, gate_answer.stderr or gate_answer.stdout
    gate_answer_payload = json.loads(gate_answer.stdout)
    assert gate_answer_payload["status"] == "pass", gate_answer_payload
    resolved_list = run_oag_gate_frame("list", "--ip-dir", str(ip), "--json")
    assert resolved_list.returncode == 0, resolved_list.stderr or resolved_list.stdout
    resolved_payload = json.loads(resolved_list.stdout)
    assert resolved_payload["pending_gate_count"] == 0 and len(resolved_payload["resolved_gates"]) == 1, resolved_payload

    guard_clean = run_oag_orchestration_guard("audit", "--ip-dir", str(ip), "--json", project_root=project)
    assert guard_clean.returncode == 0, guard_clean.stderr or guard_clean.stdout
    assert json.loads(guard_clean.stdout)["status"] == "pass", guard_clean.stdout

    guard_template = project / "run_control_guard_template.json"
    guard_template.write_text(
        json.dumps(
            {
                        "schema_version": "oag_wavefront_template.v1",
                        "tasks": [
                            {
                                "task_id": "GATE_REVIEW_SMOKE",
                                "kind": "write",
                                "phase": "tb",
                        "depends_on": [],
                        "allowed_write_paths": ["tb/run_control_guard_smoke.sv"],
                        "ownership_mode": "exclusive_file",
                        "may_claim_complete": False,
                    }
                ],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    run_id = "RUN_CONTROL_GUARD_SMOKE"
    plan = run_wavefront("plan", "--ip-dir", str(ip), "--run-id", run_id, "--template", str(guard_template), "--json", project_root=project)
    assert plan.returncode == 0, plan.stderr or plan.stdout
    dispatch = run_dispatch(
        "create",
        "--ip-dir",
        str(ip),
        "--agent-type",
        "oag-gate-reviewer",
        "--stage",
        "tb",
        "--allowed-write-path",
        str(ip / "tb" / "run_control_guard_smoke.sv"),
        "--receipt-path",
        str(ip / "knowledge" / "subagents" / "GATE_REVIEW_SMOKE.json"),
        "--wavefront-run-id",
        run_id,
        "--task-id",
        "GATE_REVIEW_SMOKE",
        "--ownership-mode",
        "exclusive_file",
        "--json",
        project_root=project,
    )
    assert dispatch.returncode == 0, dispatch.stderr or dispatch.stdout
    dispatch_id = json.loads(dispatch.stdout)["dispatch"]["dispatch_id"]
    claim = run_wavefront(
        "claim",
        "--ip-dir",
        str(ip),
        "--run-id",
        run_id,
        "--task-id",
        "GATE_REVIEW_SMOKE",
        "--dispatch-id",
        dispatch_id,
        "--claimed-by",
        "smoke-guard",
        "--json",
        project_root=project,
    )
    assert claim.returncode == 0, claim.stderr or claim.stdout
    guard_locked = run_oag_orchestration_guard(
        "audit",
        "--ip-dir",
        str(ip),
        "--run-id",
        run_id,
        "--stale-seconds",
        "0",
        "--json",
        project_root=project,
    )
    assert guard_locked.returncode != 0, guard_locked.stdout
    guard_locked_payload = json.loads(guard_locked.stdout)
    assert any(item["code"] == "STALE_ACTIVE_LOCK" for item in guard_locked_payload["issues"]), guard_locked_payload
    assert any(item["code"] == "GATE_REVIEWER_STUCK" for item in guard_locked_payload["issues"]), guard_locked_payload
    recommendation_ids = {item["id"] for item in guard_locked_payload["recommendations"]}
    assert {"gate-reviewer-custom-fallback", "do-not-open-new-dispatch"} <= recommendation_ids, guard_locked_payload
    fallback = run_oag_orchestration_guard(
        "fallback-plan",
        "--ip-dir",
        str(ip),
        "--run-id",
        run_id,
        "--stale-seconds",
        "0",
        "--json",
        project_root=project,
    )
    assert fallback.returncode != 0, fallback.stdout
    fallback_payload = json.loads(fallback.stdout)
    assert fallback_payload["schema_version"] == "oag_gate_fallback_plan.v1", fallback_payload
    assert fallback_payload["summary"]["hung_gate_lock_count"] == 1, fallback_payload
    assert fallback_payload["fallback_actions"][0]["fallback_agent_type"] == "oag-custom-reviewer", fallback_payload
    assert (ip / fallback_payload["path"]).is_file(), fallback_payload

    abort = run_oag_orchestration_guard(
        "abort-task",
        "--ip-dir",
        str(ip),
        "--run-id",
        run_id,
        "--task-id",
        "GATE_REVIEW_SMOKE",
        "--status",
        "failed",
        "--json",
        project_root=project,
    )
    assert abort.returncode == 0, abort.stderr or abort.stdout
    abort_payload = json.loads(abort.stdout)
    assert abort_payload["status"] == "pass", abort_payload
    status = run_wavefront("status", "--ip-dir", str(ip), "--run-id", run_id, "--json", project_root=project)
    assert status.returncode == 0, status.stderr or status.stdout
    assert json.loads(status.stdout)["active_locks"] == [], status.stdout


def test_oag_decision_autonomy_policy(tmp_root: Path) -> None:
    ip = tmp_root / "decision_autonomy_ip"
    (ip / "ontology").mkdir(parents=True)
    matrix_path = ip / "ontology" / "decision_matrix.yaml"
    matrix_path.write_text(
        json.dumps(
            {
                "schema_version": "oag_decision_matrix.v1",
                "ip": ip.name,
                "decisions": [
                    {
                        "id": "D_FACT",
                        "question": "Which source fact applies?",
                        "status": "unresolved",
                        "lock_required": True,
                        "owner": "agent",
                        "decision_class": "fact",
                        "refs": ["doc/fact.txt"],
                    },
                    {
                        "id": "D_ARCH",
                        "question": "Which queue architecture wins the target envelope?",
                        "status": "unresolved",
                        "lock_required": True,
                        "owner": "agent",
                        "decision_class": "architecture_tradeoff",
                    },
                    {
                        "id": "D_PARAM",
                        "question": "Which timeout value should remain integrator-selectable?",
                        "status": "unresolved",
                        "lock_required": True,
                        "owner": "agent",
                        "decision_class": "parameterizable",
                    },
                    {
                        "id": "D_PRODUCT",
                        "question": "Which product-visible protocol mode is in scope?",
                        "status": "unresolved",
                        "lock_required": True,
                        "owner": "user",
                    },
                    {
                        "id": "D_MISSING_CLASS",
                        "question": "Which unclassified decision should fail closed?",
                        "status": "unresolved",
                        "lock_required": True,
                        "owner": "agent",
                    },
                ],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (ip / "doc").mkdir(exist_ok=True)
    (ip / "doc" / "fact.txt").write_text("fact source\n", encoding="utf-8")
    (ip / "ontology" / "mission_charter.yaml").write_text(
        json.dumps(
            {
                "schema_version": "oag_mission_charter.v1",
                "status": "approved",
                "approved": True,
                "approval": {"status": "approved", "approved": True, "actor": {"kind": "human", "id": "smoke-owner", "surface": "smoke"}},
                "question_batching": "checkpoint",
                "autonomy_grants": [
                    {
                        "id": "AUT_PARAMETER",
                        "decision_class": "parameterizable",
                        "granted": True,
                    },
                    {
                        "id": "AUT_ARCH_TRADEOFF",
                        "decision_class": "architecture_tradeoff",
                        "granted": True,
                    }
                ],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    spec = importlib.util.spec_from_file_location("oag_mission_loop_autonomy_smoke", MISSION_LOOP)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(ROOT / "scripts"))
    spec.loader.exec_module(module)

    fact_candidate = {"action_type": "ACT_RESOLVE_DECISION", "target_objects": {"decisions": ["D_FACT"]}}
    arch_candidate = {"action_type": "ACT_RESOLVE_DECISION", "target_objects": {"decisions": ["D_ARCH"]}}
    param_candidate = {"action_type": "ACT_RESOLVE_DECISION", "target_objects": {"decisions": ["D_PARAM"]}}
    product_candidate = {"action_type": "ACT_RESOLVE_DECISION", "target_objects": {"decisions": ["D_PRODUCT"]}}
    missing_class_candidate = {"action_type": "ACT_RESOLVE_DECISION", "target_objects": {"decisions": ["D_MISSING_CLASS"]}}

    assert module.classify_candidate(fact_candidate, ip) == ("auto_decide", "fact_decision_has_local_citation")
    assert module.classify_candidate(arch_candidate, ip) == ("route_dse", "measured_tradeoff_granted_requires_measurement")
    assert module.classify_candidate(param_candidate, ip) == ("auto_decide", "parameterizable_decision_promoted_to_parameter_policy")
    assert module.classify_candidate(product_candidate, ip) == ("defer_question", "product_defining_question_batched_to_checkpoint")
    assert module.classify_candidate(missing_class_candidate, ip) == ("defer_question", "product_defining_question_batched_to_checkpoint")

    autoresolve_spec = importlib.util.spec_from_file_location("oag_decision_autoresolve_smoke", ROOT / "scripts" / "oag_decision_autoresolve.py")
    assert autoresolve_spec and autoresolve_spec.loader
    oag_decision_autoresolve = importlib.util.module_from_spec(autoresolve_spec)
    autoresolve_spec.loader.exec_module(oag_decision_autoresolve)
    readiness_spec = importlib.util.spec_from_file_location("oag_lock_readiness_check_smoke", LOCK_READINESS_CHECK)
    assert readiness_spec and readiness_spec.loader
    oag_lock_readiness_check = importlib.util.module_from_spec(readiness_spec)
    readiness_spec.loader.exec_module(oag_lock_readiness_check)
    validate_spec = importlib.util.spec_from_file_location("oag_validate_json_smoke", VALIDATE_JSON)
    assert validate_spec and validate_spec.loader
    oag_validate_json = importlib.util.module_from_spec(validate_spec)
    validate_spec.loader.exec_module(oag_validate_json)

    missing_policy = oag_decision_autoresolve.resolve_candidate_policy(ip, missing_class_candidate)
    assert missing_policy["decision_class"] == "product_defining", missing_policy
    assert missing_policy["decision"] != "auto_decide", missing_policy

    receipt_dir = ip / "knowledge" / "decisions"
    receipt_dir.mkdir(parents=True, exist_ok=True)
    receipt_path = receipt_dir / "D_MISSING_CLASS.json"
    receipt_path.write_text(
        json.dumps(
            {
                "schema_version": "oag_agent_decision_receipt.v1",
                "id": "D_MISSING_CLASS",
                "decision_id": "D_MISSING_CLASS",
                "decision_class": "product_defining",
                "decision": "unsafe",
                "provisional": True,
                "evidence_refs": ["doc/fact.txt"],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    matrix = json.loads(matrix_path.read_text(encoding="utf-8"))
    missing_row = next(item for item in matrix["decisions"] if item["id"] == "D_MISSING_CLASS")
    missing_row.update(
        {
            "status": "decided",
            "decision": "unsafe",
            "decided_by": {"kind": "agent_with_charter", "id": "smoke"},
            "evidence_refs": ["doc/fact.txt"],
            "decision_receipt_ref": "knowledge/decisions/D_MISSING_CLASS.json",
        }
    )
    matrix_path.write_text(json.dumps(matrix, indent=2) + "\n", encoding="utf-8")
    readiness_issues, _, _ = oag_lock_readiness_check.check_decisions(ip, hard_gate=True)
    assert any(item["code"] == "DECISION_PRODUCT_AGENT" for item in readiness_issues), readiness_issues

    exploration_doc = {
        "schema_version": "oag_exploration_plan.v1",
        "status": "pass",
        "generated_at": "2026-01-01T00:00:00Z",
        "ip": ip.name,
        "ask_vs_explore": {
            "decision": "auto_decide",
            "reason": "fact_decision_has_local_citation",
            "question_required_now": False,
            "lock_critical": True,
            "decision_class": "fact",
            "decision_id": "D_FACT",
            "charter_grant_id": "",
            "evidence_plan": {"required": True, "available_refs": ["doc/fact.txt"]},
        },
        "input_fingerprint": {"sha256": "smoke"},
        "source_targets": [],
        "option_axes": [{"id": "FACT", "label": "Fact"}],
        "research_prompt": "No user question is required for a cited fact.",
        "issues": [],
    }
    assert oag_validate_json.schema_issues("oag_exploration_plan.schema.json", exploration_doc) == []

    no_charter = tmp_root / "decision_autonomy_no_charter_ip"
    (no_charter / "ontology").mkdir(parents=True)
    (no_charter / "ontology" / "decision_matrix.yaml").write_text(matrix_path.read_text(encoding="utf-8"), encoding="utf-8")
    assert module.classify_candidate(product_candidate, no_charter) == ("needs_user", "human_input_required")

    no_grant = tmp_root / "decision_autonomy_no_grant_ip"
    (no_grant / "ontology").mkdir(parents=True)
    (no_grant / "ontology" / "decision_matrix.yaml").write_text(matrix_path.read_text(encoding="utf-8"), encoding="utf-8")
    (no_grant / "ontology" / "mission_charter.yaml").write_text(
        json.dumps(
            {
                "schema_version": "oag_mission_charter.v1",
                "status": "approved",
                "approved": True,
                "approval": {"status": "approved", "approved": True, "actor": {"kind": "human", "id": "smoke-owner", "surface": "smoke"}},
                "question_batching": "checkpoint",
                "autonomy_grants": [],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    assert module.classify_candidate(param_candidate, no_grant) == ("needs_user", "human_input_required")


def test_oag_arch_exploration_blocker_regressions(tmp_root: Path) -> None:
    sweep_doc = tmp_root / "sweep.json"
    sweep_doc.write_text(
        json.dumps(
            {
                "parameter": "depth",
                "constraint": {"metric": "throughput", "objective": "max", "target": 100, "margin": 5},
                "candidate_values": [4, 8, 16],
                "metric_curve": [
                    {"value": 4, "metrics": {"throughput": 80}},
                    {"value": 8, "metrics": {"throughput": 96}},
                    {"value": 16, "metrics": {"throughput": 110}},
                ],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    sweep = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "oag_parameter_sweep.py"), "select", "--input", str(sweep_doc), "--json"],
        text=True,
        capture_output=True,
        check=False,
    )
    assert sweep.returncode == 0, sweep.stderr or sweep.stdout
    assert json.loads(sweep.stdout)["selected"]["value"] == 8.0

    min_sweep_doc = tmp_root / "sweep_min.json"
    min_sweep_doc.write_text(
        json.dumps(
            {
                "parameter": "depth",
                "constraint": {"metric": "latency", "objective": "min", "target": 10, "margin": 1},
                "candidate_values": [4, 8, 16],
                "metric_curve": [
                    {"value": 4, "metrics": {"latency": 12}},
                    {"value": 8, "metrics": {"latency": 11}},
                    {"value": 16, "metrics": {"latency": 8}},
                ],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    min_sweep = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "oag_parameter_sweep.py"), "select", "--input", str(min_sweep_doc), "--json"],
        text=True,
        capture_output=True,
        check=False,
    )
    assert min_sweep.returncode == 0, min_sweep.stderr or min_sweep.stdout
    assert json.loads(min_sweep.stdout)["selected"]["value"] == 8.0

    ip = tmp_root / "dse_prune_evidence_ip"
    ip.mkdir()
    subprocess.run(["git", "-C", str(ip), "init", "-q"], check=True)
    subprocess.run(["git", "-C", str(ip), "config", "user.email", "smoke@example.com"], check=True)
    subprocess.run(["git", "-C", str(ip), "config", "user.name", "Smoke"], check=True)
    (ip / "seed.txt").write_text("seed\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(ip), "add", "seed.txt"], check=True)
    subprocess.run(["git", "-C", str(ip), "commit", "-q", "-m", "seed"], check=True)
    evidence_dir = ip / "knowledge" / "arch_exploration" / "RUN1" / "CAND1"
    evidence_dir.mkdir(parents=True)
    evidence_file = evidence_dir / "bench_result.json"
    evidence_file.write_text('{"status":"pass"}\n', encoding="utf-8")
    subprocess.run(["git", "-C", str(ip), "branch", "oag/dse/M1/CAND1"], check=True)
    prune = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "oag_dse_worktree.py"),
            "prune",
            "--ip-dir",
            str(ip),
            "--run-id",
            "RUN1",
            "--candidate",
            "CAND1",
            "--mission",
            "M1",
            "--json",
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    assert prune.returncode == 0, prune.stderr or prune.stdout
    assert evidence_file.is_file()
    branches = subprocess.run(["git", "-C", str(ip), "branch", "--list", "oag/dse/*"], text=True, capture_output=True, check=True)
    assert branches.stdout.strip() == ""


def test_oag_arch_exploration_remaining_review_gates(tmp_root: Path) -> None:
    ip = tmp_root / "arch_remaining_gates_ip"
    (ip / "ontology").mkdir(parents=True)
    (ip / "knowledge" / "mission_loop").mkdir(parents=True)
    (ip / "ontology" / "mission_charter.yaml").write_text(
        json.dumps(
            {
                "schema_version": "oag_mission_charter.v1",
                "ip": ip.name,
                "status": "approved",
                "approved": True,
                "created_at": "2026-01-01T00:00:00Z",
                "updated_at": "2026-01-01T00:00:00Z",
                "actor": {"kind": "ai", "id": "smoke", "surface": "smoke"},
                "autonomy": {"question_batching": "checkpoint", "grants": [{"id": "G_ARCH", "decision_class": "architecture_tradeoff", "granted": True, "rationale": "smoke"}]},
                "approval": {"status": "approved", "approved": True, "actor": {"kind": "human", "id": "owner", "surface": "smoke"}},
                "objective_weights": {"throughput": 1.0},
                "constraints": {"required": ["pipeline"], "forbidden": ["huge"]},
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    matrix: dict[str, Any] = {
        "schema_version": "oag_decision_matrix.v1",
        "ip": ip.name,
        "decisions": [
            {
                "id": "D_ARCH",
                "question": "Which queue architecture?",
                "status": "unresolved",
                "lock_required": True,
                "owner": "agent",
                "decision_class": "architecture_tradeoff",
                "options": [
                    {"id": "pipeline_small", "label": "pipeline small", "metrics": {"throughput": 120}, "parameters": {"depth": 8}},
                    {"id": "simple_small", "label": "simple small", "metrics": {"throughput": 100}, "parameters": {"depth": 4}},
                    {"id": "huge_pipeline", "label": "huge pipeline", "metrics": {"throughput": 200}, "parameters": {"depth": 32}},
                ],
            }
        ],
    }
    matrix_path = ip / "ontology" / "decision_matrix.yaml"
    matrix_path.write_text(json.dumps(matrix, indent=2) + "\n", encoding="utf-8")
    gen = subprocess.run([sys.executable, str(ROOT / "scripts" / "oag_architecture_options.py"), "generate", "--ip-dir", str(ip), "--run-id", "RUNX", "--json"], text=True, capture_output=True, check=False)
    assert gen.returncode == 0, gen.stderr or gen.stdout
    estimate = subprocess.run([sys.executable, str(ROOT / "scripts" / "oag_architecture_options.py"), "estimate", "--ip-dir", str(ip), "--run-id", "RUNX", "--json"], text=True, capture_output=True, check=False)
    assert estimate.returncode == 0, estimate.stderr or estimate.stdout
    score = subprocess.run([sys.executable, str(ROOT / "scripts" / "oag_architecture_options.py"), "score", "--ip-dir", str(ip), "--run-id", "RUNX", "--json"], text=True, capture_output=True, check=False)
    assert score.returncode == 0, score.stderr or score.stdout
    rows = json.loads(score.stdout)["artifact"]["rows"]
    assert any(row["hard_constraint_pass"] is True for row in rows), rows
    assert any(row["hard_constraint_pass"] is False and "required constraint missing: pipeline" in row["constraint_issues"] for row in rows), rows

    bench = subprocess.run([sys.executable, str(ROOT / "scripts" / "oag_arch_bench.py"), "run", "--ip-dir", str(ip), "--run-id", "RUNX", "--candidate", "CAND_001", "--json"], text=True, capture_output=True, check=False)
    assert bench.returncode == 0, bench.stderr or bench.stdout
    bench_artifact = json.loads(bench.stdout)["artifact"]
    assert bench_artifact["evidence_tier"] == "tier2_probe", bench_artifact
    assert "exploration_comparison" in bench_artifact["valid_for"], bench_artifact
    assert "scope_lock" in bench_artifact["not_valid_for"], bench_artifact
    assert all(path.startswith("knowledge/arch_exploration/") for path in bench_artifact["generated_artifacts"]), bench_artifact
    assert (ip / "knowledge" / "arch_exploration" / "RUNX" / "CAND_001" / "generated" / "CAND_001_skeleton.v").is_file()
    bad_bench = subprocess.run([sys.executable, str(ROOT / "scripts" / "oag_arch_bench.py"), "run", "--ip-dir", str(ip), "--run-id", "RUNX", "--candidate", "../rtl", "--json"], text=True, capture_output=True, check=False)
    assert bad_bench.returncode != 0, bad_bench.stdout
    assert not (ip / "rtl").exists()
    missing_provenance_sweep = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "oag_arch_bench.py"),
            "sweep",
            "--ip-dir",
            str(ip),
            "--run-id",
            "RUNX",
            "--candidate",
            "CAND_001",
            "--parameter",
            "depth",
            "--metric",
            "throughput",
            "--objective",
            "max",
            "--target",
            "100",
            "--candidate-value",
            "4",
            "--metric-point",
            "4=80",
            "--json",
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    assert missing_provenance_sweep.returncode != 0, missing_provenance_sweep.stdout
    missing_provenance_payload = json.loads(missing_provenance_sweep.stdout)
    assert any(item["code"] == "SWEEP_POINT_PROVENANCE_MISSING" for item in missing_provenance_payload["issues"]), missing_provenance_payload
    missing_input_sweep_path = ip / "missing_input_sweep.json"
    missing_input_sweep_path.write_text(
        json.dumps(
            {
                "parameter": "depth",
                "constraint": {"metric": "throughput", "objective": "max", "target": 100, "margin": 5},
                "candidate_values": [4, 8],
                "metric_curve": [{"value": 4, "metrics": {"throughput": 80}}, {"value": 8, "metrics": {"throughput": 100}}],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    missing_input_sweep = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "oag_arch_bench.py"),
            "sweep",
            "--ip-dir",
            str(ip),
            "--run-id",
            "RUNX",
            "--candidate",
            "CAND_001",
            "--input",
            str(missing_input_sweep_path),
            "--json",
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    assert missing_input_sweep.returncode != 0, missing_input_sweep.stdout
    missing_input_payload = json.loads(missing_input_sweep.stdout)
    assert any(item["code"] == "SWEEP_POINT_PROVENANCE_MISSING" for item in missing_input_payload["issues"]), missing_input_payload
    bench_ref = "knowledge/arch_exploration/RUNX/CAND_001/bench_result.json"
    bench_hash = sha256(ip / bench_ref)
    sweep = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "oag_arch_bench.py"),
            "sweep",
            "--ip-dir",
            str(ip),
            "--run-id",
            "RUNX",
            "--candidate",
            "CAND_001",
            "--parameter",
            "depth",
            "--metric",
            "throughput",
            "--objective",
            "max",
            "--target",
            "100",
            "--margin",
            "5",
            "--candidate-value",
            "4",
            "--candidate-value",
            "8",
            "--candidate-value",
            "16",
            "--metric-point",
            f"4=80@{bench_ref}#sha256:{bench_hash}",
            "--metric-point",
            f"8=96@{bench_ref}#sha256:{bench_hash}",
            "--metric-point",
            f"16=110@{bench_ref}#sha256:{bench_hash}",
            "--json",
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    assert sweep.returncode == 0, sweep.stderr or sweep.stdout
    sweep_artifact = json.loads(sweep.stdout)["artifact"]
    assert sweep_artifact["selected"]["value"] == 8.0
    assert sweep_artifact["evidence_tier"] == "tier2_probe", sweep_artifact
    assert "scope_lock" in sweep_artifact["not_valid_for"], sweep_artifact
    assert (ip / "knowledge" / "arch_exploration" / "RUNX" / "CAND_001" / "parameter_sweep_depth.json").is_file()

    candidates_path = ip / "knowledge" / "arch_exploration" / "RUNX" / "candidates.json"
    candidates_doc = json.loads(candidates_path.read_text(encoding="utf-8"))
    for candidate in candidates_doc["candidates"]:
        if candidate["id"] == "CAND_001":
            candidate["parameter_draft"] = {"depth": {"value": 8, "public": True}}
            candidate["generate_options"] = [
                {
                    "id": "GEN_PIPE",
                    "retain": True,
                    "decision_ref": "D_ARCH",
                    "configuration_model_entry": "CFG_PIPE",
                    "verification_plan_config_mapping": "CFG_UNKNOWN",
                }
            ]
    candidates_path.write_text(json.dumps(candidates_doc, indent=2) + "\n", encoding="utf-8")
    raw_sweep_ref = "knowledge/arch_exploration/RUNX/CAND_001/parameter_sweep_depth.json"
    promoted_sweep_ref = "knowledge/views/promoted/arch/RUNX/CAND_001/parameter_sweep_depth.json"
    receipt_path = ip / "knowledge" / "decisions" / "D_PARAM.json"
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    receipt_path.write_text(
        json.dumps(
            {
                "schema_version": "oag_agent_decision_receipt.v1",
                "decision_id": "D_PARAM",
                "decision_class": "parameterizable",
                "autonomy_class": "reversible_internal",
                "candidate_set": ["CAND_001"],
                "bench_command": "oag_arch_bench.py sweep --candidate CAND_001 --parameter depth",
                "metrics": {"throughput": 96.0},
                "comparison": "depth sweep selected the smallest satisfying value",
                "selection_rule": "smallest_satisfying_with_margin",
                "artifact_paths": [raw_sweep_ref],
                "rollback_path": "knowledge/arch_exploration/RUNX",
                "evidence_refs": [raw_sweep_ref],
                "evidence_required": [raw_sweep_ref],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    matrix["decisions"].append(
        {
            "id": "D_PARAM",
            "question": "Public depth parameter?",
            "status": "decided",
            "lock_required": True,
            "owner": "agent",
            "decision_class": "parameterizable",
            "representation": "parameter",
            "external_contract_impact": "indirect",
            "provisional": True,
            "decision": 8,
            "autonomy_class": "reversible_internal",
            "decided_by": {"kind": "agent_with_charter", "id": "smoke"},
            "evidence_refs": [raw_sweep_ref],
            "evidence_required": [raw_sweep_ref],
            "decision_receipt_ref": "knowledge/decisions/D_PARAM.json",
        }
    )
    matrix_path.write_text(json.dumps(matrix, indent=2) + "\n", encoding="utf-8")
    cleanup_before_promote = subprocess.run([sys.executable, str(ROOT / "scripts" / "oag_exploration_cleanup_check.py"), "--ip-dir", str(ip), "--json"], text=True, capture_output=True, check=False)
    assert cleanup_before_promote.returncode != 0, cleanup_before_promote.stdout
    cleanup_before_codes = {item["code"] for item in json.loads(cleanup_before_promote.stdout)["issues"]}
    assert "PRODUCT_ARCH_EXPLORATION_REFERENCE" in cleanup_before_codes, cleanup_before_codes
    promote = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "oag_architecture_options.py"),
            "promote",
            "--ip-dir",
            str(ip),
            "--run-id",
            "RUNX",
            "--candidate",
            "CAND_001",
            "--json",
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    assert promote.returncode == 0, promote.stderr or promote.stdout
    promote_result = json.loads(promote.stdout)
    assert promote_result["artifact"]["candidate_id"] == "CAND_001", promote_result
    assert (ip / promoted_sweep_ref).is_file()
    assert (ip / "knowledge" / "views" / "promoted" / "arch" / "RUNX" / "CAND_001" / "structure_draft.json").is_file()
    assert (ip / "knowledge" / "views" / "promoted" / "arch" / "RUNX" / "CAND_001" / "parameter_decision_draft.json").is_file()
    candidates_after_promote = json.loads(candidates_path.read_text(encoding="utf-8"))
    selected_rows = [item for item in candidates_after_promote["candidates"] if item.get("status") == "selected"]
    assert [item["id"] for item in selected_rows] == ["CAND_001"], candidates_after_promote
    assert all(item.get("status") in {"selected", "pruned"} for item in candidates_after_promote["candidates"]), candidates_after_promote
    import yaml  # type: ignore

    matrix_after_promote = yaml.safe_load(matrix_path.read_text(encoding="utf-8"))
    d_param = next(item for item in matrix_after_promote["decisions"] if item["id"] == "D_PARAM")
    assert d_param["evidence_refs"] == [promoted_sweep_ref], d_param
    assert d_param["evidence_required"] == [promoted_sweep_ref], d_param
    promoted_receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert promoted_receipt["evidence_refs"] == [promoted_sweep_ref], promoted_receipt
    assert promoted_receipt["evidence_required"] == [promoted_sweep_ref], promoted_receipt
    assert raw_sweep_ref in promoted_receipt["promotion"]["original_exploration_refs"], promoted_receipt
    (ip / "knowledge" / "mission_loop" / "pending_questions.json").write_text(
        json.dumps({"schema_version": "oag_pending_questions.v1", "ip": ip.name, "status": "checkpoint_ready", "created_at": "x", "updated_at": "x", "questions": []}) + "\n",
        encoding="utf-8",
    )
    (ip / "ontology" / "verification_plan.yaml").write_text(json.dumps({"schema_version": "oag_verification_plan.v1", "ip": ip.name, "verification_configurations": [{"id": "CFG_PIPE"}], "verification_objectives": []}) + "\n", encoding="utf-8")
    cleanup = subprocess.run([sys.executable, str(ROOT / "scripts" / "oag_exploration_cleanup_check.py"), "--ip-dir", str(ip), "--json"], text=True, capture_output=True, check=False)
    assert cleanup.returncode != 0, cleanup.stdout
    cleanup_codes = {item["code"] for item in json.loads(cleanup.stdout)["issues"]}
    assert "PRODUCT_ARCH_EXPLORATION_REFERENCE" not in cleanup_codes, cleanup_codes
    assert "PUBLIC_PARAMETER_RATIONALE_MISSING" in cleanup_codes, cleanup_codes
    assert "PROVISIONAL_DECISION_REMAINS" in cleanup_codes, cleanup_codes
    assert "GENERATE_OPTION_VERIFICATION_MAPPING_UNKNOWN" in cleanup_codes, cleanup_codes

    pending_spec = importlib.util.spec_from_file_location("oag_pending_questions_smoke", ROOT / "scripts" / "oag_pending_questions.py")
    assert pending_spec and pending_spec.loader
    oag_pending_questions = importlib.util.module_from_spec(pending_spec)
    pending_spec.loader.exec_module(oag_pending_questions)
    mismatch_ip = tmp_root / "pending_schema_mismatch_ip"
    (mismatch_ip / "knowledge" / "mission_loop").mkdir(parents=True)
    (mismatch_ip / "knowledge" / "mission_loop" / "pending_questions.json").write_text(
        json.dumps(
            {
                "schema_version": "old_schema",
                "ip": mismatch_ip.name,
                "status": "active",
                "created_at": "x",
                "updated_at": "x",
                "questions": [{"id": "PQ_0001", "status": "pending", "candidate_selector": "decision:D1"}],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    pending_summary = oag_pending_questions.summary(mismatch_ip)
    assert pending_summary["ready"] is True, pending_summary
    assert pending_summary["question_count"] == 1, pending_summary
    assert pending_summary["checkpoint_reason"] == "pending_questions_schema_mismatch", pending_summary

    readiness_spec = importlib.util.spec_from_file_location("oag_lock_readiness_agent_receipt_smoke", LOCK_READINESS_CHECK)
    assert readiness_spec and readiness_spec.loader
    oag_lock_readiness_check = importlib.util.module_from_spec(readiness_spec)
    readiness_spec.loader.exec_module(oag_lock_readiness_check)
    receipt_ip = tmp_root / "agent_receipt_required_ip"
    (receipt_ip / "ontology").mkdir(parents=True)
    (receipt_ip / "ontology" / "decision_matrix.yaml").write_text(
        json.dumps(
            {
                "schema_version": "oag_decision_matrix.v1",
                "ip": receipt_ip.name,
                "decisions": [
                    {
                        "id": "D_AGENT",
                        "question": "Agent evidence final decision?",
                        "status": "decided",
                        "lock_required": True,
                        "owner": "agent",
                        "decision_class": "architecture_tradeoff",
                        "autonomy_class": "measured_tradeoff",
                        "decision": "x",
                        "provisional": False,
                        "decided_by": {"kind": "agent_with_evidence", "id": "smoke"},
                    }
                ],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    readiness_issues, _, _ = oag_lock_readiness_check.check_decisions(receipt_ip, hard_gate=True)
    assert any(item["code"] == "DECISION_EVIDENCE_REFS" for item in readiness_issues), readiness_issues
    assert any(item["code"] == "DECISION_RECEIPT_REF" for item in readiness_issues), readiness_issues

    bypass_ip = tmp_root / "agent_decided_by_bypass_ip"
    (bypass_ip / "ontology").mkdir(parents=True)
    (bypass_ip / "ontology" / "decision_matrix.yaml").write_text(
        json.dumps(
            {
                "schema_version": "oag_decision_matrix.v1",
                "ip": bypass_ip.name,
                "decisions": [
                    {
                        "id": "D_AGENT_BYPASS",
                        "question": "Can an agent-owned row omit decided_by?",
                        "status": "decided",
                        "lock_required": True,
                        "owner": "agent",
                        "decision_class": "product_defining",
                        "decision": "unsafe",
                    }
                ],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    bypass_issues, _, _ = oag_lock_readiness_check.check_decisions(bypass_ip, hard_gate=True)
    assert any(item["code"] == "DECISION_AGENT_DECIDED_BY" for item in bypass_issues), bypass_issues
    assert any(item["code"] == "DECISION_PRODUCT_AGENT" for item in bypass_issues), bypass_issues

    tier2_ip = tmp_root / "tier2_only_evidence_ip"
    tier2_evidence = tier2_ip / "knowledge" / "arch_exploration" / "RUN_LOCK" / "CAND_LOCK" / "bench_result.json"
    tier2_receipt = tier2_ip / "knowledge" / "decisions" / "D_TIER2.json"
    tier2_evidence.parent.mkdir(parents=True)
    tier2_receipt.parent.mkdir(parents=True)
    (tier2_ip / "ontology").mkdir(parents=True)
    tier2_evidence.write_text(
        json.dumps(
            {
                "schema_version": "oag_arch_bench_result.v1",
                "status": "pass",
                "ip": tier2_ip.name,
                "run_id": "RUN_LOCK",
                "candidate_id": "CAND_LOCK",
                "candidate_ref": "knowledge/arch_exploration/RUN_LOCK/CAND_LOCK",
                "result_ref": "knowledge/arch_exploration/RUN_LOCK/CAND_LOCK/bench_result.json",
                "evidence_tier": "tier2_probe",
                "valid_for": ["exploration_comparison"],
                "not_valid_for": ["scope_lock", "product_rtl_claim", "external_contract_claim", "product_defining_claim"],
                "measurement_kind": "adapter_probe",
                "adapter_status": {},
                "probes": {},
                "metrics": {},
                "generated_artifacts": ["knowledge/arch_exploration/RUN_LOCK/CAND_LOCK/generated/CAND_LOCK_skeleton.v"],
                "issues": [],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    tier2_receipt.write_text(
        json.dumps(
            {
                "schema_version": "oag_agent_decision_receipt.v1",
                "decision_id": "D_TIER2",
                "decision_class": "architecture_tradeoff",
                "autonomy_class": "measured_tradeoff",
                "candidate_set": ["CAND_LOCK"],
                "bench_command": "smoke",
                "metrics": {},
                "comparison": {},
                "selection_rule": "smoke",
                "artifact_paths": ["knowledge/arch_exploration/RUN_LOCK/CAND_LOCK/bench_result.json"],
                "rollback_path": "git:smoke",
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (tier2_ip / "ontology" / "decision_matrix.yaml").write_text(
        json.dumps(
            {
                "schema_version": "oag_decision_matrix.v1",
                "ip": tier2_ip.name,
                "decisions": [
                    {
                        "id": "D_TIER2",
                        "question": "Can Tier-2-only evidence lock an architecture?",
                        "status": "decided",
                        "lock_required": True,
                        "owner": "agent",
                        "decision_class": "architecture_tradeoff",
                        "autonomy_class": "measured_tradeoff",
                        "decision": "CAND_LOCK",
                        "provisional": False,
                        "decided_by": {"kind": "agent_with_evidence", "id": "smoke"},
                        "evidence_refs": ["knowledge/arch_exploration/RUN_LOCK/CAND_LOCK/bench_result.json"],
                        "decision_receipt_ref": "knowledge/decisions/D_TIER2.json",
                    }
                ],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    tier2_issues, _, _ = oag_lock_readiness_check.check_decisions(tier2_ip, hard_gate=True)
    assert any(item["code"] == "DECISION_TIER2_ONLY_EVIDENCE" for item in tier2_issues), tier2_issues


def test_deep_interview_handoff_persists_decision_rows(tmp_root: Path) -> None:
    ip = make_ip(tmp_root / "deep_interview_handoff")
    round_doc = {
        "schema_version": "oag_deep_interview_round.v1",
        "round": 7,
        "component": "control-boundary",
        "dimension": "rtl_readiness",
        "question": "Which control boundary should be locked for RTL dispatch?",
        "source_refs": ["req/source_claims.yaml#seed"],
        "options": [
            {
                "id": "A",
                "label": "Ready single-cycle control",
                "description": "Lock the single-cycle externally visible control response.",
                "recommended": True,
                "decision_matrix_ref": "DEC_SMOKE_CONTROL_BOUNDARY",
                "affects": ["rtl", "tb", "evidence"],
            },
            {
                "id": "B",
                "label": "Add handshake detail",
                "description": "Continue the interview before lock.",
                "recommended": False,
            },
            {
                "id": "C",
                "label": "Defer control boundary",
                "description": "Keep dispatch blocked.",
                "recommended": False,
            },
            {
                "id": "D",
                "label": "Other / custom",
                "description": "User supplies the exact correction.",
                "recommended": False,
            },
        ],
    }
    round_path = ip / "req" / "deep_semantic_intake" / "round_7.json"
    round_path.write_text(json.dumps(round_doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    handoff = subprocess.run(
        [
            sys.executable,
            str(DEEP_INTERVIEW_ROUND),
            "handoff",
            "--ip-dir",
            str(ip),
            "--json-file",
            str(round_path),
            "--selected-option",
            "A",
            "--confirmed",
            "--write-decision-matrix",
            "--write-source-claim",
            "--refresh-action-plan",
            "--render-operation-frame",
        ],
        text=True,
        capture_output=True,
        check=False,
        cwd=ROOT,
    )
    assert handoff.returncode == 0, handoff.stderr or handoff.stdout
    payload = json.loads(handoff.stdout)
    assert payload["schema_version"] == "oag_deep_interview_handoff_result.v1", payload
    assert payload["status"] == "pass", payload
    assert payload["decision_matrix_ref"] == "DEC_SMOKE_CONTROL_BOUNDARY", payload
    assert payload["action_plan"]["status"] == "pass", payload
    assert payload["action_plan"]["mission_instance_id"], payload
    assert payload["operation_frame"]["status"] == "pass", payload
    assert Path(payload["handoff_path"]).is_file(), payload
    assert Path(payload["operation_frame"]["html"]).is_file(), payload
    handoff_doc = json.loads(Path(payload["handoff_path"]).read_text(encoding="utf-8"))
    assert handoff_doc["action_plan_ref"]["mission_instance_id"] == payload["action_plan"]["mission_instance_id"], handoff_doc
    assert handoff_doc["operation_frame_ref"]["html"] == payload["operation_frame"]["html"], handoff_doc
    decision_text = (ip / "ontology" / "decision_matrix.yaml").read_text(encoding="utf-8")
    assert "DEC_SMOKE_CONTROL_BOUNDARY" in decision_text, decision_text
    assert "status: decided" in decision_text, decision_text
    assert "Ready single-cycle control" in decision_text, decision_text
    claims_text = (ip / "req" / "source_claims.yaml").read_text(encoding="utf-8")
    assert "Ready single-cycle control" in claims_text, claims_text
    assert "source_type: user_interview" in claims_text, claims_text


def test_pyslang_lint_runner() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        ip = Path(tmp) / "lint_ip"
        (ip / "rtl").mkdir(parents=True)
        (ip / "list").mkdir()
        (ip / "rtl" / "demo.sv").write_text(
            "\n".join(
                [
                    "module demo(input logic clk, output logic done);",
                    "  assign done = clk;",
                    "endmodule",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        (ip / "list" / "rtl.f").write_text("+incdir+rtl\nrtl/*.sv\n", encoding="utf-8")
        (ip / "list" / "lint.f").write_text("-f list/rtl.f\n", encoding="utf-8")
        proc = subprocess.run(
            [
                sys.executable,
                str(PYSLANG_LINT),
                "--ip-dir",
                str(ip),
                "--filelist",
                "list/lint.f",
                "--out",
                "lint/dut_lint.json",
                "--allow-missing",
                "--json",
            ],
            text=True,
            capture_output=True,
            check=False,
            cwd=ROOT,
        )
        assert proc.returncode == 0, proc.stderr or proc.stdout
        result = json.loads((ip / "lint" / "dut_lint.json").read_text(encoding="utf-8"))
        assert result["status"] in {"pass", "skipped"}, result
        assert result["tool"] == "pyslang", result
        assert result["files"] == ["rtl/demo.sv"], result


def test_rtl_role_wavefront_template(tmp_root: Path) -> None:
    project = tmp_root / "rtl_wavefront_project"
    project.mkdir(parents=True)
    ip = project / "rtl_wave_ip"
    ip.mkdir()
    run_id = "RUN_RTL_ROLE_SMOKE"

    def claim_wavefront_task(task_id: str, *, ownership_mode: str = "exclusive_file") -> None:
        dispatch_id = ""
        graph = json.loads((ip / "ontology" / "runs" / run_id / "wavefront_task_graph.json").read_text(encoding="utf-8"))
        task = next(item for item in graph["tasks"] if item["task_id"] == task_id)
        assert task["ownership_mode"] == ownership_mode, task
        if ownership_mode != "none":
            dispatch_id = write_wavefront_claim_dispatch(project, ip, run_id, task)

        claim_args = [
            "claim",
            "--ip-dir",
            str(ip),
            "--run-id",
            run_id,
            "--task-id",
            task_id,
            "--claimed-by",
            f"smoke-{task_id.lower()}",
            "--json",
        ]
        if dispatch_id:
            claim_args.extend(["--dispatch-id", dispatch_id])
        claim = run_wavefront(*claim_args, project_root=project)
        assert claim.returncode == 0, claim.stderr or claim.stdout

    def approve_wavefront_task(task_id: str, *barrier_outputs: str) -> None:
        review_pending = run_wavefront(
            "record",
            "--ip-dir",
            str(ip),
            "--run-id",
            run_id,
            "--task-id",
            task_id,
            "--status",
            "review_pending",
            "--receipt",
            str(ip / "knowledge" / "subagents" / f"{task_id.lower()}_receipt.json"),
            "--json",
            project_root=project,
        )
        assert review_pending.returncode == 0, review_pending.stderr or review_pending.stdout
        decision_args = [
            "record",
            "--ip-dir",
            str(ip),
            "--run-id",
            run_id,
            "--task-id",
            task_id,
            "--decision-id",
            f"DEC_{task_id}_RTL_ROLE_SMOKE",
            "--decision-type",
            "custom_review",
            "--verdict",
            "approved",
            "--summary",
            f"{task_id} RTL role handoff reviewed by smoke test.",
            "--checked-against",
            f"{ip}/ontology/runs/{run_id}/wavefront_task_graph.json#{task_id}",
            "--preserved",
            "declared RTL role barrier semantics",
            "--json",
        ]
        for token in barrier_outputs:
            decision_args.extend(["--barrier-output", token])
        decision = run_decision_harness(*decision_args, project_root=project)
        assert decision.returncode == 0, decision.stderr or decision.stdout
        decision_path = json.loads(decision.stdout)["path"]
        handoff_args = [
            "record",
            "--ip-dir",
            str(ip),
            "--run-id",
            run_id,
            "--task-id",
            task_id,
            "--status",
            "handoff_pass",
            "--decision",
            decision_path,
            "--json",
        ]
        for token in barrier_outputs:
            handoff_args.extend(["--barrier-output", token])
        handoff = run_wavefront(*handoff_args, project_root=project)
        assert handoff.returncode == 0, handoff.stderr or handoff.stdout

    plan = run_wavefront(
        "plan",
        "--ip-dir",
        str(ip),
        "--run-id",
        run_id,
        "--template",
        str(OAG_RTL_WAVEFRONT_TEMPLATE),
        "--json",
        project_root=project,
    )
    assert plan.returncode == 0, plan.stderr or plan.stdout
    plan_result = json.loads(plan.stdout)
    assert plan_result["status"] == "pass", plan_result
    assert plan_result["ready_tasks"] == ["RTL_PACKET_CONTEXT"], plan_result

    claim_wavefront_task("RTL_PACKET_CONTEXT", ownership_mode="none")
    approve_wavefront_task("RTL_PACKET_CONTEXT", "rtl_authoring_packet_ready", "rtl_role_split_ready")

    role_ready = run_wavefront("ready", "--ip-dir", str(ip), "--run-id", run_id, "--json", project_root=project)
    assert role_ready.returncode == 0, role_ready.stderr or role_ready.stdout
    role_ready_ids = sorted(task["task_id"] for task in json.loads(role_ready.stdout)["ready_tasks"])
    role_barriers = {
        "RTL_INTERFACE_SHELL": "rtl_interface_shell_ready",
        "RTL_CONTROL_FSM": "rtl_control_fsm_ready",
        "RTL_DATAPATH_STATE": "rtl_datapath_state_ready",
        "RTL_CLOCK_RESET_DOMAIN": "rtl_clock_reset_domain_ready",
    }
    assert role_ready_ids == sorted(role_barriers), role_ready.stdout

    for task_id, barrier_output in role_barriers.items():
        claim_wavefront_task(task_id)
        approve_wavefront_task(task_id, barrier_output)

    integration_ready = run_wavefront("ready", "--ip-dir", str(ip), "--run-id", run_id, "--json", project_root=project)
    assert integration_ready.returncode == 0, integration_ready.stderr or integration_ready.stdout
    integration_ready_ids = [task["task_id"] for task in json.loads(integration_ready.stdout)["ready_tasks"]]
    assert integration_ready_ids == ["RTL_INTEGRATION_OWNER"], integration_ready.stdout

    verify = run_wavefront("verify", "--ip-dir", str(ip), "--run-id", run_id, "--json", project_root=project)
    assert verify.returncode == 0, verify.stderr or verify.stdout


def test_wavefront_scheduler(tmp_root: Path) -> None:
    project = tmp_root / "wavefront_project"
    project.mkdir(parents=True)
    ip = project / "wave_ip"
    ip.mkdir()
    run_id = "RUN_WAVE_SMOKE"

    def approve_wavefront_task(task_id: str, *barrier_outputs: str) -> None:
        review_pending = run_wavefront(
            "record",
            "--ip-dir",
            str(ip),
            "--run-id",
            run_id,
            "--task-id",
            task_id,
            "--status",
            "review_pending",
            "--receipt",
            str(ip / "knowledge" / "subagents" / f"{task_id.lower()}_receipt.json"),
            "--json",
            project_root=project,
        )
        assert review_pending.returncode == 0, review_pending.stderr or review_pending.stdout
        decision_id = f"DEC_{task_id}_SMOKE"
        decision_args = [
            "record",
            "--ip-dir",
            str(ip),
            "--run-id",
            run_id,
            "--task-id",
            task_id,
            "--decision-id",
            decision_id,
            "--decision-type",
            "custom_review",
            "--verdict",
            "approved",
            "--summary",
            f"{task_id} handoff reviewed by smoke test.",
            "--checked-against",
            f"{ip}/ontology/runs/{run_id}/wavefront_task_graph.json#{task_id}",
            "--preserved",
            "declared wavefront barrier semantics",
            "--json",
        ]
        for token in barrier_outputs:
            decision_args.extend(["--barrier-output", token])
        decision = run_decision_harness(*decision_args, project_root=project)
        assert decision.returncode == 0, decision.stderr or decision.stdout
        decision_path = json.loads(decision.stdout)["path"]
        handoff_args = [
            "record",
            "--ip-dir",
            str(ip),
            "--run-id",
            run_id,
            "--task-id",
            task_id,
            "--status",
            "handoff_pass",
            "--decision",
            decision_path,
            "--json",
        ]
        for token in barrier_outputs:
            handoff_args.extend(["--barrier-output", token])
        handoff = run_wavefront(*handoff_args, project_root=project)
        assert handoff.returncode == 0, handoff.stderr or handoff.stdout

    def claim_wavefront_task(task_id: str, *, ownership_mode: str = "exclusive_file") -> None:
        dispatch_id = ""
        graph = json.loads((ip / "ontology" / "runs" / run_id / "wavefront_task_graph.json").read_text(encoding="utf-8"))
        task = next(item for item in graph["tasks"] if item["task_id"] == task_id)
        assert task["ownership_mode"] == ownership_mode, task
        if ownership_mode != "none":
            dispatch_id = write_wavefront_claim_dispatch(project, ip, run_id, task)

        claim_args = [
            "claim",
            "--ip-dir",
            str(ip),
            "--run-id",
            run_id,
            "--task-id",
            task_id,
            "--claimed-by",
            f"smoke-{task_id.lower()}",
            "--json",
        ]
        if dispatch_id:
            claim_args.extend(["--dispatch-id", dispatch_id])
        claim = run_wavefront(*claim_args, project_root=project)
        assert claim.returncode == 0, claim.stderr or claim.stdout

    plan = run_wavefront(
        "plan",
        "--ip-dir",
        str(ip),
        "--run-id",
        run_id,
        "--template",
        str(OAG_WAVEFRONT_TEMPLATE),
        "--json",
        project_root=project,
    )
    assert plan.returncode == 0, plan.stderr or plan.stdout
    plan_result = json.loads(plan.stdout)
    assert plan_result["status"] == "pass", plan_result
    assert sorted(plan_result["ready_tasks"]) == ["TB_PACKET_CONTEXT"], plan_result

    ready = run_wavefront("ready", "--ip-dir", str(ip), "--run-id", run_id, "--json", project_root=project)
    assert ready.returncode == 0, ready.stderr or ready.stdout
    ready_ids = sorted(task["task_id"] for task in json.loads(ready.stdout)["ready_tasks"])
    assert ready_ids == ["TB_PACKET_CONTEXT"], ready.stdout

    early_scenario = run_wavefront(
        "claim",
        "--ip-dir",
        str(ip),
        "--run-id",
        run_id,
        "--task-id",
        "TB_SCENARIO_RESET",
        "--json",
        project_root=project,
    )
    assert early_scenario.returncode != 0, early_scenario.stdout
    early_result = json.loads(early_scenario.stdout)
    early_codes = {item["code"] for item in early_result["issues"]}
    assert "DEPENDENCY_UNMET" in early_codes and "BARRIER_UNMET" in early_codes, early_result

    claim_wavefront_task("TB_PACKET_CONTEXT", ownership_mode="none")

    bad_barrier_record = run_wavefront(
        "record",
        "--ip-dir",
        str(ip),
        "--run-id",
        run_id,
        "--task-id",
        "TB_PACKET_CONTEXT",
        "--status",
        "handoff_pass",
        "--barrier-output",
        "tb_driver_api_ready",
        "--json",
        project_root=project,
    )
    assert bad_barrier_record.returncode != 0, bad_barrier_record.stdout
    assert any(
        item["code"] == "BARRIER_OUTPUT_UNDECLARED"
        for item in json.loads(bad_barrier_record.stdout)["issues"]
    ), bad_barrier_record.stdout

    missing_decision_record = run_wavefront(
        "record",
        "--ip-dir",
        str(ip),
        "--run-id",
        run_id,
        "--task-id",
        "TB_PACKET_CONTEXT",
        "--status",
        "handoff_pass",
        "--barrier-output",
        "tb_authoring_packet_ready",
        "--json",
        project_root=project,
    )
    assert missing_decision_record.returncode != 0, missing_decision_record.stdout
    missing_decision_codes = {item["code"] for item in json.loads(missing_decision_record.stdout)["issues"]}
    assert "TERMINAL_DECISION_REQUIRED" in missing_decision_codes, missing_decision_record.stdout

    approve_wavefront_task("TB_PACKET_CONTEXT", "tb_authoring_packet_ready", "tb_methodology_ready")

    role_ready = run_wavefront("ready", "--ip-dir", str(ip), "--run-id", run_id, "--json", project_root=project)
    assert role_ready.returncode == 0, role_ready.stderr or role_ready.stdout
    role_ready_ids = sorted(task["task_id"] for task in json.loads(role_ready.stdout)["ready_tasks"])
    role_barriers = {
        "TB_DRIVER_BFM": "tb_driver_api_ready",
        "TB_MONITOR": "tb_monitor_api_ready",
        "TB_PREDICTOR_MODEL": "tb_predictor_model_ready",
        "TB_SCOREBOARD_SCHEMA": "scoreboard_schema_frozen",
        "TB_ASSERTION_HOOKS": "tb_assertion_hooks_ready",
    }
    assert role_ready_ids == sorted(role_barriers), role_ready.stdout

    forged_dispatch_claim = run_wavefront(
        "claim",
        "--ip-dir",
        str(ip),
        "--run-id",
        run_id,
        "--task-id",
        "TB_DRIVER_BFM",
        "--dispatch-id",
        "DISPATCH_FORGED_20260101T000000Z_ABCD1234",
        "--claimed-by",
        "smoke-forged",
        "--json",
        project_root=project,
    )
    assert forged_dispatch_claim.returncode != 0, forged_dispatch_claim.stdout
    assert any(
        item["code"] == "CLAIM_DISPATCH_NOT_FOUND"
        for item in json.loads(forged_dispatch_claim.stdout)["issues"]
    ), forged_dispatch_claim.stdout

    claim_wavefront_task("TB_DRIVER_BFM")
    claim_wavefront_task("TB_SCOREBOARD_SCHEMA")

    active_close = run_wavefront(
        "close",
        "--ip-dir",
        str(ip),
        "--run-id",
        run_id,
        "--allow-open",
        "--json",
        project_root=project,
    )
    assert active_close.returncode != 0, active_close.stdout
    assert any(item["code"] == "ACTIVE_LOCKS" for item in json.loads(active_close.stdout)["issues"]), active_close.stdout

    approve_wavefront_task("TB_DRIVER_BFM", "tb_driver_api_ready")
    approve_wavefront_task("TB_SCOREBOARD_SCHEMA", "scoreboard_schema_frozen")
    for task_id, barrier_output in role_barriers.items():
        if task_id in {"TB_DRIVER_BFM", "TB_SCOREBOARD_SCHEMA"}:
            continue
        claim_wavefront_task(task_id)
        approve_wavefront_task(task_id, barrier_output)

    coverage_ready = run_wavefront("ready", "--ip-dir", str(ip), "--run-id", run_id, "--json", project_root=project)
    assert coverage_ready.returncode == 0, coverage_ready.stderr or coverage_ready.stdout
    coverage_ready_ids = [task["task_id"] for task in json.loads(coverage_ready.stdout)["ready_tasks"]]
    assert coverage_ready_ids == ["TB_COVERAGE_MODEL"], coverage_ready.stdout
    claim_wavefront_task("TB_COVERAGE_MODEL")
    approve_wavefront_task("TB_COVERAGE_MODEL", "tb_coverage_model_ready")

    scenario_ready = run_wavefront("ready", "--ip-dir", str(ip), "--run-id", run_id, "--json", project_root=project)
    assert scenario_ready.returncode == 0, scenario_ready.stderr or scenario_ready.stdout
    scenario_ready_ids = [task["task_id"] for task in json.loads(scenario_ready.stdout)["ready_tasks"]]
    scenario_barriers = {
        "TB_SCENARIO_RESET": "scenario_reset_import_clean",
        "TB_SCENARIO_BACKPRESSURE": "scenario_backpressure_import_clean",
        "TB_SCENARIO_PROTOCOL_ERROR": "scenario_protocol_error_import_clean",
    }
    assert sorted(scenario_ready_ids) == sorted(scenario_barriers), scenario_ready.stdout

    for task_id, barrier_output in scenario_barriers.items():
        claim_wavefront_task(task_id)
        approve_wavefront_task(task_id, barrier_output)

    runner_ready = run_wavefront("ready", "--ip-dir", str(ip), "--run-id", run_id, "--json", project_root=project)
    assert runner_ready.returncode == 0, runner_ready.stderr or runner_ready.stdout
    runner_ready_ids = [task["task_id"] for task in json.loads(runner_ready.stdout)["ready_tasks"]]
    assert runner_ready_ids == ["TB_RUNNER_OWNER"], runner_ready.stdout
    verify = run_wavefront("verify", "--ip-dir", str(ip), "--run-id", run_id, "--json", project_root=project)
    assert verify.returncode == 0, verify.stderr or verify.stdout

    close = run_wavefront(
        "close",
        "--ip-dir",
        str(ip),
        "--run-id",
        run_id,
        "--allow-open",
        "--json",
        project_root=project,
    )
    assert close.returncode == 0, close.stderr or close.stdout

    conflict_ip = project / "conflict_ip"
    conflict_ip.mkdir()
    conflict_template = project / "conflict_template.json"
    conflict_template.write_text(
        json.dumps(
            {
                "schema_version": "oag_wavefront_template.v1",
                "tasks": [
                    {
                        "task_id": "WRITE_A",
                        "kind": "write",
                        "phase": "rtl",
                        "depends_on": [],
                        "allowed_write_paths": ["rtl/shared.sv"],
                        "ownership_mode": "exclusive_file",
                        "may_claim_complete": False,
                    },
                    {
                        "task_id": "WRITE_B",
                        "kind": "write",
                        "phase": "rtl",
                        "depends_on": [],
                        "allowed_write_paths": ["rtl/shared.sv"],
                        "ownership_mode": "exclusive_file",
                        "may_claim_complete": False,
                    },
                ],
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    conflict_run = "RUN_CONFLICT_SMOKE"
    conflict_plan = run_wavefront(
        "plan",
        "--ip-dir",
        str(conflict_ip),
        "--run-id",
        conflict_run,
        "--template",
        str(conflict_template),
        "--json",
        project_root=project,
    )
    assert conflict_plan.returncode == 0, conflict_plan.stderr or conflict_plan.stdout
    conflict_graph = json.loads(
        (conflict_ip / "ontology" / "runs" / conflict_run / "wavefront_task_graph.json").read_text(encoding="utf-8")
    )
    conflict_tasks = {task["task_id"]: task for task in conflict_graph["tasks"]}
    dispatch_a_id = write_wavefront_claim_dispatch(project, conflict_ip, conflict_run, conflict_tasks["WRITE_A"])
    claim_a = run_wavefront(
        "claim",
        "--ip-dir",
        str(conflict_ip),
        "--run-id",
        conflict_run,
        "--task-id",
        "WRITE_A",
        "--dispatch-id",
        dispatch_a_id,
        "--json",
        project_root=project,
    )
    assert claim_a.returncode == 0, claim_a.stderr or claim_a.stdout
    dispatch_b_id = write_wavefront_claim_dispatch(project, conflict_ip, conflict_run, conflict_tasks["WRITE_B"])
    claim_b = run_wavefront(
        "claim",
        "--ip-dir",
        str(conflict_ip),
        "--run-id",
        conflict_run,
        "--task-id",
        "WRITE_B",
        "--dispatch-id",
        dispatch_b_id,
        "--json",
        project_root=project,
    )
    assert claim_b.returncode != 0, claim_b.stdout
    assert any(item["code"] == "OWNERSHIP_CONFLICT" for item in json.loads(claim_b.stdout)["issues"]), claim_b.stdout

    shared_scope_ip = project / "shared_scope_ip"
    shared_scope_ip.mkdir()
    shared_scope_template = project / "shared_scope_template.json"
    shared_scope_template.write_text(
        json.dumps(
            {
                "schema_version": "oag_wavefront_template.v1",
                "tasks": [
                    {
                        "task_id": "BAD_SHARED_WRITER",
                        "kind": "write",
                        "phase": "sim",
                        "depends_on": [],
                        "shared_artifacts": ["sim/results.xml"],
                        "ownership_mode": "exclusive_file",
                        "may_claim_complete": False,
                    }
                ],
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    shared_scope_run = "RUN_SHARED_SCOPE_SMOKE"
    shared_scope_plan = run_wavefront(
        "plan",
        "--ip-dir",
        str(shared_scope_ip),
        "--run-id",
        shared_scope_run,
        "--template",
        str(shared_scope_template),
        "--json",
        project_root=project,
    )
    assert shared_scope_plan.returncode != 0, shared_scope_plan.stdout
    shared_scope_issues = json.loads(shared_scope_plan.stdout)["issues"]
    assert any(item["code"] == "SHARED_ARTIFACT_OWNERSHIP" for item in shared_scope_issues), shared_scope_plan.stdout

    stale_ip = project / "stale_guard_ip"
    stale_ip.mkdir()
    (stale_ip / "rtl").mkdir()
    watched_path = stale_ip / "rtl" / "watched.sv"
    watched_path.write_text("module watched; endmodule\n", encoding="utf-8")
    stale_template = project / "stale_template.json"
    stale_template.write_text(
        json.dumps(
            {
                "schema_version": "oag_wavefront_template.v1",
                "tasks": [
                    {
                        "task_id": "STALE_GUARDED_WRITE",
                        "kind": "write",
                        "phase": "rtl",
                        "depends_on": [],
                        "allowed_write_paths": ["rtl/output.sv"],
                        "stale_if_paths_changed": ["rtl/watched.sv"],
                        "ownership_mode": "exclusive_file",
                        "may_claim_complete": False,
                    }
                ],
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    stale_run = "RUN_STALE_SMOKE"
    stale_plan = run_wavefront(
        "plan",
        "--ip-dir",
        str(stale_ip),
        "--run-id",
        stale_run,
        "--template",
        str(stale_template),
        "--json",
        project_root=project,
    )
    assert stale_plan.returncode == 0, stale_plan.stderr or stale_plan.stdout
    watched_path.write_text("module watched; wire changed; endmodule\n", encoding="utf-8")
    stale_claim = run_wavefront(
        "claim",
        "--ip-dir",
        str(stale_ip),
        "--run-id",
        stale_run,
        "--task-id",
        "STALE_GUARDED_WRITE",
        "--json",
        project_root=project,
    )
    assert stale_claim.returncode != 0, stale_claim.stdout
    assert any(item["code"] == "STALE_PATH_CHANGED" for item in json.loads(stale_claim.stdout)["issues"]), stale_claim.stdout


def test_artifact_lifecycle_checker(tmp_root: Path) -> None:
    ip = tmp_root / "lifecycle_ip"
    (ip / "ontology").mkdir(parents=True)

    missing = run_lifecycle_check("--ip-dir", str(ip), "--require", "--json")
    assert missing.returncode != 0, missing.stdout
    assert any(item["code"] == "LIFECYCLE_MISSING" for item in json.loads(missing.stdout)["issues"]), missing.stdout

    lifecycle = {
        "schema_version": "oag_artifact_lifecycle.v1",
        "artifacts": [
            {
                "id": "ontology/contracts.yaml",
                "path": "ontology/contracts.yaml",
                "granularity": "file",
                "processing_stage": "canonical",
                "approval_state": "approved",
                "validity_state": "current",
                "approval_ref": "ontology/validations/contracts_review.json",
                "derived_from": ["ontology/requirements.yaml"],
                "allowed_consumers": ["rtl_authoring_packet", "tb_authoring_packet"],
            },
            {
                "id": "ontology/decision_matrix.yaml:D001",
                "path": "ontology/decision_matrix.yaml",
                "object_id": "D001",
                "granularity": "object",
                "processing_stage": "canonical",
                "approval_state": "candidate",
                "validity_state": "current",
                "derived_from": ["req/source_claims.yaml:SRC001"],
                "allowed_consumers": ["clarification_agent"],
            },
        ],
    }
    path = ip / "ontology" / "artifact_lifecycle.json"
    path.write_text(json.dumps(lifecycle, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    valid = run_lifecycle_check("--ip-dir", str(ip), "--consumer", "rtl_authoring_packet", "--json")
    assert valid.returncode == 0, valid.stderr or valid.stdout
    valid_result = json.loads(valid.stdout)
    assert valid_result["status"] == "pass", valid_result

    denied = run_lifecycle_check(
        "--ip-dir",
        str(ip),
        "--artifact-id",
        "ontology/decision_matrix.yaml:D001",
        "--consumer",
        "rtl_authoring_packet",
        "--json",
    )
    assert denied.returncode != 0, denied.stdout
    denied_codes = {item["code"] for item in json.loads(denied.stdout)["issues"]}
    assert "LIFECYCLE_CONSUMER_FORBIDDEN" in denied_codes
    assert "LIFECYCLE_APPROVAL_STATE" in denied_codes

    bad = lifecycle.copy()
    bad["artifacts"] = [
        {
            "id": "ontology/generated/authoring_packets/rtl__demo.json",
            "path": "ontology/generated/authoring_packets/rtl__demo.json",
            "granularity": "file",
            "processing_stage": "serving",
            "approval_state": "approved",
            "validity_state": "current",
            "allowed_consumers": ["rtl_agent"],
        }
    ]
    path.write_text(json.dumps(bad, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    bad_result = run_lifecycle_check("--ip-dir", str(ip), "--json")
    assert bad_result.returncode != 0, bad_result.stdout
    bad_codes = {item["code"] for item in json.loads(bad_result.stdout)["issues"]}
    assert "LIFECYCLE_DERIVED_FROM" in bad_codes
    assert "LIFECYCLE_APPROVAL_REF" in bad_codes


def test_authoring_packet_lifecycle_firewall(tmp_root: Path) -> None:
    ip = tmp_root / "packet_lifecycle_ip"
    packet_dir = ip / "ontology" / "generated" / "authoring_packets"
    packet_dir.mkdir(parents=True)
    (ip / "ontology").mkdir(exist_ok=True)
    (ip / "ontology" / "contracts.yaml").write_text(
        "schema_version: oag_contracts.v2\ncontracts:\n- id: CONTRACT_DEMO\n  status: locked\n",
        encoding="utf-8",
    )
    (ip / "ontology" / "decomposition.yaml").write_text(
        "\n".join(
            [
                "schema: oag_decomposition.v1",
                "ip: packet_lifecycle_ip",
                "profile:",
                "  mode: greenfield_modular",
                "modules:",
                "  - id: demo",
                "    name: demo",
                "    role: rtl",
                "    ownership: current_ip",
                "    file: rtl/top.sv",
                "    owned_obligations: [OBL_DEMO]",
                "    owned_contracts: [CONTRACT_DEMO]",
                "    structure_refs: [SIG_DEMO]",
                "    source_refs: [ontology/contracts.yaml]",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (ip / "ontology" / "domain_intent.yaml").write_text(
        "\n".join(
            [
                "schema_version: oag_domain_intent.v1",
                "ip: packet_lifecycle_ip",
                "clock_domains:",
                "  - id: CD_CLK",
                "    clock: clk",
                "reset_domains:",
                "  - id: RD_RST_N",
                "    reset: rst_n",
                "    clock_domain: CD_CLK",
                "    polarity: active_low",
                "    assertion: asynchronous",
                "    deassertion: synchronous",
                "cdc_crossings: []",
                "rdc_crossings:",
                "  - id: RDC_NONE",
                "    classification: no_known_rdc",
                "    basis: [single clock/reset fixture]",
                "",
            ]
        ),
        encoding="utf-8",
    )
    lifecycle = {
        "schema_version": "oag_artifact_lifecycle.v1",
        "artifacts": [
            {
                "id": "ontology/contracts.yaml",
                "path": "ontology/contracts.yaml",
                "granularity": "file",
                "processing_stage": "canonical",
                "approval_state": "approved",
                "validity_state": "current",
                "approval_ref": "ontology/validations/contracts_review.json",
                "derived_from": ["ontology/requirements.yaml"],
                "allowed_consumers": ["rtl_authoring_packet", "tb_authoring_packet"],
            },
            {
                "id": "ontology/decision_matrix.yaml:D001",
                "path": "ontology/decision_matrix.yaml",
                "object_id": "D001",
                "granularity": "object",
                "processing_stage": "canonical",
                "approval_state": "candidate",
                "validity_state": "current",
                "derived_from": ["req/source_claims.yaml:SRC001"],
                "allowed_consumers": ["clarification_agent"],
            },
            {
                "id": "rtl/top.sv",
                "path": "rtl/top.sv",
                "granularity": "file",
                "processing_stage": "serving",
                "approval_state": "approved",
                "validity_state": "current",
                "approval_ref": "ontology/validations/rtl_review.json",
                "derived_from": ["ontology/generated/authoring_packets/rtl__demo.json"],
                "allowed_consumers": ["rtl_agent"],
            },
        ],
    }
    (ip / "ontology" / "artifact_lifecycle.json").write_text(
        json.dumps(lifecycle, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    rtl_packet = {
        "schema_version": "oag_rtl_authoring_packet.v1",
        "packet_type": "rtl_authoring_packet",
        "ip": "packet_lifecycle_ip",
        "allowed_truth_sources": ["ontology/contracts.yaml"],
        "forbidden_sources": ["tb", "sim", "dut_output"],
        "contract_refs_to_implement": ["CONTRACT_DEMO"],
        "behavior_refs_implemented_target": ["behavior_model.demo"],
        "ppa_notes_required": True,
        "cdc_rdc_notes_required": True,
        "lifecycle_input_refs": ["ontology/contracts.yaml"],
    }
    tb_packet = {
        "schema_version": "oag_tb_authoring_packet.v1",
        "packet_type": "tb_authoring_packet",
        "ip": "packet_lifecycle_ip",
        "expected_source_policy": "contract_oracle_only",
        "forbidden_expected_sources": ["dut_output", "rtl_expression", "post_hoc_simulation"],
        "contract_refs": ["CONTRACT_DEMO"],
        "scenario_refs": ["SCN_DEMO"],
        "scoreboard_row_refs": ["EVT_DEMO"],
        "lifecycle_input_refs": ["ontology/contracts.yaml"],
    }
    rtl_path = packet_dir / "rtl__demo.json"
    tb_path = packet_dir / "tb__demo.json"
    module_path = packet_dir / "module__demo.json"
    rtl_path.write_text(json.dumps(rtl_packet, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tb_path.write_text(json.dumps(tb_packet, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    module_path.write_text(
        json.dumps(
            {
                "schema_version": "oag_authoring_packet.v1",
                "generated_by": "smoke",
                "generated_at": "2026-01-01T00:00:00Z",
                "ip": "packet_lifecycle_ip",
                "module": {"id": "demo", "name": "demo", "file": "rtl/top.sv"},
                "structure_profile": "greenfield_modular",
                "source_refs": ["ontology/contracts.yaml"],
                "structure_refs": ["SIG_DEMO"],
                "obligations": [{"id": "OBL_DEMO"}],
                "contracts": [{"id": "CONTRACT_DEMO"}],
                "requirements": [],
                "execution_policy": {"edit_policy": "subagent_only"},
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    compile_inputs = [
        "ontology/contracts.yaml",
        "ontology/decomposition.yaml",
        "ontology/domain_intent.yaml",
    ]
    (ip / "ontology" / "generated" / "compile_manifest.json").write_text(
        json.dumps(
            {
                "schema_version": "oag_compile_manifest.v1",
                "status": "pass",
                "compiled_at": "2026-01-01T00:00:00Z",
                "input_fingerprints": [{"path": rel, "sha256": sha256(ip / rel)} for rel in compile_inputs],
                "output_fingerprints": [],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    good = run_authoring_packet_check("--ip-dir", str(ip), "--require-packets", "--require-lifecycle", "--json")
    assert good.returncode == 0, good.stderr or good.stdout
    assert json.loads(good.stdout)["status"] == "pass", good.stdout

    rtl_packet["lifecycle_input_refs"] = ["ontology/decision_matrix.yaml:D001"]
    rtl_path.write_text(json.dumps(rtl_packet, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    bad_rtl = run_authoring_packet_check("--ip-dir", str(ip), "--require-packets", "--require-lifecycle", "--json")
    assert bad_rtl.returncode != 0, bad_rtl.stdout
    assert any(
        item["code"] == "PACKET_LIFECYCLE_BLOCKED"
        for item in json.loads(bad_rtl.stdout)["issues"]
    ), bad_rtl.stdout

    rtl_packet["lifecycle_input_refs"] = ["ontology/contracts.yaml"]
    rtl_path.write_text(json.dumps(rtl_packet, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tb_packet["lifecycle_input_refs"] = ["rtl/top.sv"]
    tb_path.write_text(json.dumps(tb_packet, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    bad_tb = run_authoring_packet_check("--ip-dir", str(ip), "--require-packets", "--require-lifecycle", "--json")
    assert bad_tb.returncode != 0, bad_tb.stdout
    assert any(
        item["code"] == "TB_PACKET_RTL_DERIVED_LIFECYCLE_INPUT"
        for item in json.loads(bad_tb.stdout)["issues"]
    ), bad_tb.stdout


def test_stale_propagation_checker(tmp_root: Path) -> None:
    ip = tmp_root / "stale_ip"
    (ip / "ontology" / "generated" / "authoring_packets").mkdir(parents=True)
    (ip / "sim").mkdir(parents=True)
    req_path = ip / "ontology" / "requirements.yaml"
    contracts_path = ip / "ontology" / "contracts.yaml"
    rtl_packet_path = ip / "ontology" / "generated" / "authoring_packets" / "rtl__demo.json"
    evidence_path = ip / "sim" / "results.xml"
    req_path.write_text("requirements:\n- id: REQ_DEMO\n  text: changed\n", encoding="utf-8")
    contracts_path.write_text("contracts:\n- contract_id: CONTRACT_DEMO\n", encoding="utf-8")
    rtl_packet_path.write_text("{}\n", encoding="utf-8")
    evidence_path.write_text("<testsuite tests=\"1\" failures=\"0\"/>\n", encoding="utf-8")

    lifecycle = {
        "schema_version": "oag_artifact_lifecycle.v1",
        "artifacts": [
            {
                "id": "ontology/requirements.yaml",
                "path": "ontology/requirements.yaml",
                "granularity": "file",
                "processing_stage": "canonical",
                "approval_state": "approved",
                "validity_state": "current",
                "approval_ref": "ontology/validations/req_review.json",
                "derived_from": ["req/source_claims.yaml"],
                "allowed_consumers": ["contract_projection"],
                "hash": {
                    "content_sha256": "sha256:" + ("0" * 64),
                    "hash_mode": "raw_bytes",
                    "size_bytes": 1,
                },
            },
            {
                "id": "ontology/contracts.yaml",
                "path": "ontology/contracts.yaml",
                "granularity": "file",
                "processing_stage": "canonical",
                "approval_state": "approved",
                "validity_state": "current",
                "approval_ref": "ontology/validations/contracts_review.json",
                "derived_from": ["ontology/requirements.yaml"],
                "allowed_consumers": ["rtl_authoring_packet", "tb_authoring_packet"],
            },
            {
                "id": "ontology/generated/authoring_packets/rtl__demo.json",
                "path": "ontology/generated/authoring_packets/rtl__demo.json",
                "granularity": "file",
                "processing_stage": "serving",
                "approval_state": "approved",
                "validity_state": "current",
                "approval_ref": "ontology/validations/rtl_packet_review.json",
                "derived_from": ["ontology/contracts.yaml"],
                "allowed_consumers": ["rtl_agent"],
            },
            {
                "id": "sim/results.xml",
                "path": "sim/results.xml",
                "granularity": "file",
                "processing_stage": "serving",
                "approval_state": "approved",
                "validity_state": "current",
                "approval_ref": "ontology/validations/sim_review.json",
                "derived_from": ["ontology/generated/authoring_packets/rtl__demo.json"],
                "allowed_consumers": ["gate"],
            },
        ],
    }
    lifecycle_path = ip / "ontology" / "artifact_lifecycle.json"
    lifecycle_path.write_text(json.dumps(lifecycle, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    stale = run_stale_check("--ip-dir", str(ip), "--json")
    assert stale.returncode != 0, stale.stdout
    result = json.loads(stale.stdout)
    codes = {item["code"] for item in result["issues"]}
    assert "STALE_HASH_MISMATCH_CURRENT" in codes
    assert "STALE_DEPENDENT_CURRENT" in codes
    stale_ids = set(result["stale_artifacts"])
    assert "ontology/contracts.yaml" in stale_ids
    assert "ontology/generated/authoring_packets/rtl__demo.json" in stale_ids
    assert "sim/results.xml" in stale_ids

    lifecycle["artifacts"][0]["hash"] = {
        "content_sha256": "sha256:" + hashlib.sha256(req_path.read_bytes()).hexdigest(),
        "hash_mode": "raw_bytes",
        "size_bytes": req_path.stat().st_size,
    }
    lifecycle_path.write_text(json.dumps(lifecycle, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    clean = run_stale_check("--ip-dir", str(ip), "--json")
    assert clean.returncode == 0, clean.stderr or clean.stdout
    assert json.loads(clean.stdout)["status"] == "pass", clean.stdout


def test_baseline_manifest_checker(tmp_root: Path) -> None:
    import yaml  # type: ignore

    ip = tmp_root / "baseline_ip"
    for rel in (
        "ontology/baselines",
        "ontology/gates",
        "ontology/validations",
        "ontology",
        "rtl",
        "sim",
    ):
        (ip / rel).mkdir(parents=True, exist_ok=True)
    files = {
        "ontology/contracts.yaml": "schema_version: contracts.v1\ncontracts: []\n",
        "rtl/top.sv": "module top; endmodule\n",
        "sim/results.xml": "<testsuite tests=\"1\" failures=\"0\"/>\n",
        "ontology/validations/validation.json": "{\"status\":\"pass\"}\n",
        "ontology/gates/closure_gate.json": "{\"decision\":\"pass\"}\n",
    }
    for rel, text in files.items():
        (ip / rel).write_text(text, encoding="utf-8")

    def hash_entry(rel: str) -> dict[str, object]:
        data = (ip / rel).read_bytes()
        return {
            "content_sha256": f"sha256:{hashlib.sha256(data).hexdigest()}",
            "hash_mode": "raw_bytes",
            "size_bytes": len(data),
        }

    manifest = {
        "schema_version": "oag_baseline_manifest.v1",
        "baseline_id": "baseline_ip.golden.v0.1.0",
        "ip": "baseline_ip",
        "baseline": {"class": "golden", "version": "0.1.0", "state": "active", "supersedes": None},
        "approval": {"state": "approved", "approval_ref": "ontology/gates/closure_gate.json"},
        "git": {"tag": "oag/baseline_ip/v0.1.0", "commit": "resolved_by_tag", "tag_type": "annotated"},
        "tracked_artifacts": {
            "truth": ["ontology/contracts.yaml"],
            "implementation": ["rtl/top.sv"],
            "evidence_summary": ["sim/results.xml"],
            "gate": ["ontology/validations/validation.json", "ontology/gates/closure_gate.json"],
        },
        "hashes": {rel: hash_entry(rel) for rel in files},
        "gate": {
            "gate_ref": "ontology/gates/closure_gate.json",
            "validation_ref": "ontology/validations/validation.json",
            "decision": "pass",
        },
    }
    manifest_path = ip / "ontology" / "baselines" / "baseline_ip_golden_v0.1.0.yaml"
    manifest_path.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")

    good = run_baseline_check("--manifest", str(manifest_path), "--json")
    assert good.returncode == 0, good.stderr or good.stdout
    assert json.loads(good.stdout)["status"] == "pass", good.stdout

    (ip / "sim/results.xml").write_text("<testsuite tests=\"1\" failures=\"1\"/>\n", encoding="utf-8")
    mismatch = run_baseline_check("--manifest", str(manifest_path), "--json")
    assert mismatch.returncode != 0, mismatch.stdout
    assert any(item["code"] == "BASELINE_HASH_MISMATCH" for item in json.loads(mismatch.stdout)["issues"]), mismatch.stdout

    broken = manifest.copy()
    broken["git"] = {"tag": "", "commit": "abc123", "tag_type": "lightweight"}
    broken["tracked_artifacts"] = {"truth": ["ontology/missing.yaml"]}
    broken_path = ip / "ontology" / "baselines" / "broken.yaml"
    broken_path.write_text(yaml.safe_dump(broken, sort_keys=False), encoding="utf-8")
    bad = run_baseline_check("--manifest", str(broken_path), "--json")
    assert bad.returncode != 0, bad.stdout
    bad_codes = {item["code"] for item in json.loads(bad.stdout)["issues"]}
    assert "BASELINE_GIT_TAG" in bad_codes
    assert "BASELINE_TAG_TYPE" in bad_codes
    assert "BASELINE_SELF_COMMIT" in bad_codes
    assert "BASELINE_TRACKED_FILE_MISSING" in bad_codes

    (ip / "sim" / "waves.fst").write_text("waveform bytes\n", encoding="utf-8")
    forbidden = manifest.copy()
    forbidden["tracked_artifacts"] = {"evidence_summary": ["sim/waves.fst"]}
    forbidden["hashes"] = {"sim/waves.fst": hash_entry("sim/waves.fst")}
    forbidden_path = ip / "ontology" / "baselines" / "forbidden.yaml"
    forbidden_path.write_text(yaml.safe_dump(forbidden, sort_keys=False), encoding="utf-8")
    forbidden_result = run_baseline_check("--manifest", str(forbidden_path), "--json")
    assert forbidden_result.returncode != 0, forbidden_result.stdout
    assert any(
        item["code"] == "BASELINE_TRACKED_FORBIDDEN"
        for item in json.loads(forbidden_result.stdout)["issues"]
    ), forbidden_result.stdout

    external_bad = manifest.copy()
    external_bad["external_artifacts"] = [
        {
            "id": "WAVES",
            "kind": "waveform",
            "uri": "artifacts://baseline_ip/v0.1.0/waves.fst",
            "required_for": "debug_only",
            "retention": "optional",
        }
    ]
    external_path = ip / "ontology" / "baselines" / "external_bad.yaml"
    external_path.write_text(yaml.safe_dump(external_bad, sort_keys=False), encoding="utf-8")
    external_result = run_baseline_check("--manifest", str(external_path), "--json")
    assert external_result.returncode != 0, external_result.stdout
    assert any(
        item["code"] == "BASELINE_EXTERNAL_SHA"
        for item in json.loads(external_result.stdout)["issues"]
    ), external_result.stdout


def test_baseline_cut_helper(tmp_root: Path) -> None:
    ip = tmp_root / "baseline_cut_ip"
    (ip / "ontology" / "baselines").mkdir(parents=True)
    (ip / "ontology" / "gates").mkdir(parents=True)
    (ip / "ontology" / "validations").mkdir(parents=True)
    (ip / "rtl").mkdir()
    (ip / "sim").mkdir()
    (ip / "ontology" / "requirements.yaml").write_text("requirements: []\n", encoding="utf-8")
    (ip / "rtl" / "top.sv").write_text("module top; endmodule\n", encoding="utf-8")
    (ip / "sim" / "results.xml").write_text("<testsuite tests=\"1\" failures=\"0\"/>\n", encoding="utf-8")
    (ip / "ontology" / "gates" / "closure_gate.json").write_text("{\"decision\":\"pass\"}\n", encoding="utf-8")
    (ip / "ontology" / "validations" / "validation.json").write_text("{\"status\":\"pass\"}\n", encoding="utf-8")
    manifest = ip / "ontology" / "baselines" / "baseline_cut.yaml"
    cut = run_baseline_cut(
        "--ip-dir",
        str(ip),
        "--baseline-id",
        "baseline_cut_ip.candidate.v0.1.0",
        "--version",
        "0.1.0",
        "--approval-ref",
        "ontology/validations/validation.json",
        "--gate-ref",
        "ontology/gates/closure_gate.json",
        "--validation-ref",
        "ontology/validations/validation.json",
        "--tracked-artifact",
        "truth:ontology/requirements.yaml",
        "--tracked-artifact",
        "implementation:rtl/top.sv",
        "--tracked-artifact",
        "evidence_summary:sim/results.xml",
        "--tracked-artifact",
        "gate:ontology/gates/closure_gate.json",
        "--output",
        str(manifest),
        "--allow-dirty",
        "--json",
    )
    assert cut.returncode == 0, cut.stderr or cut.stdout
    assert json.loads(cut.stdout)["status"] == "pass", cut.stdout
    assert manifest.is_file(), manifest

    generated = run_baseline_check("--manifest", str(manifest), "--json")
    assert generated.returncode == 0, generated.stderr or generated.stdout
    assert json.loads(generated.stdout)["status"] == "pass", generated.stdout

    repo = tmp_root / "dirty_repo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, text=True, capture_output=True, check=True)
    dirty_ip = repo / "dirty_ip"
    (dirty_ip / "ontology" / "baselines").mkdir(parents=True)
    (dirty_ip / "ontology" / "requirements.yaml").write_text("requirements: []\n", encoding="utf-8")
    dirty = run_baseline_cut(
        "--ip-dir",
        str(dirty_ip),
        "--baseline-id",
        "dirty_ip.candidate.v0.1.0",
        "--version",
        "0.1.0",
        "--approval-ref",
        "ontology/validations/validation.json",
        "--gate-ref",
        "ontology/gates/closure_gate.json",
        "--validation-ref",
        "ontology/validations/validation.json",
        "--tracked-artifact",
        "truth:ontology/requirements.yaml",
        "--output",
        str(dirty_ip / "ontology" / "baselines" / "dirty.yaml"),
        "--json",
        cwd=repo,
    )
    assert dirty.returncode != 0, dirty.stdout
    assert any(
        item["code"] == "BASELINE_CUT_DIRTY_TREE"
        for item in json.loads(dirty.stdout)["issues"]
    ), dirty.stdout


def test_baseline_verify_git_tag(tmp_root: Path) -> None:
    repo = tmp_root / "verify_repo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, text=True, capture_output=True, check=True)
    subprocess.run(["git", "config", "--local", "core.autocrlf", "false"], cwd=repo, text=True, capture_output=True, check=True)
    ip = repo / "verify_ip"
    (ip / "ontology" / "baselines").mkdir(parents=True)
    (ip / "ontology" / "gates").mkdir(parents=True)
    (ip / "ontology" / "validations").mkdir(parents=True)
    (ip / "rtl").mkdir()
    (ip / "sim").mkdir()
    (ip / "ontology" / "requirements.yaml").write_text("requirements: []\n", encoding="utf-8")
    (ip / "rtl" / "top.sv").write_text("module top; endmodule\n", encoding="utf-8")
    (ip / "sim" / "results.xml").write_text("<testsuite tests=\"1\" failures=\"0\"/>\n", encoding="utf-8")
    (ip / "ontology" / "gates" / "closure_gate.json").write_text("{\"decision\":\"pass\"}\n", encoding="utf-8")
    (ip / "ontology" / "validations" / "validation.json").write_text("{\"status\":\"pass\"}\n", encoding="utf-8")
    tag = "oag/verify_ip/v0.1.0"
    manifest = ip / "ontology" / "baselines" / "verify.yaml"
    cut = run_baseline_cut(
        "--ip-dir",
        str(ip),
        "--baseline-id",
        "verify_ip.golden.v0.1.0",
        "--version",
        "0.1.0",
        "--baseline-class",
        "golden",
        "--baseline-state",
        "active",
        "--approval-state",
        "approved",
        "--approval-ref",
        "ontology/validations/validation.json",
        "--gate-ref",
        "ontology/gates/closure_gate.json",
        "--validation-ref",
        "ontology/validations/validation.json",
        "--tag",
        tag,
        "--tracked-artifact",
        "truth:ontology/requirements.yaml",
        "--tracked-artifact",
        "implementation:rtl/top.sv",
        "--tracked-artifact",
        "evidence_summary:sim/results.xml",
        "--tracked-artifact",
        "gate:ontology/gates/closure_gate.json",
        "--tracked-artifact",
        "gate:ontology/validations/validation.json",
        "--output",
        str(manifest),
        "--allow-dirty",
        "--json",
        cwd=repo,
    )
    assert cut.returncode == 0, cut.stderr or cut.stdout
    manifest.write_bytes(manifest.read_bytes().replace(b"\r\n", b"\n").replace(b"\n", b"\r\n"))
    subprocess.run(["git", "add", "."], cwd=repo, text=True, capture_output=True, check=True)
    subprocess.run(
        ["git", "-c", "user.name=Smoke", "-c", "user.email=smoke@example.com", "commit", "-m", "baseline"],
        cwd=repo,
        text=True,
        capture_output=True,
        check=True,
    )
    manifest_sha = "sha256:" + hashlib.sha256(manifest.read_bytes()).hexdigest()
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=Smoke",
            "-c",
            "user.email=smoke@example.com",
            "tag",
            "-a",
            tag,
            "-m",
            f"manifest_sha256: {manifest_sha}",
        ],
        cwd=repo,
        text=True,
        capture_output=True,
        check=True,
    )

    good = run_baseline_verify("--manifest", str(manifest), "--verify-git-tag", "--json", cwd=repo)
    assert good.returncode == 0, good.stderr or good.stdout
    assert json.loads(good.stdout)["status"] == "pass", good.stdout

    crlf_bytes = manifest.read_bytes()
    manifest.write_bytes(crlf_bytes.replace(b"\r\n", b"\n"))
    eol_mismatch = run_baseline_verify("--manifest", str(manifest), "--verify-git-tag", "--json", cwd=repo)
    assert eol_mismatch.returncode != 0, eol_mismatch.stdout
    eol_codes = {item["code"] for item in json.loads(eol_mismatch.stdout)["issues"]}
    assert "BASELINE_VERIFY_MANIFEST_TREE_MISMATCH" in eol_codes, eol_mismatch.stdout
    manifest.write_bytes(crlf_bytes)
    restored = run_baseline_verify("--manifest", str(manifest), "--verify-git-tag", "--json", cwd=repo)
    assert restored.returncode == 0, restored.stderr or restored.stdout

    manifest.write_text(manifest.read_text(encoding="utf-8") + "# local edit after tag\n", encoding="utf-8")
    stale = run_baseline_verify("--manifest", str(manifest), "--verify-git-tag", "--json", cwd=repo)
    assert stale.returncode != 0, stale.stdout
    codes = {item["code"] for item in json.loads(stale.stdout)["issues"]}
    assert "BASELINE_VERIFY_MANIFEST_TREE_MISMATCH" in codes


def test_ip_version_policy_checker(tmp_root: Path) -> None:
    ip = tmp_root / "version_ip"
    (ip / "ontology").mkdir(parents=True)
    (ip / "ontology" / "baselines").mkdir(parents=True)
    (ip / "ontology" / "validations").mkdir(parents=True)
    (ip / "ontology" / "baselines" / "version_ip_golden_v0.1.1.yaml").write_text(
        "schema_version: oag_baseline_manifest.v1\n",
        encoding="utf-8",
    )
    (ip / "ontology" / "validations" / "version_review.json").write_text("{\"status\":\"approved\"}\n", encoding="utf-8")
    ledger = {
        "schema_version": "oag_ip_version.v1",
        "ip": "version_ip",
        "current_version": "0.1.1",
        "version_policy": {
            "git_scope": "ip_local_repo",
            "tag_prefix": "oag/version_ip/",
        },
        "versions": [
            {
                "version": "0.1.0",
                "baseline_class": "golden",
                "state": "superseded",
                "change_class": "minor",
                "functional_truth_changed": True,
                "baseline_manifest": "ontology/baselines/version_ip_golden_v0.1.0.yaml",
                "git_tag": "oag/version_ip/v0.1.0",
                "approval_ref": "ontology/validations/version_review.json",
            },
            {
                "version": "0.1.1",
                "baseline_class": "golden",
                "state": "active",
                "change_class": "patch",
                "functional_truth_changed": False,
                "baseline_manifest": "ontology/baselines/version_ip_golden_v0.1.1.yaml",
                "git_tag": "oag/version_ip/v0.1.1",
                "approval_ref": "ontology/validations/version_review.json",
            },
        ],
    }
    version_path = ip / "ontology" / "ip_version.yaml"
    import yaml  # type: ignore

    version_path.write_text(yaml.safe_dump(ledger, sort_keys=False), encoding="utf-8")

    no_git = run_ip_version_check("--ip-dir", str(ip), "--require-ip-git", "--json")
    assert no_git.returncode != 0, no_git.stdout
    assert any(item["code"] == "IP_VERSION_LOCAL_GIT_MISSING" for item in json.loads(no_git.stdout)["issues"]), no_git.stdout

    init = run_ip_git("init", "--ip-dir", str(ip), "--json")
    assert init.returncode == 0, init.stderr or init.stdout
    assert json.loads(init.stdout)["status"] == "pass", init.stdout
    good = run_ip_version_check("--ip-dir", str(ip), "--require-ip-git", "--json")
    assert good.returncode == 0, good.stderr or good.stdout
    assert json.loads(good.stdout)["status"] == "pass", good.stdout

    ledger["versions"][1]["functional_truth_changed"] = True
    version_path.write_text(yaml.safe_dump(ledger, sort_keys=False), encoding="utf-8")
    bad_patch = run_ip_version_check("--ip-dir", str(ip), "--require-ip-git", "--json")
    assert bad_patch.returncode != 0, bad_patch.stdout
    assert any(item["code"] == "IP_VERSION_PATCH_TRUTH_CHANGE" for item in json.loads(bad_patch.stdout)["issues"]), bad_patch.stdout


def test_ip_git_helper_checkpoint(tmp_root: Path) -> None:
    ip = tmp_root / "git_helper_ip"
    (ip / "req").mkdir(parents=True)
    (ip / "req" / "intent.md").write_text("# Intent\n\nDraft.\n", encoding="utf-8")
    init = run_ip_git(
        "init",
        "--ip-dir",
        str(ip),
        "--initial-commit",
        "--message",
        "OAG scaffold git helper",
        "--json",
    )
    assert init.returncode == 0, init.stderr or init.stdout
    init_doc = json.loads(init.stdout)
    assert init_doc["status"] == "pass", init_doc
    assert init_doc["commit"]["committed"] is True, init_doc
    assert init_doc["repo"]["core_autocrlf"] == "false", init_doc
    assert (ip / ".git").exists(), init_doc
    assert "*.fst" in (ip / ".gitignore").read_text(encoding="utf-8")

    (ip / "req" / "intent.md").write_text("# Intent\n\nRefined.\n", encoding="utf-8")
    (ip / "sim" / "waves").mkdir(parents=True)
    (ip / "sim" / "waves" / "debug.fst").write_text("ignored\n", encoding="utf-8")
    checkpoint = run_ip_git(
        "checkpoint",
        "--ip-dir",
        str(ip),
        "--message",
        "OAG draft: refine intent",
        "--json",
    )
    assert checkpoint.returncode == 0, checkpoint.stderr or checkpoint.stdout
    checkpoint_doc = json.loads(checkpoint.stdout)
    assert checkpoint_doc["status"] == "pass", checkpoint_doc
    assert checkpoint_doc["commit"]["committed"] is True, checkpoint_doc
    log = subprocess.run(["git", "-C", str(ip), "log", "-1", "--pretty=%s"], text=True, capture_output=True, check=False)
    assert log.stdout.strip() == "OAG draft: refine intent", log.stdout
    status = subprocess.run(["git", "-C", str(ip), "status", "--porcelain"], text=True, capture_output=True, check=False)
    assert status.stdout == "", status.stdout

    noop = run_ip_git(
        "checkpoint",
        "--ip-dir",
        str(ip),
        "--message",
        "OAG draft: no changes",
        "--json",
    )
    assert noop.returncode == 0, noop.stderr or noop.stdout
    noop_doc = json.loads(noop.stdout)
    assert noop_doc["status"] == "pass", noop_doc
    assert noop_doc["commit"]["committed"] is False, noop_doc
    assert noop_doc["commit"]["reason"] == "no_changes", noop_doc


def write_stage_receipt(ip: Path, stage: str) -> None:
    receipt = {
        "schema_version": "stage_run_receipt.v1",
        "stage": stage,
        "owner": stage,
        "status": "pass",
        "command": "smoke-test",
        "actor": {"kind": "tool", "id": "smoke_test"},
        "started_at": "2026-01-01T00:00:00Z",
        "completed_at": "2026-01-01T00:00:01Z",
        "input_fingerprints": [
            {"path": "rtl/rtl_compile.json", "sha256": sha256(ip / "rtl" / "rtl_compile.json")},
            {"path": "lint/dut_lint.json", "sha256": sha256(ip / "lint" / "dut_lint.json")},
        ],
        "output_fingerprints": [
            {"path": "sim/results.xml", "sha256": sha256(ip / "sim" / "results.xml")},
            {"path": "sim/scoreboard_events.jsonl", "sha256": sha256(ip / "sim" / "scoreboard_events.jsonl")},
        ],
    }
    out = ip / "ontology" / "evidence" / "stage_runs" / f"{stage}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")


def write_ip_validator_report(ip: Path) -> None:
    path = ip / "signoff" / "ip_validator_report.json"
    path.write_text(
        json.dumps({"schema_version": "ip_validator_report.v1", "status": "pass"}) + "\n",
        encoding="utf-8",
    )


def closure_gate_artifacts(ip: Path) -> list[str]:
    candidates = [
        "knowledge/validations/oag_validation_report.json",
        "rtl/rtl_compile.json",
        "lint/dut_lint.json",
        "sim/results.xml",
        "sim/scoreboard_events.jsonl",
        "cov/coverage.json",
        "ontology/generated/design_truth_graph.json",
        "ontology/generated/design_facts_graph.json",
        "signoff/truth_coverage.json",
    ]
    return [rel for rel in candidates if (ip / rel).is_file()]


def close_demo_counter(ip: Path, *, claim: str, evidence_files: list[str] | None = None) -> dict:
    return call(
        {
            "tool": "oag.record",
            "arguments": {
                "ip_dir": str(ip),
                "stage": "sim",
                "type": "finding",
                "claim": claim,
                "summary": "development validator smoke evidence closes the counter scoreboard obligation",
                "actor": {"kind": "ai", "id": "codex", "surface": "smoke"},
                "rocev": {
                    "obligation": {"id": "OBL_DEMO_COUNTER_CX1_RESET_KNOWN", "text": "scoreboard has no mismatches"},
                    "contract": {
                        "id": "CONTRACT_DEMO_COUNTER_CX1_SIM_SCOREBOARD",
                        "method": "scoreboard",
                        "pass_condition": "mismatch count is zero",
                    },
                    "evidence": {
                        "files": evidence_files or ["sim/results.xml", "sim/scoreboard_events.jsonl"],
                        "tests": [],
                        "commit": "",
                    },
                    "validation": {"status": "closed", "verdict": "pass", "rationale": "all development validator gates have evidence"},
                },
            },
        }
    )


def write_closure_reports(ip: Path, *, gate_decision: str = "PASS") -> None:
    validation_path = ip / "knowledge" / "validations" / "oag_validation_report.json"
    gate_path = ip / "knowledge" / "gate_reviews" / "oag_gate_decision.json"
    validation_path.parent.mkdir(parents=True, exist_ok=True)
    gate_path.parent.mkdir(parents=True, exist_ok=True)
    validation_path.write_text(
        json.dumps(
            {
                "schema_version": "oag_validation_report.v1",
                "product_name": "IP Dev Agent",
                "internal_gateway": "Ontology Agent Gateway",
                "ip_id": ip.name,
                "role_name": "oag-evidence-validator",
                "status": "pass",
                "closure_matrix": {"status": "pass", "open_count": 0},
                "evidence": {"status": "pass"},
                "mutation_guard": {"status": "pass"},
                "coverage": {"status": "pass"},
                "issues": [],
                "created_at": "2026-01-01T00:00:00Z",
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    checked_artifacts = closure_gate_artifacts(ip)
    gate_path.write_text(
        json.dumps(
            {
                "schema_version": "oag_gate_decision.v1",
                "product_name": "IP Dev Agent",
                "internal_gateway": "Ontology Agent Gateway",
                "ip_id": ip.name,
                "role_name": "oag-gate-reviewer",
                "decision": gate_decision,
                "validation_report": "knowledge/validations/oag_validation_report.json",
                "checked_artifacts": checked_artifacts,
                "checked_artifact_hashes": {rel: sha256(ip / rel) for rel in checked_artifacts},
                "blockers": [] if gate_decision == "PASS" else ["smoke blocker"],
                "created_at": "2026-01-01T00:00:00Z",
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        hooks = json.loads(HOOKS_JSON.read_text(encoding="utf-8"))
        def win_hook(script: str) -> str:
            return "cmd.exe /d /c .codex\\bin\\oag-python.cmd .codex\\hooks\\" + script

        session_start_hooks = hooks["hooks"]["SessionStart"][0]["hooks"]
        assert session_start_hooks[0]["command"] == "python3 .codex/hooks/codex_oag_session_start.py", hooks
        assert session_start_hooks[0]["commandWindows"] == win_hook("codex_oag_session_start.py"), hooks
        user_hooks = hooks["hooks"]["UserPromptSubmit"][0]["hooks"]
        assert user_hooks[0]["command"] == "python3 .codex/hooks/codex_oag_mode_trigger.py", hooks
        assert user_hooks[0]["commandWindows"] == win_hook("codex_oag_mode_trigger.py"), hooks
        assert user_hooks[1]["command"] == "python3 .codex/hooks/codex_native_subagent_guard.py", hooks
        assert user_hooks[1]["commandWindows"] == win_hook("codex_native_subagent_guard.py"), hooks
        assert user_hooks[2]["command"] == "python3 .codex/hooks/codex_deep_interview_prompt_guard.py", hooks
        assert user_hooks[2]["commandWindows"] == win_hook("codex_deep_interview_prompt_guard.py"), hooks
        assert user_hooks[3]["command"] == "python3 .codex/hooks/codex_context_inject.py", hooks
        assert user_hooks[3]["commandWindows"] == win_hook("codex_context_inject.py"), hooks
        assert user_hooks[4]["command"] == "python3 .codex/hooks/codex_draft_pressure.py", hooks
        assert user_hooks[4]["commandWindows"] == win_hook("codex_draft_pressure.py"), hooks
        stop_hooks = hooks["hooks"]["Stop"][0]["hooks"]
        stop_command = stop_hooks[0]["command"]
        assert stop_command == "python3 .codex/hooks/codex_stop_gate.py", hooks
        assert stop_hooks[0]["commandWindows"] == win_hook("codex_stop_gate.py"), hooks
        assert "/bin/sh" not in stop_command and "sh.exe" not in stop_command, hooks
        subagent_start_hooks = hooks["hooks"]["SubagentStart"][0]
        assert subagent_start_hooks["matcher"] == "^oag-", hooks
        assert subagent_start_hooks["hooks"][0]["command"] == "python3 .codex/hooks/codex_subagent_oag_start.py", hooks
        assert subagent_start_hooks["hooks"][0]["commandWindows"] == win_hook("codex_subagent_oag_start.py"), hooks
        subagent_hooks = hooks["hooks"]["SubagentStop"][0]
        assert subagent_hooks["matcher"] == "^oag-", hooks
        assert subagent_hooks["hooks"][0]["command"] == "python3 .codex/hooks/codex_subagent_oag_gate.py", hooks
        assert subagent_hooks["hooks"][0]["commandWindows"] == win_hook("codex_subagent_oag_gate.py"), hooks
        post_compact_hooks = hooks["hooks"]["PostCompact"][0]["hooks"]
        assert post_compact_hooks[0]["command"] == "python3 .codex/hooks/codex_context_inject.py", hooks
        assert post_compact_hooks[0]["commandWindows"] == win_hook("codex_context_inject.py"), hooks
        assert (ROOT / "bin" / "oag-python.cmd").is_file(), hooks
        assert STOP_GATE.is_file(), STOP_GATE
        assert SUBAGENT_START.is_file(), SUBAGENT_START
        assert SUBAGENT_GATE.is_file(), SUBAGENT_GATE
        assert OAG_MODE_TRIGGER.is_file(), OAG_MODE_TRIGGER
        assert NATIVE_SUBAGENT_GUARD.is_file(), NATIVE_SUBAGENT_GUARD
        assert DEEP_INTERVIEW_GUARD.is_file(), DEEP_INTERVIEW_GUARD
        assert OAG_SESSION_START.is_file(), OAG_SESSION_START
        assert CONTEXT_HOOK.is_file(), CONTEXT_HOOK
        assert DRAFT_HOOK.is_file(), DRAFT_HOOK
        assert DEEP_INTERVIEW_ROUND.is_file(), DEEP_INTERVIEW_ROUND
        assert PORTABLE_DB.is_file(), PORTABLE_DB
        assert OKF.is_file(), OKF
        assert EVAL.is_file(), EVAL
        assert ANSWER_KEY_EVAL.is_file(), ANSWER_KEY_EVAL
        assert DEV_VALIDATOR.is_file(), DEV_VALIDATOR
        assert SPEC_RTL_LOOP.is_file(), SPEC_RTL_LOOP
        assert EXPLORATION_PLAN.is_file(), EXPLORATION_PLAN
        assert TEAM_PLAN.is_file(), TEAM_PLAN
        assert WINDOWS_SMOKE.is_file(), WINDOWS_SMOKE
        spec_loop_source = SPEC_RTL_LOOP.read_text(encoding="utf-8")
        assert "shell=True" not in spec_loop_source, spec_loop_source
        assert "/bin/sh" not in spec_loop_source and "sh.exe" not in spec_loop_source, spec_loop_source
        windows_smoke = run_oag_windows_smoke("--json")
        assert windows_smoke.returncode == 0, windows_smoke.stderr or windows_smoke.stdout
        windows_smoke_payload = json.loads(windows_smoke.stdout)
        assert windows_smoke_payload["status"] == "pass", windows_smoke_payload
        assert windows_smoke_payload["checks"]["hook_commands"] == "pass", windows_smoke_payload
        assert windows_smoke_payload["checks"]["argv_command_split"] == "pass", windows_smoke_payload
        test_pyslang_lint_runner()
        test_rtl_role_wavefront_template(Path(tmp))
        test_wavefront_scheduler(Path(tmp))
        test_dispatch_prompt_contract_subagent_boundary()
        test_task5_dispatch_wavefront_matrix(Path(tmp))
        test_dispatch_hardening_guards(Path(tmp))
        test_dispatch_authoring_packet_retry_classifier()
        test_nested_ip_repository_main_write_gate(Path(tmp))
        test_canonical_run_evidence_archive_guard(Path(tmp))
        test_artifact_lifecycle_checker(Path(tmp))
        test_authoring_packet_lifecycle_firewall(Path(tmp))
        test_stale_propagation_checker(Path(tmp))
        test_baseline_manifest_checker(Path(tmp))
        test_baseline_cut_helper(Path(tmp))
        test_baseline_verify_git_tag(Path(tmp))
        test_ip_version_policy_checker(Path(tmp))
        test_ip_git_helper_checkpoint(Path(tmp))
        test_lock_preview_frame_preserves_verbatim_source(Path(tmp))
        test_oag_team_plan_mode(Path(tmp))
        test_oag_run_control_layer(Path(tmp))
        test_oag_decision_autonomy_policy(Path(tmp))
        test_oag_arch_exploration_blocker_regressions(Path(tmp))
        test_oag_arch_exploration_remaining_review_gates(Path(tmp))
        test_deep_interview_handoff_persists_decision_rows(Path(tmp))
        assert DISPATCH.is_file(), DISPATCH
        assert WAVEFRONT.is_file(), WAVEFRONT
        assert MAIN_WRITE_GATE.is_file(), MAIN_WRITE_GATE
        assert VALIDATE_JSON.is_file(), VALIDATE_JSON
        assert AGENT_CATALOG_CHECK.is_file(), AGENT_CATALOG_CHECK
        assert CODEX_CONFIG_DOCTOR.is_file(), CODEX_CONFIG_DOCTOR
        assert DEBUG_EVAL_METRICS.is_file(), DEBUG_EVAL_METRICS
        assert CLOSURE_CHECK.is_file(), CLOSURE_CHECK
        assert PACK_RELEASE_CHECK.is_file(), PACK_RELEASE_CHECK
        assert DOMAIN_CROSSING_CHECK.is_file(), DOMAIN_CROSSING_CHECK
        test_oag_paths_resolver(Path(tmp))
        test_dot_oag_layout_state_scripts(Path(tmp))
        test_dot_oag_scaffold_layout(Path(tmp))
        test_dot_oag_migration_tool(Path(tmp))
        test_dot_oag_mixed_layout_rejected(Path(tmp))
        assert PYSLANG_LINT.is_file(), PYSLANG_LINT
        assert REQ_QUALITY_CHECK.is_file(), REQ_QUALITY_CHECK
        assert LOCK_READINESS_CHECK.is_file(), LOCK_READINESS_CHECK
        assert LOCK_PREVIEW_FRAME.is_file(), LOCK_PREVIEW_FRAME
        assert CONTRACT_STRENGTH_CHECK.is_file(), CONTRACT_STRENGTH_CHECK
        assert AUTHORING_PACKET_CHECK.is_file(), AUTHORING_PACKET_CHECK
        assert TRACE_GRAPH_CHECK.is_file(), TRACE_GRAPH_CHECK
        assert DEEP_SEMANTIC_INTAKE.is_file(), DEEP_SEMANTIC_INTAKE
        assert DECISION_MATRIX_GENERATE.is_file(), DECISION_MATRIX_GENERATE
        assert LIFECYCLE_CHECK.is_file(), LIFECYCLE_CHECK
        assert BASELINE_CHECK.is_file(), BASELINE_CHECK
        assert STALE_CHECK.is_file(), STALE_CHECK
        assert BASELINE_CUT.is_file(), BASELINE_CUT
        assert BASELINE_VERIFY.is_file(), BASELINE_VERIFY
        assert IP_VERSION_CHECK.is_file(), IP_VERSION_CHECK
        assert IP_GIT.is_file(), IP_GIT
        assert RUN_FRAME.is_file(), RUN_FRAME
        assert ORCHESTRATION_GUARD.is_file(), ORCHESTRATION_GUARD
        assert WINDOWS_SMOKE.is_file(), WINDOWS_SMOKE
        assert REVIEW_FRAME.is_file(), REVIEW_FRAME
        assert GATE_FRAME.is_file(), GATE_FRAME
        assert SSOT_SECTION_CHECK.is_file(), SSOT_SECTION_CHECK
        assert AGENT_CATALOG.is_file(), AGENT_CATALOG
        assert OAG_MODE_DIRECTIVE.is_file(), OAG_MODE_DIRECTIVE
        assert OAG_DECISION_AUTONOMY_POLICY.is_file(), OAG_DECISION_AUTONOMY_POLICY
        assert SUBAGENT_WORKFLOWS.is_file(), SUBAGENT_WORKFLOWS
        assert OAG_RULE_INDEX.is_file(), OAG_RULE_INDEX
        assert OAG_DECISION_AUTONOMY_RULES.is_file(), OAG_DECISION_AUTONOMY_RULES
        assert OAG_IP_WORKFLOW_SKILL.is_file(), OAG_IP_WORKFLOW_SKILL
        assert OAG_DEEP_SEMANTIC_SKILL.is_file(), OAG_DEEP_SEMANTIC_SKILL
        assert OAG_DECISION_MATRIX_SKILL.is_file(), OAG_DECISION_MATRIX_SKILL
        assert OAG_LOCK_PREVIEW_FRAME_SKILL.is_file(), OAG_LOCK_PREVIEW_FRAME_SKILL
        assert OAG_CONTRACT_PROJECTION_SKILL.is_file(), OAG_CONTRACT_PROJECTION_SKILL
        assert OAG_AUTHORING_PACKET_SKILL.is_file(), OAG_AUTHORING_PACKET_SKILL
        assert OAG_EVIDENCE_CLOSURE_SKILL.is_file(), OAG_EVIDENCE_CLOSURE_SKILL
        assert OAG_WAVEFRONT_SKILL.is_file(), OAG_WAVEFRONT_SKILL
        assert OAG_TEAM_MODE_SKILL.is_file(), OAG_TEAM_MODE_SKILL
        assert OAG_WAVEFRONT_TEMPLATE.is_file(), OAG_WAVEFRONT_TEMPLATE
        assert OAG_RTL_WAVEFRONT_TEMPLATE.is_file(), OAG_RTL_WAVEFRONT_TEMPLATE
        assert OAG_DATA_LIFECYCLE_POLICY.is_file(), OAG_DATA_LIFECYCLE_POLICY
        assert OAG_BASELINE_GIT_POLICY.is_file(), OAG_BASELINE_GIT_POLICY
        assert OAG_IP_VERSIONING_POLICY.is_file(), OAG_IP_VERSIONING_POLICY
        assert OAG_FEATURE_IPXACT_POLICY.is_file(), OAG_FEATURE_IPXACT_POLICY
        assert OAG_IP_VERSIONING_SKILL.is_file(), OAG_IP_VERSIONING_SKILL
        assert OAG_IP_VERSIONING_RULES.is_file(), OAG_IP_VERSIONING_RULES
        for schema_file in SCHEMA_FILES:
            assert schema_file.is_file(), schema_file
            schema_payload = json.loads(schema_file.read_text(encoding="utf-8"))
            assert "$schema" in schema_payload and "required" in schema_payload, schema_payload
        assert not (ROOT / "agents" / "oag-agent-catalog.toml").exists()
        assert all(path.suffix == ".toml" for path in (ROOT / "agents").iterdir() if path.is_file())
        agent_catalog_check = run_agent_catalog_check()
        assert agent_catalog_check.returncode == 0, agent_catalog_check.stderr or agent_catalog_check.stdout
        agent_catalog_result = json.loads(agent_catalog_check.stdout)
        assert agent_catalog_result["status"] == "pass", agent_catalog_result
        assert agent_catalog_result["counts"] == {"core": 15, "custom": 3, "total": 18, "toml_files": 18}, agent_catalog_result
        assert agent_catalog_result["completion_authority"] == ["oag-gate-reviewer"], agent_catalog_result
        assert agent_catalog_result["final_decision_authority"] == ["oag-gate-reviewer"], agent_catalog_result
        pack_release_check = run_pack_release_check()
        assert pack_release_check.returncode == 0, pack_release_check.stderr or pack_release_check.stdout
        pack_release_result = json.loads(pack_release_check.stdout)
        assert pack_release_result["status"] == "pass", pack_release_result
        assert pack_release_result["counts"]["agent_tomls"] == 18, pack_release_result
        assert pack_release_result["counts"]["schemas"] >= 4, pack_release_result
        ppa_bad_ip = Path(tmp) / "ppa_bad_function"
        (ppa_bad_ip / "rtl").mkdir(parents=True)
        (ppa_bad_ip / "list").mkdir(parents=True)
        (ppa_bad_ip / "list" / "rtl.f").write_text("rtl/bad_function.sv\n", encoding="utf-8")
        (ppa_bad_ip / "rtl" / "bad_function.sv").write_text(
            "\n".join(
                [
                    "module bad_function(input logic a, output logic y);",
                    "  function logic helper;",
                    "    input logic in;",
                    "    begin",
                    "      helper = in;",
                    "    end",
                    "  endfunction",
                    "  assign y = helper(a);",
                    "endmodule",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        ppa_bad = subprocess.run(
            [sys.executable, str(PPA_CHECK), "--ip-dir", str(ppa_bad_ip), "--json"],
            text=True,
            capture_output=True,
            check=False,
            cwd=ROOT,
        )
        assert ppa_bad.returncode == 1, ppa_bad.stderr or ppa_bad.stdout
        ppa_bad_result = json.loads(ppa_bad.stdout)
        assert ppa_bad_result["status"] == "fail", ppa_bad_result
        assert ppa_bad_result["scanned_files"] == ["rtl/bad_function.sv"], ppa_bad_result
        assert any(issue["code"] == "FUNCTION" for issue in ppa_bad_result["issues"]), ppa_bad_result
        ppa_bad_mixed_ip = Path(tmp) / "ppa_bad_mixed_assign"
        (ppa_bad_mixed_ip / "rtl").mkdir(parents=True)
        (ppa_bad_mixed_ip / "list").mkdir(parents=True)
        (ppa_bad_mixed_ip / "list" / "rtl.f").write_text("rtl/bad_mixed_assign.sv\n", encoding="utf-8")
        (ppa_bad_mixed_ip / "rtl" / "bad_mixed_assign.sv").write_text(
            "\n".join(
                [
                    "module bad_mixed_assign(input logic clk, input logic a, output logic y);",
                    "  logic tmp;",
                    "  always @(posedge clk) begin",
                    "    tmp = a;",
                    "    y <= tmp;",
                    "  end",
                    "endmodule",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        ppa_bad_mixed = subprocess.run(
            [sys.executable, str(PPA_CHECK), "--ip-dir", str(ppa_bad_mixed_ip), "--json"],
            text=True,
            capture_output=True,
            check=False,
            cwd=ROOT,
        )
        assert ppa_bad_mixed.returncode == 1, ppa_bad_mixed.stderr or ppa_bad_mixed.stdout
        ppa_bad_mixed_result = json.loads(ppa_bad_mixed.stdout)
        assert ppa_bad_mixed_result["status"] == "fail", ppa_bad_mixed_result
        assert any(issue["code"] == "MIXED_BLOCKING_NONBLOCKING_ALWAYS" for issue in ppa_bad_mixed_result["issues"]), ppa_bad_mixed_result
        ppa_good_ip = Path(tmp) / "ppa_good_generate"
        (ppa_good_ip / "rtl").mkdir(parents=True)
        (ppa_good_ip / "list").mkdir(parents=True)
        (ppa_good_ip / "list" / "rtl.f").write_text("rtl/good_generate.sv\n", encoding="utf-8")
        (ppa_good_ip / "rtl" / "good_generate.sv").write_text(
            "\n".join(
                [
                    "module good_generate(input logic [1:0] a, output logic [1:0] y);",
                    "  genvar gi;",
                    "  generate",
                    "    for (gi = 0; gi < 2; gi = gi + 1) begin : gen_bits",
                    "      assign y[gi] = a[gi];",
                    "    end",
                    "  endgenerate",
                    "endmodule",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        ppa_good = subprocess.run(
            [sys.executable, str(PPA_CHECK), "--ip-dir", str(ppa_good_ip), "--json"],
            text=True,
            capture_output=True,
            check=False,
            cwd=ROOT,
        )
        assert ppa_good.returncode == 0, ppa_good.stderr or ppa_good.stdout
        ppa_good_result = json.loads(ppa_good.stdout)
        assert ppa_good_result["status"] == "pass", ppa_good_result
        subagent_workflows = SUBAGENT_WORKFLOWS.read_text(encoding="utf-8")
        assert "multi_agent_v1.spawn_agent" in subagent_workflows, subagent_workflows
        assert "agent_type" in subagent_workflows, subagent_workflows
        assert "native Codex collaboration workers" in subagent_workflows, subagent_workflows
        assert "SubagentStart" in subagent_workflows, subagent_workflows
        assert "generated tool output" in subagent_workflows, subagent_workflows
        assert "STATIC_HANDOFF_PASS" in subagent_workflows, subagent_workflows
        assert "git status --short -uall -- <ip>" in subagent_workflows, subagent_workflows
        assert "After user lock, main agent orchestrates" in subagent_workflows, subagent_workflows
        assert "oag_main_write_gate.py" in subagent_workflows, subagent_workflows
        assert "oag_exec_auto_research.py" in subagent_workflows, subagent_workflows
        assert "codex exec resume" in subagent_workflows, subagent_workflows
        assert "spawn_agent" in subagent_workflows and ".codex/runs/auto_research/" in subagent_workflows, subagent_workflows
        assert "oag-verification-strategy-agent" in subagent_workflows, subagent_workflows
        assert "ontology/verification_plan.yaml" in subagent_workflows, subagent_workflows
        assert "repo schema or existing writer" in subagent_workflows and "convention supports those fields" in subagent_workflows, subagent_workflows
        assert "scoreboard_rows.v1" in subagent_workflows, subagent_workflows
        assert "smoke_fallback_used=false" in subagent_workflows, subagent_workflows
        assert "scoreboard schema issue remains" in subagent_workflows, subagent_workflows
        skill_text = OAG_IP_WORKFLOW_SKILL.read_text(encoding="utf-8")
        agents_text = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        directive_text = OAG_MODE_DIRECTIVE.read_text(encoding="utf-8")
        assert "python3 scripts/" not in skill_text, skill_text
        assert "python3 .codex/scripts/oag_cli.py" in skill_text, skill_text
        assert "python3 .codex/scripts/oag_agent_catalog_check.py" in skill_text, skill_text
        assert "python3 .codex/scripts/oag_closure_check.py" in skill_text, skill_text
        assert "python3 .codex/scripts/oag_req_quality_check.py" in skill_text, skill_text
        assert "python3 .codex/scripts/oag_lock_readiness_check.py" in skill_text, skill_text
        assert "python3 .codex/scripts/oag_contract_strength_check.py" in skill_text, skill_text
        assert "python3 .codex/scripts/oag_authoring_packet_check.py" in skill_text, skill_text
        assert "python3 .codex/scripts/oag_trace_graph_check.py" in skill_text, skill_text
        assert "oag_deep_semantic_intake.py" in skill_text, skill_text
        assert "oag_decision_matrix_generate.py" in skill_text, skill_text
        assert "python3 .codex/scripts/oag_verification_plan_check.py" in skill_text, skill_text
        assert "oag_pyslang_lint.py" in skill_text, skill_text
        assert "Skill Router" in skill_text, skill_text
        assert "oag-deep-interview" in skill_text, skill_text
        assert "oag-deep-semantic-intake" in skill_text, skill_text
        assert "oag-decision-matrix" in skill_text, skill_text
        assert "oag-contract-projection" in skill_text, skill_text
        assert "oag-authoring-packet" in skill_text, skill_text
        assert "oag-wavefront" in skill_text, skill_text
        assert "oag_wavefront.py" in skill_text, skill_text
        assert "oag-evidence-closure" in skill_text, skill_text
        assert "SubagentStart" in skill_text, skill_text
        assert "generated tool output" in skill_text, skill_text
        assert "STATIC_HANDOFF_PASS" in skill_text, skill_text
        assert "New IP Intake Guard" in skill_text, skill_text
        assert "Scope Lock" in skill_text, skill_text
        assert "oag.lock_status" in skill_text, skill_text
        assert "No lock, no RTL" in skill_text, skill_text
        assert "After user lock, main agent orchestrates" in skill_text, skill_text
        assert "oag_main_write_gate.py" in skill_text, skill_text
        assert "short IP request" in skill_text, skill_text
        assert "Round 0 topology" in skill_text, skill_text
        assert "one-question-per-round discipline" in skill_text, skill_text
        assert "decision-matrix handoff" in skill_text, skill_text
        assert "one-sentence scope restatement" in skill_text, skill_text
        assert "do not enrich or rewrite `req/locked_truth.md`" in skill_text, skill_text
        assert "single-packet versus multi-packet" in skill_text, skill_text
        deep_interview_text = OAG_DEEP_INTERVIEW_SKILL.read_text(encoding="utf-8")
        assert "name: oag-deep-interview" in deep_interview_text, deep_interview_text
        assert "Phase 1: Round 0 Topology" in deep_interview_text, deep_interview_text
        assert "weakest score next" in deep_interview_text, deep_interview_text
        assert "highest-impact ambiguity" in deep_interview_text, deep_interview_text
        assert "Importance Ranking Protocol" in deep_interview_text, deep_interview_text
        assert "SSOT required gap" in deep_interview_text, deep_interview_text
        assert "oag_deep_interview_round.py rank" in deep_interview_text, deep_interview_text
        assert "spec document, or existing RTL" in deep_interview_text, deep_interview_text
        assert "RTL-readiness checklist" in deep_interview_text, deep_interview_text
        assert "If none of A-D fits, type a custom answer directly" in deep_interview_text, deep_interview_text
        assert "Option Set Protocol" in deep_interview_text, deep_interview_text
        assert "Options:" in deep_interview_text, deep_interview_text
        assert "(Recommended)" in deep_interview_text, deep_interview_text
        assert "Other / refine" in deep_interview_text, deep_interview_text
        assert "native question UI" in deep_interview_text, deep_interview_text
        assert "Ambiguity is bidirectional" in deep_interview_text, deep_interview_text
        assert "Decision Matrix Handoff" in deep_interview_text, deep_interview_text
        assert "oag_lock_readiness_check.py" in deep_interview_text, deep_interview_text
        assert "oag.draft" in deep_interview_text, deep_interview_text
        assert "one-sentence scope restatement" in deep_interview_text, deep_interview_text
        deep_interview_openai = (OAG_DEEP_INTERVIEW_SKILL.parent / "agents" / "openai.yaml").read_text(encoding="utf-8")
        assert "$oag-deep-interview" in deep_interview_openai, deep_interview_openai
        assert "one-question rounds" in deep_interview_openai, deep_interview_openai
        assert "RTL-ready draft OAG scope" in deep_interview_openai, deep_interview_openai
        deep_interview_ref = (OAG_DEEP_INTERVIEW_SKILL.parent / "references" / "scoring-and-output.md").read_text(encoding="utf-8")
        assert "ambiguity = 1 -" in deep_interview_ref, deep_interview_ref
        assert "Round Option Set Shape" in deep_interview_ref, deep_interview_ref
        assert "Recommendation policy" in deep_interview_ref, deep_interview_ref
        assert "Question selection policy" in deep_interview_ref, deep_interview_ref
        assert "Importance Ranking" in deep_interview_ref, deep_interview_ref
        assert "Document And RTL Inputs" in deep_interview_ref, deep_interview_ref
        assert "RTL Implementation Readiness" in deep_interview_ref, deep_interview_ref
        assert "type a custom answer directly" in deep_interview_ref, deep_interview_ref
        assert "researchable_fact" in deep_interview_ref, deep_interview_ref
        assert "Option History" in deep_interview_ref, deep_interview_ref
        assert "Final Draft Scope Template" in deep_interview_ref, deep_interview_ref
        round_template = subprocess.run(
            [
                sys.executable,
                str(DEEP_INTERVIEW_ROUND),
                "template",
                "--round",
                "2",
                "--component",
                "packet-filter",
                "--dimension",
                "constraints",
                "--ambiguity",
                "0.42",
                "--why-now",
                "The boundary is the weakest lock-blocking dimension.",
                "--question",
                "Which filtering boundary should v0 lock?",
            ],
            text=True,
            capture_output=True,
            check=False,
            cwd=ROOT,
        )
        assert round_template.returncode == 0, round_template.stderr or round_template.stdout
        round_doc = json.loads(round_template.stdout)
        assert round_doc["schema_version"] == "oag_deep_interview_round.v1", round_doc
        assert len(round_doc["options"]) == 4, round_doc
        assert sum(1 for option in round_doc["options"] if option.get("recommended")) == 1, round_doc
        round_validate = subprocess.run(
            [sys.executable, str(DEEP_INTERVIEW_ROUND), "validate", "--json-file", "-"],
            input=json.dumps(round_doc),
            text=True,
            capture_output=True,
            check=False,
            cwd=ROOT,
        )
        assert round_validate.returncode == 0, round_validate.stderr or round_validate.stdout
        assert json.loads(round_validate.stdout)["status"] == "pass", round_validate.stdout
        round_render = subprocess.run(
            [sys.executable, str(DEEP_INTERVIEW_ROUND), "render", "--json-file", "-"],
            input=json.dumps(round_doc),
            text=True,
            capture_output=True,
            check=False,
            cwd=ROOT,
        )
        assert round_render.returncode == 0, round_render.stderr or round_render.stdout
        assert "Question: Which filtering boundary should v0 lock?" in round_render.stdout, round_render.stdout
        assert "A. Recommended boundary (Recommended)" in round_render.stdout, round_render.stdout
        assert "type a custom answer directly" in round_render.stdout, round_render.stdout
        rtl_round_template = subprocess.run(
            [
                sys.executable,
                str(DEEP_INTERVIEW_ROUND),
                "template",
                "--round",
                "4",
                "--component",
                "datapath-control",
                "--dimension",
                "rtl_readiness",
                "--ambiguity",
                "0.31",
                "--why-now",
                "The draft is not yet implementable by an RTL agent.",
                "--question",
                "Is this behavior ready for RTL contract generation, or which cycle/interface detail is missing?",
            ],
            text=True,
            capture_output=True,
            check=False,
            cwd=ROOT,
        )
        assert rtl_round_template.returncode == 0, rtl_round_template.stderr or rtl_round_template.stdout
        rtl_round_doc = json.loads(rtl_round_template.stdout)
        assert rtl_round_doc["dimension"] == "rtl_readiness", rtl_round_doc
        assert rtl_round_doc["options"][0]["label"] == "Ready for RTL contract", rtl_round_doc
        bad_round = {**round_doc, "options": round_doc["options"][:2]}
        round_bad_validate = subprocess.run(
            [sys.executable, str(DEEP_INTERVIEW_ROUND), "validate", "--json-file", "-"],
            input=json.dumps(bad_round),
            text=True,
            capture_output=True,
            check=False,
            cwd=ROOT,
        )
        assert round_bad_validate.returncode != 0, round_bad_validate.stdout
        assert json.loads(round_bad_validate.stdout)["status"] == "fail", round_bad_validate.stdout
        rank_payload = {
            "schema_version": "oag_deep_interview_candidates.v1",
            "candidates": [
                {
                    "id": "C_PERF_BOUNDARY",
                    "component": "performance-contract",
                    "dimension": "constraints",
                    "question": "Should latency be hard, target-only, or out of v0 closure?",
                    "clarity": 0.2,
                    "lock_blocker": 3,
                    "ssot_required_gap": 3,
                    "downstream_fanout": 3,
                    "irreversibility": 2,
                    "proof_gap": 3,
                    "contradiction_risk": 1,
                    "user_value": 3,
                    "brownfield_risk": 1,
                    "upstream_dependency": 2,
                    "researchable_fact": 0,
                },
                {
                    "id": "C_STATUS_DETAIL",
                    "component": "status-reporting",
                    "dimension": "context",
                    "question": "Which existing status signal should carry this observation?",
                    "clarity": 0.45,
                    "lock_blocker": 1,
                    "ssot_required_gap": 1,
                    "downstream_fanout": 1,
                    "irreversibility": 1,
                    "proof_gap": 1,
                    "contradiction_risk": 0,
                    "user_value": 1,
                    "brownfield_risk": 1,
                    "upstream_dependency": 1,
                    "researchable_fact": 2,
                },
            ],
        }
        rank_proc = subprocess.run(
            [sys.executable, str(DEEP_INTERVIEW_ROUND), "rank", "--json-file", "-"],
            input=json.dumps(rank_payload),
            text=True,
            capture_output=True,
            check=False,
            cwd=ROOT,
        )
        assert rank_proc.returncode == 0, rank_proc.stderr or rank_proc.stdout
        rank_doc = json.loads(rank_proc.stdout)
        assert rank_doc["schema_version"] == "oag_deep_interview_rank.v1", rank_doc
        assert rank_doc["selected_id"] == "C_PERF_BOUNDARY", rank_doc
        assert "ambiguity_gap" in rank_doc["selected"]["score_breakdown"], rank_doc
        assert "researchable_fact" in rank_doc["selected"]["score_breakdown"], rank_doc
        intake_skill_text = OAG_DEEP_SEMANTIC_SKILL.read_text(encoding="utf-8")
        assert "Deep Interview Discipline" in intake_skill_text, intake_skill_text
        assert "Round 0 topology check" in intake_skill_text, intake_skill_text
        assert "weakest clarity dimension" in intake_skill_text, intake_skill_text
        assert "oag-decision-matrix" in intake_skill_text, intake_skill_text
        rule_index_text = OAG_RULE_INDEX.read_text(encoding="utf-8")
        assert "RULE-LOCK-003" in rule_index_text, rule_index_text
        assert "RULE-CONTRACT-AG-001" in rule_index_text, rule_index_text
        assert "RULE-PACKET-ROLE-001" in rule_index_text, rule_index_text
        assert "RULE-TRACE-001" in rule_index_text, rule_index_text
        assert "RULE-WAVE-001" in rule_index_text, rule_index_text
        assert "RULE-IPVER-001" in rule_index_text, rule_index_text
        assert "RULE-AUTO-001" in rule_index_text, rule_index_text
        assert "RULE-AUTO-004" in rule_index_text, rule_index_text
        decision_skill_text = OAG_DECISION_MATRIX_SKILL.read_text(encoding="utf-8")
        lock_preview_skill_text = OAG_LOCK_PREVIEW_FRAME_SKILL.read_text(encoding="utf-8")
        contract_skill_text = OAG_CONTRACT_PROJECTION_SKILL.read_text(encoding="utf-8")
        packet_skill_text = OAG_AUTHORING_PACKET_SKILL.read_text(encoding="utf-8")
        wavefront_skill_text = OAG_WAVEFRONT_SKILL.read_text(encoding="utf-8")
        ip_versioning_skill_text = OAG_IP_VERSIONING_SKILL.read_text(encoding="utf-8")
        feature_ipxact_policy_text = OAG_FEATURE_IPXACT_POLICY.read_text(encoding="utf-8")
        closure_skill_text = OAG_EVIDENCE_CLOSURE_SKILL.read_text(encoding="utf-8")
        assert "oag_decision_matrix_generate.py" in decision_skill_text, decision_skill_text
        assert "lock_required: true" in decision_skill_text, decision_skill_text
        assert "oag_lock_preview_frame.py" in lock_preview_skill_text, lock_preview_skill_text
        assert "verbatim" in lock_preview_skill_text, lock_preview_skill_text
        assert "SHA-256" in lock_preview_skill_text, lock_preview_skill_text
        assert "assume" in contract_skill_text and "guarantee" in contract_skill_text, contract_skill_text
        assert "oag_contract_strength_check.py" in contract_skill_text, contract_skill_text
        assert "rtl__*.json" in packet_skill_text and "tb__*.json" in packet_skill_text, packet_skill_text
        assert "oag_authoring_packet_check.py" in packet_skill_text, packet_skill_text
        assert "dependency" in wavefront_skill_text and "ownership" in wavefront_skill_text, wavefront_skill_text
        assert "oag_wavefront.py" in wavefront_skill_text, wavefront_skill_text
        assert "spawn" in wavefront_skill_text and "whole ready wave" in wavefront_skill_text, wavefront_skill_text
        assert "oag_ip_version_check.py" in ip_versioning_skill_text, ip_versioning_skill_text
        assert "oag_ip_git.py" in ip_versioning_skill_text, ip_versioning_skill_text
        assert "checkpoint" in ip_versioning_skill_text, ip_versioning_skill_text
        assert "PowerShell" in ip_versioning_skill_text, ip_versioning_skill_text
        assert "IP-local" in ip_versioning_skill_text, ip_versioning_skill_text
        assert "Feature -> Requirement" in feature_ipxact_policy_text, feature_ipxact_policy_text
        assert "ontology/features.yaml" in feature_ipxact_policy_text, feature_ipxact_policy_text
        assert "ontology/ipxact_projection.yaml" in feature_ipxact_policy_text, feature_ipxact_policy_text
        assert "IP-XACT is not the behavior oracle" in feature_ipxact_policy_text, feature_ipxact_policy_text
        assert "oag_closure_check.py" in closure_skill_text, closure_skill_text
        assert "claim_complete" in closure_skill_text, closure_skill_text
        assert "Short IP requests are not implementation authorization" in agents_text, agents_text
        assert "scope_lock.json" in agents_text, agents_text
        assert "No lock, no RTL" in agents_text, agents_text
        assert "oag_req_quality_check.py" in agents_text, agents_text
        assert "req/source_claims.yaml" in agents_text, agents_text
        assert "req/ambiguity_register.yaml" in agents_text, agents_text
        assert "oag_lock_readiness_check.py" in agents_text, agents_text
        assert "oag_contract_strength_check.py" in agents_text, agents_text
        assert "oag_authoring_packet_check.py" in agents_text, agents_text
        assert "oag_wavefront.py" in agents_text, agents_text
        assert "oag_ip_version_check.py" in agents_text, agents_text
        assert "oag_ip_git.py" in agents_text, agents_text
        assert "feature-ipxact-policy.md" in agents_text, agents_text
        assert "lock preview" in agents_text, agents_text
        assert "oag_lock_preview_frame.py" in agents_text, agents_text
        assert "verbatim source panels" in agents_text, agents_text
        assert "oag_trace_graph_check.py" in agents_text, agents_text
        assert "oag_deep_semantic_intake.py" in agents_text, agents_text
        assert "oag_decision_matrix_generate.py" in agents_text, agents_text
        assert "oag_verification_plan_check.py" in agents_text, agents_text
        assert "ontology/verification_plan.yaml" in agents_text, agents_text
        assert "After user lock, main agent orchestrates" in agents_text, agents_text
        assert "oag_main_write_gate.py" in agents_text, agents_text
        assert "oag_exec_auto_research.py" in agents_text, agents_text
        assert "A short IP request is requirement-interview input" in directive_text, directive_text
        assert "Round 0 topology confirmation" in directive_text, directive_text
        assert "one-sentence scope restatement" in directive_text, directive_text
        assert "oag_ip_git.py" in directive_text, directive_text
        assert "PowerShell-compatible" in directive_text, directive_text
        assert "lock preview" in directive_text, directive_text
        assert "oag_lock_preview_frame.py" in directive_text, directive_text
        assert "verbatim panels" in directive_text, directive_text
        assert "feature-ipxact-policy.md" in directive_text, directive_text
        assert "IP-XACT" in directive_text, directive_text
        assert "oag.lock_status" in directive_text, directive_text
        assert "No lock, no RTL" in directive_text, directive_text
        assert "oag_req_quality_check.py" in directive_text, directive_text
        assert "req/source_claims.yaml" in directive_text, directive_text
        assert "req/ambiguity_register.yaml" in directive_text, directive_text
        assert "oag_lock_readiness_check.py" in directive_text, directive_text
        assert "oag_contract_strength_check.py" in directive_text, directive_text
        assert "oag_authoring_packet_check.py" in directive_text, directive_text
        assert "oag_ip_version_check.py" in directive_text, directive_text
        assert "oag_trace_graph_check.py" in directive_text, directive_text
        assert "oag_deep_semantic_intake.py" in directive_text, directive_text
        assert "oag_decision_matrix_generate.py" in directive_text, directive_text
        assert "oag_verification_plan_check.py" in directive_text, directive_text
        assert "ontology/verification_plan.yaml" in directive_text, directive_text
        assert "ontology/generated/authoring_packets" in directive_text, directive_text
        assert "rtl__*.json" in directive_text, directive_text
        assert "tb__*.json" in directive_text, directive_text
        assert "After user lock, main agent orchestrates" in directive_text, directive_text
        assert "oag_main_write_gate.py" in directive_text, directive_text
        assert "find .. -name AGENTS.md" in skill_text, skill_text
        assert "repo schema or existing writer" in skill_text and "convention supports those fields" in skill_text, skill_text
        assert "scenario_source=ontology/verification_plan.yaml" in skill_text, skill_text
        assert "scoreboard schema issue remains" in skill_text, skill_text
        assert "Do not run a Python" in subagent_workflows and "manual role-play substitute" in subagent_workflows, subagent_workflows
        assert "first attempt a minimal explicit" in subagent_workflows and "native spawn" in subagent_workflows, subagent_workflows
        assert "observed" in subagent_workflows and "native-spawn blocker" in subagent_workflows, subagent_workflows
        assert "spawn the whole ready wave as one native subagent batch" in subagent_workflows, subagent_workflows
        assert "BLOCKED: native Codex subagent unavailable in this surface" not in subagent_workflows, subagent_workflows
        config_text = (ROOT / "config.toml").read_text(encoding="utf-8")
        user_home_prefix = "/" + "Users/"
        assert user_home_prefix not in config_text, config_text
        assert 'multi_agent = true' in config_text, config_text
        assert 'child_agents_md = true' in config_text, config_text
        assert 'enabled = false' in config_text, config_text
        assert 'max_concurrent_threads_per_session = 1000' in config_text, config_text
        assert 'max_depth = 1' in config_text, config_text
        assert "mcp_servers" not in config_text, config_text

        dry_run_root = Path(tmp) / "exec_auto_research_runs"
        exec_auto_research = subprocess.run(
            [
                sys.executable,
                str(EXEC_AUTO_RESEARCH),
                "--ip-dir",
                "timer_ip",
                "--objective",
                "dry-run wrapper contract check",
                "--run-root",
                str(dry_run_root),
                "--dry-run",
                "--json",
            ],
            text=True,
            capture_output=True,
            check=False,
            cwd=PROJECT_ROOT,
        )
        assert exec_auto_research.returncode == 0, exec_auto_research.stderr or exec_auto_research.stdout
        exec_auto_research_result = json.loads(exec_auto_research.stdout)
        assert exec_auto_research_result["status"] == "dry_run", exec_auto_research_result
        assert exec_auto_research_result["dry_run"] is True, exec_auto_research_result
        assert exec_auto_research_result["prompt_sha256"], exec_auto_research_result
        prompt_text = Path(exec_auto_research_result["prompt_path"]).read_text(encoding="utf-8")
        assert "codex exec" in " ".join(exec_auto_research_result["command_preview"]), exec_auto_research_result
        assert "spawn_agent" in prompt_text, prompt_text
        assert "Use a native Codex subagent. Spawn one bounded research subagent" in prompt_text, prompt_text
        assert "Do not run parent-side shell commands before the native spawn attempt" in prompt_text, prompt_text
        assert "Product root:" in prompt_text, prompt_text
        assert "from the product root, not from inside the IP directory" in prompt_text, prompt_text
        assert "Do not decide native-spawn availability from the visible callable tool namespace alone" in prompt_text, prompt_text
        assert "built-in explorer-style native subagent" in prompt_text, prompt_text
        assert "not an OAG custom/write-capable role" in prompt_text, prompt_text
        assert "FINAL_AUTO_RESEARCH_SUMMARY" in prompt_text, prompt_text
        gitignore_path = PROJECT_ROOT / ".gitignore"
        if gitignore_path.is_file():
            gitignore_text = gitignore_path.read_text(encoding="utf-8")
            assert ".codex/runs/" in gitignore_text, gitignore_text

        codex_home = Path(tmp) / "codex_home"
        codex_home.mkdir(parents=True, exist_ok=True)
        user_config = codex_home / "config.toml"
        legacy_oag_mcp_server = "ontology" + "-ip-agent-oag"
        legacy_oag_mcp_path = "/old/" + "ontology" + "_ip_agent/.codex/scripts/oag_mcp_server.py"
        user_config.write_text(
            "\n".join(
                [
                    "[features]",
                    "multi_agent = false",
                    "child_agents_md = false",
                    "hooks = false",
                    "multi_agent_v2 = true",
                    "",
                    "[features.multi_agent_v2]",
                    "enabled = true",
                    "max_concurrent_threads_per_session = 1",
                    "",
                    "[agents]",
                    "max_depth = 0",
                    "",
                    "[mcp_servers.ip-dev-agent-oag]",
                    'command = "python3"',
                    'args = [".codex/scripts/oag_mcp_server.py"]',
                    "",
                    "[mcp_servers.ip-dev-agent-oag.env]",
                    'OAG_ACTOR_SURFACE = "codex-mcp"',
                    "",
                    f"[mcp_servers.{legacy_oag_mcp_server}]",
                    'command = "python3"',
                    f'args = ["{legacy_oag_mcp_path}"]',
                    "",
                    "[mcp_servers.node_repl]",
                    'command = "/Applications/Codex.app/Contents/Resources/cua_node/bin/node_repl"',
                    "",
                    '[plugins."computer-use@openai-bundled"]',
                    "enabled = true",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        session_migration = session_start_hook({"hook_event_name": "SessionStart"}, {"CODEX_HOME": str(codex_home)})
        assert session_migration.returncode == 0, session_migration.stderr or session_migration.stdout
        migrated_config = user_config.read_text(encoding="utf-8")
        assert "multi_agent = true" in migrated_config, migrated_config
        assert "child_agents_md = true" in migrated_config, migrated_config
        assert "hooks = true" in migrated_config, migrated_config
        assert "plugins = true" in migrated_config, migrated_config
        assert "plugin_hooks = true" in migrated_config, migrated_config
        assert "multi_agent_v2 = true" not in migrated_config, migrated_config
        assert "enabled = false" in migrated_config, migrated_config
        assert "max_concurrent_threads_per_session = 1000" in migrated_config, migrated_config
        assert "max_depth = 1" in migrated_config, migrated_config
        assert "openai/codex#26753" in migrated_config, migrated_config
        assert "ip-dev-agent-oag" not in migrated_config, migrated_config
        assert legacy_oag_mcp_server not in migrated_config, migrated_config
        assert "oag_mcp_server.py" not in migrated_config, migrated_config
        assert "[mcp_servers.node_repl]" in migrated_config, migrated_config
        assert '[plugins."computer-use@openai-bundled"]\nenabled = true' in migrated_config, migrated_config
        assert "OAG CODEX CONFIG MIGRATION" in hook_context(session_migration), session_migration.stdout

        session_idempotent = session_start_hook({"hook_event_name": "SessionStart"}, {"CODEX_HOME": str(codex_home)})
        assert session_idempotent.returncode == 0, session_idempotent.stderr or session_idempotent.stdout
        assert session_idempotent.stdout == "", session_idempotent.stdout
        lean_doctor = subprocess.run(
            [
                sys.executable,
                str(CODEX_CONFIG_DOCTOR),
                "--config",
                str(user_config),
                "--include-omo-plugin-features",
                "--lean-subagent-runtime",
                "--apply",
                "--json",
            ],
            text=True,
            capture_output=True,
            check=False,
            cwd=ROOT,
        )
        assert lean_doctor.returncode == 0, lean_doctor.stderr or lean_doctor.stdout
        lean_result = json.loads(lean_doctor.stdout)
        assert lean_result["status"] == "pass", lean_result
        lean_config = user_config.read_text(encoding="utf-8")
        assert '[plugins."computer-use@openai-bundled"]\nenabled = false' in lean_config, lean_config
        assert '[plugins."computer-use@openai-bundled".mcp_servers.computer-use]\nenabled = false' in lean_config, lean_config

        hook_metric_dir = Path(tmp) / "hook_metric_outputs"
        hook_metric_dir.mkdir(parents=True, exist_ok=True)
        (hook_metric_dir / "mcp.txt").write_text(
            "Starting MCP servers (2/3): computer-use\n/mcp\ncomputer-use\n",
            encoding="utf-8",
        )
        debug_metrics = subprocess.run(
            [
                sys.executable,
                str(DEBUG_EVAL_METRICS),
                "--hook-output",
                str(hook_metric_dir),
                "--json",
            ],
            text=True,
            capture_output=True,
            check=False,
            cwd=ROOT,
        )
        assert debug_metrics.returncode == 0, debug_metrics.stderr or debug_metrics.stdout
        debug_payload = json.loads(debug_metrics.stdout)
        debug_codes = {item["code"] for item in debug_payload["findings"]}
        assert "COMPUTER_USE_MCP_SEEN" in debug_codes, debug_payload
        assert "MCP_STARTUP_SEEN" in debug_codes, debug_payload

        trigger_silent = oag_mode_trigger({"prompt": "rtl work"})
        assert trigger_silent.returncode == 0, trigger_silent.stderr or trigger_silent.stdout
        assert trigger_silent.stdout == "", trigger_silent.stdout
        for prompt in (
            "ipdev use subagent for timer",
            "auto research timer",
            "subagent for timer",
            "signoff timer",
            "rocev timer",
            "OAG 명시 안해도 oag ip workflow가 enable 되던데?",
            "why does OAG mode activate here?",
            "please use oag later",
        ):
            non_oag_trigger = oag_mode_trigger({"prompt": prompt})
            assert non_oag_trigger.returncode == 0, non_oag_trigger.stderr or non_oag_trigger.stdout
            assert non_oag_trigger.stdout == "", non_oag_trigger.stdout
        guard_silent = native_subagent_guard({"prompt": "auto research timer"})
        assert guard_silent.returncode == 0, guard_silent.stderr or guard_silent.stdout
        assert guard_silent.stdout == "", guard_silent.stdout
        for prompt in (
            "이러 왜 이렇게 subagent iteration 이 많아? 잘되게 fix 좀",
            "why are there so many subagent iterations?",
            "fix the subagent guard trigger loop",
            "subagent iteration count is too high; reduce it",
            "# Files mentioned by the user:\n\n## › tb를 cocotb가 아니라 uvm 기반으로 재작성하자. use all parrele sub agent • UserPromptSubmit …: /tmp/pasted-text.txt\n\n## My request for Codex:\n 이제 잘 되는가?",
        ):
            meta_guard = native_subagent_guard({"prompt": prompt})
            assert meta_guard.returncode == 0, meta_guard.stderr or meta_guard.stdout
            assert meta_guard.stdout == "", meta_guard.stdout
        guard_from_request_section = native_subagent_guard(
            {
                "prompt": "# Files mentioned by the user:\n\n"
                "## old discussion without commands: /tmp/pasted-text.txt\n\n"
                "## My request for Codex:\n use all parallel sub agents for tb rewrite"
            }
        )
        assert guard_from_request_section.returncode == 0, guard_from_request_section.stderr or guard_from_request_section.stdout
        assert "NATIVE CODEX SUBAGENT GUARD" in hook_context(guard_from_request_section), guard_from_request_section.stdout
        guard_on = native_subagent_guard({"prompt": "Use sub agent to make req in detail"})
        assert guard_on.returncode == 0, guard_on.stderr or guard_on.stdout
        guard_context = hook_context(guard_on)
        assert "NATIVE CODEX SUBAGENT GUARD" in guard_context, guard_on.stdout
        assert "first attempt a minimal read-only native spawn" in guard_context, guard_on.stdout
        assert "Do not answer BLOCKED or report an observed native-spawn blocker before an actual `spawn_agent` attempt fails" in guard_context, guard_on.stdout
        assert "Do not decide native-spawn availability from the visible callable tool namespace alone" in guard_context, guard_on.stdout
        assert "explicitly request the native `spawn_agent` collaboration event" in guard_context, guard_on.stdout
        assert "A wait timeout only means no new child update arrived" in guard_context, guard_on.stdout
        assert "at least three native wait cycles" in guard_context, guard_on.stdout
        assert "targeted status/heartbeat request" in guard_context, guard_on.stdout
        assert "spawn the whole ready wave as a native subagent batch" in guard_context, guard_on.stdout
        assert "TB generation should be sharded" in guard_context, guard_on.stdout
        assert "Do not run `omo run --agent`" in guard_context, guard_on.stdout
        assert "observed native-spawn blocker" in guard_context, guard_on.stdout
        assert "BLOCKED: native Codex subagent unavailable in this surface" not in guard_context, guard_on.stdout
        assert "OAG MODE ENABLED!" not in guard_context, guard_on.stdout
        trigger_on = oag_mode_trigger({"prompt": "oag use subagent for timer"})
        assert trigger_on.returncode == 0, trigger_on.stderr or trigger_on.stdout
        trigger_context = hook_context(trigger_on)
        assert "OAG MODE ENABLED!" in trigger_context, trigger_on.stdout
        assert "Requirement -> Obligation -> Contract -> Evidence -> Validation -> Decision" in trigger_context, trigger_on.stdout
        assert "short IP request is requirement-interview input" in trigger_context, trigger_on.stdout
        assert "multi_agent_v1.spawn_agent" in trigger_context, trigger_on.stdout
        assert "oag.lock_status" in trigger_context, trigger_on.stdout
        assert "No lock, no RTL" in trigger_context, trigger_on.stdout
        assert "record_decision=true" in trigger_context, trigger_on.stdout
        trigger_colon = oag_mode_trigger({"prompt": "oag: inspect timer"})
        assert trigger_colon.returncode == 0, trigger_colon.stderr or trigger_colon.stdout
        assert "OAG MODE ENABLED!" in hook_context(trigger_colon), trigger_colon.stdout

        deep_guard_silent = deep_interview_prompt_guard({"prompt": "please run a normal lint check"})
        assert deep_guard_silent.returncode == 0, deep_guard_silent.stderr or deep_guard_silent.stdout
        assert deep_guard_silent.stdout == "", deep_guard_silent.stdout
        deep_guard_on = deep_interview_prompt_guard({"prompt": "Use oag-deep-interview for this ambiguous IP requirement"})
        assert deep_guard_on.returncode == 0, deep_guard_on.stderr or deep_guard_on.stdout
        deep_guard_context = hook_context(deep_guard_on)
        assert "OAG DEEP INTERVIEW PROMPT GUARD" in deep_guard_context, deep_guard_on.stdout
        assert "Ask exactly one user-facing question" in deep_guard_context, deep_guard_on.stdout
        assert "Rank candidates by lock blocker" in deep_guard_context, deep_guard_on.stdout
        assert "documents/specs/RTL" in deep_guard_context, deep_guard_on.stdout
        assert "four concise candidate answers" in deep_guard_context, deep_guard_on.stdout
        assert "Other / refine" in deep_guard_context, deep_guard_on.stdout
        assert "custom answer directly" in deep_guard_context, deep_guard_on.stdout
        assert "RTL/TB authoring packets" in deep_guard_context, deep_guard_on.stdout
        assert "decision matrix" in deep_guard_context, deep_guard_on.stdout

        hook_cwd = Path(tmp) / "subagent_hook_project"
        hook_cwd.mkdir(parents=True, exist_ok=True)
        start_cache = Path(tmp) / "subagent_start_events.jsonl"
        start_payload = {
            "hook_event_name": "SubagentStart",
            "agent_type": "oag-rtl-implementation-agent",
            "agent_id": "rtl-worker-1",
            "session_id": "smoke-session",
            "cwd": str(hook_cwd),
            "model": "gpt-5.5",
            "permission_mode": "default",
        }
        start_hook = subagent_start(start_payload, {"OAG_SUBAGENT_START_CACHE": str(start_cache)})
        assert start_hook.returncode == 0, start_hook.stderr or start_hook.stdout
        start_context = hook_context(start_hook)
        assert "OAG SUBAGENT START CONTRACT" in start_context, start_hook.stdout
        assert "STATIC_HANDOFF_PASS" in start_context, start_hook.stdout
        assert "Short IP intake guard" in start_context, start_hook.stdout
        assert "single-packet versus multi-packet" in start_context, start_hook.stdout
        assert "Scope lock guard" in start_context, start_hook.stdout
        assert "scope_lock.json state=locked" in start_context, start_hook.stdout
        assert "OAG_EVIDENCE_RECORDED" in start_context, start_hook.stdout
        assert start_cache.is_file(), start_cache
        start_event = json.loads(start_cache.read_text(encoding="utf-8").splitlines()[-1])
        assert start_event["schema_version"] == "oag_subagent_start_event.v1", start_event
        assert start_event["agent_type"] == "oag-rtl-implementation-agent", start_event
        transcript_path = Path(tmp) / "subagent_transcript.txt"
        transcript_path.write_text("normal transcript\n", encoding="utf-8")
        invalid_payload = {
            "hook_event_name": "SubagentStop",
            "agent_type": "oag-custom-worker",
            "agent_id": "worker-1",
            "session_id": "smoke-session",
            "cwd": str(hook_cwd),
            "transcript_path": str(transcript_path),
            "model": "gpt-5.5",
            "permission_mode": "default",
            "stop_hook_active": False,
            "last_assistant_message": "done without receipt",
        }
        invalid_gate = subagent_gate(invalid_payload, {"OAG_SUBAGENT_GATE_CACHE": str(Path(tmp) / "subagent_gate_cache.json")})
        assert invalid_gate.returncode == 0, invalid_gate.stderr or invalid_gate.stdout
        invalid_gate_payload = json.loads(invalid_gate.stdout)
        assert invalid_gate_payload["decision"] == "block", invalid_gate_payload
        assert "OAG_EVIDENCE_RECORDED" in invalid_gate_payload["reason"], invalid_gate_payload
        diagnostic_receipt = hook_cwd / "knowledge" / "subagents" / "pre_dispatch_blocked.json"
        diagnostic_receipt.parent.mkdir(parents=True, exist_ok=True)
        diagnostic_payload_body = {
            "schema_version": "oag_subagent_diagnostic_receipt.v1",
            "product_name": "IP Dev Agent",
            "internal_gateway": "Ontology Agent Gateway",
            "role_name": "oag-custom-worker",
            "shard_scope": "unassigned",
            "stage": "pre_dispatch",
            "status": "BLOCKED",
            "blocker_class": "missing_dispatch",
            "blockers": ["assignment did not include dispatch_id or dispatch_path"],
            "changed_paths": [],
            "generated_side_effects": [],
            "evidence_outputs": [],
            "diagnostic_only": True,
            "covers_writes": False,
            "dispatch_verified": False,
            "implementation_evidence": False,
            "may_claim_complete": False,
            "created_at": "2026-01-01T00:00:00Z",
        }
        diagnostic_receipt.write_text(json.dumps(diagnostic_payload_body, sort_keys=True) + "\n", encoding="utf-8")
        diagnostic_schema_validation = run_validate_json(
            ROOT / "schemas" / "oag_subagent_diagnostic_receipt.schema.json",
            diagnostic_receipt,
        )
        assert diagnostic_schema_validation.returncode == 0, diagnostic_schema_validation.stderr or diagnostic_schema_validation.stdout
        diagnostic_payload = {
            **invalid_payload,
            "last_assistant_message": "OAG_EVIDENCE_RECORDED: knowledge/subagents/pre_dispatch_blocked.json",
        }
        diagnostic_gate = subagent_gate(
            diagnostic_payload,
            {"OAG_SUBAGENT_GATE_CACHE": str(Path(tmp) / "subagent_gate_cache_diagnostic.json")},
        )
        assert diagnostic_gate.returncode == 0, diagnostic_gate.stderr or diagnostic_gate.stdout
        assert diagnostic_gate.stdout == "", diagnostic_gate.stdout
        diagnostic_receipt.write_text(
            json.dumps({**diagnostic_payload_body, "status": "HANDOFF_PASS"}, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        diagnostic_handoff_gate = subagent_gate(
            diagnostic_payload,
            {"OAG_SUBAGENT_GATE_CACHE": str(Path(tmp) / "subagent_gate_cache_diagnostic_handoff.json")},
        )
        assert diagnostic_handoff_gate.returncode == 0, diagnostic_handoff_gate.stderr or diagnostic_handoff_gate.stdout
        diagnostic_handoff_payload = json.loads(diagnostic_handoff_gate.stdout)
        assert diagnostic_handoff_payload["decision"] == "block", diagnostic_handoff_payload
        assert "diagnostic receipt.status" in diagnostic_handoff_payload["reason"], diagnostic_handoff_payload
        diagnostic_receipt.write_text(
            json.dumps(
                {**diagnostic_payload_body, "changed_paths": ["smoke_ip/rtl/smoke.sv"]},
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        diagnostic_changed_gate = subagent_gate(
            diagnostic_payload,
            {"OAG_SUBAGENT_GATE_CACHE": str(Path(tmp) / "subagent_gate_cache_diagnostic_changed.json")},
        )
        assert diagnostic_changed_gate.returncode == 0, diagnostic_changed_gate.stderr or diagnostic_changed_gate.stdout
        diagnostic_changed_payload = json.loads(diagnostic_changed_gate.stdout)
        assert diagnostic_changed_payload["decision"] == "block", diagnostic_changed_payload
        assert "changed_paths must be empty" in diagnostic_changed_payload["reason"], diagnostic_changed_payload
        diagnostic_receipt.write_text(
            json.dumps(
                {**diagnostic_payload_body, "evidence_outputs": ["knowledge/subagents/pre_dispatch_blocked.json"]},
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        diagnostic_evidence_gate = subagent_gate(
            diagnostic_payload,
            {"OAG_SUBAGENT_GATE_CACHE": str(Path(tmp) / "subagent_gate_cache_diagnostic_evidence.json")},
        )
        assert diagnostic_evidence_gate.returncode == 0, diagnostic_evidence_gate.stderr or diagnostic_evidence_gate.stdout
        diagnostic_evidence_payload = json.loads(diagnostic_evidence_gate.stdout)
        assert diagnostic_evidence_payload["decision"] == "block", diagnostic_evidence_payload
        assert "evidence_outputs must be empty" in diagnostic_evidence_payload["reason"], diagnostic_evidence_payload
        diagnostic_receipt.write_text(
            json.dumps({**diagnostic_payload_body, "dispatch_path": "smoke_ip/knowledge/dispatches/fake.json"}, sort_keys=True)
            + "\n",
            encoding="utf-8",
        )
        diagnostic_dispatch_gate = subagent_gate(
            diagnostic_payload,
            {"OAG_SUBAGENT_GATE_CACHE": str(Path(tmp) / "subagent_gate_cache_diagnostic_dispatch.json")},
        )
        assert diagnostic_dispatch_gate.returncode == 0, diagnostic_dispatch_gate.stderr or diagnostic_dispatch_gate.stdout
        diagnostic_dispatch_payload = json.loads(diagnostic_dispatch_gate.stdout)
        assert diagnostic_dispatch_payload["decision"] == "block", diagnostic_dispatch_payload
        assert "dispatch_path is not allowed" in diagnostic_dispatch_payload["reason"], diagnostic_dispatch_payload
        diagnostic_receipt.write_text(
            json.dumps({**diagnostic_payload_body, "blockers": "assignment did not include dispatch_id"}, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        diagnostic_blockers_gate = subagent_gate(
            diagnostic_payload,
            {"OAG_SUBAGENT_GATE_CACHE": str(Path(tmp) / "subagent_gate_cache_diagnostic_blockers.json")},
        )
        assert diagnostic_blockers_gate.returncode == 0, diagnostic_blockers_gate.stderr or diagnostic_blockers_gate.stdout
        diagnostic_blockers_payload = json.loads(diagnostic_blockers_gate.stdout)
        assert diagnostic_blockers_payload["decision"] == "block", diagnostic_blockers_payload
        assert "blockers must be a non-empty list" in diagnostic_blockers_payload["reason"], diagnostic_blockers_payload
        subprocess.run(["git", "init"], cwd=hook_cwd, text=True, capture_output=True, check=True)
        unlocked_hook_ip = hook_cwd / "unlocked_smoke_ip"
        (unlocked_hook_ip / "rtl").mkdir(parents=True, exist_ok=True)
        (unlocked_hook_ip / "knowledge" / "subagents").mkdir(parents=True, exist_ok=True)
        unlocked_dispatch = run_dispatch(
            "create",
            "--ip-dir",
            str(unlocked_hook_ip),
            "--agent-type",
            "oag-custom-worker",
            "--role-kind",
            "custom",
            "--stage",
            "rtl",
            "--allowed-write-path",
            str(unlocked_hook_ip / "rtl" / "smoke.sv"),
            "--receipt-path",
            str(unlocked_hook_ip / "knowledge" / "subagents" / "smoke.json"),
            "--json",
            project_root=hook_cwd,
        )
        assert unlocked_dispatch.returncode != 0, unlocked_dispatch.stdout
        assert "scope lock required" in (unlocked_dispatch.stderr + unlocked_dispatch.stdout), unlocked_dispatch.stderr or unlocked_dispatch.stdout
        main_gate_ip = hook_cwd / "main_gate_ip"
        (main_gate_ip / "ontology").mkdir(parents=True, exist_ok=True)
        (main_gate_ip / "rtl").mkdir(parents=True, exist_ok=True)
        (main_gate_ip / "ontology" / "scope_lock.json").write_text(
            json.dumps(
                {
                    "schema_version": "oag_scope_lock.v1",
                    "ip": "main_gate_ip",
                    "state": "locked",
                    "summary": "Smoke scope is locked before implementation.",
                    "confirmed_scope": ["main write gate smoke"],
                }
            )
            + "\n",
            encoding="utf-8",
        )
        (main_gate_ip / "rtl" / "direct_main.sv").write_text("module direct_main; endmodule\n", encoding="utf-8")
        main_gate_blocked = run_main_write_gate(main_gate_ip, project_root=hook_cwd)
        assert main_gate_blocked.returncode != 0, main_gate_blocked.stdout
        main_gate_payload = json.loads(main_gate_blocked.stdout)
        assert main_gate_payload["status"] == "fail", main_gate_payload
        assert main_gate_payload["issues"][0]["code"] == "MAIN_AGENT_WRITE_WITHOUT_SUBAGENT", main_gate_payload
        main_gate_diagnostic = main_gate_ip / "knowledge" / "subagents" / "diagnostic_only.json"
        main_gate_diagnostic.parent.mkdir(parents=True, exist_ok=True)
        main_gate_diagnostic.write_text(
            json.dumps({**diagnostic_payload_body, "shard_scope": "main-write-gate"}, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        main_gate_still_blocked = run_main_write_gate(main_gate_ip, project_root=hook_cwd)
        assert main_gate_still_blocked.returncode != 0, main_gate_still_blocked.stdout
        main_gate_still_blocked_payload = json.loads(main_gate_still_blocked.stdout)
        still_blocked_codes = {item["code"] for item in main_gate_still_blocked_payload["issues"]}
        assert "MAIN_AGENT_WRITE_WITHOUT_SUBAGENT" in still_blocked_codes, main_gate_still_blocked_payload
        assert "DIAGNOSTIC_RECEIPT_NOT_WRITE_COVERAGE" in still_blocked_codes, main_gate_still_blocked_payload
        assert main_gate_still_blocked_payload["results"][0]["diagnostic_receipts"], main_gate_still_blocked_payload
        stop_gate_blocked = stop_gate({"ip_dir": str(main_gate_ip)}, {"OAG_PROJECT_ROOT": str(hook_cwd)})
        assert stop_gate_blocked.returncode == 0, stop_gate_blocked.stderr or stop_gate_blocked.stdout
        stop_gate_payload = json.loads(stop_gate_blocked.stdout)
        assert stop_gate_payload["decision"] == "block", stop_gate_payload
        assert "locked implementation write requires native subagent evidence" in stop_gate_payload["reason"], stop_gate_payload
        hook_ip = hook_cwd / "smoke_ip"
        (hook_ip / "rtl").mkdir(parents=True, exist_ok=True)
        (hook_ip / "ontology").mkdir(parents=True, exist_ok=True)
        (hook_ip / "knowledge" / "subagents").mkdir(parents=True, exist_ok=True)
        (hook_ip / "ontology" / "scope_lock.json").write_text(
            json.dumps(
                {
                    "schema_version": "oag_scope_lock.v1",
                    "ip": "smoke_ip",
                    "state": "locked",
                    "summary": "Smoke dispatch scope is locked.",
                    "confirmed_scope": ["rtl smoke dispatch"],
                }
            )
            + "\n",
            encoding="utf-8",
        )
        write_minimal_rtl_dispatch_readiness(
            hook_ip,
            module_id="smoke",
            rtl_file="rtl/smoke.sv",
            contract_id="CONTRACT_SMOKE",
            obligation_id="OBL_SMOKE",
        )
        dispatch_create_args = (
            "create",
            "--ip-dir",
            str(hook_ip),
            "--agent-type",
            "oag-custom-worker",
            "--role-kind",
            "custom",
            "--stage",
            "rtl",
            "--owned-obligation",
            "OBL_SMOKE",
            "--contract",
            "CONTRACT_SMOKE",
            "--allowed-write-path",
            str(hook_ip / "rtl" / "smoke.sv"),
            "--allowed-write-path",
            str(hook_ip / "knowledge" / "subagents"),
            "--allowed-tool-side-effect",
            str(hook_ip / "ontology" / "generated"),
            "--allowed-tool-side-effect",
            str(hook_ip / "ontology" / "runs" / "RUN_DISPATCH_SMOKE" / "ownership_locks.json"),
            "--receipt-path",
            str(hook_ip / "knowledge" / "subagents" / "smoke.json"),
            "--wavefront-run-id",
            "RUN_DISPATCH_SMOKE",
            "--task-id",
            "RTL_SMOKE_TASK",
            "--ownership-mode",
            "exclusive_file",
            "--json",
        )
        write_task5_wavefront_state(hook_ip, "RUN_DISPATCH_SMOKE", "RTL_SMOKE_TASK", "PENDING_DISPATCH_ID", "exclusive_file", "claimed")
        dispatch_create = run_dispatch(*dispatch_create_args, project_root=hook_cwd)
        assert dispatch_create.returncode == 0, dispatch_create.stderr or dispatch_create.stdout
        dispatch_result = json.loads(dispatch_create.stdout)
        dispatch = dispatch_result["dispatch"]
        assert dispatch["schema_version"] == "oag_dispatch.v1", dispatch
        assert "prompt_contract" in dispatch and "dispatch_id" in dispatch["prompt_contract"], dispatch
        assert dispatch["wavefront_run_id"] == "RUN_DISPATCH_SMOKE", dispatch
        assert dispatch["task_id"] == "RTL_SMOKE_TASK", dispatch
        assert "wavefront_run_id" in dispatch["prompt_contract"], dispatch
        assert "Subagent implementation boundary:" in dispatch["prompt_contract"], dispatch["prompt_contract"]
        assert "Do not create a new dispatch" in dispatch["prompt_contract"], dispatch["prompt_contract"]
        assert "Do not run decision_harness record" in dispatch["prompt_contract"], dispatch["prompt_contract"]
        assert "HANDOFF_PASS is only for the assigned deliverable" in dispatch["prompt_contract"], dispatch["prompt_contract"]
        assert "repo schema or writer convention" in dispatch["prompt_contract"], dispatch["prompt_contract"]
        assert "scenario_count" in dispatch["prompt_contract"], dispatch["prompt_contract"]
        assert "smoke_fallback_used=false" in dispatch["prompt_contract"], dispatch["prompt_contract"]
        dispatch_nonce = dispatch["dispatch_id"].rsplit("_", 1)[-1]
        assert len(dispatch_nonce) == 8 and all(char in "0123456789ABCDEF" for char in dispatch_nonce), dispatch
        write_task5_ownership_locks(hook_ip, "RUN_DISPATCH_SMOKE", "RTL_SMOKE_TASK", dispatch["dispatch_id"])
        (hook_ip / "rtl" / "smoke.sv").write_text("module smoke; endmodule\n", encoding="utf-8")
        receipt = hook_ip / "knowledge" / "subagents" / "smoke.json"
        receipt.parent.mkdir(parents=True, exist_ok=True)
        receipt.write_text(
            json.dumps(
                {
                    "schema_version": "oag_subagent_receipt.v1",
                    "product_name": "IP Dev Agent",
                    "internal_gateway": "Ontology Agent Gateway",
                    "ip_id": dispatch["ip_id"],
                    "dispatch_id": dispatch["dispatch_id"],
                    "dispatch_path": dispatch["dispatch_path"],
                    "wavefront_run_id": "RUN_DISPATCH_SMOKE",
                    "task_id": "RTL_SMOKE_TASK",
                    "ownership_mode": "exclusive_file",
                    "role_name": dispatch["role_name"],
                    "registered_id": dispatch["registered_id"],
                    "shard_scope": "smoke",
                    "stage": "rtl",
                    "status": "STATIC_HANDOFF_PASS",
                    "owned_obligations": dispatch["owned_obligations"],
                    "contracts": dispatch["contracts"],
                    "allowed_write_paths": dispatch["allowed_write_paths"],
                    "changed_paths": ["smoke_ip/rtl/smoke.sv"],
                    "generated_side_effects": [],
                    "evidence_outputs": [dispatch["receipt_path"]],
                    "diagnostic_only": False,
                    "covers_writes": True,
                    "dispatch_verified": True,
                    "implementation_evidence": True,
                    "may_claim_complete": False,
                    "created_at": "2026-01-01T00:00:00Z",
                },
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        receipt_validation = run_validate_json(ROOT / "schemas" / "oag_subagent_receipt.schema.json", receipt)
        assert receipt_validation.returncode == 0, receipt_validation.stderr or receipt_validation.stdout
        dispatch_verify = run_dispatch(
            "verify",
            "--dispatch",
            str(hook_cwd / dispatch["dispatch_path"]),
            "--receipt",
            str(receipt),
            "--json",
            project_root=hook_cwd,
        )
        assert dispatch_verify.returncode == 0, dispatch_verify.stderr or dispatch_verify.stdout
        main_gate_allowed = run_main_write_gate(hook_ip, project_root=hook_cwd)
        assert main_gate_allowed.returncode == 0, main_gate_allowed.stderr or main_gate_allowed.stdout
        main_gate_allowed_payload = json.loads(main_gate_allowed.stdout)
        assert main_gate_allowed_payload["status"] == "pass", main_gate_allowed_payload
        dispatch_verify_result = json.loads(dispatch_verify.stdout)
        assert dispatch_verify_result["status"] == "pass", dispatch_verify_result
        valid_payload = {**invalid_payload, "last_assistant_message": "OAG_EVIDENCE_RECORDED: smoke_ip/knowledge/subagents/smoke.json"}
        valid_gate = subagent_gate(valid_payload, {"OAG_SUBAGENT_GATE_CACHE": str(Path(tmp) / "subagent_gate_cache_valid.json")})
        assert valid_gate.returncode == 0, valid_gate.stderr or valid_gate.stdout
        assert valid_gate.stdout == "", valid_gate.stdout
        bad_receipt = hook_ip / "knowledge" / "subagents" / "bad_scope.json"
        bad_payload = json.loads(receipt.read_text(encoding="utf-8"))
        bad_payload["changed_paths"] = ["smoke_ip/list/rtl.f"]
        bad_payload["evidence_outputs"] = ["smoke_ip/knowledge/subagents/bad_scope.json"]
        bad_receipt.write_text(json.dumps(bad_payload, sort_keys=True) + "\n", encoding="utf-8")
        bad_verify = run_dispatch(
            "verify",
            "--dispatch",
            str(hook_cwd / dispatch["dispatch_path"]),
            "--receipt",
            str(bad_receipt),
            "--json",
            project_root=hook_cwd,
        )
        assert bad_verify.returncode != 0, bad_verify.stdout
        bad_verify_result = json.loads(bad_verify.stdout)
        assert any(item["code"] == "RECEIPT_PATH_MISMATCH" for item in bad_verify_result["issues"]), bad_verify_result
        assert any(item["code"] == "OWNED_PATH_OUT_OF_SCOPE" for item in bad_verify_result["issues"]), bad_verify_result
        (hook_ip / "rtl" / "unrelated_concurrent.sv").write_text("module unrelated_concurrent; endmodule\n", encoding="utf-8")
        concurrent_blocked_payload = json.loads(receipt.read_text(encoding="utf-8"))
        concurrent_blocked_payload["status"] = "BLOCKED"
        concurrent_blocked_payload["blockers"] = [
            "oag_dispatch.py verify reports only ACTUAL_PATH_OUT_OF_SCOPE deltas from unrelated concurrent workspace edits."
        ]
        receipt.write_text(json.dumps(concurrent_blocked_payload, sort_keys=True) + "\n", encoding="utf-8")
        concurrent_verify = run_dispatch(
            "verify",
            "--dispatch",
            str(hook_cwd / dispatch["dispatch_path"]),
            "--receipt",
            str(receipt),
            "--json",
            project_root=hook_cwd,
        )
        assert concurrent_verify.returncode != 0, concurrent_verify.stdout
        concurrent_verify_result = json.loads(concurrent_verify.stdout)
        concurrent_codes = {item["code"] for item in concurrent_verify_result["issues"]}
        assert concurrent_codes == {"ACTUAL_PATH_OUT_OF_SCOPE"}, concurrent_verify_result
        concurrent_gate = subagent_gate(valid_payload, {"OAG_SUBAGENT_GATE_CACHE": str(Path(tmp) / "subagent_gate_cache_concurrent.json")})
        assert concurrent_gate.returncode == 0, concurrent_gate.stderr or concurrent_gate.stdout
        assert concurrent_gate.stdout == "", concurrent_gate.stdout
        concurrent_unblocked_payload = {**concurrent_blocked_payload, "status": "RTL_HANDOFF_PASS"}
        concurrent_unblocked_payload.pop("blockers", None)
        receipt.write_text(json.dumps(concurrent_unblocked_payload, sort_keys=True) + "\n", encoding="utf-8")
        unblocked_status_gate = subagent_gate(valid_payload, {"OAG_SUBAGENT_GATE_CACHE": str(Path(tmp) / "subagent_gate_cache_concurrent_bad_status.json")})
        assert unblocked_status_gate.returncode == 0, unblocked_status_gate.stderr or unblocked_status_gate.stdout
        unblocked_status_payload = json.loads(unblocked_status_gate.stdout)
        assert unblocked_status_payload["decision"] == "block", unblocked_status_payload
        assert "BLOCKED, INCONCLUSIVE, or FAIL" in unblocked_status_payload["reason"], unblocked_status_payload

        closure_ip = make_ip(Path(tmp) / "closure_check")
        close_demo_counter(closure_ip, claim="closure check smoke counter closed")
        write_closure_reports(closure_ip)
        closure_pass = run_closure_check(closure_ip)
        assert closure_pass.returncode == 0, closure_pass.stderr or closure_pass.stdout
        closure_pass_result = json.loads(closure_pass.stdout)
        assert closure_pass_result["status"] == "pass", closure_pass_result
        assert closure_pass_result["validation_report"] == "knowledge/validations/oag_validation_report.json", closure_pass_result
        assert closure_pass_result["gate_report"] == "knowledge/gate_reviews/oag_gate_decision.json", closure_pass_result

        stale_gate_ip = make_ip(Path(tmp) / "stale_gate_closure")
        close_demo_counter(stale_gate_ip, claim="stale gate smoke counter closed")
        write_closure_reports(stale_gate_ip)
        (stale_gate_ip / "cov" / "coverage.json").write_text(json.dumps({"status": "pass", "post_gate": True}), encoding="utf-8")
        stale_gate = run_closure_check(stale_gate_ip)
        assert stale_gate.returncode != 0, stale_gate.stdout
        stale_gate_result = json.loads(stale_gate.stdout)
        assert any(item["code"] == "GATE_ARTIFACT_STALE" for item in stale_gate_result["issues"]), stale_gate_result

        missing_closure_ip = make_ip(Path(tmp) / "missing_closure")
        closure_missing = run_closure_check(missing_closure_ip)
        assert closure_missing.returncode != 0, closure_missing.stdout
        closure_missing_result = json.loads(closure_missing.stdout)
        missing_codes = {item["code"] for item in closure_missing_result["issues"]}
        assert {"VALIDATION_REPORT_MISSING", "GATE_REPORT_MISSING"}.issubset(missing_codes), closure_missing_result

        bad_gate_ip = make_ip(Path(tmp) / "bad_gate_closure")
        close_demo_counter(bad_gate_ip, claim="bad gate smoke counter closed")
        write_closure_reports(bad_gate_ip, gate_decision="FAIL")
        closure_bad_gate = run_closure_check(bad_gate_ip)
        assert closure_bad_gate.returncode != 0, closure_bad_gate.stdout
        closure_bad_gate_result = json.loads(closure_bad_gate.stdout)
        assert any(item["code"] == "GATE_DECISION" for item in closure_bad_gate_result["issues"]), closure_bad_gate_result

        custom_claim_ip = make_ip(Path(tmp) / "custom_claim_closure")
        close_demo_counter(custom_claim_ip, claim="custom claim smoke counter closed")
        write_closure_reports(custom_claim_ip)
        custom_receipt = custom_claim_ip / "knowledge" / "subagents" / "custom_worker.json"
        custom_receipt.parent.mkdir(parents=True, exist_ok=True)
        custom_receipt.write_text(
            json.dumps(
                {
                    "schema_version": "oag_subagent_receipt.v1",
                    "product_name": "IP Dev Agent",
                    "internal_gateway": "Ontology Agent Gateway",
                    "role_name": "oag-custom-worker",
                    "shard_scope": "rtl_timer",
                    "stage": "rtl",
                    "status": "STATIC_HANDOFF_PASS",
                    "owned_obligations": [],
                    "contracts": [],
                    "allowed_write_paths": ["rtl/"],
                    "evidence_outputs": [],
                    "may_claim_complete": True,
                    "created_at": "2026-01-01T00:00:00Z",
                }
            )
            + "\n",
            encoding="utf-8",
        )
        closure_custom_claim = run_closure_check(custom_claim_ip)
        assert closure_custom_claim.returncode != 0, closure_custom_claim.stdout
        closure_custom_claim_result = json.loads(closure_custom_claim.stdout)
        assert any(item["code"] == "CUSTOM_COMPLETION_CLAIM" for item in closure_custom_claim_result["issues"]), closure_custom_claim_result

        ip = make_ip(Path(tmp))
        (ip / "ontology" / "decision_matrix.yaml").write_text(
            json.dumps(
                {
                    "schema_version": "oag_decision_matrix.v1",
                    "ip": ip.name,
                    "decisions": [
                        {
                            "id": "D_AUTHORING_PACKET_REF",
                            "question": "Which locked decision must RTL/TB authoring packets honor?",
                            "status": "decided",
                            "lock_required": True,
                            "owner": "human",
                            "decision_class": "parameterizable",
                            "representation": "parameter",
                            "decision": 4,
                            "affects": ["rtl", "tb"],
                            "contract_refs": ["CONTRACT_DEMO_COUNTER_CX1_SIM_SCOREBOARD"],
                        },
                        {
                            "id": "D_AUTHORING_PACKET_MODULE_REF",
                            "question": "Which module-scoped decision must generated top-level packets honor?",
                            "status": "decided",
                            "lock_required": True,
                            "owner": "human",
                            "decision_class": "parameterizable",
                            "representation": "parameter",
                            "decision": 1,
                            "target_modules": ["demo_counter_cx1"],
                        }
                    ],
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        decision_matrix_approval = call(
            {
                "tool": "oag.record",
                "arguments": {
                    "ip_dir": str(ip),
                    "stage": "requirements",
                    "type": "decision",
                    "claim": "protected decision_matrix.yaml change approved",
                    "summary": "Human owner approved adding a locked decision for authoring packet compile coverage.",
                    "tags": ["human_approval", "protected_truth"],
                    "actor": {"kind": "human", "id": "smoke-owner", "surface": "smoke"},
                    "approval": {
                        "kind": "human",
                        "approved": True,
                        "approved_by": "smoke-owner",
                        "reason": "authoring packet compile smoke",
                    },
                    "status": "open",
                },
            }
        )
        assert decision_matrix_approval["result"]["ledger_event"], decision_matrix_approval
        compiled = call({"tool": "oag.compile", "arguments": {"ip_dir": str(ip)}})
        assert compiled["result"]["status"] == "pass", compiled
        assert compiled["result"]["stats"]["design_rules"] >= 13, compiled
        assert compiled["result"]["stats"]["modules"] >= 1, compiled
        assert compiled["result"]["stats"]["design_facts_modules"] == 0, compiled
        assert compiled["result"]["stats"]["domain_rdc_crossings"] >= 1, compiled
        assert compiled["result"]["stats"]["tb_methodology_roles"] >= 6, compiled
        assert compiled["result"]["stats"]["tb_coverage_goals"] >= 1, compiled
        assert compiled["result"]["stats"]["authoring_packets"] >= 1, compiled
        assert (ip / "ontology" / "generated" / "design_truth_graph.json").is_file()
        assert (ip / "ontology" / "generated" / "design_spec.json").is_file()
        assert (ip / "ontology" / "generated" / "domain_crossing_matrix.json").is_file()
        assert (ip / "ontology" / "generated" / "tb_methodology_matrix.json").is_file()
        assert (ip / "ontology" / "generated" / "compile_manifest.json").is_file()
        authoring_packet_dir = ip / "ontology" / "generated" / "authoring_packets"
        rtl_packet = json.loads((authoring_packet_dir / f"rtl__{ip.name}.json").read_text(encoding="utf-8"))
        tb_packet = json.loads((authoring_packet_dir / f"tb__{ip.name}.json").read_text(encoding="utf-8"))
        assert "D_AUTHORING_PACKET_REF" in rtl_packet.get("decision_refs_to_honor", []), rtl_packet
        assert "D_AUTHORING_PACKET_REF" in tb_packet.get("decision_refs_to_honor", []), tb_packet
        assert "D_AUTHORING_PACKET_MODULE_REF" in rtl_packet.get("decision_refs_to_honor", []), rtl_packet
        assert "D_AUTHORING_PACKET_MODULE_REF" in tb_packet.get("decision_refs_to_honor", []), tb_packet
        compile_cached = call({"tool": "oag.compile", "arguments": {"ip_dir": str(ip)}})
        assert compile_cached["result"]["status"] == "pass", compile_cached
        assert compile_cached["result"]["skipped"] is True, compile_cached
        compile_forced = call({"tool": "oag.compile", "arguments": {"ip_dir": str(ip), "force": True}})
        assert compile_forced["result"]["status"] == "pass", compile_forced
        assert compile_forced["result"]["skipped"] is False, compile_forced
        design_facts_path = ip / "ontology" / "generated" / "design_facts_graph.json"
        assert design_facts_path.is_file()
        design_facts = json.loads(design_facts_path.read_text(encoding="utf-8"))
        assert design_facts["schema_version"] == "oag_design_facts_graph.v1", design_facts
        assert design_facts["status"] == "pass", design_facts
        assert design_facts["stats"]["rtl_source_files"] == 0, design_facts
        assert "git_head" not in (design_facts.get("extractor") or {}), design_facts
        truth_graph = json.loads((ip / "ontology" / "generated" / "design_truth_graph.json").read_text(encoding="utf-8"))
        truth_facts = truth_graph.get("generated", {}).get("design_facts", {})
        assert "git_head" not in (truth_facts.get("extractor") or {}), truth_graph
        closure_graph_edges = [
            edge
            for edge in truth_graph.get("edges", [])
            if edge.get("type") == "closed_by" and edge.get("load_bearing") is True
        ]
        assert closure_graph_edges, truth_graph
        for edge in closure_graph_edges:
            assert edge["closure_edge"] is True, edge
            assert edge["approval_policy"] == "evidence_required", edge
            assert edge["approved"] is False, edge
            assert edge["approved_reason"] == "", edge
            assert edge["criteria"] == [
                "contract exists and remains bound to obligation",
                "required evidence exists and is fresh",
                "closed ROCEV validation record links this obligation-contract edge",
            ], edge
            assert edge["required_evidence"] == ["sim/results.xml", "sim/scoreboard_events.jsonl"], edge
        domain_matrix = json.loads((ip / "ontology" / "generated" / "domain_crossing_matrix.json").read_text(encoding="utf-8"))
        assert domain_matrix["schema_version"] == "oag_domain_crossing_matrix.v1", domain_matrix
        assert domain_matrix["status"] == "present", domain_matrix
        assert (ip / "ontology" / "generated" / "authoring_packets" / "module__demo_counter_cx1.json").is_file()
        assert (ip / "ontology" / "runs").is_dir()
        inspect = call({"tool": "oag.inspect", "arguments": {"ip_dir": str(ip), "stage": "sim"}})
        assert inspect["result"]["validation"] == "partial", inspect
        assert "closure matrix has open obligations" in inspect["result"]["gaps"], inspect
        assert inspect["result"]["evidence"]["truth_graph"]["status"] == "pass", inspect
        assert inspect["result"]["evidence"]["design_facts_graph"]["status"] == "pass", inspect
        assert inspect["result"]["evidence"]["design_rules"]["count"] >= 13, inspect
        assert inspect["result"]["evidence"]["structure"]["profile"] == "small_leaf_single_file", inspect
        assert inspect["result"]["evidence"]["decomposition"]["modules"] >= 1, inspect
        assert inspect["result"]["evidence"]["authoring_packets"]["count"] >= 1, inspect
        scoreboard = inspect["result"]["evidence"]["scoreboard"]["summary"]
        assert scoreboard["schema"] == "scoreboard_rows.v1", scoreboard
        assert scoreboard["standard_rows"] == 2, scoreboard
        assert scoreboard["schema_failed"] == 0, scoreboard
        init = call({"tool": "oag.init", "arguments": {"ip_dir": str(ip)}})
        assert init["ok"] is True, init
        limit_ip = make_ip(Path(tmp) / "policy_limit")
        limit_run = call(
            {
                "tool": "oag.run.start",
                "arguments": {
                    "ip_dir": str(limit_ip),
                    "stage": "sim",
                    "intent": "smoke stage-limit policy",
                    "actor": {"kind": "ai", "id": "codex", "surface": "smoke"},
                },
            }
        )
        limit_run_id = limit_run["result"]["run_id"]
        limit_config = call(
            {
                "tool": "oag.configure",
                "arguments": {
                    "ip_dir": str(limit_ip),
                    "hook_auto_continue_until": "rtl",
                    "actor": {"kind": "human", "id": "smoke-owner", "surface": "smoke"},
                    "approval": {
                        "kind": "human",
                        "approved": True,
                        "approved_by": "smoke-owner",
                        "reason": "smoke limit",
                    },
                },
            }
        )
        assert limit_config["result"]["updates"]["hook_auto_continue_until"] == "rtl", limit_config
        limited_stop = call({"tool": "oag.stop_check", "arguments": {"ip_dir": str(limit_ip), "run_id": limit_run_id}})
        assert limited_stop["result"]["should_continue"] is False, limited_stop
        assert limited_stop["result"]["reason"] == "policy_limit_reached", limited_stop
        assert limited_stop["result"]["policy"]["next_action_stage"] == "sim", limited_stop
        limited_hook = stop_gate({"ip_dir": str(limit_ip), "run_id": limit_run_id})
        assert limited_hook.returncode == 0, limited_hook.stderr or limited_hook.stdout
        limited_hook_payload = json.loads(limited_hook.stdout)
        assert limited_hook_payload["decision"] == "block", limited_hook_payload
        assert "MAIN_AGENT_WRITE_WITHOUT_SUBAGENT" in limited_hook_payload["reason"], limited_hook_payload
        sim_config = call(
            {
                "tool": "oag.configure",
                "arguments": {
                    "ip_dir": str(limit_ip),
                    "hook_auto_continue_until": "sim",
                    "actor": {"kind": "human", "id": "smoke-owner", "surface": "smoke"},
                    "approval": {
                        "kind": "human",
                        "approved": True,
                        "approved_by": "smoke-owner",
                        "reason": "smoke limit",
                    },
                },
            }
        )
        assert sim_config["result"]["updates"]["hook_auto_continue_until"] == "sim", sim_config
        sim_stop = call({"tool": "oag.stop_check", "arguments": {"ip_dir": str(limit_ip), "run_id": limit_run_id}})
        assert sim_stop["result"]["should_continue"] is True, sim_stop
        assert "closure_matrix=open" in sim_stop["result"]["prompt_block"], sim_stop
        assert "closure_edges_open=" in sim_stop["result"]["prompt_block"], sim_stop
        assert "owner=demo_counter_cx1" in sim_stop["result"]["prompt_block"], sim_stop
        assert "approval_policy=evidence_required" in sim_stop["result"]["prompt_block"], sim_stop
        assert "evidence=sim/results.xml,sim/scoreboard_events.jsonl" in sim_stop["result"]["prompt_block"], sim_stop
        stop_edges = sim_stop["result"]["closure_edges"]
        assert len(stop_edges) == 1, sim_stop
        stop_edge = stop_edges[0]
        assert stop_edge["schema_version"] == "oag_closure_edge_todo.v1", stop_edge
        assert stop_edge["source"] == "obligation::OBL_DEMO_COUNTER_CX1_RESET_KNOWN", stop_edge
        assert stop_edge["target"] == "contract::CONTRACT_DEMO_COUNTER_CX1_SIM_SCOREBOARD", stop_edge
        assert stop_edge["status"] == "open", stop_edge
        assert stop_edge["owner_module"] == "demo_counter_cx1", stop_edge
        assert stop_edge["owner_file"] == "rtl/demo_counter_cx1.sv", stop_edge
        assert stop_edge["required_evidence"] == ["sim/results.xml", "sim/scoreboard_events.jsonl"], stop_edge
        assert stop_edge["approval_policy"] == "evidence_required", stop_edge
        assert stop_edge["approved"] is False, stop_edge
        assert stop_edge["approved_reason"] == "", stop_edge
        assert stop_edge["criteria"] == [
            "contract exists and remains bound to obligation",
            "required evidence exists and is fresh",
            "closed ROCEV validation record links this obligation-contract edge",
        ], stop_edge
        stored_action = json.loads((limit_ip / "ontology" / "runs" / limit_run_id / "next_action.json").read_text(encoding="utf-8"))
        assert stored_action["closure_edges"] == stop_edges, stored_action
        bounded_rtl = call(
            {
                "tool": "oag.run.next",
                "arguments": {
                    "ip_dir": str(limit_ip),
                    "run_id": limit_run_id,
                    "loop_policy": {"until": "rtl"},
                },
            }
        )
        assert bounded_rtl["result"]["next_batch"] is None, bounded_rtl
        assert bounded_rtl["result"]["loop_stop_reason"] == "boundary_reached", bounded_rtl
        assert bounded_rtl["result"]["closure_edges"] == stop_edges, bounded_rtl
        hook_rtl = run_loop_hook("--ip-dir", str(limit_ip), "--run-id", limit_run_id, "--until", "rtl", "--json")
        assert hook_rtl.returncode == 0, hook_rtl.stderr or hook_rtl.stdout
        hook_rtl_json = json.loads(hook_rtl.stdout)
        assert hook_rtl_json["decision"] == "stop", hook_rtl_json
        assert hook_rtl_json["reason"] == "boundary_reached", hook_rtl_json
        hook_tb = run_loop_hook(
            "--ip-dir",
            str(limit_ip),
            "--run-id",
            limit_run_id,
            "--until",
            "tb",
            "--requirement",
            "REQ_DEMO_COUNTER_CX1_RESET_KNOWN",
            "--json",
        )
        assert hook_tb.returncode == 0, hook_tb.stderr or hook_tb.stdout
        hook_tb_json = json.loads(hook_tb.stdout)
        assert hook_tb_json["decision"] == "continue", hook_tb_json
        tb_batch = hook_tb_json["recommended_batch"]
        assert tb_batch["boundary_stage"] == "evidence", hook_tb_json
        assert "REQ_DEMO_COUNTER_CX1_RESET_KNOWN" in tb_batch["requirements"], hook_tb_json
        bad_req = run_loop_hook(
            "--ip-dir",
            str(limit_ip),
            "--run-id",
            limit_run_id,
            "--until",
            "tb",
            "--requirement",
            "REQ_DOES_NOT_EXIST",
            "--json",
        )
        assert bad_req.returncode == 0, bad_req.stderr or bad_req.stdout
        bad_req_json = json.loads(bad_req.stdout)
        assert bad_req_json["decision"] == "stop", bad_req_json
        assert bad_req_json["reason"] == "no_runnable_batch", bad_req_json
        loop_stop = call(
            {
                "tool": "oag.stop_check",
                "arguments": {
                    "ip_dir": str(limit_ip),
                    "run_id": limit_run_id,
                    "loop_policy": {"until": "rtl"},
                },
            }
        )
        assert loop_stop["result"]["should_continue"] is False, loop_stop
        assert loop_stop["result"]["reason"] == "boundary_reached", loop_stop
        maxed_loop = call(
            {
                "tool": "oag.stop_check",
                "arguments": {
                    "ip_dir": str(limit_ip),
                    "run_id": limit_run_id,
                    "loop_policy": {"until": "tb", "max_iterations": 1},
                },
            }
        )
        assert maxed_loop["result"]["should_continue"] is False, maxed_loop
        assert maxed_loop["result"]["reason"] == "max_iterations_reached", maxed_loop
        runner = run_loop_runner(
            "--ip-dir",
            str(limit_ip),
            "--run-id",
            limit_run_id,
            "--until",
            "tb",
            "--requirement",
            "REQ_DEMO_COUNTER_CX1_RESET_KNOWN",
            "--mode",
            "plan_only",
            "--json",
        )
        assert runner.returncode == 0, runner.stderr or runner.stdout
        runner_json = json.loads(runner.stdout)
        assert runner_json["decision"] == "continue", runner_json
        assert runner_json["reason"] == "plan_available", runner_json
        assert Path(runner_json["loop_decision_path"]).is_file(), runner_json
        none_config = call(
            {
                "tool": "oag.configure",
                "arguments": {
                    "ip_dir": str(limit_ip),
                    "hook_auto_continue_until": "none",
                    "actor": {"kind": "human", "id": "smoke-owner", "surface": "smoke"},
                    "approval": {
                        "kind": "human",
                        "approved": True,
                        "approved_by": "smoke-owner",
                        "reason": "smoke limit",
                    },
                },
            }
        )
        assert none_config["result"]["updates"]["hook_auto_continue_until"] == "none", none_config
        none_stop = call({"tool": "oag.stop_check", "arguments": {"ip_dir": str(limit_ip), "run_id": limit_run_id}})
        assert none_stop["result"]["should_continue"] is False, none_stop
        command_ip = make_ip(Path(tmp) / "command_limit")
        command_run = call(
            {
                "tool": "oag.run.start",
                "arguments": {
                    "ip_dir": str(command_ip),
                    "stage": "sim",
                    "intent": "smoke short chat run-limit command",
                    "actor": {"kind": "ai", "id": "codex", "surface": "smoke"},
                },
            }
        )
        command_hook = context_hook({"ip_dir": str(command_ip), "prompt": "rtl까지만"})
        assert command_hook.returncode == 0, command_hook.stderr or command_hook.stdout
        assert "OAG RUN LIMIT CONFIGURED" in hook_context(command_hook), command_hook.stdout
        command_stop = call({"tool": "oag.stop_check", "arguments": {"ip_dir": str(command_ip), "run_id": command_run["result"]["run_id"]}})
        assert command_stop["result"]["should_continue"] is False, command_stop
        assert command_stop["result"]["policy"]["hook_auto_continue_until"] == "rtl", command_stop
        run_start = call(
            {
                "tool": "oag.run.start",
                "arguments": {
                    "ip_dir": str(ip),
                    "stage": "sim",
                    "intent": "smoke close reset scoreboard obligation",
                    "actor": {"kind": "ai", "id": "codex", "surface": "smoke"},
                },
            }
        )
        assert run_start["result"]["schema_version"] == "oag_run_start.v1", run_start
        run_id = run_start["result"]["run_id"]
        assert run_start["result"]["status"] == "in_progress", run_start
        assert run_start["result"]["next_action"]["active_obligation"] == "OBL_DEMO_COUNTER_CX1_RESET_KNOWN", run_start
        assert run_start["result"]["next_action"]["next_action"]["kind"] == "dispatch_ready_wave", run_start
        assert "OAG NEXT ACTION" in run_start["result"]["next_action"]["prompt_block"], run_start
        run_start_candidates = run_start["result"]["dispatch_command_candidates"]
        assert len(run_start_candidates) >= 2, run_start
        first_candidate = run_start_candidates[0]
        assert "oag_dispatch.py create" in first_candidate["dispatch_create_command"], first_candidate
        assert "--wavefront-run-id" in first_candidate["dispatch_create_command"], first_candidate
        assert "--task-id triage.OBL_DEMO_COUNTER_CX1_RESET_KNOWN" in first_candidate["dispatch_create_command"], first_candidate
        assert "--dispatch-id <dispatch_id>" in first_candidate["claim_command"], first_candidate
        assert first_candidate["command_sequence"] == [
            first_candidate["dispatch_create_command"],
            first_candidate["claim_command"],
        ], first_candidate
        run_start_prompt = run_start["result"]["next_action"]["prompt_block"]
        assert "dispatch_candidates=" in run_start_prompt, run_start_prompt
        assert "parallel_spawn_batch=required" in run_start_prompt, run_start_prompt
        assert "oag_dispatch.py create" in run_start_prompt, run_start_prompt
        assert "--dispatch-id <dispatch_id>" in run_start_prompt, run_start_prompt
        assert (ip / "ontology" / "runs" / run_id / "run_state.json").is_file(), run_start
        assert (ip / "ontology" / "runs" / run_id / "next_action.json").is_file(), run_start
        assert (ip / "ontology" / "runs" / run_id / "checkpoint_history.jsonl").is_file(), run_start
        stop_before = call({"tool": "oag.stop_check", "arguments": {"ip_dir": str(ip), "run_id": run_id}})
        assert stop_before["result"]["should_continue"] is True, stop_before
        assert "OAG NEXT ACTION" in stop_before["result"]["prompt_block"], stop_before
        stop_hook_before = stop_gate({"ip_dir": str(ip), "run_id": run_id})
        assert stop_hook_before.returncode == 0, stop_hook_before.stderr or stop_hook_before.stdout
        stop_hook_block = json.loads(stop_hook_before.stdout)
        assert stop_hook_block["decision"] == "block", stop_hook_block
        assert "OAG NEXT ACTION" in stop_hook_block["reason"], stop_hook_block
        assert "run incomplete" in stop_hook_block["reason"], stop_hook_block
        stop_cache = Path(tmp) / "stop_gate_cache.json"
        limited_env = {"OAG_STOP_GATE_CACHE": str(stop_cache), "OAG_STOP_GATE_MAX_BLOCK_REPEATS": "1"}
        stop_hook_limited_first = stop_gate({"ip_dir": str(ip), "run_id": run_id}, limited_env)
        assert stop_hook_limited_first.returncode == 0, stop_hook_limited_first.stderr or stop_hook_limited_first.stdout
        assert json.loads(stop_hook_limited_first.stdout)["decision"] == "block", stop_hook_limited_first.stdout
        stop_hook_limited_second = stop_gate({"ip_dir": str(ip), "run_id": run_id}, limited_env)
        assert stop_hook_limited_second.returncode == 0, stop_hook_limited_second.stderr or stop_hook_limited_second.stdout
        assert json.loads(stop_hook_limited_second.stdout)["decision"] == "block", stop_hook_limited_second.stdout
        run_shard = ip / "sim" / "slices" / "OBL_DEMO_COUNTER_CX1_RESET_KNOWN" / "scoreboard_events.jsonl"
        run_shard.parent.mkdir(parents=True, exist_ok=True)
        run_shard.write_text((ip / "sim" / "scoreboard_events.jsonl").read_text(encoding="utf-8"), encoding="utf-8")
        for task_id in (
            "triage.OBL_DEMO_COUNTER_CX1_RESET_KNOWN",
            "evidence.sim.OBL_DEMO_COUNTER_CX1_RESET_KNOWN",
            "merge.sim.aggregate",
        ):
            graph_path = ip / "ontology" / "runs" / run_id / "wavefront_task_graph.json"
            graph = json.loads(graph_path.read_text(encoding="utf-8"))
            graph_task = next(item for item in graph["tasks"] if item["task_id"] == task_id)
            dispatch_id = ""
            if graph_task["ownership_mode"] != "none":
                dispatch_id = write_wavefront_claim_dispatch(Path(tmp), ip, run_id, graph_task)
            claim_args = [
                "claim",
                "--ip-dir",
                str(ip),
                "--run-id",
                run_id,
                "--task-id",
                task_id,
                "--claimed-by",
                "smoke-run-loop",
                "--json",
            ]
            if dispatch_id:
                claim_args.extend(["--dispatch-id", dispatch_id])
            graph_claim = run_wavefront(*claim_args, project_root=Path(tmp))
            assert graph_claim.returncode == 0, graph_claim.stderr or graph_claim.stdout
            review_pending = run_wavefront(
                "record",
                "--ip-dir",
                str(ip),
                "--run-id",
                run_id,
                "--task-id",
                task_id,
                "--status",
                "review_pending",
                "--json",
                project_root=Path(tmp),
            )
            assert review_pending.returncode == 0, review_pending.stderr or review_pending.stdout
            decision = run_decision_harness(
                "record",
                "--ip-dir",
                str(ip),
                "--run-id",
                run_id,
                "--task-id",
                task_id,
                "--decision-id",
                f"DEC_{re.sub(r'[^A-Z0-9]+', '_', task_id.upper())}_RUN_LOOP_SMOKE",
                "--decision-type",
                "custom_review",
                "--verdict",
                "approved",
                "--summary",
                f"{task_id} run-loop evidence reviewed by smoke test.",
                "--checked-against",
                str(graph_path),
                "--preserved",
                "declared run-loop closure semantics",
                "--wavefront-status",
                "closed",
                "--json",
                project_root=Path(tmp),
            )
            assert decision.returncode == 0, decision.stderr or decision.stdout
            decision_path = json.loads(decision.stdout)["path"]
            graph_record = run_wavefront(
                "record",
                "--ip-dir",
                str(ip),
                "--run-id",
                run_id,
                "--task-id",
                task_id,
                "--status",
                "closed",
                "--decision",
                decision_path,
                "--json",
                project_root=Path(tmp),
            )
            assert graph_record.returncode == 0, graph_record.stderr or graph_record.stdout
        run_loop_record = call(
            {
                "tool": "oag.run.record",
                "arguments": {
                    "ip_dir": str(ip),
                    "run_id": run_id,
                    "stage": "sim",
                    "summary": "run-loop smoke scoreboard evidence closes the reset obligation",
                    "evidence_files": ["sim/results.xml", "sim/scoreboard_events.jsonl"],
                    "actor": {"kind": "ai", "id": "codex", "surface": "smoke"},
                },
            }
        )
        assert run_loop_record["result"]["record"]["status"] == "closed", run_loop_record
        assert run_loop_record["result"]["graph_record"]["task"]["status"] == "review_pending", run_loop_record
        assert run_loop_record["result"]["status"] == "in_progress", run_loop_record
        closure_task_id = "closure.OBL_DEMO_COUNTER_CX1_RESET_KNOWN"
        closure_decision = run_decision_harness(
            "record",
            "--ip-dir",
            str(ip),
            "--run-id",
            run_id,
            "--task-id",
            closure_task_id,
            "--decision-id",
            "DEC_PARENT_CLOSURE_RUN_LOOP_SMOKE",
            "--decision-type",
            "evidence_validation",
            "--verdict",
            "approved",
            "--summary",
            "Parent ROCEV closure record reviewed after all graph evidence completed.",
            "--checked-against",
            str(ip / "ontology" / "runs" / run_id / "wavefront_task_graph.json"),
            "--preserved",
            "independent closure review boundary",
            "--barrier-output",
            "closure:OBL_DEMO_COUNTER_CX1_RESET_KNOWN:recorded",
            "--wavefront-status",
            "closed",
            "--reviewer-id",
            "oag-gate-reviewer",
            "--json",
            project_root=Path(tmp),
        )
        assert closure_decision.returncode == 0, closure_decision.stderr or closure_decision.stdout
        closure_graph_record = run_wavefront(
            "record",
            "--ip-dir",
            str(ip),
            "--run-id",
            run_id,
            "--task-id",
            closure_task_id,
            "--status",
            "closed",
            "--decision",
            json.loads(closure_decision.stdout)["path"],
            "--barrier-output",
            "closure:OBL_DEMO_COUNTER_CX1_RESET_KNOWN:recorded",
            "--json",
            project_root=Path(tmp),
        )
        assert closure_graph_record.returncode == 0, closure_graph_record.stderr or closure_graph_record.stdout
        checkpoint_ready = call({"tool": "oag.run.next", "arguments": {"ip_dir": str(ip), "run_id": run_id}})
        assert checkpoint_ready["result"]["status"] == "checkpoint_ready", checkpoint_ready
        write_closure_reports(ip)
        claim_complete_review = call(
            {
                "tool": "oag.review",
                "arguments": {
                    "ip_dir": str(ip),
                    "action": "claim_complete",
                    "stage": "sim",
                    "verdict": "pass",
                    "actor": {"kind": "ai", "id": "oag-gate-reviewer", "surface": "smoke"},
                    "producer_actor": {"kind": "ai", "id": "codex", "surface": "smoke"},
                    "findings": [],
                },
            }
        )
        assert claim_complete_review["result"]["allowed"] is True, claim_complete_review
        run_checkpoint = call(
            {
                "tool": "oag.run.checkpoint",
                "arguments": {
                    "ip_dir": str(ip),
                    "run_id": run_id,
                    "stage": "sim",
                    "intent": "smoke close reset scoreboard obligation",
                    "approval": {
                        "kind": "human",
                        "approved": True,
                        "approved_by": "smoke-owner",
                        "reason": "smoke owner approved run checkpoint completion",
                    },
                    "actor": {"kind": "human", "id": "smoke-owner", "surface": "smoke"},
                },
            }
        )
        assert run_checkpoint["result"]["allowed"] is True, run_checkpoint
        assert run_checkpoint["result"]["status"] == "complete", run_checkpoint
        assert run_checkpoint["result"]["decision"]["decision_receipt"], run_checkpoint
        run_state_path = ip / "ontology" / "runs" / run_id / "run_state.json"
        run_history_path = ip / "ontology" / "runs" / run_id / "checkpoint_history.jsonl"
        complete_state = json.loads(run_state_path.read_text(encoding="utf-8"))
        complete_history = run_history_path.read_text(encoding="utf-8")
        terminal_next = call({"tool": "oag.run.next", "arguments": {"ip_dir": str(ip), "run_id": run_id}})
        assert terminal_next["result"]["status"] == "complete", terminal_next
        assert terminal_next["result"]["terminal"] is True, terminal_next
        assert terminal_next["result"]["reason"] == "run_complete", terminal_next
        assert json.loads(run_state_path.read_text(encoding="utf-8"))["iteration"] == complete_state["iteration"], terminal_next
        assert run_history_path.read_text(encoding="utf-8") == complete_history, terminal_next
        main_write_waiver = call(
            {
                "tool": "oag.decide",
                "arguments": {
                    "ip_dir": str(ip),
                    "action": "main_agent_subagent_waiver",
                    "stage": "sim",
                    "record_decision": True,
                    "actor": {"kind": "human", "id": "smoke-owner", "surface": "smoke"},
                    "approval": {
                        "kind": "human",
                        "approved": True,
                        "approved_by": "smoke-owner",
                        "reason": "The smoke fixture intentionally writes synthetic implementation evidence in the parent process.",
                    },
                },
            }
        )
        assert main_write_waiver["result"]["allowed"] is True, main_write_waiver
        assert main_write_waiver["result"]["decision_receipt"]["ledger_event"], main_write_waiver
        stop_after = call({"tool": "oag.stop_check", "arguments": {"ip_dir": str(ip), "run_id": run_id}})
        assert stop_after["result"]["should_continue"] is False, stop_after
        assert stop_after["result"]["reason"] == "run_complete", stop_after
        stop_hook_after = stop_gate({"ip_dir": str(ip), "run_id": run_id})
        assert stop_hook_after.returncode == 0, stop_hook_after.stderr or stop_hook_after.stdout
        assert stop_hook_after.stdout == "", stop_hook_after.stdout
        record = call(
            {
                "tool": "oag.record",
                "arguments": {
                    "ip_dir": str(ip),
                    "stage": "sim",
                    "type": "finding",
                    "claim": "counter scoreboard closed",
                    "summary": "scoreboard rows are clean",
                    "actor": {"kind": "ai", "id": "codex", "surface": "smoke"},
                    "rocev": {
                        "obligation": {"id": "OBL_DEMO_COUNTER_CX1_RESET_KNOWN", "text": "scoreboard has no mismatches"},
                        "contract": {
                            "id": "CONTRACT_DEMO_COUNTER_CX1_SIM_SCOREBOARD",
                            "method": "scoreboard",
                            "pass_condition": "mismatch count is zero",
                        },
                        "evidence": {"files": ["sim/results.xml", "sim/scoreboard_events.jsonl"], "tests": [], "commit": ""},
                        "validation": {"status": "closed", "verdict": "pass", "rationale": "all scoreboard rows have mismatch=false"},
                    },
                },
            }
        )
        assert record["result"]["status"] == "closed", record
        assert len(record["result"]["record"]["evidence"]["file_hashes"]) == 2, record
        assert record["result"]["ledger_event"], record
        assert (ip / "knowledge" / "ledger.jsonl").read_text(encoding="utf-8").strip(), record
        index_body = json.loads((ip / "knowledge" / "_index.json").read_text(encoding="utf-8"))
        record_files = [
            *sorted((ip / "knowledge" / "records").glob("*.json")),
            *sorted((ip / "knowledge" / "records").glob("*.yaml")),
            *sorted((ip / "knowledge" / "records").glob("*.yml")),
        ]
        assert index_body["record_count"] == len(record_files), index_body
        indexed_record = next(item for item in index_body["records"] if item["id"] == record["result"]["id"])
        assert indexed_record["obligation_id"] == "OBL_DEMO_COUNTER_CX1_RESET_KNOWN", indexed_record
        assert indexed_record["contract_id"] == "CONTRACT_DEMO_COUNTER_CX1_SIM_SCOREBOARD", indexed_record
        assert indexed_record["validation_status"] == "closed", indexed_record
        assert indexed_record["evidence_files"] == ["sim/results.xml", "sim/scoreboard_events.jsonl"], indexed_record
        metrics = call(
            {
                "tool": "oag.metrics",
                "arguments": {
                    "ip_dir": str(ip),
                    "stage": "sim",
                    "intent": "smoke numeric improvement snapshot",
                    "actor": {"kind": "ai", "id": "codex", "surface": "smoke"},
                },
            }
        )
        assert metrics["result"]["recorded"] is True, metrics
        assert Path(metrics["result"]["path"]).is_file(), metrics
        assert Path(metrics["result"]["history"]).is_file(), metrics
        metric_body = metrics["result"]["metrics"]
        assert metric_body["schema_version"] == "oag_improvement_metrics.v1", metric_body
        assert metric_body["closure"]["closed"] == metric_body["closure"]["total"], metric_body
        assert metric_body["closure"]["closed_percent"] == 100.0, metric_body
        assert metric_body["check"]["issue_count"] == 0, metric_body
        assert metric_body["evidence"]["files_present_count"] >= 2, metric_body
        metrics_check = call({"tool": "oag.check", "arguments": {"ip_dir": str(ip), "stage": "sim"}})
        assert metrics_check["result"]["improvement_metrics"]["closure"]["closed_percent"] == 100.0, metrics_check
        metrics_context = call({"tool": "oag.context", "arguments": {"ip_dir": str(ip), "stage": "sim", "intent": "metrics"}})
        assert "metrics closure=1/1 (100.0%)" in metrics_context["result"]["prompt_block"], metrics_context
        (ip / "signoff").mkdir(parents=True, exist_ok=True)
        (ip / "signoff" / "truth_coverage.json").write_text(
            json.dumps(
                {
                    "schema_version": "truth_coverage.v1",
                    "evidence_summary": {
                        "formal_assertion": {
                            "status": "development_pass",
                            "property_count": 3,
                            "bound_cycles": 8,
                            "numeric_summary": {
                                "baseline_property_count": 1,
                                "properties_checked": 3,
                                "properties_added": 2,
                                "baseline_bound_cycles": 4,
                                "bound_cycles": 8,
                                "bound_cycles_added": 4,
                                "bounded_steps_checked": 8,
                                "baseline_assertion_site_count": 2,
                                "source_assertion_site_count": 5,
                                "assertion_sites_added": 3,
                                "bounded_property_step_checks": 24,
                                "baseline_bounded_property_step_checks": 4,
                                "bounded_property_step_checks_added": 20,
                                "bounded_assertion_site_step_checks": 40,
                                "issues_found": 0,
                            },
                        },
                        "mutation": {
                            "status": "pass",
                            "mutants_run": 2,
                            "mutants_killed": 2,
                            "mutants_survived": 0,
                            "fault_models": ["reset_missing", "count_stuck"],
                        },
                        "implementation_sta": {
                            "status": "development_pass",
                            "target_clocks": [{"name": "clk", "period_ns": 10.0}],
                            "metrics": {
                                "wns_ns": 0.0,
                                "tns_ns": 0.0,
                                "unconstrained_text_seen": False,
                                "corner_count": 3,
                                "corners_passed": 3,
                                "corners_failed": 0,
                                "violated_corner_count": 0,
                            },
                            "numeric_summary": {
                                "baseline_corner_count": 1,
                                "corner_count": 3,
                                "corners_added": 2,
                                "corners_passed": 3,
                                "corners_failed": 0,
                                "worst_setup_slack_ns": 1.25,
                                "worst_hold_slack_ns": 0.12,
                                "worst_wns_ns": 0.0,
                                "worst_tns_ns": 0.0,
                                "violated_corner_count": 0,
                                "timing_analysis_count": 6,
                                "timing_metric_count": 12,
                                "negative_timing_metric_count": 0,
                                "worst_setup_slack_corner": "slow",
                                "worst_hold_slack_corner": "fast",
                                "worst_setup_slack_margin_percent_of_period": 12.5,
                                "worst_hold_slack_margin_percent_of_period": 1.2,
                            },
                        },
                        "gate_reset_xprop": {
                            "status": "development_pass",
                            "numeric_summary": {
                                "baseline_known_output_check_count": 2,
                                "known_output_check_count": 4,
                                "known_output_checks_added": 2,
                                "baseline_scenario_count": 1,
                                "scenario_count": 2,
                                "scenarios_added": 1,
                                "known_output_bit_check_count": 136,
                                "failures": 0,
                            },
                            "observations": {
                                "known_output_check_count": 4,
                                "known_output_bit_check_count": 136,
                                "scenarios": ["reset", "readback"],
                            },
                        },
                        "protocol_compliance": {
                            "status": "pass",
                            "protocol": "APB4",
                            "interface": "if_apb4_slave",
                            "method": "scoreboard_rows_v1_protocol_observation",
                            "numeric_summary": {
                                "baseline_protocol_row_count": 3,
                                "protocol_row_count": 5,
                                "protocol_rows_added": 2,
                                "baseline_response_row_count": 3,
                                "response_row_count": 5,
                                "response_rows_added": 2,
                                "read_response_row_count": 3,
                                "write_response_row_count": 2,
                                "invalid_response_row_count": 2,
                                "invalid_read_response_row_count": 1,
                                "invalid_write_response_row_count": 1,
                                "baseline_phase_row_count": 3,
                                "phase_row_count": 5,
                                "phase_rows_added": 2,
                                "baseline_protocol_coverage_ref_count": 4,
                                "required_protocol_coverage_ref_count": 6,
                                "protocol_coverage_refs_added": 2,
                                "observed_protocol_coverage_ref_count": 6,
                                "baseline_coverage_ref_count": 2,
                                "coverage_ref_count": 4,
                                "coverage_refs_added": 2,
                                "scoreboard_row_count": 6,
                                "protocol_check_count": 20,
                                "protocol_checks_passed": 20,
                                "protocol_checks_failed": 0,
                            },
                        },
                        "scoreboard": {"total": 2, "passed": 2, "failed": 0},
                        "coverage": {"status": "pass", "covered": ["reset", "count"]},
                    },
                }
            )
            + "\n",
            encoding="utf-8",
        )
        handoff = call(
            {
                "tool": "oag.handoff",
                "arguments": {
                    "ip_dir": str(ip),
                    "stage": "handoff",
                    "intent": "smoke numeric readiness handoff",
                    "actor": {"kind": "ai", "id": "codex", "surface": "smoke"},
                },
            }
        )
        assert handoff["result"]["recorded"] is True, handoff
        assert Path(handoff["result"]["path"]).is_file(), handoff
        assert Path(handoff["result"]["history"]).is_file(), handoff
        assert Path(handoff["result"]["metrics_path"]).is_file(), handoff
        handoff_body = handoff["result"]["handoff"]
        assert handoff_body["schema_version"] == "oag_readiness_handoff.v1", handoff_body
        assert handoff_body["progress_denominator"] == "derived_from_active_ip_obligations", handoff_body
        assert handoff_body["numeric_summary"]["obligations_closed"] == 1, handoff_body
        assert handoff_body["numeric_summary"]["obligations_total"] == 1, handoff_body
        assert handoff_body["numeric_summary"]["closure_percent"] == 100.0, handoff_body
        strength = handoff_body["evidence_strength_summary"]
        assert strength["formal"]["property_count"] == 3, strength
        assert strength["formal"]["properties_added"] == 2, strength
        assert strength["formal"]["bound_cycles"] == 8, strength
        assert strength["formal"]["bound_cycles_added"] == 4, strength
        assert strength["formal"]["bounded_property_step_checks"] == 24, strength
        assert strength["formal"]["source_assertion_site_count"] == 5, strength
        assert strength["formal"]["assertion_sites_added"] == 3, strength
        assert strength["mutation"]["mutation_score_percent"] == 100.0, strength
        assert strength["implementation_sta"]["corner_count"] == 3, strength
        assert strength["implementation_sta"]["corners_passed"] == 3, strength
        assert strength["implementation_sta"]["violated_corner_count"] == 0, strength
        assert strength["implementation_sta"]["worst_setup_slack_ns"] == 1.25, strength
        assert strength["implementation_sta"]["timing_metric_count"] == 12, strength
        assert strength["implementation_sta"]["negative_timing_metric_count"] == 0, strength
        assert strength["implementation_sta"]["worst_setup_slack_corner"] == "slow", strength
        assert strength["implementation_sta"]["worst_setup_slack_margin_percent_of_period"] == 12.5, strength
        assert strength["gate_reset_xprop"]["known_output_check_count"] == 4, strength
        assert strength["gate_reset_xprop"]["known_output_checks_added"] == 2, strength
        assert strength["gate_reset_xprop"]["scenario_count"] == 2, strength
        assert strength["gate_reset_xprop"]["known_output_bit_check_count"] == 136, strength
        assert strength["protocol"]["protocol_row_count"] == 5, strength
        assert strength["protocol"]["protocol_rows_added"] == 2, strength
        assert strength["protocol"]["invalid_write_response_row_count"] == 1, strength
        assert strength["protocol"]["protocol_checks_passed"] == 20, strength
        assert strength["scoreboard"]["status"] == "pass", strength
        assert handoff_body["checks"]["evidence_strength_summary_has_formal_count"] is True, handoff_body
        assert handoff_body["checks"]["evidence_strength_summary_has_formal_step_count"] is True, handoff_body
        assert handoff_body["checks"]["evidence_strength_summary_has_protocol_count"] is True, handoff_body
        assert handoff_body["readiness"]["development_ready"] is True, handoff_body
        assert handoff_body["readiness"]["signoff_ready"] is False, handoff_body
        assert "closure_profile is development, not signoff" in handoff_body["readiness"]["not_ready_reasons"], handoff_body
        handoff_check = call({"tool": "oag.check", "arguments": {"ip_dir": str(ip), "stage": "handoff"}})
        assert handoff_check["result"]["ok"] is True, handoff_check
        zero_strength_ip = make_ip(Path(tmp) / "zero_strength")
        zero_handoff = call(
            {
                "tool": "oag.handoff",
                "arguments": {
                    "ip_dir": str(zero_strength_ip),
                    "stage": "handoff",
                    "intent": "smoke zero-count development handoff",
                    "actor": {"kind": "ai", "id": "codex", "surface": "smoke"},
                },
            }
        )
        assert zero_handoff["result"]["recorded"] is True, zero_handoff
        zero_body = zero_handoff["result"]["handoff"]
        assert zero_body["evidence_strength_summary"]["formal"]["property_count"] == 0, zero_body
        assert zero_body["evidence_strength_summary"]["formal"]["bounded_property_step_checks"] == 0, zero_body
        assert zero_body["evidence_strength_summary"]["protocol"]["protocol_row_count"] == 0, zero_body
        assert zero_body["evidence_strength_summary"]["protocol"]["protocol_check_count"] == 0, zero_body
        assert zero_body["checks"]["evidence_strength_summary_has_formal_count"] is True, zero_body
        assert zero_body["checks"]["evidence_strength_summary_has_formal_step_count"] is True, zero_body
        assert zero_body["checks"]["evidence_strength_summary_has_protocol_count"] is True, zero_body
        zero_handoff_check = call({"tool": "oag.check", "arguments": {"ip_dir": str(zero_strength_ip), "stage": "handoff"}})
        assert not any("handoff report check failed" in issue for issue in zero_handoff_check["result"]["issues"]), zero_handoff_check
        draft = call(
            {
                "tool": "oag.draft",
                "arguments": {
                    "ip_dir": str(ip),
                    "stage": "req",
                    "title": "counter requirement interview round 1",
                    "summary": "Captured draft requirement facts before locked-truth promotion.",
                    "facts": ["AXI data width is 256 bits"],
                    "open_questions": ["Which reset value is architecturally locked?"],
                    "actor": {"kind": "ai", "id": "codex", "surface": "smoke"},
                },
            }
        )
        assert draft["result"]["status"] == "draft", draft
        assert Path(draft["result"]["draft_path"]).is_file(), draft
        assert Path(draft["result"]["markdown_path"]).is_file(), draft
        assert draft["result"]["scope_lock"]["state"] == "draft", draft
        assert draft["result"]["scope_update"], draft
        unlocked_decide = call({"tool": "oag.decide", "arguments": {"ip_dir": str(ip), "action": "claim_complete", "stage": "sim"}})
        assert unlocked_decide["result"]["allowed"] is False, unlocked_decide
        assert unlocked_decide["result"]["reason"] == "scope_lock_required", unlocked_decide
        relocked = call(
            {
                "tool": "oag.lock",
                "arguments": {
                    "ip_dir": str(ip),
                    "summary": "Smoke owner reconfirmed scope after the interview draft.",
                    "confirmed_scope": ["demo counter reset/count scoreboard closure remains approved"],
                    "source_draft": draft["result"]["id"],
                    "actor": {"kind": "human", "id": "smoke-owner", "surface": "smoke"},
                    "approval": {
                        "kind": "human",
                        "approved": True,
                        "approved_by": "smoke-owner",
                        "reason": "Smoke owner reconfirmed the semantically ready scope after the interview draft.",
                    },
                },
            }
        )
        assert relocked["result"]["locked"] is True, relocked
        context = call({"tool": "oag.context", "arguments": {"ip_dir": str(ip), "stage": "sim", "intent": "scoreboard"}})
        assert "IP KNOWLEDGE LEDGER" in context["result"]["prompt_block"], context
        assert "scope_lock=locked" in context["result"]["prompt_block"], context
        cache_path = ROOT / ".cache" / "context_inject.json"
        cache_path.unlink(missing_ok=True)
        context_payload = {"ip_dir": str(ip), "stage": "sim", "prompt": f"Continue sim work for {ip.name}"}
        context_first = context_hook(context_payload)
        assert context_first.returncode == 0, context_first.stderr or context_first.stdout
        assert "OAG CONTEXT INJECTION" in hook_context(context_first), context_first.stdout
        context_duplicate = context_hook(context_payload)
        assert context_duplicate.returncode == 0, context_duplicate.stderr or context_duplicate.stdout
        assert context_duplicate.stdout == "", context_duplicate.stdout
        context_high_pressure = context_hook({**context_payload, "context_pressure": "high"})
        assert context_high_pressure.returncode == 0, context_high_pressure.stderr or context_high_pressure.stdout
        if context_high_pressure.stdout:
            assert "OAG CONTEXT INJECTION" in hook_context(context_high_pressure), context_high_pressure.stdout
        context_post_compact = context_hook({**context_payload, "hook_event_name": "PostCompact"})
        assert context_post_compact.returncode == 0, context_post_compact.stderr or context_post_compact.stdout
        assert context_post_compact.stdout == "", context_post_compact.stdout
        context_recovery = context_hook(context_payload)
        assert context_recovery.returncode == 0, context_recovery.stderr or context_recovery.stdout
        recovery_payload = json.loads(context_recovery.stdout)
        assert recovery_payload["hookSpecificOutput"]["hookEventName"] == "UserPromptSubmit", recovery_payload
        assert "OAG CONTEXT INJECTION" in hook_context(context_recovery), context_recovery.stdout
        route_root = Path(tmp) / "hook_route_project"
        for name, run_id in (("route_alpha", "RUN_ALPHA"), ("route_beta", "RUN_BETA")):
            route_ip = route_root / name
            (route_ip / "ontology" / "runs").mkdir(parents=True)
            (route_ip / "rtl").mkdir(parents=True)
            (route_ip / "tb" / "uvm").mkdir(parents=True)
            (route_ip / "ontology" / "ip.yaml").write_text(f"ip: {name}\n", encoding="utf-8")
            (route_ip / "rtl" / "unit.sv").write_text(f"module {name}_unit; endmodule\n", encoding="utf-8")
            (route_ip / "rtl" / f"{name}_only.sv").write_text(f"module {name}_only; endmodule\n", encoding="utf-8")
            (route_ip / "tb" / "uvm" / "unit_tb.sv").write_text("module unit_tb; endmodule\n", encoding="utf-8")
            (route_ip / "ontology" / "runs" / "active_run.json").write_text(
                json.dumps({"run_id": run_id, "status": "in_progress"}) + "\n",
                encoding="utf-8",
            )
        (route_root / "not_an_ip" / "rtl").mkdir(parents=True)
        (route_root / "not_an_ip" / "rtl" / "unit.sv").write_text("module outside; endmodule\n", encoding="utf-8")
        assert hook_target_names(route_root, {"prompt": "승인", "context_pressure": "critical"}, require_signal=False) == []
        assert hook_target_names(route_root, {"prompt": "oag context"}, require_signal=True) == []
        assert hook_target_names(route_root, {"prompt": "OAG context"}, require_signal=True) == []
        assert hook_target_names(route_root, {"prompt": "route OAG"}, require_signal=True) == []
        assert hook_target_names(route_root, {"prompt": "continue route_alpha OAG"}, require_signal=True) == ["route_alpha"]
        assert hook_target_names(route_root, {"prompt": "compare route_alpha and route_beta OAG"}, require_signal=True) == []
        assert hook_target_names(route_root, {"ip_dir": str(route_root / "route_beta"), "prompt": "승인"}, require_signal=False) == ["route_beta"]
        assert hook_target_names(route_root, {"prompt": "Find and fix a bug in @route_alpha/rtl/unit.sv"}, require_signal=True) == ["route_alpha"]
        assert hook_target_names(route_root, {"prompt": "Find and fix a bug in `route_alpha/tb/uvm/unit_tb.sv`"}, require_signal=True) == ["route_alpha"]
        assert hook_target_names(route_root, {"prompt": f"Find and fix a bug in @{route_root / 'route_beta' / 'rtl' / 'unit.sv'}"}, require_signal=True) == ["route_beta"]
        assert hook_target_names(route_root, {"prompt": "Find and fix a bug in @route_alpha_only.sv"}, require_signal=True) == ["route_alpha"]
        assert hook_target_names(route_root, {"prompt": "Find and fix a bug in @unit.sv"}, require_signal=True) == []
        assert hook_target_names(route_root, {"prompt": "Fix @route_alpha/rtl/unit.sv and @route_beta/rtl/unit.sv"}, require_signal=True) == []
        assert hook_target_names(route_root, {"prompt": "Find and fix a bug in @not_an_ip/rtl/unit.sv"}, require_signal=True) == []
        single_route_root = Path(tmp) / "single_hook_route_project"
        single_route_ip = single_route_root / "solo_route"
        (single_route_ip / "ontology" / "runs").mkdir(parents=True)
        (single_route_ip / "ontology" / "ip.yaml").write_text("ip: solo_route\n", encoding="utf-8")
        (single_route_ip / "ontology" / "runs" / "active_run.json").write_text(
            json.dumps({"run_id": "RUN_SOLO", "status": "in_progress"}) + "\n",
            encoding="utf-8",
        )
        assert hook_target_names(single_route_root, {"prompt": "rtl work"}, require_signal=True) == []
        assert hook_target_names(single_route_root, {"prompt": "ipdev rtl work"}, require_signal=True) == []
        assert hook_target_names(single_route_root, {"prompt": "OAG rtl work"}, require_signal=True) == []
        assert hook_target_names(single_route_root, {"prompt": "please use oag for rtl work"}, require_signal=True) == []
        assert hook_target_names(single_route_root, {"prompt": "oag rtl work"}, require_signal=True) == ["solo_route"]
        write_closure_reports(ip)
        undecided = call({"tool": "oag.decide", "arguments": {"ip_dir": str(ip), "action": "claim_complete", "stage": "sim"}})
        assert undecided["result"]["allowed"] is False, undecided
        assert undecided["result"]["reason"] == "decision_receipt_required", undecided
        missing_approval = call(
            {
                "tool": "oag.decide",
                "arguments": {
                    "ip_dir": str(ip),
                    "action": "claim_complete",
                    "stage": "sim",
                    "record_decision": True,
                    "actor": {"kind": "ai", "id": "codex", "surface": "smoke"},
                },
            }
        )
        assert missing_approval["result"]["allowed"] is False, missing_approval
        assert missing_approval["result"]["reason"] == "completion_approval_required", missing_approval
        approved_without_reason = call(
            {
                "tool": "oag.decide",
                "arguments": {
                    "ip_dir": str(ip),
                    "action": "claim_complete",
                    "stage": "sim",
                    "record_decision": True,
                    "approval": {"approved": True},
                    "actor": {"kind": "ai", "id": "codex", "surface": "smoke"},
                },
            }
        )
        assert approved_without_reason["result"]["allowed"] is False, approved_without_reason
        assert approved_without_reason["result"]["reason"] == "completion_approval_required", approved_without_reason
        human_without_reason = call(
            {
                "tool": "oag.decide",
                "arguments": {
                    "ip_dir": str(ip),
                    "action": "claim_complete",
                    "stage": "sim",
                    "record_decision": True,
                    "actor": {"kind": "human", "id": "smoke-owner", "surface": "smoke"},
                },
            }
        )
        assert human_without_reason["result"]["allowed"] is False, human_without_reason
        assert human_without_reason["result"]["reason"] == "completion_approval_required", human_without_reason
        approved_by_reason = call(
            {
                "tool": "oag.decide",
                "arguments": {
                    "ip_dir": str(ip),
                    "action": "claim_complete",
                    "stage": "sim",
                    "record_decision": True,
                    "approved_by": "smoke-owner",
                    "approval_reason": "smoke owner approved claim_complete through approved_by",
                    "actor": {"kind": "ai", "id": "codex", "surface": "smoke"},
                },
            }
        )
        assert approved_by_reason["result"]["allowed"] is False, approved_by_reason
        assert approved_by_reason["result"]["reason"] == "completion_approval_required", approved_by_reason
        assert approved_by_reason["result"]["approval"]["approved"] is False, approved_by_reason
        decide = call(
            {
                "tool": "oag.decide",
                "arguments": {
                    "ip_dir": str(ip),
                    "action": "claim_complete",
                    "stage": "sim",
                    "record_decision": True,
                    "approval": {
                        "kind": "human",
                        "approved": True,
                        "approved_by": "smoke-owner",
                        "reason": "smoke owner approved claim_complete",
                    },
                    "actor": {"kind": "human", "id": "smoke-owner", "surface": "smoke"},
                },
            }
        )
        assert decide["result"]["allowed"] is True, decide
        assert Path(decide["result"]["decision_receipt"]["path"]).is_file(), decide
        signoff_blocked = call({"tool": "oag.decide", "arguments": {"ip_dir": str(ip), "action": "signoff", "stage": "signoff"}})
        assert signoff_blocked["result"]["allowed"] is False, signoff_blocked
        assert signoff_blocked["result"]["reason"] == "closure_profile_not_signoff", signoff_blocked
        policies = ip / "ontology" / "policies.yaml"
        policies.write_text(policies.read_text(encoding="utf-8").replace("closure_profile: development", "closure_profile: signoff"), encoding="utf-8")
        approval = call(
            {
                "tool": "oag.record",
                "arguments": {
                    "ip_dir": str(ip),
                    "stage": "signoff",
                    "type": "decision",
                    "claim": "human approval to enter signoff closure profile",
                    "summary": "Human owner approved the protected policy transition to signoff.",
                    "actor": {"kind": "human", "id": "smoke-owner", "surface": "smoke"},
                    "approval": {
                        "kind": "human",
                        "approved": True,
                        "approved_by": "smoke-owner",
                        "reason": "smoke signoff path",
                    },
                    "status": "open",
                },
            }
        )
        assert approval["result"]["ledger_event"], approval
        compiled = call({"tool": "oag.compile", "arguments": {"ip_dir": str(ip)}})
        assert compiled["result"]["status"] == "pass", compiled
        write_stage_receipt(ip, "sim")
        write_closure_reports(ip)
        signoff_without_review = call({"tool": "oag.decide", "arguments": {"ip_dir": str(ip), "action": "signoff", "stage": "signoff"}})
        assert signoff_without_review["result"]["allowed"] is False, signoff_without_review
        assert signoff_without_review["result"]["reason"] == "reviewer_receipt_required", signoff_without_review
        fake_review_path = ip / "ontology" / "validations" / "REV_SELF_ALLOWED.json"
        fake_review_path.write_text(
            json.dumps(
                {
                    "schema_version": "oag_reviewer_receipt.v1",
                    "id": "REV_SELF_ALLOWED",
                    "ip": ip.name,
                    "action": "signoff",
                    "allowed": True,
                    "reason": "allowed",
                    "verdict": "pass",
                    "actor": {"kind": "ai", "id": "codex", "surface": "smoke"},
                    "producer_actor": {"kind": "ai", "id": "codex", "surface": "smoke"},
                    "independent": False,
                    "findings": [],
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        signoff_with_non_independent_review = call({"tool": "oag.decide", "arguments": {"ip_dir": str(ip), "action": "signoff", "stage": "signoff"}})
        assert signoff_with_non_independent_review["result"]["allowed"] is False, signoff_with_non_independent_review
        assert signoff_with_non_independent_review["result"]["reason"] == "reviewer_receipt_required", signoff_with_non_independent_review
        review = call(
            {
                "tool": "oag.review",
                "arguments": {
                    "ip_dir": str(ip),
                    "action": "signoff",
                    "stage": "signoff",
                    "verdict": "pass",
                    "actor": {"kind": "ai", "id": "oag-gate-reviewer", "surface": "smoke"},
                    "producer_actor": {"kind": "ai", "id": "codex", "surface": "smoke"},
                    "findings": [],
                },
            }
        )
        assert review["result"]["allowed"] is True, review
        assert Path(review["result"]["reviewer_receipt"]["path"]).is_file(), review
        signoff = call(
            {
                "tool": "oag.decide",
                "arguments": {
                    "ip_dir": str(ip),
                    "action": "signoff",
                    "stage": "signoff",
                    "record_decision": True,
                    "approval": {
                        "kind": "human",
                        "approved": True,
                        "approved_by": "smoke-owner",
                        "reason": "smoke owner approved signoff after independent review",
                    },
                    "actor": {"kind": "human", "id": "smoke-owner", "surface": "smoke"},
                },
            }
        )
        assert signoff["result"]["allowed"] is True, signoff
        assert Path(signoff["result"]["decision_receipt"]["path"]).is_file(), signoff
        ticket = call(
            {
                "tool": "oag.ticket",
                "arguments": {
                    "ip_dir": str(ip),
                    "stage": "sim",
                    "reason": "scoreboard mismatch example",
                    "failing_contract": {"id": "CONTRACT_SIM_SCOREBOARD"},
                    "expected": {"count": 3},
                    "observed": {"count": 2},
                    "evidence": {"files": ["sim/scoreboard_events.jsonl"]},
                    "editable_files": ["rtl/demo_counter_cx1.sv"],
                    "required_evidence_after_patch": ["sim/results.xml", "sim/scoreboard_events.jsonl"],
                },
            }
        )
        assert ticket["result"]["owner_workflow"] == "tb", ticket
        assert Path(ticket["result"]["path"]).is_file(), ticket
        graph_json = Path(tmp) / "ontology_graph.json"
        graph_html = Path(tmp) / "ontology_graph.html"
        graph_proc = subprocess.run(
            [
                sys.executable,
                str(GRAPH),
                "build",
                "--ip-dir",
                str(ip),
                "--stage",
                "sim",
                "--intent",
                "scoreboard",
                "--json-out",
                str(graph_json),
                "--html-out",
                str(graph_html),
            ],
            text=True,
            capture_output=True,
            check=False,
            cwd=ROOT,
            env={**os.environ, "OAG_DISABLE_BACKEND": "1"},
        )
        assert graph_proc.returncode == 0, graph_proc.stderr or graph_proc.stdout
        graph_data = json.loads(graph_json.read_text(encoding="utf-8"))
        assert graph_data["schema_version"] == "oag_ontology_graph.v1", graph_data
        assert graph_data["stats"]["record_count"] >= 1, graph_data
        assert any(node["type"] == "obligation" for node in graph_data["graph"]["nodes"]), graph_data
        assert any(node["type"] == "structure" for node in graph_data["graph"]["nodes"]), graph_data
        assert any(node["type"] == "module" for node in graph_data["graph"]["nodes"]), graph_data
        assert any(node["type"] == "authoring_packet" for node in graph_data["graph"]["nodes"]), graph_data
        assert any(node["type"] == "rule" for node in graph_data["graph"]["nodes"]), graph_data
        assert any(node["type"] == "rule_instance" for node in graph_data["graph"]["nodes"]), graph_data
        assert any(node["type"] == "draft" for node in graph_data["graph"]["nodes"]), graph_data
        assert any(node["type"] == "protection" for node in graph_data["graph"]["nodes"]), graph_data
        assert any(node["type"] == "ledger" for node in graph_data["graph"]["nodes"]), graph_data
        assert any(node["type"] == "stage" for node in graph_data["graph"]["nodes"]), graph_data
        assert any(node["type"] == "decision" for node in graph_data["graph"]["nodes"]), graph_data
        assert any(node["type"] == "run" for node in graph_data["graph"]["nodes"]), graph_data
        assert any(node["type"] == "ticket" for node in graph_data["graph"]["nodes"]), graph_data
        assert "OAG Ontology Graph" in graph_html.read_text(encoding="utf-8")
        portable_archive = Path(tmp) / "oag_portable_smoke.tar.gz"
        portable_export = subprocess.run(
            [
                sys.executable,
                str(PORTABLE_DB),
                "export",
                "--root",
                tmp,
                "--ip",
                ip.name,
                "--out",
                str(portable_archive),
                "--no-artifacts",
            ],
            text=True,
            capture_output=True,
            check=False,
            cwd=ROOT.parent,
        )
        assert portable_export.returncode == 0, portable_export.stderr or portable_export.stdout
        portable_summary = json.loads(portable_export.stdout)
        assert portable_summary["status"] == "pass", portable_summary
        assert portable_summary["file_count"] > 0, portable_summary
        portable_inspect = subprocess.run(
            [sys.executable, str(PORTABLE_DB), "inspect", str(portable_archive)],
            text=True,
            capture_output=True,
            check=False,
            cwd=ROOT.parent,
        )
        assert portable_inspect.returncode == 0, portable_inspect.stderr or portable_inspect.stdout
        portable_manifest = json.loads(portable_inspect.stdout)
        assert portable_manifest["schema_version"] == "oag_portable_db.v1", portable_manifest
        import_dest = Path(tmp) / "portable_import"
        portable_import = subprocess.run(
            [
                sys.executable,
                str(PORTABLE_DB),
                "import",
                str(portable_archive),
                "--dest",
                str(import_dest),
                "--dry-run",
            ],
            text=True,
            capture_output=True,
            check=False,
            cwd=ROOT.parent,
        )
        assert portable_import.returncode == 0, portable_import.stderr or portable_import.stdout
        assert json.loads(portable_import.stdout)["changed"] == portable_summary["file_count"], portable_import.stdout
        okf_dir = Path(tmp) / "okf_bundle"
        okf_export = subprocess.run(
            [
                sys.executable,
                str(OKF),
                "export",
                "--ip-dir",
                str(ip),
                "--out",
                str(okf_dir),
                "--force",
            ],
            text=True,
            capture_output=True,
            check=False,
            cwd=ROOT.parent,
            env={**os.environ, "OAG_DISABLE_BACKEND": "1"},
        )
        assert okf_export.returncode == 0, okf_export.stderr or okf_export.stdout
        okf_summary = json.loads(okf_export.stdout)
        assert okf_summary["status"] == "pass", okf_summary
        assert okf_summary["counts"]["requirements"] >= 1, okf_summary
        assert (okf_dir / "index.md").is_file(), okf_summary
        assert (okf_dir / "requirements").is_dir(), okf_summary
        okf_validate = subprocess.run(
            [sys.executable, str(OKF), "validate", str(okf_dir)],
            text=True,
            capture_output=True,
            check=False,
            cwd=ROOT.parent,
        )
        assert okf_validate.returncode == 0, okf_validate.stderr or okf_validate.stdout
        okf_validation = json.loads(okf_validate.stdout)
        assert okf_validation["ok"] is True, okf_validation
        assert okf_validation["concept_count"] >= okf_summary["counts"]["requirements"], okf_validation
        okf_obsidian_dir = Path(tmp) / "okf_obsidian_bundle"
        okf_obsidian_export = subprocess.run(
            [
                sys.executable,
                str(OKF),
                "export",
                "--profile",
                "obsidian",
                "--ip-dir",
                str(ip),
                "--out",
                str(okf_obsidian_dir),
                "--force",
            ],
            text=True,
            capture_output=True,
            check=False,
            cwd=ROOT.parent,
            env={**os.environ, "OAG_DISABLE_BACKEND": "1"},
        )
        assert okf_obsidian_export.returncode == 0, okf_obsidian_export.stderr or okf_obsidian_export.stdout
        okf_obsidian_summary = json.loads(okf_obsidian_export.stdout)
        assert okf_obsidian_summary["profile"] == "obsidian", okf_obsidian_summary
        assert (okf_obsidian_dir / "OAG Knowledge.base").is_file(), okf_obsidian_summary
        obsidian_index = (okf_obsidian_dir / "index.md").read_text(encoding="utf-8")
        assert "[[OAG Knowledge.base|OAG Knowledge Base views]]" in obsidian_index, obsidian_index
        obsidian_requirement = next(
            path for path in (okf_obsidian_dir / "requirements").glob("*.md") if path.name != "index.md"
        )
        obsidian_requirement_text = obsidian_requirement.read_text(encoding="utf-8")
        assert "aliases:" in obsidian_requirement_text, obsidian_requirement_text
        assert "oag_kind: \"requirement\"" in obsidian_requirement_text, obsidian_requirement_text
        obsidian_obligation = next(
            path for path in (okf_obsidian_dir / "obligations").glob("*.md") if path.name != "index.md"
        )
        assert "[[contracts/" in obsidian_obligation.read_text(encoding="utf-8"), obsidian_obligation
        okf_obsidian_validate = subprocess.run(
            [sys.executable, str(OKF), "validate", str(okf_obsidian_dir)],
            text=True,
            capture_output=True,
            check=False,
            cwd=ROOT.parent,
        )
        assert okf_obsidian_validate.returncode == 0, okf_obsidian_validate.stderr or okf_obsidian_validate.stdout
        okf_obsidian_validation = json.loads(okf_obsidian_validate.stdout)
        assert okf_obsidian_validation["ok"] is True, okf_obsidian_validation
        okf_import_ip = make_ip(Path(tmp) / "okf_import")
        okf_locked_truth_before = sha256(okf_import_ip / "req" / "locked_truth.md")
        okf_ontology_before = sha256(okf_import_ip / "ontology" / "requirements.yaml")
        okf_import = subprocess.run(
            [
                sys.executable,
                str(OKF),
                "import-draft",
                str(okf_dir),
                "--ip-dir",
                str(okf_import_ip),
                "--title",
                "smoke OKF import draft",
            ],
            text=True,
            capture_output=True,
            check=False,
            cwd=ROOT.parent,
            env={**os.environ, "OAG_DISABLE_BACKEND": "1"},
        )
        assert okf_import.returncode == 0, okf_import.stderr or okf_import.stdout
        okf_import_summary = json.loads(okf_import.stdout)
        assert okf_import_summary["status"] == "pass", okf_import_summary
        assert okf_import_summary["canonical_sources_preserved"] is True, okf_import_summary
        assert okf_import_summary["draft"]["status"] == "draft", okf_import_summary
        assert Path(okf_import_summary["draft"]["draft_path"]).is_file(), okf_import_summary
        assert sha256(okf_import_ip / "req" / "locked_truth.md") == okf_locked_truth_before, okf_import_summary
        assert sha256(okf_import_ip / "ontology" / "requirements.yaml") == okf_ontology_before, okf_import_summary
        okf_rtl_ip = make_ip(Path(tmp) / "okf_rtl")
        (okf_rtl_ip / "list" / "rtl.f").write_text("rtl/demo_counter_cx1.sv\n", encoding="utf-8")
        (okf_rtl_ip / "rtl" / "demo_counter_cx1.sv").write_text(
            "\n".join(
                [
                    "module demo_counter_cx1(",
                    "    input logic clk_i,",
                    "    input logic rst_ni,",
                    "    output logic [7:0] count_o",
                    ");",
                    "    assign count_o = rst_ni ? 8'h01 : 8'h00;",
                    "endmodule",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        okf_rtl_compile = call({"tool": "oag.compile", "arguments": {"ip_dir": str(okf_rtl_ip)}})
        assert okf_rtl_compile["result"]["stats"]["design_facts_modules"] >= 1, okf_rtl_compile
        okf_rtl_dir = Path(tmp) / "okf_rtl_bundle"
        okf_rtl_export = subprocess.run(
            [
                sys.executable,
                str(OKF),
                "export",
                "--ip-dir",
                str(okf_rtl_ip),
                "--out",
                str(okf_rtl_dir),
                "--force",
            ],
            text=True,
            capture_output=True,
            check=False,
            cwd=ROOT.parent,
            env={**os.environ, "OAG_DISABLE_BACKEND": "1"},
        )
        assert okf_rtl_export.returncode == 0, okf_rtl_export.stderr or okf_rtl_export.stdout
        okf_rtl_validate = subprocess.run(
            [sys.executable, str(OKF), "validate", str(okf_rtl_dir)],
            text=True,
            capture_output=True,
            check=False,
            cwd=ROOT.parent,
        )
        assert okf_rtl_validate.returncode == 0, okf_rtl_validate.stderr or okf_rtl_validate.stdout
        module_page = okf_rtl_dir / "design" / "modules" / "demo_counter_cx1.md"
        assert module_page.is_file(), module_page
        assert "source_file: \"rtl/demo_counter_cx1.sv\"" in module_page.read_text(encoding="utf-8"), module_page
        assert "- Source: `rtl/demo_counter_cx1.sv`" in module_page.read_text(encoding="utf-8"), module_page
        eval_proc = subprocess.run(
            [sys.executable, str(EVAL), "--json"],
            text=True,
            capture_output=True,
            check=False,
            cwd=ROOT.parent,
            env={**os.environ, "OAG_DISABLE_BACKEND": "1"},
        )
        assert eval_proc.returncode == 0, eval_proc.stderr or eval_proc.stdout
        eval_report = json.loads(eval_proc.stdout)
        assert eval_report["schema_version"] == "oag_evaluation_report.v1", eval_report
        assert eval_report["ok"] is True, eval_report
        assert eval_report["passed"] == eval_report["total"], eval_report
        assert eval_report["total"] >= 14, eval_report
        answer_key_proc = subprocess.run(
            [sys.executable, str(ANSWER_KEY_EVAL), "--json", "--speed-scale", "5"],
            text=True,
            capture_output=True,
            check=False,
            cwd=ROOT.parent,
            env={**os.environ, "OAG_DISABLE_BACKEND": "1"},
        )
        assert answer_key_proc.returncode == 0, answer_key_proc.stderr or answer_key_proc.stdout
        answer_key_report = json.loads(answer_key_proc.stdout)
        assert answer_key_report["schema_version"] == "oag_answer_key_report.v1", answer_key_report
        assert answer_key_report["ok"] is True, answer_key_report
        assert answer_key_report["score"] == 1.0, answer_key_report
        needs_human_ip = make_ip(Path(tmp) / "needs_human_run")
        needs_human_run = call(
            {
                "tool": "oag.run.start",
                "arguments": {
                    "ip_dir": str(needs_human_ip),
                    "stage": "sim",
                    "intent": "smoke repeated blocker",
                    "actor": {"kind": "ai", "id": "codex", "surface": "smoke"},
                },
            }
        )
        needs_human_run_id = needs_human_run["result"]["run_id"]
        needs_human_checkpoint = call(
            {
                "tool": "oag.run.checkpoint",
                "arguments": {
                    "ip_dir": str(needs_human_ip),
                    "run_id": needs_human_run_id,
                    "stage": "sim",
                    "intent": "smoke repeated blocker",
                    "max_blocker_repeats": 1,
                    "actor": {"kind": "ai", "id": "codex", "surface": "smoke"},
                },
            }
        )
        assert needs_human_checkpoint["result"]["status"] == "needs_human", needs_human_checkpoint
        stop_hook_human = stop_gate({"ip_dir": str(needs_human_ip), "run_id": needs_human_run_id})
        assert stop_hook_human.returncode == 0, stop_hook_human.stderr or stop_hook_human.stdout
        assert json.loads(stop_hook_human.stdout)["decision"] == "block", stop_hook_human.stdout
        explicit_ip = make_ip(Path(tmp) / "bad_explicit_validation")
        draftish = call(
            {
                "tool": "oag.record",
                "arguments": {
                    "ip_dir": str(explicit_ip),
                    "stage": "sim",
                    "claim": "evidence without explicit validation status",
                    "actor": {"kind": "ai", "id": "codex", "surface": "smoke"},
                    "rocev": {
                        "obligation": {"id": "OBL_DEMO_COUNTER_CX1_RESET_KNOWN"},
                        "contract": {"id": "CONTRACT_DEMO_COUNTER_CX1_SIM_SCOREBOARD", "method": "scoreboard"},
                        "evidence": {"files": ["sim/results.xml"], "tests": [], "commit": ""},
                        "validation": {"verdict": "pass", "rationale": "missing explicit status"},
                    },
                },
            }
        )
        assert draftish["result"]["status"] == "open", draftish
        explicit_check = call({"tool": "oag.check", "arguments": {"ip_dir": str(explicit_ip)}})
        assert explicit_check["result"]["ok"] is False, explicit_check
        assert any("closure requires all_of contract validation" in issue for issue in explicit_check["result"]["issues"]), explicit_check
        rejected_closed = call_process(
            {
                "tool": "oag.record",
                "arguments": {
                    "ip_dir": str(explicit_ip),
                    "stage": "sim",
                    "status": "closed",
                    "claim": "top-level closed without validation status",
                    "actor": {"kind": "ai", "id": "codex", "surface": "smoke"},
                    "rocev": {
                        "obligation": {"id": "OBL_DEMO_COUNTER_CX1_RESET_KNOWN"},
                        "contract": {"id": "CONTRACT_DEMO_COUNTER_CX1_SIM_SCOREBOARD", "method": "scoreboard"},
                        "evidence": {"files": ["sim/results.xml"], "tests": [], "commit": ""},
                        "validation": {"verdict": "pass", "rationale": "top-level close only"},
                    },
                },
            }
        )
        assert rejected_closed.returncode != 0, rejected_closed.stdout
        assert "closed records require explicit rocev.validation.status" in json.loads(rejected_closed.stdout)["errors"][0], rejected_closed.stdout
        freshness_ip = make_ip(Path(tmp) / "bad_freshness")
        fresh_record = call(
            {
                "tool": "oag.record",
                "arguments": {
                    "ip_dir": str(freshness_ip),
                    "stage": "sim",
                    "claim": "fresh evidence baseline",
                    "actor": {"kind": "ai", "id": "codex", "surface": "smoke"},
                    "rocev": {
                        "obligation": {"id": "OBL_DEMO_COUNTER_CX1_RESET_KNOWN"},
                        "contract": {"id": "CONTRACT_DEMO_COUNTER_CX1_SIM_SCOREBOARD", "method": "scoreboard"},
                        "evidence": {"files": ["sim/results.xml"], "tests": [], "commit": ""},
                        "validation": {"status": "closed", "verdict": "pass", "rationale": "hash baseline"},
                    },
                },
            }
        )
        assert fresh_record["result"]["status"] == "closed", fresh_record
        (freshness_ip / "sim" / "results.xml").write_text('<testsuite failures="1"/>\n', encoding="utf-8")
        freshness_check = call({"tool": "oag.check", "arguments": {"ip_dir": str(freshness_ip)}})
        assert freshness_check["result"]["ok"] is False, freshness_check
        assert any("evidence file stale: sim/results.xml" in issue for issue in freshness_check["result"]["issues"]), freshness_check
        bad_ip = make_ip(Path(tmp) / "bad")
        bad_row = {
            "goal_id": "GOAL_BAD",
            "scenario_id": "SC_BAD",
            "cycle": 1,
            "stimulus": {},
            "expected": {"count": 1},
            "observed": {"count": 1},
            "passed": True,
            "mismatch": "",
            "coverage_refs": [],
        }
        (bad_ip / "sim" / "scoreboard_events.jsonl").write_text(json.dumps(bad_row) + "\n", encoding="utf-8")
        bad_inspect = call({"tool": "oag.inspect", "arguments": {"ip_dir": str(bad_ip), "stage": "sim"}})
        assert bad_inspect["result"]["validation"] == "partial", bad_inspect
        assert "scoreboard schema has invalid rows" in bad_inspect["result"]["gaps"], bad_inspect
        dev_validator_ip = make_ip(Path(tmp) / "dev_validator")
        write_ip_validator_report(dev_validator_ip)
        write_stage_receipt(dev_validator_ip, "sim")
        dev_validator_record = close_demo_counter(
            dev_validator_ip,
            claim="development validator positive smoke",
            evidence_files=[
                "rtl/rtl_compile.json",
                "lint/dut_lint.json",
                "sim/results.xml",
                "sim/scoreboard_events.jsonl",
                "cov/coverage.json",
                "signoff/ip_validator_report.json",
                "ontology/evidence/stage_runs/sim.json",
            ],
        )
        assert dev_validator_record["result"]["status"] == "closed", dev_validator_record
        dev_validator_proc = run_dev_validator(dev_validator_ip)
        assert dev_validator_proc.returncode == 0, dev_validator_proc.stderr or dev_validator_proc.stdout
        dev_validator_report = json.loads(dev_validator_proc.stdout)
        assert dev_validator_report["status"] == "pass", dev_validator_report
        assert dev_validator_report["failed_gates"] == [], dev_validator_report
        dev_validator_gates = {gate["id"]: gate for gate in dev_validator_report["gates"]}
        assert dev_validator_gates["scoreboard_rows_v1"]["status"] == "pass", dev_validator_report
        assert dev_validator_gates["stage_run_receipts"]["status"] == "pass", dev_validator_report
        assert dev_validator_gates["oag_check"]["status"] == "pass", dev_validator_report
        bad_validator_ip = make_ip(Path(tmp) / "bad_dev_validator")
        bad_validator_row = {
            "goal_id": "GOAL_BAD_VALIDATOR",
            "scenario_id": "SC_BAD_VALIDATOR",
            "cycle": 1,
            "stimulus": {},
            "expected": {"count": 1},
            "observed": {"count": 1},
            "passed": True,
            "mismatch": "",
            "coverage_refs": [],
        }
        (bad_validator_ip / "sim" / "scoreboard_events.jsonl").write_text(json.dumps(bad_validator_row) + "\n", encoding="utf-8")
        write_ip_validator_report(bad_validator_ip)
        write_stage_receipt(bad_validator_ip, "sim")
        bad_validator_proc = run_dev_validator(bad_validator_ip)
        assert bad_validator_proc.returncode != 0, bad_validator_proc.stdout
        bad_validator_report = json.loads(bad_validator_proc.stdout)
        assert bad_validator_report["status"] == "fail", bad_validator_report
        assert "scoreboard_rows_v1" in bad_validator_report["failed_gates"], bad_validator_report
        bad_validator_gates = {gate["id"]: gate for gate in bad_validator_report["gates"]}
        assert any("observed_source" in issue for issue in bad_validator_gates["scoreboard_rows_v1"]["issues"]), bad_validator_report
        loop_spec = Path(tmp) / "loop_spec.md"
        loop_spec.write_text(
            "\n".join(
                [
                    "# Demo counter spec",
                    "",
                    "- Reset drives count to zero.",
                    "- Valid cycles increment count.",
                    "- Scoreboard evidence must be DUT-facing.",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        spec_loop_ip = make_ip(Path(tmp) / "spec_to_rtl_loop")
        write_ip_validator_report(spec_loop_ip)
        write_stage_receipt(spec_loop_ip, "sim")
        spec_loop_record = close_demo_counter(
            spec_loop_ip,
            claim="spec-to-RTL loop positive smoke",
            evidence_files=[
                "rtl/rtl_compile.json",
                "lint/dut_lint.json",
                "sim/results.xml",
                "sim/scoreboard_events.jsonl",
                "cov/coverage.json",
                "signoff/ip_validator_report.json",
                "ontology/evidence/stage_runs/sim.json",
            ],
        )
        assert spec_loop_record["result"]["status"] == "closed", spec_loop_record
        spec_loop_proc = run_spec_to_rtl_loop(spec_loop_ip, loop_spec, metrics=True)
        assert spec_loop_proc.returncode == 0, spec_loop_proc.stderr or spec_loop_proc.stdout
        spec_loop_result = json.loads(spec_loop_proc.stdout)
        assert spec_loop_result["validator"]["status"] == "pass", spec_loop_result
        assert spec_loop_result["auto_research"]["ranked_next_actions"] >= 1, spec_loop_result
        spec_loop_report_path = spec_loop_ip / "signoff" / "ip_research_report.json"
        assert spec_loop_report_path.is_file(), spec_loop_result
        spec_loop_report = json.loads(spec_loop_report_path.read_text(encoding="utf-8"))
        assert spec_loop_report["schema_version"] == "ip_research_report.v1", spec_loop_report
        assert spec_loop_report["checks"]["ranked_next_actions_present"] is True, spec_loop_report
        assert spec_loop_report["ranked_next_actions"][0]["id"] == "SIGNOFF_PROMOTION_REVIEW", spec_loop_report
        spec_loop_check = call({"tool": "oag.check", "arguments": {"ip_dir": str(spec_loop_ip)}})
        assert spec_loop_check["result"]["ok"] is True, spec_loop_check
        spec_loop_metrics = spec_loop_check["result"]["improvement_metrics"]["auto_research"]
        assert spec_loop_metrics["reports"] >= 1, spec_loop_metrics
        assert spec_loop_metrics["actions"] >= 1, spec_loop_metrics
        partial_loop_ip = make_ip(Path(tmp) / "partial_spec_to_rtl_loop")
        partial_loop_proc = run_spec_to_rtl_loop(partial_loop_ip, loop_spec)
        assert partial_loop_proc.returncode == 0, partial_loop_proc.stderr or partial_loop_proc.stdout
        partial_loop_result = json.loads(partial_loop_proc.stdout)
        assert partial_loop_result["validator"]["status"] == "fail", partial_loop_result
        partial_loop_report = json.loads((partial_loop_ip / "signoff" / "ip_research_report.json").read_text(encoding="utf-8"))
        partial_actions = {action["id"]: action for action in partial_loop_report["ranked_next_actions"]}
        assert "IP_SPECIFIC_VALIDATOR" in partial_actions, partial_loop_report
        assert "ROCEV_INSPECT_CLOSURE" in partial_actions or "ROCEV_CHECK" in partial_actions, partial_loop_report
        partial_loop_check = call({"tool": "oag.check", "arguments": {"ip_dir": str(partial_loop_ip)}})
        assert partial_loop_check["result"]["ok"] is False, partial_loop_check
        assert not any(issue.startswith("auto research report") for issue in partial_loop_check["result"]["issues"]), partial_loop_check
        empty_ip = Path(tmp) / "empty_vacuous"
        empty_ip.mkdir()
        empty_compile = call({"tool": "oag.compile", "arguments": {"ip_dir": str(empty_ip)}})
        assert empty_compile["result"]["status"] == "fail", empty_compile
        assert "no requirements in ontology/requirements.yaml" in empty_compile["result"]["issues"], empty_compile
        bad_rules_ip = make_ip(Path(tmp) / "bad_rules")
        (bad_rules_ip / "ontology" / "design_rules.yaml").write_text(
            "\n".join(
                [
                    "schema: oag_design_rules.v1",
                    f"ip: {bad_rules_ip.name}",
                    "rules:",
                    "  - id: RULE_ONLY_SCOREBOARD",
                    "    kind: scoreboard_evidence_schema",
                    "    status: active",
                    "instances: []",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        bad_rules_compile = call({"tool": "oag.compile", "arguments": {"ip_dir": str(bad_rules_ip)}})
        assert bad_rules_compile["result"]["status"] == "fail", bad_rules_compile
        assert "missing required design rule kind: same_cycle_priority_declared" in bad_rules_compile["result"]["issues"], bad_rules_compile
        bad_lang_ip = make_ip(Path(tmp) / "bad_language_policy")
        bad_lang_rules = (bad_lang_ip / "ontology" / "design_rules.yaml").read_text(encoding="utf-8")
        bad_lang_rules = bad_lang_rules.replace(
            "    allowed_constructs: [logic, generate, genvar, generate_for]",
            "    allowed_constructs: [logic]",
            1,
        )
        bad_lang_rules = bad_lang_rules.replace(
            "    forbidden_constructs: [procedural_for, procedural_while, procedural_repeat, procedural_forever, function, task, always_ff, always_comb, always_latch, package, import, interface, modport, typedef, enum, struct, class, program, clocking, bind, dpi, randomization, constraints, unique_priority, assertions, covergroups, mixed_blocking_nonblocking_always]",
            "    forbidden_constructs: [procedural_for, procedural_while, generate_for]",
            1,
        )
        (bad_lang_ip / "ontology" / "design_rules.yaml").write_text(bad_lang_rules, encoding="utf-8")
        bad_lang_compile = call({"tool": "oag.compile", "arguments": {"ip_dir": str(bad_lang_ip)}})
        assert bad_lang_compile["result"]["status"] == "fail", bad_lang_compile
        assert "RULE_RTL_LANGUAGE_SUBSET: rtl language subset must allow generate" in bad_lang_compile["result"]["issues"], bad_lang_compile
        assert "RULE_RTL_LANGUAGE_SUBSET: rtl language subset must not forbid generate constructs" in bad_lang_compile["result"]["issues"], bad_lang_compile
        bad_subset_ip = make_ip(Path(tmp) / "bad_rtl_subset_instance")
        (bad_subset_ip / "rtl").mkdir(exist_ok=True)
        (bad_subset_ip / "rtl" / "demo_counter_cx1.sv").write_text(
            "\n".join(
                [
                    "module demo_counter_cx1(input logic clk);",
                    "  logic tmp;",
                    "  function logic bad_helper;",
                    "    input logic in;",
                    "    begin",
                    "      bad_helper = in;",
                    "    end",
                    "  endfunction",
                    "  always_ff @(posedge clk) begin",
                    "  end",
                    "  always @(posedge clk) begin",
                    "    tmp = 1'b0;",
                    "    tmp <= 1'b1;",
                    "  end",
                    "endmodule",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        (bad_subset_ip / "rtl" / "rtl_compile.json").write_text(
            json.dumps(
                {
                    "schema": "rtl_compile_report.v1",
                    "status": "pass",
                    "files": ["rtl/demo_counter_cx1.sv"],
                }
            )
            + "\n",
            encoding="utf-8",
        )
        bad_subset_rules_path = bad_subset_ip / "ontology" / "design_rules.yaml"
        bad_subset_rules = bad_subset_rules_path.read_text(encoding="utf-8")
        if not bad_subset_rules.endswith("\n"):
            bad_subset_rules += "\n"
        bad_subset_rules += "\n".join(
            [
                "  - id: INST_BAD_RTL_LANGUAGE_SUBSET",
                "    rule: RULE_RTL_LANGUAGE_SUBSET",
                "    status: closed",
                "    requirement: REQ_DEMO_COUNTER_CX1_RESET_KNOWN",
                "    obligation: OBL_DEMO_COUNTER_CX1_RESET_KNOWN",
                "    contract: CONTRACT_DEMO_COUNTER_CX1_SIM_SCOREBOARD",
                "    language_policy: smoke_negative_subset",
                "    rtl_compile_report: rtl/rtl_compile.json",
                "    rtl_sources: [rtl/demo_counter_cx1.sv]",
                "    forbidden_constructs_absent: [always_ff, function, mixed_blocking_nonblocking_always]",
                "    evidence_refs:",
                "      - rtl/demo_counter_cx1.sv",
                "      - rtl/rtl_compile.json",
                "",
            ]
        )
        bad_subset_rules_path.write_text(bad_subset_rules, encoding="utf-8")
        bad_subset_compile = call({"tool": "oag.compile", "arguments": {"ip_dir": str(bad_subset_ip)}})
        assert bad_subset_compile["result"]["status"] == "fail", bad_subset_compile
        assert "INST_BAD_RTL_LANGUAGE_SUBSET: rtl/demo_counter_cx1.sv: forbidden RTL construct present: always_ff" in bad_subset_compile["result"]["issues"], bad_subset_compile
        assert "INST_BAD_RTL_LANGUAGE_SUBSET: rtl/demo_counter_cx1.sv: forbidden RTL construct present: function" in bad_subset_compile["result"]["issues"], bad_subset_compile
        assert "INST_BAD_RTL_LANGUAGE_SUBSET: rtl/demo_counter_cx1.sv:11: forbidden RTL construct present: mixed_blocking_nonblocking_always" in bad_subset_compile["result"]["issues"], bad_subset_compile
        bad_protocol_ip = make_ip(Path(tmp) / "bad_protocol_report")
        (bad_protocol_ip / "signoff").mkdir(exist_ok=True)
        (bad_protocol_ip / "signoff" / "protocol_compliance_report.json").write_text(
            json.dumps(
                {
                    "schema_version": "protocol_compliance_report.v1",
                    "status": "fail",
                    "issues": ["smoke negative"],
                }
            )
            + "\n",
            encoding="utf-8",
        )
        bad_protocol_rules_path = bad_protocol_ip / "ontology" / "design_rules.yaml"
        bad_protocol_rules = bad_protocol_rules_path.read_text(encoding="utf-8")
        if not bad_protocol_rules.endswith("\n"):
            bad_protocol_rules += "\n"
        bad_protocol_rules += "\n".join(
            [
                "  - id: INST_BAD_PROTOCOL_REPORT",
                "    rule: RULE_PROTOCOL_COMPLIANCE",
                "    status: closed",
                "    requirement: REQ_DEMO_COUNTER_CX1_RESET_KNOWN",
                "    obligation: OBL_DEMO_COUNTER_CX1_RESET_KNOWN",
                "    contract: CONTRACT_DEMO_COUNTER_CX1_SIM_SCOREBOARD",
                "    protocol: APB4",
                "    compliance_report: signoff/protocol_compliance_report.json",
                "    evidence_refs:",
                "      - signoff/protocol_compliance_report.json",
                "",
            ]
        )
        bad_protocol_rules_path.write_text(bad_protocol_rules, encoding="utf-8")
        bad_protocol_compile = call({"tool": "oag.compile", "arguments": {"ip_dir": str(bad_protocol_ip)}})
        assert bad_protocol_compile["result"]["status"] == "fail", bad_protocol_compile
        assert (
            "INST_BAD_PROTOCOL_REPORT: protocol compliance report is not passing: signoff/protocol_compliance_report.json status=fail"
            in bad_protocol_compile["result"]["issues"]
        ), bad_protocol_compile
        missing_phase_ip = make_ip(Path(tmp) / "missing_protocol_phase_trace")
        (missing_phase_ip / "signoff").mkdir(exist_ok=True)
        (missing_phase_ip / "signoff" / "protocol_compliance_report.json").write_text(
            json.dumps(
                {
                    "schema_version": "protocol_compliance_report.v1",
                    "status": "pass",
                    "issues": [],
                }
            )
            + "\n",
            encoding="utf-8",
        )
        missing_phase_rules_path = missing_phase_ip / "ontology" / "design_rules.yaml"
        missing_phase_rules = missing_phase_rules_path.read_text(encoding="utf-8")
        if not missing_phase_rules.endswith("\n"):
            missing_phase_rules += "\n"
        missing_phase_rules += "\n".join(
            [
                "  - id: INST_MISSING_PROTOCOL_PHASE_TRACE",
                "    rule: RULE_PROTOCOL_COMPLIANCE",
                "    status: closed",
                "    requirement: REQ_DEMO_COUNTER_CX1_RESET_KNOWN",
                "    obligation: OBL_DEMO_COUNTER_CX1_RESET_KNOWN",
                "    contract: CONTRACT_DEMO_COUNTER_CX1_SIM_SCOREBOARD",
                "    protocol: APB4",
                "    compliance_report: signoff/protocol_compliance_report.json",
                "    phase_trace: sim/missing_apb_phase_trace.jsonl",
                "    evidence_refs:",
                "      - signoff/protocol_compliance_report.json",
                "",
            ]
        )
        missing_phase_rules_path.write_text(missing_phase_rules, encoding="utf-8")
        missing_phase_compile = call({"tool": "oag.compile", "arguments": {"ip_dir": str(missing_phase_ip)}})
        assert missing_phase_compile["result"]["status"] == "fail", missing_phase_compile
        assert (
            "INST_MISSING_PROTOCOL_PHASE_TRACE: protocol phase trace missing on disk: sim/missing_apb_phase_trace.jsonl"
            in missing_phase_compile["result"]["issues"]
        ), missing_phase_compile
        bad_research_ip = make_ip(Path(tmp) / "bad_auto_research_report")
        (bad_research_ip / "signoff" / "static_signoff_summary.json").write_text(
            json.dumps(
                {
                    "schema_version": "static_signoff_summary.v1",
                    "status": "pass",
                    "reports": {"auto_research": "signoff/ip_research_report.json"},
                    "checks": {"auto_research_next_actions": "pass"},
                }
            )
            + "\n",
            encoding="utf-8",
        )
        (bad_research_ip / "signoff" / "ip_research_report.json").write_text(
            json.dumps(
                {
                    "schema_version": "ip_research_report.v1",
                    "status": "pass",
                    "method": "smoke_negative",
                    "automation_boundary": "test-only report",
                    "checks": {"ranked_next_actions_present": False},
                    "evidence_refs": ["sim/results.xml"],
                    "evidence_strengths": [
                        {
                            "id": "SMOKE_STRENGTH",
                            "status": "pass",
                            "evidence_refs": ["sim/results.xml"],
                        }
                    ],
                    "ranked_next_actions": [],
                }
            )
            + "\n",
            encoding="utf-8",
        )
        bad_research_check = call({"tool": "oag.check", "arguments": {"ip_dir": str(bad_research_ip)}})
        assert bad_research_check["result"]["ok"] is False, bad_research_check
        assert (
            "auto research report has no ranked_next_actions: signoff/ip_research_report.json"
            in bad_research_check["result"]["issues"]
        ), bad_research_check
        unsafe_sta_research_ip = make_ip(Path(tmp) / "unsafe_sta_auto_research_report")
        (unsafe_sta_research_ip / "signoff" / "implementation_sta_report.json").write_text(
            json.dumps(
                {
                    "schema_version": "implementation_sta_report.v1",
                    "status": "development_pass",
                    "method": "smoke_development_sta",
                    "metrics": {"wns_ns": 0.0, "tns_ns": 0.0},
                    "issues": [],
                }
            )
            + "\n",
            encoding="utf-8",
        )
        (unsafe_sta_research_ip / "signoff" / "static_signoff_summary.json").write_text(
            json.dumps(
                {
                    "schema_version": "static_signoff_summary.v1",
                    "status": "pass",
                    "reports": {"auto_research": "signoff/ip_research_report.json"},
                    "checks": {"auto_research_next_actions": "pass"},
                }
            )
            + "\n",
            encoding="utf-8",
        )
        (unsafe_sta_research_ip / "signoff" / "ip_research_report.json").write_text(
            json.dumps(
                {
                    "schema_version": "ip_research_report.v1",
                    "status": "pass",
                    "method": "smoke_unsafe_development_sta_closure",
                    "automation_boundary": "test-only report",
                    "checks": {"ranked_next_actions_present": True},
                    "evidence_refs": ["signoff/implementation_sta_report.json"],
                    "evidence_strengths": [
                        {
                            "id": "DEVELOPMENT_IMPLEMENTATION_STA_EXECUTION",
                            "status": "pass",
                            "evidence_refs": ["signoff/implementation_sta_report.json"],
                        }
                    ],
                    "ranked_next_actions": [
                        {
                            "rank": 1,
                            "id": "IMPLEMENTATION_STA",
                            "status": "closed",
                            "reason": "Development STA passed, incorrectly treated as signoff closure.",
                            "evidence_refs": ["signoff/implementation_sta_report.json"],
                        }
                    ],
                    "signoff_blockers": ["Independent reviewer receipt is still required for signoff/promote."],
                }
            )
            + "\n",
            encoding="utf-8",
        )
        unsafe_sta_research_check = call({"tool": "oag.check", "arguments": {"ip_dir": str(unsafe_sta_research_ip)}})
        assert unsafe_sta_research_check["result"]["ok"] is False, unsafe_sta_research_check
        assert any(
            issue.startswith(
                "auto research report must rank development implementation STA as partially_closed after development_pass"
            )
            for issue in unsafe_sta_research_check["result"]["issues"]
        ), unsafe_sta_research_check
        assert (
            "auto research report missing foundry/PVT blocker after development implementation STA pass: signoff/ip_research_report.json"
            in unsafe_sta_research_check["result"]["issues"]
        ), unsafe_sta_research_check
        assert (
            "auto research report missing gate-level reset/X-prop blocker after development implementation STA pass: signoff/ip_research_report.json"
            in unsafe_sta_research_check["result"]["issues"]
        ), unsafe_sta_research_check
        unsafe_gate_research_ip = make_ip(Path(tmp) / "unsafe_gate_auto_research_report")
        (unsafe_gate_research_ip / "signoff" / "gate_reset_xprop_report.json").write_text(
            json.dumps(
                {
                    "schema_version": "gate_reset_xprop_report.v1",
                    "status": "development_pass",
                    "method": "smoke_development_gate_reset_xprop",
                    "issues": [],
                }
            )
            + "\n",
            encoding="utf-8",
        )
        (unsafe_gate_research_ip / "signoff" / "static_signoff_summary.json").write_text(
            json.dumps(
                {
                    "schema_version": "static_signoff_summary.v1",
                    "status": "pass",
                    "reports": {"auto_research": "signoff/ip_research_report.json"},
                    "checks": {"auto_research_next_actions": "pass"},
                }
            )
            + "\n",
            encoding="utf-8",
        )
        (unsafe_gate_research_ip / "signoff" / "ip_research_report.json").write_text(
            json.dumps(
                {
                    "schema_version": "ip_research_report.v1",
                    "status": "pass",
                    "method": "smoke_unsafe_development_gate_closure",
                    "automation_boundary": "test-only report",
                    "checks": {"ranked_next_actions_present": True},
                    "evidence_refs": ["signoff/gate_reset_xprop_report.json"],
                    "evidence_strengths": [
                        {
                            "id": "DEVELOPMENT_GATE_RESET_XPROP_EXECUTION",
                            "status": "development_pass",
                            "evidence_refs": ["signoff/gate_reset_xprop_report.json"],
                        }
                    ],
                    "ranked_next_actions": [
                        {
                            "rank": 1,
                            "id": "GATE_LEVEL_RESET_XPROP",
                            "status": "closed",
                            "reason": "Development mapped-netlist smoke passed, incorrectly treated as production closure.",
                            "evidence_refs": ["signoff/gate_reset_xprop_report.json"],
                        }
                    ],
                    "signoff_blockers": ["Independent reviewer receipt is still required for signoff/promote."],
                }
            )
            + "\n",
            encoding="utf-8",
        )
        unsafe_gate_research_check = call({"tool": "oag.check", "arguments": {"ip_dir": str(unsafe_gate_research_ip)}})
        assert unsafe_gate_research_check["result"]["ok"] is False, unsafe_gate_research_check
        assert any(
            issue.startswith(
                "auto research report must rank development gate reset/X-prop as partially_closed after development_pass"
            )
            for issue in unsafe_gate_research_check["result"]["issues"]
        ), unsafe_gate_research_check
        assert (
            "auto research report missing SDF/foundry blocker after development gate reset/X-prop pass: signoff/ip_research_report.json"
            in unsafe_gate_research_check["result"]["issues"]
        ), unsafe_gate_research_check
        unsafe_formal_research_ip = make_ip(Path(tmp) / "unsafe_formal_auto_research_report")
        (unsafe_formal_research_ip / "signoff" / "formal_assertion_report.json").write_text(
            json.dumps(
                {
                    "schema_version": "formal_assertion_report.v1",
                    "status": "development_pass",
                    "method": "smoke_bounded_formal",
                    "bound_cycles": 8,
                    "issues": [],
                }
            )
            + "\n",
            encoding="utf-8",
        )
        (unsafe_formal_research_ip / "signoff" / "static_signoff_summary.json").write_text(
            json.dumps(
                {
                    "schema_version": "static_signoff_summary.v1",
                    "status": "pass",
                    "reports": {"auto_research": "signoff/ip_research_report.json"},
                    "checks": {"auto_research_next_actions": "pass"},
                }
            )
            + "\n",
            encoding="utf-8",
        )
        (unsafe_formal_research_ip / "signoff" / "ip_research_report.json").write_text(
            json.dumps(
                {
                    "schema_version": "ip_research_report.v1",
                    "status": "pass",
                    "method": "smoke_unsafe_development_formal_closure",
                    "automation_boundary": "test-only report",
                    "checks": {"ranked_next_actions_present": True},
                    "evidence_refs": ["signoff/formal_assertion_report.json"],
                    "evidence_strengths": [
                        {
                            "id": "DEVELOPMENT_FORMAL_ASSERTION_EXECUTION",
                            "status": "development_pass",
                            "evidence_refs": ["signoff/formal_assertion_report.json"],
                        }
                    ],
                    "ranked_next_actions": [
                        {
                            "rank": 1,
                            "id": "FORMAL_ASSERTION_OPTION",
                            "status": "closed",
                            "reason": "Formal proof passed.",
                            "evidence_refs": ["signoff/formal_assertion_report.json"],
                        }
                    ],
                    "signoff_blockers": ["Independent reviewer receipt is still required for signoff/promote."],
                }
            )
            + "\n",
            encoding="utf-8",
        )
        unsafe_formal_research_check = call({"tool": "oag.check", "arguments": {"ip_dir": str(unsafe_formal_research_ip)}})
        assert unsafe_formal_research_check["result"]["ok"] is False, unsafe_formal_research_check
        assert any(
            issue.startswith(
                "auto research report must rank development formal assertion as partially_closed after development_pass"
            )
            for issue in unsafe_formal_research_check["result"]["issues"]
        ), unsafe_formal_research_check
        assert any(
            issue.startswith(
                "auto research formal assertion action missing bounded/development limitation after development_pass"
            )
            for issue in unsafe_formal_research_check["result"]["issues"]
        ), unsafe_formal_research_check
        assert any(
            issue.startswith(
                "auto research formal assertion action missing contract/signoff limitation after development_pass"
            )
            for issue in unsafe_formal_research_check["result"]["issues"]
        ), unsafe_formal_research_check
        unsafe_handoff_ip = make_ip(Path(tmp) / "unsafe_handoff_report")
        bad_metrics = {
            "schema_version": "oag_improvement_metrics.v1",
            "closure_profile": "development",
            "requirements": {"total": 1},
            "contracts": {"total": 1},
            "closure": {"total": 1, "closed": 1, "open": 0, "closed_percent": 100.0, "issue_count": 0},
            "check": {"issue_count": 0, "stale_issue_count": 0},
            "evidence": {"files_present_count": 2, "files_missing_count": 0},
            "stage_receipts": {"count": 0},
            "ledger": {"events": 0},
            "auto_research": {
                "reports": 0,
                "actions": 0,
                "blocked_actions": 0,
                "partially_closed_actions": 0,
                "closed_actions": 0,
                "signoff_blockers": 0,
            },
            "decisions": {"receipts": 0, "independent_passing_reviewers": 0},
        }
        (unsafe_handoff_ip / "handoff" / "readiness_handoff.json").write_text(
            json.dumps(
                {
                    "schema_version": "oag_readiness_handoff.v1",
                    "id": "HANDOFF_UNSAFE_DEVELOPMENT_SIGNOFF_READY",
                    "ip": unsafe_handoff_ip.name,
                    "stage": "handoff",
                    "intent": "smoke unsafe handoff",
                    "generated_at": "2026-06-19T00:00:00Z",
                    "closure_profile": "development",
                    "status": "pass",
                    "method": "smoke_negative",
                    "automation_boundary": "Readiness handoff only; this is not a signoff decision.",
                    "progress_denominator": "derived_from_active_ip_obligations",
                    "numeric_summary": {
                        "requirements_total": 1,
                        "contracts_total": 1,
                        "obligations_total": 1,
                        "obligations_closed": 1,
                        "obligations_open": 0,
                        "closure_percent": 100.0,
                        "closure_issue_count": 0,
                        "check_issue_count": 0,
                        "stale_issue_count": 0,
                        "evidence_files_present": 2,
                        "evidence_files_total": 2,
                        "evidence_files_missing": 0,
                        "stage_receipts": 0,
                        "ledger_events": 0,
                        "auto_research_reports": 0,
                        "ranked_next_actions": 0,
                        "blocked_actions": 0,
                        "partially_closed_actions": 0,
                        "closed_actions": 0,
                        "signoff_blockers": 0,
                        "decision_receipts": 0,
                        "independent_passing_reviewers": 0,
                    },
                    "readiness": {
                        "development_ready": True,
                        "signoff_ready": True,
                        "closure_complete": True,
                        "check_clean": True,
                        "evidence_complete": True,
                    },
                    "ranked_next_actions": [],
                    "signoff_blockers": [],
                    "evidence_refs": ["sim/results.xml"],
                    "improvement_metrics": bad_metrics,
                }
            )
            + "\n",
            encoding="utf-8",
        )
        unsafe_handoff_check = call({"tool": "oag.check", "arguments": {"ip_dir": str(unsafe_handoff_ip)}})
        assert unsafe_handoff_check["result"]["ok"] is False, unsafe_handoff_check
        assert (
            "handoff report cannot mark signoff_ready=true when closure_profile=development: handoff/readiness_handoff.json"
            in unsafe_handoff_check["result"]["issues"]
        ), unsafe_handoff_check
        formal_ip = make_ip(Path(tmp) / "bad_formal")
        formal_contracts_path = formal_ip / "ontology" / "contracts.yaml"
        formal_contracts = json.loads(formal_contracts_path.read_text(encoding="utf-8"))
        formal_contracts["contracts"].append(
            {
                "id": "CONTRACT_BAD_FORMAL",
                "status": "locked",
                "obligation": "OBL_DEMO_COUNTER_CX1_RESET_KNOWN",
                "contract_type": "formal",
                "method": "formal",
                "variables": {"inputs": ["clk"], "outputs": ["smoke_output"]},
                "assume": {"clock": "stable"},
                "guarantee": {"behavior": "register map is proven"},
                "pass_condition": "register map is proven",
                "evidence_kinds": ["formal"],
            }
        )
        formal_contracts_path.write_text(json.dumps(formal_contracts, indent=2) + "\n", encoding="utf-8")
        formal_approval = call(
            {
                "tool": "oag.record",
                "arguments": {
                    "ip_dir": str(formal_ip),
                    "stage": "ontology",
                    "type": "decision",
                    "claim": "negative formal-contract fixture approved",
                    "summary": "Human owner approved the intentionally incomplete formal contract used by the smoke test.",
                    "actor": {"kind": "human", "id": "smoke-owner", "surface": "smoke"},
                    "approval": {
                        "kind": "human",
                        "approved": True,
                        "approved_by": "smoke-owner",
                        "reason": "exercise formal proof-reference gate",
                    },
                    "status": "open",
                },
            }
        )
        assert formal_approval["result"]["ledger_event"], formal_approval
        formal_compile = call({"tool": "oag.compile", "arguments": {"ip_dir": str(formal_ip)}})
        assert formal_compile["result"]["status"] == "fail", formal_compile
        assert "CONTRACT_BAD_FORMAL: formal/assertion contract missing assertion/proof reference" in formal_compile["result"]["issues"], formal_compile
        bad_decomp_ip = make_ip(Path(tmp) / "bad_decomposition")
        (bad_decomp_ip / "ontology" / "decomposition.yaml").write_text(
            "\n".join(
                [
                    "schema: oag_decomposition.v1",
                    f"ip: {bad_decomp_ip.name}",
                    "profile:",
                    "  mode: greenfield_modular",
                    "  rationale: one module is intentionally invalid for this negative test",
                    "modules:",
                    f"  - id: {bad_decomp_ip.name}",
                    "    ownership: current_ip",
                    f"    file: rtl/{bad_decomp_ip.name}.sv",
                    "    owned_obligations: [OBL_DEMO_COUNTER_CX1_RESET_KNOWN]",
                    "    owned_contracts: [CONTRACT_DEMO_COUNTER_CX1_SIM_SCOREBOARD]",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        bad_decomp_compile = call({"tool": "oag.compile", "arguments": {"ip_dir": str(bad_decomp_ip)}})
        assert bad_decomp_compile["result"]["status"] == "fail", bad_decomp_compile
        assert "greenfield_modular profile requires at least two current_ip modules or use small_leaf_single_file" in bad_decomp_compile["result"]["issues"], bad_decomp_compile
        bad_file_boundary_ip = make_ip(Path(tmp) / "bad_file_boundary")
        (bad_file_boundary_ip / "ontology" / "decomposition.yaml").write_text(
            "\n".join(
                [
                    "schema: oag_decomposition.v1",
                    f"ip: {bad_file_boundary_ip.name}",
                    "profile:",
                    "  mode: greenfield_modular",
                    "  rationale: duplicate physical files are intentionally invalid for this negative test",
                    "modules:",
                    f"  - id: {bad_file_boundary_ip.name}_top",
                    "    ownership: current_ip",
                    f"    file: rtl/{bad_file_boundary_ip.name}.sv",
                    "    role: top",
                    "    owned_obligations: [OBL_DEMO_COUNTER_CX1_RESET_KNOWN]",
                    "    owned_contracts: [CONTRACT_DEMO_COUNTER_CX1_SIM_SCOREBOARD]",
                    f"  - id: {bad_file_boundary_ip.name}_core",
                    "    ownership: current_ip",
                    f"    file: rtl/{bad_file_boundary_ip.name}.sv",
                    "    role: core",
                    "    owned_obligations: []",
                    "    owned_contracts: []",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        bad_file_boundary_compile = call({"tool": "oag.compile", "arguments": {"ip_dir": str(bad_file_boundary_ip)}})
        assert bad_file_boundary_compile["result"]["status"] == "fail", bad_file_boundary_compile
        assert any(
            "greenfield_modular module file boundary requires unique file per current_ip module" in issue
            for issue in bad_file_boundary_compile["result"]["issues"]
        ), bad_file_boundary_compile
        priority_ip = make_ip(Path(tmp) / "bad_priority")
        rules_path = priority_ip / "ontology" / "design_rules.yaml"
        rules_text = rules_path.read_text(encoding="utf-8").replace(
            "instances:\n",
            "\n".join(
                [
                    "instances:",
                    "  - id: BAD_PRIORITY_INSTANCE",
                    "    rule: RULE_SAME_CYCLE_PRIORITY_DECLARED",
                    "    status: active",
                    "    conflict: [ctrl_disable_write, terminal_tick]",
                    "    requirement: REQ_DEMO_COUNTER_CX1_RESET_KNOWN",
                    "    obligation: OBL_DEMO_COUNTER_CX1_RESET_KNOWN",
                    "    contract: CONTRACT_DEMO_COUNTER_CX1_SIM_SCOREBOARD",
                    "",
                ]
            ),
            1,
        )
        rules_path.write_text(rules_text, encoding="utf-8")
        priority_compile = call({"tool": "oag.compile", "arguments": {"ip_dir": str(priority_ip)}})
        assert priority_compile["result"]["status"] == "fail", priority_compile
        assert "BAD_PRIORITY_INSTANCE: same-cycle priority rule missing priority" in priority_compile["result"]["issues"], priority_compile
        protection_ip = make_ip(Path(tmp) / "bad_protection")
        baseline = call(
            {
                "tool": "oag.record",
                "arguments": {
                    "ip_dir": str(protection_ip),
                    "stage": "req",
                    "type": "decision",
                    "claim": "baseline protected truth snapshot",
                    "summary": "Establish protected field snapshot before edits.",
                    "actor": {"kind": "ai", "id": "codex", "surface": "smoke"},
                    "status": "open",
                },
            }
        )
        assert baseline["result"]["ledger_event"], baseline
        locked_truth = protection_ip / "req" / "locked_truth.md"
        locked_truth.write_text(locked_truth.read_text(encoding="utf-8") + "\n- Unauthorized semantic edit.\n", encoding="utf-8")
        before_records = sorted((protection_ip / "knowledge" / "records").glob("*.json"))
        rejected = call_process(
            {
                "tool": "oag.record",
                "arguments": {
                    "ip_dir": str(protection_ip),
                    "stage": "req",
                    "claim": "unauthorized protected edit record",
                    "actor": {"kind": "ai", "id": "codex", "surface": "smoke"},
                    "status": "open",
                },
            }
        )
        assert rejected.returncode != 0, rejected.stdout
        rejected_response = json.loads(rejected.stdout)
        assert "protected fields changed without human approval" in rejected_response["errors"][0], rejected_response
        after_records = sorted((protection_ip / "knowledge" / "records").glob("*.json"))
        assert after_records == before_records, [before_records, after_records]
        protection_check = call({"tool": "oag.check", "arguments": {"ip_dir": str(protection_ip)}})
        assert protection_check["result"]["ok"] is False, protection_check
        assert any("protected fields changed without ledger approval" in issue for issue in protection_check["result"]["issues"]), protection_check
        ledger_ip = make_ip(Path(tmp) / "bad_ledger")
        ledger_record = call(
            {
                "tool": "oag.record",
                "arguments": {
                    "ip_dir": str(ledger_ip),
                    "stage": "sim",
                    "claim": "ledger tamper baseline",
                    "actor": {"kind": "ai", "id": "codex", "surface": "smoke"},
                    "status": "open",
                },
            }
        )
        assert ledger_record["result"]["ledger_event"], ledger_record
        ledger_path = ledger_ip / "knowledge" / "ledger.jsonl"
        ledger_path.write_text(ledger_path.read_text(encoding="utf-8").replace('"action": "log"', '"action": "tampered"', 1), encoding="utf-8")
        ledger_check = call({"tool": "oag.check", "arguments": {"ip_dir": str(ledger_ip)}})
        assert ledger_check["result"]["ok"] is False, ledger_check
        assert any("event_hash mismatch" in issue for issue in ledger_check["result"]["issues"]), ledger_check
        monotonic_ip = make_ip(Path(tmp) / "bad_monotonic")
        closed = call(
            {
                "tool": "oag.record",
                "arguments": {
                    "ip_dir": str(monotonic_ip),
                    "stage": "sim",
                    "claim": "monotonic obligation closed",
                    "actor": {"kind": "ai", "id": "codex", "surface": "smoke"},
                    "rocev": {
                        "obligation": {"id": "OBL_MONO_SCOREBOARD", "text": "closed once"},
                        "contract": {"id": "CONTRACT_MONO_SCOREBOARD", "method": "scoreboard"},
                        "evidence": {"files": ["sim/results.xml"], "tests": [], "commit": ""},
                        "validation": {"status": "closed", "verdict": "pass", "rationale": "baseline close"},
                    },
                },
            }
        )
        assert closed["result"]["status"] == "closed", closed
        reopened = call(
            {
                "tool": "oag.record",
                "arguments": {
                    "ip_dir": str(monotonic_ip),
                    "stage": "sim",
                    "claim": "monotonic obligation silently reopened",
                    "actor": {"kind": "ai", "id": "codex", "surface": "smoke"},
                    "status": "open",
                    "rocev": {
                        "obligation": {"id": "OBL_MONO_SCOREBOARD", "text": "reopened without decision", "status": "open"},
                        "contract": {"id": "CONTRACT_MONO_SCOREBOARD", "method": "scoreboard", "status": "open"},
                        "validation": {"status": "open", "verdict": "pending", "rationale": "silent downgrade"},
                    },
                },
            }
        )
        assert reopened["result"]["status"] == "open", reopened
        monotonic_check = call({"tool": "oag.check", "arguments": {"ip_dir": str(monotonic_ip)}})
        assert monotonic_check["result"]["ok"] is False, monotonic_check
        assert any("monotonic closure violation" in issue for issue in monotonic_check["result"]["issues"]), monotonic_check
        print(json.dumps({"ok": True, "ip": str(ip), "runtime": "script_skill_hooks"}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
