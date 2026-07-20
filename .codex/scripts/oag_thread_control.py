#!/usr/bin/env python3
"""Inspect an OAG worker task and queue audited steering for its owning runtime."""

from __future__ import annotations

import argparse
import json
import os
import shlex
import sys
import time
import uuid
from pathlib import Path
from typing import Any

from oag_dispatch_support import load_json, resolve_project_path
from oag_thread_worker import (
    AppServerClient,
    CONTROL_DIRECTION,
    CONTROL_SCHEMA_VERSION,
)


JsonObject = dict[str, Any]


class NullEventLog:
    def append(self, direction: str, message: Any) -> None:
        del direction, message


def utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def manifest_path(raw: str) -> Path:
    candidate = Path(raw).expanduser()
    return candidate.resolve() if candidate.is_absolute() else resolve_project_path(raw)


def load_manifest(raw: str) -> tuple[Path, JsonObject]:
    path = manifest_path(raw)
    payload = load_json(path)
    if not isinstance(payload, dict) or payload.get("schema_version") != "oag_thread_execution.v1":
        raise ValueError(f"not an OAG thread execution manifest: {path}")
    return path, payload


def event_path(manifest: JsonObject) -> Path:
    reference = str(manifest.get("event_log_path") or "")
    if not reference:
        raise ValueError("manifest has no event_log_path")
    return resolve_project_path(reference)


def read_task(thread_id: str, command: str) -> JsonObject:
    argv = shlex.split(command)
    if not argv:
        raise ValueError("app server command is empty")
    client = AppServerClient(argv, cwd=resolve_project_path("."), env=os.environ.copy(), event_log=NullEventLog())
    try:
        client.request(
            "initialize",
            {"clientInfo": {"name": "oag-thread-control", "version": "1.0"}, "capabilities": {}},
            timeout=20,
        )
        client.notify("initialized", {})
        return client.request(
            "thread/read",
            {"threadId": thread_id, "includeTurns": True},
            timeout=30,
        )
    finally:
        client.close()


def compact_task(result: JsonObject, *, message_limit: int) -> JsonObject:
    thread = result.get("thread") if isinstance(result.get("thread"), dict) else {}
    turns = thread.get("turns") if isinstance(thread.get("turns"), list) else []
    latest = turns[-1] if turns and isinstance(turns[-1], dict) else {}
    items = latest.get("items") if isinstance(latest.get("items"), list) else []
    messages: list[JsonObject] = []
    for item in items:
        if not isinstance(item, dict) or item.get("type") != "agentMessage":
            continue
        text = item.get("text")
        if isinstance(text, str):
            messages.append({"id": str(item.get("id") or ""), "text": text})
    return {
        "thread_id": str(thread.get("id") or ""),
        "persisted_thread_status": thread.get("status"),
        "thread_updated_at": thread.get("updatedAt"),
        "turn_count": len(turns),
        "latest_turn_id": str(latest.get("id") or ""),
        "persisted_latest_turn_status": str(latest.get("status") or ""),
        "latest_turn_error": latest.get("error"),
        "latest_agent_messages": messages[-message_limit:],
    }


def status(args: argparse.Namespace) -> JsonObject:
    path, manifest = load_manifest(args.manifest)
    thread_id = str(manifest.get("thread_id") or "")
    if not thread_id:
        raise ValueError("manifest has no thread_id")
    task = compact_task(read_task(thread_id, args.app_server_command), message_limit=args.message_limit)
    running = manifest.get("status") == "running"
    control_capable = manifest.get("control_protocol") == CONTROL_SCHEMA_VERSION
    persisted_turn = str(task.get("persisted_latest_turn_status") or "")
    coherence = "coherent"
    if running and persisted_turn in {"interrupted", "failed"}:
        coherence = "active_turn_owned_by_another_app_server"
    return {
        "schema_version": "oag_thread_status.v1",
        "status": "pass",
        "manifest_path": str(path),
        "live_status": str(manifest.get("status") or ""),
        "live_status_source": "execution_manifest",
        "updated_at": manifest.get("updated_at"),
        "model": manifest.get("model"),
        "reasoning_effort": manifest.get("reasoning_effort"),
        "token_usage": manifest.get("token_usage"),
        "failure_reason": str(manifest.get("failure_reason") or ""),
        "steering_supported": running and control_capable,
        "control_protocol": str(manifest.get("control_protocol") or ""),
        "steering_request_count": int(manifest.get("steering_request_count") or 0),
        "steering_applied_count": int(manifest.get("steering_applied_count") or 0),
        "steering_rejected_count": int(manifest.get("steering_rejected_count") or 0),
        "status_coherence": coherence,
        "task": task,
    }


def existing_control_ids(path: Path) -> set[str]:
    values: set[str] = set()
    if not path.is_file():
        return values
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(row, dict) or row.get("direction") != CONTROL_DIRECTION:
            continue
        message = row.get("message") if isinstance(row.get("message"), dict) else {}
        request_id = str(message.get("request_id") or "")
        if request_id:
            values.add(request_id)
    return values


def append_row(path: Path, row: JsonObject) -> None:
    encoded = (json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
    descriptor = os.open(path, os.O_WRONLY | os.O_APPEND)
    try:
        written = os.write(descriptor, encoded)
        if written != len(encoded):
            raise OSError(f"short event-log append: {written}/{len(encoded)}")
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def steer(args: argparse.Namespace) -> JsonObject:
    path, manifest = load_manifest(args.manifest)
    if manifest.get("status") != "running":
        raise ValueError("steering requires a running worker manifest")
    if manifest.get("control_protocol") != CONTROL_SCHEMA_VERSION:
        raise ValueError("running worker does not advertise the steering control protocol")
    thread_id = str(manifest.get("thread_id") or "")
    turn_ids = manifest.get("turn_ids") if isinstance(manifest.get("turn_ids"), list) else []
    active_turn = str(turn_ids[-1] if turn_ids else "")
    expected_turn = str(args.expected_turn_id or active_turn)
    if not thread_id or not expected_turn:
        raise ValueError("manifest has no active thread/turn identity")
    message = str(args.message or "").strip()
    if not message:
        raise ValueError("steering message is empty")
    if len(message) > 12000:
        raise ValueError("steering message exceeds 12000 characters")
    request_id = str(args.request_id or f"STEER_{uuid.uuid4().hex.upper()}")
    events = event_path(manifest)
    if request_id in existing_control_ids(events):
        raise ValueError(f"duplicate steering request_id: {request_id}")
    control = {
        "schema_version": CONTROL_SCHEMA_VERSION,
        "request_id": request_id,
        "method": "turn/steer",
        "thread_id": thread_id,
        "expected_turn_id": expected_turn,
        "input": message,
    }
    append_row(
        events,
        {"created_at": utc_now(), "direction": CONTROL_DIRECTION, "message": control},
    )
    return {
        "schema_version": "oag_thread_control_result.v1",
        "status": "queued",
        "manifest_path": str(path),
        "event_log_path": str(events),
        "request_id": request_id,
        "thread_id": thread_id,
        "expected_turn_id": expected_turn,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Inspect or steer an OAG App Server worker task.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    inspect = subparsers.add_parser("status", help="Combine live manifest state with task thread/read history.")
    inspect.add_argument("--manifest", required=True)
    inspect.add_argument("--message-limit", type=int, default=5)
    inspect.add_argument("--app-server-command", default="codex app-server")
    inspect.add_argument("--json", action="store_true")

    control = subparsers.add_parser("steer", help="Queue steering for the App Server process that owns the live turn.")
    control.add_argument("--manifest", required=True)
    control.add_argument("--message", required=True)
    control.add_argument("--expected-turn-id")
    control.add_argument("--request-id")
    control.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        result = status(args) if args.command == "status" else steer(args)
        return_code = 0
    except (OSError, RuntimeError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
        result = {"schema_version": "oag_thread_control_result.v1", "status": "fail", "error": str(exc)}
        return_code = 1
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(json.dumps(result, sort_keys=True))
    return return_code


if __name__ == "__main__":
    raise SystemExit(main())
