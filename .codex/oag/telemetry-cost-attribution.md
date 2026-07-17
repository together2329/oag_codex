# Codex OTEL Cost Attribution

Codex native OpenTelemetry is the token and runtime-model source of truth.
OAG hook events add execution identity only: workspace, main or child
conversation IDs, agent role, dispatch, stage, receipt, and evidence links.
Prompt text is not stored (`otel.log_user_prompt = false`). The local receiver
also redacts user account IDs and email attributes before writing JSONL.

For dispatch-backed children, correlation also carries task/wavefront identity,
execution budget, model capability tier, compact-context contract, result,
content fingerprint, and dispatch scope hash. These fields make budget and
duplicate-review checks reproducible without storing prompt text.

## Runtime

Start the loopback OTLP/HTTP JSON receiver before opening a new Codex session:

```bash
python3 .codex/scripts/oag_otel_receiver.py start
python3 .codex/scripts/oag_otel_receiver.py status
```

Codex accepts OTEL settings only from user-level `~/.codex/config.toml`; it
ignores project-local OTEL keys. The user config exports Codex log events to
`http://127.0.0.1:4318/v1/logs`. Captures are written to the ignored local file
`.codex/.cache/otel/codex-logs.jsonl`. Stop the receiver with:

```bash
python3 .codex/scripts/oag_otel_receiver.py stop
```

Codex emits actual runtime model and token fields on
`codex.sse_event` / `response.completed`. OAG writes correlation events to
`.codex/.cache/otel/oag-executions.jsonl`. A child `agent_id` is treated as the
child conversation ID; `session_id` remains the parent conversation ID.

## Report

For current OTEL data only:

```bash
python3 .codex/scripts/oag_otel_cost.py \
  --workspace "$PWD" \
  --output .codex/.cache/otel/reports/current.json
```

Validate the resulting report against execution-efficiency targets:

```bash
python3 .codex/scripts/oag_execution_efficiency_check.py \
  --report .codex/.cache/otel/reports/current.json --json
```

Historical reports created before dispatch budgets should use `--advisory`;
new runs should use the default enforcing mode.

For pre-OTEL history, add Codex rollout directories. The reporter selects the
larger complete session total when rollout and OTEL overlap, preventing double
counting while preserving OTEL model breakdown when it is complete.

```bash
python3 .codex/scripts/oag_otel_cost.py \
  --workspace "$PWD" \
  --rollout-root "$HOME/.codex/sessions" \
  --rollout-root "$HOME/.codex/archived_sessions" \
  --output .codex/.cache/otel/reports/current-with-backfill.json
```

Use `telemetry-rate-card.example.json` as an effective-dated rate-card shape.
The reporter separates non-cached input, cached input, visible output, and
reasoning output. It emits no monetary total for a model without a matching
rate. Runtime token counts are measured; a configured token-rate result is a
rate-card calculation, not an OpenAI invoice.

For ChatGPT subscription authentication, token totals and attribution are
exact at the captured event boundary, but API list prices do not define the
subscription charge. Exact currency cost requires the applicable contract,
credit schedule, or internal chargeback rate in the rate card.

## External Backends

The localhost receiver is deliberately small. To use an OpenTelemetry
Collector or a hosted backend, change `[otel].exporter` to its OTLP logs
endpoint. Keep the OAG correlation JSONL or forward equivalent correlation
records so `conversation.id` remains joinable to dispatch and receipt data.

References:

- <https://learn.chatgpt.com/docs/config-file/config-advanced>
- <https://learn.chatgpt.com/docs/config-file/config-reference>
- <https://opentelemetry.io/docs/specs/otlp/>
