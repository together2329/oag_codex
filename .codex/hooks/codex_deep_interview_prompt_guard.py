#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
from pathlib import Path
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
TRANSITION_TRIGGER_RE = re.compile(
    r"(?ix)"
    r"("
    r"\block\b|"
    r"\blocked\b|"
    r"\bimplement\b|"
    r"\bimplementation\b|"
    r"\bdispatch\b|"
    r"\bclosure\b|"
    r"\bsignoff\b|"
    r"락|"
    r"구현|"
    r"디스패치|"
    r"클로저|"
    r"사인오프"
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


def _ip_dir_from_payload(payload: dict[str, Any]) -> Path | None:
    for key in ("ip_dir", "ipDir", "target_ip_dir", "targetIpDir"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            path = Path(value).expanduser()
            if not path.is_absolute():
                path = Path(str(payload.get("cwd") or ".")).expanduser() / path
            return path.resolve()
    env_value = os.environ.get("OAG_IP_DIR")
    if env_value:
        return Path(env_value).expanduser().resolve()
    return None


def _yaml_doc(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        import yaml  # type: ignore

        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def _text(value: Any) -> str:
    return str(value or "").strip()


def _payload_has_lock_blocker(payload: dict[str, Any]) -> bool:
    for key in ("lock_readiness", "lockReadiness", "oag_lock_readiness"):
        value = payload.get(key)
        if not isinstance(value, dict):
            continue
        blockers = value.get("unresolved_lock_blockers")
        if isinstance(blockers, list) and any(_text(item) for item in blockers):
            return True
        counts = value.get("counts")
        if isinstance(counts, dict) and int(counts.get("unresolved_lock_blockers") or 0) > 0:
            return True
    return False


def _state_has_lock_blocker(ip_dir: Path) -> bool:
    def state_path(relative: str) -> Path:
        hidden = ip_dir / ".oag" / relative
        return hidden if hidden.exists() else ip_dir / relative

    decision_doc = _yaml_doc(state_path("ontology/decision_matrix.yaml"))
    for decision in _as_list(decision_doc.get("decisions")):
        if not isinstance(decision, dict):
            continue
        if decision.get("lock_required") is True and _text(decision.get("status")).lower() not in {"decided", "waived"}:
            return True

    ambiguity_doc = _yaml_doc(state_path("req/ambiguity_register.yaml"))
    for row in _as_list(ambiguity_doc.get("ambiguities") or ambiguity_doc.get("items")):
        if not isinstance(row, dict):
            continue
        lock_required = row.get("lock_required") is True or row.get("lock_blocker") is True
        status = _text(row.get("status")).lower()
        if lock_required and status not in {"resolved", "waived", "closed"}:
            return True
    return False


def _should_state_trigger(payload: dict[str, Any], prompt: str) -> bool:
    if not TRANSITION_TRIGGER_RE.search(prompt):
        return False
    if _payload_has_lock_blocker(payload):
        return True
    ip_dir = _ip_dir_from_payload(payload)
    return bool(ip_dir and _state_has_lock_blocker(ip_dir))


def _should_inject(payload: dict[str, Any]) -> bool:
    prompt = _first_text(payload)
    if not prompt.strip():
        return False
    if _already_recently_injected(prompt):
        return False
    return bool(DIRECT_TRIGGER_RE.search(prompt) or _should_state_trigger(payload, prompt))


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
