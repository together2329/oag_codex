#!/usr/bin/env python3
"""Start, update, and inspect durable OAG Action instances."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import oag_action_plan  # noqa: E402
import oag_ip_git  # noqa: E402
import oag_mission_runtime  # noqa: E402
import oag_paths  # noqa: E402
import oag_run_control_common as run_common  # noqa: E402
from oag_validate_json import contextual_schema_issues  # noqa: E402


SCHEMA_VERSION = "oag_action_instance.v1"
RESULT_SCHEMA_VERSION = "oag_action_record_result.v1"
TERMINAL_STATUSES = {"accepted", "rejected", "blocked", "failed", "inconclusive", "aborted"}
VALID_STATUSES = {"started", "running", *TERMINAL_STATUSES}

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


def action_dir(ip_dir: Path) -> Path:
    return oag_paths.state_path(ip_dir, "knowledge/actions")


def action_path(ip_dir: Path, action_id: str) -> Path:
    clean = re.sub(r"[^A-Za-z0-9_.:-]+", "_", action_id).strip("_")
    return action_dir(ip_dir) / f"{clean}.json"


def existing_action_paths(ip_dir: Path) -> list[Path]:
    root = action_dir(ip_dir)
    if not root.is_dir():
        return []
    return sorted(path for path in root.glob("ACT_RUN_*.json") if path.is_file())


def dispatch_dir(ip_dir: Path) -> Path:
    return oag_paths.legacy_or_hidden(ip_dir, "knowledge/dispatches")


def latest_dispatch(ip_dir: Path) -> JsonObject:
    root = dispatch_dir(ip_dir)
    if not root.is_dir():
        return {}
    paths = sorted((path for path in root.glob("*.json") if path.is_file()), key=lambda path: path.stat().st_mtime)
    if not paths:
        return {}
    path = paths[-1]
    payload = read_json(path)
    return {
        "dispatch_id": payload.get("dispatch_id") or path.stem,
        "path": run_common.rel_to_ip(ip_dir, path),
        "agent_type": payload.get("agent_type") or "",
        "stage": payload.get("stage") or "",
    }


def latest_action_id(ip_dir: Path) -> str:
    paths = existing_action_paths(ip_dir)
    return paths[-1].stem if paths else ""


def candidate_file(ip_dir: Path) -> Path:
    return oag_paths.legacy_or_hidden(ip_dir, "ontology/generated/action_candidates.json")


def load_candidates(ip_dir: Path, *, refresh: bool) -> JsonObject:
    if refresh or not candidate_file(ip_dir).is_file():
        result = oag_action_plan.build_plan(ip_dir, write=True, run_semantic_checks=False)
        plan = result.get("plan")
        if isinstance(plan, dict):
            return plan
    payload = read_json(candidate_file(ip_dir))
    return payload


def select_candidate(plan: JsonObject, candidate_id: str) -> JsonObject:
    candidates = [item for item in plan.get("candidates", []) if isinstance(item, dict)]
    if candidate_id in {"", "recommended"}:
        return next((item for item in candidates if item.get("recommended") is True), candidates[0] if candidates else {})
    return next((item for item in candidates if item.get("id") == candidate_id), {})


def sanitize_suffix(value: str) -> str:
    clean = re.sub(r"[^A-Za-z0-9_.:-]+", "_", value).strip("_")
    return clean[:80] or "ACTION"


def new_action_id(ip_dir: Path, candidate: JsonObject) -> str:
    base = f"ACT_RUN_{run_common.utc_now().replace('-', '').replace(':', '')}_{sanitize_suffix(str(candidate.get('id') or candidate.get('action_type') or 'ACTION'))}"
    path = action_path(ip_dir, base)
    if not path.exists():
        return base
    for index in range(2, 100):
        candidate_id = f"{base}_{index}"
        if not action_path(ip_dir, candidate_id).exists():
            return candidate_id
    raise RuntimeError("could not allocate unique action id")


def validate_instance(payload: JsonObject, path: Path) -> list[dict[str, str]]:
    return contextual_schema_issues(
        "oag_action_instance.schema.json",
        payload,
        code_prefix="ACTION_INSTANCE_SCHEMA",
        document_path=str(path),
    )


def write_instance(ip_dir: Path, payload: JsonObject) -> Path:
    path = action_path(ip_dir, str(payload.get("id") or ""))
    issues = validate_instance(payload, path)
    if issues:
        raise ValueError(json.dumps({"schema_issues": issues}, indent=2, sort_keys=True))
    run_common.write_json(path, payload)
    write_index(ip_dir)
    return path


def action_summary(path: Path) -> JsonObject:
    payload = read_json(path)
    result = payload.get("result") if isinstance(payload.get("result"), dict) else {}
    return {
        "id": payload.get("id") or path.stem,
        "action_type": payload.get("action_type") or "",
        "status": payload.get("status") or "",
        "candidate_ref": payload.get("candidate_ref") or "",
        "mission_instance_refs": payload.get("mission_instance_refs") if isinstance(payload.get("mission_instance_refs"), list) else [],
        "started_at": payload.get("started_at") or "",
        "completed_at": payload.get("completed_at") or "",
        "selected_reason": payload.get("selected_reason") or "",
        "summary": result.get("summary") or "",
        "path": path.name,
    }


def write_index(ip_dir: Path) -> Path:
    root = action_dir(ip_dir)
    rows = [action_summary(path) for path in existing_action_paths(ip_dir)]
    payload = {
        "schema_version": "oag_action_index.v1",
        "generated_at": run_common.utc_now(),
        "ip": ip_dir.name,
        "actions": rows,
        "counts": {
            "total": len(rows),
            "open": sum(1 for row in rows if row.get("status") not in TERMINAL_STATUSES),
            "terminal": sum(1 for row in rows if row.get("status") in TERMINAL_STATUSES),
        },
    }
    path = root / "_index.json"
    run_common.write_json(path, payload)
    return path


def start_action(args: argparse.Namespace) -> JsonObject:
    ip_dir = oag_paths.ip_root(args.ip_dir)
    plan = load_candidates(ip_dir, refresh=not args.no_refresh_plan)
    candidate = select_candidate(plan, args.candidate_id)
    if not candidate:
        return {
            "schema_version": RESULT_SCHEMA_VERSION,
            "status": "fail",
            "issues": [issue("ACTION_CANDIDATE_NOT_FOUND", f"candidate not found: {args.candidate_id}", run_common.rel_to_ip(ip_dir, candidate_file(ip_dir)))],
        }
    if candidate.get("status") == "blocked" and not args.allow_blocked:
        return {
            "schema_version": RESULT_SCHEMA_VERSION,
            "status": "fail",
            "issues": [issue("ACTION_CANDIDATE_BLOCKED", "candidate is blocked; pass --allow-blocked only when deliberately recording the blocked action", str(candidate.get("id") or ""))],
            "candidate": candidate,
        }

    selected_reason = args.selected_reason or str(candidate.get("recommendation_reason") or "selected from generated OAG action candidates")
    action_id = new_action_id(ip_dir, candidate)
    started_at = run_common.utc_now()
    mission_template = str(candidate.get("mission_template") or plan.get("mission_template") or "")
    mission_instance_id = str(plan.get("mission_instance_id") or "")
    if not mission_instance_id and mission_template:
        mission = oag_mission_runtime.ensure_mission_instance(ip_dir, mission_template, plan_payload=plan, actor=args.actor_id or "codex")
        mission_instance_id = str(mission.get("id") or "")
    payload: JsonObject = {
        "schema_version": SCHEMA_VERSION,
        "id": action_id,
        "action_type": candidate.get("action_type") or "",
        "candidate_ref": candidate.get("id") or "",
        "mission_instance_refs": [mission_instance_id] if mission_instance_id else [],
        "status": "started",
        "selected_by": {
            "kind": args.actor_kind,
            "id": args.actor_id,
            "surface": args.actor_surface,
        },
        "selected_reason": selected_reason,
        "started_at": started_at,
        "target_objects": candidate.get("target_objects") if isinstance(candidate.get("target_objects"), dict) else {},
        "mission_template": mission_template,
        "result": {
            "summary": "",
            "candidate_snapshot": candidate,
            "open_item_refs": candidate.get("open_items") if isinstance(candidate.get("open_items"), list) else [],
            "owner_role": candidate.get("owner_role") or "",
            "command": candidate.get("command") or "",
            "expected_effects": candidate.get("expected_effects") if isinstance(candidate.get("expected_effects"), dict) else {},
            "status_history": [
                {
                    "status": "started",
                    "at": started_at,
                    "summary": selected_reason,
                }
            ],
        },
    }
    path = write_instance(ip_dir, payload)
    if mission_instance_id:
        oag_mission_runtime.attach_action(ip_dir, mission_instance_id, action_id)
    return {
        "schema_version": RESULT_SCHEMA_VERSION,
        "status": "pass",
        "action_id": action_id,
        "action_type": payload["action_type"],
        "path": run_common.rel_to_ip(ip_dir, path),
        "index": run_common.rel_to_ip(ip_dir, action_dir(ip_dir) / "_index.json"),
        "mission_instance_id": mission_instance_id,
        "candidate": candidate,
    }


def update_action(args: argparse.Namespace) -> JsonObject:
    ip_dir = oag_paths.ip_root(args.ip_dir)
    action_id = args.action_id
    if action_id == "latest":
        action_id = latest_action_id(ip_dir)
    if not action_id:
        return {"schema_version": RESULT_SCHEMA_VERSION, "status": "fail", "issues": [issue("ACTION_ID_MISSING", "no action id was supplied and no latest action exists")]}
    path = action_path(ip_dir, action_id)
    payload = read_json(path)
    if not payload:
        return {"schema_version": RESULT_SCHEMA_VERSION, "status": "fail", "issues": [issue("ACTION_INSTANCE_MISSING", f"action instance does not exist: {action_id}", str(path))]}
    if args.status not in VALID_STATUSES:
        return {"schema_version": RESULT_SCHEMA_VERSION, "status": "fail", "issues": [issue("ACTION_STATUS_INVALID", f"invalid action status: {args.status}")]}

    now = run_common.utc_now()
    result = payload.setdefault("result", {})
    if not isinstance(result, dict):
        result = {}
        payload["result"] = result
    result["summary"] = args.summary or result.get("summary") or ""

    def extend_list(key: str, values: list[str] | None) -> None:
        if not values:
            return
        current = result.get(key)
        if not isinstance(current, list):
            current = []
        for value in values:
            if value and value not in current:
                current.append(value)
        result[key] = current

    extend_list("dispatch_ids", args.dispatch_id)
    extend_list("dispatch_paths", args.dispatch_path)
    extend_list("receipt_paths", args.receipt_path)
    extend_list("review_decisions", args.review_decision)
    extend_list("changed_paths", args.changed_path)
    extend_list("evidence_paths", args.evidence)
    extend_list("blockers", args.blocker)
    extend_list("deep_interview_rounds", args.deep_interview_round)
    if args.auto_link_latest_dispatch:
        latest = latest_dispatch(ip_dir)
        if latest:
            extend_list("dispatch_ids", [str(latest.get("dispatch_id") or "")])
            extend_list("dispatch_paths", [str(latest.get("path") or "")])
            result["latest_dispatch_snapshot"] = latest
    if args.auto_link_active_wavefront:
        state = run_common.collect_run_state(ip_dir)
        locks = state.get("wavefront", {}).get("active_locks", [])
        if isinstance(locks, list):
            refs = result.get("wavefront_refs")
            if not isinstance(refs, list):
                refs = []
            for lock in locks:
                if isinstance(lock, dict):
                    ref = {
                        "run_id": lock.get("run_id") or "",
                        "task_id": lock.get("task_id") or "",
                        "dispatch_id": lock.get("dispatch_id") or "",
                        "path": lock.get("path") or "",
                    }
                    if ref not in refs:
                        refs.append(ref)
            result["wavefront_refs"] = refs
    if args.wavefront_run_id or args.wavefront_task_id:
        refs = result.get("wavefront_refs")
        if not isinstance(refs, list):
            refs = []
        refs.append({"run_id": args.wavefront_run_id or "", "task_id": args.wavefront_task_id or ""})
        result["wavefront_refs"] = refs

    history = result.get("status_history")
    if not isinstance(history, list):
        history = []
    history.append({"status": args.status, "at": now, "summary": args.summary or ""})
    result["status_history"] = history
    payload["status"] = args.status
    if args.status in TERMINAL_STATUSES:
        payload["completed_at"] = now
        if args.git_checkpoint:
            message = args.checkpoint_message or f"OAG action {action_id} {args.status}"
            result["git_checkpoint"] = oag_ip_git.checkpoint_ip_git(ip_dir, message=message)
    path = write_instance(ip_dir, payload)
    for mission_id in payload.get("mission_instance_refs", []) if isinstance(payload.get("mission_instance_refs"), list) else []:
        oag_mission_runtime.attach_action(ip_dir, str(mission_id), action_id)
    return {
        "schema_version": RESULT_SCHEMA_VERSION,
        "status": "pass",
        "action_id": action_id,
        "action_status": payload["status"],
        "path": run_common.rel_to_ip(ip_dir, path),
        "index": run_common.rel_to_ip(ip_dir, action_dir(ip_dir) / "_index.json"),
        "git_checkpoint": result.get("git_checkpoint", {}),
    }


def show_action(args: argparse.Namespace) -> JsonObject:
    ip_dir = oag_paths.ip_root(args.ip_dir)
    action_id = args.action_id
    if action_id == "latest":
        action_id = latest_action_id(ip_dir)
    if not action_id:
        return {"schema_version": RESULT_SCHEMA_VERSION, "status": "fail", "issues": [issue("ACTION_ID_MISSING", "no action id was supplied and no latest action exists")]}
    path = action_path(ip_dir, action_id)
    payload = read_json(path)
    if not payload:
        return {"schema_version": RESULT_SCHEMA_VERSION, "status": "fail", "issues": [issue("ACTION_INSTANCE_MISSING", f"action instance does not exist: {action_id}", str(path))]}
    return {"schema_version": RESULT_SCHEMA_VERSION, "status": "pass", "path": run_common.rel_to_ip(ip_dir, path), "action": payload}


def list_actions(args: argparse.Namespace) -> JsonObject:
    ip_dir = oag_paths.ip_root(args.ip_dir)
    index_path = write_index(ip_dir)
    index = read_json(index_path)
    return {
        "schema_version": RESULT_SCHEMA_VERSION,
        "status": "pass",
        "path": run_common.rel_to_ip(ip_dir, index_path),
        "index": index,
    }


def print_result(result: JsonObject, *, json_mode: bool) -> int:
    if json_mode:
        print(json.dumps(result, indent=2, sort_keys=True))
    elif result.get("status") == "pass":
        if "action_id" in result:
            print(f"PASS {RESULT_SCHEMA_VERSION}: {result['action_id']} -> {result.get('path')}")
        else:
            print(f"PASS {RESULT_SCHEMA_VERSION}: {result.get('path', '')}")
    else:
        print(f"FAIL {RESULT_SCHEMA_VERSION}", file=sys.stderr)
        for item in result.get("issues", []):
            print(f"- {item.get('code')}: {item.get('message')}", file=sys.stderr)
    return 0 if result.get("status") == "pass" else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    start = sub.add_parser("start", help="Create a started action instance from a generated candidate.")
    start.add_argument("--ip-dir", required=True)
    start.add_argument("--candidate-id", default="recommended")
    start.add_argument("--selected-reason", default="")
    start.add_argument("--actor-kind", default="ai")
    start.add_argument("--actor-id", default="codex")
    start.add_argument("--actor-surface", default="cli")
    start.add_argument("--allow-blocked", action="store_true")
    start.add_argument("--no-refresh-plan", action="store_true")
    start.add_argument("--json", action="store_true")

    update = sub.add_parser("update", help="Update an existing action instance.")
    update.add_argument("--ip-dir", required=True)
    update.add_argument("--action-id", required=True, help="Action id, or 'latest'.")
    update.add_argument("--status", required=True)
    update.add_argument("--summary", default="")
    update.add_argument("--dispatch-id", action="append")
    update.add_argument("--dispatch-path", action="append")
    update.add_argument("--receipt-path", action="append")
    update.add_argument("--review-decision", action="append")
    update.add_argument("--wavefront-run-id", default="")
    update.add_argument("--wavefront-task-id", default="")
    update.add_argument("--changed-path", action="append")
    update.add_argument("--evidence", action="append")
    update.add_argument("--blocker", action="append")
    update.add_argument("--deep-interview-round", action="append")
    update.add_argument("--auto-link-latest-dispatch", action="store_true")
    update.add_argument("--auto-link-active-wavefront", action="store_true")
    update.add_argument("--git-checkpoint", action="store_true")
    update.add_argument("--checkpoint-message", default="")
    update.add_argument("--json", action="store_true")

    show = sub.add_parser("show", help="Show one action instance.")
    show.add_argument("--ip-dir", required=True)
    show.add_argument("--action-id", required=True, help="Action id, or 'latest'.")
    show.add_argument("--json", action="store_true")

    list_cmd = sub.add_parser("list", help="Refresh and show the IP-local action index.")
    list_cmd.add_argument("--ip-dir", required=True)
    list_cmd.add_argument("--json", action="store_true")

    args = parser.parse_args(argv)
    try:
        if args.command == "start":
            result = start_action(args)
        elif args.command == "update":
            result = update_action(args)
        elif args.command == "show":
            result = show_action(args)
        elif args.command == "list":
            result = list_actions(args)
        else:
            result = {"schema_version": RESULT_SCHEMA_VERSION, "status": "fail", "issues": [issue("UNKNOWN_COMMAND", str(args.command))]}
    except Exception as exc:
        result = {"schema_version": RESULT_SCHEMA_VERSION, "status": "fail", "issues": [issue("ACTION_RECORD_EXCEPTION", str(exc))]}
    return print_result(result, json_mode=bool(getattr(args, "json", False)))


if __name__ == "__main__":
    raise SystemExit(main())
