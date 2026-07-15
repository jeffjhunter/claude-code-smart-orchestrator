# Releasing

Run all checks from the repository root before building a release:

```powershell
python -I starter/scripts/validate_kit.py
python -m unittest discover -s starter/tests -v
python -m unittest discover -s tests -v
python scripts/build_release.py
python scripts/verify_release.py
```

The output directory is an exact inventory. Before the first build after a
`VERSION` change, remove the previous `dist/` directory. The builder and
verifier intentionally fail if a stale archive, sidecar, temporary file, or
other unexpected entry is present. This prevents obsolete Full Kit artifacts
from being uploaded alongside the public Giveaway.

`scripts/build_release.py` packages one exact public allowlist, normalizes
text to UTF-8 with LF endings, scans packaged text for secret-like material,
snapshots source bytes once, and writes deterministic stored ZIP members. It rejects
unexpected files, sensitive extensions, backups, symbolic links, missing
required files, and invalid text. Each file is staged and flushed before
publication. A build lock prevents concurrent writers, ordinary publication
errors roll back to the last byte-for-byte output set, and a commit marker is
replaced last so interrupted multi-file publication fails closed. Outputs are:

- `dist/Claude-Code-Smart-Orchestrator-Giveaway-v<VERSION>.zip`
- `dist/MANIFEST.json`, with each Giveaway file's size and SHA-256
- `dist/SHA256SUMS.txt`, with the public archive hash
- `dist/RELEASE-COMMIT.json`, binding the archive, manifest, and checksum by
  name, size, order, and SHA-256

## GitHub release assets

Upload only this file to the public GitHub release:

- `Claude-Code-Smart-Orchestrator-Giveaway-v<VERSION>.zip`

The manifests, checksum, and commit marker are build and verification sidecars.
Do not upload them as separate release assets. Put the archive hash in the
release notes. Never upload internal launch, delivery, automation, or
promotional materials to this public repository or its releases.

The extracted Giveaway contains its embedded `MANIFEST.json` and only public
consumer resources. Tests fail if repository tooling or internal materials are
added to the package.

`scripts/verify_release.py` reconstructs the canonical public archive from the
trusted checkout and requires an exact byte match. It also checks strict
manifest and commit-marker schemas, exact member order, modes, comments, extra
fields and other ZIP metadata, the exact checksum bytes, asset headers, and
secret scanning. It runs both unit-test suites from this trusted checkout.

Build twice without source changes and confirm that every file in `dist/` is
unchanged. Inspect the PDF and public README image before publishing. Extract
the Giveaway and confirm that it contains only public resources. Runtime routing tests are
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
