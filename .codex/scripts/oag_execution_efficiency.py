#!/usr/bin/env python3
"""Deterministic execution budgets and compact-context contracts for OAG work."""

from __future__ import annotations

from typing import Any


BUDGET_PROFILES = {
    "simple": {"max_total_tokens": 5_000_000, "max_direct_source_files": 8},
    "medium": {"max_total_tokens": 10_000_000, "max_direct_source_files": 16},
    "complex": {"max_total_tokens": 20_000_000, "max_direct_source_files": 24},
}


def infer_complexity(agent_type: str, stage: str) -> str:
    value = f"{agent_type} {stage}".lower()
    if any(word in value for word in ("rtl", "tb", "formal", "architecture", "sim-debug", "debug")):
        return "complex"
    if any(word in value for word in ("lint", "manifest", "report", "evidence", "coverage", "gate")):
        return "simple"
    return "medium"


def infer_model_tier(agent_type: str, stage: str) -> str:
    value = f"{agent_type} {stage}".lower()
    if any(word in value for word in ("rtl", "architecture", "formal", "debug", "contract")):
        return "reasoning"
    if any(word in value for word in ("lint", "manifest", "report", "evidence", "coverage")):
        return "mechanical"
    return "balanced"


def build_execution_controls(
    *,
    agent_type: str,
    stage: str,
    complexity: str = "",
    max_total_tokens: int = 0,
    max_review_attempts: int = 1,
    model_tier: str = "",
) -> tuple[dict[str, Any], dict[str, Any]]:
    profile = complexity or infer_complexity(agent_type, stage)
    if profile not in BUDGET_PROFILES:
        raise ValueError(f"invalid execution complexity: {profile}")
    default = BUDGET_PROFILES[profile]
    token_limit = max_total_tokens or int(default["max_total_tokens"])
    if token_limit < 100_000 or token_limit > 25_000_000:
        raise ValueError("max_total_tokens must be between 100000 and 25000000")
    if max_review_attempts < 0 or max_review_attempts > 2:
        raise ValueError("max_review_attempts must be between 0 and 2")
    tier = model_tier or infer_model_tier(agent_type, stage)
    if tier not in {"mechanical", "balanced", "reasoning"}:
        raise ValueError(f"invalid model tier: {tier}")

    budget = {
        "schema_version": "oag_execution_budget.v1",
        "complexity": profile,
        "max_total_tokens": token_limit,
        "warning_total_tokens": token_limit * 4 // 5,
        "max_review_attempts": max_review_attempts,
        "over_budget_action": "stop_and_replan",
        "model_tier": tier,
    }
    context = {
        "schema_version": "oag_context_contract.v1",
        "fork_turns": "none",
        "input_mode": "authoring_packet_or_explicit_file_list",
        "max_direct_source_files": int(default["max_direct_source_files"]),
        "require_source_hashes": True,
        "repeat_review_policy": "content_hash_delta_only",
    }
    return budget, context
