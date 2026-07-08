# ChatGPT Review Workflow

Use this reference when the review should go through the user's logged-in ChatGPT session. Chrome connector control is the preferred route. Desktop UI control is a fallback only when the user explicitly names `computer-use` or explicitly approves that route.

## Required Setup

1. Use the `chrome:control-chrome` skill and read its instructions before using Chrome tools.
2. Prefer the Chrome connector's browser-client workflow over raw GUI scripting.
3. After connecting, name the session clearly, for example `GPT web review`.
4. Reuse an existing ChatGPT tab when it is already open and suitable. Otherwise open `https://chatgpt.com/` in a new Chrome tab.

## Route Decision Tree

1. Try the Chrome connector route first.
2. If the Chrome connector reports that the extension browser is unavailable or blocked, run the troubleshooting checks below and retry once after a short wait.
3. If the connector is still unavailable, use desktop fallback only when the user explicitly requested `computer-use` or explicitly approved the fallback.
4. If neither route is available, stop and report the concrete blocker. Offer a Codex `gpt-5.5` review thread only when the user explicitly wants that non-web fallback.

Do not silently switch from Chrome connector control to desktop UI control. The route affects privacy, reliability, and visible user state.

## Chrome Connector Troubleshooting

When the connector fails before opening or controlling ChatGPT:

- Inspect available browser backends through the Chrome control workflow, for example the equivalent of `agent.browsers.list()`.
- If the extension backend says `Browser is not available: extension`, verify that Chrome is running, the extension is installed/enabled in the active profile, and the native host manifest is present.
- If plugin helper scripts are used and direct execution fails because of permissions, run them with `node <script>` instead of editing permissions.
- Retry the connector once after Chrome is focused or restarted.
- If Chrome is running and the extension/native host checks look correct but the connector still fails, record that exact state as the blocker before choosing an approved fallback.

Do not use AppleScript, ad hoc DOM scraping, or shell-based browser automation to bypass a broken connector.

## Data Boundary

Before sending anything to ChatGPT, classify the prompt content:

- Safe bounded summary: goal, file names, contracts, short pseudocode, test results, and exact questions. Send this when the user requested GPT web review.
- Sensitive or bulky content: full source files, full diffs, private logs, secrets, credentials, customer data, personal data, proprietary documents, or local file contents. Do not send this unless the user explicitly approves those exact data and destination.

Do not paste secrets or credentials. If a file or log may contain secrets, summarize the relevant behavior instead.

## Prompt Transfer Safety

Large review packets often contain quotes, backticks, braces, shell fragments, or Markdown fences. Avoid inline shell-quoted prompt arguments, especially on PowerShell or mixed shell paths.

- Compose the packet locally as plain text.
- Transfer it through clipboard, browser-client input APIs, or stdin-based paste commands.
- Before sending, inspect the ChatGPT input and confirm that the packet was not truncated, quote-mangled, or expanded by the shell.
- If the prompt is too large for reliable UI paste, shorten it to a bounded summary and ask narrower questions rather than pasting more source.

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
- Exact questions:

Please answer with:
1. Top correctness/safety risks, ordered by severity.
2. Missing regression tests.
3. Architectural adjustments to make now.
4. Go/no-go recommendation.
```

## Desktop Fallback With Computer Use

Use this path only when the user explicitly names `computer-use` or explicitly approves desktop fallback.

1. Read the `computer-use` skill before controlling desktop UI.
2. Check Orca availability with its status/capabilities commands. If the runtime is not running and the user already approved desktop fallback, start or focus Orca/Codex and retry the status check.
3. Prefer the ChatGPT desktop app when available. Use the app identifier visible to the computer-use tools, such as `com.openai.chat`.
4. If ChatGPT desktop is unavailable, use an already suitable desktop browser window only when it is clearly under user-approved fallback scope.
5. Inspect the visible model/mode text. For example, a valid visible selection may look like `ChatGPT 5.5 Pro`.
6. Focus the composer, paste the bounded packet through a safe paste method, then inspect visible input text before sending.
7. If a UI action reports a stale window, wrong window, or unresolved target, re-read the app state and re-focus the intended text field before retrying.
8. Do not click notification permission prompts, account prompts, or unrelated overlays unless the user explicitly asks.

For computer-use prompt transfer, prefer stdin or clipboard paste over embedding the packet in a shell command argument. This avoids breaking prompts that contain quotes or Markdown fences.

## Reading the Answer

1. Wait until generation completes. In Korean UI, stop or active-generation controls may appear as `답변 중지`, `생성 중단하기`, or similar text; wait until they disappear.
2. Poll the visible app or browser state rather than assuming a fixed timeout. If the accessible tree is stale or ambiguous, take a screenshot or re-read the window state.
3. Extract the rendered response text. Use a visible copy control, including `복사` or `마크다운으로 복사`, when it is more reliable than reading the accessibility tree.
4. If copying succeeds, read the clipboard once and treat that text as the extracted answer. If copying is unavailable, use visible text and scroll only as needed.
5. Save the useful findings in the working notes or final response summary, not as an unreviewed source of truth.

## Local Follow-Up

Treat the ChatGPT response as review input, not authority.

- Accept advice only after checking local source and requirements.
- Reject or defer advice that conflicts with local invariants, user instructions, or available evidence.
- Add or update local tests for any accepted behavioral change.
- Run the relevant local verification gates before final reporting.

## Closing the Browser Task

When the review tab is a useful artifact, finalize the Chrome browser-client session with the ChatGPT tab kept as a deliverable. If the tab has no value after extraction, leave no deliverable tab.

If the Chrome extension is unavailable or blocked, follow the troubleshooting and route decision tree above. Leave the desktop app or browser in a stable state and report which route was used, which model/mode was visible, and whether the answer was copied or manually extracted.
