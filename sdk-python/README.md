# sdk-python

Python SDK for organ integration: contracts, event emission, gateway client, identity helpers. DALEOBANKS and WealthMachineIntelligence migrate onto this in Phases 2-3. Publish target: Phase 10.

## Contents

- `uniimente_kernel/ledger.py`: append-only hash-chained decision ledger, kill switch, rate governor. Extracted from DALEOBANKS in Phase 2, generalized behind organ-agnostic APIs. See `docs/EXTRACTION_MAP.md`.
- `uniimente_kernel/raw_vault.py`: verbatim raw-evidence preservation with per-record sha256 (PR #12).
- `uniimente_kernel/capability.py`: narrow, expiring, revocable capability grants minted only behind verified human approval (PR #12).
- `uniimente_kernel/prompt_firewall.py`: prompt-injection defense — untrusted text is data, never instruction (PR #13).
- `uniimente_kernel/context_packet.py`: normalized ContextPacket builders for every sensor (PR #13).
- `uniimente_kernel/constitution_check.py`: constitution hash guard; runtime drift disarms live action (PR #14).
- `uniimente_kernel/heartbeat.py`: supervised loop with consecutive-failure breaker (PR #14).
- `uniimente_kernel/approval_queue.py`: the operator command channel — YES/NO/EDIT/WHY/HOLD/FREEZE/NEWS/INTERVIEW/OPINION (PR #14).
- `uniimente_kernel/contracts.py`: the Phase 3 signal wire — venture-signal / signal-assessment v1.1, unified from both organs (PR #17).
- `uniimente_kernel/events.py`: Phase 4 event spine — typed, hash-chained institutional events with explicit causal parents.
- `tests/`: stdlib unittest suite. Run: `python -m unittest discover -s sdk-python/tests`.

## Usage

```python
from uniimente_kernel.ledger import DecisionLedger, KillSwitch, RateGovernor

ledger = DecisionLedger()
entry = ledger.record_decision({...})   # validates contracts/decision.schema.json required fields
ok, first_bad = ledger.verify_chain()

switch = KillSwitch(ledger=ledger, apply=my_organ_config_update)  # starts disarmed; fails toward silence
governor = RateGovernor(max_actions=30, window_seconds=3600)
```

```python
from uniimente_kernel.events import EventSpine

spine = EventSpine(ledger, source="spiffe://uniimente.internal/organ/my_organ",
                   actor="spiffe://uniimente.internal/organ/my_organ/agent/worker",
                   legal_principal="alfonso-lopez", policy_version="1.0.0")
signal = spine.emit("signal.detected", data={"signal_type": "operator_thought"})
spine.chain("approval.requested", signal)   # causal_parent bound automatically
chain = spine.causal_chain(signal.id)        # walk any outcome back to its origin
```
