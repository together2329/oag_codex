#!/usr/bin/env python3
"""Check generated OAG role-specific authoring packets."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

SCRIPTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS_DIR))
import oag_paths  # noqa: E402
import oag_domain_crossing_check  # noqa: E402
from oag_lifecycle_check import check as lifecycle_check  # noqa: E402
from oag_validate_json import contextual_schema_issues  # noqa: E402


PACKET_DIR = Path("ontology/generated/authoring_packets")
RTL_INTERFACE_API_REL = Path("ontology/generated/rtl_interface_api.md")
DUT_DERIVED_TOKENS = {"dut_output", "rtl_expression", "post_hoc_simulation", "observed dut behavior", "observed_dut_output"}
TB_FORBIDDEN_LIFECYCLE_PREFIXES = ("rtl/", "sim/", "waveform", "dut_output")
CURRENT_IP_OWNERSHIPS = {"current_ip", "manifest", "owned"}


def read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception as exc:
        return {"__load_error__": str(exc)}


def read_yaml(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        import yaml  # type: ignore

        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        return data if isinstance(data, dict) else {}
    except Exception as exc:
        return {"__load_error__": str(exc)}


def as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def str_items(value: Any) -> list[str]:
    return [str(item).strip() for item in as_list(value) if str(item).strip()]


def issue(code: str, message: str, path: str = "") -> dict[str, str]:
    payload = {"code": code, "message": message}
    if path:
        payload["path"] = path
    return payload


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def is_locked(ip_dir: Path) -> bool:
    scope = read_json(oag_paths.legacy_or_hidden(ip_dir, "ontology/scope_lock.json"))
    return scope.get("state") == "locked"


def module_id(module: dict[str, Any]) -> str:
    for key in ("id", "name", "module"):
        value = str(module.get(key) or "").strip()
        if value:
            return value
    return ""


def module_edge_touches(edge: dict[str, Any], mid: str) -> bool:
    producer = str(edge.get("producer") or "").strip()
    consumer = str(edge.get("consumer") or "").strip()
    return (
        producer == mid
        or consumer == mid
        or producer in {"all_modules", "all_leaf_modules"}
        or consumer in {"all_modules", "all_leaf_modules"}
    )


def contract_interface_refs(contract: dict[str, Any]) -> list[str]:
    refs = str_items(contract.get("interface_contract_refs"))
    boundary = contract.get("module_boundary") if isinstance(contract.get("module_boundary"), dict) else {}
    refs.extend(str_items(boundary.get("interface_contract_refs")))
    refs.extend(str_items(boundary.get("interface_contract")))
    return sorted(set(refs))


def check_lifecycle_refs(
    ip_dir: Path,
    path: Path,
    data: dict[str, Any],
    *,
    consumer: str,
    require_lifecycle: bool,
) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    rel = str(path)
    if not require_lifecycle:
        return issues
    refs = str_items(data.get("lifecycle_input_refs"))
    if not refs:
        return [issue("PACKET_LIFECYCLE_REFS", "Packet needs lifecycle_input_refs when --require-lifecycle is set.", rel)]
    for ref in refs:
        lowered = ref.lower()
        if consumer == "tb_authoring_packet" and lowered.startswith(TB_FORBIDDEN_LIFECYCLE_PREFIXES):
            issues.append(issue("TB_PACKET_RTL_DERIVED_LIFECYCLE_INPUT", "TB expected-source lifecycle input must not derive from RTL, sim, waveform, or DUT output.", rel))
            continue
        result = lifecycle_check(ip_dir, require=True, artifact_id=ref, consumer=consumer)
        if result.get("status") != "pass":
            codes = ", ".join(str(item.get("code")) for item in result.get("issues", []) if isinstance(item, dict))
            issues.append(issue("PACKET_LIFECYCLE_BLOCKED", f"Lifecycle input {ref} is not eligible for {consumer}: {codes}", rel))
    return issues


def check_rtl_packet(path: Path, data: dict[str, Any], *, ip_dir: Path, hard_gate: bool, require_lifecycle: bool) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    rel = str(path)
    if data.get("__load_error__"):
        return [issue("PACKET_INVALID_JSON", f"Cannot read packet: {data['__load_error__']}", rel)]
    issues.extend(
        contextual_schema_issues(
            "oag_rtl_authoring_packet.schema.json",
            data,
            code_prefix="RTL_PACKET_SCHEMA",
            document_path=rel,
        )
    )
    if data.get("schema_version") != "oag_rtl_authoring_packet.v1":
        issues.append(issue("RTL_PACKET_SCHEMA", "RTL packet must use schema_version oag_rtl_authoring_packet.v1.", rel))
    if data.get("packet_type") != "rtl_authoring_packet":
        issues.append(issue("RTL_PACKET_TYPE", "RTL packet must use packet_type rtl_authoring_packet.", rel))
    if not str_items(data.get("allowed_truth_sources")):
        issues.append(issue("RTL_PACKET_TRUTH_SOURCES", "RTL packet needs allowed_truth_sources.", rel))
    forbidden = {item.lower() for item in str_items(data.get("forbidden_sources"))}
    if hard_gate and not any("tb" in item or "sim" in item or "dut" in item for item in forbidden):
        issues.append(issue("RTL_PACKET_FORBIDDEN_SOURCES", "RTL packet must forbid TB/simulation/DUT-observed truth sources.", rel))
    if hard_gate and not str_items(data.get("contract_refs_to_implement")):
        issues.append(issue("RTL_PACKET_CONTRACT_REFS", "RTL packet needs contract_refs_to_implement.", rel))
    if hard_gate and not (
        str_items(data.get("behavior_refs_implemented_target"))
        or str_items(data.get("cycle_rule_refs_implemented_target"))
        or str_items(data.get("domain_intent_refs"))
    ):
        issues.append(issue("RTL_PACKET_ORACLE_TARGETS", "RTL packet needs behavior/cycle/domain implementation targets.", rel))
    if hard_gate and data.get("ppa_notes_required") is not True:
        issues.append(issue("RTL_PACKET_PPA_NOTES", "RTL packet should require PPA notes.", rel))
    if hard_gate and data.get("cdc_rdc_notes_required") is not True:
        issues.append(issue("RTL_PACKET_CDC_RDC_NOTES", "RTL packet should require CDC/RDC notes.", rel))
    issues.extend(check_lifecycle_refs(ip_dir, path, data, consumer="rtl_authoring_packet", require_lifecycle=require_lifecycle))
    return issues


def check_tb_packet(path: Path, data: dict[str, Any], *, ip_dir: Path, hard_gate: bool, require_lifecycle: bool) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    rel = str(path)
    if data.get("__load_error__"):
        return [issue("PACKET_INVALID_JSON", f"Cannot read packet: {data['__load_error__']}", rel)]
    issues.extend(
        contextual_schema_issues(
            "oag_tb_authoring_packet.schema.json",
            data,
            code_prefix="TB_PACKET_SCHEMA",
            document_path=rel,
        )
    )
    if data.get("schema_version") != "oag_tb_authoring_packet.v1":
        issues.append(issue("TB_PACKET_SCHEMA", "TB packet must use schema_version oag_tb_authoring_packet.v1.", rel))
    if data.get("packet_type") != "tb_authoring_packet":
        issues.append(issue("TB_PACKET_TYPE", "TB packet must use packet_type tb_authoring_packet.", rel))
    if data.get("expected_source_policy") != "contract_oracle_only":
        issues.append(issue("TB_PACKET_EXPECTED_SOURCE_POLICY", "TB packet must require contract_oracle_only expected sources.", rel))
    forbidden = {item.lower() for item in str_items(data.get("forbidden_expected_sources"))}
    if hard_gate and not (forbidden & DUT_DERIVED_TOKENS or any("dut" in item or "rtl" in item for item in forbidden)):
        issues.append(issue("TB_PACKET_FORBIDDEN_EXPECTED", "TB packet must forbid DUT/RTL/post-hoc expected sources.", rel))
    if hard_gate and not str_items(data.get("contract_refs")):
        issues.append(issue("TB_PACKET_CONTRACT_REFS", "TB packet needs contract_refs.", rel))
    if hard_gate and not str_items(data.get("scenario_refs")):
        issues.append(issue("TB_PACKET_SCENARIOS", "TB packet needs scenario_refs.", rel))
    if hard_gate and not str_items(data.get("scoreboard_row_refs")):
        issues.append(issue("TB_PACKET_SCOREBOARD_ROWS", "TB packet needs scoreboard_row_refs.", rel))
    issues.extend(check_lifecycle_refs(ip_dir, path, data, consumer="tb_authoring_packet", require_lifecycle=require_lifecycle))
    return issues


def check_module_packets(ip_dir: Path, packets_dir: Path, *, hard_gate: bool) -> tuple[list[dict[str, str]], dict[str, int]]:
    issues: list[dict[str, str]] = []
    counts = {
        "module_packets": 0,
        "current_ip_modules": 0,
        "module_packet_issues": 0,
    }
    if not hard_gate:
        return issues, counts

    decomp_path = oag_paths.legacy_or_hidden(ip_dir, "ontology/decomposition.yaml")
    decomp = read_yaml(decomp_path)
    if "__load_error__" in decomp:
        issues.append(issue("MODULE_DECOMPOSITION_INVALID", f"Cannot read decomposition.yaml: {decomp['__load_error__']}", str(decomp_path)))
        counts["module_packet_issues"] = len(issues)
        return issues, counts
    modeling_path = oag_paths.legacy_or_hidden(ip_dir, "ontology/modeling.yaml")
    modeling = read_yaml(modeling_path)
    if "__load_error__" in modeling:
        issues.append(issue("MODULE_MODELING_INVALID", f"Cannot read modeling.yaml: {modeling['__load_error__']}", str(modeling_path)))
        counts["module_packet_issues"] = len(issues)
        return issues, counts

    profile = ""
    if isinstance(decomp.get("profile"), dict):
        profile = str(decomp["profile"].get("mode") or "").strip()
    modules = [item for item in as_list(decomp.get("modules")) if isinstance(item, dict)]
    decomposition_edges = [item for item in as_list(decomp.get("interfaces")) if isinstance(item, dict)]
    model_interfaces = [item for item in as_list(modeling.get("module_interface_contracts")) if isinstance(item, dict)]
    model_interface_ids = {str(item.get("id") or "").strip() for item in model_interfaces if str(item.get("id") or "").strip()}
    interface_truth_present = bool(decomposition_edges or model_interfaces)
    current_modules = [
        module for module in modules
        if str(module.get("ownership") or "current_ip").strip() in CURRENT_IP_OWNERSHIPS
        and str(module.get("edit_policy") or "editable").strip() != "do_not_edit"
    ]
    counts["current_ip_modules"] = len(current_modules)
    if not modules:
        issues.append(issue("MODULE_DECOMPOSITION_MISSING", "Hard packet gate requires decomposition modules before RTL dispatch.", str(decomp_path)))
    if modules and not current_modules:
        issues.append(issue("MODULE_CURRENT_IP_MISSING", "Hard packet gate requires at least one editable current-IP module before RTL dispatch.", str(decomp_path)))

    module_packets = sorted(packets_dir.glob("module__*.json")) if packets_dir.is_dir() else []
    counts["module_packets"] = len(module_packets)
    packets_by_module: dict[str, tuple[Path, dict[str, Any]]] = {}
    for path in module_packets:
        payload = read_json(path)
        packet_module = payload.get("module") if isinstance(payload.get("module"), dict) else {}
        mid = module_id(packet_module) if isinstance(packet_module, dict) else ""
        if not mid:
            issues.append(issue("MODULE_PACKET_ID", "Module authoring packet is missing module.id.", str(path)))
            continue
        if mid in packets_by_module:
            issues.append(issue("MODULE_PACKET_DUPLICATE", f"Duplicate module authoring packet for {mid}.", str(path)))
            continue
        packets_by_module[mid] = (path, payload)

    contract_owners: dict[str, list[str]] = {}
    obligation_owners: dict[str, list[str]] = {}
    file_owners: dict[str, list[str]] = {}
    for module in current_modules:
        mid = module_id(module)
        if not mid:
            issues.append(issue("MODULE_ID", "Current-IP decomposition module is missing id/name.", str(decomp_path)))
            continue
        file_rel = str(module.get("file") or "").strip()
        if file_rel:
            file_owners.setdefault(file_rel, []).append(mid)
        for cid in str_items(module.get("owned_contracts") or module.get("contracts")):
            contract_owners.setdefault(cid, []).append(mid)
        for oid in str_items(module.get("owned_obligations") or module.get("obligations")):
            obligation_owners.setdefault(oid, []).append(mid)

        packet_entry = packets_by_module.get(mid)
        if not packet_entry:
            issues.append(issue("MODULE_PACKET_MISSING", f"Missing generated module packet for current-IP module {mid}.", str(packets_dir)))
            continue
        path, payload = packet_entry
        if payload.get("__load_error__"):
            issues.append(issue("MODULE_PACKET_INVALID_JSON", f"Cannot read module packet: {payload['__load_error__']}", str(path)))
            continue
        if payload.get("schema_version") != "oag_authoring_packet.v1":
            issues.append(issue("MODULE_PACKET_SCHEMA", "Module packet must use schema_version oag_authoring_packet.v1.", str(path)))
        packet_module = payload.get("module") if isinstance(payload.get("module"), dict) else {}
        packet_file = str(packet_module.get("file") or "").strip() if isinstance(packet_module, dict) else ""
        if file_rel and packet_file != file_rel:
            issues.append(issue("MODULE_PACKET_FILE_MISMATCH", f"{mid} packet file {packet_file or '<missing>'} does not match decomposition file {file_rel}.", str(path)))

        expected_obligations = set(str_items(module.get("owned_obligations") or module.get("obligations")))
        expected_contracts = set(str_items(module.get("owned_contracts") or module.get("contracts")))
        packet_obligations = {str(item.get("id") or "") for item in as_list(payload.get("obligations")) if isinstance(item, dict)}
        packet_contracts = {str(item.get("id") or "") for item in as_list(payload.get("contracts")) if isinstance(item, dict)}
        if expected_obligations and not expected_obligations <= packet_obligations:
            missing = sorted(expected_obligations - packet_obligations)
            issues.append(issue("MODULE_PACKET_OBLIGATION_MISSING", f"{mid} packet is missing owned obligations: {missing}.", str(path)))
        if expected_contracts and not expected_contracts <= packet_contracts:
            missing = sorted(expected_contracts - packet_contracts)
            issues.append(issue("MODULE_PACKET_CONTRACT_MISSING", f"{mid} packet is missing owned contracts: {missing}.", str(path)))
        if (expected_obligations or expected_contracts) and not str_items(payload.get("source_refs")):
            issues.append(issue("MODULE_PACKET_SOURCE_REFS", f"{mid} packet needs source_refs for owned work.", str(path)))
        if profile == "greenfield_modular" and (expected_obligations or expected_contracts) and not str_items(payload.get("structure_refs")):
            issues.append(issue("MODULE_PACKET_STRUCTURE_REFS", f"{mid} packet needs structure_refs for greenfield modular RTL dispatch.", str(path)))
        if profile == "greenfield_modular" and interface_truth_present and (expected_obligations or expected_contracts):
            packet_interface_refs = set(str_items(payload.get("interface_contract_refs")))
            packet_interfaces = [item for item in as_list(payload.get("interface_contracts")) if isinstance(item, dict)]
            packet_edges = [item for item in as_list(payload.get("edge_interfaces")) if isinstance(item, dict)]
            packet_boundaries = [item for item in as_list(payload.get("module_boundaries")) if isinstance(item, dict)]
            expected_interface_refs: set[str] = set()
            for contract in as_list(payload.get("contracts")):
                if isinstance(contract, dict):
                    expected_interface_refs.update(contract_interface_refs(contract))
            for edge in decomposition_edges:
                if module_edge_touches(edge, mid) and str(edge.get("interface_contract") or "").strip():
                    expected_interface_refs.add(str(edge.get("interface_contract") or "").strip())
            if expected_interface_refs and not packet_interface_refs:
                issues.append(issue("MODULE_PACKET_INTERFACE_CONTRACT_REFS", f"{mid} packet needs interface_contract_refs projected from contracts/modeling.", str(path)))
            missing_interface_refs = sorted(expected_interface_refs - packet_interface_refs)
            if missing_interface_refs:
                issues.append(issue("MODULE_PACKET_INTERFACE_CONTRACT_MISSING", f"{mid} packet missing interface contract refs: {missing_interface_refs}.", str(path)))
            unknown_interface_refs = sorted(ref for ref in packet_interface_refs if model_interface_ids and ref not in model_interface_ids)
            if unknown_interface_refs:
                issues.append(issue("MODULE_PACKET_INTERFACE_CONTRACT_UNKNOWN", f"{mid} packet references interface contracts absent from modeling.yaml: {unknown_interface_refs}.", str(path)))
            if packet_interface_refs and not packet_interfaces:
                issues.append(issue("MODULE_PACKET_INTERFACE_CONTRACT_PAYLOAD", f"{mid} packet needs interface_contracts payloads for interface refs.", str(path)))
            if any(isinstance(item, dict) and item.get("missing") for item in packet_interfaces):
                issues.append(issue("MODULE_PACKET_INTERFACE_CONTRACT_UNRESOLVED", f"{mid} packet has unresolved interface_contracts entries.", str(path)))
            expected_edges = [edge for edge in decomposition_edges if module_edge_touches(edge, mid)]
            if expected_edges and not packet_edges:
                issues.append(issue("MODULE_PACKET_EDGE_INTERFACES", f"{mid} packet needs edge_interfaces projected from decomposition interfaces.", str(path)))
            if expected_interface_refs and not packet_boundaries and not packet_edges:
                issues.append(issue("MODULE_PACKET_INTERFACE_BOUNDARY", f"{mid} packet needs module_boundaries or edge_interfaces for interface-authoring dispatch.", str(path)))

    if profile == "greenfield_modular":
        for file_rel, mids in sorted(file_owners.items()):
            if len(mids) > 1:
                issues.append(issue("MODULE_PACKET_FILE_OWNERSHIP", f"Greenfield module file is shared by multiple current-IP modules: {file_rel} -> {mids}.", str(decomp_path)))

    rtl_packets = sorted(packets_dir.glob("rtl__*.json")) if packets_dir.is_dir() else []
    rtl_contracts: set[str] = set()
    for path in rtl_packets:
        payload = read_json(path)
        rtl_contracts.update(str_items(payload.get("contract_refs_to_implement")))
    for cid in sorted(rtl_contracts):
        if cid not in contract_owners:
            issues.append(issue("RTL_PACKET_UNOWNED_CONTRACT", f"RTL packet contract {cid} has no current-IP module owner.", str(decomp_path)))
    for oid, owners in sorted(obligation_owners.items()):
        if not owners:
            issues.append(issue("MODULE_PACKET_UNOWNED_OBLIGATION", f"Obligation {oid} has no current-IP module owner.", str(decomp_path)))

    counts["module_packet_issues"] = len(issues)
    return issues, counts


def check_domain_readiness(ip_dir: Path, *, hard_gate: bool) -> tuple[list[dict[str, str]], dict[str, int]]:
    if not hard_gate:
        return [], {"domain_issues": 0}
    result = oag_domain_crossing_check.check(ip_dir, [], require_domain_intent=True)
    raw_issues = result.get("issues", []) if isinstance(result, dict) else []
    issues = [
        issue("DOMAIN_CROSSING_READINESS", str(item), str(result.get("domain_intent") or "ontology/domain_intent.yaml"))
        for item in raw_issues
    ]
    return issues, {"domain_issues": len(issues)}


def check_compile_manifest_freshness(ip_dir: Path, *, hard_gate: bool) -> tuple[list[dict[str, str]], dict[str, int]]:
    if not hard_gate:
        return [], {"compile_manifest_issues": 0}
    manifest_path = oag_paths.legacy_or_hidden(ip_dir, "ontology/generated/compile_manifest.json")
    manifest = read_json(manifest_path)
    issues: list[dict[str, str]] = []
    if not manifest:
        return [issue("COMPILE_MANIFEST_MISSING", "Hard packet gate requires ontology/generated/compile_manifest.json from oag.compile.", str(manifest_path))], {"compile_manifest_issues": 1}
    if manifest.get("__load_error__"):
        return [issue("COMPILE_MANIFEST_INVALID", f"Cannot read compile manifest: {manifest['__load_error__']}", str(manifest_path))], {"compile_manifest_issues": 1}
    if manifest.get("schema_version") != "oag_compile_manifest.v1":
        issues.append(issue("COMPILE_MANIFEST_SCHEMA", "compile_manifest.json must use schema_version oag_compile_manifest.v1.", str(manifest_path)))
    if manifest.get("status") != "pass":
        issues.append(issue("COMPILE_MANIFEST_STATUS", "compile_manifest.json status must be pass before RTL/TB dispatch.", str(manifest_path)))
    fingerprints = [item for item in as_list(manifest.get("input_fingerprints")) if isinstance(item, dict)]
    if not fingerprints:
        issues.append(issue("COMPILE_MANIFEST_INPUTS", "compile_manifest.json must include input_fingerprints before RTL/TB dispatch.", str(manifest_path)))
    for item in fingerprints:
        rel = str(item.get("path") or "").strip()
        expected = str(item.get("sha256") or "").strip()
        if not rel or not expected:
            issues.append(issue("COMPILE_MANIFEST_INPUT_FINGERPRINT", "compile manifest input entries need path and sha256.", str(manifest_path)))
            continue
        source_path = oag_paths.legacy_or_hidden(ip_dir, rel)
        if not source_path.is_file():
            issues.append(issue("COMPILE_MANIFEST_INPUT_MISSING", "compile manifest input file is missing; rerun oag.compile after repair.", str(source_path)))
            continue
        actual = sha256(source_path)
        if actual != expected:
            issues.append(issue("COMPILE_MANIFEST_STALE_INPUT", "compile manifest input hash is stale; rerun oag.compile before RTL/TB dispatch.", str(source_path)))
    return issues, {"compile_manifest_issues": len(issues)}


def check(ip_dir: Path, *, require_locked: bool = False, require_packets: bool = False, require_lifecycle: bool = False) -> dict[str, Any]:
    ip_dir = oag_paths.ip_root(ip_dir)
    hard_gate = require_locked or require_packets or is_locked(ip_dir)
    packets_dir = oag_paths.legacy_or_hidden(ip_dir, PACKET_DIR)
    rtl_packets = sorted(packets_dir.glob("rtl__*.json")) if packets_dir.is_dir() else []
    tb_packets = sorted(packets_dir.glob("tb__*.json")) if packets_dir.is_dir() else []
    issues: list[dict[str, str]] = []
    module_issues, module_counts = check_module_packets(ip_dir, packets_dir, hard_gate=hard_gate)
    domain_issues, domain_counts = check_domain_readiness(ip_dir, hard_gate=hard_gate)
    manifest_issues, manifest_counts = check_compile_manifest_freshness(ip_dir, hard_gate=hard_gate)

    if hard_gate and not rtl_packets:
        issues.append(issue("RTL_PACKET_MISSING", "RTL implementation dispatch needs generated rtl__*.json authoring packet.", str(packets_dir)))
    if hard_gate and not tb_packets:
        issues.append(issue("TB_PACKET_MISSING", "TB implementation dispatch needs generated tb__*.json authoring packet.", str(packets_dir)))

    for path in rtl_packets:
        issues.extend(check_rtl_packet(path, read_json(path), ip_dir=ip_dir, hard_gate=hard_gate, require_lifecycle=require_lifecycle))
    for path in tb_packets:
        issues.extend(check_tb_packet(path, read_json(path), ip_dir=ip_dir, hard_gate=hard_gate, require_lifecycle=require_lifecycle))
    issues.extend(module_issues)
    issues.extend(domain_issues)
    issues.extend(manifest_issues)

    next_actions: list[str] = []
    if issues:
        next_actions.append("Run oag.compile and repair generated packet inputs by fixing authored ontology, decomposition, structure, or domain intent.")
    elif not hard_gate:
        next_actions.append("Draft packet check is advisory; use --require-packets before RTL/TB dispatch.")
    else:
        next_actions.append("Role-specific authoring packets are ready for bounded subagent dispatch.")

    return {
        "schema_version": "oag_authoring_packet_check.v1",
        "status": "fail" if issues else "pass",
        "ip": ip_dir.name,
        "scope_locked": is_locked(ip_dir),
        "require_locked": require_locked,
        "require_packets": require_packets,
        "require_lifecycle": require_lifecycle,
        "hard_gate": hard_gate,
        "counts": {
            "rtl_packets": len(rtl_packets),
            "tb_packets": len(tb_packets),
            **module_counts,
            **domain_counts,
            **manifest_counts,
            "issues": len(issues),
        },
        "issues": issues,
        "next_actions": next_actions,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ip-dir", required=True)
    parser.add_argument("--require-locked", action="store_true")
    parser.add_argument("--require-packets", action="store_true", help="Require RTL and TB role packets even if scope is draft.")
    parser.add_argument("--require-lifecycle", action="store_true", help="Require lifecycle_input_refs and approved/current lifecycle eligibility.")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    result = check(
        Path(args.ip_dir),
        require_locked=args.require_locked,
        require_packets=args.require_packets,
        require_lifecycle=args.require_lifecycle,
    )
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    elif result["status"] == "pass":
        print("PASS oag authoring packet check")
    else:
        print("FAIL oag authoring packet check")
        for item in result["issues"]:
            path = f" {item['path']}" if item.get("path") else ""
            print(f"- {item['code']}:{path} {item['message']}")
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
