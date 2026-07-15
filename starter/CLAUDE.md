# Smart Orchestrator project instructions

Use role-based delegation to keep the parent conversation focused and to match effort to consequence. These instructions guide routing; they do not guarantee that Claude Code will automatically delegate.

## Configured routes

| Agent | Use for | Model alias | Effort |
|---|---|---:|---:|
| `fable-planner` | User-opted-in Fable roadmaps, phased strategy, scenarios, and decision gates | `fable` | `xhigh` |
| `architect` | Plans, boundaries, interfaces, and dependency order | `opus` | `high` |
| `deep-reasoner` | Ambiguous root causes, difficult algorithms, security-sensitive decisions | `opus` | `xhigh` |
| `fast-worker` | Clear, bounded implementation and routine code changes | `haiku` | `low` |
| `qa-reviewer` | Independent requirements and test verification | `sonnet` | `high` |

Aliases and effort settings are targets. Runtime configuration, policy, or model availability can change the observed route. Follow `MODEL-POLICY.md` and capture runtime evidence for routing claims.

## Operating rules

1. Classify the request before delegating: explicit Fable opt-in, architecture, hard reasoning, implementation, or verification.
2. Delegate only self-contained work with explicit inputs, file paths, constraints, excluded scope, acceptance criteria, and a verification method.
3. Use `fable-planner` only when the user explicitly requests Fable by name or directly invokes `@agent-fable-planner`. A broad or strategic task alone is not an opt-in. It must not edit files and does not replace the concrete architecture route.
4. Use `architect` before implementation when repository boundaries, interfaces, or dependency ordering are unclear. It must not edit files.
5. Reserve `deep-reasoner` for uncertainty or consequence that justifies its higher effort. It must not edit files.
6. Use `fast-worker` only after the work is bounded and the finish line is explicit.
7. Use `qa-reviewer` after implementation. It should inspect independently and report evidence rather than rely on another agent's summary.
8. Do not ask agents to delegate further. The parent conversation owns orchestration, ordering, and synthesis.
9. Do not run two agents concurrently when either may edit the same file or depend on the other's unfinished output.
10. Do not accept completion claims without file references, commands or inspections performed, and their outcomes.
11. Ask for clarification when a missing decision would materially change the result.
12. Treat prompts and permission modes as guardrails, not a security boundary. The parent permission mode can override them.
13. Treat QA shell access as potentially mutating even though the QA role is described as read-only.

## Default sequences

- Small, obvious change: parent or `fast-worker`, then `qa-reviewer` when the risk justifies review.
- Explicit Fable opt-in for a long-horizon roadmap: `fable-planner`; after a direction is selected, use `architect` to translate the next phase into concrete repository boundaries and implementation order.
- Broad roadmap without an explicit Fable request: `architect` remains the default planner.
- Multi-file feature: `architect`, bounded `fast-worker` assignments, then `qa-reviewer`.
- Difficult failure: `deep-reasoner`, then `fast-worker`, then `qa-reviewer`.
- Read-only design audit: `architect`.
- Read-only compliance or implementation audit: `qa-reviewer`.

Automatic selection remains probabilistic. For a deterministic invocation test, use the agent's UI mention, such as `@agent-fable-planner` or `@agent-architect`, and verify the observed model in runtime evidence.

## Delegation packet

Every delegated task must include:

- Objective
- Inputs and relevant file paths
- Constraints and excluded scope
- Required output format
- Acceptance criteria
- Verification command or inspection method

## Completion gate

Before reporting completion:

- Confirm the requested files changed and unrelated files did not.
- Run the narrowest relevant tests or inspections.
- Review the final diff or artifact.
- Resolve or report failed checks.
- Separate verified facts from assumptions.
- Report routing as configured unless runtime evidence proves the observed agent, model, and lifecycle.
