#!/usr/bin/env python3
"""Focused receipt-root path regressions for the OAG closure check."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import oag_closure_check


def write_custom_completion_claim(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "schema_version": "oag_subagent_receipt.v1",
                "role_name": "oag-custom-worker",
                "may_claim_complete": True,
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def scan(ip_dir: Path) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    oag_closure_check.scan_custom_completion_claims(ip_dir, issues)
    return issues


def issue_codes(issues: list[dict[str, str]]) -> set[str]:
    return {str(item.get("code") or "") for item in issues}


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="oag-closure-receipt-path-") as temp:
        root = Path(temp)

        external_codex = root / "external_codex"
        write_custom_completion_claim(external_codex / "oag" / "subagent-receipts" / "external.json")
        linked_ip = root / "linked_ip"
        linked_ip.mkdir()
        (linked_ip / ".codex").symlink_to(external_codex, target_is_directory=True)
        assert scan(linked_ip) == [], "an optional legacy receipt root outside ip-dir must be ignored"

        canonical_ip = root / "canonical_ip"
        write_custom_completion_claim(canonical_ip / "knowledge" / "subagents" / "canonical.json")
        assert "CUSTOM_COMPLETION_CLAIM" in issue_codes(scan(canonical_ip)), "canonical receipts must remain enforced"

        escaped_canonical_ip = root / "escaped_canonical_ip"
        (escaped_canonical_ip / "knowledge").mkdir(parents=True)
        external_subagents = root / "external_subagents"
        external_subagents.mkdir()
        (escaped_canonical_ip / "knowledge" / "subagents").symlink_to(external_subagents, target_is_directory=True)
        assert "CUSTOM_RECEIPT_PATH" in issue_codes(scan(escaped_canonical_ip)), "canonical root escapes must remain fail-closed"

        legacy_ip = root / "legacy_ip"
        legacy_receipts = legacy_ip / ".codex" / "oag" / "subagent-receipts"
        write_custom_completion_claim(legacy_receipts / "legacy.json")
        assert "CUSTOM_COMPLETION_CLAIM" in issue_codes(scan(legacy_ip)), "an in-IP legacy root must still be scanned"

        external_receipt = root / "external_receipt.json"
        write_custom_completion_claim(external_receipt)
        (legacy_receipts / "escaped.json").symlink_to(external_receipt)
        assert "CUSTOM_RECEIPT_PATH" in issue_codes(scan(legacy_ip)), "receipt-file escapes must remain fail-closed"

    print(json.dumps({"ok": True, "suite": "oag_closure_receipt_path"}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
