#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib
import json
import sys
from pathlib import Path
from typing import Any, Final

SCRIPTS_DIR: Final = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

run_common = importlib.import_module("oag_run_control_common")
contextual_schema_issues = importlib.import_module("oag_validate_json").contextual_schema_issues

SCHEMA_VERSION: Final = "oag_parameter_sweep.v1"
SCHEMA_NAME: Final = "oag_parameter_sweep.schema.json"
RULE: Final = "smallest_satisfying_with_margin"
EVIDENCE_TIER: Final = "tier2_probe"
VALID_FOR: Final = ["exploration_comparison"]
NOT_VALID_FOR: Final = [
    "scope_lock",
    "product_rtl_claim",
    "timing_claim",
    "area_claim",
    "performance_claim",
    "external_contract_claim",
    "product_defining_claim",
]
PROVISIONAL_BEGIN: Final = "OAG-BEGIN-PROVISIONAL"
PROVISIONAL_END: Final = "OAG-END-PROVISIONAL"

JsonObject = dict[str, Any]


def text(value: Any) -> str:
    return str(value or "").strip()


def as_list(value: Any) -> list[Any]:
    return [] if value is None else value if isinstance(value, list) else [value]


def issue(code: str, message: str, path: str = "") -> dict[str, str]:
    payload = {"code": code, "message": message}
    if path:
        payload["path"] = path
    return payload


def load_json_object(path: Path) -> JsonObject:
    return run_common.read_json_object(path)


def numeric(value: Any) -> float | None:
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def values_from_input(document: JsonObject) -> list[float]:
    raw_values = as_list(document.get("candidate_values"))
    values = [item for item in (numeric(raw) for raw in raw_values) if item is not None]
    if values:
        return sorted(set(values))
    candidates = [item for item in as_list(document.get("candidates")) if isinstance(item, dict)]
    return sorted(set(item for item in (numeric(candidate.get("value")) for candidate in candidates) if item is not None))


def metric_curve(document: JsonObject) -> dict[float, JsonObject]:
    points = [item for item in as_list(document.get("metric_curve") or document.get("candidates")) if isinstance(item, dict)]
    curve: dict[float, JsonObject] = {}
    for point in points:
        value = numeric(point.get("value") or point.get("candidate_value"))
        if value is not None:
            curve[value] = point
    return curve


def constraint(document: JsonObject) -> JsonObject:
    raw = document.get("constraint")
    return raw if isinstance(raw, dict) else {}


def metric_at(point: JsonObject, metric: str) -> float | None:
    raw_metrics = point.get("metrics")
    metrics = raw_metrics if isinstance(raw_metrics, dict) else {}
    value = metrics.get(metric, point.get(metric))
    if isinstance(value, dict):
        value = value.get("value")
    return numeric(value)


def candidate_rows(document: JsonObject, values: list[float], curve: dict[float, JsonObject]) -> list[JsonObject]:
    rows: list[JsonObject] = []
    for value in values:
        point = curve.get(value, {})
        row: JsonObject = {"value": value}
        raw_metrics = point.get("metrics")
        if isinstance(raw_metrics, dict):
            row["metrics"] = raw_metrics
        else:
            row["metrics"] = {key: raw for key, raw in point.items() if key not in {"value", "candidate_value", "evidence_refs"} and numeric(raw) is not None}
        refs = [text(item) for item in as_list(point.get("evidence_refs")) if text(item)]
        if refs:
            row["evidence_refs"] = refs
        rows.append(row)
    return rows


def selects(point_metric: float, target: float, margin: float, objective: str) -> bool:
    required = target + margin if objective == "min" else target - margin
    return point_metric <= required if objective == "min" else point_metric >= required


def select(document: JsonObject) -> JsonObject:
    parameter = text(document.get("parameter"))
    cons = constraint(document)
    metric = text(cons.get("metric") or document.get("metric"))
    objective = text(cons.get("objective") or "min").lower()
    target = numeric(cons.get("target"))
    margin = numeric(cons.get("margin")) or 0.0
    values = values_from_input(document)
    curve = metric_curve(document)
    issues: list[dict[str, str]] = []
    if not parameter:
        issues.append(issue("PARAMETER_MISSING", "parameter is required", "$.parameter"))
    if not metric:
        issues.append(issue("METRIC_MISSING", "constraint.metric is required", "$.constraint.metric"))
    if objective not in {"min", "max"}:
        issues.append(issue("OBJECTIVE_INVALID", "constraint.objective must be min or max", "$.constraint.objective"))
    if target is None:
        issues.append(issue("TARGET_MISSING", "constraint.target is required", "$.constraint.target"))
    if not values:
        issues.append(issue("CANDIDATES_MISSING", "candidate_values or candidates are required", "$.candidate_values"))
    rows = candidate_rows(document, values, curve)
    selected: JsonObject = {}
    if not issues and target is not None:
        missing = [value for value in values if value not in curve or metric_at(curve[value], metric) is None]
        if missing:
            issues.append(issue("METRIC_POINT_MISSING", f"metric {metric} missing for candidate values {missing}", "$.metric_curve"))
        else:
            for value in values:
                point = curve[value]
                point_metric = metric_at(point, metric)
                if point_metric is not None and selects(point_metric, target, margin, objective):
                    required = target + margin if objective == "min" else target - margin
                    refs = sorted(set([text(item) for item in as_list(document.get("evidence_refs")) if text(item)] + [text(item) for item in as_list(point.get("evidence_refs")) if text(item)]))
                    selected = {
                        "value": value,
                        "metric": metric,
                        "metric_value": point_metric,
                        "required_metric_value": required,
                        "rationale": f"selected smallest {parameter}={value:g} with {metric}={point_metric:g} satisfying {objective} target {target:g} with margin {margin:g}",
                        "evidence_refs": refs,
                    }
                    break
            if not selected:
                issues.append(issue("NO_SATISFYING_CANDIDATE", f"no candidate satisfies {metric} {objective} target {target:g} with margin {margin:g}", "$.metric_curve"))
    evidence_refs = sorted(set(text(item) for item in as_list(document.get("evidence_refs")) if text(item)))
    payload: JsonObject = {
        "schema_version": SCHEMA_VERSION,
        "status": "fail" if issues else "pass",
        "parameter": parameter,
        "selection_rule": RULE,
        "constraint": cons,
        "evidence_tier": EVIDENCE_TIER,
        "valid_for": VALID_FOR,
        "not_valid_for": NOT_VALID_FOR,
        "measurement_kind": "parameter_sweep",
        "candidates": rows,
        "evidence_refs": evidence_refs,
        "issues": issues,
    }
    if selected:
        payload["selected"] = selected
        payload["margin_rationale"] = selected["rationale"]
    return with_schema_issues(payload)


def has_generate_retention(option: JsonObject) -> bool:
    lifecycle = text(option.get("lifecycle")).lower()
    status = text(option.get("status")).lower()
    raw_generate = option.get("generate_option")
    generate = raw_generate if isinstance(raw_generate, dict) else {}
    return option.get("retain") is True or option.get("retained") is True or lifecycle == "retained" or status == "retained" or generate.get("retain") is True or generate.get("retained") is True


def generate_option_issues(option: JsonObject, index: int) -> list[dict[str, str]]:
    prefix = f"$.generate_options[{index}]"
    option_id = text(option.get("id") or option.get("option_id") or f"index {index}")
    findings: list[dict[str, str]] = []
    if not text(option.get("decision_ref") or option.get("decision_row_ref")):
        findings.append(issue("GENERATE_OPTION_DECISION_REF_MISSING", f"retained generate option {option_id} needs a decision row reference", prefix))
    if not text(option.get("configuration_model_entry") or option.get("config_model_entry") or option.get("configuration_ref")):
        findings.append(issue("GENERATE_OPTION_CONFIG_ENTRY_MISSING", f"retained generate option {option_id} needs a configuration model entry", prefix))
    if not text(option.get("verification_plan_config_mapping") or option.get("verification_mapping_ref") or option.get("vplan_config_mapping")):
        findings.append(issue("GENERATE_OPTION_VERIFICATION_MAPPING_MISSING", f"retained generate option {option_id} needs a verification plan config mapping", prefix))
    return findings


def check_generate_options(document: JsonObject) -> JsonObject:
    options = [item for item in as_list(document.get("generate_options")) if isinstance(item, dict)]
    issues: list[dict[str, str]] = []
    checked: list[JsonObject] = []
    for index, option in enumerate(options):
        option_issues = generate_option_issues(option, index) if has_generate_retention(option) else []
        checked.append({"id": text(option.get("id") or option.get("option_id") or f"GENOPT_{index}"), "retained": has_generate_retention(option), "valid": not option_issues, "issues": option_issues})
        issues.extend(option_issues)
    return {"schema_version": "oag_generate_option_lifecycle_check.v1", "status": "fail" if issues else "pass", "checked_options": checked, "issues": issues}


def check_provisional_text(content: str, path: str) -> list[dict[str, str]]:
    depth = 0
    issues: list[dict[str, str]] = []
    for line_no, line in enumerate(content.splitlines(), start=1):
        if PROVISIONAL_BEGIN in line:
            depth += 1
        if PROVISIONAL_END in line:
            depth -= 1
            if depth < 0:
                issues.append(issue("PROVISIONAL_MARKER_UNMATCHED_END", "end marker appears before a begin marker", f"{path}:{line_no}"))
                depth = 0
    if depth:
        issues.append(issue("PROVISIONAL_MARKER_UNMATCHED_BEGIN", "begin marker has no matching end marker", path))
    return issues


def check_provisional(path: Path) -> JsonObject:
    try:
        content = path.read_text(encoding="utf-8")
        issues = check_provisional_text(content, str(path))
    except OSError as exc:
        issues = [issue("PROVISIONAL_FILE_READ_ERROR", str(exc), str(path))]
    return {"schema_version": "oag_provisional_marker_check.v1", "status": "fail" if issues else "pass", "path": str(path), "issues": issues}


def with_schema_issues(payload: JsonObject) -> JsonObject:
    schema_issues = contextual_schema_issues(SCHEMA_NAME, payload, code_prefix="PARAMETER_SWEEP_SCHEMA")
    if schema_issues:
        payload["issues"] = [item for item in as_list(payload.get("issues")) if isinstance(item, dict)] + schema_issues
        payload["status"] = "fail"
    return payload


def write_if_requested(payload: JsonObject, output: str) -> None:
    if output:
        run_common.write_json(Path(output), payload)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Select OAG parameter sweep values and check lifecycle fixtures.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    select_parser = subparsers.add_parser("select")
    select_parser.add_argument("--input", required=True)
    select_parser.add_argument("--output", default="")
    select_parser.add_argument("--json", action="store_true")
    gen_parser = subparsers.add_parser("check-generate-options")
    gen_parser.add_argument("--input", required=True)
    gen_parser.add_argument("--json", action="store_true")
    marker_parser = subparsers.add_parser("check-provisional")
    marker_parser.add_argument("--path", required=True)
    marker_parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    if args.command == "select":
        payload = select(load_json_object(Path(args.input)))
        write_if_requested(payload, args.output)
    elif args.command == "check-generate-options":
        payload = check_generate_options(load_json_object(Path(args.input)))
    else:
        payload = check_provisional(Path(args.path))
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    elif payload["status"] == "pass":
        print(f"PASS {payload['schema_version']}")
    else:
        print(f"FAIL {payload['schema_version']}", file=sys.stderr)
        for item in payload.get("issues", []):
            print(f"- {item.get('code')}: {item.get('message')}", file=sys.stderr)
    return 0 if payload["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
