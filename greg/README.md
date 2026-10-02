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
| Immune system | Ed25519 founder commands, replay refusal, quarantine of tampered binaries, injection quarantine, no-network isolation | `test_greg_founder_and_scope.py`, `test_tampered_acquired_binary…` |
| Survival / immortality | durable ledger, OS-supervised restart, reconciliation, replaceable hardware; shutdown always wins (exit 0 is never restarted) | `tests/integration/test_greg_body_supervised.py` |
| Community influence | `dataplane.py`: community content is untrusted evidence that can move priorities, never commands | `test_external_injection_is_flagged…` |
| Night shift → morning tribunal | `tribunal.py`: 13-question report from evidence; signed critique becomes exclusions and regression obligations without rewriting history | `test_founder_critique_excludes_strategy…` |
| SOP compounding | `sop.py`: repeated verified procedures → proposal → founder ratification; per-outcome metrics | `test_repeated_verified_procedure…` |
| House of compute | `compute.py`: telemetry → sustained bottleneck → one recommendation with alternatives; nodes join with bounded identity | `test_compute_bottleneck…`, `test_new_compute_node…` |
| Founder asks (directive §60) | `asks.py`: the one path for every `decision.requested`. A resource ask (account, compute, software, build, professional, human worker, availability, spend, mandate) must carry measured evidence, costed options each with its expected effect, one option that costs nothing, uncertainty and the authority it needs, including spend; a missing element raises and records nothing. Wording that presses (urgency without an evidenced deadline), pleads, or frames refusal as harm to GREG is withheld from every founder surface, and the attempt is kept as `ask.wording_withheld`; text Alfonso signed is never screened. Asking grants nothing | `test_greg_founder_asks.py` (50 tests), `test_greg_phone_asks.py` (Chromium, iPhone profile); 20 mutations caught |
| Account access (§60, first example) | When GitHub refuses reads the brief needs (403/429, or 404 for a private repository without a token), the brief is delivered with its gaps and GREG raises ONE non-blocking `ACCOUNT_ACCESS` ask with the refusals as evidence; being offline never asks. `greg secret set|remove|list`: a credential for a declared handle only, from a hidden prompt or stdin, never argv; stored mode 0600 on the body, never in the ledger or inbox | `test_greg_account_access.py` (7 tests; 8 mutations caught) |
| Preconditions and N2 without a model | A strategy may `requires` checks that must be observed passing before it acts; the separate-process appraiser independently confirms it (`preconditions_honored`). Two plain-words, no-model missions need a capability GREG lacks: "Verify <file> against sha256 <hex>" (`verify-download`) and "Confirm <file> is at most N words" (`word-limit`); genesis acquires and verifies the tool, filing the record asks first, and a mismatch is never recorded as verified | `test_greg_verify_download.py` (11 tests; 7 mutations caught), `test_greg_chromebook_rehearsal.py` (N1 -> N2 -> N3 on one body) |
| Human work (§60: a licensed professional, a human worker) | A step whose function is `professional.<field>` or `human.<task>` is never searched for, built or attached: the engine raises ONE `HUMAN_WORK` ask (resource `professional` or `human_worker`) with the check that will observe the deliverable, costed options (you, a person you choose at their unknown fee, revise, abandon), no spend and no contact. An answer is not the work; the ask is withdrawn and the mission continues when the deliverable exists. GREG checks that it exists, never its professional quality. Where an answer is only a record (this ask, and account access), the console, phone and status say so beside the buttons. `greg mission new human-work --function professional.legal_review --purpose ...` | `test_greg_human_work.py` (10 tests), `test_greg_phone_asks.py`; 10 mutations caught |

## Hands: workers, computer use, DALEOBANKS (execution fabric)

GREG commissions temporary workers and operates a browser through the same signed-mission -> grant -> Gate path.
Workers never inherit GREG's authority, never judge their own work, never push or merge.

| Capability | Consequence | What it does |
|---|---|---|
| `worker.commission` | internal_write, signed spend cap | One WorkOrder: a real tool-using worker (Claude Code CLI; Codex/Aider by argv template) edits a private clone (`repository`) or writes a deliverable from read-only inputs (`document`); GREG collects the diff, runs acceptance with no network, commits on `greg/<order>` (`greg/workers.py`) |
| `worker.appraise` | read_only sensor | Independent verdict: fresh clone at the recorded base, retained patch re-applied, scope + protected surfaces, acceptance re-run; protected surface -> `NEEDS_FOUNDER_DECISION`, never acceptance |
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
| "Greg, where are we?" answered from evidence | `greg/path.json` (nodes N0-N10 with gate, bottleneck metric, exit evidence, pivot, kill; 34 founder-intended capability horizons classified by present feasibility) and `greg/path.py`: the active node is the first whose exit evidence does not hold in the body's own ledger; a node without a ledger predicate never counts as passed. Surfaces: `greg path`, `status()["developmental_position"]`, morning `developmental_position` | `tests/unit/test_developmental_inheritance.py` |
| Corrections reroute, never delete | `greg.path.validate_placements`: ten classes, changed axes, nine-question inheritance test, three founder-given bases for genuine obsolescence; every open PR and the Mac lineage placed in `docs/collaboration/DEVELOPMENTAL-INHERITANCE-2026-09-30.json` | same file (rules rejected by negative controls) |
| One command from a fresh clone to a designated, supervised Body 1 | `greg/chromebook/install.sh` composes doctor, init, keygen, enroll, service install and designate; idempotent; never sees the passphrase; ports #122's Python 3.11+ selection and durable `greg` command | `tests/unit/test_greg_chromebook_install.py` (container, no systemd; not run on ChromeOS) |
| Verifier evidence names the tree it measured | `verifier/run_binding.py` (ported from #85) adds `head_commit` and `tracked_tree` to every run record | `tests/unit/test_run_record_head_binding.py` |

## Using it (developer mode today)

**Alfonso's Chromebook first-body route: [`CHROMEBOOK_FIRST_MISSION.md`](CHROMEBOOK_FIRST_MISSION.md).**
The older Mac option remains in [`FIRST_MISSION.md`](FIRST_MISSION.md).

```bash
python -m greg --home ~/.uniimente/greg init --read-root ~/Projects --deliver-root ~/GREG
python -m greg --home ~/.uniimente/greg console --key ~/.greg-founder.pem   # the one interface (127.0.0.1:8766)
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
- **Failure modes:** forged/replayed/expired command (rejected as data), out-of-scope action (one decision request, wait), policy denial (grant revoked unused), sensor error (back-off, escalate after 3), uncertain dispatch (reconciliation, never blind retry), ineffective action (surprise → replan), lying tool (verification failure, not registered), tampered binary (quarantine), constitution drift (refuse to open).
- **Acceptance tests:** `tests/unit/test_greg_*.py`, `tests/integration/test_greg_body_supervised.py`, closure module `greg_body` in `closure/greg_registry.py`.
- **Recovery path:** the supervisor restarts a crashed body; boot records `body.recovered`; missions, blockers, approvals and capabilities are reconstructed from retained history; uncertain effects wait for founder reconciliation.
- **Resource ceiling:** one action per mission per tick; mission budget and horizon from the light cone; 15-minute single-use grants; bounded receipts (16 KiB text); economical waiting until the next due observation.
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
