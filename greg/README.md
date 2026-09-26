# GREG — the persistent, founder-sovereign operating layer (Body 1)

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

## Spider-Web compounding (INTENT-2026-09-25-SPIDER-WEB-COMPOUNDING)

The optimization target is one transaction: *Alfonso's authorized intention → verified real-world
outcome → evidence and capability that make the next intention easier.*

| Control point | Mechanism | Evidence |
|---|---|---|
| Eligibility | `CapabilityRegistry.register` refuses a capability that strengthens none of the seven super-nodes; light cones; Ed25519 founder envelopes | `test_spider_web_rule_rejects_capabilities_that_strengthen_nothing` |
| Default routing | `routing.py`: ledger-derived reliability (Laplace) per capability; strategies ranked by expected discrepancy value closed minus cost; each choice recorded with its alternatives | `test_routing_learns_from_one_missions_failure_for_the_next_mission` |
| Proof / truth | `appraisal.py`: a **separate process** re-verifies the founder signature, re-derives checks from receipt bytes, re-observes the world and confirms exactly-once | `test_independent_appraiser_…`, `test_appraiser_refutes_a_false_closure_claim` |
| Proof → routing | an appraiser refutation of the *effect* lowers that capability's reliability for every future mission; refutations for foreign faults do not | `test_appraiser_refutation_of_the_effect_lowers_routing_but_foreign_faults_do_not` |
| Settlement / outcome | `metrics.py`: VEPMC computed only from ledger facts (nine conditions; two only Alfonso and his Mac can supply) | `tests/integration/test_greg_vepmc_path.py` |
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
| Learns from the founder, only when a later case proves it | a signed `CRITIQUE` with a typed `review` (ACCEPT / REJECT / CORRECT / PREFERENCE / FAILURE_CLAIM; preference, claim and verified failure kept apart) becomes a frozen candidate over whitelisted learnable knobs; the first later result of that capability compares the unchanged baseline with the candidate (re-render from its receipted inputs against labels given after the freeze, or a shadow acquisition against an exhaustive independent observation inside the same approved action); RETAIN / NO_IMPROVEMENT / REGRESS / CONFLICTED / NEEDS_MORE_EVIDENCE; retained knobs are ledgered, versioned, revertible by a signed rejection, printed in every brief, and are what the next brief runs with. Constitutional state (authority, budgets, scope, credentials, shutdown, policy) is never learnable | `tests/unit/test_greg_learning.py`, `tests/evidence/greg-product/learning-closures.json` |
| Any model vendor | `greg/models.py`: one router over the Anthropic API, the OpenAI API (Responses) and Claude Code; failover, demotion with cooldown, route health retained in the ledger (`greg.model.route`), the true author recorded on every draft and built capability. Refusals are final (never re-asked elsewhere); in a spending context an unpriced route is skipped and every priced route bounds its worst-case cost to the remaining signed budget | `tests/unit/test_greg_models.py` (SDK-shaped fakes; no live key used) |

## Using it (developer mode today)

**First mission on the Mac (VEPMC 0 → 1): follow [`FIRST_MISSION.md`](FIRST_MISSION.md).**

```bash
python -m greg --home ~/.uniimente/greg init --read-root ~/Projects --deliver-root ~/GREG
python -m greg --home ~/.uniimente/greg console --key ~/.greg-founder.pem   # the one interface (127.0.0.1:8766)
python -m greg --home ~/.uniimente/greg mission new engineering-brief --local kernel=~/src/uniimente-kernel \
       --github dababiyoda/uniimente-kernel [--daily] --key ~/.greg-founder.pem
python -m greg --home ~/.uniimente/greg run --builder models          # Genesis builds/repairs via any reachable model
                                                                     # (anthropic_api_key / openai_api_key handles, or Claude Code)
python -m greg founder keygen --key ~/.greg-founder.pem          # on a device Alfonso controls
python -m greg --home ~/.uniimente/greg founder enroll --pubkey <printed hex>
python -m greg --home ~/.uniimente/greg service install --platform macos [--builder models]   # writes, does not load
python -m greg --home ~/.uniimente/greg mission submit mission.json --key ~/.greg-founder.pem
python -m greg --home ~/.uniimente/greg mission new workspace-note|repo-guardian ... --key ...   # templates
python -m greg --home ~/.uniimente/greg vepmc | routing       # the bottleneck metric; learned routing
python -m greg --home ~/.uniimente/greg device enroll --pubkey <phone hex> --label phone --key ~/.greg-founder.pem
python -m greg --home ~/.uniimente/greg serve                   # phone channel; expose with tailscale serve
python -m greg --home ~/.uniimente/greg accept <closure_event_id> --key ~/.greg-founder.pem
python -m greg --home ~/.uniimente/greg status | decisions | morning | learning
python -m greg --home ~/.uniimente/greg critique <brief action event> --classification PREFERENCE \
       --needs owner/repo#12 --text "..." --key ~/.greg-founder.pem   # GREG learns only if a later brief proves it
python -m greg --home ~/.uniimente/greg decide <request_id> approve --key ~/.greg-founder.pem
python -m greg --home ~/.uniimente/greg stop --local            # OS-level stop always works
```

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
no external business outcome. **VEPMC = 0**: on Linux 8 of 9 conditions hold with a test key; `mac_body` (and Alfonso's
own key and acceptance) remain. Self-repair and the model router are TESTED on the product path (real body, real
isolated interpreters; model SDKs faked, no live key used); a live OpenAI/Anthropic API route awaits Alfonso's own keys.
Human work fabric and business runtime are PROPOSED.
