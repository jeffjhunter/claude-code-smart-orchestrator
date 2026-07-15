# Routing test prompts

Run these in a disposable repository or branch. Record the task UI or stream JSON evidence and the observed model for every direct invocation. A configured alias is not runtime proof.

## Fable availability preflight

Before invoking the optional Fable agent, run this direct-model probe from a
disposable project and keep its trace outside the repository:

```powershell
$preflight = Join-Path $env:TEMP "ccso-fable-preflight.jsonl"
claude -p "Return exactly FABLE_PREFLIGHT_OK. Do not use tools." `
  --model fable `
  --output-format stream-json `
  --verbose `
  --no-session-persistence |
  Set-Content -LiteralPath $preflight -Encoding utf8
```

Then switch to the kit root and run:

```powershell
python -I starter/scripts/verify_direct_model_trace.py $preflight --expected-model fable --expected-result FABLE_PREFLIGHT_OK
```

The direct verifier requires Fable-family assistant `message.model` metadata,
no tool or Agent lifecycle, and the exact successful sentinel. Do not use the
Agent-only `verify_runtime_trace.py` for this preflight. Delete or securely
retain the trace after review; never commit it.

## Deterministic direct-invocation tests

Run each prompt separately in the Claude Code UI.

### Fable Planner

```text
@agent-fable-planner Inspect this repository and produce a read-only, long-horizon roadmap for evolving the starter into a mature multi-environment routing system. Separate facts from assumptions; compare viable scenarios; include phases, dependencies, decision gates, leading indicators, fallback paths, and phase-level success criteria. End with the first bounded handoff. Do not edit files, run commands, invent owners, or invent deadlines.
```

Expected configured target: `fable` with `xhigh` effort. If the alias is unavailable or overridden, record that outcome; an Opus result is not Fable proof.

### Architect

```text
@agent-architect Inspect this repository and propose one small architectural improvement. Stay read-only. Include exact file references, tradeoffs, acceptance criteria, and verification commands.
```

Expected configured target: `opus` with `high` effort.

### Deep Reasoner

```text
@agent-deep-reasoner Inspect existing test-output or timing artifacts in this repository and analyze the slowest recorded test. Compare evidence-based hypotheses for why it is slow. If no timing evidence exists, report that evidence gap and propose a measurement plan. Stay read-only; do not run commands or claim a cause the artifacts cannot support.
```

Expected configured target: `opus` with `xhigh` effort.

### Fast Worker

```text
@agent-fast-worker Objective: update README.md by adding a two-sentence local development note. Allowed path: README.md only. Excluded scope: every other path. Acceptance criteria: exactly two useful sentences are added under the existing development section, existing content remains intact, and no other file changes. Exact verification command: git diff --check -- README.md. Make the bounded edit, run that command, review the README.md diff, and report the exact result.
```

Expected configured target: `haiku` with `low` effort. Run only in a disposable branch because this test requests a real edit.

### QA Reviewer

```text
@agent-qa-reviewer Review the current README.md change against this acceptance criteria: exactly two useful local-development sentences were added under the existing development section, existing content is intact, and no other source file was changed. Stay behaviorally non-editing. Exact first verification command: git diff --check -- README.md. Run that command verbatim first. Then you are explicitly authorized to run each of these commands at most once, without variants: git diff -- README.md and git status --short. Use that evidence plus read/search tools, run no other shell command, and return PASS, PASS WITH WARNINGS, or FAIL with criterion-by-criterion evidence.
```

Expected configured target: `sonnet` with `high` effort. Remember that shell-based checks can still create caches or other artifacts.

## Explicit end-to-end sequence

Run the five prompts above as separate routing proofs. For a real end-to-end task, select the applicable planning route and pass bounded outputs forward:

1. `@agent-fable-planner` is optional and runs only when the user explicitly requests Fable.
2. `@agent-architect` translates the selected direction or next phase into concrete repository boundaries, implementation order, and acceptance criteria.
3. `@agent-deep-reasoner` is used only if a difficult uncertainty remains.
4. `@agent-fast-worker` receives one bounded implementation assignment.
5. `@agent-qa-reviewer` independently verifies the final result.

Do not invoke both planning routes by default. When explicitly requested, Fable Planner defines the strategic path; Architect defines concrete repository design. A Fable-to-Architect handoff is useful only when both layers are actually needed.

Do not infer a successful route from the final answer alone. Save lifecycle and model evidence for every invoked task.

## Probabilistic automatic-routing tests

These prompts intentionally omit an `@agent-*` mention. They test whether the parent conversation follows the guidance in `CLAUDE.md`; they do not force delegation.

### Automatic broad-planning fallback

```text
Inspect this repository and build a multi-phase roadmap for evolving it over several release cycles. Compare scenarios, identify dependencies and decision gates, define leading indicators and fallback paths, and stay read-only. End with the first bounded handoff.
```

Expected policy route: `architect`. Fable Planner must not be selected without an explicit request for Fable or a direct `@agent-fable-planner` invocation.

### Automatic architecture selection

```text
Inspect this multi-module repository and produce an implementation-ready plan for adding a health-check endpoint. Do not edit files. Include boundaries, exact paths, risks, and verification commands.
```

### Automatic difficult-reasoning selection

```text
Investigate this intermittent test failure. Compare plausible root causes, gather the smallest useful evidence set, and recommend a corrective action without editing files.
```

### Automatic implementation and review selection

```text
Add the already-specified README development note, keep the change bounded, and independently verify it before reporting completion.
```

For each automatic test, record whether the parent delegated, which agent it chose, and which model actually ran. A decision not to delegate is a valid observation of probabilistic routing, not proof that direct invocation is broken.

## Evidence checklist

- Prompt and timestamp
- Claude Code version
- Installed agent file hash or commit
- Requested agent
- Observed subagent lifecycle
- Configured alias and effort
- Observed model metadata
- Files changed, including incidental artifacts
- Commands and outcomes
- Final verdict and unresolved uncertainty

The trace verifier checks routing structure and model metadata, not semantic
task success. A parent result can be successful even when an agent reports a
blocked command or unmet criterion. Always evaluate the agent output and the
repository state in addition to running the verifier.
