#!/usr/bin/env python3
"""Focused tests for dispatch cost controls and integrity compatibility."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))

from oag_dispatch_prompt import build_prompt_contract  # noqa: E402
from oag_dispatch_support import dispatch_integrity, dispatch_integrity_fields, files_under  # noqa: E402
from oag_dispatch_verify import valid_dispatch_integrity  # noqa: E402
from oag_execution_efficiency import build_execution_controls, infer_complexity, infer_model_tier  # noqa: E402


def base_dispatch() -> dict:
    return {
        "schema_version": "oag_dispatch.v1",
        "dispatch_id": "DISPATCH_TEST_20260717T000000Z_00000000",
        "dispatch_path": "ip/knowledge/dispatches/test.json",
        "agent_type": "oag-rtl-implementation-agent",
        "role_name": "oag-rtl-implementation-agent",
        "role_kind": "core",
        "registered_id": "oag-rtl-implementation-agent",
        "ip_id": "ip",
        "ip_dir": "ip",
        "stage": "rtl",
        "owned_obligations": [],
        "contracts": [],
        "allowed_write_paths": ["ip/rtl/a.sv"],
        "allowed_tool_side_effects": [],
        "receipt_path": "ip/knowledge/subagents/test.json",
        "may_claim_complete": False,
        "wavefront_run_id": "",
        "task_id": "",
        "ownership_mode": "",
        "baseline": {},
        "created_at": "2026-07-17T00:00:00Z",
    }


def main() -> int:
    assert infer_complexity("oag-rtl-implementation-agent", "rtl") == "complex"
    assert infer_complexity("oag-evidence-validator", "evidence") == "simple"
    assert infer_model_tier("oag-rtl-implementation-agent", "rtl") == "reasoning"
    assert infer_model_tier("oag-evidence-validator", "evidence") == "mechanical"

    budget, context = build_execution_controls(agent_type="oag-rtl-implementation-agent", stage="rtl")
    assert budget["max_total_tokens"] == 20_000_000
    assert budget["warning_total_tokens"] == 16_000_000

    early_budget, _ = build_execution_controls(
        agent_type="oag-custom-reviewer",
        stage="rtl_review",
        complexity="medium",
        max_total_tokens=250_000,
        warning_total_tokens=90_000,
    )
    assert early_budget["warning_total_tokens"] == 90_000
    assert budget["max_review_attempts"] == 1
    assert context["fork_turns"] == "none"

    legacy = base_dispatch()
    legacy["dispatch_integrity"] = dispatch_integrity(legacy)
    assert valid_dispatch_integrity(legacy)

    current = base_dispatch()
    current["execution_budget"] = budget
    current["context_contract"] = context
    current["execution_actor"] = {
        "schema_version": "oag_execution_actor.v1",
        "kind": "worker_thread",
        "isolation": "fresh_thread",
        "resume_limit": 1,
        "subagents_allowed": False,
        "manifest_path": "ip/knowledge/executions/test.thread.json",
    }
    current["dispatch_integrity"] = dispatch_integrity(current)
    assert valid_dispatch_integrity(current)
    assert dispatch_integrity_fields(current)[-3:] == ["execution_budget", "context_contract", "execution_actor"]
    prompt = build_prompt_contract(current)
    assert "max_total_tokens: 20000000" in prompt
    assert "fork_turns: none" in prompt
    assert "do not request or replay the full parent transcript" in prompt
    assert "do not spawn, delegate to, or communicate with subagents" in prompt

    with tempfile.TemporaryDirectory(prefix="oag-baseline-filter-") as tmp:
        root = Path(tmp)
        source = root / "keep.py"
        cache = root / "__pycache__" / "keep.cpython-314.pyc"
        source.write_text("pass\n", encoding="utf-8")
        cache.parent.mkdir(parents=True)
        cache.write_bytes(b"cache")
        assert files_under(root) == [source]

    current["execution_budget"]["max_total_tokens"] += 1
    assert not valid_dispatch_integrity(current)
    print('{"status":"pass","tests":15,"suite":"oag_execution_efficiency"}')
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
