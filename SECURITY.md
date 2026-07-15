# Security policy

## Supported version

Security fixes are applied to the current 2.0.x kit. Older copies should be upgraded and revalidated before use.

## Reporting a vulnerability

Do not post credentials, private traces, exploit details, or sensitive
repository content in a public issue, discussion, or pull request.

Use GitHub's [private vulnerability reporting
form](https://github.com/jeffjhunter/codex-model-router-optimization/security/advisories/new)
for the preferred confidential route. Private reporting is enabled for the
project's public repository. Include the affected version, file, reproduction
steps, impact, and a redacted proof.

If that form is unavailable, use the maintainer's [contact
page](https://jeffjhunter.com/connect) to request a secure contact method. In
that first message, include only the project name and your contact information;
do not include credentials, exploit details, traces, or private source. If
the project has not yet been published or the GitHub form is not enabled, use
this same no-details fallback. If neither route works, wait for a private
channel rather than opening a public security issue.

## Security boundaries

- Agent prompts, tool lists, and permission modes reduce accidental scope; they are not a sandbox.
- Parent permissions and user approvals can broaden an agent's effective access.
- Bash and PowerShell commands can write files, change state, access the network, or expose environment data.
- A behaviorally read-only QA agent can still create test caches, snapshots, coverage output, lockfiles, or other artifacts through shell commands.
- Model aliases and automatic routing must not be treated as access-control mechanisms.
- `SubagentStart` and `SubagentStop` hooks are optional and are not installed by this kit. Review hook commands, inputs, outputs, and retention before enabling them.
- Runtime traces and hook logs can contain prompts, paths, source content, identifiers, and tokens. Redact them before sharing.

Run unknown projects in an isolated environment, review commands before approval, use least-privilege credentials, and inspect `.claude/` recursively before trusting an installation. The bundled validator is a static safety check, not a guarantee that runtime behavior is safe.

PyYAML is needed for the validation and release tooling. Keep Python and dependencies updated through your normal security process.

The release manifest, exact agent-body hashes, and local validator are tamper-evidence relative to the files in the same checkout. They are not a digital signature. Establish repository and release provenance through your hosting platform before trusting an independently downloaded archive.
