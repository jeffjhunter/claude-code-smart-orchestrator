# Smart Orchestrator project instructions

Use role-based delegation to keep the main conversation focused and to avoid spending deep-reasoning effort on routine work.

## Operating rules

1. Classify the request before delegating: architecture, hard reasoning, implementation, or verification.
2. Delegate only self-contained work with explicit inputs, file paths, constraints, and acceptance criteria.
3. Use `architect` for system boundaries, plans, tradeoffs, and dependency ordering. It does not edit files.
4. Use `deep-reasoner` only for ambiguous root causes, difficult algorithms, security-sensitive reasoning, or decisions with expensive consequences. It does not edit files.
5. Use `fast-worker` for bounded implementation, boilerplate, formatting, focused refactors, and test updates after the plan is clear.
6. Use `qa-reviewer` after implementation. It validates requirements, runs relevant checks, and reports evidence without editing files.
7. Do not ask agents to delegate further. The main conversation owns orchestration and synthesis.
8. Do not run two agents that may edit the same file at the same time.
9. Do not accept completion claims without file paths, commands run, and test or inspection evidence.
10. If requirements are unclear, stop and ask for clarification instead of guessing.

## Default routing sequence

- Small, obvious change: main conversation or `fast-worker`, then `qa-reviewer`.
- Multi-file feature: `architect`, then one or more bounded `fast-worker` tasks, then `qa-reviewer`.
- Difficult failure: `deep-reasoner`, then `fast-worker`, then `qa-reviewer`.
- Read-only audit: `qa-reviewer` or `architect`, depending on whether the goal is compliance or design.

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

- Confirm the requested files changed.
- Run the narrowest relevant tests or checks.
- Review the final diff or artifact.
- Report failures and uncertainty honestly.
