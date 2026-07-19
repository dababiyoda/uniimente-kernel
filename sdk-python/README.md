# sdk-python

Python SDK for organ integration: contracts, event emission, gateway client, identity helpers. DALEOBANKS and WealthMachineIntelligence migrate onto this in Phases 2-3. Publish target: Phase 10.

## Contents

- `uniimente_kernel/ledger.py`: append-only hash-chained decision ledger, kill switch, rate governor. Extracted from DALEOBANKS in Phase 2, generalized behind organ-agnostic APIs. See `docs/EXTRACTION_MAP.md`.
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
