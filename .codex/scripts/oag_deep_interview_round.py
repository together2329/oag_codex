#!/usr/bin/env python3
"""Build, validate, and render one-question OAG deep-interview rounds."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "oag_deep_interview_round.v1"
CHECK_SCHEMA_VERSION = "oag_deep_interview_round_check.v1"
RANK_SCHEMA_VERSION = "oag_deep_interview_rank.v1"
VALID_DIMENSIONS = {"topology", "goal", "constraints", "criteria", "context", "closure"}
VALID_DECISION_EFFECTS = {"none", "unresolved", "proposed", "decided", "waiver_or_deferral", "free_text"}

IMPORTANCE_WEIGHTS: tuple[tuple[str, float], ...] = (
    ("lock_blocker", 3.0),
    ("ssot_required_gap", 2.0),
    ("downstream_fanout", 2.0),
    ("irreversibility", 2.0),
    ("ambiguity_gap", 1.0),
    ("proof_gap", 2.0),
    ("contradiction_risk", 2.0),
    ("user_value", 1.0),
    ("brownfield_risk", 1.0),
    ("upstream_dependency", 1.0),
)
NEGATIVE_IMPORTANCE_WEIGHTS: tuple[tuple[str, float], ...] = (
    ("researchable_fact", 2.0),
)

OPTION_PATTERNS: dict[str, list[tuple[str, str, str]]] = {
    "topology": [
        ("Looks right", "Use this as the draft topology for scoring.", "proposed"),
        ("Add/remove/merge components", "Revise topology before scoring starts.", "unresolved"),
        ("Defer component", "Keep a component visible but out of v0 scope.", "waiver_or_deferral"),
        ("Other / refine", "Supply the exact topology correction.", "free_text"),
    ],
    "goal": [
        ("Recommended behavior", "Smallest behavior that appears to satisfy the current scope.", "proposed"),
        ("Narrower behavior", "Reduce v0 scope and leave expansion explicit.", "proposed"),
        ("Explicitly unsupported", "Exclude this behavior and record the non-goal.", "waiver_or_deferral"),
        ("Other / refine", "Supply the exact behavior in your words.", "free_text"),
    ],
    "constraints": [
        ("Recommended boundary", "Keeps the boundary concrete without expanding scope.", "proposed"),
        ("Stricter boundary", "Reduces implementation and proof surface.", "proposed"),
        ("Defer or waive boundary", "Leaves a visible lock/readiness risk.", "waiver_or_deferral"),
        ("Other / refine", "Supply a different boundary or constraint.", "free_text"),
    ],
    "criteria": [
        ("Scoreboard-first proof", "Best for externally observable behavior.", "proposed"),
        ("Assertion/coverage proof", "Best for local invariants and corner cases.", "proposed"),
        ("Review-only with risk", "Faster, but weaker closure evidence.", "waiver_or_deferral"),
        ("Other / refine", "Supply another proof shape.", "free_text"),
    ],
    "context": [
        ("Extend existing path", "Reuse the observed brownfield boundary.", "proposed"),
        ("Create new boundary", "Separates the feature but increases integration scope.", "unresolved"),
        ("Defer until source review", "Avoids guessing while keeping the gap visible.", "waiver_or_deferral"),
        ("Other / refine", "Supply a different mapping.", "free_text"),
    ],
    "closure": [
        ("Approve for lock-readiness review", "Proceed to readiness checks with current draft facts.", "proposed"),
        ("Adjust wording", "Fix the scope statement before closure.", "unresolved"),
        ("Missing scope", "Return to interview for the omitted behavior.", "unresolved"),
        ("Other / refine", "Supply the exact closure correction.", "free_text"),
    ],
}


def load_json(path: str) -> dict[str, Any]:
    try:
        raw = sys.stdin.read() if path == "-" else Path(path).read_text(encoding="utf-8")
        data = json.loads(raw)
    except Exception as exc:
        raise SystemExit(f"cannot read round JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise SystemExit("round JSON must be an object")
    return data


def dump_json(data: dict[str, Any]) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True))


def _text(value: Any) -> str:
    return str(value or "").strip()


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def _number(value: Any, *, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _clamp(value: float, low: float = 0.0, high: float = 3.0) -> float:
    return max(low, min(high, value))


def _candidate_ambiguity_gap(candidate: dict[str, Any]) -> float:
    if "ambiguity_gap" in candidate:
        return _clamp(_number(candidate.get("ambiguity_gap")))
    if "clarity" in candidate:
        clarity = max(0.0, min(1.0, _number(candidate.get("clarity"), default=0.0)))
        return _clamp((1.0 - clarity) * 3.0)
    return 0.0


def _ranked_candidate(candidate: dict[str, Any], index: int) -> tuple[dict[str, Any], tuple[float, float, float, float, float, float, int]]:
    breakdown: dict[str, float] = {}
    weighted_score = 0.0
    for field, weight in IMPORTANCE_WEIGHTS:
        raw = _candidate_ambiguity_gap(candidate) if field == "ambiguity_gap" else _clamp(_number(candidate.get(field)))
        breakdown[field] = round(raw, 3)
        weighted_score += raw * weight
    for field, weight in NEGATIVE_IMPORTANCE_WEIGHTS:
        raw = _clamp(_number(candidate.get(field)))
        breakdown[field] = round(raw, 3)
        weighted_score -= raw * weight

    ranked = dict(candidate)
    ranked["id"] = _text(candidate.get("id")) or f"C{index + 1}"
    ranked["component"] = _text(candidate.get("component"))
    ranked["dimension"] = _text(candidate.get("dimension")).lower()
    ranked["importance_score"] = round(weighted_score, 3)
    ranked["score_breakdown"] = breakdown
    tie_breaker = (
        -weighted_score,
        -breakdown["lock_blocker"],
        -breakdown["ssot_required_gap"],
        -breakdown["downstream_fanout"],
        -breakdown["upstream_dependency"],
        breakdown["researchable_fact"],
        index,
    )
    return ranked, tie_breaker


def build_template(args: argparse.Namespace) -> dict[str, Any]:
    dimension = str(args.dimension or "").strip().lower()
    if dimension not in OPTION_PATTERNS:
        raise SystemExit(f"unsupported dimension: {dimension}")
    options: list[dict[str, Any]] = []
    for idx, (label, tradeoff, effect) in enumerate(OPTION_PATTERNS[dimension]):
        option_id = chr(ord("A") + idx)
        options.append(
            {
                "id": option_id,
                "label": label,
                "recommended": option_id == "A",
                "tradeoff": tradeoff,
                "decision_effect": effect,
                "affects": [],
                "decision_matrix_ref": "",
            }
        )
    return {
        "schema_version": SCHEMA_VERSION,
        "round": int(args.round),
        "component": _text(args.component),
        "dimension": dimension,
        "ambiguity": float(args.ambiguity),
        "why_now": _text(args.why_now),
        "question": _text(args.question),
        "recommendation": {
            "option_id": "A",
            "rationale": _text(args.rationale)
            or "This is the smallest concrete answer that appears to reduce the current ambiguity.",
        },
        "options": options,
        "source_refs": [ref for ref in args.source_ref if ref],
    }


def validate_round(round_doc: dict[str, Any]) -> dict[str, Any]:
    issues: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []

    def issue(code: str, message: str, path: str = "") -> None:
        issues.append({"code": code, "message": message, "path": path})

    def warn(code: str, message: str, path: str = "") -> None:
        warnings.append({"code": code, "message": message, "path": path})

    if round_doc.get("schema_version") != SCHEMA_VERSION:
        issue("SCHEMA_VERSION", f"schema_version must be {SCHEMA_VERSION}", "schema_version")
    question = _text(round_doc.get("question"))
    if not question:
        issue("QUESTION_MISSING", "round must have exactly one primary question", "question")
    if isinstance(round_doc.get("questions"), list) or isinstance(round_doc.get("additional_questions"), list):
        issue("MULTIPLE_QUESTIONS", "do not batch multiple questions in one round")

    dimension = _text(round_doc.get("dimension")).lower()
    if dimension not in VALID_DIMENSIONS:
        issue("DIMENSION_INVALID", f"dimension must be one of {sorted(VALID_DIMENSIONS)}", "dimension")

    options = _as_list(round_doc.get("options"))
    if not (3 <= len(options) <= 5):
        issue("OPTION_COUNT", "round should have 3-5 options, preferably 4", "options")
    elif len(options) != 4:
        warn("OPTION_COUNT_NOT_FOUR", "round should normally present four options", "options")

    option_ids: set[str] = set()
    recommended_ids: list[str] = []
    has_free_text = False
    for index, item in enumerate(options):
        path = f"options[{index}]"
        if not isinstance(item, dict):
            issue("OPTION_INVALID", "option must be an object", path)
            continue
        oid = _text(item.get("id"))
        label = _text(item.get("label"))
        tradeoff = _text(item.get("tradeoff"))
        effect = _text(item.get("decision_effect"))
        if not oid:
            issue("OPTION_ID_MISSING", "option id is required", f"{path}.id")
        if oid in option_ids:
            issue("OPTION_ID_DUPLICATE", f"duplicate option id {oid}", f"{path}.id")
        option_ids.add(oid)
        if not label:
            issue("OPTION_LABEL_MISSING", "option label is required", f"{path}.label")
        if not tradeoff:
            issue("OPTION_TRADEOFF_MISSING", "option tradeoff is required", f"{path}.tradeoff")
        if effect not in VALID_DECISION_EFFECTS:
            issue("OPTION_DECISION_EFFECT", f"decision_effect must be one of {sorted(VALID_DECISION_EFFECTS)}", f"{path}.decision_effect")
        if bool(item.get("recommended")):
            recommended_ids.append(oid)
        if "other" in label.lower() or "refine" in label.lower() or "기타" in label or "수정" in label:
            has_free_text = True
        if label.endswith("?"):
            warn("OPTION_LOOKS_LIKE_QUESTION", "option labels should be answers, not new questions", f"{path}.label")
        affects = [str(value).strip() for value in _as_list(item.get("affects")) if str(value).strip()]
        if affects and not _text(item.get("decision_matrix_ref")):
            warn("DECISION_MATRIX_REF_MISSING", "implementation-affecting option should name a decision_matrix_ref", path)

    if len(recommended_ids) != 1:
        issue("RECOMMENDATION_COUNT", "exactly one option should be recommended", "options")
    recommendation = round_doc.get("recommendation") if isinstance(round_doc.get("recommendation"), dict) else {}
    rec_id = _text(recommendation.get("option_id"))
    if rec_id and rec_id not in option_ids:
        issue("RECOMMENDATION_OPTION_UNKNOWN", "recommendation.option_id must match an option id", "recommendation.option_id")
    if recommended_ids and rec_id and recommended_ids != [rec_id]:
        issue("RECOMMENDATION_MISMATCH", "recommended option and recommendation.option_id must match", "recommendation")
    if not _text(recommendation.get("rationale")):
        issue("RECOMMENDATION_RATIONALE_MISSING", "recommendation rationale is required", "recommendation.rationale")
    if not has_free_text:
        issue("FREE_TEXT_OPTION_MISSING", "include Other / refine or equivalent free-text escape", "options")

    status = "fail" if issues else "pass"
    return {
        "schema_version": CHECK_SCHEMA_VERSION,
        "status": status,
        "issues": issues,
        "warnings": warnings,
        "summary": {
            "option_count": len(options),
            "recommended": recommended_ids[0] if len(recommended_ids) == 1 else "",
            "dimension": dimension,
        },
    }


def rank_candidates(payload: dict[str, Any]) -> dict[str, Any]:
    issues: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []

    def issue(code: str, message: str, path: str = "") -> None:
        issues.append({"code": code, "message": message, "path": path})

    def warn(code: str, message: str, path: str = "") -> None:
        warnings.append({"code": code, "message": message, "path": path})

    candidates = _as_list(payload.get("candidates"))
    if not candidates:
        issue("NO_CANDIDATES", "rank payload must include at least one candidate", "candidates")
    ranked_pairs: list[tuple[dict[str, Any], tuple[float, float, float, float, float, float, int]]] = []
    for index, item in enumerate(candidates):
        path = f"candidates[{index}]"
        if not isinstance(item, dict):
            issue("CANDIDATE_INVALID", "candidate must be an object", path)
            continue
        ranked, tie_breaker = _ranked_candidate(item, index)
        if ranked["dimension"] not in VALID_DIMENSIONS:
            issue("DIMENSION_INVALID", f"dimension must be one of {sorted(VALID_DIMENSIONS)}", f"{path}.dimension")
        if not ranked["component"]:
            warn("COMPONENT_MISSING", "candidate should name the active component", f"{path}.component")
        if not _text(ranked.get("question")):
            warn("QUESTION_MISSING", "candidate should include the one question it would ask", f"{path}.question")
        if ranked["score_breakdown"]["researchable_fact"] >= 2 and ranked["importance_score"] > 0:
            warn(
                "RESEARCH_BEFORE_ASKING",
                "high researchable_fact means repo/spec reading may be better than asking the user",
                path,
            )
        ranked_pairs.append((ranked, tie_breaker))

    ranked_pairs.sort(key=lambda pair: pair[1])
    ranked = [pair[0] for pair in ranked_pairs]
    selected = ranked[0] if ranked and not issues else None
    return {
        "schema_version": RANK_SCHEMA_VERSION,
        "status": "fail" if issues else "pass",
        "selected_id": selected.get("id") if selected else "",
        "selected": selected,
        "ranked": ranked,
        "issues": issues,
        "warnings": warnings,
        "policy": {
            "positive_weights": dict(IMPORTANCE_WEIGHTS),
            "negative_weights": dict(NEGATIVE_IMPORTANCE_WEIGHTS),
            "tie_breakers": [
                "importance_score",
                "lock_blocker",
                "ssot_required_gap",
                "downstream_fanout",
                "upstream_dependency",
                "lower_researchable_fact",
                "input_order",
            ],
        },
    }


def render_round(round_doc: dict[str, Any]) -> str:
    rec = round_doc.get("recommendation") if isinstance(round_doc.get("recommendation"), dict) else {}
    rec_id = _text(rec.get("option_id")) or "A"
    rationale = _text(rec.get("rationale"))
    lines = [
        f"Round {round_doc.get('round')} | Component: {_text(round_doc.get('component'))} | Targeting: {_text(round_doc.get('dimension'))} | Ambiguity: {round_doc.get('ambiguity')}",
        f"Why now: {_text(round_doc.get('why_now'))}",
        f"Recommendation: {rec_id} because {rationale}.",
        "",
        f"Question: {_text(round_doc.get('question'))}",
        "",
        "Options:",
    ]
    for item in _as_list(round_doc.get("options")):
        if not isinstance(item, dict):
            continue
        suffix = " (Recommended)" if bool(item.get("recommended")) else ""
        lines.append(f"{_text(item.get('id'))}. {_text(item.get('label'))}{suffix} - {_text(item.get('tradeoff'))}")
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    template = sub.add_parser("template", help="emit a one-question round JSON template")
    template.add_argument("--round", type=int, default=1)
    template.add_argument("--component", required=True)
    template.add_argument("--dimension", required=True, choices=sorted(VALID_DIMENSIONS))
    template.add_argument("--ambiguity", type=float, default=1.0)
    template.add_argument("--why-now", required=True)
    template.add_argument("--question", required=True)
    template.add_argument("--rationale", default="")
    template.add_argument("--source-ref", action="append", default=[])

    validate = sub.add_parser("validate", help="validate a round JSON payload")
    validate.add_argument("--json-file", default="-", help="round JSON file, or '-' for stdin")

    render = sub.add_parser("render", help="render a round JSON payload as chat text")
    render.add_argument("--json-file", default="-", help="round JSON file, or '-' for stdin")

    rank = sub.add_parser("rank", help="rank candidate next questions by OAG lock impact")
    rank.add_argument("--json-file", default="-", help="candidate JSON file, or '-' for stdin")

    args = parser.parse_args()
    if args.command == "template":
        dump_json(build_template(args))
        return 0
    if args.command == "validate":
        result = validate_round(load_json(args.json_file))
        dump_json(result)
        return 0 if result["status"] == "pass" else 1
    if args.command == "render":
        round_doc = load_json(args.json_file)
        result = validate_round(round_doc)
        if result["status"] != "pass":
            dump_json(result)
            return 1
        sys.stdout.write(render_round(round_doc))
        return 0
    if args.command == "rank":
        result = rank_candidates(load_json(args.json_file))
        dump_json(result)
        return 0 if result["status"] == "pass" else 1
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
