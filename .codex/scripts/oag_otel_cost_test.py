#!/usr/bin/env python3
"""Focused tests for Codex OTEL capture and cost attribution."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import oag_otel_cost as cost
import oag_otel_receiver as receiver


def attr(key: str, value: object) -> dict[str, object]:
    if isinstance(value, int):
        wrapped = {"intValue": str(value)}
    else:
        wrapped = {"stringValue": str(value)}
    return {"key": key, "value": wrapped}


def capture(conversation_id: str = "child-1") -> dict[str, object]:
    attrs = [
        attr("event.name", "codex.sse_event"),
        attr("event.kind", "response.completed"),
        attr("conversation.id", conversation_id),
        attr("model", "gpt-test"),
        attr("input_token_count", 1000),
        attr("cached_token_count", 600),
        attr("output_token_count", 200),
        attr("reasoning_token_count", 80),
        attr("event.timestamp", "2026-07-17T00:00:00Z"),
        attr("user.email", "private@example.com"),
    ]
    return {
        "schema_version": "oag_otlp_capture.v1",
        "received_at": "2026-07-17T00:00:01Z",
        "payload": {
            "resourceLogs": [
                {"resource": {"attributes": []}, "scopeLogs": [{"logRecords": [{"attributes": attrs}]}]}
            ]
        },
    }


class OagOtelCostTest(unittest.TestCase):
    def test_redacts_account_identifiers(self) -> None:
        value = capture()
        redacted = receiver.redact_identifiers(value)
        text = json.dumps(redacted)
        self.assertNotIn("private@example.com", text)
        self.assertIn("[REDACTED]", text)

    def test_extracts_and_deduplicates_usage(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "otel.jsonl"
            row = json.dumps(capture())
            path.write_text(row + "\n" + row + "\n", encoding="utf-8")
            items = cost.usage_from_otel([path])
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["model"], "gpt-test")
        self.assertEqual(items[0]["request_count"], 1)
        self.assertEqual(items[0]["tokens"]["input_tokens"], 1000)
        self.assertEqual(items[0]["tokens"]["cached_input_tokens"], 600)

    def test_cost_separates_cached_and_reasoning_tokens(self) -> None:
        rate = {
            "input_usd_per_million": 10,
            "cached_input_usd_per_million": 1,
            "output_usd_per_million": 20,
            "reasoning_output_usd_per_million": 30,
        }
        result = cost.calculate_cost(
            {
                "input_tokens": 1_000_000,
                "cached_input_tokens": 600_000,
                "output_tokens": 200_000,
                "reasoning_output_tokens": 80_000,
            },
            rate,
        )
        self.assertAlmostEqual(result["components"]["non_cached_input_usd"], 4.0)
        self.assertAlmostEqual(result["components"]["cached_input_usd"], 0.6)
        self.assertAlmostEqual(result["components"]["visible_output_usd"], 2.4)
        self.assertAlmostEqual(result["components"]["reasoning_output_usd"], 2.4)
        self.assertAlmostEqual(result["total"], 9.4)

    def test_rollout_backfill_uses_maximum_session_total(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "rollout.jsonl"
            rows = [
                {
                    "timestamp": "2026-07-17T00:00:00Z",
                    "type": "session_meta",
                    "payload": {"id": "child-1", "cwd": temp},
                },
                {
                    "timestamp": "2026-07-17T00:00:01Z",
                    "type": "turn_context",
                    "payload": {"model": "gpt-runtime"},
                },
                {
                    "timestamp": "2026-07-17T00:00:02Z",
                    "type": "event_msg",
                    "payload": {
                        "type": "token_count",
                        "info": {
                            "total_token_usage": {
                                "input_tokens": 10,
                                "cached_input_tokens": 5,
                                "output_tokens": 2,
                                "reasoning_output_tokens": 1,
                            }
                        },
                    },
                },
                {
                    "timestamp": "2026-07-17T00:00:03Z",
                    "type": "event_msg",
                    "payload": {
                        "type": "token_count",
                        "info": {
                            "total_token_usage": {
                                "input_tokens": 8,
                                "cached_input_tokens": 4,
                                "output_tokens": 1,
                                "reasoning_output_tokens": 0,
                            }
                        },
                    },
                },
            ]
            path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
            item = cost.parse_rollout(path, str(Path(temp).resolve()))
        assert item is not None
        self.assertEqual(item["model"], "gpt-runtime")
        self.assertEqual(item["tokens"]["input_tokens"], 10)

    def test_otel_selection_preserves_rollout_completion(self) -> None:
        otel = [{
            "conversation_id": "child-1",
            "model": "gpt-test",
            "source": "codex_otel",
            "tokens": {
                "input_tokens": 110,
                "cached_input_tokens": 60,
                "output_tokens": 20,
                "reasoning_output_tokens": 8,
            },
            "request_count": 2,
            "started_at": "2026-07-17T00:00:00Z",
            "ended_at": "2026-07-17T00:00:01Z",
        }]
        rollouts = [{
            "conversation_id": "child-1",
            "model": "gpt-test",
            "source": "codex_rollout_backfill",
            "tokens": {
                "input_tokens": 100,
                "cached_input_tokens": 60,
                "output_tokens": 20,
                "reasoning_output_tokens": 8,
            },
            "session_complete": True,
            "rollout_path": "/tmp/rollout.jsonl",
        }]
        items = cost.merge_sources(otel, rollouts)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["source"], "codex_otel")
        self.assertIs(items[0]["session_complete"], True)
        self.assertEqual(items[0]["rollout_path"], "/tmp/rollout.jsonl")
        summary = cost.summarize(items, {"rates": []})
        self.assertEqual(summary["complete_sessions"], 1)
        self.assertEqual(summary["incomplete_or_unknown_sessions"], 0)

    def test_subagent_rollout_subtracts_imported_parent_history(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "rollout.jsonl"
            rows = [
                {
                    "timestamp": "2026-07-17T00:00:00Z",
                    "type": "session_meta",
                    "payload": {
                        "id": "019f6d0c-6900-7b40-ae0f-ed5a577ad4f0",
                        "cwd": temp,
                        "source": {
                            "subagent": {
                                "thread_spawn": {"parent_thread_id": "parent-1", "agent_path": "/root/worker"}
                            }
                        },
                    },
                },
                {
                    "timestamp": "2026-07-17T00:00:00.001Z",
                    "type": "event_msg",
                    "payload": {
                        "type": "token_count",
                        "info": {
                            "total_token_usage": {
                                "input_tokens": 1000,
                                "cached_input_tokens": 600,
                                "output_tokens": 200,
                                "reasoning_output_tokens": 80,
                            }
                        },
                    },
                },
                {
                    "timestamp": "2026-07-17T00:00:00.002Z",
                    "type": "session_meta",
                    "payload": {"id": "parent-1", "cwd": temp},
                },
                {
                    "timestamp": "2026-07-17T00:00:02Z",
                    "type": "event_msg",
                    "payload": {"type": "task_started", "turn_id": "019f6d0c-6a62-7631-b4b3-f92bcfd77aa3"},
                },
                {
                    "timestamp": "2026-07-17T00:00:02.001Z",
                    "type": "turn_context",
                    "payload": {"model": "gpt-runtime"},
                },
                {
                    "timestamp": "2026-07-17T00:00:03Z",
                    "type": "event_msg",
                    "payload": {
                        "type": "token_count",
                        "info": {
                            "total_token_usage": {
                                "input_tokens": 1300,
                                "cached_input_tokens": 700,
                                "output_tokens": 250,
                                "reasoning_output_tokens": 90,
                            }
                        },
                    },
                },
            ]
            path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
            item = cost.parse_rollout(path, str(Path(temp).resolve()))
        assert item is not None
        self.assertEqual(item["conversation_id"], "019f6d0c-6900-7b40-ae0f-ed5a577ad4f0")
        self.assertEqual(item["tokens"]["input_tokens"], 300)
        self.assertEqual(item["tokens"]["cached_input_tokens"], 100)
        self.assertEqual(item["tokens"]["output_tokens"], 50)
        self.assertEqual(item["tokens"]["reasoning_output_tokens"], 10)
        self.assertEqual(item["rollout_accounting"], "post_fork_delta")

    def test_summary_adds_independent_parent_and_child_execution_usage(self) -> None:
        parent = {
            "conversation_id": "parent-1",
            "model": "gpt-runtime",
            "source": "codex_rollout_backfill",
            "parent_session_id": "",
            "rollout_accounting": "root_cumulative_total",
            "tokens": {
                "input_tokens": 1000,
                "cached_input_tokens": 600,
                "output_tokens": 200,
                "reasoning_output_tokens": 80,
            },
        }
        child = {
            "conversation_id": "child-1",
            "model": "gpt-runtime",
            "source": "codex_rollout_backfill",
            "parent_session_id": "parent-1",
            "agent_path": "/root/worker",
            "rollout_accounting": "post_fork_delta",
            "tokens": {
                "input_tokens": 300,
                "cached_input_tokens": 100,
                "output_tokens": 50,
                "reasoning_output_tokens": 10,
            },
        }

        summary = cost.summarize([parent, child], {"rates": []})

        self.assertEqual(summary["tokens"]["input_tokens"], 1300)
        self.assertEqual(summary["tokens"]["cached_input_tokens"], 700)
        self.assertEqual(summary["tokens"]["output_tokens"], 250)
        self.assertEqual(summary["tokens"]["reasoning_output_tokens"], 90)
        self.assertEqual(parent["attribution_basis"], "root_cumulative_total")
        self.assertEqual(child["attribution_basis"], "post_fork_delta")

    def test_correlation_prefers_child_conversation_id(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "correlation.jsonl"
            path.write_text(
                json.dumps(
                    {
                        "conversation_ids": ["child-1", "parent-1"],
                        "primary_conversation_id": "child-1",
                        "agent_type": "oag-rtl-implementation-agent",
                        "dispatch_id": "dispatch-42",
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            mapping = cost.load_correlations([path])
        self.assertEqual(mapping["child-1"]["dispatch_id"], "dispatch-42")
        self.assertEqual(mapping["parent-1"]["dispatch_id"], "dispatch-42")


if __name__ == "__main__":
    unittest.main()
