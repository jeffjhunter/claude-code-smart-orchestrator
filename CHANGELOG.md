# Changelog

All notable changes to this kit are documented here.

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
