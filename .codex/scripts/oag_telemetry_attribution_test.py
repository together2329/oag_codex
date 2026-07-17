#!/usr/bin/env python3
"""Focused tests for OAG execution attribution and budget evaluation."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "hooks"))
sys.path.insert(0, str(ROOT / "scripts"))

import oag_otel_cost  # noqa: E402
import oag_telemetry  # noqa: E402


def write(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def main() -> int:
    with tempfile.TemporaryDirectory() as raw:
        root = Path(raw)
        dispatch_path = root / "ip/knowledge/dispatches/d.json"
        receipt_path = root / "ip/knowledge/subagents/r.json"
        write(
            dispatch_path,
            {
                "execution_budget": {
                    "complexity": "simple",
                    "max_total_tokens": 5_000_000,
                    "warning_total_tokens": 4_000_000,
                    "max_review_attempts": 1,
                    "model_tier": "mechanical",
                },
                "context_contract": {
                    "fork_turns": "none",
                    "input_mode": "authoring_packet_or_explicit_file_list",
                    "max_direct_source_files": 8,
                    "repeat_review_policy": "content_hash_delta_only",
                },
                "dispatch_integrity": {"scope_hash": "f" * 64},
                "allowed_write_paths": ["ip/knowledge/reviews/"],
                "baseline": {
                    "file_hashes": {
                        "ip/rtl/dut.sv": "b" * 64,
                        "ip/knowledge/reviews/old.json": "c" * 64,
                    }
                },
            },
        )
        write(
            receipt_path,
            {
                "dispatch_id": "DISPATCH_TEST",
                "dispatch_path": "ip/knowledge/dispatches/d.json",
                "role_name": "oag-evidence-validator",
                "stage": "evidence",
                "status": "HANDOFF_PASS",
                "task_id": "task-evidence",
                "wavefront_run_id": "RUN_1",
                "output_hashes": {"ip/report.json": "sha256:" + "a" * 64},
            },
        )
        payload = {
            "cwd": str(root),
            "last_assistant_message": "OAG_EVIDENCE_RECORDED: ip/knowledge/subagents/r.json",
        }
        metadata = oag_telemetry._receipt_metadata(payload)  # noqa: SLF001
        assert metadata["task_id"] == "task-evidence"
        assert metadata["model_tier"] == "mechanical"
        assert metadata["max_total_tokens"] == 5_000_000
        assert metadata["fork_turns"] == "none"
        assert metadata["content_fingerprint"].startswith("sha256:")
        assert metadata["review_target_fingerprint"].startswith("sha256:")

        item = {
            "conversation_id": "child",
            "model": "gpt-test",
            "source": "codex_otel",
            "tokens": {
                "input_tokens": 4_100_000,
                "cached_input_tokens": 4_000_000,
                "output_tokens": 100_000,
                "reasoning_output_tokens": 20_000,
            },
            "started_at": "2026-07-17T00:00:00Z",
            "ended_at": "2026-07-17T00:01:00Z",
            **metadata,
        }
        summary = oag_otel_cost.summarize([item], oag_otel_cost.load_rate_card(None))
        assert item["budget_status"] == "warning"
        assert summary["budget_status"]["warning"] == 1
        assert summary["by_task"]["task-evidence"]["tokens"]["input_tokens"] == 4_100_000
        assert "oag-evidence-validator" in summary["by_role"]
        assert "RUN_1" in summary["by_mission"]

    print('{"status":"pass","tests":11,"suite":"oag_telemetry_attribution"}')
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
