Claude Code orchestration should be testable, not just a prompt that sounds smart.

Version 2.1 of the Claude Code Smart Orchestrator Kit keeps the four proven routes and adds a fifth, opt-in planning option:

- Architect: Opus with high effort
- Deep Reasoner: Opus with xhigh effort
- Fable Planner: Fable with xhigh effort, explicit opt-in
- Fast Worker: Haiku with low effort
- QA Reviewer: Sonnet with high effort

Opus remains the default repository architect, even for a broad roadmap. Fable runs only when the user explicitly requests it by name or invokes `@agent-fable-planner`; it is not a silent replacement for a route that already works.

The Fable option requires Claude Code 2.1.170 or newer, and 2.1.210 or newer is recommended. On 2.1.210, a five-event no-tool preflight and a 14-event explicit `@agent-fable-planner` foreground lifecycle both completed with linked `claude-fable-5` metadata and passed their separate strict verifiers. The delegated pilot used the exact release-candidate agent file, made one allowed Read, and made no edits or command calls. That is honest evidence for one environment and run, not a future-routing guarantee; every team should repeat the proof, with Opus as the fallback when Fable is unavailable or inconclusive.

The kit includes model aliases, five scoped agent definitions, deterministic `@agent-*` proof prompts, automatic-routing experiments, a routing matrix, safe setup guidance, a strict validator, and separate verifiers for direct-model and delegated-Agent traces.

I ran the four established routes through Claude Code 2.1.210 in a disposable project and observed linked Opus, Opus, Haiku, and Sonnet model metadata. The test caught a real defect too: plan mode blocked QA's exact test command, so the shipped QA route now uses default mode with a bounded command contract.

The docs show how to verify one completed agent lifecycle and its reported model metadata through stream JSON. Aliases can be overridden or unavailable, and traces do not attest effective effort, so configuration alone is never treated as proof.

This is not a promise of lower cost or better results. It is a practical way to make routing visible, bounded, and measurable against your own baseline.

The full kit, visual guide, adversarial tests, and deterministic release archive are free under the MIT License. Built with appreciation for Matt Farmer's original model-routing idea and encouragement.

Get it here: https://github.com/jeffjhunter/claude-code-smart-orchestrator
