# FOUNDER RULING — Opus Maximus frontier, 2026-08-22

**Authority:** Alfonso Lopez, founder.
**Scope:** constitutional. Rules on DEC-OM-001, DEC-OM-002, DEC-OM-004,
technologies #7 and #26, GAP-BRIDGE-D-001 and GAP-BRIDGE-G-001, and sets the
standing direction for the remainder of Opus Maximus.
**Reference id:** `FOUNDER-RULING-2026-08-22`

This file exists so that every `authorization_ref` in
`docs/deliberations/*.json` resolves to something a reader can open. The ruling
is reproduced verbatim below. Nothing in it is paraphrased, and where the
implementation departs from a literal reading, the departure is recorded in the
relevant deliberation record rather than by editing this text.

## Authorization boundary, as stated

> You have my approval to perform the internal, reversible, consequence-inert
> work necessary to implement the following rulings and continue Opus Maximus.
> Keep it on branches/draft PRs and preserve provenance. This is not
> authorization to merge to main, publicly deploy, spend money, move funds,
> contact counterparties, publish externally, open public network surfaces, or
> otherwise create a real-world consequence. Those remain separately
> founder-gated.

## Verbatim ruling

> My objective is not to make your branch look finished. My objective is to
> build the complete UNIIMENTE I have described across all sources, chats,
> repositories, Claude work, Kimi work, ChatGPT work, proofs, failures, negative
> results, and unresolved ideas. Treat all of it as one cumulative substrate.
> Preserve founder intent, recombine the strongest mechanisms into one canonical
> institution, eliminate unnecessary duplication, and continuously attack the
> largest remaining verified gap. Do not optimize for preserving any model's
> architecture or authorship. Optimize the whole.
>
> **1. DEC-OM-002 — APPROVE OPTION A.** Apply the frozen-corpus remedy now.
> Package 3 is a historical experiment and must reproduce the institution it
> actually measured. Point the sealed experiment at the byte-identical
> freeze-time corpus already built under evolution/repair/corpus/. Do not change
> the frozen expectation values and do not rewrite the historical evidence.
> Preserve the current live institution separately.
>
> Strengthen Option A so its adversarial weakness is closed: create or retain a
> separate current-institution health check that evaluates the live manifests
> and live linker without pretending the historical expectation of 7 applies
> today. The frozen experiment answers "can I reproduce the historical
> experiment?" The live check answers "is the institution healthy now?" Never
> let one masquerade as the other. Then run the full suite and verify that
> CONTRADICTION-0001 is actually resolved rather than hidden.
>
> **2. Technologies #7 and #26 — RATIFY** isolated service identity and mutually
> authenticated transport. The shared HMAC key is no longer acceptable as the
> institutional trust boundary.
>
> Implement one cryptographically isolated asymmetric workload identity per
> service/organ, with mutual TLS, independent keys, certificate expiry, rotation
> and revocation. Preserve the existing SPIFFE-style identity namespace where
> useful. Start with the smallest sufficient PKI; do not install a giant SPIRE
> infrastructure merely for architectural aesthetics if a smaller implementation
> proves the mechanism.
>
> Identity must remain strictly separate from authority. A valid certificate
> proves which workload is speaking; it does not create a capability, budget,
> approval, role, grant, or execution right.
>
> If legacy HMAC compatibility must temporarily survive, it must be an explicit
> development compatibility mode, fail closed, never auto-downgrade, and never
> be mistaken for mutually isolated identity. Test impersonation, wrong-cert
> identity, expired certs, revoked certs, replay, rotation, downgrade attempts,
> and cross-organ authentication. Then recompute the dependency graph and
> advance only what the evidence actually earns.
>
> **3. GAP-BRIDGE-D-001 + GAP-BRIDGE-G-001 — APPROVE ONE COORDINATED VERSIONED
> SIGNED-CONTRACT MIGRATION.** Do not patch these independently.
>
> Create the smallest coherent next-version durable action/witness contract that
> permanently preserves at least: evidence_confidence, consequence_class,
> effective budget/exposure ceiling, and the applicable authority/grant
> reference. If the exact representation needs a different field layout,
> preserve the semantics.
>
> Old signed records remain historical truth. Do not rewrite them and do not
> fabricate values that were never recorded. Support explicit legacy reading,
> deterministic signing/canonicalization, tamper detection, version negotiation,
> migration tests, downgrade refusal, and causal-memory ingestion. After this
> change the institution must be able to reconstruct: what did we believe, how
> confident were we, under exactly what authority did we act, what exposure was
> permitted, what happened, and were we right?
>
> That is the minimum substrate for real calibration and for learning whether
> authority itself is being allocated intelligently.
>
> **4. DEC-OM-001 — SELECT OPTION A.** routing/decision_router.py is the
> canonical selector. A router decides; it does not instantiate or execute.
>
> Preserve PR #70. Do not discard its useful lifecycle machinery. Rehome
> Implementation.origin, lifecycle states, restore/set-lifecycle behavior, and
> anything else genuinely superior into the canonical capability/module-
> management layer instead of leaving those concerns fused to routing.
>
> Move provider construction/execution downstream to a caller possessing the
> required capability and crossing the Consequence Gate.
>
> Also close the adjacent typing gap if it can be done without creating another
> parallel contract: there should be one canonical typed RoutingDecision
> boundary owned by the Kernel. Organ adapters consume it; they do not copy it.
>
> Later, once real outcomes exist, competing routing implementations may be
> evaluated as challengers. Architectural selection today must not be
> misrepresented as evidence that one router produces better outcomes.
>
> **5. DEC-OM-004 — APPROVE OPTION A.** Build the inert application half of
> technology #31. Build pure typed request parsing, routing and response
> rendering. No listener, socket, bind, public port, outbound connection, HTTP
> client, external contact or hidden network primitive.
>
> Ship the three non-negotiables already identified in the deliberation:
> structural/AST inertness enforcement, explicit gap text saying the
> transport/listener half remains absent and founder-gated, and a kill criterion
> that turns any unauthorized network primitive into a stop-the-line failure.
>
> Do not game the ladder. If this only earns SKETCHED, call it SKETCHED. Its
> value is that it creates a clean application boundary and raises legitimately
> earned headroom—not that we can claim to possess a real web server.
>
> **6.** After applying those decisions, do not stop because "Claude's lane is
> empty." Recompute the WHOLE institution. The owner field is work-routing
> metadata, not territorial ownership. Claude, Kimi and ChatGPT are three
> reasoning engines building one institution.
>
> Re-run the blueprint, critical path, gap audit, closure verdict, handoff
> conformance, side-effect inventory, full tests and every applicable verifier.
> Recalculate the Single Bottleneck Metric. Compare current main, your branch,
> ChatGPT Part 2, PR #70, Kimi's reconciliation work, DALEOBANKS, WMI,
> RailScout, PumpStation and every relevant preserved mechanism. Where another
> branch has the stronger mechanism, assimilate it instead of defending yours.
> Where mechanisms overlap, identify one canonical owner and preserve the useful
> remainder as challenger, adapter, history or superseded evidence.
>
> Continue recursively: inspect → identify actual bottleneck → search existing
> substrate before inventing → construct smallest sufficient intervention →
> adversarially test → measure → retain/regress/kill → recompute frontier.
>
> Do not build another abstraction merely because it is buildable. A change that
> moves no real dependency, proof threshold, integration boundary or falsifiable
> capability should receive no progress credit.
>
> **7.** Drive the internal build toward the actual operating milestone, not
> merely a green Kernel. The target is a canonical UNIIMENTE Alpha that can
> eventually be installed and powered on as one governed body: Kernel +
> DALEOBANKS + at least one real reasoning/refinery pathway, persistent state
> across restart, one authoritative identity/contract spine, Founder Cockpit
> visibility, standing bounded mandates for routine work, reserved matters
> escalated to me, automatic refusal/kill behavior, full auditability, and no
> need for me to babysit every harmless routine operation.
>
> RailScout must become an actual research-refinery runtime rather than doctrine
> alone. WMI must remain the venture/economic reasoning organ rather than
> growing parallel constitutional authority. DALEOBANKS must become the governed
> public/distribution organ rather than merely a standalone bot. PumpStation and
> the economic mechanisms remain part of the cumulative architecture but must
> earn progression through evidence and bounded lawful implementation. Preserve
> the long-range developmental, regenerative, morphogenetic, scientific,
> economic and embodiment aspirations instead of silently shrinking them because
> they are not yet implemented. Translate them into mechanisms and tests.
>
> **8.** Do not weaken the external-reality wall. HARDENED = 0 and CVO/SBM = 0
> are currently useful truths. Keep them true until reality changes them.
>
> But remove every internal obstacle between us and the first legitimate
> external proof. Build an External Reality Graduation Packet now: identify the
> smallest, cheapest, reversible, lawful and most informative first canary;
> preregister the prediction and success/failure criteria; specify exact
> capability, authority, consequence class, budget/exposure, identity, kill
> switch, reconciliation method, external verification method and rollback;
> connect the complete Bridge C → D → learning path; and prove it end-to-end
> against a consequence-inert rehearsal.
>
> A likely candidate may be one narrowly bounded DALEOBANKS publication because
> it can test sensing → decision → authorization → public action → external
> observation → reconciliation → causal learning without financial custody. But
> do not choose it just because I mentioned it—compare it against the strongest
> alternatives and select based on information value, reversibility and
> relevance to the complete system.
>
> Do not execute that real canary yet. Bring me the finished one-screen
> graduation decision when the system is technically ready. During this
> developmental period we continue consequence-inert testing until I explicitly
> authorize the external experiment or graduation.
>
> **9.** Preserve the recursive founder-intent rule permanently. No success
> metric, model, agent, organ, Venture Cell, router, evaluator, developmental
> engine or future Founder Twin may expand its own authority. Nothing may erase
> failures or negative evidence to make progress look better. Current
> implementation does not supersede aspiration. Aspiration does not constitute
> current capability. Simulation does not equal reality. Passing tests do not
> equal external proof.
>
> My ultimate instruction remains:
>
> Take all existing UNIIMENTE work—founder intent, current main, Claude work,
> Kimi work, ChatGPT work, prior proofs, failures, unresolved ideas and every
> useful source—as one cumulative substrate. Determine how the pieces strengthen
> one another. Eliminate unnecessary duplication by recombining the strongest
> mechanisms into one canonical system. Then direct the next work according to
> the largest remaining gap between the current institution and my intended
> complete UNIIMENTE. Do not optimize for preserving any model's architecture or
> ownership. Optimize the whole.
>
> Implement these founder rulings, leave a clean evidence trail and handoff for
> Kimi and ChatGPT, then continue the goal chase. Do not declare completion
> because the current frontier disappears. Completion means the intended
> institution has been progressively built and externally earned, not that one
> branch ran out of authorized work.

## Standing constraints this ruling does NOT relax

Recorded explicitly so no later reader mistakes broad build authorization for
consequence authorization:

- no merge to `main`;
- no public deployment;
- no money movement or fund custody;
- no contact with counterparties;
- no external publication;
- no public network surface, listener, bind or outbound connection;
- no execution of the external canary until a separate explicit authorization.

`HARDENED = 0` and `CVO/SBM = 0` are to remain true until reality changes them.
