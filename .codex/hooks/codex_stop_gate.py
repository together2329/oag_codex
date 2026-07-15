#!/usr/bin/env python3
"""Codex Stop hook: block incomplete OAG runs and main-agent locked writes.

Output contract (Codex Stop hook):
  - print {"decision": "block", "reason": "<next-action prompt>"} on stdout to block the stop
  - exit 0 ALWAYS (a hook must never break the turn)

Target resolution order:
  1. hook stdin payload: {"ip_dir": "...", "run_id": "..."}
  2. environment: OAG_IP_DIR / OAG_RUN_ID
  3. fallback scan: <project>/*/ontology/runs/active_run.json

For each target it calls oag.stop_check. If a run wants to continue, it blocks
the stop with that run's prompt block. It also runs the main-write gate: after
scope lock, RTL/TB/sim/lint/coverage/formal/SDC/signoff/filelist writes require
native OAG subagent dispatch + receipt or a human waiver. Human-decision states
stay silent because the agent has no further local action to take. Repeated
identical failures remain blocked; the durable cache records retry exhaustion
without turning a failed gate into permission to stop.

This is the Codex-hook-shaped sibling of scripts-driven oag.stop_check; the older
hooks/oag_stop_check.py stays as a manual/example runner.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from pathlib import Path

sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parents[1]  # .codex/
sys.path.insert(0, str(ROOT / "scripts"))
INACTIVE_RUN_STATUSES = {"complete", "parked", "needs_human"}

import oag_cli  # noqa: E402
import oag_main_write_gate  # noqa: E402
from oag_hook_utils import (  # noqa: E402
    active_run_ips,
    cache_file_lock,
    has_oag_work_signal,
    hook_cache_path,
    hook_identity,
    identity_matches,
    invocation_cwd,
    is_ip_dir,
    path_under,
    project_path,
    prompt_text,
    state_path,
)


def _default_cache(identity: dict[str, str]) -> dict:
    return {"schema_version": "oag_stop_gate_cache.v2", "identity": identity, "entries": {}}


def _read_cache(path: Path, identity: dict[str, str]) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return _default_cache(identity)
    if not isinstance(data, dict) or data.get("schema_version") != "oag_stop_gate_cache.v2":
        return _default_cache(identity)
    if not identity_matches(data.get("identity"), identity):
        return _default_cache(identity)
    data["identity"] = identity
    return data


def _write_cache(path: Path, cache: dict) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(f".{os.getpid()}.tmp")
        tmp.write_text(json.dumps(cache, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        tmp.replace(path)
    except Exception:
        return


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _safe_int(value: object, default: int) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _max_block_repeats(result: dict) -> int:
    if os.environ.get("OAG_STOP_GATE_MAX_BLOCK_REPEATS") is not None:
        return max(_safe_int(os.environ.get("OAG_STOP_GATE_MAX_BLOCK_REPEATS"), 3), 0)
    policy = result.get("policy") if isinstance(result.get("policy"), dict) else {}
    if "stop_hook_max_repeats" in policy:
        return max(_safe_int(policy.get("stop_hook_max_repeats"), 3), 0)
    return 3


def _block_allowed(cache: dict, *, key: str, digest: str, max_repeats: int) -> bool:
    max_repeats = max(max_repeats, 1)
    entries = cache.setdefault("entries", {})
    if not isinstance(entries, dict):
        cache["entries"] = entries = {}
    entry = entries.get(key)
    if not isinstance(entry, dict) or entry.get("digest") != digest:
        entries[key] = {
            "digest": digest,
            "count": 1,
            "retry_exhausted": False,
            "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
        return True
    count = int(entry.get("count") or 0) + 1
    entry["count"] = count
    entry["retry_exhausted"] = count > max_repeats
    entry["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    return True


def _read_payload() -> dict:
    try:
        raw = sys.stdin.read()
    except Exception:
        return {}
    if not raw.strip():
        return {}
    try:
        data = json.loads(raw)
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _selected_target(ip_dir: Path, run_id: str, source: str) -> dict[str, str]:
    return {"ip_dir": str(ip_dir.resolve()), "run_id": run_id, "source": source}


def _active_run_id(ip_dir: Path) -> str:
    active = state_path(ip_dir, "ontology/runs/active_run.json")
    if not active.is_file():
        return ""
    try:
        data = json.loads(active.read_text(encoding="utf-8"))
    except Exception:
        return ""
    if not isinstance(data, dict) or str(data.get("status") or "") in INACTIVE_RUN_STATUSES:
        return ""
    return str(data.get("run_id") or "")


def _session_context_target(payload: dict, identity: dict[str, str]) -> list[dict[str, str]]:
    if not identity["session_id"]:
        return []
    cache_path = hook_cache_path(payload, hook_name="context_inject", exact_env="OAG_CONTEXT_INJECT_CACHE")
    try:
        with cache_file_lock(cache_path):
            data = json.loads(cache_path.read_text(encoding="utf-8"))
    except Exception:
        return []
    if not isinstance(data, dict) or data.get("schema_version") != "oag_context_inject_cache.v2":
        return []
    if not identity_matches(data.get("identity"), identity):
        return []
    target = data.get("last_target")
    if not isinstance(target, dict):
        return []
    if any(str(target.get(key) or "") != identity[key] for key in ("session_key", "workspace_key", "workspace_root")):
        return []
    source = str(target.get("target_source") or "")
    if source not in {"payload", "environment", "prompt", "workspace_cwd", "workspace_scan"}:
        return []
    raw_ip = str(target.get("ip_dir") or "").strip()
    if not raw_ip:
        return []
    ip_dir = Path(raw_ip).expanduser().resolve()
    if not is_ip_dir(ip_dir):
        return []
    if source not in {"payload", "environment"} and not path_under(ip_dir, Path(identity["workspace_root"])):
        return []
    return [_selected_target(ip_dir, "", "session_context")]


def _target_runs(payload: dict, identity: dict[str, str]) -> list[dict[str, str]]:
    payload_ip = str(payload.get("ip_dir") or "").strip()
    env_ip = os.environ.get("OAG_IP_DIR", "").strip()
    payload_run = str(payload.get("run_id") or "").strip()
    env_run = os.environ.get("OAG_RUN_ID", "").strip()
    run_id = payload_run or env_run

    explicit_ip = payload_ip or env_ip
    if explicit_ip:
        ip_dir = project_path(explicit_ip, base=invocation_cwd(payload))
        return [_selected_target(ip_dir, run_id, "payload" if payload_ip else "environment")]

    context_targets = _session_context_target(payload, identity)
    if context_targets:
        context_targets[0]["run_id"] = run_id or _active_run_id(Path(context_targets[0]["ip_dir"]))
        return context_targets

    cwd = Path(identity["cwd"])
    if is_ip_dir(cwd):
        return [_selected_target(cwd, run_id or _active_run_id(cwd), "workspace_cwd")]

    workspace = Path(identity["workspace_root"])
    active = active_run_ips(workspace)
    if run_id:
        matches = [ip for ip in active if _active_run_id(ip) == run_id]
        return [_selected_target(matches[0], run_id, "workspace_scan")] if len(matches) == 1 else []
    if has_oag_work_signal(prompt_text(payload)) and len(active) == 1 and identity["session_id"]:
        return [_selected_target(active[0], _active_run_id(active[0]), "workspace_scan")]
    return []


def _dedupe_targets(targets: list[dict[str, str]]) -> list[dict[str, str]]:
    seen: set[tuple[str, str]] = set()
    unique: list[dict[str, str]] = []
    for target in targets:
        key = (target.get("ip_dir", ""), target.get("run_id", ""))
        if not key[0] or key in seen:
            continue
        seen.add(key)
        unique.append(target)
    return unique


def _stop_check(target: dict[str, str]) -> dict:
    args = {"ip_dir": target["ip_dir"]}
    if target.get("run_id"):
        args["run_id"] = target["run_id"]
    response = oag_cli.dispatch_call({"tool": "oag.stop_check", "arguments": args})
    if not isinstance(response, dict) or not response.get("ok"):
        return {}
    result = response.get("result")
    return result if isinstance(result, dict) else {}


def _main_write_gate(target: dict[str, str]) -> dict:
    return oag_main_write_gate.check_ip(Path(target["ip_dir"]))


def _run_gate(payload: dict, targets: list[dict[str, str]], cache: dict, cache_path: Path, *, write_cache: bool) -> int:
    cache_changed = False
    blocks: list[str] = []
    for target in targets:
        try:
            result = _stop_check(target)
        except Exception as exc:
            name = Path(target["ip_dir"]).name
            blocks.append(f"[OAG:{name}] stop check failed closed: {exc}")
            continue
        if result.get("reason") == "needs_human_decision":
            continue
        should_continue = result.get("should_continue") is True
        if not should_continue:
            continue
        reason_code = str(result.get("reason") or "")
        name = result.get("ip") or Path(target["ip_dir"]).name
        prompt = str(result.get("prompt_block") or "").strip()
        header = f"[OAG:{name}] run incomplete ({reason_code}; target_source={target.get('source') or 'unknown'})."
        block = f"{header}\n{prompt}".strip()
        key = f"{Path(target['ip_dir']).resolve()}::{target.get('run_id') or result.get('run_id') or ''}"
        if _block_allowed(cache, key=key, digest=_digest(block), max_repeats=_max_block_repeats(result)):
            blocks.append(block)
        cache_changed = True
    for target in targets:
        try:
            result = _main_write_gate(target)
        except Exception as exc:
            name = Path(target["ip_dir"]).name
            blocks.append(f"[OAG:{name}] main-write gate failed closed: {exc}")
            continue
        if result.get("status") != "fail":
            continue
        name = result.get("ip") or Path(target["ip_dir"]).name
        lines = [
            f"[OAG:{name}] locked implementation write requires native subagent evidence "
            f"(target_source={target.get('source') or 'unknown'}; ip_dir={target['ip_dir']})."
        ]
        for item in result.get("issues", [])[:8]:
            if isinstance(item, dict):
                path = f" ({item.get('path')})" if item.get("path") else ""
                lines.append(f"- {item.get('code')}: {item.get('message')}{path}")
        lines.extend(
            [
                "Required next step: create an OAG dispatch and spawn the owning native subagent,",
                "or record a human main-agent subagent waiver before stopping.",
            ]
        )
        block = "\n".join(lines)
        key = f"{Path(target['ip_dir']).resolve()}::main-write-gate"
        if _block_allowed(cache, key=key, digest=_digest(block), max_repeats=3):
            blocks.append(block)
        cache_changed = True

    if blocks:
        reason = (
            "OAG stop gate blocked this response. Resolve the matching item below:\n\n" + "\n\n".join(blocks)
        )
        print(json.dumps({"decision": "block", "reason": reason}, ensure_ascii=False))
    if cache_changed and write_cache:
        _write_cache(cache_path, cache)
    return 0


def main() -> int:
    payload = _read_payload()
    identity = hook_identity(payload)
    targets = _dedupe_targets(_target_runs(payload, identity))
    cache_path = hook_cache_path(payload, hook_name="stop_gate", exact_env="OAG_STOP_GATE_CACHE")
    try:
        with cache_file_lock(cache_path):
            cache = _read_cache(cache_path, identity)
            return _run_gate(payload, targets, cache, cache_path, write_cache=True)
    except Exception:
        return _run_gate(payload, targets, _default_cache(identity), cache_path, write_cache=False)


if __name__ == "__main__":
    raise SystemExit(main())
