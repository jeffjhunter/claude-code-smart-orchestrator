Claude Code orchestration should be testable, not just a prompt that sounds smart.

I built the Claude Code Smart Orchestrator Kit v2 with four explicit routes:

- Architect: Opus with high effort
- Deep Reasoner: Opus with xhigh effort
- Fast Worker: Haiku with low effort
- QA Reviewer: Sonnet with high effort

The kit includes model aliases, scoped agent definitions, deterministic `@agent-*` proof prompts, automatic-routing experiments, a routing matrix, safe setup guidance, a strict validator, and a runtime-trace verifier.

I ran all four routes through Claude Code 2.1.210 in a disposable project and observed linked Opus, Opus, Haiku, and Sonnet model metadata. The test caught a real defect too: plan mode blocked QA's exact test command, so the shipped QA route now uses default mode with a bounded command contract.

The docs show how to verify one completed agent lifecycle and its reported model metadata through stream JSON. Aliases can be overridden or unavailable, and traces do not attest effective effort, so configuration alone is never treated as proof.

This is not a promise of lower cost or better results. It is a practical way to make routing visible, bounded, and measurable against your own baseline.

The full kit, visual guide, adversarial tests, and deterministic release archive are free under the MIT License. Built with appreciation for Matt Farmer's original model-routing idea and encouragement.

Get it here: https://github.com/jeffjhunter/claude-code-smart-orchestrator
