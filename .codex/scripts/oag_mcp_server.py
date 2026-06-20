#!/usr/bin/env python3
"""Minimal MCP stdio server for the OAG tool-call gateway.

This implementation avoids external MCP dependencies so the plugin can be
tested immediately. It supports initialize, tools/list, and tools/call.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import oag_cli  # noqa: E402
import oag_graph  # noqa: E402


TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "name": "oag_scaffold",
        "description": "Create an ontology-first hardware IP scaffold with req/ontology/knowledge/artifact directories, structure namespace, and decomposition profile.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "ip_dir": {"type": "string"},
                "owner": {"type": "string"},
                "force": {"type": "boolean"},
            },
            "required": ["ip_dir"],
        },
    },
    {
        "name": "oag_inspect",
        "description": "Read-only scan of an IP folder for ROCEV evidence health and gaps.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "ip_dir": {"type": "string"},
                "stage": {"type": "string"},
                "intent": {"type": "string"},
            },
            "required": ["ip_dir"],
        },
    },
    {
        "name": "oag_context",
        "description": "Return an OAG context pack and prompt block for an IP/stage/intent.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "ip_dir": {"type": "string"},
                "stage": {"type": "string"},
                "intent": {"type": "string"},
                "limit": {"type": "integer"},
            },
            "required": ["ip_dir"],
        },
    },
    {
        "name": "oag_compile",
        "description": "Compile ontology YAML into generated truth graph, design spec projection, and module authoring packets with typed edges, structure/decomposition checks, common design-rule checks, and orphan issues.",
        "inputSchema": {
            "type": "object",
            "properties": {"ip_dir": {"type": "string"}},
            "required": ["ip_dir"],
        },
    },
    {
        "name": "oag_record",
        "description": "Append an actor-provenanced ROCEV-backed knowledge record.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "ip_dir": {"type": "string"},
                "stage": {"type": "string"},
                "claim": {"type": "string"},
                "summary": {"type": "string"},
                "actor": {"type": "object"},
                "rocev": {"type": "object"},
            },
            "required": ["ip_dir", "claim"],
        },
    },
    {
        "name": "oag_draft",
        "description": "Persist a requirement interview draft without promoting it to locked truth.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "ip_dir": {"type": "string"},
                "stage": {"type": "string"},
                "title": {"type": "string"},
                "summary": {"type": "string"},
                "facts": {"type": "array", "items": {"type": "string"}},
                "decisions": {"type": "array", "items": {"type": "string"}},
                "assumptions": {"type": "array", "items": {"type": "string"}},
                "open_questions": {"type": "array", "items": {"type": "string"}},
                "actor": {"type": "object"},
                "source": {"type": "string"},
            },
            "required": ["ip_dir", "title"],
        },
    },
    {
        "name": "oag_ticket",
        "description": "Write a contract-linked failure ticket for owner-routed repair.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "ip_dir": {"type": "string"},
                "stage": {"type": "string"},
                "reason": {"type": "string"},
                "owner_workflow": {"type": "string"},
                "failing_contract": {"type": "object"},
                "expected": {"type": "object"},
                "observed": {"type": "object"},
                "evidence": {"type": "object"},
                "editable_files": {"type": "array", "items": {"type": "string"}},
                "forbidden_edits": {"type": "array", "items": {"type": "string"}},
                "required_evidence_after_patch": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["ip_dir", "reason"],
        },
    },
    {
        "name": "oag_metrics",
        "description": "Persist a numeric improvement snapshot derived from the active IP ontology and evidence graph.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "ip_dir": {"type": "string"},
                "stage": {"type": "string"},
                "intent": {"type": "string"},
                "record": {"type": "boolean"},
                "actor": {"type": "object"},
            },
            "required": ["ip_dir"],
        },
    },
    {
        "name": "oag_handoff",
        "description": "Persist a numeric readiness handoff that combines OAG metrics with auto-research ranked next actions and signoff blockers.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "ip_dir": {"type": "string"},
                "stage": {"type": "string"},
                "intent": {"type": "string"},
                "record": {"type": "boolean"},
                "actor": {"type": "object"},
            },
            "required": ["ip_dir"],
        },
    },
    {
        "name": "oag_check",
        "description": "Validate IP knowledge index, protected fields, append-only ledger hash chain, monotonic closure, closure matrix, evidence hashes, design rules, and stage receipts.",
        "inputSchema": {
            "type": "object",
            "properties": {"ip_dir": {"type": "string"}},
            "required": ["ip_dir"],
        },
    },
    {
        "name": "oag_decide",
        "description": "Return deterministic allow/block guidance for an action; completion actions require record_decision=true to write a decision receipt.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "ip_dir": {"type": "string"},
                "action": {"type": "string"},
                "stage": {"type": "string"},
                "intent": {"type": "string"},
                "record_decision": {"type": "boolean"},
                "actor": {"type": "object"},
            },
            "required": ["ip_dir", "action"],
        },
    },
    {
        "name": "oag_review",
        "description": "Write an independent reviewer receipt for signoff/promote gating without replacing oag.decide.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "ip_dir": {"type": "string"},
                "action": {"type": "string"},
                "stage": {"type": "string"},
                "intent": {"type": "string"},
                "verdict": {"type": "string"},
                "actor": {"type": "object"},
                "producer_actor": {"type": "object"},
                "findings": {"type": "array", "items": {"type": "string"}},
                "record_review": {"type": "boolean"},
            },
            "required": ["ip_dir"],
        },
    },
    {
        "name": "oag_run_start",
        "description": "Start a durable OAG run loop for one IP, derive the active obligation, and write ontology/runs/<run_id>/run_state.json.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "ip_dir": {"type": "string"},
                "stage": {"type": "string"},
                "intent": {"type": "string"},
                "run_id": {"type": "string"},
                "target_obligation": {"type": "string"},
                "actor": {"type": "object"},
            },
            "required": ["ip_dir"],
        },
    },
    {
        "name": "oag_run_next",
        "description": "Refresh and return the single next OAG action for an active run.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "ip_dir": {"type": "string"},
                "run_id": {"type": "string"},
                "stage": {"type": "string"},
                "intent": {"type": "string"},
            },
            "required": ["ip_dir"],
        },
    },
    {
        "name": "oag_run_record",
        "description": "Record ROCEV evidence for the active run target, fingerprint evidence files, and refresh next action.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "ip_dir": {"type": "string"},
                "run_id": {"type": "string"},
                "obligation": {"type": "string"},
                "contract": {"type": "string"},
                "evidence_files": {"type": "array", "items": {"type": "string"}},
                "evidence_tests": {"type": "array", "items": {"type": "string"}},
                "status": {"type": "string"},
                "verdict": {"type": "string"},
                "summary": {"type": "string"},
                "actor": {"type": "object"},
            },
            "required": ["ip_dir"],
        },
    },
    {
        "name": "oag_run_checkpoint",
        "description": "Run compile/check/decide for the active run, write a decision receipt when requested, and update run status.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "ip_dir": {"type": "string"},
                "run_id": {"type": "string"},
                "stage": {"type": "string"},
                "intent": {"type": "string"},
                "action": {"type": "string"},
                "record_decision": {"type": "boolean"},
                "max_blocker_repeats": {"type": "integer"},
                "actor": {"type": "object"},
            },
            "required": ["ip_dir"],
        },
    },
    {
        "name": "oag_stop_check",
        "description": "Return whether an unfinished OAG run should continue and provide the prompt block for the next action.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "ip_dir": {"type": "string"},
                "run_id": {"type": "string"},
                "stage": {"type": "string"},
                "intent": {"type": "string"},
            },
            "required": ["ip_dir"],
        },
    },
    {
        "name": "oag_graph",
        "description": "Build an OAG ontology graph and optionally write JSON/HTML viewer files.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "ip_dir": {"type": "string"},
                "stage": {"type": "string"},
                "intent": {"type": "string"},
                "json_out": {"type": "string"},
                "html_out": {"type": "string"},
            },
            "required": ["ip_dir"],
        },
    },
]


def _jsonrpc_result(request_id: Any, result: Any) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def _jsonrpc_error(request_id: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


def _tool_to_oag(name: str) -> str:
    mapping = {
        "oag_scaffold": "oag.scaffold",
        "oag_inspect": "oag.inspect",
        "oag_context": "oag.context",
        "oag_compile": "oag.compile",
        "oag_record": "oag.record",
        "oag_draft": "oag.draft",
        "oag_ticket": "oag.ticket",
        "oag_metrics": "oag.metrics",
        "oag_handoff": "oag.handoff",
        "oag_check": "oag.check",
        "oag_decide": "oag.decide",
        "oag_review": "oag.review",
        "oag_run_start": "oag.run.start",
        "oag_run_next": "oag.run.next",
        "oag_run_record": "oag.run.record",
        "oag_run_checkpoint": "oag.run.checkpoint",
        "oag_stop_check": "oag.stop_check",
    }
    if name not in mapping:
        raise ValueError(f"unknown tool: {name}")
    return mapping[name]


def handle(request: dict[str, Any]) -> dict[str, Any] | None:
    method = request.get("method")
    request_id = request.get("id")
    if method == "notifications/initialized":
        return None
    if method == "initialize":
        return _jsonrpc_result(
            request_id,
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "ontology-ip-agent-oag", "version": "0.1.0"},
            },
        )
    if method == "tools/list":
        return _jsonrpc_result(request_id, {"tools": TOOL_SCHEMAS})
    if method == "tools/call":
        params = request.get("params") if isinstance(request.get("params"), dict) else {}
        name = str(params.get("name") or "")
        arguments = params.get("arguments") if isinstance(params.get("arguments"), dict) else {}
        if name == "oag_graph":
            ip_dir = Path(str(arguments.get("ip_dir") or "")).expanduser()
            graph = oag_graph.build_graph(
                ip_dir,
                stage=str(arguments.get("stage") or ""),
                intent=str(arguments.get("intent") or ""),
            )
            if arguments.get("json_out"):
                json_out = Path(str(arguments["json_out"])).expanduser()
                json_out.parent.mkdir(parents=True, exist_ok=True)
                json_out.write_text(json.dumps(graph, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            if arguments.get("html_out"):
                oag_graph.write_html(graph, Path(str(arguments["html_out"])).expanduser())
            response = {
                "schema_version": "oag_tool_response.v1",
                "ok": True,
                "tool": "oag.graph",
                "result": {
                    "schema_version": graph["schema_version"],
                    "ip": graph["ip"],
                    "stats": graph["stats"],
                    "json_out": str(arguments.get("json_out") or ""),
                    "html_out": str(arguments.get("html_out") or ""),
                    "graph": graph if not (arguments.get("json_out") or arguments.get("html_out")) else None,
                },
                "errors": [],
            }
        else:
            response = oag_cli.dispatch_call({"tool": _tool_to_oag(name), "arguments": arguments})
        return _jsonrpc_result(
            request_id,
            {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(response, ensure_ascii=False, indent=2),
                    }
                ],
                "isError": not bool(response.get("ok")),
            },
        )
    return _jsonrpc_error(request_id, -32601, f"method not found: {method}")


def main() -> int:
    for line in sys.stdin:
        if not line.strip():
            continue
        try:
            request = json.loads(line)
            response = handle(request)
        except Exception as exc:
            response = _jsonrpc_error(None, -32000, str(exc))
        if response is not None:
            print(json.dumps(response, ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
