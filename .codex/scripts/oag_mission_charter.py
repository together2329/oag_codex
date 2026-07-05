#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib
import json
import sys
from pathlib import Path
from typing import Any

if __package__:
    from . import oag_paths
    from . import oag_run_control_common as run_common
else:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    oag_paths = importlib.import_module("oag_paths")
    run_common = importlib.import_module("oag_run_control_common")

SCHEMA_VERSION = "oag_mission_charter.v1"
RESULT_SCHEMA = "oag_mission_charter_result.v1"
GRANT_CLASSES = frozenset({"fact", "parameterizable", "architecture_tradeoff"})
ACTOR_KINDS = frozenset({"human", "ai"})

JsonObject = dict[str, Any]


def text(value: Any) -> str:
    return str(value or "").strip()


def charter_path(ip_dir: Path) -> Path:
    return oag_paths.legacy_or_hidden(ip_dir, "ontology/mission_charter.yaml")


def read_yaml(path: Path) -> JsonObject:
    if not path.is_file():
        return {}
    try:
        import yaml  # type: ignore
    except ImportError as exc:
        return {"__load_error__": f"PyYAML import failed: {exc}"}
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        return {"__load_error__": str(exc)}
    return data if isinstance(data, dict) else {"__load_error__": "mission charter root must be an object"}


def write_yaml(path: Path, data: JsonObject) -> None:
    import yaml  # type: ignore

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")


def actor(kind: str, actor_id: str) -> JsonObject:
    return {"kind": kind, "id": actor_id, "surface": "cli"}


def issue(code: str, message: str) -> JsonObject:
    return {"code": code, "message": message}


def result(status: str, ip_dir: Path, charter: JsonObject, issues: list[JsonObject]) -> JsonObject:
    path = charter_path(ip_dir)
    return {
        "schema_version": RESULT_SCHEMA,
        "status": status,
        "ip": ip_dir.name,
        "charter_path": run_common.rel_to_ip(ip_dir, path),
        "charter": charter,
        "issues": issues,
    }


def parse_grants(values: list[str]) -> tuple[list[JsonObject], list[JsonObject]]:
    grants: list[JsonObject] = []
    issues: list[JsonObject] = []
    for value in values:
        decision_class = text(value).lower()
        if decision_class == "product_defining":
            issues.append(issue("PRODUCT_DEFINING_GRANT_REFUSED", "product_defining grants require direct human decisions"))
            continue
        if decision_class not in GRANT_CLASSES:
            issues.append(issue("GRANT_CLASS_INVALID", f"unsupported grant class: {value}"))
            continue
        grants.append(
            {
                "id": f"GRANT_{decision_class.upper()}",
                "decision_class": decision_class,
                "granted": True,
                "rationale": "Mission charter proposal grant.",
                "scope": "bounded OAG operation planning",
            }
        )
    return grants, issues


def parse_weight_values(values: list[str]) -> tuple[JsonObject, list[JsonObject]]:
    weights: JsonObject = {}
    issues: list[JsonObject] = []
    for value in values:
        key, sep, raw = text(value).partition("=")
        if not sep or not key:
            issues.append(issue("OBJECTIVE_WEIGHT_INVALID", f"expected metric=value: {value}"))
            continue
        try:
            weight = float(raw)
        except ValueError:
            issues.append(issue("OBJECTIVE_WEIGHT_INVALID", f"weight must be numeric: {value}"))
            continue
        if weight < 0:
            issues.append(issue("OBJECTIVE_WEIGHT_INVALID", f"weight must be non-negative: {value}"))
            continue
        weights[key] = weight
    return weights, issues


def optional_budgets(args: argparse.Namespace) -> JsonObject:
    budgets: JsonObject = {}
    if args.max_candidates_tier1 is not None:
        budgets["max_candidates_tier1"] = args.max_candidates_tier1
    if args.max_sweep_points_per_parameter is not None:
        budgets["max_sweep_points_per_parameter"] = args.max_sweep_points_per_parameter
    if args.max_bench_wall_clock_sec is not None:
        budgets["max_bench_wall_clock_sec"] = args.max_bench_wall_clock_sec
    if args.max_worktrees is not None:
        budgets["max_worktrees"] = args.max_worktrees
    return budgets


def inert_charter(ip_dir: Path) -> JsonObject:
    return {
        "schema_version": "oag_mission_charter_absent.v1",
        "ip": ip_dir.name,
        "status": "absent",
        "approved": False,
        "autonomy": {"question_batching": "immediate", "grants": []},
        "approval": {"status": "pending", "approved": False, "actor": {"kind": "human", "id": ""}},
    }


def show(args: argparse.Namespace) -> JsonObject:
    ip_dir = oag_paths.ip_root(args.ip_dir)
    charter = read_yaml(charter_path(ip_dir))
    if not charter:
        return result("pass", ip_dir, inert_charter(ip_dir), [])
    if charter.get("__load_error__"):
        return result("fail", ip_dir, {}, [issue("CHARTER_LOAD_ERROR", text(charter.get("__load_error__")))])
    return result("pass", ip_dir, charter, [])


def propose(args: argparse.Namespace) -> JsonObject:
    ip_dir = oag_paths.ip_root(args.ip_dir)
    if args.actor_kind not in ACTOR_KINDS:
        return result("fail", ip_dir, {}, [issue("ACTOR_KIND_INVALID", f"unsupported actor kind: {args.actor_kind}")])
    grants, issues = parse_grants(args.grant)
    weights, weight_issues = parse_weight_values(args.objective_weight)
    issues.extend(weight_issues)
    if issues:
        return result("fail", ip_dir, {}, issues)
    budgets = optional_budgets(args)
    constraints = {
        "forbidden": [text(item) for item in args.constraint_forbidden if text(item)],
        "required": [text(item) for item in args.constraint_required if text(item)],
    }
    now = run_common.utc_now()
    charter = {
        "schema_version": SCHEMA_VERSION,
        "ip": ip_dir.name,
        "status": "proposed",
        "approved": False,
        "created_at": now,
        "updated_at": now,
        "actor": actor(args.actor_kind, args.actor_id),
        "autonomy": {"question_batching": args.question_batching, "grants": grants},
        "approval": {
            "status": "pending",
            "approved": False,
            "actor": actor("human", "pending"),
            "rationale": text(args.rationale),
        },
    }
    if budgets:
        charter["budgets"] = budgets
    if weights:
        charter["objective_weights"] = weights
    if constraints["forbidden"] or constraints["required"]:
        charter["constraints"] = constraints
    write_yaml(charter_path(ip_dir), charter)
    return result("pass", ip_dir, charter, [])


def approve(args: argparse.Namespace) -> JsonObject:
    ip_dir = oag_paths.ip_root(args.ip_dir)
    charter = read_yaml(charter_path(ip_dir))
    if not charter:
        return result("fail", ip_dir, {}, [issue("CHARTER_MISSING", "mission charter must be proposed before approval")])
    if charter.get("__load_error__"):
        return result("fail", ip_dir, {}, [issue("CHARTER_LOAD_ERROR", text(charter.get("__load_error__")))])
    if args.actor_kind != "human":
        return result("fail", ip_dir, charter, [issue("HUMAN_APPROVAL_REQUIRED", "mission charter approval requires actor kind human")])
    grants = charter.get("autonomy", {}).get("grants", []) if isinstance(charter.get("autonomy"), dict) else []
    _, issues = parse_grants([text(item.get("decision_class")) for item in grants if isinstance(item, dict)])
    if issues:
        return result("fail", ip_dir, charter, issues)
    now = run_common.utc_now()
    charter["status"] = "approved"
    charter["approved"] = True
    charter["updated_at"] = now
    charter["approval"] = {
        "status": "approved",
        "approved": True,
        "actor": actor("human", args.actor_id),
        "approved_at": now,
        "rationale": text(args.rationale),
    }
    write_yaml(charter_path(ip_dir), charter)
    return result("pass", ip_dir, charter, [])


def revoke(args: argparse.Namespace) -> JsonObject:
    ip_dir = oag_paths.ip_root(args.ip_dir)
    charter = read_yaml(charter_path(ip_dir))
    if not charter:
        return result("pass", ip_dir, inert_charter(ip_dir), [])
    if charter.get("__load_error__"):
        return result("fail", ip_dir, {}, [issue("CHARTER_LOAD_ERROR", text(charter.get("__load_error__")))])
    now = run_common.utc_now()
    charter["status"] = "revoked"
    charter["approved"] = False
    charter["updated_at"] = now
    charter["approval"] = {
        "status": "revoked",
        "approved": False,
        "actor": actor(args.actor_kind, args.actor_id),
        "revoked_at": now,
        "rationale": text(args.rationale),
    }
    write_yaml(charter_path(ip_dir), charter)
    return result("pass", ip_dir, charter, [])


def print_result(payload: JsonObject, as_json: bool) -> None:
    if as_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
        return
    if payload.get("status") == "pass":
        print(f"PASS {RESULT_SCHEMA}: {payload.get('charter_path')}")
        return
    print(f"FAIL {RESULT_SCHEMA}", file=sys.stderr)
    for item in payload.get("issues", []):
        print(f"- {item.get('code')}: {item.get('message')}", file=sys.stderr)


def add_common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--ip-dir", required=True)
    parser.add_argument("--json", action="store_true")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Create and manage an OAG mission charter.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    show_parser = subparsers.add_parser("show")
    add_common(show_parser)
    show_parser.set_defaults(func=show)

    propose_parser = subparsers.add_parser("propose")
    add_common(propose_parser)
    propose_parser.add_argument("--actor-kind", choices=sorted(ACTOR_KINDS), default="ai")
    propose_parser.add_argument("--actor-id", default="oag_mission_charter")
    propose_parser.add_argument("--question-batching", choices=["immediate", "checkpoint"], default="immediate")
    propose_parser.add_argument("--grant", action="append", default=[])
    propose_parser.add_argument("--max-candidates-tier1", type=int)
    propose_parser.add_argument("--max-sweep-points-per-parameter", type=int)
    propose_parser.add_argument("--max-bench-wall-clock-sec", type=float)
    propose_parser.add_argument("--max-worktrees", type=int)
    propose_parser.add_argument("--objective-weight", action="append", default=[])
    propose_parser.add_argument("--constraint-forbidden", action="append", default=[])
    propose_parser.add_argument("--constraint-required", action="append", default=[])
    propose_parser.add_argument("--rationale", default="")
    propose_parser.set_defaults(func=propose)

    approve_parser = subparsers.add_parser("approve")
    add_common(approve_parser)
    approve_parser.add_argument("--actor-kind", choices=sorted(ACTOR_KINDS), required=True)
    approve_parser.add_argument("--actor-id", default="human")
    approve_parser.add_argument("--rationale", default="")
    approve_parser.set_defaults(func=approve)

    revoke_parser = subparsers.add_parser("revoke")
    add_common(revoke_parser)
    revoke_parser.add_argument("--actor-kind", choices=sorted(ACTOR_KINDS), default="ai")
    revoke_parser.add_argument("--actor-id", default="oag_mission_charter")
    revoke_parser.add_argument("--rationale", default="")
    revoke_parser.set_defaults(func=revoke)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    payload = args.func(args)
    print_result(payload, args.json)
    return 0 if payload.get("status") == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
