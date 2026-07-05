#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any


GUARD_MARKER = "NATIVE CODEX SUBAGENT GUARD"
PROMPT_KEYS = ("prompt", "user_prompt", "userPrompt", "message", "content", "input")
SUBAGENT_REQUEST_RE = re.compile(
    r"(?<![A-Za-z0-9_-])("
    r"sub\s*agent|subagent|sub-agent|"
    r"spawn[_\s-]*agent|"
    r"close[_\s-]*agent|"
    r"wait[_\s-]*agent|"
    r"multi[_\s-]*agent(?:_v1)?|"
    r"parallel\s+agents?|"
    r"agent\s+cleanup|cleanup\s+agents?|stale\s+agents?|"
    r"agent\s+per|"
    r"서브\s*에이전트"
    r")(?![A-Za-z0-9_-])",
    re.IGNORECASE,
)


def first_text(payload: Any) -> str:
    if isinstance(payload, dict):
        for key in PROMPT_KEYS:
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value
        for value in payload.values():
            found = first_text(value)
            if found:
                return found
    if isinstance(payload, list):
        for value in payload:
            found = first_text(value)
            if found:
                return found
    return ""


def read_payload() -> dict[str, Any]:
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


def hook_additional_context(text: str) -> dict[str, Any]:
    return {"hookSpecificOutput": {"hookEventName": "UserPromptSubmit", "additionalContext": text}}


def transcript_already_has_guard(payload: dict[str, Any]) -> bool:
    transcript_path = str(payload.get("transcript_path") or "").strip()
    if not transcript_path:
        return False
    try:
        raw = Path(transcript_path).read_bytes()
    except Exception:
        return False
    tail = raw[-512_000:].decode("utf-8", errors="ignore")
    for line in tail.splitlines():
        try:
            item = json.loads(line)
        except Exception:
            continue
        if not isinstance(item, dict):
            continue
        hook_output = item.get("hookSpecificOutput")
        if not isinstance(hook_output, dict):
            continue
        context = hook_output.get("additionalContext")
        if isinstance(context, str) and GUARD_MARKER in context:
            return True
    return False


def guard_text() -> str:
    return "\n".join(
        [
            GUARD_MARKER,
            "",
            "The user requested subagent or parallel-agent work. Use native Codex subagents only.",
            "Use `multi_agent_v1.spawn_agent` where the current surface exposes it, or the equivalent Codex CLI/App native `spawn_agent` collaboration event.",
            "Do not treat missing direct `multi_agent_v1` namespace visibility as failure; Codex CLI/App may expose native spawning only as an internal `spawn_agent` collaboration event.",
            "Do not decide native-spawn availability from the visible callable tool namespace alone.",
            "For Codex CLI/App probes, explicitly request the native `spawn_agent` collaboration event even when no `multi_agent_v1` tool namespace is visible.",
            "For a subagent capability probe, first attempt a minimal read-only native spawn, wait for the child, and then report the result.",
            "For long RTL/TB work, do not treat one wait timeout or missing mailbox update as failure. A wait timeout only means no new child update arrived.",
            "Keep long children alive through repeated native waits and targeted follow-up. Only abandon a child when it is completed without the deliverable, explicitly `BLOCKED:`, no longer running, or inconclusive after multiple wait cycles with a recorded parent rationale.",
            "For long write-capable RTL/TB children, put a heartbeat contract in the spawn prompt: `WORKING:` within the first wait cycle and at each major phase, plus `python3 .codex/scripts/oag_wavefront.py heartbeat --ip-dir <ip> --run-id <run> --task-id <task> --message \"<phase>\" --json` when wavefront-backed, or an owned draft file, receipt, or `BLOCKED:` reason.",
            "Never put `close_agent`, wait cleanup, or stale-agent cleanup in a parallel batch with status checks, dispatch planning, receipt review, RTL/TB work, or any critical-path operation.",
            "Do not make child-thread closedness a progress gate. Use OAG dispatch, ownership lock, wavefront task status, receipts, and reviewer decisions as the gates.",
            "After a child receipt is integrated, rejected, or routed to `INCONCLUSIVE`/`BLOCKED`/`FAIL`, defer cleanup. If cleanup is needed, run one standalone bounded cleanup call after the OAG state transition is recorded.",
            "If stale completed children have no deliverable receipt, record the wavefront task outcome from available evidence and start a fresh dispatch from the current baseline; do not mass-close stale children to unblock new work.",
            "When an OAG wavefront reports two or more dependency-ready non-conflicting tasks, spawn the whole ready wave as a native subagent batch; do not serialize it unless dependency, ownership, or runtime budget blocks it.",
            "Treat large write-capable TB scenario shards as a runtime-budget blocker by default: open one or two children first, require early heartbeat or owned-path evidence, then open the next scenario shard.",
            "If a claimed task has no heartbeat, owned file, or receipt after a bounded status request, route the existing dispatch to `INCONCLUSIVE`/`BLOCKED` before any replacement; never start a replacement under the active lock.",
            "TB generation should be sharded into common API, scoreboard/schema, scenario groups, and integration review so each child has a bounded deliverable and can emit `WORKING:` heartbeats plus an OAG receipt.",
            "Do not answer BLOCKED or report an observed native-spawn blocker before an actual `spawn_agent` attempt fails or the runtime returns a spawn-unavailable error.",
            "Do not run `omo run --agent`, `./.codex/bin/omo run`, Python scripts, shell wrappers, or manual explorer-style role-play as a substitute.",
            "Do not try to lazy-load native subagent tools through tool search or MCP; native subagents are a Codex runtime collaboration capability.",
            "Only if an actual native spawn attempt fails or the active Codex runtime reports that spawning is unavailable, stop and report the observed native-spawn blocker.",
            "Continue with a non-native fallback only if the user explicitly waives the native-subagent requirement.",
        ]
    )


def main() -> int:
    payload = read_payload()
    prompt = first_text(payload)
    if not SUBAGENT_REQUEST_RE.search(prompt):
        return 0
    if transcript_already_has_guard(payload):
        return 0
    print(json.dumps(hook_additional_context(guard_text()), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
