# P8 cycle 5: constraint-release search policy, cover/1 (2026-10-16): REJECT at the adversarial gate

Every number below is copied from `cycle-cr-5.json` by script. Nothing was re-run.

## Protocol

| Item | Value |
|---|---|
| Pre-registration | `PREREGISTRATION.md` (design merged at `651d310`). Freeze and seals committed at `6fa98ff`, before the run. |
| Run | once, through the clean room (`fresh detached checkout of 6fa98ffb13819d446b2274808206cd4e8748b4cc`), pinned to one core, exit 0 (`cycle-cr-5.log`); 2026-10-16T07:25:18.848910+00:00 to 2026-10-16T07:30:06.592972+00:00 |
| Freeze check | `sha256:1142c7d09d47a1dde...` matched; `source_dirty` []. The record's `freeze.commit` reads "unknown: a shallow clone's history may not reach the commit that added it" because the launcher's checkout is shallow; the freeze was committed at `6fa98ff`. |
| Execution | {"recorded": true, "require_confinement": true, "clean_room": "checked: fresh checkout, empty bytecode prefix, executed code inside the freeze", "launcher_stated": "fresh detached checkout of 6fa98ffb13819d446b2274808206cd4e8748b4cc", "allow_dirty_for_test": false} |
| Search | cover/1, lhs 0, 5 generations, population 8, search seed 20261016; 48 configurations evaluated |

## Result

| Stage | Outcome |
|---|---|
| Trigger | 45.0% of train items failed against random restart (threshold 25%): **triggered** |
| Train | candidate `cfg-562c6fdf85bc` mean loss 0.004899 against the incumbent's 0.007035: **30.4% better** |
| Changed keys | {'offspring': 6} |
| Adversarial | outputs verified: True. `fewval` 0.013923 → 0.012089; `lean` 0.007737 → 0.009868 (+27.5%, past the 5% tolerance) |
| Held-out | **not evaluated**: the rule stops before the held-out look when the adversarial gate fails |
| Decision | **REJECT** (adversarial evaluation failed). No proposal; nothing applied. |

## Reading

- **The search now reaches the restart region; the selection step did not take it.**
  - The restart-heavy anchor `cfg-12b387892289` (`p_restart` 1.0) was evaluated in generation 1, with train mean loss 0.004922.
  - That is within 0.5% of the selected candidate's 0.004899.
  - 10 evaluated configurations share the anchor's exact train loss.
  - The frozen rule selects the lowest train mean loss. Among near-ties, that picked an operator variant (`offspring` 6), which then failed the lean-budget stress set.
- **This is the failure the pilot predicted for this selection signal.** Train mean loss did not rank configurations on review seeds (Spearman −0.179 between pilot halves, `PREREGISTRATION.md`, *Pilot*). The pilot measured headroom in the restart region; this cycle cannot say whether that headroom holds on the cycle-5 held-out split, because the split was never evaluated.
- **The held-out split (7700-7879) was never looked at.** Under `_looked`, it is not spent by this record.
- **Protected evolution has still never kept an improvement:** five cycles, five REJECTs. Section 31 item 7 remains unmet.
  - Cycle 1: an overfit.
  - Cycle 2: a scarce-sample fragility.
  - Cycles 3 and 5: the adversarial gate.
  - Cycle 4: the held-out gate.
- **Next experiment (a hypothesis, not a conclusion):** a selection rule that does not rest on near-tied train means. Examples are a sign test against the incumbent on train items, or a stress-aware selection. It would be pre-registered with a fresh split. Changing the selection rule is a change to the trusted parent and needs its own pre-registration.

## Reproduce

```
git worktree add /tmp/p8c5 6fa98ff && cd /tmp/p8c5
PYTHONPATH=. taskset -c 1 python -B -m greg.cognition.evolution --target constraint_release \
  --freeze docs/evidence/greg-protected-evolution/2026-10-16-cr-5/freeze.json --out /tmp/cycle-cr-5.json
```
