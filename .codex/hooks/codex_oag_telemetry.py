#!/usr/bin/env python3
"""Record main Codex session identity for OTEL-to-OAG correlation."""

from __future__ import annotations

import json
import sys
from typing import Any

from oag_telemetry import append_execution_event


def read_payload() -> dict[str, Any]:
    try:
        value = json.loads(sys.stdin.read())
    except Exception:
        return {}
    return value if isinstance(value, dict) else {}


def main() -> int:
    payload = read_payload()
    if payload.get("hook_event_name") == "SessionStart":
        append_execution_event(payload, "session_start")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
