from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from pathlib import Path, PurePosixPath

from oag_dispatch_support import (
    DISPATCH_INTEGRITY_FIELDS,
    Issue,
    JsonObject,
    JsonValue,
    hash_known_paths,
    issue,
    load_json,
    dispatch_scope_hash,
    dispatch_integrity_fields,
    nested_ip_generated_artifact,
    normalize_rel,
    path_matches,
    project_rel,
    resolve_project_path,
    schema_issues,
    sha256,
)
import oag_paths
from oag_dispatch_wavefront import (
    WAVEFRONT_FIELDS,
    collect_wavefront_claim_issues,
    dispatch_has_wavefront_metadata,
    is_canonical_aggregate_path,
    is_shard_scope_path,
    requires_shard_scope,
)
from oag_dispatch_support import git_status_paths

RECEIPT_SAFE_STATUSES = {
    "HANDOFF_PASS",
    "STATIC_HANDOFF_PASS",
    "RTL_HANDOFF_PASS",
    "FAIL",
    "BLOCKED",
    "INCONCLUSIVE",
}
LEGACY_RECEIPT_STATUSES = {"PASS"}
FORBIDDEN_STATUS_WORDS = ("COMPLETE", "DONE", "SIGNOFF", "RELEASED", "CLOSED")
WAVEFRONT_ABORT_STATUSES = {"blocked", "failed", "inconclusive"}
MIRRORED_SCALAR_FIELDS = ("role_name", "stage", "ip_id", "registered_id")
MIRRORED_LIST_FIELDS = ("owned_obligations", "contracts", "allowed_write_paths")
ACTION_INSTANCE_SCHEMA = "oag_action_instance.v1"
ACTION_INDEX_SCHEMA = "oag_action_index.v1"
MISSION_INSTANCE_SCHEMA = "oag_mission_instance.v1"
MISSION_INDEX_SCHEMA = "oag_mission_index.v1"
ACTION_ID_RE = re.compile(r"^ACT_RUN_[A-Za-z0-9_.:-]+$")
MISSION_ID_RE = re.compile(r"^MISSION_RUN_[A-Za-z0-9_.:-]+$")
DECISION_ID_RE = re.compile(r"^DEC_[A-Za-z0-9_.:-]+$")
OUTPUT_SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
ACTION_TERMINAL_STATUSES = {"accepted", "rejected", "blocked", "failed", "inconclusive", "aborted"}
MISSION_TERMINAL_STATUSES = {"completed", "blocked", "superseded", "abandoned"}
WAVEFRONT_ACTIVE_STATUSES = {"claimed", "review_pending"}
WAVEFRONT_DECISION_STATUSES = {"handoff_pass", "closed", "waived", "blocked", "failed", "inconclusive"}
WAVEFRONT_APPROVED_TERMINAL_STATUSES = {"handoff_pass", "closed", "waived"}


def string_list(payload: JsonObject, *fields: str) -> list[str]:
    values: list[str] = []
    for field in fields:
        raw = payload.get(field)
        if isinstance(raw, list):
            values.extend(str(item) for item in raw if isinstance(item, str))
    return sorted(set(values))


def filesystem_delta(dispatch: JsonObject) -> list[str]:
    ip_rel = str(dispatch.get("ip_dir") or "")
    baseline = dispatch.get("baseline") if isinstance(dispatch.get("baseline"), dict) else {}
    previous_hashes = baseline.get("file_hashes") if isinstance(baseline.get("file_hashes"), dict) else {}
    current_hashes = hash_known_paths([ip_rel])
    changed = {
        path
        for path, digest in current_hashes.items()
        if str(previous_hashes.get(path) or "") != digest
    }
    changed.update(str(path) for path in previous_hashes if path not in current_hashes)
    return sorted(changed)


def actual_delta(dispatch: JsonObject) -> tuple[list[str], list[str]]:
    ip_rel = str(dispatch.get("ip_dir") or "")
    _, current = git_status_paths(ip_rel)
    baseline = dispatch.get("baseline") if isinstance(dispatch.get("baseline"), dict) else {}
    previous = baseline.get("git_status_paths") if isinstance(baseline.get("git_status_paths"), list) else []
    previous_set = {str(item) for item in previous}
    delta = sorted({path for path in current if path not in previous_set} | set(filesystem_delta(dispatch)))
    return current, delta


def append_schema_issues(issues: list[Issue], schema_name: str, document: JsonObject, prefix: str) -> None:
    for item in schema_issues(schema_name, document):
        issues.append(issue(f"{prefix}_{item['code']}", item["message"], item["path"]))


def json_shape_name(payload: JsonValue) -> str:
    if payload is None:
        return "null"
    if isinstance(payload, list):
        return "array"
    if isinstance(payload, str):
        return "string"
    if isinstance(payload, bool):
        return "boolean"
    if isinstance(payload, int | float):
        return "number"
    return type(payload).__name__


def load_json_object(path: Path, artifact_name: str, issue_code: str, issues: list[Issue]) -> JsonObject:
    try:
        payload = load_json(path)
    except (OSError, ValueError) as exc:
        issues.append(issue(issue_code, f"cannot load {artifact_name}: {exc}", project_rel(path)))
        return {}
    if not isinstance(payload, dict):
        issues.append(
            issue(
                f"{issue_code}_SHAPE",
                f"{artifact_name} JSON must be an object, got {json_shape_name(payload)}",
                project_rel(path),
            )
        )
        return {}
    return payload


def wavefront_task_for_dispatch(dispatch: JsonObject) -> JsonObject:
    run_id = str(dispatch.get("wavefront_run_id") or "")
    task_id = str(dispatch.get("task_id") or "")
    ip_rel = str(dispatch.get("ip_dir") or "")
    if not run_id or not task_id or not ip_rel:
        return {}
    graph_path = oag_paths.legacy_or_hidden(resolve_project_path(ip_rel), f"ontology/runs/{run_id}/wavefront_task_graph.json")
    try:
        graph = load_json(graph_path)
    except (OSError, RuntimeError, ValueError):
        return {}
    if not isinstance(graph, dict):
        return {}
    for task in graph.get("tasks", []):
        if isinstance(task, dict) and str(task.get("task_id") or "") == task_id:
            return task
    return {}


def wavefront_sibling_scope_paths(dispatch: JsonObject) -> list[str]:
    run_id = str(dispatch.get("wavefront_run_id") or "")
    task_id = str(dispatch.get("task_id") or "")
    ip_rel = str(dispatch.get("ip_dir") or "")
    if not run_id or not task_id or not ip_rel:
        return []

    graph_path = oag_paths.legacy_or_hidden(resolve_project_path(ip_rel), f"ontology/runs/{run_id}/wavefront_task_graph.json")
    try:
        graph = load_json(graph_path)
    except (OSError, ValueError):
        return []
    if not isinstance(graph, dict):
        return []

    sibling_paths: list[str] = []
    active_statuses = {"claimed", "review_pending", "handoff_pass"}
    ip_prefix = ip_rel.rstrip("/")
    for task in graph.get("tasks", []):
        if not isinstance(task, dict):
            continue
        sibling_task_id = str(task.get("task_id") or "")
        if not sibling_task_id or sibling_task_id == task_id:
            continue
        if str(task.get("status") or "") not in active_statuses:
            continue

        receipt_path = str(task.get("receipt_path") or "")
        if receipt_path:
            normalized_receipt = normalize_rel(receipt_path)
            if ip_prefix in {"", "."} or normalized_receipt == ip_prefix or normalized_receipt.startswith(f"{ip_prefix}/"):
                sibling_paths.append(normalized_receipt)
            else:
                sibling_paths.append(f"{ip_prefix}/{normalized_receipt}")

        for raw_path in task.get("allowed_write_paths") or []:
            rel_path = str(raw_path).strip("/")
            if rel_path:
                sibling_paths.append(f"{ip_prefix}/{rel_path}")

    return sorted(set(sibling_paths))


def string_items(value: JsonValue) -> list[str] | None:
    if not isinstance(value, list) or any(not isinstance(item, str) or not item for item in value):
        return None
    return list(value)


def load_json_dict_if_valid(path: Path) -> JsonObject:
    try:
        payload = load_json(path)
    except (OSError, ValueError):
        return {}
    return payload if isinstance(payload, dict) else {}


def safe_ip_artifact(path: Path, ip_dir: Path) -> tuple[bool, Issue | None]:
    try:
        resolved = path.resolve(strict=True)
        resolved.relative_to(ip_dir.resolve(strict=True))
    except FileNotFoundError:
        return False, None
    except (OSError, RuntimeError, ValueError):
        return False, issue(
            "PARENT_ORCHESTRATION_PATH_ESCAPE",
            "parent orchestration path resolves outside the IP root or cannot be resolved safely",
            str(path),
        )
    return True, None


def baseline_contains(dispatch: JsonObject, paths: list[str]) -> bool:
    baseline = dispatch.get("baseline") if isinstance(dispatch.get("baseline"), dict) else {}
    hashes = baseline.get("file_hashes") if isinstance(baseline.get("file_hashes"), dict) else {}
    return all(path in hashes and isinstance(hashes.get(path), str) and bool(hashes.get(path)) for path in paths)


def exact_nonnegative_int(value: JsonValue) -> bool:
    return type(value) is int and value >= 0


def parse_timestamp(value: JsonValue) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else None


def normalized_ip_reference(value: JsonValue) -> str | None:
    if not isinstance(value, str) or not value or "\\" in value or value.startswith("/"):
        return None
    candidate = value[2:] if value.startswith("./") else value
    path = PurePosixPath(candidate)
    if not path.parts or any(part in {"", ".", ".."} for part in path.parts):
        return None
    return path.as_posix()


def action_index_row(action: JsonObject) -> JsonObject:
    result = action.get("result") if isinstance(action.get("result"), dict) else {}
    return {
        "id": action.get("id") or "",
        "action_type": action.get("action_type") or "",
        "status": action.get("status") or "",
        "candidate_ref": action.get("candidate_ref") or "",
        "mission_instance_refs": action.get("mission_instance_refs") if isinstance(action.get("mission_instance_refs"), list) else [],
        "started_at": action.get("started_at") or "",
        "completed_at": action.get("completed_at") or "",
        "selected_reason": action.get("selected_reason") or "",
        "summary": result.get("summary") or "",
        "path": f"{action.get('id')}.json",
    }


def mission_index_row(mission: JsonObject) -> JsonObject:
    recommendation = mission.get("current_recommended_action") if isinstance(mission.get("current_recommended_action"), dict) else {}
    action_refs = mission.get("action_instance_refs") if isinstance(mission.get("action_instance_refs"), list) else []
    return {
        "id": mission.get("id") or "",
        "template_id": mission.get("template_id") or "",
        "status": mission.get("status") or "",
        "started_at": mission.get("started_at") or "",
        "last_observed_at": mission.get("last_observed_at") or "",
        "completed_at": mission.get("completed_at") or "",
        "action_count": len(action_refs),
        "current_recommended_action_type": recommendation.get("action_type"),
        "path": f"{mission.get('id')}.json",
    }


def validate_current_index(
    path: Path,
    *,
    schema_version: str,
    collection: str,
    expected_ip: str,
    ip_dir: Path,
) -> tuple[bool, dict[str, JsonObject], list[Issue]]:
    index_issues: list[Issue] = []
    payload = load_json_dict_if_valid(path)
    rows = payload.get(collection)
    counts = payload.get("counts")
    expected_top_keys = {"schema_version", "generated_at", "ip", collection, "counts"}
    if (
        set(payload) != expected_top_keys
        or payload.get("schema_version") != schema_version
        or str(payload.get("ip") or "") != expected_ip
        or not isinstance(payload.get("generated_at"), str)
        or not payload.get("generated_at")
        or not isinstance(rows, list)
        or not isinstance(counts, dict)
        or any(not isinstance(row, dict) for row in rows)
        or any(not exact_nonnegative_int(value) for value in counts.values())
    ):
        return False, {}, index_issues
    row_ids = [str(row.get("id") or "") for row in rows]
    if any(not item_id for item_id in row_ids) or len(row_ids) != len(set(row_ids)):
        return False, {}, index_issues

    is_action = collection == "actions"
    id_re = ACTION_ID_RE if is_action else MISSION_ID_RE
    instance_glob = "ACT_RUN_*.json" if is_action else "MISSION_RUN_*.json"
    instance_schema = "oag_action_instance.schema.json" if is_action else "oag_mission_instance.schema.json"
    projector = action_index_row if is_action else mission_index_row
    instance_paths = sorted(path.parent.glob(instance_glob))
    if {instance_path.stem for instance_path in instance_paths} != set(row_ids):
        return False, {}, index_issues
    for instance_path in instance_paths:
        safe, path_issue = safe_ip_artifact(instance_path, ip_dir)
        if path_issue:
            index_issues.append(path_issue)
            return False, {}, index_issues
        if not safe:
            return False, {}, index_issues
    instances: dict[str, JsonObject] = {}
    for item_id, row in zip(row_ids, rows):
        expected_name = f"{item_id}.json"
        if (
            id_re.fullmatch(item_id) is None
            or row.get("path") != expected_name
            or (not is_action and not exact_nonnegative_int(row.get("action_count")))
        ):
            return False, {}, index_issues
        instance_path = path.parent / expected_name
        safe, path_issue = safe_ip_artifact(instance_path, ip_dir)
        if path_issue:
            index_issues.append(path_issue)
            return False, {}, index_issues
        if not safe:
            return False, {}, index_issues
        instance = load_json_dict_if_valid(instance_path)
        if (
            str(instance.get("id") or "") != item_id
            or bool(schema_issues(instance_schema, instance))
            or row != projector(instance)
        ):
            return False, {}, index_issues
        instances[item_id] = instance

    if is_action:
        expected_counts = {
            "total": len(rows),
            "open": sum(1 for instance in instances.values() if instance.get("status") not in ACTION_TERMINAL_STATUSES),
            "terminal": sum(1 for instance in instances.values() if instance.get("status") in ACTION_TERMINAL_STATUSES),
        }
    else:
        expected_counts = {
            "total": len(rows),
            "active": sum(1 for instance in instances.values() if instance.get("status") == "active"),
            "terminal": sum(1 for instance in instances.values() if instance.get("status") in MISSION_TERMINAL_STATUSES),
        }
    if counts != expected_counts:
        return False, {}, index_issues
    return True, instances, index_issues


def wavefront_parent_orchestration_scope(dispatch: JsonObject) -> tuple[list[str], list[Issue]]:
    """Validate the complete parent Action/Mission closure for one wavefront dispatch."""
    path_issues: list[Issue] = []
    if not dispatch_has_wavefront_metadata(dispatch):
        return [], path_issues
    dispatch_id = str(dispatch.get("dispatch_id") or "")
    run_id = str(dispatch.get("wavefront_run_id") or "")
    task_id = str(dispatch.get("task_id") or "")
    ip_rel = str(dispatch.get("ip_dir") or "")
    if not dispatch_id or not run_id or not task_id or not ip_rel:
        return [], path_issues

    ip_dir = resolve_project_path(ip_rel)
    action_dir = oag_paths.legacy_or_hidden(ip_dir, "knowledge/actions")
    mission_dir = oag_paths.legacy_or_hidden(ip_dir, "knowledge/missions")
    for directory in (action_dir, mission_dir):
        safe, path_issue = safe_ip_artifact(directory, ip_dir)
        if path_issue:
            path_issues.append(path_issue)
        if not safe or not directory.is_dir():
            return [], path_issues

    linked_actions: dict[str, JsonObject] = {}
    mission_to_actions: dict[str, set[str]] = {}
    for action_path in sorted(action_dir.glob("ACT_RUN_*.json")):
        safe, path_issue = safe_ip_artifact(action_path, ip_dir)
        if path_issue:
            path_issues.append(path_issue)
            return [], path_issues
        if not safe:
            continue
        action = load_json_dict_if_valid(action_path)
        action_id = str(action.get("id") or "")
        result = action.get("result") if isinstance(action.get("result"), dict) else {}
        dispatch_ids = string_items(result.get("dispatch_ids"))
        wavefront_refs = result.get("wavefront_refs")
        mission_ids = string_items(action.get("mission_instance_refs"))
        exact_ref = isinstance(wavefront_refs, list) and any(
            isinstance(ref, dict)
            and str(ref.get("dispatch_id") or "") == dispatch_id
            and str(ref.get("run_id") or "") == run_id
            and str(ref.get("task_id") or "") == task_id
            for ref in wavefront_refs
        )
        linked_by_id = dispatch_ids is not None and dispatch_id in dispatch_ids and exact_ref
        valid_mission_ids = mission_ids is not None and bool(mission_ids) and all(MISSION_ID_RE.fullmatch(item) for item in mission_ids)
        if (
            action.get("schema_version") != ACTION_INSTANCE_SCHEMA
            or bool(schema_issues("oag_action_instance.schema.json", action))
            or not action_id
            or action_path.stem != action_id
            or not linked_by_id
            or not valid_mission_ids
        ):
            if linked_by_id:
                return [], path_issues
            continue
        linked_actions[action_id] = action
        for mission_id in mission_ids or []:
            mission_to_actions.setdefault(mission_id, set()).add(action_id)

    if not linked_actions:
        return [], path_issues

    action_index = action_dir / "_index.json"
    safe, path_issue = safe_ip_artifact(action_index, ip_dir)
    if path_issue:
        path_issues.append(path_issue)
    action_paths = [project_rel(action_dir / f"{action_id}.json") for action_id in linked_actions]
    action_index_path = project_rel(action_index) if safe else ""
    action_index_valid, indexed_actions, action_index_issues = validate_current_index(
        action_index,
        schema_version=ACTION_INDEX_SCHEMA,
        collection="actions",
        expected_ip=ip_dir.name,
        ip_dir=ip_dir,
    ) if safe else (False, {}, [])
    path_issues.extend(action_index_issues)
    if (
        not safe
        or not baseline_contains(dispatch, [*action_paths, action_index_path])
        or not action_index_valid
        or any(indexed_actions.get(action_id) != action for action_id, action in linked_actions.items())
    ):
        return [], path_issues

    linked_missions: dict[str, JsonObject] = {}
    mission_paths: list[str] = []
    for mission_id, action_ids in mission_to_actions.items():
        mission_path = mission_dir / f"{mission_id}.json"
        safe, path_issue = safe_ip_artifact(mission_path, ip_dir)
        if path_issue:
            path_issues.append(path_issue)
        if not safe:
            return [], path_issues
        mission = load_json_dict_if_valid(mission_path)
        action_refs = string_items(mission.get("action_instance_refs"))
        if (
            mission.get("schema_version") != MISSION_INSTANCE_SCHEMA
            or bool(schema_issues("oag_mission_instance.schema.json", mission))
            or mission_path.stem != str(mission.get("id") or "")
            or action_refs is None
            or not action_ids.issubset(set(action_refs))
        ):
            return [], path_issues
        linked_missions[mission_id] = mission
        mission_paths.append(project_rel(mission_path))

    mission_index = mission_dir / "_index.json"
    safe, path_issue = safe_ip_artifact(mission_index, ip_dir)
    if path_issue:
        path_issues.append(path_issue)
    mission_index_path = project_rel(mission_index) if safe else ""
    mission_index_valid, indexed_missions, mission_index_issues = validate_current_index(
        mission_index,
        schema_version=MISSION_INDEX_SCHEMA,
        collection="missions",
        expected_ip=ip_dir.name,
        ip_dir=ip_dir,
    ) if safe else (False, {}, [])
    path_issues.extend(mission_index_issues)
    if (
        not safe
        or not baseline_contains(dispatch, [*mission_paths, mission_index_path])
        or not mission_index_valid
        or any(indexed_missions.get(mission_id) != mission for mission_id, mission in linked_missions.items())
    ):
        return [], path_issues
    for action_id, action in indexed_actions.items():
        mission_refs = string_items(action.get("mission_instance_refs", []))
        if mission_refs is None or any(
            MISSION_ID_RE.fullmatch(mission_id) is None
            or mission_id not in indexed_missions
            or action_id not in indexed_missions[mission_id].get("action_instance_refs", [])
            for mission_id in mission_refs
        ):
            return [], path_issues
    for mission_id, mission in indexed_missions.items():
        action_refs = string_items(mission.get("action_instance_refs"))
        if action_refs is None or any(
            ACTION_ID_RE.fullmatch(action_id) is None
            or action_id not in indexed_actions
            or mission_id not in indexed_actions[action_id].get("mission_instance_refs", [])
            for action_id in action_refs
        ):
            return [], path_issues
    return sorted({*action_paths, action_index_path, *mission_paths, mission_index_path}), path_issues


def wavefront_parent_orchestration_paths(dispatch: JsonObject) -> list[str]:
    paths, _ = wavefront_parent_orchestration_scope(dispatch)
    return paths


def load_wavefront_events(path: Path, run_id: str) -> list[JsonObject] | None:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError):
        return None
    events: list[JsonObject] = []
    previous_time: datetime | None = None
    for line in lines:
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except (TypeError, ValueError):
            return None
        event_time = parse_timestamp(payload.get("created_at")) if isinstance(payload, dict) else None
        if (
            not isinstance(payload, dict)
            or bool(schema_issues("oag_wavefront_event.schema.json", payload))
            or str(payload.get("run_id") or "") != run_id
            or event_time is None
            or (previous_time is not None and event_time < previous_time)
        ):
            return None
        events.append(payload)
        previous_time = event_time
    return events


def safe_ip_regular_file(path: Path, ip_dir: Path) -> tuple[bool, Issue | None]:
    safe, path_issue = safe_ip_artifact(path, ip_dir)
    if not safe or path_issue:
        return safe, path_issue
    try:
        lexical_rel = path.relative_to(ip_dir)
    except ValueError:
        return False, issue(
            "PARENT_WAVEFRONT_PATH_ESCAPE",
            "parent wavefront artifact is not lexically contained by the IP root",
            str(path),
        )
    probe = ip_dir
    for part in lexical_rel.parts:
        probe = probe / part
        if probe.is_symlink():
            return False, issue(
                "PARENT_WAVEFRONT_ARTIFACT_SYMLINK",
                "parent wavefront artifacts used for dispatch verification must not be symlinks",
                str(path),
            )
    return path.is_file(), None


def ip_relative_reference(value: JsonValue, ip_dir: Path) -> str | None:
    normalized = normalized_ip_reference(value)
    if normalized is None:
        return None
    ip_project_path = project_rel(ip_dir)
    if ip_project_path not in {"", "."}:
        prefix = f"{ip_project_path.rstrip('/')}/"
        if normalized.startswith(prefix):
            return normalized[len(prefix):]
    return normalized


def reference_matches_file(value: JsonValue, path: Path, ip_dir: Path) -> bool:
    normalized = normalized_ip_reference(value)
    if normalized is None:
        return False
    ip_path = path.resolve().relative_to(ip_dir.resolve()).as_posix()
    return normalized in {ip_path, project_rel(path)}


def valid_dispatch_integrity(payload: JsonObject) -> bool:
    integrity = payload.get("dispatch_integrity") if isinstance(payload.get("dispatch_integrity"), dict) else {}
    protected_fields = integrity.get("protected_fields")
    expected_fields = dispatch_integrity_fields(payload)
    return (
        integrity.get("schema_version") == "oag_dispatch_integrity.v1"
        and integrity.get("scope_hash_algorithm") == "sha256:jcs-v1"
        and protected_fields == expected_fields
        and str(integrity.get("scope_hash") or "") == dispatch_scope_hash(payload, protected_fields)
    )


def dispatch_scope_matches_task(payload: JsonObject, task: JsonObject, ip_dir: Path) -> bool:
    task_paths = {str(item) for item in task.get("allowed_write_paths", []) if isinstance(item, str)}
    if len(task_paths) != len(task.get("allowed_write_paths", [])):
        return False
    raw_dispatch_paths = payload.get("allowed_write_paths") if isinstance(payload.get("allowed_write_paths"), list) else []
    normalized_dispatch_paths = [ip_relative_reference(raw, ip_dir) for raw in raw_dispatch_paths]
    if any(item is None for item in normalized_dispatch_paths):
        return False
    dispatch_paths = {str(item) for item in normalized_dispatch_paths}
    if len(dispatch_paths) != len(raw_dispatch_paths):
        return False
    receipt_ip_path = ip_relative_reference(payload.get("receipt_path"), ip_dir)
    if receipt_ip_path is None:
        return False
    receipt_parent = PurePosixPath(receipt_ip_path).parent.as_posix()
    return frozenset(dispatch_paths) in {
        frozenset(task_paths),
        frozenset({*task_paths, receipt_parent}),
    }


def load_strict_wavefront_context(
    dispatch: JsonObject,
) -> tuple[Path | None, dict[str, JsonObject], list[JsonObject] | None, JsonObject, list[Issue]]:
    context_issues: list[Issue] = []
    run_id = str(dispatch.get("wavefront_run_id") or "")
    ip_rel = str(dispatch.get("ip_dir") or "")
    if not run_id or not ip_rel:
        return None, {}, None, {}, context_issues
    ip_dir = resolve_project_path(ip_rel)
    graph_path = oag_paths.legacy_or_hidden(ip_dir, f"ontology/runs/{run_id}/wavefront_task_graph.json")
    events_path = oag_paths.legacy_or_hidden(ip_dir, f"knowledge/wavefront/{run_id}/events.jsonl")
    locks_path = oag_paths.legacy_or_hidden(ip_dir, f"ontology/runs/{run_id}/ownership_locks.json")
    for path in (graph_path, events_path, locks_path):
        safe, path_issue = safe_ip_regular_file(path, ip_dir)
        if path_issue:
            context_issues.append(path_issue)
        if not safe:
            return ip_dir, {}, None, {}, context_issues
    graph = load_json_dict_if_valid(graph_path)
    locks = load_json_dict_if_valid(locks_path)
    events = load_wavefront_events(events_path, run_id)
    if (
        str(graph.get("run_id") or "") != run_id
        or str(graph.get("ip_id") or "") != str(dispatch.get("ip_id") or "")
        or str(graph.get("ip_dir") or "") != ip_rel
        or str(locks.get("run_id") or "") != run_id
        or str(locks.get("ip_id") or "") != str(dispatch.get("ip_id") or "")
        or bool(schema_issues("oag_wavefront_task_graph.schema.json", graph))
        or bool(schema_issues("oag_ownership_locks.schema.json", locks))
        or events is None
    ):
        return ip_dir, {}, None, {}, context_issues
    tasks = graph.get("tasks") if isinstance(graph.get("tasks"), list) else []
    task_map: dict[str, JsonObject] = {}
    for task in tasks:
        if not isinstance(task, dict):
            return ip_dir, {}, None, {}, context_issues
        task_id = str(task.get("task_id") or "")
        if not task_id or task_id in task_map:
            return ip_dir, {}, None, {}, context_issues
        task_map[task_id] = task
    lock_rows = locks.get("locks") if isinstance(locks.get("locks"), list) else []
    lock_paths = [str(lock.get("path") or "") for lock in lock_rows if isinstance(lock, dict)]
    if (
        len(lock_paths) != len(lock_rows)
        or len(lock_paths) != len(set(lock_paths))
        or any(str(lock.get("task_id") or "") not in task_map for lock in lock_rows if isinstance(lock, dict))
    ):
        return ip_dir, {}, None, {}, context_issues
    return ip_dir, task_map, events, locks, context_issues


def load_strict_dispatch(
    path: Path,
    *,
    current_dispatch: JsonObject,
    ip_dir: Path,
    task_map: dict[str, JsonObject],
) -> JsonObject:
    safe, _ = safe_ip_regular_file(path, ip_dir)
    if not safe:
        return {}
    payload = load_json_dict_if_valid(path)
    dispatch_id = str(payload.get("dispatch_id") or "")
    task_id = str(payload.get("task_id") or "")
    task = task_map.get(task_id, {})
    if (
        bool(schema_issues("oag_dispatch.schema.json", payload))
        or not valid_dispatch_integrity(payload)
        or path.stem != dispatch_id
        or not reference_matches_file(payload.get("dispatch_path"), path, ip_dir)
        or str(payload.get("ip_id") or "") != str(current_dispatch.get("ip_id") or "")
        or str(payload.get("ip_dir") or "") != str(current_dispatch.get("ip_dir") or "")
        or str(payload.get("wavefront_run_id") or "") != str(current_dispatch.get("wavefront_run_id") or "")
        or not task_id
        or task_id == str(current_dispatch.get("task_id") or "")
        or not task
        or str(payload.get("ownership_mode") or "") != str(task.get("ownership_mode") or "")
        or str(payload.get("stage") or "") != str(task.get("phase") or "")
        or parse_timestamp(payload.get("created_at")) is None
        or parse_timestamp((payload.get("baseline") or {}).get("created_at") if isinstance(payload.get("baseline"), dict) else None) is None
        or parse_timestamp(payload.get("created_at"))
        != parse_timestamp((payload.get("baseline") or {}).get("created_at") if isinstance(payload.get("baseline"), dict) else None)
    ):
        return {}
    graph_agent_type = str(task.get("agent_type") or "")
    if graph_agent_type and str(payload.get("agent_type") or "") != graph_agent_type:
        return {}
    if not dispatch_scope_matches_task(payload, task, ip_dir):
        return {}
    return payload


def trusted_successor_output_hashes(
    payload: JsonObject,
    *,
    current_dispatch: JsonObject,
    ip_dir: Path,
    task_map: dict[str, JsonObject],
    receipt_time: datetime | None,
) -> dict[str, set[str]]:
    """Return hashes from the immediate later same-task dispatch baseline."""
    payload_time = parse_timestamp(payload.get("created_at"))
    task_id = str(payload.get("task_id") or "")
    if payload_time is None or receipt_time is None or not task_id:
        return {}
    task = task_map.get(task_id, {})
    marker = task.get("abort_marker") if isinstance(task.get("abort_marker"), dict) else {}
    anchored_successor_ids = {
        str(value)
        for value in (task.get("dispatch_id"), marker.get("dispatch_id"))
        if isinstance(value, str) and value
    }
    if not anchored_successor_ids:
        return {}
    dispatch_dir = oag_paths.legacy_or_hidden(ip_dir, "knowledge/dispatches")
    successors: list[tuple[datetime, JsonObject]] = []
    for candidate_path in sorted(dispatch_dir.glob("DISPATCH_*.json")):
        candidate = load_strict_dispatch(
            candidate_path,
            current_dispatch=current_dispatch,
            ip_dir=ip_dir,
            task_map=task_map,
        )
        candidate_time = parse_timestamp(candidate.get("created_at")) if candidate else None
        baseline = candidate.get("baseline") if isinstance(candidate.get("baseline"), dict) else {}
        baseline_time = parse_timestamp(baseline.get("created_at"))
        if (
            candidate
            and str(candidate.get("dispatch_id") or "") != str(payload.get("dispatch_id") or "")
            and str(candidate.get("dispatch_id") or "") in anchored_successor_ids
            and str(candidate.get("task_id") or "") == task_id
            and candidate_time is not None
            and candidate_time > payload_time
            and baseline_time is not None
            and baseline_time >= receipt_time
        ):
            successors.append((candidate_time, candidate))
    if not successors:
        return {}
    _, successor = min(successors, key=lambda item: item[0])
    baseline = successor.get("baseline") if isinstance(successor.get("baseline"), dict) else {}
    file_hashes = baseline.get("file_hashes") if isinstance(baseline.get("file_hashes"), dict) else {}
    trusted: dict[str, set[str]] = {}
    for raw_path, raw_digest in file_hashes.items():
        path = ip_relative_reference(raw_path, ip_dir)
        digest = str(raw_digest) if isinstance(raw_digest, str) else ""
        if path is None:
            continue
        if re.fullmatch(r"[0-9a-f]{64}", digest):
            digest = f"sha256:{digest}"
        if OUTPUT_SHA256_RE.fullmatch(digest):
            trusted.setdefault(path, set()).add(digest)
    return trusted


def load_dispatch_receipt(
    payload: JsonObject,
    *,
    ip_dir: Path,
    require_schema: bool,
    trusted_output_hashes: dict[str, set[str]] | None = None,
    require_current_output_hashes: bool = True,
) -> tuple[JsonObject, Path | None, str]:
    receipt_ip_path = ip_relative_reference(payload.get("receipt_path"), ip_dir)
    if (
        receipt_ip_path is None
        or not receipt_ip_path.startswith("knowledge/subagents/")
        or not receipt_ip_path.endswith(".json")
    ):
        return {}, None, ""
    receipt_path = ip_dir / receipt_ip_path
    safe, _ = safe_ip_regular_file(receipt_path, ip_dir)
    if not safe:
        return {}, None, ""
    receipt = load_json_dict_if_valid(receipt_path)
    receipt_time = parse_timestamp(receipt.get("created_at"))
    dispatch_time = parse_timestamp(payload.get("created_at"))
    receipt_schema_issues = schema_issues("oag_subagent_receipt.schema.json", receipt)
    if require_schema:
        receipt_schema_invalid = bool(receipt_schema_issues)
    else:
        receipt_schema_invalid = any(
            not (
                item.get("code") == "CONST"
                and item.get("path") == "$.dispatch_verified"
                and receipt.get("dispatch_verified") is False
            )
            for item in receipt_schema_issues
        )
    dispatch_write_paths = [str(item) for item in payload.get("allowed_write_paths", []) if isinstance(item, str)]
    dispatch_side_effects = [str(item) for item in payload.get("allowed_tool_side_effects", []) if isinstance(item, str)]
    normalized_write_scope = [ip_relative_reference(path, ip_dir) for path in dispatch_write_paths]
    normalized_side_effect_scope = [ip_relative_reference(path, ip_dir) for path in dispatch_side_effects]
    receipt_write_paths = string_items(receipt.get("allowed_write_paths"))
    receipt_changed_paths = string_items(receipt.get("changed_paths"))
    receipt_side_effects = string_items(receipt.get("generated_side_effects"))
    owned_changed_paths = receipt.get("owned_changed_paths")
    if owned_changed_paths is not None and string_items(owned_changed_paths) is None:
        return {}, None, ""
    changed_paths = [*(receipt_changed_paths or []), *(string_items(owned_changed_paths) or [])]
    mirrored_scalars_match = all(
        str(receipt.get(field) or "") == str(payload.get(field) or "")
        for field in MIRRORED_SCALAR_FIELDS
    )
    mirrored_lists_match = all(
        string_items(receipt.get(field)) == string_items(payload.get(field))
        for field in MIRRORED_LIST_FIELDS
    )
    output_hashes = receipt.get("output_hashes") if isinstance(receipt.get("output_hashes"), dict) else {}
    changed_paths_in_scope = all(
        (normalized := ip_relative_reference(path, ip_dir)) is not None
        and all(scope is not None for scope in normalized_write_scope)
        and path_matches(normalized, [str(scope) for scope in normalized_write_scope])
        for path in changed_paths
    )
    side_effects_in_scope = all(
        (normalized := ip_relative_reference(path, ip_dir)) is not None
        and all(scope is not None for scope in normalized_side_effect_scope)
        and path_matches(normalized, [str(scope) for scope in normalized_side_effect_scope])
        for path in receipt_side_effects or []
    )
    output_hashes_in_scope = all(
        (normalized := ip_relative_reference(path, ip_dir)) is not None
        and all(scope is not None for scope in normalized_write_scope)
        and path_matches(normalized, [str(scope) for scope in normalized_write_scope])
        for path in output_hashes
    )
    output_hash_issues = collect_output_hash_issues(
        receipt,
        ip_dir,
        trusted_hashes=trusted_output_hashes,
    )
    if not require_current_output_hashes:
        output_hash_issues = [
            item for item in output_hash_issues
            if str(item.get("code") or "") != "OUTPUT_HASH_MISMATCH"
        ]
    if (
        receipt_schema_invalid
        or bool(output_hash_issues)
        or receipt.get("schema_version") != "oag_subagent_receipt.v1"
        or receipt.get("product_name") != "IP Dev Agent"
        or receipt.get("internal_gateway") != "Ontology Agent Gateway"
        or str(receipt.get("dispatch_id") or "") != str(payload.get("dispatch_id") or "")
        or not reference_matches_file(receipt.get("dispatch_path"), ip_dir / "knowledge" / "dispatches" / f"{payload.get('dispatch_id')}.json", ip_dir)
        or str(receipt.get("wavefront_run_id") or "") != str(payload.get("wavefront_run_id") or "")
        or str(receipt.get("task_id") or "") != str(payload.get("task_id") or "")
        or str(receipt.get("ownership_mode") or "") != str(payload.get("ownership_mode") or "")
        or not mirrored_scalars_match
        or not mirrored_lists_match
        or receipt_write_paths is None
        or receipt_changed_paths is None
        or receipt_side_effects is None
        or not changed_paths_in_scope
        or not side_effects_in_scope
        or not output_hashes_in_scope
        or receipt.get("may_claim_complete") is not False
        or receipt_time is None
        or dispatch_time is None
        or receipt_time < dispatch_time
    ):
        return {}, None, ""
    return receipt, receipt_path, receipt_ip_path


def event_receipt_matches(details: JsonObject, receipt_path: Path, ip_dir: Path) -> bool:
    return reference_matches_file(details.get("receipt"), receipt_path, ip_dir)


def decision_verdict_status_valid(verdict: str, status: str, reviewer: JsonObject, blockers: list[JsonValue]) -> bool:
    if verdict == "approved":
        return status in {"handoff_pass", "closed"} and not blockers
    if verdict == "waived":
        return status == "waived" and str(reviewer.get("kind") or "").lower() == "human"
    if verdict == "rejected":
        return status == "failed" and bool(blockers)
    if verdict in {"blocked", "needs_human_review", "needs_clarification", "needs_decision"}:
        return status == "blocked"
    if verdict == "inconclusive":
        return status == "inconclusive"
    return False


def matching_claim_events(
    events: list[JsonObject],
    payload: JsonObject,
    task: JsonObject,
) -> list[JsonObject]:
    dispatch_time = parse_timestamp(payload.get("created_at"))
    task_paths = sorted(str(item) for item in task.get("allowed_write_paths", []) if isinstance(item, str))
    if dispatch_time is None or len(task_paths) != len(task.get("allowed_write_paths", [])):
        return []
    matches: list[JsonObject] = []
    for event in events:
        details = event.get("details") if isinstance(event.get("details"), dict) else {}
        write_paths = string_items(details.get("write_paths"))
        event_time = parse_timestamp(event.get("created_at"))
        if (
            event.get("event") == "claimed"
            and str(event.get("task_id") or "") == str(payload.get("task_id") or "")
            and str(event.get("status") or "") == "claimed"
            and write_paths is not None
            and sorted(write_paths) == task_paths
            and event_time is not None
            and event_time >= dispatch_time
        ):
            matches.append(event)
    return matches


def active_lock_anchor(
    locks: JsonObject,
    payload: JsonObject,
    task: JsonObject,
    claim_event: JsonObject,
) -> bool:
    all_locks = locks.get("locks") if isinstance(locks.get("locks"), list) else []
    task_id = str(payload.get("task_id") or "")
    dispatch_id = str(payload.get("dispatch_id") or "")
    task_locks = [
        lock for lock in all_locks
        if isinstance(lock, dict) and str(lock.get("task_id") or "") == task_id
    ]
    expected_paths = sorted(str(item) for item in task.get("allowed_write_paths", []) if isinstance(item, str))
    claim_time = parse_timestamp(claim_event.get("created_at"))
    return (
        bool(expected_paths)
        and len(task_locks) == len(expected_paths)
        and sorted(str(lock.get("path") or "") for lock in task_locks) == expected_paths
        and all(str(lock.get("dispatch_id") or "") == dispatch_id for lock in task_locks)
        and all(str(lock.get("mode") or "") == str(task.get("ownership_mode") or "") for lock in task_locks)
        and claim_time is not None
        and all(parse_timestamp(lock.get("claimed_at")) == claim_time for lock in task_locks)
    )


def recorded_event_receipt_path(events: list[JsonObject], event_index: int, ip_dir: Path) -> Path | None:
    event = events[event_index]
    if event.get("event") != "recorded":
        return None
    task_id = str(event.get("task_id") or "")
    status = str(event.get("status") or "")
    details = event.get("details") if isinstance(event.get("details"), dict) else {}
    receipt_ref = ip_relative_reference(details.get("receipt"), ip_dir)
    if status in WAVEFRONT_APPROVED_TERMINAL_STATUSES:
        previous: JsonObject | None = None
        for candidate in reversed(events[:event_index]):
            if candidate.get("event") == "recorded" and str(candidate.get("task_id") or "") == task_id:
                previous = candidate
                break
        if previous is None or str(previous.get("status") or "") != "review_pending":
            return None
        previous_details = previous.get("details") if isinstance(previous.get("details"), dict) else {}
        previous_barriers = string_items(previous_details.get("barrier_outputs"))
        previous_receipt = ip_relative_reference(previous_details.get("receipt"), ip_dir)
        if (
            previous_barriers != []
            or normalized_ip_reference(previous_details.get("decision")) is not None
            or previous_receipt is None
            or (receipt_ref is not None and receipt_ref != previous_receipt)
        ):
            return None
        receipt_ref = previous_receipt
    if receipt_ref is None or not receipt_ref.startswith("knowledge/subagents/") or not receipt_ref.endswith(".json"):
        return None
    receipt_path = ip_dir / receipt_ref
    safe, _ = safe_ip_regular_file(receipt_path, ip_dir)
    return receipt_path if safe else None


def repair_decision_review_anchor(
    events: list[JsonObject],
    event_index: int,
    ip_dir: Path,
) -> tuple[Path | None, datetime | None]:
    """Resolve the reviewed receipt that a rejection routed back to claimed."""
    event = events[event_index]
    if event.get("event") != "recorded" or str(event.get("status") or "") != "claimed":
        return None, None
    task_id = str(event.get("task_id") or "")
    details = event.get("details") if isinstance(event.get("details"), dict) else {}
    if not task_id or not normalized_ip_reference(details.get("decision")):
        return None, None

    review_index: int | None = None
    for candidate_index in range(event_index - 1, -1, -1):
        candidate = events[candidate_index]
        if candidate.get("event") == "recorded" and str(candidate.get("task_id") or "") == task_id:
            review_index = candidate_index
            break
    if review_index is None:
        return None, None
    review_event = events[review_index]
    review_details = review_event.get("details") if isinstance(review_event.get("details"), dict) else {}
    review_barriers = string_items(review_details.get("barrier_outputs"))
    review_time = parse_timestamp(review_event.get("created_at"))
    if (
        str(review_event.get("status") or "") != "review_pending"
        or review_barriers != []
        or normalized_ip_reference(review_details.get("decision")) is not None
        or review_time is None
    ):
        return None, None
    receipt_path = recorded_event_receipt_path(events, review_index, ip_dir)
    if receipt_path is None:
        return None, None

    current_receipt = details.get("receipt")
    if current_receipt and not reference_matches_file(current_receipt, receipt_path, ip_dir):
        return None, None
    return receipt_path, review_time


def terminal_decision_for_event(
    event: JsonObject,
    *,
    ip_dir: Path,
    run_id: str,
    task_id: str,
) -> tuple[JsonObject, Path | None]:
    status = str(event.get("status") or "")
    if status not in WAVEFRONT_APPROVED_TERMINAL_STATUSES:
        return {}, None
    details = event.get("details") if isinstance(event.get("details"), dict) else {}
    decision_ref = ip_relative_reference(details.get("decision"), ip_dir)
    event_barriers = string_items(details.get("barrier_outputs"))
    if (
        decision_ref is None
        or not decision_ref.startswith("knowledge/decisions/")
        or not decision_ref.endswith(".json")
        or event_barriers is None
    ):
        return {}, None
    decision_path = ip_dir / decision_ref
    safe, _ = safe_ip_regular_file(decision_path, ip_dir)
    if not safe:
        return {}, None
    decision = load_json_dict_if_valid(decision_path)
    target = decision.get("target") if isinstance(decision.get("target"), dict) else {}
    unlocks = decision.get("unlocks") if isinstance(decision.get("unlocks"), dict) else {}
    decision_barriers = string_items(unlocks.get("barrier_outputs"))
    rationale = decision.get("rationale") if isinstance(decision.get("rationale"), dict) else {}
    blockers = rationale.get("blockers") if isinstance(rationale.get("blockers"), list) else []
    reviewer = decision.get("reviewer") if isinstance(decision.get("reviewer"), dict) else {}
    verdict = str(decision.get("verdict") or "")
    if (
        bool(schema_issues("oag_wavefront_decision.schema.json", decision))
        or decision_path.stem != str(decision.get("decision_id") or "")
        or str(target.get("kind") or "") != "wavefront_task"
        or str(target.get("run_id") or "") != run_id
        or str(target.get("task_id") or "") != task_id
        or str(unlocks.get("wavefront_status") or "") != status
        or decision_barriers is None
        or sorted(decision_barriers) != sorted(event_barriers)
        or parse_timestamp(decision.get("created_at")) is None
        or parse_timestamp(event.get("created_at")) is None
        or parse_timestamp(decision.get("created_at")) > parse_timestamp(event.get("created_at"))
        or not decision_verdict_status_valid(verdict, status, reviewer, blockers)
    ):
        return {}, None
    return decision, decision_path


def wavefront_current_terminal_scope(
    dispatch: JsonObject,
    expected_receipt_path: Path,
) -> tuple[bool, list[str], list[Issue]]:
    """Recognize an idempotent re-verify of the graph's exact terminal dispatch."""
    ip_dir, task_map, events, locks, lineage_issues = load_strict_wavefront_context(dispatch)
    task_id = str(dispatch.get("task_id") or "")
    dispatch_id = str(dispatch.get("dispatch_id") or "")
    task = task_map.get(task_id, {})
    if ip_dir is None or events is None or not task:
        return False, [], lineage_issues
    dispatch_path = ip_dir / "knowledge" / "dispatches" / f"{dispatch_id}.json"
    safe, path_issue = safe_ip_regular_file(dispatch_path, ip_dir)
    if path_issue:
        lineage_issues.append(path_issue)
    graph_agent_type = str(task.get("agent_type") or "")
    if (
        not safe
        or load_json_dict_if_valid(dispatch_path) != dispatch
        or bool(schema_issues("oag_dispatch.schema.json", dispatch))
        or not valid_dispatch_integrity(dispatch)
        or parse_timestamp(dispatch.get("created_at"))
        != parse_timestamp((dispatch.get("baseline") or {}).get("created_at") if isinstance(dispatch.get("baseline"), dict) else None)
        or not reference_matches_file(dispatch.get("dispatch_path"), dispatch_path, ip_dir)
        or str(task.get("dispatch_id") or "") != dispatch_id
        or str(task.get("status") or "") not in WAVEFRONT_APPROVED_TERMINAL_STATUSES
        or str(task.get("ownership_mode") or "") != str(dispatch.get("ownership_mode") or "")
        or str(task.get("phase") or "") != str(dispatch.get("stage") or "")
        or (graph_agent_type and graph_agent_type != str(dispatch.get("agent_type") or ""))
        or not dispatch_scope_matches_task(dispatch, task, ip_dir)
    ):
        return False, [], lineage_issues

    receipt, receipt_path, _ = load_dispatch_receipt(dispatch, ip_dir=ip_dir, require_schema=True)
    receipt_time = parse_timestamp(receipt.get("created_at")) if receipt else None
    if (
        not receipt
        or receipt_path is None
        or receipt_path.resolve() != expected_receipt_path.resolve()
        or not reference_matches_file(task.get("receipt_path"), receipt_path, ip_dir)
        or receipt_time is None
    ):
        return False, [], lineage_issues

    task_locks = [
        lock for lock in locks.get("locks", [])
        if isinstance(lock, dict) and str(lock.get("task_id") or "") == task_id
    ] if isinstance(locks.get("locks"), list) else []
    claim_events = matching_claim_events(events, dispatch, task)
    if task_locks or len(claim_events) != 1:
        return False, [], lineage_issues

    matching_terminal: list[tuple[JsonObject, JsonObject, Path]] = []
    for event_index, event in enumerate(events):
        event_time = parse_timestamp(event.get("created_at"))
        if (
            event.get("event") != "recorded"
            or str(event.get("task_id") or "") != task_id
            or str(event.get("status") or "") != str(task.get("status") or "")
            or event_time is None
            or event_time < receipt_time
            or recorded_event_receipt_path(events, event_index, ip_dir) != receipt_path
        ):
            continue
        decision, decision_path = terminal_decision_for_event(
            event,
            ip_dir=ip_dir,
            run_id=str(dispatch.get("wavefront_run_id") or ""),
            task_id=task_id,
        )
        decision_time = parse_timestamp(decision.get("created_at")) if decision else None
        decision_id = str(decision.get("decision_id") or "")
        unlocks = decision.get("unlocks") if isinstance(decision.get("unlocks"), dict) else {}
        decision_barriers = string_items(unlocks.get("barrier_outputs"))
        task_barriers = string_items(task.get("barrier_outputs"))
        if (
            not decision
            or decision_path is None
            or decision_time is None
            or decision_time < receipt_time
            or str(task.get("decision_id") or "") != decision_id
            or str(task.get("decision_type") or "") != str(decision.get("decision_type") or "")
            or not reference_matches_file(task.get("decision_path"), decision_path, ip_dir)
            or decision_barriers is None
            or task_barriers is None
            or sorted(decision_barriers) != sorted(task_barriers)
            or parse_timestamp(task.get("recorded_at")) != event_time
        ):
            continue
        matching_terminal.append((event, decision, decision_path))
    if len(matching_terminal) != 1:
        return False, [], lineage_issues
    return True, [project_rel(matching_terminal[0][2])], lineage_issues


def wavefront_parent_dispatch_scope(dispatch: JsonObject) -> tuple[list[str], list[str], list[Issue]]:
    """Return schema- and integrity-valid active or historically aborted sibling dispatches."""
    ip_dir, task_map, events, locks, dispatch_issues = load_strict_wavefront_context(dispatch)
    if ip_dir is None or events is None or not task_map:
        return [], [], dispatch_issues
    baseline = dispatch.get("baseline") if isinstance(dispatch.get("baseline"), dict) else {}
    baseline_hashes = baseline.get("file_hashes") if isinstance(baseline.get("file_hashes"), dict) else {}
    baseline_time = parse_timestamp(baseline.get("created_at"))
    if baseline_time is None:
        return [], [], dispatch_issues
    dispatch_dir = oag_paths.legacy_or_hidden(ip_dir, "knowledge/dispatches")
    safe, path_issue = safe_ip_artifact(dispatch_dir, ip_dir)
    if path_issue:
        dispatch_issues.append(path_issue)
    if not safe or not dispatch_dir.is_dir():
        return [], [], dispatch_issues

    exempted: list[str] = []
    exempted_receipts: list[str] = []
    for path in sorted(dispatch_dir.glob("DISPATCH_*.json")):
        project_path = project_rel(path)
        if project_path in baseline_hashes:
            continue
        payload = load_strict_dispatch(path, current_dispatch=dispatch, ip_dir=ip_dir, task_map=task_map)
        if not payload:
            continue
        dispatch_time = parse_timestamp(payload.get("created_at"))
        if dispatch_time is None or dispatch_time <= baseline_time:
            continue
        dispatch_id = str(payload.get("dispatch_id") or "")
        task_id = str(payload.get("task_id") or "")
        task = task_map[task_id]
        claim_events = matching_claim_events(events, payload, task)
        active_anchor = (
            str(task.get("dispatch_id") or "") == dispatch_id
            and str(task.get("status") or "") in WAVEFRONT_ACTIVE_STATUSES
            and len(claim_events) == 1
            and active_lock_anchor(locks, payload, task, claim_events[0])
        )
        historical_anchor = False
        receipt_ip_path = ip_relative_reference(payload.get("receipt_path"), ip_dir)
        raw_receipt = load_json_dict_if_valid(ip_dir / receipt_ip_path) if receipt_ip_path is not None else {}
        trusted_hashes = trusted_successor_output_hashes(
            payload,
            current_dispatch=dispatch,
            ip_dir=ip_dir,
            task_map=task_map,
            receipt_time=parse_timestamp(raw_receipt.get("created_at")),
        )
        receipt, receipt_path, _ = load_dispatch_receipt(
            payload,
            ip_dir=ip_dir,
            require_schema=False,
            trusted_output_hashes=trusted_hashes,
        )
        active_receipt_anchor = False
        if active_anchor and str(task.get("status") or "") == "review_pending":
            active_receipt_anchor = (
                bool(receipt)
                and receipt_path is not None
                and reference_matches_file(task.get("receipt_path"), receipt_path, ip_dir)
            )
            active_anchor = active_receipt_anchor
        if receipt and receipt_path is not None:
            receipt_time = parse_timestamp(receipt.get("created_at"))
            matching_terminal_events: list[tuple[JsonObject, JsonObject, Path | None]] = []
            for event_index, event in enumerate(events):
                details = event.get("details") if isinstance(event.get("details"), dict) else {}
                event_time = parse_timestamp(event.get("created_at"))
                event_barriers = string_items(details.get("barrier_outputs"))
                status = str(event.get("status") or "")
                if (
                    event.get("event") != "recorded"
                    or str(event.get("task_id") or "") != task_id
                    or status not in WAVEFRONT_ABORT_STATUSES | WAVEFRONT_APPROVED_TERMINAL_STATUSES
                    or event_barriers is None
                    or event_time is None
                    or receipt_time is None
                    or event_time < receipt_time
                    or recorded_event_receipt_path(events, event_index, ip_dir) != receipt_path
                ):
                    continue
                terminal_decision: JsonObject = {}
                terminal_decision_path: Path | None = None
                if status in WAVEFRONT_APPROVED_TERMINAL_STATUSES:
                    if bool(schema_issues("oag_subagent_receipt.schema.json", receipt)):
                        continue
                    terminal_decision, terminal_decision_path = terminal_decision_for_event(
                        event,
                        ip_dir=ip_dir,
                        run_id=str(dispatch.get("wavefront_run_id") or ""),
                        task_id=task_id,
                    )
                    if (
                        not terminal_decision
                        or terminal_decision_path is None
                        or parse_timestamp(terminal_decision.get("created_at")) is None
                        or parse_timestamp(terminal_decision.get("created_at")) < receipt_time
                    ):
                        continue
                matching_terminal_events.append((event, terminal_decision, terminal_decision_path))
            historical_anchor = len(matching_terminal_events) == 1
            marker = task.get("abort_marker") if isinstance(task.get("abort_marker"), dict) else {}
            if str(marker.get("dispatch_id") or "") == dispatch_id:
                marker_time = parse_timestamp(marker.get("recorded_at"))
                historical_anchor = historical_anchor and any(
                    str(event.get("status") or "") == str(marker.get("status") or "")
                    and parse_timestamp(event.get("created_at")) == marker_time
                    and reference_matches_file(marker.get("receipt_path"), receipt_path, ip_dir)
                    for event, _, _ in matching_terminal_events
                )
            if historical_anchor:
                terminal_event, terminal_decision, terminal_decision_path = matching_terminal_events[0]
                current_dispatch_match = str(task.get("dispatch_id") or "") == dispatch_id
                current_decision_match = bool(terminal_decision) and (
                    str(task.get("decision_id") or "") == str(terminal_decision.get("decision_id") or "")
                )
                if current_dispatch_match or current_decision_match:
                    historical_anchor = historical_anchor and (
                        current_dispatch_match
                        and str(task.get("status") or "") == str(terminal_event.get("status") or "")
                        and reference_matches_file(task.get("receipt_path"), receipt_path, ip_dir)
                    )
                    if terminal_decision and terminal_decision_path is not None:
                        historical_anchor = historical_anchor and (
                            current_decision_match
                            and str(task.get("decision_type") or "") == str(terminal_decision.get("decision_type") or "")
                            and reference_matches_file(task.get("decision_path"), terminal_decision_path, ip_dir)
                        )
        if active_anchor or historical_anchor:
            exempted.append(project_path)
            if receipt_path is not None and (active_receipt_anchor or historical_anchor):
                exempted_receipts.append(project_rel(receipt_path))
    return sorted(set(exempted)), sorted(set(exempted_receipts)), dispatch_issues


def wavefront_parent_decision_scope(dispatch: JsonObject) -> tuple[list[str], list[Issue]]:
    """Return new parent decisions anchored by immutable event, receipt, and dispatch lineage."""
    ip_dir, task_map, events, locks, decision_issues = load_strict_wavefront_context(dispatch)
    if ip_dir is None or events is None or not task_map:
        return [], decision_issues
    run_id = str(dispatch.get("wavefront_run_id") or "")
    current_task_id = str(dispatch.get("task_id") or "")
    baseline = dispatch.get("baseline") if isinstance(dispatch.get("baseline"), dict) else {}
    baseline_hashes = baseline.get("file_hashes") if isinstance(baseline.get("file_hashes"), dict) else {}
    baseline_time = parse_timestamp(baseline.get("created_at"))
    if baseline_time is None:
        return [], decision_issues
    decisions_dir = oag_paths.legacy_or_hidden(ip_dir, "knowledge/decisions")
    safe, path_issue = safe_ip_artifact(decisions_dir, ip_dir)
    if path_issue:
        decision_issues.append(path_issue)
    if not safe or not decisions_dir.is_dir():
        return [], decision_issues

    exempted: list[str] = []
    for decision_path in sorted(decisions_dir.glob("DEC_*.json")):
        decision_project_path = project_rel(decision_path)
        if decision_project_path in baseline_hashes:
            continue
        safe, path_issue = safe_ip_regular_file(decision_path, ip_dir)
        if path_issue:
            decision_issues.append(path_issue)
        if not safe:
            continue
        decision = load_json_dict_if_valid(decision_path)
        decision_id = str(decision.get("decision_id") or "")
        target = decision.get("target") if isinstance(decision.get("target"), dict) else {}
        sibling_task_id = str(target.get("task_id") or "")
        task = task_map.get(sibling_task_id, {})
        unlocks = decision.get("unlocks") if isinstance(decision.get("unlocks"), dict) else {}
        barrier_outputs = string_items(unlocks.get("barrier_outputs"))
        expected_status = str(unlocks.get("wavefront_status") or "")
        decision_time = parse_timestamp(decision.get("created_at"))
        verdict = str(decision.get("verdict") or "")
        rationale = decision.get("rationale") if isinstance(decision.get("rationale"), dict) else {}
        blockers = rationale.get("blockers") if isinstance(rationale.get("blockers"), list) else []
        reviewer = decision.get("reviewer") if isinstance(decision.get("reviewer"), dict) else {}
        repair_route = (
            expected_status == "claimed"
            and verdict == "rejected"
            and bool(blockers)
            and barrier_outputs == []
        )
        current_repair_route = repair_route and sibling_task_id == current_task_id
        if (
            bool(schema_issues("oag_wavefront_decision.schema.json", decision))
            or DECISION_ID_RE.fullmatch(decision_id) is None
            or decision_path.stem != decision_id
            or str(target.get("kind") or "") != "wavefront_task"
            or str(target.get("run_id") or "") != run_id
            or not sibling_task_id
            or (sibling_task_id == current_task_id and not current_repair_route)
            or not task
            or barrier_outputs is None
            or (expected_status not in WAVEFRONT_DECISION_STATUSES and not repair_route)
            or decision_time is None
            or decision_time <= baseline_time
            or (not repair_route and not decision_verdict_status_valid(verdict, expected_status, reviewer, blockers))
            or (verdict == "rejected" and not blockers)
        ):
            continue
        if str(task.get("decision_id") or "") == decision_id and (
            str(task.get("decision_type") or "") != str(decision.get("decision_type") or "")
            or not reference_matches_file(task.get("decision_path"), decision_path, ip_dir)
        ):
            continue
        matching_events: list[tuple[int, JsonObject]] = []
        for event_index, event in enumerate(events):
            details = event.get("details") if isinstance(event.get("details"), dict) else {}
            event_barriers = string_items(details.get("barrier_outputs"))
            event_time = parse_timestamp(event.get("created_at"))
            if (
                event.get("event") == "recorded"
                and str(event.get("task_id") or "") == sibling_task_id
                and str(event.get("status") or "") == expected_status
                and reference_matches_file(details.get("decision"), decision_path, ip_dir)
                and event_barriers is not None
                and sorted(event_barriers) == sorted(barrier_outputs)
                and event_time is not None
                and event_time >= decision_time
            ):
                if expected_status in WAVEFRONT_APPROVED_TERMINAL_STATUSES:
                    terminal_decision, terminal_decision_path = terminal_decision_for_event(
                        event,
                        ip_dir=ip_dir,
                        run_id=run_id,
                        task_id=sibling_task_id,
                    )
                    if terminal_decision != decision or terminal_decision_path != decision_path:
                        continue
                matching_events.append((event_index, event))
        if len(matching_events) != 1:
            continue
        event_index, decision_event = matching_events[0]
        repair_review_time: datetime | None = None
        if repair_route:
            receipt_path, repair_review_time = repair_decision_review_anchor(events, event_index, ip_dir)
        else:
            receipt_path = recorded_event_receipt_path(events, event_index, ip_dir)
        if receipt_path is None:
            continue
        safe, path_issue = safe_ip_regular_file(receipt_path, ip_dir)
        if path_issue:
            decision_issues.append(path_issue)
        if not safe:
            continue
        receipt = load_json_dict_if_valid(receipt_path)
        linked_dispatch_id = str(receipt.get("dispatch_id") or "")
        linked_dispatch_path = ip_dir / "knowledge" / "dispatches" / f"{linked_dispatch_id}.json"
        if current_repair_route:
            dispatch_id = str(dispatch.get("dispatch_id") or "")
            current_dispatch_path = ip_dir / "knowledge" / "dispatches" / f"{dispatch_id}.json"
            safe, path_issue = safe_ip_regular_file(current_dispatch_path, ip_dir)
            if path_issue:
                decision_issues.append(path_issue)
            baseline_payload = dispatch.get("baseline") if isinstance(dispatch.get("baseline"), dict) else {}
            graph_agent_type = str(task.get("agent_type") or "")
            claim_events = matching_claim_events(events, dispatch, task)
            if (
                not safe
                or linked_dispatch_id != dispatch_id
                or linked_dispatch_path != current_dispatch_path
                or load_json_dict_if_valid(current_dispatch_path) != dispatch
                or bool(schema_issues("oag_dispatch.schema.json", dispatch))
                or not valid_dispatch_integrity(dispatch)
                or current_dispatch_path.stem != dispatch_id
                or not reference_matches_file(dispatch.get("dispatch_path"), current_dispatch_path, ip_dir)
                or parse_timestamp(dispatch.get("created_at")) is None
                or parse_timestamp(dispatch.get("created_at")) != parse_timestamp(baseline_payload.get("created_at"))
                or str(task.get("status") or "") not in WAVEFRONT_ACTIVE_STATUSES
                or str(task.get("dispatch_id") or "") != dispatch_id
                or str(task.get("ownership_mode") or "") != str(dispatch.get("ownership_mode") or "")
                or str(task.get("phase") or "") != str(dispatch.get("stage") or "")
                or (graph_agent_type and graph_agent_type != str(dispatch.get("agent_type") or ""))
                or not dispatch_scope_matches_task(dispatch, task, ip_dir)
                or not reference_matches_file(task.get("receipt_path"), receipt_path, ip_dir)
                or str(task.get("decision_id") or "") != decision_id
                or str(task.get("decision_type") or "") != str(decision.get("decision_type") or "")
                or not reference_matches_file(task.get("decision_path"), decision_path, ip_dir)
                or len(claim_events) != 1
                or not active_lock_anchor(locks, dispatch, task, claim_events[0])
            ):
                continue
            linked_dispatch = dispatch
        else:
            linked_dispatch = load_strict_dispatch(
                linked_dispatch_path,
                current_dispatch=dispatch,
                ip_dir=ip_dir,
                task_map=task_map,
            )
        raw_receipt = load_json_dict_if_valid(receipt_path)
        trusted_hashes = trusted_successor_output_hashes(
            linked_dispatch,
            current_dispatch=dispatch,
            ip_dir=ip_dir,
            task_map=task_map,
            receipt_time=parse_timestamp(raw_receipt.get("created_at")),
        ) if linked_dispatch else {}
        anchored_receipt, anchored_receipt_path, _ = load_dispatch_receipt(
            linked_dispatch,
            ip_dir=ip_dir,
            require_schema=not current_repair_route,
            trusted_output_hashes=trusted_hashes,
            require_current_output_hashes=not repair_route,
        ) if linked_dispatch else ({}, None, "")
        anchored_receipt_time = parse_timestamp(anchored_receipt.get("created_at")) if anchored_receipt else None
        decision_event_time = parse_timestamp(decision_event.get("created_at"))
        if (
            not linked_dispatch
            or not anchored_receipt
            or anchored_receipt_path != receipt_path
            or str(linked_dispatch.get("task_id") or "") != sibling_task_id
            or str(linked_dispatch.get("wavefront_run_id") or "") != run_id
            or anchored_receipt_time is None
            or (not repair_route and decision_time < anchored_receipt_time)
            or decision_event_time is None
            or (repair_route and (
                repair_review_time is None
                or decision_time < repair_review_time
                or decision_time > decision_event_time
            ))
        ):
            continue
        if expected_status in WAVEFRONT_APPROVED_TERMINAL_STATUSES and str(task.get("decision_id") or "") == decision_id:
            if (
                str(task.get("status") or "") != expected_status
                or str(task.get("dispatch_id") or "") != linked_dispatch_id
                or not reference_matches_file(task.get("receipt_path"), receipt_path, ip_dir)
            ):
                continue
        exempted.append(decision_project_path)
    return sorted(set(exempted)), decision_issues


def current_repair_receipt_anchor(dispatch: JsonObject, receipt_path: Path) -> bool:
    """Recognize the exact interim receipt used by a current-task repair decision."""
    if not dispatch_has_wavefront_metadata(dispatch):
        return False
    ip_dir, task_map, _, _, context_issues = load_strict_wavefront_context(dispatch)
    task_id = str(dispatch.get("task_id") or "")
    task = task_map.get(task_id, {})
    if ip_dir is None or not task or context_issues:
        return False
    receipt_ref = ip_relative_reference(dispatch.get("receipt_path"), ip_dir)
    decision_ref = ip_relative_reference(task.get("decision_path"), ip_dir)
    if (
        receipt_ref is None
        or decision_ref is None
        or not decision_ref.startswith("knowledge/decisions/")
        or not decision_ref.endswith(".json")
    ):
        return False
    expected_receipt_path = ip_dir / receipt_ref
    safe, _ = safe_ip_regular_file(expected_receipt_path, ip_dir)
    if not safe or expected_receipt_path.resolve() != receipt_path.resolve():
        return False
    decision_paths, decision_issues = wavefront_parent_decision_scope(dispatch)
    return not decision_issues and project_rel(ip_dir / decision_ref) in decision_paths


def append_receipt_schema_issues(
    issues: list[Issue],
    receipt: JsonObject,
    *,
    allow_interim_current_repair: bool,
) -> None:
    for item in schema_issues("oag_subagent_receipt.schema.json", receipt):
        if (
            allow_interim_current_repair
            and item.get("code") == "CONST"
            and item.get("path") == "$.dispatch_verified"
            and receipt.get("dispatch_verified") is False
        ):
            continue
        issues.append(issue(f"RECEIPT_SCHEMA_{item['code']}", item["message"], item["path"]))


def collect_output_hash_issues(
    receipt: JsonObject,
    ip_dir: Path,
    *,
    trusted_hashes: dict[str, set[str]] | None = None,
) -> list[Issue]:
    issues: list[Issue] = []
    if "output_hashes" not in receipt:
        return issues
    output_hashes = receipt.get("output_hashes")
    if not isinstance(output_hashes, dict):
        issues.append(issue("OUTPUT_HASHES_OBJECT", "receipt.output_hashes must be an object"))
        return issues
    for raw_path, raw_digest in output_hashes.items():
        if not isinstance(raw_path, str) or raw_path != PurePosixPath(raw_path).as_posix():
            issues.append(issue("OUTPUT_HASH_PATH_UNSAFE", "output hash path must be in canonical relative form", str(raw_path)))
            continue
        path = ip_relative_reference(raw_path, ip_dir)
        if path is None:
            issues.append(issue("OUTPUT_HASH_PATH_UNSAFE", "output hash path must be a canonical relative path inside the IP", str(raw_path)))
            continue
        digest = str(raw_digest) if isinstance(raw_digest, str) else ""
        if OUTPUT_SHA256_RE.fullmatch(digest) is None:
            issues.append(
                issue(
                    "OUTPUT_HASH_FORMAT",
                    "output hash must use canonical sha256:<64 lowercase hex> form",
                    str(raw_path),
                )
            )
            continue
        if digest in (trusted_hashes or {}).get(path, set()):
            continue
        artifact_path = ip_dir / path
        safe, path_issue = safe_ip_regular_file(artifact_path, ip_dir)
        if not safe:
            code = "OUTPUT_HASH_PATH_UNSAFE" if path_issue else "OUTPUT_HASH_FILE"
            message = (
                "output hash path resolves through a symlink or outside the IP"
                if path_issue
                else "output hash path must name an existing regular file"
            )
            issues.append(issue(code, message, str(raw_path)))
            continue
        observed = f"sha256:{sha256(artifact_path)}"
        if digest != observed:
            issues.append(issue("OUTPUT_HASH_MISMATCH", "output hash does not match the current file", str(raw_path)))
    return issues


def append_output_hash_issues(issues: list[Issue], receipt: JsonObject, ip_dir: Path) -> None:
    issues.extend(collect_output_hash_issues(receipt, ip_dir))


def append_wavefront_abort_issues(issues: list[Issue], dispatch: JsonObject, receipt_path: Path) -> None:
    task = wavefront_task_for_dispatch(dispatch)
    if not task:
        return
    status = str(task.get("status") or "")
    if status not in WAVEFRONT_ABORT_STATUSES:
        return
    recorded_receipt = normalize_rel(str(task.get("receipt_path") or "")) if task.get("receipt_path") else ""
    current_receipt = project_rel(receipt_path)
    if recorded_receipt and recorded_receipt == current_receipt:
        return
    marker = task.get("abort_marker") if isinstance(task.get("abort_marker"), dict) else {}
    issues.append(
        issue(
            "WAVEFRONT_TASK_ABORTED",
            "receipt arrived for a wavefront task already recorded as "
            f"{status}; create a fresh dispatch from the current baseline instead of integrating late child output",
            str(marker.get("receipt_path") or current_receipt),
        )
    )


def verify_dispatch(args: argparse.Namespace) -> JsonObject:
    issues: list[Issue] = []
    parallel_wavefront_paths: list[str] = []
    parent_orchestration_paths: list[str] = []
    parent_wavefront_dispatch_paths: list[str] = []
    parent_wavefront_receipt_paths: list[str] = []
    parent_wavefront_decision_paths: list[str] = []
    current_terminal_decision_paths: list[str] = []
    dispatch_path = resolve_project_path(args.dispatch)
    receipt_path = resolve_project_path(args.receipt)
    dispatch = load_json_object(dispatch_path, "dispatch", "DISPATCH_LOAD", issues)
    receipt = load_json_object(receipt_path, "receipt", "RECEIPT_LOAD", issues)
    allow_interim_current_repair = False
    if (
        dispatch
        and receipt
        and not getattr(args, "schema_only", False)
        and receipt.get("dispatch_verified") is False
    ):
        try:
            allow_interim_current_repair = current_repair_receipt_anchor(dispatch, receipt_path)
        except (OSError, RuntimeError, ValueError):
            allow_interim_current_repair = False

    if dispatch:
        append_schema_issues(issues, "oag_dispatch.schema.json", dispatch, "DISPATCH_SCHEMA")
    if receipt:
        append_receipt_schema_issues(
            issues,
            receipt,
            allow_interim_current_repair=allow_interim_current_repair,
        )

    if getattr(args, "schema_only", False):
        return {
            "schema_version": "oag_dispatch_schema_preflight_result.v1",
            "status": "fail" if issues else "pass",
            "dispatch_path": str(dispatch_path),
            "receipt_path": str(receipt_path),
            "dispatch_id": dispatch.get("dispatch_id", ""),
            "receipt_status": receipt.get("status", ""),
            "schema_only": True,
            "issues": issues,
        }

    if dispatch and receipt:
        integrity = dispatch.get("dispatch_integrity") if isinstance(dispatch.get("dispatch_integrity"), dict) else {}
        expected_scope_hash = str(integrity.get("scope_hash") or "")
        observed_scope_hash = dispatch_scope_hash(dispatch)
        if not expected_scope_hash:
            issues.append(issue("DISPATCH_INTEGRITY_MISSING", "dispatch is missing immutable scope hash metadata"))
        elif observed_scope_hash != expected_scope_hash:
            issues.append(
                issue(
                    "DISPATCH_MUTATED_AFTER_CREATE",
                    "dispatch protected scope fields changed after dispatch creation; create a new dispatch instead of widening this one",
                    project_rel(dispatch_path),
                )
            )
        dispatch_id = str(dispatch.get("dispatch_id") or "")
        if str(receipt.get("dispatch_id") or "") != dispatch_id:
            issues.append(issue("DISPATCH_ID_MISMATCH", "receipt.dispatch_id does not match dispatch.dispatch_id"))
        receipt_dispatch_path = str(receipt.get("dispatch_path") or "")
        if receipt_dispatch_path and normalize_rel(receipt_dispatch_path) != project_rel(dispatch_path):
            issues.append(issue("DISPATCH_PATH_MISMATCH", "receipt.dispatch_path does not match the dispatch file"))
        if normalize_rel(str(dispatch.get("receipt_path") or "")) != project_rel(receipt_path):
            issues.append(issue("RECEIPT_PATH_MISMATCH", "dispatch.receipt_path does not match the receipt file"))
        for field in MIRRORED_SCALAR_FIELDS:
            if str(receipt.get(field) or "") != str(dispatch.get(field) or ""):
                issues.append(issue("RECEIPT_SCOPE_FIELD_MISMATCH", f"receipt.{field} does not match dispatch.{field}"))
        for field in MIRRORED_LIST_FIELDS:
            dispatch_values = string_list(dispatch, field)
            receipt_values = string_list(receipt, field)
            if field == "allowed_write_paths":
                dispatch_values = sorted(normalize_rel(item) for item in dispatch_values)
                receipt_values = sorted(normalize_rel(item) for item in receipt_values)
            if receipt_values != dispatch_values:
                issues.append(issue("RECEIPT_SCOPE_LIST_MISMATCH", f"receipt.{field} does not match dispatch.{field}"))
        if receipt.get("may_claim_complete") is not False or dispatch.get("may_claim_complete") is not False:
            issues.append(issue("COMPLETION_CLAIM", "dispatch and receipt must keep may_claim_complete=false"))
        if receipt.get("diagnostic_only") is not False:
            issues.append(issue("RECEIPT_DIAGNOSTIC_ONLY", "dispatch-backed handoff receipt must set diagnostic_only=false"))
        if receipt.get("dispatch_verified") is not True and not allow_interim_current_repair:
            issues.append(issue("RECEIPT_DISPATCH_VERIFIED", "dispatch-backed handoff receipt must set dispatch_verified=true"))

        wavefront_dispatch = dispatch_has_wavefront_metadata(dispatch)
        if wavefront_dispatch:
            for field in WAVEFRONT_FIELDS:
                dispatch_value = str(dispatch.get(field) or "")
                receipt_value = str(receipt.get(field) or "")
                if not dispatch_value:
                    issues.append(issue("DISPATCH_WAVEFRONT_FIELD_MISSING", f"dispatch.{field} is required for wavefront dispatches"))
                elif not receipt_value:
                    issues.append(issue("WAVEFRONT_FIELD_MISSING", f"receipt.{field} is required for wavefront dispatches"))
                elif receipt_value != dispatch_value:
                    issues.append(issue("WAVEFRONT_FIELD_MISMATCH", f"receipt.{field} does not match dispatch.{field}"))
            current_terminal_valid, current_terminal_decision_paths, current_terminal_issues = wavefront_current_terminal_scope(
                dispatch,
                receipt_path,
            )
            issues.extend(current_terminal_issues)
            claim_issues = collect_wavefront_claim_issues(dispatch)
            if current_terminal_valid:
                claim_issues = [
                    item
                    for item in claim_issues
                    if item.get("code") not in {"WAVEFRONT_TASK_UNCLAIMED", "WAVEFRONT_CLAIM_DISPATCH_MISMATCH"}
                ]
            issues.extend(claim_issues)
            append_wavefront_abort_issues(issues, dispatch, receipt_path)

        status = str(receipt.get("status") or "")
        if status in LEGACY_RECEIPT_STATUSES:
            issues.append(issue("LEGACY_STATUS", "receipt status PASS is no longer accepted for dispatch-verified subagents"))
        elif status not in RECEIPT_SAFE_STATUSES:
            issues.append(issue("STATUS", f"receipt status is not an OAG handoff status: {status}"))
        if status in {"HANDOFF_PASS", "STATIC_HANDOFF_PASS", "RTL_HANDOFF_PASS"} and receipt.get("covers_writes") is not True:
            issues.append(issue("RECEIPT_WRITE_COVERAGE", "passing handoff receipt must set covers_writes=true"))
        if any(word in status.upper() for word in FORBIDDEN_STATUS_WORDS):
            issues.append(issue("STATUS_COMPLETION_LANGUAGE", "receipt status must not imply completion or signoff"))

        allowed_write_paths = [str(item) for item in dispatch.get("allowed_write_paths") or []]
        allowed_tool_side_effects = [str(item) for item in dispatch.get("allowed_tool_side_effects") or []]
        ip_rel = str(dispatch.get("ip_dir") or "")
        ip_name = str(dispatch.get("ip_id") or Path(ip_rel).name)
        append_output_hash_issues(issues, receipt, resolve_project_path(ip_rel))
        for path in allowed_tool_side_effects:
            if nested_ip_generated_artifact(path, ip_rel, ip_name):
                issues.append(
                    issue(
                        "NESTED_IP_DIR_GENERATED_ARTIFACT",
                        "dispatch allowed_tool_side_effects target nested generated output; check cwd and create a new clean dispatch",
                        path,
                    )
                )
        owned = string_list(receipt, "changed_paths", "owned_changed_paths")
        generated = string_list(receipt, "generated_side_effects")
        for path in owned:
            if not path_matches(normalize_rel(path), allowed_write_paths):
                issues.append(issue("OWNED_PATH_OUT_OF_SCOPE", "receipt changed path is outside allowed_write_paths", path))
        for path in generated:
            if nested_ip_generated_artifact(normalize_rel(path), ip_rel, ip_name):
                issues.append(
                    issue(
                        "NESTED_IP_DIR_GENERATED_ARTIFACT",
                        "receipt generated side effect targets nested generated output; treat it as cwd contamination, not valid evidence",
                        path,
                    )
                )
            if not path_matches(normalize_rel(path), allowed_tool_side_effects):
                issues.append(issue("GENERATED_PATH_OUT_OF_SCOPE", "receipt generated side effect is outside allowed_tool_side_effects", path))

        current_paths, delta_paths = actual_delta(dispatch)
        expected_paths = [*allowed_write_paths, *allowed_tool_side_effects, str(dispatch.get("receipt_path") or ""), str(dispatch.get("dispatch_path") or "")]
        parallel_wavefront_paths = wavefront_sibling_scope_paths(dispatch) if dispatch_has_wavefront_metadata(dispatch) else []
        if wavefront_dispatch:
            try:
                parent_orchestration_paths, parent_orchestration_issues = wavefront_parent_orchestration_scope(dispatch)
                issues.extend(parent_orchestration_issues)
            except (OSError, RuntimeError, ValueError):
                parent_orchestration_paths = []
                issues.append(
                    issue(
                        "PARENT_ORCHESTRATION_PATH_UNSAFE",
                        "parent orchestration closure could not be resolved safely",
                        ip_rel,
                    )
                )
            try:
                parent_wavefront_dispatch_paths, parent_wavefront_receipt_paths, parent_dispatch_issues = wavefront_parent_dispatch_scope(dispatch)
                issues.extend(parent_dispatch_issues)
            except (OSError, RuntimeError, ValueError):
                parent_wavefront_dispatch_paths = []
                parent_wavefront_receipt_paths = []
                issues.append(
                    issue(
                        "PARENT_WAVEFRONT_DISPATCH_UNSAFE",
                        "parent wavefront dispatch history could not be resolved safely",
                        ip_rel,
                    )
                )
            try:
                parent_wavefront_decision_paths, parent_decision_issues = wavefront_parent_decision_scope(dispatch)
                issues.extend(parent_decision_issues)
                parent_wavefront_decision_paths = sorted(
                    set(parent_wavefront_decision_paths + current_terminal_decision_paths)
                )
            except (OSError, RuntimeError, ValueError):
                parent_wavefront_decision_paths = []
                issues.append(
                    issue(
                        "PARENT_WAVEFRONT_DECISION_UNSAFE",
                        "parent wavefront decision closure could not be resolved safely",
                        ip_rel,
                    )
                )
        out_of_scope_actual = [
            path
            for path in delta_paths
            if not path_matches(path, expected_paths)
            and not path_matches(path, parallel_wavefront_paths)
            and not path_matches(path, parent_orchestration_paths)
            and not path_matches(path, parent_wavefront_dispatch_paths)
            and not path_matches(path, parent_wavefront_receipt_paths)
            and not path_matches(path, parent_wavefront_decision_paths)
        ]
        for path in delta_paths:
            if nested_ip_generated_artifact(path, ip_rel, ip_name):
                issues.append(
                    issue(
                        "NESTED_IP_DIR_GENERATED_ARTIFACT",
                        "actual delta includes nested generated output; cleanup/rebaseline instead of closing this dispatch",
                        path,
                    )
                )
        for path in out_of_scope_actual:
            issues.append(issue("ACTUAL_PATH_OUT_OF_SCOPE", "actual git status delta is outside dispatch scope", path))
        if wavefront_dispatch:
            ownership_mode = str(dispatch.get("ownership_mode") or "")
            wavefront_bookkeeping_paths = [str(dispatch.get("dispatch_path") or ""), *allowed_tool_side_effects]
            scoped_wavefront_paths = [
                path
                for path in sorted(
                    set(
                        owned
                        + [
                            item
                            for item in delta_paths
                            if not path_matches(item, parent_orchestration_paths)
                            and not path_matches(item, parent_wavefront_dispatch_paths)
                            and not path_matches(item, parent_wavefront_receipt_paths)
                            and not path_matches(item, parent_wavefront_decision_paths)
                        ]
                    )
                )
                if not path_matches(normalize_rel(path), wavefront_bookkeeping_paths)
            ]
            for path in scoped_wavefront_paths:
                if ownership_mode != "integration_owner" and is_canonical_aggregate_path(path, ip_rel):
                    issues.append(issue("WORKER_CANONICAL_AGGREGATE_WRITE", "ordinary wavefront workers must not write canonical aggregate evidence", path))
                if requires_shard_scope(dispatch) and not is_shard_scope_path(path, dispatch, ip_rel):
                    issues.append(issue("WORKER_SHARD_SCOPE", "ordinary wavefront workers may only write shard evidence paths", path))
    else:
        current_paths, delta_paths = [], []
        owned, generated = [], []
        out_of_scope_actual = []

    return {
        "schema_version": "oag_dispatch_verify_result.v1",
        "status": "fail" if issues else "pass",
        "dispatch_path": str(dispatch_path),
        "receipt_path": str(receipt_path),
        "dispatch_id": dispatch.get("dispatch_id", ""),
        "receipt_status": receipt.get("status", ""),
        "owned_changed_paths": owned,
        "generated_side_effects": generated,
        "actual_status_paths": current_paths,
        "actual_delta_paths": delta_paths,
        "parallel_wavefront_exempted_paths": parallel_wavefront_paths if dispatch_has_wavefront_metadata(dispatch) else [],
        "parent_orchestration_exempted_paths": parent_orchestration_paths if dispatch_has_wavefront_metadata(dispatch) else [],
        "parent_wavefront_dispatch_exempted_paths": parent_wavefront_dispatch_paths if dispatch_has_wavefront_metadata(dispatch) else [],
        "parent_wavefront_receipt_exempted_paths": parent_wavefront_receipt_paths if dispatch_has_wavefront_metadata(dispatch) else [],
        "parent_wavefront_decision_exempted_paths": parent_wavefront_decision_paths if dispatch_has_wavefront_metadata(dispatch) else [],
        "current_terminal_decision_exempted_paths": current_terminal_decision_paths if dispatch_has_wavefront_metadata(dispatch) else [],
        "out_of_scope_paths": out_of_scope_actual,
        "issues": issues,
    }
