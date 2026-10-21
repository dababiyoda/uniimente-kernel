# PR #113 → #114 supersession accounting (mechanism level)

Founder direction (2026-09-26, comment on #113): #114 is the product-convergence descendant;
#113 stays as substrate and must not become a second canonical future beside it. Canonical
issue: #117. VEPMC remains 0 until founder-owned Mac proof.

#114 (`claude/greg-persistent-mission-build-t0vqu7`) was branched from #113 at `7c34b70`, so
every #113 mechanism up to that commit is already in #114 as the same Git objects. This record
covers only what #113 gained after `7c34b70`.

## #113-only commits

| Commit | Mechanism | State in #114 at `4179749` | Disposition |
|---|---|---|---|
| `25ab9b4` (via `337118f`, main hotfix #116) | Standing-cognition resume needs a Gate on the same ledger and a pre-existing exact-suspension grant | `egregore/runtime.py` already carries the same fix (ported earlier from #112). Only the test file name and its `ROOT` import differ. | **CARRY**: test moves to `tests/unit/test_resume_authority.py` (main's name) with #114's extra cases kept |
| `40d3bdc` | A signed `BODY_STOP` persists as the STOP file plus `greg.body.stop_persisted`; restart cannot resume missions until a human runs `greg start --local`; an OS SIGTERM is not persisted | **Missing.** #114 honours a STOP file that a person creates, but a signed founder stop from the phone or console lives only in process memory, so a reboot or `launchctl kickstart` resumes work. | **CARRY (safety)** |
| `40d3bdc` | `PR112-SUPERSESSION.md` and the #112 metabolism entry | Missing. | **CARRY, corrected below** |

## Trial merge evidence

`git merge --no-ff origin/claude/egregore-project-overview-btn5y2` into `4179749`, in a scratch
worktree, on 2026-09-26: no conflicts; 7 files; full suite `862 passed, 6 skipped`. Nothing was
pushed to the #114 branch; that branch belongs to another active session.

## Corrections to the #112 record on the #114 line

`PR112-SUPERSESSION.md` was written against #113. #114 changed three of its dispositions:

| #112 mechanism | #113 record said | On the #114 line |
|---|---|---|
| 10 loopback console | REPLACED by `greg serve` + phone; console retained only as evidence | **PORTED as `greg/console.py`** (port 8766), which signs with the founder key held in memory. It sits beside the phone channel (8765, delegated device key). Both write founder-signed envelopes into one body inbox, so this is two transports over one authority path, not two authorities. |
| 10–11 `egregore/local_console.py`, `development_session.py` | not active | **Still active in #114**: `tests/unit/test_greg_console.py`, `tests/greg_acceptance_driver.py` and `docs/GREG_LOCAL_START.md` drive them. `GREG_LOCAL_START.md` tells the founder to start the synthetic-authority console. **Duplicate active founder path.** Recommended: take the synthetic-authority `egregore.local_console` out of active founder instructions; keep its modules, tests and the document as historical provenance. |
| 12 brief "what changed" | gap | **PORTED as `greg/briefs.py`** (source-bound morning brief, appraiser re-renders and byte-compares). |
| 13 held-out gate `brief_learning.compare` | not ported as code | Imported by the #114 resume-authority test; the module is present. Still recorded as the admission rule for future learned changes. |

## Residuals on the #114 line

1. Persisted founder stop (above), until #113's head is merged into #114.
2. The synthetic `egregore.local_console` founder path is still advertised.

**Founder correction (2026-09-26).** `greg/FIRST_MISSION.md` is the founder-owned first-mission,
onboarding and VEPMC acceptance runbook. It is not meant to be GREG's only permanent entry point.
The product is Alfonso ↔ GREG: one persistent GREG identity with several authenticated surfaces
(`greg console`, the phone channel, the CLI). They coexist because each writes founder-signed
envelopes into the same inbox, so none is a separate authority. Only the synthetic-authority
`egregore.local_console` leaves active founder instructions.
3. Model cognition is Anthropic-only (`greg/planner.py`: `AnthropicTransport`, `ClaudeCodeTransport`).
   The founder asked for provider-independent OpenAI and Anthropic routing with health, capability,
   cost, latency, task suitability, fallback and model provenance. This is the next product
   residual and belongs in #114's planner/builder seam, not in a parallel #113 module.

## Decision

#113 accrues no further product work. Its remaining value reaches #114 by one merge of #113's
head into #114's branch. After that, #113 is kept open only as #114's base until #114 is
retargeted to `main`, then closed as superseded. Its branch and history are not deleted.

## Residual status on #114 (2026-09-26, after merging #113 head `51c1374`)

1. Persisted founder stop — **carried** by the merge of `40d3bdc`; full suite green on the merged tree.
2. Synthetic `egregore.local_console` founder path — **removed from active founder instructions**:
   `docs/GREG_LOCAL_START.md` now opens with a supersession notice; modules, tests and the page stay as provenance.
3. Anthropic-only model cognition — **closed for vendors, partial for scoring**: `greg/models.py` routes planner
   and builder across the Anthropic API, the OpenAI Responses API and Claude Code with failover, demotion and
   cooldown, ledgered route health, budget-bounded spend and true-author provenance; refusals are never shopped.
   Not yet scored: latency and task suitability (routing is preference order plus health). Live API routes
   await Alfonso's own keys; tests use SDK-shaped fakes.
