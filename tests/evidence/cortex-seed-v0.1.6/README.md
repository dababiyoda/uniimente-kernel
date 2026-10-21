# Cortex seed v0.1.6 — frozen held-out run with the declared baselines served from a recorded transcript

Freeze `cortex/evaluation/freeze-v0.1.6.json` (sha256:1f736f20273759a72979d916a2fa5395f7673d0291ace9f3b8b628c181722c88), frozen at 2026-10-14T00:22:13Z;
run at 2026-10-14T00:39:15Z; 42 held-out items; scoring `cortex-scoring/0.2`; exit rule
unchanged since 0.1.3.

**Exit: `GAIN_ABSENT`** (promote: False). Reasons recorded by the frozen exit rule:

- gain over always_llm not established (lower bound 0.024)
- gain over llm_committee not established (lower bound 0.000)

The rule needs, for each declared baseline, a paired-gain 95% lower bound above 0.05, no more
critical errors than the baseline, gain in at least 2 geometry groups with no group worse,
and no gate violation. `GAIN_ABSENT` is the rule's label for "a gain was not established"; it is not a finding that
the arms are equal.

| Arm | Status | Mean quality [95% CI] | critical / unsupported certainty / gate violations | p95 latency / cost recorded | Paired gain of routed over this arm [95% CI] |
| --- | --- | --- | --- | --- | --- |
| `routed_seed` | RUN | 1.000 [1.000, 1.000] | 0 / 0 / 0 | 0.142s / 0.0000 | — |
| `always_llm` | RUN | 0.905 [0.810, 0.976] | 2 / 3 / 1 | 0.001s / 0.0000 | +0.095 [0.024, 0.190] |
| `llm_committee` | RUN | 0.929 [0.833, 1.000] | 1 / 3 / 1 | 0.002s / 0.0000 | +0.071 [0.000, 0.143] |
| `always_abstain` | RUN | 0.577 [0.452, 0.696] | 0 / 0 / 0 | 0.000s / 0.0000 | +0.423 [0.304, 0.548] |

Items any arm did not answer fully correctly:

| Arm | Item | Geometry | Disposition | Score | Critical | Unsupported certainty | Gate violation |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `always_llm` | H-F08 | formal | recommend | 0.00 | no | yes | no |
| `always_llm` | H-G03 | options | abstain | 0.00 | no | no | no |
| `always_llm` | H-G04 | options | recommend | 0.00 | yes | yes | yes |
| `always_llm` | H-N01 | normative_value | recommend | 0.00 | yes | yes | no |
| `llm_committee` | H-F08 | formal | recommend | 0.00 | no | yes | no |
| `llm_committee` | H-G03 | options | recommend | 0.00 | no | yes | no |
| `llm_committee` | H-G04 | options | recommend | 0.00 | yes | yes | yes |

Per geometry group (mean item score):

| Geometry | routed_seed | always_llm | llm_committee |
| --- | --- | --- | --- |
| claim:association | 1.000 (n=1) | 1.000 (n=1) | 1.000 (n=1) |
| claim:factual_support | 1.000 (n=5) | 1.000 (n=5) | 1.000 (n=5) |
| claim:intervention | 1.000 (n=5) | 1.000 (n=5) | 1.000 (n=5) |
| claim:prediction | 1.000 (n=1) | 1.000 (n=1) | 1.000 (n=1) |
| composition | 1.000 (n=2) | 1.000 (n=2) | 1.000 (n=2) |
| estimate | 1.000 (n=6) | 1.000 (n=6) | 1.000 (n=6) |
| formal | 1.000 (n=11) | 0.909 (n=11) | 0.909 (n=11) |
| legal | 1.000 (n=1) | 1.000 (n=1) | 1.000 (n=1) |
| none | 1.000 (n=1) | 1.000 (n=1) | 1.000 (n=1) |
| normative_value | 1.000 (n=1) | 0.000 (n=1) | 1.000 (n=1) |
| options | 1.000 (n=5) | 0.600 (n=5) | 0.600 (n=5) |
| semantic | 1.000 (n=3) | 1.000 (n=3) | 1.000 (n=3) |

Kill criterion (ADR): `GAIN_ABSENT` on two frozen versions **with no critical-error advantage**. This is the first
frozen version with the baselines run, and the routed seed has the critical-error advantage, so the criterion is not met.

The 42 routed items compared with 0.1.5 item for item (`heldout-routed-vs-v0.1.5.json`): with the semantic organ
unavailable, as it was in 0.1.5 (`heldout-routed-no-model.json`, same freeze), there are
0 scoring-field differences. With the organ served by
the transcript, the 4 sourced items
(H-M02, H-S01, H-S02, H-S04) move from `DEPENDENCY_UNAVAILABLE` to `OK`
(14 field differences, all on those items). Answer-only differences elsewhere
are other valid Z3 witnesses or last-digit floating-point differences.

## How the baseline arms were served

- Model: every reply in `baseline-transcript.json` and `semantic-transcript.json` was served by frontier-model-A,
  an Anthropic frontier model, attributed per reply from the model field of its agent transcript. Repository artifacts
  carry neutral labels (frontier-model-A, frontier-model-B); the exact model identifiers are kept out of repository
  artifacts by this session's publication rule and are recorded in the session. The user switched the session's model
  during collection; 55 baseline replies and 5 semantic replies first served by frontier-model-B were re-collected with
  identical prompts. The earlier replies are kept in the `*-frontier-model-B-partial.json` files and no reported arm
  uses them.
- Run record: these results are from a second run of the same frozen inputs and transcripts. The first run
  (2026-10-14T00:25:44Z) is not kept in the repository only because its labels carried exact model identifiers; every
  item score, every arm summary and the exit were compared between the two runs and are identical.
- Baseline transcript: sha256:045d5361373a6f832e5bf26be67b8811418157176ff7d640e3722b87308c9f13; 184 replies used, one per prompt;
  0 replies failed the tool-use audit (`baseline-transcript-audit.json` lists every collected reply, used or not);
  the harness requested 168 prompts, served 168,
  missed 0.
- Semantic transcript: sha256:8e405a020ada8eed11c661764e1e25164a8a5fe3718e72173503491e8f8a3caf; 5 replies used; observed during the run:
  {"model_label_on_receipts": "frontier-model-A", "prompts_missing": 0, "prompts_requested": 4, "prompts_served": 4}.
- Replay code: sha256:5dd31759527713c8ca2d16ec0f561631f7cd97c314ada29bc8f09d8dd0668455. The harness, scorer, suites and exit rule are the frozen
  ones; `cortex/evaluation/replay.py` only supplies the `client.complete` replies and annotates provenance.
- Operator-declared provenance (`arm-provenance.json`) and the harness-computed record are both in
  `heldout-results.json` under `arm_provenance`.

## Read narrowly

- The baseline model is from the same vendor family as the agents that authored the held-out suite.
- The suite is self-authored and structured-only: 42 items in six geometry groups. A free-text, externally authored
  suite is the next evidence step.
- Replayed arms carry cost 0.0 and Workflow wall-clock latency; the cost and latency criteria therefore do not
  discriminate in the routed seed's favour and are not comparable across arms.
- Tool use was prohibited by instruction and audited after the fact from agent transcripts; it was not blocked at
  runtime.
- Smoke and dev are development partitions, not reported results. `smoke-results.json` is replayed with both
  transcripts; `dev-results.json` has no transcript, so its language-model arms are `NOT_RUN`.
- Nothing in this directory creates authority or promotes any organ.
