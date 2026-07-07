#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any


GUARD_MARKER = "NATIVE CODEX SUBAGENT GUARD"
PROMPT_KEYS = ("prompt", "user_prompt", "userPrompt", "message", "content", "input")
MY_REQUEST_HEADER_RE = re.compile(r"(?im)^##\s*My request for Codex:\s*$")
SUBAGENT_REQUEST_RE = re.compile(
    r"(?<![A-Za-z0-9_-])("
    r"sub\s*agents?|subagents?|sub-agents?|"
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
SUBAGENT_COMMAND_RE = re.compile(
    r"("
    r"\b(use|run|spawn|start|launch|open|dispatch|assign|send|close|wait\s+for|"
    r"clean\s*up|cleanup|fan\s*out|parallelize|parallel)\b.{0,80}"
    r"(sub\s*agents?|subagents?|sub-agents?|spawn[_\s-]*agent|close[_\s-]*agent|"
    r"wait[_\s-]*agent|multi[_\s-]*agent(?:_v1)?|parallel\s+agents?)"
    r"|"
    r"(sub\s*agents?|subagents?|sub-agents?|multi[_\s-]*agent(?:_v1)?|parallel\s+agents?)"
    r".{0,80}\b(run|spawn|start|launch|dispatch|implement|review|test|verify)\b"
    r"|"
    r"(sub\s*agents?|subagents?|sub-agents?|서브\s*에이전트).{0,30}"
    r"(로|으로|에게|써|사용|실행|돌려|붙여|맡겨|열어|닫아)"
    r")",
    re.IGNORECASE | re.DOTALL,
)
SUBAGENT_META_DISCUSSION_RE = re.compile(
    r"("
    r"\b(why|what|how|explain|diagnose|debug|fix|reduce|too\s+many|excessive|"
    r"iteration|iterations|loop|loops|repeat|repeated|trigger|activate|enable|"
    r"guard|hook|policy|instruction|config|workflow|orchestration)\b"
    r"|왜|뭐|무엇|어떻게|설명|진단|디버그|고쳐|수정|줄여|너무|많|반복|자꾸|"
    r"트리거|활성|가드|훅|설정|정책|지침|워크플로|오케스트레이션"
    r")",
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


def effective_prompt_text(prompt: str) -> str:
    matches = list(MY_REQUEST_HEADER_RE.finditer(prompt or ""))
    if not matches:
        return prompt
    return prompt[matches[-1].end() :].strip()


def should_inject_guard(prompt: str) -> bool:
    prompt = effective_prompt_text(prompt)
    if not SUBAGENT_REQUEST_RE.search(prompt):
        return False
    if SUBAGENT_META_DISCUSSION_RE.search(prompt) and not SUBAGENT_COMMAND_RE.search(prompt):
        return False
    return True


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
            "Default long-work patience budget: keep an active child through at least three native wait cycles. After the first silent cycle, send at most one targeted status/heartbeat request, then continue waiting.",
            "Only abandon a child when it is completed without the deliverable, explicitly `BLOCKED:`, no longer running, or still has no `WORKING:`, heartbeat, owned-path evidence, receipt, or blocker after the full patience budget and a recorded parent rationale.",
            "For long write-capable RTL/TB children, put a heartbeat contract in the spawn prompt: `WORKING:` within the first wait cycle and at each major phase, plus `python3 .codex/scripts/oag_wavefront.py heartbeat --ip-dir <ip> --run-id <run> --task-id <task> --message \"<phase>\" --json` when wavefront-backed, or an owned draft file, receipt, or `BLOCKED:` reason.",
            "Never put `close_agent`, wait cleanup, or stale-agent cleanup in a parallel batch with status checks, dispatch planning, receipt review, RTL/TB work, or any critical-path operation.",
            "Do not make child-thread closedness a progress gate. Use OAG dispatch, ownership lock, wavefront task status, receipts, and reviewer decisions as the gates.",
            "After a child receipt is integrated, rejected, or routed to `INCONCLUSIVE`/`BLOCKED`/`FAIL`, defer cleanup. If cleanup is needed, run one standalone bounded cleanup call after the OAG state transition is recorded.",
            "If stale completed children have no deliverable receipt, record the wavefront task outcome from available evidence and start a fresh dispatch from the current baseline; do not mass-close stale children to unblock new work.",
            "If a child/thread stalls at `Starting MCP servers` and shows optional `computer-use`, treat that as runtime startup noise. Use `python3 .codex/scripts/oag_codex_config_doctor.py --include-omo-plugin-features --lean-subagent-runtime --apply` and open a fresh trusted session; do not make MCP startup or close cleanup an OAG progress gate.",
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
    if not should_inject_guard(prompt):
        return 0
    if transcript_already_has_guard(payload):
        return 0
    print(json.dumps(hook_additional_context(guard_text()), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
