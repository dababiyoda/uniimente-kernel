# External audit: UNIIMENTE repository audit, 5 September 2026 (preserved verbatim)

- Supplied by: Alfonso Lopez (founder), uploaded to Claude Code cloud session `session_01TnTfFXr93jtNSzVD9SWeGx` on 2026-10-14
  together with the third issuance of the Goal Gravity directive (`docs/intent/sources/GOAL-GRAVITY-DIRECTIVE-2026-10-13-source.md`,
  "Third issuance").
- Upload file: `UNIIMENTE_Audit_2026-09-05.md`, 45783 bytes, sha256 `fac5d1ecc41fcaf63aa0af5825a1b337eb4bb7cc96247e13ea2a40e119973fd4`.
- Authorship: the audit text names itself as an audit by an AI assistant over the connected GitHub account on 2026-09-05; it is
  preserved here as `external_evidence` / `historical_artifact`, not as founder intent and not as authority. Its findings are
  claims to verify, which the disposition table below does for the Kernel-side items only.
- Preservation rule: the body below is the uploaded file reproduced byte-for-byte after this header. Nothing in it changes
  Kernel authority, gate states or founder decisions.

## Kernel-side disposition on 2026-10-14 (main `d64a6c9`, verified by reading code and running the suite)

| Audit finding | Kernel-side status on `main` | How verified |
|---|---|---|
| F03 the canonical gate also issues a missing grant | REPAIRED: `policy/consequence_gate.py::run` refuses `executor admission requires pre-existing grant` when `standing_grant is None`; supplied grants are resolved against the issuer and bound to actor/objective/target | code read; `tests/unit/test_goal_gravity_absence.py::test_report_separates_executed_prepared_refused_and_unknown` exercises a Gate refusal on a mis-bound grant |
| F04 ledger verification does not fully verify its genesis | REPAIRED: `provenance/ledger.py::verify_chain` recomputes the genesis hash and compares the expected constitution; a second genesis is refused | code read; full suite green (783 passed) |
| F05 event replay protection fails across restart | REPAIRED: `events/spine.py::_refresh` derives `_seen_ids` from verified durable history and updates volatile indexes only after a successful append | code read |
| F13 backlog of conflicting development lines | OPEN: 118 open draft PRs on 2026-10-14 (100 on the first listing page, 18 on the second); the Goal Gravity work continues on draft #160 rather than opening a parallel lineage | GitHub listing in the session |
| F01, F02, F06–F12, F14, F15 (organ-side: WMI, DALEOBANKS, PumpStation, RESEARCH-IN, RAILSCOUT) | NOT ASSESSED HERE: outside this repository; preserved as claims for their owners | — |

The audit's "next highest-value change" (WMI authentication and the packaged bridge entrypoint) is an organ-side item and is not
addressed by the Kernel increment that preserves this file.

---

# UNIIMENTE repository audit — 5 September 2026

**Finding: UNIIMENTE has a coherent institutional direction and meaningful implementations, but its development process is accumulating competing states faster than it integrates and verifies them.** The highest-value work is now authentication and durability repair, adoption of existing hardening, and one verified founder workflow across the organs.

This is an audit and repair proposal. It does not declare a release safe, select a new constitutional authority, activate an organ, or authorize deployment. No GitHub source, branch, PR, issue, review, credential, or deployment was changed during this audit.

## Scope and evidence

The connected GitHub account exposes seven repositories. The repository listing's next page was empty. I inspected all seven complete default-branch trees: **816 file entries**, **232 branch references**, and **109 open PR summaries**. Deep inspection covered selected authority, authentication, event, contract, bridge, deployment and prototype files; critical draft source; existing ownership and rationalization documents; and current check/review records for kernel PRs #70, #87, #92 and #93.

This is portfolio-wide coverage, not a line-by-line review of every file or every historical branch. Closed PR history, every branch diff, production environments, actual credentials, deployment configuration, real customer outcomes, and private repositories outside this connection remain unverified. No running service was attacked. Prior conversation context informed the objective; fresh GitHub evidence governs current-state findings.

Evidence tiers used below:

- **Observed source:** a file or GitHub record opened in this audit.
- **Reproduced:** an offline probe of inspected code, with no service startup or network. Authentication functions were extracted with AST to avoid application/database imports.
- **Reported CI:** GitHub reports a passing check at a specified PR head; full suites were not rerun locally.
- **Inference/proposal:** interpretation or repair design, distinguished from observed behavior.

The reproduction harness demonstrated **13 failing cases across authentication, replay, integrity and identity translation**, plus **two passing checks of existing draft repairs**. This is not 13 independent vulnerabilities or a production penetration test. All 25 source versions in the pinned source manifest were matched to GitHub blob hashes before the final probe run.

## What you are doing right

1. **The mission has a useful invariant.** Capability can grow without granting the system more authority. Your permanent order distinguishes one authority from many governed capability implementations. That supports ambitious development without making every model or organ sovereign. [Permanent build order](https://github.com/dababiyoda/uniimente-kernel/blob/bcbb1ab4a0c42cda4a97aec42a11125753962762/docs/UNIIMENTE_FINAL_BUILD_ORDER.md).
2. **The organ split has a purpose.** Media/perception, venture assessment, and constitutional enforcement are different responsibilities. Keeping their specialist implementations separate can reduce coupling. Their interfaces and authority checks need to catch up with that architecture.
3. **There is executable substrate worth retaining.** The kernel contains an EvidenceLedger, EventSpine, DurableWorkflow, ConsequenceGate, capability machinery and causal memory. These are implementation, although this audit found consequential gaps in the shared primitives.
4. **The recent work is more honest about maturity.** PR #92 produces organization hypotheses and explicitly refuses execution. PR #93 builds a founder-facing persistent sandbox episode and expressly distinguishes one simulated closure from zero real outcomes. Neither should be dismissed as empty documentation. [Compiler PR](https://github.com/dababiyoda/uniimente-kernel/pull/92), [Goal Chase PR](https://github.com/dababiyoda/uniimente-kernel/pull/93).
5. **You preserve counterevidence.** Static workflows and do-nothing remain competitors. Recent PRs retain failures, dissent and uncertainty rather than redefining success to make an experiment pass. Keep this discipline.
6. **Useful protections already exist.** Organ contract adapters refuse missing enrichment; assessment handling fixes approval requirements and rejects explicit authority inflation. The next step is complete protocol validation and durable identity preservation, not abandoning those protections.

## Repository map: intended role versus inspected reality

| Repository | Default files / branches / open PRs | Intended relationship to UNIIMENTE | Inspected reality | Recommended disposition |
|---|---:|---|---|---|
| uniimente-kernel | 301 / 92 / 52 | Canonical authority, contracts, evidence, events, composition and learning | Substantial implementation; several competing unmerged lines. Recent compiler and founder-loop work lives in drafts. Shared integrity/replay defects remain on main. | **RETAIN** its ownership; repair primitives; reconcile runtime candidates before activation. |
| DALEOBANKS | 243 / 62 / 17 | Public voice, perception, relationships and opportunity signals | Real media stack and direct WMI client. Governance extraction, publishing gates and transport hardening remain in separate PR lines. | **RETAIN** specialist behavior; converge transport and governance consumption. |
| WealthMachineIntelligence | 207 / 36 / 15 | Venture evaluation and bounded venture-cell behavior | Real assessment code; multiple application surfaces; permissive authentication; 56 tracked .pyc files; nested Enhanced Edition. | **REPAIR FIRST**; resolve its application entrypoint and identity boundary. |
| PumpStation | 7 / 11 / 10 | Candidate bounded capital/community experiment | Main is a wallet-registration demo. Institutional simulation and wallet hardening are draft work. Main's scripts refer to missing Next.js. | **STAGE-GATE**; retain simulation, repair demo; no institutional capital capability claim. |
| RESEARCH-IN | 53 / 23 / 11 | Potential research/evidence supplier | Scaffold with Rust HTTP ingestion stub, minimal web page and conceptual infrastructure. No inspected kernel contract connection. | **PARK broad platform expansion**; revive through one real evidence-ingestion capability. |
| RAILSCOUT | 1 / 7 / 4 | Perception and evidence refinery | Main contains only “RAILSCOUT / Egregore organ.” Four governance PRs; additional kernel registration drafts. | **RECONFIGURE** repeated doctrine into one authoritative charter and one bounded executable evidence task. |
| build-your-own-x | 4 / 1 / 0 | Mechanism discovery and learning reference | Tutorial index and supporting assets, not a deployed capability library. | **RETAIN AS REFERENCE**; trace selected mechanisms to primary implementations and licenses. |

Counts measure repository structure and backlog, not usefulness. An open PR is not necessarily redundant, and a small repository is not necessarily a failure.

## How they actually connect

| Edge | Source-backed connection | Gap |
|---|---|---|
| DALEOBANKS → WMI | `services/wealthmachine_client.py` sends OpportunityPacket to `/api/opportunities/intake`. WMI implements intake in `src/api/routes/opportunities.py`. | Direct organ HTTP bypasses the registry's stated event-only routing rule. Missing credentials permit unsigned mode on main. |
| WMI → DALEOBANKS | VentureAssessment returns to the client; `assessment_to_actions` prepares drafts and an approval request. | Assessment remains a recommendation. Durable recovery and outcome reconciliation are not proved by returning JSON. |
| Kernel ↔ both organs | Kernel adapters, organ manifests, and vendored schema adapters exist. | Three manually mirrored transport implementations disagree about recognized identities. “Consumes kernel contracts” does not prove runtime mediation. |
| Founder → kernel | PR #93 uses existing EventSpine, DurableWorkflow, ConsequenceGate and CausalMemory with a synthetic founder signer. | Sandbox CLI and explicit ticks; real founder authentication, persistent inbox/application delivery and service operation remain open. |
| Compiler → runtime | PR #92 defines content-bound organization designs and comparison records. | Execution is deliberately refused. Runtime ownership between #70 and #87 remains unresolved; #93 adds another composition candidate to evaluate. |
| RAILSCOUT / RESEARCH-IN / PumpStation → core | Registry/doctrine and draft integration intentions. | Operational connectivity is not established by the inspected defaults. Treat these as proposed edges until tested. |

Sources: [DALEOBANKS client](https://github.com/dababiyoda/DALEOBANKS/blob/ed5e95d7f48e006d180b972efe138179325c31d2/services/wealthmachine_client.py), [WMI intake route](https://github.com/dababiyoda/WealthMachineIntelligence/blob/ec84b6a2eec4efbc07bed7f167da81f5e25d890c/src/api/routes/opportunities.py), [organ registry](https://github.com/dababiyoda/uniimente-kernel/blob/bcbb1ab4a0c42cda4a97aec42a11125753962762/identity/organ-registry.yaml).

## Findings and concrete repairs

Priority means repair order before increased exposure; it does not imply any service is currently deployed or compromised.

### F01 — Authentication is permissive on ordinary WMI application paths

**Priority 0 · Reproduced.** Root `jwt.py` decodes arbitrary text as `test-user`. `src/api/auth.py:get_current_user(None)` returns the development admin. Root `main.py:get_current_user` accepts `demo` and `demo_token` explicitly. The Dockerfile starts `main:app`, so that root application is a documented deployment surface. These are separate bypasses; removing the JWT stub alone does not fix them all.

**Repair:** consolidate the existing #23/#24 authentication work into the selected application path; remove production import visibility of the JWT stub; use a maintained verifier with explicit issuer, audience, algorithm, expiry and key configuration; reject missing credentials; keep demo identity in an isolated test fixture. Reject plaintext-password fallback in deployed modes. Do not silently substitute demo implementations after an ImportError.

**Acceptance:** every supported startup command rejects anonymous, demo, malformed, expired, wrong-audience and wrong-issuer credentials; authorized access remains functional. Exercise an actual protected route, not only the token helper. PR #23 changes `jwt.py`, `main.py` and `src/api/auth.py`, so inspect and reuse it before authoring another auth subsystem.

[JWT stub](https://github.com/dababiyoda/WealthMachineIntelligence/blob/ec84b6a2eec4efbc07bed7f167da81f5e25d890c/jwt.py), [auth](https://github.com/dababiyoda/WealthMachineIntelligence/blob/ec84b6a2eec4efbc07bed7f167da81f5e25d890c/src/api/auth.py), [entrypoint](https://github.com/dababiyoda/WealthMachineIntelligence/blob/ec84b6a2eec4efbc07bed7f167da81f5e25d890c/main.py), [existing PR #23](https://github.com/dababiyoda/WealthMachineIntelligence/pull/23).

### F02 — Missing transport configuration disables authentication

**Priority 0 · Reproduced in all three default-branch mirrors.** Kernel, DALEOBANKS and WMI compute the default signature requirement from whether a signing key exists. With no key, empty headers are accepted as unsigned-local. This is contrary to the intended fail-closed boundary.

**Repair:** reuse kernel #71/#87 and organ #74/#32 hardening, with one explicit compatibility policy. Offline probes confirmed that WMI #32 and DALEOBANKS #74 reject the missing-key default. Neither has been merged by this audit. A development opt-in must not become a deployment shortcut.

**Acceptance:** missing key rejects; forged signature rejects; a configured key cannot be bypassed by stale development flags; valid peer traffic succeeds. Test actual request and response bytes. Shared HMAC establishes possession of a shared secret, not isolation between key holders. Preserve that distinction until independently keyed workloads are adopted.

[Kernel mirror](https://github.com/dababiyoda/uniimente-kernel/blob/bcbb1ab4a0c42cda4a97aec42a11125753962762/adapters/bridge_transport.py), [WMI #32](https://github.com/dababiyoda/WealthMachineIntelligence/pull/32), [DALEOBANKS #74](https://github.com/dababiyoda/DALEOBANKS/pull/74).

### F03 — The canonical gate also issues a missing grant

**Priority 0 · Observed source, not a reproduced external action.** `ConsequenceGate.run` uses `standing_grant or self.grants.issue_single_action(...)`. Institutional enforcement and authority issuance are coupled. PR #87 records a repair that makes external grants explicit, while also acknowledging that same-process callers can still reach the issuer.

**Repair:** port the external-grant refusal into the selected canonical path; authenticate and bind the authorizing principal separately from the executor. Preserve an explicitly scoped internal sandbox path only where policy authorizes it. Do not call a process-local separation an unforgeable security boundary.

**Acceptance:** an otherwise admissible external proposal without a valid pre-existing authorization fails before executor invocation; the executor cannot mint or widen it; revocation and changed payload/target invalidate it. [Gate source](https://github.com/dababiyoda/uniimente-kernel/blob/bcbb1ab4a0c42cda4a97aec42a11125753962762/policy/consequence_gate.py), [#87](https://github.com/dababiyoda/uniimente-kernel/pull/87).

### F04 — Ledger verification does not fully verify its genesis

**Priority 0 · Reproduced.** Changing the in-memory genesis constitution payload still returns “chain intact.” Loading an existing ledger also does not compare its constitution with the constructor's requested constitution. The current verifier skips recomputing the genesis payload hash.

**Repair:** enforce the genesis schema, recomputed genesis hash and expected constitution binding in the shared ledger loader/verifier. Define lawful versioned amendment behavior explicitly; do not invalidate genuine history by comparing every old record to today's constitution.

**Counterevidence:** PR #93 already performs additional genesis and expected-constitution checks in its GoalChase `_refresh`. This protects that wrapper's declared use; it does not repair the shared ledger for all consumers. Extract the shared invariant once, retain GoalChase-specific checks, and rerun both histories.

**Acceptance:** tampered genesis, foreign constitution, malformed/empty persisted history and broken links refuse; valid historical replay and authorized amendments remain possible. This detects tampering relative to a trusted anchor; it is not proof that a fully malicious host cannot rewrite all unsigned history. [Ledger](https://github.com/dababiyoda/uniimente-kernel/blob/bcbb1ab4a0c42cda4a97aec42a11125753962762/provenance/ledger.py), [GoalChase wrapper](https://github.com/dababiyoda/uniimente-kernel/blob/21fb21ed803f43e47acb8e6420f6cdc4f74925cd/egregore/goal_chase.py).

### F05 — Event replay protection fails across restart and persistence failure

**Priority 0 · Reproduced.** Reconstructing EventSpine from a persisted ledger starts `_seen_ids` empty. The same event is accepted and ledgered twice; the hash chain still validates. Separately, `ingest` marks an event seen before appending it. A failed append makes a later retry disappear despite no persisted event.

**Repair:** derive the accepted-event index from verified durable history; define which event directions count; update volatile indexes only after a successful durable append. Add transactional uniqueness for concurrent writers when that runtime is introduced. PR #87 contains restart work to evaluate and port.

**Acceptance:** restart, duplicate delivery, failed append/retry, emitted-event re-ingestion, ID collision with changed payload, and concurrent arrival have explicit outcomes. A hash chain that contains duplicates is still a valid hash chain; integrity and idempotency require separate tests. [EventSpine](https://github.com/dababiyoda/uniimente-kernel/blob/bcbb1ab4a0c42cda4a97aec42a11125753962762/events/spine.py).

### F06 — Transport replay and WMI idempotency are process-local

**Priority 1 · Nonce restart reproduced; idempotency limitation observed.** A valid signed request is accepted again by a fresh NonceCache. WMI stores assessments and idempotency keys in dictionaries. Concurrent requests can also pass lookup before either stores a result.

**Repair:** bind durable idempotency to authenticated sender, operation and payload digest; atomically claim and finish work; reject changed payload under a reused key; return the original result for legitimate retries. Separate transport freshness from application idempotency. Do not label an in-memory nonce dictionary distributed replay protection.

**Acceptance:** process restart and simultaneous duplicate delivery cause one evaluation/result; uncertain side-effect dispatch becomes reconciliation-required. [Intake service](https://github.com/dababiyoda/WealthMachineIntelligence/blob/ec84b6a2eec4efbc07bed7f167da81f5e25d890c/src/services/opportunity_intake.py).

### F07 — Translation changes causal identity

**Priority 1 · Reproduced in both organ adapters.** Repeating an accepted non-UUID packet translation produces a different random kernel packet ID. The assessment translator also generates new IDs. This can break stable links and make retry look like new work.

**Repair:** preserve canonical IDs when valid; either refuse unsupported identifiers or use a documented deterministic namespaced mapping with the original ID retained. Require an actual immutable assessment identity when mapping assessments. Keep observation time separate from translation time.

**Acceptance:** same source object maps to the same identity across retries/restarts; assessment resolves to its exact original packet; namespace collisions and conflicting payloads refuse. [DALEOBANKS adapter](https://github.com/dababiyoda/DALEOBANKS/blob/ed5e95d7f48e006d180b972efe138179325c31d2/services/kernel_contracts.py), [WMI adapter](https://github.com/dababiyoda/WealthMachineIntelligence/blob/ec84b6a2eec4efbc07bed7f167da81f5e25d890c/src/services/kernel_contracts.py).

### F08 — WMI's documented startup does not select its bridge application

**Priority 1 · Observed.** Docker starts root `main:app`. The intake router is mounted in `src.api.main:app`; root `main.py` does not include it. A healthy root API therefore does not establish the documented DALEOBANKS bridge.

**Repair:** choose one supported application composition; point Docker, local run instructions and CI at it; retain alternate surfaces as explicitly historical or bounded development applications. A legacy adapter may route to the selected composition without duplicating authentication.

**Acceptance:** the exact packaged startup command serves the expected authenticated bridge and health endpoints. [Dockerfile](https://github.com/dababiyoda/WealthMachineIntelligence/blob/ec84b6a2eec4efbc07bed7f167da81f5e25d890c/Dockerfile), [bridge app](https://github.com/dababiyoda/WealthMachineIntelligence/blob/ec84b6a2eec4efbc07bed7f167da81f5e25d890c/src/api/main.py).

### F09 — PumpStation wallet registration has no freshness binding

**Priority 1 · Observed.** Main verifies a signature over the constant `Connect PumpStation`; there is no per-session nonce, expiry or domain binding. A previously obtained valid signature can be reused. This finding concerns wallet registration, not proof that the repository can spend wallet funds.

**Repair:** review and reuse PR #16's challenge/response work; separate its auth changes from broader governance additions for easier adoption. Test expiry, replay, wrong origin/address, capacity exhaustion and restart behavior. ERC-4361 provides the relevant message and verification requirements. [Server](https://github.com/dababiyoda/PumpStation/blob/df6a732f44412c626098ee9591b9d19f420d02dd/server/index.js), [PR #16](https://github.com/dababiyoda/PumpStation/pull/16), [ERC-4361](https://ercs.ethereum.org/ERCS/erc-4361).

### F10 — Prototype success responses and scripts overstate implementation

**Priority 1 for honest status; otherwise scoped maintenance.** PumpStation's server package runs `next dev/build/start` without Next.js installed, and its test script exits successfully after saying there are no tests. RESEARCH-IN's ingestion route returns `ingested` when a URL starts with `http`; it does not ingest evidence. Its root package defines no advertised lint/test/dev scripts. Its Qdrant Terraform contains explicitly conceptual provider/resource assumptions.

**Repair:** make the executable entrypoints accurate; classify stub behavior as unimplemented; keep conceptual infrastructure outside an actionable deployment path. Build one ingestion path that fetches an allowed source, retains provenance and returns an evidence artifact before adding search platforms, social/community features or infrastructure breadth.

**Acceptance:** fresh checkout starts by the documented command; ingestion success requires stored, retrievable source-backed content; failure never returns success; provider configuration is validated against an actual supported version before use. The audit did not execute Terraform or make a cloud-provider compatibility claim. [PumpStation scripts](https://github.com/dababiyoda/PumpStation/blob/df6a732f44412c626098ee9591b9d19f420d02dd/server/package.json), [ingestion stub](https://github.com/dababiyoda/RESEARCH-IN/blob/576913809432fc1dd47a245a14184988607e27eb/services/ingest/src/lib.rs), [root package](https://github.com/dababiyoda/RESEARCH-IN/blob/576913809432fc1dd47a245a14184988607e27eb/package.json), [conceptual Terraform](https://github.com/dababiyoda/RESEARCH-IN/blob/576913809432fc1dd47a245a14184988607e27eb/infrastructure/modules/qdrant/main.tf).

### F11 — Reproducible debris and multiple application generations obscure ownership

**Priority 2 · Observed tree.** WMI tracks **56 .pyc files totaling 490,667 bytes**, package egg-info, and a nested `WealthMachineIntelligenceEnhanced` application with its own deployment and CI files. The nested app is a duplicate candidate/alternative implementation, not proven byte-identical waste. Across all default trees there are seven nonempty identical-blob groups, including intentionally mirrored contracts and duplicated prompt artifacts.

**Repair:** preserve provenance; exclude reproducible bytecode from active authored source and future commits; classify the Enhanced Edition as active, experimental, fallback or historical with an owner and activation boundary. Consolidate repeated prompt artifacts by content hash and provenance pointers where permitted. Preserve lockfiles: reproducibility metadata is useful generated content, not arbitrary debris.

**Acceptance:** clean builds generate caches outside tracked source; no alternative app silently supplies authority; source and historical replay remain recoverable. [WMI tree](https://github.com/dababiyoda/WealthMachineIntelligence/tree/ec84b6a2eec4efbc07bed7f167da81f5e25d890c), [Enhanced Edition](https://github.com/dababiyoda/WealthMachineIntelligence/blob/ec84b6a2eec4efbc07bed7f167da81f5e25d890c/WealthMachineIntelligenceEnhanced/README.md).

### F12 — Useful test checks have important blind spots

**Priority 1–2 · Observed.** WMI CI runs Ruff with `--exit-zero`, so lint findings cannot fail that step. DALEOBANKS contract parity uses a hand-written top-level validator; it does not implement full schema types, nested structures or formats. Local pin checks prove vendored bytes match a local pin, not that a live peer uses that version.

**Repair:** make required lint enforceable with a bounded existing-debt baseline; validate complete schemas using the canonical validator; add producer/consumer compatibility tests at the exact repository versions chosen for integration. Freeze evaluator data separately from the builder, and anchor evidence to code versions.

**Acceptance:** intentionally malformed nested/type payloads fail; valid peer payloads pass; stale schema or peer version is visible. Reuse verifier head-binding PR #85. [WMI CI](https://github.com/dababiyoda/WealthMachineIntelligence/blob/ec84b6a2eec4efbc07bed7f167da81f5e25d890c/.github/workflows/ci.yml), [parity tests](https://github.com/dababiyoda/DALEOBANKS/blob/ed5e95d7f48e006d180b972efe138179325c31d2/tests/test_kernel_contract_parity.py), [#85](https://github.com/dababiyoda/uniimente-kernel/pull/85).

### F13 — The backlog contains conflicting and repeated development lines

**Priority 1 · Observed metadata; waste assessment is inference.** There are 109 open PRs, including 52 in the kernel. The compiler is stacked on #90 → #88 → #87 → #71, while #93 starts directly from main. SDK extraction, WP runtime work, core runtime composition and organ control-plane work coexist. Kernel PRs #70/#87/#92/#93 all have passing reported checks but **no submitted review records** at inspection. No submitted reviews is not proof nobody examined them elsewhere.

**Repair:** use one integration matrix linked to existing PRs. Give each PR one disposition: adopt as dependency, extract specific changes, benchmark alternative, superseded-with-lineage, or defer. Start with the auth/replay prerequisites and runtime-owner decision; do not bulk-merge the backlog or create another whole-system rewrite. Bound active implementation work by reviewed bottlenecks, not by number of named subsystems.

**Acceptance:** every active PR names canonical owner, exact base, dependency, acceptance evidence and rollback; competing changes are behaviorally compared before adoption. Preserve the strongest alternative as a benchmark, not a simultaneous authority.

### F14 — RAILSCOUT's registration and doctrine work is repeating

**Priority 2 · Observed.** Dedicated RAILSCOUT main has one README and four open governance PRs (#2–#5). Kernel also has registration/refinery PRs #72/#76/#77, while its default organ registry says the repository has not yet been created.

**Repair:** reconcile the existing intent records and repository pointer; select one charter with provenance; keep competing doctrine as proposed or historical. Then implement one bounded evidence-refinery task with citation, contradiction preservation and a typed output. A fifth charter-only PR would not resolve the current capability gap.

**Acceptance:** the registry resolves to the actual repository, lifecycle says what is executable, and one source-backed evidence packet reaches the selected kernel path. [RAILSCOUT](https://github.com/dababiyoda/RAILSCOUT), [open drafts](https://github.com/dababiyoda/RAILSCOUT/pulls), [kernel registry](https://github.com/dababiyoda/uniimente-kernel/blob/bcbb1ab4a0c42cda4a97aec42a11125753962762/identity/organ-registry.yaml).

### F15 — Model assumptions and demo labels need stronger separation from outcomes

**Priority 1 for decisions · Observed source plus inference.** WMI intake maps urgency to fixed market-demand values and inserts a base price of 29. Its root dashboard labels achievement from stored failure-probability fields. These may support a deterministic experiment; they do not establish measured demand, calibrated risk or commercial success. “Production-ready,” “enterprise-ready” and phase-completion language therefore needs an explicit evidence tier.

**Repair:** attach source and assumption status to modeled inputs; keep synthetic scores out of verified-outcome counters; derive commercial state from accepted external records only. Tie README status to code SHA, environment, command and acceptance evidence. Preserve historical claims as dated history rather than rewriting them as current proof.

**Acceptance:** an invented high score cannot increment a verified outcome; invalidated evidence reopens the claim; actual founder attention and actual accepted outcomes are measured separately. [Intake assumptions](https://github.com/dababiyoda/WealthMachineIntelligence/blob/ec84b6a2eec4efbc07bed7f167da81f5e25d890c/src/services/opportunity_intake.py), [dashboard](https://github.com/dababiyoda/WealthMachineIntelligence/blob/ec84b6a2eec4efbc07bed7f167da81f5e25d890c/main.py).

## The process correction

My inference is that broad “build the whole institution” prompts are repeatedly producing architectures, branches, proofs and doctrines without a comparably strong adoption process. This can make every session look productive while leaving the default runtime behind.

The corrective unit of work should be **one named bottleneck, one canonical integration path, one falsifiable acceptance result**. Preserve alternate capability implementations and the far-future ambition; stop treating every preserved branch as an active roadmap commitment.

Your existing rationalization plan already diagnosed multiple truth surfaces. The missing work is enforcing it through adoption, ownership and runtime evidence. Another general governance document would add little. [Existing rationalization plan](https://github.com/dababiyoda/uniimente-kernel/blob/bcbb1ab4a0c42cda4a97aec42a11125753962762/docs/REPOSITORY_RATIONALIZATION_PLAN.md).

## Repair sequence, reusing existing work

The intervals below are proposed work windows, not promises of elapsed completion or scheduled automations.

| Order | Work package | Existing work to examine/reuse | Exit evidence | Rollback / stop condition |
|---|---|---|---|---|
| 1 · next bounded change | Close WMI authentication bypasses; select and exercise its intended application entrypoint | WMI #23/#24; default Docker and both app modules | No anonymous/demo access; real signed bridge route reachable by the packaged command | Pause exposure if valid auth cannot be supported; preserve old app only as isolated historical/test code |
| 2 · first repair window | Repair missing-key transport defaults and shared ledger/event invariants | Kernel #71/#87; DALEOBANKS #71/#74; WMI #31/#32; PR #93's local integrity checks | All reproduced negative cases fail safely; authorized traffic/replay succeeds | Never roll back by silently reopening unsigned live traffic; narrow admission or pause instead |
| 3 · before integration | Stabilize translation IDs, durable idempotency, full schema validation and response-byte signing | Existing contract adapters/parity tests; kernel #85; organ SDK alternatives | One signal retains identity and evidence through restart, retry and assessment | Stop on lost lineage, duplicate work, fabricated evidence or incompatible wire meaning |
| 4 · one integration candidate | Choose one runtime composition and adapt PR #93's founder loop to it | Kernel #70 versus #87; PR #93; #88/#90/#92 as design/capability candidates | Founder goal → authorized bounded work → evidence-backed result → durable inbox → restart → one verified closure | Stop on parallel authority, false closure or implicit expansion of scope |
| 5 · after the core path works | Add one RAILSCOUT or RESEARCH-IN source-backed evidence operation; repair PumpStation demo separately | Existing RailScout charters/registration; research ingestion; PumpStation #16 | One real evidence artifact meets the core contract; prototype startup/auth works honestly | Defer extra services and speculative governance that do not improve this result |
| 6 · after reliable baseline | Compare organizational forms on independent held-out tasks under equal budgets | #88/#90/#92, static DurableWorkflow, WMI fixed roster | Measured quality, cost, latency, recovery and founder-attention improvement with no authority violations | Retain static if more elaborate organization adds no demonstrated advantage |

**One live constitutional decision remains:** the canonical runtime composition and adoption path. This audit proposes a comparison; it does not silently settle #70 versus #87 or merge #93. Security repairs that preserve established authority should be kept small and reviewable rather than bundled into that entire architectural decision.

## Founder intent ledger and conflicts

| Audit intent ID | Faithful intent | Lineage | State | Authority and unresolved issue |
|---|---|---|---|---|
| A-01 | Audit all exposed repos; expose unnecessary work and identify repairs | Current user instruction, 5 Sep 2026 | implemented | Authorizes inspection/reporting and this offline evidence package; no external operation inferred |
| A-02 | Preserve an ambitious, cumulative founder assistant and Infinite Goal Chase | Prior project context; PR #93; Final Build Order | active | Current verified tier is sandbox; authenticate real founder and prove a durable operational loop next |
| A-03 | Capability may expand; authority may not self-expand | Final Build Order §§3/11; CLAUDE.md | active | F01–F05 expose implementation gaps; generated roles and identities grant no authority |
| A-04 | Preserve useful work while organizing the architecture | Final Build Order §§2/9/12 | active | Conflicts with indiscriminate deletion, not with deactivation, provenance-preserving consolidation or excluding bytecode |
| A-05 | Use blockchain and zero-trust mechanisms for security | User project direction; PR #92 | exploratory | Mechanism reuse is compatible with no custom blockchain; runtime enforcement must be separately proved |
| A-06 | Use the simplest adequate organization and retain the static baseline | #88/#90/#92 | active | Dynamic organizational superiority needs evidence; unbounded swarm growth is not the acceptance test |
| A-07 | Reach broad tools, computer use and eventual embodied capabilities | Prior founder direction; Final Build Order; PR #93's deferred horizon | deferred | Destination preserved. Catalog entries, mocks and speculative descendants are not operational capability or authority |

Important conflicts to resolve explicitly:

- **Direct HTTP versus event-only doctrine:** existing organ code calls directly while the registry prohibits organ-to-organ calls. Ratify whether typed requests are admitted through a mediated adapter; do not let configuration decide doctrine.
- **One canonical mechanism versus preserved alternatives:** the newer permanent order permits many governed capability implementations. Select one authority and active interface, while preserving alternatives as bounded candidates.
- **Runtime owner versus independent founder slice:** #93 usefully advances the founder experience without depending on #70/#87. Adoption still needs a decision about shared ownership and security prerequisites.
- **Historical phase claims versus present evidence:** “executable and verified” must name which behavior and tier. A local demonstration, passing CI and an independently accepted outcome remain different claims.

## Requested skill application: a bounded institutional diagnosis

### Spider-Web Hegemony

The governing transaction is: **Alfonso authorizes a bounded goal; the institution must return an accepted outcome while preserving authority and minimizing founder intervention.** The broken governing state is consistent admission, durable causal identity and outcome verification across repositories.

| Super-node | Eight practical sides | Current weakness | Smallest correction |
|---|---|---|---|
| Eligibility | Actor identity; action authority | Demo/unsigned paths; gate issues missing grant | Authenticate actual actor; bind independent grant at action boundary |
| Default routing | Contract routing; resource limits | Divergent startup/transport modes; competing runtime branches | Pin one integration path; enforce declared budget and fallback |
| Proof / Truth | Evidence lineage; independent verification | Random translated IDs, replay/genesis gaps, builder-supplied proof | Stable IDs; verified replay; independent frozen evaluation |
| Resource / Settlement | Completion reconciliation; recovery/continuity | In-memory idempotency; sandbox closures can be misread | Durable claim/result state; distinguish accepted outcomes from simulation |

Commercial, participant-welfare, capital and market-control outcomes are **unmeasured in this audit**. There is no evidence here to call UNIIMENTE a proven commercial settlement rail or claim network effects. The current form is a developing founder-operated institution and experimental toolset.

**Decision: Reconfigure.** Next externally observable test, after authorization prerequisites: deliver one bounded evidence-backed result that Alfonso can independently accept. Measure real Founder Intervention Minutes per Verified Outcome and Clean Mission Completion Rate, with the denominator including failed/abandoned admitted missions. Proposed review gate: the first integration window, before expanding scope. Terminate or regress the candidate on unauthorized effect, duplicate consequence, false closure or loss of lineage. No outreach or deployment was performed.

### Mechanism Recombination Foundry

Do not build another blockchain or organizational framework for the defects above. PR #92 already contains a coherent design direction. Repair and exercise the underlying primitives first.

| Source mechanism | Three material mutations for UNIIMENTE | Preserved invariant / new failure to test |
|---|---|---|
| Transparency log and content-bound history | Certificates/blocks become mission-policy-artifact records; consistency checking moves to admission and replay; witnesses attest evidence while a separate principal authorizes consequences | Detect inconsistent history relative to trusted roots; stale or captured roots can still mislead |
| Zero-trust per-resource admission | Network membership becomes exact mission/action eligibility; persistent trust becomes expiring scoped leases; replacement workers re-prove identity and context eligibility | Missing identity/authority rejects; excessive checks can create availability and founder-attention costs |
| Versioned selection and durable workflow recovery already in the kernel | Alternative implementations become named benchmark candidates; resource allocation follows verified marginal improvement rather than PR volume; ambiguous dispatch becomes reconciliation rather than automatic retry | Preserve recoverability and dissent; correlated evaluators or poor metrics can select a worse implementation |

The useful combined behavior is a goal that can survive worker/runtime replacement while retaining its exact authorization, causal identity and evidence standard. This is **BUILDABLE in bounded forms; EXPERIMENTAL as a whole institutional runtime**. Autonomous open-ended scientific discovery or highly reliable recursive self-improvement remains a frontier aspiration. No claim of patent or mechanism novelty is made; event sourcing, capability security and transparency logs are established precedents.

NIST distinguishes authentication from authorization and rejects implicit trust based on network location. Certificate Transparency specifies auditable append-only log mechanisms, not the truth of everything logged. Those are useful source mechanisms, not proof that this repository already enforces them. [NIST SP 800-207](https://csrc.nist.gov/pubs/sp/800/207/final), [RFC 9162](https://www.rfc-editor.org/rfc/rfc9162.pdf).

**Decision: EXPERIMENT.** Next build is the bounded integrated founder episode, after shared primitive repairs. Require independently evaluated acceptance, restart/duplicate tests and complete lineage before admitting dynamic organizations. Stop if the extra machinery fails to outperform the static baseline under comparable constraints.

### Adaptive Omnidirectional Response

The code defects are complicated but testable; the long-horizon institution is complex and needs bounded experiments. The audience here is the founder, so the report leads with failure mechanisms, their effect on founder leverage, and the next reviewable intervention.

Routes compared: a fresh architecture rewrite; blanket backlog cleanup; focused repair plus integration. The selected route is the third because it retains useful work, tests actual failure and reduces the number of decisions that must remain open. A rewrite could reproduce the same bypasses; indiscriminate cleanup would erase options and violate preservation intent.

## Two strengthening passes on the integration recommendation

These are five explicitly separated perspectives from one audit, **not five independent reviewers**. Independent evidence review remains a prerequisite for constitutional adoption.

| Role | Position and evidence | Preserved concern |
|---|---|---|
| Founder-Intent Steward | Prioritize the real founder loop in #93; preserve broad tool and embodiment horizons as staged goals | Narrowing the next build must not silently retire the destination |
| Systems Architect | One authority and canonical event meaning; explicit organ adapters; retain useful alternative implementations | Shared-library migration may create lockstep release coupling |
| Adversarial Reviewer | Authentication/replay probes outweigh readiness prose; reject compiler scores as authorization | A passing suite can miss a deployment path or share builder blind spots |
| Operator and Maintainer | One documented startup and integration manifest; recover from restart and ambiguous dispatch | Too many permanent compatibility modes can recreate the original complexity |
| Evidence and Welfare Guardian | Accepted outcomes, consent and reversible operation; preserve negative evidence and disputes | Faster operation must not externalize risk or falsely claim commercial results |

### Pass 1 — Strengthen the smallest viable intervention

Retain the current baseline for comparison. First repair shared primitives and reduce ambiguity in application startup. Compose one founder episode on the selected substrate, with exact repository versions and no new execution authority.

Alternatives: **do nothing** preserves history but leaves reproduced failures; **patch organs independently** fixes immediate bugs but perpetuates drift; **new unified runtime/monorepo** offers centralized composition but conflicts with specialization and raises migration risk; **bounded integration experiment** exercises actual interfaces without committing to a rewrite. The last is preferred. Revive a stronger replacement only if the canonical interface cannot meet measured recovery or maintainability needs after bounded repair.

Pass-1 disadvantages: **D1** authority-owner ambiguity; **D2** tightly coupled releases; **D3** builder/evaluator correlation; **D4** founder attention spent on repeated approvals; **D5** historical evidence loss during cleanup.

### Pass 2 — Attack the strengthened design

- **D1 — deferred:** do not activate competing runtime owners. Owner: Alfonso with the kernel maintainer; review at the #70/#87/#93 composition decision.
- **D2 — experiment:** pin compatible versions and keep a temporary explicit adapter window. Owner: kernel and organ maintainers; review when one peer advances independently.
- **D3 — deferred:** freeze acceptance cases and obtain independent review; CI alone is insufficient. Owner: independent verifier to be assigned; review before declaring integration proved.
- **D4 — accepted within a bound:** request authority once for a clear mission/policy/budget envelope; escalate only exceptions. Owner: founder-loop maintainer; review measured intervention minutes, not synthetic fixture minutes.
- **D5 — prohibited:** no evidence destruction. Owner: each repository maintainer; preserve commit lineage and hashes before any archival operation.

New weaknesses created by the repair: **N1**, the integration manifest becomes another stale truth surface; derive checkable fields from pinned source and make drift fail. **N2**, compatibility shims become permanent; give each an owner and removal trigger. **N3**, a sandbox can be mistaken for production; carry reality status through UI, messages and metrics. **N4**, an expanded audit creates more bureaucracy; attach this evidence to existing work, rather than installing another general protocol.

Residual dissent: keeping #93 independent speeds founder-facing proof but may increase later composition work. Resolve by comparing its actual dependencies and recovery behavior with the selected owner before adoption. Static DurableWorkflow remains the fallback and may win outright.

**Final protocol decision: EXPERIMENT.** This authorizes no new external effects. Proposed owner roles are not people assigned or notified by this audit. Rollback is reverting a bounded implementation while retaining its evidence; stop on weaker authority, duplicate consequence, lost provenance, or a second active institutional truth.

## What is complete and what remains

Completed: repository/branch/open-PR inventory; selected source and draft inspection; current CI/review checks; 13 offline negative reproductions; two checks of existing draft repairs; pinned evidence, preservation-aware ownership diagnosis and ordered repair specifications.

Unfinished by design of this audit: a complete review of all historical diffs; deployed-environment validation; full suite reruns; actual fixes merged into canonical branches; independent acceptance testing; founder ratification of runtime adoption; real founder authentication and operating inbox; a real-world accepted goal closure.

**The next highest-value change is WMI authentication plus the real packaged bridge entrypoint, followed by shared replay/integrity repair.** Once those are dependable, advance the founder loop using existing PR #93 work and measure a complete outcome. More names, charters, agents, platforms or compiler phases do not substitute for that closure.
