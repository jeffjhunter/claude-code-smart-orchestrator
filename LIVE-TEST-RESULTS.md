# Live routing test results

Tested on 2026-07-14 with Claude Code 2.1.210 in a disposable Git repository.
Each run explicitly requested exactly one project subagent through the Agent
tool, used project-only settings, disabled session persistence, emitted
stream JSON, and set a USD 0.75 maximum budget.

## Accepted v2 runs

| Agent | Configured route | Observed model metadata | Events | Task outcome | CLI-reported cost |
|---|---|---|---:|---|---:|
| `architect` | Opus, high, plan | `claude-opus-4-8` | 19 | Read-only architecture probe completed | USD 0.18913975 |
| `deep-reasoner` | Opus, xhigh, plan | `claude-opus-4-8` | 22 | Read-only evidence analysis completed | USD 0.18881375 |
| `fast-worker` | Haiku, low, default | `claude-haiku-4-5-20251001` | 34 | Exact disposable file content created and verified | USD 0.17055520 |
| `qa-reviewer` | Sonnet, high, default | `claude-sonnet-5` | 22 | Exact unit-test command ran once; verdict PASS | USD 0.19635080 |

The four accepted traces total USD 0.74485950 as reported by this CLI run.
That number is a test observation, not a price quote or savings claim. Context,
cache state, retries, model resolution, provider, and billing policy can change
the result.

For every accepted trace, `verify_runtime_trace.py` found exactly one expected
Agent call, linked child-assistant model metadata from one model family, and one
successful final result event. The task acceptance outcome was reviewed
separately; a successful parent result alone does not prove that acceptance
criteria passed.

The recorded traces establish observed model metadata, not effective effort.
Effort values in the table are the frontmatter policy used for the run and can
be overridden or adjusted for model support.

## Defect found and corrected

The first QA run used `permissionMode: plan`. It resolved to Sonnet, but the
mode blocked the supplied unit-test command. That run also attempted two
unapproved no-op command variants, so it did not satisfy the QA contract.

The release changes QA to `permissionMode: default` while keeping no Edit or
Write tools and a prompt contract that requires the exact supplied command
first and forbids variants. With the parent session explicitly allowing the
verification tools, the corrected QA run used one Bash call containing exactly:

```text
python -m unittest discover -s tests -v
```

The command ran one test with zero failures and QA returned PASS. Default mode
does not silently grant shell access; user, organization, and session policy
still apply. Shell checks can also create artifacts, so QA remains
behaviorally non-editing rather than sandboxed read-only.

## Evidence handling

Raw traces are intentionally excluded from the public archive because they can
contain prompts, local paths, source excerpts, usage data, and signed response
metadata. The local audit traces had these SHA-256 digests at review time:

- Architect: `E262F6CEF8F7E1B54125DE8B3861103FDC37BC05BECA8555F8AEA7C3A22C4808`
- Deep Reasoner: `2F1BD7905B1B2FD2BB21E0AC8FF3B1EC3BD078BEBA038E6129DD13279164585E`
- Fast Worker: `54D2FDA60FE92F3097F0A8922773ACBC17EEB0586210C22BFC25A8434547E9C2`
- Corrected QA: `628DF6F1D22643596A9327F3116F4B022163BCF94FCB150AF80E0B970E93C474`
- Blocked QA discovery run: `DCE2D6204B48CB5B40B24D03A65A893AAFD735AB4756651420BF85662394FCB5`

Trace metadata is observed evidence, not cryptographic proof of remote model
execution. Re-run the probes in your own account and environment before making
deployment, security, quality, latency, or cost claims.
