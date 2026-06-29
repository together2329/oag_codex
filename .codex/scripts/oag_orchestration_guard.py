#!/usr/bin/env python3
"""Audit and route OAG wavefront orchestration hazards."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import oag_paths  # noqa: E402
from oag_run_control_common import JsonObject, age_seconds, collect_run_state, issue, parse_utc  # noqa: E402
from oag_wavefront import cmd_record  # noqa: E402


AUDIT_SCHEMA_VERSION = "oag_orchestration_guard_audit.v1"
ABORT_SCHEMA_VERSION = "oag_orchestration_guard_abort.v1"
TERMINAL_ABORT_STATUSES = {"blocked", "failed", "inconclusive"}


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


def _rel_to_ip(ip_dir: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(ip_dir.resolve()).as_posix()
    except ValueError:
        return str(path)


def audit(ip_dir: Path, *, run_id: str = "", stale_seconds: int = 1800) -> JsonObject:
    ip_dir = oag_paths.ip_root(ip_dir)
    state = collect_run_state(ip_dir)
    issues: list[dict[str, str]] = []
    recommendations: list[JsonObject] = []

    stale_locks: list[JsonObject] = []
    for lock in state.get("wavefront", {}).get("active_locks", []):
        age = lock.get("age_seconds")
        if isinstance(age, (int, float)) and age >= stale_seconds:
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
        "active_locks": state.get("wavefront", {}).get("active_locks", []),
        "stale_locks": stale_locks,
        "late_receipts": late_receipts,
        "repeated_blockers": repeated,
        "issues": issues,
        "recommendations": recommendations,
    }


def detect_late_receipts(ip_dir: Path, *, run_id: str = "") -> list[JsonObject]:
    receipts = _find_subagent_receipts(ip_dir)
    by_dispatch: dict[str, list[Path]] = {}
    for receipt in receipts:
        payload = _load_json(receipt)
        dispatch_id = str(payload.get("dispatch_id") or "").strip()
        if dispatch_id:
            by_dispatch.setdefault(dispatch_id, []).append(receipt)
    late: list[JsonObject] = []
    for run_dir in _iter_run_dirs(ip_dir, run_id):
        graph = _load_json(run_dir / "wavefront_task_graph.json")
        for task in graph.get("tasks", []) if isinstance(graph.get("tasks"), list) else []:
            if not isinstance(task, dict):
                continue
            abort_marker = task.get("abort_marker") if isinstance(task.get("abort_marker"), dict) else {}
            if not abort_marker:
                continue
            abort_time = parse_utc(abort_marker.get("recorded_at"))
            dispatch_id = str(task.get("dispatch_id") or abort_marker.get("dispatch_id") or "").strip()
            candidate_receipts = list(by_dispatch.get(dispatch_id, []))
            receipt_path = str(task.get("receipt_path") or abort_marker.get("receipt_path") or "").strip()
            if receipt_path:
                candidate = oag_paths.legacy_or_hidden(ip_dir, receipt_path)
                if candidate.is_file():
                    candidate_receipts.append(candidate)
            for receipt in sorted(set(candidate_receipts)):
                if abort_time is None or receipt.stat().st_mtime >= abort_time.timestamp():
                    late.append(
                        {
                            "run_id": run_dir.name,
                            "task_id": task.get("task_id") or "",
                            "dispatch_id": dispatch_id,
                            "abort_status": abort_marker.get("status") or task.get("status") or "",
                            "receipt_path": _rel_to_ip(ip_dir, receipt),
                        }
                    )
    return late


def detect_repeated_blockers(ip_dir: Path, *, run_id: str = "", threshold: int = 3) -> list[JsonObject]:
    counts: dict[str, int] = {}
    latest: dict[str, str] = {}
    for run_dir in _iter_run_dirs(ip_dir, run_id):
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
            status = str(event.get("status") or "")
            if status not in TERMINAL_ABORT_STATUSES and event.get("event") != "blocked":
                continue
            details = event.get("details") if isinstance(event.get("details"), dict) else {}
            raw_issues = details.get("issues") if isinstance(details.get("issues"), list) else []
            if raw_issues:
                for item in raw_issues:
                    if not isinstance(item, dict):
                        continue
                    key = f"{run_dir.name}:{event.get('task_id', '')}:{item.get('code', '')}:{item.get('path', '')}"
                    counts[key] = counts.get(key, 0) + 1
                    latest[key] = str(event.get("created_at") or "")
            else:
                key = f"{run_dir.name}:{event.get('task_id', '')}:{status or event.get('event')}"
                counts[key] = counts.get(key, 0) + 1
                latest[key] = str(event.get("created_at") or "")
    return [{"key": key, "count": count, "latest_at": latest.get(key, "")} for key, count in sorted(counts.items()) if count >= threshold]


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
    audit_cmd.add_argument("--json", action="store_true")

    abort_cmd = sub.add_parser("abort-task", help="Explicitly record a stuck task terminal status and release its wavefront lock.")
    abort_cmd.add_argument("--ip-dir", required=True)
    abort_cmd.add_argument("--run-id", required=True)
    abort_cmd.add_argument("--task-id", required=True)
    abort_cmd.add_argument("--status", required=True, choices=sorted(TERMINAL_ABORT_STATUSES))
    abort_cmd.add_argument("--receipt", default="")
    abort_cmd.add_argument("--json", action="store_true")

    args = parser.parse_args(argv)
    try:
        if args.command == "audit":
            payload = audit(Path(args.ip_dir), run_id=args.run_id, stale_seconds=args.stale_seconds)
        else:
            payload = abort_task(Path(args.ip_dir), run_id=args.run_id, task_id=args.task_id, status=args.status, receipt=args.receipt)
    except Exception as exc:
        schema = AUDIT_SCHEMA_VERSION if args.command == "audit" else ABORT_SCHEMA_VERSION
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
