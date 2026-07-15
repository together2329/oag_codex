#!/usr/bin/env python3
"""Check phase-aware OAG semantic projection safety pins."""

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
from oag_validate_json import contextual_schema_issues  # noqa: E402


PHASES = {"draft", "lock", "closure"}
AUTHORITY_REQUIRED_CLASSES = {"narrowed", "broadened", "defaulted"}
READY_STATUSES = {"ready", "waived"}
LOCKED_STATUSES = {"locked", "ready", "closed", "complete", "validated", "pass", "passed", "signoff"}
LOAD_BEARING_LAYERS = {"rtl", "tb", "contract", "contracts", "evidence", "validation", "closure", "signoff"}
REF_SOURCE_PATHS = {
    "source_claim_refs": "req/source_claims.yaml",
    "requirement_refs": "ontology/requirements.yaml",
    "atom_refs": "ontology/requirement_atoms.yaml",
    "obligation_refs": "ontology/obligations.yaml",
    "contract_refs": "ontology/contracts.yaml",
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


def str_items(value: Any) -> list[str]:
    return [str(item).strip() for item in as_list(value) if str(item).strip()]


def text(value: Any) -> str:
    return str(value or "").strip()


def item_id(item: Any) -> str:
    if not isinstance(item, dict):
        return ""
    return text(item.get("id") or item.get("contract_id") or item.get("obligation_id"))


def issue(code: str, message: str, path: str = "") -> dict[str, str]:
    payload = {"code": code, "message": message}
    if path:
        payload["path"] = path
    return payload


def is_locked(ip_dir: Path) -> bool:
    scope = read_json(oag_paths.legacy_or_hidden(ip_dir, "ontology/scope_lock.json"))
    return scope.get("state") == "locked"


def semantic_projection_path(ip_dir: Path) -> Path:
    for rel in ("ontology/semantic_projection.yaml", "ontology/semantic_projection.json"):
        path = oag_paths.legacy_or_hidden(ip_dir, rel)
        if path.is_file():
            return path
    return oag_paths.legacy_or_hidden(ip_dir, "ontology/semantic_projection.yaml")


def load_projection_doc(path: Path) -> dict[str, Any]:
    if path.suffix.lower() == ".json":
        return read_json(path)
    return read_yaml(path)


def yaml_items(ip_dir: Path, rel: str, key: str) -> list[dict[str, Any]]:
    doc = read_yaml(oag_paths.legacy_or_hidden(ip_dir, rel))
    return [item for item in as_list(doc.get(key)) if isinstance(item, dict)] if isinstance(doc, dict) else []


def status(item: dict[str, Any]) -> str:
    return text(item.get("status") or item.get("validation_status") or item.get("decision_status")).lower()


def explicit_load_bearing(item: dict[str, Any]) -> bool:
    if item.get("load_bearing") is True:
        return True
    if item.get("closure_grade") is True or item.get("signoff_grade") is True:
        return True
    layers = {entry.lower() for entry in str_items(item.get("affected_layers"))}
    return bool(layers & LOAD_BEARING_LAYERS)


def load_bearing_object(item: dict[str, Any]) -> bool:
    if explicit_load_bearing(item):
        return True
    return status(item) in LOCKED_STATUSES


def collect_required_refs(ip_dir: Path) -> dict[str, set[str]]:
    claims = yaml_items(ip_dir, "req/source_claims.yaml", "claims")
    requirements = yaml_items(ip_dir, "ontology/requirements.yaml", "requirements")
    atoms = yaml_items(ip_dir, "ontology/requirement_atoms.yaml", "requirement_atoms")
    obligations = yaml_items(ip_dir, "ontology/obligations.yaml", "obligations")
    contracts = yaml_items(ip_dir, "ontology/contracts.yaml", "contracts")
    return {
        "source_claim_refs": {item_id(item) for item in claims if item_id(item) and load_bearing_object(item)},
        "requirement_refs": {item_id(item) for item in requirements if item_id(item) and load_bearing_object(item)},
        "atom_refs": {item_id(item) for item in atoms if item_id(item) and load_bearing_object(item)},
        "obligation_refs": {item_id(item) for item in obligations if item_id(item) and load_bearing_object(item)},
        "contract_refs": {item_id(item) for item in contracts if item_id(item) and load_bearing_object(item)},
    }


def projection_ref_sets(projections: list[dict[str, Any]]) -> dict[str, set[str]]:
    covered: dict[str, set[str]] = {
        "source_claim_refs": set(),
        "requirement_refs": set(),
        "atom_refs": set(),
        "obligation_refs": set(),
        "contract_refs": set(),
    }
    for projection in projections:
        for key in covered:
            covered[key].update(str_items(projection.get(key)))
    return covered


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def stale_input_hash_issues(ip_dir: Path, projection: dict[str, Any], base: str, *, required: bool) -> list[dict[str, str]]:
    raw = projection.get("input_hashes")
    if not isinstance(raw, dict):
        return [issue("SEMANTIC_PROJECTION_INPUT_HASHES_REQUIRED", "Load-bearing semantic projection needs input_hashes.", base)] if required else []
    issues: list[dict[str, str]] = []
    required_paths = {
        rel
        for key, rel in REF_SOURCE_PATHS.items()
        if str_items(projection.get(key))
    }
    missing_hashes = sorted(required_paths - {text(key) for key in raw})
    for rel in missing_hashes:
        issues.append(issue("SEMANTIC_PROJECTION_INPUT_HASH_MISSING", f"{rel} must be hash-bound by this projection.", base))
    for rel, expected in raw.items():
        rel_text = text(rel)
        expected_text = text(expected)
        if not rel_text or not expected_text:
            continue
        candidate = oag_paths.legacy_or_hidden(ip_dir, rel_text)
        try:
            path = candidate.resolve(strict=False)
            path.relative_to(ip_dir.resolve())
        except Exception:
            issues.append(issue("SEMANTIC_PROJECTION_INPUT_OUTSIDE_IP", f"{rel_text} resolves outside the IP workspace.", base))
            continue
        if not path.is_file():
            issues.append(issue("SEMANTIC_PROJECTION_INPUT_MISSING", f"{rel_text} referenced by projection input_hashes is missing.", base))
            continue
        if len(expected_text) != 64 or any(char not in "0123456789abcdefABCDEF" for char in expected_text):
            issues.append(issue("SEMANTIC_PROJECTION_INPUT_HASH_INVALID", f"{rel_text} needs a full SHA-256 digest.", base))
            continue
        current = sha256(path)
        if current != expected_text:
            issues.append(issue("SEMANTIC_PROJECTION_INPUT_STALE", f"{rel_text} hash changed after semantic projection.", base))
    return issues


def classify_phase(raw_phase: str | None, ip_dir: Path) -> str:
    if raw_phase:
        phase = raw_phase.lower()
        if phase in PHASES:
            return phase
    return "lock" if is_locked(ip_dir) else "draft"


def check(ip_dir: Path, *, phase: str | None = None) -> dict[str, Any]:
    ip_dir = oag_paths.ip_root(ip_dir)
    phase_name = classify_phase(phase, ip_dir)
    hard_gate = phase_name in {"lock", "closure"}
    path = semantic_projection_path(ip_dir)
    doc = load_projection_doc(path)
    issues: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []

    if "__load_error__" in doc:
        issues.append(issue("SEMANTIC_PROJECTION_FILE_INVALID", f"Cannot read semantic projection: {doc['__load_error__']}", str(path)))
        doc = {}

    if not doc:
        target = issues if hard_gate else warnings
        target.append(issue("SEMANTIC_PROJECTION_MISSING", "Add ontology/semantic_projection.yaml before lock/closure consumes load-bearing ontology.", str(path)))
        projections: list[dict[str, Any]] = []
    else:
        projections = [item for item in as_list(doc.get("projections")) if isinstance(item, dict)]
        schema_issues = contextual_schema_issues(
            "oag_semantic_projection.schema.json",
            doc,
            code_prefix="SEMANTIC_PROJECTION_SCHEMA",
            document_path=str(path),
        )
        (issues if hard_gate else warnings).extend(schema_issues)
        if doc.get("schema_version") != "oag_semantic_projection.v1":
            (issues if hard_gate else warnings).append(
                issue("SEMANTIC_PROJECTION_SCHEMA_VERSION", "semantic_projection must use schema_version oag_semantic_projection.v1.", str(path))
            )

    covered = projection_ref_sets(projections)
    required = collect_required_refs(ip_dir) if hard_gate else {key: set() for key in covered}
    decision_refs = {
        item_id(item)
        for item in yaml_items(ip_dir, "ontology/decision_matrix.yaml", "decisions")
        if item_id(item)
    }
    for key, refs in required.items():
        missing = sorted(refs - covered.get(key, set()))
        for ref in missing:
            issues.append(issue("SEMANTIC_PROJECTION_REQUIRED_REF_MISSING", f"Load-bearing {key[:-5]} {ref} has no semantic projection row.", key))

    seen: set[str] = set()
    for index, projection in enumerate(projections):
        base = f"projections[{index}]"
        pid = item_id(projection) or base
        if pid in seen:
            (issues if hard_gate else warnings).append(issue("SEMANTIC_PROJECTION_DUPLICATE_ID", f"Duplicate semantic projection id {pid}.", base))
        seen.add(pid)
        pclass = text(projection.get("projection_class")).lower()
        pstatus = status(projection)
        target = issues if hard_gate else warnings
        if projection.get("load_bearing") is not True and hard_gate:
            target.append(issue("SEMANTIC_PROJECTION_LOAD_BEARING", f"{pid} must mark load_bearing=true before lock/closure use.", base))
        authority_ref = text(projection.get("authority_ref"))
        if pclass in AUTHORITY_REQUIRED_CLASSES and not authority_ref:
            target.append(issue("SEMANTIC_PROJECTION_AUTHORITY_REF", f"{pid} projection_class={pclass} needs authority_ref.", base))
        elif pclass in AUTHORITY_REQUIRED_CLASSES and hard_gate and authority_ref not in decision_refs:
            issues.append(issue("SEMANTIC_PROJECTION_AUTHORITY_UNRESOLVED", f"{pid} authority_ref={authority_ref} does not resolve in decision_matrix.yaml.", base))
        populated_layers = sum(bool(str_items(projection.get(key))) for key in REF_SOURCE_PATHS)
        if hard_gate and populated_layers < 2:
            issues.append(issue("SEMANTIC_PROJECTION_CHAIN_INCOMPLETE", f"{pid} must connect at least two semantic layers.", base))
        if pclass == "blocked" or pstatus == "blocked":
            feeds = any(str_items(projection.get(key)) for key in ("atom_refs", "obligation_refs", "contract_refs"))
            if feeds and hard_gate:
                issues.append(issue("SEMANTIC_PROJECTION_BLOCKED_FEEDS_IMPLEMENTATION", f"{pid} is blocked but feeds implementation/closure objects.", base))
        if hard_gate:
            issues.extend(stale_input_hash_issues(ip_dir, projection, base, required=projection.get("load_bearing") is True))
        if phase_name == "closure":
            if pstatus not in READY_STATUSES:
                issues.append(issue("SEMANTIC_PROJECTION_NOT_READY", f"{pid} must be ready or waived for closure.", base))

    next_actions: list[str] = []
    if issues:
        next_actions.append("Add or repair semantic projection rows for locked/load-bearing source, atom, obligation, and contract objects.")
    elif warnings:
        next_actions.append("Semantic projection is advisory in draft; resolve warnings before lock.")
    else:
        next_actions.append("Semantic projection safety pins are phase-appropriate.")

    return {
        "schema_version": "oag_semantic_projection_check.v1",
        "status": "fail" if issues else "pass",
        "ip": ip_dir.name,
        "phase": phase_name,
        "hard_gate": hard_gate,
        "scope_locked": is_locked(ip_dir),
        "semantic_projection": str(path),
        "counts": {
            "projections": len(projections),
            "required_refs": sum(len(refs) for refs in required.values()),
            "issues": len(issues),
            "warnings": len(warnings),
        },
        "issues": issues,
        "warnings": warnings,
        "next_actions": next_actions,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ip-dir", required=True)
    parser.add_argument("--phase", choices=sorted(PHASES), help="draft warns; lock/closure hard-fail load-bearing gaps.")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    result = check(Path(args.ip_dir), phase=args.phase)
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    elif result["status"] == "pass":
        print("PASS oag semantic projection check")
    else:
        print("FAIL oag semantic projection check")
        for item in result["issues"]:
            path = f" {item['path']}" if item.get("path") else ""
            print(f"- {item['code']}:{path} {item['message']}")
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
