# Claude Code Smart Orchestrator Kit v2.0.0

An evidence-backed starter for routing Claude Code work by role, model alias, and effort level.

## Default routes

| Agent | Intended work | Configured model alias | Effort |
|---|---|---:|---:|
| `architect` | Plans, boundaries, interfaces, and tradeoffs | `opus` | `high` |
| `deep-reasoner` | Ambiguous failures and high-consequence reasoning | `opus` | `xhigh` |
| `fast-worker` | Clear, bounded implementation | `haiku` | `low` |
| `qa-reviewer` | Independent verification | `sonnet` | `high` |

These are configured targets, not proof of the model that actually ran. Claude Code, an organization policy, a provider, or an account plan can override or exclude an alias. Verify every test run in the Claude task UI or CLI event output. See `starter/MODEL-POLICY.md`.

`starter/CLAUDE.md` provides routing guidance to the parent conversation. It does not deterministically force automatic delegation. Use direct UI mentions such as `@agent-architect` when proving that a particular agent was invoked.

## Bundle contents

- `starter/.claude/agents/`: four project subagent definitions
- `starter/CLAUDE.md`: parent routing and completion guidance
- `starter/MODEL-POLICY.md`: configured routes, caveats, and proof requirements
- `starter/ROUTING-MATRIX.md`: task-to-agent reference
- `starter/SETUP.md`: safe installation, upgrade, and removal instructions
- `starter/TEST-PROMPTS.md`: deterministic and probabilistic test prompts
- `starter/scripts/validate_kit.py`: static validation for the starter
- `starter/scripts/verify_runtime_trace.py`: fail-closed checks for one observed Agent/model trace
- `LIVE-TEST-RESULTS.md`: dated v2 probe results, the QA defect found, and evidence limitations
- `CREDITS.md`: attribution and project provenance
- `Claude-Code-Smart-Orchestrator-Kit.pdf`: companion visual guide
- `Claude-Code-Smart-Orchestrator-Infographic.png`: companion overview graphic
- `social-post.md`: launch copy

The executable starter files and current Markdown documentation are authoritative for v2. Companion visual assets are explanatory and are not runtime evidence.

## Requirements

- Claude Code 2.1.210 or newer is recommended.
- Confirm current model aliases, effort support, subagent syntax, and permission behavior in the current official Claude Code documentation before production use.
- Python 3.10 or newer and PyYAML are required for the bundled validation and release scripts.
- PowerShell is recommended for native Windows commands; Git Bash is also supported when the project commands are portable. On Windows with Git Bash installed, the PowerShell tool may need `CLAUDE_CODE_USE_POWERSHELL_TOOL=1` for the current shell.

Install the pinned development dependency range if needed:

```bash
python -m pip install -r requirements-dev.txt
```

## Safe start

1. Read `starter/SETUP.md`.
2. Back up and merge an existing `CLAUDE.md` or `.claude/` directory. Do not overwrite project instructions or agents blindly.
3. Run the static validator from the kit root:

   ```bash
   python -I starter/scripts/validate_kit.py
   ```

4. Install into a disposable project or branch.
5. Run the four direct-mention proof tests in `starter/TEST-PROMPTS.md`.
6. Record the observed model and agent lifecycle evidence before relying on a route.

Validate a saved CLI trace from the kit root, substituting the expected route:

```powershell
$trace = Join-Path $env:TEMP "ccso-architect-proof.jsonl"
python -I starter/scripts/verify_runtime_trace.py $trace --expected-agent architect --expected-model opus
```

This proves only that the supplied trace contains the expected linked routing
evidence and a successful parent result. Review the agent's actual output,
commands, file changes, and acceptance criteria separately.

For proof runs, record whether `CLAUDE_CODE_SUBAGENT_MODEL` or
`CLAUDE_CODE_EFFORT_LEVEL` is set without printing its value. The former can
override every subagent model; the latter can override frontmatter effort.
The bundled trace verifier validates model metadata, not observed effort.

## Boundaries

- Model aliases and effort settings do not guarantee availability, quality, latency, or cost.
- The kit does not guarantee savings. Measure token use, elapsed time, retries, and acceptance rates against a baseline.
- Agent prompts and `permissionMode` values are not a security sandbox. Parent permissions can override or broaden behavior.
- QA has shell access so it can run checks. A shell command can create or modify artifacts even when the QA prompt says read-only.
- QA uses `permissionMode: default`; its exact verification command still depends on the parent session's current user, organization, and tool permissions.
- The manifest, validator, and body hashes detect changes relative to the shipped local policy. They are not an external signature or trust anchor.
- The kit does not install hooks. Optional `SubagentStart` and `SubagentStop` hooks can record lifecycle evidence, but review them before adding them.

Use only on repositories and systems you are authorized to access. Keep credentials, personal data, and proprietary content out of shared prompts, traces, screenshots, and test fixtures.

Licensed under the MIT License. See `LICENSE`.

Special thanks to Matt Farmer, whose Codex model-routing article helped inspire
the experiment. See `CREDITS.md` for attribution and project provenance.
