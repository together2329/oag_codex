#!/usr/bin/env python3
"""Aggregate OAG closure checker reports into a sealed super-gate verdict."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import oag_paths  # noqa: E402


PASS_STATUSES = {"pass", "passed", "ok", "skipped"}
PROFILES = {"development", "signoff"}
DEFAULT_REPORTS = {
    "req_quality": ("reports/oag_req_quality_check.json",),
    "requirement_atom": ("reports/oag_requirement_atom_check.json",),
    "semantic_projection": ("reports/oag_semantic_projection_check.json",),
    "contract_strength": ("reports/oag_contract_strength_check.json",),
    "trace_graph": ("reports/oag_trace_graph_check.json",),
    "verification_plan": ("reports/oag_verification_plan_check.json",),
    "authoring_packet": ("reports/oag_authoring_packet_check.json",),
    "lifecycle": ("reports/oag_lifecycle_check.json",),
    "stale": ("reports/oag_stale_check.json",),
    "decision_rtl_consistency": ("reports/oag_decision_rtl_consistency_check.json",),
    "closure_check": ("reports/oag_closure_check.json",),
    "validation_report": (
        "knowledge/validations/oag_validation_report.json",
        "ontology/validations/oag_validation_report.json",
        "reports/oag_validation_report.json",
    ),
    "gate_decision": (
        "knowledge/gate_reviews/oag_gate_decision.json",
        "ontology/decisions/oag_gate_decision.json",
        "reports/oag_gate_decision.json",
    ),
}


def issue(code: str, message: str, path: str = "") -> dict[str, str]:
    payload = {"code": code, "message": message}
    if path:
        payload["path"] = path
    return payload


def text(value: Any) -> str:
    return str(value or "").strip()


def as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def read_json(path: Path) -> dict[str, Any] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def display_path(ip_dir: Path, path: Path) -> str:
    try:
        rel = path.resolve().relative_to(ip_dir.resolve())
    except Exception:
        return str(path)
    parts = rel.parts
    if parts and parts[0] == oag_paths.HIDDEN_DIR:
        rel = Path(*parts[1:]) if len(parts) > 1 else Path()
    return str(rel)


def resolve_inside_ip(ip_dir: Path, rel: str | Path) -> Path | None:
    raw = Path(rel).expanduser()
    candidate = raw if raw.is_absolute() else ip_dir / raw
    try:
        resolved = candidate.resolve(strict=False)
        resolved.relative_to(ip_dir.resolve())
    except Exception:
        return None
    return resolved


def logical_or_hidden(ip_dir: Path, rel: str) -> Path:
    return oag_paths.legacy_or_hidden(ip_dir, rel) if rel.startswith(("ontology/", "knowledge/")) else ip_dir / rel


def load_manifest(path: Path | None) -> dict[str, Any]:
    if not path or not path.is_file():
        return {}
    payload = read_json(path)
    return payload if isinstance(payload, dict) else {}


def configured_reports(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    raw_reports = manifest.get("required_reports")
    if isinstance(raw_reports, list) and raw_reports:
        return [item for item in raw_reports if isinstance(item, dict)]
    return [{"name": name, "paths": list(paths)} for name, paths in DEFAULT_REPORTS.items()]


def candidate_paths(item: dict[str, Any]) -> list[str]:
    paths = item.get("paths")
    if isinstance(paths, list):
        return [text(path) for path in paths if text(path)]
    path = text(item.get("path"))
    return [path] if path else []


def find_report(ip_dir: Path, item: dict[str, Any]) -> Path | None:
    for rel in candidate_paths(item):
        path = logical_or_hidden(ip_dir, rel)
        if path.is_file():
            return path
    return None


def normalized_status(payload: dict[str, Any]) -> str:
    if isinstance(payload.get("status"), bool):
        return "pass" if payload["status"] else "fail"
    return text(payload.get("status") or payload.get("decision") or payload.get("verdict")).lower()


def iter_input_hashes(payload: dict[str, Any]) -> list[tuple[str, str]]:
    raw = payload.get("input_hashes")
    if isinstance(raw, dict):
        return [(text(path), text(digest)) for path, digest in raw.items() if text(path) and text(digest)]
    raw_inputs = payload.get("inputs")
    pairs: list[tuple[str, str]] = []
    for item in as_list(raw_inputs):
        if not isinstance(item, dict):
            continue
        path = text(item.get("path") or item.get("artifact") or item.get("artifact_path"))
        digest = text(item.get("sha256") or item.get("hash"))
        if path and digest:
            pairs.append((path, digest))
    return pairs


def report_freshness_issues(
    ip_dir: Path,
    payload: dict[str, Any],
    report_name: str,
    *,
    require_hashes: bool,
) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    inputs = iter_input_hashes(payload)
    if require_hashes and not inputs:
        issues.append(issue("CHECK_OUTPUT_INPUT_HASHES_REQUIRED", f"{report_name} must bind its source inputs for signoff freshness."))
    for rel, expected in inputs:
        path = resolve_inside_ip(ip_dir, logical_or_hidden(ip_dir, rel))
        if path is None:
            issues.append(issue("CHECK_OUTPUT_INPUT_OUTSIDE_IP", f"{report_name} input resolves outside the IP workspace.", rel))
            continue
        if not path.is_file():
            issues.append(issue("CHECK_OUTPUT_INPUT_MISSING", f"{report_name} input is missing.", rel))
            continue
        current = sha256(path)
        if current != expected:
            issues.append(issue("CHECK_OUTPUT_INPUT_HASH_MISMATCH", f"{report_name} input hash is stale.", rel))
    return issues


def report_seen(payload: dict[str, Any], report_name: str, report_rel: str, report_hash: str) -> bool:
    checked_hashes = payload.get("checked_report_hashes")
    if not isinstance(checked_hashes, dict):
        checked_hashes = payload.get("checked_artifact_hashes")
    if not isinstance(checked_hashes, dict):
        checked_hashes = {}
    return checked_hashes.get(report_rel) == report_hash or checked_hashes.get(report_name) == report_hash


def actor_id(payload: dict[str, Any]) -> str:
    actor = payload.get("actor")
    if isinstance(actor, dict):
        return text(actor.get("id") or actor.get("actor_id"))
    return text(payload.get("actor_id") or payload.get("reviewer_id") or payload.get("validator_id"))


def approved_equivalent_unstructured(ip_dir: Path) -> list[dict[str, str]]:
    try:
        import yaml  # type: ignore
    except Exception:
        return []
    path = oag_paths.legacy_or_hidden(ip_dir, "ontology/contracts.yaml")
    if not path.is_file():
        return []
    try:
        doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:
        return []
    issues: list[dict[str, str]] = []
    for index, contract in enumerate(as_list(doc.get("contracts") if isinstance(doc, dict) else [])):
        if not isinstance(contract, dict):
            continue
        refs = as_list(contract.get("approved_equivalent_oracle_refs"))
        oracle = contract.get("oracle") if isinstance(contract.get("oracle"), dict) else {}
        refs.extend(as_list(oracle.get("approved_equivalent_oracle_refs")))
        if refs and not as_list(contract.get("approved_equivalent_oracles")):
            issues.append(
                issue(
                    "APPROVED_EQUIVALENT_ORACLE_UNSTRUCTURED",
                    "Contract names approved_equivalent_oracle_refs without structured approved_equivalent_oracles.",
                    f"contracts[{index}]",
                )
            )
    return issues


def check(ip_dir: Path, *, profile: str = "development", manifest_path: Path | None = None) -> dict[str, Any]:
    ip_dir = oag_paths.ip_root(ip_dir)
    profile_name = profile if profile in PROFILES else "development"
    manifest = load_manifest(manifest_path)
    reports = configured_reports(manifest)
    issues: list[dict[str, str]] = []
    loaded_reports: dict[str, dict[str, Any]] = {}
    report_hashes: dict[str, str] = {}
    report_paths: dict[str, str] = {}

    for item in reports:
        name = text(item.get("name"))
        if not name:
            issues.append(issue("MISSING_CHECK_NAME", "required_reports entry needs name."))
            continue
        path = find_report(ip_dir, item)
        if path is None:
            issues.append(issue("MISSING_CHECK_OUTPUT", f"Missing required closure super-gate report {name}.", ",".join(candidate_paths(item))))
            continue
        payload = read_json(path)
        rel = display_path(ip_dir, path)
        if payload is None:
            issues.append(issue("CHECK_OUTPUT_INVALID_JSON", f"{name} report must be JSON object.", rel))
            continue
        status = normalized_status(payload)
        if status not in PASS_STATUSES:
            issues.append(issue("CHECK_OUTPUT_NOT_PASS", f"{name} report status must pass before closure super-gate.", rel))
        if payload.get("diagnostic_only") is True or payload.get("implementation_evidence") is False and name not in {"validation_report", "gate_decision"}:
            issues.append(issue("DIAGNOSTIC_RECEIPT_USED_AS_EVIDENCE", f"{name} is diagnostic/non-evidence and cannot satisfy closure.", rel))
        issues.extend(
            report_freshness_issues(
                ip_dir,
                payload,
                name,
                require_hashes=profile_name == "signoff" and name not in {"validation_report", "gate_decision"},
            )
        )
        loaded_reports[name] = payload
        report_hashes[name] = sha256(path)
        report_paths[name] = rel

    validator = loaded_reports.get("validation_report") or {}
    gate = loaded_reports.get("gate_decision") or {}
    if profile_name == "signoff":
        validator_actor = actor_id(validator)
        gate_actor = actor_id(gate)
        if not validator_actor or not gate_actor:
            issues.append(issue("SIGNOFF_REVIEW_ACTOR_REQUIRED", "Validation and gate reports must identify their actors."))
        elif validator_actor == gate_actor:
            issues.append(issue("SIGNOFF_REVIEWER_SEPARATION_REQUIRED", "Validation and gate actors must be independent for signoff."))
    for name, rel in sorted(report_paths.items()):
        if name in {"validation_report", "gate_decision"}:
            continue
        digest = report_hashes[name]
        if not report_seen(validator, name, rel, digest):
            issues.append(issue("CHECK_OUTPUT_NOT_SEEN_BY_VALIDATOR", f"Validation report did not record {name}.", rel))
        if not report_seen(gate, name, rel, digest):
            issues.append(issue("CHECK_OUTPUT_NOT_SEEN_BY_GATE", f"Gate decision did not record {name}.", rel))

    issues.extend(approved_equivalent_unstructured(ip_dir))

    if profile_name == "signoff":
        for name, payload in loaded_reports.items():
            if normalized_status(payload) == "skipped":
                issues.append(issue("SIGNOFF_CHECK_SKIPPED", f"{name} cannot be skipped for signoff closure.", report_paths.get(name, "")))

    result = {
        "schema_version": "oag_closure_super_gate.v1",
        "product_name": "IP Dev Agent",
        "internal_gateway": "Ontology Agent Gateway",
        "status": "fail" if issues else "pass",
        "closure_profile": profile_name,
        "ip_dir": str(ip_dir),
        "manifest": str(manifest_path) if manifest_path else None,
        "reports": report_paths,
        "report_hashes": report_hashes,
        "issues": issues,
    }
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ip-dir", required=True)
    parser.add_argument("--profile", choices=sorted(PROFILES), default="development")
    parser.add_argument("--manifest", help="Optional closure manifest JSON with required_reports.")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    manifest = Path(args.manifest).expanduser().resolve() if args.manifest else None
    result = check(Path(args.ip_dir), profile=args.profile, manifest_path=manifest)
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    elif result["status"] == "pass":
        print("PASS oag closure super-gate")
    else:
        print("FAIL oag closure super-gate")
        for item in result["issues"]:
            suffix = f" ({item['path']})" if item.get("path") else ""
            print(f"- {item['code']}: {item['message']}{suffix}")
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
