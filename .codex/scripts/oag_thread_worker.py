#!/usr/bin/env python3
"""Run one bounded OAG dispatch in a fresh Codex App Server thread."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import queue
import signal
import shlex
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any, Callable

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python < 3.11 compatibility
    import tomli as tomllib  # type: ignore[no-redef]


SCRIPTS_DIR = Path(__file__).resolve().parent
CODEX_ROOT = SCRIPTS_DIR.parent
PROJECT_ROOT = CODEX_ROOT.parent
AGENT_CATALOG = CODEX_ROOT / "oag" / "agent-catalog.toml"
AGENT_COMMON_PREAMBLE = CODEX_ROOT / "oag" / "agent-common-preamble.md"
sys.path.insert(0, str(SCRIPTS_DIR))

from oag_dispatch_support import (  # noqa: E402
    JsonObject,
    load_json,
    project_rel,
    resolve_project_path,
    schema_issues,
    sha256,
)
from oag_dispatch_verify import valid_dispatch_integrity, verify_dispatch  # noqa: E402
from oag_receipt_finalize import (  # noqa: E402
    finalize_worker_receipt,
    receipt_prompt_skeleton,
)


def utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def text_input(value: str) -> list[JsonObject]:
    return [{"type": "text", "text": value}]


def atomic_write_json(path: Path, payload: JsonObject) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def zero_usage() -> JsonObject:
    return {
        "input_tokens": 0,
        "cached_input_tokens": 0,
        "output_tokens": 0,
        "reasoning_output_tokens": 0,
        "total_tokens": 0,
    }


def normalized_usage(payload: JsonObject) -> JsonObject:
    return {
        "input_tokens": int(payload.get("inputTokens") or 0),
        "cached_input_tokens": int(payload.get("cachedInputTokens") or 0),
        "output_tokens": int(payload.get("outputTokens") or 0),
        "reasoning_output_tokens": int(payload.get("reasoningOutputTokens") or 0),
        "total_tokens": int(payload.get("totalTokens") or 0),
    }


def contains_subagent_activity(value: Any) -> bool:
    if isinstance(value, dict):
        if value.get("type") == "collabAgentToolCall":
            return True
        return any(contains_subagent_activity(item) for item in value.values())
    if isinstance(value, list):
        return any(contains_subagent_activity(item) for item in value)
    return False


CONTROL_SCHEMA_VERSION = "oag_thread_control.v1"
CONTROL_DIRECTION = "controller_to_worker"
CONTROL_ACK_DIRECTION = "worker_control_ack"
RUNTIME_CLEANUP_DIRECTION = "worker_runtime_cleanup"

# Some formal backends write fixed-name scratch files in the caller's cwd.
# Keep this list narrow: cleanup is permitted only when the path did not exist
# when this worker invocation started.
TRANSIENT_ROOT_ARTIFACTS = {
    "sm01.aig": "yosys-abc unresolved-miter scratch output",
}


def transient_root_snapshot(root: Path) -> dict[str, JsonObject]:
    snapshot: dict[str, JsonObject] = {}
    for relative_path in TRANSIENT_ROOT_ARTIFACTS:
        path = root / relative_path
        snapshot[relative_path] = {
            "exists": path.exists() or path.is_symlink(),
            "is_file": path.is_file() and not path.is_symlink(),
            "sha256": f"sha256:{sha256(path)}" if path.is_file() and not path.is_symlink() else "",
        }
    return snapshot


def cleanup_new_transient_root_artifacts(
    root: Path,
    baseline: dict[str, JsonObject],
    event_log: "JsonlEventLog",
) -> list[JsonObject]:
    cleaned: list[JsonObject] = []
    for relative_path, reason in TRANSIENT_ROOT_ARTIFACTS.items():
        path = root / relative_path
        before = baseline.get(relative_path) or {}
        if bool(before.get("exists")) or not path.exists() or path.is_symlink() or not path.is_file():
            continue
        row: JsonObject = {
            "path": relative_path,
            "reason": reason,
            "sha256": f"sha256:{sha256(path)}",
            "size_bytes": path.stat().st_size,
        }
        path.unlink()
        cleaned.append(row)
        event_log.append(RUNTIME_CLEANUP_DIRECTION, row)
    return cleaned


class ThreadControlReader:
    """Tail externally appended steering requests from the execution event log."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.offset = 0
        self.buffer = b""
        self.acknowledged: set[str] = set()

    def poll(self) -> list[JsonObject]:
        try:
            with self.path.open("rb") as handle:
                handle.seek(self.offset)
                chunk = handle.read()
                self.offset = handle.tell()
        except FileNotFoundError:
            return []
        if not chunk:
            return []

        parts = (self.buffer + chunk).split(b"\n")
        self.buffer = parts.pop()
        rows: list[JsonObject] = []
        for raw in parts:
            if not raw:
                continue
            try:
                row = json.loads(raw)
            except (UnicodeDecodeError, json.JSONDecodeError):
                continue
            if isinstance(row, dict):
                rows.append(row)

        for row in rows:
            if row.get("direction") != CONTROL_ACK_DIRECTION:
                continue
            message = row.get("message") if isinstance(row.get("message"), dict) else {}
            request_id = str(message.get("request_id") or "")
            if request_id:
                self.acknowledged.add(request_id)

        controls: list[JsonObject] = []
        observed: set[str] = set()
        for row in rows:
            if row.get("direction") != CONTROL_DIRECTION:
                continue
            message = row.get("message") if isinstance(row.get("message"), dict) else {}
            request_id = str(message.get("request_id") or "")
            if request_id and request_id not in self.acknowledged and request_id not in observed:
                controls.append(message)
                observed.add(request_id)
        return controls


def load_toml(path: Path) -> JsonObject:
    with path.open("rb") as handle:
        payload = tomllib.load(handle)
    if not isinstance(payload, dict):
        raise ValueError(f"TOML document must be an object: {path}")
    return payload


def resolve_role_definition(dispatch: JsonObject) -> JsonObject:
    role_id = str(
        dispatch.get("registered_id")
        or dispatch.get("role_name")
        or dispatch.get("agent_type")
        or ""
    )
    if not role_id:
        raise ValueError("dispatch has no registered OAG role identity")

    catalog = load_toml(AGENT_CATALOG)
    entries = catalog.get("agents") if isinstance(catalog.get("agents"), list) else []
    entry = next(
        (candidate for candidate in entries if isinstance(candidate, dict) and candidate.get("id") == role_id),
        None,
    )
    if not isinstance(entry, dict):
        raise ValueError(f"registered OAG role is missing from agent catalog: {role_id}")

    source_ref = str(entry.get("source_file") or "")
    source_path = (PROJECT_ROOT / source_ref).resolve()
    agents_root = (CODEX_ROOT / "agents").resolve()
    if not source_ref or source_path.parent != agents_root:
        raise ValueError(f"unsafe OAG role definition path for {role_id}: {source_ref}")
    role = load_toml(source_path)
    if str(role.get("name") or "") != role_id:
        raise ValueError(f"OAG role definition name mismatch for {role_id}")
    instructions = str(role.get("developer_instructions") or "").strip()
    if not instructions:
        raise ValueError(f"OAG role definition has no developer_instructions: {role_id}")

    preamble = AGENT_COMMON_PREAMBLE.read_text(encoding="utf-8").strip()
    return {
        "id": role_id,
        "kind": str(entry.get("kind") or dispatch.get("role_kind") or ""),
        "source_path": source_ref,
        "source_sha256": f"sha256:{sha256(source_path)}",
        "catalog_path": ".codex/oag/agent-catalog.toml",
        "catalog_sha256": f"sha256:{sha256(AGENT_CATALOG)}",
        "common_preamble_path": ".codex/oag/agent-common-preamble.md",
        "common_preamble_sha256": f"sha256:{sha256(AGENT_COMMON_PREAMBLE)}",
        "developer_instructions": instructions,
        "common_preamble": preamble,
        "default_model": str(role.get("model") or ""),
        "default_reasoning_effort": str(role.get("model_reasoning_effort") or "medium"),
        "default_sandbox": str(role.get("sandbox_mode") or "workspace-write"),
    }


class JsonlEventLog:
    def __init__(self, path: Path, *, append: bool = False) -> None:
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        flags = os.O_WRONLY | os.O_CREAT | os.O_APPEND | (0 if append else os.O_TRUNC)
        fd = os.open(path, flags, 0o600)
        self._file = os.fdopen(fd, "w", encoding="utf-8", buffering=1)
        self._lock = threading.Lock()

    def append(self, direction: str, message: Any) -> None:
        row = {"created_at": utc_now(), "direction": direction, "message": message}
        with self._lock:
            self._file.write(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n")
            self._file.flush()

    def digest(self) -> str:
        with self._lock:
            self._file.flush()
        return f"sha256:{sha256(self.path)}"

    def close(self) -> None:
        with self._lock:
            if not self._file.closed:
                self._file.flush()
                self._file.close()


class AppServerClient:
    def __init__(self, command: list[str], *, cwd: Path, env: dict[str, str], event_log: JsonlEventLog) -> None:
        self.event_log = event_log
        self.process = subprocess.Popen(
            command,
            cwd=cwd,
            env=env,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            start_new_session=os.name != "nt",
        )
        self.messages: queue.Queue[JsonObject] = queue.Queue()
        self.stderr_lines: list[str] = []
        self._next_id = 1
        self._stdout_thread = threading.Thread(target=self._read_stdout, daemon=True)
        self._stderr_thread = threading.Thread(target=self._read_stderr, daemon=True)
        self._stdout_thread.start()
        self._stderr_thread.start()

    def _read_stdout(self) -> None:
        assert self.process.stdout is not None
        for line in self.process.stdout:
            stripped = line.strip()
            if not stripped:
                continue
            try:
                message = json.loads(stripped)
            except json.JSONDecodeError:
                message = {"invalid_json": stripped}
            if isinstance(message, dict):
                self.event_log.append("server_to_client", message)
                self.messages.put(message)

    def _read_stderr(self) -> None:
        assert self.process.stderr is not None
        for line in self.process.stderr:
            if len(self.stderr_lines) < 200:
                self.stderr_lines.append(line.rstrip())

    def send(self, message: JsonObject) -> None:
        if self.process.stdin is None:
            raise RuntimeError("app server stdin is unavailable")
        self.event_log.append("client_to_server", message)
        self.process.stdin.write(json.dumps(message, separators=(",", ":")) + "\n")
        self.process.stdin.flush()

    def notify(self, method: str, params: JsonObject | None = None) -> None:
        message: JsonObject = {"method": method}
        if params is not None:
            message["params"] = params
        self.send(message)

    def send_request(self, method: str, params: JsonObject) -> int:
        request_id = self._next_id
        self._next_id += 1
        self.send({"id": request_id, "method": method, "params": params})
        return request_id

    def request(
        self,
        method: str,
        params: JsonObject,
        *,
        timeout: float,
        notification: Callable[[JsonObject], None] | None = None,
    ) -> JsonObject:
        request_id = self.send_request(method, params)
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                message = self.messages.get(timeout=min(0.25, max(0.01, deadline - time.monotonic())))
            except queue.Empty:
                if self.process.poll() is not None:
                    raise RuntimeError(f"app server exited with code {self.process.returncode}")
                continue
            if message.get("id") == request_id:
                if "error" in message:
                    raise RuntimeError(f"app server {method} failed: {message['error']}")
                result = message.get("result")
                return result if isinstance(result, dict) else {}
            if "method" in message and notification is not None:
                notification(message)
        raise TimeoutError(f"timed out waiting for app server {method}")

    @staticmethod
    def _descendant_pids(root_pid: int) -> set[int]:
        if os.name == "nt":
            return set()
        result = subprocess.run(
            ["ps", "-axo", "pid=,ppid="],
            text=True,
            capture_output=True,
            check=False,
        )
        children: dict[int, list[int]] = {}
        for line in result.stdout.splitlines():
            fields = line.split()
            if len(fields) != 2:
                continue
            try:
                pid, parent = (int(value) for value in fields)
            except ValueError:
                continue
            children.setdefault(parent, []).append(pid)
        descendants: set[int] = set()
        pending = list(children.get(root_pid, []))
        while pending:
            pid = pending.pop()
            if pid in descendants:
                continue
            descendants.add(pid)
            pending.extend(children.get(pid, []))
        return descendants

    def close(self) -> None:
        if self.process.poll() is None:
            if os.name == "nt":
                subprocess.run(
                    ["taskkill", "/PID", str(self.process.pid), "/T", "/F"],
                    text=True,
                    capture_output=True,
                    check=False,
                )
            else:
                descendants = self._descendant_pids(self.process.pid)
                targets = [self.process.pid, *sorted(descendants, reverse=True)]
                for pid in targets:
                    try:
                        os.kill(pid, signal.SIGTERM)
                    except ProcessLookupError:
                        pass
                deadline = time.monotonic() + 2
                while time.monotonic() < deadline:
                    if all(not Path(f"/proc/{pid}").exists() for pid in targets) and sys.platform.startswith("linux"):
                        break
                    if self.process.poll() is not None:
                        break
                    time.sleep(0.05)
                for pid in targets:
                    try:
                        os.kill(pid, 0)
                    except ProcessLookupError:
                        continue
                    try:
                        os.kill(pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=5)
        self._stdout_thread.join(timeout=1)
        self._stderr_thread.join(timeout=1)


def thread_id_from_result(result: JsonObject) -> str:
    thread = result.get("thread") if isinstance(result.get("thread"), dict) else {}
    return str(thread.get("id") or "")


def turn_id_from_result(result: JsonObject) -> str:
    turn = result.get("turn") if isinstance(result.get("turn"), dict) else {}
    return str(turn.get("id") or "")


def run_worker(args: argparse.Namespace) -> JsonObject:
    dispatch_path = resolve_project_path(args.dispatch)
    dispatch = load_json(dispatch_path)
    if not isinstance(dispatch, dict):
        raise ValueError("dispatch JSON must be an object")
    dispatch_schema = schema_issues("oag_dispatch.schema.json", dispatch)
    if dispatch_schema or not valid_dispatch_integrity(dispatch):
        raise ValueError(f"dispatch schema/integrity failed: {dispatch_schema[:3]}")
    actor = dispatch.get("execution_actor") if isinstance(dispatch.get("execution_actor"), dict) else {}
    if actor.get("kind") != "worker_thread" or actor.get("subagents_allowed") is not False:
        raise ValueError("oag_thread_worker requires a worker_thread dispatch with subagents_allowed=false")
    role_definition = resolve_role_definition(dispatch)
    if role_definition["kind"] != str(dispatch.get("role_kind") or ""):
        raise ValueError("dispatch role_kind does not match the registered OAG agent catalog entry")

    manifest_path = resolve_project_path(str(actor.get("manifest_path") or ""))
    event_ref = str(actor.get("event_log_path") or "")
    if not event_ref:
        event_ref = project_rel(manifest_path.with_name(f"{dispatch['dispatch_id']}.events.jsonl"))
    event_path = resolve_project_path(event_ref)
    prior_manifest: JsonObject = {}
    if args.resume:
        loaded_manifest = load_json(manifest_path)
        if not isinstance(loaded_manifest, dict):
            raise ValueError("resume requires an existing thread execution manifest object")
        prior_manifest = loaded_manifest
        manifest_schema = schema_issues("oag_thread_execution.schema.json", prior_manifest)
        if manifest_schema:
            raise ValueError(f"resume manifest schema failed: {manifest_schema[:3]}")
        if str(prior_manifest.get("dispatch_id") or "") != str(dispatch.get("dispatch_id") or ""):
            raise ValueError("resume manifest dispatch_id does not match dispatch")
        prior_role = prior_manifest.get("role_definition") if isinstance(prior_manifest.get("role_definition"), dict) else {}
        if str(prior_role.get("source_sha256") or "") != role_definition["source_sha256"]:
            raise ValueError("resume role definition hash does not match the original execution")
        if str(prior_manifest.get("status") or "") not in {"failed", "interrupted"}:
            raise ValueError("resume requires a failed or interrupted prior execution")
        if int(prior_manifest.get("subagent_activity_count") or 0) != 0:
            raise ValueError("execution with subagent activity cannot be resumed")
        prior_event_path = resolve_project_path(str(prior_manifest.get("event_log_path") or ""))
        if prior_event_path != event_path or f"sha256:{sha256(event_path)}" != str(prior_manifest.get("event_log_sha256") or ""):
            raise ValueError("resume event log is missing or does not match the prior manifest")
    task_text = args.task or ""
    if args.task_file:
        task_text = Path(args.task_file).expanduser().resolve().read_text(encoding="utf-8")
    if not task_text.strip():
        raise ValueError("--task or --task-file is required")

    budget = dispatch.get("execution_budget") if isinstance(dispatch.get("execution_budget"), dict) else {}
    warning_tokens = int(budget.get("warning_total_tokens") or 0)
    max_tokens = int(budget.get("max_total_tokens") or 0)
    token_budget_mode = str(args.token_budget_mode or prior_manifest.get("token_budget_mode") or "enforce")
    hard_stop_tokens = 0
    if token_budget_mode == "enforce" and max_tokens:
        hard_stop_tokens = max(warning_tokens + 1, max_tokens - max(1, max_tokens // 6))
    timeout_seconds = int(args.timeout_seconds)
    effective_model = str(
        args.model
        or prior_manifest.get("model")
        or role_definition["default_model"]
        or ""
    )
    effective_effort = str(
        args.effort
        or prior_manifest.get("reasoning_effort")
        or role_definition["default_reasoning_effort"]
        or "medium"
    )
    effective_sandbox = str(args.sandbox or role_definition["default_sandbox"] or "workspace-write")
    if not effective_model:
        raise ValueError(f"OAG role has no default model and no --model override: {role_definition['id']}")
    if effective_effort not in {"none", "minimal", "low", "medium", "high", "xhigh"}:
        raise ValueError(f"invalid OAG role reasoning effort: {effective_effort}")
    if effective_sandbox not in {"read-only", "workspace-write", "danger-full-access"}:
        raise ValueError(f"invalid OAG role sandbox: {effective_sandbox}")
    command = shlex.split(args.app_server_command)
    if not command:
        raise ValueError("--app-server-command must not be empty")

    started_at = str(prior_manifest.get("started_at") or utc_now())
    prior_usage = prior_manifest.get("token_usage") if isinstance(prior_manifest.get("token_usage"), dict) else zero_usage()
    prior_resume_count = int(prior_manifest.get("resume_count") or 0)
    resume_count = prior_resume_count + 1 if args.resume else 0
    resume_limit = int(actor.get("resume_limit") or 0)
    if resume_count > resume_limit:
        raise ValueError("dispatch resume_limit exceeded")
    if token_budget_mode == "enforce" and int(prior_usage.get("total_tokens") or 0) >= max_tokens:
        raise ValueError("cannot resume because the dispatch hard token budget is already exhausted")
    event_log = JsonlEventLog(event_path, append=bool(args.resume))
    control_reader = ThreadControlReader(event_path)
    runtime_root = resolve_project_path(".")
    transient_baseline = transient_root_snapshot(runtime_root)
    state: JsonObject = {
        "thread_id": str(prior_manifest.get("thread_id") or ""),
        "turn_ids": list(prior_manifest.get("turn_ids") or []),
        "model": effective_model,
        "usage": prior_usage,
        "warning_sent": bool(prior_manifest.get("warning_sent")) if args.resume else False,
        "budget_warning_observed": bool(prior_manifest.get("budget_warning_observed")) if args.resume else False,
        "budget_max_observed": bool(prior_manifest.get("budget_max_observed")) if args.resume else False,
        "budget_exceeded": False,
        "subagent_activity_count": 0,
        "failure_reason": "",
        "turn_status": "",
        "steering_request_count": int(prior_manifest.get("steering_request_count") or 0),
        "steering_applied_count": int(prior_manifest.get("steering_applied_count") or 0),
        "steering_rejected_count": int(prior_manifest.get("steering_rejected_count") or 0),
        "last_steering_at": str(prior_manifest.get("last_steering_at") or ""),
    }

    def manifest(status: str, *, completed_at: str = "") -> JsonObject:
        return {
            "schema_version": "oag_thread_execution.v1",
            "execution_kind": "worker_thread",
            "control_protocol": CONTROL_SCHEMA_VERSION,
            "dispatch_id": dispatch["dispatch_id"],
            "dispatch_path": dispatch["dispatch_path"],
            "thread_id": state["thread_id"],
            "turn_ids": state["turn_ids"],
            "status": status,
            "model": state["model"] or "unknown",
            "reasoning_effort": effective_effort,
            "model_source": "cli_override" if args.model else ("resume_manifest" if args.resume else "role_default"),
            "reasoning_effort_source": "cli_override" if args.effort else ("resume_manifest" if args.resume else "role_default"),
            "sandbox": effective_sandbox,
            "sandbox_source": "cli_override" if args.sandbox else "role_default",
            "role_definition": {
                key: value
                for key, value in role_definition.items()
                if key not in {"developer_instructions", "common_preamble"}
            },
            "started_at": started_at,
            "updated_at": utc_now(),
            "completed_at": completed_at,
            "token_usage": state["usage"],
            "warning_sent": state["warning_sent"],
            "budget_warning_observed": state["budget_warning_observed"],
            "budget_max_observed": state["budget_max_observed"],
            "budget_exceeded": state["budget_exceeded"],
            "token_budget_mode": token_budget_mode,
            "budget_warning_tokens": warning_tokens,
            "budget_hard_stop_tokens": hard_stop_tokens,
            "budget_configured_max_tokens": max_tokens,
            "resume_count": resume_count,
            "subagent_activity_count": state["subagent_activity_count"],
            "steering_request_count": state["steering_request_count"],
            "steering_applied_count": state["steering_applied_count"],
            "steering_rejected_count": state["steering_rejected_count"],
            "last_steering_at": state["last_steering_at"],
            "event_log_path": project_rel(event_path),
            "event_log_sha256": event_log.digest(),
            "failure_reason": state["failure_reason"],
        }

    env = {
        **os.environ,
        "OAG_EXECUTION_KIND": "worker_thread",
        "OAG_DISPATCH_ID": str(dispatch["dispatch_id"]),
        "OAG_DISPATCH_PATH": str(dispatch["dispatch_path"]),
        "OAG_THREAD_EXECUTION_MANIFEST": project_rel(manifest_path),
    }
    client: AppServerClient | None = None
    interrupt_sent_at: float | None = None

    def update_running_manifest() -> None:
        if state["thread_id"] and state["turn_ids"]:
            atomic_write_json(manifest_path, manifest("running"))

    def handle(message: JsonObject) -> None:
        nonlocal interrupt_sent_at
        method = str(message.get("method") or "")
        params = message.get("params") if isinstance(message.get("params"), dict) else {}
        if contains_subagent_activity(params):
            state["subagent_activity_count"] = 1
            state["failure_reason"] = "subagent activity violates thread-only execution contract"
            if client is not None and state["thread_id"] and state["turn_ids"] and interrupt_sent_at is None:
                client.send_request(
                    "turn/interrupt",
                    {"threadId": state["thread_id"], "turnId": state["turn_ids"][-1]},
                )
                interrupt_sent_at = time.monotonic()
        if method == "thread/tokenUsage/updated":
            token_usage = params.get("tokenUsage") if isinstance(params.get("tokenUsage"), dict) else {}
            total = token_usage.get("total") if isinstance(token_usage.get("total"), dict) else {}
            state["usage"] = normalized_usage(total)
            total_tokens = int(state["usage"]["total_tokens"])
            if warning_tokens and total_tokens >= warning_tokens:
                state["budget_warning_observed"] = True
                if token_budget_mode == "enforce" and not state["warning_sent"]:
                    state["warning_sent"] = True
                    if client is not None and state["thread_id"] and state["turn_ids"]:
                        client.send_request(
                            "turn/steer",
                            {
                                "threadId": state["thread_id"],
                                "expectedTurnId": state["turn_ids"][-1],
                                "input": text_input(
                                    "OAG budget warning reached. Stop exploration, write the required outputs now, copy the literal RECEIPT IDENTITY CONSTANTS, and report remaining work without expanding scope."
                                ),
                            },
                        )
            if max_tokens and total_tokens >= max_tokens:
                state["budget_max_observed"] = True
            if hard_stop_tokens and total_tokens >= hard_stop_tokens and interrupt_sent_at is None:
                state["budget_exceeded"] = True
                state["failure_reason"] = (
                    f"hard token budget guard reached at {total_tokens} tokens "
                    f"(configured max {max_tokens}, stop threshold {hard_stop_tokens})"
                )
                if client is not None and state["thread_id"] and state["turn_ids"]:
                    client.send_request(
                        "turn/interrupt",
                        {"threadId": state["thread_id"], "turnId": state["turn_ids"][-1]},
                    )
                    interrupt_sent_at = time.monotonic()
        if method == "turn/completed":
            turn = params.get("turn") if isinstance(params.get("turn"), dict) else {}
            state["turn_status"] = str(turn.get("status") or "")
        update_running_manifest()

    def acknowledge_control(request: JsonObject, status: str, reason: str = "") -> None:
        request_id = str(request.get("request_id") or "")
        event_log.append(
            CONTROL_ACK_DIRECTION,
            {
                "schema_version": CONTROL_SCHEMA_VERSION,
                "request_id": request_id,
                "method": str(request.get("method") or ""),
                "thread_id": str(state["thread_id"]),
                "turn_id": str(state["turn_ids"][-1] if state["turn_ids"] else ""),
                "status": status,
                "reason": reason,
            },
        )
        if request_id:
            control_reader.acknowledged.add(request_id)
        state["steering_request_count"] += 1
        if status == "applied":
            state["steering_applied_count"] += 1
        else:
            state["steering_rejected_count"] += 1
        state["last_steering_at"] = utc_now()
        update_running_manifest()

    def process_controls() -> None:
        if client is None or not state["thread_id"] or not state["turn_ids"]:
            return
        for request in control_reader.poll():
            request_id = str(request.get("request_id") or "")
            method = str(request.get("method") or "")
            expected_thread = str(request.get("thread_id") or "")
            expected_turn = str(request.get("expected_turn_id") or "")
            input_text = str(request.get("input") or "").strip()
            rejection = ""
            if request.get("schema_version") != CONTROL_SCHEMA_VERSION:
                rejection = "unsupported control schema"
            elif not request_id:
                rejection = "request_id is required"
            elif method != "turn/steer":
                rejection = "only turn/steer is supported"
            elif expected_thread != state["thread_id"]:
                rejection = "thread_id does not match the active worker"
            elif expected_turn != state["turn_ids"][-1]:
                rejection = "expected_turn_id does not match the active turn"
            elif not input_text:
                rejection = "steering input is empty"
            elif len(input_text) > 12000:
                rejection = "steering input exceeds 12000 characters"
            if rejection:
                acknowledge_control(request, "rejected", rejection)
                continue
            try:
                client.request(
                    "turn/steer",
                    {
                        "threadId": state["thread_id"],
                        "expectedTurnId": state["turn_ids"][-1],
                        "input": text_input(input_text),
                    },
                    timeout=15,
                    notification=handle,
                )
            except (RuntimeError, TimeoutError) as exc:
                acknowledge_control(request, "rejected", str(exc))
            else:
                acknowledge_control(request, "applied")

    try:
        client = AppServerClient(command, cwd=resolve_project_path("."), env=env, event_log=event_log)
        client.request(
            "initialize",
            {"clientInfo": {"name": "oag-thread-worker", "version": "1.0"}, "capabilities": {}},
            timeout=20,
            notification=handle,
        )
        client.notify("initialized", {})
        developer_instructions = "\n\n".join(
            [
                str(role_definition["common_preamble"]),
                "REGISTERED OAG ROLE PROFILE\n" + str(role_definition["developer_instructions"]),
                (
                    "THREAD-ONLY EXECUTION OVERRIDE\n"
                    "This registered OAG role is running as an independent top-level worker thread, not as a subagent. "
                    "Do not spawn, delegate to, or message subagents. "
                    "The parent already completed OAG intake, orchestration, and dispatch validation. "
                    "Do not load OAG skills, inspect workflow manuals, run OAG orchestration commands, or search the broad repository. "
                    "The complete dispatch contract is embedded in the turn input; do not open or read the dispatch JSON file. "
                    "Use only the role profile, dispatch contract, assigned task, and explicitly named source files. "
                    "Stay within the dispatch write scope and write the required executor receipt before finishing. "
                    "Run formal and solver subprocesses from a dispatch-owned build directory; fixed-name scratch outputs such as "
                    "sm01.aig must never be left in the repository root."
                ),
            ]
        )
        thread_method = "thread/resume" if args.resume else "thread/start"
        thread_params: JsonObject = {
            "cwd": str(resolve_project_path(".")),
            "approvalPolicy": "never",
            "sandbox": effective_sandbox,
            "model": effective_model,
            "config": {
                "features.multi_agent": False,
                "features.child_agents_md": False,
            },
            "developerInstructions": developer_instructions,
        }
        if args.resume:
            thread_params["threadId"] = state["thread_id"]
        else:
            thread_params["ephemeral"] = False
        thread_result = client.request(
            thread_method,
            thread_params,
            timeout=30,
            notification=handle,
        )
        observed_thread_id = thread_id_from_result(thread_result)
        if args.resume and observed_thread_id and observed_thread_id != state["thread_id"]:
            raise RuntimeError("thread/resume returned a different thread id")
        state["thread_id"] = observed_thread_id or state["thread_id"]
        state["model"] = str(thread_result.get("model") or effective_model)
        if not state["thread_id"]:
            raise RuntimeError("thread/start returned no thread id")

        prompt = "\n\n".join(
            [
                str(dispatch.get("prompt_contract") or ""),
                "RUNTIME IDENTITY\n"
                f"- thread_id: {state['thread_id']}\n"
                f"- execution_manifest_path: {project_rel(manifest_path)}\n"
                f"- execution_event_log_path: {project_rel(event_path)}\n"
                f"- resume_count: {resume_count}\n"
                "- receipt must set execution_kind=worker_thread, include the thread and manifest identity values exactly, "
                "and list both manifest and event log under generated_side_effects",
                "RECEIPT IDENTITY CONSTANTS\n"
                f"- product_name: {dispatch.get('product_name') or 'IP Dev Agent'}\n"
                f"- internal_gateway: {dispatch.get('internal_gateway') or 'Ontology Agent Gateway'}\n"
                f"- ip_id: {dispatch.get('ip_id') or ''}\n"
                f"- agent_type: {dispatch.get('agent_type') or ''}\n"
                f"- role_name: {dispatch.get('role_name') or ''}\n"
                f"- registered_id: {dispatch.get('registered_id') or ''}\n"
                f"- stage: {dispatch.get('stage') or ''}\n"
                "- copy these literal values into the receipt; do not paraphrase or rename them",
                "RECEIPT JSON SKELETON\n"
                "Start from this exact object. Preserve the semantic status and blocker details you observe. "
                "Leave dispatch_verified=false; the worker runtime alone changes it to true after structural preverification.\n"
                + receipt_prompt_skeleton(
                    dispatch,
                    thread_id=str(state["thread_id"]),
                    manifest_path=project_rel(manifest_path),
                    event_log_path=project_rel(event_path),
                ),
                (
                    "TOKEN BUDGET RUNTIME OVERRIDE\n"
                    "- mode: observe\n"
                    "- token warning and maximum thresholds are telemetry only in this run\n"
                    "- do not stop, summarize early, or reduce scope because a token threshold was crossed\n"
                    "- continue until the assigned task is complete or the wall-clock timeout is reached"
                    if token_budget_mode == "observe"
                    else "TOKEN BUDGET RUNTIME OVERRIDE\n- mode: enforce\n- follow the dispatch warning and hard-stop policy"
                ),
                "ASSIGNED TASK\n" + task_text.strip(),
            ]
        )
        turn_result = client.request(
            "turn/start",
            {
                "threadId": state["thread_id"],
                "input": text_input(prompt),
                "model": effective_model,
                "effort": effective_effort,
                "cwd": str(resolve_project_path(".")),
            },
            timeout=30,
            notification=handle,
        )
        turn_id = turn_id_from_result(turn_result)
        if not turn_id:
            raise RuntimeError("turn/start returned no turn id")
        state["turn_ids"] = [*state["turn_ids"], turn_id]
        update_running_manifest()

        deadline = time.monotonic() + timeout_seconds
        while not state["turn_status"]:
            process_controls()
            if time.monotonic() >= deadline and interrupt_sent_at is None:
                state["failure_reason"] = "wall-clock timeout reached"
                client.send_request("turn/interrupt", {"threadId": state["thread_id"], "turnId": turn_id})
                interrupt_sent_at = time.monotonic()
            if interrupt_sent_at is not None and time.monotonic() - interrupt_sent_at > 30:
                break
            try:
                message = client.messages.get(timeout=0.25)
            except queue.Empty:
                if client.process.poll() is not None:
                    state["failure_reason"] = state["failure_reason"] or f"app server exited with code {client.process.returncode}"
                    break
                continue
            if "method" in message:
                handle(message)
        client.close()
        client = None
        cleanup_new_transient_root_artifacts(runtime_root, transient_baseline, event_log)

        if state["subagent_activity_count"]:
            final_status = "failed"
        elif state["budget_exceeded"] or state["failure_reason"] == "wall-clock timeout reached":
            final_status = "interrupted"
        elif state["turn_status"] == "completed":
            final_status = "completed"
        elif state["turn_status"] == "interrupted":
            final_status = "interrupted"
        else:
            final_status = "failed"
            state["failure_reason"] = state["failure_reason"] or f"turn ended with status {state['turn_status'] or 'unknown'}"

        completed_at = utc_now()
        atomic_write_json(manifest_path, manifest(final_status, completed_at=completed_at))
        receipt_path = resolve_project_path(str(dispatch.get("receipt_path") or ""))
        receipt_finalization: JsonObject = {
            "status": "not_run",
            "normalized_fields": [],
            "semantic_status_before": "",
            "semantic_status_after": "",
        }
        if final_status == "completed" and receipt_path.is_file():
            raw_receipt = load_json(receipt_path)
            if isinstance(raw_receipt, dict):
                semantic_status_before = str(raw_receipt.get("status") or "")
                finalized_receipt, normalized_fields = finalize_worker_receipt(
                    dispatch,
                    raw_receipt,
                    thread_id=str(state["thread_id"]),
                    manifest_path=project_rel(manifest_path),
                    event_log_path=project_rel(event_path),
                    created_at=completed_at,
                )
                atomic_write_json(receipt_path, finalized_receipt)
                preverification = verify_dispatch(
                    argparse.Namespace(
                        dispatch=str(dispatch_path),
                        receipt=str(receipt_path),
                        schema_only=False,
                        allow_worker_receipt_preverify=True,
                    )
                )
                receipt_finalization = {
                    "status": "preverify_pass" if preverification.get("status") == "pass" else "preverify_fail",
                    "normalized_fields": normalized_fields,
                    "semantic_status_before": semantic_status_before,
                    "semantic_status_after": str(finalized_receipt.get("status") or ""),
                    "preverification": preverification,
                }
                if preverification.get("status") == "pass":
                    finalized_receipt["dispatch_verified"] = True
                    atomic_write_json(receipt_path, finalized_receipt)
                    verification = verify_dispatch(
                        argparse.Namespace(dispatch=str(dispatch_path), receipt=str(receipt_path), schema_only=False)
                    )
                    if verification.get("status") == "pass":
                        receipt_finalization["status"] = "pass"
                    else:
                        finalized_receipt["dispatch_verified"] = False
                        atomic_write_json(receipt_path, finalized_receipt)
                        receipt_finalization["status"] = "full_verify_fail"
                else:
                    verification = preverification
            else:
                receipt_finalization["status"] = "invalid_receipt"
                verification = verify_dispatch(
                    argparse.Namespace(dispatch=str(dispatch_path), receipt=str(receipt_path), schema_only=False)
                )
        else:
            receipt_finalization["status"] = "missing_receipt" if final_status == "completed" else "turn_not_completed"
            verification = verify_dispatch(
                argparse.Namespace(dispatch=str(dispatch_path), receipt=str(receipt_path), schema_only=False)
            )
        if final_status == "completed" and verification.get("status") != "pass":
            issue_codes = [
                str(item.get("code") or "")
                for item in verification.get("issues", [])
                if isinstance(item, dict) and item.get("code")
            ]
            suffix = f": {', '.join(issue_codes[:5])}" if issue_codes else ""
            state["failure_reason"] = "dispatch receipt verification failed" + suffix
            final_status = "failed"
            atomic_write_json(manifest_path, manifest(final_status, completed_at=completed_at))
        return {
            "schema_version": "oag_thread_worker_result.v1",
            "status": "pass" if final_status == "completed" and verification.get("status") == "pass" else "fail",
            "dispatch_id": dispatch["dispatch_id"],
            "thread_id": state["thread_id"],
            "turn_ids": state["turn_ids"],
            "manifest_path": project_rel(manifest_path),
            "event_log_path": project_rel(event_path),
            "token_usage": state["usage"],
            "warning_sent": state["warning_sent"],
            "budget_warning_observed": state["budget_warning_observed"],
            "budget_max_observed": state["budget_max_observed"],
            "budget_exceeded": state["budget_exceeded"],
            "token_budget_mode": token_budget_mode,
            "subagent_activity_count": state["subagent_activity_count"],
            "failure_reason": state["failure_reason"],
            "role_definition": {
                key: value
                for key, value in role_definition.items()
                if key not in {"developer_instructions", "common_preamble"}
            },
            "receipt_finalization": receipt_finalization,
            "verification": verification,
        }
    finally:
        if client is not None:
            client.close()
        event_log.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run an OAG dispatch in a fresh thread-only Codex App Server worker.")
    parser.add_argument("--dispatch", required=True)
    task_group = parser.add_mutually_exclusive_group(required=True)
    task_group.add_argument("--task")
    task_group.add_argument("--task-file")
    parser.add_argument("--model")
    parser.add_argument("--effort", choices=["none", "minimal", "low", "medium", "high", "xhigh"])
    parser.add_argument("--sandbox", choices=["read-only", "workspace-write", "danger-full-access"])
    parser.add_argument("--timeout-seconds", type=int, default=1800)
    parser.add_argument(
        "--token-budget-mode",
        choices=["enforce", "observe"],
        help="Enforce dispatch token guards, or record thresholds as telemetry without steering or interruption.",
    )
    parser.add_argument("--app-server-command", default="codex app-server")
    parser.add_argument("--resume", action="store_true", help="Resume the failed/interrupted manifest thread within resume_limit and remaining budget.")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        result = run_worker(args)
    except Exception as exc:
        result = {
            "schema_version": "oag_thread_worker_result.v1",
            "status": "fail",
            "failure_reason": str(exc),
        }
    print(json.dumps(result, indent=2, sort_keys=True) if args.json else f"{result['status'].upper()} oag thread worker")
    return 0 if result.get("status") == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
