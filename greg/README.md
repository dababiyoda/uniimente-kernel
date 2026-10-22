# GREG — the persistent, founder-sovereign operating layer (first-body candidate)

Current bounded product integration: [Seed Genome on the canonical GREG path](../docs/cortex/GREG_SEED_GENOME.md). The older sandbox experiment and its frozen results remain historical evidence.

> **Founder-effect rule (INTENT-0030, INTENT-2026-09-25-EGREGORE-ECOLOGY):** the egregore is built
> as real, running mechanisms. The *effects* (persistence, self-direction inside scope,
> self-healing, capability genesis, continuity, community influence, Jarvis-like integration)
> are literal engineering targets. The biological surface (cells, tissues, organs) is not.

```
HARDWARE → macOS / Linux → OS supervisor (launchd | systemd | supervisord)
        → GREG body  (greg/body.py: lifecycle, inbox, waiting, recovery — no policy)
        → Kernel     (EvidenceLedger, EventSpine, policy engine, ConsequenceGate, GrantIssuer)
        → capabilities (broker: API → CLI → OS automation → visual; acquired by Capability Genesis)
        → authorized effects, receipts, re-observed outcomes → morning tribunal
```

## One mind, many competencies (Levin mapping, mechanically)

Every competency is a goal-directed feedback loop with a bounded **light cone**
(`greg/lightcone.py`: capabilities × targets × consequence ceiling × budget × horizon).
Founder mandate ⊇ mission ⊇ worker lease (one short-lived passport per action) ⊇ single
Gate-mediated effect. Larger loops set goals for smaller ones; containment makes every child
scope strictly inside its parent. Unity of agency comes from one ledger, one founder key, one
Constitution and one Gate — not from a hierarchy of personas.

| Founder metaphor | Real mechanism here | Evidence |
|---|---|---|
| Infinite Goal Chase / regenerative pressure | `missions.py`: observe → discrepancy → highest-leverage strategy; infinite missions climb a setpoint ladder and never close | `test_infinite_mission_climbs_ladder_then_heals_drift` |
| Self-healing / homeostasis | holding missions re-observe on cadence; drift re-triggers pursuit; surprises trigger replanning | same test; `test_ineffective_action_is_a_surprise…` |
| Morphogenesis | `genesis.py`: CapabilityDeficit → frozen oracle → search (attached, detached, installed software, builder) → isolated independent verification → register → attach under founder scope → resume | `test_capability_genesis_acquires_installed_tool…`, `test_genesis_rejects_a_lying_tool…` |
| Immune system | Ed25519 founder commands, replay refusal, quarantine of tampered binaries, injection quarantine, no-network isolation, redirects repaired as urllib repairs them, then re-checked per hop against the egress allowlist with credentials kept on their origin (scheme, host, port) (`egress.py`; also the OCI registry client `foundry/systems/containers.py`) | `test_greg_founder_and_scope.py`, `test_tampered_acquired_binary…`, `test_credentials_are_never_forwarded_to_another_host` |
| Survival / immortality | durable ledger, OS-supervised restart, reconciliation, replaceable hardware; shutdown always wins (exit 0 is never restarted) | `tests/integration/test_greg_body_supervised.py` |
| Community influence | `dataplane.py`: community content is untrusted evidence that can move priorities, never commands; injection patterns are matched on every way the text reads (`identity/text.py`: invisible set derived from Unicode properties, NFKC, look-alike letters folded, whitespace collapsed; tag-character and variation-selector smuggling decoded); an instruction pattern, or concealing invisible characters together with a role marker (ChatML, markdown, bracket or line-leading), quarantines the item; either alone only flags, so header lines, ANSI logs and orthographic joiners stay usable evidence | `test_external_injection_is_flagged…`, `test_greg_dataplane_invisible.py` |
| Night shift → morning tribunal | `tribunal.py`: 13-question report from evidence; signed critique becomes exclusions and regression obligations without rewriting history | `test_founder_critique_excludes_strategy…` |
| Second venture and its books (node N7) | Business cases carry `--venture`. A procedure ratified from one venture's verified cases runs in another with `greg sop run --venture`; that is a capability transplant. `--approve-writes` keeps GREG asking before it drafts or settles, which a ratified procedure can pre-approve. Templates record their normalized inputs in signed provenance, so a business procedure asks only for reference, buyer, offer, price and acceptance; every taught run must still be rebuilt exactly. `venture_books.transfers` measures founder interventions, model spend and hours to close per verified outcome on two or more closed cases in the second venture. Founder-only `TREASURY_REQUIREMENTS` (`greg treasury set`) signs per-tier amounts. `venture_books.books` runs N3-closed revenue through the Kernel's own waterfall (`capital/treasury.py`, `capital/allocation-policy.yaml`). Surplus exists only after every tier above reinvestment is funded; with nothing signed there is no figure. GREG moves no money. `venture_compounding` measures N7 | `test_greg_venture_books.py` (17 tests; 15 mutations checked: 14 caught, 1 equivalent and removed) |
| Work with a named person (node N6) | `greg mission new shared-work --task --person --relationship contract (or employment) --function human.<task> --deliverable --acceptance`. GREG writes the handoff first, including the person's right to decline. Three steps each close one `HUMAN_WORK` ask only when observed in the case folder: the person's written agreement, their deliverable, and Alfonso's `ACCEPT` review. GREG then records the outcome; it contacts, hires and pays no one. A step may carry `declined_if`: an observed refusal is honored as legitimate, so the ask is withdrawn, the step is never asked again, and Alfonso chooses the next move. `human_work_shared` measures N6 and needs Alfonso's acceptance, which attests the person and the relationship | `test_greg_shared_work.py` (15 tests; 16 mutations caught) |
| SOP compounding (node N4) | `sop.py`: three verified closures with the same capabilities and signed shape → a proposal whose workflow is the least general generalization of the signed specs (only parameter positions become inputs; checks, operators, capabilities and the light cone must match in every run; every run is rebuilt from it before it is proposed) → founder `SOP_RATIFY`, optionally pre-approving steps approved in every verified run (internal at most, free) → `greg sop run` makes a run with zero model calls that Alfonso signs. `sop.trend` measures founder interventions, model calls and model cost per verified outcome before and after; `sop_compounding` measures N4 | `test_repeated_verified_procedure…`, `test_greg_sop_compounding.py` (26 tests; 23 mutations caught) |
| House of compute | `compute.py`: telemetry → sustained bottleneck → one recommendation with alternatives; nodes join with bounded identity | `test_compute_bottleneck…`, `test_new_compute_node…` |
| Founder asks (directive §60) | `asks.py`: the one path for every `decision.requested`. A resource ask (account, compute, software, build, professional, human worker, availability, spend, mandate) must carry measured evidence, costed options each with its expected effect, one option that costs nothing, uncertainty and the authority it needs, including spend; a missing element raises and records nothing. Wording that presses (urgency without an evidenced deadline), pleads, or frames refusal as harm to GREG is withheld from every founder surface, and the attempt is kept as `ask.wording_withheld`; text Alfonso signed is never screened. Asking grants nothing | `test_greg_founder_asks.py` (50 tests), `test_greg_phone_asks.py` (Chromium, iPhone profile); 20 mutations caught |
| Account access (§60, first example) | When GitHub refuses reads the brief needs (403/429, or 404 for a private repository without a token), the brief is delivered with its gaps and GREG raises ONE non-blocking `ACCOUNT_ACCESS` ask with the refusals as evidence; being offline never asks. `greg secret set|remove|list`: a credential for a declared handle only, from a hidden prompt or stdin, never argv; stored mode 0600 on the body, never in the ledger or inbox | `test_greg_account_access.py` (7 tests; 8 mutations caught) |
| Preconditions and N2 without a model | A strategy may `requires` checks that must be observed passing before it acts; the separate-process appraiser independently confirms it (`preconditions_honored`). Two plain-words, no-model missions need a capability GREG lacks: "Verify <file> against sha256 <hex>" (`verify-download`) and "Confirm <file> is at most N words" (`word-limit`); genesis acquires and verifies the tool, filing the record asks first, and a mismatch is never recorded as verified | `test_greg_verify_download.py` (11 tests; 7 mutations caught), `test_greg_chromebook_rehearsal.py` (N1 and N2 exits structurally met on one body; its test key keeps `greg path` at N1) |
| Human work (§60: a licensed professional, a human worker) | A step whose function is `professional.<field>` or `human.<task>` is never searched for, built or attached: the engine raises ONE `HUMAN_WORK` ask (resource `professional` or `human_worker`) with the check that will observe the deliverable, costed options (you, a person you choose at their unknown fee, revise, abandon), no spend and no contact. An answer is not the work; the ask is withdrawn and the mission continues when the deliverable exists. GREG checks that it exists, never its professional quality. Where an answer is only a record (this ask, and account access), the console, phone and status say so beside the buttons. `greg mission new human-work --function professional.legal_review --purpose ...` | `test_greg_human_work.py` (10 tests), `test_greg_phone_asks.py`; 10 mutations caught |
| Founder tier for N1-N4, N6, N7 (#137 verifier; #138 port) | A ledger proves which enrolled key signed a closure, not whether it is Alfonso's key or a test key. `greg body designate` (with a passphrase-protected key) and `greg founder attest` sign a `FOUNDER_TIER` attestation only after decrypting the key file; it grants nothing. `metrics.founder_tier` puts a mission at the founder tier only when its MISSION was signed by the enrolled founder key (never a device) that had attested before the mission was registered. `business_loop_closed`, `sop_compounding`, `human_work_shared` and `venture_compounding` report `structurally_met` and `evidence_level`. `met`, which moves `greg path`, also needs every closure they rest on to be at the founder tier, so test keys, fixtures and `--no-passphrase` rehearsals stay `STRUCTURAL_CANDIDATE`. Residual: the tier is the key holder's claim of passphrase custody, not verified custody. The CLI's refusal is the only custody check; the body sees only the public key, so anything holding an enrolled key, protected or not (an unprotected rehearsal or fixture key included), can sign `FOUNDER_TIER` directly and its later closures read `FOUNDER_TIER` (`test_greg_closure_integrity.py` pins this). A met result carries `founder_tier_basis` saying so; whether N1 needs more than this claim is an open founder decision (`greg/path.json` N1). N1 and N2 (#138's structural-candidate gate, 673726a) use the same rule instead of a hardcoded `met=False`, so a founder-tier run can clear N1; `greg vepmc` adds `structural_candidate_count`, `founder_tier_count` and a per-row `evidence_level` | `test_greg_founder_tier.py`; founder-tier variants of the N3, N4 and N6 body tests; N7 structural plus refusal; `test_developmental_inheritance.py` and `test_greg_vepmc_path.py` (test key vs passphrase key) for N1/N2; 6 mutations caught (`check_cortex_mutants.py`, group "founder tier") plus 1 in group "founder tier (body)" |
| Closure integrity (installed-body review, 2026-10-14) | The appraiser re-admits every completed action against the founder-signed light cone and accepts an out-of-cone action only after an exact-scope approval carried by a re-verified founder (or delegated device) `DECISION`, or a step the signed mission itself pre-approves. A ratified SOP run carries `pre_approved_steps` (one exact free internal strategy each) instead of widening its cone. `fs.write` writes only the file its signed target names. N3 and N6 refuse a case where GREG wrote a person's evidence file; N3 counts only observed (not declined) work. A read-only sensor's file notices the payment step within minutes. `SCOPE_RENEWAL` takes no decision (a new signed MISSION renews it). An `external` node passes only with recorded external evidence (Alfonso's acceptances). Signing commands refuse a missing key plainly; `greg path --node` reads a later node. `docs/collaboration/INSTALLED-BODY-CONVERGENCE-2026-10-14.md` records each finding and residual | `test_greg_closure_integrity.py` (18 tests), `test_greg_human_work_latency.py`, `test_greg_chromebook_install.py`; 11 mutations in `check_cortex_mutants.py` group "closure integrity" |
| One business case (node N3) | `greg mission new business-case`: a founder-signed case fixes buyer, price and acceptance terms, then runs in the Kernel's commercial order (`business/commercial_loop.py`). GREG drafts the offer and writes the settlement; people send, collect, deliver and confirm through costed `HUMAN_WORK` asks. `business.reconcile` counts payment only for exactly one statement posting of the signed amount and currency carrying the case reference, to the cent; the settlement waits for payment, delivery and confirmation. `business_loop_closed` measures N3 and needs your acceptance; a step the person declined is not observed work, and a case where any GREG write landed on a file a person's step is measured by (e.g. a statement GREG wrote) never counts (`human_work_shared` applies the same rule) | `test_greg_business_case.py` (20 tests; 10 mutations caught) |

## Hands: workers, computer use, DALEOBANKS (execution fabric)

GREG commissions temporary workers and operates a browser through the same signed-mission -> grant -> Gate path.
Workers never inherit GREG's authority, never judge their own work, never push or merge.

| Capability | Consequence | What it does |
|---|---|---|
| `worker.commission` | internal_write, signed spend cap | One WorkOrder: a real tool-using worker (Claude Code CLI; Codex/Aider by argv template) edits a private clone (`repository`) or writes a deliverable from read-only inputs (`document`); GREG collects the diff, runs acceptance with no network, commits on `greg/<order>` (`greg/workers.py`). On Linux with Landlock the worker process and its children read only the host runtime and write only their work directory: no Body home (ledger, witness and device keys, inbox), no other workspace or order, no source checkout, no other process's environment; the evidence records the confinement, or that the host had none (`greg/isolation.py` `worker_grants`). Network is not confined (the provider needs it). A worker dies with its Body (Linux parent-death signal); its interrupted dispatch is reconciled, never re-run blind, and every grant runs its own worker in a fresh clone: evidence a stopped Body wrote before its receipt is never reused (`tests/integration/test_greg_worker_midflight_kill.py`). Limit: an interrupted run's provider spend is not observable, so either reconciliation answer books its signed cap, "not executed" included, and the RECONCILIATION ask says so before you answer; a dispatch whose Body stopped before the worker started (while cloning) is booked the same way, overstating spend by up to the cap; the separate appraiser does not yet re-derive that booking (it re-admits DONE actions only); and a run whose evidence exists but whose receipt was never recorded cannot be accepted even if you answer that it executed: its cap is booked and the mission asks once (`NO_STRATEGY`) instead of closing |
| Worker confinement (founder's `greg init --worker-confinement`) | body setting | `required` (default): a worker the bubblewrap envelope cannot confine is refused before dispatch, and so is acceptance the envelope cannot host. `supervised`: such a worker runs under process supervision (own session, killed with the body, scrubbed environment, capped output) with #178's Landlock grants as its floor where the kernel has them (it reads only the host runtime and the files named for its order, and writes only its work directory); without Landlock its report says its filesystem and network were NOT confined (it can read whatever the body's user can, including a founder key kept on the body). Its report states which floor ran. Acceptance the envelope cannot host runs with the network denied and, where Landlock exists, confined to its clone. A reviewed provider on an envelope host stays confined; the script worker and confined egress never fall back. `tests/unit/test_greg_worker_confinement_setting.py` |
| `worker.appraise` | read_only sensor | Independent verdict, bound to the WorkOrder's canonical commission receipt in the mission engine's own observation as in the separate appraiser (an order whose grant has no receipt is `REJECTED`): fresh clone at the recorded base, retained patch re-applied, scope + protected surfaces, acceptance re-run with no network and confined like the worker (Landlock: the clone writable, the runtime read-only; the same holds for GREG's own run during commission); protected surface -> `NEEDS_FOUNDER_DECISION`, never acceptance. The evaluator is frozen: a patch that modifies a test the acceptance commands name, or adds or changes a `conftest.py`, `pytest.ini` or `tox.ini`, is `REJECTED`; a changed `pyproject.toml`/`setup.cfg` needs a founder decision. Limit: the acceptance run executes the worker's code, so a change built to subvert the test process itself (exiting 0 at import) is not caught by the exit code alone. A document order with `bound_claims` is accepted only if every sentence is a claim the Mind answered as written against GREG's copy of the inputs (`greg/cognition/restatement.py`); the signed contract applies |
| `browser.session` / `browser.trace` | internal_write / read_only | Disposable real Chromium via Playwright: goto/fill/type/select/click/press/scroll/extract/download/mouse with per-step screenshots; stops at `consequential` steps, unprovisioned credentials and bot challenges; only signed hosts reachable (`greg/computer.py`) |
| `daleobanks.verify` / `daleobanks.publish` / `daleobanks.outcome` | read_only / external_contact / read_only | DALEOBANKS's own EthicsGuard/Critic/PromptFirewall and its publishing gate (ledger, LIVE kill switch, rate governor) in DALEOBANKS's interpreter; a dry-run is reported as a block (`greg/daleobanks_bridge.py`) |

Plain words: `Improve GREG: <objective>` routes to `templates.code_change` (planner `template:code-change`);
`templates.browser_task` and `templates.daleobanks_post` build the other missions. End-to-end runner and real
evidence: `scripts/greg_hands_proof.py`, `docs/evidence/greg-hands/2026-10-02/`.

## Spider-Web compounding (INTENT-2026-09-25-SPIDER-WEB-COMPOUNDING)

The optimization target is one transaction: *Alfonso's authorized intention → verified real-world
outcome → evidence and capability that make the next intention easier.*

The `memory.precedents` read-only tool makes previous actions available to a later signed
mission via `{"capability":"fs.write"}` at `memory:fs.write` (change both together for
another built-in capability). It reports action validation levels and separate local
mission appraisal references; it never upgrades either to external proof. The
founder light cone must include this capability and exact target. It can be detached
with the same signed founder command as other built-ins. Item 17 of the Foundry's
55-system obligation remains partial pending broader, outcome-ranked retrieval.

`artifact.store`, `artifact.inspect` and `artifact.materialize` form one small
content-addressed tool family for item 36. A founder-signed mission imports a file
from an allowed read root or its own workspace at `artifact:<namespace>`; the Gate
receipts the SHA-256 address. A later signed mission can inspect the exact bytes
under that namespace or materialize them once under its own signed
`workspace:<relative_path>`. The source bytes, not just the address, survive body
process death. `greg mission submit mission.json --key ...` invokes these tools by
name like any other mission strategy or sensor; `greg status` lists them and
signed `greg detach artifact.store` disables imports across restarts. See
`tests/integration/test_greg_artifact_process.py` for two complete mission
contracts and real process replacement, and `tests/unit/test_greg_artifacts.py`
for corruption, traversal, wrong namespace, duplicate and scope refusals.

The store is body-local, capped at 256 KiB per object, 512 objects and 64 MiB
total; it is not backed up here.
An orphaned object written before an interrupted Gate receipt is not readable
through the tool; the mission waits for reconciliation, never blindly repeats
the action. Tampered bytes are refused and an earlier local appraisal becomes
refuted on recheck. Genesis built sources use the same storage primitive while
retaining their historical `.py` paths and quarantine evidence. The canonical
ledger remains the only authority/evidence history. A hash shows byte integrity,
not a truthful claim, external attribution, causality or independent witness.
Item 36 remains partial: no large-object streaming, portable off-body artifact
backup, multi-body custody or media distribution has been demonstrated.

| Control point | Mechanism | Evidence |
|---|---|---|
| Eligibility | `CapabilityRegistry.register` refuses a capability that strengthens none of the seven super-nodes; light cones; Ed25519 founder envelopes | `test_spider_web_rule_rejects_capabilities_that_strengthen_nothing` |
| Default routing | `routing.py`: ledger-derived reliability (Laplace) per capability; strategies ranked by expected discrepancy value closed minus cost; each choice recorded with its alternatives | `test_routing_learns_from_one_missions_failure_for_the_next_mission` |
| Proof / truth | `appraisal.py`: a **separate process** re-verifies the founder signature, re-derives checks from receipt bytes, re-observes the world and confirms exactly-once | `test_independent_appraiser_…`, `test_appraiser_refutes_a_false_closure_claim` |
| Proof → routing | an appraiser refutation of the *effect* lowers that capability's reliability for every future mission; refutations for foreign faults do not | `test_appraiser_refutation_of_the_effect_lowers_routing_but_foreign_faults_do_not` |
| Settlement / outcome | `metrics.py`: nine ledger conditions, including a founder-signed first-body designation; external confirmation of hardware ownership remains necessary | `tests/integration/test_greg_vepmc_path.py` |
| Reliability | `repo.pin_audit`: a real, read-only watcher of Kernel/DALEOBANKS/WMI pin consistency (`templates.repo_guardian`) | `test_repository_guardian_holds_then_escalates_real_git_drift_once` |

| Reliability (organs) | `repo.integration_audit` + `templates.integration_watch`: static integration findings with exact commits, blobs and lines (from PR #112); one decision per defect, withdrawn as moot when the world heals, re-raised if it returns | `test_integration_watch_escalates_a_real_authority_defect_once_then_holds_after_the_fix` |

## Phone and browser (2026-09-26)

| Effect | Mechanism | Evidence |
|---|---|---|
| Check and steer GREG from the phone | `DEVICE_ENROLL` (founder-signed) delegates a narrow, expiring key: decide, criticize, pause, resume, stop, never missions, capabilities, rotation or enrollment. `greg serve` (`remote.py`) is loopback-only transport: signed reads, pre-verified commands into the inbox, ledger opened read-only. `phone/` holds a non-extractable WebCrypto Ed25519 key in IndexedDB. Reached over HTTPS through `tailscale serve`. | `test_greg_remote.py` (incl. JS↔Python byte compatibility), `tests/integration/test_greg_phone_e2e.py` (real Chromium, iPhone profile) |
| Use the browser | `browser.render`: installed Chrome/Chromium headless, JavaScript executed. The signed target must be `web:<host of the URL>` (`target_from`). Only that exact origin is reachable: DNS rules plus a dead proxy with the loopback bypass removed, so no third-party beacons, even by IP literal. | `test_greg_browser.py` (hostile beacon control; mutation-tested) |

The strategy tribunal in `evolution/spider_web.py` keeps its four-node vocabulary. `STRATEGY_SUPER_NODES`
is the single tested translation. Dispositions for the rest of the project are in
`docs/collaboration/REPOSITORY-METABOLISM-2026-09-25.json`.

## The founder interface, useful work, real capability formation (2026-09-26)

| Product requirement | Mechanism | Evidence |
|---|---|---|
| One coherent interface | `greg console`: loopback page; plain words -> `greg/planner.py` proposal -> "what signing lets GREG do" -> Ed25519 signature into the inbox. Reads only through the read-only observer; never a second Kernel | `tests/unit/test_greg_interface.py`, `tests/integration/test_greg_product_path.py` |
| Models propose, founder signs | template route first (zero model calls); model route via Anthropic SDK or installed Claude Code (no tools, spend cap); every draft vetted (contract, known capabilities, would-it-run check, one repair round) and clamped to read-only, $0, <= 7 days | `tests/evidence/greg-product/planner-live-draft-*.json` (first live draft unrunnable and caught) |
| A real, useful capability | `brief.engineering`: local Git + GitHub PRs/checks -> one brief in the founder's folder; the appraiser re-renders it from the receipt and byte-compares | `tests/evidence/greg-product/live-real-repos-summary.json` (real repos, live API, VERIFIED) |
| Capability Genesis that builds | missing function + founder-frozen contract -> Claude Code writes source only -> static screen -> isolated no-network run vs held-out vectors -> VERIFIED -> signed attach rule -> ORIGINAL mission resumes | `tests/unit/test_greg_genesis_builder.py`, `tests/evidence/greg-product/genesis-live-claude-code.json` |
| Survive power loss | torn ledger tail quarantined to a sidecar, never replayed, never lost; observers ignore unacknowledged tails | `tests/unit/test_ledger_tail_recovery.py`, product-path test (SIGSTOP + torn write + SIGKILL) |
| Refuse a rolled-back ledger | Every start checks that the ledger head the previous process last published in `heartbeat.json` (each turn, and at a clean stop) is still in the ledger, whatever state the heartbeat reports (tested for RUNNING and STOPPED); if not (truncated, restored from an older copy, forked), the body stays down and writes nothing (`Body._require_published_head`). Window: records appended since the last heartbeat (at most one turn, or a boot and its first turn) can be rolled back unseen; rewriting both files is caught only by the TSA witness below. Cost: a start reads and verifies the whole chain twice, in this check and in the writer's own open: the check took 0.09 s at 5,000 records and 0.34 s at 20,000 (Body.open 0.23 s and 0.75 s with it) | `tests/integration/test_greg_recovery_scenarios_process.py::test_corrupted_ledger_head` (clean stop, and SIGKILL with the heartbeat RUNNING) |
| Keep ticking for months without re-hashing all history on every read | Retained ledger records never leave the ledger: every read (records, by_type, find, replay, latest, outbox) hands out a plain copy, so a reader cannot change history. Appends and spine reads verify only new records; the whole chain is still reconstructed on open, on every explicit `verify_chain()` and at least every 300 s. The spine folds new records into indexed views, and improvement numbering no longer replays history. One emit at 5,000 records: 395 ms before, 0.42 ms after. The mission book folds only new events and the ledger answers lookups by hash, type and payload field from indexes, so a holding mission's tick at 31,256 records costs 18 ms instead of 137 ms; the remaining growth (0.34 ms per thousand records) is the Consequence Gate's own claim scan, whose fix changes a continuity artifact and waits on your decision | `tests/unit/test_ledger_incremental_verification.py` (20); `tests/unit/test_greg_mission_book_incremental.py` (17); `tests/unit/test_ledger_lookup_index.py` (9); `docs/collaboration/FINDING-LEDGER-APPEND-COST-2026-10-14.md` |
| No crash loops | `Journal.record` is idempotent on type + key + payload (it hashed the per-boot envelope before) | `tests/unit/test_greg_continuity.py` |
| Self-repair | a formed capability that faults twice in service (source/binary changed, or raises on live input) is quarantined with the failure as evidence and re-formed as a new deficit generation under the same signed contract and one shared build budget; the rebuild must also run cleanly on the live input that broke its predecessor (replayed locally; never sent to a model). Before: a tampered capability crash-looped the body (`EventError`), a failing one only escalated | `tests/unit/test_greg_self_repair.py`, `tests/evidence/greg-product/self-repair-summary.json` |
| Replaceable model routes | `greg/models.py`: one router over Anthropic API, OpenAI API, Claude Code and opt-in local Ollama; founder-signed route selection is replayed from the ledger after restart. Failover, route health and author provenance remain on the same spine. Refusals are final; unpriced spending routes are skipped and priced routes bound cost | `tests/unit/test_greg_models.py`, `tests/unit/test_greg_ollama.py` (local HTTP stub; no live model) |

## Externally detectable rewrite or rollback of witnessed history (2026-09-26)

| Effect | Mechanism | Evidence |
|---|---|---|
| A verifier holding witness state kept outside GREG can tell that a presented ledger is inconsistent with history an independent TSA already timestamped: a rewrite, deletion, rollback, root or anchor substitution, or wholesale reconstruction inside the witnessed prefix | Once Alfonso signs `ANCHOR_CONFIGURE`, the body timestamps its ledger head at an RFC 3161 TSA (`greg/anchor.py`; only a SHA-256 digest leaves the machine; outages are recorded and never block missions). `greg anchor export --roots R.pem --out W.json` writes an append-only witness bundle (head, position, token) **outside GREG's home**. `greg anchor verify --witness W.json --roots R.pem` checks the presented ledger using only that bundle and the verifier's own TSA root: `VERIFIED`, or `DIVERGED` / `ROLLED_BACK` / `INVALID_TOKEN` (exit 3). | `tests/unit/test_greg_anchor_witness.py` (attacker with total ledger write access, attacks A-F, real OpenSSL TSA; mutation to a self-referential verifier lets B-F through); `tests/evidence/greg-product/anchor-live-2026-09-26.json` |

**Limits, stated plainly.** `greg anchor verify` without `--witness` reads anchors and roots from the ledger it checks, so a complete rewriter defeats it; it is an internal consistency check only. Records after the latest witnessed head are not covered. A rewriter who can also edit the witness bundle and the verifier's root file defeats the scheme. So on one Mac the witness belongs on another device (phone, second machine, removable media). Nothing here is immutability.

On the Mac (not yet exercised against a public TSA: this build container's network policy blocks every public TSA): fetch Sigstore's chain from `https://timestamp.sigstore.dev/api/v1/timestamp/certchain`, keep only its last (root) certificate, then
`greg anchor configure --tsa-url https://timestamp.sigstore.dev/api/v1/timestamp --roots ROOT.pem --key ~/.greg-founder.pem`, and periodically `greg anchor export --roots ROOT.pem --out /Volumes/<elsewhere>/greg-witness.json`.

## Standing missions are appraised per closure; signal → venture memo (2026-09-27)

**Standing missions.** Before this, a standing (infinite) mission never reached `mission.achieved`, so the separate-process appraiser never judged it. Every `--daily` brief went unverified. Now:
- each hold reached after new action is recorded once as `mission.held`;
- it is appraised in the separate process;
- the verdict is bound to that closure (`closure_event`);
- the appraisal is scoped to the actions since the previous hold, so superseded evidence is never re-judged as a present claim.

VEPMC is unchanged: it still counts only bounded `mission.achieved` closures.

**`venture.assess` / `venture.status`** (`greg/ventures.py`). The flow:
1. RailScout `appraise` on sha256-pinned sources.
2. A deterministic wire packet. A buyer or budget owner is included only if evidenced, and sourced counterevidence is carried as `risk_flags`.
3. WealthMachine `evaluate_packet`.
4. The Kernel canonical adapters, where a contract violation becomes `CapabilityError`.
5. One write-once memo.

Organ execution:
- Each organ runs in its own process with a stripped environment and a fresh bytecode cache.
- Organs hold no authority.

The verdict may not outrun the evidence: the engine's verdict is capped at `needs_more_evidence` unless RailScout says `READY_FOR_HUMAN_REVIEW`. The memo names what would change the verdict. The appraiser re-renders the memo and re-runs both organs.

`--standing` reuses the canonical infinite-mission machinery: one approval, and a re-assessment whenever the evidence changes.

    greg mission new venture-assessment --railscout RS --wmi WMI --manifest M.json --source-root DIR [--standing]

Reality: IMPLEMENTED / TESTED / LOCAL-REAL (Linux, test key; developmental evidence in #124). It is not Mac-verified, not founder-used, and no real buyer is evidenced. WealthMachine's score is insensitive to evidence meaning; that defect belongs to WealthMachine and is not corrected here.

## Truthful persistence on a part-time body; open-source-first cognition (2026-09-30)

The first body is a Chromebook (founder correction 2026-09-26). ChromeOS stops Linux at sign-out, never
restarts it at sign-in, and suspends it with the lid. Missions stay durable; the body is not always present.

| Effect | Mechanism | Evidence |
|---|---|---|
| GREG says whether it was actually running | `greg/presence.py`: `body.booted.previous_heartbeat` bounds the absence between processes to one tick (the heartbeat file survives SIGKILL and a killed VM); `body.gap_observed` records host sleep (wall clock ran, monotonic clock did not) or a stalled process; founder stops are excluded from availability; due observations that fell in an absence are reported late. Surfaces: `greg presence`, `status()["presence"]`, morning `q0_was_i_present` (asked first) | `tests/unit/test_greg_presence.py` (12 tests incl. a real SIGKILLed body process; six mutations each caught) |
| Growth from a measured bottleneck, not self-preservation | `presence.recommend`: availability below 75% over 72h **and** late mission work -> ONE `BODY_AVAILABILITY` decision, no-spend options first, argued from mission lateness; nothing bought, rented or enrolled | same file |
| No paid model by default | `greg/models.py` `DEFAULT_ROUTE_ORDER = ()`: with no founder selection there is no model route (templates still work); a local open model when selected; paid routes only when a signed selection names them (INTENT-20260930-open-source-first) | `tests/unit/test_greg_open_source_first_routing.py` (restoring the old paid default fails 5 of 6) |

Limits: host sleep is detected from clock divergence and tested with injected clocks, not yet observed on a
suspending Chromebook; the heartbeat file is unsigned local evidence; nothing here proves who used the computer.

## Where GREG stands, and the one-command Body 1 install (2026-09-30)

| Effect | Mechanism | Evidence |
|---|---|---|
| "Greg, where are we?" answered from evidence | `greg/path.json` (nodes N0-N10 with gate, bottleneck metric, exit evidence, pivot, kill; 34 founder-intended capability horizons classified by present feasibility) and `greg/path.py`: the active node is the first whose exit evidence does not hold in the body's own ledger; a node without a ledger predicate never counts as passed, so `greg path` stops at N5 (no predicate yet) and never shows N6/N7. `greg path --node N6` reads one later node's own measurement and says where the path stops; it is reported, not counted. Surfaces: `greg path`, `status()["developmental_position"]`, morning `developmental_position` | `tests/unit/test_developmental_inheritance.py` |
| Corrections reroute, never delete | `greg.path.validate_placements`: ten classes, changed axes, nine-question inheritance test, three founder-given bases for genuine obsolescence; every open PR and the Mac lineage placed in `docs/collaboration/DEVELOPMENTAL-INHERITANCE-2026-09-30.json` | same file (rules rejected by negative controls) |
| One command from a fresh clone to a designated, supervised Body 1 | `greg/chromebook/install.sh` composes doctor, init, keygen, enroll, service install and designate; idempotent; never sees the passphrase; ports #122's Python 3.11+ selection and durable `greg` command | `tests/unit/test_greg_chromebook_install.py` (container, no systemd; not run on ChromeOS) |
| Verifier evidence names the tree it measured | `verifier/run_binding.py` (ported from #85) adds `head_commit` and `tracked_tree` to every run record | `tests/unit/test_run_record_head_binding.py` |

## Using it (developer mode today)

**Alfonso's Chromebook first-body route: [`CHROMEBOOK_FIRST_MISSION.md`](CHROMEBOOK_FIRST_MISSION.md).**
The older Mac option remains in [`FIRST_MISSION.md`](FIRST_MISSION.md).

```bash
python -m greg --home ~/.uniimente/greg init --read-root ~/Projects --deliver-root ~/GREG
python -m greg --home ~/.uniimente/greg console --key ~/.greg-founder.pem   # the one interface; open the private link it prints
python -m greg --home ~/.uniimente/greg mission new engineering-brief --local kernel=~/src/uniimente-kernel \
       --github dababiyoda/uniimente-kernel [--daily] --key ~/.greg-founder.pem
python -m greg --home ~/.uniimente/greg run --builder models          # Genesis builds/repairs via any reachable model
                                                                     # (explicit local Ollama, API handles, or Claude Code)
python -m greg founder keygen --key ~/.greg-founder.pem          # on a device Alfonso controls
python -m greg --home ~/.uniimente/greg founder enroll --pubkey <printed hex>
python -m greg --home ~/.uniimente/greg service install --platform macos [--builder models]   # writes, does not load
python -m greg --home ~/.uniimente/greg mission submit mission.json --key ~/.greg-founder.pem
python -m greg --home ~/.uniimente/greg mission new workspace-note|repo-guardian ... --key ...   # templates
python -m greg --home ~/.uniimente/greg vepmc | routing       # the bottleneck metric; learned routing
python -m greg --home ~/.uniimente/greg device enroll --pubkey <phone hex> --label phone --key ~/.greg-founder.pem
python -m greg --home ~/.uniimente/greg serve                   # phone channel; expose with tailscale serve
python -m greg --home ~/.uniimente/greg accept <closure_event_id> --key ~/.greg-founder.pem
python -m greg --home ~/.uniimente/greg status | decisions | morning
python -m greg --home ~/.uniimente/greg decide <request_id> approve --key ~/.greg-founder.pem
python -m greg --home ~/.uniimente/greg stop --local            # OS-level stop always works
```

### Optional open-weight local cognition

This uses the **same** `greg.models.ModelRouter` for mission proposals and
Capability Genesis. A local model only drafts or generates source; the founder
still signs missions and the Kernel retains the consequence boundary. Ollama
is opt-in and must already be installed with a downloaded GGUF model. GREG does
not install software, pull a model, sign into Ollama, enroll a key or spend money.

Before creating a **new** body, disable Ollama's cloud features (Ollama's
`~/.ollama/server.json`: `{"disable_ollama_cloud":true}`; restart Ollama).
Confirm the model appears in `ollama list`, and that the local API is available
on 127.0.0.1:11434. Choose a model that fits the actual hardware. Run:

```bash
python -m greg --home ~/.uniimente/greg init --read-root ~/src --deliver-root ~/GREG \
  --local-model '<downloaded-model-name>'
python -m greg --home ~/.uniimente/greg service install --platform linux --builder models
python -m greg --home ~/.uniimente/greg console --key ~/.greg-founder.pem
```

Complete the other founder-key and supervisor steps in the Chromebook first
mission guide before starting the service. The model must be in Ollama's local
`/api/tags` inventory with positive disk size, a GGUF format and digest;
`:cloud` models and uninstalled models are refused without a pull. The adapter
only contacts the fixed loopback native API, caps output, records requested
model, served model and artifact digest, and participates in the router's
terminal-refusal and outage-failover rules. The Ollama server itself is an
operator-controlled dependency; local inventory does not prove that an altered
server cannot proxy requests elsewhere. A local inference uses no model API
charge but still consumes device resources. No model performance or founder
device run is claimed from the in-process HTTP acceptance tests.

To **replace** the cognition route after GREG exists, queue a founder-signed
selection (the body applies it and preserves its identity, missions and ledger):

```bash
python -m greg --home ~/.uniimente/greg model set --route ollama \
  --local-model '<downloaded-model-name>' --key ~/.greg-founder.pem
python -m greg --home ~/.uniimente/greg model set --off --key ~/.greg-founder.pem
```

`--route` can be repeated in founder preference order for registered adapters;
this never grants credentials, money or external effects. A disabled route stays
detached across process death. The supervised body's builder switches on ingest;
an open founder console refreshes from the ledger before drafting or signing
and discards pending drafts from a detached route.
`--builder models` must be selected for Capability Genesis. A future stronger
model needs one tested route adapter with this same interface; it cannot become
a new Kernel, authority plane, mission ledger or autonomous policy selection.

### Swapping a tool while preserving GREG

`greg attach <capability_id>` and `greg detach <capability_id>` queue signed
founder commands. Detaching a capability removes it from execution across body
restarts. Genesis cannot automatically rediscover and reattach that exact
identity, even if a later mission allows read-only auto-attachment. It may
independently verify and attach a different installed tool for the same function
inside the mission's signed light cone. Reusing the detached identity requires
an explicit signed `greg attach`. Mission history, identity and the Kernel stay
on the same ledger. This behavior is exercised with `sha256sum` and `shasum`
where both are installed; it does not establish arbitrary plugin compatibility
or a completed run on founder-owned hardware.

Mission contract: `contracts/greg-mission.schema.json`. Native macOS verification package:
`greg/mac/verify_mac_body.sh` (must be run by Alfonso on the Mac; nothing here claims it ran).

## Buildability standard (14 conditions)

- **Existing mechanism:** Kernel EvidenceLedger, EventSpine, policy engine, ConsequenceGate, GrantIssuer, PassportRegistry, CapabilityGenome registry; commodity `cryptography` (Ed25519), launchd/systemd/supervisord, installed CLI tools, seccomp / macOS sandbox-exec.
- **Defined interface:** signed founder commands (`greg/founder.py`), `Body.run/tick/apply`, `MissionEngine.tick`, `AuthorityOffice.act`, `Genesis.resolve`, `morning_report`, CLI `python -m greg`.
- **Bounded authority:** the body holds no policy; every effect is a single-action grant issued only inside a founder-signed light cone (or an exact founder-approved scope) and executed by the Gate. Nothing self-attaches, self-promotes or inherits founder authority.
- **Available dependencies:** Python ≥3.11, `cryptography`, `jsonschema`, `pyyaml`; optional `supervisor` for Linux supervision; macOS built-ins for the Mac adapters.
- **Security model:** Ed25519 founder envelopes bound to body, kind, window and nonce; nonces retained; single ledger writer (flock); secrets resolved per declared handle only and never written to the ledger; no-network isolation for CLI and candidate code; untrusted data plane.
- **Failure modes:** forged/replayed/expired command (rejected as data), out-of-scope action (one decision request, wait), policy denial (grant revoked unused), sensor error (back-off, escalate after 3), uncertain dispatch (reconciliation, never blind retry), ineffective action (surprise → replan), lying tool (verification failure, not registered), tampered binary (quarantine), constitution drift (refuse to open), appraiser killed, timed out or without a readable verdict (no verdict recorded for it: one `mission.appraisal_unavailable` attempt, appraised again on the next tick, and after 3 such runs the closure is recorded appraised `UNAVAILABLE`, never `VERIFIED`; a hung appraiser no longer crashes the body), body killed mid-build (nothing is registered or attached before the frozen oracle passes it; each builder call is its own `genesis.build_started` fact charged against the signed build budget, a call interrupted before it reported its cost at the per-call ceiling it was given; an auto-attach cut short before its deficit was resolved is resolved at restart).
- **Interruption residuals (acceptance H.G7, narrowed, not closed):** (1) a hung appraiser holds the main loop: each run may take the full appraisal timeout (120 s) and its retries come on the next ticks without backoff, so one closure can hold the loop for up to 3 x 120 s, and each other closure awaiting appraisal adds as much; (2) no test interrupts the anchor (TSA) call, so its retry bound under interruption is not shown (a failure is recorded and the next try waits the configured interval, untested here); (3) an interrupted build is reserved at its ceiling only when the body dies inside the builder's call: a builder that itself fails is settled by `genesis.build_failed` at $0, whatever it spent before failing; (4) mission cost measurement (`greg/sop.py`) counts a build the body died inside at its reservation and marks that mission's model cost unknown; (5) a torn temporary file of an interrupted console or remote write stays in `inbox/` unread, and nothing sweeps it.
- **Acceptance tests:** `tests/unit/test_greg_*.py`, `tests/integration/test_greg_body_supervised.py`, closure module `greg_body` in `closure/greg_registry.py`.
- **Recovery path:** the supervisor restarts a crashed body; boot records `body.recovered`; missions, blockers, approvals and capabilities are reconstructed from retained history; uncertain effects wait for founder reconciliation, except where the founder signed `standing_reconciliation: {"consequence_inert": true}` into the mission and the retained facts prove the interrupted run consequence-inert (the script worker; no completed evidence; at most twice per action): then the engine records the proof (`greg.workers.inert_interruption_proof`) and retries once (`tests/unit/test_greg_standing_reconciliation.py`, ten-step proof step 7c).
- **Crash-loop hold:** if 5 main-loop boots in a row (no clean stop between them) end without a clean stop within 10 minutes, the next boot holds the body instead of crash-looping under the supervisor. A held body keeps running, its heartbeat reads `HELD`, it reads its inbox, and it runs no mission. Like a paused body, it waits a full tick between turns (a new inbox file or a STOP wakes it sooner), even when a mission's observation is due, and records no compute telemetry and no compute or presence asks. If the little a paused or held body still does (reading its inbox, noting a host suspension) fails, the failure is recorded once per boot and failure site as `body.fault_contained` and the body stays up; a body that is not paused still exits on the failure, so the breaker counts it. An inbox file that a paused or held body cannot ingest (whether reading, applying or rejecting it fails) is moved, unchanged and not accepted as a command, to `inbox/faulted/` (or, when that directory cannot take it, renamed in place to `<name>.<random>.faulted`, outside the files the body reads) and recorded once as `command.faulted`, so the files behind it, your signed resume among them, are still read; a running body still exits on such a file. A command the body accepted and applied whose file then could not be moved to `inbox/processed` is set aside the same way but recorded as applied, and status tells you not to sign it again. `greg status` lists both kinds under `security.contained_faults`, each with how to clear it; clearing one lifts nothing. It shows the hold's reason under `security.crash_loop_hold` and as each active mission's `active_constraint`. The hold raises one `CRASH_LOOP_HOLD` decision request; Approve or Reject cannot answer it. Only a signed `BODY_RESUME` lifts the hold, and it withdraws that request: `greg resume` with your founder key, or a phone or other device key you delegated `BODY_RESUME` to (the default `greg device enroll` grant includes it). The hold is the breaker's own record, and it is never shown as your pause; a body you paused keeps your pause however often it restarts.
- **Resource ceiling:** one action per mission per tick; mission budget and horizon from the light cone; 15-minute single-use grants; bounded receipts (16 KiB text); economical waiting until the next due observation (a mission you paused has none due).
- **Operating cost:** local CPU/disk for ledger verification and ticks; zero model calls and zero spend in this version unless a founder-signed mission budgets a paid capability.
- **Legal operator:** Alfonso Lopez (`alfonso_lopez`); UNIIMENTE is never a legal principal.
- **Handoff:** retained ledger (`ledger.jsonl`), heartbeat, morning report, `tests/evidence/greg-body/`.
- **Replaceable:** hardware, supervisor, capability implementations, installed tools, future model providers and UI shells; the Constitution, ledger continuity and Gate path are not bypassable.

## Reality gradient (as of this commit)

IMPLEMENTED · UNIT TESTED · INTEGRATION TESTED (real processes under supervisord: SIGKILL, SIGSTOP + torn write,
console closed mid-mission; 5/5 repeated runs) · SANDBOXED (phone path in real Chromium with an iPhone profile, not iOS
Safari) · LOCAL-REAL (engineering brief on real Kernel/DALEOBANKS/WMI checkouts and the live GitHub API; repo guardian and
integration watch read the real repositories; browser.render drove a real Chromium; Claude Code built and verified a
missing capability; Claude Code drafted a mission) · **not** PACKAGED · **not** MAC-VERIFIED · **not** REBOOT-VERIFIED
(power loss is simulated by a torn write, not a real reboot) · **not** FOUNDER-USED · **not** PRODUCTION-AUTHORIZED ·
no external business outcome. **Externally verified VEPMC = 0**: Linux fixtures can satisfy the nine structural
ledger conditions, but they use test keys and test machines. Alfonso's Chromebook Linux availability, his own key,
physical first-body designation and acceptance remain untested. Self-repair and the model router are TESTED on the product path (real body, real
isolated interpreters; model SDKs faked, no live key used); a live OpenAI/Anthropic API route awaits Alfonso's own keys.
Human work fabric and business runtime are PROPOSED. Presence accounting and open-source-first routing are
UNIT/INTEGRATION TESTED in a Linux container (2026-09-30), not observed on the founder's Chromebook.

### Bounded cognition seed (2026-10-01)

The signed mission path supports bounded source extraction, scenario estimation,
SMT feasibility, integer optimization, evidence binding and randomized two-arm
computation with typed receipts and separate-process checks. See
[cognition operator instructions](cognition/README.md), the
[seed decision and limits](../docs/collaboration/COGNITION-SEED-20261001.md), and
[retained test evidence](../tests/evidence/cognition-seed-20261001/).
The existing console and authenticated phone status view show scoped cognitive
results. This is a consequence-inert experiment; real founder-device acceptance
and comparative superiority remain separate gates.

The controlling [full-machine correction](../docs/intent/INTENT-20261001-FULL-MACHINE-COMPLETION.json) fixes Body + Organs + Mind as the completion boundary. After each proved integration, continue the next unblocked parent requirement. Seed and VEPMC are sequencing/evidence units; pending founder use does not stop achievable machinery.
