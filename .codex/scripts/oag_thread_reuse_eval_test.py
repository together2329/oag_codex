#!/usr/bin/env python3
"""Regression test for the fresh-versus-reuse evaluation runner."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path


SCRIPTS_DIR = Path(__file__).resolve().parent
EVAL_SCRIPT = SCRIPTS_DIR / "oag_thread_reuse_eval.py"
SUITE = SCRIPTS_DIR.parent / "evals" / "thread_reuse_contract_v1.json"


FAKE_SERVER = r'''#!/usr/bin/env python3
import json
import sys

threads = {}
next_thread = 1
next_turn = 1

def send(value):
    print(json.dumps(value), flush=True)

for raw in sys.stdin:
    message = json.loads(raw)
    method = message.get("method")
    request_id = message.get("id")
    params = message.get("params") or {}
    if method == "initialize":
        send({"id": request_id, "result": {}})
    elif method == "initialized":
        continue
    elif method == "thread/start":
        thread_id = f"thread-{next_thread}"
        next_thread += 1
        threads[thread_id] = {"usage": 0, "turns": 0}
        send({"id": request_id, "result": {"thread": {"id": thread_id}, "model": params.get("model")}})
    elif method == "turn/start":
        thread_id = params["threadId"]
        prompt = params["input"][0]["text"]
        turn_id = f"turn-{next_turn}"
        next_turn += 1
        if "Compute the SRAM word count" in prompt:
            result = {"sram_words": 8192, "total_slots": 60, "descriptor_bytes_total": 1920, "slot_payload_bytes": 4064}
        elif "For queues 7 and 14" in prompt:
            result = {"q7_slots": [28, 31], "q14_slots": [56, 59], "simultaneous_context_limit": 15}
        elif "Audit these claims" in prompt:
            result = {"invalid_claims": ["a", "b", "c", "d"], "safe_read_boundary": "published_watermark"}
        else:
            result = {"queue_count": 8, "total_slots": 16, "slot_payload_bytes": 1984, "sram_word_bytes": 16, "active_read_allowed": False}
        send({"id": request_id, "result": {"turn": {"id": turn_id}}})
        state = threads[thread_id]
        increment = 1000 if state["turns"] == 0 else 800
        state["turns"] += 1
        state["usage"] += increment
        total = state["usage"]
        usage = {
            "inputTokens": total - 100,
            "cachedInputTokens": max(0, total - 300),
            "outputTokens": 100,
            "reasoningOutputTokens": 25,
            "totalTokens": total,
        }
        last = {
            "inputTokens": increment - 100,
            "cachedInputTokens": max(0, increment - 300),
            "outputTokens": 100,
            "reasoningOutputTokens": 25,
            "totalTokens": increment,
        }
        send({"method": "item/completed", "params": {"threadId": thread_id, "turnId": turn_id, "item": {"id": f"item-{turn_id}", "type": "agentMessage", "text": "<RESULT>" + json.dumps(result) + "</RESULT>"}}})
        send({"method": "thread/tokenUsage/updated", "params": {"threadId": thread_id, "turnId": turn_id, "tokenUsage": {"total": usage, "last": last}}})
        send({"method": "turn/completed", "params": {"threadId": thread_id, "turn": {"id": turn_id, "status": "completed"}}})
'''


def run_arm(root: Path, server: Path, mode: str) -> dict:
    output = root / f"{mode}.json"
    result = subprocess.run(
        [
            sys.executable,
            str(EVAL_SCRIPT),
            "--suite",
            str(SUITE),
            "--mode",
            mode,
            "--model",
            "fake-model",
            "--effort",
            "medium",
            "--cwd",
            str(root),
            "--output",
            str(output),
            "--app-server-command",
            f"{sys.executable} {server}",
            "--json",
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise AssertionError((result.stdout, result.stderr))
    return json.loads(output.read_text(encoding="utf-8"))


def main() -> int:
    sys.path.insert(0, str(SCRIPTS_DIR))
    from oag_thread_reuse_eval import expected_matches

    assert expected_matches({"value": {"$any_of": ["full_name", "short_name"]}}, {"value": "short_name"})
    with tempfile.TemporaryDirectory(prefix="oag-thread-reuse-eval-") as raw_root:
        root = Path(raw_root)
        server = root / "fake_app_server.py"
        server.write_text(FAKE_SERVER, encoding="utf-8")
        fresh = run_arm(root, server, "fresh")
        reuse = run_arm(root, server, "reuse")

        assert fresh["all_passed"] and fresh["passed_count"] == 4, fresh
        assert reuse["all_passed"] and reuse["passed_count"] == 4, reuse
        assert fresh["unique_thread_count"] == 4, fresh
        assert reuse["unique_thread_count"] == 1, reuse
        assert fresh["token_usage"]["total_tokens"] == 4000, fresh
        assert reuse["token_usage"]["total_tokens"] == 3400, reuse
        assert [case["usage"]["total_tokens"] for case in reuse["cases"]] == [1000, 800, 800, 800], reuse
        assert reuse["cases"][-1]["actual"]["queue_count"] == 8, reuse

    print(json.dumps({"status": "pass", "suite": "oag_thread_reuse_eval", "tests": 9}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
