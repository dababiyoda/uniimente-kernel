# WealthMachine reads the Mind's staffing figures on the real organ path — evidence, 2026-10-28

Draft child of #196 (`4e970f2d`) on branch `claude/wmi-staffing-figures-step9-20261028`. Implementer: Claude Code cloud session `session_01Kucyfoabgsg6W8H8xj4qea` (board claim #96 6473380596; split with `session_01KucyfnwWG7Lgp8QvCTKeHg`, which holds #205 → #210, recorded at 6473659708). Self-review only. The organ change it adopts is WMI #45 (`b2c7f234`) with its hardening child WMI #47 (`0e80582d`).

## What GREG can do now that it could not before

Two certified staffing answers travel the real organ path:

1. DALEOBANKS refines the seed in its own interpreter and signs the packet.
2. WealthMachine verifies the packet, assesses it and signs the assessment.
3. The Kernel verifies both messages under per-organ keys.
4. A second WealthMachine process reproduces the assessment.

The two packets carry the same number of evidence items, and the only difference between them is the report: one says every unit is staffed, the other says half are. They now produce different assessments, and nothing else explains the difference. In the fifteen-step mission, WealthMachine's reading of the Mind's own answer (8 of 9) becomes its first validation step. GREG's receipt carries that step.

| WealthMachine | 8/8 | 4/8 | Identical between the two |
|---|---|---|---|
| `7a45d223` (#44, the pin on #196) | go, score 0.726, "Post one educational thread…" | go, 0.726, same step | everything: evidence count, verdict, score, reasons, plan, first step |
| `0e80582d` (#47, pinned here) | go, 0.696, "Validate the reported staffing result of 8/8 units…" | **needs_more_evidence**, 0.696, "Validate the reported staffing **shortage of 4 units**… resolve unfilled orders {"Dock": 2, "Line": 2}" | evidence count (2) and score only |

The score falls from 0.726 to 0.696 on both packets because #47 stops counting a staffing report as demand evidence. With or without a report, the score is the same.

## The founder's eight conditions, and where each is shown

| # | Condition | Evidence |
|---|---|---|
| 1 | Equal-count 8/8 and 4/8 reports travel the real DALEOBANKS→WMI path | `test_a_shortage_changes_…`: the real `IdeaRefinery`, signed bridge, Kernel verification and a second WMI process (REPRODUCED). The answers are certified by the Kernel's own `certify_staffing`. The seeds are bound exactly by `bound_value` with the fifteen-step edge. Both packets have 2 evidence items. |
| 2 | The shortage changes reasons, evidence requests and validation priority | The same test: the readings differ, `validation_plan[0]` and `recommended_next_action` differ, the later plan steps are identical, and the verdict is capped. GREG's exchange receipt now carries `recommended_next_action`. |
| 3 | Evidence-count inflation or unrelated score changes cannot explain the result | The packets are equal except for the report (and the ids derived from it). `opportunity_score`, `market_alignment`, `risk_level`, `legal_readiness`, `expected_roi` and `pricing_hypothesis` are identical. Every non-staffing reason is identical. WMI #47 also keeps reports out of the demand signals (tested there across urgency × confidence). |
| 4 | Malformed, inconsistent, truncated, replayed or contradictory reports keep explicit uncertainty | `test_hostile_reports_keep_explicit_uncertainty`, five cases (truncated, inconsistent, contradictory, replayed, self-promoting) through the real producer. Each one holds `go`, names its cause and leads with "Resolve…" or "Reconcile…". |
| 5 | Internal arithmetic agreement does not become verification | Every reading says "unverified report" and "not verified". No assessment contains a verification phrase. The step-9 gap text states what is not checked. |
| 6 | A go recommendation creates no execution authority | `requires_human_approval` is true on every assessment and every receipt. `authority_created` is false and `external_effects` is None. The fifteen-step mission still closes only through its existing gates. |
| 7 | Existing isolation, approval, interruption, revocation and reconciliation behaviour is intact | `job8.txt`: CI job 8's full command passes, 117 of 117, with real organs, bubblewrap, `GREG_REQUIRE_LANDLOCK=1` and no skips. That run covers the 15-step SIGKILL reconciliation, the forged-attach refusal, the separate-process appraisal and the attack suite. |
| 8 | The evidence names exact revisions, configuration, environment, commands, outcomes and limitations | Each file's header in this directory. |

## Files

| File | What it shows |
|---|---|
| `three-pins.txt` | The contrast test against WMI `7a45d22` (7 of 7 fail), `b2c7f23` (5 pass, 2 fail: merged contradictory and replayed reports are held but misread as malformed) and `0e80582` (7 of 7 pass). |
| `contrast-wmi-7a45d223.json`, `contrast-wmi-0e80582d.json`, `contrast.py` | The two assessments per head, produced by the script beside them. |
| `job8.txt` | CI job 8's full command run locally on the new pin: 117 passed. |
| `loop15-step-map.json` | The fifteen-step mission's step → ledger-event map from that run. In step 9, WealthMachine's reading is `staffed=8, total_demand=9, shortage=1, unfilled={"Dock2": 1}`, its first validation step is the shortage, the verdict is `needs_more_evidence`, and the organ heads are exact. The ledger chain is verified (578 records). `counts_toward_vepmc` is false. |
| `ablation.txt` | Without `recommended_next_action` in the receipt summary, 2 of 7 contrast tests fail. |
| `deliberation.json` | Five roles and exactly two passes, validated by the collaboration protocol's `validate_deliberation.py`. Decision: EXPERIMENT. |

WMI's own evidence is in WMI #47, under `docs/evidence/staffing-reader-hardening-2026-10-28/`:

- 35 of 46 new tests fail on #45 and 46 of 46 pass;
- 28 of 28 guard-removal mutants are caught;
- the WMI suite passes 213 of 213;
- an independent five-lens review was run, and skeptic verification was still running at push time.

## What changed in the Kernel

- `greg/organs.py`: the receipt's assessment summary adds `recommended_next_action`. This is untrusted organ text that the journal already retains.
- `tests/integration/test_one_mission_fifteen_steps.py`: step 9 now asserts WealthMachine's reading of the 8-of-9 answer, its first step, the capped verdict and human approval, all from the signed assessment the Kernel verified and retained. GAPS[9] and the docstring are updated.
- `tests/integration/test_organ_staffing_figures.py` (new): the contrast test, the 8-of-9 case and the five hostile cases. It is added to CI job 8's list.
- `.github/workflows/canonical-ci.yml`: WMI `ref` changes to `0e80582d` in jobs 5 and 8. Job 5's real-consumer test passes on it (4 of 4, local).
- `organs/wealthmachine.manifest.yaml`: `last_verified` now names `0e80582d`.

## Limits

- **What is checked:** only a report's internal arithmetic. A consistent fabrication still reads as consistent. Original-input verification needs an original-input reference in the packet, which is a Kernel contract-owner decision.
- **Remaining transport gaps (unchanged):** HMAC still lets WealthMachine forge DALEOBANKS's signature. The second WealthMachine process shows same-code determinism, not independent verification.
- **Real-world tier:** the staffing problems are synthetic, and the founder key is a test key. There is no real staffing outcome or buyer. VEPMC stays 0.
- **Review and records:** no hosted Canonical CI result yet, no independent review, no integrator acknowledgment, no merge. On intake, the ledger row INTENT-20261023-ORGAN-PINS-UPGRADED ("WealthMachine counts evidence items but does not read figures") is closed by this child. The integrator's dated handoff `INTEGRATION-196-HANDOFF-2026-10-22.md` is left as written.
