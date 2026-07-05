#!/usr/bin/env python3
# noqa: SIZE_OK - OAG readiness checker centralizes cross-gate diagnostics.
"""Check OAG decision matrix and post-lock requirement readiness."""

from __future__ import annotations

import argparse
import importlib
import json
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

oag_paths = importlib.import_module("oag_paths")
oag_requirement_atom_check = importlib.import_module("oag_requirement_atom_check")
oag_req_quality_check = importlib.import_module("oag_req_quality_check")
oag_verification_plan_check = importlib.import_module("oag_verification_plan_check")
oag_contract_strength_check = importlib.import_module("oag_contract_strength_check")
oag_trace_graph_check = importlib.import_module("oag_trace_graph_check")
oag_domain_crossing_check = importlib.import_module("oag_domain_crossing_check")
oag_decision_autoresolve = importlib.import_module("oag_decision_autoresolve")
oag_exploration_cleanup_check = importlib.import_module("oag_exploration_cleanup_check")
oag_decision_rtl_consistency_check = importlib.import_module("oag_decision_rtl_consistency_check")
contextual_schema_issues = importlib.import_module("oag_validate_json").contextual_schema_issues


LOCK_READY_STATUSES = {"decided", "waived"}
VALID_STATUSES = {"unresolved", "proposed", "decided", "waived", "blocked"}
DECISION_CLASSES = {"fact", "parameterizable", "architecture_tradeoff", "product_defining"}
AUTONOMY_CLASSES = {"fact", "reversible_internal", "measured_tradeoff", "external_contract"}
EXTERNAL_CONTRACT_IMPACTS = {"none", "indirect", "direct"}
TIER2_EVIDENCE_TIER = "tier2_probe"
TIER2_SCOPE_LOCK_BLOCKERS = {
    "scope_lock",
    "product_rtl_claim",
    "external_contract_claim",
    "product_defining_claim",
}


def read_yaml(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        import yaml  # type: ignore

        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        return data if isinstance(data, dict) else {}
    except Exception as exc:
        return {"__load_error__": str(exc)}


def read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception as exc:
        return {"__load_error__": str(exc)}


def as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def text(value: Any) -> str:
    return str(value or "").strip()


def issue(code: str, message: str, path: str = "") -> dict[str, str]:
    payload = {"code": code, "message": message}
    if path:
        payload["path"] = path
    return payload


def is_locked(ip_dir: Path) -> bool:
    scope = read_json(oag_paths.legacy_or_hidden(ip_dir, "ontology/scope_lock.json"))
    return scope.get("state") == "locked"


def has_value(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, dict)):
        return bool(value)
    return True


def autonomy_class(decision: dict[str, Any]) -> str:
    raw = text(decision.get("autonomy_class")).lower()
    return raw if raw in AUTONOMY_CLASSES else "external_contract"


def external_contract_impact(decision: dict[str, Any]) -> str:
    raw = text(decision.get("external_contract_impact")).lower()
    return raw if raw in EXTERNAL_CONTRACT_IMPACTS else "none"


def evidence_required_refs(decision: dict[str, Any]) -> list[str]:
    refs: list[str] = []
    for item in as_list(decision.get("evidence_required")):
        if isinstance(item, str) and text(item):
            refs.append(text(item))
        elif isinstance(item, dict):
            ref = text(item.get("path") or item.get("ref") or item.get("artifact") or item.get("artifact_path"))
            if ref:
                refs.append(ref)
    return refs


def evidence_refs(decision: dict[str, Any]) -> list[str]:
    return [text(item) for item in as_list(decision.get("evidence_refs")) if text(item)]


def evidence_doc(ip_dir: Path, ref: str) -> dict[str, Any]:
    path = oag_paths.legacy_or_hidden(ip_dir, ref.split("#", maxsplit=1)[0])
    return read_json(path)


def tier2_limited_evidence(doc: dict[str, Any]) -> bool:
    if not doc or doc.get("__load_error__"):
        return False
    tier = text(doc.get("evidence_tier")).lower()
    not_valid_for = {text(item).lower() for item in as_list(doc.get("not_valid_for")) if text(item)}
    return tier == TIER2_EVIDENCE_TIER or bool(not_valid_for & TIER2_SCOPE_LOCK_BLOCKERS)


def _tier2_lock_evidence_issues(
    ip_dir: Path,
    decision: dict[str, Any],
    *,
    hard_gate: bool,
    lock_required: bool,
    status: str,
    base: str,
    did: str,
) -> list[dict[str, str]]:
    if status != "decided":
        return []
    refs = evidence_refs(decision)
    if not refs:
        return []
    row_class = text(decision.get("decision_class")).lower()
    blocks_scope_lock = hard_gate and lock_required
    blocks_product_claim = row_class == "product_defining"
    blocks_external_contract = external_contract_impact(decision) == "direct"
    if not (blocks_scope_lock or blocks_product_claim or blocks_external_contract):
        return []
    docs = [evidence_doc(ip_dir, ref) for ref in refs]
    existing_docs = [doc for doc in docs if doc and not doc.get("__load_error__")]
    if existing_docs and all(tier2_limited_evidence(doc) for doc in existing_docs):
        return [
            issue(
                "DECISION_TIER2_ONLY_EVIDENCE",
                f"{did or base} cannot use only Tier-2 exploration probe/sweep evidence for scope-lock, product, or direct external-contract readiness.",
                base,
            )
        ]
    return []


def _evidence_requirement_issues(
    ip_dir: Path,
    decision: dict[str, Any],
    *,
    base: str,
    did: str,
) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    refs = evidence_refs(decision)
    evidence_set = set(refs)
    for ref in evidence_required_refs(decision):
        if ref not in evidence_set:
            issues.append(issue("DECISION_EVIDENCE_REQUIRED", f"{did or base} evidence_required is not resolved by evidence_refs: {ref}.", base))
        elif not oag_paths.legacy_or_hidden(ip_dir, ref.split("#", maxsplit=1)[0]).exists():
            issues.append(issue("DECISION_EVIDENCE_REQUIRED_MISSING", f"{did or base} required evidence does not exist: {ref}.", base))
    return issues


def _receipt_structural_issues(receipt_doc: dict[str, Any], *, base: str, did: str) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    required_fields = {
        "candidate_set": list,
        "bench_command": str,
        "metrics": dict,
        "comparison": (str, dict, list, int, float, bool, type(None)),
        "selection_rule": (str, dict, type(None)),
        "artifact_paths": list,
        "rollback_path": str,
    }
    for field, expected_type in required_fields.items():
        if field not in receipt_doc:
            issues.append(issue("DECISION_RECEIPT_FIELD", f"{did or base} receipt missing structured field {field}.", base))
        elif not isinstance(receipt_doc[field], expected_type):
            issues.append(issue("DECISION_RECEIPT_FIELD", f"{did or base} receipt field {field} has invalid type.", base))
    return issues


def _agent_decision_issues(
    ip_dir: Path,
    decision: dict[str, Any],
    *,
    base: str,
    did: str,
) -> tuple[list[dict[str, str]], dict[str, Any] | None]:
    decided_by_raw = decision.get("decided_by")
    decided_by: dict[str, Any] = decided_by_raw if isinstance(decided_by_raw, dict) else {}
    decided_by_kind = text(decided_by.get("kind")).lower()
    owner = text(decision.get("owner")).lower()
    agent_owned = owner in {"agent", "ai", "codex"} or owner.startswith("agent:")
    if not decided_by_kind.startswith("agent_") and not agent_owned:
        return [], None
    issues: list[dict[str, str]] = []
    if agent_owned and not decided_by_kind.startswith("agent_"):
        issues.append(issue("DECISION_AGENT_DECIDED_BY", f"{did or base} agent-owned decided rows require decided_by.kind agent_with_evidence or agent_with_charter.", base))
    raw_class = text(decision.get("decision_class")).lower()
    row_class = raw_class if raw_class in DECISION_CLASSES else "product_defining"
    row_autonomy = autonomy_class(decision)
    raw_autonomy = text(decision.get("autonomy_class")).lower()
    if raw_class not in DECISION_CLASSES:
        issues.append(issue("DECISION_CLASS", f"{did or base} has invalid decision_class {raw_class or '<missing>'}.", base))
    if raw_autonomy not in AUTONOMY_CLASSES:
        issues.append(issue("DECISION_AUTONOMY_CLASS", f"{did or base} has invalid autonomy_class {raw_autonomy or '<missing>'}; default is external_contract.", base))
    if row_class == "product_defining":
        issues.append(issue("DECISION_PRODUCT_AGENT", f"{did or base} product_defining decisions cannot be agent-decided.", base))
    if row_autonomy == "external_contract":
        issues.append(issue("DECISION_EXTERNAL_CONTRACT_AGENT", f"{did or base} external_contract autonomy cannot be agent-decided.", base))
    if external_contract_impact(decision) == "direct":
        issues.append(issue("DECISION_DIRECT_EXTERNAL_IMPACT", f"{did or base} external_contract_impact direct requires checkpoint/user review.", base))
    grant: dict[str, Any] = {}
    if decided_by_kind == "agent_with_charter":
        charter = oag_decision_autoresolve.read_yaml(oag_decision_autoresolve.mission_charter_path(ip_dir))
        grant = oag_decision_autoresolve.charter_grant_for_autonomy(charter, row_autonomy)
        if not grant:
            issues.append(issue("DECISION_CHARTER_GRANT", f"{did or base} agent decision lacks approved charter grant for {row_autonomy}.", base))

    refs = evidence_refs(decision)
    if not refs:
        issues.append(issue("DECISION_EVIDENCE_REFS", f"{did or base} agent decision requires evidence_refs.", base))
    for ref in refs:
        if not oag_paths.legacy_or_hidden(ip_dir, ref.split("#", maxsplit=1)[0]).exists():
            issues.append(issue("DECISION_EVIDENCE_MISSING", f"{did or base} evidence ref does not exist: {ref}.", base))

    receipt_ref = text(decision.get("decision_receipt_ref"))
    if not receipt_ref:
        issues.append(issue("DECISION_RECEIPT_REF", f"{did or base} agent decision requires decision_receipt_ref.", base))
        return issues, None
    receipt = oag_paths.legacy_or_hidden(ip_dir, receipt_ref)
    receipt_doc = read_json(receipt)
    if not receipt.is_file():
        issues.append(issue("DECISION_RECEIPT_MISSING", f"{did or base} agent decision receipt is missing: {receipt_ref}.", base))
    elif not receipt.read_text(encoding="utf-8").strip():
        issues.append(issue("DECISION_RECEIPT_EMPTY", f"{did or base} agent decision receipt is empty: {receipt_ref}.", base))
    elif receipt_doc.get("__load_error__"):
        issues.append(issue("DECISION_RECEIPT_INVALID", f"{did or base} agent decision receipt is invalid JSON: {receipt_ref}.", base))
    else:
        if text(receipt_doc.get("schema_version")) != "oag_agent_decision_receipt.v1":
            issues.append(issue("DECISION_RECEIPT_SCHEMA", f"{did or base} agent decision receipt has invalid schema_version.", base))
        if text(receipt_doc.get("decision_id")) != did:
            issues.append(issue("DECISION_RECEIPT_DECISION_ID", f"{did or base} agent decision receipt decision_id mismatch.", base))
        if text(receipt_doc.get("decision_class")).lower() != row_class:
            issues.append(issue("DECISION_RECEIPT_CLASS", f"{did or base} agent decision receipt decision_class mismatch.", base))
        if text(receipt_doc.get("autonomy_class")).lower() != row_autonomy:
            issues.append(issue("DECISION_RECEIPT_AUTONOMY_CLASS", f"{did or base} agent decision receipt autonomy_class mismatch.", base))
        issues.extend(_receipt_structural_issues(receipt_doc, base=base, did=did))

    if issues or decision.get("provisional") is not True:
        return issues, None
    return issues, {
        "id": did or base,
        "decision_class": row_class,
        "autonomy_class": row_autonomy,
        "decision_receipt_ref": receipt_ref,
        "charter_grant_id": text(grant.get("id")),
        "charter_ref": text(decided_by.get("charter_ref")),
        "evidence_refs": refs,
        "review_required": "human_lock_review",
    }


def check_decisions(
    ip_dir: Path,
    *,
    hard_gate: bool,
) -> tuple[list[dict[str, str]], dict[str, int], list[str]]:
    issues, counts, blockers, _review_items = _check_decisions(ip_dir, hard_gate=hard_gate)
    return issues, counts, blockers


def _check_decisions(
    ip_dir: Path,
    *,
    hard_gate: bool,
) -> tuple[list[dict[str, str]], dict[str, int], list[str], list[dict[str, Any]]]:
    path = oag_paths.legacy_or_hidden(ip_dir, "ontology/decision_matrix.yaml")
    doc = read_yaml(path)
    issues: list[dict[str, str]] = []
    blockers: list[str] = []
    provisional_review_items: list[dict[str, Any]] = []

    if "__load_error__" in doc:
        return [issue("DECISION_MATRIX_INVALID", f"Cannot read decision_matrix.yaml: {doc['__load_error__']}", str(path))], {
            "decisions": 0,
            "lock_required": 0,
            "unresolved_lock_blockers": 0,
        }, blockers, provisional_review_items

    if not doc:
        if hard_gate:
            issues.append(issue("DECISION_MATRIX_MISSING", "Locked or required scope needs ontology/decision_matrix.yaml.", str(path)))
        return issues, {"decisions": 0, "lock_required": 0, "unresolved_lock_blockers": 0}, blockers, provisional_review_items

    issues.extend(
        contextual_schema_issues(
            "oag_decision_matrix.schema.json",
            doc,
            code_prefix="DECISION_MATRIX_SCHEMA",
            document_path=str(path),
        )
    )
    if doc.get("schema_version") != "oag_decision_matrix.v1":
        issues.append(issue("DECISION_MATRIX_SCHEMA_VERSION", "decision_matrix.yaml must use schema_version oag_decision_matrix.v1.", str(path)))

    decisions = [item for item in as_list(doc.get("decisions")) if isinstance(item, dict)]
    counts = {"decisions": len(decisions), "lock_required": 0, "unresolved_lock_blockers": 0}
    if hard_gate and not decisions:
        issues.append(issue("DECISION_REQUIRED", "Locked or required scope needs at least one decision row.", "decisions"))

    seen: set[str] = set()
    for index, decision in enumerate(decisions):
        base = f"decisions[{index}]"
        did = text(decision.get("id"))
        status = text(decision.get("status")).lower()
        lock_required = decision.get("lock_required")

        if not did:
            issues.append(issue("DECISION_ID", "Decision row missing id.", base))
        elif did in seen:
            issues.append(issue("DECISION_DUPLICATE_ID", f"Duplicate decision id {did}.", base))
        seen.add(did)

        if not text(decision.get("question")):
            issues.append(issue("DECISION_QUESTION", f"{did or base} missing question.", base))
        if status not in VALID_STATUSES:
            issues.append(issue("DECISION_STATUS", f"{did or base} has invalid status {status or '<missing>'}.", base))
        if not isinstance(lock_required, bool):
            issues.append(issue("DECISION_LOCK_REQUIRED", f"{did or base} lock_required must be boolean.", base))
            lock_required = False
        if not text(decision.get("owner")):
            issues.append(issue("DECISION_OWNER", f"{did or base} missing owner.", base))

        if lock_required:
            counts["lock_required"] += 1
            if status not in LOCK_READY_STATUSES:
                counts["unresolved_lock_blockers"] += 1
                blockers.append(did or base)
                if hard_gate:
                    issues.append(issue("DECISION_LOCK_BLOCKER", f"{did or base} is lock-required but status is {status or '<missing>'}.", base))

        if status == "decided" and not has_value(decision.get("decision")):
            issues.append(issue("DECISION_VALUE_MISSING", f"{did or base} is decided but has no decision value.", base))
        issues.extend(_evidence_requirement_issues(ip_dir, decision, base=base, did=did))
        issues.extend(
            _tier2_lock_evidence_issues(
                ip_dir,
                decision,
                hard_gate=hard_gate,
                lock_required=bool(lock_required),
                status=status,
                base=base,
                did=did,
            )
        )
        agent_issues, provisional_review_item = _agent_decision_issues(ip_dir, decision, base=base, did=did)
        issues.extend(agent_issues)
        if provisional_review_item:
            provisional_review_items.append(provisional_review_item)
        if status == "waived" and not text(decision.get("waiver_reason")):
            issues.append(issue("DECISION_WAIVER_REASON", f"{did or base} is waived but has no waiver_reason.", base))

    return issues, counts, blockers, provisional_review_items


def check(ip_dir: Path, *, require_locked: bool = False) -> dict[str, Any]:
    ip_dir = oag_paths.ip_root(ip_dir)
    locked = is_locked(ip_dir)
    hard_gate = require_locked or locked
    decision_issues, decision_counts, blockers, provisional_review_items = _check_decisions(ip_dir, hard_gate=hard_gate)
    req_quality_result = oag_req_quality_check.check(ip_dir, require_locked=hard_gate)
    req_quality_issues = req_quality_result.get("issues", []) if isinstance(req_quality_result, dict) else []
    atom_result = oag_requirement_atom_check.check(ip_dir, require_locked=hard_gate)
    atom_issues = atom_result.get("issues", []) if isinstance(atom_result, dict) else []
    contract_strength_result = oag_contract_strength_check.check(ip_dir, require_locked=hard_gate)
    contract_strength_issues = contract_strength_result.get("issues", []) if isinstance(contract_strength_result, dict) else []
    vplan_result = oag_verification_plan_check.check(ip_dir, require_locked=hard_gate)
    vplan_issues = vplan_result.get("issues", []) if isinstance(vplan_result, dict) else []
    trace_result = oag_trace_graph_check.check(ip_dir, require_locked=hard_gate)
    trace_issues = trace_result.get("issues", []) if isinstance(trace_result, dict) else []
    has_rtl_files = bool(oag_decision_rtl_consistency_check.rtl_files(ip_dir))
    rtl_consistency_result = (
        oag_decision_rtl_consistency_check.check(ip_dir)
        if has_rtl_files
        else {
            "schema_version": "oag_decision_rtl_consistency_check.v1",
            "status": "skipped",
            "ip": ip_dir.name,
            "reason": "no_rtl_files",
            "counts": {"decisions": 0, "rtl_files": 0, "parameters": 0, "issues": 0},
            "issues": [],
        }
    )
    rtl_consistency_raw = rtl_consistency_result.get("issues", []) if isinstance(rtl_consistency_result, dict) else []
    rtl_consistency_issues = [
        issue(
            text(item.get("code") or "DECISION_RTL_CONSISTENCY"),
            text(item.get("message") or "decision/RTL consistency issue"),
            text(item.get("path") or ""),
        )
        for item in rtl_consistency_raw
        if isinstance(item, dict)
    ]
    cleanup_result = oag_exploration_cleanup_check.check(ip_dir)
    raw_cleanup_issues = cleanup_result.get("issues", []) if isinstance(cleanup_result, dict) else []
    cleanup_issues = [
        issue(
            text(item.get("code") or "EXPLORATION_CLEANUP"),
            text(item.get("message") or "exploration cleanup issue"),
            text(item.get("path") or ""),
        )
        for item in raw_cleanup_issues
        if isinstance(item, dict)
    ]
    domain_result = oag_domain_crossing_check.check(ip_dir, [], require_domain_intent=hard_gate)
    raw_domain_issues = domain_result.get("issues", []) if isinstance(domain_result, dict) else []
    domain_issues = [
        issue("DOMAIN_CROSSING_READINESS", str(item), str(domain_result.get("domain_intent") or "ontology/domain_intent.yaml"))
        for item in raw_domain_issues
    ]
    issues = decision_issues + req_quality_issues + atom_issues + contract_strength_issues + vplan_issues + trace_issues + rtl_consistency_issues + cleanup_issues + domain_issues

    next_actions: list[str] = []
    if decision_counts["unresolved_lock_blockers"]:
        next_actions.append("Resolve or waive lock-required decisions in ontology/decision_matrix.yaml.")
    if req_quality_issues:
        next_actions.append("Resolve source claims, ambiguity register, or requirement quality issues.")
    if atom_issues:
        next_actions.append("Resolve requirement atom, shallow obligation, or assume/guarantee contract issues.")
    if contract_strength_issues:
        next_actions.append("Resolve closure-grade contract strength issues before implementation or validation.")
    if vplan_issues:
        next_actions.append("Resolve verification strategy plan issues before TB implementation or closure.")
    if trace_issues:
        next_actions.append("Resolve source-to-contract-to-evidence trace graph issues.")
    if rtl_consistency_issues:
        next_actions.append("Resolve locked decision to RTL/configuration consistency issues before implementation review or closure.")
    if cleanup_issues:
        next_actions.append("Run exploration cleanup: select or collapse one candidate, prune/archive the rest, remove provisional/product references, prune DSE worktrees, and map retained generate options.")
    if domain_issues:
        next_actions.append("Resolve clock/reset-domain intent and mitigation issues before RTL implementation dispatch.")
    if not issues and not hard_gate:
        next_actions.append("Draft is lock-ready only after user lock and hard gate re-check.")

    return {
        "schema_version": "oag_lock_readiness_check.v1",
        "status": "fail" if issues else "pass",
        "ip": ip_dir.name,
        "scope_locked": locked,
        "require_locked": require_locked,
        "hard_gate": hard_gate,
        "counts": {
            **decision_counts,
            "decision_issues": len(decision_issues),
            "requirement_quality_issues": len(req_quality_issues),
            "atom_issues": len(atom_issues),
            "contract_strength_issues": len(contract_strength_issues),
            "verification_plan_issues": len(vplan_issues),
            "trace_issues": len(trace_issues),
            "decision_rtl_consistency_issues": len(rtl_consistency_issues),
            "exploration_cleanup_issues": len(cleanup_issues),
            "domain_crossing_issues": len(domain_issues),
            "provisional_review_items": len(provisional_review_items),
            "issues": len(issues),
        },
        "unresolved_lock_blockers": blockers,
        "provisional_review_items": provisional_review_items,
        "decision_rtl_consistency": rtl_consistency_result,
        "exploration_cleanup": cleanup_result,
        "issues": issues,
        "next_actions": next_actions,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ip-dir", required=True)
    parser.add_argument("--require-locked", action="store_true", help="Apply post-lock hard gates even if scope_lock is still draft.")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    result = check(Path(args.ip_dir), require_locked=args.require_locked)
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    elif result["status"] == "pass":
        print("PASS oag lock readiness check")
    else:
        print("FAIL oag lock readiness check")
        for item in result["issues"]:
            path = f" {item['path']}" if item.get("path") else ""
            print(f"- {item['code']}:{path} {item['message']}")
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
