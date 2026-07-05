#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
from typing import Any


DEEP_INTERVIEW_MARKER = "OAG DEEP INTERVIEW PROMPT GUARD"
PROMPT_KEYS = ("prompt", "user_prompt", "userPrompt", "message", "content", "input")
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


def _first_text(payload: Any) -> str:
    if isinstance(payload, dict):
        for key in PROMPT_KEYS:
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value
        for value in payload.values():
            found = _first_text(value)
            if found:
                return found
    if isinstance(payload, list):
        for value in payload:
            found = _first_text(value)
            if found:
                return found
    return ""


def _read_payload() -> dict[str, Any]:
    try:
        raw = os.read(0, 1_000_000).decode("utf-8")
    except OSError:
        return {}
    if not raw.strip():
        return {}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _hook_additional_context(text: str) -> dict[str, Any]:
    return {"hookSpecificOutput": {"hookEventName": "UserPromptSubmit", "additionalContext": text}}


def _already_recently_injected(text: str) -> bool:
    if not text:
        return False
    return DEEP_INTERVIEW_MARKER in text[-32_000:]


def _should_inject(payload: dict[str, Any]) -> bool:
    prompt = _first_text(payload)
    if not prompt.strip():
        return False
    if _already_recently_injected(prompt):
        return False
    return bool(DIRECT_TRIGGER_RE.search(prompt))


def _guard_text() -> str:
    return "\n".join(
        [
            f"=== {DEEP_INTERVIEW_MARKER} ===",
            "For an OAG deep-interview round:",
            "- Ask exactly one user-facing question: the highest-impact ambiguity right now.",
            "- Rank candidates by lock blocker, SSOT required gap, downstream fanout, ambiguity gap, proof gap, user value, and lower researchable-fact score.",
            "- If documents/specs/RTL are provided, extract facts from them first; ask only unresolved intent, conflicts, or missing boundaries.",
            "- Provide four concise candidate answers; mark exactly one `(Recommended)` when facts support it.",
            "- All options must answer the same question; do not bundle protocol, firmware, verification, and integration questions.",
            "- Include `Other / refine` and say the user can type a custom answer directly if A-D do not fit.",
            "- Continue until the scope is concrete enough for RTL/TB authoring packets: trigger, condition, response, timing, interface, reset/state, error policy, and proof.",
            "- If no native popup/ask UI is available, render the single question and options in chat.",
            "- Treat recommendations as draft guidance; implementation-affecting choices still go through the decision matrix.",
            f"=== END {DEEP_INTERVIEW_MARKER} ===",
        ]
    )


def main() -> int:
    payload = _read_payload()
    if _should_inject(payload):
        print(json.dumps(_hook_additional_context(_guard_text()), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
