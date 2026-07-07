#!/usr/bin/env python3
from __future__ import annotations

import argparse, glob, json, re, sys
from collections import Counter; from datetime import datetime, timezone; from pathlib import Path; from typing import Optional


SCHEMA_VERSION = "oag_debug_eval_metrics.v1"; EVIDENCE_RE = re.compile(r"OAG_EVIDENCE_RECORDED:\s*`?([^`\s,]+)`?")
AGENT_RE = re.compile(r"\b(close_agent|wait_agent|spawn_agent|multi_agent|send_message_to_thread|handoff_thread)\b"); INTERVIEW_RE = re.compile(r"\b(deep[-_ ]interview|interview hook|oag-deep-interview)\b", re.I)
MCP_START_RE = re.compile(r"Starting MCP servers|MCP Tools|/mcp", re.I)
COMPUTER_USE_RE = re.compile(r"computer-use|Codex Computer Use", re.I)


def as_dict(value: object) -> dict[str, object]:
    return value if isinstance(value, dict) else {}


def as_list(value: object) -> list[object]: return value if isinstance(value, list) else []


def is_pass_status(value: object) -> bool: return isinstance(value, str) and (value.lower() in ("pass", "pass_with_warnings") or value.upper().endswith("_PASS"))


def now_iso() -> str:
    return iso(datetime.now(timezone.utc)) or ""


def parse_ts(value: object) -> Optional[datetime]:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def iso(value: Optional[datetime]) -> Optional[str]:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def duration(start: Optional[datetime], end: Optional[datetime]) -> Optional[float]:
    if start is None or end is None:
        return None
    return round((end - start).total_seconds(), 3)


def compact(value: object, limit: int = 500) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        text = value
    else:
        try:
            text = json.dumps(value, ensure_ascii=True, sort_keys=True)
        except TypeError:
            text = str(value)
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 3] + "..."


def read_jsonl(path: Path) -> tuple[list[dict[str, object]], list[str]]:
    rows: list[dict[str, object]] = []
    errors: list[str] = []
    try:
        with path.open("r", encoding="utf-8") as handle:
            for line_no, line in enumerate(handle, 1):
                if not line.strip():
                    continue
                try:
                    value = json.loads(line)
                except json.JSONDecodeError as exc:
                    errors.append(f"{path}:{line_no}: {exc.msg}")
                    continue
                if isinstance(value, dict):
                    rows.append(value)
                else:
                    errors.append(f"{path}:{line_no}: top-level JSON is not an object")
    except OSError as exc:
        errors.append(f"{path}: {exc}")
    return rows, errors


def message_text(payload: dict[str, object]) -> str:
    if payload.get("type") == "agent_message":
        return compact(payload.get("message"), 4000)
    if payload.get("type") != "message":
        return ""
    parts: list[str] = []
    content = payload.get("content")
    if not isinstance(content, list):
        return ""
    for item in content:
        data = as_dict(item)
        for key in ("text", "input_text", "output_text"):
            value = data.get(key)
            if isinstance(value, str):
                parts.append(value)
    return "\n".join(parts)


def clean_evidence(value: str) -> Optional[str]:
    marker = value.strip("`'\" ,.;:)]}")
    if not marker or marker.startswith("<") or marker.startswith("..."):
        return None
    if "/" not in marker and "." not in marker:
        return None
    return marker


def start_call(payload: dict[str, object], at: Optional[datetime]) -> Optional[dict[str, object]]:
    payload_type = payload.get("type")
    if payload_type not in ("function_call", "custom_tool_call"):
        return None
    call_id = payload.get("call_id") or payload.get("id")
    if not isinstance(call_id, str) or not call_id:
        return None
    name = payload.get("name")
    if not isinstance(name, str) or not name:
        name = str(payload_type)
    preview = compact(payload.get("arguments") if payload.get("arguments") is not None else payload.get("input"))
    combined = f"{name} {preview}"
    return {
        "call_id": call_id,
        "name": name,
        "started_at": at,
        "ended_at": None,
        "duration_s": None,
        "status": "open",
        "agent_management": bool(AGENT_RE.search(combined)),
        "parallel_batch": "multi_tool_use.parallel" in combined,
        "preview": preview,
    }


def end_call(payload: dict[str, object], at: Optional[datetime]) -> Optional[tuple[str, datetime, str]]:
    if payload.get("type") not in ("function_call_output", "custom_tool_call_output", "patch_apply_end"):
        return None
    call_id = payload.get("call_id")
    if not isinstance(call_id, str) or not call_id:
        return None
    status = payload.get("status")
    return call_id, at or datetime.now(timezone.utc), status if isinstance(status, str) and status else "completed"


def top_numeric(rows: list[dict[str, object]], key: str, limit: int = 8) -> list[dict[str, object]]:
    def value(row: dict[str, object]) -> float:
        item = row.get(key)
        return float(item) if isinstance(item, (int, float)) else -1.0

    return sorted(rows, key=value, reverse=True)[:limit]


def metric_at_least(row: dict[str, object], key: str, threshold: float) -> bool:
    item = row.get(key)
    return isinstance(item, (int, float)) and float(item) >= threshold


def normalize_call_times(rows: list[dict[str, object]]) -> None:
    for row in rows:
        started = row.get("started_at")
        ended = row.get("ended_at")
        if isinstance(started, datetime):
            row["started_at"] = iso(started)
        if isinstance(ended, datetime):
            row["ended_at"] = iso(ended)


def session_meta(payload: dict[str, object]) -> dict[str, object]:
    if payload.get("type") != "session_meta":
        return {}
    keys = ("id", "cwd", "originator", "cli_version", "model", "agent_nickname", "agent_role", "parent_thread_id")
    return {key: payload.get(key) for key in keys if isinstance(payload.get(key), (str, int, float, bool)) or payload.get(key) is None}


def summarize_session(path: Path, long_tool_s: float) -> dict[str, object]:
    events, errors = read_jsonl(path)
    first: Optional[datetime] = None
    last: Optional[datetime] = None
    meta: dict[str, object] = {}
    started: dict[str, dict[str, object]] = {}
    done: list[dict[str, object]] = []
    evidence: set[str] = set()
    runtime_markers: Counter[str] = Counter()

    for event in events:
        at = parse_ts(event.get("timestamp"))
        if at is not None:
            first = at if first is None or at < first else first
            last = at if last is None or at > last else last

        payload = as_dict(event.get("payload"))
        if not meta:
            meta = session_meta(payload)

        call = start_call(payload, at)
        if call is not None:
            started[str(call["call_id"])] = call
            continue

        call_end = end_call(payload, at)
        if call_end is not None:
            call_id, ended_at, status = call_end
            maybe_row = started.pop(call_id, None)
            row: dict[str, object]
            if maybe_row is None:
                row = {"call_id": call_id, "name": "unknown", "started_at": None, "agent_management": False, "parallel_batch": False, "preview": ""}
            else:
                row = maybe_row
            row_started = row.get("started_at")
            row["ended_at"] = ended_at
            row["duration_s"] = duration(row_started if isinstance(row_started, datetime) else None, ended_at)
            row["status"] = status
            done.append(row)
            continue

        text = message_text(payload)
        if text:
            if MCP_START_RE.search(text):
                runtime_markers["mcp_start_seen"] += 1
            if COMPUTER_USE_RE.search(text):
                runtime_markers["computer_use_seen"] += 1
            for match in EVIDENCE_RE.finditer(text):
                marker = clean_evidence(match.group(1))
                if marker:
                    evidence.add(marker)

    open_calls = list(started.values())
    all_calls = done + open_calls
    normalize_call_times(all_calls)
    completed = [row for row in all_calls if row.get("status") != "open"]
    long_calls = [row for row in completed if metric_at_least(row, "duration_s", long_tool_s)]
    agent_calls = [row for row in all_calls if row.get("agent_management")]
    agent_parallel = [row for row in agent_calls if row.get("parallel_batch")]
    by_name = Counter(str(row.get("name", "unknown")) for row in all_calls)
    status = "no_events" if not events else "evidence_recorded" if evidence else "no_evidence_recorded"
    if open_calls:
        status = "tool_calls_open"

    return {
        "path": str(path),
        "event_count": len(events),
        "read_errors": errors,
        "started_at": iso(first),
        "ended_at": iso(last),
        "duration_s": duration(first, last),
        "status": status,
        "meta": meta,
        "tool_calls": {
            "total": len(all_calls),
            "completed": len(completed),
            "open": len(open_calls),
            "long": len(long_calls),
            "agent_management": len(agent_calls),
            "agent_management_in_parallel": len(agent_parallel),
            "by_name": dict(by_name.most_common()),
            "longest": top_numeric(completed, "duration_s"),
            "open_calls": open_calls[:8],
            "long_calls": top_numeric(long_calls, "duration_s"),
        },
        "evidence_recorded": sorted(evidence),
        "runtime_markers": dict(runtime_markers),
    }


def status_counts(rows: object) -> dict[str, int]:
    counts: Counter[str] = Counter()
    if isinstance(rows, list):
        for row in rows:
            status = as_dict(row).get("status")
            if isinstance(status, str) and status:
                counts[status] += 1
    return dict(counts)


def summarize_receipt(path: Path) -> dict[str, object]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {"path": str(path), "read_error": str(exc), "status": "unreadable"}
    data = as_dict(raw)
    if not data:
        return {"path": str(path), "read_error": "top-level JSON is not an object", "status": "unreadable"}
    checks = data.get("checks_run")
    blockers = data.get("blockers")
    risks = data.get("residual_risks")
    return {
        "path": str(path),
        "schema_version": data.get("schema_version"),
        "status": data.get("status", "unknown"),
        "handoff": data.get("handoff"),
        "agent_role": data.get("agent_role"),
        "may_claim_complete": data.get("may_claim_complete"),
        "checks": {"total": len(checks) if isinstance(checks, list) else 0, "by_status": status_counts(checks)},
        "blockers": len(blockers) if isinstance(blockers, list) else 0,
        "residual_risks": len(risks) if isinstance(risks, list) else 0,
    }


def expand_paths(paths: list[str], patterns: list[str]) -> list[Path]:
    found = [Path(raw).expanduser() for raw in paths if Path(raw).expanduser().exists()]
    for pattern in patterns:
        found.extend(Path(item).expanduser() for item in glob.glob(str(Path(pattern).expanduser()), recursive=True))
    deduped: list[Path] = []
    seen: set[str] = set()
    for path in found:
        key = str(path.resolve()) if path.exists() else str(path)
        if key not in seen:
            seen.add(key)
            deduped.append(path)
    return deduped


def latest_sessions(root: Path, count: int) -> list[Path]:
    if count <= 0 or not root.exists():
        return []
    logs = [path for path in root.rglob("*.jsonl") if path.is_file()]
    return sorted(logs, key=lambda path: path.stat().st_mtime, reverse=True)[:count]


def hook_files(paths: list[str]) -> list[Path]:
    files: list[Path] = []
    for raw in paths:
        path = Path(raw).expanduser()
        if path.is_file():
            files.append(path)
        elif path.is_dir():
            files.extend(item for item in path.rglob("*.txt") if item.is_file())
    return sorted(files)


def summarize_hooks(paths: list[str]) -> dict[str, object]:
    rows: list[dict[str, object]] = []
    markers: Counter[str] = Counter()
    for path in hook_files(paths):
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            rows.append({"path": str(path), "read_error": str(exc), "status": "unreadable"})
            continue
        row_markers: list[str] = []
        for name, seen in (
            ("oag_mode_enabled", "OAG MODE ENABLED" in text),
            ("native_subagent_guard", "NATIVE CODEX SUBAGENT GUARD" in text),
            ("interview", bool(INTERVIEW_RE.search(text))),
            ("mcp_start", bool(MCP_START_RE.search(text))),
            ("computer_use", bool(COMPUTER_USE_RE.search(text))),
        ):
            if seen:
                row_markers.append(name)
                markers[name] += 1
        stat = path.stat()
        rows.append({"path": str(path), "bytes": stat.st_size, "lines": text.count("\n") + (1 if text else 0), "mtime_utc": iso(datetime.fromtimestamp(stat.st_mtime, timezone.utc)), "markers": row_markers})
    return {"count": len(rows), "total_bytes": sum(value for row in rows for value in [row.get("bytes")] if isinstance(value, int)), "markers": dict(markers), "largest": top_numeric(rows, "bytes")}


def derive(report: dict[str, object], long_tool_s: float) -> tuple[list[dict[str, object]], list[str], list[str]]:
    findings: list[dict[str, object]] = []
    positives: list[str] = []
    for session in as_list(report.get("sessions")):
        data = as_dict(session)
        calls = as_dict(data.get("tool_calls"))
        label = str(data.get("path", "session"))
        if calls.get("open"):
            findings.append({"code": "OPEN_TOOL_CALL", "path": label, "count": calls.get("open")})
        if calls.get("long"):
            findings.append({"code": "LONG_TOOL_CALL", "path": label, "count": calls.get("long"), "threshold_s": long_tool_s})
        if calls.get("agent_management_in_parallel"):
            findings.append({"code": "AGENT_MANAGEMENT_IN_PARALLEL", "path": label, "count": calls.get("agent_management_in_parallel")})
        if data.get("evidence_recorded"):
            positives.append(f"{Path(label).name}: evidence marker recorded")
        if data.get("event_count") and calls.get("open") == 0:
            positives.append(f"{Path(label).name}: no open tool calls in supplied log")
        markers = as_dict(data.get("runtime_markers"))
        if markers.get("computer_use_seen"):
            findings.append({"code": "COMPUTER_USE_MCP_SEEN", "path": label, "count": markers.get("computer_use_seen")})
        if markers.get("mcp_start_seen"):
            findings.append({"code": "MCP_STARTUP_SEEN", "path": label, "count": markers.get("mcp_start_seen")})

    for receipt in as_list(report.get("receipts")):
        data = as_dict(receipt)
        label = Path(str(data.get("path", "receipt"))).name
        if is_pass_status(data.get("status")):
            positives.append(f"{label}: receipt status pass")
        elif data.get("status") not in (None, "unreadable"):
            findings.append({"code": "RECEIPT_NOT_PASS", "path": data.get("path"), "status": data.get("status")})
        if data.get("blockers"):
            findings.append({"code": "RECEIPT_BLOCKERS", "path": data.get("path"), "count": data.get("blockers")})

    hooks = as_dict(report.get("hook_outputs"))
    for row in as_list(hooks.get("largest")):
        data = as_dict(row)
        size = data.get("bytes")
        if isinstance(size, int) and size >= 50_000:
            findings.append({"code": "LARGE_HOOK_OUTPUT", "path": data.get("path"), "bytes": size})
    hook_markers = as_dict(hooks.get("markers"))
    if hook_markers.get("interview"):
        findings.append({"code": "INTERVIEW_HOOK_SEEN", "count": hook_markers.get("interview")})
    if hook_markers.get("computer_use"):
        findings.append({"code": "COMPUTER_USE_MCP_SEEN", "count": hook_markers.get("computer_use")})
    if hook_markers.get("mcp_start"):
        findings.append({"code": "MCP_STARTUP_SEEN", "count": hook_markers.get("mcp_start")})

    codes = {str(item.get("code")) for item in findings}
    recommendations: list[str] = []
    if "AGENT_MANAGEMENT_IN_PARALLEL" in codes:
        recommendations.append("Keep close/wait/handoff agent-management calls out of parallel batches and off the critical path.")
    if {"OPEN_TOOL_CALL", "LONG_TOOL_CALL"} & codes:
        recommendations.append("Split long operations into bounded single-purpose calls and record the artifact path before dispatching more work.")
    if "INTERVIEW_HOOK_SEEN" in codes:
        recommendations.append("Gate interview hooks behind an explicit user request or a lock-blocking ambiguity condition.")
    if "COMPUTER_USE_MCP_SEEN" in codes or "MCP_STARTUP_SEEN" in codes:
        recommendations.append("For OAG subagent-heavy sessions, disable optional UI/MCP startup with oag_codex_config_doctor.py --lean-subagent-runtime and restart into a fresh trusted session.")
    if not recommendations:
        recommendations.append("No runtime tracking issue was detected in the supplied artifacts.")
    return findings, positives, recommendations


def build_report(args: argparse.Namespace) -> dict[str, object]:
    sessions = expand_paths(args.session_log, args.session_glob)
    sessions.extend(latest_sessions(Path(args.session_root).expanduser(), args.latest_session))
    sessions = expand_paths([str(path) for path in sessions], [])
    report: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": now_iso(),
        "thresholds": {"long_tool_s": args.long_tool_s},
        "sessions": [summarize_session(path, args.long_tool_s) for path in sessions],
        "receipts": [summarize_receipt(path) for path in expand_paths(args.receipt, args.receipt_glob)],
        "hook_outputs": summarize_hooks(args.hook_output),
    }
    findings, positives, recommendations = derive(report, args.long_tool_s)
    report["findings"] = findings
    report["positives"] = positives
    report["recommendations"] = recommendations
    return report


def fmt_duration(value: object) -> str:
    return f"{float(value):.1f}s" if isinstance(value, (int, float)) else "n/a"


def print_text(report: dict[str, object]) -> None:
    sessions = as_list(report.get("sessions"))
    receipts = as_list(report.get("receipts"))
    print(f"OAG debug/eval metrics ({report.get('schema_version')})")
    print(f"generated_at: {report.get('generated_at')}")
    print(f"sessions: {len(sessions)}, receipts: {len(receipts)}")
    for session in sessions:
        data = as_dict(session)
        calls = as_dict(data.get("tool_calls"))
        path = Path(str(data.get("path", ""))).name
        print(f"- session {path}: status={data.get('status')} duration={fmt_duration(data.get('duration_s'))} events={data.get('event_count')} calls={calls.get('completed', 0)}/{calls.get('total', 0)} open={calls.get('open', 0)} long={calls.get('long', 0)} agent_mgmt={calls.get('agent_management', 0)}")
        longest = calls.get("longest")
        if isinstance(longest, list) and longest:
            top = as_dict(longest[0])
            print(f"  longest: {top.get('name')} {fmt_duration(top.get('duration_s'))}")
        evidence = data.get("evidence_recorded")
        if isinstance(evidence, list) and evidence:
            print(f"  evidence: {', '.join(str(item) for item in evidence)}")
    for receipt in receipts:
        data = as_dict(receipt)
        print(f"- receipt {Path(str(data.get('path', ''))).name}: status={data.get('status')} handoff={data.get('handoff')} may_claim_complete={data.get('may_claim_complete')} blockers={data.get('blockers')} residual_risks={data.get('residual_risks')}")
    hooks = as_dict(report.get("hook_outputs"))
    if hooks.get("count"):
        print(f"- hook outputs: count={hooks.get('count')} total_bytes={hooks.get('total_bytes')} markers={hooks.get('markers')}")
    for title in ("positives", "findings", "recommendations"):
        rows = report.get(title)
        if isinstance(rows, list) and rows:
            print(f"{title}:")
            for row in rows:
                print(f"- {row}")


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Track Codex/OAG hangs, latency, hook noise, receipt status, and positive evidence.", formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("--session-log", action="append", default=[], help="Codex rollout JSONL path")
    parser.add_argument("--session-glob", action="append", default=[], help="Glob for Codex rollout JSONL paths")
    parser.add_argument("--latest-session", type=int, default=0, help="Include N newest session logs")
    parser.add_argument("--session-root", default="~/.codex/sessions", help="Root used by --latest-session")
    parser.add_argument("--receipt", action="append", default=[], help="Subagent/OAG receipt JSON path")
    parser.add_argument("--receipt-glob", action="append", default=[], help="Glob for receipt JSON paths")
    parser.add_argument("--hook-output", action="append", default=[], help="Hook output file or directory")
    parser.add_argument("--long-tool-s", type=float, default=30.0, help="Duration threshold for long tool calls")
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of text")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    report = build_report(args)
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True, ensure_ascii=True))
    else:
        print_text(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
