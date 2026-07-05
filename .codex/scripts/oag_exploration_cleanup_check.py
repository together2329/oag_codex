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

oag_paths = importlib.import_module("oag_paths")
run_common = importlib.import_module("oag_run_control_common")
oag_parameter_sweep = importlib.import_module("oag_parameter_sweep")
oag_dse_worktree = importlib.import_module("oag_dse_worktree")

SCHEMA_VERSION: Final = "oag_exploration_cleanup_check.v1"
ARCH_REF: Final = "knowledge/arch_exploration"
PROVISIONAL_MARKERS: Final = ("OAG-BEGIN-PROVISIONAL", "OAG-END-PROVISIONAL")
PRODUCT_DIRS: Final = (
    "rtl",
    "tb",
    "req",
    "ontology",
    "list",
    "sim",
    "lint",
    "formal",
    "syn",
    "sdc",
    "doc",
    "signoff",
)
SELECTED_STATUSES: Final = {"selected", "promoted", "collapsed"}
PRUNED_STATUSES: Final = {"pruned", "archived"}
SKIP_DIRS: Final = {".git", "__pycache__", "generated"}

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


def read_json(path: Path) -> JsonObject:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


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
            return {}
        try:
            data = yaml.safe_load(raw) or {}
        except yaml.YAMLError:
            return {}
    return data if isinstance(data, dict) else {}


def rel_to_ip(ip_dir: Path, path: Path) -> str:
    rel = run_common.rel_to_ip(ip_dir, path)
    if rel.startswith(".oag/"):
        return rel.removeprefix(".oag/")
    return rel


def state_dirs(ip_dir: Path, rel: str) -> list[Path]:
    return run_common.state_dirs(ip_dir, rel)


def exploration_dirs(ip_dir: Path) -> list[Path]:
    return state_dirs(ip_dir, ARCH_REF)


def has_exploration_artifacts(ip_dir: Path) -> bool:
    return any(any(path.is_file() for path in root.rglob("*")) for root in exploration_dirs(ip_dir))


def candidate_docs(ip_dir: Path) -> list[tuple[Path, JsonObject]]:
    docs: list[tuple[Path, JsonObject]] = []
    for root in exploration_dirs(ip_dir):
        for path in sorted(root.glob("*/candidates.json")):
            docs.append((path, read_json(path)))
    return docs


def candidate_rows(doc: JsonObject) -> list[JsonObject]:
    return [item for item in as_list(doc.get("candidates")) if isinstance(item, dict)]


def candidate_id(row: JsonObject, index: int) -> str:
    return text(row.get("id") or row.get("candidate_id") or f"candidate[{index}]")


def check_candidate_collapse(ip_dir: Path, docs: list[tuple[Path, JsonObject]]) -> tuple[list[dict[str, str]], list[str]]:
    issues: list[dict[str, str]] = []
    selected: list[str] = []
    if not docs:
        return [issue("EXPLORATION_CANDIDATES_MISSING", "exploration artifacts exist but no candidates.json files were found", ARCH_REF)], selected
    for path, doc in docs:
        rows = candidate_rows(doc)
        rel = rel_to_ip(ip_dir, path)
        if not rows:
            issues.append(issue("EXPLORATION_CANDIDATES_EMPTY", "candidates.json has no candidate rows", rel))
            continue
        for index, row in enumerate(rows):
            cid = candidate_id(row, index)
            status = text(row.get("status") or row.get("lifecycle")).lower()
            if status in SELECTED_STATUSES or row.get("selected") is True or row.get("promoted") is True or row.get("collapsed") is True:
                selected.append(cid)
                continue
            if status in PRUNED_STATUSES and text(row.get("pruned_reason") or row.get("archive_reason")):
                continue
            issues.append(
                issue(
                    "EXPLORATION_CANDIDATE_UNPRUNED",
                    f"unselected candidate {cid} must be pruned or archived with pruned_reason",
                    f"{rel}#{cid}",
                )
            )
    if not selected:
        issues.append(issue("EXPLORATION_SELECTION_MISSING", "exploration cleanup needs a selected, promoted, or collapsed candidate", ARCH_REF))
    return issues, selected


def retained_generate_options(docs: list[tuple[Path, JsonObject]]) -> list[tuple[Path, str, JsonObject]]:
    rows: list[tuple[Path, str, JsonObject]] = []
    for path, doc in docs:
        for index, candidate in enumerate(candidate_rows(doc)):
            cid = candidate_id(candidate, index)
            for option in as_list(candidate.get("generate_options")):
                if isinstance(option, dict) and oag_parameter_sweep.has_generate_retention(option):
                    rows.append((path, cid, option))
            generate = candidate.get("generate_option")
            if isinstance(generate, dict) and oag_parameter_sweep.has_generate_retention(generate):
                rows.append((path, cid, generate))
    return rows


def check_generate_options(ip_dir: Path, docs: list[tuple[Path, JsonObject]]) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    vplan_ids = verification_plan_config_ids(ip_dir)
    for path, cid, option in retained_generate_options(docs):
        for item in oag_parameter_sweep.generate_option_issues(option, 0):
            rel = rel_to_ip(ip_dir, path)
            issues.append(issue(item["code"], f"candidate {cid}: {item['message']}", f"{rel}#{cid}"))
        mapping = verification_mapping_ref(option)
        if mapping and vplan_ids and mapping not in vplan_ids:
            rel = rel_to_ip(ip_dir, path)
            issues.append(
                issue(
                    "GENERATE_OPTION_VERIFICATION_MAPPING_UNKNOWN",
                    f"candidate {cid}: verification plan config mapping {mapping} is not defined",
                    f"{rel}#{cid}",
                )
            )
        elif mapping and not vplan_ids:
            issues.append(
                issue(
                    "GENERATE_OPTION_VERIFICATION_PLAN_MISSING",
                    f"candidate {cid}: retained generate option needs ontology/verification_plan.yaml config entries",
                    "ontology/verification_plan.yaml",
                )
            )
    return issues


def verification_mapping_ref(option: JsonObject) -> str:
    raw = text(option.get("verification_plan_config_mapping") or option.get("verification_mapping_ref") or option.get("vplan_config_mapping"))
    return raw.split("#", maxsplit=1)[-1] if raw else ""


def collect_config_ids(value: Any) -> set[str]:
    found: set[str] = set()
    if isinstance(value, dict):
        for key in ("id", "name", "config_id", "configuration_id", "verification_plan_config_mapping"):
            ident = text(value.get(key))
            if ident:
                found.add(ident)
        for child in value.values():
            found.update(collect_config_ids(child))
    elif isinstance(value, list):
        for child in value:
            found.update(collect_config_ids(child))
    return found


def verification_plan_config_ids(ip_dir: Path) -> set[str]:
    plan = read_structured(oag_paths.legacy_or_hidden(ip_dir, "ontology/verification_plan.yaml"))
    if not plan:
        return set()
    roots = [
        plan.get("configurations"),
        plan.get("verification_configurations"),
        plan.get("config_matrix"),
        plan.get("configs"),
        plan.get("verification_objectives"),
    ]
    ids: set[str] = set()
    for root in roots:
        ids.update(collect_config_ids(root))
    expanded = set(ids)
    for ident in ids:
        expanded.add(ident.split("#", maxsplit=1)[-1])
    return expanded


def iter_authored_product_files(ip_dir: Path) -> list[Path]:
    files: list[Path] = []
    for rel in PRODUCT_DIRS:
        roots = state_dirs(ip_dir, rel) if rel in {"ontology", "req"} else [ip_dir / rel]
        for root in roots:
            if not root.exists():
                continue
            candidates = [root] if root.is_file() else sorted(path for path in root.rglob("*") if path.is_file())
            for path in candidates:
                if any(part in SKIP_DIRS for part in path.parts):
                    continue
                files.append(path)
    return sorted(set(files))


def read_text_or_skip(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None


def check_product_leaks(ip_dir: Path) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    for path in iter_authored_product_files(ip_dir):
        content = read_text_or_skip(path)
        if content is None:
            continue
        rel = rel_to_ip(ip_dir, path)
        for marker in PROVISIONAL_MARKERS:
            if marker in content:
                issues.append(issue("PROVISIONAL_MARKER_IN_PRODUCT", f"authored/product file still contains {marker}", rel))
        if ARCH_REF in content:
            issues.append(issue("PRODUCT_ARCH_EXPLORATION_REFERENCE", "authored/product file references knowledge/arch_exploration", rel))
    return issues


def check_worktrees(ip_dir: Path) -> list[dict[str, str]]:
    root = ip_dir / ".oag_worktrees"
    if not root.exists():
        return []
    entries = [path for path in sorted(root.iterdir()) if path.name not in {".DS_Store"}]
    if not entries:
        return []
    return [
        issue(
            "DSE_WORKTREE_STALE",
            ".oag_worktrees contains stale exploration worktrees; prune or archive before lock",
            rel_to_ip(ip_dir, path),
        )
        for path in entries
    ]


def check_dse_branches(ip_dir: Path) -> list[dict[str, str]]:
    branches = oag_dse_worktree.list_dse_branches(ip_dir)
    return [
        issue(
            "DSE_BRANCH_STALE",
            "git branch under oag/dse remains after exploration; prune before lock",
            branch,
        )
        for branch in branches
    ]


def decision_matrix(ip_dir: Path) -> JsonObject:
    return read_structured(oag_paths.legacy_or_hidden(ip_dir, "ontology/decision_matrix.yaml"))


def decision_rows(ip_dir: Path) -> list[JsonObject]:
    matrix = decision_matrix(ip_dir)
    return [item for item in as_list(matrix.get("decisions")) if isinstance(item, dict)]


def has_public_parameter_rationale(row: JsonObject) -> bool:
    for key in ("public_parameter_rationale", "parameter_rationale", "product_rationale", "rationale"):
        if text(row.get(key)):
            return True
    return False


def row_declares_public_parameter(row: JsonObject) -> bool:
    if row.get("public_parameter") is True:
        return True
    if text(row.get("parameter_scope")).lower() in {"public", "external", "integration"}:
        return True
    if text(row.get("parameter_visibility")).lower() in {"public", "external", "integration"}:
        return True
    return text(row.get("representation")).lower() == "parameter" and text(row.get("external_contract_impact")).lower() in {"indirect", "direct"}


def check_public_parameter_rationales(ip_dir: Path, docs: list[tuple[Path, JsonObject]]) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    for index, row in enumerate(decision_rows(ip_dir)):
        did = text(row.get("id") or f"decisions[{index}]")
        if row_declares_public_parameter(row) and not has_public_parameter_rationale(row):
            issues.append(issue("PUBLIC_PARAMETER_RATIONALE_MISSING", f"public parameter decision {did} needs a product rationale", f"ontology/decision_matrix.yaml#{did}"))
    for path, doc in docs:
        rel = rel_to_ip(ip_dir, path)
        for c_index, candidate in enumerate(candidate_rows(doc)):
            cid = candidate_id(candidate, c_index)
            raw_parameters = candidate.get("parameter_draft")
            parameters = raw_parameters if isinstance(raw_parameters, dict) else {}
            for name, value in parameters.items():
                if isinstance(value, dict) and value.get("public") is True and not text(value.get("rationale") or value.get("product_rationale")):
                    issues.append(issue("PUBLIC_PARAMETER_RATIONALE_MISSING", f"candidate {cid} public parameter {name} needs a product rationale", f"{rel}#{cid}.{name}"))
    return issues


def checkpoint_review_started(ip_dir: Path) -> bool:
    state = read_json(oag_paths.legacy_or_hidden(ip_dir, "knowledge/mission_loop/pending_questions.json"))
    status = text(state.get("status")).lower()
    if status in {"checkpoint_ready", "answered", "abandoned"}:
        return True
    return state.get("checkpoint_ready") is True


def check_provisional_decisions(ip_dir: Path) -> list[dict[str, str]]:
    if not checkpoint_review_started(ip_dir):
        return []
    issues: list[dict[str, str]] = []
    for index, row in enumerate(decision_rows(ip_dir)):
        if row.get("provisional") is True:
            did = text(row.get("id") or f"decisions[{index}]")
            issues.append(issue("PROVISIONAL_DECISION_REMAINS", f"{did} is still provisional after checkpoint review started", f"ontology/decision_matrix.yaml#{did}"))
    return issues


def check(ip_dir: Path) -> JsonObject:
    ip_dir = oag_paths.ip_root(ip_dir)
    present = has_exploration_artifacts(ip_dir)
    docs = candidate_docs(ip_dir) if present else []
    selection_issues, selected = check_candidate_collapse(ip_dir, docs) if present else ([], [])
    issues = (
        selection_issues
        + check_generate_options(ip_dir, docs)
        + check_public_parameter_rationales(ip_dir, docs)
        + check_provisional_decisions(ip_dir)
        + check_product_leaks(ip_dir)
        + check_worktrees(ip_dir)
        + check_dse_branches(ip_dir)
    )
    cleanup_state = "blocked" if issues else "ready" if present else "neutral"
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "fail" if issues else "pass",
        "cleanup_state": cleanup_state,
        "ip": ip_dir.name,
        "exploration_present": present,
        "selected_candidates": selected,
        "counts": {
            "candidate_docs": len(docs),
            "selected_candidates": len(selected),
            "issues": len(issues),
        },
        "issues": issues,
        "next_actions": [] if not issues else [
            "Select, promote, or collapse one architecture candidate.",
            "Prune or archive all unselected candidates with pruned_reason.",
            "Resolve public parameter rationales and provisional decision rows before lock.",
            "Remove provisional markers and exploration references from authored/product paths.",
            "Prune stale .oag_worktrees entries and oag/dse/* branches.",
            "Map retained generate options to decision, configuration model, and verification plan config entries.",
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check that architecture exploration has been cleaned before scope lock.")
    parser.add_argument("--ip-dir", required=True)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    result = check(Path(args.ip_dir))
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    elif result["status"] == "pass":
        print(f"PASS {SCHEMA_VERSION}: cleanup_state={result['cleanup_state']}")
    else:
        print(f"FAIL {SCHEMA_VERSION}", file=sys.stderr)
        for item in result["issues"]:
            print(f"- {item.get('code')}: {item.get('message')}", file=sys.stderr)
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
