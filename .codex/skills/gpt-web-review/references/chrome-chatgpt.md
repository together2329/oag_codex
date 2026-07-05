# Chrome ChatGPT Review Workflow

Use this reference when the review should go through the user's logged-in ChatGPT session in Chrome.

## Required Setup

1. Use the `chrome:control-chrome` skill and read its instructions before using Chrome tools.
2. Prefer the Chrome connector's browser-client workflow over raw GUI scripting.
3. After connecting, name the session clearly, for example `GPT web review`.
4. Reuse an existing ChatGPT tab when it is already open and suitable. Otherwise open `https://chatgpt.com/` in a new Chrome tab.

## Data Boundary

Before sending anything to ChatGPT, classify the prompt content:

- Safe bounded summary: goal, file names, contracts, short pseudocode, test results, and exact questions. Send this when the user requested GPT web review.
- Sensitive or bulky content: full source files, full diffs, private logs, secrets, credentials, customer data, personal data, proprietary documents, or local file contents. Do not send this unless the user explicitly approves those exact data and destination.

Do not paste secrets or credentials. If a file or log may contain secrets, summarize the relevant behavior instead.

## Model Selection

Select the requested model or mode by visible UI text only. Do not assume fixed DOM node IDs or menu structure.

For GPT-5.5 Pro review:

1. Inspect the visible model picker or mode selector.
2. Select `Pro` if the product exposes Pro mode separately.
3. Select `GPT-5.5` when visible.
4. If the requested model is not visible, report that exactly and use the closest visible model only with user consent.

## Sending the Prompt

1. Compose the bounded review packet locally first.
2. Paste it into the ChatGPT input using clipboard or browser-client DOM input.
3. Inspect the input area before sending. Confirm it contains only the bounded packet.
4. Send only after the selected model/mode looks correct.

Use this structure:

```text
You are reviewing <system>. Act as a strict senior reviewer.

Context:
- Goal:
- Invariants:
- Implemented changes:
- Verification:
- Known caveats:

Please answer with:
1. Top correctness/safety risks, ordered by severity.
2. Missing regression tests.
3. Architectural adjustments to make now.
4. Go/no-go recommendation.
```

## Reading the Answer

1. Wait until generation completes. In Korean UI, the stop button may appear as `답변 중지`; wait until it disappears.
2. Extract the rendered response text. Use a visible copy button if it is more reliable than DOM text extraction.
3. Save the useful findings in the working notes or final response summary, not as an unreviewed source of truth.

## Local Follow-Up

Treat the ChatGPT response as review input, not authority.

- Accept advice only after checking local source and requirements.
- Reject or defer advice that conflicts with local invariants, user instructions, or available evidence.
- Add or update local tests for any accepted behavioral change.
- Run the relevant local verification gates before final reporting.

## Closing the Browser Task

When the review tab is a useful artifact, finalize the Chrome browser-client session with the ChatGPT tab kept as a deliverable. If the tab has no value after extraction, leave no deliverable tab.

If the Chrome extension is unavailable or blocked, follow the Chrome skill troubleshooting path. Do not use AppleScript, raw accessibility scripting, or shell-based browser automation as a workaround. Offer a Codex `gpt-5.5` review thread only if the user explicitly wants that fallback.
