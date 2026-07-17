#!/usr/bin/env python3
"""Focused regression for execution-efficiency issue detection."""

from __future__ import annotations

import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent))
from oag_execution_efficiency_check import check_report  # noqa: E402


def session(name: str, tokens: int, **extra: object) -> dict:
    return {
        "conversation_id": name,
        "agent_type": name,
        "tokens": {"input_tokens": tokens, "cached_input_tokens": 0, "output_tokens": 0, "reasoning_output_tokens": 0},
        **extra,
    }


def main() -> int:
    small = {
        "sessions": [
            session("review_a", 110, max_total_tokens=100, content_fingerprint="sha256:a", review_target_fingerprint="sha256:target"),
            session("review_b", 10, content_fingerprint="sha256:b", review_target_fingerprint="sha256:target"),
        ]
    }
    failed = check_report(small)
    codes = {item["code"] for item in failed["issues"]}
    assert failed["status"] == "fail"
    assert codes == {"EFF-BUDGET-001", "EFF-REVIEW-001"}
    assert failed["metrics"]["root_token_share"] is None

    balanced = {
        "sessions": [
            session("root", 100, execution_kind="main"),
            *[session(f"rtl_{index}", 100, parent_session_id="root") for index in range(1, 20)],
        ]
    }
    passed = check_report(balanced, single_agent_share_max=0.06)
    assert passed["status"] == "pass"
    assert passed["metrics"]["root_token_share"] == 0.05
    assert passed["metrics"]["largest_agent_token_share"] == 0.05

    concentrated = {
        "sessions": [
            session("root", 600, execution_kind="main"),
            *[session(f"review_{i}", 100, parent_session_id="root") for i in range(4)],
        ]
    }
    bad = check_report(concentrated)
    bad_codes = {item["code"] for item in bad["issues"]}
    assert {"EFF-ROOT-001", "EFF-PROCESS-001", "EFF-AGENT-001"} <= bad_codes

    print('{"status":"pass","tests":10,"suite":"oag_execution_efficiency_check"}')
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
