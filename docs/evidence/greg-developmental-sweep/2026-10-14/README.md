# Layer 4: MICA/CDPE local repair on unseen damage, 2026-10-14

Runner `cortex/evaluation/developmental_sweep/run.py`; freeze `freeze-v1.json` committed before the run
(`b99daba`); results `results.json`. TARGET_FORM_001 (`developmental/`) is unchanged; this composes its
components (`MICAField`, `simulate_transport`) on damage the lab never saw: 40 seeds, 10/20/30/40 % of cells
removed uniformly at random (source and sink excepted), every original-route edge blocked, 40 ticks.

| Removed | seeds | distributed (local field) delivered | adaptive central replanner delivered | static route delivered |
|---|---:|---:|---:|---:|
| 10 % | 10 | 272 (10 seeds deliver) | 272 (10) | 0 |
| 20 % | 10 | 228 (9) | 228 (9) | 0 |
| 30 % | 10 | 122 (5) | 122 (5) | 0 |
| 40 % | 10 | 0 (0) | 0 (0) | 0 |

**Verdict (frozen): PARITY.** Distributed equals adaptive central on all 40 seeds (0 wins, 0 losses);
median planning-operation ratio 1.07; zero false activations and zero exact-restoration attempts.
Seeds where neither delivers are disconnected fields: no routing method can deliver there.

## Reading

- This is the outcome stated in the runner before the run: the MICA field is a distributed shortest-path
  (distance-vector) computation, so on static damage it finds the same routes as a central replanner. The
  reserved organ's falsifier - "MICA/CDPE beats strong centralized adaptive baseline on unseen failures" -
  is **not met**; the organ stays FRONTIER_HORIZON as a cortex organ and EXPERIMENTAL as a lab mechanism.
- What the local field does deliver is recovery without a central coordinator at equal throughput and about
  equal planning cost. That is the effect distributed routing protocols already provide (RIP/OSPF-style),
  i.e. a commodity mechanism; any advantage would have to come from coordinator failure or dynamic damage,
  which this runner does not measure. Founder-effect compilation: preserve the effect (function survives
  unseen damage), do not claim morphogenesis beyond it.
- Next falsifiable Layer 4 test, if pursued: damage arriving during transport with a central replanner that
  replans every k ticks, and coordinator loss. Not run.
