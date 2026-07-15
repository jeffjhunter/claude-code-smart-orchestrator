# Changelog

All notable changes to this kit are documented here.

## 2.1.0 - 2026-07-15

### Added

- An opt-in long-horizon `fable-planner` project agent configured for the `fable` alias at `xhigh` effort in plan mode.
- Explicit `@agent-fable-planner` preflight and delegated-proof guidance.
- A strict no-tool direct-model trace verifier so the Fable availability preflight and delegated Agent proof stay separate.
- A Claude Code 2.1.170 minimum for the optional Fable route, with 2.1.210 or newer recommended.
- An Opus fallback path when Fable is unavailable, rejected, or cannot be attributed in a delegated trace.

### Changed

- Kept the proven Opus `architect` as the default planning route; Fable is additive and runs only after the user explicitly requests it.
- Expanded the routing documentation and editable visual sources from four configured agents to five.
- Separated direct Fable availability evidence from delegated subagent evidence.

### Evidence

- A direct Fable preflight on Claude Code 2.1.210 completed and reported `claude-fable-5` model metadata.
- A five-event no-tool direct preflight and a 14-event explicit `@agent-fable-planner` foreground lifecycle both linked to `claude-fable-5` metadata and passed their separate strict verifiers.
- The delegated pilot used an agent file byte-identical to the release candidate, performed one allowed Read, made no edits or command calls, and returned the three requested bounded-planning bullets.
- Both observations describe single runs in one environment, not a model, quality, latency, cost, or future-routing guarantee.

## 2.0.0 - 2026-07-14

### Added

- Explicit role routes for Opus, Sonnet, and Haiku aliases with per-agent effort levels.
- Runtime evidence guidance using direct agent mentions, the task UI, or stream JSON.
- Separate deterministic direct-invocation tests and probabilistic automatic-routing tests.
- A model policy explaining overrides, exclusions, measurement, and honest claims.
- Windows PowerShell and Git Bash installation guidance.
- Safe backup, merge, upgrade, and uninstall instructions.
- MIT license and security guidance.
- A fail-closed static validator with exact agent-body integrity checks and adversarial tests.
- A runtime-trace verifier that checks one linked Agent call, completed lifecycle, non-error result, model-family evidence, and successful parent result.
- A deterministic allowlisted release builder with manifests, checksums, secret scanning, and trusted-checkout verification.
- Reproducible HTML/SVG visual sources, a 14-page PDF guide, and a 1600x2000 launch infographic.
- Public-repository issue templates, private vulnerability reporting guidance, pinned GitHub Actions, and Dependabot coverage for Actions and Python dependencies.

### Changed

- Clarified that `CLAUDE.md` is routing guidance rather than deterministic enforcement.
- Clarified that prompts and permission modes are not a security sandbox.
- Clarified that QA shell checks can create artifacts despite a behaviorally read-only role.
- Set QA to the default permission mode after a live plan-mode probe blocked its required verification command.
- Replaced guaranteed savings language with a requirement to measure routed runs against a baseline.
- Recorded live direct-invocation observations for all four routes and documented the limits of that evidence.

### Security

- Documented runtime evidence handling, hook review, credential hygiene, and configuration merge safety.
