#!/usr/bin/env python3
from __future__ import annotations

import json
import importlib
import sys
from pathlib import Path
from typing import Any

if __package__:
    from . import oag_paths
    from . import oag_run_control_common as run_common
else:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    oag_paths = importlib.import_module("oag_paths")
    run_common = importlib.import_module("oag_run_control_common")


SCHEMA_VERSION = "oag_pending_questions.v1"
REL_PATH = "knowledge/mission_loop/pending_questions.json"
READY_STATUSES = {"checkpoint_ready", "ready_for_checkpoint", "ready"}

JsonObject = dict[str, Any]


def text(value: Any) -> str:
    return str(value or "").strip()


def as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def path(ip_dir: Path) -> Path:
    return oag_paths.legacy_or_hidden(ip_dir, REL_PATH)


def default_state(ip_dir: Path) -> JsonObject:
    now = run_common.utc_now()
    return {
        "schema_version": SCHEMA_VERSION,
        "ip": ip_dir.name,
        "status": "active",
        "created_at": now,
        "updated_at": now,
        "checkpoint_reason": "",
        "questions": [],
        "stats": {"enqueued_count": 0},
    }


def normalize_state(ip_dir: Path, payload: JsonObject) -> JsonObject:
    state = dict(payload)
    questions = [item for item in as_list(state.get("questions")) if isinstance(item, dict)]
    state["schema_version"] = SCHEMA_VERSION
    state["ip"] = text(state.get("ip")) or ip_dir.name
    state["status"] = text(state.get("status")) or "active"
    state["created_at"] = text(state.get("created_at")) or run_common.utc_now()
    state["updated_at"] = text(state.get("updated_at")) or run_common.utc_now()
    state["checkpoint_reason"] = text(state.get("checkpoint_reason"))
    state["questions"] = questions
    stats_raw = state.get("stats")
    state["stats"] = stats_raw if isinstance(stats_raw, dict) else {"enqueued_count": len(questions)}
    return state


def read_state(ip_dir: Path) -> JsonObject:
    state_path = path(ip_dir)
    if not state_path.is_file():
        return default_state(ip_dir)
    try:
        payload = json.loads(state_path.read_text(encoding="utf-8"))
    except OSError as exc:
        state = default_state(ip_dir)
        state["status"] = "checkpoint_ready"
        state["checkpoint_reason"] = "pending_questions_read_error"
        state["load_error"] = str(exc)
        return state
    except json.JSONDecodeError as exc:
        state = default_state(ip_dir)
        state["status"] = "checkpoint_ready"
        state["checkpoint_reason"] = "pending_questions_parse_error"
        state["load_error"] = str(exc)
        return state
    if not isinstance(payload, dict):
        state = default_state(ip_dir)
        state["status"] = "checkpoint_ready"
        state["checkpoint_reason"] = "pending_questions_root_invalid"
        state["load_error"] = "pending question queue root is not an object"
        return state
    if payload.get("schema_version") != SCHEMA_VERSION:
        state = normalize_state(ip_dir, payload)
        state["status"] = "checkpoint_ready"
        state["checkpoint_reason"] = "pending_questions_schema_mismatch"
        state["load_error"] = f"expected {SCHEMA_VERSION}, found {text(payload.get('schema_version')) or '<missing>'}"
        return state
    return normalize_state(ip_dir, payload)


def write_state(ip_dir: Path, payload: JsonObject) -> Path:
    state = normalize_state(ip_dir, payload)
    state["updated_at"] = run_common.utc_now()
    out_path = path(ip_dir)
    run_common.write_json(out_path, state)
    return out_path


def is_checkpoint_ready(payload: JsonObject) -> bool:
    return text(payload.get("status")).lower() in READY_STATUSES or payload.get("checkpoint_ready") is True


def pending_questions(payload: JsonObject) -> list[JsonObject]:
    return [item for item in as_list(payload.get("questions")) if isinstance(item, dict) and text(item.get("status") or "pending") == "pending"]


def approved_checkpoint_batching(charter: JsonObject) -> bool:
    approval_raw = charter.get("approval")
    approval: JsonObject = approval_raw if isinstance(approval_raw, dict) else {}
    actor_raw = approval.get("actor")
    actor: JsonObject = actor_raw if isinstance(actor_raw, dict) else {}
    autonomy_raw = charter.get("autonomy")
    autonomy: JsonObject = autonomy_raw if isinstance(autonomy_raw, dict) else {}
    approved = (
        charter.get("approved") is True
        or text(charter.get("status")).lower() == "approved"
        or approval.get("approved") is True
        or text(approval.get("status")).lower() == "approved"
    )
    human = text(actor.get("kind")).lower() == "human"
    batching = text(charter.get("question_batching") or autonomy.get("question_batching")).lower()
    return approved and human and batching == "checkpoint"


def int_value(*values: Any) -> int:
    for value in values:
        if isinstance(value, int) and not isinstance(value, bool) and value > 0:
            return value
    return 0


def queue_limits(charter: JsonObject) -> JsonObject:
    question_policy_raw = charter.get("question_policy")
    question_policy: JsonObject = question_policy_raw if isinstance(question_policy_raw, dict) else {}
    autonomy_raw = charter.get("autonomy")
    autonomy: JsonObject = autonomy_raw if isinstance(autonomy_raw, dict) else {}
    budgets_raw = charter.get("budgets")
    budgets: JsonObject = budgets_raw if isinstance(budgets_raw, dict) else {}
    return {
        "max_deferred_questions": int_value(
            question_policy.get("max_deferred_questions"),
            autonomy.get("max_deferred_questions"),
            budgets.get("max_deferred_questions"),
        ),
        "max_ticks_before_checkpoint": int_value(
            question_policy.get("max_ticks_before_checkpoint"),
            autonomy.get("max_ticks_before_checkpoint"),
            budgets.get("max_ticks_before_checkpoint"),
            budgets.get("max_mission_loop_ticks_before_checkpoint"),
        ),
    }


def budget_exhausted(charter: JsonObject, tick_count: int) -> bool:
    limit = int(queue_limits(charter).get("max_ticks_before_checkpoint") or 0)
    return limit > 0 and tick_count >= limit


def candidate_selector(candidate: JsonObject, policy: JsonObject) -> str:
    decision_id = text(policy.get("decision_id"))
    if decision_id:
        return f"decision:{decision_id}"
    return text(candidate.get("id")) or text(candidate.get("action_type"))


def exclusion_selectors(payload: JsonObject) -> set[str]:
    selectors: set[str] = set()
    for item in pending_questions(payload):
        selector = text(item.get("candidate_selector"))
        if selector:
            selectors.add(selector)
        candidate_raw = item.get("candidate")
        candidate: JsonObject = candidate_raw if isinstance(candidate_raw, dict) else {}
        candidate_id = text(candidate.get("id"))
        if candidate_id:
            selectors.add(candidate_id)
        policy_raw = item.get("decision_autonomy")
        policy: JsonObject = policy_raw if isinstance(policy_raw, dict) else {}
        decision_id = text(policy.get("decision_id"))
        if decision_id:
            selectors.add(f"decision:{decision_id}")
    return selectors


def enqueue(
    ip_dir: Path,
    *,
    candidate: JsonObject,
    question: JsonObject,
    policy: JsonObject,
    charter: JsonObject,
) -> JsonObject:
    state = read_state(ip_dir)
    if not approved_checkpoint_batching(charter):
        return {
            "status": "not_queued",
            "reason": "checkpoint_question_batching_not_approved",
            "state": state,
            "path": run_common.rel_to_ip(ip_dir, path(ip_dir)),
        }
    selector = candidate_selector(candidate, policy)
    for item in pending_questions(state):
        if text(item.get("candidate_selector")) == selector:
            return {
                "status": "already_queued",
                "reason": "pending_question_already_queued",
                "state": state,
                "path": run_common.rel_to_ip(ip_dir, path(ip_dir)),
            }
    questions = pending_questions(state)
    now = run_common.utc_now()
    question_id = f"PQ_{len(questions) + 1:04d}"
    questions.append(
        {
            "id": question_id,
            "status": "pending",
            "created_at": now,
            "updated_at": now,
            "candidate_selector": selector,
            "candidate": candidate,
            "human_question": question,
            "decision_autonomy": policy,
        }
    )
    state["questions"] = questions
    stats_raw = state.get("stats")
    stats: JsonObject = stats_raw if isinstance(stats_raw, dict) else {}
    stats["enqueued_count"] = int(stats.get("enqueued_count") or 0) + 1
    state["stats"] = stats
    max_deferred = int(queue_limits(charter).get("max_deferred_questions") or 0)
    if max_deferred > 0 and len(questions) >= max_deferred:
        state["status"] = "checkpoint_ready"
        state["checkpoint_reason"] = "max_deferred_questions_reached"
    else:
        state["status"] = "active"
        state["checkpoint_reason"] = ""
    out_path = write_state(ip_dir, state)
    return {
        "status": "queued",
        "reason": text(state.get("checkpoint_reason")) or "question_deferred_to_checkpoint",
        "checkpoint_ready": is_checkpoint_ready(state),
        "question_id": question_id,
        "question_count": len(questions),
        "state": state,
        "path": run_common.rel_to_ip(ip_dir, out_path),
    }


def mark_checkpoint_ready(ip_dir: Path, reason: str) -> JsonObject:
    state = read_state(ip_dir)
    if pending_questions(state):
        state["status"] = "checkpoint_ready"
        state["checkpoint_reason"] = reason
        write_state(ip_dir, state)
    return state


def summary(ip_dir: Path, charter: JsonObject | None = None) -> JsonObject:
    state = read_state(ip_dir)
    questions = pending_questions(state)
    ready = is_checkpoint_ready(state)
    if charter is not None:
        max_deferred = int(queue_limits(charter).get("max_deferred_questions") or 0)
        ready = ready or (max_deferred > 0 and len(questions) >= max_deferred)
    return {
        "path": REL_PATH,
        "exists": path(ip_dir).is_file(),
        "ready": ready,
        "status": text(state.get("status")),
        "checkpoint_reason": text(state.get("checkpoint_reason")),
        "question_count": len(questions),
        "questions": questions,
        "excluded_selectors": sorted(exclusion_selectors(state)),
    }
