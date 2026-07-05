#!/usr/bin/env python3
"""Build a bounded ask-versus-explore plan for OAG Mission Loop work."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import oag_action_plan  # noqa: E402
import oag_decision_autoresolve  # noqa: E402
import oag_paths  # noqa: E402
import oag_run_control_common as run_common  # noqa: E402
from oag_validate_json import contextual_schema_issues  # noqa: E402


SCHEMA_VERSION = "oag_exploration_plan.v1"
RESULT_SCHEMA = "oag_exploration_plan_result.v1"

HUMAN_ACTION_TYPES = {
    "ACT_ASK_DEEP_INTERVIEW_QUESTION",
    "ACT_RESOLVE_DECISION",
    "ACT_RESOLVE_PENDING_GATE",
    "ACT_LOCK_SCOPE",
    "ACT_CUSTOM_OPERATOR_INPUT",
}

LOCK_CRITICAL_ACTION_TYPES = {
    "ACT_ASK_DEEP_INTERVIEW_QUESTION",
    "ACT_RESOLVE_DECISION",
    "ACT_LOCK_SCOPE",
}

SOURCE_HINTS = {
    "req/source_claims.yaml": "User/spec claims already captured by OAG.",
    "req/ambiguity_register.yaml": "Known ambiguity rows and lock blockers.",
    "req/deep_semantic_intake": "Source-claim decomposition and hidden implications.",
    "doc": "Imported specifications, TRMs, diagrams, or design notes.",
    "rtl": "Existing implementation facts for brownfield or repair work.",
    "ontology/decision_matrix.yaml": "Open decisions, recommendations, and lock requirements.",
    "ontology/features.yaml": "Feature boundaries and feature IDs.",
    "ontology/ipxact_projection.yaml": "IP-XACT-style interface, register, parameter, and fileset intent.",
    "ontology/requirements.yaml": "Current requirements.",
    "ontology/requirement_atoms.yaml": "Atomic requirement decomposition.",
    "ontology/obligations.yaml": "Owned proof/implementation responsibilities.",
    "ontology/contracts.yaml": "Assume/guarantee behavior and proof refs.",
    "ontology/verification_plan.yaml": "Scenario, scoreboard, and coverage intent.",
}

OPTION_AXES = [
    {
        "id": "AXIS_FUNCTIONAL_FEATURE",
        "label": "Functional Feature",
        "why": "Product-defining behavior must be explicit before RTL can be locked.",
    },
    {
        "id": "AXIS_INTERFACE_INTEGRATION",
        "label": "Interface and Integration",
        "why": "IP-XACT-style ports, bus bindings, registers, memory maps, and parameters drive tool integration.",
    },
    {
        "id": "AXIS_ARCHITECTURE_PARTITION",
        "label": "Architecture Partition",
        "why": "Module boundaries, state ownership, queues, arbiters, and datapaths determine implementation risk.",
    },
    {
        "id": "AXIS_PERFORMANCE_PPA",
        "label": "Performance and PPA",
        "why": "Throughput, latency, area, power, timing, and configurability decide whether a feature is practical.",
    },
    {
        "id": "AXIS_VERIFICATION_EVIDENCE",
        "label": "Verification Evidence",
        "why": "A decision is RTL-ready only when it can map to scenarios, scoreboard rows, assertions, or coverage.",
    },
]


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


def output_path(ip_dir: Path) -> Path:
    return oag_paths.state_path(ip_dir, "knowledge/mission_loop/exploration_plan.json")


def generated_action_plan(ip_dir: Path) -> JsonObject:
    path = oag_paths.generated_path(ip_dir, "action_candidates.json")
    return read_json(path)


def recommended_candidate(plan: JsonObject) -> JsonObject:
    candidates = [item for item in plan.get("candidates", []) if isinstance(item, dict)]
    return next((item for item in candidates if item.get("recommended") is True), candidates[0] if candidates else {})


def _source_target(ip_dir: Path, rel_path: str) -> JsonObject:
    path = oag_paths.legacy_or_hidden(ip_dir, rel_path)
    row: JsonObject = {
        "path": rel_path,
        "hint": SOURCE_HINTS.get(rel_path, "OAG local source."),
        "exists": False,
        "kind": "missing",
        "bytes": 0,
        "sha256": "",
        "sample_files": [],
    }
    if path.is_file():
        row.update(
            {
                "path": run_common.rel_to_ip(ip_dir, path),
                "exists": True,
                "kind": "file",
                "bytes": path.stat().st_size,
                "sha256": run_common.sha256_file(path),
            }
        )
    elif path.is_dir():
        sample = []
        total_bytes = 0
        for child in sorted(item for item in path.rglob("*") if item.is_file())[:24]:
            size = child.stat().st_size
            total_bytes += size
            sample.append({"path": run_common.rel_to_ip(ip_dir, child), "bytes": size})
        row.update(
            {
                "path": run_common.rel_to_ip(ip_dir, path),
                "exists": True,
                "kind": "directory",
                "bytes": total_bytes,
                "sample_files": sample,
            }
        )
    return row


def infer_decision(ip_dir: Path, candidate: JsonObject, source_targets: list[JsonObject]) -> JsonObject:
    action_type = str(candidate.get("action_type") or "")
    owner_role = str(candidate.get("owner_role") or "")
    local_sources_available = any(item.get("exists") is True for item in source_targets)
    lock_critical = action_type in LOCK_CRITICAL_ACTION_TYPES

    if not action_type:
        return {
            "decision": "idle",
            "reason": "No recommended Action candidate is available.",
            "question_required_now": False,
            "lock_critical": False,
            "local_sources_available": local_sources_available,
        }
    if action_type == "ACT_SELF_EXPLORE_OPTIONS":
        return {
            "decision": "self_explore",
            "reason": "The recommended Action is to inspect local sources before asking the user.",
            "question_required_now": False,
            "lock_critical": False,
            "local_sources_available": local_sources_available,
        }
    if action_type in HUMAN_ACTION_TYPES or owner_role == "human_via_main":
        policy = oag_decision_autoresolve.resolve_candidate_policy(ip_dir, candidate)
        policy_decision = str(policy.get("decision") or "")
        if policy_decision in {"auto_decide", "route_dse"}:
            return {
                "decision": "auto_decide",
                "reason": str(policy.get("reason") or "charter_autonomy_policy"),
                "question_required_now": False,
                "lock_critical": lock_critical,
                "local_sources_available": local_sources_available,
                "decision_class": policy.get("decision_class") or "",
                "decision_id": policy.get("decision_id") or "",
                "charter_grant_id": policy.get("charter_grant_id") or "",
                "evidence_plan": policy.get("evidence_plan") if isinstance(policy.get("evidence_plan"), dict) else {},
            }
        if local_sources_available:
            return {
                "decision": "self_explore",
                "reason": "A user question is likely, but local sources exist and must be mined first.",
                "question_required_now": False,
                "lock_critical": lock_critical,
                "local_sources_available": True,
            }
        return {
            "decision": "ask_user",
            "reason": "No useful local source was found; ask the smallest lock-reducing question.",
            "question_required_now": True,
            "lock_critical": lock_critical,
            "local_sources_available": False,
        }
    return {
        "decision": "proceed_action",
        "reason": "The recommended Action is not a user-question boundary.",
        "question_required_now": False,
        "lock_critical": False,
        "local_sources_available": local_sources_available,
    }


def build_research_prompt(ip_dir: Path, candidate: JsonObject, ask_vs_explore: JsonObject, source_targets: list[JsonObject]) -> str:
    available = [item["path"] for item in source_targets if item.get("exists") is True]
    action_type = candidate.get("action_type") or "none"
    reason = candidate.get("recommendation_reason") or ""
    target_objects = candidate.get("target_objects") if isinstance(candidate.get("target_objects"), dict) else {}
    lines = [
        f"Act as the OAG self-exploration worker for IP `{ip_dir.name}`.",
        f"Recommended Action: {action_type}.",
        f"Reason: {reason}",
        f"Target objects: {json.dumps(target_objects, sort_keys=True)}",
        "Goal: answer from local spec/RTL/ontology first; ask the user only if the remaining point is product-defining or unsafe to infer.",
        "Inspect these available sources:",
    ]
    lines.extend(f"- {path}" for path in available[:24])
    lines.extend(
        [
            "Produce exactly four options when a choice remains, mark one Recommendation, and allow a custom answer.",
            "Classify each option by Functional Feature, Interface/Integration, Architecture Partition, Performance/PPA, and Verification Evidence.",
            "If the local sources answer the question, write the inferred answer plus citations and do not ask the user.",
            "If a residual question remains, ask exactly one question.",
        ]
    )
    if ask_vs_explore.get("lock_critical"):
        lines.append("Because the point is lock-critical, do not silently decide final product intent.")
    return "\n".join(lines)


def build_plan(ip_dir: Path, *, write: bool = True) -> JsonObject:
    ip_dir = oag_paths.ip_root(ip_dir)
    plan = generated_action_plan(ip_dir)
    candidate = recommended_candidate(plan)
    target_objects = candidate.get("target_objects") if isinstance(candidate.get("target_objects"), dict) else {}
    preconditions = candidate.get("preconditions") if isinstance(candidate.get("preconditions"), dict) else {}
    precomputed_fingerprint = str(preconditions.get("fingerprint") or "")
    if precomputed_fingerprint:
        fingerprint = {"sha256": precomputed_fingerprint, "source_count": len(oag_action_plan.SELF_EXPLORE_SOURCE_RELS)}
    else:
        fingerprint = oag_action_plan.self_explore_fingerprint(
            ip_dir,
            target_objects=target_objects,
            reason=str(candidate.get("recommendation_reason") or ""),
        )
    source_targets = [_source_target(ip_dir, rel_path) for rel_path in oag_action_plan.SELF_EXPLORE_SOURCE_RELS]
    ask_vs_explore = infer_decision(ip_dir, candidate, source_targets)
    payload: JsonObject = {
        "schema_version": SCHEMA_VERSION,
        "status": "pass",
        "generated_at": run_common.utc_now(),
        "ip": ip_dir.name,
        "candidate": {
            "id": candidate.get("id") or "",
            "action_type": candidate.get("action_type") or "",
            "owner_role": candidate.get("owner_role") or "",
            "priority": candidate.get("priority") or "",
            "reason": candidate.get("recommendation_reason") or "",
            "target_objects": target_objects,
        },
        "ask_vs_explore": ask_vs_explore,
        "input_fingerprint": {
            "sha256": fingerprint.get("sha256") or "",
            "source_count": fingerprint.get("source_count") or 0,
        },
        "source_targets": source_targets,
        "option_axes": OPTION_AXES,
        "research_prompt": build_research_prompt(ip_dir, candidate, ask_vs_explore, source_targets),
        "residual_question_policy": {
            "ask_one_question_only": True,
            "option_count": 4,
            "require_recommendation": True,
            "allow_custom_answer": True,
            "do_not_ask_for_repo_facts": True,
        },
        "issues": [],
    }
    schema_issues = contextual_schema_issues(
        "oag_exploration_plan.schema.json",
        payload,
        code_prefix="EXPLORATION_PLAN_SCHEMA",
        document_path="knowledge/mission_loop/exploration_plan.json",
    )
    if schema_issues:
        payload["status"] = "fail"
        payload["issues"] = schema_issues
    if write:
        run_common.write_json(output_path(ip_dir), payload)
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ip-dir", required=True)
    parser.add_argument("--no-write", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    payload = build_plan(Path(args.ip_dir), write=not args.no_write)
    result = {
        "schema_version": RESULT_SCHEMA,
        "status": payload.get("status"),
        "ip": payload.get("ip"),
        "output_path": run_common.rel_to_ip(oag_paths.ip_root(args.ip_dir), output_path(oag_paths.ip_root(args.ip_dir))),
        "written": not args.no_write,
        "plan": payload,
        "issues": payload.get("issues", []),
    }
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    elif result["status"] == "pass":
        print(f"PASS {RESULT_SCHEMA}: {payload.get('ask_vs_explore', {}).get('decision')}")
        if result["written"]:
            print(f"Wrote {result['output_path']}")
    else:
        print(f"FAIL {RESULT_SCHEMA}", file=sys.stderr)
        for item in result.get("issues", []):
            print(f"- {item.get('code')}: {item.get('message')}", file=sys.stderr)
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
