---
name: oag-doc-to-markdown
description: Use when converting PDFs, PowerPoint .pptx, Word .docx, Excel, HTML, text-like specs, datasheets, uploaded documents, or binary design notes into Markdown for OAG source intake or general agent review. Uses a bundled converter with text passthrough and markitdown-backed conversion when available.
---

# OAG Document To Markdown

Use this skill when a source document must become Markdown before analysis,
source-claim capture, deep semantic intake, or ordinary review.

This skill is intentionally usable without full OAG mode. It converts document
formats into Markdown; it does not approve, normalize, lock, or promote the
content as requirement truth.

## Quick Use

```bash
python3 .codex/skills/oag-doc-to-markdown/scripts/doc_to_markdown.py \
  --input <source-file> \
  --out-dir <markdown-output-dir> \
  --json
```

Print Markdown directly:

```bash
python3 .codex/skills/oag-doc-to-markdown/scripts/doc_to_markdown.py \
  --input <source-file> \
  --stdout
```

## Supported Paths

Passthrough text-like inputs are decoded as UTF-8 with replacement for invalid
bytes:

- `.md`, `.markdown`, `.txt`, `.rst`
- `.yaml`, `.yml`, `.json`, `.xml`
- `.csv`, `.tsv`
- common code/spec text such as `.sv`, `.svh`, `.v`, `.vh`, `.py`, `.tcl`,
  `.sdc`, `.rpt`, and `.log`

Converted document inputs use `markitdown` when it is available:

- `.pdf`
- `.pptx`
- `.docx`
- `.xlsx`
- `.html`, `.htm`

Other formats may work if `markitdown` supports them locally. If conversion
fails, report the blocker. Do not infer or summarize unseen document content.

## Backend Setup

The converter first tries the in-process Python package and then a subprocess
backend:

```bash
python3.10 -m pip install 'markitdown[all]'
```

If the working Python is not the one with `markitdown` installed, set:

```bash
export OAG_MARKITDOWN_PYTHON=/path/to/python
```

## OAG Intake Boundary

Treat generated Markdown as raw or parsed source material:

```text
source document -> Markdown source -> source_claims / ambiguity / intake notes
```

Do not treat generated Markdown as canonical `requirements.yaml`, locked truth,
approved assumptions, or closure evidence by itself. If the Markdown carries
load-bearing IP meaning, preserve source references and run the usual OAG
intake, decision, requirement, contract, and validation workflow before RTL/TB
consumption.
