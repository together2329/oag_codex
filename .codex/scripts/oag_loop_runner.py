#!/usr/bin/env python3
"""Bounded OAG loop runner wrapper for plan-only and dispatch-safe modes."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

SCRIPTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS_DIR))

import oag_cli  # noqa: E402
import oag_paths  # noqa: E402
from oag_loop_core import loop_decision_from_plan, loop_policy_storage, resolve_loop_policy, write_loop_decision  # noqa: E402


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ip-dir", required=True)
    parser.add_argument("--run-id", default=os.environ.get("OAG_RUN_ID", ""))
    parser.add_argument("--until", default=None)
    parser.add_argument("--requirement", action="append", default=[])
    parser.add_argument("--obligation", action="append", default=[])
    parser.add_argument("--owner-module", action="append", default=[])
    parser.add_argument("--job-type", action="append", default=[])
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--max-iterations", type=int, default=None)
    parser.add_argument("--mode", choices=("plan_only", "dispatch", "execute"), default=None)
    parser.add_argument("--write-decision", dest="write_decision", action="store_true", default=True)
    parser.add_argument("--no-write-decision", dest="write_decision", action="store_false")
    parser.add_argument("--json", action="store_true")
    return parser


def _policy_args(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "until": args.until,
        "requirement": args.requirement,
        "obligation": args.obligation,
        "owner_module": args.owner_module,
        "job_type": args.job_type,
        "limit": args.limit,
        "max_iterations": args.max_iterations,
        "mode": args.mode,
    }


def _run_next(ip: Path, run_id: str, policy: dict[str, Any]) -> dict[str, Any]:
    response = oag_cli.dispatch_call(
        {
            "tool": "oag.run.next",
            "arguments": {
                "ip_dir": str(ip),
                "run_id": run_id,
                "loop_policy": loop_policy_storage(policy),
            },
        }
    )
    if not response.get("ok"):
        return {
            "schema_version": "oag_loop_runner.v1",
            "status": "failed",
            "decision": "stop",
            "reason": "planner_error",
            "errors": [str(item) for item in response.get("errors") or []],
            "loop_policy": loop_policy_storage(policy),
            "recommended_batch": None,
        }
    raw_result = response.get("result")
    result: dict[str, Any] = raw_result if isinstance(raw_result, dict) else {}
    raw_plan = result.get("loop_plan")
    plan: dict[str, Any] = raw_plan if isinstance(raw_plan, dict) else {}
    if plan:
        decision: dict[str, Any] = loop_decision_from_plan(plan)
    else:
        batch = result.get("next_batch") if isinstance(result.get("next_batch"), dict) else None
        decision = {
            "schema_version": "oag_loop_hook_decision.v1",
            "decision": "continue" if batch else "stop",
            "reason": "batch_available" if batch else str(result.get("loop_stop_reason") or "no_runnable_batch"),
            "loop_policy": result.get("loop_policy") if isinstance(result.get("loop_policy"), dict) else loop_policy_storage(policy),
            "recommended_batch": batch,
            "plan": {},
        }
    return {
        "schema_version": "oag_loop_runner.v1",
        "status": "pass",
        "run_id": result.get("run_id") or run_id,
        "planner_result": result,
        "decision": decision.get("decision"),
        "reason": decision.get("reason"),
        "loop_policy": decision.get("loop_policy") if isinstance(decision.get("loop_policy"), dict) else loop_policy_storage(policy),
        "recommended_batch": decision.get("recommended_batch") if isinstance(decision.get("recommended_batch"), dict) else None,
        "plan": decision.get("plan") if isinstance(decision.get("plan"), dict) else plan,
        "dispatch_command_candidates": result.get("dispatch_command_candidates")
        if isinstance(result.get("dispatch_command_candidates"), list)
        else [],
    }


def _safe_segment(value: str, fallback: str) -> str:
    text = "".join(ch if ch.isalnum() or ch in {"_", "-", "."} else "_" for ch in str(value or "").strip())
    return text.strip("._-") or fallback


def _execute_receipt_path(ip: Path, run_id: str, batch_id: str) -> Path:
    run_name = _safe_segment(run_id, "run")
    batch_name = _safe_segment(batch_id, "batch")
    return oag_paths.state_path(ip, Path("knowledge") / "loop_runner" / run_name / f"{batch_name}.json")


def _execute_validation_record_task(ip: Path, run_id: str, batch_id: str, task: dict[str, Any], index: int) -> dict[str, Any]:
    task_id = str(task.get("task_id") or f"task_{index}")
    obligations = [str(item).strip() for item in task.get("obligations", []) if str(item).strip()] if isinstance(task.get("obligations"), list) else []
    contracts = [str(item).strip() for item in task.get("contracts", []) if str(item).strip()] if isinstance(task.get("contracts"), list) else []
    evidence_refs = [str(item).strip() for item in task.get("required_evidence", []) if str(item).strip()] if isinstance(task.get("required_evidence"), list) else []
    record_response = oag_cli.dispatch_call(
        {
            "tool": "oag.record",
            "arguments": {
                "ip_dir": str(ip),
                "stage": "record",
                "type": "validation",
                "claim": f"loop runner validation record for {task_id}",
                "summary": f"Bounded execute mode recorded validation task {task_id} from {batch_id}.",
                "tags": ["loop_runner_execute", "validation_record"],
                "actor": {"kind": "ai", "id": "oag_loop_runner", "surface": "bounded_execute"},
                "status": "open",
                "rocev": {
                    "evidence": {"files": evidence_refs, "tests": []},
                    "validation": {
                        "status": "open",
                        "verdict": "pending",
                        "rationale": "automatic bounded validation-record execution; closure still requires normal gates",
                    },
                },
                "obligations": obligations,
                "contracts": contracts,
            },
        }
    )
    return {
        "task_id": task_id,
        "status": "pass" if record_response.get("ok") else "fail",
        "record_response": record_response,
    }


def _execute_batch(ip: Path, run_id: str, result: dict[str, Any], batch: dict[str, Any]) -> dict[str, Any]:
    if batch.get("can_execute") is not True:
        return {
            **result,
            "mode": "execute",
            "decision": "stop",
            "reason": "execute_not_allowed",
            "execution_guard": {
                "can_execute": False,
                "job_type": str(batch.get("job_type") or ""),
                "message": "recommended batch is not marked safe for bounded execute mode",
            },
        }
    if str(batch.get("job_type") or "") != "VALIDATION_RECORD_JOB":
        return {
            **result,
            "mode": "execute",
            "decision": "stop",
            "reason": "execute_job_type_not_allowed",
            "execution_guard": {
                "can_execute": False,
                "job_type": str(batch.get("job_type") or ""),
                "message": "bounded execute mode only supports VALIDATION_RECORD_JOB",
            },
        }
    receipt_path = _execute_receipt_path(ip, run_id, str(batch.get("batch_id") or "batch"))
    raw_tasks = batch.get("tasks")
    tasks = raw_tasks if isinstance(raw_tasks, list) else []
    task_results = [
        _execute_validation_record_task(ip, run_id, str(batch.get("batch_id") or "batch"), task, index)
        for index, task in enumerate(tasks)
        if isinstance(task, dict)
    ]
    compile_response = oag_cli.dispatch_call({"tool": "oag.compile", "arguments": {"ip_dir": str(ip)}})
    check_response = oag_cli.dispatch_call({"tool": "oag.check", "arguments": {"ip_dir": str(ip)}})
    execution_passed = all(item.get("status") == "pass" for item in task_results) and compile_response.get("ok") is True and check_response.get("ok") is True
    receipt = {
        "schema_version": "oag_loop_runner_execute_receipt.v1",
        "status": "pass" if execution_passed else "fail",
        "run_id": run_id,
        "batch_id": str(batch.get("batch_id") or ""),
        "job_type": str(batch.get("job_type") or ""),
        "executed_at_epoch": int(time.time()),
        "tasks": tasks,
        "task_results": task_results,
        "post_checks": {"compile": compile_response, "check": check_response},
        "action": "bounded_execute_validation_record",
    }
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {
        **result,
        "mode": "execute",
        "decision": "continue" if execution_passed else "stop",
        "reason": "executed_batch" if execution_passed else "execute_batch_failed",
        "execution": {
            "status": receipt["status"],
            "receipt_path": str(receipt_path),
            "batch_id": receipt["batch_id"],
            "job_type": receipt["job_type"],
        },
    }


def run(args: argparse.Namespace) -> dict[str, Any]:
    ip = Path(args.ip_dir).resolve()
    run_id = str(args.run_id or "")
    policy = resolve_loop_policy(ip, _policy_args(args), force_active=True)
    mode = str(policy.get("mode") or "plan_only")
    result = _run_next(ip, run_id, policy)
    batch = result.get("recommended_batch") if isinstance(result.get("recommended_batch"), dict) else None
    if result.get("status") != "pass":
        payload = result
    elif not batch:
        payload = {**result, "mode": mode, "decision": "stop", "reason": result.get("reason") or "boundary_reached"}
    elif mode == "dispatch":
        payload = {**result, "mode": mode, "decision": "continue", "reason": "dispatch_ready"}
    elif mode == "execute":
        payload = _execute_batch(ip, run_id, result, batch)
    else:
        payload = {**result, "mode": mode, "decision": "continue", "reason": "plan_available"}
    if args.write_decision and run_id:
        path = write_loop_decision(ip, run_id, payload)
        payload["loop_decision_path"] = str(path)
    return payload


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        payload = run(args)
    except Exception as exc:
        payload = {
            "schema_version": "oag_loop_runner.v1",
            "status": "failed",
            "decision": "stop",
            "reason": "runner_error",
            "errors": [str(exc)],
        }
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if payload.get("status") != "failed" else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
