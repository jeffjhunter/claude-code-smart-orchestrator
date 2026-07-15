# Setup, upgrade, and removal

## Requirements

- Claude Code 2.1.210 or newer is recommended.
- Validate model aliases, effort levels, agent mentions, hooks, tools, and permission behavior against the current official Claude Code documentation before production use.
- Python 3.10 or newer and PyYAML are required for the validation and release tooling.
- Use a disposable repository or branch for the first run.

Install the development dependency range if needed:

```bash
python -m pip install -r requirements-dev.txt
```

### Native Windows PowerShell check

On Windows without Git Bash, Claude Code enables its PowerShell tool automatically. With Git Bash installed, the PowerShell tool may still be in progressive rollout. Enable it for the current PowerShell process and verify that a supported executable is available:

```powershell
$env:CLAUDE_CODE_USE_POWERSHELL_TOOL = '1'
Get-Command pwsh.exe, powershell.exe -ErrorAction SilentlyContinue
claude
```

Confirm that the PowerShell tool is available before testing Fast Worker or QA. Git Bash remains a fallback for portable POSIX commands. Current preview limitations include unloaded PowerShell profiles and no Windows sandboxing, so tool availability is not a security boundary.

## 1. Back up existing project configuration

Do not replace an existing `CLAUDE.md` or `.claude/` directory wholesale. Back it up, compare it with this starter, and merge only the intended sections and agent files.

PowerShell, from the target project root:

```powershell
$backup = ".orchestrator-backup-$(Get-Date -Format 'yyyyMMdd-HHmmss')"
New-Item -ItemType Directory -Path $backup | Out-Null
if (Test-Path .\CLAUDE.md) { Copy-Item .\CLAUDE.md $backup }
if (Test-Path .\.claude) { Copy-Item .\.claude $backup -Recurse }
```

Git Bash, from the target project root:

```bash
backup=".orchestrator-backup-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$backup"
[ ! -f CLAUDE.md ] || cp CLAUDE.md "$backup/"
[ ! -d .claude ] || cp -R .claude "$backup/"
```

Keep the backup outside any commit containing secrets. If project configuration contains sensitive values, protect or remove the backup when it is no longer needed.

## 2. Merge the starter

For a new project, copy these items from `starter/` into the project root:

```text
CLAUDE.md
MODEL-POLICY.md
ROUTING-MATRIX.md
.claude/agents/architect.md
.claude/agents/deep-reasoner.md
.claude/agents/fast-worker.md
.claude/agents/qa-reviewer.md
```

For an existing project:

1. Merge the orchestration rules into the existing `CLAUDE.md` without removing project-specific instructions.
2. Inspect `.claude/agents/` recursively for name collisions or untrusted agent files.
3. Compare each matching agent file before replacing it.
4. Copy `MODEL-POLICY.md` and `ROUTING-MATRIX.md`, or merge their content into equivalent project documentation.
5. Review the resulting diff before starting Claude Code.

PowerShell works best for native Windows project commands. Git Bash is suitable when the project's commands and paths are portable. Adapt verification commands in agent assignments to the shell actually available in your Claude Code environment.

## 3. Validate the source kit

From the kit root:

```bash
python -I starter/scripts/validate_kit.py
```

The validator checks static files and policy. It cannot prove which model will run, that a prompt will automatically route, or that a shell command is harmless.

If you intentionally change an agent's model, effort, tools, or permissions, update your local policy and validation expectations together. Treat a validation failure as a review point, not something to bypass.

## 4. Start and confirm discovery

From the target project root:

```bash
claude
```

Restart Claude Code after adding `.claude/agents/` if the agents are not discovered in the current session. Ask Claude to list the project agents, then compare the list with the four installed files.

## 5. Prove direct invocation and runtime routing

Run each direct-mention prompt in `TEST-PROMPTS.md` separately. For example:

```text
@agent-architect Inspect this repository and return a read-only architecture summary. Do not edit files.
```

The direct mention makes the requested agent invocation explicit. It does not by itself prove the observed model alias. Confirm the subagent and model in Claude Code's task UI.

Before a proof run, record only whether the two highest-priority override variables are present. Do not print their values:

```powershell
'CLAUDE_CODE_SUBAGENT_MODEL', 'CLAUDE_CODE_EFFORT_LEVEL' | ForEach-Object {
    [pscustomobject]@{ Name = $_; IsSet = Test-Path "Env:$_" }
}
```

If policy permits, start a clean process with both variables unset. Otherwise label the override in the test record.

For CLI evidence, run a safe read-only prompt and retain the JSON Lines output outside the repository:

```powershell
$trace = Join-Path $env:TEMP "ccso-architect-proof.jsonl"
claude -p "@agent-architect Inspect this repository read-only and summarize its top-level structure." `
  --output-format stream-json `
  --verbose `
  --no-session-persistence |
  Set-Content -LiteralPath $trace -Encoding utf8
```

Inspect the trace for the subagent lifecycle and model metadata supported by your current Claude Code version. Redact prompts, paths, tokens, and other sensitive data before sharing it.

From the kit root, the bundled verifier can check the expected Agent call,
linked model family, and final result structure:

```powershell
python -I starter/scripts/verify_runtime_trace.py $trace --expected-agent architect --expected-model opus
```

An `OBSERVED TRACE PASS` is routing evidence, not proof that the task's
acceptance criteria passed and not cryptographic proof of remote execution.
Review the output, commands, and diff independently.
The verifier checks model metadata, not effective effort. Delete or securely retain the temporary trace after review; never commit a raw trace.

Claude Code also supports optional `SubagentStart` and `SubagentStop` hooks. This kit does not install hooks silently. Add them only after reviewing the current hook schema and the command that will receive event data. Lifecycle hooks supplement the task UI or trace; they are not a substitute for observed model metadata.

## 6. Review permissions before real work

- Agent prompts and `permissionMode` values are behavioral controls, not a security sandbox.
- A parent permission mode or user approval can override or broaden an agent's effective permissions.
- QA needs shell access to run tests. Bash or PowerShell commands can write caches, coverage files, snapshots, lockfiles, build output, or source files even when the agent is described as read-only.
- QA uses `permissionMode: default` so an explicitly supplied command can be approved or allowed. The parent session's current user, organization, and tool permissions still decide whether it runs.
- Run untrusted repositories in an isolated environment and review commands before approval.
- Keep credentials and private data out of prompts, agent definitions, traces, and hook logs.

## Upgrade

1. Read `VERSION` and `CHANGELOG.md` in the new kit.
2. Back up the project's current `CLAUDE.md`, `.claude/`, and policy documents.
3. Compare and merge changes instead of replacing the directory.
4. Reapply intentional local model, tool, and permission policy changes.
5. Run the validator and all four direct-mention proof tests again.
6. Record fresh runtime evidence because model availability and resolution can change.

## Uninstall

1. Remove only the four kit-owned files from `.claude/agents/`.
2. Remove only the Smart Orchestrator sections merged into `CLAUDE.md`.
3. Remove `MODEL-POLICY.md` and `ROUTING-MATRIX.md` only if no project content depends on them.
4. Restore your backup if that is safer than a manual reversal.
5. Do not delete the entire `.claude/` directory if it contains other agents, settings, commands, or hooks.
6. Restart Claude Code and confirm the removed agents are no longer discovered.
