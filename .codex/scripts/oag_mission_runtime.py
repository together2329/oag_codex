#!/usr/bin/env python3
"""Create and maintain durable OAG Mission instances."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

SCRIPTS_DIR = Path(__file__).resolve().parent
CODEX_ROOT = SCRIPTS_DIR.parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import oag_paths  # noqa: E402
import oag_run_control_common as run_common  # noqa: E402
from oag_validate_json import contextual_schema_issues  # noqa: E402


SCHEMA_VERSION = "oag_mission_instance.v1"
RESULT_SCHEMA_VERSION = "oag_mission_runtime_result.v1"
MISSION_CATALOG = CODEX_ROOT / "oag" / "mission_templates.yaml"
ACTIVE_STATUSES = {"active"}
TERMINAL_STATUSES = {"completed", "blocked", "superseded", "abandoned"}
ACTION_TERMINAL_STATUSES = {"accepted", "rejected", "blocked", "failed", "inconclusive", "aborted"}

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


def read_yaml(path: Path) -> JsonObject:
    if not path.is_file():
        return {}
    try:
        import yaml  # type: ignore

        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        return data if isinstance(data, dict) else {}
    except Exception as exc:
        return {"__load_error__": str(exc)}


def action_dir(ip_dir: Path) -> Path:
    return oag_paths.state_path(ip_dir, "knowledge/actions")


def action_paths(ip_dir: Path) -> list[Path]:
    root = action_dir(ip_dir)
    if not root.is_dir():
        return []
    return sorted(path for path in root.glob("ACT_RUN_*.json") if path.is_file())


def action_instances_by_id(ip_dir: Path) -> dict[str, JsonObject]:
    rows: dict[str, JsonObject] = {}
    for path in action_paths(ip_dir):
        payload = read_json(path)
        action_id = str(payload.get("id") or path.stem)
        if action_id:
            rows[action_id] = payload
    return rows


def mission_dir(ip_dir: Path) -> Path:
    return oag_paths.state_path(ip_dir, "knowledge/missions")


def sanitize(value: str) -> str:
    clean = re.sub(r"[^A-Za-z0-9_.:-]+", "_", value).strip("_")
    return clean[:96] or "MISSION"


def mission_path(ip_dir: Path, mission_id: str) -> Path:
    return mission_dir(ip_dir) / f"{sanitize(mission_id)}.json"


def existing_mission_paths(ip_dir: Path) -> list[Path]:
    root = mission_dir(ip_dir)
    if not root.is_dir():
        return []
    return sorted(path for path in root.glob("MISSION_RUN_*.json") if path.is_file())


def load_mission_templates() -> dict[str, JsonObject]:
    payload = read_yaml(MISSION_CATALOG)
    rows = [item for item in payload.get("mission_templates", []) if isinstance(item, dict)]
    return {str(row.get("id") or ""): row for row in rows if row.get("id")}


def latest_active_mission(ip_dir: Path, *, template_id: str = "") -> JsonObject:
    active: list[JsonObject] = []
    for path in existing_mission_paths(ip_dir):
        payload = read_json(path)
        if payload.get("status") != "active":
            continue
        if template_id and payload.get("template_id") != template_id:
            continue
        payload["_path"] = path
        active.append(payload)
    active.sort(key=lambda item: str(item.get("started_at") or ""))
    return active[-1] if active else {}


def latest_mission(ip_dir: Path) -> JsonObject:
    rows: list[JsonObject] = []
    for path in existing_mission_paths(ip_dir):
        payload = read_json(path)
        payload["_path"] = path
        rows.append(payload)
    rows.sort(key=lambda item: str(item.get("started_at") or ""))
    return rows[-1] if rows else {}


def new_mission_id(template_id: str) -> str:
    stamp = run_common.utc_now().replace("-", "").replace(":", "").replace(".", "")
    return f"MISSION_RUN_{stamp}_{sanitize(template_id)}"


def validate_instance(payload: JsonObject, path: Path) -> list[dict[str, str]]:
    return contextual_schema_issues(
        "oag_mission_instance.schema.json",
        payload,
        code_prefix="MISSION_INSTANCE_SCHEMA",
        document_path=str(path),
    )


def write_instance(ip_dir: Path, payload: JsonObject) -> Path:
    path = mission_path(ip_dir, str(payload.get("id") or ""))
    issues = validate_instance(payload, path)
    if issues:
        raise ValueError(json.dumps({"schema_issues": issues}, indent=2, sort_keys=True))
    run_common.write_json(path, payload)
    write_index(ip_dir)
    return path


def summarize_plan(plan_payload: JsonObject | None) -> JsonObject:
    if not isinstance(plan_payload, dict):
        return {"open_items": [], "recommended_action": {}, "candidate_count": 0, "open_item_count": 0}
    candidates = [item for item in plan_payload.get("candidates", []) if isinstance(item, dict)]
    recommended = next((item for item in candidates if item.get("recommended") is True), candidates[0] if candidates else {})
    open_items = [item for item in plan_payload.get("open_items", []) if isinstance(item, dict)]
    return {
        "open_items": open_items,
        "recommended_action": recommended,
        "candidate_count": len(candidates),
        "open_item_count": len(open_items),
        "action_graph_summary": plan_payload.get("dependency_graph_summary") if isinstance(plan_payload.get("dependency_graph_summary"), dict) else {},
    }


def unresolved_open_items(payload: JsonObject) -> list[JsonObject]:
    return [
        item
        for item in payload.get("current_open_items", [])
        if isinstance(item, dict) and str(item.get("severity") or "") in {"P0", "P1"}
    ]


def mission_action_types(ip_dir: Path, payload: JsonObject) -> dict[str, int]:
    actions = action_instances_by_id(ip_dir)
    counts: dict[str, int] = {}
    for action_id in payload.get("action_instance_refs", []) if isinstance(payload.get("action_instance_refs"), list) else []:
        action = actions.get(str(action_id), {})
        if action.get("status") != "accepted":
            continue
        action_type = str(action.get("action_type") or "")
        if action_type:
            counts[action_type] = counts.get(action_type, 0) + 1
    return counts


def criterion(name: str, passed: bool, detail: str = "") -> JsonObject:
    return {"name": name, "passed": bool(passed), "detail": detail}


def evaluate_mission_completion(ip_dir: Path, mission_id: str = "active", mission_payload: JsonObject | None = None) -> JsonObject:
    ip_dir = oag_paths.ip_root(ip_dir)
    payload = dict(mission_payload) if isinstance(mission_payload, dict) else resolve_mission(ip_dir, mission_id)
    payload.pop("_path", None)
    if not payload:
        return {"status": "missing", "criteria": [], "issues": [issue("MISSION_INSTANCE_MISSING", f"mission not found: {mission_id}")]}
    state = run_common.collect_run_state(ip_dir)
    template_id = str(payload.get("template_id") or "")
    open_items = unresolved_open_items(payload)
    accepted_types = mission_action_types(ip_dir, payload)
    gates = state.get("gates", {}) if isinstance(state.get("gates"), dict) else {}
    scope = state.get("scope_lock", {}) if isinstance(state.get("scope_lock"), dict) else {}
    compile_manifest = state.get("compile_manifest", {}) if isinstance(state.get("compile_manifest"), dict) else {}
    stale_lifecycle = state.get("stale_lifecycle", {}) if isinstance(state.get("stale_lifecycle"), dict) else {}
    wavefront = state.get("wavefront", {}) if isinstance(state.get("wavefront"), dict) else {}
    criteria = [
        criterion("no_active_wavefront_locks", int(wavefront.get("active_lock_count") or 0) == 0),
        criterion("no_pending_gates", int(gates.get("pending_gate_count") or 0) == 0),
        criterion("no_p0_p1_open_items", not open_items, f"{len(open_items)} unresolved P0/P1 open items"),
    ]

    if template_id == "MISSION_INTAKE_TO_RTL_READY":
        criteria.extend(
            [
                criterion("scope_locked", scope.get("state") == "locked", str(scope.get("state") or "")),
                criterion("compile_manifest_pass", compile_manifest.get("status") == "pass", str(compile_manifest.get("status") or "")),
            ]
        )
    elif template_id == "MISSION_RTL_READY_TO_IMPLEMENTED":
        criteria.extend(
            [
                criterion("rtl_action_accepted", accepted_types.get("ACT_RTL_IMPLEMENTATION", 0) > 0),
                criterion("tb_action_accepted", accepted_types.get("ACT_TB_IMPLEMENTATION", 0) > 0),
            ]
        )
    elif template_id == "MISSION_IMPLEMENTED_TO_VALIDATED":
        criteria.extend(
            [
                criterion("evidence_validation_action_accepted", accepted_types.get("ACT_EVIDENCE_VALIDATION", 0) > 0),
                criterion("lifecycle_not_stale", stale_lifecycle.get("status") != "fail", str(stale_lifecycle.get("status") or "")),
            ]
        )
    elif template_id == "MISSION_VALIDATED_TO_GATE_PASS":
        gate_decision = gates.get("gate_decision") if isinstance(gates.get("gate_decision"), dict) else {}
        validation_report = gates.get("validation_report") if isinstance(gates.get("validation_report"), dict) else {}
        criteria.extend(
            [
                criterion("validation_report_exists", bool(validation_report.get("exists"))),
                criterion("gate_decision_exists", bool(gate_decision.get("exists"))),
                criterion("gate_decision_fresh", not bool(gates.get("gate_decision_stale"))),
            ]
        )
    elif template_id == "MISSION_LEGACY_IP_GAP_REPAIR":
        criteria.extend(
            [
                criterion("implementation_or_validation_action_accepted", any(accepted_types.get(action_type, 0) > 0 for action_type in {"ACT_RTL_IMPLEMENTATION", "ACT_TB_IMPLEMENTATION", "ACT_EVIDENCE_VALIDATION"})),
            ]
        )

    open_action_count = 0
    actions = action_instances_by_id(ip_dir)
    for action_id in payload.get("action_instance_refs", []) if isinstance(payload.get("action_instance_refs"), list) else []:
        action = actions.get(str(action_id), {})
        if action and action.get("status") not in ACTION_TERMINAL_STATUSES:
            open_action_count += 1
    criteria.append(criterion("no_open_action_instances", open_action_count == 0, f"{open_action_count} open actions"))

    complete = all(item.get("passed") for item in criteria)
    blocked = any(str(item.get("name")) in {"no_active_wavefront_locks", "no_pending_gates"} and not item.get("passed") for item in criteria)
    return {
        "schema_version": "oag_mission_completion_evaluation.v1",
        "status": "completed" if complete else "blocked" if blocked else "in_progress",
        "mission_id": payload.get("id") or "",
        "template_id": template_id,
        "evaluated_at": run_common.utc_now(),
        "criteria": criteria,
        "accepted_action_types": accepted_types,
        "unresolved_open_items": open_items,
    }


def bounded_observations(payload: JsonObject, observation: JsonObject) -> list[JsonObject]:
    observations = payload.get("observations")
    if not isinstance(observations, list):
        observations = []
    observations.append(observation)
    return [item for item in observations[-24:] if isinstance(item, dict)]


def ensure_mission_instance(
    ip_dir: Path,
    template_id: str,
    *,
    plan_payload: JsonObject | None = None,
    actor: str = "codex",
    rotate_on_template_change: bool = True,
) -> JsonObject:
    ip_dir = oag_paths.ip_root(ip_dir)
    templates = load_mission_templates()
    now = run_common.utc_now()
    summary = summarize_plan(plan_payload)
    active = latest_active_mission(ip_dir, template_id=template_id)
    if active:
        path = active.pop("_path", mission_path(ip_dir, str(active.get("id") or "")))
        active["last_observed_at"] = now
        active["current_open_items"] = summary["open_items"]
        active["current_recommended_action"] = summary["recommended_action"]
        active["current_action_graph_summary"] = summary["action_graph_summary"]
        active["completion_evaluation"] = evaluate_mission_completion(ip_dir, str(active.get("id") or "active"), mission_payload=active)
        active["observations"] = bounded_observations(
            active,
            {
                "at": now,
                "kind": "mission_observed",
                "actor": actor,
                "candidate_count": summary["candidate_count"],
                "open_item_count": summary["open_item_count"],
                "recommended_action_type": summary["recommended_action"].get("action_type") if isinstance(summary["recommended_action"], dict) else "",
            },
        )
        write_instance(ip_dir, active)
        active["_path"] = path
        return active

    if rotate_on_template_change:
        for path in existing_mission_paths(ip_dir):
            payload = read_json(path)
            if payload.get("status") == "active":
                payload["status"] = "superseded"
                payload["completed_at"] = now
                payload["superseded_by_template"] = template_id
                payload["observations"] = bounded_observations(
                    payload,
                    {
                        "at": now,
                        "kind": "mission_superseded",
                        "actor": actor,
                        "new_template_id": template_id,
                    },
                )
                write_instance(ip_dir, payload)

    template = templates.get(template_id, {})
    mission_id = new_mission_id(template_id)
    payload: JsonObject = {
        "schema_version": SCHEMA_VERSION,
        "id": mission_id,
        "template_id": template_id,
        "status": "active",
        "started_at": now,
        "last_observed_at": now,
        "target_state": template.get("target_state") if isinstance(template.get("target_state"), dict) else {},
        "current_open_items": summary["open_items"],
        "current_recommended_action": summary["recommended_action"],
        "current_action_graph_summary": summary["action_graph_summary"],
        "action_instance_refs": [],
        "observations": [
            {
                "at": now,
                "kind": "mission_started",
                "actor": actor,
                "candidate_count": summary["candidate_count"],
                "open_item_count": summary["open_item_count"],
            }
        ],
    }
    payload["completion_evaluation"] = {
        "schema_version": "oag_mission_completion_evaluation.v1",
        "status": "in_progress",
        "mission_id": mission_id,
        "template_id": template_id,
        "evaluated_at": now,
        "criteria": [],
    }
    path = write_instance(ip_dir, payload)
    payload["_path"] = path
    return payload


def attach_action(ip_dir: Path, mission_id: str, action_id: str) -> JsonObject:
    path = mission_path(ip_dir, mission_id)
    payload = read_json(path)
    if not payload:
        return {"status": "fail", "issues": [issue("MISSION_INSTANCE_MISSING", f"mission does not exist: {mission_id}", str(path))]}
    refs = payload.get("action_instance_refs")
    if not isinstance(refs, list):
        refs = []
    if action_id not in refs:
        refs.append(action_id)
    payload["action_instance_refs"] = refs
    payload["last_observed_at"] = run_common.utc_now()
    payload["observations"] = bounded_observations(payload, {"at": payload["last_observed_at"], "kind": "action_attached", "action_id": action_id})
    written = write_instance(ip_dir, payload)
    return {"status": "pass", "path": run_common.rel_to_ip(ip_dir, written), "mission_id": mission_id, "action_id": action_id}


def update_mission_status(ip_dir: Path, mission_id: str, status: str, summary: str = "") -> JsonObject:
    if status not in ACTIVE_STATUSES | TERMINAL_STATUSES:
        return {"status": "fail", "issues": [issue("MISSION_STATUS_INVALID", f"invalid mission status: {status}")]}
    if mission_id in {"active", "latest"}:
        payload = latest_active_mission(ip_dir) if mission_id == "active" else latest_mission(ip_dir)
        mission_id = str(payload.get("id") or "")
    path = mission_path(ip_dir, mission_id)
    payload = read_json(path)
    if not payload:
        return {"status": "fail", "issues": [issue("MISSION_INSTANCE_MISSING", f"mission does not exist: {mission_id}", str(path))]}
    now = run_common.utc_now()
    payload["status"] = status
    payload["last_observed_at"] = now
    if status in TERMINAL_STATUSES:
        payload["completed_at"] = now
    payload["observations"] = bounded_observations(payload, {"at": now, "kind": "mission_status_update", "status": status, "summary": summary})
    written = write_instance(ip_dir, payload)
    return {"status": "pass", "path": run_common.rel_to_ip(ip_dir, written), "mission": payload}


def mission_summary(path: Path) -> JsonObject:
    payload = read_json(path)
    return {
        "id": payload.get("id") or path.stem,
        "template_id": payload.get("template_id") or "",
        "status": payload.get("status") or "",
        "started_at": payload.get("started_at") or "",
        "last_observed_at": payload.get("last_observed_at") or "",
        "completed_at": payload.get("completed_at") or "",
        "action_count": len(payload.get("action_instance_refs", [])) if isinstance(payload.get("action_instance_refs"), list) else 0,
        "current_recommended_action_type": payload.get("current_recommended_action", {}).get("action_type") if isinstance(payload.get("current_recommended_action"), dict) else "",
        "path": path.name,
    }


def write_index(ip_dir: Path) -> Path:
    root = mission_dir(ip_dir)
    rows = [mission_summary(path) for path in existing_mission_paths(ip_dir)]
    payload = {
        "schema_version": "oag_mission_index.v1",
        "generated_at": run_common.utc_now(),
        "ip": ip_dir.name,
        "missions": rows,
        "counts": {
            "total": len(rows),
            "active": sum(1 for row in rows if row.get("status") == "active"),
            "terminal": sum(1 for row in rows if row.get("status") in TERMINAL_STATUSES),
        },
    }
    path = root / "_index.json"
    run_common.write_json(path, payload)
    return path


def resolve_mission(ip_dir: Path, selector: str) -> JsonObject:
    if selector == "active":
        return latest_active_mission(ip_dir)
    if selector == "latest":
        return latest_mission(ip_dir)
    path = mission_path(ip_dir, selector)
    payload = read_json(path)
    if payload:
        payload["_path"] = path
    return payload


def print_result(result: JsonObject, *, json_mode: bool) -> int:
    if json_mode:
        print(json.dumps(result, indent=2, sort_keys=True))
    elif result.get("status") == "pass":
        print(f"PASS {RESULT_SCHEMA_VERSION}: {result.get('path', result.get('mission_id', ''))}")
    else:
        print(f"FAIL {RESULT_SCHEMA_VERSION}", file=sys.stderr)
        for item in result.get("issues", []):
            print(f"- {item.get('code')}: {item.get('message')}", file=sys.stderr)
    return 0 if result.get("status") == "pass" else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    ensure = sub.add_parser("ensure", help="Ensure an active mission instance for a template.")
    ensure.add_argument("--ip-dir", required=True)
    ensure.add_argument("--template-id", required=True)
    ensure.add_argument("--actor", default="codex")
    ensure.add_argument("--json", action="store_true")

    show = sub.add_parser("show", help="Show active, latest, or a specific mission.")
    show.add_argument("--ip-dir", required=True)
    show.add_argument("--mission-id", default="active")
    show.add_argument("--json", action="store_true")

    list_cmd = sub.add_parser("list", help="Refresh and show the mission index.")
    list_cmd.add_argument("--ip-dir", required=True)
    list_cmd.add_argument("--json", action="store_true")

    complete = sub.add_parser("complete", help="Update mission status.")
    complete.add_argument("--ip-dir", required=True)
    complete.add_argument("--mission-id", default="active")
    complete.add_argument("--status", required=True, choices=sorted(ACTIVE_STATUSES | TERMINAL_STATUSES))
    complete.add_argument("--summary", default="")
    complete.add_argument("--json", action="store_true")

    evaluate = sub.add_parser("evaluate", help="Evaluate mission completion criteria.")
    evaluate.add_argument("--ip-dir", required=True)
    evaluate.add_argument("--mission-id", default="active")
    evaluate.add_argument("--mark-complete", action="store_true")
    evaluate.add_argument("--json", action="store_true")

    args = parser.parse_args(argv)
    ip_dir = oag_paths.ip_root(args.ip_dir)
    try:
        if args.command == "ensure":
            mission = ensure_mission_instance(ip_dir, args.template_id, actor=args.actor)
            path = mission.pop("_path", mission_path(ip_dir, str(mission.get("id") or "")))
            result = {
                "schema_version": RESULT_SCHEMA_VERSION,
                "status": "pass",
                "mission_id": mission.get("id"),
                "path": run_common.rel_to_ip(ip_dir, path),
                "mission": mission,
            }
        elif args.command == "show":
            mission = resolve_mission(ip_dir, args.mission_id)
            if not mission:
                result = {"schema_version": RESULT_SCHEMA_VERSION, "status": "fail", "issues": [issue("MISSION_INSTANCE_MISSING", f"mission not found: {args.mission_id}")]}
            else:
                path = mission.pop("_path", mission_path(ip_dir, str(mission.get("id") or "")))
                result = {"schema_version": RESULT_SCHEMA_VERSION, "status": "pass", "path": run_common.rel_to_ip(ip_dir, path), "mission": mission}
        elif args.command == "list":
            path = write_index(ip_dir)
            result = {"schema_version": RESULT_SCHEMA_VERSION, "status": "pass", "path": run_common.rel_to_ip(ip_dir, path), "index": read_json(path)}
        elif args.command == "complete":
            updated = update_mission_status(ip_dir, args.mission_id, args.status, args.summary)
            result = {"schema_version": RESULT_SCHEMA_VERSION, **updated}
        elif args.command == "evaluate":
            evaluation = evaluate_mission_completion(ip_dir, args.mission_id)
            updated: JsonObject = {}
            if args.mark_complete and evaluation.get("status") == "completed":
                updated = update_mission_status(ip_dir, evaluation.get("mission_id") or args.mission_id, "completed", "mission completion criteria passed")
            result = {"schema_version": RESULT_SCHEMA_VERSION, "status": "pass" if not evaluation.get("issues") else "fail", "evaluation": evaluation, "updated": updated}
        else:
            result = {"schema_version": RESULT_SCHEMA_VERSION, "status": "fail", "issues": [issue("UNKNOWN_COMMAND", str(args.command))]}
    except Exception as exc:
        result = {"schema_version": RESULT_SCHEMA_VERSION, "status": "fail", "issues": [issue("MISSION_RUNTIME_EXCEPTION", str(exc))]}
    return print_result(result, json_mode=bool(getattr(args, "json", False)))


if __name__ == "__main__":
    raise SystemExit(main())
