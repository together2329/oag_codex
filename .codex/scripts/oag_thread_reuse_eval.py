#!/usr/bin/env python3
"""Compare fresh and reused Codex App Server threads on a fixed eval suite."""

from __future__ import annotations

import argparse
import json
import os
import queue
import shlex
import subprocess
import time
from pathlib import Path
from typing import Any

from oag_thread_worker import (
    AppServerClient,
    JsonObject,
    JsonlEventLog,
    normalized_usage,
    text_input,
    thread_id_from_result,
    turn_id_from_result,
    utc_now,
    zero_usage,
)


RESULT_BEGIN = "<RESULT>"
RESULT_END = "</RESULT>"


def load_object(path: Path) -> JsonObject:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return payload


def write_object(path: Path, payload: JsonObject) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def usage_delta(after: JsonObject, before: JsonObject) -> JsonObject:
    return {
        key: max(0, int(after.get(key) or 0) - int(before.get(key) or 0))
        for key in zero_usage()
    }


def add_usage(total: JsonObject, value: JsonObject) -> JsonObject:
    return {key: int(total.get(key) or 0) + int(value.get(key) or 0) for key in zero_usage()}


def expected_matches(expected: Any, actual: Any) -> bool:
    if isinstance(expected, dict):
        if set(expected) == {"$any_of"}:
            alternatives = expected.get("$any_of")
            return isinstance(alternatives, list) and any(expected_matches(value, actual) for value in alternatives)
        return isinstance(actual, dict) and all(
            key in actual and expected_matches(value, actual[key]) for key, value in expected.items()
        )
    if isinstance(expected, list):
        return isinstance(actual, list) and expected == actual
    return expected == actual


def parse_result(text: str) -> tuple[JsonObject | None, str]:
    start = text.rfind(RESULT_BEGIN)
    end = text.rfind(RESULT_END)
    if start < 0 or end < 0 or end <= start:
        return None, "missing RESULT markers"
    raw = text[start + len(RESULT_BEGIN) : end].strip()
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        return None, f"invalid RESULT JSON: {exc}"
    if not isinstance(payload, dict):
        return None, "RESULT JSON must be an object"
    return payload, ""


def prompt_for_case(
    suite: JsonObject,
    case: JsonObject,
    *,
    mode: str,
    case_index: int,
) -> str:
    reference = str(suite.get("reference") or "").strip()
    replacement = str(case.get("replacement_reference") or "").strip()
    include_reference = mode == "fresh" or case_index == 0 or bool(case.get("repeat_reference"))
    parts = [
        "THREAD REUSE EVALUATION\n"
        + (
            "Use local tools as needed, remain inside the evaluation workspace, and complete the requested implementation and tests. "
            if suite.get("allow_tools") is True
            else "Do not use tools, inspect files, or add commentary. Solve only from the supplied text. "
        )
        + f"Return exactly {RESULT_BEGIN}<one JSON object>{RESULT_END} as the final response.",
    ]
    if replacement:
        parts.append("NEW AUTHORITATIVE REFERENCE\n" + replacement)
    elif include_reference:
        parts.append("AUTHORITATIVE REFERENCE\n" + reference)
    else:
        parts.append(
            "REFERENCE CONTINUITY\n"
            "Use the authoritative reference supplied earlier in this same thread. Do not substitute defaults."
        )
    parts.append("TASK\n" + str(case.get("instruction") or "").strip())
    return "\n\n".join(parts)


def run_eval(args: argparse.Namespace) -> JsonObject:
    suite_path = Path(args.suite).expanduser().resolve()
    suite = load_object(suite_path)
    cases = suite.get("cases") if isinstance(suite.get("cases"), list) else []
    if not cases or not all(isinstance(case, dict) for case in cases):
        raise ValueError("suite cases must be a non-empty object array")
    if not str(suite.get("reference") or "").strip():
        raise ValueError("suite reference is required")

    output_path = Path(args.output).expanduser().resolve()
    event_path = output_path.with_suffix(".events.jsonl")
    event_log = JsonlEventLog(event_path)
    client: AppServerClient | None = None
    started = time.monotonic()
    results: list[JsonObject] = []
    aggregate = zero_usage()
    shared_thread_id = ""
    shared_thread_usage = zero_usage()
    active: JsonObject = {}
    allow_tools = suite.get("allow_tools") is True

    def handle(message: JsonObject) -> None:
        method = str(message.get("method") or "")
        params = message.get("params") if isinstance(message.get("params"), dict) else {}
        if method == "thread/tokenUsage/updated":
            token_usage = params.get("tokenUsage") if isinstance(params.get("tokenUsage"), dict) else {}
            total = token_usage.get("total") if isinstance(token_usage.get("total"), dict) else {}
            last = token_usage.get("last") if isinstance(token_usage.get("last"), dict) else {}
            active["thread_usage"] = normalized_usage(total)
            active["last_usage"] = normalized_usage(last)
        elif method == "item/completed":
            item = params.get("item") if isinstance(params.get("item"), dict) else {}
            if item.get("type") == "agentMessage":
                active["agent_text"] = str(item.get("text") or "")
        elif method == "turn/completed":
            turn = params.get("turn") if isinstance(params.get("turn"), dict) else {}
            active["turn_status"] = str(turn.get("status") or "")

    try:
        command = shlex.split(args.app_server_command)
        if not command:
            raise ValueError("app server command must not be empty")
        cwd = Path(args.cwd).expanduser().resolve()
        client = AppServerClient(command, cwd=cwd, env=dict(os.environ), event_log=event_log)
        client.request(
            "initialize",
            {"clientInfo": {"name": "oag-thread-reuse-eval", "version": "1.0"}, "capabilities": {}},
            timeout=20,
            notification=handle,
        )
        client.notify("initialized", {})

        for index, raw_case in enumerate(cases):
            case = dict(raw_case)
            if args.mode == "fresh" or not shared_thread_id:
                thread_result = client.request(
                    "thread/start",
                    {
                        "cwd": str(cwd),
                        "approvalPolicy": "never",
                        "sandbox": "workspace-write" if allow_tools else "read-only",
                        "model": args.model,
                        "ephemeral": False,
                        "config": {
                            "features.multi_agent": False,
                            "features.child_agents_md": False,
                        },
                        "developerInstructions": (
                            "This is a deterministic evaluation. Do not use subagents. Stay within the evaluation workspace. "
                            + (
                                "Use local tools and tests as needed. "
                                if allow_tools
                                else "Do not use tools. "
                            )
                            + "Return only the requested RESULT object."
                        ),
                    },
                    timeout=30,
                    notification=handle,
                )
                thread_id = thread_id_from_result(thread_result)
                before_usage = zero_usage()
                if args.mode == "reuse":
                    shared_thread_id = thread_id
                    shared_thread_usage = zero_usage()
            else:
                thread_id = shared_thread_id
                before_usage = dict(shared_thread_usage)
            if not thread_id:
                raise RuntimeError("thread/start returned no thread id")

            active = {
                "thread_usage": dict(before_usage),
                "last_usage": zero_usage(),
                "agent_text": "",
                "turn_status": "",
            }
            prompt = prompt_for_case(suite, case, mode=args.mode, case_index=index)
            turn_started = time.monotonic()
            turn_result = client.request(
                "turn/start",
                {
                    "threadId": thread_id,
                    "input": text_input(prompt),
                    "model": args.model,
                    "effort": args.effort,
                    "cwd": str(cwd),
                },
                timeout=30,
                notification=handle,
            )
            turn_id = turn_id_from_result(turn_result)
            if not turn_id:
                raise RuntimeError("turn/start returned no turn id")
            deadline = time.monotonic() + args.timeout_seconds
            while not active.get("turn_status"):
                if time.monotonic() >= deadline:
                    client.send_request("turn/interrupt", {"threadId": thread_id, "turnId": turn_id})
                    active["turn_status"] = "interrupted"
                    break
                try:
                    message = client.messages.get(timeout=0.25)
                except queue.Empty:
                    if client.process.poll() is not None:
                        raise RuntimeError(f"app server exited with code {client.process.returncode}")
                    continue
                if "method" in message:
                    handle(message)

            after_usage = active.get("thread_usage") if isinstance(active.get("thread_usage"), dict) else before_usage
            last_usage = active.get("last_usage") if isinstance(active.get("last_usage"), dict) else zero_usage()
            measured = usage_delta(after_usage, before_usage)
            if not measured["total_tokens"] and int(last_usage.get("total_tokens") or 0):
                measured = dict(last_usage)
            if args.mode == "reuse":
                shared_thread_usage = dict(after_usage)
            aggregate = add_usage(aggregate, measured)
            actual, parse_error = parse_result(str(active.get("agent_text") or ""))
            expected = case.get("expected") if isinstance(case.get("expected"), dict) else {}
            check: JsonObject = {"configured": False, "returncode": 0, "stdout": "", "stderr": ""}
            raw_check = case.get("check_command")
            if isinstance(raw_check, list) and raw_check and all(isinstance(value, str) for value in raw_check):
                check_result = subprocess.run(
                    raw_check,
                    cwd=cwd,
                    text=True,
                    capture_output=True,
                    timeout=args.check_timeout_seconds,
                    check=False,
                )
                check = {
                    "configured": True,
                    "command": raw_check,
                    "returncode": check_result.returncode,
                    "stdout": check_result.stdout[-4000:],
                    "stderr": check_result.stderr[-4000:],
                }
            elif raw_check is not None:
                raise ValueError(f"case {case.get('id')} check_command must be a non-empty string array")
            passed = (
                active.get("turn_status") == "completed"
                and actual is not None
                and expected_matches(expected, actual)
                and int(check.get("returncode") or 0) == 0
            )
            results.append(
                {
                    "case_id": str(case.get("id") or f"case-{index + 1}"),
                    "thread_id": thread_id,
                    "turn_id": turn_id,
                    "turn_status": active.get("turn_status"),
                    "duration_seconds": round(time.monotonic() - turn_started, 3),
                    "prompt_characters": len(prompt),
                    "usage": measured,
                    "expected": expected,
                    "actual": actual,
                    "parse_error": parse_error,
                    "check": check,
                    "passed": passed,
                }
            )
    finally:
        if client is not None:
            client.close()
        event_log.close()

    payload: JsonObject = {
        "schema_version": "oag_thread_reuse_eval.v1",
        "suite_id": str(suite.get("id") or suite_path.stem),
        "mode": args.mode,
        "model": args.model,
        "reasoning_effort": args.effort,
        "started_at": utc_now(),
        "duration_seconds": round(time.monotonic() - started, 3),
        "case_count": len(results),
        "passed_count": sum(1 for result in results if result.get("passed")),
        "all_passed": all(bool(result.get("passed")) for result in results),
        "token_usage": aggregate,
        "unique_thread_count": len({str(result.get("thread_id") or "") for result in results}),
        "event_log_path": str(event_path),
        "cases": results,
    }
    write_object(output_path, payload)
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Compare fresh and reused App Server threads.")
    parser.add_argument("--suite", required=True)
    parser.add_argument("--mode", choices=["fresh", "reuse"], required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--effort", choices=["none", "minimal", "low", "medium", "high", "xhigh"], default="medium")
    parser.add_argument("--cwd", default=".")
    parser.add_argument("--output", required=True)
    parser.add_argument("--timeout-seconds", type=int, default=300)
    parser.add_argument("--check-timeout-seconds", type=int, default=120)
    parser.add_argument("--app-server-command", default="codex app-server")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        result = run_eval(args)
    except Exception as exc:
        result = {
            "schema_version": "oag_thread_reuse_eval.v1",
            "status": "fail",
            "failure_reason": str(exc),
        }
    print(json.dumps(result, indent=2, sort_keys=True) if args.json else json.dumps(result, sort_keys=True))
    return 0 if result.get("all_passed") else 1


if __name__ == "__main__":
    raise SystemExit(main())
