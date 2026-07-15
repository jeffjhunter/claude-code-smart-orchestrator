# Test prompts

## Discovery test

```text
List the project subagents available in this repository. For each one, explain when you would and would not use it.
```

## Planning test

```text
Use the architect agent to inspect this project and create a plan for adding a health-check endpoint. Do not edit files. Include exact paths and verification commands.
```

## Reasoning test

```text
Use the deep-reasoner agent to investigate why the slowest test takes much longer than the others. Gather evidence, but do not edit files.
```

## Bounded implementation test

```text
Use the fast-worker agent to update only README.md with a short local-development section. Run any relevant formatting check and report the exact file changed.
```

## Independent review test

```text
Use the qa-reviewer agent to verify the README change against the request. Do not edit files. Return PASS, PASS WITH WARNINGS, or FAIL with evidence.
```

## Full sequence test

```text
For this small feature, use architect first, fast-worker second, and qa-reviewer last. Keep each assignment bounded. Do not let agents delegate further. Report the evidence from each stage.
```
