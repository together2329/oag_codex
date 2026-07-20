#!/usr/bin/env python3
"""Block locked-stage implementation writes that bypass dispatched OAG executors."""

from __future__ import annotations

import argparse
import fnmatch
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from pathlib import PurePosixPath
from typing import Any


SCRIPTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS_DIR))

import oag_paths  # noqa: E402
import oag_dispatch_verify  # noqa: E402
import oag_dispatch_support  # noqa: E402
import oag_ip_git  # noqa: E402

PROJECT_ROOT = Path(os.environ.get("OAG_PROJECT_ROOT") or oag_dispatch_support.PROJECT_ROOT).expanduser().resolve()

IMPLEMENTATION_PATTERNS = (
    "rtl/*.sv",
    "rtl/**/*.sv",
    "rtl/*.v",
    "rtl/**/*.v",
    "rtl/*.svh",
    "rtl/**/*.svh",
    "list/*.f",
    "list/**/*.f",
    "list/*.vf",
    "list/**/*.vf",
    "tb/*",
    "tb/**/*",
    "scripts/run_lint.sh",
    "scripts/run_lint.py",
    "scripts/*lint*",
    "scripts/**/*lint*",
    "scripts/run_sim.sh",
    "scripts/*sim*",
    "scripts/**/*sim*",
    "sim/*",
    "sim/**/*",
    "lint/*",
    "lint/**/*",
    "cov/*",
    "cov/**/*",
    "coverage/*",
    "coverage/**/*",
    "formal/*",
    "formal/**/*",
    "sdc/*",
    "sdc/**/*",
    "signoff/*",
    "signoff/**/*",
)
IGNORED_PATH_PATTERNS = (
    "**/.gitkeep",
    "**/__pycache__/**",
    "**/*.pyc",
    "**/*.pyo",
    "**/.pytest_cache/**",
    "knowledge/dispatches/**/*",
    "knowledge/subagents/**/*",
    "ontology/generated/**/*",
)
COVERING_RECEIPT_STATUSES = {"HANDOFF_PASS", "STATIC_HANDOFF_PASS", "RTL_HANDOFF_PASS"}
TERMINAL_RECEIPT_STATUSES = COVERING_RECEIPT_STATUSES | {"FAIL", "BLOCKED", "INCONCLUSIVE"}
WAIVER_ACTIONS = {"main_agent_subagent_waiver", "subagent_waiver", "main_agent_implementation_waiver"}
OUTPUT_SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


def issue(code: str, message: str, path: str | None = None) -> dict[str, str]:
    payload = {"code": code, "message": message}
    if path:
        payload["path"] = path
    return payload


def timestamps_in_nondecreasing_order(*values: datetime | None) -> bool:
    """Require complete causal timestamps while allowing second-boundary skew."""
    return all(value is not None for value in values) and all(
        earlier <= later for earlier, later in zip(values, values[1:])
    )


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def project_rel(path: Path) -> str:
    resolved = path.expanduser().resolve()
    try:
        return resolved.relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        return resolved.as_posix()


def resolve_project_path(raw: str) -> Path:
    path = Path(raw).expanduser()
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return path.resolve()


def normalize_candidate(raw: str, ip_dir: Path) -> str:
    if not raw:
        return ""
    path = Path(raw).expanduser()
    if path.is_absolute():
        return project_rel(path)
    ip_rel = project_rel(ip_dir)
    normalized = raw.strip().replace("\\", "/").strip("/")
    while normalized.startswith("./"):
        normalized = normalized[2:]
    if ip_rel in {"", "."}:
        return normalized
    if normalized == ip_rel or normalized.startswith(ip_rel + "/"):
        return normalized
    return f"{ip_rel}/{normalized}" if ip_rel else normalized


def ip_relative(path: str, ip_dir: Path) -> str:
    ip_rel = project_rel(ip_dir)
    return path[len(ip_rel) + 1:] if path.startswith(ip_rel + "/") else path


def path_matches(path: str, patterns: tuple[str, ...] | list[str]) -> bool:
    normalized = path.strip("/")
    for pattern in patterns:
        pat = str(pattern).strip("/")
        if not pat:
            continue
        if fnmatch.fnmatch(normalized, pat) or fnmatch.fnmatch(normalized, pat.rstrip("/") + "/*"):
            return True
        if normalized == pat or normalized.startswith(pat + "/"):
            return True
    return False


def scope_locked(ip_dir: Path) -> bool:
    try:
        payload = load_json(oag_paths.legacy_or_hidden(ip_dir, "ontology/scope_lock.json"))
    except Exception:
        return False
    return isinstance(payload, dict) and str(payload.get("state") or "").strip().lower() == "locked"


def git_status_paths(ip_dir: Path) -> tuple[list[str], list[dict[str, str]]]:
    _raw, paths, error = oag_ip_git.repository_status_paths(ip_dir, PROJECT_ROOT)
    if error:
        return [], [issue("IP_GIT_STATUS_FAILED", error, project_rel(ip_dir))]
    return paths, []


def implementation_changes(ip_dir: Path) -> tuple[list[str], list[dict[str, str]]]:
    candidates: list[str] = []
    status_paths, status_issues = git_status_paths(ip_dir)
    for path in status_paths:
        rel = ip_relative(path, ip_dir)
        if path_matches(rel, IGNORED_PATH_PATTERNS):
            continue
        if path_matches(rel, IMPLEMENTATION_PATTERNS):
            candidates.append(path)
    return sorted(set(candidates)), status_issues


def human_waiver(ip_dir: Path) -> dict[str, Any] | None:
    validations = oag_paths.legacy_or_hidden(ip_dir, "ontology/validations")
    for path in sorted(validations.glob("DEC_*.json"), reverse=True):
        try:
            receipt = load_json(path)
        except Exception:
            continue
        if not isinstance(receipt, dict):
            continue
        action = str(receipt.get("action") or "").strip()
        actor = receipt.get("actor") if isinstance(receipt.get("actor"), dict) else {}
        approval = receipt.get("approval") if isinstance(receipt.get("approval"), dict) else {}
        if (
            action in WAIVER_ACTIONS
            and receipt.get("allowed") is True
            and str(actor.get("kind") or "").lower() == "human"
            and approval.get("approved") is True
            and str(approval.get("approved_by") or "") == str(actor.get("id") or "")
            and str(approval.get("reason") or "").strip()
            and str(receipt.get("ledger_event") or "").strip()
        ):
            return {"path": project_rel(path), "receipt": receipt}
    return None


def static_receipt_contract(
    ip_dir: Path,
    dispatch_path: Path,
    dispatch: dict[str, Any],
    receipt_path: Path,
    receipt: dict[str, Any],
) -> tuple[list[str], set[str], set[str], dict[str, str]]:
    """Validate immutable dispatch/receipt fields without reading current outputs."""
    errors: list[str] = []
    if oag_dispatch_verify.schema_issues("oag_dispatch.schema.json", dispatch):
        errors.append("DISPATCH_SCHEMA")
    if oag_dispatch_verify.schema_issues("oag_subagent_receipt.schema.json", receipt):
        errors.append("RECEIPT_SCHEMA")
    dispatch_id = str(dispatch.get("dispatch_id") or "")
    if dispatch_path.stem != dispatch_id or not oag_dispatch_verify.valid_dispatch_integrity(dispatch):
        errors.append("DISPATCH_INTEGRITY")
    raw_ip_dir = str(dispatch.get("ip_dir") or "")
    raw_ip_path = Path(raw_ip_dir).expanduser()
    ip_candidates = {
        (ip_dir / raw_ip_path).resolve(),
        (ip_dir.parent / raw_ip_path).resolve(),
        (PROJECT_ROOT / raw_ip_path).resolve(),
    }
    if raw_ip_path.is_absolute():
        ip_candidates.add(raw_ip_path.resolve())
    if ip_dir not in ip_candidates:
        errors.append("DISPATCH_IP_DIR")
    if not oag_dispatch_verify.reference_matches_file(dispatch.get("dispatch_path"), dispatch_path, ip_dir):
        errors.append("DISPATCH_PATH")
    if not oag_dispatch_verify.reference_matches_file(dispatch.get("receipt_path"), receipt_path, ip_dir):
        errors.append("RECEIPT_PATH")
    if str(receipt.get("dispatch_id") or "") != dispatch_id:
        errors.append("DISPATCH_ID_MISMATCH")
    if not oag_dispatch_verify.reference_matches_file(receipt.get("dispatch_path"), dispatch_path, ip_dir):
        errors.append("RECEIPT_DISPATCH_PATH")
    for field in oag_dispatch_verify.MIRRORED_SCALAR_FIELDS:
        if str(receipt.get(field) or "") != str(dispatch.get(field) or ""):
            errors.append(f"MIRRORED_{field.upper()}")
    for field in oag_dispatch_verify.MIRRORED_LIST_FIELDS:
        if oag_dispatch_verify.string_items(receipt.get(field)) != oag_dispatch_verify.string_items(dispatch.get(field)):
            errors.append(f"MIRRORED_{field.upper()}")
    if oag_dispatch_verify.dispatch_has_wavefront_metadata(dispatch):
        for field in oag_dispatch_verify.WAVEFRONT_FIELDS:
            if not str(dispatch.get(field) or "") or str(receipt.get(field) or "") != str(dispatch.get(field) or ""):
                errors.append(f"WAVEFRONT_{field.upper()}")
    dispatch_time = oag_dispatch_verify.parse_timestamp(dispatch.get("created_at"))
    baseline = dispatch.get("baseline") if isinstance(dispatch.get("baseline"), dict) else {}
    baseline_time = oag_dispatch_verify.parse_timestamp(baseline.get("created_at"))
    receipt_time = oag_dispatch_verify.parse_timestamp(receipt.get("created_at"))
    if not timestamps_in_nondecreasing_order(baseline_time, dispatch_time):
        errors.append("DISPATCH_TIMESTAMP")
    if not timestamps_in_nondecreasing_order(dispatch_time, receipt_time):
        errors.append("RECEIPT_TIMESTAMP")
    if (
        receipt.get("may_claim_complete") is not False
        or receipt.get("diagnostic_only") is not False
        or receipt.get("dispatch_verified") is not True
        or str(receipt.get("status") or "") not in TERMINAL_RECEIPT_STATUSES
    ):
        errors.append("RECEIPT_FLAGS")
    errors.extend(item["code"] for item in oag_dispatch_verify.worker_thread_execution_issues(dispatch, receipt))

    allowed_write_paths = {
        normalize_candidate(item, ip_dir)
        for item in oag_dispatch_verify.string_items(dispatch.get("allowed_write_paths")) or []
    }
    allowed_side_effects = {
        normalize_candidate(item, ip_dir)
        for item in oag_dispatch_verify.string_items(dispatch.get("allowed_tool_side_effects")) or []
    }
    owned_raw: list[str] = []
    for field in ("changed_paths", "owned_changed_paths"):
        value = receipt.get(field)
        if value is None and field == "owned_changed_paths":
            continue
        items = oag_dispatch_verify.string_items(value)
        if items is None:
            errors.append(f"RECEIPT_{field.upper()}")
            continue
        owned_raw.extend(items)
    generated_items = oag_dispatch_verify.string_items(receipt.get("generated_side_effects"))
    if generated_items is None:
        errors.append("RECEIPT_GENERATED_SIDE_EFFECTS")
        generated_items = []
    owned = {normalize_candidate(item, ip_dir) for item in owned_raw}
    generated = {normalize_candidate(item, ip_dir) for item in generated_items}
    if any(not item or not path_matches(item, list(allowed_write_paths)) for item in owned):
        errors.append("OWNED_PATH_OUT_OF_SCOPE")
    if any(not item or not path_matches(item, list(allowed_side_effects)) for item in generated):
        errors.append("GENERATED_PATH_OUT_OF_SCOPE")

    output_hashes: dict[str, str] = {}
    raw_hashes = receipt.get("output_hashes")
    if raw_hashes is not None and not isinstance(raw_hashes, dict):
        errors.append("OUTPUT_HASHES_OBJECT")
    elif isinstance(raw_hashes, dict):
        for raw_path, raw_digest in raw_hashes.items():
            if (
                not isinstance(raw_path, str)
                or raw_path.startswith("/")
                or "\\" in raw_path
                or raw_path != PurePosixPath(raw_path).as_posix()
            ):
                errors.append("OUTPUT_HASH_PATH_UNSAFE")
                continue
            normalized = normalize_candidate(raw_path, ip_dir)
            digest = raw_digest if isinstance(raw_digest, str) else ""
            if OUTPUT_SHA256_RE.fullmatch(digest) is None:
                errors.append("OUTPUT_HASH_FORMAT")
                continue
            if not path_matches(normalized, list(allowed_write_paths)):
                errors.append("OUTPUT_HASH_OUT_OF_SCOPE")
                continue
            output_hashes[normalized] = digest
    return sorted(set(errors)), owned, generated, output_hashes


def wavefront_task_scope_matches(
    dispatch: dict[str, Any],
    task: dict[str, Any],
    events: list[dict[str, Any]],
    ip_dir: Path,
) -> bool:
    """Match the claimed task scope, including integration shared artifacts."""
    task_paths = {
        str(item)
        for field in ("allowed_write_paths", "shared_artifacts")
        for item in task.get(field, [])
        if isinstance(item, str)
    }
    raw_dispatch_paths = dispatch.get("allowed_write_paths") if isinstance(dispatch.get("allowed_write_paths"), list) else []
    dispatch_paths = {
        normalized
        for raw in raw_dispatch_paths
        if (normalized := oag_dispatch_verify.ip_relative_reference(raw, ip_dir)) is not None
    }
    if len(dispatch_paths) != len(raw_dispatch_paths):
        return False
    receipt_path = oag_dispatch_verify.ip_relative_reference(dispatch.get("receipt_path"), ip_dir)
    if receipt_path is None:
        return False
    receipt_parent = PurePosixPath(receipt_path).parent.as_posix()
    scope_matches = frozenset(dispatch_paths) in {
        frozenset(task_paths),
        frozenset({*task_paths, receipt_path}),
        frozenset({*task_paths, receipt_parent}),
    }
    if not scope_matches:
        return False
    dispatch_time = oag_dispatch_verify.parse_timestamp(dispatch.get("created_at"))
    task_claim_time = oag_dispatch_verify.parse_timestamp(task.get("claimed_at"))
    claim_events = []
    for event in events:
        details = event.get("details") if isinstance(event.get("details"), dict) else {}
        write_paths = oag_dispatch_verify.string_items(details.get("write_paths"))
        event_time = oag_dispatch_verify.parse_timestamp(event.get("created_at"))
        if (
            event.get("event") == "claimed"
            and str(event.get("task_id") or "") == str(dispatch.get("task_id") or "")
            and str(event.get("status") or "") == "claimed"
            and write_paths is not None
            and set(write_paths) == task_paths
            and event_time is not None
            and timestamps_in_nondecreasing_order(dispatch_time, task_claim_time, event_time)
        ):
            claim_events.append(event)
    return len(claim_events) == 1


def safe_ip_file_reference(value: Any, ip_dir: Path) -> Path | None:
    if not isinstance(value, str) or not value:
        return None
    raw = Path(value).expanduser()
    candidates = [raw] if raw.is_absolute() else [ip_dir / value, PROJECT_ROOT / value]
    for candidate in candidates:
        try:
            resolved = candidate.resolve(strict=True)
            resolved.relative_to(ip_dir.resolve(strict=True))
        except (FileNotFoundError, OSError, RuntimeError, ValueError):
            continue
        safe, _ = oag_dispatch_verify.safe_ip_regular_file(resolved, ip_dir)
        if safe:
            return resolved
    return None


def recorded_event_receipt_path(
    events: list[dict[str, Any]],
    event_index: int,
    ip_dir: Path,
) -> Path | None:
    event = events[event_index]
    if event.get("event") != "recorded":
        return None
    task_id = str(event.get("task_id") or "")
    status = str(event.get("status") or "")
    details = event.get("details") if isinstance(event.get("details"), dict) else {}
    raw_receipt = details.get("receipt")
    if status in oag_dispatch_verify.WAVEFRONT_APPROVED_TERMINAL_STATUSES:
        previous = next(
            (
                candidate
                for candidate in reversed(events[:event_index])
                if candidate.get("event") == "recorded" and str(candidate.get("task_id") or "") == task_id
            ),
            None,
        )
        if previous is None or str(previous.get("status") or "") != "review_pending":
            return None
        previous_time = oag_dispatch_verify.parse_timestamp(previous.get("created_at"))
        event_time = oag_dispatch_verify.parse_timestamp(event.get("created_at"))
        if not timestamps_in_nondecreasing_order(previous_time, event_time):
            return None
        previous_details = previous.get("details") if isinstance(previous.get("details"), dict) else {}
        if oag_dispatch_verify.string_items(previous_details.get("barrier_outputs")) != []:
            return None
        previous_receipt = safe_ip_file_reference(previous_details.get("receipt"), ip_dir)
        current_receipt = safe_ip_file_reference(raw_receipt, ip_dir)
        if previous_receipt is None or (current_receipt is not None and current_receipt != previous_receipt):
            return None
        return previous_receipt
    return safe_ip_file_reference(raw_receipt, ip_dir)


def terminal_event_decision(
    event: dict[str, Any],
    *,
    ip_dir: Path,
    run_id: str,
    task_id: str,
) -> tuple[dict[str, Any], Path | None]:
    status = str(event.get("status") or "")
    if status not in oag_dispatch_verify.WAVEFRONT_APPROVED_TERMINAL_STATUSES:
        return {}, None
    details = event.get("details") if isinstance(event.get("details"), dict) else {}
    decision_path = safe_ip_file_reference(details.get("decision"), ip_dir)
    event_barriers = oag_dispatch_verify.string_items(details.get("barrier_outputs"))
    if decision_path is None or event_barriers is None:
        return {}, None
    decision = oag_dispatch_verify.load_json_dict_if_valid(decision_path)
    target = decision.get("target") if isinstance(decision.get("target"), dict) else {}
    unlocks = decision.get("unlocks") if isinstance(decision.get("unlocks"), dict) else {}
    decision_barriers = oag_dispatch_verify.string_items(unlocks.get("barrier_outputs"))
    rationale = decision.get("rationale") if isinstance(decision.get("rationale"), dict) else {}
    blockers = rationale.get("blockers") if isinstance(rationale.get("blockers"), list) else []
    reviewer = decision.get("reviewer") if isinstance(decision.get("reviewer"), dict) else {}
    verdict = str(decision.get("verdict") or "")
    decision_time = oag_dispatch_verify.parse_timestamp(decision.get("created_at"))
    event_time = oag_dispatch_verify.parse_timestamp(event.get("created_at"))
    if (
        oag_dispatch_verify.schema_issues("oag_wavefront_decision.schema.json", decision)
        or decision_path.stem != str(decision.get("decision_id") or "")
        or str(target.get("kind") or "") != "wavefront_task"
        or str(target.get("run_id") or "") != run_id
        or str(target.get("task_id") or "") != task_id
        or str(unlocks.get("wavefront_status") or "") != status
        or decision_barriers is None
        or sorted(decision_barriers) != sorted(event_barriers)
        or decision_time is None
        or event_time is None
        or decision_time > event_time
        or not oag_dispatch_verify.decision_verdict_status_valid(verdict, status, reviewer, blockers)
    ):
        return {}, None
    return decision, decision_path


def wavefront_receipt_attestation(
    dispatch: dict[str, Any],
    receipt_path: Path,
    receipt: dict[str, Any],
) -> tuple[str, str, list[str]]:
    """Resolve a receipt to active, approved terminal, aborted, or invalid lineage."""
    if not oag_dispatch_verify.dispatch_has_wavefront_metadata(dispatch):
        return "non_wavefront", "", []
    ip_dir, task_map, events, locks, context_issues = oag_dispatch_verify.load_strict_wavefront_context(dispatch)
    task_id = str(dispatch.get("task_id") or "")
    dispatch_id = str(dispatch.get("dispatch_id") or "")
    task = task_map.get(task_id, {})
    if ip_dir is None or events is None or not task:
        fallback = oag_dispatch_verify.wavefront_task_for_dispatch(dispatch)
        fallback_status = str(fallback.get("status") or "")
        if fallback_status in oag_dispatch_verify.WAVEFRONT_ACTIVE_STATUSES:
            return "active", fallback_status, [str(item.get("code") or "WAVEFRONT_CONTEXT") for item in context_issues]
        return "invalid", fallback_status, [str(item.get("code") or "WAVEFRONT_CONTEXT") for item in context_issues]

    status = str(task.get("status") or "")
    marker = task.get("abort_marker") if isinstance(task.get("abort_marker"), dict) else {}
    dispatch_anchored = str(task.get("dispatch_id") or "") == dispatch_id
    abort_anchored = str(marker.get("dispatch_id") or "") == dispatch_id
    if status in oag_dispatch_verify.WAVEFRONT_ACTIVE_STATUSES:
        return ("active" if dispatch_anchored else "invalid"), status, []
    if status in oag_dispatch_verify.WAVEFRONT_ABORT_STATUSES and (dispatch_anchored or abort_anchored):
        return "aborted", status, []
    if status not in oag_dispatch_verify.WAVEFRONT_APPROVED_TERMINAL_STATUSES or not dispatch_anchored:
        return "invalid", status, []

    dispatch_path = ip_dir / "knowledge" / "dispatches" / f"{dispatch_id}.json"
    task_locks = [
        lock
        for lock in locks.get("locks", [])
        if isinstance(lock, dict) and str(lock.get("task_id") or "") == task_id
    ] if isinstance(locks.get("locks"), list) else []
    graph_agent_type = str(task.get("agent_type") or "")
    if (
        oag_dispatch_verify.load_json_dict_if_valid(dispatch_path) != dispatch
        or task_locks
        or not oag_dispatch_verify.reference_matches_file(task.get("receipt_path"), receipt_path, ip_dir)
        or str(task.get("ownership_mode") or "") != str(dispatch.get("ownership_mode") or "")
        or str(task.get("phase") or "") != str(dispatch.get("stage") or "")
        or (graph_agent_type and graph_agent_type != str(dispatch.get("agent_type") or ""))
        or not wavefront_task_scope_matches(dispatch, task, events, ip_dir)
    ):
        return "terminal_invalid", status, ["WAVEFRONT_TERMINAL_ANCHOR"]

    receipt_time = oag_dispatch_verify.parse_timestamp(receipt.get("created_at"))
    matching: list[tuple[dict[str, Any], dict[str, Any], Path, datetime]] = []
    for event_index, event in enumerate(events):
        event_time = oag_dispatch_verify.parse_timestamp(event.get("created_at"))
        if (
            event.get("event") != "recorded"
            or str(event.get("task_id") or "") != task_id
            or str(event.get("status") or "") != status
            or event_time is None
            or receipt_time is None
            or event_time < receipt_time
            or recorded_event_receipt_path(events, event_index, ip_dir) != receipt_path
        ):
            continue
        decision, decision_path = terminal_event_decision(
            event,
            ip_dir=ip_dir,
            run_id=str(dispatch.get("wavefront_run_id") or ""),
            task_id=task_id,
        )
        previous = next(
            (
                candidate
                for candidate in reversed(events[:event_index])
                if candidate.get("event") == "recorded" and str(candidate.get("task_id") or "") == task_id
            ),
            None,
        )
        review_time = oag_dispatch_verify.parse_timestamp(previous.get("created_at")) if previous else None
        if (
            decision
            and decision_path is not None
            and review_time is not None
            and timestamps_in_nondecreasing_order(receipt_time, review_time, event_time)
        ):
            matching.append((event, decision, decision_path, review_time))
    if len(matching) != 1:
        return "terminal_invalid", status, ["WAVEFRONT_TERMINAL_EVENT"]
    event, decision, decision_path, review_time = matching[0]
    decision_time = oag_dispatch_verify.parse_timestamp(decision.get("created_at"))
    event_time = oag_dispatch_verify.parse_timestamp(event.get("created_at"))
    task_recorded_time = oag_dispatch_verify.parse_timestamp(task.get("recorded_at"))
    unlocks = decision.get("unlocks") if isinstance(decision.get("unlocks"), dict) else {}
    decision_barriers = oag_dispatch_verify.string_items(unlocks.get("barrier_outputs"))
    task_barriers = oag_dispatch_verify.string_items(task.get("barrier_outputs"))
    if (
        not timestamps_in_nondecreasing_order(
            receipt_time,
            review_time,
            decision_time,
            task_recorded_time,
            event_time,
        )
        or str(task.get("decision_id") or "") != str(decision.get("decision_id") or "")
        or str(task.get("decision_type") or "") != str(decision.get("decision_type") or "")
        or not oag_dispatch_verify.reference_matches_file(task.get("decision_path"), decision_path, ip_dir)
        or decision_barriers is None
        or task_barriers is None
        or sorted(decision_barriers) != sorted(task_barriers)
    ):
        return "terminal_invalid", status, ["WAVEFRONT_DECISION_ANCHOR"]
    return "terminal_approved", status, [project_rel(decision_path)]


def current_output_digest(path: str) -> str | None:
    artifact = PROJECT_ROOT / path
    if not artifact.is_file() or artifact.is_symlink():
        return None
    return f"sha256:{oag_dispatch_verify.sha256(artifact)}"


def full_dispatch_verification(dispatch_path: Path, receipt_path: Path) -> bool:
    result = oag_dispatch_verify.verify_dispatch(
        argparse.Namespace(dispatch=str(dispatch_path), receipt=str(receipt_path), schema_only=False)
    )
    return result.get("status") == "pass"


def receipt_covered_paths(
    ip_dir: Path,
) -> tuple[set[str], list[dict[str, Any]], set[str], list[dict[str, str]]]:
    coverage_candidates: dict[str, list[tuple[datetime, str]]] = {}
    receipts: list[dict[str, Any]] = []
    receipt_rows: dict[str, dict[str, Any]] = {}
    completed_dispatch_ids: set[str] = set()
    for path in sorted(oag_paths.legacy_or_hidden(ip_dir, "knowledge/subagents").glob("*.json")):
        try:
            receipt = load_json(path)
        except Exception:
            continue
        if not isinstance(receipt, dict):
            continue
        role = str(receipt.get("role_name") or "")
        if not role.startswith("oag-"):
            continue
        if receipt.get("schema_version") != "oag_subagent_receipt.v1":
            continue
        status = str(receipt.get("status") or "")
        if receipt.get("may_claim_complete") is not False or status not in TERMINAL_RECEIPT_STATUSES:
            continue
        dispatch_path = normalize_candidate(str(receipt.get("dispatch_path") or ""), ip_dir)
        if not dispatch_path or not (PROJECT_ROOT / dispatch_path).is_file():
            receipts.append(
                {
                    "path": project_rel(path),
                    "role_name": role,
                    "dispatch_id": str(receipt.get("dispatch_id") or ""),
                    "status": status,
                    "provenance_status": "ignored",
                    "provenance_notes": ["SUBAGENT_RECEIPT_DISPATCH_MISSING"],
                    "covers_writes": False,
                    "covered_paths": [],
                }
            )
            continue
        dispatch_file = (PROJECT_ROOT / dispatch_path).resolve()
        try:
            dispatch = load_json(dispatch_file)
        except Exception:
            dispatch = {}
        if not isinstance(dispatch, dict):
            dispatch = {}
        contract_errors, owned, generated, output_hashes = static_receipt_contract(
            ip_dir,
            dispatch_file,
            dispatch,
            path.resolve(),
            receipt,
        )
        dispatch_id = str(receipt.get("dispatch_id") or "").strip()
        live_verified = False
        if contract_errors:
            task = oag_dispatch_verify.wavefront_task_for_dispatch(dispatch)
            if str(task.get("status") or "") in oag_dispatch_verify.WAVEFRONT_ACTIVE_STATUSES:
                live_verified = full_dispatch_verification(dispatch_file, path.resolve())
            if not live_verified:
                receipts.append(
                    {
                        "path": project_rel(path),
                        "role_name": role,
                        "dispatch_id": dispatch_id,
                        "status": status,
                        "provenance_status": "ignored",
                        "provenance_notes": contract_errors,
                        "covers_writes": False,
                        "covered_paths": [],
                    }
                )
                continue

        attestation, terminal_status, attestation_notes = wavefront_receipt_attestation(dispatch, path.resolve(), receipt)
        if attestation == "active" and not live_verified:
            live_verified = full_dispatch_verification(dispatch_file, path.resolve())
        elif attestation == "non_wavefront" and not output_hashes:
            live_verified = full_dispatch_verification(dispatch_file, path.resolve())
        if attestation in {"terminal_approved", "aborted", "non_wavefront"} or live_verified:
            completed_dispatch_ids.add(dispatch_id)
        can_cover = bool(
            status in COVERING_RECEIPT_STATUSES
            and receipt.get("diagnostic_only") is False
            and receipt.get("covers_writes") is True
            and receipt.get("dispatch_verified") is True
            and (attestation in {"terminal_approved", "non_wavefront"} or live_verified)
        )
        candidate_paths: set[str] = set()
        if can_cover:
            attested_paths = owned | generated
            if attestation == "terminal_approved":
                attested_paths |= set(output_hashes)
            for candidate in attested_paths:
                digest = current_output_digest(candidate)
                if (digest is not None and output_hashes.get(candidate) == digest) or live_verified:
                    candidate_paths.add(candidate)
        row = {
            "path": project_rel(path),
            "role_name": role,
            "dispatch_id": dispatch_id,
            "status": status,
            "dispatch_verified": True,
            "attestation": attestation,
            "terminal_status": terminal_status,
            "provenance_status": "candidate" if candidate_paths else ("quarantined" if attestation == "aborted" else "superseded"),
            "provenance_notes": attestation_notes,
            "covers_writes": False,
            "covered_paths": [],
        }
        receipts.append(row)
        receipt_rows[project_rel(path)] = row
        receipt_time = oag_dispatch_verify.parse_timestamp(receipt.get("created_at"))
        if receipt_time is not None:
            for candidate in candidate_paths:
                coverage_candidates.setdefault(candidate, []).append((receipt_time, project_rel(path)))

    covered: set[str] = set()
    for candidate, candidates in coverage_candidates.items():
        _, selected_receipt = max(candidates, key=lambda item: (item[0], item[1]))
        covered.add(candidate)
        row = receipt_rows[selected_receipt]
        row["covered_paths"].append(candidate)
        row["covers_writes"] = True
        row["provenance_status"] = "selected"
    for row in receipt_rows.values():
        row["covered_paths"] = sorted(row["covered_paths"])
    return covered, receipts, completed_dispatch_ids, []


def diagnostic_receipts(ip_dir: Path) -> list[dict[str, Any]]:
    receipts: list[dict[str, Any]] = []
    for path in sorted(oag_paths.legacy_or_hidden(ip_dir, "knowledge/subagents").glob("*.json")):
        try:
            receipt = load_json(path)
        except Exception:
            continue
        if not isinstance(receipt, dict):
            continue
        if receipt.get("schema_version") != "oag_subagent_diagnostic_receipt.v1":
            continue
        receipts.append(
            {
                "path": project_rel(path),
                "role_name": str(receipt.get("role_name") or ""),
                "status": str(receipt.get("status") or ""),
                "blocker_class": str(receipt.get("blocker_class") or ""),
                "covers_writes": str(receipt.get("covers_writes") or ""),
            }
        )
    return receipts


def wavefront_dispatch_is_terminal(dispatch: dict[str, Any]) -> bool:
    if not oag_dispatch_verify.dispatch_has_wavefront_metadata(dispatch):
        return False
    ip_dir, task_map, events, _locks, context_issues = oag_dispatch_verify.load_strict_wavefront_context(dispatch)
    task_id = str(dispatch.get("task_id") or "")
    dispatch_id = str(dispatch.get("dispatch_id") or "")
    task = task_map.get(task_id, {})
    if ip_dir is None or events is None or context_issues or not task:
        return False
    status = str(task.get("status") or "")
    marker = task.get("abort_marker") if isinstance(task.get("abort_marker"), dict) else {}
    if status in oag_dispatch_verify.WAVEFRONT_DECISION_STATUSES and (
        str(task.get("dispatch_id") or "") == dispatch_id or str(marker.get("dispatch_id") or "") == dispatch_id
    ):
        return True

    receipt_path = safe_ip_file_reference(dispatch.get("receipt_path"), ip_dir)
    dispatch_time = oag_dispatch_verify.parse_timestamp(dispatch.get("created_at"))
    if receipt_path is None or dispatch_time is None:
        return False
    for event_index, event in enumerate(events):
        event_status = str(event.get("status") or "")
        event_time = oag_dispatch_verify.parse_timestamp(event.get("created_at"))
        if (
            event.get("event") != "recorded"
            or str(event.get("task_id") or "") != task_id
            or event_status not in oag_dispatch_verify.WAVEFRONT_DECISION_STATUSES
            or event_time is None
            or event_time < dispatch_time
            or recorded_event_receipt_path(events, event_index, ip_dir) != receipt_path
        ):
            continue
        if event_status in oag_dispatch_verify.WAVEFRONT_ABORT_STATUSES:
            return True
        decision, decision_path = terminal_event_decision(
            event,
            ip_dir=ip_dir,
            run_id=str(dispatch.get("wavefront_run_id") or ""),
            task_id=task_id,
        )
        if decision and decision_path is not None:
            return True
    return False


def active_dispatch_conflicts(ip_dir: Path, changes: list[str], completed_dispatch_ids: set[str]) -> list[dict[str, str]]:
    conflicts: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    dispatch_dir = oag_paths.legacy_or_hidden(ip_dir, "knowledge/dispatches")
    for path in sorted(dispatch_dir.glob("*.json")):
        try:
            dispatch = load_json(path)
        except Exception:
            continue
        if not isinstance(dispatch, dict) or dispatch.get("schema_version") != "oag_dispatch.v1":
            continue
        dispatch_id = str(dispatch.get("dispatch_id") or "").strip()
        if (dispatch_id and dispatch_id in completed_dispatch_ids) or wavefront_dispatch_is_terminal(dispatch):
            continue
        allowed = [str(item) for item in dispatch.get("allowed_write_paths") or [] if isinstance(item, str)]
        for changed in changes:
            key = (changed, dispatch_id)
            if path_matches(changed, allowed) and key not in seen:
                seen.add(key)
                conflicts.append({"path": changed, "dispatch_id": dispatch_id, "dispatch_path": project_rel(path)})
    return conflicts


def active_lock_conflicts(ip_dir: Path, changes: list[str]) -> list[dict[str, str]]:
    conflicts: list[dict[str, str]] = []
    runs_dir = oag_paths.legacy_or_hidden(ip_dir, "ontology/runs")
    for locks_path in sorted(runs_dir.glob("*/ownership_locks.json")):
        try:
            payload = load_json(locks_path)
        except Exception:
            continue
        if not isinstance(payload, dict):
            continue
        for lock in payload.get("locks", []):
            if not isinstance(lock, dict):
                continue
            lock_path = str(lock.get("path") or "").strip()
            if not lock_path:
                continue
            for changed in changes:
                if path_matches(ip_relative(changed, ip_dir), [lock_path]):
                    conflicts.append(
                        {
                            "path": changed,
                            "task_id": str(lock.get("task_id") or ""),
                            "dispatch_id": str(lock.get("dispatch_id") or ""),
                            "lock_path": project_rel(locks_path),
                        }
                    )
    return conflicts


def check_ip(ip_dir: Path) -> dict[str, Any]:
    ip_dir = ip_dir.expanduser().resolve()
    issues: list[dict[str, str]] = []
    if not ip_dir.exists():
        issues.append(issue("IP_DIR_MISSING", "IP directory does not exist.", str(ip_dir)))
        return build_result(ip_dir, locked=False, changes=[], receipts=[], waiver=None, issues=issues)

    locked = scope_locked(ip_dir)
    changes, git_issues = implementation_changes(ip_dir)
    issues.extend(git_issues)
    if not locked or not changes:
        return build_result(ip_dir, locked=locked, changes=changes, receipts=[], waiver=None, issues=issues)

    waiver = human_waiver(ip_dir)
    if waiver:
        return build_result(ip_dir, locked=locked, changes=changes, receipts=[], waiver=waiver, issues=issues)

    covered, receipts, completed_dispatch_ids, receipt_issues = receipt_covered_paths(ip_dir)
    issues.extend(receipt_issues)
    diagnostics = diagnostic_receipts(ip_dir)
    for conflict in active_dispatch_conflicts(ip_dir, changes, completed_dispatch_ids):
        issues.append(
            issue(
                "PARENT_WRITE_WITH_ACTIVE_DISPATCH",
                "Locked implementation/verification artifact changed while an unfinished OAG dispatch owns the same path; wait for the executor receipt or close it as INCONCLUSIVE/BLOCKED.",
                conflict["path"],
            )
        )
    for conflict in active_lock_conflicts(ip_dir, changes):
        issues.append(
            issue(
                "PARENT_WRITE_WITH_ACTIVE_CHILD_DISPATCH",
                "Locked implementation/verification artifact changed while a wavefront ownership lock is active for the same path.",
                conflict["path"],
            )
        )
    uncovered = []
    for path in changes:
        if path in covered:
            continue
        rel = ip_relative(path, ip_dir)
        if any(path_matches(rel, [ip_relative(candidate, ip_dir)]) for candidate in covered):
            continue
        uncovered.append(path)
    for path in uncovered:
        issues.append(
            issue(
                "MAIN_AGENT_WRITE_WITHOUT_SUBAGENT",
                "Locked implementation/verification artifact changed without a covering dispatched executor receipt.",
                path,
            )
        )
    if uncovered and diagnostics:
        for receipt in diagnostics:
            issues.append(
                issue(
                    "DIAGNOSTIC_RECEIPT_NOT_WRITE_COVERAGE",
                    "Diagnostic subagent receipts are non-evidence reports and cannot cover locked implementation or verification writes.",
                    receipt["path"],
                )
            )
    return build_result(
        ip_dir,
        locked=locked,
        changes=changes,
        receipts=receipts,
        diagnostic_receipts=diagnostics,
        waiver=waiver,
        issues=issues,
    )


def build_result(
    ip_dir: Path,
    *,
    locked: bool,
    changes: list[str],
    receipts: list[dict[str, Any]],
    waiver: dict[str, Any] | None,
    issues: list[dict[str, str]],
    diagnostic_receipts: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "schema_version": "oag_main_write_gate.v1",
        "product_name": "IP Dev Agent",
        "internal_gateway": "Ontology Agent Gateway",
        "status": "fail" if issues else "pass",
        "ip": ip_dir.name,
        "ip_dir": project_rel(ip_dir),
        "scope_locked": locked,
        "implementation_changes": changes,
        "executor_receipts": receipts,
        "subagent_receipts": receipts,
        "diagnostic_receipts": diagnostic_receipts or [],
        "waiver": waiver,
        "issues": issues,
    }


def aggregate(results: list[dict[str, Any]]) -> dict[str, Any]:
    issues = [item for result in results for item in result.get("issues", [])]
    return {
        "schema_version": "oag_main_write_gate_report.v1",
        "status": "fail" if issues else "pass",
        "results": results,
        "issues": issues,
    }


def print_result(result: dict[str, Any], as_json: bool) -> None:
    if as_json:
        print(json.dumps(result, indent=2, sort_keys=True))
    elif result["status"] == "pass":
        print("PASS oag main write gate")
    else:
        print("FAIL oag main write gate", file=sys.stderr)
        for item in result.get("issues", []):
            suffix = f" ({item['path']})" if item.get("path") else ""
            print(f"- {item['code']}: {item['message']}{suffix}", file=sys.stderr)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Require dispatched OAG executor receipts for locked implementation writes.")
    parser.add_argument("--ip-dir", action="append", required=True)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    result = aggregate([check_ip(resolve_project_path(raw)) for raw in args.ip_dir])
    print_result(result, args.json)
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
