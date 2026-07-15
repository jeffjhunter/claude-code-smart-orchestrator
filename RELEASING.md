# Releasing

Run all checks from the repository root before building a release:

```powershell
python -I starter/scripts/validate_kit.py
python -m unittest discover -s starter/tests -v
python -m unittest discover -s tests -v
python scripts/build_release.py
python scripts/verify_release.py
```

`scripts/build_release.py` packages two exact audience allowlists, normalizes
text to UTF-8 with LF endings, scans packaged text for secret-like material,
hydrates copy-ready team links, snapshots source bytes once, and writes
deterministic stored ZIP members. It rejects
unexpected files, sensitive extensions, backups, symbolic links, missing
required files, and invalid text. Each file is staged and flushed before
publication. A build lock prevents concurrent writers, ordinary publication
errors roll back to the last byte-for-byte output set, and a commit marker is
replaced last so interrupted multi-file publication fails closed. Outputs are:

- `dist/Claude-Code-Smart-Orchestrator-Giveaway-v<VERSION>.zip`
- `dist/Claude-Code-Smart-Orchestrator-Team-Assets-v<VERSION>.zip`
- `dist/MANIFEST-GIVEAWAY.json`, with each Giveaway file's size and SHA-256
- `dist/MANIFEST-TEAM-ASSETS.json`, with each Team Assets file's size and SHA-256
- `dist/SHA256SUMS.txt`, with both archive hashes
- `dist/RELEASE-COMMIT.json`, binding both archives, both manifests, and the
  checksum by name, size, order, and SHA-256

## GitHub release assets

Upload only these two files to the public GitHub release:

- `Claude-Code-Smart-Orchestrator-Giveaway-v<VERSION>.zip`
- `Claude-Code-Smart-Orchestrator-Team-Assets-v<VERSION>.zip`

The manifests, checksum, and commit marker are build and verification sidecars.
Do not upload them as separate release assets. Put the two archive hashes in the
release notes instead. This keeps the public release page limited to the two
audiences the team actually uses.

Each extracted archive contains its own embedded `MANIFEST.json`. The Giveaway
archive must contain only consumer resources. The Team Assets archive must
contain only launch and delivery assets plus generated links. Tests fail if
the audiences are mixed or a placeholder survives packaging.

`scripts/verify_release.py` reconstructs both canonical archives from the
trusted checkout and requires exact byte matches. It also checks strict
manifest and commit-marker schemas, exact member order, modes, comments, extra
fields and other ZIP metadata, the exact checksum bytes, asset headers, and
secret scanning. It runs both unit-test suites from this trusted checkout.

Build twice without source changes and confirm that every file in `dist/` is
unchanged. Inspect the PDF and PNG before publishing. Extract both archives and
confirm that only the Giveaway ZIP is suitable for leads. Runtime routing tests are
separate from this static release process; follow `starter/TEST-PROMPTS.md` and
retain only redacted evidence.

For the optional Fable route, record direct model availability and delegated
subagent routing as two separate checks. A successful `--model fable`
preflight must not be described as a successful `@agent-fable-planner` run.
Publish a delegated-route claim only after a complete, attributable Agent
lifecycle reports the expected Fable model family and the task outcome passes
its acceptance checks. If that evidence is missing, label the route opt-in and
retain the documented Opus fallback.

For a public GitHub repository, enable private vulnerability reporting under
the repository security settings before announcing the release. Confirm that
the absolute repository link in `SECURITY.md` opens its private report form.

The verifier is deliberately **not** a general untrusted-ZIP sandbox or an
external signature check. Use it for an archive built from the checkout you
already trust. Establish release provenance through the hosting platform and
do not extract or execute an independently supplied archive merely because it
passes a checksum supplied beside it.
