# Task routing matrix

| Work type | Primary route | Configured target | Next route | Verification |
|---|---|---|---|---|
| Small, obvious edit | `fast-worker` | Haiku, low | none | Parent or `qa-reviewer` |
| Multi-file feature | `architect` | Opus, high | `fast-worker` | `qa-reviewer` |
| Difficult bug or unclear failure | `deep-reasoner` | Opus, xhigh | `fast-worker` | `qa-reviewer` |
| Architecture or interface decision | `architect` | Opus, high | `deep-reasoner` only if consequence is high | Parent or `qa-reviewer` |
| Boilerplate or repetitive refactor | `fast-worker` | Haiku, low | none | `qa-reviewer` when risk justifies it |
| Security-sensitive change | `architect` | Opus, high | `deep-reasoner`, then `fast-worker` | `qa-reviewer` |
| Read-only design audit | `architect` | Opus, high | none | Parent synthesis |
| Read-only compliance audit | `qa-reviewer` | Sonnet, high | `architect` if redesign is needed | Parent synthesis |
| High-volume failure analysis | `deep-reasoner` | Opus, xhigh | `fast-worker` if the fix is clear | `qa-reviewer` |

## Route by consequence

Use high or xhigh reasoning when a wrong decision would be expensive, dangerous, or difficult to reverse. Use the worker when the assignment is already bounded. Keep orchestration in the parent conversation so one place owns scope and sequencing.

The configured target is not runtime proof. Aliases may be overridden or unavailable, and `CLAUDE.md` cannot force automatic routing. Use a direct `@agent-*` mention for deterministic invocation tests, then confirm the observed agent and model in the Claude task UI or stream JSON output. See `MODEL-POLICY.md`.
