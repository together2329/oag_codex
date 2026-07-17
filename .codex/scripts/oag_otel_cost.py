#!/usr/bin/env python3
"""Aggregate Codex OTEL and rollout usage by model and OAG execution."""

from __future__ import annotations

import argparse
import json
import os
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Iterator


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OTEL_LOG = ROOT / ".cache" / "otel" / "codex-logs.jsonl"
DEFAULT_CORRELATION_LOG = ROOT / ".cache" / "otel" / "oag-executions.jsonl"
DEFAULT_LEGACY_START_LOG = ROOT / ".cache" / "subagent_oag_starts.jsonl"
TOKEN_KEYS = ("input_tokens", "cached_input_tokens", "output_tokens", "reasoning_output_tokens")


def empty_tokens() -> dict[str, int]:
    return {key: 0 for key in TOKEN_KEYS}


def add_tokens(target: dict[str, int], value: dict[str, int]) -> None:
    for key in TOKEN_KEYS:
        target[key] = int(target.get(key, 0)) + int(value.get(key, 0))


def subtract_tokens(value: dict[str, int], deduction: dict[str, int]) -> dict[str, int]:
    return {key: max(int(value.get(key, 0)) - int(deduction.get(key, 0)), 0) for key in TOKEN_KEYS}


def token_total(value: dict[str, int]) -> int:
    return int(value.get("input_tokens", 0)) + int(value.get("output_tokens", 0))


def to_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def read_jsonl(path: Path) -> Iterator[dict[str, Any]]:
    try:
        handle = path.open("r", encoding="utf-8", errors="replace")
    except OSError:
        return
    with handle:
        for line in handle:
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except Exception:
                continue
            if isinstance(value, dict):
                yield value


def otel_value(value: Any) -> Any:
    if not isinstance(value, dict):
        return value
    scalar_keys = ("stringValue", "intValue", "doubleValue", "boolValue", "bytesValue")
    for key in scalar_keys:
        if key in value:
            return value[key]
    array_value = value.get("arrayValue")
    if isinstance(array_value, dict):
        return [otel_value(item) for item in array_value.get("values", [])]
    kvlist_value = value.get("kvlistValue")
    if isinstance(kvlist_value, dict):
        return attributes(kvlist_value.get("values", []))
    return value


def attributes(items: Any) -> dict[str, Any]:
    result: dict[str, Any] = {}
    if not isinstance(items, list):
        return result
    for item in items:
        if not isinstance(item, dict):
            continue
        key = str(item.get("key") or "")
        if key:
            result[key] = otel_value(item.get("value"))
    return result


def first(mapping: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in mapping and mapping[key] not in (None, ""):
            return mapping[key]
    return ""


def _list(mapping: dict[str, Any], camel: str, snake: str) -> list[Any]:
    value = mapping.get(camel, mapping.get(snake, []))
    return value if isinstance(value, list) else []


def iter_otlp_log_records(capture: dict[str, Any]) -> Iterator[dict[str, Any]]:
    payload = capture.get("payload", capture)
    if not isinstance(payload, dict):
        return
    for resource_log in _list(payload, "resourceLogs", "resource_logs"):
        if not isinstance(resource_log, dict):
            continue
        resource = resource_log.get("resource")
        resource_attrs = attributes(resource.get("attributes", [])) if isinstance(resource, dict) else {}
        for scope_log in _list(resource_log, "scopeLogs", "scope_logs"):
            if not isinstance(scope_log, dict):
                continue
            for record in _list(scope_log, "logRecords", "log_records"):
                if not isinstance(record, dict):
                    continue
                merged = dict(resource_attrs)
                merged.update(attributes(record.get("attributes", [])))
                body = otel_value(record.get("body"))
                if isinstance(body, dict):
                    merged.update(body)
                elif isinstance(body, str) and body.startswith("{"):
                    try:
                        parsed = json.loads(body)
                    except Exception:
                        parsed = None
                    if isinstance(parsed, dict):
                        merged.update(parsed)
                merged["_time_unix_nano"] = first(record, "timeUnixNano", "time_unix_nano")
                merged["_received_at"] = capture.get("received_at", "")
                yield merged


def usage_from_otel(paths: Iterable[Path]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], dict[str, Any]] = {}
    seen: set[tuple[Any, ...]] = set()
    for path in paths:
        for capture in read_jsonl(path):
            for attrs in iter_otlp_log_records(capture):
                event_name = str(first(attrs, "event.name", "name"))
                event_kind = str(first(attrs, "event.kind", "kind"))
                if event_name != "codex.sse_event" or event_kind != "response.completed":
                    continue
                conversation_id = str(first(attrs, "conversation.id", "conversation_id", "thread.id"))
                model = str(first(attrs, "model", "slug", "gen_ai.request.model")) or "unknown"
                tokens = {
                    "input_tokens": to_int(first(attrs, "input_token_count", "input_tokens", "gen_ai.usage.input_tokens")),
                    "cached_input_tokens": to_int(first(attrs, "cached_token_count", "cached_input_tokens")),
                    "output_tokens": to_int(first(attrs, "output_token_count", "output_tokens", "gen_ai.usage.output_tokens")),
                    "reasoning_output_tokens": to_int(first(attrs, "reasoning_token_count", "reasoning_output_tokens")),
                }
                timestamp = str(first(attrs, "event.timestamp", "_received_at", "_time_unix_nano"))
                fingerprint = (conversation_id, model, timestamp, *(tokens[key] for key in TOKEN_KEYS))
                if fingerprint in seen:
                    continue
                seen.add(fingerprint)
                key = (conversation_id, model)
                item = grouped.setdefault(
                    key,
                    {
                        "conversation_id": conversation_id,
                        "model": model,
                        "models_seen": [model],
                        "source": "codex_otel",
                        "tokens": empty_tokens(),
                        "request_count": 0,
                        "started_at": timestamp,
                        "ended_at": timestamp,
                        "auth_mode": str(first(attrs, "auth_mode", "auth.mode")),
                        "workspace": "",
                        "agent_path": "",
                    },
                )
                add_tokens(item["tokens"], tokens)
                item["request_count"] += 1
                if timestamp:
                    item["started_at"] = min(str(item["started_at"] or timestamp), timestamp)
                    item["ended_at"] = max(str(item["ended_at"] or timestamp), timestamp)
    return list(grouped.values())


def nested(mapping: dict[str, Any], *keys: str) -> Any:
    value: Any = mapping
    for key in keys:
        if not isinstance(value, dict):
            return None
        value = value.get(key)
    return value


def uuid7_milliseconds(value: str) -> int | None:
    try:
        compact = value.replace("-", "")
        return int(compact[:12], 16) if len(compact) >= 12 else None
    except ValueError:
        return None


def parse_rollout(path: Path, workspace_filter: str) -> dict[str, Any] | None:
    session_id = ""
    workspace = ""
    started_at = ""
    ended_at = ""
    agent_path = ""
    parent_session_id = ""
    models: list[str] = []
    best_tokens: dict[str, int] | None = None
    best_total = -1
    inherited_tokens = empty_tokens()
    inherited_total = -1
    live_boundary_seen = False
    plan_type = ""
    task_complete = False
    for row in read_jsonl(path):
        timestamp = str(row.get("timestamp") or "")
        if timestamp:
            started_at = started_at or timestamp
            ended_at = timestamp
        row_type = row.get("type")
        payload = row.get("payload")
        if not isinstance(payload, dict):
            continue
        if row_type == "session_meta":
            if session_id:
                # Forked rollouts embed parent history, including its session_meta.
                # Only the first row identifies the rollout being measured.
                continue
            session_id = str(payload.get("id") or session_id)
            workspace = str(payload.get("cwd") or workspace)
            source = payload.get("source")
            if isinstance(source, dict):
                spawn = nested(source, "subagent", "thread_spawn")
                if isinstance(spawn, dict):
                    agent_path = str(spawn.get("agent_path") or "")
                    parent_session_id = str(spawn.get("parent_thread_id") or "")
            live_boundary_seen = not bool(parent_session_id)
            if workspace_filter and os.path.realpath(workspace) != workspace_filter:
                return None
        elif row_type == "event_msg" and payload.get("type") == "task_started":
            turn_ms = uuid7_milliseconds(str(payload.get("turn_id") or ""))
            session_ms = uuid7_milliseconds(session_id)
            if not parent_session_id or (turn_ms is not None and session_ms is not None and turn_ms >= session_ms):
                live_boundary_seen = True
        elif row_type == "turn_context":
            model = str(payload.get("model") or "")
            if live_boundary_seen and model and model not in models:
                models.append(model)
        elif row_type == "event_msg" and payload.get("type") == "token_count":
            info = payload.get("info")
            total = info.get("total_token_usage") if isinstance(info, dict) else None
            if not isinstance(total, dict):
                continue
            tokens = {
                "input_tokens": to_int(total.get("input_tokens")),
                "cached_input_tokens": to_int(total.get("cached_input_tokens")),
                "output_tokens": to_int(total.get("output_tokens")),
                "reasoning_output_tokens": to_int(total.get("reasoning_output_tokens")),
            }
            current_total = token_total(tokens)
            if parent_session_id and not live_boundary_seen:
                if current_total >= inherited_total:
                    inherited_tokens = tokens
                    inherited_total = current_total
            elif current_total >= best_total:
                best_tokens = tokens
                best_total = current_total
            rate_limits = payload.get("rate_limits")
            if isinstance(rate_limits, dict):
                plan_type = str(rate_limits.get("plan_type") or plan_type)
        elif row_type == "event_msg" and payload.get("type") == "task_complete":
            task_complete = True
    if not session_id:
        return None
    if best_tokens is None:
        best_tokens = dict(inherited_tokens) if not parent_session_id else empty_tokens()
    execution_tokens = subtract_tokens(best_tokens, inherited_tokens) if parent_session_id else best_tokens
    model = models[0] if len(models) == 1 else "mixed:" + ",".join(models or ["unknown"])
    return {
        "conversation_id": session_id,
        "model": model,
        "models_seen": models,
        "model_attribution": "exact" if len(models) == 1 else "mixed_session_total",
        "source": "codex_rollout_backfill",
        "tokens": execution_tokens,
        "cumulative_tokens_at_end": best_tokens,
        "inherited_tokens_at_fork": inherited_tokens if parent_session_id else empty_tokens(),
        "rollout_accounting": "post_fork_delta" if parent_session_id else "root_cumulative_total",
        "request_count": None,
        "started_at": started_at,
        "ended_at": ended_at,
        "auth_mode": "chatgpt_subscription" if plan_type else "",
        "plan_type": plan_type,
        "workspace": workspace,
        "agent_path": agent_path,
        "parent_session_id": parent_session_id,
        "rollout_path": str(path),
        "session_complete": task_complete,
    }


def usage_from_rollouts(roots: Iterable[Path], workspace_filter: str) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    seen: set[Path] = set()
    for root in roots:
        if not root.exists():
            continue
        paths = [root] if root.is_file() else root.rglob("*.jsonl")
        for path in paths:
            resolved = path.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            item = parse_rollout(resolved, workspace_filter)
            if item is not None:
                result.append(item)
    return result


def load_correlations(paths: Iterable[Path]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for path in paths:
        for event in read_jsonl(path):
            ids = event.get("conversation_ids")
            if not isinstance(ids, list):
                ids = [event.get("primary_conversation_id") or event.get("agent_id")]
            for conversation_id in ids:
                key = str(conversation_id or "")
                if not key:
                    continue
                target = result.setdefault(key, {})
                for field, value in event.items():
                    if value not in (None, "", []):
                        target[field] = value
    return result


def merge_sources(otel: list[dict[str, Any]], rollouts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    otel_by_conversation: dict[str, list[dict[str, Any]]] = defaultdict(list)
    rollout_by_conversation: dict[str, dict[str, Any]] = {}
    for item in otel:
        otel_by_conversation[str(item.get("conversation_id") or "")].append(item)
    for item in rollouts:
        rollout_by_conversation[str(item.get("conversation_id") or "")] = item
    result: list[dict[str, Any]] = []
    for conversation_id in sorted(set(otel_by_conversation) | set(rollout_by_conversation)):
        otel_items = otel_by_conversation.get(conversation_id, [])
        rollout = rollout_by_conversation.get(conversation_id)
        if not otel_items:
            assert rollout is not None
            result.append(rollout)
            continue
        if rollout is None:
            result.extend(otel_items)
            continue
        otel_tokens = empty_tokens()
        for item in otel_items:
            add_tokens(otel_tokens, item["tokens"])
        rollout_total = token_total(rollout["tokens"])
        otel_total = token_total(otel_tokens)
        if rollout_total > otel_total:
            selected = dict(rollout)
            selected["available_sources"] = ["codex_otel", "codex_rollout_backfill"]
            selected["source_reconciliation"] = "larger_rollout_session_total_selected"
            result.append(selected)
            continue
        for item in otel_items:
            selected = dict(item)
            for field in (
                "session_complete",
                "rollout_path",
                "parent_session_id",
                "agent_path",
                "plan_type",
            ):
                value = rollout.get(field)
                if value not in (None, "", []):
                    selected[field] = value
            selected["available_sources"] = ["codex_otel", "codex_rollout_backfill"]
            selected["source_reconciliation"] = (
                "sources_agree" if len(otel_items) == 1 and item["tokens"] == rollout["tokens"]
                else "otel_model_breakdown_selected"
            )
            result.append(selected)
    return result


def parse_time(value: str) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def load_rate_card(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {"schema_version": "oag_model_rate_card.v1", "currency": "USD", "rates": []}
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or value.get("schema_version") != "oag_model_rate_card.v1":
        raise ValueError("rate card must use schema_version=oag_model_rate_card.v1")
    if not isinstance(value.get("rates"), list):
        raise ValueError("rate card rates must be a list")
    return value


def select_rate(card: dict[str, Any], model: str, timestamp: str) -> dict[str, Any] | None:
    when = parse_time(timestamp) or datetime.now(timezone.utc)
    candidates: list[dict[str, Any]] = []
    for rate in card.get("rates", []):
        if not isinstance(rate, dict) or rate.get("model") != model:
            continue
        start = parse_time(str(rate.get("effective_from") or ""))
        end = parse_time(str(rate.get("effective_to") or ""))
        if start and when < start:
            continue
        if end and when >= end:
            continue
        candidates.append(rate)
    return candidates[-1] if candidates else None


def calculate_cost(tokens: dict[str, int], rate: dict[str, Any]) -> dict[str, Any]:
    cached = min(tokens["cached_input_tokens"], tokens["input_tokens"])
    non_cached = max(tokens["input_tokens"] - cached, 0)
    reasoning = min(tokens["reasoning_output_tokens"], tokens["output_tokens"])
    visible_output = max(tokens["output_tokens"] - reasoning, 0)
    reasoning_rate = float(rate.get("reasoning_output_usd_per_million", rate["output_usd_per_million"]))
    components = {
        "non_cached_input_usd": non_cached * float(rate["input_usd_per_million"]) / 1_000_000,
        "cached_input_usd": cached * float(rate["cached_input_usd_per_million"]) / 1_000_000,
        "visible_output_usd": visible_output * float(rate["output_usd_per_million"]) / 1_000_000,
        "reasoning_output_usd": reasoning * reasoning_rate / 1_000_000,
    }
    return {"currency": "USD", "components": components, "total": sum(components.values())}


def summarize(items: list[dict[str, Any]], rate_card: dict[str, Any]) -> dict[str, Any]:
    total_tokens = empty_tokens()
    total_cost = 0.0
    priced_accounting = 0
    accounting_sessions = 0
    group_factory = lambda: {  # noqa: E731
        "sessions": 0,
        "priced_sessions": 0,
        "tokens": empty_tokens(),
        "agent_duration_seconds": 0.0,
        "partially_priced_cost_usd": 0.0,
    }
    by_model: dict[str, dict[str, Any]] = defaultdict(group_factory)
    by_task: dict[str, dict[str, Any]] = defaultdict(group_factory)
    by_role: dict[str, dict[str, Any]] = defaultdict(group_factory)
    by_mission: dict[str, dict[str, Any]] = defaultdict(group_factory)
    budget_status = {"within": 0, "warning": 0, "exceeded": 0, "unbudgeted": 0}
    starts: list[datetime] = []
    ends: list[datetime] = []
    complete_sessions = 0
    for item in items:
        start = parse_time(str(item.get("started_at") or ""))
        end = parse_time(str(item.get("ended_at") or ""))
        if start:
            starts.append(start)
        if end:
            ends.append(end)
        duration = max((end - start).total_seconds(), 0.0) if start and end else None
        item["duration_seconds"] = duration
        if item.get("session_complete") is True:
            complete_sessions += 1
        task_tokens = item["tokens"]
        task = str(item.get("task_id") or item.get("dispatch_id") or item.get("agent_path") or item.get("agent_type") or "")
        role = str(item.get("role_name") or item.get("agent_type") or "unattributed")
        mission = str(item.get("mission_id") or item.get("wavefront_run_id") or "unattributed")
        if item.get("source") == "codex_rollout_backfill":
            task = task or "main_and_unattributed_residual"
            item["attributed_tokens"] = task_tokens
            item["attribution_basis"] = str(item.get("rollout_accounting") or "conversation_execution_usage")
        else:
            task = task or "unattributed"
            item["attributed_tokens"] = task_tokens
            item["attribution_basis"] = "conversation_usage"
        included_in_total = token_total(task_tokens) > 0
        item["included_in_project_total"] = included_in_total
        if included_in_total:
            accounting_sessions += 1
            add_tokens(total_tokens, task_tokens)
            model_group = by_model[item["model"]]
            model_group["sessions"] += 1
            model_group["agent_duration_seconds"] += duration or 0.0
            add_tokens(model_group["tokens"], task_tokens)
        else:
            model_group = None
        task_group = by_task[task]
        task_group["sessions"] += 1
        task_group["agent_duration_seconds"] += duration or 0.0
        add_tokens(task_group["tokens"], task_tokens)
        for group in (by_role[role], by_mission[mission]):
            group["sessions"] += 1
            group["agent_duration_seconds"] += duration or 0.0
            add_tokens(group["tokens"], task_tokens)
        max_tokens = to_int(item.get("max_total_tokens"))
        warning_tokens = to_int(item.get("warning_total_tokens"))
        actual_tokens = token_total(task_tokens)
        if not max_tokens:
            item["budget_status"] = "unbudgeted"
            item["budget_ratio"] = None
        else:
            item["budget_ratio"] = actual_tokens / max_tokens
            item["budget_status"] = "exceeded" if actual_tokens > max_tokens else "warning" if actual_tokens >= warning_tokens else "within"
        budget_status[item["budget_status"]] += 1
        rate = select_rate(rate_card, item["model"], str(item.get("started_at") or ""))
        if rate is not None:
            item["cost"] = calculate_cost(task_tokens, rate)
            item["cost_basis"] = str(rate_card.get("billing_basis") or "configured_rate_card")
            task_group["priced_sessions"] += 1
            task_group["partially_priced_cost_usd"] += float(item["cost"]["total"])
            for group in (by_role[role], by_mission[mission]):
                group["priced_sessions"] += 1
                group["partially_priced_cost_usd"] += float(item["cost"]["total"])
            if included_in_total and model_group is not None:
                cost = float(item["cost"]["total"])
                total_cost += cost
                model_group["priced_sessions"] += 1
                model_group["partially_priced_cost_usd"] += cost
                priced_accounting += 1
        else:
            item["cost"] = None
            item["cost_basis"] = "unpriced"
    def finalize_groups(groups: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
        for group in groups.values():
            priced_count = int(group["priced_sessions"])
            session_count = int(group["sessions"])
            partial = float(group["partially_priced_cost_usd"])
            group["cost_usd"] = partial if priced_count == session_count and session_count else None
            if not priced_count:
                group["partially_priced_cost_usd"] = None
        return dict(sorted(groups.items()))

    earliest = min(starts).isoformat().replace("+00:00", "Z") if starts else None
    latest = max(ends).isoformat().replace("+00:00", "Z") if ends else None
    wall_span = max((max(ends) - min(starts)).total_seconds(), 0.0) if starts and ends else None
    return {
        "sessions": len(items),
        "accounting_sessions": accounting_sessions,
        "complete_sessions": complete_sessions,
        "incomplete_or_unknown_sessions": len(items) - complete_sessions,
        "started_at": earliest,
        "ended_at": latest,
        "wall_span_seconds": wall_span,
        "agent_duration_seconds": sum(float(item.get("duration_seconds") or 0.0) for item in items),
        "priced_accounting_sessions": priced_accounting,
        "unpriced_accounting_sessions": accounting_sessions - priced_accounting,
        "tokens": total_tokens,
        "non_cached_input_tokens": max(total_tokens["input_tokens"] - total_tokens["cached_input_tokens"], 0),
        "cost_usd": total_cost if priced_accounting == accounting_sessions and accounting_sessions else None,
        "partially_priced_cost_usd": total_cost if priced_accounting else None,
        "by_model": finalize_groups(by_model),
        "by_task": finalize_groups(by_task),
        "by_role": finalize_groups(by_role),
        "by_mission": finalize_groups(by_mission),
        "budget_status": budget_status,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--otel-log", action="append", default=[])
    parser.add_argument("--correlation-log", default=str(DEFAULT_CORRELATION_LOG))
    parser.add_argument("--legacy-start-log", default=str(DEFAULT_LEGACY_START_LOG))
    parser.add_argument("--rollout-root", action="append", default=[])
    parser.add_argument("--workspace", default="")
    parser.add_argument("--rate-card")
    parser.add_argument("--output")
    args = parser.parse_args()

    workspace_filter = os.path.realpath(args.workspace) if args.workspace else ""
    otel_paths = [Path(path).expanduser() for path in args.otel_log] or [DEFAULT_OTEL_LOG]
    rollout_roots = [Path(path).expanduser() for path in args.rollout_root]
    correlation_paths = [Path(args.legacy_start_log).expanduser(), Path(args.correlation_log).expanduser()]
    correlations = load_correlations(correlation_paths)
    otel_items = usage_from_otel(otel_paths)
    for item in otel_items:
        correlation = correlations.get(item["conversation_id"], {})
        for key, value in correlation.items():
            if key not in item or item[key] in (None, "", []):
                item[key] = value
        item["workspace"] = str(item.get("cwd") or item.get("workspace") or "")
    if workspace_filter:
        otel_items = [item for item in otel_items if os.path.realpath(str(item.get("workspace") or "")) == workspace_filter]
    rollout_items = usage_from_rollouts(rollout_roots, workspace_filter)
    items = merge_sources(otel_items, rollout_items)
    for item in items:
        correlation = correlations.get(item["conversation_id"], {})
        for key, value in correlation.items():
            if key not in item or item[key] in (None, "", []):
                item[key] = value
    items.sort(key=lambda item: (str(item.get("started_at") or ""), item["conversation_id"]))
    rate_card = load_rate_card(Path(args.rate_card).expanduser() if args.rate_card else None)
    summary = summarize(items, rate_card)
    report = {
        "schema_version": "oag_codex_cost_report.v1",
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "workspace": workspace_filter,
        "data_sources": {
            "otel_logs": [str(path) for path in otel_paths],
            "correlation_logs": [str(path) for path in correlation_paths],
            "rollout_roots": [str(path) for path in rollout_roots],
        },
        "monetary_cost_note": (
            "Token counts are measured. Monetary cost is emitted only for sessions covered by the supplied "
            "effective-dated rate card; ChatGPT subscription usage is not an API-token invoice."
        ),
        "summary": summary,
        "sessions": items,
    }
    text = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output:
        output = Path(args.output).expanduser()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(text, encoding="utf-8")
    print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
