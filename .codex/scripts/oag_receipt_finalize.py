from __future__ import annotations

import json
from typing import Any

from oag_dispatch_support import (
    JsonObject,
    SCHEMAS_DIR,
    load_json,
    normalize_rel,
    path_matches,
)


NESTED_STRING_LIST_FIELDS = {
    "ppa_notes": ("performance", "power", "area", "tradeoffs"),
    "domain_crossing_notes": (
        "clock_domains",
        "reset_domains",
        "open_domain_crossing_blockers",
    ),
    "tb_methodology_notes": (
        "architecture",
        "stimulus_strategy",
        "coverage_strategy",
        "assertion_hooks",
        "formal_candidates",
        "open_methodology_blockers",
    ),
}

PASSING_HANDOFF_STATUSES = {
    "HANDOFF_PASS",
    "STATIC_HANDOFF_PASS",
    "RTL_HANDOFF_PASS",
}

OBJECT_LIST_FIELD_ALIASES = {
    "tb_methodology_notes": {
        "architecture_roles": "architecture",
    },
}


def normalize_schema_shapes(value: Any, schema: Any, *, field_name: str = "") -> Any:
    """Repair only lossless string/list/object shape drift declared by the schema.

    Workers occasionally render a prose string as a JSON string list, or a
    string-list field as a scalar string.  Preserve every string while fixing
    those two shapes.  A schema-defined object may also arrive as a list of
    uniquely labeled ``key=value`` strings.  Convert it only when every label
    maps to a declared property; otherwise leave it intact so verification
    still rejects malformed semantic data.
    """
    if not isinstance(schema, dict):
        return value
    expected_type = schema.get("type")
    if expected_type == "object" and isinstance(value, list):
        properties = schema.get("properties")
        aliases = OBJECT_LIST_FIELD_ALIASES.get(field_name, {})
        if not isinstance(properties, dict) or not all(isinstance(item, str) for item in value):
            return value
        parsed: JsonObject = {}
        for item in value:
            if "=" not in item:
                return value
            raw_key, raw_value = item.split("=", 1)
            key = aliases.get(raw_key.strip(), raw_key.strip())
            if not key or key not in properties or key in parsed:
                return value
            parsed[key] = normalize_schema_shapes(
                raw_value.strip(), properties[key], field_name=key
            )
        value = parsed
    if expected_type == "object" and isinstance(value, dict):
        properties = schema.get("properties")
        if not isinstance(properties, dict):
            return value
        normalized = dict(value)
        for field, field_schema in properties.items():
            if field in normalized:
                normalized[field] = normalize_schema_shapes(
                    normalized[field], field_schema, field_name=field
                )
        return normalized
    if expected_type == "array":
        item_schema = schema.get("items")
        if (
            isinstance(value, str)
            and isinstance(item_schema, dict)
            and item_schema.get("type") == "string"
        ):
            return [value] if value else []
        if isinstance(value, list) and isinstance(item_schema, dict):
            return [
                normalize_schema_shapes(item, item_schema, field_name=field_name)
                for item in value
            ]
        return value
    if expected_type == "string" and isinstance(value, list):
        if all(isinstance(item, str) for item in value):
            return "\n".join(value)
    return value


def string_list(value: Any) -> list[Any]:
    if isinstance(value, str):
        return [value] if value else []
    if isinstance(value, list):
        return list(value)
    return []


def append_unique(values: list[Any], *items: str) -> list[Any]:
    result = list(values)
    for item in items:
        if item and item not in result:
            result.append(item)
    return result


def classify_receipt_paths(
    finalized: JsonObject,
    dispatch: JsonObject,
    *,
    manifest_path: str,
    event_log_path: str,
) -> None:
    """Classify worker outputs by the dispatch-owned path contract.

    Models describe semantic outputs, but they should not decide whether an
    output is an implementation write or a runtime side effect.  Move paths
    between the two receipt collections only when the dispatch makes that
    classification unambiguous.  Unknown paths remain in their original
    collection so verification still rejects out-of-scope writes.
    """
    allowed_writes = [str(item) for item in string_list(dispatch.get("allowed_write_paths"))]
    allowed_tools = [str(item) for item in string_list(dispatch.get("allowed_tool_side_effects"))]
    changed: list[Any] = []
    generated: list[Any] = []

    def add_classified(raw: Any, *, original: str) -> None:
        if not isinstance(raw, str):
            (generated if original == "generated" else changed).append(raw)
            return
        normalized = normalize_rel(raw)
        if path_matches(normalized, allowed_tools):
            if raw not in generated:
                generated.append(raw)
        elif path_matches(normalized, allowed_writes):
            if raw not in changed:
                changed.append(raw)
        else:
            target = generated if original == "generated" else changed
            if raw not in target:
                target.append(raw)

    for item in string_list(finalized.get("changed_paths")):
        add_classified(item, original="changed")
    for item in string_list(finalized.get("owned_changed_paths")):
        add_classified(item, original="changed")
    for item in string_list(finalized.get("generated_side_effects")):
        add_classified(item, original="generated")
    for item in (manifest_path, event_log_path):
        add_classified(item, original="generated")

    finalized["changed_paths"] = changed
    if "owned_changed_paths" in finalized:
        finalized["owned_changed_paths"] = list(changed)
    finalized["generated_side_effects"] = generated


def runtime_receipt_skeleton(
    dispatch: JsonObject,
    *,
    thread_id: str,
    manifest_path: str,
    event_log_path: str,
    created_at: str,
) -> JsonObject:
    actor = dispatch.get("execution_actor") if isinstance(dispatch.get("execution_actor"), dict) else {}
    receipt_path = str(dispatch.get("receipt_path") or "")
    shard_scope = str(dispatch.get("task_id") or dispatch.get("dispatch_id") or "dispatch")
    payload: JsonObject = {
        "schema_version": "oag_subagent_receipt.v1",
        "product_name": str(dispatch.get("product_name") or "IP Dev Agent"),
        "internal_gateway": str(dispatch.get("internal_gateway") or "Ontology Agent Gateway"),
        "ip_id": str(dispatch.get("ip_id") or ""),
        "agent_type": str(dispatch.get("agent_type") or ""),
        "role_name": str(dispatch.get("role_name") or ""),
        "registered_id": str(dispatch.get("registered_id") or ""),
        "dispatch_id": str(dispatch.get("dispatch_id") or ""),
        "dispatch_path": str(dispatch.get("dispatch_path") or ""),
        "execution_kind": str(actor.get("kind") or "worker_thread"),
        "thread_id": thread_id,
        "execution_manifest_path": manifest_path,
        "shard_scope": shard_scope,
        "stage": str(dispatch.get("stage") or ""),
        "status": "INCONCLUSIVE",
        "owned_obligations": string_list(dispatch.get("owned_obligations")),
        "contracts": string_list(dispatch.get("contracts")),
        "allowed_write_paths": string_list(dispatch.get("allowed_write_paths")),
        "changed_paths": [],
        "generated_side_effects": append_unique([], manifest_path, event_log_path),
        "evidence_outputs": append_unique([], receipt_path),
        "diagnostic_only": False,
        "covers_writes": False,
        "dispatch_verified": False,
        "implementation_evidence": False,
        "may_claim_complete": False,
        "created_at": created_at,
    }
    for field in ("wavefront_run_id", "task_id", "ownership_mode"):
        value = str(dispatch.get(field) or "")
        if value:
            payload[field] = value
    return payload


def receipt_prompt_skeleton(
    dispatch: JsonObject,
    *,
    thread_id: str,
    manifest_path: str,
    event_log_path: str,
) -> str:
    skeleton = runtime_receipt_skeleton(
        dispatch,
        thread_id=thread_id,
        manifest_path=manifest_path,
        event_log_path=event_log_path,
        created_at="<UTC timestamp after dispatch creation>",
    )
    return json.dumps(skeleton, indent=2, sort_keys=True)


def finalize_worker_receipt(
    dispatch: JsonObject,
    receipt: JsonObject,
    *,
    thread_id: str,
    manifest_path: str,
    event_log_path: str,
    created_at: str,
) -> tuple[JsonObject, list[str]]:
    """Normalize dispatch-owned structure without promoting semantic status."""
    original = dict(receipt)
    finalized = dict(receipt)
    skeleton = runtime_receipt_skeleton(
        dispatch,
        thread_id=thread_id,
        manifest_path=manifest_path,
        event_log_path=event_log_path,
        created_at=created_at,
    )

    protected_fields = (
        "schema_version",
        "product_name",
        "internal_gateway",
        "ip_id",
        "agent_type",
        "role_name",
        "registered_id",
        "dispatch_id",
        "dispatch_path",
        "execution_kind",
        "thread_id",
        "execution_manifest_path",
        "stage",
        "owned_obligations",
        "contracts",
        "allowed_write_paths",
        "diagnostic_only",
        "dispatch_verified",
        "may_claim_complete",
        "created_at",
    )
    for field in protected_fields:
        finalized[field] = skeleton[field]

    for field in ("wavefront_run_id", "task_id", "ownership_mode"):
        if field in skeleton:
            finalized[field] = skeleton[field]
        else:
            finalized.pop(field, None)

    if not isinstance(finalized.get("shard_scope"), str) or not finalized.get("shard_scope"):
        finalized["shard_scope"] = skeleton["shard_scope"]

    status = finalized.get("status")
    if not isinstance(status, str) or not status:
        finalized["status"] = "INCONCLUSIVE"

    for field in ("changed_paths", "generated_side_effects", "evidence_outputs"):
        finalized[field] = string_list(finalized.get(field))
    finalized["evidence_outputs"] = append_unique(
        finalized["evidence_outputs"], str(dispatch.get("receipt_path") or "")
    )

    classify_receipt_paths(
        finalized,
        dispatch,
        manifest_path=manifest_path,
        event_log_path=event_log_path,
    )

    if finalized.get("status") in PASSING_HANDOFF_STATUSES:
        finalized["covers_writes"] = True
    elif not isinstance(finalized.get("covers_writes"), bool):
        finalized["covers_writes"] = False
    if not isinstance(finalized.get("implementation_evidence"), bool):
        finalized["implementation_evidence"] = False

    for field in ("checks_run", "implemented_contracts", "behavior_refs_implemented", "cycle_rule_refs_implemented"):
        if field in finalized:
            finalized[field] = string_list(finalized[field])
    if "owned_changed_paths" in finalized:
        finalized["owned_changed_paths"] = string_list(finalized["owned_changed_paths"])

    for object_field, list_fields in NESTED_STRING_LIST_FIELDS.items():
        nested = finalized.get(object_field)
        if not isinstance(nested, dict):
            continue
        normalized_nested = dict(nested)
        for list_field in list_fields:
            if list_field in normalized_nested:
                normalized_nested[list_field] = string_list(normalized_nested[list_field])
        finalized[object_field] = normalized_nested

    receipt_schema = load_json(SCHEMAS_DIR / "oag_subagent_receipt.schema.json")
    finalized = normalize_schema_shapes(finalized, receipt_schema)

    normalized_fields = sorted(
        field
        for field in set(original) | set(finalized)
        if original.get(field) != finalized.get(field)
    )
    return finalized, normalized_fields
