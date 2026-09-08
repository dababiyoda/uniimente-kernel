# Repository Rationalization Plan

## SR-001 adoption handoff — draft submissions, 2026-09-08

This package repairs shared admission/history/recovery mechanisms and connects
the real producer and consumer at exact revisions. It is a submitted integration
candidate, not an all-green adoption gate or complete founder workflow.

| Review order | Draft and implementation commit | Base / owner |
| --- | --- | --- |
| 1 | [Kernel #98](https://github.com/dababiyoda/uniimente-kernel/pull/98), `3e059c20331d96e05a44daac1b097896aaabde93` | main `bcbb1ab4a0c42cda4a97aec42a11125753962762`; contracts/adapters/events/provenance, existing Consequence Gate |
| 2 | Preserved [WMI #33](https://github.com/dababiyoda/WealthMachineIntelligence/pull/33), `fbc959936610d529bcb89d2782ec5158791aaadb` | main `ec84b6a2eec4efbc07bed7f167da81f5e25d890c`; WMI authentication and packaged startup |
| 3, jointly | [DALEOBANKS #77](https://github.com/dababiyoda/DALEOBANKS/pull/77), `b3c8722eaf1c8118567eea363204622e21b93412` | main `ed5e95d7f48e006d180b972efe138179325c31d2`; producer composition |
| 3, jointly | [WMI #35](https://github.com/dababiyoda/WealthMachineIntelligence/pull/35), `fa11e133500c07cc87f12257ec6993f1b1e77a49` | #33 branch `agent/wmi-auth-packaged-startup-recovery`; consumer composition |

Both consumers pin Kernel boundary package 0.1.1 at the same exact commit. WMI CI
checks out the exact producer commit. The source-binding record 21 captures clean
implementation worktrees, tree hashes, dependency versions, project-source hashes
and 28 installed package files matching the Kernel source byte-for-byte. Later
handoff/evidence commits change documentation only; the implementation pins above
remain the tested subjects. This content binding is not founder authentication.

| Executed evidence | Result and limits |
| --- | --- |
| Kernel focused controls | 138 passed; files/command in evidence 20 |
| Kernel broader suite | 522 passed, 17 failed; all failures retained in 19; main baseline 495 passed before repair |
| Shared-schema static checks | 14 declared dialects checked; 12 local references resolved; runtime missing-format defect separately reproduced (2 failed) then repaired |
| Authority singleton check | Six named authority artifacts, one source each; static evidence only |
| PR94 retained-evidence controls | Preserved #94: 21 passed; disposable shared-primitive compatibility overlay: initial 6 failed/34 passed, then 40 passed after writer-lifecycle fixes; patch retained, not a new runtime branch |
| DALEOBANKS focused controls | 33 passed; broader suite BLOCKED/INCOMPLETE after two safety-review rejections over api.twitter.com access |
| WMI local broader collection | 129 passed, 430 warnings; raw log in WMI evidence 06 |
| WMI pinned cross-consumer rerun | 1 passed, 3 warnings, 2.39s after all three implementation commits existed; actual localhost packaged subprocess, producer replacement, consumer kill/restart, retained result/dissent and negative controls |
| WMI implementation CI | Run 34292000142 at fa11e133: 127 passed, 6 warnings (Python 3.11, tests/ only); separate from local root collection |
| CI lint | 2100 findings, non-blocking --exit-zero, includes preserved generations and producer checkout; CI success is not lint success |
| Docker and local lint | Docker image build/run UNVERIFIED; local ruff unavailable (exit 127) |

Initial failures, intermediate failures, missing dependencies, warnings and
incomplete runs remain in each repository's tests/evidence/shared-recovery.
CI log summary and unmet optional-dependency warnings are in evidence 22, with
the complete upstream run/job reference. No scores/counts are combined into
institutional readiness. PR33's reported 69/126/9 checks and PR94's reported
78/207/1440 plus three baseline failures remain distinct historical evidence.

### Concrete remaining review gates and replacement path

1. Review Kernel #98's strict history, pre-existing grants, replay/append ordering
   and durable claims against the frozen SR01-SR12 controls below. Its 17 broader
   failures assert historical implementation hashes, old checkpoint contracts or
   experiments derived from those subjects. Keep those frozen subjects as
   historical benchmarks; do not rewrite their receipts/hashes or call those
   experiments restored. A separately subject-bound migration/repair evaluation
   of this implementation is still required before those claims can be renewed.
2. Review WMI #33 then the #35/#77 pair at the table's pins. Missing JWT/body
   signature, wrong principal/recipient, altered bytes, duplicate nonces and
   conflicting logical payloads must remain refusals. Legitimate retries return
   retained results. Kernel remains the sole shared semantic owner; no mirror
   is retained as an active fallback.
3. Provide an independently OS/container-isolated offline runner and inspect
   DALEOBANKS network fixtures before retrying its broad suite. The Python guard
   did not establish safe isolation. This is an unavailable test-facility gate,
   not a request for external-network or customer-operation authority. Preserve
   the Docker image build/startup gate separately; localhost evidence cannot fill it.
4. After these gates and independent review, compose the founder loop using #93
   as the inbox candidate and #94 as the appraisal candidate. Delegate #93's
   duplicate writer lock to the shared ledger; retain its distinct subject/head
   checks. Apply the retained #94 lifecycle compatibility patch to a bounded
   composition candidate and rerun its protected appraisal controls. Compare
   #70/#87 implementations without importing either whole branch as sovereign.
   Live routing remains refused: the governed HTTP adapter still needs canonical
   Kernel mediation. Existing ownership settles the direction; no direct-organ
   bypass or alternate authority system is implied.

No default branch was changed: the inspected default implementations still have
the boundary defects this package addresses until separately authorized adoption.
#33 and #94 were rechecked draft/unmerged and at their original heads. No code in
OMNIMORPH, standing cognition, founder enrollment, provider/tool ecosystems,
PumpStation or RailScout was activated or expanded. CMC and VDM remain zero.

Rollback now means retaining the drafts and leaving defaults untouched. Any later
authorized sandbox rollback must stop the exclusive writer, preserve ledger
bytes/head, pending claims and obligations, and refuse unsupported history.
Never truncate evidence, transfer authority by replacement, restore unsigned
admission or blindly retry an uncertain dispatch. Kill/refuse on an invalid
anchor/grant, concurrent writer, corrupt history, identity conflict, fabricated
appraisal, uncertain completion or lost lineage.

The larger dependency remains visible: durable identity and obligations allow
the Egregore to retain a founder goal while execution machinery is replaced;
Standing Cognition and the higher Mission Resolution Router can then choose the
smallest sufficient capability/workflow or justified temporary organization.
OMNIMORPH stays subordinate; static DurableWorkflow wins exact ties. The Golden
Kernel retains authority, protected appraisal retains independent judgment, and
the Developmental Engine must earn each capability through bounded evaluation.
Broad computer use, tools/models, ventures and eventual approved infrastructure
remain future exercised-capability dependencies, not outcomes of this repair.
Founder attention per verified outcome and time to closure remain unmeasured here;
the local security-overhead sample is retained separately and proves no economic
surplus or participant improvement. No new formal strengthening pass occurred.

Contributor handoff for Claude, Kimi, ChatGPT and future maintainers: use this
table, the existing owner map, frozen controls, evidence 18-22 and consumer
Instructions/README. Independent review has not occurred. Continue authorized
ordinary repairs on these branches; reserve merge/deploy/credentials/external
effects for a new ruling. The immediate unblock is the isolated test facility
and subject-bound compatibility review, not another whole-machine architecture.

## Shared recovery package SR-001 — frozen acceptance, 2026-09-08

Scope: the current chat's founder-authorized shared repair after WMI #33.
This paragraph is a summary, not a verbatim direction or authenticated command.
Message timestamp/conversation identifier are not exposed; no invented metadata.
The September 5 audit and its two passes govern; no third pass is performed.
The complete audit artifact was not located (personal-context search returned no
matches). Its counts and historical test counts remain founder-reported. This
package maps the specifically named cases below, not all 816 audited entries.

Inspection snapshots before implementation: Kernel main bcbb1ab; #71 2221705;
#87 dfd491d; #85 d611771; #93 21fb21e; #94 5e2f221 (Phase3 base c137e86).
DALEOBANKS main ed5e95d; #71 a13f279; #74 ecbb4b7. WMI main ec84b6a;
#31 45e3d02; #32 efbf524; #33 fbc9599. Exact SHAs are retained in the linked
PR inspection/handoff evidence. #33/#94 are preserved, draft and unchanged.
Inspected: shared ledger/spine/gate/transport/adapters, owner map, wire schemas,
both real bridge consumers, their tests, PR changes and existing rationalization.
PR #85 subject-binding is a useful evidence primitive, not proof about dirty code.
#93 wrapper checks do not repair shared consumers; #94 appraisal remains a
protected comparison/dependency for subsequent runtime composition, not imported
as a new whole-machine branch. Other audit categories are outside this package.

Frozen controls (all safety controls must refuse AND positive controls succeed;
no statistical superiority threshold or external-outcome claim):

| ID | Reproduced/named failure and fixed acceptance rule |
| --- | --- |
| SR01 | Missing/blank keys or credentials, invalid signatures, unknown protocol/schema versions refuse; no unsigned fallback |
| SR02 | Sign exact bytes plus sender, recipient, operation, request binding and logical key; altered/context-mismatched bytes refuse |
| SR03 | Recompute genesis, bind expected constitution, reject empty/partial/malformed/foreign history; unsupported amendment records refuse |
| SR04 | Rebuild accepted event IDs and payload binding from verified durable history; conflicting reuse refuses |
| SR05 | Definite append failure leaves memory/ID unconsumed; uncertain write or dispatch requires reconciliation, never blind redispatch |
| SR06 | One writer enforced by OS file lock; competing process refuses. Concurrent in-process claims serialize at the same durable boundary |
| SR07 | Logical caller/operation/key binds request digest; fresh nonce retry returns retained result; conflicting payload refuses |
| SR08 | Translation uses deterministic namespaced IDs and original observation time; missing observation time is unresolved/refused |
| SR09 | External execution without a registered pre-existing valid grant never invokes executor; uncertain effects remain unsettled |
| SR10 | Full canonical nested schema validation, version agreement and required dissent survive real producer/consumer exchange |
| SR11 | Existing #94 fabricated-evidence and appraisal controls remain a separately pinned gate, not caller acceptance |
| SR12 | Fresh process reconstructs state; retained result is unchanged, process-local cache replacement grants no authority |

Declare limits before tests: local POSIX filesystem, one durable writer per
ledger, threads serialized, no distributed consensus or exactly-once claim.
Legacy hash format is preserved; timestamps omitted from legacy hashes cannot be
retroactively authenticated. Prefix truncation needs a separately supplied head
commitment; chain self-consistency alone cannot detect an attacker replacing the
entire chain. No amendment authority is invented. Harmless computation may have
run before a crash; an outstanding claim becomes RECONCILIATION_REQUIRED.
Docker is unavailable; retain image-build/run gap and use localhost composition.
No production credential, founder enrollment, merge, deployment or external act.

Integration path: Kernel-owned versioned boundary dependency, then WMI adapter
stacked on #33, then DALEOBANKS adapter. No permanent three-way security mirrors.
Transport status is derived from canonical EventSpine/EvidenceLedger, not a second
truth engine. HTTP is an adapter carrier only; default organ-to-organ bypass stays
refused. Only explicit synthetic localhost composition is exercised here; lawful
live routing/admission remains a separate review gate, not a runtime flag grant.

The full anatomy remains active intent: Alfonso/Golden Kernel, developmental
substrate, Developmental Engine, Egregore and reality. These repairs enable
mission continuity, not 24/7 operation. Broad tools/models/computer use, temporary
organizations, ventures and approved hardware still require exercised capability
and authorized consequence evidence. Router above OMNIMORPH; static workflow wins
ties; five powers remain separate. CMC/VDM/external outcomes do not increment.

## SR-001 implementation record — bounded integration recovery

Status: EXPERIMENT; draft adoption candidate, not a completed integration gate.
This is an implementation check under the existing September 5 decision, not
another strengthening pass. No independent human/model review is claimed.

### Intent, scope and source distinctions

The current founder directive is active manual development direction. Its exact
message timestamp and conversation ID are unavailable; this record summarizes it
and does not manufacture an authenticated runtime command. Project-memory
summaries (September 3–7) are summaries, not complete transcripts or new authority.
The nine supplied text files were inspected for relevant continuity, authority,
recovery and capability claims; longer documents received targeted inspection,
not an exhaustive factual audit. Their aspirational claims about flawless
receipts, automatic policy rewriting and unlimited autonomy are not implemented
facts. Source 06's automatic policy deployment conflicts with the current
explicit prohibition; that proposed activation is superseded, its broader
capability ambition remains exploratory. Source 07's endless unattended execution
is needs_evidence. Source 08's bounded authority envelope remains a design goal.

One current bottleneck: make authenticated internal work retain logical identity
and evidence through retry and process replacement. Canonical owner remains the
Kernel; organs own their adapter composition. WMI #33 and Kernel #94 remain
preserved unmerged dependencies/comparison points, not default-branch repairs.

### Source disposition and exact inspected revisions

| Source | Head | Base at inspection | Disposition in SR-001 |
| --- | --- | --- | --- |
| Kernel main | bcbb1ab4a0c42cda4a97aec42a11125753962762 | — | adopt as dependency/base; baseline 495 passes executed |
| Kernel #71 | 2221705421eed655e5edcb0608593cdf9d3cd72b | bcbb1ab4a0c42cda4a97aec42a11125753962762 | extract specific admission/integrity mechanisms |
| Kernel #87 | dfd491d8b34fa963e4902008b5d8dc7690fdde63 | 2221705421eed655e5edcb0608593cdf9d3cd72b | extract replay/grant/transport repairs; benchmark runtime; do not import amendment by caller string |
| Kernel #85 | d611771a38b2679f6f8b5c6c57e819ff0d433b53 | 542c8f576eea0d9511a148b4204a1dd531a4adbd | extract evaluated-subject binding in evidence; a Git HEAD alone misses dirty source |
| Kernel #93 | 21fb21ed803f43e47acb8e6420f6cdc4f74925cd | bcbb1ab4a0c42cda4a97aec42a11125753962762 | benchmark founder-loop candidate; shared repair does not replace its distinct appraisal protections |
| Kernel #94 | 5e2f221b1911309db10de26246065553c1bdcbfc | c137e863851f0f7d8dce7bcb060b4e1d5066ea80 | benchmark protected appraisal; preserve draft/Phase3 stack |
| DALEOBANKS #71 | a13f279210c3dc9722a61c1714b17b064a8c05c8 | 1ba3b85474af60c1c0b1f34159f464cf69011e18 | extract missing-key refusal; preserve alternate line |
| DALEOBANKS #74 | ecbb4b744b69f8ea16ed38ba2f0711c1969547b5 | ed5e95d7f48e006d180b972efe138179325c31d2 | extract explicit compatibility/identity limitations |
| WMI #31 | 45e3d02e1e1fd71433a810b390e337c39097cef7 | 6549984a22a171f68b268b775f19192aee599609 | extract refusal mechanism, not full branch |
| WMI #32 | efbf524113c3c1805264459f64442e77fe1dd279 | ec84b6a2eec4efbc07bed7f167da81f5e25d890c | extract non-isolated shared-key labeling |
| WMI #33 | fbc959936610d529bcb89d2782ec5158791aaadb | ec84b6a2eec4efbc07bed7f167da81f5e25d890c | adopt as dependency; separate consumer PR stacked here |

Other open PRs are deferred from this bounded refresh, not adjudicated.
Historical transport mirrors are superseded with Git lineage; thin import
adapters retain their canonical source, owner, supported version, expiry,
removal and failure rules in module headers. No alternate branch is deleted.

### Mechanism cards and mutation lineage

**M1 — retained-history admission.** Sources: existing EvidenceLedger and
[Certificate Transparency RFC 9162](https://www.rfc-editor.org/rfc/rfc9162.html).
Primitive/invariant: recompute commitments and compare an expected anchor before
using retained history. CT audits certificate issuance; this package keeps the
existing linear hash chain rather than adding CT, Merkle trees or consensus.
State/memory: versioned records, predecessor hashes, expected constitution/head.
Actors/authority: Kernel writer and read-only verifier; readers cannot amend law.
Visible: record bytes/lineage; hidden or unavailable: actual-world truth and any
independently trusted checkpoint not supplied. Resources: disk, fsync and full
history verification. Threshold/selection: every link and supported version must
verify; first mismatch refuses. Feedback/incentive: a corrupt history cannot buy
fresh institutional status by presenting an empty file. Proof: retained hashes
and negative controls, not truth or permission. Recovery: preserve bytes and
reconcile; never rewrite old evidence to today's anchor. External consequence:
none in the package.
Three material mutations: (1) certificate-history admission becomes
constitution-bound institutional replay, with unsupported amendments refused;
(2) append acknowledgment follows durable flush and uncertain writes fence later
work; (3) old hash format is read without silently assigning it new timestamp
coverage, while an independent expected head detects prefix truncation.
New failures: missing trusted head limits truncation detection; full scans cost
more as history grows; partial writes deliberately stop progress. Decisive tests:
SR03/SR05, prefix truncation, foreign anchor and malformed history controls.

**M2 — exact-context admission without inherited permission.** Sources:
[NIST SP 800-207](https://csrc.nist.gov/pubs/sp/800/207/final),
[JWT BCP RFC 8725](https://www.rfc-editor.org/rfc/rfc8725.html), Kernel/WMI
existing HMAC/JWT implementations. Primitive: authenticate each request for a
specific resource and keep authorization separate. State: configured key,
issuer/audience, supported protocol, durable nonce records. Transition:
untrusted bytes to eligible transport or refusal. Actors: producer, consumer,
canonical policy issuer, Gate; no local token or grant minting. Visible:
context/claims and byte commitments; hidden: key material; key holders are NOT
isolated from one another. Resources: verification and bounded operation claim;
no increased budget. Threshold: both WMI JWT and body authentication plus schema
and caller/sender agreement. Proof: positive and tampered-byte tests. Memory:
nonces survive process loss. Feedback/incentive: no reward for omitting config.
Recovery: fresh nonce can retry the same logical key; unsigned/version downgrade
cannot. Consequence: only a pre-existing canonical grant can admit an executor.
Mutations: (1) HMAC binds request/response bytes, recipient, operation, status and
request correlation in a structured domain, using unchanged SHA-256/HMAC;
(2) transport freshness is separate from application identity, so lawful retries
recover a result instead of acquiring new work; (3) a caller's low-consequence
label cannot cause the Gate to fill in a missing grant. Additional change: live
direct-organ routing remains refused while synthetic localhost compatibility is
exercised. New failures: configuration/clock/version errors refuse useful work;
shared-key compromise affects all holders; live mediated routing remains a gate.
Decisive tests: SR01/SR02/SR07/SR09 and real JWT/body producer-consumer exchange.

**M3 — replaceable execution with retained obligations.** Sources: existing
EventSpine/DurableWorkflow; POSIX advisory
[file locking](https://docs.python.org/3/library/fcntl.html);
high-reliability organizations' independent judgment and reluctance to simplify
failure ([AHRQ primer](https://psnet.ahrq.gov/primer/high-reliability)).
Primitive: claim before invocation, durably record result, preserve uncertainty.
State: accepted IDs, logical claim, result, evaluator dissent and unresolved
dispatch. Actors: writer, worker, reader/appraiser and operator. Authority:
replacement receives no predecessor permission. Visible: causal retained state;
hidden: effects whose acknowledgments were lost. Resources: one writer per ledger,
serialized internal claims; no distributed performance claim. Selection/threshold:
only an unclaimed operation may execute; uncertain completion reconciles.
Proof: process restart, competing-writer refusal, concurrent duplicate controls.
Memory/feedback: failed predictions and results retained; no automatic promotion.
Recovery/dissolution: release file lock on close, retain unfinished obligations;
old executable/checkpoint versions require explicit reviewed migration.
Mutations: (1) retry eligibility is an explicit harmless/idempotent step contract,
not a default after arbitrary executor exceptions; (2) worker/process replacement
reconstructs nonce and logical-operation state but not authority; (3) retained
worker output still needs #94's protected evidence appraisal to qualify mission
closure. New failures: one-writer availability tradeoff, reconciliation burden,
old experimental checkpoint incompatibility. Decisive tests: SR04–SR07/SR12 and
the separately pinned #94 appraisal overlay; not a universal replacement proof.

**Modular distribution** is ordinary integration, not a fourth invention:
one exact-revision Kernel boundary package supplies both real consumers. Full
Draft 2020-12 validation uses jsonschema 4.26.0 (MIT license/METADATA inspected),
with FormatChecker explicitly enabled; no third-party implementation was copied.
Python standard cryptographic/file primitives are unchanged. The custom
interaction is stable internal work through replacement with refusal preserved
across both consumers. General novelty, superiority and a compounding economic
advantage are unproven. Conventional workflow remains the strongest baseline.

### Eight-side implementation mapping

Internal transaction: authorized work should reach an evidence-backed result
despite interruption. No market transaction or external acceptance is invented.

| Side | Mechanism, proof and failure disposition | Super-node | Reinforces |
| --- | --- | --- | --- |
| 1 Failure geometry | frozen SR01–12; failed cases retained; uncertain ack reconciles | Proof/Truth | 5, 8 |
| 2 Participants | founder authority distinct from writer, worker, evaluator and Gate; shared-key holders explicitly non-isolated | Eligibility | 3, 5 |
| 3 Eligibility | JWT plus exact-context HMAC, strict versions and pre-existing grants; missing config refuses | Eligibility | 4, 8 |
| 4 Routing | governed adapter carrier only; live direct-organ bypass refused; fresh nonce retry retains logical operation | Default Routing | 3, 6 |
| 5 Proof | recomputed genesis/history, full schemas and protected #94 appraisal; hashes do not establish factual truth | Proof/Truth | 1, 7 |
| 6 Resources | one OS-enforced writer, durable dispatch claims, uncertainty retains obligation; overhead measured separately | Resource/Settlement | 4, 8 |
| 7 Reuse | one pinned boundary dependency, two actual consumers; old mirrors preserved in Git | Default Routing, Proof/Truth | 3, 5 |
| 8 Continuity | restart, reconciliation, fail-closed replacement and explicit rollback gate; cannot discard unresolved effects | Proof/Truth, Resource/Settlement | 1, 6 |

Removing admission reopens bypass; removing durable claims reopens duplicate work;
removing appraisal reopens false closure; removing ownership/version pins restores
diverging mirrors. Each removal is therefore a kill trigger, not a convenience.

### Dissent, loops and limits

Steward/architect/adversary/operator/evidence-guardian perspectives below are
one assistant's review prompts, NOT independent reviewers or additional passes.
Steward: preserve 24/7 goal continuity and broad tools as active destination;
architect: avoid importing #87/#94 wholesale; adversary: hashes and JWT shared
secrets cannot authenticate Alfonso; operator: one writer and historical workflow
incompatibility increase manual repair burden; evidence guardian: keep every red,
blocked and unknown result visible. Dissent is accepted for draft review only.
Independent adoption review remains required before any later merge ruling.

Operational loop is tested only at internal retry/result retention. Resource loop
has a small local overhead sample, not verified efficiency gains. Institutional
trust, lower founder intervention and regenerative participant gains remain
unmeasured. No claim of improvement in three consequential decisions is made.
All four longer loops remain hypotheses until accepted mission/outcome evidence.
Founder Intervention Minutes per Verified Outcome and authenticated-intention
to closure time are UNKNOWN because no qualifying outcome occurred. CMC/VDM0.

No authority, credential or evaluator is replaced by these commits. PR93's
wrapper uses its own lock: before composition, delegate its writer ownership to
the shared ledger (never acquire the same .lock twice), preserving its distinct
manifest/appraisal checks. PR94 requires the retained lifecycle compatibility
patch before the shared ledger can be used by its restart fixtures. Broader
provider/tool/organization replacement, production key custody, trusted checkpoint
custody and historical constitutional amendment policy remain separate gates.

## Executive diagnosis

UNIIMENTE has strong doctrine, increasingly capable runtime modules, and explicit organ boundaries. Its primary maintainability risk is no longer missing capability. It is the multiplication of truth surfaces:

- canonical kernel contracts plus historical mirrored protocol modules;
- upstream repositories plus copied or quarantined repository snapshots;
- generated clients and compiled output stored beside authored source;
- proof artifacts, handoff documents, issues, and README claims describing overlapping states;
- multiple implementation eras remaining discoverable without a clear canonicality marker.

The remedy is not a monorepo rewrite. It is a strict source-of-truth hierarchy and staged extraction.

## Canonical ownership

| Concern | Canonical owner | Organs may contain |
|---|---|---|
| Constitution, authority, shared contracts, event spine, evidence, consequence policy | `uniimente-kernel` | pinned SDK dependency, adapters, compatibility shims |
| Public identity, media perception, publication operations | `DALEOBANKS` | organ-specific workflows and local state |
| Venture evaluation, underwriting, portfolio recommendations | `WealthMachineIntelligence` | organ-specific models and local state |
| Founder cockpit / institutional digital twin | integration application | projections and commands through contracts; no duplicate governance engine |
| Archived source and external evidence | content-addressed archive outside authored source tree | manifest, hash, provenance pointer only |

## Immediate rules

1. No repository snapshot, ZIP, build directory, dependency tree, or generated client belongs in authored source unless a documented exception exists.
2. Every copied implementation must declare `canonical_source`, `sync_method`, `version`, and `removal_trigger`.
3. Compatibility shims may re-export canonical modules but may not fork behavior.
4. README status claims must point to executable proof or be labeled proposed, simulated, or historical.
5. Proof artifacts are append-only evidence; generated build output is disposable and reproducible.
6. The cockpit consumes governance; it does not become a second constitution, event spine, ledger, autonomy ladder, or consequence gate.

## Migration waves

### Wave 0 - inventory and freeze

- Generate a machine-readable repository manifest.
- Classify every top-level path as authored source, generated, vendored, evidence, archive, runtime state, or documentation.
- Freeze new copied-source additions.
- Record exact and semantic duplicates.

### Wave 1 - hygiene

- Remove nested ZIPs and compiled output from source branches after hashes and provenance pointers are preserved.
- Expand `.gitignore` consistently across repositories.
- Add canonicality headers to compatibility shims and historical documents.
- Introduce repository maps and owner files.

### Wave 2 - contract convergence

- Complete the existing kernel contract extraction work.
- Replace organ-local copies with version-pinned SDK imports.
- Add parity tests at each organ boundary.
- Publish a compatibility and deprecation matrix.

### Wave 3 - collaboration substrate

- Add Founder Intent Ledger records.
- Require the Recursive Collaboration Protocol for material PRs.
- Add ADR and RFC indexes.
- Add automated checks for duplicate schemas, copied modules, broken provenance links, and unclassified top-level paths.

### Wave 4 - cockpit integration

- Define the cockpit as a replaceable projection and command client.
- Move embedded organ source trees to pinned dependencies or service boundaries.
- Preserve simulation fixtures separately from institutional evidence.
- Display canonical source, reality status, policy version, and evidence provenance for every major object.

## Kill criteria

Stop or regress a consolidation when it:

- weakens fail-closed behavior;
- erases provenance or contributor lineage;
- requires coordinated releases without a compatibility window;
- makes an organ unable to operate safely during kernel unavailability;
- converts historical evidence into mutable application state;
- increases the number of authorities or execution paths;
- creates a monolith without measurable maintenance or reliability advantage.

## Success metrics

- duplicate canonical implementations: 0;
- unclassified top-level paths: 0;
- material PRs with complete deliberation records: 100%;
- shared contract parity failures caught before merge: 100%;
- generated or archived bytes in authored source: trending to 0;
- time for a new contributor to identify canonical owners and run tests: under 30 minutes;
- founder intentions silently dropped: 0.
# SR-001 format-check correction (implementation check, 2026-09-08)

After initial draft PR #98 commit a84f408494bec219a397b67c9b831e80150f1c27,
two additional controls showed that jsonschema silently accepted a malformed
date-time when its optional checker was unavailable. This corrects the earlier
claim of complete runtime format validation; the earlier green checks did not
establish that property. The initial failures remain in evidence file 18.

Boundary package 0.1.1 requires rfc3339-validator 0.1.4 (installed MIT license
inspected). The canonical validator now refuses to load any registered schema
whose declared formats have no implementation. No cryptographic primitive,
authority, schema meaning, old evidence or frozen experiment threshold changed.
The existing wire contracts remain peripheral contracts; their compatibility is
not a claim that optional peripheral fields satisfy canonical mission lineage.
Canonical translation still requires the original observation/assessment time.

Executed checks after repair: 138 focused passes; broader suite 522 passes and
17 failures. These 17 are regressions against historical frozen migration/repair
experiments, not PR #94's three reported baseline failures. They remain an
adoption blocker; frozen hashes and old unsafe retry assumptions were not retuned.
Main baseline previously passed 495 tests. See evidence 18-20 and the final
subject binding. Documentation review perspectives remain one assistant's work,
not independent review or a third strengthening pass.
