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

## Using it (developer mode today)

```bash
python -m greg --home ~/.uniimente/greg init --read-root ~/Projects
python -m greg founder keygen --key ~/.greg-founder.pem          # on a device Alfonso controls
python -m greg --home ~/.uniimente/greg founder enroll --pubkey <printed hex>
python -m greg --home ~/.uniimente/greg service install --platform macos   # writes, does not load
python -m greg --home ~/.uniimente/greg mission submit mission.json --key ~/.greg-founder.pem
python -m greg --home ~/.uniimente/greg status | decisions | morning
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

IMPLEMENTED · UNIT TESTED · INTEGRATION TESTED (real processes, commodity supervisor, SIGKILL) ·
**not** PACKAGED · **not** MAC-VERIFIED · **not** FOUNDER-USED · **not** LIVE-BOUNDED · no external outcome.
Model router, human work fabric and business runtime are PROPOSED (see
`docs/collaboration/GREG-BODY-DECISION-2026-09-25.md`).
