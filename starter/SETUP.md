# Setup

## 1. Copy the starter files

Copy `CLAUDE.md` and the `.claude/` directory into the root of a Claude Code project.

Expected structure:

```text
project-root/
├── CLAUDE.md
└── .claude/
    └── agents/
        ├── architect.md
        ├── deep-reasoner.md
        ├── fast-worker.md
        └── qa-reviewer.md
```

## 2. Start Claude Code in the project

```bash
cd path/to/project
claude
```

If `.claude/agents/` did not exist when the current session started, restart Claude Code after creating it.

## 3. Confirm discovery

Ask:

```text
Which project subagents are available, and what is each one for?
```

## 4. Run a safe first test

Ask:

```text
Use the architect agent to inspect this project and propose one small improvement. Do not edit files.
```

Then test the implementation and review sequence on a disposable branch or small sample project.

## 5. Customize deliberately

- Tighten each agent's `tools` list for your environment.
- Keep `model: inherit` for portability, or choose a supported alias in your own private copy.
- Add project-specific commands and conventions to `CLAUDE.md`.
- Check these files into version control if the whole team should share them.

## Safety notes

- Review commands before approving them.
- Run the first tests in a disposable branch or sample project.
- Do not give read-only agents Edit or Write unless their role truly changes.
- Keep `Agent` out of agent tool lists if you do not want nested delegation.
