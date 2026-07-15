# Claude Code Smart Orchestrator Kit

## What is in this bundle

- `Claude-Code-Smart-Orchestrator-Kit.pdf`: the complete 19-page guide
- `Claude-Code-Smart-Orchestrator-Infographic.png`: the 1200 x 1500 social graphic
- `social-post.md`: the ready-to-paste launch post
- `starter/CLAUDE.md`: the main project orchestration rules
- `starter/.claude/agents/`: four project subagent templates
- `starter/ROUTING-MATRIX.md`: the quick task-routing reference
- `starter/SETUP.md`: installation and safety instructions
- `starter/TEST-PROMPTS.md`: safe prompts for validating the system
- `starter/scripts/validate_kit.py`: structural validator for the agent files

## Quick installation

1. Open the `starter` folder.
2. Copy `CLAUDE.md` and the `.claude` directory into the root of a sample Claude Code project.
3. Restart Claude Code if `.claude/agents/` did not exist when the current session started.
4. Ask Claude Code which project subagents are available.
5. Test the Architect on a read-only task before allowing file edits.
6. Read `SETUP.md` before adapting the system to a production project.

## Validate the starter

With Python and PyYAML available, run:

```bash
python starter/scripts/validate_kit.py
```

The public templates intentionally use `model: inherit`. Choose model aliases only in your private project and confirm them against the current official Claude Code documentation and your provider plan.

## Responsible use

Review commands before approving them. Test in a disposable branch or sample project. Never place credentials or private data in prompts, agent files, screenshots, or shared logs. Results depend on the project, requirements, configuration, team, and verification process.
