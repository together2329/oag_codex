#!/usr/bin/env python3
"""Bounded Mission Loop controller for OAG-managed IP work.

This is the "keeps working" control surface. It does not bypass OAG truth,
scope lock, wavefront ownership, dispatch receipts, or gate decisions. One tick
observes current IP state, ranks the next Action, records what the runner should
do next, and stops whenever human input or an ownership boundary is required.
"""

from __future__ import annotations

import argparse
import importlib
import json
import os
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import oag_action_plan  # noqa: E402
import oag_action_record  # noqa: E402
import oag_decision_autoresolve  # noqa: E402
import oag_exploration_plan  # noqa: E402
import oag_mission_runtime  # noqa: E402
import oag_orchestration_guard  # noqa: E402
import oag_paths  # noqa: E402
import oag_run_control_common as run_common  # noqa: E402

oag_pending_questions = importlib.import_module("oag_pending_questions")


STATE_SCHEMA = "oag_mission_loop_state.v1"
TICK_SCHEMA = "oag_mission_loop_tick.v1"
RESULT_SCHEMA = "oag_mission_loop_result.v1"

HUMAN_ACTION_TYPES = {
    "ACT_ASK_DEEP_INTERVIEW_QUESTION",
    "ACT_RESOLVE_DECISION",
    "ACT_RESOLVE_PENDING_GATE",
    "ACT_LOCK_SCOPE",
    "ACT_CUSTOM_OPERATOR_INPUT",
}

CHECKPOINT_ACTION_TYPES = {
    "ACT_CHECKPOINT_REVIEW",
}

DISPATCH_ACTION_TYPES = {
    "ACT_REPAIR_AUTHORING_PACKET_PROJECTION",
    "ACT_ARCHITECTURE_PROJECTION",
    "ACT_RTL_IMPLEMENTATION",
    "ACT_TB_IMPLEMENTATION",
    "ACT_LINT_STATIC_CHECK",
    "ACT_SIMULATION_RUN",
    "ACT_FAILURE_TRIAGE",
    "ACT_COVERAGE_REVIEW",
    "ACT_EVIDENCE_VALIDATION",
    "ACT_GATE_REVIEW",
    "ACT_REVIEW_REQUIREMENTS",
    "ACT_PROJECT_REQUIREMENT_ATOMS",
    "ACT_PROJECT_OBLIGATIONS",
    "ACT_PROJECT_CONTRACTS",
    "ACT_PROJECT_VERIFICATION_PLAN",
}

SAFE_TOOL_ACTION_TYPES = {
    "ACT_RENDER_LOCK_PREVIEW",
    "ACT_COMPILE_AUTHORING_PACKETS",
}

SELF_EXPLORE_ACTION_TYPES = {
    "ACT_SELF_EXPLORE_OPTIONS",
}

OPEN_ACTION_STATUSES = {"started", "running"}

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


def loop_dir(ip_dir: Path) -> Path:
    return oag_paths.state_path(ip_dir, "knowledge/mission_loop")


def state_path(ip_dir: Path) -> Path:
    return loop_dir(ip_dir) / "state.json"


def tick_log_path(ip_dir: Path) -> Path:
    return loop_dir(ip_dir) / "ticks.jsonl"


def lock_path(ip_dir: Path) -> Path:
    return loop_dir(ip_dir) / "runner.lock"


def rel(ip_dir: Path, path: Path) -> str:
    return run_common.rel_to_ip(ip_dir, path)


def write_json(path: Path, payload: Any) -> None:
    run_common.write_json(path, payload)


def append_jsonl(path: Path, payload: JsonObject) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(payload, sort_keys=True) + "\n")


def default_state(ip_dir: Path) -> JsonObject:
    return {
        "schema_version": STATE_SCHEMA,
        "ip": ip_dir.name,
        "status": "active",
        "created_at": run_common.utc_now(),
        "updated_at": run_common.utc_now(),
        "tick_count": 0,
        "mode": "record",
        "last_tick": {},
        "pause_reason": "",
        "autonomy_policy": {
            "bounded": True,
            "one_action_per_tick": True,
            "human_questions_stop_loop": True,
            "active_locks_stop_loop": True,
            "post_lock_writes_require_dispatch": True,
        },
    }


def load_state(ip_dir: Path) -> JsonObject:
    path = state_path(ip_dir)
    payload = read_json(path)
    if payload.get("schema_version") == STATE_SCHEMA:
        return payload
    return default_state(ip_dir)


def save_state(ip_dir: Path, payload: JsonObject) -> Path:
    payload["schema_version"] = STATE_SCHEMA
    payload["ip"] = ip_dir.name
    payload["updated_at"] = run_common.utc_now()
    path = state_path(ip_dir)
    write_json(path, payload)
    return path


@contextmanager
def runner_lock(ip_dir: Path, *, stale_seconds: int = 1800, enabled: bool = True) -> Iterator[JsonObject]:
    if not enabled:
        yield {"locked": False, "path": ""}
        return
    path = lock_path(ip_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    now = run_common.utc_now()
    lock_payload = {
        "schema_version": "oag_mission_loop_lock.v1",
        "ip": ip_dir.name,
        "pid": os.getpid(),
        "created_at": now,
    }
    try:
        with path.open("x", encoding="utf-8") as fh:
            fh.write(json.dumps(lock_payload, sort_keys=True) + "\n")
    except FileExistsError:
        existing = read_json(path)
        age = run_common.age_seconds(existing.get("created_at"))
        if isinstance(age, (int, float)) and age >= stale_seconds:
            path.unlink(missing_ok=True)
            with path.open("x", encoding="utf-8") as fh:
                fh.write(json.dumps({**lock_payload, "replaced_stale_lock": existing}, sort_keys=True) + "\n")
        else:
            raise RuntimeError(f"mission loop already locked: {path}")
    try:
        yield {"locked": True, "path": rel(ip_dir, path)}
    finally:
        try:
            path.unlink()
        except FileNotFoundError:
            pass


def open_actions(ip_dir: Path) -> list[JsonObject]:
    rows: list[JsonObject] = []
    for path in oag_action_record.existing_action_paths(ip_dir):
        payload = read_json(path)
        if payload.get("status") in OPEN_ACTION_STATUSES:
            rows.append(
                {
                    "id": payload.get("id") or path.stem,
                    "action_type": payload.get("action_type") or "",
                    "status": payload.get("status") or "",
                    "path": rel(ip_dir, path),
                    "started_at": payload.get("started_at") or "",
                }
            )
    return rows


def recommended_candidate(plan_result: JsonObject) -> JsonObject:
    candidate = plan_result.get("recommended_action")
    if isinstance(candidate, dict) and candidate:
        return candidate
    plan = plan_result.get("plan") if isinstance(plan_result.get("plan"), dict) else {}
    candidates = [item for item in plan.get("candidates", []) if isinstance(item, dict)]
    return next((item for item in candidates if item.get("recommended") is True), candidates[0] if candidates else {})


def classify_candidate(candidate: JsonObject, ip_dir: Path | None = None) -> tuple[str, str]:
    action_type = str(candidate.get("action_type") or "")
    owner_role = str(candidate.get("owner_role") or "")
    if action_type in CHECKPOINT_ACTION_TYPES:
        return "checkpoint_ready", "pending_questions_checkpoint_ready"
    if action_type in SELF_EXPLORE_ACTION_TYPES:
        return "self_explore", "local_research_before_user_question"
    if action_type in HUMAN_ACTION_TYPES or owner_role == "human_via_main":
        if ip_dir is not None:
            policy = oag_decision_autoresolve.resolve_candidate_policy(ip_dir, candidate)
            policy_decision = str(policy.get("decision") or "")
            if policy_decision in {"auto_decide", "route_dse", "defer_question"}:
                return policy_decision, str(policy.get("reason") or "charter_autonomy_policy")
        return "needs_user", "human_input_required"
    if action_type in DISPATCH_ACTION_TYPES or str(candidate.get("allowed_write_policy", "")) == "dispatch":
        return "dispatch_required", "bounded_subagent_or_dispatch_required"
    if action_type in SAFE_TOOL_ACTION_TYPES:
        return "tool_ready", "safe_tool_action_ready"
    if not action_type:
        return "idle", "no_recommended_action"
    return "record_ready", "main_owned_action_ready"


def candidate_summary(candidate: JsonObject) -> JsonObject:
    return {
        "id": candidate.get("id") or "",
        "action_type": candidate.get("action_type") or "",
        "priority": candidate.get("priority") or "",
        "status": candidate.get("status") or "",
        "owner_role": candidate.get("owner_role") or "",
        "reason": candidate.get("recommendation_reason") or candidate.get("reason") or "",
        "command": candidate.get("command") or "",
        "target_objects": candidate.get("target_objects") if isinstance(candidate.get("target_objects"), dict) else {},
    }


def build_question(candidate: JsonObject) -> JsonObject:
    action_type = str(candidate.get("action_type") or "")
    if action_type == "ACT_ASK_DEEP_INTERVIEW_QUESTION":
        prompt = "다음 Deep Interview round에서 가장 중요한 lock-blocking 질문을 하나만 물어야 합니다."
    elif action_type == "ACT_RESOLVE_DECISION":
        prompt = "lock 전에 결정해야 하는 설계/제품 decision을 사용자에게 하나만 선택하게 해야 합니다."
    elif action_type == "ACT_LOCK_SCOPE":
        prompt = "현재 preview와 semantic gates를 보고 scope lock 승인 여부를 사용자에게 확인해야 합니다."
    elif action_type == "ACT_RESOLVE_PENDING_GATE":
        prompt = "pending workflow gate에 대해 사용자 또는 reviewer 결정을 받아야 합니다."
    else:
        prompt = "사용자 입력이 필요한 Action입니다."
    return {
        "prompt": prompt,
        "action": candidate_summary(candidate),
        "policy": {
            "one_question_per_round": True,
            "option_count": 4,
            "require_recommendation": True,
            "allow_custom_answer": True,
        },
    }


def maybe_start_action(ip_dir: Path, candidate: JsonObject, *, mode: str, allow_blocked: bool) -> JsonObject:
    if mode not in {"record", "dispatch_ready"}:
        return {"started": False, "reason": f"mode_{mode}_does_not_start_actions"}
    if not candidate:
        return {"started": False, "reason": "no_candidate"}
    if candidate.get("status") == "blocked" and not allow_blocked:
        return {"started": False, "reason": "candidate_blocked"}
    namespace = argparse.Namespace(
        ip_dir=str(ip_dir),
        candidate_id=str(candidate.get("id") or "recommended"),
        selected_reason=f"Mission Loop selected {candidate.get('action_type') or candidate.get('id')}",
        actor_kind="ai",
        actor_id="oag_mission_loop",
        actor_surface="cli",
        allow_blocked=allow_blocked,
        no_refresh_plan=True,
    )
    return oag_action_record.start_action(namespace)


def tick(args: argparse.Namespace) -> JsonObject:
    ip_dir = oag_paths.ip_root(args.ip_dir)
    with runner_lock(ip_dir, stale_seconds=args.lock_stale_seconds, enabled=not args.no_lock) as lock:
        state = load_state(ip_dir)
        if state.get("status") == "paused" and not args.ignore_pause:
            payload = {
                "schema_version": TICK_SCHEMA,
                "status": "paused",
                "decision": "stop",
                "reason": state.get("pause_reason") or "mission loop paused",
                "ip": ip_dir.name,
                "lock": lock,
            }
            append_jsonl(tick_log_path(ip_dir), payload)
            state["last_tick"] = payload
            save_state(ip_dir, state)
            return {"schema_version": RESULT_SCHEMA, "status": "pass", "tick": payload, "state_path": rel(ip_dir, state_path(ip_dir))}

        guard = oag_orchestration_guard.audit(ip_dir, stale_seconds=args.stale_seconds)
        active_locks = guard.get("active_locks") if isinstance(guard.get("active_locks"), list) else []
        open_action_rows = open_actions(ip_dir)
        charter = oag_action_plan.mission_charter(ip_dir)
        pending_before = oag_pending_questions.summary(ip_dir, charter)
        exclude_candidates = set(pending_before.get("excluded_selectors") if isinstance(pending_before.get("excluded_selectors"), list) else [])
        plan_result = oag_action_plan.build_plan(
            ip_dir,
            write=not args.no_write_plan,
            run_semantic_checks=not args.quick,
            stuck_seconds=args.stuck_seconds,
            exclude_candidates=exclude_candidates,
        )
        candidate = recommended_candidate(plan_result)
        decision, reason = classify_candidate(candidate, ip_dir)
        exploration_plan: JsonObject = {}
        if str(candidate.get("action_type") or "") in SELF_EXPLORE_ACTION_TYPES or decision in {"needs_user", "auto_decide", "route_dse", "defer_question"}:
            exploration_plan = oag_exploration_plan.build_plan(ip_dir, write=False)

        issues: list[dict[str, str]] = []
        if plan_result.get("status") != "pass":
            decision = "blocked"
            reason = "action_plan_failed"
            issues.extend(plan_result.get("issues") if isinstance(plan_result.get("issues"), list) else [])
        elif guard.get("status") == "fail" and active_locks and str(candidate.get("action_type") or "") not in {"ACT_RESOLVE_ORCHESTRATION_HAZARD", "ACT_ORCHESTRATION_RECOVERY"}:
            decision = "blocked"
            reason = "active_orchestration_lock"
            issues.extend(guard.get("issues") if isinstance(guard.get("issues"), list) else [])
        elif open_action_rows and not args.allow_open_action:
            decision = "blocked"
            reason = "open_action_exists"
            issues.append(issue("OPEN_ACTION_EXISTS", "existing open Action must be completed, blocked, or aborted before starting another", open_action_rows[0].get("path", "")))
        elif candidate.get("status") == "blocked" and decision not in {"needs_user", "blocked"}:
            decision = "blocked"
            reason = "candidate_blocked"
        elif not candidate:
            decision = "idle"
            reason = "no_candidate"

        pending_queue: JsonObject = pending_before
        if decision == "defer_question":
            policy = oag_decision_autoresolve.resolve_candidate_policy(ip_dir, candidate)
            queued = oag_pending_questions.enqueue(
                ip_dir,
                candidate=candidate_summary(candidate),
                question=build_question(candidate),
                policy=policy,
                charter=charter,
            )
            pending_queue = oag_pending_questions.summary(ip_dir, charter)
            if queued.get("status") == "not_queued":
                decision = "needs_user"
                reason = str(queued.get("reason") or "checkpoint_question_batching_not_approved")
            elif queued.get("checkpoint_ready") is True:
                decision = "checkpoint_ready"
                reason = str(queued.get("reason") or "pending_questions_checkpoint_ready")
        if decision == "idle" and int(pending_queue.get("question_count") or 0) > 0:
            oag_pending_questions.mark_checkpoint_ready(ip_dir, "no_runnable_non_user_work")
            pending_queue = oag_pending_questions.summary(ip_dir, charter)
            decision = "checkpoint_ready"
            reason = "no_runnable_non_user_work"
        next_tick_count = int(state.get("tick_count") or 0) + 1
        if decision not in {"needs_user", "blocked", "checkpoint_ready"} and int(pending_queue.get("question_count") or 0) > 0 and oag_pending_questions.budget_exhausted(charter, next_tick_count):
            oag_pending_questions.mark_checkpoint_ready(ip_dir, "mission_loop_checkpoint_budget_exhausted")
            pending_queue = oag_pending_questions.summary(ip_dir, charter)
            decision = "checkpoint_ready"
            reason = "mission_loop_checkpoint_budget_exhausted"

        action_record: JsonObject = {}
        if decision in {"record_ready", "tool_ready", "dispatch_required", "self_explore", "auto_decide", "route_dse"} and not args.dry_run:
            action_record = maybe_start_action(ip_dir, candidate, mode=args.mode, allow_blocked=args.allow_blocked)
            if action_record.get("status") == "pass":
                decision = "action_started"
                reason = "action_record_started"
            elif action_record.get("started") is False:
                pass
            else:
                decision = "blocked"
                reason = "action_record_failed"
                issues.extend(action_record.get("issues") if isinstance(action_record.get("issues"), list) else [])

        mission = oag_mission_runtime.latest_active_mission(ip_dir)
        mission_id = str(mission.get("id") or plan_result.get("mission_instance_id") or "")
        completion = oag_mission_runtime.evaluate_mission_completion(ip_dir, mission_id) if mission_id else {}

        payload: JsonObject = {
            "schema_version": TICK_SCHEMA,
            "status": "pass" if not issues else "blocked",
            "decision": decision,
            "reason": reason,
            "ip": ip_dir.name,
            "generated_at": run_common.utc_now(),
            "mode": args.mode,
            "dry_run": bool(args.dry_run),
            "lock": lock,
            "mission": {
                "mission_id": mission_id,
                "template_id": mission.get("template_id") or plan_result.get("mission_template") or "",
                "completion_status": completion.get("status") or "",
            },
            "candidate": candidate_summary(candidate),
            "human_question": build_question(candidate) if decision == "needs_user" else {},
            "decision_autonomy": oag_decision_autoresolve.resolve_candidate_policy(ip_dir, candidate)
            if decision in {"auto_decide", "route_dse", "defer_question", "checkpoint_ready"}
            else {},
            "pending_questions": pending_queue,
            "exploration_plan": {
                "status": exploration_plan.get("status") or "",
                "decision": exploration_plan.get("ask_vs_explore", {}).get("decision") if isinstance(exploration_plan.get("ask_vs_explore"), dict) else "",
                "reason": exploration_plan.get("ask_vs_explore", {}).get("reason") if isinstance(exploration_plan.get("ask_vs_explore"), dict) else "",
                "fingerprint": exploration_plan.get("input_fingerprint", {}).get("sha256") if isinstance(exploration_plan.get("input_fingerprint"), dict) else "",
                "research_prompt": exploration_plan.get("research_prompt") or "",
            },
            "action_record": action_record,
            "open_actions": open_action_rows,
            "guard_summary": {
                "status": guard.get("status"),
                "active_lock_count": len(active_locks),
                "recommendations": guard.get("recommendations") if isinstance(guard.get("recommendations"), list) else [],
            },
            "plan_summary": {
                "status": plan_result.get("status"),
                "candidate_count": plan_result.get("candidate_count"),
                "open_item_count": plan_result.get("open_item_count"),
            },
            "issues": issues,
            "next_instruction": next_instruction(decision, reason, candidate, action_record),
        }

        state["status"] = "blocked" if decision == "blocked" else "waiting_for_user" if decision in {"needs_user", "checkpoint_ready"} else "active"
        state["mode"] = args.mode
        state["tick_count"] = int(state.get("tick_count") or 0) + 1
        state["last_tick"] = payload
        state["last_mission_id"] = mission_id
        state["last_decision"] = decision
        state_file = save_state(ip_dir, state)
        if not args.dry_run:
            append_jsonl(tick_log_path(ip_dir), payload)
        return {
            "schema_version": RESULT_SCHEMA,
            "status": "pass" if payload["status"] != "blocked" else "blocked",
            "state_path": rel(ip_dir, state_file),
            "tick_log_path": rel(ip_dir, tick_log_path(ip_dir)),
            "tick": payload,
        }


def next_instruction(decision: str, reason: str, candidate: JsonObject, action_record: JsonObject) -> str:
    action_type = str(candidate.get("action_type") or "")
    command = str(candidate.get("command") or "")
    if decision == "needs_user":
        return "Ask the user the one highest-impact question, with four options and a recommendation."
    if decision == "auto_decide":
        return "Run oag_decision_autoresolve.py with cited evidence, then refresh the Action plan."
    if decision == "route_dse":
        return "Route a bounded architecture exploration/DSE action before deciding this tradeoff."
    if decision == "defer_question":
        return "Queue this product-defining question for the consolidated checkpoint review."
    if decision == "checkpoint_ready":
        return "Review the batched pending questions at the mission-loop checkpoint before continuing deferred work."
    if decision == "self_explore":
        return "Explore local specs, RTL, and OAG truth first; run the exploration command, then ask only one residual question if needed."
    if decision == "dispatch_required":
        return "Create an OAG dispatch/wavefront task for this Action before any write-capable work."
    if decision == "action_started":
        path = action_record.get("path") or ""
        return f"Execute or route the started Action, then update the Action record: {path}"
    if decision == "tool_ready" and command:
        return f"Run the safe tool command, then update the Action record: {command}"
    if decision == "blocked":
        return f"Resolve blocker before continuing: {reason}"
    if action_type:
        return f"Prepare Action {action_type}; command hint: {command}" if command else f"Prepare Action {action_type}."
    return "No runnable Mission Action was found."


def run_loop(args: argparse.Namespace) -> JsonObject:
    ticks: list[JsonObject] = []
    final: JsonObject = {}
    for _ in range(max(1, args.max_ticks)):
        result = tick(args)
        ticks.append(result.get("tick") if isinstance(result.get("tick"), dict) else result)
        final = result
        decision = str(result.get("tick", {}).get("decision") if isinstance(result.get("tick"), dict) else "")
        if decision in {"blocked", "needs_user", "checkpoint_ready", "self_explore", "auto_decide", "route_dse", "action_started", "idle"}:
            break
    return {
        "schema_version": RESULT_SCHEMA,
        "status": final.get("status") or "pass",
        "tick_count": len(ticks),
        "final_decision": ticks[-1].get("decision") if ticks else "",
        "ticks": ticks,
        "state_path": final.get("state_path") or "",
        "tick_log_path": final.get("tick_log_path") or "",
    }


def pause(args: argparse.Namespace) -> JsonObject:
    ip_dir = oag_paths.ip_root(args.ip_dir)
    state = load_state(ip_dir)
    state["status"] = "paused"
    state["pause_reason"] = args.reason or "paused by operator"
    path = save_state(ip_dir, state)
    return {"schema_version": RESULT_SCHEMA, "status": "pass", "state_path": rel(ip_dir, path), "state": state}


def resume(args: argparse.Namespace) -> JsonObject:
    ip_dir = oag_paths.ip_root(args.ip_dir)
    state = load_state(ip_dir)
    state["status"] = "active"
    state["pause_reason"] = ""
    path = save_state(ip_dir, state)
    return {"schema_version": RESULT_SCHEMA, "status": "pass", "state_path": rel(ip_dir, path), "state": state}


def explain(args: argparse.Namespace) -> JsonObject:
    ip_dir = oag_paths.ip_root(args.ip_dir)
    state = load_state(ip_dir)
    return {
        "schema_version": RESULT_SCHEMA,
        "status": "pass",
        "state_path": rel(ip_dir, state_path(ip_dir)),
        "tick_log_path": rel(ip_dir, tick_log_path(ip_dir)),
        "state": state,
        "last_tick": state.get("last_tick") if isinstance(state.get("last_tick"), dict) else {},
    }


def print_result(payload: JsonObject, *, json_mode: bool) -> int:
    if json_mode:
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        status = payload.get("status")
        tick_payload = payload.get("tick") if isinstance(payload.get("tick"), dict) else {}
        print(f"{str(status).upper()} {RESULT_SCHEMA}: {tick_payload.get('decision') or payload.get('final_decision') or ''} {tick_payload.get('reason') or ''}")
        instruction = tick_payload.get("next_instruction")
        if instruction:
            print(instruction)
    return 0 if payload.get("status") in {"pass", "blocked", "paused"} else 1


def add_common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--ip-dir", required=True)
    parser.add_argument("--mode", choices=("advisory", "record", "dispatch_ready"), default="record")
    parser.add_argument("--quick", action="store_true", help="Use quick Action planning checks.")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--no-lock", action="store_true")
    parser.add_argument("--ignore-pause", action="store_true")
    parser.add_argument("--no-write-plan", action="store_true")
    parser.add_argument("--allow-open-action", action="store_true")
    parser.add_argument("--allow-blocked", action="store_true")
    parser.add_argument("--stuck-seconds", type=int, default=900)
    parser.add_argument("--stale-seconds", type=int, default=1800)
    parser.add_argument("--lock-stale-seconds", type=int, default=1800)
    parser.add_argument("--json", action="store_true")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    tick_parser = sub.add_parser("tick", help="Run one bounded Mission Loop tick.")
    add_common(tick_parser)

    run_parser = sub.add_parser("run", help="Run bounded ticks until the next stop boundary.")
    add_common(run_parser)
    run_parser.add_argument("--max-ticks", type=int, default=5)

    pause_parser = sub.add_parser("pause", help="Pause the Mission Loop for an IP.")
    pause_parser.add_argument("--ip-dir", required=True)
    pause_parser.add_argument("--reason", default="")
    pause_parser.add_argument("--json", action="store_true")

    resume_parser = sub.add_parser("resume", help="Resume the Mission Loop for an IP.")
    resume_parser.add_argument("--ip-dir", required=True)
    resume_parser.add_argument("--json", action="store_true")

    explain_parser = sub.add_parser("explain", help="Show current Mission Loop state.")
    explain_parser.add_argument("--ip-dir", required=True)
    explain_parser.add_argument("--json", action="store_true")

    args = parser.parse_args(argv)
    try:
        if args.command == "tick":
            payload = tick(args)
        elif args.command == "run":
            payload = run_loop(args)
        elif args.command == "pause":
            payload = pause(args)
        elif args.command == "resume":
            payload = resume(args)
        elif args.command == "explain":
            payload = explain(args)
        else:
            payload = {"schema_version": RESULT_SCHEMA, "status": "fail", "issues": [issue("UNKNOWN_COMMAND", str(args.command))]}
    except Exception as exc:
        payload = {"schema_version": RESULT_SCHEMA, "status": "fail", "issues": [issue("MISSION_LOOP_EXCEPTION", str(exc))]}
    return print_result(payload, json_mode=bool(getattr(args, "json", False)))


if __name__ == "__main__":
    raise SystemExit(main())
