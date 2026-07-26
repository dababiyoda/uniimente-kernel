# Package 1 — Canonical Core Release Candidate

Evidence package produced under the three-pass founder protocol, **corrected** by the
core-versus-venture boundary ruling: *UNIIMENTE may create and govern ventures. No
venture may define UNIIMENTE.*

Package 1 produces **one trustworthy UNIIMENTE core line**. It does not merge, deploy,
activate a venture, or create any external effect.

| # | Deliverable | File |
|---|---|---|
| 1 | Archive of main | branch `archive/main-2026-07-19` — see deviation in `05-rollback.md` |
| 2 | Release candidate | branch `release/canonical-v1` |
| 3 | Baseline CI | `.github/workflows/canonical-ci.yml` + `scripts/ci/` |
| 4 | Two clean CI records | recorded on the draft pull request |
| 5 | Candidate vs archived main | `01-comparison.md` |
| 6 | Authority-duplication report | `02-authority-duplication.md` |
| 7 | Core-versus-venture boundary | `03-core-venture-boundary.md`, `boundary.json` |
| 8 | Contract inventory | `04-contract-inventory.md` |
| 9 | Rollback instructions | `05-rollback.md` |
| 10 | Draft pull request | opened against `main`, not merged |

## The three findings that matter

**The candidate strictly contains main.** 80 commits ahead, 0 behind, 0 files deleted.

**There is exactly one source of authority.** One Constitution, one Consequence Gate, one
authority matrix, one legal-principal registry, two identity registries each singular. None
of the ten integration-only directories defines authority of its own. This was Pass 2's
decisive open question; it is now closed by evidence.

**The core is not yet venture-neutral.** Four contamination points are named in
`03-core-venture-boundary.md`. None is in the Constitution, gate, identity, authority,
events, provenance, or memory. None is remediated in Package 1.

## What was deliberately excluded

No IVIO contracts. No PR #45, #42, #44, #35, #26 integration. No historical PR closed.
No contract decisions. No remediation of the four contamination points. `main` untouched.
