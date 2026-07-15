# Contributing

Thanks for helping make model routing more testable and honest.

## Before opening a change

1. Open an issue for a material route, schema, or permission-policy change.
2. Keep agent assignments bounded; do not add nested delegation or hidden hooks.
3. Update the agent definition, validator profile, documentation, and test
   expectations together.
4. Do not include raw traces, credentials, private paths, proprietary source,
   or signed response metadata in an issue or pull request.

## Local checks

```powershell
python -m pip install -r requirements-dev.txt
python -I starter/scripts/validate_kit.py
python -m unittest discover -s starter/tests -v
python -m py_compile starter/scripts/validate_kit.py starter/scripts/verify_runtime_trace.py scripts/build_release.py scripts/verify_release.py
git diff --check
python scripts/build_release.py
python scripts/verify_release.py
```

When visual policy changes, edit `source/guide.html` and
`source/infographic.svg`, run `scripts/build_visual_assets.ps1`, render every
PDF page, and inspect the final PNG before committing.

## Pull-request expectations

- Explain the problem and why the chosen route or guardrail is appropriate.
- Include tests for both the intended behavior and at least one failure case.
- Separate configured policy from observed runtime claims.
- Report exact commands and outcomes.
- Note security, permission, compatibility, cost, and migration effects.
- Keep unrelated formatting or generated changes out of the pull request.

Report vulnerabilities through the private process in [SECURITY.md](SECURITY.md),
not a public issue, discussion, or pull request. If the private form is
unavailable, use the documented no-details fallback to request a secure channel.
