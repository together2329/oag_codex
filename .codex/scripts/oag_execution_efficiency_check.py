#!/usr/bin/env python3
"""Validate an OAG cost report against bounded-execution efficiency rules."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any


PROCESS_REVIEW_MARKERS = ("review", "repair", "prelock", "audit", "canonical", "inspect", "triage")


def token_total(session: dict[str, Any]) -> int:
    tokens = session.get("tokens") if isinstance(session.get("tokens"), dict) else {}
    return int(tokens.get("input_tokens") or 0) + int(tokens.get("output_tokens") or 0)


def identity(session: dict[str, Any]) -> str:
    return str(
        session.get("task_id")
        or session.get("dispatch_id")
        or session.get("agent_path")
        or session.get("role_name")
        or session.get("agent_type")
        or session.get("conversation_id")
        or "unattributed"
    )


def issue(code: str, message: str, path: str = "") -> dict[str, str]:
    value = {"code": code, "message": message}
    if path:
        value["path"] = path
    return value


def check_report(
    report: dict[str, Any],
    *,
    root_share_max: float = 0.15,
    process_review_share_max: float = 0.25,
    single_agent_share_max: float = 0.05,
    ratio_gate_min_sessions: int = 5,
) -> dict[str, Any]:
    sessions = [item for item in report.get("sessions", []) if isinstance(item, dict) and token_total(item) > 0]
    total = sum(token_total(item) for item in sessions)
    issues: list[dict[str, str]] = []

    for item in sessions:
        maximum = int(item.get("max_total_tokens") or 0)
        if maximum and token_total(item) > maximum:
            issues.append(issue("EFF-BUDGET-001", f"execution exceeded token budget: {token_total(item)} > {maximum}", identity(item)))

    review_fingerprints: dict[str, list[str]] = defaultdict(list)
    for item in sessions:
        label = " ".join(str(item.get(key) or "") for key in ("task_id", "role_name", "agent_type")).lower()
        fingerprint = str(item.get("review_target_fingerprint") or item.get("content_fingerprint") or "")
        if "review" in label and fingerprint:
            review_fingerprints[fingerprint].append(identity(item))
    for fingerprint, reviews in sorted(review_fingerprints.items()):
        if len(reviews) > 1:
            issues.append(issue("EFF-REVIEW-001", f"unchanged content was reviewed {len(reviews)} times: {', '.join(reviews)}", fingerprint))

    metrics = {
        "accounting_sessions": len(sessions),
        "total_tokens": total,
        "root_token_share": None,
        "process_review_token_share": None,
        "largest_agent_token_share": None,
    }
    if total and len(sessions) >= ratio_gate_min_sessions:
        root_tokens = sum(
            token_total(item)
            for item in sessions
            if str(item.get("execution_kind") or "") == "main"
            or (not item.get("parent_session_id") and not item.get("agent_path"))
        )
        process_tokens = sum(
            token_total(item)
            for item in sessions
            if any(marker in identity(item).lower() for marker in PROCESS_REVIEW_MARKERS)
        )
        largest_tokens = max(token_total(item) for item in sessions)
        metrics.update(
            {
                "root_token_share": root_tokens / total,
                "process_review_token_share": process_tokens / total,
                "largest_agent_token_share": largest_tokens / total,
            }
        )
        if root_tokens / total > root_share_max:
            issues.append(issue("EFF-ROOT-001", f"root token share exceeds {root_share_max:.0%}: {root_tokens / total:.2%}"))
        if process_tokens / total > process_review_share_max:
            issues.append(issue("EFF-PROCESS-001", f"process/review token share exceeds {process_review_share_max:.0%}: {process_tokens / total:.2%}"))
        if largest_tokens / total > single_agent_share_max:
            issues.append(issue("EFF-AGENT-001", f"largest agent token share exceeds {single_agent_share_max:.0%}: {largest_tokens / total:.2%}"))

    return {
        "schema_version": "oag_execution_efficiency_check.v1",
        "status": "pass" if not issues else "fail",
        "metrics": metrics,
        "issues": issues,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", required=True)
    parser.add_argument("--root-share-max", type=float, default=0.15)
    parser.add_argument("--process-review-share-max", type=float, default=0.25)
    parser.add_argument("--single-agent-share-max", type=float, default=0.05)
    parser.add_argument("--ratio-gate-min-sessions", type=int, default=5)
    parser.add_argument("--advisory", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    report = json.loads(Path(args.report).read_text(encoding="utf-8"))
    result = check_report(
        report,
        root_share_max=args.root_share_max,
        process_review_share_max=args.process_review_share_max,
        single_agent_share_max=args.single_agent_share_max,
        ratio_gate_min_sessions=args.ratio_gate_min_sessions,
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["status"] == "pass" or args.advisory else 1


if __name__ == "__main__":
    raise SystemExit(main())
