# GREG body evidence — 2026-09-25 (refreshed 2026-09-26 for the Spider-Web commit)

Environment: Linux container, Python 3.11, cryptography 41.0.7, supervisor 4.3.0, libseccomp present.
Not macOS. The founder key in every run is a per-test Ed25519 key, never Alfonso's.

| File | What it shows |
|---|---|
| `full-suite.log` | `python -m pytest -q`: 800 passed (739 before GREG, 788 at the first GREG commit; 0 regressions) |
| `greg-unit-offline.log` | 59 GREG unit tests under `tools/offline_test.py` (seccomp: socket creation denied) |
| `supervised-repeat.log` | real-process supervised test repeated (9/9 passes across the session incl. these 3) |
| `supervised-run-ledger.jsonl`, `supervised-run-summary.json` | retained history of one supervised run: 2 boots, `body.recovered` after SIGKILL, exactly 1 decision request, exactly 1 receipted action, supervisor `EXITED` after the signed stop |
| `vepmc-path-summary.json`, `vepmc-path-ledger.jsonl` | first-VEPMC acceptance path through the product CLI under supervisord: signed template mission, interface exits, approval boundary, SIGKILL while waiting, autonomous restart + `body.recovered`, signed approval, one receipted write, separate-process appraiser VERIFIED, closure id read from `greg vepmc`, signed acceptance. VEPMC conditions met 8/9; missing only `mac_body` (Linux). VEPMC = 0 |
| `vepmc-path-repeat.log` | the VEPMC path test repeated 5/5 |
| `ci-and-verifier.log` | schema refs, authority singleton, sealed-developmental, verifier V1–V5 PASS (V3 includes `greg_body`) |

Negative evidence retained in the session record (fixed before commit, preserved here as lineage):
genome validator rejected a capability without inputs; sensor-identity collision refused by the spine
(event id reused with different content); surprise loop (ineffective action repeated) caught by test;
paid strategies refused because policy was pre-evaluated without the grant; acquired tool ran in a missing
workspace; missing file misclassified as sensor failure; signal handler installation outside the main thread.

Spider-Web commit negative evidence: the Proof→Routing test first carried a vacuous `or` assertion
(caught on self-review and tightened); two mutations of the routing rule (penalty removed; foreign faults
penalized) each fail the test. A runbook dry run with a mistyped repository path was correctly refused by
`fs` root containment; the corrected run observed the real Kernel/DALEOBANKS/WMI repositories consistent.
