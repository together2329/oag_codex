#!/usr/bin/env python3
"""Summarize OAG role health from durable Action and wavefront state."""

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
import oag_run_control_common as run_common  # noqa: E402


SCHEMA_VERSION = "oag_role_health.v1"
RESULT_SCHEMA_VERSION = "oag_role_health_result.v1"
BAD_TERMINAL_STATUSES = {"blocked", "failed", "inconclusive", "aborted", "rejected"}
OPEN_STATUSES = {"started", "running"}

JsonObject = dict[str, Any]


def issue(code: str, message: str, path: str = "") -> dict[str, str]:
    payload = {"code": code, "message": message}
    if path:
        payload["path"] = path
    return payload


def read_json(path: Path) -> JsonObject:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def action_paths(ip_dir: Path) -> list[Path]:
    root = oag_paths.state_path(ip_dir, "knowledge/actions")
    if not root.is_dir():
        return []
    return sorted(path for path in root.glob("ACT_RUN_*.json") if path.is_file())


def owner_role(payload: JsonObject) -> str:
    result = payload.get("result") if isinstance(payload.get("result"), dict) else {}
    owner = str(result.get("owner_role") or "").strip()
    if owner:
        return owner
    snapshot = result.get("candidate_snapshot") if isinstance(result.get("candidate_snapshot"), dict) else {}
    return str(snapshot.get("owner_role") or "unknown").strip() or "unknown"


def collect_role_health(ip_dir: Path, *, stuck_seconds: int = 900, failure_threshold: int = 2) -> JsonObject:
    ip_dir = oag_paths.ip_root(ip_dir)
    now = run_common.parse_utc(run_common.utc_now())
    roles: dict[str, JsonObject] = {}
    hazards: list[JsonObject] = []
    for path in action_paths(ip_dir):
        payload = read_json(path)
        role = owner_role(payload)
        row = roles.setdefault(
            role,
            {
                "role": role,
                "status": "healthy",
                "actions_total": 0,
                "accepted": 0,
                "bad_terminal": 0,
                "open": 0,
                "stuck": 0,
                "last_action_id": "",
                "last_action_status": "",
                "issues": [],
            },
        )
        status = str(payload.get("status") or "")
        row["actions_total"] += 1
        row["last_action_id"] = payload.get("id") or path.stem
        row["last_action_status"] = status
        if status == "accepted":
            row["accepted"] += 1
        if status in BAD_TERMINAL_STATUSES:
            row["bad_terminal"] += 1
        if status in OPEN_STATUSES:
            row["open"] += 1
            age = run_common.age_seconds(payload.get("started_at"), now=now)
            if age is not None and age >= stuck_seconds:
                row["stuck"] += 1
                row["issues"].append(issue("ROLE_ACTION_STUCK", f"open action exceeded {stuck_seconds}s", run_common.rel_to_ip(ip_dir, path)))

    state = run_common.collect_run_state(ip_dir)
    for lock in state.get("wavefront", {}).get("active_locks", []) if isinstance(state.get("wavefront", {}).get("active_locks"), list) else []:
        if not isinstance(lock, dict):
            continue
        age = lock.get("age_seconds")
        if isinstance(age, (int, float)) and age >= stuck_seconds:
            role = str(lock.get("claimed_by") or lock.get("agent_type") or "wavefront").strip() or "wavefront"
            row = roles.setdefault(
                role,
                {
                    "role": role,
                    "status": "healthy",
                    "actions_total": 0,
                    "accepted": 0,
                    "bad_terminal": 0,
                    "open": 0,
                    "stuck": 0,
                    "last_action_id": "",
                    "last_action_status": "",
                    "issues": [],
                },
            )
            row["stuck"] += 1
            row["issues"].append(issue("ROLE_WAVEFRONT_LOCK_STUCK", f"active wavefront lock exceeded {stuck_seconds}s", str(lock.get("path") or "")))

    for role, row in roles.items():
        role_issues = row.get("issues") if isinstance(row.get("issues"), list) else []
        if row.get("stuck", 0) > 0:
            row["status"] = "stuck"
            hazards.append({"role": role, "code": "ROLE_STUCK", "message": "role has stuck open work", "issues": role_issues})
        elif row.get("bad_terminal", 0) >= failure_threshold:
            row["status"] = "degraded"
            hazards.append({"role": role, "code": "ROLE_REPEATED_BAD_TERMINAL", "message": "role has repeated blocked/failed/inconclusive/aborted actions", "bad_terminal": row.get("bad_terminal", 0)})

    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": run_common.utc_now(),
        "ip": ip_dir.name,
        "stuck_seconds": stuck_seconds,
        "failure_threshold": failure_threshold,
        "roles": sorted(roles.values(), key=lambda item: str(item.get("role") or "")),
        "hazards": hazards,
        "summary": {
            "role_count": len(roles),
            "hazard_count": len(hazards),
            "stuck_role_count": sum(1 for row in roles.values() if row.get("status") == "stuck"),
            "degraded_role_count": sum(1 for row in roles.values() if row.get("status") == "degraded"),
        },
    }
    return payload


def write_role_health(ip_dir: Path, payload: JsonObject) -> Path:
    path = oag_paths.state_path(ip_dir, "knowledge/operations/role_health.json")
    run_common.write_json(path, payload)
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ip-dir", required=True)
    parser.add_argument("--stuck-seconds", type=int, default=900)
    parser.add_argument("--failure-threshold", type=int, default=2)
    parser.add_argument("--no-write", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    ip_dir = oag_paths.ip_root(args.ip_dir)
    payload = collect_role_health(ip_dir, stuck_seconds=args.stuck_seconds, failure_threshold=args.failure_threshold)
    path = Path("")
    if not args.no_write:
        path = write_role_health(ip_dir, payload)
    result = {
        "schema_version": RESULT_SCHEMA_VERSION,
        "status": "pass",
        "ip": ip_dir.name,
        "written": not args.no_write,
        "path": run_common.rel_to_ip(ip_dir, path) if path else "",
        "role_health": payload,
    }
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(f"PASS {RESULT_SCHEMA_VERSION}: {payload['summary']['hazard_count']} hazards")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
