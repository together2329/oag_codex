---
name: oag-lock-preview-frame
description: Use before locking a hardware IP scope when the user wants a formal, readable HTML review surface that preserves OAG source artifacts verbatim. Generates a static pre-lock review frame with lock-readiness issues, source hashes, navigation summaries, and unmodified raw panels for source claims, ambiguities, features, decisions, requirement atoms, requirements, obligations, contracts, verification intent, and IP-XACT-style integration metadata.
---

# OAG Lock Preview Frame

Use this skill immediately before asking the user to approve or lock an OAG IP
scope. The purpose is review clarity, not truth generation: the HTML is a
read-only review envelope over the authored OAG files.

## Core Rule

Do not paraphrase source truth into the review artifact. The frame may provide
navigation, counts, hashes, and readiness issues, but each lock-relevant file
must be shown in a verbatim source panel. A user must be able to review the raw
text exactly as it exists on disk.

## Workflow

1. Finish the active deep interview, semantic intake, decision-matrix, or
   contract-projection step enough that draft files exist.
2. Run the frame generator:

```bash
python3 .codex/scripts/oag_lock_preview_frame.py --ip-dir <ip> --json
```

3. Open or point the user to `<ip>/knowledge/lock_preview/index.html`.
4. Ask for approval only after the user has a chance to review the frame.
5. If the user corrects anything, update draft/OAG source files and regenerate
   the frame. Do not lock from a stale frame.

Use draft mode only when intentionally showing an early preview:

```bash
python3 .codex/scripts/oag_lock_preview_frame.py --ip-dir <ip> --readiness-mode draft --json
```

## What The Frame Must Contain

The frame must show:

- readiness status and issues from the OAG lock-readiness checker;
- source index with file path, present/missing status, line count, and SHA-256;
- verbatim panels for `req/source_claims.yaml`, `req/ambiguity_register.yaml`,
  `req/interview_draft.md`, `ontology/features.yaml`,
  `ontology/decision_matrix.yaml`, `ontology/requirement_atoms.yaml`,
  `ontology/requirements.yaml`, `ontology/obligations.yaml`,
  `ontology/contracts.yaml`, `ontology/modeling.yaml`,
  `ontology/structure.yaml`, `ontology/decomposition.yaml`,
  `ontology/verification_plan.yaml`, `ontology/tb_methodology.yaml`,
  `ontology/ipxact_projection.yaml`, `ontology/scope_lock.json`, and legacy
  `req/locked_truth.md` if present.

The generated JSON sidecar is for automation and hashes. The HTML is for human
review.

## Review Standard

Treat the frame as acceptable only when:

- the user can inspect the original wording without leaving the page;
- every lock-relevant section is either present or visibly missing;
- summaries never replace raw source panels;
- lock-blocking ambiguities and decisions are visible;
- requirement atoms, obligations, and contracts are visible before lock;
- feature scope and IP-XACT-style integration gaps are visible;
- the displayed hashes match the current files.

If any of these fail, continue interview or projection work before lock.
