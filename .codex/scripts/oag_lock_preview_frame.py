#!/usr/bin/env python3
"""Render a verbatim pre-lock OAG review frame as static HTML."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import html
import json
import sys
from pathlib import Path
from typing import Any

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import oag_lock_readiness_check  # noqa: E402
import oag_paths  # noqa: E402


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


def render_html(ip_dir: Path, metadata: dict[str, Any], sources: list[dict[str, Any]], readiness: dict[str, Any]) -> str:
    mode = str(metadata.get("frame_mode") or "pre-lock")
    mode_cfg = FRAME_MODES.get(mode, FRAME_MODES["pre-lock"])
    status = str(readiness.get("status") or "unknown")
    issues = readiness.get("issues") if isinstance(readiness.get("issues"), list) else []
    next_actions = readiness.get("next_actions") if isinstance(readiness.get("next_actions"), list) else []
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
        summary = source.get("summary") if isinstance(source.get("summary"), dict) else {}
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
    @media (max-width: 860px) {{
      main {{ padding: 20px 12px 48px; }}
      .grid {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
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


def build_frame(ip_dir: Path, output_dir: Path | None, *, readiness_mode: str, frame_mode: str = "pre-lock") -> dict[str, Any]:
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
    }
    html_text = render_html(ip_dir, metadata, sources, readiness)
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
    parser.add_argument("--json", action="store_true", help="Print JSON result.")
    args = parser.parse_args()
    try:
        result = build_frame(
            Path(args.ip_dir),
            Path(args.output_dir) if args.output_dir else None,
            readiness_mode=args.readiness_mode,
            frame_mode=args.frame_mode,
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
