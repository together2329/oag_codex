#!/usr/bin/env python3
"""Focused regressions for selectively integrated OAG hardening."""

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
CODEX_ROOT = SCRIPTS.parent
SEMANTIC_CHECK = SCRIPTS / "oag_semantic_projection_check.py"
CLOSURE_GATE = SCRIPTS / "oag_closure_super_gate.py"
SUBAGENT_GATE = CODEX_ROOT / "hooks" / "codex_subagent_oag_gate.py"
DEEP_INTERVIEW_GUARD = CODEX_ROOT / "hooks" / "codex_deep_interview_prompt_guard.py"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def run_json(script: Path, *args: str, input_payload: dict[str, Any] | None = None, env: dict[str, str] | None = None) -> tuple[subprocess.CompletedProcess[str], dict[str, Any]]:
    proc = subprocess.run(
        [sys.executable, str(script), *args],
        input=json.dumps(input_payload) if input_payload is not None else None,
        text=True,
        capture_output=True,
        check=False,
        env=env,
    )
    payload = json.loads(proc.stdout) if proc.stdout.strip() else {}
    return proc, payload


def semantic_projection_regression(root: Path) -> None:
    ip = root / "semantic_ip"
    documents = {
        "req/source_claims.yaml": {"claims": [{"id": "CLAIM_1", "status": "locked"}]},
        "ontology/requirements.yaml": {"requirements": [{"id": "REQ_1", "status": "locked"}]},
        "ontology/requirement_atoms.yaml": {"requirement_atoms": [{"id": "ATOM_1", "status": "locked"}]},
        "ontology/obligations.yaml": {"obligations": [{"id": "OBL_1", "status": "locked"}]},
        "ontology/contracts.yaml": {"contracts": [{"id": "CONTRACT_1", "status": "locked"}]},
    }
    for rel, payload in documents.items():
        write_json(ip / rel, payload)
    write_json(ip / "ontology/scope_lock.json", {"state": "locked"})
    projection = {
        "schema_version": "oag_semantic_projection.v1",
        "ip": ip.name,
        "projections": [
            {
                "id": "PROJ_1",
                "status": "ready",
                "load_bearing": True,
                "projection_class": "preserved",
                "source_claim_refs": ["CLAIM_1"],
                "requirement_refs": ["REQ_1"],
                "atom_refs": ["ATOM_1"],
                "obligation_refs": ["OBL_1"],
                "contract_refs": ["CONTRACT_1"],
                "input_hashes": {rel: sha256(ip / rel) for rel in documents},
            }
        ],
    }
    write_json(ip / "ontology/semantic_projection.yaml", projection)
    passed, payload = run_json(SEMANTIC_CHECK, "--ip-dir", str(ip), "--phase", "lock", "--json")
    assert passed.returncode == 0 and payload.get("status") == "pass", passed.stdout + passed.stderr

    projection["projections"][0]["input_hashes"] = {rel: sha256(ip / rel).upper() for rel in documents}
    write_json(ip / "ontology/semantic_projection.yaml", projection)
    uppercase, payload = run_json(SEMANTIC_CHECK, "--ip-dir", str(ip), "--phase", "lock", "--json")
    assert uppercase.returncode == 0 and payload.get("status") == "pass", uppercase.stdout + uppercase.stderr

    projection["projections"][0]["input_hashes"]["../outside.json"] = "0" * 64
    write_json(ip / "ontology/semantic_projection.yaml", projection)
    outside, payload = run_json(SEMANTIC_CHECK, "--ip-dir", str(ip), "--phase", "lock", "--json")
    assert outside.returncode != 0, outside.stdout
    assert any(item.get("code") == "SEMANTIC_PROJECTION_INPUT_OUTSIDE_IP" for item in payload.get("issues", [])), payload
    projection["projections"][0]["input_hashes"].pop("../outside.json")
    write_json(ip / "ontology/semantic_projection.yaml", projection)

    write_json(ip / "ontology/contracts.yaml", {"contracts": [{"id": "CONTRACT_1", "status": "locked", "changed": True}]})
    stale, payload = run_json(SEMANTIC_CHECK, "--ip-dir", str(ip), "--phase", "lock", "--json")
    assert stale.returncode != 0, stale.stdout
    assert any(item.get("code") == "SEMANTIC_PROJECTION_INPUT_STALE" for item in payload.get("issues", [])), payload


def closure_gate_regression(root: Path) -> None:
    ip = root / "closure_ip"
    source = ip / "inputs/source.json"
    write_json(source, {"value": 1})
    checker = ip / "reports/semantic.json"
    write_json(checker, {"status": "pass", "input_hashes": {"inputs/source.json": sha256(source)}})
    checker_hash = sha256(checker)
    validator = ip / "reports/validator.json"
    gate = ip / "reports/gate.json"
    write_json(validator, {"status": "pass", "actor": {"id": "validator"}, "checked_report_hashes": {"semantic_projection": checker_hash}})
    write_json(gate, {"status": "pass", "actor": {"id": "gate-reviewer"}, "checked_report_hashes": {"semantic_projection": checker_hash}})
    manifest = ip / "closure_manifest.json"
    write_json(
        manifest,
        {
            "required_reports": [
                {"name": "semantic_projection", "path": "reports/semantic.json"},
                {"name": "validation_report", "path": "reports/validator.json"},
                {"name": "gate_decision", "path": "reports/gate.json"},
            ]
        },
    )
    passed, payload = run_json(CLOSURE_GATE, "--ip-dir", str(ip), "--profile", "signoff", "--manifest", str(manifest), "--json")
    assert passed.returncode == 0 and payload.get("status") == "pass", passed.stdout + passed.stderr

    outside_report = root / "outside-report.json"
    write_json(outside_report, {"status": "pass"})
    outside_manifest = ip / "outside_manifest.json"
    write_json(outside_manifest, {"required_reports": [{"name": "outside", "path": str(outside_report)}]})
    outside, payload = run_json(CLOSURE_GATE, "--ip-dir", str(ip), "--manifest", str(outside_manifest), "--json")
    assert outside.returncode != 0, outside.stdout
    assert any(item.get("code") == "MISSING_CHECK_OUTPUT" for item in payload.get("issues", [])), payload

    write_json(validator, {"status": "pass", "actor": {"id": "validator"}, "checked_reports": ["semantic_projection"]})
    forged, payload = run_json(CLOSURE_GATE, "--ip-dir", str(ip), "--profile", "signoff", "--manifest", str(manifest), "--json")
    assert forged.returncode != 0, forged.stdout
    assert any(item.get("code") == "CHECK_OUTPUT_NOT_SEEN_BY_VALIDATOR" for item in payload.get("issues", [])), payload


def hook_regressions(root: Path) -> None:
    ip = root / "blocked_ip"
    write_json(ip / "ontology/decision_matrix.yaml", {"decisions": [{"id": "DEC_1", "lock_required": True, "status": "open"}]})
    guard, payload = run_json(DEEP_INTERVIEW_GUARD, input_payload={"prompt": "implement this IP", "ip_dir": str(ip)})
    assert guard.returncode == 0, guard.stderr
    assert "OAG DEEP INTERVIEW PROMPT GUARD" in json.dumps(payload), payload

    hidden_ip = root / "hidden_blocked_ip"
    write_json(hidden_ip / ".oag/ontology/decision_matrix.yaml", {"decisions": [{"id": "DEC_2", "lock_required": True, "status": "open"}]})
    guard, payload = run_json(DEEP_INTERVIEW_GUARD, input_payload={"prompt": "implement this hidden-layout IP", "ip_dir": str(hidden_ip)})
    assert guard.returncode == 0, guard.stderr
    assert "OAG DEEP INTERVIEW PROMPT GUARD" in json.dumps(payload), payload

    mixed_ip = root / "hidden_ontology_legacy_req_ip"
    write_json(mixed_ip / ".oag/ontology/scope_lock.json", {"state": "draft"})
    write_json(mixed_ip / "req/ambiguity_register.yaml", {"ambiguities": [{"id": "AMB_1", "lock_blocker": True, "status": "open"}]})
    guard, payload = run_json(DEEP_INTERVIEW_GUARD, input_payload={"prompt": "lock this mixed-layout IP", "ip_dir": str(mixed_ip)})
    assert guard.returncode == 0, guard.stderr
    assert "OAG DEEP INTERVIEW PROMPT GUARD" in json.dumps(payload), payload

    hook_cwd = root / "subagent"
    hook_cwd.mkdir(parents=True)
    env = dict(os.environ)
    env["OAG_SUBAGENT_GATE_CACHE"] = str(root / "subagent_gate_cache.json")
    subagent_payload = {
        "hook_event_name": "SubagentStop",
        "agent_type": "oag-test-worker",
        "agent_id": "worker-1",
        "session_id": "session-1",
        "cwd": str(hook_cwd),
    }
    for attempt in range(1, 5):
        proc, payload = run_json(SUBAGENT_GATE, input_payload=subagent_payload, env=env)
        assert proc.returncode == 0, proc.stderr
        if attempt <= 3:
            assert payload.get("decision") == "block", payload
        else:
            assert payload == {}, payload
    states = sorted((hook_cwd / ".codex/oag/subagent-terminal-states").glob("*.json"))
    assert states, "retry exhaustion must leave a durable terminal state"
    state = json.loads(states[-1].read_text(encoding="utf-8"))
    assert state.get("status") == "INCONCLUSIVE" and state.get("quarantine") is True, state
    assert state.get("evidence_usable_for_closure") is False, state


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="oag-selective-hardening-") as temp:
        root = Path(temp)
        semantic_projection_regression(root)
        closure_gate_regression(root)
        hook_regressions(root)
    print(json.dumps({"ok": True, "suite": "oag_selective_hardening"}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
