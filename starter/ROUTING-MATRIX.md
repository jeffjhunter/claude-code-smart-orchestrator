# Task routing matrix

| Work type | First route | Next route | Verification |
|---|---|---|---|
| Small, obvious edit | fast-worker | none | qa-reviewer |
| Multi-file feature | architect | fast-worker | qa-reviewer |
| Difficult bug or unclear failure | deep-reasoner | fast-worker | qa-reviewer |
| Architecture or interface decision | architect | deep-reasoner only if risk is high | qa-reviewer |
| Boilerplate, formatting, repetitive refactor | fast-worker | none | qa-reviewer |
| Security-sensitive change | architect | deep-reasoner, then fast-worker | qa-reviewer |
| Read-only compliance audit | qa-reviewer | architect if redesign is needed | main conversation |
| High-volume logs or test output | deep-reasoner or qa-reviewer | fast-worker if a fix is clear | qa-reviewer |

## Route by consequence, not novelty

Use deep reasoning when a wrong decision would be expensive, hard to reverse, or dangerous. Use the implementation agent when the task is already well specified. Keep orchestration in the main conversation so one place owns scope, ordering, and final synthesis.
