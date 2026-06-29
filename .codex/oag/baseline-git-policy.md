# OAG Baseline Git and External Artifact Policy

OAG baselines use git for small source-of-record files and an OAG manifest for
meaning, hashes, evidence scope, and versioning.

```text
git commit          = exact tracked file tree
annotated git tag   = human-readable baseline version
baseline manifest   = trust boundary linking truth, implementation, evidence,
                      external artifacts, validation, and gate decision
```

## Routine Checkpoints vs Golden Baselines

Routine IP-local commits are expected during development. They should happen
after meaningful OAG stage boundaries with:

```bash
python3 .codex/scripts/oag_ip_git.py checkpoint --ip-dir <ip> --message "OAG <stage>: <meaningful summary>" --json
```

Those commits are not product signoff by themselves. They are a compact audit
trail so draft intake, decision rows, contract projection, implementation
handoffs, evidence refresh, and validation/gate artifacts can be recovered and
reviewed. Golden or release baselines require the separate manifest/tag flow
below and explicit approval.

The IP-local `.gitignore` must keep large or rerunnable tool output out of
routine commits. Do not bypass it by force-adding waveforms, simulator
databases, object directories, logs, or bulky reports. Reference required
external artifacts in the baseline manifest with `sha256` instead.

## Manifest and Git

Baseline manifests must not embed their own concrete commit hash. The manifest
is committed inside the git tree, so writing that commit hash into the manifest
creates a self-reference loop.

Use:

```yaml
git:
  tag: oag/<ip>/v0.1.0
  commit: resolved_by_tag
  tag_type: annotated
```

The checker resolves the tag when git verification is requested.

Annotated tag messages may include:

```text
manifest: ontology/baselines/<ip>_golden_v0.1.0.yaml
manifest_sha256: sha256:<digest>
```

## Tracked Artifacts

Tracked artifacts should be small, reviewable, and sufficient for compact
audit:

- ontology truth files;
- RTL/TB source;
- scripts/config needed to reproduce;
- compact simulation and coverage summaries;
- validation and gate records;
- baseline manifests.

Do not put large/transient evidence into `tracked_artifacts`.

Blocked tracked patterns include:

```text
*.vcd
*.fst
*.fsdb
*.vpd
*.wlf
*.ucdb
*.vdb
*.log
sim/build/**
work/**
.cache/**
```

## External Artifacts

Git-external does not mean governance-external. Any external artifact referenced
by a baseline must carry at least:

```yaml
id:
kind:
uri:
sha256:
required_for: audit | reproduce | debug_only | optional
retention: required | time_bound | optional | ephemeral
```

Waveforms are usually `debug_only` and `optional`. Raw coverage databases may be
`audit` and `required` for stricter release profiles.

Default baseline checking validates shape and hashes recorded in the manifest.
Availability/download checks should be explicit so ordinary CI does not depend
on artifact-store reachability.
