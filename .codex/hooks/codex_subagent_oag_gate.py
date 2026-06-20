#!/usr/bin/env python3
"""Codex SubagentStop hook for OAG evidence-producing subagents.

This hook does not spawn subagents. Codex does that through
multi_agent_v1.spawn_agent. The hook only checks that evidence-producing OAG
subagents end with a durable receipt line:

  OAG_EVIDENCE_RECORDED: <relative-path>

The path must point to a non-empty file inside either:
  - <ip>/knowledge/subagents/
  - knowledge/subagents/
  - .codex/oag/subagent-receipts/
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CACHE_PATH = Path(os.environ.get("OAG_SUBAGENT_GATE_CACHE") or ROOT / ".cache" / "subagent_oag_gate.json")
MAX_ATTEMPTS = 3
RECEIPT_RE = re.compile(r"OAG_EVIDENCE_RECORDED:\s*(\S+)")
CONTEXT_PRESSURE_MARKERS = (
    "context compacted",
    "context_length_exceeded",
    "skill descriptions were shortened",
    "context_too_large",
    "codex ran out of room in the model's context window",
    "your input exceeds the context window",
    "long threads and multiple compactions",
)


def read_payload() -> dict:
    try:
        raw = sys.stdin.read()
    except Exception:
        return {}
    if not raw.strip():
        return {}
    try:
        payload = json.loads(raw)
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def read_cache() -> dict:
    try:
        payload = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {"schema_version": "oag_subagent_gate_cache.v1", "entries": {}}
    return payload if isinstance(payload, dict) else {"schema_version": "oag_subagent_gate_cache.v1", "entries": {}}


def write_cache(cache: dict) -> None:
    try:
        CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        tmp = CACHE_PATH.with_suffix(f".{os.getpid()}.tmp")
        tmp.write_text(json.dumps(cache, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        tmp.replace(CACHE_PATH)
    except Exception:
        return


def cache_key(payload: dict) -> str:
    parts = [
        str(payload.get("cwd") or ""),
        str(payload.get("session_id") or ""),
        str(payload.get("agent_id") or ""),
        str(payload.get("agent_type") or ""),
    ]
    return hashlib.sha256("::".join(parts).encode("utf-8")).hexdigest()


def attempt_allowed(payload: dict) -> bool:
    cache = read_cache()
    entries = cache.setdefault("entries", {})
    if not isinstance(entries, dict):
        cache["entries"] = entries = {}
    key = cache_key(payload)
    entry = entries.get(key)
    if not isinstance(entry, dict):
        entry = {"attempts": 0}
        entries[key] = entry
    attempts = int(entry.get("attempts") or 0) + 1
    entry["attempts"] = attempts
    entry["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    write_cache(cache)
    return attempts <= MAX_ATTEMPTS


def clear_attempt(payload: dict) -> None:
    cache = read_cache()
    entries = cache.get("entries")
    if isinstance(entries, dict):
        entries.pop(cache_key(payload), None)
        write_cache(cache)


def transcript_has_context_pressure(path: str) -> bool:
    try:
        text = Path(path).read_text(encoding="utf-8", errors="ignore").lower()
    except Exception:
        return False
    return any(marker in text for marker in CONTEXT_PRESSURE_MARKERS)


def is_allowed_receipt_path(base: Path, receipt: Path) -> bool:
    try:
        relative = receipt.resolve().relative_to(base.resolve())
    except ValueError:
        return False
    parts = relative.parts
    if len(parts) >= 2 and parts[0] == "knowledge" and parts[1] == "subagents":
        return True
    if len(parts) >= 3 and parts[1] == "knowledge" and parts[2] == "subagents":
        return True
    if len(parts) >= 4 and parts[0] == ".codex" and parts[1] == "oag" and parts[2] == "subagent-receipts":
        return True
    return False


def valid_receipt(payload: dict) -> bool:
    message = str(payload.get("last_assistant_message") or "")
    match = RECEIPT_RE.search(message)
    if not match:
        return False
    raw_path = match.group(1)
    if not raw_path or Path(raw_path).is_absolute():
        return False
    cwd = Path(str(payload.get("cwd") or ".")).expanduser().resolve()
    receipt = (cwd / raw_path).resolve()
    if not is_allowed_receipt_path(cwd, receipt):
        return False
    try:
        if receipt.is_symlink() or not receipt.is_file() or receipt.stat().st_size <= 0:
            return False
    except Exception:
        return False
    return True


def directive(payload: dict) -> str:
    agent_type = payload.get("agent_type") or "oag-subagent"
    return (
        f"{agent_type} stopped without a valid OAG evidence receipt.\n\n"
        "Before stopping, write a non-empty receipt JSON/Markdown file under one of:\n"
        "- <ip>/knowledge/subagents/\n"
        "- knowledge/subagents/\n"
        "- .codex/oag/subagent-receipts/\n\n"
        "Then make the final line exactly:\n"
        "OAG_EVIDENCE_RECORDED: <relative-path>\n\n"
        "The receipt must name the shard scope, checked/changed paths, commands or artifacts, "
        "ROCEV links, blockers, and whether the result is PASS, FAIL, or INCONCLUSIVE. "
        "Do not claim final completion."
    )


def main() -> int:
    payload = read_payload()
    if payload.get("hook_event_name") != "SubagentStop":
        return 0
    if not str(payload.get("agent_type") or "").startswith("oag-"):
        return 0
    if transcript_has_context_pressure(str(payload.get("transcript_path") or "")):
        return 0
    if valid_receipt(payload):
        clear_attempt(payload)
        return 0
    if attempt_allowed(payload):
        print(json.dumps({"decision": "block", "reason": directive(payload)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
