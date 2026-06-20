#!/usr/bin/env python3
"""Evaluation runner for OAG run-loop and Codex hook gates.

Unlike smoke_test.py, this script reports scenario-level observations. It is
intended for quickly checking whether the OAG gates behave like an agent harness:
incomplete work blocks stop, complete work passes, repeated blockers ask for a
human decision without trapping Stop in a loop, completion still requires a
decision receipt, stale evidence is invalidated, vacuous closure is blocked, and
greenfield module boundaries are enforced.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
import traceback
from pathlib import Path
from typing import Any, Callable


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import smoke_test  # noqa: E402


CaseFn = Callable[[Path], dict[str, Any]]
HOOKS_DIR = smoke_test.ROOT / "hooks"
PROJECT = smoke_test.ROOT.parent


def _approve_eval_protected_update(ip: Path, *, summary: str) -> dict[str, Any]:
    response = smoke_test.call(
        {
            "tool": "oag.decide",
            "arguments": {
                "ip_dir": str(ip),
                "action": "protected_ontology_eval_update",
                "stage": "ontology",
                "record_decision": True,
                "actor": {"kind": "human", "id": "eval-owner", "surface": "eval"},
                "summary": summary,
            },
        }
    )
    assert response["result"]["decision_receipt"], response
    return response["result"]


def _start_run(ip: Path, *, intent: str) -> tuple[str, dict[str, Any]]:
    response = smoke_test.call(
        {
            "tool": "oag.run.start",
            "arguments": {
                "ip_dir": str(ip),
                "stage": "sim",
                "intent": intent,
                "actor": {"kind": "ai", "id": "codex", "surface": "eval"},
            },
        }
    )
    return str(response["result"]["run_id"]), response["result"]


def _close_run(ip: Path, run_id: str, *, intent: str) -> dict[str, Any]:
    record = smoke_test.call(
        {
            "tool": "oag.run.record",
            "arguments": {
                "ip_dir": str(ip),
                "run_id": run_id,
                "stage": "sim",
                "summary": "evaluation evidence closes the active obligation",
                "actor": {"kind": "ai", "id": "codex", "surface": "eval"},
            },
        }
    )
    checkpoint = smoke_test.call(
        {
            "tool": "oag.run.checkpoint",
            "arguments": {
                "ip_dir": str(ip),
                "run_id": run_id,
                "stage": "sim",
                "intent": intent,
                "actor": {"kind": "ai", "id": "codex", "surface": "eval"},
            },
        }
    )
    return {"record": record["result"], "checkpoint": checkpoint["result"]}


def _hook_json(ip: Path, run_id: str) -> tuple[int, dict[str, Any] | None, str]:
    proc = smoke_test.stop_gate({"ip_dir": str(ip), "run_id": run_id})
    if not proc.stdout.strip():
        return proc.returncode, None, proc.stderr
    return proc.returncode, json.loads(proc.stdout), proc.stderr


def _run_hook(script: str, payload: dict[str, Any]) -> tuple[int, dict[str, Any] | None, str]:
    proc = subprocess.run(
        [sys.executable, str(HOOKS_DIR / script)],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        check=False,
        cwd=PROJECT,
        env={**os.environ, "OAG_DISABLE_BACKEND": "1"},
    )
    if not proc.stdout.strip():
        return proc.returncode, None, proc.stderr
    return proc.returncode, json.loads(proc.stdout), proc.stderr


def _additional_context(payload: dict[str, Any] | None) -> str:
    if not isinstance(payload, dict):
        return ""
    output = payload.get("hookSpecificOutput")
    if not isinstance(output, dict):
        return ""
    return str(output.get("additionalContext") or "")


def _human_approve_signoff_profile(ip: Path) -> None:
    policies = ip / "ontology" / "policies.yaml"
    policies.write_text(policies.read_text(encoding="utf-8").replace("closure_profile: development", "closure_profile: signoff"), encoding="utf-8")
    approval = smoke_test.call(
        {
            "tool": "oag.record",
            "arguments": {
                "ip_dir": str(ip),
                "stage": "signoff",
                "type": "decision",
                "claim": "human approval to enter signoff closure profile",
                "summary": "Human owner approved the protected policy transition to signoff.",
                "actor": {"kind": "human", "id": "eval-owner", "surface": "eval"},
                "approval": {"kind": "human", "approved": True, "reason": "eval signoff path"},
                "status": "open",
            },
        }
    )
    assert approval["result"]["ledger_event"], approval


def _record_closed_validation(ip: Path, *, surface: str = "eval") -> dict[str, Any]:
    response = smoke_test.call(
        {
            "tool": "oag.record",
            "arguments": {
                "ip_dir": str(ip),
                "stage": "sim",
                "claim": "evaluation closes reset obligation",
                "summary": "Evaluation closes the scaffold reset obligation through scoreboard evidence.",
                "actor": {"kind": "ai", "id": "producer", "surface": surface},
                "rocev": {
                    "obligation": {"id": "OBL_DEMO_COUNTER_CX1_RESET_KNOWN", "status": "closed"},
                    "contract": {"id": "CONTRACT_DEMO_COUNTER_CX1_SIM_SCOREBOARD", "method": "scoreboard", "status": "closed"},
                    "evidence": {"files": ["sim/results.xml", "sim/scoreboard_events.jsonl"], "tests": [], "commit": ""},
                    "validation": {"status": "closed", "verdict": "pass", "rationale": "scoreboard evidence passed"},
                },
            },
        }
    )
    assert response["result"]["status"] == "closed", response
    return response["result"]


def case_stop_gate_blocks_incomplete(root: Path) -> dict[str, Any]:
    ip = smoke_test.make_ip(root / "blocks_incomplete")
    run_id, started = _start_run(ip, intent="eval incomplete run blocks stop")
    rc, payload, stderr = _hook_json(ip, run_id)
    assert rc == 0, stderr
    assert payload is not None, "expected Codex hook block JSON"
    assert payload.get("decision") == "block", payload
    reason = str(payload.get("reason") or "")
    assert "OAG NEXT ACTION" in reason, payload
    assert "run incomplete" in reason, payload
    return {
        "ip": str(ip),
        "run_id": run_id,
        "active_obligation": started["next_action"]["active_obligation"],
        "hook_decision": payload["decision"],
        "contains_next_action": "OAG NEXT ACTION" in reason,
    }


def case_stop_gate_obeys_policy_limit(root: Path) -> dict[str, Any]:
    ip = smoke_test.make_ip(root / "policy_limited")
    run_id, _started = _start_run(ip, intent="eval policy-limited run")
    configured = smoke_test.call(
        {
            "tool": "oag.configure",
            "arguments": {
                "ip_dir": str(ip),
                "hook_auto_continue_until": "rtl",
                "actor": {"kind": "human", "id": "eval-owner", "surface": "eval"},
                "approval": {"kind": "human", "approved": True, "reason": "eval policy limit"},
            },
        }
    )
    stop = smoke_test.call({"tool": "oag.stop_check", "arguments": {"ip_dir": str(ip), "run_id": run_id}})
    rc, payload, stderr = _hook_json(ip, run_id)
    assert rc == 0, stderr
    assert payload is None, payload
    assert stop["result"]["should_continue"] is False, stop
    assert stop["result"]["reason"] == "policy_limit_reached", stop
    return {
        "ip": str(ip),
        "run_id": run_id,
        "configured": configured["result"]["updates"],
        "reason": stop["result"]["reason"],
        "next_action_stage": stop["result"]["policy"]["next_action_stage"],
    }


def case_compile_skips_fresh_graph(root: Path) -> dict[str, Any]:
    ip = smoke_test.make_ip(root / "fresh_compile")
    first = smoke_test.call({"tool": "oag.compile", "arguments": {"ip_dir": str(ip)}})
    second = smoke_test.call({"tool": "oag.compile", "arguments": {"ip_dir": str(ip)}})
    assert first["result"]["status"] == "pass", first
    assert second["result"]["status"] == "pass", second
    assert first["result"]["skipped"] is False, first
    assert second["result"]["skipped"] is True, second
    manifest = ip / "ontology" / "generated" / "compile_manifest.json"
    assert manifest.is_file(), manifest
    return {
        "ip": str(ip),
        "first_skipped": first["result"]["skipped"],
        "second_skipped": second["result"]["skipped"],
        "manifest": str(manifest),
    }


def case_stop_gate_allows_complete(root: Path) -> dict[str, Any]:
    ip = smoke_test.make_ip(root / "allows_complete")
    intent = "eval complete run passes stop"
    run_id, _started = _start_run(ip, intent=intent)
    closed = _close_run(ip, run_id, intent=intent)
    rc, payload, stderr = _hook_json(ip, run_id)
    assert rc == 0, stderr
    assert payload is None, payload
    assert closed["checkpoint"]["allowed"] is True, closed
    assert closed["checkpoint"]["status"] == "complete", closed
    return {
        "ip": str(ip),
        "run_id": run_id,
        "checkpoint_status": closed["checkpoint"]["status"],
        "hook_stdout": "",
    }


def case_stop_gate_allows_needs_human(root: Path) -> dict[str, Any]:
    ip = smoke_test.make_ip(root / "needs_human")
    run_id, _started = _start_run(ip, intent="eval repeated blocker needs human")
    checkpoint = smoke_test.call(
        {
            "tool": "oag.run.checkpoint",
            "arguments": {
                "ip_dir": str(ip),
                "run_id": run_id,
                "stage": "sim",
                "intent": "eval repeated blocker needs human",
                "max_blocker_repeats": 1,
                "actor": {"kind": "ai", "id": "codex", "surface": "eval"},
            },
        }
    )
    assert checkpoint["result"]["status"] == "needs_human", checkpoint
    rc, payload, stderr = _hook_json(ip, run_id)
    assert rc == 0, stderr
    assert payload is None, payload
    return {
        "ip": str(ip),
        "run_id": run_id,
        "checkpoint_status": checkpoint["result"]["status"],
        "hook_stdout": "",
        "allows_stop": True,
    }


def case_completion_requires_decision_receipt(root: Path) -> dict[str, Any]:
    ip = smoke_test.make_ip(root / "decision_receipt")
    run_id, _started = _start_run(ip, intent="eval decision receipt gate")
    _close_run(ip, run_id, intent="eval decision receipt gate")
    undecided = smoke_test.call(
        {
            "tool": "oag.decide",
            "arguments": {
                "ip_dir": str(ip),
                "action": "claim_complete",
                "stage": "sim",
            },
        }
    )
    assert undecided["result"]["allowed"] is False, undecided
    assert undecided["result"]["reason"] == "decision_receipt_required", undecided
    decided = smoke_test.call(
        {
            "tool": "oag.decide",
            "arguments": {
                "ip_dir": str(ip),
                "action": "claim_complete",
                "stage": "sim",
                "record_decision": True,
                "actor": {"kind": "ai", "id": "codex", "surface": "eval"},
            },
        }
    )
    assert decided["result"]["allowed"] is True, decided
    receipt = Path(decided["result"]["decision_receipt"]["path"])
    assert receipt.is_file(), receipt
    return {
        "ip": str(ip),
        "run_id": run_id,
        "without_receipt": undecided["result"]["reason"],
        "with_receipt_allowed": decided["result"]["allowed"],
        "receipt": str(receipt),
    }


def case_context_injection_before_work(root: Path) -> dict[str, Any]:
    ip = smoke_test.make_ip(root / "context_injection")
    cache_path = smoke_test.ROOT / ".cache" / "context_inject.json"
    cache_path.unlink(missing_ok=True)
    rc, payload, stderr = _run_hook(
        "codex_context_inject.py",
        {
            "ip_dir": str(ip),
            "stage": "rtl",
            "prompt": f"Start rtl stage work for {ip.name}. Please inspect the OAG context first.",
        },
    )
    assert rc == 0, stderr
    context = _additional_context(payload)
    assert "OAG CONTEXT INJECTION" in context, payload
    assert ip.name in context, payload
    assert "IP KNOWLEDGE LEDGER" in context, payload
    rc_duplicate, duplicate_payload, duplicate_stderr = _run_hook(
        "codex_context_inject.py",
        {
            "ip_dir": str(ip),
            "stage": "rtl",
            "prompt": f"Start rtl stage work for {ip.name}. Please inspect the OAG context first.",
        },
    )
    assert rc_duplicate == 0, duplicate_stderr
    assert duplicate_payload is None, duplicate_payload
    rc_high_pressure, high_pressure_payload, high_pressure_stderr = _run_hook(
        "codex_context_inject.py",
        {
            "ip_dir": str(ip),
            "stage": "rtl",
            "context_pressure": "high",
            "prompt": f"Start rtl stage work for {ip.name}. Please inspect the OAG context first.",
        },
    )
    assert rc_high_pressure == 0, high_pressure_stderr
    assert high_pressure_payload is None, high_pressure_payload
    rc_post_compact, post_compact_payload, post_compact_stderr = _run_hook(
        "codex_context_inject.py",
        {
            "ip_dir": str(ip),
            "stage": "rtl",
            "hook_event_name": "PostCompact",
            "prompt": f"Start rtl stage work for {ip.name}. Please inspect the OAG context first.",
        },
    )
    assert rc_post_compact == 0, post_compact_stderr
    assert post_compact_payload is None, post_compact_payload
    rc_recovery, recovery_payload, recovery_stderr = _run_hook(
        "codex_context_inject.py",
        {
            "ip_dir": str(ip),
            "stage": "rtl",
            "prompt": f"Start rtl stage work for {ip.name}. Please inspect the OAG context first.",
        },
    )
    assert rc_recovery == 0, recovery_stderr
    recovery_context = _additional_context(recovery_payload)
    assert "OAG CONTEXT INJECTION" in recovery_context, recovery_payload
    assert recovery_payload["hookSpecificOutput"]["hookEventName"] == "UserPromptSubmit", recovery_payload
    return {
        "ip": str(ip),
        "hook": "codex_context_inject.py",
        "contains_context": "IP KNOWLEDGE LEDGER" in context,
        "duplicate_suppressed": duplicate_payload is None,
        "high_pressure_does_not_force": high_pressure_payload is None,
        "post_compact_marker_is_silent": post_compact_payload is None,
        "post_compact_recovers": "OAG CONTEXT INJECTION" in recovery_context,
        "stage_inferred": "rtl",
    }


def case_draft_on_pressure_injects_guard(root: Path) -> dict[str, Any]:
    ip = smoke_test.make_ip(root / "draft_pressure")
    rc, payload, stderr = _run_hook(
        "codex_draft_pressure.py",
        {
            "ip_dir": str(ip),
            "prompt": f"Continue deep requirement interview for {ip.name}",
            "context_pressure": "high",
        },
    )
    assert rc == 0, stderr
    context = _additional_context(payload)
    assert "OAG DRAFT PRESSURE GUARD" in context, payload
    assert "oag.draft" in context, payload
    assert str(ip) in context, payload
    return {
        "ip": str(ip),
        "hook": "codex_draft_pressure.py",
        "pressure_guard": True,
        "requires_draft": "oag.draft" in context,
    }


def case_evidence_freshness_mutation_blocks(root: Path) -> dict[str, Any]:
    ip = smoke_test.make_ip(root / "freshness_mutation")
    record = smoke_test.call(
        {
            "tool": "oag.record",
            "arguments": {
                "ip_dir": str(ip),
                "stage": "sim",
                "claim": "evaluation fresh evidence baseline",
                "actor": {"kind": "ai", "id": "codex", "surface": "eval"},
                "rocev": {
                    "obligation": {"id": "OBL_DEMO_COUNTER_CX1_RESET_KNOWN"},
                    "contract": {"id": "CONTRACT_DEMO_COUNTER_CX1_SIM_SCOREBOARD", "method": "scoreboard"},
                    "evidence": {"files": ["sim/results.xml"], "tests": [], "commit": ""},
                    "validation": {"status": "closed", "verdict": "pass", "rationale": "hash baseline"},
                },
            },
        }
    )
    assert record["result"]["status"] == "closed", record
    before_hash = record["result"]["record"]["evidence"]["file_hashes"][0]["sha256"]
    (ip / "sim" / "results.xml").write_text('<testsuite failures="1"/>\n', encoding="utf-8")
    check = smoke_test.call({"tool": "oag.check", "arguments": {"ip_dir": str(ip)}})
    stale_issues = [issue for issue in check["result"]["issues"] if "evidence file stale: sim/results.xml" in issue]
    assert check["result"]["ok"] is False, check
    assert stale_issues, check
    return {
        "ip": str(ip),
        "record": record["result"]["id"],
        "baseline_hash": before_hash[:12],
        "mutated_file": "sim/results.xml",
        "stale_issue": stale_issues[0],
    }


def case_evidence_supersession_clears_stale_record(root: Path) -> dict[str, Any]:
    ip = smoke_test.make_ip(root / "freshness_supersession")
    baseline = smoke_test.call(
        {
            "tool": "oag.record",
            "arguments": {
                "ip_dir": str(ip),
                "stage": "sim",
                "claim": "evaluation stale evidence baseline",
                "actor": {"kind": "ai", "id": "codex", "surface": "eval"},
                "rocev": {
                    "obligation": {"id": "OBL_DEMO_COUNTER_CX1_RESET_KNOWN"},
                    "contract": {"id": "CONTRACT_DEMO_COUNTER_CX1_SIM_SCOREBOARD", "method": "scoreboard"},
                    "evidence": {"files": ["sim/results.xml"], "tests": [], "commit": ""},
                    "validation": {"status": "closed", "verdict": "pass", "rationale": "hash baseline"},
                },
            },
        }
    )
    (ip / "sim" / "results.xml").write_text('<testsuite failures="1"/>\n', encoding="utf-8")
    stale_check = smoke_test.call({"tool": "oag.check", "arguments": {"ip_dir": str(ip)}})
    assert any("evidence file stale: sim/results.xml" in issue for issue in stale_check["result"]["issues"]), stale_check
    superseder = smoke_test.call(
        {
            "tool": "oag.record",
            "arguments": {
                "ip_dir": str(ip),
                "stage": "sim",
                "claim": "evaluation fresh evidence supersedes stale baseline",
                "supersedes": [baseline["result"]["id"]],
                "actor": {"kind": "ai", "id": "codex", "surface": "eval"},
                "rocev": {
                    "obligation": {"id": "OBL_DEMO_COUNTER_CX1_RESET_KNOWN"},
                    "contract": {"id": "CONTRACT_DEMO_COUNTER_CX1_SIM_SCOREBOARD", "method": "scoreboard"},
                    "evidence": {"files": ["sim/results.xml"], "tests": [], "commit": ""},
                    "validation": {"status": "closed", "verdict": "pass", "rationale": "fresh evidence"},
                },
            },
        }
    )
    fresh_check = smoke_test.call({"tool": "oag.check", "arguments": {"ip_dir": str(ip)}})
    stale_issues = [issue for issue in fresh_check["result"]["issues"] if "evidence file stale: sim/results.xml" in issue]
    assert not stale_issues, fresh_check
    assert fresh_check["result"]["ok"] is True, fresh_check
    return {
        "ip": str(ip),
        "baseline": baseline["result"]["id"],
        "superseder": superseder["result"]["id"],
        "stale_before": True,
        "stale_after": False,
    }


def case_no_vacuous_pass_blocks_empty_matrix(root: Path) -> dict[str, Any]:
    ip = root / "empty_vacuous"
    ip.mkdir(parents=True)
    compile_result = smoke_test.call({"tool": "oag.compile", "arguments": {"ip_dir": str(ip)}})
    check = smoke_test.call({"tool": "oag.check", "arguments": {"ip_dir": str(ip)}})
    decision = smoke_test.call(
        {
            "tool": "oag.decide",
            "arguments": {
                "ip_dir": str(ip),
                "action": "claim_complete",
                "stage": "signoff",
            },
        }
    )
    assert compile_result["result"]["status"] == "fail", compile_result
    assert "no requirements in ontology/requirements.yaml" in compile_result["result"]["issues"], compile_result
    assert check["result"]["ok"] is False, check
    assert "closure matrix has no obligations" in check["result"]["issues"], check
    assert decision["result"]["allowed"] is False, decision
    assert decision["result"]["reason"] == "scope_lock_required", decision
    locked = smoke_test.call(
        {
            "tool": "oag.lock",
            "arguments": {
                "ip_dir": str(ip),
                "summary": "Evaluation locks empty scope to verify vacuous closure remains blocked after lock.",
                "confirmed_scope": ["empty matrix must not be accepted as closure"],
                "actor": {"kind": "human", "id": "eval-owner", "surface": "eval"},
            },
        }
    )
    assert locked["result"]["locked"] is True, locked
    locked_decision = smoke_test.call(
        {
            "tool": "oag.decide",
            "arguments": {
                "ip_dir": str(ip),
                "action": "claim_complete",
                "stage": "signoff",
            },
        }
    )
    assert locked_decision["result"]["allowed"] is False, locked_decision
    assert locked_decision["result"]["reason"] == "knowledge_check_failed", locked_decision
    return {
        "ip": str(ip),
        "compile_status": compile_result["result"]["status"],
        "check_ok": check["result"]["ok"],
        "decision_allowed": decision["result"]["allowed"],
        "decision_reason": decision["result"]["reason"],
        "locked_decision_reason": locked_decision["result"]["reason"],
        "matrix_issue": "closure matrix has no obligations",
    }


def case_module_per_file_boundary_blocks_greenfield(root: Path) -> dict[str, Any]:
    ip = smoke_test.make_ip(root / "module_file_boundary")
    bad_decomposition = "\n".join(
        [
            "schema: oag_decomposition.v1",
            f"ip: {ip.name}",
            "profile:",
            "  mode: greenfield_modular",
            "  rationale: evaluation duplicate physical files must be justified",
            "modules:",
            f"  - id: {ip.name}_top",
            "    ownership: current_ip",
            f"    file: rtl/{ip.name}.sv",
            "    role: top",
            "    owned_obligations: [OBL_DEMO_COUNTER_CX1_RESET_KNOWN]",
            "    owned_contracts: [CONTRACT_DEMO_COUNTER_CX1_SIM_SCOREBOARD]",
            f"  - id: {ip.name}_core",
            "    ownership: current_ip",
            f"    file: rtl/{ip.name}.sv",
            "    role: core",
            "    owned_obligations: []",
            "    owned_contracts: []",
            "",
        ]
    )
    decomp_path = ip / "ontology" / "decomposition.yaml"
    decomp_path.write_text(bad_decomposition, encoding="utf-8")
    _approve_eval_protected_update(ip, summary="Approve temporary duplicate-file decomposition fixture.")
    blocked = smoke_test.call({"tool": "oag.compile", "arguments": {"ip_dir": str(ip)}})
    boundary_issues = [
        issue
        for issue in blocked["result"]["issues"]
        if "greenfield_modular module file boundary requires unique file per current_ip module" in issue
    ]
    assert blocked["result"]["status"] == "fail", blocked
    assert boundary_issues, blocked

    decomp_path.write_text(
        bad_decomposition.replace(
            "  rationale: evaluation duplicate physical files must be justified\n",
            "  rationale: evaluation duplicate physical files must be justified\n"
            "  shared_file_rationale: evaluation permits generated wrapper/core in one temporary file\n",
            1,
        ),
        encoding="utf-8",
    )
    _approve_eval_protected_update(ip, summary="Approve shared-file rationale fixture update.")
    allowed = smoke_test.call({"tool": "oag.compile", "arguments": {"ip_dir": str(ip)}})
    assert not any(
        "greenfield_modular module file boundary requires unique file per current_ip module" in issue
        for issue in allowed["result"]["issues"]
    ), allowed
    assert allowed["result"]["status"] in {"ok", "pass"}, allowed
    return {
        "ip": str(ip),
        "blocked_status": blocked["result"]["status"],
        "boundary_issue": boundary_issues[0],
        "exception_status": allowed["result"]["status"],
        "exception": "profile.shared_file_rationale",
    }


def case_design_facts_graph_extraction_gate(root: Path) -> dict[str, Any]:
    ip = smoke_test.make_ip(root / "design_facts_graph")
    (ip / "list" / "rtl.f").write_text("rtl/demo_counter_cx1.sv\nrtl/counter_leaf.sv\n", encoding="utf-8")
    (ip / "ontology" / "decomposition.yaml").write_text(
        "\n".join(
            [
                "schema: oag_decomposition.v1",
                f"ip: {ip.name}",
                "profile:",
                "  mode: greenfield_modular",
                "  rationale: evaluation extracts implementation facts and checks module mapping",
                "modules:",
                "  - id: demo_counter_cx1",
                "    name: demo_counter_cx1",
                "    ownership: current_ip",
                "    file: rtl/demo_counter_cx1.sv",
                "    role: top",
                "    owned_obligations: [OBL_DEMO_COUNTER_CX1_RESET_KNOWN]",
                "    owned_contracts: [CONTRACT_DEMO_COUNTER_CX1_SIM_SCOREBOARD]",
                "  - id: counter_leaf",
                "    name: counter_leaf",
                "    ownership: current_ip",
                "    file: rtl/counter_leaf.sv",
                "    role: datapath_leaf",
                "    owned_obligations: []",
                "    owned_contracts: []",
                "",
            ]
        ),
        encoding="utf-8",
    )
    _approve_eval_protected_update(ip, summary="Approve design-facts decomposition fixture.")
    top = ip / "rtl" / "demo_counter_cx1.sv"
    leaf = ip / "rtl" / "counter_leaf.sv"
    top.write_text(
        "\n".join(
            [
                "module demo_counter_cx1(",
                "  input logic clk_i,",
                "  input logic rst_ni,",
                "  inout wire pad_io,",
                "  output logic [7:0] count_o",
                ");",
                "  parameter int DEPTH = 4;",
                "  logic [7:0] count_q;",
                "  logic [31:0] mem_q [0:3];",
                "  counter_leaf u_leaf(.clk_i(clk_i), .rst_ni(rst_ni), .count_o(count_o));",
                "  assign pad_io = 1'bz;",
                "  always_ff @(posedge clk_i or negedge rst_ni) begin",
                "    if (!rst_ni) count_q <= '0;",
                "    else count_q <= count_q + 8'd1;",
                "  end",
                "endmodule",
                "",
            ]
        ),
        encoding="utf-8",
    )
    leaf.write_text(
        "\n".join(
            [
                "module wrong_leaf(input logic clk_i, input logic rst_ni, output logic [7:0] count_o);",
                "  logic [7:0] leaf_q;",
                "  assign count_o = leaf_q;",
                "endmodule",
                "",
            ]
        ),
        encoding="utf-8",
    )
    blocked = smoke_test.call({"tool": "oag.compile", "arguments": {"ip_dir": str(ip)}})
    assert blocked["result"]["status"] == "fail", blocked
    assert any("design_facts: counter_leaf not found in extracted RTL facts" in issue for issue in blocked["result"]["issues"]), blocked
    assert any("design_facts: extracted RTL module is not mapped" in issue for issue in blocked["result"]["issues"]), blocked

    leaf.write_text(leaf.read_text(encoding="utf-8").replace("module wrong_leaf", "module counter_leaf", 1), encoding="utf-8")
    allowed = smoke_test.call({"tool": "oag.compile", "arguments": {"ip_dir": str(ip)}})
    assert allowed["result"]["status"] == "pass", allowed
    facts = json.loads((ip / "ontology" / "generated" / "design_facts_graph.json").read_text(encoding="utf-8"))
    modules = {module["name"]: module for module in facts["modules"]}
    assert {"demo_counter_cx1", "counter_leaf"} <= set(modules), facts
    top_facts = modules["demo_counter_cx1"]
    assert any(port["name"] == "pad_io" and port["direction"] == "inout" for port in top_facts["ports"]), facts
    assert any(memory["name"] == "mem_q" for memory in top_facts["memories"]), facts
    assert any(instance["name"] == "u_leaf" and instance["module"] == "counter_leaf" for instance in top_facts["instances"]), facts
    assert allowed["result"]["stats"]["design_facts_modules"] == 2, allowed
    return {
        "ip": str(ip),
        "blocked_issue": "decomposition module not found in extracted RTL facts",
        "after_fix_status": allowed["result"]["status"],
        "extractor": facts["extractor"]["backend"],
        "modules": sorted(modules),
        "ports": len(top_facts["ports"]),
        "instances": len(top_facts["instances"]),
    }


def case_interleaved_context_coverage_gate(root: Path) -> dict[str, Any]:
    ip = smoke_test.make_ip(root / "interleaved_context")
    rules_path = ip / "ontology" / "design_rules.yaml"
    rules_text = rules_path.read_text(encoding="utf-8")
    rules_text = rules_text.replace(
        "instances:\n",
        "\n".join(
            [
                "  - id: RULE_INTERLEAVED_CONTEXT_COVERAGE",
                "    kind: interleaved_context_coverage",
                "    status: active",
                "instances:",
                "  - id: INST_CONTEXT_A_B_INTERLEAVED",
                "    rule: RULE_INTERLEAVED_CONTEXT_COVERAGE",
                "    status: closed",
                "    requirement: REQ_DEMO_COUNTER_CX1_001",
                "    obligation: OBL_DEMO_COUNTER_CX1_RESET_KNOWN",
                "    contract: CONTRACT_DEMO_COUNTER_CX1_SIM_SCOREBOARD",
                "    context_count: 2",
                "    interleaving_pattern: [A.SOM, B.SOM, A.EOM, B.EOM]",
                "    coverage_refs: [COV_INTERLEAVED_CTX]",
                "",
            ]
        ),
        1,
    )
    rules_path.write_text(rules_text, encoding="utf-8")
    blocked = smoke_test.call({"tool": "oag.compile", "arguments": {"ip_dir": str(ip)}})
    assert blocked["result"]["status"] == "fail", blocked
    assert "INST_CONTEXT_A_B_INTERLEAVED: interleaved context coverage ref not observed: COV_INTERLEAVED_CTX" in blocked["result"]["issues"], blocked

    scoreboard_path = ip / "sim" / "scoreboard_events.jsonl"
    row = {
        "goal_id": "GOAL_INTERLEAVED_CTX",
        "scenario_id": "SC_A_B_INTERLEAVED",
        "cycle": 8,
        "stimulus": {"pattern": ["A.SOM", "B.SOM", "A.EOM", "B.EOM"]},
        "expected": {"contexts_closed": ["A", "B"]},
        "observed": {"contexts_closed": ["A", "B"]},
        "observed_source": {"kind": "monitor", "path": "ctx_monitor.closed_ids"},
        "passed": True,
        "mismatch": "",
        "coverage_refs": ["COV_INTERLEAVED_CTX"],
    }
    scoreboard_path.write_text(scoreboard_path.read_text(encoding="utf-8") + json.dumps(row, sort_keys=True) + "\n", encoding="utf-8")
    allowed = smoke_test.call({"tool": "oag.compile", "arguments": {"ip_dir": str(ip)}})
    assert allowed["result"]["status"] == "pass", allowed
    return {
        "ip": str(ip),
        "blocked_issue": "interleaved context coverage ref not observed",
        "coverage_ref": "COV_INTERLEAVED_CTX",
        "after_scoreboard_status": allowed["result"]["status"],
    }


def case_fault_model_coverage_gate(root: Path) -> dict[str, Any]:
    ip = smoke_test.make_ip(root / "fault_model_coverage")
    rules_path = ip / "ontology" / "design_rules.yaml"
    rules_text = rules_path.read_text(encoding="utf-8")
    rules_text += "\n".join(
        [
            "",
            "  - id: INST_COUNTER_INC_FAULT_MODEL_COVERAGE",
            "    rule: RULE_FAULT_MODEL_COVERAGE",
            "    status: closed",
            "    requirement: REQ_DEMO_COUNTER_CX1_001",
            "    obligation: OBL_DEMO_COUNTER_CX1_RESET_KNOWN",
            "    contract: CONTRACT_DEMO_COUNTER_CX1_SIM_SCOREBOARD",
            "    coverage_refs: [COV_INC]",
            "    fault_models: [FM_COUNTER_STUCK_AT_ZERO]",
            "    mutation_results: []",
            "",
        ]
    )
    rules_path.write_text(rules_text, encoding="utf-8")
    blocked = smoke_test.call({"tool": "oag.compile", "arguments": {"ip_dir": str(ip)}})
    assert blocked["result"]["status"] == "fail", blocked
    assert (
        "INST_COUNTER_INC_FAULT_MODEL_COVERAGE: fault model has no mutation result: FM_COUNTER_STUCK_AT_ZERO"
        in blocked["result"]["issues"]
    ), blocked

    mutation_summary = ip / "mutation" / "relevant_tc" / "relevant_mutation_summary.json"
    mutation_summary.parent.mkdir(parents=True, exist_ok=True)
    mutation_summary.write_text(
        json.dumps(
            {
                "schema_version": "oag_relevant_mutation_summary.v1",
                "baseline_rows": 2,
                "mutants_run": 1,
                "mutants_killed": 1,
                "relevant_rows_total": 2,
                "relevant_rows_killed": 2,
                "uncovered_scenarios": [],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    rules_text = rules_path.read_text(encoding="utf-8").replace(
        "    mutation_results: []",
        "\n".join(
            [
                "    mutation_results:",
                "      - id: MUT_COUNTER_STUCK_AT_ZERO",
                "        fault_model: FM_COUNTER_STUCK_AT_ZERO",
                "        status: killed",
                "        evidence_ref: mutation/relevant_tc/relevant_mutation_summary.json",
            ]
        ),
        1,
    )
    rules_path.write_text(rules_text, encoding="utf-8")
    allowed = smoke_test.call({"tool": "oag.compile", "arguments": {"ip_dir": str(ip)}})
    assert allowed["result"]["status"] == "pass", allowed
    graph = json.loads((ip / "ontology" / "generated" / "design_truth_graph.json").read_text(encoding="utf-8"))
    node_types = {node.get("type") for node in graph.get("nodes", []) if isinstance(node, dict)}
    assert "fault_model" in node_types, graph
    assert "mutation" in node_types, graph
    return {
        "ip": str(ip),
        "blocked_issue": "fault model has no mutation result",
        "mutation_evidence": "mutation/relevant_tc/relevant_mutation_summary.json",
        "after_mutation_status": allowed["result"]["status"],
        "graph_has_fault_model_nodes": "fault_model" in node_types,
    }


def case_verification_role_decomposition_gate(root: Path) -> dict[str, Any]:
    ip = smoke_test.make_ip(root / "verification_role_decomposition")
    rules_path = ip / "ontology" / "design_rules.yaml"
    rules_text = rules_path.read_text(encoding="utf-8")
    rules_text += "\n".join(
        [
            "",
            "  - id: INST_COUNTER_VERIF_ARCH",
            "    rule: RULE_VERIFICATION_ROLE_DECOMPOSITION",
            "    status: closed",
            "    requirement: REQ_DEMO_COUNTER_CX1_001",
            "    obligation: OBL_DEMO_COUNTER_CX1_RESET_KNOWN",
            "    contract: CONTRACT_DEMO_COUNTER_CX1_SIM_SCOREBOARD",
            "    style: uvm_concepts",
            "    framework: verilator_cpp",
            "    roles:",
            "      sequence: tb/sequence.cpp",
            "      driver: tb/driver.cpp",
            "      monitor: tb/monitor.cpp",
            "      reference_model: tb/reference_model.cpp",
            "      scoreboard: tb/scoreboard.cpp",
            "      coverage: tb/coverage.cpp",
            "      env: tb/env.cpp",
            "",
        ]
    )
    rules_path.write_text(rules_text, encoding="utf-8")
    blocked = smoke_test.call({"tool": "oag.compile", "arguments": {"ip_dir": str(ip)}})
    assert blocked["result"]["status"] == "fail", blocked
    assert "INST_COUNTER_VERIF_ARCH: verification role missing artifact: test" in blocked["result"]["issues"], blocked
    assert "INST_COUNTER_VERIF_ARCH: verification role independence missing expected_source" in blocked["result"]["issues"], blocked

    for rel in [
        "tb/sequence.cpp",
        "tb/driver.cpp",
        "tb/monitor.cpp",
        "tb/reference_model.cpp",
        "tb/scoreboard.cpp",
        "tb/coverage.cpp",
        "tb/env.cpp",
        "tb/tests/test_counter.cpp",
    ]:
        path = ip / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"// {rel}\n", encoding="utf-8")
    rules_text = rules_path.read_text(encoding="utf-8")
    rules_text = rules_text.replace(
        "      env: tb/env.cpp\n",
        "\n".join(
            [
                "      env: tb/env.cpp",
                "      test: tb/tests/test_counter.cpp",
                "    independence:",
                "      expected_source: reference_model",
                "      observed_source: monitor",
                "      compare_source: scoreboard",
            ]
        )
        + "\n",
        1,
    )
    rules_path.write_text(rules_text, encoding="utf-8")
    allowed = smoke_test.call({"tool": "oag.compile", "arguments": {"ip_dir": str(ip)}})
    assert allowed["result"]["status"] == "pass", allowed
    graph = json.loads((ip / "ontology" / "generated" / "design_truth_graph.json").read_text(encoding="utf-8"))
    role_nodes = [node for node in graph.get("nodes", []) if isinstance(node, dict) and node.get("type") == "verification_role"]
    assert len(role_nodes) >= 8, graph
    return {
        "ip": str(ip),
        "blocked_issue": "verification role missing artifact",
        "style": "uvm_concepts",
        "framework": "verilator_cpp",
        "after_roles_status": allowed["result"]["status"],
        "verification_role_nodes": len(role_nodes),
    }


def case_signoff_domain_rule_gates(root: Path) -> dict[str, Any]:
    ip = smoke_test.make_ip(root / "signoff_domain_rules")
    rules_path = ip / "ontology" / "design_rules.yaml"
    rules_path.write_text(
        rules_path.read_text(encoding="utf-8")
        + "\n".join(
            [
                "",
                "  - id: INST_AXI_APB_CDC",
                "    rule: RULE_CDC_CROSSING_COVERAGE",
                "    status: closed",
                "    requirement: REQ_DEMO_COUNTER_CX1_001",
                "    obligation: OBL_DEMO_COUNTER_CX1_RESET_KNOWN",
                "    contract: CONTRACT_DEMO_COUNTER_CX1_SIM_SCOREBOARD",
                "    clock_domains: [axi_aclk, pclk]",
                "    crossings: [apb_cfg_to_axi_shadow, axi_event_to_apb_status]",
                "    evidence_refs: [cdc/cdc_report.json]",
                "  - id: INST_AXI4_PROTOCOL",
                "    rule: RULE_PROTOCOL_COMPLIANCE",
                "    status: closed",
                "    requirement: REQ_DEMO_COUNTER_CX1_001",
                "    obligation: OBL_DEMO_COUNTER_CX1_RESET_KNOWN",
                "    contract: CONTRACT_DEMO_COUNTER_CX1_SIM_SCOREBOARD",
                "    protocol: AXI4",
                "    coverage_refs: [COV_AXI_PROTOCOL]",
                "    evidence_refs: [protocol/axi4_assertions.log]",
                "  - id: INST_STA_TIMING",
                "    rule: RULE_TIMING_CLOSURE",
                "    status: closed",
                "    requirement: REQ_DEMO_COUNTER_CX1_001",
                "    obligation: OBL_DEMO_COUNTER_CX1_RESET_KNOWN",
                "    contract: CONTRACT_DEMO_COUNTER_CX1_SIM_SCOREBOARD",
                "    sdc_refs: [sdc/top.sdc]",
                "    timing_reports: [sta/out/wns.json]",
                "    setup_wns_ns: 0.01",
                "    hold_wns_ns: 0.02",
                "    setup_wns_ns_min: 0.0",
                "    hold_wns_ns_min: 0.0",
                "    evidence_refs: [sta/out/wns.json]",
                "  - id: INST_FUNCTIONAL_COVERAGE",
                "    rule: RULE_FUNCTIONAL_COVERAGE_CLOSURE",
                "    status: closed",
                "    requirement: REQ_DEMO_COUNTER_CX1_001",
                "    obligation: OBL_DEMO_COUNTER_CX1_RESET_KNOWN",
                "    contract: CONTRACT_DEMO_COUNTER_CX1_SIM_SCOREBOARD",
                "    coverage_refs: [COV_FUNC_DONE]",
                "    coverage_goal: 100",
                "    coverage_actual: 95",
                "    evidence_refs: [cov/coverage_functional.json, cov/coverage_ssot.json]",
                "  - id: INST_RESET_XPROP",
                "    rule: RULE_RESET_XPROP_COVERAGE",
                "    status: closed",
                "    requirement: REQ_DEMO_COUNTER_CX1_001",
                "    obligation: OBL_DEMO_COUNTER_CX1_RESET_KNOWN",
                "    contract: CONTRACT_DEMO_COUNTER_CX1_SIM_SCOREBOARD",
                "    reset_scenarios: [async_assert_sync_deassert]",
                "    xprop_checks: [reset_release_no_unknown_outputs]",
                "    coverage_refs: [COV_RESET_XPROP]",
                "    evidence_refs: [sim/xprop_reset.log]",
                "",
            ]
        ),
        encoding="utf-8",
    )
    blocked = smoke_test.call({"tool": "oag.compile", "arguments": {"ip_dir": str(ip)}})
    assert blocked["result"]["status"] == "fail", blocked
    issues = blocked["result"]["issues"]
    assert "INST_AXI_APB_CDC: CDC crossing coverage evidence ref missing on disk: cdc/cdc_report.json" in issues, blocked
    assert "INST_AXI4_PROTOCOL: protocol compliance coverage ref not observed: COV_AXI_PROTOCOL" in issues, blocked
    assert "INST_STA_TIMING: timing closure missing target_clocks/target_frequency" in issues, blocked
    assert "INST_STA_TIMING: timing closure evidence ref missing on disk: sdc/top.sdc" in issues, blocked
    assert "INST_FUNCTIONAL_COVERAGE: functional coverage below goal: 95.0 < 100.0" in issues, blocked
    assert "INST_RESET_XPROP: reset/X-prop coverage coverage ref not observed: COV_RESET_XPROP" in issues, blocked

    files = {
        "cdc/cdc_report.json": {"status": "pass", "crossings": 2},
        "protocol/axi4_assertions.log": "AXI4 protocol assertions PASS\n",
        "sdc/top.sdc": "create_clock -name axi_aclk -period 10 [get_ports axi_aclk]\n",
        "sta/out/wns.json": {"status": "pass", "summary": {"all_setup_met": True, "all_hold_met": True}},
        "cov/coverage_functional.json": {"status": "pass", "score": 100},
        "cov/coverage_ssot.json": {"status": "pass", "covered": ["COV_FUNC_DONE"]},
        "sim/xprop_reset.log": "reset/X-prop checks PASS\n",
    }
    for rel, content in files.items():
        path = ip / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, dict):
            path.write_text(json.dumps(content, indent=2) + "\n", encoding="utf-8")
        else:
            path.write_text(content, encoding="utf-8")
    (ip / "cov" / "coverage.json").write_text(
        json.dumps(
            {
                "status": "pass",
                "coverage_points": [
                    {"id": "COV_AXI_PROTOCOL", "status": "hit"},
                    {"id": "COV_FUNC_DONE", "status": "hit"},
                    {"id": "COV_RESET_XPROP", "status": "hit"},
                ],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    rules_text = rules_path.read_text(encoding="utf-8")
    rules_text = rules_text.replace(
        "    sdc_refs: [sdc/top.sdc]\n",
        "\n".join(
            [
                "    target_clocks:",
                "      - name: axi_aclk",
                "        frequency_mhz: 100",
                "        period_ns: 10.0",
                "      - name: pclk",
                "        frequency_mhz: 50",
                "        period_ns: 20.0",
                "    async_clock_groups:",
                "      - [axi_aclk, pclk]",
                "    input_delay_ratio: 0.5",
                "    output_delay_ratio: 0.5",
                "    sdc_refs: [sdc/top.sdc]",
            ]
        )
        + "\n",
        1,
    )
    rules_text = rules_text.replace("    coverage_actual: 95", "    coverage_actual: 100", 1)
    rules_path.write_text(rules_text, encoding="utf-8")
    allowed = smoke_test.call({"tool": "oag.compile", "arguments": {"ip_dir": str(ip)}})
    assert allowed["result"]["status"] == "pass", allowed
    graph = json.loads((ip / "ontology" / "generated" / "design_truth_graph.json").read_text(encoding="utf-8"))
    node_types = {node.get("type") for node in graph.get("nodes", []) if isinstance(node, dict)}
    assert {"protocol", "clock_domain", "coverage_ref", "artifact"} <= node_types, graph
    return {
        "ip": str(ip),
        "blocked_checks": [
            "cdc evidence missing",
            "protocol coverage unobserved",
            "timing target frequency and SDC/report missing",
            "functional coverage below goal",
            "reset/X-prop coverage unobserved",
        ],
        "after_evidence_status": allowed["result"]["status"],
        "graph_node_types": sorted(node_types & {"protocol", "clock_domain", "coverage_ref", "artifact"}),
    }


def case_reviewer_separation_signoff_gate(root: Path) -> dict[str, Any]:
    ip = smoke_test.make_ip(root / "reviewer_gate")
    _record_closed_validation(ip)
    _human_approve_signoff_profile(ip)
    compiled = smoke_test.call({"tool": "oag.compile", "arguments": {"ip_dir": str(ip)}})
    assert compiled["result"]["status"] == "pass", compiled
    smoke_test.write_stage_receipt(ip, "sim")
    blocked = smoke_test.call(
        {
            "tool": "oag.decide",
            "arguments": {
                "ip_dir": str(ip),
                "action": "signoff",
                "stage": "signoff",
                "record_decision": True,
                "actor": {"kind": "human", "id": "eval-owner", "surface": "eval"},
            },
        }
    )
    assert blocked["result"]["allowed"] is False, blocked
    assert blocked["result"]["reason"] == "reviewer_receipt_required", blocked
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
                "actor": {"kind": "ai", "id": "producer", "surface": "eval"},
                "producer_actor": {"kind": "ai", "id": "producer", "surface": "eval"},
                "independent": False,
                "findings": [],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    still_blocked = smoke_test.call(
        {
            "tool": "oag.decide",
            "arguments": {
                "ip_dir": str(ip),
                "action": "signoff",
                "stage": "signoff",
                "record_decision": True,
                "actor": {"kind": "human", "id": "eval-owner", "surface": "eval"},
            },
        }
    )
    assert still_blocked["result"]["allowed"] is False, still_blocked
    assert still_blocked["result"]["reason"] == "reviewer_receipt_required", still_blocked
    review = smoke_test.call(
        {
            "tool": "oag.review",
            "arguments": {
                "ip_dir": str(ip),
                "action": "signoff",
                "stage": "signoff",
                "verdict": "pass",
                "actor": {"kind": "ai", "id": "signoff-reviewer", "surface": "eval"},
                "producer_actor": {"kind": "ai", "id": "producer", "surface": "eval"},
                "findings": [],
            },
        }
    )
    assert review["result"]["allowed"] is True, review
    assert Path(review["result"]["reviewer_receipt"]["path"]).is_file(), review
    allowed = smoke_test.call(
        {
            "tool": "oag.decide",
            "arguments": {
                "ip_dir": str(ip),
                "action": "signoff",
                "stage": "signoff",
                "record_decision": True,
                "actor": {"kind": "human", "id": "eval-owner", "surface": "eval"},
            },
        }
    )
    assert allowed["result"]["allowed"] is True, allowed
    return {
        "ip": str(ip),
        "blocked_reason": blocked["result"]["reason"],
        "non_independent_receipt_rejected": still_blocked["result"]["reason"] == "reviewer_receipt_required",
        "review_receipt": review["result"]["reviewer_receipt"]["id"],
        "signoff_allowed_after_review": allowed["result"]["allowed"],
    }


def case_codex_runtime_hook_configuration(root: Path) -> dict[str, Any]:
    hooks = json.loads((smoke_test.ROOT / "hooks.json").read_text(encoding="utf-8"))
    events = hooks.get("hooks") if isinstance(hooks.get("hooks"), dict) else {}
    user_commands = [
        hook.get("command")
        for group in events.get("UserPromptSubmit", [])
        for hook in group.get("hooks", [])
        if isinstance(hook, dict)
    ]
    stop_commands = [
        hook.get("command")
        for group in events.get("Stop", [])
        for hook in group.get("hooks", [])
        if isinstance(hook, dict)
    ]
    post_compact_commands = [
        hook.get("command")
        for group in events.get("PostCompact", [])
        for hook in group.get("hooks", [])
        if isinstance(hook, dict)
    ]
    assert "python3 .codex/hooks/codex_context_inject.py" in user_commands, hooks
    assert "python3 .codex/hooks/codex_draft_pressure.py" in user_commands, hooks
    assert "python3 .codex/hooks/codex_stop_gate.py" in stop_commands, hooks
    assert "python3 .codex/hooks/codex_context_inject.py" in post_compact_commands, hooks
    return {
        "hooks_json": str(smoke_test.ROOT / "hooks.json"),
        "user_prompt_submit_hooks": len(user_commands),
        "stop_hooks": len(stop_commands),
        "post_compact_hooks": len(post_compact_commands),
        "runtime_note": "Codex must approve hooks at startup; this case verifies the committed hook contract.",
    }


CASES: list[tuple[str, CaseFn]] = [
    ("stop_gate_blocks_incomplete", case_stop_gate_blocks_incomplete),
    ("stop_gate_obeys_policy_limit", case_stop_gate_obeys_policy_limit),
    ("compile_skips_fresh_graph", case_compile_skips_fresh_graph),
    ("stop_gate_allows_complete", case_stop_gate_allows_complete),
    ("stop_gate_allows_needs_human", case_stop_gate_allows_needs_human),
    ("completion_requires_decision_receipt", case_completion_requires_decision_receipt),
    ("context_injection_before_work", case_context_injection_before_work),
    ("draft_on_pressure_injects_guard", case_draft_on_pressure_injects_guard),
    ("evidence_freshness_mutation_blocks", case_evidence_freshness_mutation_blocks),
    ("evidence_supersession_clears_stale_record", case_evidence_supersession_clears_stale_record),
    ("no_vacuous_pass_blocks_empty_matrix", case_no_vacuous_pass_blocks_empty_matrix),
    ("module_per_file_boundary_blocks_greenfield", case_module_per_file_boundary_blocks_greenfield),
    ("design_facts_graph_extraction_gate", case_design_facts_graph_extraction_gate),
    ("interleaved_context_coverage_gate", case_interleaved_context_coverage_gate),
    ("fault_model_coverage_gate", case_fault_model_coverage_gate),
    ("verification_role_decomposition_gate", case_verification_role_decomposition_gate),
    ("signoff_domain_rule_gates", case_signoff_domain_rule_gates),
    ("reviewer_separation_signoff_gate", case_reviewer_separation_signoff_gate),
    ("codex_runtime_hook_configuration", case_codex_runtime_hook_configuration),
]


def _run_case(name: str, fn: CaseFn, root: Path) -> dict[str, Any]:
    started = time.perf_counter()
    try:
        observations = fn(root / name)
        return {
            "name": name,
            "ok": True,
            "duration_s": round(time.perf_counter() - started, 3),
            "observations": observations,
            "error": "",
        }
    except Exception as exc:  # pragma: no cover - failure path is for reports
        return {
            "name": name,
            "ok": False,
            "duration_s": round(time.perf_counter() - started, 3),
            "observations": {},
            "error": f"{type(exc).__name__}: {exc}",
            "traceback": traceback.format_exc(limit=6),
        }


def _format_text(report: dict[str, Any]) -> str:
    lines = [
        f"OAG evaluation: {report['passed']}/{report['total']} passed",
        f"temp_root: {report['temp_root']}",
    ]
    for case in report["cases"]:
        mark = "PASS" if case["ok"] else "FAIL"
        lines.append(f"- {mark} {case['name']} ({case['duration_s']}s)")
        if case["error"]:
            lines.append(f"  error: {case['error']}")
        else:
            for key, value in case["observations"].items():
                lines.append(f"  {key}: {value}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="print JSON report")
    parser.add_argument("--keep-temp", action="store_true", help="keep the temporary evaluation IPs on disk")
    args = parser.parse_args(argv)

    if args.keep_temp:
        temp_dir = tempfile.mkdtemp(prefix="oag-eval-")
        cleanup = None
    else:
        cleanup = tempfile.TemporaryDirectory(prefix="oag-eval-")
        temp_dir = cleanup.name

    root = Path(temp_dir)
    cases = [_run_case(name, fn, root) for name, fn in CASES]
    passed = sum(1 for case in cases if case["ok"])
    report = {
        "schema_version": "oag_evaluation_report.v1",
        "ok": passed == len(cases),
        "passed": passed,
        "failed": len(cases) - passed,
        "total": len(cases),
        "temp_root": temp_dir,
        "cases": cases,
    }
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(_format_text(report))

    if cleanup is not None:
        cleanup.cleanup()
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
