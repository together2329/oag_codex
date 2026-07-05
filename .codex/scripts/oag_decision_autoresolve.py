#!/usr/bin/env python3
# noqa: SIZE_OK - OAG CLI policy, receipt, and row update stay together for auditability.
from __future__ import annotations

import argparse
import importlib
import json
import sys
from pathlib import Path
from typing import Any

scripts_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(scripts_dir))
oag_action_plan = importlib.import_module("oag_action_plan")
oag_paths = importlib.import_module("oag_paths")
run_common = importlib.import_module("oag_run_control_common")


POLICY_SCHEMA = "oag_decision_autoresolve_policy.v1"
RESULT_SCHEMA = "oag_decision_autoresolve_result.v1"
RECEIPT_SCHEMA = "oag_agent_decision_receipt.v1"
DECISION_CLASSES = {"fact", "parameterizable", "architecture_tradeoff", "product_defining"}
AUTONOMY_CLASSES = {"fact", "reversible_internal", "measured_tradeoff", "external_contract"}
RESOLUTION_STRATEGIES = {
    "cite",
    "parameterize",
    "generate_option",
    "measure_and_select",
    "parameterized_default",
    "defer",
    "ask",
}
REPRESENTATIONS = {"truth", "parameter", "generate_option"}
EXTERNAL_CONTRACT_IMPACTS = {"none", "indirect", "direct"}

JsonObject = dict[str, Any]


def read_yaml(path: Path) -> JsonObject:
    if not path.is_file():
        return {}
    try:
        import yaml  # type: ignore

        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        return data if isinstance(data, dict) else {}
    except Exception as exc:
        return {"__load_error__": str(exc)}


def write_yaml(path: Path, data: JsonObject) -> None:
    import yaml  # type: ignore

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")


def as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def text(value: Any) -> str:
    return str(value or "").strip()


def decision_matrix_path(ip_dir: Path) -> Path:
    return oag_paths.legacy_or_hidden(ip_dir, "ontology/decision_matrix.yaml")


def mission_charter_path(ip_dir: Path) -> Path:
    return oag_paths.legacy_or_hidden(ip_dir, "ontology/mission_charter.yaml")


def receipt_path(ip_dir: Path, decision_id: str) -> Path:
    safe = "".join(char if char.isalnum() or char in {"_", "-", "."} else "_" for char in decision_id)
    return oag_paths.state_path(ip_dir, f"knowledge/decisions/{safe}.json")


def load_decision_rows(ip_dir: Path) -> list[JsonObject]:
    matrix = read_yaml(decision_matrix_path(ip_dir))
    return [item for item in as_list(matrix.get("decisions")) if isinstance(item, dict)]


def decision_row_by_id(ip_dir: Path, decision_id: str) -> JsonObject:
    for row in load_decision_rows(ip_dir):
        if text(row.get("id")) == decision_id:
            return row
    return {}


def decision_class(row: JsonObject) -> str:
    raw = text(row.get("decision_class")).lower()
    return raw if raw in DECISION_CLASSES else "product_defining"


def autonomy_class(row: JsonObject) -> str:
    raw = text(row.get("autonomy_class")).lower()
    if raw in AUTONOMY_CLASSES:
        return raw
    row_class = decision_class(row)
    if row_class in DECISION_CLASSES:
        return legacy_autonomy_class(row_class)
    return "external_contract"


def resolution_strategy(row: JsonObject) -> str:
    raw = text(row.get("resolution_strategy")).lower()
    return raw if raw in RESOLUTION_STRATEGIES else "ask"


def representation(row: JsonObject) -> str:
    raw = text(row.get("representation")).lower()
    return raw if raw in REPRESENTATIONS else "truth"


def external_contract_impact(row: JsonObject) -> str:
    raw = text(row.get("external_contract_impact")).lower()
    return raw if raw in EXTERNAL_CONTRACT_IMPACTS else "none"


def target_decision_ids(candidate: JsonObject) -> list[str]:
    target_objects_raw = candidate.get("target_objects")
    target_objects: JsonObject = target_objects_raw if isinstance(target_objects_raw, dict) else {}
    return [text(item) for item in as_list(target_objects.get("decisions")) if text(item)]


def charter_approved(charter: JsonObject) -> bool:
    approval_raw = charter.get("approval")
    approval: JsonObject = approval_raw if isinstance(approval_raw, dict) else {}
    charter_status = text(charter.get("status")).lower()
    approval_status = text(approval.get("status")).lower()
    approved = (
        charter.get("approved") is True
        or charter_status == "approved"
        or approval.get("approved") is True
        or approval_status == "approved"
    )
    if text(charter.get("schema_version")) != "oag_mission_charter.v1":
        return approved
    actor_raw = approval.get("actor")
    actor: JsonObject = actor_raw if isinstance(actor_raw, dict) else {}
    return (
        approved
        and charter_status == "approved"
        and charter.get("approved") is True
        and approval_status == "approved"
        and approval.get("approved") is True
        and text(actor.get("kind")).lower() == "human"
    )


def charter_question_batching(charter: JsonObject) -> str:
    autonomy_raw = charter.get("autonomy")
    autonomy: JsonObject = autonomy_raw if isinstance(autonomy_raw, dict) else {}
    question_policy_raw = charter.get("question_policy")
    question_policy: JsonObject = question_policy_raw if isinstance(question_policy_raw, dict) else {}
    return text(charter.get("question_batching") or question_policy.get("batching") or autonomy.get("question_batching")).lower()


def _grant_rows(charter: JsonObject) -> list[JsonObject]:
    autonomy_raw = charter.get("autonomy")
    autonomy: JsonObject = autonomy_raw if isinstance(autonomy_raw, dict) else {}
    grants = [item for item in as_list(charter.get("autonomy_grants")) if isinstance(item, dict)]
    grants.extend(item for item in as_list(autonomy.get("grants")) if isinstance(item, dict))
    class_map_raw = autonomy.get("decision_classes")
    class_map: JsonObject = class_map_raw if isinstance(class_map_raw, dict) else {}
    for key, value in class_map.items():
        if isinstance(value, dict):
            grants.append({"decision_class": key, **value})
        elif value is True:
            grants.append({"decision_class": key, "granted": True})
    return grants


def charter_grant_for_class(charter: JsonObject, row_class: str) -> JsonObject:
    if row_class == "product_defining":
        return {}
    if not charter_approved(charter):
        return {}
    for grant in _grant_rows(charter):
        granted_class = text(grant.get("decision_class") or grant.get("class")).lower()
        if granted_class != row_class:
            continue
        grant_status = text(grant.get("status")).lower()
        if grant.get("granted") is False or grant_status in {"denied", "draft", "pending", "proposed", "rejected", "revoked"}:
            continue
        if grant.get("granted") is True or grant_status == "approved":
            return grant
    return {}


def charter_grant_for_autonomy(charter: JsonObject, row_autonomy: str) -> JsonObject:
    if row_autonomy == "external_contract":
        return {}
    if not charter_approved(charter):
        return {}
    for grant in _grant_rows(charter):
        granted_autonomy = text(grant.get("autonomy_class")).lower()
        legacy_class = text(grant.get("decision_class") or grant.get("class")).lower()
        if granted_autonomy:
            if granted_autonomy != row_autonomy:
                continue
        elif legacy_class:
            if row_autonomy != legacy_autonomy_class(legacy_class):
                continue
        else:
            continue
        grant_status = text(grant.get("status")).lower()
        if grant.get("granted") is False or grant_status in {"denied", "draft", "pending", "proposed", "rejected", "revoked"}:
            continue
        if grant.get("granted") is True or grant_status == "approved":
            return grant
    return {}


def legacy_autonomy_class(row_class: str) -> str:
    if row_class == "fact":
        return "fact"
    if row_class == "parameterizable":
        return "reversible_internal"
    if row_class == "architecture_tradeoff":
        return "measured_tradeoff"
    return "external_contract"


def has_fact_citation(ip_dir: Path, row: JsonObject) -> bool:
    refs = [text(item) for item in as_list(row.get("refs")) + as_list(row.get("evidence_refs")) if text(item)]
    if not refs:
        return False
    return any(oag_paths.legacy_or_hidden(ip_dir, ref.split("#", maxsplit=1)[0]).exists() for ref in refs)


def evidence_required_refs(row: JsonObject) -> list[str]:
    refs: list[str] = []
    for item in as_list(row.get("evidence_required")):
        if isinstance(item, str) and text(item):
            refs.append(text(item))
        elif isinstance(item, dict):
            ref = text(item.get("path") or item.get("ref") or item.get("artifact") or item.get("artifact_path"))
            if ref:
                refs.append(ref)
    return refs


def evidence_available(ip_dir: Path, row: JsonObject) -> bool:
    required = evidence_required_refs(row)
    refs = [text(item) for item in as_list(row.get("evidence_refs")) + as_list(row.get("refs")) if text(item)]
    if required:
        refs_set = set(refs)
        return all(ref in refs_set and oag_paths.legacy_or_hidden(ip_dir, ref.split("#", maxsplit=1)[0]).exists() for ref in required)
    return bool(refs) and all(oag_paths.legacy_or_hidden(ip_dir, ref.split("#", maxsplit=1)[0]).exists() for ref in refs)


def resolve_candidate_policy(ip_dir: Path, candidate: JsonObject) -> JsonObject:
    ip_dir = oag_paths.ip_root(ip_dir)
    decision_ids = target_decision_ids(candidate)
    if not decision_ids:
        return {
            "schema_version": POLICY_SCHEMA,
            "decision": "needs_user",
            "reason": "human_input_required",
            "decision_class": "product_defining",
            "autonomy_class": "external_contract",
            "resolution_strategy": "ask",
            "representation": "truth",
            "external_contract_impact": "direct",
            "decision_id": "",
            "charter_grant_id": "",
        }
    decision_id = decision_ids[0]
    row = decision_row_by_id(ip_dir, decision_id)
    row_class = decision_class(row)
    row_autonomy = autonomy_class(row)
    row_strategy = resolution_strategy(row)
    row_representation = representation(row)
    row_impact = external_contract_impact(row)
    charter = read_yaml(mission_charter_path(ip_dir))
    grant = {} if row_impact == "direct" else charter_grant_for_autonomy(charter, row_autonomy)
    grant_id = text(grant.get("id"))

    if row_impact == "direct":
        decision = "defer_question" if charter_approved(charter) and charter_question_batching(charter) == "checkpoint" else "needs_user"
        reason = "external_contract_direct_requires_human_checkpoint"
    elif row_autonomy == "fact" and has_fact_citation(ip_dir, row):
        decision = "auto_decide"
        reason = "fact_decision_has_local_citation"
    elif (row_class == "parameterizable" or row_strategy in {"parameterize", "parameterized_default"}) and grant:
        decision = "auto_decide"
        reason = "parameterizable_decision_promoted_to_parameter_policy"
    elif row_autonomy == "reversible_internal" and grant:
        decision = "auto_decide"
        reason = "reversible_internal_granted_by_charter"
    elif row_autonomy == "measured_tradeoff" and grant and evidence_available(ip_dir, row):
        decision = "auto_decide"
        reason = "measured_tradeoff_evidence_satisfies_selection_rule"
    elif row_autonomy == "measured_tradeoff" and grant:
        decision = "route_dse"
        reason = "measured_tradeoff_granted_requires_measurement"
    elif row_autonomy == "external_contract" and charter_approved(charter) and charter_question_batching(charter) == "checkpoint":
        decision = "defer_question"
        reason = "product_defining_question_batched_to_checkpoint" if row_class == "product_defining" else "external_contract_question_batched_to_checkpoint"
    else:
        decision = "needs_user"
        reason = "human_input_required"

    return {
        "schema_version": POLICY_SCHEMA,
        "decision": decision,
        "reason": reason,
        "decision_class": row_class,
        "autonomy_class": row_autonomy,
        "resolution_strategy": row_strategy,
        "representation": row_representation,
        "external_contract_impact": row_impact,
        "decision_id": decision_id,
        "charter_grant_id": grant_id,
        "charter_path": "ontology/mission_charter.yaml" if charter else "",
        "evidence_plan": {
            "required": row_autonomy in {"fact", "measured_tradeoff"} or bool(evidence_required_refs(row)),
            "required_refs": evidence_required_refs(row),
            "available_refs": [text(item) for item in as_list(row.get("evidence_refs")) + as_list(row.get("refs")) if text(item)],
        },
    }


def parse_json_value(value: str) -> Any:
    if not value:
        return ""
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value


def parse_key_values(values: list[str]) -> JsonObject:
    parsed: JsonObject = {}
    for value in values:
        key, sep, raw = value.partition("=")
        if sep and text(key):
            parsed[text(key)] = parse_json_value(raw)
    return parsed


def selected_autonomy_class(args: argparse.Namespace, row: JsonObject) -> str:
    raw = text(args.autonomy_class or row.get("autonomy_class")).lower()
    return raw if raw in AUTONOMY_CLASSES else autonomy_class(row)


def selected_resolution_strategy(args: argparse.Namespace, row: JsonObject) -> str:
    raw = text(args.resolution_strategy or row.get("resolution_strategy")).lower()
    return raw if raw in RESOLUTION_STRATEGIES else resolution_strategy(row)


def selected_representation(args: argparse.Namespace, row: JsonObject) -> str:
    raw = text(args.representation or row.get("representation")).lower()
    return raw if raw in REPRESENTATIONS else representation(row)


def selected_external_contract_impact(args: argparse.Namespace, row: JsonObject) -> str:
    raw = text(args.external_contract_impact or row.get("external_contract_impact")).lower()
    return raw if raw in EXTERNAL_CONTRACT_IMPACTS else external_contract_impact(row)


def selected_candidate_values(args: argparse.Namespace, row: JsonObject) -> list[Any]:
    values: list[Any] = []
    row_values = row.get("candidate_values")
    if isinstance(row_values, list):
        values.extend(row_values)
    if text(args.candidate_values):
        parsed = parse_json_value(text(args.candidate_values))
        values.extend(parsed if isinstance(parsed, list) else [parsed])
    values.extend(parse_json_value(text(item)) for item in args.candidate_value if text(item))
    return values


def selected_evidence_required(args: argparse.Namespace, row: JsonObject) -> list[Any]:
    values = list(as_list(row.get("evidence_required")))
    values.extend(text(item) for item in args.evidence_required if text(item))
    return values


def missing_required_evidence(ip_dir: Path, required: list[Any], evidence_refs: list[str]) -> list[str]:
    required_refs = evidence_required_refs({"evidence_required": required})
    evidence_set = set(evidence_refs)
    missing: list[str] = []
    for ref in required_refs:
        if ref not in evidence_set or not oag_paths.legacy_or_hidden(ip_dir, ref.split("#", maxsplit=1)[0]).exists():
            missing.append(ref)
    return missing


def resolve_decision(args: argparse.Namespace) -> JsonObject:
    ip_dir = oag_paths.ip_root(args.ip_dir)
    matrix_path = decision_matrix_path(ip_dir)
    matrix = read_yaml(matrix_path)
    if matrix.get("__load_error__"):
        return {"schema_version": RESULT_SCHEMA, "status": "fail", "issues": [{"code": "DECISION_MATRIX_INVALID", "message": matrix["__load_error__"]}]}
    rows = [item for item in as_list(matrix.get("decisions")) if isinstance(item, dict)]
    row = next((item for item in rows if text(item.get("id")) == args.decision_id), None)
    if row is None:
        return {"schema_version": RESULT_SCHEMA, "status": "fail", "issues": [{"code": "DECISION_NOT_FOUND", "message": f"decision not found: {args.decision_id}"}]}
    row_class = text(args.decision_class or row.get("decision_class")).lower()
    row_class = row_class if row_class in DECISION_CLASSES else "product_defining"
    row_autonomy = selected_autonomy_class(args, row)
    row_strategy = selected_resolution_strategy(args, row)
    row_representation = selected_representation(args, row)
    row_impact = selected_external_contract_impact(args, row)
    if row_class == "product_defining":
        return {"schema_version": RESULT_SCHEMA, "status": "fail", "issues": [{"code": "PRODUCT_DEFINING_REFUSED", "message": "product_defining decisions require human review"}]}
    if row_autonomy == "external_contract":
        return {"schema_version": RESULT_SCHEMA, "status": "fail", "issues": [{"code": "EXTERNAL_CONTRACT_REFUSED", "message": "external_contract autonomy requires human review"}]}
    if row_impact == "direct":
        return {"schema_version": RESULT_SCHEMA, "status": "fail", "issues": [{"code": "DIRECT_EXTERNAL_CONTRACT_IMPACT", "message": "external_contract_impact direct requires checkpoint/user review"}]}
    evidence_refs = [text(item) for item in args.evidence if text(item)]
    missing = [ref for ref in evidence_refs if not oag_paths.legacy_or_hidden(ip_dir, ref.split("#", maxsplit=1)[0]).exists()]
    if missing:
        return {"schema_version": RESULT_SCHEMA, "status": "fail", "issues": [{"code": "EVIDENCE_MISSING", "message": ", ".join(missing)}]}
    charter = read_yaml(mission_charter_path(ip_dir))
    grant = charter_grant_for_autonomy(charter, row_autonomy)
    if row_autonomy in {"reversible_internal", "measured_tradeoff"} and not grant:
        return {"schema_version": RESULT_SCHEMA, "status": "fail", "issues": [{"code": "CHARTER_GRANT_MISSING", "message": f"{row_autonomy} requires an approved charter grant"}]}
    evidence_required = selected_evidence_required(args, row)
    missing_required = missing_required_evidence(ip_dir, evidence_required, evidence_refs)
    if missing_required:
        return {"schema_version": RESULT_SCHEMA, "status": "fail", "issues": [{"code": "EVIDENCE_REQUIRED_UNSATISFIED", "message": ", ".join(missing_required)}]}

    candidate_values = selected_candidate_values(args, row)
    artifact_paths = [text(item) for item in args.artifact_path if text(item)]
    artifact_paths.extend(evidence_refs)
    receipt = {
        "schema_version": RECEIPT_SCHEMA,
        "id": text(args.receipt_id) or text(args.decision_id),
        "ip": ip_dir.name,
        "decision_id": text(args.decision_id),
        "decision_class": row_class,
        "autonomy_class": row_autonomy,
        "resolution_strategy": row_strategy,
        "representation": row_representation,
        "external_contract_impact": row_impact,
        "decision": text(args.decision),
        "provisional": not args.final,
        "charter_grant_id": text(args.charter_grant) or text(grant.get("id")),
        "evidence_refs": evidence_refs,
        "evidence_required": evidence_required,
        "rollback_cost": row.get("rollback_cost") if row.get("rollback_cost") is not None else parse_json_value(text(args.rollback_cost)),
        "candidate_values": candidate_values,
        "candidate_set": candidate_values,
        "bench_command": text(args.bench_command),
        "metrics": parse_key_values(args.metric),
        "comparison": parse_json_value(text(args.comparison)),
        "selection_rule": parse_json_value(text(args.selection_rule or row.get("selection_rule"))),
        "artifact_paths": artifact_paths,
        "rollback_path": text(args.rollback_path),
        "rationale": text(args.rationale),
        "actor": {"kind": "ai", "id": "oag_decision_autoresolve", "surface": "cli"},
        "created_at": run_common.utc_now(),
    }
    out_path = receipt_path(ip_dir, text(args.decision_id))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    row.update(
        {
            "status": "decided",
            "decision": text(args.decision),
            "decision_class": row_class,
            "autonomy_class": row_autonomy,
            "resolution_strategy": row_strategy,
            "representation": row_representation,
            "external_contract_impact": row_impact,
            "decided_by": {
                "kind": "agent_with_charter" if row_autonomy in {"reversible_internal", "measured_tradeoff"} else "agent_with_evidence",
                "id": "oag_decision_autoresolve",
                "charter_ref": f"ontology/mission_charter.yaml#{receipt['charter_grant_id']}" if receipt["charter_grant_id"] else "",
            },
            "provisional": not args.final,
            "evidence_refs": evidence_refs,
            "evidence_required": evidence_required,
            "decision_receipt_ref": run_common.rel_to_ip(ip_dir, out_path),
            "rationale": text(args.rationale) or text(row.get("rationale")),
        }
    )
    matrix["decisions"] = rows
    write_yaml(matrix_path, matrix)
    action_plan = oag_action_plan.build_plan(ip_dir, write=True, run_semantic_checks=False)
    return {
        "schema_version": RESULT_SCHEMA,
        "status": "pass",
        "ip": ip_dir.name,
        "decision_id": text(args.decision_id),
        "decision_class": row_class,
        "autonomy_class": row_autonomy,
        "resolution_strategy": row_strategy,
        "representation": row_representation,
        "external_contract_impact": row_impact,
        "decision_receipt": run_common.rel_to_ip(ip_dir, out_path),
        "decision_matrix": run_common.rel_to_ip(ip_dir, matrix_path),
        "action_plan_status": action_plan.get("status") or "",
        "issues": [],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ip-dir", required=True)
    parser.add_argument("--decision-id", required=True)
    parser.add_argument("--decision", required=True)
    parser.add_argument("--decision-class", choices=sorted(DECISION_CLASSES), default="")
    parser.add_argument("--autonomy-class", choices=sorted(AUTONOMY_CLASSES), default="")
    parser.add_argument("--resolution-strategy", choices=sorted(RESOLUTION_STRATEGIES), default="")
    parser.add_argument("--representation", choices=sorted(REPRESENTATIONS), default="")
    parser.add_argument("--external-contract-impact", choices=sorted(EXTERNAL_CONTRACT_IMPACTS), default="")
    parser.add_argument("--evidence", action="append", default=[])
    parser.add_argument("--evidence-required", action="append", default=[])
    parser.add_argument("--charter-grant", default="")
    parser.add_argument("--receipt-id", default="")
    parser.add_argument("--rationale", default="")
    parser.add_argument("--candidate-value", action="append", default=[])
    parser.add_argument("--candidate-values", default="")
    parser.add_argument("--selection-rule", default="")
    parser.add_argument("--bench-command", default="")
    parser.add_argument("--metric", action="append", default=[])
    parser.add_argument("--comparison", default="")
    parser.add_argument("--artifact-path", action="append", default=[])
    parser.add_argument("--rollback-cost", default="")
    parser.add_argument("--rollback-path", default="")
    parser.add_argument("--final", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    payload = resolve_decision(args)
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    elif payload.get("status") == "pass":
        print(f"PASS {RESULT_SCHEMA}: {payload.get('decision_id')}")
    else:
        print(f"FAIL {RESULT_SCHEMA}", file=sys.stderr)
        for item in payload.get("issues", []):
            print(f"- {item.get('code')}: {item.get('message')}", file=sys.stderr)
    return 0 if payload.get("status") == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
