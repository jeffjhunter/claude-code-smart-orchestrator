# Claude Code Smart Orchestrator

Route Claude Code work by role, model alias, and effort level - then verify
what actually ran.

![Claude Code Smart Orchestrator v2 routing overview](Claude-Code-Smart-Orchestrator-Infographic.png)

## The four default lanes

| Agent | Job | Model | Effort | Permission mode |
|---|---|---:|---:|---:|
| `architect` | Plans, interfaces, tradeoffs, and sequencing | `opus` | `high` | `plan` |
| `deep-reasoner` | Ambiguous failures and high-consequence reasoning | `opus` | `xhigh` | `plan` |
| `fast-worker` | Clear, bounded implementation | `haiku` | `low` | `default` |
| `qa-reviewer` | Independent review and exact supplied checks | `sonnet` | `high` | `default` |

These are configured targets, not permanent runtime guarantees. Model aliases,
account policy, permissions, and availability can change the observed route.

## What v2 observed and fixed

Version 2.0.0 was tested in a disposable repository with Claude Code 2.1.210.
Four explicit Agent calls produced linked Opus, Opus, Haiku, and Sonnet model
metadata respectively. The test also caught a real QA configuration defect:
plan mode blocked the required test command, so QA now uses default mode with a
strict exact-first-command/no-unapproved-variant prompt contract.

Read [LIVE-TEST-RESULTS.md](LIVE-TEST-RESULTS.md) for the dated observations,
the defect-and-fix record, evidence hashes, costs, and limitations. Observed
trace metadata is not cryptographic proof, and one successful demo is not a
general quality or savings claim.

## Quick start

Do the first run in a disposable project or branch. Do not overwrite an
existing `CLAUDE.md` or `.claude/` directory.

```powershell
python -m pip install -r requirements-dev.txt
python -I starter/scripts/validate_kit.py
```

Python 3.10 or newer is required.

Then follow [starter/SETUP.md](starter/SETUP.md) to back up and deliberately
merge the project instructions and four agent files.

For a deterministic agent-invocation check, use an explicit mention:

```text
@agent-architect Inspect this repository read-only and return one risk.
```

Capture CLI evidence and validate it separately:

```powershell
$trace = Join-Path $env:TEMP "ccso-architect-proof.jsonl"
claude -p "Use @agent-architect to inspect the project. Do not edit." `
  --output-format stream-json `
  --verbose `
  --no-session-persistence |
  Set-Content -LiteralPath $trace -Encoding utf8

python -I starter/scripts/verify_runtime_trace.py $trace `
  --expected-agent architect `
  --expected-model opus
```

An `OBSERVED TRACE PASS` verifies the supplied trace structure and linked
model metadata. Review the task output, commands, diff, and acceptance criteria
independently.

Before a proof run, record whether `CLAUDE_CODE_SUBAGENT_MODEL` and
`CLAUDE_CODE_EFFORT_LEVEL` are set without printing their values. They can
override the configured model and effort. The trace verifier checks model
metadata, not effective effort. Keep raw traces outside the repository and
delete or securely retain them after review.

## Included

- Four strict project-agent definitions in `starter/.claude/agents/`
- Parent routing guidance and model policy
- Deterministic direct-invocation prompts and probabilistic router evaluations
- A recursive strict validator with fail-closed structural gates, exact agent-body hashes, a heuristic secret scan, and adversarial tests
- A runtime trace verifier with UTF-8 and UTF-16 support
- Safe Windows setup, upgrade, merge, rollback, and uninstall guidance
- A 14-page PDF guide and editable HTML/SVG visual sources
- Allowlisted deterministic ZIP builder, manifest, checksum, and trusted-source release verifier

Start with [README-FIRST.md](README-FIRST.md). The complete visual guide is
[Claude-Code-Smart-Orchestrator-Kit.pdf](Claude-Code-Smart-Orchestrator-Kit.pdf).

## Safety and honest claims

Agent prompts, tool lists, and permission modes are guardrails, not an
operating-system sandbox. Shell checks can mutate caches, snapshots, lockfiles,
or source. Keep secrets out of prompts and traces, review commands before
approval, and use least-privilege credentials.

Routing can improve or worsen cost, latency, and quality. Measure it against a
consistent baseline instead of promising savings. See [SECURITY.md](SECURITY.md)
and [starter/MODEL-POLICY.md](starter/MODEL-POLICY.md).

The manifest, local validator, and body hashes are integrity checks relative to
this checkout. They are not an external signature or independent trust anchor.

## Credits and license

Built by Jeff J Hunter. Special thanks to Matt Farmer, whose
[Codex model-routing article](https://mattfarmer.ai/codex-model-routing) helped
inspire the experiment and whose encouragement supported this implementation.

Released under the [MIT License](LICENSE). See [CREDITS.md](CREDITS.md) for
project provenance and trademark context.
