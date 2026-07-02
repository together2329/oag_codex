#!/usr/bin/env python3
"""Generate Mission/Action candidates from the current OAG state."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

SCRIPTS_DIR = Path(__file__).resolve().parent
CODEX_ROOT = SCRIPTS_DIR.parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import oag_authoring_packet_check  # noqa: E402
import oag_contract_strength_check  # noqa: E402
import oag_lock_readiness_check  # noqa: E402
import oag_mission_runtime  # noqa: E402
import oag_paths  # noqa: E402
import oag_req_quality_check  # noqa: E402
import oag_requirement_atom_check  # noqa: E402
import oag_role_health  # noqa: E402
import oag_run_control_common as run_common  # noqa: E402
import oag_verification_plan_check  # noqa: E402
from oag_validate_json import contextual_schema_issues  # noqa: E402


SCHEMA_VERSION = "oag_action_candidates.v1"
RESULT_SCHEMA_VERSION = "oag_action_plan_result.v1"
ACTION_CATALOG = CODEX_ROOT / "oag" / "operation_action_types.yaml"
MISSION_CATALOG = CODEX_ROOT / "oag" / "mission_templates.yaml"

PRIORITY_RANK = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}
STATUS_RANK = {"ready": 0, "blocked": 1, "informational": 2}
PRIORITY_SCORE = {"P0": 100, "P1": 70, "P2": 40, "P3": 10}
OPEN_ITEM_SCORE = {"P0": 30, "P1": 20, "P2": 10, "P3": 5}
STATUS_SCORE = {"ready": 20, "blocked": -30, "informational": 0}
RECOVERY_ACTIONS = {"ACT_RESOLVE_ORCHESTRATION_HAZARD", "ACT_ORCHESTRATION_RECOVERY", "ACT_RESOLVE_PENDING_GATE"}
SELF_EXPLORE_ACTION = "ACT_SELF_EXPLORE_OPTIONS"
SELF_EXPLORE_SOURCE_RELS = (
    "req/source_claims.yaml",
    "req/ambiguity_register.yaml",
    "req/deep_semantic_intake",
    "doc",
    "rtl",
    "ontology/decision_matrix.yaml",
    "ontology/features.yaml",
    "ontology/ipxact_projection.yaml",
    "ontology/requirements.yaml",
    "ontology/requirement_atoms.yaml",
    "ontology/obligations.yaml",
    "ontology/contracts.yaml",
    "ontology/verification_plan.yaml",
)


JsonObject = dict[str, Any]


def issue(code: str, message: str, path: str = "") -> dict[str, str]:
    payload = {"code": code, "message": message}
    if path:
        payload["path"] = path
    return payload


def read_yaml(path: Path) -> JsonObject:
    if not path.is_file():
        return {}
    try:
        import yaml  # type: ignore

        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        return data if isinstance(data, dict) else {}
    except Exception as exc:
        return {"__load_error__": str(exc)}


def as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def text(value: Any) -> str:
    return str(value or "").strip()


def load_action_catalog() -> tuple[dict[str, JsonObject], list[dict[str, str]]]:
    payload = read_yaml(ACTION_CATALOG)
    issues: list[dict[str, str]] = []
    if not payload:
        return {}, [issue("ACTION_CATALOG_MISSING", "operation action type catalog is missing", str(ACTION_CATALOG))]
    if "__load_error__" in payload:
        return {}, [issue("ACTION_CATALOG_INVALID", str(payload["__load_error__"]), str(ACTION_CATALOG))]
    issues.extend(
        contextual_schema_issues(
            "oag_operation_action_types.schema.json",
            payload,
            code_prefix="ACTION_CATALOG_SCHEMA",
            document_path=str(ACTION_CATALOG),
        )
    )
    rows = [item for item in payload.get("action_types", []) if isinstance(item, dict)]
    return {text(row.get("id")): row for row in rows if text(row.get("id"))}, issues


def load_missions() -> tuple[dict[str, JsonObject], list[dict[str, str]]]:
    payload = read_yaml(MISSION_CATALOG)
    issues: list[dict[str, str]] = []
    if not payload:
        return {}, [issue("MISSION_CATALOG_MISSING", "mission template catalog is missing", str(MISSION_CATALOG))]
    if "__load_error__" in payload:
        return {}, [issue("MISSION_CATALOG_INVALID", str(payload["__load_error__"]), str(MISSION_CATALOG))]
    issues.extend(
        contextual_schema_issues(
            "oag_mission_templates.schema.json",
            payload,
            code_prefix="MISSION_CATALOG_SCHEMA",
            document_path=str(MISSION_CATALOG),
        )
    )
    rows = [item for item in payload.get("mission_templates", []) if isinstance(item, dict)]
    return {text(row.get("id")): row for row in rows if text(row.get("id"))}, issues


def default_mission(state: JsonObject, *, gate_stale: bool = False, evidence_problem: bool = False) -> str:
    if state.get("scope_lock", {}).get("state") != "locked":
        return "MISSION_INTAKE_TO_RTL_READY"
    if gate_stale:
        return "MISSION_VALIDATED_TO_GATE_PASS"
    if evidence_problem:
        return "MISSION_IMPLEMENTED_TO_VALIDATED"
    return "MISSION_RTL_READY_TO_IMPLEMENTED"


def safe_check(label: str, fn: Any, *args: Any, **kwargs: Any) -> JsonObject:
    try:
        data = fn(*args, **kwargs)
        return data if isinstance(data, dict) else {"status": "fail", "issues": [issue("CHECK_RETURN", f"{label} returned non-object")]}
    except Exception as exc:
        return {"status": "fail", "issues": [issue("CHECK_EXCEPTION", f"{label}: {exc}")]}


def add_open_item(open_items: list[JsonObject], code: str, message: str, *, severity: str, source: str, path: str = "", target_objects: JsonObject | None = None) -> str:
    item_id = f"OPEN_{len(open_items) + 1:04d}_{code}"
    open_items.append(
        {
            "id": item_id,
            "code": code,
            "message": message,
            "severity": severity,
            "source": source,
            "path": path,
            "target_objects": target_objects or {},
        }
    )
    return item_id


def suffix(value: str) -> str:
    clean = re.sub(r"[^A-Za-z0-9_]+", "_", value).strip("_")
    return clean[:72] or "GENERIC"


def make_candidate(
    candidates: list[JsonObject],
    action_types: dict[str, JsonObject],
    *,
    action_type: str,
    priority: str,
    status: str,
    reason: str,
    target_objects: JsonObject,
    open_item_ids: list[str],
    preconditions: JsonObject,
    expected_effects: JsonObject,
    command: str,
    mission_template: str,
) -> None:
    catalog = action_types.get(action_type, {})
    owner = text(catalog.get("owner_role")) or "main"
    cid = f"ACT_CAND_{priority}_{suffix(action_type)}_{len(candidates) + 1:03d}"
    candidates.append(
        {
            "id": cid,
            "action_type": action_type,
            "action_label": text(catalog.get("label")) or action_type,
            "mission_template": mission_template,
            "status": status,
            "priority": priority,
            "recommended": False,
            "recommendation_reason": reason,
            "target_objects": target_objects,
            "open_items": open_item_ids,
            "preconditions": preconditions,
            "owner_role": owner,
            "expected_effects": expected_effects,
            "command": command,
        }
    )


def decision_rows(ip_dir: Path) -> list[JsonObject]:
    doc = read_yaml(oag_paths.legacy_or_hidden(ip_dir, "ontology/decision_matrix.yaml"))
    return [item for item in as_list(doc.get("decisions")) if isinstance(item, dict)]


def count_issues(result: JsonObject) -> int:
    return len([item for item in result.get("issues", []) if isinstance(item, dict)])


def action_instance_paths(ip_dir: Path) -> list[Path]:
    root = oag_paths.state_path(ip_dir, "knowledge/actions")
    if not root.is_dir():
        return []
    return sorted(path for path in root.glob("ACT_RUN_*.json") if path.is_file())


def read_json(path: Path) -> JsonObject:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _source_fingerprint(ip_dir: Path, rel_path: str) -> JsonObject:
    path = oag_paths.legacy_or_hidden(ip_dir, rel_path)
    if path.is_file():
        return {
            "path": run_common.rel_to_ip(ip_dir, path),
            "kind": "file",
            "exists": True,
            "sha256": run_common.sha256_file(path),
            "bytes": path.stat().st_size,
        }
    if path.is_dir():
        rows: list[JsonObject] = []
        total_bytes = 0
        for child in sorted(item for item in path.rglob("*") if item.is_file())[:128]:
            try:
                size = child.stat().st_size
            except OSError:
                size = 0
            total_bytes += size
            rows.append(
                {
                    "path": run_common.rel_to_ip(ip_dir, child),
                    "sha256": run_common.sha256_file(child),
                    "bytes": size,
                }
            )
        digest_payload = json.dumps(rows, sort_keys=True).encode("utf-8")
        return {
            "path": run_common.rel_to_ip(ip_dir, path),
            "kind": "directory",
            "exists": True,
            "sha256": hashlib.sha256(digest_payload).hexdigest(),
            "file_count_sampled": len(rows),
            "bytes_sampled": total_bytes,
        }
    return {
        "path": rel_path,
        "kind": "missing",
        "exists": False,
        "sha256": "",
        "bytes": 0,
    }


def self_explore_fingerprint(ip_dir: Path, *, target_objects: JsonObject | None = None, reason: str = "") -> JsonObject:
    sources = [_source_fingerprint(ip_dir, rel_path) for rel_path in SELF_EXPLORE_SOURCE_RELS]
    payload: JsonObject = {
        "target_objects": target_objects or {},
        "reason": reason,
        "sources": sources,
    }
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()
    return {"sha256": digest, "payload": payload, "source_count": len(sources)}


def self_explore_current(ip_dir: Path, fingerprint_sha: str) -> bool:
    path = oag_paths.state_path(ip_dir, "knowledge/mission_loop/exploration_plan.json")
    payload = read_json(path)
    if payload.get("schema_version") != "oag_exploration_plan.v1":
        return False
    if payload.get("status") != "pass":
        return False
    fingerprint = payload.get("input_fingerprint") if isinstance(payload.get("input_fingerprint"), dict) else {}
    return str(fingerprint.get("sha256") or "") == fingerprint_sha


def self_explore_sources_available(ip_dir: Path) -> bool:
    return any(_source_fingerprint(ip_dir, rel_path).get("exists") is True for rel_path in SELF_EXPLORE_SOURCE_RELS)


def stuck_action_instances(ip_dir: Path, *, stuck_seconds: int) -> list[JsonObject]:
    now = run_common.parse_utc(run_common.utc_now())
    rows: list[JsonObject] = []
    for path in action_instance_paths(ip_dir):
        payload = read_json(path)
        if payload.get("status") not in {"started", "running"}:
            continue
        age = run_common.age_seconds(payload.get("started_at"), now=now)
        if age is None or age < stuck_seconds:
            continue
        rows.append(
            {
                "action_id": payload.get("id") or path.stem,
                "action_type": payload.get("action_type") or "",
                "status": payload.get("status") or "",
                "started_at": payload.get("started_at") or "",
                "age_seconds": int(age),
                "path": run_common.rel_to_ip(ip_dir, path),
            }
        )
    return rows


def role_health_by_role(role_health: JsonObject) -> dict[str, JsonObject]:
    rows = role_health.get("roles")
    if not isinstance(rows, list):
        return {}
    return {str(row.get("role") or ""): row for row in rows if isinstance(row, dict)}


def score_candidate(candidate: JsonObject, open_items_by_id: dict[str, JsonObject], mission_priority: dict[str, int], role_health_rows: dict[str, JsonObject] | None = None) -> JsonObject:
    factors: JsonObject = {
        "priority": PRIORITY_SCORE.get(candidate.get("priority"), 0),
        "status": STATUS_SCORE.get(candidate.get("status"), 0),
        "mission_order": max(0, 30 - (mission_priority.get(candidate.get("action_type"), 999) * 2)),
        "open_item_severity": 0,
        "human_decision": 0,
        "recovery_or_gate": 0,
        "role_health": 0,
    }
    severities = []
    for item_id in candidate.get("open_items", []) if isinstance(candidate.get("open_items"), list) else []:
        item = open_items_by_id.get(str(item_id))
        if isinstance(item, dict):
            severities.append(str(item.get("severity") or ""))
    factors["open_item_severity"] = max((OPEN_ITEM_SCORE.get(severity, 0) for severity in severities), default=0)
    if str(candidate.get("owner_role") or "").startswith("human"):
        factors["human_decision"] = 8
    if candidate.get("action_type") in RECOVERY_ACTIONS:
        factors["recovery_or_gate"] = 15
    role = str(candidate.get("owner_role") or "")
    role_row = (role_health_rows or {}).get(role, {})
    if role_row.get("status") == "stuck":
        factors["role_health"] = -35
    elif role_row.get("status") == "degraded":
        factors["role_health"] = -20
    if candidate.get("action_type") == "ACT_ORCHESTRATION_RECOVERY" and role_health_rows:
        factors["role_health"] = max(int(factors["role_health"]), 15)
    total = sum(value for value in factors.values() if isinstance(value, int))
    return {"total": total, "factors": factors}


def build_dependency_graph(candidates: list[JsonObject], mission_id: str, mission_priority: dict[str, int], *, mission_instance_id: str = "") -> JsonObject:
    nodes: list[JsonObject] = []
    edges: list[JsonObject] = []
    by_type: dict[str, JsonObject] = {}
    for candidate in candidates:
        nodes.append(
            {
                "id": candidate.get("id") or "",
                "action_type": candidate.get("action_type") or "",
                "status": candidate.get("status") or "",
                "priority": candidate.get("priority") or "",
                "recommended": bool(candidate.get("recommended")),
                "score": candidate.get("score") if isinstance(candidate.get("score"), dict) else {},
            }
        )
        by_type.setdefault(str(candidate.get("action_type") or ""), candidate)

    ordered = sorted(candidates, key=lambda item: mission_priority.get(item.get("action_type"), 999))
    for earlier, later in zip(ordered, ordered[1:]):
        if mission_priority.get(earlier.get("action_type"), 999) == 999 or mission_priority.get(later.get("action_type"), 999) == 999:
            continue
        edges.append(
            {
                "from": earlier.get("id") or "",
                "to": later.get("id") or "",
                "kind": "mission_priority_before",
                "reason": "Mission template action_priority orders these action types.",
            }
        )

    for blocked in [item for item in candidates if item.get("status") == "blocked"]:
        blocked_order = mission_priority.get(blocked.get("action_type"), 999)
        blockers = [item for item in candidates if item.get("status") == "ready" and mission_priority.get(item.get("action_type"), 999) < blocked_order]
        for blocker in blockers[:3]:
            edges.append(
                {
                    "from": blocker.get("id") or "",
                    "to": blocked.get("id") or "",
                    "kind": "blocked_by_prior_action",
                    "reason": "Blocked candidate depends on an earlier ready action in the mission template.",
                }
            )

    return {
        "schema_version": "oag_action_graph.v1",
        "generated_at": run_common.utc_now(),
        "ip": "",
        "mission_template": mission_id,
        "mission_instance_id": mission_instance_id,
        "nodes": nodes,
        "edges": edges,
        "summary": {
            "node_count": len(nodes),
            "edge_count": len(edges),
            "ready_count": sum(1 for item in candidates if item.get("status") == "ready"),
            "blocked_count": sum(1 for item in candidates if item.get("status") == "blocked"),
            "recommended_action_type": next((item.get("action_type") for item in candidates if item.get("recommended")), ""),
        },
    }


def build_plan(ip_dir: Path, *, mission_template: str = "", write: bool = True, run_semantic_checks: bool = True, stuck_seconds: int = 900) -> JsonObject:
    ip_dir = oag_paths.ip_root(ip_dir)
    if not ip_dir.is_dir():
        return {
            "schema_version": RESULT_SCHEMA_VERSION,
            "status": "fail",
            "issues": [issue("IP_DIR_MISSING", "IP directory does not exist", str(ip_dir))],
        }

    action_types, catalog_issues = load_action_catalog()
    missions, mission_issues = load_missions()
    state = run_common.collect_run_state(ip_dir)
    locked = state.get("scope_lock", {}).get("state") == "locked"
    gate_stale = bool(state.get("gates", {}).get("gate_decision_stale"))
    open_items: list[JsonObject] = []
    candidates: list[JsonObject] = []
    checker_results: JsonObject = {}
    role_health = oag_role_health.collect_role_health(ip_dir, stuck_seconds=stuck_seconds)
    role_health_rows = role_health_by_role(role_health)

    if run_semantic_checks:
        checker_results["lock_readiness"] = safe_check("lock_readiness", oag_lock_readiness_check.check, ip_dir, require_locked=locked)
        checker_results["req_quality"] = safe_check("req_quality", oag_req_quality_check.check, ip_dir, require_locked=locked)
        checker_results["requirement_atom"] = safe_check("requirement_atom", oag_requirement_atom_check.check, ip_dir, require_locked=locked)
        checker_results["contract_strength"] = safe_check("contract_strength", oag_contract_strength_check.check, ip_dir, require_locked=locked)
        checker_results["verification_plan"] = safe_check("verification_plan", oag_verification_plan_check.check, ip_dir, require_locked=locked)
        if locked:
            checker_results["authoring_packet"] = safe_check("authoring_packet", oag_authoring_packet_check.check, ip_dir, require_locked=False, require_packets=True, require_lifecycle=False)

    evidence_problem = state.get("stale_lifecycle", {}).get("status") == "fail"
    mission_id = mission_template or default_mission(state, gate_stale=gate_stale, evidence_problem=evidence_problem)
    if mission_id not in missions:
        mission_issues.append(issue("MISSION_UNKNOWN", f"mission template is not in catalog: {mission_id}", str(MISSION_CATALOG)))

    active_locks = state.get("wavefront", {}).get("active_locks", [])
    if active_locks:
        item_id = add_open_item(
            open_items,
            "ACTIVE_WAVEFRONT_LOCKS",
            "Active wavefront ownership locks are present.",
            severity="P0",
            source="run_state.wavefront",
            target_objects={"active_locks": active_locks},
        )
        make_candidate(
            candidates,
            action_types,
            action_type="ACT_RESOLVE_ORCHESTRATION_HAZARD",
            priority="P0",
            status="ready",
            reason="Active locks must be audited before replacement dispatch or more write work.",
            target_objects={"active_locks": active_locks},
            open_item_ids=[item_id],
            preconditions={"active_lock_count": len(active_locks)},
            expected_effects={"creates": ["orchestration_guard_report"], "may_record": ["abort_or_recovery_decision"]},
            command="python3 .codex/scripts/oag_orchestration_guard.py audit --ip-dir <ip> --json",
            mission_template=mission_id,
        )

    pending_gates = state.get("gates", {}).get("pending_gates", [])
    if pending_gates:
        item_id = add_open_item(
            open_items,
            "PENDING_WORKFLOW_GATE",
            "A required workflow gate is pending.",
            severity="P0",
            source="run_state.gates",
            target_objects={"pending_gates": pending_gates},
        )
        make_candidate(
            candidates,
            action_types,
            action_type="ACT_RESOLVE_PENDING_GATE",
            priority="P0",
            status="ready",
            reason="A pending gate is a hard workflow stop; answer or resolve it before continuing execution.",
            target_objects={"pending_gates": pending_gates},
            open_item_ids=[item_id],
            preconditions={"pending_gate_count": len(pending_gates)},
            expected_effects={"writes": ["knowledge/gates/*.answer.json"], "creates": ["gate_resolution_record"]},
            command="python3 .codex/scripts/oag_gate_frame.py list --ip-dir <ip> --json",
            mission_template=mission_id,
        )

    stuck_actions = stuck_action_instances(ip_dir, stuck_seconds=stuck_seconds)
    if stuck_actions:
        item_id = add_open_item(
            open_items,
            "ACTION_INSTANCE_STUCK",
            "Started or running action instances exceeded the stuck timeout.",
            severity="P0",
            source="knowledge/actions",
            target_objects={"stuck_actions": stuck_actions},
        )
        make_candidate(
            candidates,
            action_types,
            action_type="ACT_ORCHESTRATION_RECOVERY",
            priority="P0",
            status="ready",
            reason="A durable action instance is still open past the timeout; recover or abort it before dispatching new dependent work.",
            target_objects={"stuck_actions": stuck_actions},
            open_item_ids=[item_id],
            preconditions={"stuck_seconds": stuck_seconds, "stuck_action_count": len(stuck_actions)},
            expected_effects={"writes": ["knowledge/actions/*.json"], "creates": ["recovery_decision"]},
            command="python3 .codex/scripts/oag_action_record.py update --ip-dir <ip> --action-id <action> --status aborted --summary '<recovery reason>' --json",
            mission_template=mission_id,
        )

    role_hazards = [item for item in role_health.get("hazards", []) if isinstance(item, dict)]
    if role_hazards:
        item_id = add_open_item(
            open_items,
            "ROLE_HEALTH_HAZARD",
            "One or more OAG roles have stuck or repeated bad terminal actions.",
            severity="P0",
            source="knowledge/operations/role_health",
            target_objects={"hazards": role_hazards},
        )
        make_candidate(
            candidates,
            action_types,
            action_type="ACT_ORCHESTRATION_RECOVERY",
            priority="P0",
            status="ready",
            reason="Role health is degraded or stuck; choose a recovery/fallback route before opening more work for the affected role.",
            target_objects={"role_health_hazards": role_hazards},
            open_item_ids=[item_id],
            preconditions={"role_health_hazard_count": len(role_hazards)},
            expected_effects={"writes": ["knowledge/actions/*.json"], "creates": ["role_recovery_decision", "fallback_route"]},
            command="python3 .codex/scripts/oag_role_health.py --ip-dir <ip> --json",
            mission_template=mission_id,
        )

    compile_status = state.get("compile_manifest", {}).get("status")
    if compile_status in {"missing", "stale"}:
        item_id = add_open_item(
            open_items,
            "COMPILE_MANIFEST_NOT_FRESH",
            f"Compile manifest status is {compile_status}.",
            severity="P0",
            source="run_state.compile_manifest",
            path=state.get("compile_manifest", {}).get("path", ""),
        )
        make_candidate(
            candidates,
            action_types,
            action_type="ACT_COMPILE_AUTHORING_PACKETS",
            priority="P0",
            status="ready",
            reason="Generated projections are missing or stale, so role packets and review frames may not reflect authored truth.",
            target_objects={"compile_manifest": state.get("compile_manifest", {})},
            open_item_ids=[item_id],
            preconditions={"authored_ontology_available": True},
            expected_effects={"writes": ["ontology/generated/*"], "creates": ["compile_manifest", "authoring_packets"]},
            command="python3 .codex/scripts/oag_cli.py call --json '{\"tool\":\"oag.compile\",\"arguments\":{\"ip_dir\":\"<ip>\"}}'",
            mission_template=mission_id,
        )

    ssot = state.get("ssot", {})
    if ssot.get("status") == "fail":
        item_id = add_open_item(
            open_items,
            "SSOT_SECTION_GAP",
            "Required SSOT sections are missing or empty.",
            severity="P0" if not locked else "P1",
            source="run_state.ssot",
            target_objects={"missing": ssot.get("missing", []), "empty": ssot.get("empty", [])},
        )
        make_candidate(
            candidates,
            action_types,
            action_type="ACT_REPAIR_SSOT_SECTION",
            priority="P0" if not locked else "P1",
            status="ready",
            reason="Required SSOT sections must exist before reliable planning, dispatch, or closure.",
            target_objects={"missing_sections": ssot.get("missing", []), "empty_sections": ssot.get("empty", [])},
            open_item_ids=[item_id],
            preconditions={"scope_locked": locked},
            expected_effects={"writes": ["req/*", "ontology/*"], "creates": ["draft_or_review_record"]},
            command="python3 .codex/scripts/oag_ssot_section_check.py --ip-dir <ip> --stage planning --json",
            mission_template=mission_id,
        )

    rows = decision_rows(ip_dir)
    unresolved = [
        row
        for row in rows
        if row.get("lock_required") is True and text(row.get("status")).lower() not in {"decided", "waived"}
    ]
    if unresolved:
        target_decisions = [text(row.get("id")) or f"decisions[{idx}]" for idx, row in enumerate(unresolved)]
        item_id = add_open_item(
            open_items,
            "UNRESOLVED_LOCK_DECISION",
            "Lock-required decision rows are unresolved, proposed, or blocked.",
            severity="P0",
            source="ontology/decision_matrix.yaml",
            path="ontology/decision_matrix.yaml",
            target_objects={"decisions": target_decisions},
        )
        explore_target = {"decisions": target_decisions, "human_action_after_exploration": "ACT_ASK_DEEP_INTERVIEW_QUESTION" if not locked else "ACT_RESOLVE_DECISION"}
        explore_fingerprint = self_explore_fingerprint(ip_dir, target_objects=explore_target, reason="resolve unresolved lock decision")
        if self_explore_sources_available(ip_dir) and not self_explore_current(ip_dir, str(explore_fingerprint.get("sha256") or "")):
            explore_item_id = add_open_item(
                open_items,
                "SELF_EXPLORATION_BEFORE_USER_QUESTION",
                "Local spec, RTL, ontology, or intake artifacts can be explored before asking the user.",
                severity="P0",
                source="action_plan.ask_vs_explore",
                target_objects={"decisions": target_decisions, "fingerprint": explore_fingerprint.get("sha256") or ""},
            )
            make_candidate(
                candidates,
                action_types,
                action_type=SELF_EXPLORE_ACTION,
                priority="P0",
                status="ready",
                reason="Before asking the human, explore available local sources and build a four-option recommendation with one residual question only if needed.",
                target_objects=explore_target,
                open_item_ids=[item_id, explore_item_id],
                preconditions={"local_sources_available": True, "fingerprint": explore_fingerprint.get("sha256") or ""},
                expected_effects={"writes": ["knowledge/mission_loop/exploration_plan.json"], "creates": ["option_matrix", "residual_question_policy"]},
                command="python3 .codex/scripts/oag_exploration_plan.py --ip-dir <ip> --json",
                mission_template=mission_id,
            )
        action = "ACT_ASK_DEEP_INTERVIEW_QUESTION" if not locked else "ACT_RESOLVE_DECISION"
        make_candidate(
            candidates,
            action_types,
            action_type=action,
            priority="P0",
            status="ready",
            reason="This is the highest-value user decision blocker for RTL-ready state.",
            target_objects={"decisions": target_decisions},
            open_item_ids=[item_id],
            preconditions={"scope_locked": locked, "lock_required_unresolved": len(unresolved)},
            expected_effects={"writes": ["ontology/decision_matrix.yaml", "req/source_claims.yaml"], "records": ["oag.draft"]},
            command="python3 .codex/scripts/oag_deep_interview_round.py template --ip-dir <ip> --dimension decision --json",
            mission_template=mission_id,
        )

    if run_semantic_checks:
        req_quality = checker_results.get("req_quality", {})
        if count_issues(req_quality):
            item_id = add_open_item(
                open_items,
                "REQUIREMENT_QUALITY_ISSUES",
                "Requirement/source-claim quality issues are present.",
                severity="P0" if locked else "P1",
                source="oag_req_quality_check",
                target_objects={"issue_count": count_issues(req_quality)},
            )
            make_candidate(
                candidates,
                action_types,
                action_type="ACT_CAPTURE_SOURCE_CLAIM",
                priority="P0" if locked else "P1",
                status="ready",
                reason="Requirement quality issues usually mean source claims, ambiguity status, or feature refs need normalization.",
                target_objects={"issue_count": count_issues(req_quality), "sample_issues": req_quality.get("issues", [])[:5]},
                open_item_ids=[item_id],
                preconditions={"scope_locked": locked},
                expected_effects={"writes": ["req/source_claims.yaml", "req/ambiguity_register.yaml", "ontology/requirements.yaml"]},
                command="python3 .codex/scripts/oag_req_quality_check.py --ip-dir <ip> --json",
                mission_template=mission_id,
            )

        atom = checker_results.get("requirement_atom", {})
        if count_issues(atom):
            item_id = add_open_item(
                open_items,
                "REQUIREMENT_ATOM_ISSUES",
                "Requirement atom, shallow obligation, or atom-derived contract issues are present.",
                severity="P0" if locked else "P1",
                source="oag_requirement_atom_check",
                target_objects={"issue_count": count_issues(atom)},
            )
            make_candidate(
                candidates,
                action_types,
                action_type="ACT_PROJECT_REQUIREMENT_ATOMS",
                priority="P0" if locked else "P1",
                status="ready",
                reason="Requirement atoms must be structured before reliable obligation and contract projection.",
                target_objects={"issue_count": count_issues(atom), "sample_issues": atom.get("issues", [])[:5]},
                open_item_ids=[item_id],
                preconditions={"scope_locked": locked},
                expected_effects={"writes": ["ontology/requirement_atoms.yaml", "ontology/obligations.yaml", "ontology/contracts.yaml"]},
                command="python3 .codex/scripts/oag_requirement_atom_check.py --ip-dir <ip> --json",
                mission_template=mission_id,
            )

        contract = checker_results.get("contract_strength", {})
        if count_issues(contract):
            item_id = add_open_item(
                open_items,
                "CONTRACT_STRENGTH_ISSUES",
                "Contract strength issues are present.",
                severity="P0" if locked else "P1",
                source="oag_contract_strength_check",
                target_objects={"issue_count": count_issues(contract)},
            )
            make_candidate(
                candidates,
                action_types,
                action_type="ACT_PROJECT_CONTRACTS",
                priority="P0" if locked else "P1",
                status="ready",
                reason="Closure-grade contracts need explicit assume/guarantee and proof refs before implementation or validation can rely on them.",
                target_objects={"issue_count": count_issues(contract), "sample_issues": contract.get("issues", [])[:5]},
                open_item_ids=[item_id],
                preconditions={"scope_locked": locked},
                expected_effects={"writes": ["ontology/contracts.yaml", "ontology/modeling.yaml", "ontology/verification_plan.yaml"]},
                command="python3 .codex/scripts/oag_contract_strength_check.py --ip-dir <ip> --json",
                mission_template=mission_id,
            )

        vplan = checker_results.get("verification_plan", {})
        if count_issues(vplan):
            item_id = add_open_item(
                open_items,
                "VERIFICATION_PLAN_ISSUES",
                "Verification plan issues are present.",
                severity="P0" if locked else "P1",
                source="oag_verification_plan_check",
                target_objects={"issue_count": count_issues(vplan)},
            )
            make_candidate(
                candidates,
                action_types,
                action_type="ACT_PROJECT_VERIFICATION_PLAN",
                priority="P0" if locked else "P1",
                status="ready",
                reason="TB implementation and closure need proof objectives, scenarios, scoreboard refs, and coverage intent.",
                target_objects={"issue_count": count_issues(vplan), "sample_issues": vplan.get("issues", [])[:5]},
                open_item_ids=[item_id],
                preconditions={"scope_locked": locked},
                expected_effects={"writes": ["ontology/verification_plan.yaml", "ontology/tb_methodology.yaml"]},
                command="python3 .codex/scripts/oag_verification_plan_check.py --ip-dir <ip> --json",
                mission_template=mission_id,
            )

        packet = checker_results.get("authoring_packet", {})
        if locked and count_issues(packet):
            item_id = add_open_item(
                open_items,
                "AUTHORING_PACKET_ISSUES",
                "Generated authoring packet issues are present.",
                severity="P0",
                source="oag_authoring_packet_check",
                target_objects={"issue_count": count_issues(packet)},
            )
            make_candidate(
                candidates,
                action_types,
                action_type="ACT_REPAIR_AUTHORING_PACKET_PROJECTION",
                priority="P0",
                status="ready",
                reason="RTL/TB dispatch must consume complete role-specific authoring packets.",
                target_objects={"issue_count": count_issues(packet), "sample_issues": packet.get("issues", [])[:5]},
                open_item_ids=[item_id],
                preconditions={"scope_locked": locked, "compile_manifest_status": compile_status},
                expected_effects={"writes": ["ontology/decomposition.yaml", "ontology/structure.yaml", "ontology/contracts.yaml"], "tool_side_effects": ["ontology/generated/*"]},
                command="python3 .codex/scripts/oag_authoring_packet_check.py --ip-dir <ip> --require-packets --json",
                mission_template=mission_id,
            )

    if not locked and not unresolved and ssot.get("status") != "fail":
        item_id = add_open_item(
            open_items,
            "SCOPE_UNLOCKED",
            "Scope is still draft.",
            severity="P1",
            source="ontology/scope_lock.json",
            path="ontology/scope_lock.json",
        )
        make_candidate(
            candidates,
            action_types,
            action_type="ACT_RENDER_LOCK_PREVIEW",
            priority="P1",
            status="ready",
            reason="Before lock, show the human exactly what would be locked in a formal review frame.",
            target_objects={"scope_lock_state": state.get("scope_lock", {}).get("state")},
            open_item_ids=[item_id],
            preconditions={"unresolved_lock_decisions": 0},
            expected_effects={"writes": ["knowledge/review_frames/*"], "creates": ["lock_preview_frame"]},
            command="python3 .codex/scripts/oag_lock_preview_frame.py --ip-dir <ip> --json",
            mission_template=mission_id,
        )
        make_candidate(
            candidates,
            action_types,
            action_type="ACT_LOCK_SCOPE",
            priority="P1",
            status="blocked",
            reason="Scope can be locked only after the user explicitly approves the current review frame.",
            target_objects={"scope_lock_state": "draft"},
            open_item_ids=[item_id],
            preconditions={"human_scope_approval_present": False},
            expected_effects={"writes": ["ontology/scope_lock.json"], "creates": ["decision_receipt"]},
            command="python3 .codex/scripts/oag_cli.py call --json '{\"tool\":\"oag.lock\",\"arguments\":{\"ip_dir\":\"<ip>\",\"summary\":\"<human-confirmed scope>\",\"confirmed_scope\":[],\"actor\":{\"kind\":\"human\",\"id\":\"user\",\"surface\":\"codex\"}}}'",
            mission_template=mission_id,
        )

    if locked and not active_locks and not pending_gates and not gate_stale:
        packet_status = checker_results.get("authoring_packet", {}).get("status")
        if packet_status == "pass" and compile_status == "pass":
            item_id = add_open_item(
                open_items,
                "IMPLEMENTATION_READY",
                "Scope is locked and authoring packets are ready for bounded implementation dispatch.",
                severity="P2",
                source="action_plan",
                target_objects={"scope_lock": "locked", "authoring_packet": "pass"},
            )
            for action_type in ("ACT_RTL_IMPLEMENTATION", "ACT_TB_IMPLEMENTATION"):
                make_candidate(
                    candidates,
                    action_types,
                    action_type=action_type,
                    priority="P2",
                    status="ready",
                    reason=f"{action_type} is available because lock, compile, and authoring packet gates are clean.",
                    target_objects={"authoring_packets": "ontology/generated/authoring_packets"},
                    open_item_ids=[item_id],
                    preconditions={"scope_locked": True, "authoring_packet_check": "pass", "active_lock_count": 0},
                    expected_effects={"creates": ["dispatch", "subagent_receipt"], "writes": ["bounded by dispatch"]},
                    command="python3 .codex/scripts/oag_dispatch.py create --ip-dir <ip> --agent-type <agent> --stage <stage> --allowed-write-path <ip>/<path> --receipt-path <ip>/knowledge/subagents/<receipt>.json --json",
                    mission_template=mission_id,
                )

    if evidence_problem:
        item_id = add_open_item(
            open_items,
            "STALE_LIFECYCLE",
            "Lifecycle stale check has issues.",
            severity="P0",
            source="oag_stale_check",
            target_objects={"stale_lifecycle": state.get("stale_lifecycle", {})},
        )
        make_candidate(
            candidates,
            action_types,
            action_type="ACT_EVIDENCE_VALIDATION",
            priority="P0",
            status="ready",
            reason="Evidence changed or went stale; refresh validation before closure or gate claims.",
            target_objects={"stale_lifecycle": state.get("stale_lifecycle", {})},
            open_item_ids=[item_id],
            preconditions={"evidence_artifacts_available": True},
            expected_effects={"writes": ["knowledge/validations/*", "knowledge/records/*"], "creates": ["validation_report"]},
            command="python3 .codex/scripts/oag_stale_check.py --ip-dir <ip> --json",
            mission_template=mission_id,
        )

    if gate_stale:
        item_id = add_open_item(
            open_items,
            "GATE_DECISION_STALE",
            "Gate decision is older than the validation report.",
            severity="P0",
            source="run_state.gates",
            target_objects={"gate_decision": state.get("gates", {}).get("gate_decision", {}), "validation_report": state.get("gates", {}).get("validation_report", {})},
        )
        make_candidate(
            candidates,
            action_types,
            action_type="ACT_GATE_REVIEW",
            priority="P0",
            status="ready",
            reason="Validation changed after gate approval, so a fresh gate review is required.",
            target_objects={"gate_decision": state.get("gates", {}).get("gate_decision", {})},
            open_item_ids=[item_id],
            preconditions={"validation_report_current": True, "gate_decision_stale": True},
            expected_effects={"writes": ["knowledge/gate_reviews/oag_gate_decision.json", "knowledge/subagents/*"], "creates": ["gate_decision"]},
            command="python3 .codex/scripts/oag_review_frame.py --ip-dir <ip> --mode gate --json",
            mission_template=mission_id,
        )

    mission_priority = {aid: idx for idx, aid in enumerate(missions.get(mission_id, {}).get("action_priority", []))}
    open_items_by_id = {str(item.get("id") or ""): item for item in open_items}
    for candidate in candidates:
        candidate["score"] = score_candidate(candidate, open_items_by_id, mission_priority, role_health_rows)
    candidates.sort(
        key=lambda item: (
            -int(item.get("score", {}).get("total", 0) if isinstance(item.get("score"), dict) else 0),
            PRIORITY_RANK.get(item.get("priority"), 99),
            STATUS_RANK.get(item.get("status"), 99),
            mission_priority.get(item.get("action_type"), 999),
            item.get("id", ""),
        )
    )
    if candidates:
        candidates[0]["recommended"] = True
    for item in candidates[1:]:
        item["recommended"] = False

    dependency_graph = build_dependency_graph(candidates, mission_id, mission_priority)
    dependency_graph["ip"] = ip_dir.name

    payload: JsonObject = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": run_common.utc_now(),
        "ip": ip_dir.name,
        "ip_dir": str(ip_dir),
        "mission_template": mission_id,
        "mission_known": mission_id in missions,
        "open_items": open_items,
        "candidates": candidates,
        "dependency_graph_summary": dependency_graph.get("summary", {}),
        "stuck_actions": stuck_actions,
        "role_health": role_health,
        "checker_results": checker_results,
        "catalog_issues": catalog_issues + mission_issues,
        "state_summary": {
            "scope_lock": state.get("scope_lock", {}).get("state"),
            "compile_manifest": compile_status,
            "active_lock_count": state.get("wavefront", {}).get("active_lock_count", 0),
            "pending_gate_count": state.get("gates", {}).get("pending_gate_count", 0),
            "ssot_status": ssot.get("status"),
            "gate_decision_stale": gate_stale,
        },
    }
    schema_issues = contextual_schema_issues(
        "oag_action_candidates.schema.json",
        payload,
        code_prefix="ACTION_CANDIDATES_SCHEMA",
        document_path="ontology/generated/action_candidates.json",
    )
    payload["schema_issues"] = schema_issues

    output_path = oag_paths.generated_path(ip_dir, "action_candidates.json")
    graph_path = oag_paths.generated_path(ip_dir, "action_graph.json")
    mission_instance_id = ""
    mission_path = ""
    if write:
        oag_role_health.write_role_health(ip_dir, role_health)
        if not catalog_issues and not mission_issues and not schema_issues:
            mission = oag_mission_runtime.ensure_mission_instance(ip_dir, mission_id, plan_payload=payload, actor="oag_action_plan")
            mission_instance_id = str(mission.get("id") or "")
            mission_path = run_common.rel_to_ip(ip_dir, mission.get("_path", oag_mission_runtime.mission_path(ip_dir, mission_instance_id)))
            payload["mission_instance_id"] = mission_instance_id
            dependency_graph["mission_instance_id"] = mission_instance_id
        run_common.write_json(output_path, payload)
        graph_issues = contextual_schema_issues(
            "oag_action_graph.schema.json",
            dependency_graph,
            code_prefix="ACTION_GRAPH_SCHEMA",
            document_path="ontology/generated/action_graph.json",
        )
        dependency_graph["schema_issues"] = graph_issues
        run_common.write_json(graph_path, dependency_graph)
    else:
        graph_issues = []
    return {
        "schema_version": RESULT_SCHEMA_VERSION,
        "status": "fail" if catalog_issues or mission_issues or schema_issues or graph_issues else "pass",
        "ip": ip_dir.name,
        "mission_template": mission_id,
        "mission_instance_id": mission_instance_id,
        "mission_path": mission_path,
        "output_path": run_common.rel_to_ip(ip_dir, output_path),
        "action_graph_path": run_common.rel_to_ip(ip_dir, graph_path),
        "written": write,
        "candidate_count": len(candidates),
        "open_item_count": len(open_items),
        "recommended_action": next((item for item in candidates if item.get("recommended")), candidates[0] if candidates else {}),
        "dependency_graph": dependency_graph,
        "issues": catalog_issues + mission_issues + schema_issues + graph_issues,
        "plan": payload,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ip-dir", required=True)
    parser.add_argument("--mission-template", default="")
    parser.add_argument("--no-write", action="store_true")
    parser.add_argument("--quick", action="store_true", help="Skip semantic checker calls and use run-state only.")
    parser.add_argument("--stuck-seconds", type=int, default=900)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    result = build_plan(Path(args.ip_dir), mission_template=args.mission_template, write=not args.no_write, run_semantic_checks=not args.quick, stuck_seconds=args.stuck_seconds)
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    elif result["status"] == "pass":
        rec = result.get("recommended_action") or {}
        print(f"PASS {RESULT_SCHEMA_VERSION}: {result['candidate_count']} candidates, recommended={rec.get('action_type', 'none')}")
        if result.get("written"):
            print(f"Wrote {result['output_path']}")
    else:
        print(f"FAIL {RESULT_SCHEMA_VERSION}", file=sys.stderr)
        for item in result.get("issues", []):
            print(f"- {item.get('code')}: {item.get('message')}", file=sys.stderr)
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
