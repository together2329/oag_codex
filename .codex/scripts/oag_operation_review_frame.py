#!/usr/bin/env python3
"""Render a formal Mission/Action operation review frame."""

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

import oag_action_plan  # noqa: E402
import oag_action_wavefront_draft  # noqa: E402
import oag_mission_runtime  # noqa: E402
import oag_paths  # noqa: E402
import oag_role_health  # noqa: E402
from oag_run_control_common import JsonObject, collect_run_state, read_json_object, rel_to_ip, utc_now, write_json  # noqa: E402


SCHEMA_VERSION = "oag_operation_review_frame.v1"
RESULT_SCHEMA_VERSION = "oag_operation_review_frame_result.v1"


def state_file(ip_dir: Path, rel: str) -> Path:
    return oag_paths.legacy_or_hidden(ip_dir, rel)


def rows_from_index(path: Path, key: str) -> list[JsonObject]:
    payload = read_json_object(path)
    rows = payload.get(key)
    return [item for item in rows if isinstance(item, dict)] if isinstance(rows, list) else []


def action_history(ip_dir: Path) -> list[JsonObject]:
    return rows_from_index(oag_paths.state_path(ip_dir, "knowledge/actions/_index.json"), "actions")


def mission_history(ip_dir: Path) -> list[JsonObject]:
    return rows_from_index(oag_paths.state_path(ip_dir, "knowledge/missions/_index.json"), "missions")


def e(value: Any) -> str:
    return html.escape(str(value or ""))


def table(rows: list[JsonObject], columns: list[tuple[str, str]]) -> str:
    if not rows:
        return f"<tr><td colspan=\"{len(columns)}\" class=\"muted\">none</td></tr>"
    rendered: list[str] = []
    for row in rows:
        cells = []
        for key, _label in columns:
            value = row.get(key, "")
            if isinstance(value, (dict, list)):
                value = json.dumps(value, sort_keys=True)
            cells.append(f"<td>{e(value)}</td>")
        rendered.append("<tr>" + "".join(cells) + "</tr>")
    return "".join(rendered)


def thead(columns: list[tuple[str, str]]) -> str:
    return "<tr>" + "".join(f"<th>{e(label)}</th>" for _key, label in columns) + "</tr>"


def render_html(frame: JsonObject) -> str:
    mission = frame.get("current_mission") if isinstance(frame.get("current_mission"), dict) else {}
    recommended = frame.get("recommended_action") if isinstance(frame.get("recommended_action"), dict) else {}
    options = [item for item in frame.get("next_actions", []) if isinstance(item, dict)]
    graph = frame.get("action_graph") if isinstance(frame.get("action_graph"), dict) else {}
    graph_nodes = [item for item in graph.get("nodes", []) if isinstance(item, dict)]
    graph_edges = [item for item in graph.get("edges", []) if isinstance(item, dict)]
    action_rows = [item for item in frame.get("action_history", []) if isinstance(item, dict)]
    stuck_rows = [item for item in frame.get("stuck_or_open_actions", []) if isinstance(item, dict)]
    open_items = [item for item in frame.get("open_items", []) if isinstance(item, dict)]
    role_health = frame.get("role_health") if isinstance(frame.get("role_health"), dict) else {}
    role_rows = [item for item in role_health.get("roles", []) if isinstance(item, dict)]
    role_hazards = [item for item in role_health.get("hazards", []) if isinstance(item, dict)]
    wavefront_draft = frame.get("wavefront_draft") if isinstance(frame.get("wavefront_draft"), dict) else {}
    wavefront_tasks = [item for item in wavefront_draft.get("tasks", []) if isinstance(item, dict)]
    completion = frame.get("mission_completion") if isinstance(frame.get("mission_completion"), dict) else {}
    criteria = [item for item in completion.get("criteria", []) if isinstance(item, dict)]

    option_rows = "".join(
        "<tr>"
        f"<td>{'yes' if option.get('recommended') else ''}</td>"
        f"<td>{e(option.get('priority'))}</td>"
        f"<td>{e(option.get('status'))}</td>"
        f"<td><code>{e(option.get('action_type'))}</code></td>"
        f"<td>{e(option.get('action_label'))}</td>"
        f"<td>{e(option.get('recommendation_reason'))}</td>"
        f"<td>{e((option.get('score') or {}).get('total') if isinstance(option.get('score'), dict) else '')}</td>"
        f"<td><code>{e(option.get('command'))}</code></td>"
        "</tr>"
        for option in options
    )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>OAG Operation Review Frame - {e(frame.get('ip'))}</title>
  <style>
    body {{ margin:0; background:#f6f7f9; color:#111827; font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }}
    main {{ max-width:1240px; margin:0 auto; padding:32px 24px 72px; }}
    section {{ background:#fff; border:1px solid #d0d5dd; border-radius:8px; margin:16px 0; padding:18px; }}
    h1, h2 {{ margin:0 0 10px; }} p {{ color:#667085; line-height:1.5; }}
    table {{ width:100%; border-collapse:collapse; }} th, td {{ border-bottom:1px solid #e4e7ec; padding:8px; text-align:left; vertical-align:top; }}
    th {{ color:#667085; font-size:12px; text-transform:uppercase; letter-spacing:.04em; }}
    code, pre {{ font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; overflow-wrap:anywhere; }}
    pre {{ background:#101828; color:#f9fafb; padding:14px; border-radius:8px; overflow:auto; }}
    .grid {{ display:grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap:12px; }}
    .metric {{ border:1px solid #d0d5dd; border-radius:8px; padding:14px; background:#fff; }}
    .metric span {{ display:block; color:#667085; font-size:12px; }} .metric strong {{ display:block; margin-top:4px; font-size:18px; }}
    .badge {{ display:inline-block; border:1px solid currentColor; border-radius:999px; padding:4px 10px; font-weight:700; color:#0f766e; }}
    .muted {{ color:#667085; }}
    @media (max-width: 900px) {{ main {{ padding:20px 12px 48px; }} .grid {{ grid-template-columns:repeat(2, minmax(0, 1fr)); }} }}
  </style>
</head>
<body>
<main>
  <section>
    <h1>OAG Operation Review Frame: {e(frame.get('ip'))}</h1>
    <p>This is a formal operating view over Mission and Action objects. Source JSON remains the source of truth; this page only renders current records without rewriting them.</p>
    <span class="badge">{e(frame.get('frame_status'))}</span>
  </section>
  <div class="grid">
    <div class="metric"><span>Generated</span><strong>{e(frame.get('generated_at'))}</strong></div>
    <div class="metric"><span>Mission</span><strong>{e(mission.get('template_id'))}</strong></div>
    <div class="metric"><span>Open Items</span><strong>{len(open_items)}</strong></div>
    <div class="metric"><span>Mission Completion</span><strong>{e(completion.get('status'))}</strong></div>
  </div>
  <section><h2>Current Mission</h2>
    <table><thead><tr><th>ID</th><th>Template</th><th>Status</th><th>Started</th><th>Last Observed</th><th>Actions</th></tr></thead>
    <tbody><tr><td><code>{e(mission.get('id'))}</code></td><td><code>{e(mission.get('template_id'))}</code></td><td>{e(mission.get('status'))}</td><td>{e(mission.get('started_at'))}</td><td>{e(mission.get('last_observed_at'))}</td><td>{len(mission.get('action_instance_refs', [])) if isinstance(mission.get('action_instance_refs'), list) else 0}</td></tr></tbody></table>
  </section>
  <section><h2>Recommended Action</h2>
    <p><code>{e(recommended.get('action_type'))}</code> - {e(recommended.get('recommendation_reason'))}</p>
    <p>Score: <strong>{e((recommended.get('score') or {}).get('total') if isinstance(recommended.get('score'), dict) else '')}</strong></p>
  </section>
  <section><h2>Four Options</h2>
    <table><thead><tr><th>Recommended</th><th>Priority</th><th>Status</th><th>Type</th><th>Action</th><th>Why</th><th>Score</th><th>Command</th></tr></thead><tbody>{option_rows}</tbody></table>
  </section>
  <section><h2>Open Items</h2>
    <table><thead>{thead([('id','ID'),('severity','Severity'),('code','Code'),('message','Message'),('source','Source'),('path','Path')])}</thead><tbody>{table(open_items, [('id','ID'),('severity','Severity'),('code','Code'),('message','Message'),('source','Source'),('path','Path')])}</tbody></table>
  </section>
  <section><h2>Action Graph Nodes</h2>
    <table><thead>{thead([('id','ID'),('action_type','Action Type'),('priority','Priority'),('status','Status'),('recommended','Recommended'),('score','Score')])}</thead><tbody>{table(graph_nodes, [('id','ID'),('action_type','Action Type'),('priority','Priority'),('status','Status'),('recommended','Recommended'),('score','Score')])}</tbody></table>
  </section>
  <section><h2>Action Graph Edges</h2>
    <table><thead>{thead([('from','From'),('to','To'),('kind','Kind'),('reason','Reason')])}</thead><tbody>{table(graph_edges, [('from','From'),('to','To'),('kind','Kind'),('reason','Reason')])}</tbody></table>
  </section>
  <section><h2>Wavefront Draft</h2>
    <p class="muted">Draft only. This does not claim, dispatch, or mutate wavefront state.</p>
    <table><thead>{thead([('task_id','Task'),('action_type','Action Type'),('agent_type','Agent'),('phase','Phase'),('depends_on','Depends On'),('ownership_mode','Ownership')])}</thead><tbody>{table(wavefront_tasks, [('task_id','Task'),('action_type','Action Type'),('agent_type','Agent'),('phase','Phase'),('depends_on','Depends On'),('ownership_mode','Ownership')])}</tbody></table>
  </section>
  <section><h2>Role Health</h2>
    <table><thead>{thead([('role','Role'),('status','Status'),('actions_total','Actions'),('accepted','Accepted'),('bad_terminal','Bad Terminal'),('open','Open'),('stuck','Stuck')])}</thead><tbody>{table(role_rows, [('role','Role'),('status','Status'),('actions_total','Actions'),('accepted','Accepted'),('bad_terminal','Bad Terminal'),('open','Open'),('stuck','Stuck')])}</tbody></table>
    <h3>Role Hazards</h3>
    <table><thead>{thead([('role','Role'),('code','Code'),('message','Message')])}</thead><tbody>{table(role_hazards, [('role','Role'),('code','Code'),('message','Message')])}</tbody></table>
  </section>
  <section><h2>Mission Completion Criteria</h2>
    <table><thead>{thead([('name','Criterion'),('passed','Passed'),('detail','Detail')])}</thead><tbody>{table(criteria, [('name','Criterion'),('passed','Passed'),('detail','Detail')])}</tbody></table>
  </section>
  <section><h2>Action History</h2>
    <table><thead>{thead([('id','ID'),('action_type','Action Type'),('status','Status'),('candidate_ref','Candidate'),('started_at','Started'),('completed_at','Completed'),('summary','Summary')])}</thead><tbody>{table(action_rows, [('id','ID'),('action_type','Action Type'),('status','Status'),('candidate_ref','Candidate'),('started_at','Started'),('completed_at','Completed'),('summary','Summary')])}</tbody></table>
  </section>
  <section><h2>Stuck or Open Actions</h2>
    <table><thead>{thead([('id','ID'),('action_type','Action Type'),('status','Status'),('started_at','Started'),('path','Path')])}</thead><tbody>{table(stuck_rows, [('id','ID'),('action_type','Action Type'),('status','Status'),('started_at','Started'),('path','Path')])}</tbody></table>
  </section>
  <section><h2>Raw JSON Snapshot</h2><pre>{e(json.dumps(frame, indent=2, sort_keys=True))}</pre></section>
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

    plan_result = oag_action_plan.build_plan(ip_dir, write=True, run_semantic_checks=False)
    plan = plan_result.get("plan") if isinstance(plan_result.get("plan"), dict) else {}
    graph = plan_result.get("dependency_graph") if isinstance(plan_result.get("dependency_graph"), dict) else read_json_object(state_file(ip_dir, "ontology/generated/action_graph.json"))
    wavefront_draft = oag_action_wavefront_draft.build_draft(ip_dir, max_tasks=8, refresh_plan=False)
    oag_action_wavefront_draft.write_draft(ip_dir, wavefront_draft)
    role_health = oag_role_health.collect_role_health(ip_dir)
    oag_role_health.write_role_health(ip_dir, role_health)
    oag_mission_runtime.write_index(ip_dir)
    active_mission = oag_mission_runtime.latest_active_mission(ip_dir)
    active_mission.pop("_path", None)
    mission_completion = oag_mission_runtime.evaluate_mission_completion(ip_dir, str(active_mission.get("id") or "active")) if active_mission else {}
    action_index_path = oag_paths.state_path(ip_dir, "knowledge/actions/_index.json")
    actions = action_history(ip_dir)
    open_actions = [item for item in actions if item.get("status") not in {"accepted", "rejected", "blocked", "failed", "inconclusive", "aborted"}]
    candidates = [item for item in plan.get("candidates", []) if isinstance(item, dict)]
    recommended = next((item for item in candidates if item.get("recommended") is True), candidates[0] if candidates else {})

    frame: JsonObject = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": utc_now(),
        "ip": ip_dir.name,
        "ip_dir": str(ip_dir),
        "frame_status": "review_ready" if plan_result.get("status") == "pass" else "needs_attention",
        "current_mission": active_mission,
        "mission_history": mission_history(ip_dir),
        "recommended_action": recommended,
        "next_actions": candidates[:4],
        "open_items": plan.get("open_items") if isinstance(plan.get("open_items"), list) else [],
        "action_graph": graph,
        "wavefront_draft": wavefront_draft,
        "role_health": role_health,
        "mission_completion": mission_completion,
        "action_history": actions,
        "stuck_or_open_actions": open_actions,
        "sources": {
            "action_candidates": rel_to_ip(ip_dir, state_file(ip_dir, "ontology/generated/action_candidates.json")),
            "action_graph": rel_to_ip(ip_dir, state_file(ip_dir, "ontology/generated/action_graph.json")),
            "mission_index": rel_to_ip(ip_dir, oag_paths.state_path(ip_dir, "knowledge/missions/_index.json")),
            "action_index": rel_to_ip(ip_dir, action_index_path),
            "wavefront_draft": rel_to_ip(ip_dir, state_file(ip_dir, "ontology/generated/action_wavefront_draft.json")),
            "role_health": rel_to_ip(ip_dir, oag_paths.state_path(ip_dir, "knowledge/operations/role_health.json")),
        },
        "run_state": collect_run_state(ip_dir),
    }
    json_path = output_dir / "operation_frame.json"
    html_path = output_dir / "index.html"
    write_json(json_path, frame)
    html_path.write_text(render_html(frame), encoding="utf-8")
    return {
        "schema_version": RESULT_SCHEMA_VERSION,
        "status": "pass",
        "ip": ip_dir.name,
        "html": str(html_path),
        "json": str(json_path),
        "frame_status": frame["frame_status"],
        "mission_id": active_mission.get("id") or "",
        "mission_completion_status": mission_completion.get("status") or "",
        "recommended_action": recommended,
        "action_history_count": len(actions),
        "wavefront_draft_task_count": len(wavefront_draft.get("tasks", []) if isinstance(wavefront_draft.get("tasks"), list) else []),
        "role_health_hazard_count": len(role_health.get("hazards", []) if isinstance(role_health.get("hazards"), list) else []),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ip-dir", required=True)
    parser.add_argument("--output-dir", default="knowledge/operation_frames/latest")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        result = build_frame(Path(args.ip_dir), Path(args.output_dir))
    except Exception as exc:
        result = {"schema_version": RESULT_SCHEMA_VERSION, "status": "fail", "issues": [{"code": "OPERATION_FRAME_EXCEPTION", "message": str(exc)}]}
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    elif result.get("status") == "pass":
        print(f"HTML: {result['html']}")
        print(f"JSON: {result['json']}")
    else:
        print(f"FAIL {RESULT_SCHEMA_VERSION}", file=sys.stderr)
        for item in result.get("issues", []):
            print(f"- {item.get('code')}: {item.get('message')}", file=sys.stderr)
    return 0 if result.get("status") == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
