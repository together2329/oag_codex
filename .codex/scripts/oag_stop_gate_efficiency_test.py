#!/usr/bin/env python3
"""Focused regressions for low-noise, fail-closed stop gating."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "hooks"))
sys.path.insert(0, str(ROOT / "scripts"))

import codex_stop_gate  # noqa: E402
import oag_main_write_gate  # noqa: E402


def main() -> int:
    cache = codex_stop_gate._default_cache(  # noqa: SLF001
        {
            "session_id": "session",
            "session_key": "session-key",
            "workspace_key": "workspace-key",
            "cwd": "/tmp",
            "workspace_root": "/tmp",
        }
    )
    mode1, count1 = codex_stop_gate._block_mode(cache, key="ip::gate", digest="a" * 64, max_repeats=3)  # noqa: SLF001
    mode2, count2 = codex_stop_gate._block_mode(cache, key="ip::gate", digest="a" * 64, max_repeats=3)  # noqa: SLF001
    mode3, count3 = codex_stop_gate._block_mode(cache, key="ip::gate", digest="b" * 64, max_repeats=3)  # noqa: SLF001
    assert (mode1, count1) == ("full", 1)
    assert (mode2, count2) == ("compact", 2)
    assert (mode3, count3) == ("full", 1)

    compact = codex_stop_gate._compact_block(label="[OAG:test] gate", digest="a" * 64, count=2)  # noqa: SLF001
    assert "issue_id=" + "a" * 16 in compact
    assert "repeat=2" in compact
    assert len(compact) < 240

    ignored = oag_main_write_gate.IGNORED_PATH_PATTERNS
    for path in (
        "tb/process/__pycache__/check.cpython-314.pyc",
        "tb/.pytest_cache/v/cache/nodeids",
        "tb/process/check.pyc",
    ):
        assert oag_main_write_gate.path_matches(path, ignored), path
    assert not oag_main_write_gate.path_matches("tb/process/check_process_evidence.py", ignored)

    print('{"status":"pass","tests":7,"suite":"oag_stop_gate_efficiency"}')
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
