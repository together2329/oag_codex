#!/usr/bin/env python3
# noqa: SIZE_OK - Single OAG CLI owns architecture candidate generation, Tier-1 estimates, and scoring receipts together.
from __future__ import annotations

import argparse
import hashlib
import importlib
import itertools
import json
import shutil
import sys
from pathlib import Path
from typing import Any, NamedTuple

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

oag_paths = importlib.import_module("oag_paths")
run_common = importlib.import_module("oag_run_control_common")
contextual_schema_issues = importlib.import_module("oag_validate_json").contextual_schema_issues


CANDIDATES_SCHEMA = "oag_architecture_candidates.v1"; SCOREBOARD_SCHEMA = "oag_architecture_scoreboard.v1"; RESULT_SCHEMA = "oag_architecture_options_result.v1"; PROMOTION_SCHEMA = "oag_architecture_promotion_receipt.v1"
ARCH_EXPLORATION_REF = "knowledge/arch_exploration"; PROMOTED_ARCH_REF = "knowledge/views/promoted/arch"
METRIC_DIRECTIONS = {"throughput": "max", "latency": "min", "area_proxy": "min", "power_proxy": "min", "verification_cost": "min"}
DEFAULT_WEIGHTS = {"throughput": 0.30, "latency": 0.25, "area_proxy": 0.20, "power_proxy": 0.05, "verification_cost": 0.20}; RETAINED_GENERATE_OPTION_VERIFICATION_PENALTY = 0.35

JsonObject = dict[str, Any]


class OptionChoice(NamedTuple):
    decision_id: str
    option_id: str
    label: str
    payload: JsonObject


def text(value: Any) -> str: return str(value or "").strip()


def as_list(value: Any) -> list[Any]: return [] if value is None else value if isinstance(value, list) else [value]


def read_structured(path: Path) -> JsonObject:
    if not path.is_file():
        return {}
    raw = path.read_text(encoding="utf-8")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        try:
            import yaml  # type: ignore
        except ImportError:
            return {"__load_error__": "YAML input requires PyYAML"}
        try:
            data = yaml.safe_load(raw) or {}
        except yaml.YAMLError as exc:
            return {"__load_error__": str(exc)}
    return data if isinstance(data, dict) else {}


def issue(code: str, message: str, path: str = "") -> dict[str, str]:
    payload = {"code": code, "message": message}
    if path: payload["path"] = path
    return payload


def candidates_path(ip_dir: Path, run_id: str) -> Path: return oag_paths.state_path(ip_dir, Path("knowledge") / "arch_exploration" / run_id) / "candidates.json"


def scoreboard_path(ip_dir: Path, run_id: str) -> Path: return oag_paths.state_path(ip_dir, Path("knowledge") / "arch_exploration" / run_id) / "architecture_scoreboard.json"


def promotion_receipt_path(ip_dir: Path, run_id: str, candidate_id: str) -> Path:
    return oag_paths.state_path(ip_dir, Path(PROMOTED_ARCH_REF) / safe_segment(run_id, "run_id") / safe_segment(candidate_id, "candidate_id")) / "promotion_receipt.json"


def promoted_candidate_path(ip_dir: Path, run_id: str, candidate_id: str) -> Path:
    return oag_paths.state_path(ip_dir, Path(PROMOTED_ARCH_REF) / safe_segment(run_id, "run_id") / safe_segment(candidate_id, "candidate_id"))


def safe_segment(value: str, field: str) -> str:
    clean = text(value)
    if not clean or Path(clean).parts != (clean,) or clean in {".", ".."}:
        raise ValueError(f"{field} must be one normalized path segment")
    return clean


def write_yaml(path: Path, data: JsonObject) -> None:
    import yaml  # type: ignore

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")


def source_fingerprint(ip_dir: Path) -> str:
    digest = hashlib.sha256()
    for rel in ("ontology/decision_matrix.yaml", "req/source_claims.yaml", "ontology/mission_charter.yaml"):
        path = oag_paths.legacy_or_hidden(ip_dir, rel)
        digest.update(rel.encode())
        if path.is_file(): digest.update(path.read_bytes())
    return digest.hexdigest()


def deterministic_run_id(fingerprint: str) -> str: return f"ARCH_RUN_{fingerprint[:12].upper()}"


def approved_arch_charter(ip_dir: Path) -> tuple[JsonObject, list[dict[str, str]]]:
    charter = read_structured(oag_paths.legacy_or_hidden(ip_dir, "ontology/mission_charter.yaml"))
    if charter.get("__load_error__"): return charter, [issue("CHARTER_INVALID", text(charter.get("__load_error__")), "ontology/mission_charter.yaml")]
    approval_raw = charter.get("approval"); approval = approval_raw if isinstance(approval_raw, dict) else {}
    actor_raw = approval.get("actor"); actor = actor_raw if isinstance(actor_raw, dict) else {}; approved_by_raw = charter.get("approved_by"); approved_by = approved_by_raw if isinstance(approved_by_raw, dict) else {}
    approved = charter.get("approved") is True or text(charter.get("status")).lower() == "approved" or approval.get("approved") is True or text(approval.get("status")).lower() == "approved"
    human = text(actor.get("kind")).lower() == "human" or text(approved_by.get("kind")).lower() == "human"
    if not approved or not human: return charter, [issue("CHARTER_NOT_APPROVED", "approved human mission charter is required", "ontology/mission_charter.yaml")]
    grant = next((item for item in charter_grants(charter) if arch_grant_enabled(item)), {})
    if not grant: return charter, [issue("CHARTER_ARCH_GRANT_MISSING", "architecture_tradeoff grant is required", "ontology/mission_charter.yaml")]
    return charter, []


def charter_grants(charter: JsonObject) -> list[JsonObject]:
    autonomy_raw = charter.get("autonomy")
    autonomy = autonomy_raw if isinstance(autonomy_raw, dict) else {}
    grants = [item for item in as_list(charter.get("autonomy_grants")) if isinstance(item, dict)]
    grants.extend(item for item in as_list(autonomy.get("grants")) if isinstance(item, dict))
    class_map_raw = autonomy.get("decision_classes")
    class_map = class_map_raw if isinstance(class_map_raw, dict) else {}
    for key, value in class_map.items():
        if isinstance(value, dict):
            grants.append({"decision_class": key, **value})
        elif value is True:
            grants.append({"decision_class": key, "granted": True})
    return grants


def arch_grant_enabled(grant: JsonObject) -> bool:
    decision_class = text(grant.get("decision_class") or grant.get("class")).lower()
    autonomy_class = text(grant.get("autonomy_class")).lower()
    if decision_class != "architecture_tradeoff" and autonomy_class != "measured_tradeoff":
        return False
    if grant.get("granted") is False:
        return False
    return text(grant.get("status")).lower() not in {"denied", "draft", "pending", "proposed", "rejected", "revoked"}


def max_candidates(charter: JsonObject) -> int:
    raw_budgets = charter.get("budgets")
    budgets = raw_budgets if isinstance(raw_budgets, dict) else {}
    value = budgets.get("max_candidates_tier1")
    return max(1, int(value)) if isinstance(value, int) and not isinstance(value, bool) else 8


def objective_weights(charter: JsonObject) -> dict[str, float]:
    raw_weights = charter.get("objective_weights")
    raw = raw_weights if isinstance(raw_weights, dict) else {}
    weights: dict[str, float] = {}
    for key, fallback in DEFAULT_WEIGHTS.items():
        value = raw.get(key, fallback)
        weights[key] = float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else fallback
    total = sum(weights.values()) or 1.0
    return {key: value / total for key, value in weights.items()}


def option_rows(row: JsonObject) -> list[OptionChoice]:
    did = text(row.get("id"))
    raw_options = as_list(row.get("options") or row.get("choices") or row.get("interview_options"))
    if not raw_options and row.get("recommended") is not None: raw_options = [row.get("recommended")]
    choices: list[OptionChoice] = []
    for index, raw in enumerate(raw_options, start=1):
        payload = raw if isinstance(raw, dict) else {"value": raw}
        option_id = text(payload.get("id") or payload.get("value") or payload.get("label") or f"OPT_{index}")
        label = text(payload.get("label") or payload.get("name") or option_id)
        choices.append(OptionChoice(did, option_id, label, payload))
    return choices


def architecture_decisions(ip_dir: Path) -> tuple[list[JsonObject], list[dict[str, str]]]:
    matrix = read_structured(oag_paths.legacy_or_hidden(ip_dir, "ontology/decision_matrix.yaml"))
    if matrix.get("__load_error__"): return [], [issue("DECISION_MATRIX_INVALID", text(matrix.get("__load_error__")), "ontology/decision_matrix.yaml")]
    rows = [item for item in as_list(matrix.get("decisions")) if isinstance(item, dict)]
    arch = [row for row in rows if text(row.get("decision_class")).lower() == "architecture_tradeoff" and text(row.get("status")).lower() not in {"decided", "waived"}]
    issues = [issue("ARCH_DECISIONS_MISSING", "open architecture_tradeoff decisions with options are required", "ontology/decision_matrix.yaml")] if not arch else []
    return arch, issues


def violates_forbidden(charter: JsonObject, combo: tuple[OptionChoice, ...]) -> str:
    raw_constraints = charter.get("constraints")
    constraints = raw_constraints if isinstance(raw_constraints, dict) else {}
    forbidden = [text(item).lower() for item in as_list(constraints.get("forbidden")) if text(item)]
    haystack = " ".join(f"{choice.option_id} {choice.label}" for choice in combo).lower()
    return next((item for item in forbidden if item in haystack), "")


def build_candidate(index: int, combo: tuple[OptionChoice, ...], pruned: str) -> JsonObject:
    assignments = {choice.decision_id: choice.option_id for choice in combo}
    parameters: JsonObject = {}
    modules: list[str] = ["arch_top"]
    axes_notes: JsonObject = {}
    for choice in combo:
        if isinstance(choice.payload.get("parameters"), dict): parameters.update(choice.payload["parameters"])
        modules.extend(text(item) for item in as_list(choice.payload.get("modules")) if text(item))
        if isinstance(choice.payload.get("axes_notes"), dict): axes_notes.update(choice.payload["axes_notes"])
    return {"id": f"CAND_{index:03d}", "label": ", ".join(choice.label for choice in combo), "decision_assignments": assignments, "parameter_draft": parameters, "structure_sketch": {"modules": sorted(set(modules))}, "axes_notes": axes_notes, "tier1_scores": {}, "status": "pruned" if pruned else "alive", "pruned_reason": f"forbidden constraint matched: {pruned}" if pruned else "", "_option_payloads": [choice.payload for choice in combo]}


def generate(ip_dir: Path, run_id: str = "") -> JsonObject:
    ip_dir = oag_paths.ip_root(ip_dir)
    fingerprint = source_fingerprint(ip_dir)
    run_id = run_id or deterministic_run_id(fingerprint)
    charter, issues = approved_arch_charter(ip_dir)
    decisions, decision_issues = architecture_decisions(ip_dir)
    issues.extend(decision_issues)
    groups = [option_rows(row) for row in decisions]
    if any(not group for group in groups):
        issues.append(issue("ARCH_OPTIONS_MISSING", "each architecture_tradeoff decision needs at least one option", "ontology/decision_matrix.yaml"))
    budget = max_candidates(charter) if not issues else 0
    candidates: list[JsonObject] = []
    if not issues:
        for index, combo in enumerate(itertools.islice(itertools.product(*groups), budget), start=1):
            candidates.append(build_candidate(index, combo, violates_forbidden(charter, combo)))
    payload: JsonObject = {"schema_version": CANDIDATES_SCHEMA, "status": "fail" if issues else "pass", "ip": ip_dir.name, "run_id": run_id, "source_fingerprint": fingerprint, "charter_ref": "ontology/mission_charter.yaml", "decision_refs": [text(row.get("id")) for row in decisions], "budget": {"max_candidates_tier1": budget, "generated_candidates": len(candidates)}, "candidates": candidates, "issues": issues}
    if not issues:
        payload["issues"] = contextual_schema_issues("oag_architecture_candidates.schema.json", payload, code_prefix="ARCH_CANDIDATES_SCHEMA", document_path=f"knowledge/arch_exploration/{run_id}/candidates.json")
        payload["status"] = "fail" if payload["issues"] else "pass"
        run_common.write_json(candidates_path(ip_dir, run_id), payload)
    return payload


def metric_from_options(options: list[JsonObject], key: str, fallback: float) -> float:
    values: list[float] = []
    for option in options:
        source = option.get("tier1_scores") if isinstance(option.get("tier1_scores"), dict) else option.get("metrics")
        metrics = source if isinstance(source, dict) else {}
        value = metrics.get(key, option.get(key))
        if isinstance(value, dict): value = value.get("value")
        if isinstance(value, (int, float)) and not isinstance(value, bool): values.append(float(value))
    penalty = sum(1 for option in options if option.get("retain") is True or option.get("retained") is True or (isinstance(option.get("generate_option"), dict) and (option["generate_option"].get("retain") is True or option["generate_option"].get("retained") is True)) or text(option.get("status") or option.get("lifecycle")).lower() == "retained") * RETAINED_GENERATE_OPTION_VERIFICATION_PENALTY if key == "verification_cost" else 0.0
    return (fallback if not values else sum(values) if key in {"latency", "area_proxy", "power_proxy", "verification_cost"} else min(values)) + penalty


def estimate_candidate(candidate: JsonObject) -> JsonObject:
    options = [item for item in as_list(candidate.get("_option_payloads")) if isinstance(item, dict)]
    modules = as_list(candidate.get("structure_sketch", {}).get("modules") if isinstance(candidate.get("structure_sketch"), dict) else [])
    defaults = {
        "throughput": 1.0,
        "latency": max(1.0, float(len(modules))),
        "area_proxy": 1000.0 + 250.0 * len(modules),
        "power_proxy": 1.0 + 0.1 * len(modules),
        "verification_cost": 0.2 + 0.1 * len(options),
    }
    scores = {}
    for key, fallback in defaults.items():
        scores[key] = {"value": round(metric_from_options(options, key, fallback), 6), "unit": "norm" if key != "latency" else "cycles", "model": "tier1-deterministic-v1"}
    candidate.pop("_option_payloads", None)
    candidate["tier1_scores"] = scores
    return candidate


def estimate(ip_dir: Path, run_id: str) -> JsonObject:
    ip_dir = oag_paths.ip_root(ip_dir)
    path = candidates_path(ip_dir, run_id)
    payload = run_common.read_json_object(path)
    issues = [] if payload else [issue("CANDIDATES_MISSING", "run candidates.json is missing", run_common.rel_to_ip(ip_dir, path))]
    if not issues:
        payload["candidates"] = [estimate_candidate(item) for item in payload.get("candidates", []) if isinstance(item, dict)]
        payload["issues"] = contextual_schema_issues("oag_architecture_candidates.schema.json", payload, code_prefix="ARCH_CANDIDATES_SCHEMA", document_path=run_common.rel_to_ip(ip_dir, path))
        payload["status"] = "fail" if payload["issues"] else "pass"
        run_common.write_json(path, payload)
    return payload if payload else {"schema_version": CANDIDATES_SCHEMA, "status": "fail", "ip": ip_dir.name, "run_id": run_id, "source_fingerprint": "", "candidates": [], "issues": issues}


def metric_value(candidate: JsonObject, key: str) -> float:
    metric = candidate.get("tier1_scores", {}).get(key) if isinstance(candidate.get("tier1_scores"), dict) else None; value = metric.get("value") if isinstance(metric, dict) else None
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else 0.0


def normalized(values: dict[str, float], key: str, candidate_id: str) -> float:
    same_metric = list(values.values())
    low = min(same_metric)
    high = max(same_metric)
    if high == low: return 1.0
    raw = values[candidate_id]
    score = (raw - low) / (high - low)
    return score if METRIC_DIRECTIONS[key] == "max" else 1.0 - score


def pareto(candidate_id: str, metrics: dict[str, dict[str, float]]) -> bool:
    for other_id in list(next(iter(metrics.values())).keys()) if metrics else []:
        if other_id == candidate_id: continue
        no_worse = all(normalized(values, key, other_id) >= normalized(values, key, candidate_id) for key, values in metrics.items())
        better = any(normalized(values, key, other_id) > normalized(values, key, candidate_id) for key, values in metrics.items())
        if no_worse and better:
            return False
    return True


def constraint_terms(charter: JsonObject, key: str) -> list[str]:
    raw_constraints = charter.get("constraints")
    constraints = raw_constraints if isinstance(raw_constraints, dict) else {}
    return [text(item).lower() for item in as_list(constraints.get(key)) if text(item)]


def candidate_haystack(candidate: JsonObject) -> str:
    searchable = {
        "id": candidate.get("id"),
        "label": candidate.get("label"),
        "decision_assignments": candidate.get("decision_assignments"),
        "parameter_draft": candidate.get("parameter_draft"),
        "structure_sketch": candidate.get("structure_sketch"),
        "axes_notes": candidate.get("axes_notes"),
    }
    return json.dumps(searchable, sort_keys=True, default=str).lower()


def constraint_issues_for_candidate(charter: JsonObject, candidate: JsonObject) -> list[str]:
    haystack = candidate_haystack(candidate)
    issues: list[str] = []
    for term in constraint_terms(charter, "forbidden"):
        if term in haystack:
            issues.append(f"forbidden constraint matched: {term}")
    for term in constraint_terms(charter, "required"):
        if term not in haystack:
            issues.append(f"required constraint missing: {term}")
    return issues


def score(ip_dir: Path, run_id: str) -> JsonObject:
    ip_dir = oag_paths.ip_root(ip_dir)
    candidates_doc = run_common.read_json_object(candidates_path(ip_dir, run_id))
    charter, charter_issues = approved_arch_charter(ip_dir)
    candidates = [item for item in candidates_doc.get("candidates", []) if isinstance(item, dict) and item.get("status") != "pruned"]
    issues = charter_issues if candidates_doc else [issue("CANDIDATES_MISSING", "estimate candidates before scoring", run_common.rel_to_ip(ip_dir, candidates_path(ip_dir, run_id)))]
    if not candidates: issues.append(issue("SCORE_CANDIDATES_EMPTY", "no live candidates are available to score"))
    weights = objective_weights(charter)
    metric_map = {key: {text(candidate.get("id")): metric_value(candidate, key) for candidate in candidates} for key in weights}
    rows: list[JsonObject] = []
    for candidate in candidates:
        cid = text(candidate.get("id"))
        constraint_issues = constraint_issues_for_candidate(charter, candidate)
        total = sum(normalized(metric_map[key], key, cid) * weight for key, weight in weights.items())
        rows.append({"candidate_id": cid, "rank": 0, "weighted_total": round(total, 6), "pareto_member": pareto(cid, metric_map), "rank_margin_pct": 0.0, "metrics": {key: metric_value(candidate, key) for key in weights}, "decision_assignments": candidate.get("decision_assignments", {}), "hard_constraint_pass": not constraint_issues, "constraint_issues": constraint_issues})
    if rows and not any(row.get("hard_constraint_pass") is True for row in rows):
        issues.append(issue("SCORE_HARD_CONSTRAINTS_EMPTY", "no live candidates satisfy charter hard constraints"))
    rows.sort(key=lambda item: (item.get("hard_constraint_pass") is not True, -float(item["weighted_total"]), text(item["candidate_id"])))
    for rank, row in enumerate(rows, start=1):
        row["rank"] = rank
    margin = 100.0 if len(rows) == 1 else round(((float(rows[0]["weighted_total"]) - float(rows[1]["weighted_total"])) / max(abs(float(rows[1]["weighted_total"])), 1e-9)) * 100.0, 6) if rows else 0.0
    if rows:
        rows[0]["rank_margin_pct"] = margin
    payload: JsonObject = {"schema_version": SCOREBOARD_SCHEMA, "status": "fail" if issues else "pass", "ip": ip_dir.name, "run_id": run_id, "source_fingerprint": text(candidates_doc.get("source_fingerprint")), "objective_weights": weights, "rank_margin_pct": margin, "rows": rows, "issues": issues}
    if not issues:
        payload["issues"] = contextual_schema_issues("oag_architecture_scoreboard.schema.json", payload, code_prefix="ARCH_SCOREBOARD_SCHEMA", document_path=f"knowledge/arch_exploration/{run_id}/architecture_scoreboard.json")
        payload["status"] = "fail" if payload["issues"] else "pass"
        run_common.write_json(scoreboard_path(ip_dir, run_id), payload)
    return payload


def split_ref(ref: str) -> tuple[str, str]:
    path, sep, fragment = text(ref).partition("#")
    return path, f"{sep}{fragment}" if sep else ""


def promoted_ref_for(run_id: str, ref: str) -> str:
    path, fragment = split_ref(ref)
    prefix = f"{ARCH_EXPLORATION_REF}/{safe_segment(run_id, 'run_id')}/"
    if not path.startswith(prefix):
        return ref
    suffix = path.removeprefix(prefix)
    return f"{PROMOTED_ARCH_REF}/{safe_segment(run_id, 'run_id')}/{suffix}{fragment}"


def copy_artifact_ref(ip_dir: Path, source_ref: str, promoted_ref: str) -> dict[str, str]:
    source_path, _ = split_ref(source_ref)
    promoted_path, _ = split_ref(promoted_ref)
    source = oag_paths.legacy_or_hidden(ip_dir, source_path)
    dest = oag_paths.state_path(ip_dir, promoted_path)
    if not source.exists():
        return issue("PROMOTION_EVIDENCE_MISSING", f"evidence artifact does not exist: {source_ref}", source_path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    if source.is_dir():
        shutil.copytree(source, dest, dirs_exist_ok=True)
    else:
        shutil.copy2(source, dest)
    return {"source": run_common.rel_to_ip(ip_dir, source), "promoted": run_common.rel_to_ip(ip_dir, dest)}


def rewrite_ref_value(run_id: str, value: Any, rewrites: dict[str, str]) -> Any:
    if isinstance(value, str):
        rewritten = promoted_ref_for(run_id, value)
        if rewritten != value:
            rewrites[value] = rewritten
        return rewritten
    if isinstance(value, list):
        return [rewrite_ref_value(run_id, item, rewrites) for item in value]
    if isinstance(value, dict):
        updated = dict(value)
        for key in ("path", "ref", "artifact", "artifact_path"):
            if isinstance(updated.get(key), str):
                updated[key] = rewrite_ref_value(run_id, updated[key], rewrites)
        return updated
    return value


def rewrite_decision_evidence_refs(ip_dir: Path, run_id: str) -> tuple[list[dict[str, str]], list[dict[str, str]], bool]:
    matrix_path = oag_paths.legacy_or_hidden(ip_dir, "ontology/decision_matrix.yaml")
    matrix = read_structured(matrix_path)
    if not matrix:
        return [], [], False
    rows = [item for item in as_list(matrix.get("decisions")) if isinstance(item, dict)]
    copied: list[dict[str, str]] = []
    issues: list[dict[str, str]] = []
    receipt_updates: list[tuple[Path, JsonObject]] = []
    changed = False
    for row in rows:
        row_rewrites: dict[str, str] = {}
        for field in ("evidence_refs", "evidence_required", "refs"):
            if field in row:
                updated = rewrite_ref_value(run_id, row[field], row_rewrites)
                if updated != row[field]:
                    row[field] = updated
                    changed = True
        receipt_ref = text(row.get("decision_receipt_ref"))
        if receipt_ref:
            receipt_path = oag_paths.legacy_or_hidden(ip_dir, receipt_ref)
            receipt = run_common.read_json_object(receipt_path)
            if receipt:
                receipt_rewrites = dict(row_rewrites)
                for field in ("evidence_refs", "evidence_required", "artifact_paths"):
                    if field in receipt:
                        receipt[field] = rewrite_ref_value(run_id, receipt[field], receipt_rewrites)
                if receipt_rewrites:
                    originals = sorted(receipt_rewrites)
                    promotion = receipt.get("promotion") if isinstance(receipt.get("promotion"), dict) else {}
                    receipt["promotion"] = {
                        **promotion,
                        "schema_version": "oag_decision_evidence_promotion.v1",
                        "promoted_at": run_common.utc_now(),
                        "promoted_run_id": run_id,
                        "original_exploration_refs": sorted(set(as_list(promotion.get("original_exploration_refs"))) | set(originals)),
                        "promoted_refs": [receipt_rewrites[item] for item in originals],
                    }
                    receipt_updates.append((receipt_path, receipt))
                    changed = True
                row_rewrites.update(receipt_rewrites)
        for source_ref, promoted_ref in sorted(row_rewrites.items()):
            copied_or_issue = copy_artifact_ref(ip_dir, source_ref, promoted_ref)
            if copied_or_issue.get("code"):
                issues.append(copied_or_issue)
            else:
                copied.append(copied_or_issue)
    if issues:
        return copied, issues, False
    if changed:
        for receipt_path, receipt in receipt_updates:
            run_common.write_json(receipt_path, receipt)
        write_yaml(matrix_path, matrix)
    return copied, issues, changed


def copy_candidate_tree(ip_dir: Path, run_id: str, candidate_id: str) -> dict[str, str]:
    source = oag_paths.legacy_or_hidden(ip_dir, Path(ARCH_EXPLORATION_REF) / safe_segment(run_id, "run_id") / safe_segment(candidate_id, "candidate_id"))
    dest = promoted_candidate_path(ip_dir, run_id, candidate_id)
    dest.mkdir(parents=True, exist_ok=True)
    if source.is_dir():
        shutil.copytree(source, dest, dirs_exist_ok=True)
    return {"source": run_common.rel_to_ip(ip_dir, source), "promoted": run_common.rel_to_ip(ip_dir, dest)}


def copy_run_receipts(ip_dir: Path, run_id: str) -> list[dict[str, str]]:
    copied: list[dict[str, str]] = []
    dest_root = oag_paths.state_path(ip_dir, Path(PROMOTED_ARCH_REF) / safe_segment(run_id, "run_id"))
    dest_root.mkdir(parents=True, exist_ok=True)
    for source in (candidates_path(ip_dir, run_id), scoreboard_path(ip_dir, run_id)):
        if not source.is_file():
            continue
        dest = dest_root / source.name
        shutil.copy2(source, dest)
        copied.append({"source": run_common.rel_to_ip(ip_dir, source), "promoted": run_common.rel_to_ip(ip_dir, dest)})
    return copied


def draft_modules(candidate: JsonObject) -> list[str]:
    raw_structure = candidate.get("structure_sketch")
    structure = raw_structure if isinstance(raw_structure, dict) else {}
    return [text(item) for item in as_list(structure.get("modules")) if text(item)]


def write_promoted_drafts(ip_dir: Path, run_id: str, candidate: JsonObject) -> list[str]:
    cid = safe_segment(text(candidate.get("id")), "candidate_id")
    root = promoted_candidate_path(ip_dir, run_id, cid)
    structure_ref = Path(PROMOTED_ARCH_REF) / safe_segment(run_id, "run_id") / cid / "structure_draft.json"
    parameter_ref = Path(PROMOTED_ARCH_REF) / safe_segment(run_id, "run_id") / cid / "parameter_decision_draft.json"
    run_common.write_json(
        root / "structure_draft.json",
        {
            "schema_version": "oag_promoted_structure_draft.v1",
            "run_id": run_id,
            "candidate_id": cid,
            "source_candidate_ref": f"{ARCH_EXPLORATION_REF}/{run_id}/candidates.json#{cid}",
            "decision_assignments": candidate.get("decision_assignments", {}),
            "structure_sketch": candidate.get("structure_sketch", {}),
            "modules": draft_modules(candidate),
        },
    )
    run_common.write_json(
        root / "parameter_decision_draft.json",
        {
            "schema_version": "oag_promoted_parameter_decision_draft.v1",
            "run_id": run_id,
            "candidate_id": cid,
            "source_candidate_ref": f"{ARCH_EXPLORATION_REF}/{run_id}/candidates.json#{cid}",
            "decision_assignments": candidate.get("decision_assignments", {}),
            "parameter_draft": candidate.get("parameter_draft", {}),
            "generate_options": candidate.get("generate_options", []),
        },
    )
    return [structure_ref.as_posix(), parameter_ref.as_posix()]


def promote(ip_dir: Path, run_id: str, candidate_id: str, pruned_reason: str = "not selected") -> JsonObject:
    ip_dir = oag_paths.ip_root(ip_dir)
    run_id = safe_segment(run_id, "run_id")
    candidate_id = safe_segment(candidate_id, "candidate_id")
    path = candidates_path(ip_dir, run_id)
    payload = run_common.read_json_object(path)
    issues = [] if payload else [issue("CANDIDATES_MISSING", "run candidates.json is missing", run_common.rel_to_ip(ip_dir, path))]
    candidates = [item for item in as_list(payload.get("candidates")) if isinstance(item, dict)]
    target = next((item for item in candidates if text(item.get("id")) == candidate_id), None)
    if payload and target is None:
        issues.append(issue("PROMOTION_CANDIDATE_MISSING", f"candidate {candidate_id} is not present in run {run_id}", run_common.rel_to_ip(ip_dir, path)))
    copied: list[dict[str, str]] = []
    draft_refs: list[str] = []
    matrix_updated = False
    if not issues and target is not None:
        for candidate in candidates:
            cid = text(candidate.get("id"))
            if cid == candidate_id:
                candidate["status"] = "selected"
                candidate["selected"] = True
                candidate["promoted_ref"] = f"{PROMOTED_ARCH_REF}/{run_id}/{candidate_id}"
                candidate.pop("pruned_reason", None)
            elif text(candidate.get("status")).lower() != "pruned":
                candidate["status"] = "pruned"
                candidate["selected"] = False
                candidate["pruned_reason"] = pruned_reason
        payload["candidates"] = candidates
        payload["issues"] = contextual_schema_issues("oag_architecture_candidates.schema.json", payload, code_prefix="ARCH_CANDIDATES_SCHEMA", document_path=run_common.rel_to_ip(ip_dir, path))
        payload["status"] = "fail" if payload["issues"] else "pass"
        issues.extend(payload["issues"])
    if issues:
        return {"schema_version": PROMOTION_SCHEMA, "status": "fail", "ip": ip_dir.name, "run_id": run_id, "candidate_id": candidate_id, "issues": issues}
    run_common.write_json(path, payload)
    assert target is not None
    copied.append(copy_candidate_tree(ip_dir, run_id, candidate_id))
    draft_refs = write_promoted_drafts(ip_dir, run_id, target)
    copied.extend(copy_run_receipts(ip_dir, run_id))
    evidence_copied, evidence_issues, matrix_updated = rewrite_decision_evidence_refs(ip_dir, run_id)
    copied.extend(evidence_copied)
    if evidence_issues:
        return {"schema_version": PROMOTION_SCHEMA, "status": "fail", "ip": ip_dir.name, "run_id": run_id, "candidate_id": candidate_id, "issues": evidence_issues}
    receipt = {
        "schema_version": PROMOTION_SCHEMA,
        "status": "pass",
        "ip": ip_dir.name,
        "run_id": run_id,
        "candidate_id": candidate_id,
        "created_at": run_common.utc_now(),
        "source_candidate_ref": f"{ARCH_EXPLORATION_REF}/{run_id}/candidates.json#{candidate_id}",
        "promoted_candidate_ref": f"{PROMOTED_ARCH_REF}/{run_id}/{candidate_id}",
        "draft_refs": draft_refs,
        "candidate_doc_ref": run_common.rel_to_ip(ip_dir, path),
        "promoted_candidate_doc_ref": f"{PROMOTED_ARCH_REF}/{run_id}/candidates.json",
        "decision_matrix_updated": matrix_updated,
        "copied_artifacts": copied,
        "issues": [],
    }
    run_common.write_json(promotion_receipt_path(ip_dir, run_id, candidate_id), receipt)
    return receipt


def command_result(action: str, payload: JsonObject, ip_dir: Path) -> JsonObject:
    run_id = text(payload.get("run_id"))
    candidate_id = text(payload.get("candidate_id"))
    rel = "promotion_receipt.json" if action == "promote" else "architecture_scoreboard.json" if action == "score" else "candidates.json"
    out_path = ""
    if run_id and payload.get("status") == "pass":
        if action == "score":
            out_path = run_common.rel_to_ip(ip_dir, scoreboard_path(ip_dir, run_id))
        elif action == "promote" and candidate_id:
            out_path = run_common.rel_to_ip(ip_dir, promotion_receipt_path(ip_dir, run_id, candidate_id))
        else:
            out_path = run_common.rel_to_ip(ip_dir, candidates_path(ip_dir, run_id))
    return {"schema_version": RESULT_SCHEMA, "status": payload.get("status"), "action": action, "ip": ip_dir.name, "run_id": run_id, "output_path": out_path, "artifact": payload, "issues": payload.get("issues", []), "artifact_name": rel}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate and score OAG Tier-1 architecture candidates.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    for name in ("generate", "estimate", "score"):
        sub = subparsers.add_parser(name)
        sub.add_argument("--ip-dir", required=True)
        sub.add_argument("--run-id", default="")
        sub.add_argument("--json", action="store_true")
    promote_parser = subparsers.add_parser("promote")
    promote_parser.add_argument("--ip-dir", required=True)
    promote_parser.add_argument("--run-id", required=True)
    promote_parser.add_argument("--candidate", required=True)
    promote_parser.add_argument("--pruned-reason", default="not selected")
    promote_parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    ip_dir = oag_paths.ip_root(args.ip_dir)
    if args.command == "generate": payload = generate(ip_dir, args.run_id)
    elif args.command == "estimate": payload = estimate(ip_dir, text(args.run_id))
    elif args.command == "score": payload = score(ip_dir, text(args.run_id))
    else: payload = promote(ip_dir, text(args.run_id), text(args.candidate), text(args.pruned_reason))
    result = command_result(args.command, payload, ip_dir)
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    elif result["status"] == "pass":
        print(f"PASS {RESULT_SCHEMA}: {result['action']} {result['run_id']}")
        print(f"Wrote {result['output_path']}")
    else:
        print(f"FAIL {RESULT_SCHEMA}: {result['action']}", file=sys.stderr)
        for item in result.get("issues", []):
            print(f"- {item.get('code')}: {item.get('message')}", file=sys.stderr)
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
