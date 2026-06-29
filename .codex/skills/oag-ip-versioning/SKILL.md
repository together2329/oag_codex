---
name: oag-ip-versioning
description: Use when managing an IP workspace's functional semantic version, IP-local git readiness, golden baseline lineage, baseline manifest/tag relation, or version bump recommendation before RTL/TB/evidence consumers rely on a baseline.
---

# OAG IP Versioning

Use this skill when an IP needs functional version governance: major/minor/patch
bump selection, golden baseline readiness, IP-local git initialization checks,
or baseline tag verification.

## Purpose

This skill does not create design truth. It governs whether an IP's approved
truth, implementation, evidence, validation, and gate artifacts are versioned
well enough to become an auditable baseline.

OAG traceability still flows through:

```text
Requirement -> Obligation -> Contract -> Evidence -> Validation -> Decision
```

The version ledger records which baseline lineage is active and which semantic
bump is appropriate.

## Inputs

Read:

- `.codex/oag/ip-versioning-policy.md`
- `.codex/rules/oag-ip-versioning.rules.md`
- `<ip>/ontology/ip_version.yaml`
- `<ip>/ontology/baselines/*.yaml`
- `<ip>/ontology/validations/*.json`
- `<ip>/ontology/gates/*.json`

For golden/release checks, use the IP-local `.git`, not the product-pack
development repository.

## IP-Local Git Discipline

New OAG IP scaffolds initialize an IP-local `.git` repository and an OAG-safe
`.gitignore` by default. Existing IP folders should be initialized before their
artifacts become implementation or baseline inputs:

```bash
python3 .codex/scripts/oag_ip_git.py init --ip-dir <ip> --initial-commit --message "OAG scaffold <ip>" --json
```

Record small, meaningful checkpoints after every stage boundary that changes
source-of-record files:

```bash
python3 .codex/scripts/oag_ip_git.py checkpoint --ip-dir <ip> --message "OAG <stage>: <meaningful summary>" --json
```

Required checkpoint points:

- scaffold creation;
- deep interview or semantic-intake draft updates;
- decision matrix, requirement atom, obligation, or contract projection;
- user scope lock or post-lock truth refresh;
- RTL/TB integration handoff;
- simulation, evidence projection, validation, and gate refresh;
- baseline manifest or version ledger update.

The checkpoint helper uses Python `subprocess` with direct `git` invocation, not
`/bin/sh` or `sh.exe`. On Windows it works from PowerShell when Git for Windows
is installed and `git.exe` is on `PATH`; if not, it also tries common Git for
Windows install locations such as `Program Files/Git/cmd/git.exe`. Large or
rerunnable dumps stay out of git through the managed IP-local `.gitignore`.
If a raw waveform, simulator database, or large report is needed for release,
store it outside git and reference it from the baseline manifest with `sha256`.

## Required Checks

Before treating a baseline as version-ready:

```bash
python3 .codex/scripts/oag_ip_version_check.py --ip-dir <ip> --require-ip-git --json
python3 .codex/scripts/oag_baseline_check.py --manifest <ip>/ontology/baselines/<baseline>.yaml --json
```

After the baseline commit and annotated tag exist:

```bash
python3 .codex/scripts/oag_ip_version_check.py --ip-dir <ip> --require-ip-git --verify-git-tag --json
python3 .codex/scripts/oag_baseline_verify.py --manifest <ip>/ontology/baselines/<baseline>.yaml --verify-git-tag --json
```

## Bump Selection

Recommend:

- `patch` only when functional truth is unchanged.
- `minor` when approved design meaning changes but the project treats it as a
  compatible baseline evolution.
- `major` when external users or downstream systems must consciously adopt the
  change.
- `initial` for the first recorded IP version entry.

If a patch candidate changes requirements, contracts, locked decisions,
behavior/cycle rules, firmware-visible storage/IRQ behavior, or interface
semantics, return BLOCKED and recommend minor or major instead.

## Agent Handoff

Use `oag-ip-version-steward-agent` for read-only version/baseline review. The
steward may write reports or versioning evidence under allowed evidence paths,
but it must not implement RTL/TB, create golden/release tags without human
approval, or claim final closure.

## Output

Useful outputs:

- version bump recommendation;
- golden baseline readiness report;
- IP-local git initialization blocker;
- missing manifest/approval/tag blocker;
- patch truth-change blocker;
- tag verification result.
