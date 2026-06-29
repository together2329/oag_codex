#!/usr/bin/env python3
"""Create, list, render, and answer OAG workflow gate frames."""

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
from oag_run_control_common import JsonObject, collect_gate_state, issue, utc_now, write_json  # noqa: E402


GATE_SCHEMA_VERSION = "oag_workflow_gate.v1"
RESULT_SCHEMA_VERSION = "oag_gate_frame_result.v1"
VALID_KINDS = {"question", "approval", "execution"}
VALID_STAGES = {
    "deep-interview",
    "decision-matrix",
    "planning",
    "pre-lock",
    "pre-dispatch",
    "implementation",
    "evidence",
    "gate",
    "closure",
}


def canonical_hash(payload: Any) -> str:
    data = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def answer_hash(answer: Any) -> str:
    return canonical_hash({"answer": answer})


def parse_option(raw: str) -> JsonObject:
    parts = raw.split("|", 2)
    if len(parts) != 3:
        raise ValueError("--option must use VALUE|LABEL|DESCRIPTION")
    value, label, description = (part.strip() for part in parts)
    if not value or not label:
        raise ValueError("--option value and label are required")
    return {"value": value, "label": label, "description": description}


def parse_stage_state(raw: str) -> JsonObject:
    if not raw:
        return {}
    candidate = Path(raw)
    try:
        text = candidate.read_text(encoding="utf-8") if candidate.is_file() else raw
        payload = json.loads(text)
        return payload if isinstance(payload, dict) else {"value": payload}
    except Exception:
        return {"summary": raw}


def build_schema(options: list[JsonObject], *, allow_custom: bool) -> JsonObject:
    enum = [str(option["value"]) for option in options]
    if allow_custom:
        return {
            "oneOf": [
                {"type": "string", "enum": enum},
                {"type": "object", "required": ["custom"], "properties": {"custom": {"type": "string", "minLength": 1}}, "additionalProperties": True},
            ]
        }
    return {"type": "string", "enum": enum}


def validate_options(options: list[JsonObject], recommended: str, *, allow_nonstandard: bool) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    if len(options) != 4 and not allow_nonstandard:
        issues.append(issue("OPTION_COUNT", "gate frames require exactly four options unless --allow-nonstandard-options is set", "options"))
    values = [str(option.get("value") or "") for option in options]
    if len(set(values)) != len(values):
        issues.append(issue("OPTION_VALUE_DUPLICATE", "option values must be unique", "options"))
    if recommended not in values:
        issues.append(issue("RECOMMENDED_OPTION_MISSING", "recommended option must match one option value", "recommended"))
    if options and recommended != str(options[0].get("value")):
        issues.append(issue("RECOMMENDED_NOT_FIRST", "the first option must be the recommended option", "options[0]"))
    last_label = str(options[-1].get("label") or "").lower() if options else ""
    if options and not any(token in last_label for token in ("other", "custom", "refine", "직접", "기타", "수정")):
        issues.append(issue("CUSTOM_ESCAPE_MISSING", "the last option should be Other / custom / refine", "options[-1]"))
    return issues


def gate_dir(ip_dir: Path) -> Path:
    path = oag_paths.state_path(ip_dir, "knowledge/gates")
    path.mkdir(parents=True, exist_ok=True)
    return path


def render_markdown(gate: JsonObject) -> str:
    context = gate.get("context") if isinstance(gate.get("context"), dict) else {}
    lines = [
        f"# OAG Gate: {gate['gate_id']}",
        "",
        f"Stage: `{gate['stage']}`",
        f"Kind: `{gate['kind']}`",
        f"Schema hash: `{gate['schema_hash']}`",
        "",
        str(context.get("prompt") or context.get("title") or ""),
        "",
        "Recommendation: choose option A unless the tradeoff is wrong for this IP.",
        "",
        "Options:",
    ]
    for index, option in enumerate(gate.get("options", [])):
        prefix = chr(ord("A") + index)
        rec = " (Recommended)" if option.get("recommended") else ""
        lines.append(f"{prefix}. {option['label']}{rec} - {option.get('description', '')}")
    lines.extend(["", "If none fits, provide a custom answer directly."])
    return "\n".join(lines).rstrip() + "\n"


def create_gate(args: argparse.Namespace) -> JsonObject:
    ip_dir = oag_paths.ip_root(args.ip_dir)
    if not ip_dir.is_dir():
        raise FileNotFoundError(f"IP directory does not exist: {ip_dir}")
    if args.kind not in VALID_KINDS:
        return {"schema_version": RESULT_SCHEMA_VERSION, "status": "fail", "issues": [issue("KIND_INVALID", f"kind must be one of {sorted(VALID_KINDS)}")]}
    if args.stage not in VALID_STAGES:
        return {"schema_version": RESULT_SCHEMA_VERSION, "status": "fail", "issues": [issue("STAGE_INVALID", f"stage must be one of {sorted(VALID_STAGES)}")]}
    options = [parse_option(raw) for raw in args.option]
    recommended = args.recommended or (options[0]["value"] if options else "")
    validation_issues = validate_options(options, recommended, allow_nonstandard=bool(args.allow_nonstandard_options))
    if validation_issues:
        return {"schema_version": RESULT_SCHEMA_VERSION, "status": "fail", "issues": validation_issues}
    for option in options:
        option["recommended"] = str(option["value"]) == recommended
    schema = build_schema(options, allow_custom=bool(args.allow_custom))
    digest = canonical_hash(schema)
    gate_id = args.gate_id or f"gate_{args.stage.replace('-', '_')}_{digest[:12]}"
    gate: JsonObject = {
        "schema_version": GATE_SCHEMA_VERSION,
        "gate_id": gate_id,
        "stage": args.stage,
        "kind": args.kind,
        "schema": schema,
        "schema_hash": digest,
        "options": options,
        "context": {
            "title": args.title or args.prompt[:80],
            "prompt": args.prompt,
            "summary": args.summary,
            "stage_state": parse_stage_state(args.stage_state),
            "artifact_refs": args.artifact_ref or [],
            "language": args.language,
        },
        "created_at": utc_now(),
        "required": True,
        "allow_custom": bool(args.allow_custom),
        "may_claim_complete": False,
    }
    path = gate_dir(ip_dir) / f"{gate_id}.json"
    md_path = gate_dir(ip_dir) / f"{gate_id}.md"
    write_json(path, gate)
    md_path.write_text(render_markdown(gate), encoding="utf-8")
    return {
        "schema_version": RESULT_SCHEMA_VERSION,
        "status": "pass",
        "operation": "create",
        "gate_id": gate_id,
        "gate_path": str(path),
        "markdown": str(md_path),
        "schema_hash": digest,
    }


def load_gate(ip_dir: Path, gate_id: str) -> tuple[Path, JsonObject]:
    path = gate_dir(ip_dir) / f"{gate_id}.json"
    if not path.is_file():
        raise FileNotFoundError(f"gate not found: {gate_id}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"gate file is not an object: {path}")
    return path, payload


def _answer_payload(raw: str) -> Any:
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return raw


def _answer_valid(gate: JsonObject, answer: Any) -> tuple[bool, str]:
    values = {str(option.get("value")) for option in gate.get("options", []) if isinstance(option, dict)}
    if isinstance(answer, str) and answer in values:
        return True, ""
    if gate.get("allow_custom") and isinstance(answer, dict) and str(answer.get("custom") or "").strip():
        return True, ""
    return False, "answer must match an option value or provide a non-empty custom answer object"


def answer_gate(args: argparse.Namespace) -> JsonObject:
    ip_dir = oag_paths.ip_root(args.ip_dir)
    path, gate = load_gate(ip_dir, args.gate_id)
    existing = gate.get("resolution") if isinstance(gate.get("resolution"), dict) else {}
    if existing.get("status") == "accepted" and not args.force:
        return {"schema_version": RESULT_SCHEMA_VERSION, "status": "fail", "issues": [issue("GATE_ALREADY_RESOLVED", "gate is already accepted", args.gate_id)]}
    answer = _answer_payload(args.answer)
    ok, reason = _answer_valid(gate, answer)
    if not ok:
        return {"schema_version": RESULT_SCHEMA_VERSION, "status": "fail", "issues": [issue("INVALID_GATE_ANSWER", reason, args.gate_id)]}
    gate["resolution"] = {
        "status": "accepted",
        "answer": answer,
        "answer_hash": answer_hash(answer),
        "actor": args.actor,
        "resolved_at": utc_now(),
    }
    write_json(path, gate)
    answer_path = gate_dir(ip_dir) / f"{args.gate_id}.answer.json"
    write_json(answer_path, {"schema_version": "oag_workflow_gate_answer.v1", "gate_id": args.gate_id, **gate["resolution"]})
    return {
        "schema_version": RESULT_SCHEMA_VERSION,
        "status": "pass",
        "operation": "answer",
        "gate_id": args.gate_id,
        "gate_path": str(path),
        "answer_path": str(answer_path),
        "answer_hash": gate["resolution"]["answer_hash"],
    }


def list_gates(args: argparse.Namespace) -> JsonObject:
    ip_dir = oag_paths.ip_root(args.ip_dir)
    state = collect_gate_state(ip_dir)
    return {"schema_version": RESULT_SCHEMA_VERSION, "status": "pass", "operation": "list", "ip": ip_dir.name, **state}


def render_gate(args: argparse.Namespace) -> JsonObject:
    ip_dir = oag_paths.ip_root(args.ip_dir)
    path, gate = load_gate(ip_dir, args.gate_id)
    markdown = render_markdown(gate)
    if not args.json:
        print(markdown)
    return {"schema_version": RESULT_SCHEMA_VERSION, "status": "pass", "operation": "render", "gate_id": args.gate_id, "gate_path": str(path), "markdown": markdown}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    create = sub.add_parser("create", help="Create a required workflow gate frame.")
    create.add_argument("--ip-dir", required=True)
    create.add_argument("--gate-id")
    create.add_argument("--stage", required=True)
    create.add_argument("--kind", required=True, choices=sorted(VALID_KINDS))
    create.add_argument("--title", default="")
    create.add_argument("--prompt", required=True)
    create.add_argument("--summary", default="")
    create.add_argument("--option", action="append", required=True, help="VALUE|LABEL|DESCRIPTION. Exactly four options by default.")
    create.add_argument("--recommended", default="")
    create.add_argument("--artifact-ref", action="append")
    create.add_argument("--stage-state", default="")
    create.add_argument("--language", default="ko")
    create.add_argument("--allow-custom", action="store_true", default=True)
    create.add_argument("--allow-nonstandard-options", action="store_true")
    create.add_argument("--json", action="store_true")

    answer = sub.add_parser("answer", help="Resolve a workflow gate.")
    answer.add_argument("--ip-dir", required=True)
    answer.add_argument("--gate-id", required=True)
    answer.add_argument("--answer", required=True, help="Option value, or JSON object such as {\"custom\":\"...\"}.")
    answer.add_argument("--actor", default="user")
    answer.add_argument("--force", action="store_true")
    answer.add_argument("--json", action="store_true")

    list_cmd = sub.add_parser("list", help="List pending and resolved gates.")
    list_cmd.add_argument("--ip-dir", required=True)
    list_cmd.add_argument("--json", action="store_true")

    render = sub.add_parser("render", help="Render a gate as chat-friendly Markdown.")
    render.add_argument("--ip-dir", required=True)
    render.add_argument("--gate-id", required=True)
    render.add_argument("--json", action="store_true")
    return parser


def dispatch(args: argparse.Namespace) -> JsonObject:
    if args.command == "create":
        return create_gate(args)
    if args.command == "answer":
        return answer_gate(args)
    if args.command == "list":
        return list_gates(args)
    return render_gate(args)


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        result = dispatch(args)
    except Exception as exc:
        result = {"schema_version": RESULT_SCHEMA_VERSION, "status": "fail", "issues": [issue("EXCEPTION", str(exc))]}
    if getattr(args, "json", False):
        print(json.dumps(result, indent=2, sort_keys=True))
    elif result.get("status") == "pass":
        if result.get("operation") != "render":
            print(f"PASS {result.get('operation')} {result.get('gate_id', '')}".strip())
    else:
        print(f"FAIL {result.get('operation', 'gate')}", file=sys.stderr)
        for item in result.get("issues", []):
            print(f"- {item.get('code')}: {item.get('message')}", file=sys.stderr)
    return 0 if result.get("status") == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
