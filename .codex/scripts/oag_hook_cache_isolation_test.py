#!/usr/bin/env python3
"""Focused cross-session and evaluator isolation regressions for OAG hooks."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


SCRIPTS = Path(__file__).resolve().parent
CODEX_ROOT = SCRIPTS.parent
CONTEXT_HOOK = CODEX_ROOT / "hooks" / "codex_context_inject.py"
STOP_HOOK = CODEX_ROOT / "hooks" / "codex_stop_gate.py"

if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import smoke_test  # noqa: E402


def hook_env(cache_dir: Path, **overrides: str) -> dict[str, str]:
    env = {
        key: value
        for key, value in os.environ.items()
        if key not in {"OAG_CONTEXT_INJECT_CACHE", "OAG_STOP_GATE_CACHE", "OAG_IP_DIR", "OAG_RUN_ID"}
    }
    env.update({"OAG_DISABLE_BACKEND": "1", "OAG_HOOK_CACHE_DIR": str(cache_dir)})
    env.update(overrides)
    return env


def run_hook(script: Path, payload: dict[str, Any], env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(script)],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        check=False,
        cwd=str(CODEX_ROOT.parent),
        env=env,
    )


def payload(session_id: str, cwd: Path, **values: Any) -> dict[str, Any]:
    return {"session_id": session_id, "cwd": str(cwd), **values}


def assert_blocked_for(proc: subprocess.CompletedProcess[str], ip: Path) -> None:
    assert proc.returncode == 0, proc.stderr
    body = json.loads(proc.stdout)
    assert body.get("decision") == "block", body
    reason = str(body.get("reason") or "")
    assert ip.name in reason and str(ip.resolve()) in reason, reason


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="oag-hook-cache-isolation-") as temp:
        root = Path(temp)
        shared_cache = root / "shared-cache"
        eval_cache = root / "eval-cache"
        live_cache = root / "live-cache"
        eval_workspace = root / "eval-workspace"
        live_workspace = root / "live-workspace"
        eval_workspace.mkdir()
        live_workspace.mkdir()
        foreign_ip = smoke_test.make_ip(eval_workspace / "foreign_eval_ip")
        live_ip = smoke_test.make_ip(live_workspace / "live_ip")

        sentinel = live_cache / "sentinel.txt"
        sentinel.parent.mkdir(parents=True)
        sentinel.write_text("live-cache-must-not-change\n", encoding="utf-8")
        eval_context = run_hook(
            CONTEXT_HOOK,
            payload(
                "eval-session",
                eval_workspace,
                hook_event_name="UserPromptSubmit",
                ip_dir=str(foreign_ip),
                stage="rtl",
                prompt="oag continue rtl evaluation",
            ),
            hook_env(eval_cache),
        )
        assert eval_context.returncode == 0 and "OAG CONTEXT INJECTION" in eval_context.stdout, eval_context.stderr or eval_context.stdout
        live_stop = run_hook(STOP_HOOK, payload("live-session", live_workspace, hook_event_name="Stop"), hook_env(live_cache))
        assert live_stop.returncode == 0 and live_stop.stdout == "", live_stop.stdout + live_stop.stderr
        assert sentinel.read_text(encoding="utf-8") == "live-cache-must-not-change\n"

        same_workspace_a = run_hook(
            CONTEXT_HOOK,
            payload(
                "session-a",
                eval_workspace,
                hook_event_name="UserPromptSubmit",
                ip_dir=str(foreign_ip),
                prompt="oag continue rtl",
            ),
            hook_env(shared_cache),
        )
        assert same_workspace_a.returncode == 0 and same_workspace_a.stdout, same_workspace_a.stderr
        same_workspace_b = run_hook(STOP_HOOK, payload("session-b", eval_workspace, hook_event_name="Stop"), hook_env(shared_cache))
        assert same_workspace_b.returncode == 0 and same_workspace_b.stdout == "", same_workspace_b.stdout + same_workspace_b.stderr

        missing_session = run_hook(
            STOP_HOOK,
            {"cwd": str(eval_workspace), "hook_event_name": "Stop"},
            hook_env(shared_cache),
        )
        assert missing_session.returncode == 0 and missing_session.stdout == "", missing_session.stdout + missing_session.stderr

        same_session_stop = run_hook(
            STOP_HOOK,
            payload("session-a", eval_workspace, hook_event_name="Stop"),
            hook_env(shared_cache),
        )
        assert_blocked_for(same_session_stop, foreign_ip)

        explicit_stop = run_hook(
            STOP_HOOK,
            payload("session-a", eval_workspace, hook_event_name="Stop", ip_dir=str(live_ip)),
            hook_env(shared_cache),
        )
        assert_blocked_for(explicit_stop, live_ip)
        assert str(foreign_ip.resolve()) not in explicit_stop.stdout, explicit_stop.stdout

        relative_stop = run_hook(
            STOP_HOOK,
            payload(
                "relative-session",
                eval_workspace,
                hook_event_name="Stop",
                ip_dir=str(foreign_ip.relative_to(eval_workspace)),
            ),
            hook_env(shared_cache),
        )
        assert_blocked_for(relative_stop, foreign_ip)

        environment_stop = run_hook(
            STOP_HOOK,
            payload("environment-session", live_workspace, hook_event_name="Stop"),
            hook_env(shared_cache, OAG_IP_DIR=str(live_ip)),
        )
        assert_blocked_for(environment_stop, live_ip)

        cwd_ip_stop = run_hook(
            STOP_HOOK,
            payload("cwd-ip-session", foreign_ip, hook_event_name="Stop"),
            hook_env(shared_cache),
        )
        assert_blocked_for(cwd_ip_stop, foreign_ip)

        legacy_cache = root / "legacy-context.json"
        legacy_cache.write_text(
            json.dumps(
                {
                    "schema_version": "oag_context_inject_cache.v1",
                    "entries": {},
                    "last_target": {"ip_dir": str(foreign_ip)},
                }
            )
            + "\n",
            encoding="utf-8",
        )
        legacy_stop = run_hook(
            STOP_HOOK,
            payload("legacy-session", live_workspace, hook_event_name="Stop"),
            hook_env(shared_cache, OAG_CONTEXT_INJECT_CACHE=str(legacy_cache)),
        )
        assert legacy_stop.returncode == 0 and legacy_stop.stdout == "", legacy_stop.stdout + legacy_stop.stderr

        recovery_cache = root / "recovery-cache"
        recovery_payload = payload(
            "recovery-session",
            eval_workspace,
            hook_event_name="UserPromptSubmit",
            ip_dir=str(foreign_ip),
            prompt="oag continue rtl",
        )
        first = run_hook(CONTEXT_HOOK, recovery_payload, hook_env(recovery_cache))
        duplicate = run_hook(CONTEXT_HOOK, recovery_payload, hook_env(recovery_cache))
        post_compact = run_hook(
            CONTEXT_HOOK,
            payload("recovery-session", eval_workspace, hook_event_name="PostCompact"),
            hook_env(recovery_cache),
        )
        recovered = run_hook(CONTEXT_HOOK, recovery_payload, hook_env(recovery_cache))
        assert first.stdout and duplicate.stdout == "" and post_compact.stdout == "" and recovered.stdout, (
            first.stdout,
            duplicate.stdout,
            post_compact.stdout,
            recovered.stdout,
        )

    print(json.dumps({"ok": True, "suite": "oag_hook_cache_isolation"}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
