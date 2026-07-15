# Model and effort policy

## Default configuration

| Agent | Model alias | Effort | Rationale |
|---|---:|---:|---|
| `fable-planner` | `fable` | `xhigh` | An explicit user opt-in can request a second planning route for goals spanning phases, scenarios, and decision gates. |
| `architect` | `opus` | `high` | Plans and interface decisions benefit from stronger reasoning without defaulting to the maximum effort tier. |
| `deep-reasoner` | `opus` | `xhigh` | Reserved for ambiguous or high-consequence problems that justify the highest configured effort. |
| `fast-worker` | `haiku` | `low` | Bounded implementation should favor speed after requirements are clear. |
| `qa-reviewer` | `sonnet` | `high` | Independent verification needs capable reasoning without reusing the implementation route. |

These values are routing policy, not observed runtime facts.

Fable Planner, Architect, and Deep Reasoner use `permissionMode: plan` because their profiles have no editing or shell tools. Fast Worker and QA Reviewer use `permissionMode: default`. QA needs the default mode so a parent-approved verification command can run; its prompt still forbids source edits, variants, and extra shell commands, but that behavioral contract is not a sandbox.

Fable Planner is additive and explicit opt-in only. Use it when the user requests Fable by name or directly invokes `@agent-fable-planner`; a broad or long-horizon task alone continues to route to Architect. Keep Architect on Opus for concrete repository architecture, interfaces, boundaries, and implementation order. A Fable roadmap can precede an Architect pass after the user selects a direction, but neither route is required for every task.

## Why runtime evidence is required

Model aliases can resolve differently over time. A Claude Code setting, organization policy, account plan, provider, region, feature rollout, or allowlist can override or exclude a configured alias or effort value. Claude Code behavior can also change between releases.

Two environment variables deserve an explicit proof-run check:

- `CLAUDE_CODE_SUBAGENT_MODEL` overrides the per-call model parameter and every subagent frontmatter model.
- `CLAUDE_CODE_EFFORT_LEVEL` overrides subagent frontmatter effort.

Record whether each variable is present without printing its value. If policy permits, run the proof from a clean process where both are unset; otherwise label the override in the evidence. The stream-JSON verifier checks linked model metadata. It does not prove the effective effort level, so record effort separately from the Claude Code UI/status indicator and current settings.

Before relying on this policy:

1. Use Claude Code 2.1.210 or newer as the recommended baseline.
2. Check the current official documentation for supported model aliases, effort levels, subagent configuration, tools, hooks, and permission precedence.
3. Invoke each agent directly with its `@agent-*` mention, including a separate Fable proof if that alias is available to the account.
4. Check the two override variables above without exposing their values.
5. Confirm the observed subagent and model in the task UI or CLI stream JSON.
6. Record effective effort separately when the current UI exposes it.
7. Record versioned evidence and redact sensitive content before sharing it.

Optional `SubagentStart` and `SubagentStop` hooks can record lifecycle events. They are not installed by this kit and must be reviewed before use. A lifecycle event alone does not prove the model unless the supported event or accompanying trace contains that metadata.

## Automatic routing is guidance

`CLAUDE.md` describes when the parent conversation should delegate. It is not deterministic enforcement. Automatic-routing tests may produce a different agent or no delegation. Use direct mentions when agent invocation itself is an acceptance criterion. If the `fable` alias is unavailable or overridden, record that result and fall back to `architect` for a concrete repository plan; do not relabel an Opus trace as Fable evidence.

## Measurement

Do not advertise or assume savings from the alias table. Compare a routed run with a consistent baseline and record:

- Input and output tokens
- Elapsed time
- Retry and repair count
- Test or review acceptance rate
- Human intervention
- Observed model metadata and separately recorded effective effort

Routing may increase cost or latency when delegation, duplicated context, or rework outweighs specialization.

## Local customization

Change a route only after defining why, how it will be verified, and what fallback is acceptable when the alias is unavailable. Update the agent definition, this policy, local validation expectations, and proof evidence together. Never weaken tool or permission controls merely to make a model route succeed.
