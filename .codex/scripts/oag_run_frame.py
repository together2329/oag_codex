#!/usr/bin/env python3
"""Generate an OAG run-control status frame as JSON and static HTML."""

from __future__ import annotations

import argparse
import html
import json
import sys
from pathlib import Path
from typing import Any

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import oag_paths  # noqa: E402
import oag_action_plan  # noqa: E402
from oag_run_control_common import JsonObject, collect_run_state, issue, utc_now, write_json  # noqa: E402


SCHEMA_VERSION = "oag_run_frame.v1"
RESULT_SCHEMA_VERSION = "oag_run_frame_result.v1"


def _bool_issue(flag: bool, code: str, message: str, path: str = "") -> list[dict[str, str]]:
    return [issue(code, message, path)] if flag else []


def classify_blockers(state: JsonObject) -> list[dict[str, str]]:
    blockers: list[dict[str, str]] = []
    blockers.extend(state.get("git", {}).get("issues", []))
    scope = state.get("scope_lock", {})
    if scope.get("state") not in {"draft", "locked"}:
        blockers.append(issue("SCOPE_LOCK_MISSING", "ontology/scope_lock.json is missing or unreadable", scope.get("path", "")))
    blockers.extend(_bool_issue(state.get("wavefront", {}).get("active_lock_count", 0) > 0, "ACTIVE_WAVEFRONT_LOCKS", "active wavefront ownership locks are present"))
    blockers.extend(_bool_issue(bool(state.get("gates", {}).get("pending_gate_count", 0)), "PENDING_WORKFLOW_GATE", "at least one required OAG gate is pending"))
    blockers.extend(_bool_issue(bool(state.get("gates", {}).get("gate_decision_stale")), "GATE_DECISION_STALE", "gate decision is older than the validation report"))
    compile_state = state.get("compile_manifest", {})
    if compile_state.get("status") in {"missing", "stale"}:
        blockers.append(issue("COMPILE_MANIFEST_NOT_FRESH", f"compile manifest status is {compile_state.get('status')}", compile_state.get("path", "")))
    stale = state.get("stale_lifecycle", {})
    if stale.get("status") == "fail":
        blockers.append(issue("STALE_LIFECYCLE", "lifecycle stale check has issues", str(stale.get("lifecycle_path") or "")))
    return blockers


def actions_from_candidates(action_plan: JsonObject) -> list[JsonObject]:
    plan = action_plan.get("plan") if isinstance(action_plan.get("plan"), dict) else {}
    candidates = [item for item in plan.get("candidates", []) if isinstance(item, dict)]
    actions: list[JsonObject] = []
    for candidate in candidates[:4]:
        actions.append(
            {
                "id": candidate.get("id") or candidate.get("action_type") or "action-candidate",
                "label": candidate.get("action_label") or candidate.get("action_type") or "Action candidate",
                "recommended": bool(candidate.get("recommended")),
                "command": candidate.get("command") or "",
                "description": candidate.get("recommendation_reason") or "",
                "action_type": candidate.get("action_type") or "",
                "priority": candidate.get("priority") or "",
                "status": candidate.get("status") or "",
                "owner_role": candidate.get("owner_role") or "",
                "score": candidate.get("score") if isinstance(candidate.get("score"), dict) else {},
            }
        )
    if actions and not any(item.get("recommended") for item in actions):
        actions[0]["recommended"] = True
    return actions


def generic_fallback_actions() -> list[JsonObject]:
    return [
        {
            "id": "render-review-frame",
            "label": "Render the current review frame",
            "recommended": False,
            "command": "python3 .codex/scripts/oag_review_frame.py --ip-dir <ip> --mode pre-dispatch --json",
            "description": "Create a formal HTML surface over current source and artifact hashes before review.",
            "action_type": "ACT_RENDER_LOCK_PREVIEW",
            "priority": "P3",
            "status": "ready",
            "owner_role": "tool",
        },
        {
            "id": "check-closure-evidence",
            "label": "Run closure/evidence checks",
            "recommended": False,
            "command": "python3 .codex/scripts/oag_closure_check.py --ip-dir <ip> --json",
            "description": "Inspect traceability, scoreboard, coverage, validation, and completion readiness.",
            "action_type": "ACT_EVIDENCE_VALIDATION",
            "priority": "P3",
            "status": "ready",
            "owner_role": "oag-evidence-validator",
        },
        {
            "id": "custom-action",
            "label": "Other / custom action",
            "recommended": False,
            "command": "",
            "description": "Use a narrower action if the frame shows a project-specific reason not captured above.",
            "action_type": "ACT_CUSTOM_OPERATOR_INPUT",
            "priority": "P3",
            "status": "informational",
            "owner_role": "human_via_main",
        },
    ]


def fill_to_four(actions: list[JsonObject]) -> list[JsonObject]:
    seen = {str(action.get("id") or "") for action in actions}
    for action in generic_fallback_actions():
        if len(actions) >= 4:
            break
        if action["id"] not in seen:
            actions.append(action)
            seen.add(action["id"])
    return actions[:4]


def next_actions(state: JsonObject, blockers: list[dict[str, str]], action_plan: JsonObject | None = None) -> list[JsonObject]:
    candidate_actions = actions_from_candidates(action_plan or {})
    if candidate_actions:
        return fill_to_four(candidate_actions)

    scope_state = state.get("scope_lock", {}).get("state")
    active_locks = state.get("wavefront", {}).get("active_lock_count", 0)
    compile_state = state.get("compile_manifest", {}).get("status")
    ssot_state = state.get("ssot", {}).get("status")
    pending_gates = state.get("gates", {}).get("pending_gate_count", 0)
    gate_stale = state.get("gates", {}).get("gate_decision_stale")

    actions: list[JsonObject] = []
    if active_locks:
        actions.append(
            {
                "id": "run-orchestration-guard",
                "label": "Audit active orchestration locks",
                "recommended": True,
                "command": "python3 .codex/scripts/oag_orchestration_guard.py audit --ip-dir <ip> --json",
                "description": "Classify stuck locks, late receipts, and safe replacement-dispatch options before opening more work.",
            }
        )
    elif pending_gates:
        actions.append(
            {
                "id": "answer-pending-gate",
                "label": "Resolve the pending gate",
                "recommended": True,
                "command": "python3 .codex/scripts/oag_gate_frame.py list --ip-dir <ip> --json",
                "description": "A required user or reviewer decision is pending; do not continue execution around it.",
            }
        )
    elif compile_state in {"missing", "stale"}:
        actions.append(
            {
                "id": "refresh-compile",
                "label": "Refresh OAG compile outputs",
                "recommended": True,
                "command": "python3 .codex/scripts/oag_cli.py call oag.compile --file <compile_args.json>",
                "description": "Generated authoring/evidence projections are not fresh enough for dispatch or review.",
            }
        )
    elif ssot_state == "fail":
        actions.append(
            {
                "id": "repair-ssot",
                "label": "Repair required SSOT sections",
                "recommended": True,
                "command": "python3 .codex/scripts/oag_ssot_section_check.py --ip-dir <ip> --json",
                "description": "Required feature, requirement, contract, verification, or integration sections are missing or empty.",
            }
        )
    elif scope_state != "locked":
        actions.append(
            {
                "id": "continue-interview",
                "label": "Continue interview and pre-lock review",
                "recommended": True,
                "command": "python3 .codex/scripts/oag_lock_preview_frame.py --ip-dir <ip> --readiness-mode draft --json",
                "description": "Scope is not locked; keep decisions draft and show the human-readable review frame before lock.",
            }
        )
    elif gate_stale:
        actions.append(
            {
                "id": "refresh-gate-review",
                "label": "Refresh gate review",
                "recommended": True,
                "command": "python3 .codex/scripts/oag_review_frame.py --ip-dir <ip> --mode gate --json",
                "description": "Validation changed after gate approval; generate a fresh gate review frame and decision.",
            }
        )
    else:
        actions.append(
            {
                "id": "proceed-wavefront",
                "label": "Proceed to the next dependency-ready OAG wavefront",
                "recommended": True,
                "command": "python3 .codex/scripts/oag_wavefront.py ready --ip-dir <ip> --run-id <run> --json",
                "description": "No obvious run-control blocker was detected in the current frame.",
            }
        )

    return fill_to_four(actions)


def run_status(blockers: list[dict[str, str]]) -> str:
    if any(item["code"] in {"ACTIVE_WAVEFRONT_LOCKS", "PENDING_WORKFLOW_GATE"} for item in blockers):
        return "blocked"
    if blockers:
        return "needs_action"
    return "ready"


def render_table(rows: list[JsonObject], columns: list[str]) -> str:
    if not rows:
        return f"<tr><td colspan=\"{len(columns)}\" class=\"muted\">none</td></tr>"
    body = []
    for row in rows:
        body.append("<tr>" + "".join(f"<td>{html.escape(str(row.get(col, '')))}</td>" for col in columns) + "</tr>")
    return "".join(body)


def render_html(frame: JsonObject) -> str:
    state = frame["state"]
    blockers = frame["blockers"]
    actions = frame["next_actions"]
    action_plan = frame.get("action_plan") if isinstance(frame.get("action_plan"), dict) else {}
    status = frame["run_status"]
    status_class = "pass" if status == "ready" else "fail" if status == "blocked" else "warn"
    action_rows = "".join(
        "<tr>"
        f"<td>{'yes' if action.get('recommended') else ''}</td>"
        f"<td>{html.escape(str(action.get('priority') or ''))}</td>"
        f"<td>{html.escape(str(action.get('status') or ''))}</td>"
        f"<td><code>{html.escape(str(action.get('action_type') or action.get('id') or ''))}</code></td>"
        f"<td>{html.escape(action['label'])}</td>"
        f"<td>{html.escape(action['description'])}</td>"
        f"<td>{html.escape(str(action.get('owner_role') or ''))}</td>"
        f"<td><code>{html.escape(action.get('command') or 'custom')}</code></td>"
        "</tr>"
        for action in actions
    )
    blocker_rows = render_table(blockers, ["code", "message", "path"])
    lock_rows = render_table(state.get("wavefront", {}).get("active_locks", []), ["run_id", "task_id", "path", "dispatch_id", "claimed_at", "age_seconds"])
    pending_gate_rows = render_table(state.get("gates", {}).get("pending_gates", []), ["gate_id", "stage", "kind", "created_at", "path"])
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>OAG Run Frame - {html.escape(state['ip'])}</title>
  <style>
    body {{ margin: 0; background: #f7f8fa; color: #1f2937; font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }}
    main {{ max-width: 1180px; margin: 0 auto; padding: 32px 24px 64px; }}
    section {{ background: #fff; border: 1px solid #d0d5dd; border-radius: 8px; padding: 18px; margin: 16px 0; }}
    h1, h2 {{ margin: 0 0 10px; }} p {{ color: #667085; }}
    table {{ width: 100%; border-collapse: collapse; }} th, td {{ border-bottom: 1px solid #d0d5dd; padding: 9px; text-align: left; vertical-align: top; }}
    th {{ color: #667085; font-size: 12px; text-transform: uppercase; letter-spacing: .04em; }}
    code {{ font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; overflow-wrap: anywhere; }}
    .badge {{ display: inline-block; border: 1px solid currentColor; border-radius: 999px; padding: 4px 10px; font-weight: 700; }}
    .pass {{ color: #0f766e; }} .warn {{ color: #b54708; }} .fail {{ color: #b42318; }} .muted {{ color: #667085; }}
    .grid {{ display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; }}
    .metric {{ background: #fff; border: 1px solid #d0d5dd; border-radius: 8px; padding: 14px; }}
    .metric span {{ display:block; color:#667085; font-size:12px; }} .metric strong {{ display:block; margin-top:4px; font-size:20px; }}
    @media (max-width: 860px) {{ main {{ padding: 20px 12px 48px; }} .grid {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }} }}
  </style>
</head>
<body>
<main>
  <section>
    <h1>OAG Run Frame: {html.escape(state['ip'])}</h1>
    <p>This frame is a run-control snapshot. JSON is the source of truth; this HTML is the human review surface.</p>
    <div class="badge {status_class}">Run status: {html.escape(status)}</div>
  </section>
  <div class="grid">
    <div class="metric"><span>Generated</span><strong>{html.escape(frame['generated_at'])}</strong></div>
    <div class="metric"><span>Scope lock</span><strong>{html.escape(str(state.get('scope_lock', {}).get('state')))}</strong></div>
    <div class="metric"><span>Active locks</span><strong>{html.escape(str(state.get('wavefront', {}).get('active_lock_count', 0)))}</strong></div>
    <div class="metric"><span>Blockers</span><strong>{html.escape(str(len(blockers)))}</strong></div>
  </div>
  <section><h2>Mission/Action Plan</h2>
    <p>Mission template: <code>{html.escape(str(action_plan.get('mission_template') or 'unknown'))}</code>.
    Candidate source: <code>{html.escape(str(action_plan.get('output_path') or 'fallback'))}</code>.</p>
    <table><thead><tr><th>Recommended</th><th>Priority</th><th>Status</th><th>Action Type</th><th>Action</th><th>Why</th><th>Owner</th><th>Command</th></tr></thead><tbody>{action_rows}</tbody></table>
  </section>
  <section><h2>Blockers</h2><table><thead><tr><th>Code</th><th>Message</th><th>Path</th></tr></thead><tbody>{blocker_rows}</tbody></table></section>
  <section><h2>Active Wavefront Locks</h2><table><thead><tr><th>Run</th><th>Task</th><th>Path</th><th>Dispatch</th><th>Claimed</th><th>Age Seconds</th></tr></thead><tbody>{lock_rows}</tbody></table></section>
  <section><h2>Pending Gates</h2><table><thead><tr><th>Gate</th><th>Stage</th><th>Kind</th><th>Created</th><th>Path</th></tr></thead><tbody>{pending_gate_rows}</tbody></table></section>
  <section><h2>Raw JSON Snapshot</h2><pre><code>{html.escape(json.dumps(frame, indent=2, sort_keys=True))}</code></pre></section>
</main>
</body>
</html>
"""


def build_frame(ip_dir: Path, output_dir: Path) -> JsonObject:
    ip_dir = oag_paths.ip_root(ip_dir)
    if not ip_dir.is_dir():
        raise FileNotFoundError(f"IP directory does not exist: {ip_dir}")
    output_dir = output_dir if output_dir.is_absolute() else ip_dir / output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    state = collect_run_state(ip_dir)
    blockers = classify_blockers(state)
    action_plan = oag_action_plan.build_plan(ip_dir, write=True, run_semantic_checks=False)
    frame: JsonObject = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": utc_now(),
        "ip": ip_dir.name,
        "ip_dir": str(ip_dir),
        "run_status": run_status(blockers),
        "blockers": blockers,
        "next_actions": next_actions(state, blockers, action_plan),
        "action_plan": {
            "status": action_plan.get("status"),
            "mission_template": action_plan.get("mission_template"),
            "mission_instance_id": action_plan.get("mission_instance_id"),
            "output_path": action_plan.get("output_path"),
            "action_graph_path": action_plan.get("action_graph_path"),
            "candidate_count": action_plan.get("candidate_count"),
            "open_item_count": action_plan.get("open_item_count"),
            "recommended_action": action_plan.get("recommended_action"),
            "issues": action_plan.get("issues", []),
        },
        "required_user_decision": bool(state.get("gates", {}).get("pending_gate_count") or state.get("scope_lock", {}).get("state") == "draft"),
        "state": state,
    }
    json_path = output_dir / "run_frame.json"
    html_path = output_dir / "index.html"
    write_json(json_path, frame)
    html_path.write_text(render_html(frame), encoding="utf-8")
    return {
        "schema_version": RESULT_SCHEMA_VERSION,
        "status": "pass",
        "ip": ip_dir.name,
        "run_status": frame["run_status"],
        "html": str(html_path),
        "json": str(json_path),
        "blocker_count": len(blockers),
        "recommended_action": next((action for action in frame["next_actions"] if action.get("recommended")), frame["next_actions"][0]),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ip-dir", required=True)
    parser.add_argument("--output-dir", default="knowledge/run_frames/latest")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        result = build_frame(Path(args.ip_dir), Path(args.output_dir))
    except Exception as exc:
        result = {"schema_version": RESULT_SCHEMA_VERSION, "status": "fail", "error": str(exc)}
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
        print(f"Run status: {result['run_status']} ({result['blocker_count']} blockers)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
