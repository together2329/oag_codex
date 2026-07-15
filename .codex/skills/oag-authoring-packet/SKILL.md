---
name: oag-authoring-packet
description: Use before locked OAG RTL, TB, or evidence implementation dispatch when role-specific generated authoring packets must be compiled, audited, or passed to native subagents instead of raw user prose.
---

# OAG Authoring Packet

Use this skill after lock readiness passes and before spawning RTL, TB, or
evidence-producing subagents.

## Rules

- RTL/TB agents consume authoring packets, not original natural-language prose.
- `rtl__*.json` packets carry implementation contract refs, behavior refs,
  cycle refs, interface refs, and PPA/CDC note requirements.
- `tb__*.json` packets carry scenarios, expected-source policy, scoreboard
  rows, coverage refs, and assertion/formal candidates.
- Do not edit files under `ontology/generated/authoring_packets/` by hand.
- If a packet is wrong, fix authored ontology and compile again.

## Commands

Generate packets:

```bash
python3 .codex/scripts/oag_cli.py call oag.compile --file <compile_args.json>
```

Validate packets:

```bash
python3 .codex/scripts/oag_authoring_packet_check.py --ip-dir <ip> --require-packets --json
```

## Dispatch Use

When spawning a native OAG subagent, include the relevant packet path and keep
the dispatch allowed paths narrow. RTL dispatch should reference `rtl__*.json`.
TB dispatch should reference `tb__*.json`.
For role-structured waves, multiple children may consume the same packet, but
each child must receive a bounded role, such as RTL_INTERFACE_SHELL,
RTL_CONTROL_FSM, TB_DRIVER_BFM, TB_MONITOR, TB_PREDICTOR_MODEL, or
TB_SCOREBOARD_SCHEMA, and must be limited to that role's allowed paths. Shared
top modules, filelists, result aggregation, and evidence manifests belong to a
single integration or runner owner.
