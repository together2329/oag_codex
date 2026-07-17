from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Union

    JsonValue = Union[None, bool, int, float, str, list["JsonValue"], dict[str, "JsonValue"]]
    JsonObject = dict[str, JsonValue]
else:
    JsonValue = str
    JsonObject = dict


def json_strings(value: JsonValue) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


def build_prompt_contract(dispatch: JsonObject) -> str:
    budget = dispatch.get("execution_budget") if isinstance(dispatch.get("execution_budget"), dict) else {}
    context = dispatch.get("context_contract") if isinstance(dispatch.get("context_contract"), dict) else {}
    lines = [
        "OAG DISPATCH",
        f"- dispatch_id: {dispatch['dispatch_id']}",
        f"- dispatch_path: {dispatch['dispatch_path']}",
        f"- agent_type: {dispatch['agent_type']}",
        f"- ip_dir: {dispatch['ip_dir']}",
        f"- stage: {dispatch['stage']}",
        f"- receipt_path: {dispatch['receipt_path']}",
        f"- allowed_write_paths: {', '.join(json_strings(dispatch['allowed_write_paths'])) or '(none)'}",
        f"- allowed_tool_side_effects: {', '.join(json_strings(dispatch['allowed_tool_side_effects'])) or '(none)'}",
        "Execution budget:",
        f"- complexity: {budget.get('complexity') or 'unspecified'}",
        f"- max_total_tokens: {budget.get('max_total_tokens') or 'unspecified'}",
        f"- warning_total_tokens: {budget.get('warning_total_tokens') or 'unspecified'}",
        f"- max_review_attempts: {budget.get('max_review_attempts') if budget else 'unspecified'}",
        f"- model_tier: {budget.get('model_tier') or 'unspecified'}",
        "- at the warning threshold, finish the current bounded check and report remaining work",
        "- at the hard limit, stop and return BLOCKED with a replan request; do not silently continue",
        "Compact context contract:",
        f"- fork_turns: {context.get('fork_turns') or 'none'}",
        f"- input_mode: {context.get('input_mode') or 'explicit_file_list'}",
        f"- max_direct_source_files: {context.get('max_direct_source_files') or 'unspecified'}",
        "- use the dispatch authoring packet and explicit file/hash list as the task context",
        "- do not request or replay the full parent transcript",
        "- repeat review only when the target content hash changed",
        "Subagent implementation boundary:",
        "- you own only the assigned implementation, verification, or evidence deliverable inside this dispatch",
        "- the parent owns OAG orchestration state: dispatch creation, wavefront claims, barrier decisions, and validation decisions",
        "- Do not create a new dispatch, mutate parent-owned dispatch records, or start replacement work",
        "- Do not open or claim wavefront barriers",
        "- Do not release or close wavefront tasks",
        "- Do not run decision_harness record",
        "- Do not call close_agent, stale-child cleanup, or native-child cleanup from this implementation task",
        "- stay inside allowed_write_paths; use allowed_tool_side_effects only for generated or wavefront bookkeeping explicitly listed above",
        "Evidence-status boundary:",
        "- if this dispatch touches scoreboard, results, or coverage evidence, use the repo evidence schema as source of truth",
        "- BLOCKED/INCONCLUSIVE environment evidence must stay traceable and must not be converted into DUT functional PASS",
        "- coverage blocked before sampling is not 0% coverage; report it as blocked, not observed, or not sampled",
        "- blocked coverage should set status=BLOCKED, coverage_observed=false, coverage_sampled=false, "
        "closure_coverage_counted=false, and a blocker reason when the repo schema or writer convention supports those fields",
        "- Do not report coverage_percent=0 for a run that never sampled coverage",
        "- for full or non-smoke runner evidence, do not fall back to the smoke subset after plan parse failure; "
        "write BLOCKED/INCONCLUSIVE runner configuration evidence instead",
        "- for full or non-smoke runner evidence, report scenario_count, scenario_source, plan_parse_success=true, "
        "and smoke_fallback_used=false in the receipt or evidence notes when those fields are allowed",
        "- when observed_source.kind=monitor is used only for schema compatibility and no DUT simulation ran, "
        "use only scoreboard_rows.v1-allowed fields; express no DUT execution through allowed metadata, "
        "blocker, mismatch, observed object, or evidence_notes",
        "- simulator setup blockers are environment blockers, not DUT functional failures",
        "- if results.xml is written for a setup blocker, classify it as environment blocked, skipped, or error; "
        "do not imply DUT functional failure or scoreboard mismatch",
    ]
    if dispatch.get("wavefront_run_id"):
        lines.extend(
            [
                f"- wavefront_run_id: {dispatch['wavefront_run_id']}",
                f"- task_id: {dispatch.get('task_id') or '(none)'}",
                f"- ownership_mode: {dispatch.get('ownership_mode') or '(none)'}",
                "Heartbeat requirements:",
                "- after the first bounded unit of work, and before a long wait, record machine-readable progress with:",
                "  python3 .codex/scripts/oag_wavefront.py heartbeat "
                f"--ip-dir {dispatch['ip_dir']} --run-id {dispatch['wavefront_run_id']} "
                f"--task-id {dispatch.get('task_id') or '<task-id>'} --message \"<phase>\" --json",
                "- emit `WORKING: <task> - <phase>` within the first parent wait cycle and at major phase changes",
                "- if the parent asks for status after a silent wait, answer with `WORKING:`, `BLOCKED:`, or the receipt path instead of staying silent",
                "Wavefront abort guard:",
                "- before writing outputs or a receipt, re-read the task in "
                f"{dispatch['ip_dir']}/ontology/runs/{dispatch['wavefront_run_id']}/wavefront_task_graph.json",
                "- if that task status is blocked, failed, or inconclusive, stop immediately and do not write late artifacts",
            ]
        )
    lines.extend(
        [
            "Receipt requirements:",
            "- include dispatch_id and dispatch_path exactly as above",
            "- include wavefront_run_id/task_id when this dispatch belongs to a wavefront task",
            "- list changed_paths and generated_side_effects separately",
            "- use HANDOFF_PASS, STATIC_HANDOFF_PASS, RTL_HANDOFF_PASS, FAIL, BLOCKED, or INCONCLUSIVE",
            "- HANDOFF_PASS is only for the assigned deliverable; it does not imply IP closure, canonical simulation evidence, DUT functional PASS, or barrier readiness",
            "- set may_claim_complete=false",
            "- end with OAG_EVIDENCE_RECORDED: <relative-path>",
        ]
    )
    return "\n".join(lines)
