#!/usr/bin/env python3
"""Render a stage-specific OAG review frame."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from oag_lock_preview_frame import FRAME_MODES, build_frame  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ip-dir", required=True)
    parser.add_argument("--mode", choices=sorted(FRAME_MODES), default="pre-dispatch")
    parser.add_argument("--output-dir", default=None)
    parser.add_argument(
        "--readiness-mode",
        choices=["draft", "lock-ready"],
        default="lock-ready",
        help="Use draft for early, non-blocking review frames.",
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        result = build_frame(
            Path(args.ip_dir),
            Path(args.output_dir) if args.output_dir else None,
            readiness_mode=args.readiness_mode,
            frame_mode=args.mode,
        )
        result["schema_version"] = "oag_review_frame_result.v1"
    except Exception as exc:
        result = {"schema_version": "oag_review_frame_result.v1", "status": "fail", "error": str(exc)}
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
        print(f"Mode: {result['frame_mode']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
