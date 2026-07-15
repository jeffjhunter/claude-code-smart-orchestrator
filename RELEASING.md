# Releasing

Run all checks from the repository root before building a release:

```powershell
python -I starter/scripts/validate_kit.py
python -m unittest discover -s starter/tests -v
python -m unittest discover -s tests -v
python scripts/build_release.py
python scripts/verify_release.py
```

`scripts/build_release.py` packages an exact allowlist, normalizes text to
UTF-8 with LF endings, scans packaged text for secret-like material, snapshots
source bytes once, and writes deterministic stored ZIP members. It rejects
unexpected files, sensitive extensions, backups, symbolic links, missing
required files, and invalid text. Each file is staged and flushed before
publication. A build lock prevents concurrent writers, ordinary publication
errors roll back to the last byte-for-byte output set, and a commit marker is
replaced last so interrupted multi-file publication fails closed. Outputs are:

- `dist/Claude-Code-Smart-Orchestrator-Full-Kit-v<VERSION>.zip`
- `dist/MANIFEST.json`, with each packaged file's size and SHA-256
- `dist/SHA256SUMS.txt`, with the archive SHA-256
- `dist/RELEASE-COMMIT.json`, binding all three outputs above by name, size,
  order, and SHA-256

An extracted release contains its embedded `MANIFEST.json` at the package
root. The builder excludes that generated file only when its bytes exactly
match the canonical manifest for the current package; a stale or injected root
manifest fails the build.

`scripts/verify_release.py` reconstructs the one canonical archive from the
trusted checkout and requires an exact byte match. It also checks strict
manifest and commit-marker schemas, exact member order, modes, comments, extra
fields and other ZIP metadata, the exact checksum bytes, asset headers, and
secret scanning. It runs both unit-test suites from this trusted checkout.

Build twice without source changes and confirm that `SHA256SUMS.txt` is
unchanged. Inspect the PDF and PNG before publishing. Runtime routing tests are
separate from this static release process; follow `starter/TEST-PROMPTS.md` and
retain only redacted evidence.

For a public GitHub repository, enable private vulnerability reporting under
the repository security settings before announcing the release. Confirm that
the absolute repository link in `SECURITY.md` opens its private report form.

The verifier is deliberately **not** a general untrusted-ZIP sandbox or an
external signature check. Use it for an archive built from the checkout you
already trust. Establish release provenance through the hosting platform and
do not extract or execute an independently supplied archive merely because it
passes a checksum supplied beside it.
