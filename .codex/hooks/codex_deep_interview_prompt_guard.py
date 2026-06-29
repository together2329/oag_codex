#!/usr/bin/env python3
"""Codex UserPromptSubmit hook: keep OAG deep interviews to one question.

The hook is intentionally small and fail-open. It runs on every prompt through
hooks.json, but emits additional context only when the prompt or recent
transcript indicates an OAG deep interview is active.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from oag_hook_utils import hook_additional_context, prompt_text, read_payload


DEEP_INTERVIEW_MARKER = "OAG DEEP INTERVIEW PROMPT GUARD"
DIRECT_TRIGGER_RE = re.compile(
    r"(?ix)"
    r"("
    r"\boag-deep-interview\b|"
    r"\bdeep[- ]interview\b|"
    r"딥\s*인터뷰|"
    r"요구사항\s*인터뷰|"
    r"인터뷰\s*스킬"
    r")"
)
CONTEXT_TRIGGER_RE = re.compile(
    r"(?ix)"
    r"("
    r"\boag\b|"
    r"\bIP\b|"
    r"\bhardware\b|"
    r"요구사항|"
    r"모호성|"
    r"스코프|"
    r"락|"
    r"decision\s*matrix"
    r")"
)
INTERVIEW_WORD_RE = re.compile(r"(?ix)(interview|인터뷰|ambiguity|ambiguous|모호|requirement|requirements|요구사항)")


def _transcript_tail(path: str, *, limit: int = 256_000) -> str:
    if not path:
        return ""
    try:
        raw = Path(path).read_bytes()
    except Exception:
        return ""
    return raw[-limit:].decode("utf-8", errors="ignore")


def _already_recently_injected(text: str) -> bool:
    if not text:
        return False
    # Avoid duplicating the guard inside the same hook payload/transcript tail.
    return DEEP_INTERVIEW_MARKER in text[-32_000:]


def _recent_transcript_has_deep_interview(payload: dict[str, Any]) -> bool:
    tail = _transcript_tail(str(payload.get("transcript_path") or ""))
    if not tail or _already_recently_injected(tail):
        return False
    lowered = tail.lower()
    return (
        "oag-deep-interview" in lowered
        or "oag deep interview" in lowered
        or "deep interview threshold" in lowered
        or "round 0 | topology confirmation" in lowered
    )


def _should_inject(payload: dict[str, Any]) -> bool:
    prompt = prompt_text(payload)
    if not prompt.strip():
        return False
    if _already_recently_injected(prompt):
        return False
    if DIRECT_TRIGGER_RE.search(prompt):
        return True
    if INTERVIEW_WORD_RE.search(prompt) and CONTEXT_TRIGGER_RE.search(prompt):
        return True
    return _recent_transcript_has_deep_interview(payload)


def _guard_text() -> str:
    return "\n".join(
        [
            f"=== {DEEP_INTERVIEW_MARKER} ===",
            "For an OAG deep-interview round:",
            "- Ask exactly one user-facing question: the highest-impact ambiguity right now.",
            "- Rank candidates by lock blocker, SSOT required gap, downstream fanout, ambiguity gap, proof gap, user value, and lower researchable-fact score.",
            "- Provide four concise candidate answers; mark exactly one `(Recommended)` when facts support it.",
            "- All options must answer the same question; do not bundle protocol, firmware, verification, and integration questions.",
            "- Include `Other / refine` so the user can correct the framing.",
            "- If no native popup/ask UI is available, render the single question and options in chat.",
            "- Treat recommendations as draft guidance; implementation-affecting choices still go through the decision matrix.",
            f"=== END {DEEP_INTERVIEW_MARKER} ===",
        ]
    )


def main() -> int:
    payload = read_payload()
    if _should_inject(payload):
        print(json.dumps(hook_additional_context(_guard_text()), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
