#!/usr/bin/env python3
"""Focused regression for authored compile-manifest input fingerprints."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import oag_authoring_packet_check  # noqa: E402
import oag_cli  # noqa: E402


TRACKED_INPUTS = [
    "ontology/ipxact_projection.yaml",
    "ontology/actions.yaml",
    "req/mctp_rx_assembler_v0_3_lock_spec.md",
    "req/evidence_plan.yaml",
]


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        legacy_ip = Path(tmp) / "legacy_compile_fingerprint_ip"
        legacy_inputs = {
            str(item["path"])
            for item in oag_cli._compile_input_fingerprints(legacy_ip)
        }
        unexpected = [rel for rel in TRACKED_INPUTS if rel in legacy_inputs]
        assert not unexpected, f"absent optional inputs must not become missing fingerprints: {unexpected}"

        ip = Path(tmp) / "compile_fingerprint_ip"
        for rel in TRACKED_INPUTS:
            path = ip / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(f"source: {rel}\n", encoding="utf-8")

        compile_inputs = {
            str(item["path"]): item
            for item in oag_cli._compile_input_fingerprints(ip)
        }
        missing = [rel for rel in TRACKED_INPUTS if rel not in compile_inputs]
        assert not missing, f"compile fingerprints omit authored inputs: {missing}"

        manifest_path = ip / "ontology" / "generated" / "compile_manifest.json"
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(
            json.dumps(
                {
                    "schema_version": "oag_compile_manifest.v1",
                    "status": "pass",
                    "input_fingerprints": [compile_inputs[rel] for rel in TRACKED_INPUTS],
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )

        baseline_issues, _ = oag_authoring_packet_check.check_compile_manifest_freshness(
            ip,
            hard_gate=True,
        )
        assert not baseline_issues, baseline_issues

        observed: list[str] = []
        for rel in TRACKED_INPUTS:
            path = ip / rel
            original = path.read_text(encoding="utf-8")
            path.write_text(original + "mutated: true\n", encoding="utf-8")
            issues, _ = oag_authoring_packet_check.check_compile_manifest_freshness(
                ip,
                hard_gate=True,
            )
            stale = [
                item
                for item in issues
                if item.get("code") == "COMPILE_MANIFEST_STALE_INPUT"
                and Path(str(item.get("path"))).resolve() == path.resolve()
            ]
            assert stale, f"mutation did not stale compile manifest input: {rel}: {issues}"
            observed.append(rel)
            path.write_text(original, encoding="utf-8")

        print(
            json.dumps(
                {
                    "status": "pass",
                    "tracked_inputs": TRACKED_INPUTS,
                    "stale_mutations_observed": observed,
                },
                indent=2,
                sort_keys=True,
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
