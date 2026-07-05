#!/usr/bin/env python3
# noqa: SIZE_OK - OAG bench CLI centralizes run/status/sweep adapter paths.

from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Final, NamedTuple


SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

oag_paths = importlib.import_module("oag_paths")
run_common = importlib.import_module("oag_run_control_common")
contextual_schema_issues = importlib.import_module("oag_validate_json").contextual_schema_issues
oag_parameter_sweep = importlib.import_module("oag_parameter_sweep")


SCHEMA_VERSION: Final = "oag_arch_bench_result.v1"
RESULT_FILE: Final = "bench_result.json"
SWEEP_SCHEMA: Final = "oag_parameter_sweep.v1"
EVIDENCE_TIER: Final = "tier2_probe"
VALID_FOR: Final = ["exploration_comparison"]
NOT_VALID_FOR: Final = [
    "scope_lock",
    "product_rtl_claim",
    "timing_claim",
    "area_claim",
    "performance_claim",
    "external_contract_claim",
    "product_defining_claim",
]
ID_RE: Final = re.compile(r"^[A-Za-z0-9_:-]+$")
DEFAULT_BENCH_TIMEOUT_SEC: Final = 30.0
JsonObject = dict[str, Any]


class BenchTarget(NamedTuple):
    ip_dir: Path
    run_id: str
    candidate_id: str


def issue(code: str, message: str, path: str = "") -> dict[str, str]:
    payload = {"code": code, "message": message}
    if path:
        payload["path"] = path
    return payload


def clean_id(kind: str, value: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{kind} is required")
    path = Path(text)
    if path.is_absolute() or len(path.parts) != 1 or path.parts[0] in {".", ".."}:
        raise ValueError(f"{kind} must be a single path segment: {value}")
    if not ID_RE.fullmatch(text):
        raise ValueError(f"{kind} contains unsupported characters: {value}")
    return text


def target_from_args(ip_dir: str, run_id: str, candidate_id: str) -> BenchTarget:
    return BenchTarget(
        ip_dir=oag_paths.ip_root(ip_dir),
        run_id=clean_id("run-id", run_id),
        candidate_id=clean_id("candidate", candidate_id),
    )


def candidate_dir(target: BenchTarget) -> Path:
    root = oag_paths.state_path(
        target.ip_dir,
        Path("knowledge") / "arch_exploration" / target.run_id / target.candidate_id,
    ).resolve(strict=False)
    base = oag_paths.state_path(
        target.ip_dir,
        Path("knowledge") / "arch_exploration" / target.run_id,
    ).resolve(strict=False)
    try:
        root.relative_to(base)
    except ValueError as exc:
        raise ValueError("candidate bench path escapes knowledge/arch_exploration") from exc
    return root


def result_path(target: BenchTarget) -> Path:
    return candidate_dir(target) / RESULT_FILE


def sweep_path(target: BenchTarget, parameter: str) -> Path:
    safe_name = re.sub(r"[^A-Za-z0-9_.:-]+", "_", parameter).strip("._:-") or "parameter"
    return candidate_dir(target) / f"parameter_sweep_{safe_name}.json"


def rel_to_ip(ip_dir: Path, path: Path) -> str:
    return run_common.rel_to_ip(ip_dir, path)


def read_structured(path: Path) -> JsonObject:
    if not path.is_file():
        return {}
    raw = path.read_text(encoding="utf-8")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        try:
            import yaml  # type: ignore
        except ImportError:
            return {}
        try:
            data = yaml.safe_load(raw) or {}
        except yaml.YAMLError:
            return {}
    return data if isinstance(data, dict) else {}


def bench_timeout_sec(ip_dir: Path) -> float:
    charter = read_structured(oag_paths.legacy_or_hidden(ip_dir, "ontology/mission_charter.yaml"))
    budgets_raw = charter.get("budgets")
    budgets = budgets_raw if isinstance(budgets_raw, dict) else {}
    value = budgets.get("max_bench_wall_clock_sec")
    if isinstance(value, (int, float)) and not isinstance(value, bool) and value > 0:
        return float(value)
    return DEFAULT_BENCH_TIMEOUT_SEC


def verilog_ident(value: str, fallback: str) -> str:
    ident = re.sub(r"[^A-Za-z0-9_$]", "_", value)
    if not ident or not (ident[0].isalpha() or ident[0] == "_"):
        ident = f"{fallback}_{ident}"
    return ident


def candidate_payload(target: BenchTarget) -> JsonObject:
    path = oag_paths.state_path(target.ip_dir, Path("knowledge") / "arch_exploration" / target.run_id) / "candidates.json"
    doc = run_common.read_json_object(path)
    candidates = doc.get("candidates") if isinstance(doc.get("candidates"), list) else []
    for candidate in candidates:
        if isinstance(candidate, dict) and str(candidate.get("id") or "").strip() == target.candidate_id:
            return candidate
    return {}


def numeric_localparam(name: str, value: Any) -> str | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return f"  localparam integer {verilog_ident(name.upper(), 'P')} = {value};"
    if isinstance(value, float):
        return f"  localparam real {verilog_ident(name.upper(), 'P')} = {value:g};"
    return None


def write_probe_rtl(root: Path, target: BenchTarget) -> Path:
    candidate = candidate_payload(target)
    path = root / "generated" / f"{target.candidate_id}_skeleton.v"
    path.parent.mkdir(parents=True, exist_ok=True)
    module_name = verilog_ident(f"oag_arch_bench_{target.run_id}_{target.candidate_id}", "oag_arch_bench")
    raw_parameters = candidate.get("parameter_draft")
    parameters = raw_parameters if isinstance(raw_parameters, dict) else {}
    raw_assignments = candidate.get("decision_assignments")
    assignments = raw_assignments if isinstance(raw_assignments, dict) else {}
    parameter_lines = []
    for name, value in sorted(parameters.items()):
        line = numeric_localparam(str(name), value)
        if line is not None:
            parameter_lines.append(line)
    assignment_lines = [f"  // decision {key}: {value}" for key, value in sorted(assignments.items())]
    path.write_text(
        "\n".join(
            [
                f"module {module_name}(input wire clk, input wire rst_n, output reg seen);",
                *assignment_lines,
                *parameter_lines,
                "  always @(posedge clk or negedge rst_n) begin",
                "    if (!rst_n) seen <= 1'b0;",
                "    else seen <= 1'b1;",
                "  end",
                "endmodule",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return path


def probe_tool(name: str, argv: list[str], cwd: Path, timeout_sec: float) -> JsonObject:
    executable = shutil.which(name)
    if executable is None:
        return {
            "tool": name,
            "available": False,
            "status": "missing",
            "argv": argv,
            "returncode": None,
            "stdout_tail": "",
            "stderr_tail": "",
        }
    try:
        proc = subprocess.run([executable, *argv[1:]], cwd=str(cwd), text=True, capture_output=True, check=False, timeout=timeout_sec)
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout if isinstance(exc.stdout, str) else ""
        stderr = exc.stderr if isinstance(exc.stderr, str) else ""
        return {
            "tool": name,
            "available": True,
            "status": "timeout",
            "argv": [executable, *argv[1:]],
            "returncode": 124,
            "stdout_tail": stdout[-2000:],
            "stderr_tail": (stderr or f"{name} timed out after {timeout_sec:g}s")[-2000:],
        }
    return {
        "tool": name,
        "available": True,
        "status": "pass" if proc.returncode == 0 else "fail",
        "argv": [executable, *argv[1:]],
        "returncode": proc.returncode,
        "stdout_tail": proc.stdout[-2000:],
        "stderr_tail": proc.stderr[-2000:],
    }


def bench_status(probes: list[JsonObject], schema_issues: list[dict[str, str]]) -> str:
    if schema_issues:
        return "fail"
    if not any(probe.get("available") is True for probe in probes):
        return "bench_unavailable"
    if any(probe.get("status") == "timeout" for probe in probes):
        return "fail"
    if any(probe.get("status") == "fail" for probe in probes):
        return "fail"
    if any(probe.get("status") == "missing" for probe in probes):
        return "pass_with_warnings"
    return "pass"


def run_bench(target: BenchTarget) -> JsonObject:
    root = candidate_dir(target)
    root.mkdir(parents=True, exist_ok=True)
    probe_rtl = write_probe_rtl(root, target)
    rel_probe = rel_to_ip(target.ip_dir, probe_rtl)
    local_probe = rel_to_ip(root, probe_rtl)
    timeout_sec = bench_timeout_sec(target.ip_dir)
    yosys = probe_tool("yosys", ["yosys", "-q", "-p", f"read_verilog {local_probe}; proc; stat"], root, timeout_sec)
    verilator = probe_tool("verilator", ["verilator", "--lint-only", local_probe], root, timeout_sec)
    probes = [yosys, verilator]
    available_adapter_count = sum(1 for probe in probes if probe.get("available") is True)
    issues = [
        issue("BENCH_ADAPTER_MISSING", f"{probe['tool']} is not available on PATH")
        for probe in probes
        if probe.get("status") == "missing"
    ]
    issues.extend(
        issue("BENCH_ADAPTER_FAILED", f"{probe['tool']} probe failed", rel_probe)
        for probe in probes
        if probe.get("status") == "fail"
    )
    issues.extend(
        issue("BENCH_ADAPTER_TIMEOUT", f"{probe['tool']} probe timed out after {timeout_sec:g}s", rel_probe)
        for probe in probes
        if probe.get("status") == "timeout"
    )
    result_ref = f"knowledge/arch_exploration/{target.run_id}/{target.candidate_id}/{RESULT_FILE}"
    payload: JsonObject = {
        "schema_version": SCHEMA_VERSION,
        "status": "pass",
        "ip": target.ip_dir.name,
        "run_id": target.run_id,
        "candidate_id": target.candidate_id,
        "candidate_ref": f"knowledge/arch_exploration/{target.run_id}/{target.candidate_id}",
        "result_ref": result_ref,
        "evidence_tier": EVIDENCE_TIER,
        "valid_for": VALID_FOR,
        "not_valid_for": NOT_VALID_FOR,
        "measurement_kind": "adapter_probe" if available_adapter_count else "adapter_unavailable",
        "adapter_status": {
            "yosys": yosys["status"],
            "verilator": verilator["status"],
        },
        "probes": {
            "yosys": yosys,
            "verilator": verilator,
        },
        "metrics": {
            "available_adapter_count": available_adapter_count,
            "generated_artifact_count": 1,
            "probe_rtl_bytes": probe_rtl.stat().st_size,
            "timeout_sec": timeout_sec,
        },
        "generated_artifacts": [rel_probe],
        "issues": issues,
    }
    schema_issues = contextual_schema_issues(
        "oag_arch_bench_result.schema.json",
        payload,
        code_prefix="ARCH_BENCH_SCHEMA",
        document_path=result_ref,
    )
    payload["issues"] = [*issues, *schema_issues]
    payload["status"] = bench_status(probes, schema_issues)
    run_common.write_json(result_path(target), payload)
    return payload


def parse_metric_point(value: str) -> JsonObject:
    raw = str(value or "").strip()
    metric_raw, _, provenance = raw.partition("@")
    separator = "=" if "=" in metric_raw else ":"
    left, sep, right = metric_raw.partition(separator)
    if not sep:
        raise ValueError(f"metric point must use value=metric: {value}")
    point: JsonObject = {"value": float(left.strip()), "metric_value": float(right.strip())}
    if provenance:
        ref, _, digest = provenance.partition("#")
        point["evidence_ref"] = ref.strip()
        point["content_hash"] = digest.strip()
    return point


def verify_metric_point_provenance(target: BenchTarget, point: JsonObject, index: int) -> list[dict[str, str]]:
    ref = str(point.get("evidence_ref") or "").strip()
    if not ref:
        refs = point.get("evidence_refs") if isinstance(point.get("evidence_refs"), list) else []
        ref = str(refs[0] if refs else "").strip()
    digest = str(point.get("content_hash") or "").strip()
    path = f"$.metric_curve[{index}]"
    if not ref or not digest:
        return [issue("SWEEP_POINT_PROVENANCE_MISSING", "sweep metric point requires @artifact#sha256:<hash> provenance", path)]
    if not digest.startswith("sha256:"):
        return [issue("SWEEP_POINT_HASH_INVALID", "sweep metric point content hash must use sha256:<hex>", path)]
    artifact = oag_paths.legacy_or_hidden(target.ip_dir, ref)
    if not artifact.is_file():
        return [issue("SWEEP_POINT_ARTIFACT_MISSING", f"sweep metric point artifact is missing: {ref}", path)]
    actual = hashlib.sha256(artifact.read_bytes()).hexdigest()
    expected = digest.removeprefix("sha256:")
    if actual != expected:
        return [issue("SWEEP_POINT_HASH_MISMATCH", f"sweep metric point hash mismatch for {ref}", path)]
    return []


def verify_sweep_input_provenance(target: BenchTarget, payload: JsonObject) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    raw_curve = payload.get("metric_curve")
    curve = raw_curve if isinstance(raw_curve, list) else []
    for index, row in enumerate(curve):
        if isinstance(row, dict):
            issues.extend(verify_metric_point_provenance(target, row, index))
    if not curve:
        issues.append(issue("SWEEP_POINT_PROVENANCE_MISSING", "sweep input requires metric_curve with artifact provenance", "$.metric_curve"))
    return issues


def sweep_input_from_args(args: argparse.Namespace, target: BenchTarget) -> JsonObject:
    if args.input:
        payload = read_structured(Path(args.input).expanduser())
        if not payload:
            raise ValueError(f"sweep input is empty or invalid: {args.input}")
        payload["provenance_issues"] = [
            *[item for item in payload.get("provenance_issues", []) if isinstance(item, dict)],
            *verify_sweep_input_provenance(target, payload),
        ]
        return payload
    if not args.parameter or not args.metric or args.target is None:
        raise ValueError("sweep requires --parameter, --metric, and --target when --input is not provided")
    points = []
    provenance_issues: list[dict[str, str]] = []
    for index, raw in enumerate(args.metric_point):
        point = parse_metric_point(raw)
        provenance_issues.extend(verify_metric_point_provenance(target, point, index))
        row: JsonObject = {"value": point["value"], "metrics": {args.metric: point["metric_value"]}}
        if point.get("evidence_ref"):
            row["evidence_refs"] = [point["evidence_ref"]]
        if point.get("content_hash"):
            row["content_hash"] = point["content_hash"]
        points.append(row)
    values = [float(item) for item in args.candidate_value] or [float(point["value"]) for point in points]
    result_ref = f"knowledge/arch_exploration/{target.run_id}/{target.candidate_id}/{RESULT_FILE}"
    evidence_refs = [result_ref] if result_path(target).is_file() else []
    return {
        "parameter": args.parameter,
        "constraint": {
            "metric": args.metric,
            "objective": args.objective,
            "target": float(args.target),
            "margin": float(args.margin),
        },
        "candidate_values": values,
        "metric_curve": points,
        "evidence_refs": evidence_refs,
        "provenance_issues": provenance_issues,
    }


def run_sweep(args: argparse.Namespace, target: BenchTarget) -> JsonObject:
    sweep_input = sweep_input_from_args(args, target)
    artifact = oag_parameter_sweep.select(sweep_input)
    provenance_issues = [item for item in sweep_input.get("provenance_issues", []) if isinstance(item, dict)]
    if provenance_issues:
        artifact["issues"] = [*provenance_issues, *[item for item in artifact.get("issues", []) if isinstance(item, dict)]]
        artifact["status"] = "fail"
    artifact["evidence_tier"] = EVIDENCE_TIER
    artifact["valid_for"] = VALID_FOR
    artifact["not_valid_for"] = NOT_VALID_FOR
    artifact["measurement_kind"] = "parameter_sweep"
    parameter = str(artifact.get("parameter") or sweep_input.get("parameter") or "parameter")
    out_path = sweep_path(target, parameter)
    run_common.write_json(out_path, artifact)
    return {
        "schema_version": "oag_arch_bench_sweep_command.v1",
        "status": artifact.get("status"),
        "action": "sweep",
        "ip": target.ip_dir.name,
        "run_id": target.run_id,
        "candidate_id": target.candidate_id,
        "output_path": rel_to_ip(target.ip_dir, out_path),
        "artifact": artifact,
        "artifact_schema": SWEEP_SCHEMA,
        "issues": artifact.get("issues", []),
    }


def load_status(target: BenchTarget) -> JsonObject:
    path = result_path(target)
    payload = run_common.read_json_object(path)
    if not payload:
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "fail",
            "ip": target.ip_dir.name,
            "run_id": target.run_id,
            "candidate_id": target.candidate_id,
            "candidate_ref": f"knowledge/arch_exploration/{target.run_id}/{target.candidate_id}",
            "result_ref": f"knowledge/arch_exploration/{target.run_id}/{target.candidate_id}/{RESULT_FILE}",
            "evidence_tier": EVIDENCE_TIER,
            "valid_for": VALID_FOR,
            "not_valid_for": NOT_VALID_FOR,
            "measurement_kind": "missing",
            "adapter_status": {},
            "probes": {},
            "metrics": {},
            "generated_artifacts": [],
            "issues": [issue("BENCH_RESULT_MISSING", "bench_result.json is missing", rel_to_ip(target.ip_dir, path))],
        }
    return payload


def command_result(action: str, target: BenchTarget, payload: JsonObject) -> JsonObject:
    return {
        "schema_version": "oag_arch_bench_command.v1",
        "status": payload.get("status"),
        "action": action,
        "ip": target.ip_dir.name,
        "run_id": target.run_id,
        "candidate_id": target.candidate_id,
        "output_path": rel_to_ip(target.ip_dir, result_path(target)),
        "artifact": payload,
        "issues": payload.get("issues", []),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run/status OAG Tier-2 architecture bench probes.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    for name in ("run", "status", "sweep"):
        sub = subparsers.add_parser(name)
        sub.add_argument("--ip-dir", required=True)
        sub.add_argument("--run-id", required=True)
        sub.add_argument("--candidate", required=True)
        sub.add_argument("--json", action="store_true")
        if name == "sweep":
            sub.add_argument("--input", default="")
            sub.add_argument("--parameter", default="")
            sub.add_argument("--metric", default="")
            sub.add_argument("--objective", choices=("min", "max"), default="min")
            sub.add_argument("--target", type=float)
            sub.add_argument("--margin", type=float, default=0.0)
            sub.add_argument("--candidate-value", action="append", default=[])
            sub.add_argument("--metric-point", action="append", default=[])
    args = parser.parse_args(argv)

    result: JsonObject
    try:
        target = target_from_args(args.ip_dir, args.run_id, args.candidate)
        if args.command == "sweep":
            result = run_sweep(args, target)
        else:
            payload = run_bench(target) if args.command == "run" else load_status(target)
            result = command_result(args.command, target, payload)
    except ValueError as exc:
        result = {
            "schema_version": "oag_arch_bench_command.v1",
            "status": "fail",
            "action": str(getattr(args, "command", "")),
            "issues": [issue("BENCH_PATH_INVALID", str(exc))],
        }

    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    elif result["status"] in {"pass", "pass_with_warnings", "bench_unavailable"}:
        print(f"{str(result['status']).upper()} oag arch bench {result.get('action', '')}")
        print(f"Result: {result.get('output_path', '')}")
    else:
        print(f"FAIL oag arch bench {result.get('action', '')}", file=sys.stderr)
        for item in result.get("issues", []):
            if isinstance(item, dict):
                print(f"- {item.get('code')}: {item.get('message')}", file=sys.stderr)
    return 1 if result["status"] == "fail" else 0


if __name__ == "__main__":
    raise SystemExit(main())
