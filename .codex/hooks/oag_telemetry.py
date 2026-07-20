#!/usr/bin/env python3
"""Privacy-safe correlation events joining Codex OTEL to OAG evidence."""

from __future__ import annotations

import hashlib
import json
import os
import re
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CORRELATION_LOG = Path(
    os.environ.get("OAG_TELEMETRY_CORRELATION_CACHE")
    or ROOT / ".cache" / "otel" / "oag-executions.jsonl"
)
RECEIPT_RE = re.compile(r"OAG_EVIDENCE_RECORDED:\s*(\S+)")


def utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _text(payload: dict[str, Any], key: str) -> str:
    return str(payload.get(key) or "").strip()


def execution_id(payload: dict[str, Any]) -> str:
    parts = [
        _text(payload, "cwd"),
        _text(payload, "session_id"),
        _text(payload, "agent_id"),
        _text(payload, "agent_type"),
    ]
    return "oag-exec-" + hashlib.sha256("::".join(parts).encode("utf-8")).hexdigest()[:20]


def _append_jsonl(path: Path, value: dict[str, Any]) -> None:
    data = (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        try:
            os.write(fd, data)
        finally:
            os.close(fd)
    except Exception:
        # Telemetry must never block an OAG or Codex workflow.
        return


def _receipt_metadata(payload: dict[str, Any]) -> dict[str, Any]:
    message = _text(payload, "last_assistant_message")
    match = RECEIPT_RE.search(message)
    if not match:
        return {}
    raw_path = match.group(1)
    if Path(raw_path).is_absolute():
        return {}
    cwd = Path(_text(payload, "cwd") or ".").expanduser().resolve()
    receipt = (cwd / raw_path).resolve()
    try:
        receipt.relative_to(cwd)
        value = json.loads(receipt.read_text(encoding="utf-8"))
    except Exception:
        return {"receipt_path": raw_path}
    if not isinstance(value, dict):
        return {"receipt_path": raw_path}
    result: dict[str, Any] = {"receipt_path": raw_path}
    for key in (
        "dispatch_id",
        "dispatch_path",
        "ip_id",
        "role_name",
        "stage",
        "status",
        "shard_scope",
        "owned_obligations",
        "contracts",
        "evidence_outputs",
        "wavefront_run_id",
        "task_id",
        "ownership_mode",
        "mission_id",
        "action_id",
        "execution_kind",
        "thread_id",
        "execution_manifest_path",
    ):
        if key in value:
            result[key] = value[key]
    fingerprint_source = value.get("output_hashes")
    if not isinstance(fingerprint_source, dict) or not fingerprint_source:
        fingerprint_source = {
            "changed_paths": value.get("changed_paths", []),
            "evidence_outputs": value.get("evidence_outputs", []),
        }
    encoded = json.dumps(fingerprint_source, sort_keys=True, separators=(",", ":")).encode("utf-8")
    result["content_fingerprint"] = "sha256:" + hashlib.sha256(encoded).hexdigest()

    dispatch_ref = str(value.get("dispatch_path") or "").strip()
    dispatch_path = (cwd / dispatch_ref).resolve() if dispatch_ref and not Path(dispatch_ref).is_absolute() else None
    try:
        if dispatch_path is None:
            return result
        dispatch_path.relative_to(cwd)
        dispatch = json.loads(dispatch_path.read_text(encoding="utf-8"))
    except Exception:
        return result
    if not isinstance(dispatch, dict):
        return result
    budget = dispatch.get("execution_budget") if isinstance(dispatch.get("execution_budget"), dict) else {}
    context = dispatch.get("context_contract") if isinstance(dispatch.get("context_contract"), dict) else {}
    integrity = dispatch.get("dispatch_integrity") if isinstance(dispatch.get("dispatch_integrity"), dict) else {}
    for key in ("complexity", "max_total_tokens", "warning_total_tokens", "max_review_attempts", "model_tier"):
        if key in budget:
            result[key] = budget[key]
    for key in ("fork_turns", "input_mode", "max_direct_source_files", "repeat_review_policy"):
        if key in context:
            result[key] = context[key]
    if integrity.get("scope_hash"):
        result["dispatch_scope_hash"] = integrity["scope_hash"]
    baseline = dispatch.get("baseline") if isinstance(dispatch.get("baseline"), dict) else {}
    baseline_hashes = baseline.get("file_hashes") if isinstance(baseline.get("file_hashes"), dict) else {}
    allowed_outputs = [str(item).strip("/") for item in dispatch.get("allowed_write_paths", []) if isinstance(item, str)]
    target_hashes = {
        str(path): digest
        for path, digest in baseline_hashes.items()
        if isinstance(path, str)
        and isinstance(digest, str)
        and "/knowledge/" not in f"/{path}/"
        and "/ontology/runs/" not in f"/{path}/"
        and not any(path.strip("/") == output or path.strip("/").startswith(output.rstrip("/") + "/") for output in allowed_outputs)
    }
    if target_hashes:
        encoded_target = json.dumps(target_hashes, sort_keys=True, separators=(",", ":")).encode("utf-8")
        result["review_target_fingerprint"] = "sha256:" + hashlib.sha256(encoded_target).hexdigest()
    return result


def append_execution_event(
    payload: dict[str, Any],
    phase: str,
    *,
    gate_outcome: str = "",
    gate_reason: str = "",
) -> None:
    agent_id = _text(payload, "agent_id")
    session_id = _text(payload, "session_id")
    conversation_ids = list(dict.fromkeys(item for item in (agent_id, session_id) if item))
    event: dict[str, Any] = {
        "schema_version": "oag_otel_correlation_event.v1",
        "created_at": utc_now(),
        "phase": phase,
        "execution_id": execution_id(payload),
        "primary_conversation_id": agent_id or session_id,
        "conversation_ids": conversation_ids,
        "parent_session_id": session_id if agent_id else "",
        "agent_id": agent_id,
        "agent_type": _text(payload, "agent_type") or "main",
        "model_from_hook": _text(payload, "model"),
        "cwd": _text(payload, "cwd"),
        "permission_mode": _text(payload, "permission_mode"),
        "gate_outcome": gate_outcome,
        "execution_kind": os.environ.get("OAG_EXECUTION_KIND") or ("subagent" if agent_id else "main"),
    }
    for env_name, event_name in (
        ("OAG_DISPATCH_ID", "dispatch_id"),
        ("OAG_DISPATCH_PATH", "dispatch_path"),
        ("OAG_THREAD_EXECUTION_MANIFEST", "execution_manifest_path"),
    ):
        value = os.environ.get(env_name, "").strip()
        if value:
            event[event_name] = value
    if gate_reason:
        event["gate_reason"] = gate_reason[:1000]
    if phase.startswith("subagent_stop"):
        event.update(_receipt_metadata(payload))
    _append_jsonl(CORRELATION_LOG, event)
