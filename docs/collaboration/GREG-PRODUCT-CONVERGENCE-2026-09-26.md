# GREG product convergence — 2026-09-26

Decision: **EXPERIMENT** (draft PR; merge, founder enrollment and any live credential remain founder decisions).
Advances: `INTENT-2026-09-25-EGREGORE-ECOLOGY`, `INTENT-2026-09-25-SPIDER-WEB-COMPOUNDING`,
`INTENT-2026-09-22-FIRST-BODY`, `INTENT-GREG-EMBODIED-2026-09-11`, `INTENT-0030`. No new intent: the
2026-09-26 directive restates the 09-25 source verbatim plus the build directive; both are already recorded.

## Founder-effect compilation

| Founder expression | Observable effect built | Metaphor, not requirement |
|---|---|---|
| "one persistent mind/interface" | one console + one signed inbox + one ledger; any interface can close | a persona |
| "absorb future technology" | capability registry + model routes behind one planner interface, clamped | a new model |
| "morphogenesis / capability genesis" | missing function -> coding agent -> held-out oracle -> isolated runtime -> signed attach -> original mission resumes | cells, tissues |
| "survival mechanisms preserve continuity" | torn-write quarantine, idempotent facts, reads while running, supervisor restart | a right to survive (none: shutdown wins) |
| "helps its community" | brief reads public PR data as untrusted text; changes nothing | autonomous outreach |

Falsifiers: a torn ledger bricks the body; a restart duplicates an effect or crash-loops; the console
writes anything but signed commands; a model draft widens authority or reaches the founder unvetted;
built code runs inside the body, sees held-out vectors, or attaches without the signed rule; a
delivered brief differs from the render of its receipted inputs yet is VERIFIED.

## Selection among competing implementations

| Concern | A | B | Selected | Why |
|---|---|---|---|---|
| Body / mission truth | #113 `greg/` (Ed25519, general missions, supervisor) | #112 finite per-mission host, synthetic authority | #113 | real founder authentication; general contract |
| Interface | #113 CLI only | #112 loopback page | recombined: #112's Host/CSRF page driving #113's signed inbox | one surface, no synthetic authority |
| Useful mission | #113 note in own workspace | #112 source-bound repo brief | recombined into `brief.engineering` (+ GitHub, + appraiser byte-compare) | useful to Alfonso, provable |
| Resume authority | hash-shaped evidence accepted | #112 grant through the Gate | #112 | security fix |
| Learning guard | — | #112 strict held-out gain | reused as Genesis acceptance principle | same invariant, higher-stakes use |

## Alternatives

| Alternative | Benefit | Liability | Disposition |
|---|---|---|---|
| Do nothing (leave #112/#113 parallel) | no risk | two GREGs, no useful mission, two latent crash loops | rejected |
| Simplest: merge #113 only | smallest diff | torn-write brick, EventError crash loop, `morning` fails while running, no interface | rejected (defects reproduced) |
| Hosted agent product as the interface | fast | second authority plane; closes with the tab | rejected; models used only as proposers/builders |
| Builder with filesystem tools in a sandbox | richer builds | wider escape surface | deferred; source-only builder is enough for the contract class |
| Proposed (this PR) | one path, real capabilities, real genesis | more surface to review | EXPERIMENT |

## Five roles

- **Builder:** every addition is on the running path and is measured by the supervised product test and two LOCAL-REAL runs.
- **Adversary:** the planner's first live draft was schema-valid and unrunnable — caught only after adding semantic vetting; overfit and escape candidates are refused; a hostile model can still propose a *plausible but useless* read-only mission (bounded: read-only, $0, founder signs).
- **Operator:** `greg console`, `greg vepmc`, one runbook; ledger append is O(n) (measured 108 ms at 10k records) — acceptable for months, a known ceiling.
- **Beneficiary:** the brief answers "what needs my decision" in five lines on real data (one failing check, three idle-PR clusters, one dirty checkout).
- **Constitutional:** no new authority source; the console signs only what the founder clicks; built code never inherits the body's keys, ledger or grants; building ≠ attaching.

## Pass 1 — structural inversion

- Proof advantage → the brief is a pure function of receipted inputs, so the appraiser re-renders and byte-compares. Reverses if a source is non-deterministic at render time (none is; time is an input).
- Genesis advantage → held-out vectors give a real acceptance test for generated code. Reverses when the founder's contract is under-specified; mitigated by requiring ≥ 3 held-out vectors and a signed budget.
- Disadvantage: the planner could drift into a second decision-maker. Converted into a constraint: it can only emit proposals the founder signs, clamped to read-only.
- Disadvantage: the tail policy weakens a fail-closed default. Bounded: default unchanged; only the body's writer quarantines, only an unterminated final line, bytes preserved.

## Pass 2 — adversarial compounding

- New risk: repeated daily briefs reuse one approved scope forever. Accepted: the scope is exact (same params, same delivery root) and the mission horizon ends it (30 days); owner Alfonso; kill if a brief ever writes outside `deliver:briefs`.
- New risk: builder cost. Bounded by the signed `build_budget_usd` inside the cone; each spend is ledgered (`genesis.built.cost_usd`).
- New risk: Linux isolation is network-only; built code could read user-readable files. Bounded by the static screen and restricted builtins; on macOS `sandbox-exec` also applies. Kill if any built capability is observed reading outside its input.
- Every Pass-1 downside is resolved, bounded with an owner, or a kill condition above.

## Unresolved dissent

1. A signature proves key possession, not presence (unchanged from #113).
2. REBOOT-VERIFIED is not claimed: power loss was simulated by a torn write under SIGSTOP/SIGKILL.
3. The template planner is narrow; broad requests need a model route, which needs an API key or Claude Code on the Mac.
4. ~~Phone access is not built.~~ Superseded: the base branch added the phone channel (device keys delegated by the founder key, `greg serve`); exercised in Chromium with an iPhone profile, not iOS Safari.

## Kill criteria

Any falsifier above observed; any built or planned artifact executing with authority it was not signed; VEPMC still 0 after Alfonso runs `greg/FIRST_MISSION.md` on the Mac (then the defect is in the product path, not the doctrine).

## Pass 2 of this PR — self-repair and provider-independent models (founder steering on #114, 2026-09-26)

Controlling source: `INTENT-2026-09-26-REAL-PRODUCT-METABOLISM` ("BUILD THE MACHINE ALFONSO ACTUALLY MEANS.",
"Do not return with another cathedral.") and the founder's #114 comment naming the next deltas: "missing-function
detector -> Genesis self-repair; provider-independent OpenAI/Anthropic model router; coding-agent builder with frozen
tests and bounded authority".

### Context Reconstruction Packet
- **Inspected:** the founder's four #114 comments; `INTENT-2026-09-26-REAL-PRODUCT-METABOLISM` and its verbatim source;
  `PROJECT_COGNITION_SOP.md`; the source census (as an index; the 93 raw Project files are not in the repository);
  `.github/PULL_REQUEST_TEMPLATE.md`; `greg/genesis.py`, `missions.py`, `authority.py`, `builders.py`, `planner.py`,
  `service.py`, `body.py`; base commits `40d3bdc` and `25ab9b4` (#116).
- **Unavailable:** the raw ChatGPT Project conversations; RailScout code (`dababiyoda/RAILSCOUT` is outside this
  session's repository scope). The RailScout adapter seam is left to its own PR, as the founder's comment allows.
- **Reproduced before fixing:** (1) a quarantined built capability made every later tick raise
  `EventError: fact identity greg.deficit.opened reused with different content`, so a supervised body would have
  crash-looped; (2) a built capability that raised on live input was only ever escalated to the founder; (3) a
  repair's build could spend past the signed budget (checked once, then two attempts); (4) the installed service
  (`launchd`/`systemd`/`supervisord`) always ran without a builder, so the persistent body could never build.
- **Contradiction resolved:** "stop experimenting / stop simulating" vs. verification. Resolved per the intent record:
  every change here is product code on the running path; tests are evidence around it.

### Product delta
GREG can now (a) notice that a capability it formed is broken in service and re-form it without asking, then keep
holding the original mission's setpoint; (b) reach models from any vendor it has a key for, failing over on outages
while never shopping a refusal; (c) build and repair from the installed background service.

### Repository metabolism
| Artifact | Disposition | Why |
|---|---|---|
| `planner.AnthropicTransport` / `planner.ClaudeCodeTransport` | RECOMBINE into `greg/models.py` routes; kept as compatibility shims | two hand-rolled transports duplicated vendor code; one router now serves planner and builder |
| `genesis` deficit id = hash(mission, function) | EXTRACT (per-incident generations) | the invariant (one identity per deficit) was right; the scope (one per function forever) caused the crash loop |
| PR #70 verified-deficit record | PRODUCTIZE (unchanged, now also on repair deficits) | the three-fact verification applies to a lost function as much as to a missing one |

### Falsifiers
Self-repair: a repaired capability that fails the frozen oracle or the live replay is attached; the builder sees the
live input or held-out vectors; total build spend for a function exceeds its signed `build_budget_usd` by more than
one route-bounded attempt; a repair escalates when the rebuild succeeds. Router: a refusal is followed by a call to
another route; an unpriced route is called with money at stake; a draft or built capability names a route other
than the one that produced it.

### Evidence tier
TESTED on the product path (real `Body`, real ledger and journal, built code in real isolated interpreters). The model
SDKs are faked with their documented call shapes; no live key was used, and a live OpenAI or Anthropic API route
awaits Alfonso's own credentials. VEPMC unchanged at 0.
