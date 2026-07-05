#!/usr/bin/env python3
"""Render a verbatim pre-lock OAG review frame as static HTML."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import html
import importlib
import json
import sys
from pathlib import Path
from typing import Any

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

oag_lock_readiness_check = importlib.import_module("oag_lock_readiness_check")
oag_paths = importlib.import_module("oag_paths")


CANONICAL_SOURCES: tuple[tuple[str, str, str], ...] = (
    ("source_claims", "req/source_claims.yaml", "Captured source facts and normalized meanings"),
    ("ambiguity_register", "req/ambiguity_register.yaml", "Open, resolved, or waived ambiguities"),
    ("interview_draft", "req/interview_draft.md", "Human-facing interview notes when present"),
    ("features", "ontology/features.yaml", "Product-visible feature scope"),
    ("decision_matrix", "ontology/decision_matrix.yaml", "Lock-blocking choices and waivers"),
    ("requirement_atoms", "ontology/requirement_atoms.yaml", "Semantic requirement decomposition"),
    ("requirements", "ontology/requirements.yaml", "Canonical requirement rows"),
    ("obligations", "ontology/obligations.yaml", "Implementation obligations"),
    ("contracts", "ontology/contracts.yaml", "Assume/guarantee contracts and proof refs"),
    ("modeling", "ontology/modeling.yaml", "Behavior and cycle modeling authority"),
    ("structure", "ontology/structure.yaml", "Interfaces, ports, registers, and shared namespace"),
    ("decomposition", "ontology/decomposition.yaml", "Module ownership and boundaries"),
    ("verification_plan", "ontology/verification_plan.yaml", "Proof objectives, scenarios, scoreboard, and coverage"),
    ("tb_methodology", "ontology/tb_methodology.yaml", "Framework-neutral verification methodology intent"),
    ("ipxact_projection", "ontology/ipxact_projection.yaml", "IP-XACT-style integration projection"),
    ("scope_lock", "ontology/scope_lock.json", "Current lock state"),
    ("locked_truth", "req/locked_truth.md", "Legacy locked truth, if this IP still uses it"),
)

FRAME_MODES: dict[str, dict[str, str]] = {
    "pre-lock": {
        "title": "Pre-Lock Review Frame",
        "badge": "Lock-readiness check",
        "purpose": "This HTML file is a review envelope. It provides navigation, hashes, and lock-readiness issues, but the lock decision must be made by reading the verbatim source panels below.",
        "instructions": "Confirm that the raw source panels express the intended feature scope, requirements, decisions, obligations, contracts, verification intent, and integration metadata before locking.",
    },
    "pre-dispatch": {
        "title": "Pre-Dispatch Review Frame",
        "badge": "Dispatch-readiness check",
        "purpose": "This HTML file is a pre-dispatch review envelope. It preserves source artifacts and hashes so RTL/TB/sim work is not launched from stale or paraphrased truth.",
        "instructions": "Confirm scope lock, source truth, obligations, contracts, verification intent, and IP-XACT-style metadata before creating implementation dispatches.",
    },
    "post-evidence": {
        "title": "Post-Evidence Review Frame",
        "badge": "Evidence-readiness check",
        "purpose": "This HTML file is a post-evidence review envelope. It keeps authored truth visible while reviewing whether evidence can be promoted without stale inputs.",
        "instructions": "Compare source truth with evidence-facing sections. Do not approve closure when evidence or lifecycle hashes are stale.",
    },
    "gate": {
        "title": "Gate Review Frame",
        "badge": "Gate-readiness check",
        "purpose": "This HTML file is a gate-review envelope. It lets a reviewer inspect current source truth and artifact hashes before making or refreshing a gate decision.",
        "instructions": "Review the raw panels and hashes before approving, rejecting, or requesting changes. A gate decision older than validation evidence must be refreshed.",
    },
}


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def rel_to_ip(ip_dir: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(ip_dir.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def read_text_lossless(path: Path) -> tuple[str, str]:
    data = path.read_bytes()
    try:
        return data.decode("utf-8"), "utf-8"
    except UnicodeDecodeError:
        return data.decode("utf-8", errors="replace"), "utf-8-replacement"


def read_yaml_or_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    suffix = path.suffix.lower()
    try:
        if suffix == ".json":
            data = json.loads(path.read_text(encoding="utf-8"))
        else:
            try:
                import yaml  # type: ignore
            except Exception:
                return {"__parse_skipped__": "PyYAML not available"}
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        return data if isinstance(data, dict) else {"__shape__": type(data).__name__}
    except Exception as exc:
        return {"__parse_error__": str(exc)}


def as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def text(value: Any) -> str:
    return str(value or "").strip()


def summarize_document(name: str, parsed: dict[str, Any]) -> dict[str, Any]:
    if not parsed:
        return {}
    if name == "source_claims":
        rows = [item for item in as_list(parsed.get("claims")) if isinstance(item, dict)]
        return {"rows": len(rows), "ids": [text(item.get("id")) for item in rows if text(item.get("id"))]}
    if name == "ambiguity_register":
        rows = [item for item in as_list(parsed.get("ambiguities")) if isinstance(item, dict)]
        return {
            "rows": len(rows),
            "lock_blockers": [
                text(item.get("id")) or f"row_{index}"
                for index, item in enumerate(rows)
                if item.get("lock_required") is True and text(item.get("status")).lower() not in {"resolved", "waived"}
            ],
        }
    if name == "features":
        rows = [item for item in as_list(parsed.get("features")) if isinstance(item, dict)]
        return {"rows": len(rows), "ids": [text(item.get("id")) for item in rows if text(item.get("id"))]}
    if name == "decision_matrix":
        rows = [item for item in as_list(parsed.get("decisions")) if isinstance(item, dict)]
        return {
            "rows": len(rows),
            "lock_blockers": [
                text(item.get("id")) or f"row_{index}"
                for index, item in enumerate(rows)
                if item.get("lock_required") is True and text(item.get("status")).lower() not in {"decided", "waived"}
            ],
        }
    if name == "requirement_atoms":
        rows = [item for item in as_list(parsed.get("requirement_atoms")) if isinstance(item, dict)]
        if not rows:
            rows = [item for item in as_list(parsed.get("atoms")) if isinstance(item, dict)]
        return {"rows": len(rows), "ids": [text(item.get("id")) for item in rows if text(item.get("id"))]}
    if name in {"requirements", "obligations", "contracts"}:
        rows = [item for item in as_list(parsed.get(name)) if isinstance(item, dict)]
        return {"rows": len(rows), "ids": [text(item.get("id")) for item in rows if text(item.get("id"))]}
    if name == "verification_plan":
        objectives = [item for item in as_list(parsed.get("verification_objectives")) if isinstance(item, dict)]
        scenarios = [item for item in as_list(parsed.get("scenarios")) if isinstance(item, dict)]
        coverage = [item for item in as_list(parsed.get("coverage_goals")) if isinstance(item, dict)]
        return {"objectives": len(objectives), "scenarios": len(scenarios), "coverage_goals": len(coverage)}
    if name == "scope_lock":
        return {"state": parsed.get("state"), "updated_at": parsed.get("updated_at") or parsed.get("locked_at")}
    if "__parse_error__" in parsed or "__parse_skipped__" in parsed:
        return parsed
    return {"schema_version": parsed.get("schema_version")} if parsed.get("schema_version") else {}


def collect_sources(ip_dir: Path) -> list[dict[str, Any]]:
    sources: list[dict[str, Any]] = []
    for name, rel, purpose in CANONICAL_SOURCES:
        path = oag_paths.legacy_or_hidden(ip_dir, rel)
        if not path.is_file():
            sources.append(
                {
                    "name": name,
                    "path": rel,
                    "purpose": purpose,
                    "exists": False,
                    "sha256": "",
                    "encoding": "",
                    "bytes": 0,
                    "lines": 0,
                    "summary": {},
                    "raw_text": "",
                }
            )
            continue
        raw_bytes = path.read_bytes()
        raw_text, encoding = read_text_lossless(path)
        parsed = read_yaml_or_json(path)
        sources.append(
            {
                "name": name,
                "path": rel_to_ip(ip_dir, path),
                "purpose": purpose,
                "exists": True,
                "sha256": sha256_bytes(raw_bytes),
                "encoding": encoding,
                "bytes": len(raw_bytes),
                "lines": raw_text.count("\n") + (0 if raw_text.endswith("\n") or not raw_text else 1),
                "summary": summarize_document(name, parsed),
                "raw_text": raw_text,
            }
        )
    return sources


def status_class(status: str) -> str:
    if status == "pass":
        return "pass"
    if status in {"missing", "not_found"}:
        return "muted"
    return "fail"


def render_summary_value(value: Any) -> str:
    if value in ("", None, [], {}):
        return "<span class=\"muted-text\">none</span>"
    if isinstance(value, list):
        return html.escape(", ".join(str(item) for item in value))
    return html.escape(str(value))


def json_summary(value: Any) -> str:
    if value in ("", None, [], {}):
        return ""
    return json.dumps(value, sort_keys=True)


def dict_value(source: dict[str, Any], key: str) -> dict[str, Any]:
    value = source.get(key)
    return value if isinstance(value, dict) else {}


def optional_artifact(ip_dir: Path, rel: str) -> dict[str, Any]:
    path = oag_paths.legacy_or_hidden(ip_dir, rel)
    if not path.is_file():
        return {
            "path": rel,
            "exists": False,
            "sha256": "",
            "raw_text": "",
            "parsed": {},
        }
    raw_bytes = path.read_bytes()
    raw_text, encoding = read_text_lossless(path)
    return {
        "path": rel_to_ip(ip_dir, path),
        "exists": True,
        "sha256": sha256_bytes(raw_bytes),
        "encoding": encoding,
        "raw_text": raw_text,
        "parsed": read_yaml_or_json(path),
    }


def latest_architecture_scoreboard(ip_dir: Path) -> dict[str, Any]:
    root = oag_paths.legacy_or_hidden(ip_dir, "knowledge/arch_exploration")
    candidates = sorted(
        (path for path in root.glob("*/architecture_scoreboard.json") if path.is_file()),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    if not candidates:
        return {
            "path": "knowledge/arch_exploration/*/architecture_scoreboard.json",
            "exists": False,
            "sha256": "",
            "raw_text": "",
            "parsed": {},
        }
    path = candidates[0]
    raw_bytes = path.read_bytes()
    raw_text, encoding = read_text_lossless(path)
    return {
        "path": rel_to_ip(ip_dir, path),
        "exists": True,
        "sha256": sha256_bytes(raw_bytes),
        "encoding": encoding,
        "raw_text": raw_text,
        "parsed": read_yaml_or_json(path),
    }


def collect_provisional_decisions(ip_dir: Path, readiness: dict[str, Any]) -> list[dict[str, Any]]:
    matrix = optional_artifact(ip_dir, "ontology/decision_matrix.yaml")
    parsed_raw = matrix.get("parsed")
    parsed = parsed_raw if isinstance(parsed_raw, dict) else {}
    rows = [item for item in as_list(parsed.get("decisions")) if isinstance(item, dict)]
    rows_by_id = {text(item.get("id")): item for item in rows if text(item.get("id"))}
    readiness_items = [
        item
        for item in as_list(readiness.get("provisional_review_items"))
        if isinstance(item, dict)
    ]
    seen: set[str] = set()
    decisions: list[dict[str, Any]] = []
    for item in readiness_items:
        did = text(item.get("id"))
        row = rows_by_id.get(did, {})
        seen.add(did)
        decisions.append(
            {
                "id": did,
                "decision_class": text(item.get("decision_class") or row.get("decision_class")),
                "question": text(row.get("question")),
                "decision": row.get("decision"),
                "charter_ref": text(item.get("charter_ref") or row.get("charter_ref")),
                "charter_grant_id": text(item.get("charter_grant_id")),
                "evidence_refs": item.get("evidence_refs") or row.get("evidence_refs") or [],
                "decision_receipt_ref": text(item.get("decision_receipt_ref") or row.get("decision_receipt_ref")),
                "review_required": text(item.get("review_required") or "human_lock_review"),
            }
        )
    for row in rows:
        did = text(row.get("id"))
        decided_by_raw = row.get("decided_by")
        decided_by = decided_by_raw if isinstance(decided_by_raw, dict) else {}
        if did in seen or row.get("provisional") is not True or not text(decided_by.get("kind")).lower().startswith("agent_"):
            continue
        decisions.append(
            {
                "id": did,
                "decision_class": text(row.get("decision_class")),
                "question": text(row.get("question")),
                "decision": row.get("decision"),
                "charter_ref": text(decided_by.get("charter_ref")),
                "charter_grant_id": "",
                "evidence_refs": row.get("evidence_refs") or [],
                "decision_receipt_ref": text(row.get("decision_receipt_ref")),
                "review_required": "human_lock_review",
            }
        )
    return decisions


def collect_checkpoint_review(ip_dir: Path, readiness: dict[str, Any]) -> dict[str, Any]:
    return {
        "mission_charter": optional_artifact(ip_dir, "ontology/mission_charter.yaml"),
        "architecture_scoreboard": latest_architecture_scoreboard(ip_dir),
        "provisional_decisions": {
            "path": "ontology/decision_matrix.yaml / readiness.provisional_review_items",
            "exists": oag_paths.legacy_or_hidden(ip_dir, "ontology/decision_matrix.yaml").is_file(),
            "rows": collect_provisional_decisions(ip_dir, readiness),
        },
        "pending_questions": optional_artifact(ip_dir, "knowledge/mission_loop/pending_questions.json"),
    }


def render_artifact_meta(artifact: dict[str, Any], available: bool) -> str:
    status = "available" if available else "unavailable"
    return f"""
  <dl class="meta">
    <div><dt>Path</dt><dd><code>{html.escape(str(artifact.get('path') or ''))}</code></dd></div>
    <div><dt>Status</dt><dd class="{'present' if available else 'missing'}">{status}</dd></div>
    <div><dt>SHA-256</dt><dd><code>{html.escape(str(artifact.get('sha256') or 'n/a'))}</code></dd></div>
    <div><dt>Encoding</dt><dd>{html.escape(str(artifact.get('encoding') or 'n/a'))}</dd></div>
  </dl>
"""


def render_checkpoint_review(checkpoint_review: dict[str, Any]) -> str:
    charter = dict_value(checkpoint_review, "mission_charter")
    charter_parsed = dict_value(charter, "parsed")
    charter_approved = (
        bool(charter.get("exists"))
        and charter_parsed.get("approved") is True
        and text(charter_parsed.get("status")).lower() == "approved"
    )
    charter_raw = str(charter.get("raw_text") or "(approved mission charter unavailable)")

    scoreboard = dict_value(checkpoint_review, "architecture_scoreboard")
    scoreboard_parsed = dict_value(scoreboard, "parsed")
    scoreboard_rows = [item for item in as_list(scoreboard_parsed.get("rows")) if isinstance(item, dict)]
    scoreboard_table_rows = "".join(
        "<tr>"
        f"<td>{html.escape(str(item.get('rank') or ''))}</td>"
        f"<td><code>{html.escape(text(item.get('candidate_id')))}</code></td>"
        f"<td>{html.escape(str(item.get('weighted_total') or ''))}</td>"
        f"<td>{'yes' if item.get('pareto_member') is True else 'no'}</td>"
        f"<td>{html.escape(str(item.get('hard_constraint_pass') if 'hard_constraint_pass' in item else ''))}</td>"
        f"<td><code>{html.escape(json_summary(item.get('metrics')))}</code></td>"
        f"<td><code>{html.escape(json_summary(item.get('decision_assignments')))}</code></td>"
        "</tr>"
        for item in scoreboard_rows
    )
    if not scoreboard_table_rows:
        scoreboard_table_rows = "<tr><td colspan=\"7\" class=\"muted-text\">Architecture scoreboard unavailable.</td></tr>"

    provisional = dict_value(checkpoint_review, "provisional_decisions")
    provisional_rows = [item for item in as_list(provisional.get("rows")) if isinstance(item, dict)]
    provisional_table_rows = "".join(
        "<tr>"
        f"<td><code>{html.escape(text(item.get('id')))}</code></td>"
        f"<td>{html.escape(text(item.get('decision_class')))}</td>"
        f"<td>{html.escape(text(item.get('question')))}</td>"
        f"<td><code>{html.escape(json_summary(item.get('decision')) or text(item.get('decision')))}</code></td>"
        f"<td><code>{html.escape(text(item.get('charter_ref') or item.get('charter_grant_id')))}</code></td>"
        f"<td><code>{html.escape(', '.join(str(ref) for ref in as_list(item.get('evidence_refs'))))}</code></td>"
        f"<td><code>{html.escape(text(item.get('decision_receipt_ref')))}</code></td>"
        "</tr>"
        for item in provisional_rows
    )
    if not provisional_table_rows:
        message = "Decision matrix unavailable." if not provisional.get("exists") else "No provisional agent decisions queued for review."
        provisional_table_rows = f"<tr><td colspan=\"7\" class=\"muted-text\">{html.escape(message)}</td></tr>"

    pending = dict_value(checkpoint_review, "pending_questions")
    pending_parsed = dict_value(pending, "parsed")
    pending_questions = [item for item in as_list(pending_parsed.get("questions")) if isinstance(item, dict)]
    pending_table_rows = "".join(
        "<tr>"
        f"<td><code>{html.escape(text(item.get('id')))}</code></td>"
        f"<td><code>{html.escape(text(item.get('decision_id')))}</code></td>"
        f"<td>{html.escape(text(item.get('decision_class')))}</td>"
        f"<td>{html.escape(text(item.get('question')))}</td>"
        f"<td><code>{html.escape(', '.join(str(option) for option in as_list(item.get('options'))))}</code></td>"
        "</tr>"
        for item in pending_questions
    )
    if not pending_table_rows:
        pending_table_rows = "<tr><td colspan=\"5\" class=\"muted-text\">Pending questions queue unavailable.</td></tr>"

    return f"""
  <section class="panel" id="mission-charter">
    <h2>Approved Mission Charter</h2>
    <p class="purpose">Human-approved mission autonomy for checkpoint batching. Review the verbatim charter before accepting agent-selected tradeoffs.</p>
    {render_artifact_meta(charter, charter_approved)}
    <pre class="raw"><code>{html.escape(charter_raw)}</code></pre>
  </section>

  <section class="panel" id="architecture-scoreboard">
    <h2>Architecture Scoreboard / Pareto Rows</h2>
    <p class="purpose">Latest architecture scoreboard with Pareto membership and decision assignments for checkpoint review.</p>
    {render_artifact_meta(scoreboard, bool(scoreboard.get('exists')))}
    <table><thead><tr><th>Rank</th><th>Candidate</th><th>Weighted Total</th><th>Pareto</th><th>Hard Constraint</th><th>Metrics</th><th>Decision Assignments</th></tr></thead><tbody>{scoreboard_table_rows}</tbody></table>
  </section>

  <section class="panel" id="provisional-agent-decisions">
    <h2>Provisional Agent Decisions</h2>
    <p class="purpose">Rows remain provisional until a human checkpoint accepts them, overrides them, or sends them back to exploration.</p>
    <dl class="meta">
      <div><dt>Path</dt><dd><code>{html.escape(str(provisional.get('path') or ''))}</code></dd></div>
      <div><dt>Status</dt><dd class="{'present' if provisional.get('exists') else 'missing'}">{'available' if provisional.get('exists') else 'unavailable'}</dd></div>
    </dl>
    <table><thead><tr><th>ID</th><th>Class</th><th>Question</th><th>Decision</th><th>Charter</th><th>Evidence</th><th>Receipt</th></tr></thead><tbody>{provisional_table_rows}</tbody></table>
  </section>

  <section class="panel" id="pending-questions">
    <h2>Pending Questions Queue</h2>
    <p class="purpose">Batched human checkpoint questions in file order, preserving option payloads for review.</p>
    {render_artifact_meta(pending, bool(pending.get('exists')))}
    <table class="summary"><tbody><tr><th>Queue Status</th><td>{render_summary_value(pending_parsed.get('status'))}</td></tr></tbody></table>
    <table><thead><tr><th>ID</th><th>Decision</th><th>Class</th><th>Question</th><th>Options</th></tr></thead><tbody>{pending_table_rows}</tbody></table>
  </section>
"""


def collect_operation_context(ip_dir: Path) -> dict[str, Any]:
    context: dict[str, Any] = {
        "status": "pass",
        "issues": [],
        "recommended_action": {},
        "next_actions": [],
        "mission": {},
        "wavefront_task_count": 0,
        "role_hazards": [],
    }
    try:
        oag_action_plan = importlib.import_module("oag_action_plan")
        oag_action_wavefront_draft = importlib.import_module("oag_action_wavefront_draft")
        oag_mission_runtime = importlib.import_module("oag_mission_runtime")
        oag_role_health = importlib.import_module("oag_role_health")

        plan_result_raw = oag_action_plan.build_plan(ip_dir, write=False, run_semantic_checks=False)
        plan_result = plan_result_raw if isinstance(plan_result_raw, dict) else {}
        plan = dict_value(plan_result, "plan")
        candidates = [item for item in plan.get("candidates", []) if isinstance(item, dict)]
        recommended = next((item for item in candidates if item.get("recommended") is True), candidates[0] if candidates else {})
        mission = oag_mission_runtime.latest_active_mission(ip_dir) or {}
        mission.pop("_path", None)
        wavefront = oag_action_wavefront_draft.build_draft(ip_dir, max_tasks=8, refresh_plan=False)
        role_health = oag_role_health.collect_role_health(ip_dir)
        context.update(
            {
                "recommended_action": recommended,
                "next_actions": candidates[:4],
                "mission": mission,
                "wavefront_task_count": len(wavefront.get("tasks", []) if isinstance(wavefront.get("tasks"), list) else []),
                "role_hazards": [item for item in role_health.get("hazards", []) if isinstance(item, dict)],
            }
        )
        if plan_result.get("status") != "pass":
            context["status"] = "needs_attention"
            context["issues"].extend(plan_result.get("issues", []) if isinstance(plan_result.get("issues"), list) else [])
    except Exception as exc:
        context["status"] = "unavailable"
        context["issues"].append({"code": "OPERATION_CONTEXT_UNAVAILABLE", "message": str(exc)})
    return context


def render_operation_context(operation_context: dict[str, Any]) -> str:
    recommended = dict_value(operation_context, "recommended_action")
    options = [item for item in operation_context.get("next_actions", []) if isinstance(item, dict)]
    mission = dict_value(operation_context, "mission")
    hazards = [item for item in operation_context.get("role_hazards", []) if isinstance(item, dict)]
    option_rows = "".join(
        "<tr>"
        f"<td>{'yes' if item.get('recommended') else ''}</td>"
        f"<td>{html.escape(str(item.get('priority') or ''))}</td>"
        f"<td><code>{html.escape(str(item.get('action_type') or ''))}</code></td>"
        f"<td>{html.escape(str(item.get('recommendation_reason') or ''))}</td>"
        "</tr>"
        for item in options
    )
    if not option_rows:
        option_rows = "<tr><td colspan=\"4\" class=\"muted-text\">No Action candidates available.</td></tr>"
    hazard_rows = "".join(
        "<tr>"
        f"<td>{html.escape(str(item.get('role') or ''))}</td>"
        f"<td><code>{html.escape(str(item.get('code') or ''))}</code></td>"
        f"<td>{html.escape(str(item.get('message') or ''))}</td>"
        "</tr>"
        for item in hazards
    )
    if not hazard_rows:
        hazard_rows = "<tr><td colspan=\"3\" class=\"pass-text\">No role hazards detected.</td></tr>"
    return f"""
  <section class="panel">
    <h2>Operation Context</h2>
    <p>This section is navigation context only. It does not replace the verbatim source panels below.</p>
    <div class="op-grid">
      <div><span>Mission</span><strong><code>{html.escape(str(mission.get('template_id') or ''))}</code></strong></div>
      <div><span>Recommended Action</span><strong><code>{html.escape(str(recommended.get('action_type') or ''))}</code></strong></div>
      <div><span>Wavefront Draft Tasks</span><strong>{html.escape(str(operation_context.get('wavefront_task_count') or 0))}</strong></div>
      <div><span>Role Hazards</span><strong>{len(hazards)}</strong></div>
    </div>
    <h3 style="margin-top:16px">Four Current Options</h3>
    <table><thead><tr><th>Recommended</th><th>Priority</th><th>Action Type</th><th>Why</th></tr></thead><tbody>{option_rows}</tbody></table>
    <h3 style="margin-top:16px">Role Hazards</h3>
    <table><thead><tr><th>Role</th><th>Code</th><th>Message</th></tr></thead><tbody>{hazard_rows}</tbody></table>
  </section>
"""


def render_html(
    ip_dir: Path,
    metadata: dict[str, Any],
    sources: list[dict[str, Any]],
    readiness: dict[str, Any],
    checkpoint_review: dict[str, Any],
    operation_context: dict[str, Any] | None = None,
) -> str:
    mode = str(metadata.get("frame_mode") or "pre-lock")
    mode_cfg = FRAME_MODES.get(mode, FRAME_MODES["pre-lock"])
    status = str(readiness.get("status") or "unknown")
    issues_raw = readiness.get("issues")
    issues: list[Any] = issues_raw if isinstance(issues_raw, list) else []
    next_actions_raw = readiness.get("next_actions")
    next_actions: list[Any] = next_actions_raw if isinstance(next_actions_raw, list) else []
    source_rows = []
    for source in sources:
        exists = bool(source["exists"])
        row_class = "present" if exists else "missing"
        source_rows.append(
            "<tr>"
            f"<td><a href=\"#{html.escape(source['name'])}\">{html.escape(source['name'])}</a></td>"
            f"<td>{html.escape(source['path'])}</td>"
            f"<td class=\"{row_class}\">{'present' if exists else 'missing'}</td>"
            f"<td>{html.escape(str(source['lines']))}</td>"
            f"<td><code>{html.escape(source['sha256'][:16])}</code></td>"
            "</tr>"
        )

    sections = []
    for source in sources:
        summary = dict_value(source, "summary")
        summary_rows = "".join(
            f"<tr><th>{html.escape(str(key))}</th><td>{render_summary_value(value)}</td></tr>"
            for key, value in summary.items()
        )
        if not summary_rows:
            summary_rows = "<tr><td colspan=\"2\" class=\"muted-text\">No parsed navigation summary. Review the source panel directly.</td></tr>"
        raw = source["raw_text"] if source["exists"] else "(file is not present)"
        sections.append(
            f"""
<section class="source-card" id="{html.escape(source['name'])}">
  <header>
    <div>
      <p class="eyebrow">Verbatim Source</p>
      <h2>{html.escape(source['name'])}</h2>
      <p class="purpose">{html.escape(source['purpose'])}</p>
    </div>
    <a class="top-link" href="#top">Top</a>
  </header>
  <dl class="meta">
    <div><dt>Path</dt><dd><code>{html.escape(source['path'])}</code></dd></div>
    <div><dt>Status</dt><dd>{'present' if source['exists'] else 'missing'}</dd></div>
    <div><dt>SHA-256</dt><dd><code>{html.escape(source['sha256'] or 'n/a')}</code></dd></div>
    <div><dt>Encoding</dt><dd>{html.escape(source['encoding'] or 'n/a')}</dd></div>
  </dl>
  <table class="summary"><tbody>{summary_rows}</tbody></table>
  <div class="verbatim-note">The block below is the file content with HTML escaping only. It is not paraphrased or normalized.</div>
  <pre class="raw"><code>{html.escape(raw)}</code></pre>
</section>
"""
        )

    issue_rows = "".join(
        "<tr>"
        f"<td><code>{html.escape(str(item.get('code') if isinstance(item, dict) else 'ISSUE'))}</code></td>"
        f"<td>{html.escape(str(item.get('path') if isinstance(item, dict) else ''))}</td>"
        f"<td>{html.escape(str(item.get('message') if isinstance(item, dict) else item))}</td>"
        "</tr>"
        for item in issues
    )
    if not issue_rows:
        issue_rows = "<tr><td colspan=\"3\" class=\"pass-text\">No lock-readiness issues reported by the checker.</td></tr>"
    action_rows = "".join(f"<li>{html.escape(str(item))}</li>" for item in next_actions) or "<li>No next action from readiness checker.</li>"
    operation_panel = render_operation_context(operation_context) if operation_context else ""
    checkpoint_panel = render_checkpoint_review(checkpoint_review)

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>OAG {html.escape(mode_cfg['title'])} - {html.escape(ip_dir.name)}</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #f7f8fa;
      --panel: #ffffff;
      --ink: #1f2937;
      --muted: #667085;
      --line: #d0d5dd;
      --soft: #eef2f6;
      --pass: #0f766e;
      --fail: #b42318;
      --warn: #b54708;
      --link: #175cd3;
      --code: #101828;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background: var(--bg);
      color: var(--ink);
      font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      line-height: 1.45;
    }}
    main {{ max-width: 1180px; margin: 0 auto; padding: 32px 24px 64px; }}
    .hero {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 24px;
      margin-bottom: 18px;
    }}
    .eyebrow {{
      margin: 0 0 6px;
      color: var(--muted);
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: .08em;
      font-weight: 700;
    }}
    h1, h2, h3 {{ margin: 0; line-height: 1.2; }}
    h1 {{ font-size: 30px; }}
    h2 {{ font-size: 22px; }}
    h3 {{ font-size: 17px; }}
    .hero p {{ max-width: 900px; color: var(--muted); }}
    .badge {{
      display: inline-flex;
      align-items: center;
      border-radius: 999px;
      padding: 4px 10px;
      font-size: 13px;
      font-weight: 700;
      border: 1px solid currentColor;
      margin-top: 14px;
    }}
    .badge.pass {{ color: var(--pass); }}
    .badge.fail {{ color: var(--fail); }}
    .badge.muted {{ color: var(--muted); }}
    .grid {{ display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; margin: 18px 0; }}
    .metric {{ background: var(--panel); border: 1px solid var(--line); border-radius: 8px; padding: 14px; }}
    .metric span {{ display: block; color: var(--muted); font-size: 12px; }}
    .metric strong {{ display: block; margin-top: 4px; font-size: 20px; }}
    table {{ width: 100%; border-collapse: collapse; }}
    th, td {{ padding: 9px 10px; border-bottom: 1px solid var(--line); text-align: left; vertical-align: top; }}
    th {{ color: var(--muted); font-size: 12px; text-transform: uppercase; letter-spacing: .04em; }}
    .panel, .source-card {{ background: var(--panel); border: 1px solid var(--line); border-radius: 8px; padding: 18px; margin: 18px 0; }}
    .source-card header {{ display: flex; justify-content: space-between; gap: 16px; align-items: flex-start; }}
    .purpose {{ margin: 6px 0 0; color: var(--muted); }}
    .top-link {{ color: var(--link); text-decoration: none; font-size: 13px; }}
    .meta {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px 18px; margin: 16px 0; }}
    .meta div {{ min-width: 0; }}
    dt {{ color: var(--muted); font-size: 12px; font-weight: 700; text-transform: uppercase; }}
    dd {{ margin: 3px 0 0; overflow-wrap: anywhere; }}
    code {{ color: var(--code); font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, "Liberation Mono", monospace; font-size: .92em; }}
    .summary {{ margin: 12px 0; border: 1px solid var(--line); }}
    .summary th {{ width: 220px; background: var(--soft); }}
    .verbatim-note {{ color: var(--warn); font-size: 13px; margin: 12px 0 8px; }}
    pre.raw {{
      margin: 0;
      padding: 16px;
      background: #fbfcfe;
      border: 1px solid var(--line);
      border-radius: 6px;
      overflow: auto;
      white-space: pre;
      tab-size: 2;
      font-size: 13px;
      line-height: 1.5;
    }}
    .present, .pass-text {{ color: var(--pass); font-weight: 700; }}
    .missing {{ color: var(--fail); font-weight: 700; }}
    .muted-text {{ color: var(--muted); }}
    .actions {{ margin: 8px 0 0; padding-left: 22px; }}
    .op-grid {{ display:grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap:12px; margin-top:12px; }}
    .op-grid div {{ border:1px solid var(--line); border-radius:8px; padding:12px; background:#fbfcfe; min-width:0; }}
    .op-grid span {{ display:block; color:var(--muted); font-size:12px; }}
    .op-grid strong {{ display:block; margin-top:4px; overflow-wrap:anywhere; }}
    @media (max-width: 860px) {{
      main {{ padding: 20px 12px 48px; }}
      .grid {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
      .op-grid {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
      .meta {{ grid-template-columns: 1fr; }}
      h1 {{ font-size: 24px; }}
    }}
  </style>
</head>
<body>
<main id="top">
  <section class="hero">
    <p class="eyebrow">Ontology Agent Gateway</p>
    <h1>{html.escape(mode_cfg['title'])}: {html.escape(ip_dir.name)}</h1>
    <p>{html.escape(mode_cfg['purpose'])}</p>
    <div class="badge {status_class(status)}">{html.escape(mode_cfg['badge'])}: {html.escape(status)}</div>
  </section>

  <section class="grid" aria-label="Metadata">
    <div class="metric"><span>Generated</span><strong>{html.escape(metadata['generated_at'])}</strong></div>
    <div class="metric"><span>IP directory</span><strong>{html.escape(ip_dir.name)}</strong></div>
    <div class="metric"><span>Present sources</span><strong>{sum(1 for item in sources if item['exists'])}</strong></div>
    <div class="metric"><span>Readiness issues</span><strong>{len(issues)}</strong></div>
  </section>

  <section class="panel">
    <h2>Review Instructions</h2>
    <p>Use the tables for navigation only. Do not approve from a paraphrase. {html.escape(mode_cfg['instructions'])}</p>
    <ol class="actions">
      <li>Read any readiness issues first.</li>
      <li>Open each required source panel and inspect the verbatim content.</li>
      <li>If a source is missing or stale, continue interview/projection instead of locking.</li>
      <li>Only after the frame matches intent, run the normal OAG command for this review stage.</li>
    </ol>
  </section>

  <section class="panel">
    <h2>Readiness Issues</h2>
    <table><thead><tr><th>Code</th><th>Path</th><th>Message</th></tr></thead><tbody>{issue_rows}</tbody></table>
    <h3 style="margin-top:16px">Next Actions</h3>
    <ul class="actions">{action_rows}</ul>
  </section>

  {operation_panel}

  {checkpoint_panel}

  <section class="panel">
    <h2>Source Index</h2>
    <table>
      <thead><tr><th>Source</th><th>Path</th><th>Status</th><th>Lines</th><th>SHA-256 Prefix</th></tr></thead>
      <tbody>{''.join(source_rows)}</tbody>
    </table>
  </section>

  {''.join(sections)}
</main>
</body>
</html>
"""


def default_output_dir(frame_mode: str) -> Path:
    if frame_mode == "pre-lock":
        return Path("knowledge/lock_preview")
    return Path("knowledge/review_frames") / frame_mode


def build_frame(ip_dir: Path, output_dir: Path | None, *, readiness_mode: str, frame_mode: str = "pre-lock", include_operation_context: bool = True) -> dict[str, Any]:
    ip_dir = oag_paths.ip_root(ip_dir)
    if not ip_dir.is_dir():
        raise FileNotFoundError(f"IP directory does not exist: {ip_dir}")
    if frame_mode not in FRAME_MODES:
        raise ValueError(f"unsupported frame mode: {frame_mode}")
    if output_dir is None:
        output_dir = default_output_dir(frame_mode)
    output_dir = output_dir if output_dir.is_absolute() else ip_dir / output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    require_locked = readiness_mode == "lock-ready"
    readiness = oag_lock_readiness_check.check(ip_dir, require_locked=require_locked)
    sources = collect_sources(ip_dir)
    checkpoint_review = collect_checkpoint_review(ip_dir, readiness)
    operation_context = collect_operation_context(ip_dir) if include_operation_context else {}
    metadata = {
        "schema_version": "oag_lock_preview_frame.v1",
        "generated_at": utc_now(),
        "ip": ip_dir.name,
        "ip_dir": str(ip_dir),
        "readiness_mode": readiness_mode,
        "frame_mode": frame_mode,
        "output_dir": str(output_dir),
    }
    index_payload = {
        **metadata,
        "readiness": readiness,
        "sources": [{key: value for key, value in source.items() if key != "raw_text"} for source in sources],
        "checkpoint_review": checkpoint_review,
        "operation_context": operation_context,
    }
    html_text = render_html(ip_dir, metadata, sources, readiness, checkpoint_review, operation_context if include_operation_context else None)
    html_path = output_dir / "index.html"
    json_path = output_dir / "lock_preview_frame.json"
    html_path.write_text(html_text, encoding="utf-8")
    json_path.write_text(json.dumps(index_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {
        "schema_version": "oag_lock_preview_frame_result.v1",
        "status": "pass",
        "ip": ip_dir.name,
        "frame_mode": frame_mode,
        "html": str(html_path),
        "json": str(json_path),
        "readiness_status": readiness.get("status"),
        "readiness_issue_count": len(readiness.get("issues") or []),
        "present_sources": sum(1 for item in sources if item["exists"]),
        "missing_sources": [item["path"] for item in sources if not item["exists"]],
        "operation_context_status": operation_context.get("status") if operation_context else "disabled",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Render a formal verbatim HTML frame for OAG review.")
    parser.add_argument("--ip-dir", required=True, help="IP workspace directory.")
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Output directory. Relative paths are resolved under the IP directory. Defaults depend on --frame-mode.",
    )
    parser.add_argument(
        "--frame-mode",
        choices=sorted(FRAME_MODES),
        default="pre-lock",
        help="Review stage rendered by this frame.",
    )
    parser.add_argument(
        "--readiness-mode",
        choices=["draft", "lock-ready"],
        default="lock-ready",
        help="Use lock-ready to run hard pre-lock gates even before scope_lock.json is locked.",
    )
    parser.add_argument("--no-operation-context", action="store_true", help="Do not include read-only Mission/Action context at the top of the frame.")
    parser.add_argument("--json", action="store_true", help="Print JSON result.")
    args = parser.parse_args()
    try:
        result = build_frame(
            Path(args.ip_dir),
            Path(args.output_dir) if args.output_dir else None,
            readiness_mode=args.readiness_mode,
            frame_mode=args.frame_mode,
            include_operation_context=not args.no_operation_context,
        )
    except Exception as exc:
        result = {
            "schema_version": "oag_lock_preview_frame_result.v1",
            "status": "fail",
            "error": str(exc),
        }
        if args.json:
            print(json.dumps(result, indent=2, sort_keys=True))
        else:
            print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(f"HTML: {result['html']}")
        print(f"JSON: {result['json']}")
        print(f"Readiness: {result['readiness_status']} ({result['readiness_issue_count']} issues)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
