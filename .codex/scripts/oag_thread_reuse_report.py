#!/usr/bin/env python3
"""Build a compact comparison report from fresh/reuse evaluation results."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def load_object(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return payload


def percent_change(before: float, after: float) -> float | None:
    if before == 0:
        return None
    return round((after - before) * 100.0 / before, 3)


def usage_with_noncached(payload: dict[str, Any]) -> dict[str, int]:
    usage = payload.get("token_usage") if isinstance(payload.get("token_usage"), dict) else {}
    result = {
        key: int(usage.get(key) or 0)
        for key in (
            "input_tokens",
            "cached_input_tokens",
            "output_tokens",
            "reasoning_output_tokens",
            "total_tokens",
        )
    }
    result["noncached_input_tokens"] = max(0, result["input_tokens"] - result["cached_input_tokens"])
    return result


def compare_pair(root: Path, item: dict[str, Any]) -> dict[str, Any]:
    fresh = load_object((root / str(item["fresh"])).resolve())
    reuse = load_object((root / str(item["reuse"])).resolve())
    fresh_usage = usage_with_noncached(fresh)
    reuse_usage = usage_with_noncached(reuse)
    fresh_passed = int(item.get("fresh_passed_override", fresh.get("passed_count") or 0))
    reuse_passed = int(item.get("reuse_passed_override", reuse.get("passed_count") or 0))
    case_count = int(fresh.get("case_count") or 0)
    metrics: dict[str, Any] = {
        "duration_seconds": {
            "fresh": float(fresh.get("duration_seconds") or 0),
            "reuse": float(reuse.get("duration_seconds") or 0),
        }
    }
    metrics["duration_seconds"]["change_percent"] = percent_change(
        metrics["duration_seconds"]["fresh"], metrics["duration_seconds"]["reuse"]
    )
    for key in fresh_usage:
        metrics[key] = {
            "fresh": fresh_usage[key],
            "reuse": reuse_usage[key],
            "change_percent": percent_change(fresh_usage[key], reuse_usage[key]),
        }
    return {
        "id": str(item.get("id") or ""),
        "category": str(item.get("category") or ""),
        "model": str(fresh.get("model") or ""),
        "reasoning_effort": str(fresh.get("reasoning_effort") or ""),
        "case_count": case_count,
        "fresh_passed": fresh_passed,
        "reuse_passed": reuse_passed,
        "both_functionally_passed": fresh_passed == case_count and reuse_passed == case_count,
        "fresh_unique_thread_count": int(fresh.get("unique_thread_count") or 0),
        "reuse_unique_thread_count": int(reuse.get("unique_thread_count") or 0),
        "hidden_quality": item.get("hidden_quality") or {},
        "metrics": metrics,
    }


def aggregate(pairs: list[dict[str, Any]], category: str) -> dict[str, Any]:
    selected = [pair for pair in pairs if pair.get("category") == category]
    keys = [
        "duration_seconds",
        "input_tokens",
        "cached_input_tokens",
        "noncached_input_tokens",
        "output_tokens",
        "reasoning_output_tokens",
        "total_tokens",
    ]
    metrics: dict[str, Any] = {}
    for key in keys:
        fresh = sum(float(pair["metrics"][key]["fresh"]) for pair in selected)
        reuse = sum(float(pair["metrics"][key]["reuse"]) for pair in selected)
        if key != "duration_seconds":
            fresh = int(fresh)
            reuse = int(reuse)
        metrics[key] = {"fresh": fresh, "reuse": reuse, "change_percent": percent_change(fresh, reuse)}
    return {
        "category": category,
        "pair_count": len(selected),
        "all_functionally_passed": all(bool(pair.get("both_functionally_passed")) for pair in selected),
        "metrics": metrics,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Summarize fresh-versus-reuse evaluation results.")
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    manifest_path = Path(args.manifest).expanduser().resolve()
    manifest = load_object(manifest_path)
    root = manifest_path.parents[2]
    items = manifest.get("experiments") if isinstance(manifest.get("experiments"), list) else []
    pairs = [compare_pair(root, item) for item in items if isinstance(item, dict)]
    categories = sorted({str(pair.get("category") or "") for pair in pairs})
    payload = {
        "schema_version": "oag_thread_reuse_report.v1",
        "report_id": str(manifest.get("id") or manifest_path.stem),
        "decision": manifest.get("decision") or {},
        "experiment_count": len(pairs),
        "experiments": pairs,
        "aggregates": [aggregate(pairs, category) for category in categories],
    }
    output = Path(args.output).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2, sort_keys=True) if args.json else json.dumps(payload, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
