# Handoff — founder rulings of 2026-08-22, as implemented

For Kimi, ChatGPT, and whoever picks this up next. Branch
`claude/opus-maximus-audit-eay0ek`, PR #71.

The owner field is work-routing metadata, not territorial ownership. Nothing
below is reserved; take any of it.

---

## State of the build

```
python -m pytest                    1169 passed, 0 failed
python verifier/v2/verify.py        PASS (V1–V5)
python -m handoff.conform           CONFORMANT, seal fe155604…, 26/26
python -m governance.gap_audit      14 machine-checked, 14 verified open, 0 stale
python -m governance.decisions      AWAITING_FOUNDER=0  AUTHORIZED=4
python -m bridges.closure_verdict   FALSELY_CLOSED (all 7 loops)
clean_verified_outcomes             0
```

The last two lines are the ones that matter. Nothing in this work moved them and
nothing was supposed to.

Before: 22 failing tests (the CONTRADICTION-0001 set plus two governance
guards). After: none.

---

## What landed, ruling by ruling

| Ruling | State | Where |
|---|---|---|
| 1 — DEC-OM-002 frozen corpus | **done** | `docs/release/package-3/AMENDMENT-001-frozen-corpus.md` |
| 2 — #7/#26 asymmetric identity | **done, not adopted** | `identity/pki/` |
| 3 — D-001 + G-001 migration | **contract done, emission blocked** | `provenance/witness_v2.py` |
| 4 — DEC-OM-001 canonical router | **done** | `capabilities/implementations.py`, `capabilities/instantiate.py` |
| 5 — DEC-OM-004 inert #31 | **done** | `application/` |
| 6 — recompute the institution | **done, continuous** | ladder, gap audit, closure verdict all re-run |
| 7 — UNIIMENTE Alpha | **long-range** | partially advanced; see below |
| 8 — graduation packet | **done, unexecuted** | `graduation/` |
| 9 — recursive founder-intent rule | **held throughout** | three contradictions raised rather than resolved |

---

## Three things need a founder decision, and nothing proceeds past them

These are the actual frontier. Each is written up with options and a
recommendation; none was decided unilaterally.

**CONTRADICTION-0002 — continuity pins block their own subject.**
`docs/deliberations/CONTRADICTION-0002-continuity-baseline.md`

Twelve files are pinned by SHA-256 inside the sealed Package 3 spec: the five
constitutional documents, the three authority documents, the three identity
registries, and `policy/consequence_gate.py`. The test asserts freeze-time
hashes against **live** files — CONTRADICTION-0001's exact shape, in a location
that covers the Constitution. The institution currently cannot amend its own
constitution without a sealed experiment failing.

This blocks ruling 3 from finishing: emitting witness v2 needs three lines in
the Gate, which is one of the twelve. Recommended: freeze copies as Amendment
001 did, and give "notice unauthorised constitutional change" its own mechanism
under the amendment policy rather than leaving it a side effect of an
experiment's baseline.

**CONTRADICTION-0003 — the confidence floor forbids an honest first canary.**
`docs/deliberations/CONTRADICTION-0003-first-canary-confidence-floor.md`

Found by *running* the graduation rehearsal, not by reading anything. The Gate
refuses CANARY-0001: predicted confidence 0.55 is below the 0.70 floor for
`external_contact`. Both numbers are right. `evidence_confidence` is carrying
two quantities — how well-evidenced the belief that we should act, and how
likely the act is to succeed — which track together for routine actions and are
opposite by construction for a first canary.

The bootstrap: confidence needs calibration, calibration needs external
outcomes, external outcomes need acting externally. Recommended: split the field
(`evidence_confidence` gates, `predicted_success_probability` calibrates) and do
it *now*, while witness v2 is unemitted, so the durable record carries the right
field from its first write instead of needing a v3.

**CANARY-0001 itself.** `python -m graduation.packet` prints the one-screen
decision. Preregistered and sealed; not executed, not authorized.

---

## For ChatGPT

The frozen handoff contract is unmoved: seal `fe155604…` at commit `9916376`,
26/26 conformant. Nothing in this work touched `handoff/`, `runtime/`, or any
Part 2 path.

Two things are now available that were not before:

- **`identity/pki/`** gives you real per-workload identity for the MCP/A2A
  boundary. `mutual_tls` returns a `PeerIdentity` carrying who, which serial,
  valid when, issued by whom — and deliberately nothing about what the peer may
  do. If your boundary envelope needs an authenticated sender, this is it; if it
  needs an *authorised* one, that is still a grant and still the Gate.
- **`application/`** is the inert request/route/render half of #31. If MCP needs
  a request boundary, it can consume this without acquiring a listener. The
  transport half is founder-gated and the kill criterion treats any network
  primitive there as stop-the-line.

The containment tiers (#9, #10, #11) remain the largest ChatGPT-owned gap, and
`#4 Databases` is the highest-leverage frontier item overall at leverage 28 —
it holds five other technologies.

## For Kimi

The gap register is the honest map: `python -m governance.gap_audit`. Fourteen
gaps are machine-checked and all fourteen currently verify as open. The
unchecked 59 are prose, and converting any of them into a machine check is
directly useful work — the check is what stops a gap going stale without anyone
noticing.

Two cautions from this session, both learned the hard way:

- **A proxy check decays exactly when work begins.** The #7/#26 check asked
  whether any module imported an asymmetric primitive. The moment `identity/pki/`
  landed it would have reported both gaps CLOSED while the live transport still
  used one shared key — failing toward "closed", the worse direction. It now
  measures *adoption*. The superseded constant is kept as
  `_SUPERSEDED_ASYMMETRIC_PRIMITIVES` with the reasoning.
- **`evidence_rank` measures evidence strength and is blind to scope.** #31 is
  BUILT and is half a web server. A technology can pass every evidence check and
  still be a fraction of its own name.

## Ruling 7 — what moved toward Alpha, and what did not

Moved: one identity spine (`identity/pki/`, built, unadopted); one durable
contract able to answer *what did we believe, how confident, under what
authority, what exposure* (`provenance/witness_v2.py`, unemitted); a canonical
selector with construction behind the Gate; an application boundary with no
transport.

Did not move: persistent state across restart, the Founder Cockpit, standing
bounded mandates, RailScout as an actual research-refinery runtime.

**Correction, made later in the same session.** An earlier draft of this file
said the peer-repo `KNOWN_IDENTITIES` change was still outstanding on both
mirrors. It is not — both carry `"kernel"` on this branch (DALEOBANKS
`f787963`). The kernel manifests still report it unresolved because they pin
commit `829c5f2`, where the claim was true. That is the commit pin working, not
drift; the manifests update when the peer PRs merge.

Both peers WERE touched, after that correction, and it surfaced a live defect:
`verify_headers` auto-downgraded in all three mirrors, and in WealthMachine the
downgrade reached a live HTTP endpoint — an unsigned POST to
`/api/opportunities/intake` returned `200` whenever `WEALTHMACHINE_SIGNING_KEY`
was unset, while the function's own docstring said "fail closed, never degrade".
Now `401`, with a permanent guard. Four WMI tests were relying on that
permissiveness without saying so; each now opts in explicitly.

Deployment note: if any environment runs that service without a signing key
today, intake will now reject rather than accept. That is intended, and it is a
behaviour change worth knowing before merge.

---

## Session close

`docs/deliberations/SESSION-CLOSE-2026-08-23-continuation-brief.md` carries the
founder-set execution order, the verified end state across all three repos, and
one hazard: routine `trig_01R7tPEGQxM5G2WLaHZH81EN` is stale, could not be
disabled from the session (every trigger tool returned "requires approval"), and
its prompt would instruct a session to restore the 20 failures this work closed.

## Working notes

- **Mutation-test every guard.** A guard never seen to fail is indistinguishable
  from a broken one. Every refusal added this session is paired with a positive
  control, and two guards were rewritten after their mutation test showed they
  did not bite.
- **Structural, never substring.** PR #70's precedent — a substring guard firing
  on `max_subprocesses_per_candidate` — held again: every guard here parses AST.
- **Check sealed artifacts before editing.** Two edits this session were refused
  by the suite for touching pinned files. Both refusals were correct.
- **Run it rather than read it.** CONTRADICTION-0003 was invisible to inspection
  and appeared the first time the rehearsal executed. Three other real defects
  this session surfaced the same way.
