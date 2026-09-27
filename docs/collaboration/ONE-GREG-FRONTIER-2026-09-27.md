# One GREG frontier — convergence record (2026-09-27)

Founder direction (2026-09-26/27): one canonical GREG frontier; exactly one executable implementation per
concern; #120 is the learning spine; metabolize #119 completely; #122 must not carry stale #120 code; no two
"canonical" frontiers. VEPMC remains 0 until the founder-owned Mac mission closes.

**Canonical frontier:** branch `codex/one-greg-vepmc-convergence` (PR #122), based on #114 `14b44e5`.
It is a fast-forward of #122's own head `73355d0`, so `greg/FIRST_MISSION.md` keeps checking out the same
branch name. Nothing on it is merged to #114 or `main`.

## One owner per concern (verified by repository search, §Evidence)

| Concern | Canonical implementation | Came from | Nothing else executable on the GREG path |
|---|---|---|---|
| Persistent body | `greg/body.py` `Body` + `greg/service.py` (launchd / systemd / supervisord) | #114 | only `class Body` in the tree |
| Authority / stop | founder-signed envelopes (`greg/founder.py`), Authority Office, persisted STOP (`body.stop_persisted`, `greg start --local`) | #114 (stop persistence from #113 `40d3bdc`) | `egregore.local_console` is superseded as founder instructions (`docs/GREG_LOCAL_START.md` banner) |
| Model routing | `greg/models.py` `ModelRouter` | #114 + #118 `7766b07` (byte-identical) | `egregore/goal_chase.CommunicationRouter` routes messages, not models |
| Capability Genesis / repair | `greg/genesis.py`, `greg/builders.py`, deficit loop in `greg/missions.py` | #114 (+ #118 refusal class) | — |
| Independent proof / witness | appraiser (`greg/appraisal.py`, separate process) + `greg/anchor.py` external witness | #114 + #115 `6c32edd` (anchor files byte-identical) | #115's arsenal files are not on the frontier |
| Recursive learning | `greg/improvement.py` (levers `brief.attention`, `brief.acquisition`) | #120 `19f59b3` + this convergence | `greg/learning.py` (#119) and `greg/corrections.py` (#121) are absent; `egregore/brief_learning.py` is reachable only from the superseded synthetic console and one test |

## What was ported into the frontier

| Mechanism | From | Where now | Evidence |
|---|---|---|---|
| #120 engine at `19f59b3` (replaces #122's copy of `ea11073`) | #120 | `greg/improvement.py`, `briefs.py`, `tribunal.py`, CLI | `tests/unit/test_greg_improvement_attacks.py`, `test_greg_learning_gate.py` |
| Learning inside a process that is SIGKILLed survives; a revert inside a killed process stays reverted; a new bounded brief uses the learned policy and the separate appraiser returns VERIFIED | #119 `test_greg_learning_durability` (7086a8a) | `test_learning_done_inside_a_killed_process_survives_and_a_revert_in_a_killed_process_stays` | forked child exits −9; parent rebuilds from the home alone |
| An unrelated open regression stays open when a learned change closes the originating one | #122 `73355d0` | `test_only_the_originating_regression_closes_on_its_declared_held_out_check` | — |
| Nine held-out-independence falsifiers (one brief = one case, derivation/retention/monitoring briefs never reused, replayed critique adds nothing, reconstruction after death) | #122 line `6bf7687` (another session) | `tests/unit/test_greg_learning_heldout_independence.py`, run against the canonical engine | 9/9 pass |
| **Defect found by those falsifiers in the canonical engine:** after a loss, re-labelling the lost-on briefs lifted the retry cool-down. Now counts briefs delivered after the decision | this convergence | `improvement._learn_preferences` | restoring label-order counting fails `test_retry_after_a_loss_needs_three_new_distinct_briefs` |
| `labelled_cases(every_label=True)`, `report()["superseded_labels"]` (a corrected label stays inspectable; neither feeds a decision) | #122 line `6bf7687` | `greg/improvement.py` | `test_4_10_…` |
| Runbook / install: Python ≥3.11 interpreter selection, persistent `greg` alias, restart-after-stop | this convergence | `greg/FIRST_MISSION.md`, `greg/mac/verify_mac_body.sh`, `greg/__main__.py` | under Python 3.9 `greg init` used to die with `TypeError` in `egregore/runtime.py`; it now exits with the fix |

## Superseded (history, branches and PRs preserved; nothing deleted)

| PR | Disposition |
|---|---|
| #118 | **Absorbed** (byte-identical; merge of `7766b07` is a no-op). Close as merged-into-frontier when the founder agrees. |
| #120 | **Absorbed** at `19f59b3`. Its branch stays as lineage. |
| #115 | **Anchor extracted** (byte-identical files). The 55-technology arsenal stays in #115's history, not on the frontier. |
| #119 | **Superseded as an executable engine.** Every mechanism is dispositioned in `PR119-METABOLISM.md`; its durability falsifier is now ported (row 13). |
| #122 line `claude/greg-122-heldout-independence-t0vqu7` | **Merged** into the frontier (`d9938cb`); its test file runs on the canonical engine. |
| #122's own weaker process-death test (child boots and dies with no learning in it) | superseded by the #119 port above; kept in #122 history. |

## Retained only as historical / negative evidence

- `greg/learning.py` (#119): one-case decisions and `CONFLICTED`, rejected; draft-ordering knob; label metrics.
- `tests/evidence/greg-product/learning-closures.json`, `learning-durability.json` (#119 branch).
- `tests/evidence/greg-product/learning-heldout-independence-mutation.json`: mutations were run against #122's
  pre-convergence engine; on the canonical engine only the cool-down mutation was re-run (caught).
- `egregore/brief_learning.py`, `egregore/local_console.py` (#112 lineage).
- #121 `greg/corrections.py` and its live evidence (`correction-loop-live-2026-09-26.json`) — see unresolved.

## Unresolved (founder decisions, not agent work)

1. **#121 is a second learning engine** (founder corrections re-rank already-authorized strategies across missions;
   `min_trials`; founder `binding` RULE; founder accept counted as a trial). It is not on the frontier. Its
   retention rule (founder acceptance counts as evidence, `min_trials` not ≥3 held-out missions, no strict
   baseline comparison) is weaker than the canonical rule. Options: (a) keep it out until VEPMC = 1, then add
   strategy selection as a third lever inside `greg/improvement.py` under the same `verdict()`; (b) close it.
   Recommended: (a). No code was ported.
2. Closing or retitling #118, #119, #120, #121 on GitHub.
3. Merging the frontier into #114 (another session owns #114's branch).

## Evidence

- Full suite in a fresh venv built from `requirements-dev.txt`: see PR #122 body for the exact run on the head.
- Duplicate-plane search (commands in the PR body): one `class Body`; one `ModelRouter`; one module importing
  `rfc3161_client`; one learning engine imported by `greg/`; `greg/learning.py` and `greg/corrections.py` absent.

Authority delta: none. VEPMC: 0.
