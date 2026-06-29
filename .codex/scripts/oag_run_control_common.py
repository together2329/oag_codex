#!/usr/bin/env python3
"""Shared read-only helpers for OAG run-control scripts."""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import subprocess
import time
from pathlib import Path
from typing import Any

import oag_ip_git
import oag_paths
import oag_stale_check


JsonObject = dict[str, Any]


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_utc(value: Any) -> dt.datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        parsed = dt.datetime.fromisoformat(text)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=dt.timezone.utc)
        return parsed.astimezone(dt.timezone.utc)
    except ValueError:
        return None


def age_seconds(value: Any, *, now: dt.datetime | None = None) -> float | None:
    parsed = parse_utc(value)
    if parsed is None:
        return None
    current = now or dt.datetime.now(dt.timezone.utc)
    return max(0.0, (current - parsed).total_seconds())


def issue(code: str, message: str, path: str = "") -> dict[str, str]:
    payload = {"code": code, "message": message}
    if path:
        payload["path"] = path
    return payload


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def rel_to_ip(ip_dir: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(ip_dir.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def read_json_object(path: Path) -> JsonObject:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(path)


def file_info(ip_dir: Path, rel: str) -> JsonObject:
    path = oag_paths.legacy_or_hidden(ip_dir, rel)
    if not path.is_file():
        return {
            "path": rel,
            "exists": False,
            "sha256": "",
            "bytes": 0,
            "mtime": "",
        }
    stat = path.stat()
    return {
        "path": rel_to_ip(ip_dir, path),
        "exists": True,
        "sha256": sha256_file(path),
        "bytes": stat.st_size,
        "mtime": dt.datetime.fromtimestamp(stat.st_mtime, dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
    }


def state_dirs(ip_dir: Path, rel: str) -> list[Path]:
    clean = Path(rel)
    candidates = [ip_dir / ".oag" / clean, ip_dir / clean]
    seen: set[Path] = set()
    dirs: list[Path] = []
    for candidate in candidates:
        resolved = candidate.resolve()
        if resolved not in seen and resolved.is_dir():
            seen.add(resolved)
            dirs.append(resolved)
    if dirs:
        return dirs
    fallback = oag_paths.legacy_or_hidden(ip_dir, rel)
    return [fallback] if fallback.is_dir() else []


def collect_git_status(ip_dir: Path) -> JsonObject:
    git = oag_ip_git.git_executable()
    if git is None:
        return {"available": False, "repo": False, "clean": False, "head": "", "porcelain": "", "issues": [issue("GIT_NOT_AVAILABLE", "git executable is not available")]}
    repo = (ip_dir / ".git").exists()
    if not repo:
        return {"available": True, "repo": False, "clean": False, "head": "", "porcelain": "", "issues": [issue("IP_GIT_MISSING", "IP-local .git repository is missing", str(ip_dir))]}
    status = subprocess.run([git, "-C", str(ip_dir), "status", "--porcelain"], text=True, capture_output=True, check=False)
    head = subprocess.run([git, "-C", str(ip_dir), "rev-parse", "--verify", "HEAD"], text=True, capture_output=True, check=False)
    issues: list[dict[str, str]] = []
    if status.returncode != 0:
        issues.append(issue("GIT_STATUS_FAILED", status.stderr.strip() or status.stdout.strip(), str(ip_dir)))
    return {
        "available": True,
        "repo": True,
        "clean": status.returncode == 0 and not status.stdout.strip(),
        "head": head.stdout.strip() if head.returncode == 0 else "",
        "porcelain": status.stdout,
        "issues": issues,
    }


def collect_scope_lock(ip_dir: Path) -> JsonObject:
    info = file_info(ip_dir, "ontology/scope_lock.json")
    payload = read_json_object(oag_paths.legacy_or_hidden(ip_dir, "ontology/scope_lock.json")) if info["exists"] else {}
    return {
        **info,
        "state": str(payload.get("state") or "missing"),
        "locked_at": payload.get("locked_at") or payload.get("updated_at") or "",
        "summary": payload.get("summary") or "",
    }


def collect_compile_manifest(ip_dir: Path) -> JsonObject:
    path = oag_paths.legacy_or_hidden(ip_dir, "ontology/generated/compile_manifest.json")
    if not path.is_file():
        return {
            "status": "missing",
            "path": rel_to_ip(ip_dir, path),
            "compiled_at": "",
            "stale_inputs": [],
            "issues": [issue("COMPILE_MANIFEST_MISSING", "ontology/generated/compile_manifest.json is missing", rel_to_ip(ip_dir, path))],
        }
    payload = read_json_object(path)
    stale_inputs: list[JsonObject] = []
    for item in payload.get("input_fingerprints", []) if isinstance(payload.get("input_fingerprints"), list) else []:
        if not isinstance(item, dict):
            continue
        rel = str(item.get("path") or "").strip()
        expected = str(item.get("sha256") or "").strip()
        if not rel or not expected:
            continue
        current_path = oag_paths.legacy_or_hidden(ip_dir, rel)
        if not current_path.is_file():
            stale_inputs.append({"path": rel, "reason": "missing", "expected_sha256": expected, "actual_sha256": ""})
            continue
        actual = sha256_file(current_path)
        if actual != expected:
            stale_inputs.append({"path": rel, "reason": "hash_mismatch", "expected_sha256": expected, "actual_sha256": actual})
    issues = [issue("COMPILE_MANIFEST_STALE", "compile manifest input fingerprint is stale", str(item["path"])) for item in stale_inputs]
    return {
        "status": "stale" if stale_inputs else "pass",
        "path": rel_to_ip(ip_dir, path),
        "compiled_at": payload.get("compiled_at") or "",
        "stale_inputs": stale_inputs,
        "issues": issues,
    }


def collect_stale_lifecycle(ip_dir: Path) -> JsonObject:
    try:
        return oag_stale_check.check(ip_dir, require=False)
    except Exception as exc:
        return {
            "schema_version": "oag_stale_check.v1",
            "status": "fail",
            "issues": [issue("STALE_CHECK_FAILED", str(exc))],
            "changed_artifacts": [],
            "stale_artifacts": [],
        }


def collect_wavefront_runs(ip_dir: Path) -> JsonObject:
    runs: list[JsonObject] = []
    total_active: list[JsonObject] = []
    for runs_dir in state_dirs(ip_dir, "ontology/runs"):
        for run_dir in sorted(path for path in runs_dir.iterdir() if path.is_dir()):
            graph_path = run_dir / "wavefront_task_graph.json"
            locks_path = run_dir / "ownership_locks.json"
            barriers_path = run_dir / "barriers.json"
            graph = read_json_object(graph_path) if graph_path.is_file() else {}
            locks = read_json_object(locks_path) if locks_path.is_file() else {"locks": []}
            tasks = [task for task in graph.get("tasks", []) if isinstance(task, dict)] if isinstance(graph.get("tasks"), list) else []
            active_locks = [lock for lock in locks.get("locks", []) if isinstance(lock, dict)] if isinstance(locks.get("locks"), list) else []
            for lock in active_locks:
                enriched = dict(lock)
                enriched["run_id"] = run_dir.name
                enriched["age_seconds"] = age_seconds(lock.get("claimed_at"))
                total_active.append(enriched)
            counts: dict[str, int] = {}
            for task in tasks:
                status = str(task.get("status") or "unknown")
                counts[status] = counts.get(status, 0) + 1
            runs.append(
                {
                    "run_id": run_dir.name,
                    "graph_path": rel_to_ip(ip_dir, graph_path),
                    "locks_path": rel_to_ip(ip_dir, locks_path),
                    "barriers_path": rel_to_ip(ip_dir, barriers_path),
                    "task_counts": counts,
                    "active_locks": active_locks,
                    "closed_at": graph.get("closed_at") or "",
                }
            )
    return {"runs": runs, "active_locks": total_active, "active_lock_count": len(total_active)}


def collect_gate_state(ip_dir: Path) -> JsonObject:
    pending: list[JsonObject] = []
    resolved: list[JsonObject] = []
    for gates_dir in state_dirs(ip_dir, "knowledge/gates"):
        for path in sorted(gates_dir.glob("*.json")):
            if path.name.endswith(".answer.json"):
                continue
            payload = read_json_object(path)
            if not payload:
                continue
            row = {
                "gate_id": payload.get("gate_id") or path.stem,
                "path": rel_to_ip(ip_dir, path),
                "stage": payload.get("stage") or "",
                "kind": payload.get("kind") or "",
                "created_at": payload.get("created_at") or "",
                "required": payload.get("required", True),
            }
            resolution = payload.get("resolution") if isinstance(payload.get("resolution"), dict) else {}
            if resolution.get("status") == "accepted":
                row["resolved_at"] = resolution.get("resolved_at") or ""
                resolved.append(row)
            elif row["required"]:
                pending.append(row)
    gate_decision_path = oag_paths.legacy_or_hidden(ip_dir, "knowledge/gate_reviews/oag_gate_decision.json")
    validation_path = oag_paths.legacy_or_hidden(ip_dir, "knowledge/validations/oag_validation_report.json")
    gate_info = file_info(ip_dir, "knowledge/gate_reviews/oag_gate_decision.json")
    validation_info = file_info(ip_dir, "knowledge/validations/oag_validation_report.json")
    stale_decision = False
    if gate_decision_path.is_file() and validation_path.is_file():
        stale_decision = validation_path.stat().st_mtime > gate_decision_path.stat().st_mtime
    return {
        "pending_gates": pending,
        "resolved_gates": resolved,
        "pending_gate_count": len(pending),
        "gate_decision": gate_info,
        "validation_report": validation_info,
        "gate_decision_stale": stale_decision,
    }


def collect_ssot_quick(ip_dir: Path) -> JsonObject:
    required = [
        "req/source_claims.yaml",
        "req/ambiguity_register.yaml",
        "ontology/features.yaml",
        "ontology/decision_matrix.yaml",
        "ontology/requirement_atoms.yaml",
        "ontology/requirements.yaml",
        "ontology/obligations.yaml",
        "ontology/contracts.yaml",
        "ontology/verification_plan.yaml",
        "ontology/tb_methodology.yaml",
        "ontology/ipxact_projection.yaml",
    ]
    rows = [file_info(ip_dir, rel) for rel in required]
    missing = [row["path"] for row in rows if not row["exists"]]
    empty = [row["path"] for row in rows if row["exists"] and row["bytes"] == 0]
    return {"status": "pass" if not missing and not empty else "fail", "missing": missing, "empty": empty, "rows": rows}


def collect_run_state(ip_dir: Path) -> JsonObject:
    ip_dir = oag_paths.ip_root(ip_dir)
    scope_lock = collect_scope_lock(ip_dir)
    compile_manifest = collect_compile_manifest(ip_dir)
    stale = collect_stale_lifecycle(ip_dir)
    wavefront = collect_wavefront_runs(ip_dir)
    gates = collect_gate_state(ip_dir)
    ssot = collect_ssot_quick(ip_dir)
    git = collect_git_status(ip_dir)
    return {
        "schema_version": "oag_run_state.v1",
        "generated_at": utc_now(),
        "ip": ip_dir.name,
        "ip_dir": str(ip_dir),
        "git": git,
        "scope_lock": scope_lock,
        "compile_manifest": compile_manifest,
        "stale_lifecycle": stale,
        "wavefront": wavefront,
        "gates": gates,
        "ssot": ssot,
    }
