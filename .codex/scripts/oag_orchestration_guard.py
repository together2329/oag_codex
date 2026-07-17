#!/usr/bin/env python3
"""Audit and route OAG wavefront orchestration hazards."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path
from typing import Any

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import oag_paths  # noqa: E402
from oag_run_control_common import JsonObject, age_seconds, collect_run_state, issue, parse_utc, utc_now, write_json  # noqa: E402
from oag_wavefront import cmd_record  # noqa: E402


AUDIT_SCHEMA_VERSION = "oag_orchestration_guard_audit.v1"
ABORT_SCHEMA_VERSION = "oag_orchestration_guard_abort.v1"
FALLBACK_SCHEMA_VERSION = "oag_gate_fallback_plan.v1"
TERMINAL_ABORT_STATUSES = {"blocked", "failed", "inconclusive"}
RESOLVED_TASK_STATUSES = {"handoff_pass", "closed", "waived"}
TERMINAL_RECEIPT_STATUSES = {
    "HANDOFF_PASS",
    "STATIC_HANDOFF_PASS",
    "RTL_HANDOFF_PASS",
    "FAIL",
    "BLOCKED",
    "INCONCLUSIVE",
}
GATE_REVIEWER_ID = "oag-gate-reviewer"
DEFAULT_PROGRESS_SECONDS = 600
DEFAULT_PARENT_WAIT_CYCLES = 3


def _load_json(path: Path) -> JsonObject:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _state_dirs(ip_dir: Path, rel: str) -> list[Path]:
    candidates = [ip_dir / ".oag" / rel, ip_dir / rel]
    return [candidate for candidate in candidates if candidate.is_dir()]


def _iter_run_dirs(ip_dir: Path, run_id: str = "") -> list[Path]:
    dirs: list[Path] = []
    for root in _state_dirs(ip_dir, "ontology/runs"):
        if run_id:
            candidate = root / run_id
            if candidate.is_dir():
                dirs.append(candidate)
        else:
            dirs.extend(path for path in sorted(root.iterdir()) if path.is_dir())
    return dirs


def _find_subagent_receipts(ip_dir: Path) -> list[Path]:
    receipts: list[Path] = []
    for root in _state_dirs(ip_dir, "knowledge/subagents"):
        receipts.extend(sorted(root.glob("*.json")))
    return receipts


def _find_dispatch(ip_dir: Path, dispatch_id: str) -> tuple[Path | None, JsonObject]:
    if not dispatch_id:
        return None, {}
    for root in _state_dirs(ip_dir, "knowledge/dispatches"):
        path = root / f"{dispatch_id}.json"
        if path.is_file():
            return path, _load_json(path)
    return None, {}


def _rel_to_ip(ip_dir: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(ip_dir.resolve()).as_posix()
    except ValueError:
        return str(path)


def _project_rel(path: Path) -> str:
    root = oag_paths.project_root()
    if root is not None:
        try:
            return path.resolve().relative_to(root.resolve()).as_posix()
        except ValueError:
            pass
    return str(path)


def _is_dedicated_gate_reviewer(dispatch: JsonObject) -> bool:
    identities = {
        str(dispatch.get("agent_type") or "").strip(),
        str(dispatch.get("role_name") or "").strip(),
        str(dispatch.get("registered_id") or "").strip(),
    }
    return GATE_REVIEWER_ID in identities


def _latest_review_events(ip_dir: Path, run_id: str, *, now: dt.datetime) -> dict[str, dt.datetime]:
    path = oag_paths.legacy_or_hidden(ip_dir, f"knowledge/wavefront/{run_id}/events.jsonl")
    if not path.is_file():
        return {}
    latest: dict[str, dt.datetime] = {}
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return {}
    for raw in lines:
        try:
            event = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if (
            not isinstance(event, dict)
            or event.get("schema_version") != "oag_wavefront_event.v1"
            or str(event.get("run_id") or "") != run_id
            or str(event.get("event") or "") != "recorded"
            or str(event.get("status") or "") != "review_pending"
        ):
            continue
        task_id = str(event.get("task_id") or "").strip()
        recorded_at = parse_utc(event.get("created_at"))
        if not task_id or recorded_at is None or recorded_at > now:
            continue
        previous = latest.get(task_id)
        if previous is None or recorded_at > previous:
            latest[task_id] = recorded_at
    return latest


def _live_active_dispatches(ip_dir: Path, *, stale_seconds: int) -> dict[tuple[str, str], str]:
    now = parse_utc(utc_now())
    if now is None:
        return {}
    live: dict[tuple[str, str], str] = {}
    for run_dir in _iter_run_dirs(ip_dir):
        graph = _load_json(run_dir / "wavefront_task_graph.json")
        review_events = _latest_review_events(ip_dir, run_dir.name, now=now)
        tasks = graph.get("tasks") if isinstance(graph.get("tasks"), list) else []
        for task in tasks:
            if not isinstance(task, dict):
                continue
            status = str(task.get("status") or "")
            task_id = str(task.get("task_id") or "").strip()
            if not task_id:
                continue
            if status == "claimed":
                deadline = parse_utc(task.get("heartbeat_deadline_at"))
                if deadline is None or deadline <= now:
                    continue
            elif status == "review_pending":
                claimed_at = parse_utc(task.get("claimed_at"))
                if claimed_at is None:
                    continue
                progress = [
                    candidate
                    for candidate in (parse_utc(task.get("recorded_at")), review_events.get(task_id))
                    if candidate is not None and claimed_at <= candidate <= now
                ]
                if not progress or (now - max(progress)).total_seconds() >= stale_seconds:
                    continue
            else:
                continue
            live[(run_dir.name, task_id)] = str(task.get("dispatch_id") or "").strip()
    return live


def _lock_has_live_task(lock: JsonObject, live: dict[tuple[str, str], str]) -> bool:
    key = (str(lock.get("run_id") or "").strip(), str(lock.get("task_id") or "").strip())
    if key not in live:
        return False
    task_dispatch = live[key]
    lock_dispatch = str(lock.get("dispatch_id") or "").strip()
    return not (task_dispatch and lock_dispatch and task_dispatch != lock_dispatch)


def _gate_lock_candidates(ip_dir: Path, locks: list[JsonObject], *, stale_seconds: int) -> list[JsonObject]:
    rows: list[JsonObject] = []
    for lock in locks:
        if not isinstance(lock, dict):
            continue
        age = lock.get("age_seconds")
        if not isinstance(age, (int, float)) or age < stale_seconds:
            continue
        dispatch_id = str(lock.get("dispatch_id") or "").strip()
        dispatch_path, dispatch = _find_dispatch(ip_dir, dispatch_id)
        if not dispatch_path or not _is_dedicated_gate_reviewer(dispatch):
            continue
        rows.append(
            {
                "run_id": lock.get("run_id") or "",
                "task_id": lock.get("task_id") or "",
                "dispatch_id": dispatch_id,
                "age_seconds": int(age),
                "claimed_at": lock.get("claimed_at") or "",
                "claimed_by": lock.get("claimed_by") or "",
                "lock_path": lock.get("path") or "",
                "dispatch_path": _rel_to_ip(ip_dir, dispatch_path) if dispatch_path else "",
                "dispatch_agent_type": dispatch.get("agent_type") or "",
                "dispatch_stage": dispatch.get("stage") or "",
            }
        )
    return rows


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item)]


def _ip_local_rel(ip_dir: Path, raw: Any) -> str:
    text = str(raw or "").strip()
    if not text:
        return ""
    path = Path(text).expanduser()
    if path.is_absolute():
        try:
            return path.resolve().relative_to(ip_dir.resolve()).as_posix()
        except ValueError:
            return ""
    normalized = text.strip("/")
    ip_name = ip_dir.name.strip("/")
    if normalized == ip_name:
        return ""
    ip_prefix = f"{ip_name}/"
    if normalized.startswith(ip_prefix):
        return normalized[len(ip_prefix):]
    return normalized


def _recent_path_evidence(ip_dir: Path, raw: Any, *, claimed_at: Any) -> str:
    claimed = parse_utc(claimed_at)
    if claimed is None:
        return ""
    rel = _ip_local_rel(ip_dir, raw)
    if not rel:
        return ""
    try:
        path = oag_paths.legacy_or_hidden(ip_dir, rel)
    except ValueError:
        return ""
    cutoff = claimed.timestamp()
    try:
        if path.is_file() and path.stat().st_size > 0 and path.stat().st_mtime >= cutoff:
            return _rel_to_ip(ip_dir, path)
        if path.is_dir():
            for item in path.rglob("*"):
                if item.is_file() and item.stat().st_size > 0 and item.stat().st_mtime >= cutoff:
                    return _rel_to_ip(ip_dir, item)
    except OSError:
        return ""
    return ""


def _progress_evidence(ip_dir: Path, task: JsonObject, dispatch: JsonObject, *, claimed_at: Any) -> list[str]:
    evidence: list[str] = []
    claimed = parse_utc(claimed_at)
    heartbeat = parse_utc(task.get("heartbeat_at"))
    if claimed is not None and heartbeat is not None and heartbeat >= claimed:
        evidence.append(f"heartbeat:{task.get('heartbeat_at')}")

    receipt_paths = [task.get("receipt_path"), dispatch.get("receipt_path")]
    for raw_receipt in receipt_paths:
        receipt_evidence = _recent_path_evidence(ip_dir, raw_receipt, claimed_at=claimed_at)
        if receipt_evidence:
            evidence.append(f"receipt:{receipt_evidence}")

    receipt_parent_rels = {
        str(Path(rel).parent).strip("/")
        for rel in (_ip_local_rel(ip_dir, raw) for raw in receipt_paths)
        if rel
    }
    owned_paths = [
        *_string_list(task.get("allowed_write_paths")),
        *_string_list(task.get("shared_artifacts")),
        *_string_list(dispatch.get("allowed_write_paths")),
    ]
    for raw_path in owned_paths:
        rel = _ip_local_rel(ip_dir, raw_path).strip("/")
        if not rel or rel in receipt_parent_rels:
            continue
        owned_evidence = _recent_path_evidence(ip_dir, rel, claimed_at=claimed_at)
        if owned_evidence:
            evidence.append(f"owned_path:{owned_evidence}")
    return sorted(set(evidence))


def detect_claimed_tasks_without_progress(ip_dir: Path, *, run_id: str = "", progress_seconds: int = DEFAULT_PROGRESS_SECONDS) -> list[JsonObject]:
    rows: list[JsonObject] = []
    for run_dir in _iter_run_dirs(ip_dir, run_id):
        graph = _load_json(run_dir / "wavefront_task_graph.json")
        locks = _load_json(run_dir / "ownership_locks.json")
        lock_by_task = {
            str(lock.get("task_id") or ""): lock
            for lock in locks.get("locks", []) if isinstance(lock, dict)
        } if isinstance(locks.get("locks"), list) else {}
        for task in graph.get("tasks", []) if isinstance(graph.get("tasks"), list) else []:
            if not isinstance(task, dict) or str(task.get("status") or "") != "claimed":
                continue
            task_id = str(task.get("task_id") or "")
            lock = lock_by_task.get(task_id, {})
            claimed_at = task.get("claimed_at") or lock.get("claimed_at")
            claimed_age = age_seconds(claimed_at)
            if claimed_age is None or claimed_age < progress_seconds:
                continue
            dispatch_id = str(task.get("dispatch_id") or lock.get("dispatch_id") or "").strip()
            dispatch_path, dispatch = _find_dispatch(ip_dir, dispatch_id)
            evidence = _progress_evidence(ip_dir, task, dispatch, claimed_at=claimed_at)
            if evidence:
                continue
            rows.append(
                {
                    "run_id": run_dir.name,
                    "task_id": task_id,
                    "dispatch_id": dispatch_id,
                    "dispatch_path": _rel_to_ip(ip_dir, dispatch_path) if dispatch_path else "",
                    "age_seconds": int(claimed_age),
                    "claimed_at": claimed_at or "",
                    "agent_type": dispatch.get("agent_type") or task.get("agent_type") or "",
                    "stage": dispatch.get("stage") or task.get("phase") or "",
                    "receipt_path": dispatch.get("receipt_path") or task.get("receipt_path") or "",
                    "heartbeat_command": (
                        "python3 .codex/scripts/oag_wavefront.py heartbeat "
                        f"--ip-dir {_project_rel(ip_dir)} --run-id {run_dir.name} --task-id {task_id} "
                        '--message "<phase>" --json'
                    ),
                }
            )
    return rows


def audit(ip_dir: Path, *, run_id: str = "", stale_seconds: int = 1800, progress_seconds: int = DEFAULT_PROGRESS_SECONDS) -> JsonObject:
    ip_dir = oag_paths.ip_root(ip_dir)
    state = collect_run_state(ip_dir)
    issues: list[dict[str, str]] = []
    recommendations: list[JsonObject] = []

    live_tasks = _live_active_dispatches(ip_dir, stale_seconds=stale_seconds)
    stale_locks: list[JsonObject] = []
    for lock in state.get("wavefront", {}).get("active_locks", []):
        age = lock.get("age_seconds")
        if (
            isinstance(age, (int, float))
            and age >= stale_seconds
            and not _lock_has_live_task(lock, live_tasks)
        ):
            stale_locks.append(lock)
            issues.append(
                issue(
                    "STALE_ACTIVE_LOCK",
                    f"active lock is older than {stale_seconds} seconds",
                    f"{lock.get('run_id', '')}/{lock.get('task_id', '')}",
                )
            )
    if state.get("wavefront", {}).get("active_lock_count", 0):
        recommendations.append(
            {
                "id": "do-not-open-new-dispatch",
                "recommended": True,
                "description": "Do not create a replacement dispatch until active locks are released or explicitly aborted.",
            }
        )
    if stale_locks:
        recommendations.append(
            {
                "id": "request-minimal-receipt",
                "recommended": True,
                "description": "Ask the child for a bounded receipt with status, changed paths, commands, and blockers.",
            }
        )
    gate_locks = _gate_lock_candidates(ip_dir, stale_locks, stale_seconds=stale_seconds)
    for row in gate_locks:
        issues.append(
            issue(
                "GATE_REVIEWER_STUCK",
                "stale gate-review lock detected; stop retrying the dedicated gate reviewer and use custom-reviewer fallback from a fresh dispatch",
                f"{row.get('run_id', '')}/{row.get('task_id', '')}",
            )
        )
    if gate_locks:
        recommendations.insert(
            0,
            {
                "id": "gate-reviewer-custom-fallback",
                "recommended": True,
                "description": "Abort the stale gate-review task as inconclusive, quarantine late receipts from that dispatch, and retry the final gate as oag-custom-reviewer from a fresh baseline.",
            },
        )

    no_progress = detect_claimed_tasks_without_progress(ip_dir, run_id=run_id, progress_seconds=progress_seconds)
    for row in no_progress:
        issues.append(
            issue(
                "CLAIMED_TASK_NO_PROGRESS_EVIDENCE",
                f"claimed task is older than {progress_seconds} seconds and has no heartbeat, receipt, or owned-path evidence",
                f"{row.get('run_id', '')}/{row.get('task_id', '')}",
            )
        )
    if no_progress:
        recommendations.insert(
            0,
            {
                "id": "record-heartbeat-or-route-task",
                "recommended": True,
                "description": f"Apply the parent patience protocol: keep an active child through at least {DEFAULT_PARENT_WAIT_CYCLES} native wait cycles, ask once for a bounded heartbeat/receipt/status response after the first silent cycle, and only then record INCONCLUSIVE/BLOCKED before replacement if no progress evidence appears.",
            },
        )

    late_receipts = detect_late_receipts(ip_dir, run_id=run_id)
    for row in late_receipts:
        issues.append(issue("LATE_RECEIPT_AFTER_ABORT", "receipt exists after task abort marker and is not a valid handoff", row["receipt_path"]))
    repeated = detect_repeated_blockers(ip_dir, run_id=run_id)
    for row in repeated:
        issues.append(issue("REPEATED_BLOCKER", f"same blocker repeated {row['count']} times", row["key"]))
    if repeated:
        recommendations.append(
            {
                "id": "surface-user-blocker",
                "recommended": True,
                "description": "Stop retry loops and surface the repeated blocker as a user-visible gate or explicit blocked receipt.",
            }
        )
    if not recommendations:
        recommendations.append(
            {
                "id": "continue-normal-wavefront",
                "recommended": True,
                "description": "No orchestration guard hazard was detected.",
            }
        )

    return {
        "schema_version": AUDIT_SCHEMA_VERSION,
        "status": "fail" if issues else "pass",
        "ip": ip_dir.name,
        "run_id": run_id,
        "stale_seconds": stale_seconds,
        "progress_seconds": progress_seconds,
        "parent_min_wait_cycles": DEFAULT_PARENT_WAIT_CYCLES,
        "active_locks": state.get("wavefront", {}).get("active_locks", []),
        "stale_locks": stale_locks,
        "stale_gate_locks": gate_locks,
        "claimed_without_progress": no_progress,
        "late_receipts": late_receipts,
        "repeated_blockers": repeated,
        "issues": issues,
        "recommendations": recommendations,
    }


def gate_fallback_plan(ip_dir: Path, *, run_id: str = "", stale_seconds: int = 900, write: bool = True) -> JsonObject:
    ip_dir = oag_paths.ip_root(ip_dir)
    audit_payload = audit(ip_dir, run_id=run_id, stale_seconds=stale_seconds)
    gate_locks = audit_payload.get("stale_gate_locks") if isinstance(audit_payload.get("stale_gate_locks"), list) else []
    late_receipts = [
        row
        for row in audit_payload.get("late_receipts", [])
        if isinstance(row, dict)
        and _is_dedicated_gate_reviewer(_find_dispatch(ip_dir, str(row.get("dispatch_id") or ""))[1])
    ]
    fallback_actions: list[JsonObject] = []
    for index, row in enumerate(gate_locks, start=1):
        source_task = str(row.get("task_id") or f"GATE_REVIEW_{index}")
        retry_task = f"{source_task}_CUSTOM_RETRY"
        receipt_name = f"{retry_task}_oag_custom_reviewer.json"
        fallback_actions.append(
            {
                "source_run_id": row.get("run_id") or "",
                "source_task_id": source_task,
                "source_dispatch_id": row.get("dispatch_id") or "",
                "abort_status": "inconclusive",
                "fallback_agent_type": "oag-custom-reviewer",
                "retry_task_id": retry_task,
                "receipt_path": f"{ip_dir.name}/knowledge/subagents/{receipt_name}",
                "gate_decision_path": f"{ip_dir.name}/knowledge/gate_reviews/oag_gate_decision.json",
                "commands": {
                    "abort_stale_task": (
                        "python3 .codex/scripts/oag_orchestration_guard.py abort-task "
                        f"--ip-dir {ip_dir.name} --run-id {row.get('run_id') or '<run-id>'} "
                        f"--task-id {source_task} --status inconclusive --json"
                    ),
                    "create_fresh_custom_dispatch": (
                        "python3 .codex/scripts/oag_dispatch.py create "
                        f"--ip-dir {ip_dir.name} --agent-type oag-custom-reviewer --stage gate "
                        f"--receipt-path {ip_dir.name}/knowledge/subagents/{receipt_name} "
                        "--ownership-mode integration_owner "
                        f"--allowed-write-path {ip_dir.name}/knowledge/gate_reviews/oag_gate_decision.json "
                        f"--allowed-write-path {ip_dir.name}/knowledge/subagents/{receipt_name} --json"
                    ),
                    "verify_clean_evidence_first": (
                        "python3 .codex/scripts/oag_cli.py call --json "
                        f"'{{\"tool\":\"oag.check\",\"arguments\":{{\"ip_dir\":\"{ip_dir.name}\"}}}}'"
                    ),
                },
                "policy": [
                    "Do not accept late receipts from the aborted dispatch as a handoff.",
                    "Do not reuse or widen the stale dispatch baseline.",
                    "Use the custom reviewer only to refresh the gate decision and receipt; do not edit RTL, TB, sim, cov, or validation records.",
                ],
            }
        )
    payload: JsonObject = {
        "schema_version": FALLBACK_SCHEMA_VERSION,
        "generated_at": utc_now(),
        "status": "fail" if gate_locks else "pass",
        "ip": ip_dir.name,
        "run_id": run_id,
        "stale_seconds": stale_seconds,
        "hung_gate_locks": gate_locks,
        "late_receipt_quarantine": late_receipts,
        "fallback_actions": fallback_actions,
        "summary": {
            "hung_gate_lock_count": len(gate_locks),
            "late_gate_receipt_count": len(late_receipts),
            "fallback_action_count": len(fallback_actions),
        },
        "audit_status": audit_payload.get("status"),
        "audit_issue_count": len(audit_payload.get("issues", []) if isinstance(audit_payload.get("issues"), list) else []),
    }
    if write:
        path = oag_paths.state_path(ip_dir, "knowledge/operations/gate_fallback_plan.json")
        write_json(path, payload)
        payload["path"] = _rel_to_ip(ip_dir, path)
    return payload


def detect_late_receipts(ip_dir: Path, *, run_id: str = "") -> list[JsonObject]:
    receipts = _find_subagent_receipts(ip_dir)
    receipt_payloads: dict[Path, JsonObject] = {}
    by_dispatch: dict[str, list[Path]] = {}
    for receipt in receipts:
        payload = _load_json(receipt)
        dispatch_id = str(payload.get("dispatch_id") or "").strip()
        receipt_time = parse_utc(payload.get("created_at"))
        receipt_status = str(payload.get("status") or "").strip()
        if (
            payload.get("schema_version") != "oag_subagent_receipt.v1"
            or not dispatch_id
            or receipt_time is None
            or receipt_status not in TERMINAL_RECEIPT_STATUSES
        ):
            continue
        normalized = receipt.resolve()
        receipt_payloads[normalized] = payload
        by_dispatch.setdefault(dispatch_id, []).append(normalized)
    late: list[JsonObject] = []
    for run_dir in _iter_run_dirs(ip_dir, run_id):
        graph = _load_json(run_dir / "wavefront_task_graph.json")
        for task in graph.get("tasks", []) if isinstance(graph.get("tasks"), list) else []:
            if not isinstance(task, dict):
                continue
            abort_marker = task.get("abort_marker") if isinstance(task.get("abort_marker"), dict) else {}
            if not abort_marker:
                continue
            abort_status = str(abort_marker.get("status") or "").strip()
            abort_time = parse_utc(abort_marker.get("recorded_at"))
            marker_dispatch_id = str(abort_marker.get("dispatch_id") or "").strip()
            if abort_status not in TERMINAL_ABORT_STATUSES or abort_time is None or not marker_dispatch_id:
                continue
            candidate_receipts = list(by_dispatch.get(marker_dispatch_id, []))
            receipt_paths = [abort_marker.get("receipt_path")]
            if str(task.get("dispatch_id") or "").strip() == marker_dispatch_id:
                receipt_paths.append(task.get("receipt_path"))
            for raw_receipt_path in receipt_paths:
                receipt_path = str(raw_receipt_path or "").strip()
                if not receipt_path:
                    continue
                try:
                    candidate = oag_paths.legacy_or_hidden(ip_dir, receipt_path).resolve()
                except ValueError:
                    continue
                if not candidate.is_file():
                    continue
                payload = receipt_payloads.get(candidate) or _load_json(candidate)
                if str(payload.get("dispatch_id") or "").strip() != marker_dispatch_id:
                    continue
                receipt_time = parse_utc(payload.get("created_at"))
                receipt_status = str(payload.get("status") or "").strip()
                if (
                    payload.get("schema_version") != "oag_subagent_receipt.v1"
                    or receipt_time is None
                    or receipt_status not in TERMINAL_RECEIPT_STATUSES
                ):
                    continue
                receipt_payloads[candidate] = payload
                candidate_receipts.append(candidate)
            for receipt in sorted(set(candidate_receipts)):
                payload = receipt_payloads.get(receipt) or _load_json(receipt)
                if str(payload.get("dispatch_id") or "").strip() != marker_dispatch_id:
                    continue
                receipt_time = parse_utc(payload.get("created_at"))
                # Equal second-resolution timestamps do not prove that the receipt followed the abort.
                if receipt_time is None or receipt_time <= abort_time:
                    continue
                late.append(
                    {
                        "run_id": run_dir.name,
                        "task_id": task.get("task_id") or "",
                        "dispatch_id": marker_dispatch_id,
                        "current_dispatch_id": str(task.get("dispatch_id") or "").strip(),
                        "task_status": str(task.get("status") or "").strip(),
                        "abort_status": abort_status,
                        "abort_recorded_at": str(abort_marker.get("recorded_at") or ""),
                        "receipt_status": str(payload.get("status") or "").strip(),
                        "receipt_created_at": str(payload.get("created_at") or ""),
                        "receipt_path": _rel_to_ip(ip_dir, receipt),
                    }
                )
    return late


def detect_repeated_blockers(ip_dir: Path, *, run_id: str = "", threshold: int = 3) -> list[JsonObject]:
    counts: dict[str, int] = {}
    latest: dict[str, str] = {}
    for run_dir in _iter_run_dirs(ip_dir, run_id):
        graph = _load_json(run_dir / "wavefront_task_graph.json")
        if str(graph.get("closed_at") or "").strip():
            continue
        raw_tasks = graph.get("tasks") if isinstance(graph.get("tasks"), list) else []
        tasks = {
            str(task.get("task_id") or "").strip(): task
            for task in raw_tasks
            if isinstance(task, dict) and str(task.get("task_id") or "").strip()
        }
        events_path = oag_paths.legacy_or_hidden(ip_dir, f"knowledge/wavefront/{run_dir.name}/events.jsonl")
        if not events_path.is_file():
            continue
        for line in events_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(event, dict):
                continue
            task_id = str(event.get("task_id") or "").strip()
            task = tasks.get(task_id)
            if task is None or str(task.get("status") or "").strip() in RESOLVED_TASK_STATUSES:
                continue
            status = str(event.get("status") or "")
            if status not in TERMINAL_ABORT_STATUSES and event.get("event") != "blocked":
                continue
            event_time = parse_utc(event.get("created_at"))
            if event_time is None:
                continue
            details = event.get("details") if isinstance(event.get("details"), dict) else {}
            raw_issues = details.get("issues") if isinstance(details.get("issues"), list) else []
            event_keys: set[str] = set()
            if raw_issues:
                for item in raw_issues:
                    if not isinstance(item, dict):
                        continue
                    event_keys.add(f"{run_dir.name}:{task_id}:{item.get('code', '')}:{item.get('path', '')}")
            else:
                event_keys.add(f"{run_dir.name}:{task_id}:{status or event.get('event')}")
            created_at = str(event.get("created_at") or "")
            for key in event_keys:
                counts[key] = counts.get(key, 0) + 1
                previous_time = parse_utc(latest.get(key))
                if previous_time is None or event_time > previous_time:
                    latest[key] = created_at
    return [
        {"key": key, "count": count, "latest_at": latest.get(key, "")}
        for key, count in sorted(counts.items())
        if count >= threshold
    ]


def abort_task(ip_dir: Path, *, run_id: str, task_id: str, status: str, receipt: str = "") -> JsonObject:
    if status not in TERMINAL_ABORT_STATUSES:
        return {"schema_version": ABORT_SCHEMA_VERSION, "status": "fail", "issues": [issue("ABORT_STATUS_INVALID", f"status must be one of {sorted(TERMINAL_ABORT_STATUSES)}")]}
    args = argparse.Namespace(
        ip_dir=str(ip_dir),
        run_id=run_id,
        task_id=task_id,
        status=status,
        barrier_output=None,
        receipt=receipt,
        decision="",
        json=True,
    )
    result = cmd_record(args)
    return {"schema_version": ABORT_SCHEMA_VERSION, "status": result.get("status"), "record_result": result}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    audit_cmd = sub.add_parser("audit", help="Read-only audit of active locks, stuck tasks, late receipts, and repeated blockers.")
    audit_cmd.add_argument("--ip-dir", required=True)
    audit_cmd.add_argument("--run-id", default="")
    audit_cmd.add_argument("--stale-seconds", type=int, default=1800)
    audit_cmd.add_argument("--progress-seconds", type=int, default=DEFAULT_PROGRESS_SECONDS)
    audit_cmd.add_argument("--json", action="store_true")

    abort_cmd = sub.add_parser("abort-task", help="Explicitly record a stuck task terminal status and release its wavefront lock.")
    abort_cmd.add_argument("--ip-dir", required=True)
    abort_cmd.add_argument("--run-id", required=True)
    abort_cmd.add_argument("--task-id", required=True)
    abort_cmd.add_argument("--status", required=True, choices=sorted(TERMINAL_ABORT_STATUSES))
    abort_cmd.add_argument("--receipt", default="")
    abort_cmd.add_argument("--json", action="store_true")

    fallback_cmd = sub.add_parser("fallback-plan", help="Create a bounded custom-reviewer fallback plan for stuck gate-review tasks.")
    fallback_cmd.add_argument("--ip-dir", required=True)
    fallback_cmd.add_argument("--run-id", default="")
    fallback_cmd.add_argument("--stale-seconds", type=int, default=900)
    fallback_cmd.add_argument("--no-write", action="store_true")
    fallback_cmd.add_argument("--json", action="store_true")

    args = parser.parse_args(argv)
    try:
        if args.command == "audit":
            payload = audit(Path(args.ip_dir), run_id=args.run_id, stale_seconds=args.stale_seconds, progress_seconds=args.progress_seconds)
        elif args.command == "abort-task":
            payload = abort_task(Path(args.ip_dir), run_id=args.run_id, task_id=args.task_id, status=args.status, receipt=args.receipt)
        else:
            payload = gate_fallback_plan(Path(args.ip_dir), run_id=args.run_id, stale_seconds=args.stale_seconds, write=not args.no_write)
    except Exception as exc:
        schema = AUDIT_SCHEMA_VERSION if args.command == "audit" else ABORT_SCHEMA_VERSION if args.command == "abort-task" else FALLBACK_SCHEMA_VERSION
        payload = {"schema_version": schema, "status": "fail", "issues": [issue("EXCEPTION", str(exc))]}
    if getattr(args, "json", False):
        print(json.dumps(payload, indent=2, sort_keys=True))
    elif payload.get("status") == "pass":
        print(f"PASS {payload.get('schema_version')}")
    else:
        print(f"FAIL {payload.get('schema_version')}", file=sys.stderr)
        for item in payload.get("issues", []):
            print(f"- {item.get('code')}: {item.get('message')}", file=sys.stderr)
    return 0 if payload.get("status") == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
