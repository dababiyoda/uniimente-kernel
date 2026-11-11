CONNECTED STAFFING PROOF: INDEPENDENT VERIFICATION
==================================================

Date: 2026-11-11. Host: Linux 6.18.44, 4 CPUs shared with other workers. Verification only: no repository file was
changed, nothing was committed, pushed, published, sent or spent. Reality tier: LABORATORY on this container, with
synthetic staffing problems. Nothing here is founder-used, externally verified or counted toward VEPMC.

RESULT
------

The claim holds on the integration head with the real organs at the commits the Kernel's CI pins.

- tests/integration/test_organ_staffing_figures.py: 7 passed, 0 failed, 0 skipped.
- tests/unit/test_greg_organs.py (all of it, the five live exchanges included): 43 passed, 0 failed, 0 skipped.
- The 8-of-8 packet and the 4-of-8 packet differ only in the staffing report. WealthMachine returned different
  go_no_go ("go" against "needs_more_evidence"), different reasons, a different first validation_plan step and a
  different recommended_next_action. Every other assessment field, the engine's scores included, is identical
  (id, opportunity_packet_id and created_at differ on every run by construction and are left out of the comparison).
- Fail-before control: with WealthMachine at #44 (before #45) the same test fails 7 of 7, and the two packets get the
  same assessment (no field differs; both "go").
- Neither packet is treated as verified. Each reading says "(unverified report)" and "original demand, capacity and
  optimality are not verified"; requires_human_approval is true in both assessments and both receipts; the Kernel
  retained both organ messages as content_trust "untrusted"; the appraisal is REPRODUCED at tier "multi-process
  reproduction + invariant check; not external acceptance"; authority_created is false and external_effects is None.

Four things a reader should know before relying on this (details in FINDINGS and SIDE EFFECT):

1. The verdict the Kernel's receipt states (`verdict`) is "needs_more_evidence" for BOTH packets. The Kernel caps
   WealthMachine's "go" because the packet states no governing_bottleneck. The difference between 8 of 8 and 4 of 8
   is in WealthMachine's own verdict (`engine_verdict`, `assessment.go_no_go`), in `verdict_why`, and in the retained
   assessment body. A consumer that reads only `verdict` cannot tell the two cases apart.
2. In the shared kernel venv of this container (requirements-dev only, no networkx) the staffing test file is skipped
   at import, also under UNIIMENTE_REQUIRE_ORGANS=1, and a combined run exits 0. The runs below used a separate venv
   with requirements-cognition.txt installed, as CI job 8 does.
3. WealthMachine checks a report's internal arithmetic only. A fabricated report that is self-consistent gets "go"
   from WealthMachine (run 18). The reading's label "unverified report" is accurate. What keeps such a report from a
   Kernel-stated "go" is the cap in point 1; what keeps it from any action is requires_human_approval. Neither is
   a check of the report.
4. This verification's three venvs take 4.2 GB, and free disk on this shared container is now 8.5% of the device,
   below the Kernel's 10% compute-telemetry threshold (SIDE EFFECT ON THE SHARED MACHINE).


COMMITS
-------

| Repository | Commit | What it is |
| --- | --- | --- |
| uniimente-kernel | 8d20532464b1533b28d71d8331ca3412a90dbb11 | PR #196 head (local ref pr196), detached worktree |
| DALEOBANKS | 664ac98c553759ce754bb684cb248225343edd7e | PR #96 head, fetched as local ref pr96; the commit CI job 8 pins |
| WealthMachineIntelligence | 0e80582d6d4f5b4d2477e13d2bb48fb4a57be3e6 | first commit of PR #47 (pr47~1); the commit CI job 8 pins |

Which organ revisions are appropriate was read from the code, not assumed: .github/workflows/canonical-ci.yml on
pr196 (job "8 · One machine", lines 375-386) checks out DALEOBANKS at 664ac98c and WealthMachineIntelligence at
0e80582d, and its comment names DALEOBANKS #96 and WealthMachineIntelligence #47 (on #45, on #44).

Difference from the task's starting point: the task said to start with WealthMachine pr47 (26c697e7). The Kernel pins
0e80582d, one commit earlier. `git diff --stat 0e80582 26c697e` changes one file,
docs/evidence/staffing-reader-hardening-2026-10-28/README.md (26 insertions, 3 deletions), and no code. The primary
runs use the pinned 0e80582d. The PR head 26c697e7 was run as well (run 6): same result.

Other WealthMachine commits used as controls: 7a45d223b74d6eea3b9ed5bdaeb12a3625b525de (#44, local ref pr44),
b2c7f2347771e78ee5a6b250a4d2c0ca5b6abd50 (#45, local ref pr45), 26c697e769108375372171c607ed7f45a3eb4661 (#47 head).
pr47 contains pr45 contains pr44 (checked with git merge-base --is-ancestor).

Worktrees (all detached, all clean before and after; the main checkouts under /home/user were not touched):

    /tmp/claude-0/-home-user/f78643ba-8a14-5107-b25c-e0462dfdc774/scratchpad/staffing-proof/kernel-pr196            8d205324
    /tmp/claude-0/-home-user/f78643ba-8a14-5107-b25c-e0462dfdc774/scratchpad/organs/daleobanks                      664ac98c
    /tmp/claude-0/-home-user/f78643ba-8a14-5107-b25c-e0462dfdc774/scratchpad/organs/wealthmachine                   0e80582d
    /tmp/claude-0/-home-user/f78643ba-8a14-5107-b25c-e0462dfdc774/scratchpad/organs/wealthmachine-pr47head          26c697e7
    /tmp/claude-0/-home-user/f78643ba-8a14-5107-b25c-e0462dfdc774/scratchpad/organs/wealthmachine-pr45              b2c7f234
    /tmp/claude-0/-home-user/f78643ba-8a14-5107-b25c-e0462dfdc774/scratchpad/organs/wealthmachine-pr44              7a45d223
    /tmp/claude-0/-home-user/f78643ba-8a14-5107-b25c-e0462dfdc774/scratchpad/organs/daleobanks-before-pr96          667439f4   (run 19)
    /tmp/claude-0/-home-user/f78643ba-8a14-5107-b25c-e0462dfdc774/scratchpad/staffing-proof/kernel-rehearsal-snapshot  b8d95167   (runs 16, 17)

The only change made in a main checkout's git metadata: the local ref pr96 in /home/user/DALEOBANKS (the task's
`git fetch origin refs/pull/96/head:pr96`) and the worktree registrations above.


INTERPRETERS AND THE BOUNDARY PIN
---------------------------------

One venv per organ, Python 3.11.18 (/usr/bin/python3.11, the version CI job 8 uses), each from the organ's own
requirements.txt, nothing else:

    /usr/bin/python3.11 -m venv .../scratchpad/organs/daleobanks-venv
    .../daleobanks-venv/bin/pip install -r .../organs/daleobanks/requirements.txt          exit 0
    /usr/bin/python3.11 -m venv .../scratchpad/organs/wealthmachine-venv
    .../wealthmachine-venv/bin/pip install -r .../organs/wealthmachine/requirements.txt    exit 0

WealthMachine's requirements are identical at pr44, pr45 and pr47 (`git diff pr44 pr47 -- requirements.txt
pyproject.toml` is empty), so one venv serves every WealthMachine commit; the exchange runs the organ's code from a
`git archive` snapshot of the checkout's HEAD, never from the venv.

Both organs pin the boundary package the same way (requirements.txt, and docs/KERNEL_PIN_UPGRADE_2026-10-23.md):

    uniimente-kernel-boundaries @ https://github.com/dababiyoda/uniimente-kernel/archive/e7dc0cbc9c9a9491da253deee018d471af5a77df.tar.gz

The proxy reached that URL (HTTP 200), so pip installed the pin exactly as specified; no local substitute was
needed. Checked afterwards, in both venvs:

- direct_url.json records that URL with archive sha256
  603cb0997599386cb7043544d9aa5cca32522d426b8e4967c1d39266ee7e0b3f;
- the installed adapters/bridge_transport.py has sha256
  409c25fab5984a1a39dd5e4f0d84e278111180113196ceb5c56d1c89f81aaf3e, equal to
  `git show e7dc0cbc:adapters/bridge_transport.py` and to `git show pr196:adapters/bridge_transport.py` in the local
  kernel repository;
- e7dc0cbc is an ancestor of pr196.

Kernel interpreter: the shared venv (.../scratchpad/venv, requirements-dev only) has no networkx, so the staffing
test file is skipped there (FINDING 2). A separate venv was built and nothing was installed into the shared one:

    /usr/local/bin/python3 -m venv .../scratchpad/staffing-proof/kernel-venv                      (Python 3.13.18)
    .../kernel-venv/bin/pip install -r requirements-dev.txt -r requirements-cognition.txt -r requirements-research-line.txt    exit 0

These are the three files CI job 8 installs. CI runs the Kernel on Python 3.11; this container's kernel convention is
3.13, and 3.13 was used. pip freeze of all three venvs is in logs/.

Landlock is available here (abi 7), so each organ stage ran confined: the receipts say filesystem_confined true for
both organs.


ENVIRONMENT VARIABLES (staffing-proof/env.sh, sourced by every run)
-------------------------------------------------------------------

    UNIIMENTE_REQUIRE_ORGANS=1
    GREG_REQUIRE_LANDLOCK=1
    UNIIMENTE_DALEOBANKS_ROOT=/tmp/claude-0/-home-user/f78643ba-8a14-5107-b25c-e0462dfdc774/scratchpad/organs/daleobanks
    UNIIMENTE_DALEOBANKS_PYTHON=/tmp/claude-0/-home-user/f78643ba-8a14-5107-b25c-e0462dfdc774/scratchpad/organs/daleobanks-venv/bin/python
    UNIIMENTE_WEALTHMACHINE_ROOT=/tmp/claude-0/-home-user/f78643ba-8a14-5107-b25c-e0462dfdc774/scratchpad/organs/wealthmachine
    UNIIMENTE_WEALTHMACHINE_PYTHON=/tmp/claude-0/-home-user/f78643ba-8a14-5107-b25c-e0462dfdc774/scratchpad/organs/wealthmachine-venv/bin/python

The four organ variables are the ones tests/unit/test_greg_organs.py reads (ORGAN_ENV, line 25);
UNIIMENTE_REQUIRE_ORGANS=1 turns an unconfigured skip into a failure (live_organs, line 34). GREG_REQUIRE_LANDLOCK=1
is what CI job 8 sets beside them. The control runs override UNIIMENTE_WEALTHMACHINE_ROOT only, as stated per run.


COMMANDS AND RESULTS
--------------------

Every pytest run: cwd = the kernel worktree, interpreter = staffing-proof/kernel-venv/bin/python, form
`python -m pytest -q -p no:cacheprovider -rA --basetemp=<own dir> <files> --junitxml=<log>.xml`.
K = .../scratchpad/staffing-proof. Raw output of each is logs/<name>.log.

| Run | What | WealthMachine at | Result |
| --- | --- | --- | --- |
| 0 | first attempt of run 1 | 0e80582d | my harness error: --basetemp parent directory did not exist; 7 errors at fixture setup, no test body ran. Kept as logs/run0-harness-error-missing-basetemp-parent.log |
| 1 | tests/integration/test_organ_staffing_figures.py | 0e80582d (pin) | 7 passed, 0 failed, 0 skipped, 13.2 s |
| 2 | tests/unit/test_greg_organs.py | 0e80582d (pin) | 43 passed, 0 failed, 0 skipped, 6.7 s |
| 3 | capture_assessments.py (8/8 and 4/8, verbatim fields) | 0e80582d (pin) | exit 0; the two assessments differ in go_no_go, reasons, recommended_next_action, validation_plan and in no other compared field |
| 4 | FAIL-BEFORE: test_organ_staffing_figures.py | 7a45d223 (#44) | 7 failed, 0 passed |
| 5 | FAIL-BEFORE: capture_assessments.py | 7a45d223 (#44) | exit 0; "(no difference)" between the two assessments; both "go"; no staffing reading |
| 6 | test_organ_staffing_figures.py + test_greg_organs.py | 26c697e7 (#47 head) | 50 passed, 0 failed, 0 skipped |
| 7 | test_organ_staffing_figures.py | b2c7f234 (#45) | 5 passed, 2 failed (hostile cases "contradictory" and "replayed") |
| 8 | gate control: organ variables unset, UNIIMENTE_REQUIRE_ORGANS=1 | none | 7 failed ("organ checkouts not configured"), exit 1 |
| 9 | gate control: organ variables unset, not required | none | 7 skipped, exit 0 |
| 10 | shared kernel venv (no networkx), organs configured and required, staffing file alone | 0e80582d | 1 skipped at import ("could not import 'networkx'"), exit 5 |
| 11 | shared kernel venv, staffing file plus one other test | 0e80582d | 1 passed, 1 skipped, exit 0 |
| 12 | tests/integration/test_one_mission_fifteen_steps.py | 0e80582d | 1 skipped: "bubblewrap is unavailable on this host" |
| 13 | the same, scratchpad bwrap on the test's PATH only | 0e80582d | 1 failed after 262 s: my provisioning was incomplete (see SIGNED MISSION) |
| 14 | the same, bwrap provided in a private mount namespace | 0e80582d | 1 passed, 77 s |
| 15 | heldout_cases.py (five problems the test file does not contain) | 0e80582d (pin) | exit 0; every stated expectation held |
| 16 | SUPPLEMENTARY: staffing + organs on the composed rehearsal snapshot b8d95167 | 0e80582d | 50 passed, 0 failed, 0 skipped |
| 17 | SUPPLEMENTARY: fifteen-step mission on b8d95167 (private namespace) | 0e80582d | 1 passed, 98 s |
| 18 | consistent_lie.py (a fabricated, self-consistent 8/8 report for the 4/8 problem) | 0e80582d (pin) | exit 0; WealthMachine "go", reading labelled unverified, Kernel-stated verdict "needs_more_evidence" (FINDING 3) |
| 13b | run 13 repeated, to keep its ledger (capture/run13b-ledger/) | 0e80582d | 1 failed after 262 s, the same way; the ledger shows worker.commission REFUSED: "bubblewrap is unavailable on this host" |
| 20 | shared kernel venv: three of this container's known-failure files (test_greg_acceptance_reality.py, test_greg_rehearsal_founder_tier.py, test_greg_large_inline_mission.py) | none | 5 failed, 16 passed: the listed 3 + 1 + 1, no more |
| 19 | ABLATION on the other organ: test_organ_staffing_figures.py with DALEOBANKS at 667439f4 (the parent of #96) | 0e80582d (pin) | 7 failed, 0 passed |

Run 19: DALEOBANKS's code at 667439f49442bd898d3655666a389f53114f1412 (worktree .../scratchpad/organs/
daleobanks-before-pr96) in the same DALEOBANKS venv, so the boundary package is the new pin and only #96's refinery
change (services/idea_refinery.py) is removed. The first test fails at line 129, `assert len(reports) == 1` with 0
reports: the packet carries no staffing report at all. Both organ changes are needed: #96 to carry the report, #45/#47
to read it.

Run 1, each test (from logs/run1-staffing-pin.xml):

    PASSED test_a_shortage_changes_reasons_evidence_requests_and_priority_with_nothing_else_changed
    PASSED test_the_fifteen_step_missions_answer_holds_the_verdict_and_leads_with_its_shortage
    PASSED test_hostile_reports_keep_explicit_uncertainty[contradictory]
    PASSED test_hostile_reports_keep_explicit_uncertainty[inconsistent]
    PASSED test_hostile_reports_keep_explicit_uncertainty[replayed]
    PASSED test_hostile_reports_keep_explicit_uncertainty[self-promoting]
    PASSED test_hostile_reports_keep_explicit_uncertainty[truncated]

Run 2, the live exchanges among the 43 (all passed):

    test_live_exchange_never_signs_as_an_organ_when_per_organ_keys_are_configured
    test_live_exchange_runs_real_organ_code_and_reproduces
    test_a_seed_with_no_opportunity_is_a_truthful_answer_not_a_fault
    test_an_answer_signed_with_another_organs_key_is_refused_at_the_kernel
    test_a_shared_scope_message_is_refused

Run 4, where the fail-before run fails: the first test stops at line 142,
`[reason_f], [reason_s] = readings(wmi_f), readings(wmi_s)`, with "ValueError: not enough values to unpack (expected
1, got 0)": WealthMachine at #44 produces no staffing reading. The fifteen-step answer test fails the same way at
line 178, and the five hostile cases fail `assert lines and ...` with an empty list. Run 5 shows the cause directly.

Run 7 (#45, before #47's hardening): the 8/8 against 4/8 test and the 8/9 test pass; "contradictory" and "replayed"
fail because #45's reader takes two reports in one evidence item as one malformed report. That is what #47 fixed, and
it is why the Kernel pins #47's commit.


THE CAPTURED EXCHANGE, VERBATIM (run 3; the whole of capture/capture-pin-dale664ac98-wmi0e80582.txt)
-----------------------------------------------------------------------------------------------------

Produced by capture_assessments.py through the test module's own certified(), seed_for() and run() helpers, hence
greg.organs.exchange with the real organs. Everything between the two rules below is the script's output.

~~~~ begin capture ~~~~
CAPTURE pin-dale664ac98-wmi0e80582
kernel HEAD        8d20532464b1533b28d71d8331ca3412a90dbb11
DALEOBANKS HEAD    664ac98c553759ce754bb684cb248225343edd7e
WealthMachine HEAD 0e80582d6d4f5b4d2477e13d2bb48fb4a57be3e6

=== full_8_of_8: GREG certified staffed=8 total_demand=8 shortage=0 unfilled={}
exchange: appraisal_verdict=REPRODUCED transport_verified=True sender_identity_isolated=True authority_created=False external_effects=None spend_usd=0.0
organ code that ran: {"daleobanks": {"filesystem_confined": true, "head": "664ac98c553759ce754bb684cb248225343edd7e", "tree_sha256": "039b2d6606927f2bb1e05434143739fa940c76ea203313fe99a30c9aa15286e4", "uncommitted_changes_ignored": false}, "wealthmachine": {"filesystem_confined": true, "head": "0e80582d6d4f5b4d2477e13d2bb48fb4a57be3e6", "tree_sha256": "64352a0fb1a84110ebad91e7011f82d80b72efed018748a89b32e4a92c74ea90", "uncommitted_changes_ignored": false}}
kernel-stated verdict='needs_more_evidence' (why: "unevidenced canonical fields (governing_bottleneck), which caps the engine's 'go'"); engine_verdict='go'
DALEOBANKS packet evidence (2 items):
  [0] operator thought 1b1177a4-f81a-48c2-9a2d-0570e9f2bb25
  [1] Evidence from GREG's certified staffing plan for the docks and the line: {
 "assignment": [
  [
   "Ana",
   "Dock",
   4
  ],
  [
   "Ben",
   "Line",
   4
  ]
 ],
 "bottleneck": null,
 "certificate": {
  "arithmetic": "exact integers",
  "checked_by": "GREG, from the original problem; shares no code with the engine",
  "kind": "deficiency set (generalized Hall/Koenig): staffed equals demand outside U plus capacity of U's eligible workers"
 },
 "certified": true,
 "shortage": 0,
 "staffed": 8,
 "total_demand": 8,
 "unfilled": {}
}
WealthMachine assessment (verbatim fields):
  go_no_go = "go"
  reasons = [
  "opportunity score 0.696 meets the 0.55 threshold",
  "engine risk level: Ultra Low",
  "[bear] only 1 evidence item(s); demand is asserted, not shown; willingness to pay is untested until a buyer commits value",
  "[incumbent_response] an incumbent with distribution can copy educational checklist quickly; the durable edge must be trust and cultural specificity, not the artifact itself",
  "[adoption_friction] audience interest does not imply workflow change; the smallest validation action must measure behavior, not applause",
  "finance content must remain educational; no personalized advice",
  "staffing evidence[1] (unverified report): staffed=8, total_demand=8, shortage=0, unfilled={}; internal arithmetic agrees only; original demand, capacity and optimality are not verified"
]
  validation_plan = [
  "Validate the reported staffing result of 8/8 units against original demand and capacity; obtain independent acceptance before relying on it",
  "Post one educational thread on the thesis and offer a free checklist waitlist; measure saves, replies, and signups",
  "Draft landing-page copy and collect waitlist interest (no payment yet)",
  "Run 3-5 buyer interviews from engaged repliers"
]
  recommended_next_action = "Validate the reported staffing result of 8/8 units against original demand and capacity; obtain independent acceptance before relying on it"
  requires_human_approval = true
  opportunity_score = 0.696
  market_alignment = 0.49
  risk_level = "low"
  legal_readiness = "review_required"
  expected_roi = "modeled 14.225x over 18 months; unknown until validation — no revenue promises"
  pricing_hypothesis = "$33.64 modeled price point; test willingness to pay before building"

=== short_4_of_8: GREG certified staffed=4 total_demand=8 shortage=4 unfilled={"Dock": 2, "Line": 2}
exchange: appraisal_verdict=REPRODUCED transport_verified=True sender_identity_isolated=True authority_created=False external_effects=None spend_usd=0.0
organ code that ran: {"daleobanks": {"filesystem_confined": true, "head": "664ac98c553759ce754bb684cb248225343edd7e", "tree_sha256": "039b2d6606927f2bb1e05434143739fa940c76ea203313fe99a30c9aa15286e4", "uncommitted_changes_ignored": false}, "wealthmachine": {"filesystem_confined": true, "head": "0e80582d6d4f5b4d2477e13d2bb48fb4a57be3e6", "tree_sha256": "64352a0fb1a84110ebad91e7011f82d80b72efed018748a89b32e4a92c74ea90", "uncommitted_changes_ignored": false}}
kernel-stated verdict='needs_more_evidence' (why: 'unevidenced canonical fields (governing_bottleneck); engine verdict already no higher'); engine_verdict='needs_more_evidence'
DALEOBANKS packet evidence (2 items):
  [0] operator thought 88520458-9a99-41c2-b7ba-e3943421d2e6
  [1] Evidence from GREG's certified staffing plan for the docks and the line: {
 "assignment": [
  [
   "Ana",
   "Dock",
   2
  ],
  [
   "Ben",
   "Line",
   2
  ]
 ],
 "bottleneck": {
  "capacity": 4,
  "demand": 8,
  "eligible_workers": [
   "Ana",
   "Ben"
  ],
  "orders": [
   "Dock",
   "Line"
  ],
  "why": "these orders can only be served by these workers, whose whole capacity is short of their demand; no assignment can do better without more capacity for exactly them"
 },
 "certificate": {
  "arithmetic": "exact integers",
  "checked_by": "GREG, from the original problem; shares no code with the engine",
  "kind": "deficiency set (generalized Hall/Koenig): staffed equals demand outside U plus capacity of U's eligible workers"
 },
 "certified": true,
 "shortage": 4,
 "staffed": 4,
 "total_demand": 8,
 "unfilled": {
  "Dock": 2,
  "Line": 2
 }
}
WealthMachine assessment (verbatim fields):
  go_no_go = "needs_more_evidence"
  reasons = [
  "opportunity score 0.696 meets the 0.55 threshold",
  "engine risk level: Ultra Low",
  "[bear] only 1 evidence item(s); demand is asserted, not shown; willingness to pay is untested until a buyer commits value",
  "[incumbent_response] an incumbent with distribution can copy educational checklist quickly; the durable edge must be trust and cultural specificity, not the artifact itself",
  "[adoption_friction] audience interest does not imply workflow change; the smallest validation action must measure behavior, not applause",
  "finance content must remain educational; no personalized advice",
  "staffing evidence[1] (unverified report): staffed=4, total_demand=8, shortage=4, unfilled={\"Dock\": 2, \"Line\": 2}; internal arithmetic agrees only; original demand, capacity and optimality are not verified",
  "reported staffing shortfall or inconsistent evidence requires validation before proceeding"
]
  validation_plan = [
  "Validate the reported staffing shortage of 4 units against original demand and capacity; resolve unfilled orders {\"Dock\": 2, \"Line\": 2} before proceeding",
  "Post one educational thread on the thesis and offer a free checklist waitlist; measure saves, replies, and signups",
  "Draft landing-page copy and collect waitlist interest (no payment yet)",
  "Run 3-5 buyer interviews from engaged repliers"
]
  recommended_next_action = "Validate the reported staffing shortage of 4 units against original demand and capacity; resolve unfilled orders {\"Dock\": 2, \"Line\": 2} before proceeding"
  requires_human_approval = true
  opportunity_score = 0.696
  market_alignment = 0.49
  risk_level = "low"
  legal_readiness = "review_required"
  expected_roi = "modeled 14.225x over 18 months; unknown until validation — no revenue promises"
  pricing_hypothesis = "$33.64 modeled price point; test willingness to pay before building"

=== unified diff of the two assessments (ids and created_at removed)
--- assessment for 8/8
+++ assessment for 4/8
@@ -53,3 +53,3 @@
  "expected_roi": "modeled 14.225x over 18 months; unknown until validation — no revenue promises",
- "go_no_go": "go",
+ "go_no_go": "needs_more_evidence",
  "legal_readiness": "review_required",
@@ -70,5 +70,6 @@
   "finance content must remain educational; no personalized advice",
-  "staffing evidence[1] (unverified report): staffed=8, total_demand=8, shortage=0, unfilled={}; internal arithmetic agrees only; original demand, capacity and optimality are not verified"
+  "staffing evidence[1] (unverified report): staffed=4, total_demand=8, shortage=4, unfilled={\"Dock\": 2, \"Line\": 2}; internal arithmetic agrees only; original demand, capacity and optimality are not verified",
+  "reported staffing shortfall or inconsistent evidence requires validation before proceeding"
  ],
- "recommended_next_action": "Validate the reported staffing result of 8/8 units against original demand and capacity; obtain independent acceptance before relying on it",
+ "recommended_next_action": "Validate the reported staffing shortage of 4 units against original demand and capacity; resolve unfilled orders {\"Dock\": 2, \"Line\": 2} before proceeding",
  "requires_human_approval": true,
@@ -77,3 +78,3 @@
  "validation_plan": [
-  "Validate the reported staffing result of 8/8 units against original demand and capacity; obtain independent acceptance before relying on it",
+  "Validate the reported staffing shortage of 4 units against original demand and capacity; resolve unfilled orders {\"Dock\": 2, \"Line\": 2} before proceeding",
   "Post one educational thread on the thesis and offer a free checklist waitlist; measure saves, replies, and signups",

=== comparison
{
 "assessment_fields_identical": [
  "cases",
  "expected_roi",
  "legal_readiness",
  "market_alignment",
  "monetization_paths",
  "opportunity_score",
  "pricing_hypothesis",
  "product_hypothesis",
  "requires_human_approval",
  "risk_level",
  "schema_version"
 ],
 "assessment_fields_that_differ": [
  "go_no_go",
  "reasons",
  "recommended_next_action",
  "validation_plan"
 ],
 "engine_scores_identical": true,
 "packet_evidence_counts": {
  "full_8_of_8": 2,
  "short_4_of_8": 2
 },
 "packet_fields_that_differ": [
  "created_at",
  "evidence",
  "id",
  "source_ref"
 ],
 "staffing_readings": {
  "full_8_of_8": [
   "staffing evidence[1] (unverified report): staffed=8, total_demand=8, shortage=0, unfilled={}; internal arithmetic agrees only; original demand, capacity and optimality are not verified"
  ],
  "short_4_of_8": [
   "staffing evidence[1] (unverified report): staffed=4, total_demand=8, shortage=4, unfilled={\"Dock\": 2, \"Line\": 2}; internal arithmetic agrees only; original demand, capacity and optimality are not verified"
  ]
 },
 "verdicts": {
  "full_8_of_8": "go",
  "short_4_of_8": "needs_more_evidence"
 }
}

=== not treated as verified
{
 "authority_created_in_any_receipt": false,
 "every_reading_says_not_verified": true,
 "every_reading_says_unverified_report": true,
 "every_retained_organ_message_content_trust": [
  "untrusted"
 ],
 "external_effects_in_receipts": [
  null,
  null
 ],
 "mission_appraised_or_achieved_events": 0,
 "organ_appraisal_tiers": [
  "multi-process reproduction + invariant check; not external acceptance"
 ],
 "organ_appraisal_verdicts": [
  "REPRODUCED"
 ],
 "phrases_absent_from_both_assessments": {
  "certified plan verified": true,
  "externally verified": true,
  "independently accepted": true,
  "verified optimal": true
 },
 "requires_human_approval_in_both_assessments": true,
 "requires_human_approval_in_both_receipts": true,
 "spend_usd_in_receipts": [
  0.0,
  0.0
 ]
}
~~~~ end capture ~~~~


FAIL-BEFORE, VERBATIM (run 5; WealthMachine at #44, 7a45d223; file capture/capture-failbefore-dale664ac98-wmi7a45d22-pr44.txt)
-----------------------------------------------------------------------------------------------------------------------------

The same two packets, the same DALEOBANKS, WealthMachine before #45. An excerpt of that file: the assessment for
the 4-of-8 packet and the comparison. Lines are quoted unchanged; each [...] marks lines left out here (the packet
evidence, and the 8-of-8 assessment, which is identical to the 4-of-8 one apart from id, opportunity_packet_id and
created_at). The complete file is beside this one.

~~~~ begin capture ~~~~
CAPTURE failbefore-dale664ac98-wmi7a45d22-pr44
kernel HEAD        8d20532464b1533b28d71d8331ca3412a90dbb11
DALEOBANKS HEAD    664ac98c553759ce754bb684cb248225343edd7e
WealthMachine HEAD 7a45d223b74d6eea3b9ed5bdaeb12a3625b525de
[...]
=== short_4_of_8: GREG certified staffed=4 total_demand=8 shortage=4 unfilled={"Dock": 2, "Line": 2}
exchange: appraisal_verdict=REPRODUCED transport_verified=True sender_identity_isolated=True authority_created=False external_effects=None spend_usd=0.0
kernel-stated verdict='needs_more_evidence' (why: "unevidenced canonical fields (governing_bottleneck), which caps the engine's 'go'"); engine_verdict='go'
[... packet evidence as above ...]
WealthMachine assessment (verbatim fields):
  go_no_go = "go"
  reasons = [
  "opportunity score 0.726 meets the 0.55 threshold",
  "engine risk level: Ultra Low",
  "[bear] only 2 evidence item(s); demand is asserted, not shown; willingness to pay is untested until a buyer commits value",
  "[incumbent_response] an incumbent with distribution can copy educational checklist quickly; the durable edge must be trust and cultural specificity, not the artifact itself",
  "[adoption_friction] audience interest does not imply workflow change; the smallest validation action must measure behavior, not applause",
  "finance content must remain educational; no personalized advice"
]
  validation_plan = [
  "Post one educational thread on the thesis and offer a free checklist waitlist; measure saves, replies, and signups",
  "Draft landing-page copy and collect waitlist interest (no payment yet)",
  "Run 3-5 buyer interviews from engaged repliers"
]
  recommended_next_action = "Post one educational thread on the thesis and offer a free checklist waitlist; measure saves, replies, and signups"
  requires_human_approval = true
  opportunity_score = 0.726
  market_alignment = 0.49
  risk_level = "low"
  legal_readiness = "review_required"
  expected_roi = "modeled 14.225x over 18 months; unknown until validation — no revenue promises"
  pricing_hypothesis = "$33.64 modeled price point; test willingness to pay before building"

=== unified diff of the two assessments (ids and created_at removed)
(no difference)

=== comparison
{
 "assessment_fields_identical": [
  "cases",
  "expected_roi",
  "go_no_go",
  "legal_readiness",
  "market_alignment",
  "monetization_paths",
  "opportunity_score",
  "pricing_hypothesis",
  "product_hypothesis",
  "reasons",
  "recommended_next_action",
  "requires_human_approval",
  "risk_level",
  "schema_version",
  "validation_plan"
 ],
 "assessment_fields_that_differ": [],
 "engine_scores_identical": true,
 "packet_evidence_counts": {
  "full_8_of_8": 2,
  "short_4_of_8": 2
 },
 "packet_fields_that_differ": [
  "created_at",
  "evidence",
  "id",
  "source_ref"
 ],
 "staffing_readings": {
  "full_8_of_8": [],
  "short_4_of_8": []
 },
 "verdicts": {
  "full_8_of_8": "go",
  "short_4_of_8": "go"
 }
}

~~~~ end capture ~~~~


HELD-OUT PROBLEMS, VERBATIM (run 15; logs/run15-heldout-pin.log)
----------------------------------------------------------------

Five problems the Kernel's test file does not contain, certified by the Kernel's own chain and sent over the real
exchange at the pinned commits. The expectation was written into heldout_cases.py before the run: "go" exactly when
the certified shortage is 0; one reading with the exact figures, labelled unverified; the first validation step names
the figures; identical engine scores; requires_human_approval true.

~~~~ begin output ~~~~
H1 surplus capacity: certified 8/8 shortage 0 unfilled {}
   predicted 'go'; WealthMachine returned 'go'; kernel-stated 'needs_more_evidence'
   reading: ['staffing evidence[1] (unverified report): staffed=8, total_demand=8, shortage=0, unfilled={}; internal arithmetic agrees only; original demand, capacity and optimality are not verified']
   first step: Validate the reported staffing result of 8/8 units against original demand and capacity; obtain independent acceptance before relying on it
   checks: {"engine_scores_unchanged_between_problems": true, "first_step_names_the_figures": true, "no_authority_no_effect": true, "one_reading_with_exact_figures": true, "reading_labelled_unverified": true, "reproduced_and_isolated": true, "requires_human_approval": true, "verdict_as_predicted": true}
H2 one order short: certified 5/8 shortage 3 unfilled {"Line": 3}
   predicted 'needs_more_evidence'; WealthMachine returned 'needs_more_evidence'; kernel-stated 'needs_more_evidence'
   reading: ['staffing evidence[1] (unverified report): staffed=5, total_demand=8, shortage=3, unfilled={"Line": 3}; internal arithmetic agrees only; original demand, capacity and optimality are not verified']
   first step: Validate the reported staffing shortage of 3 units against original demand and capacity; resolve unfilled orders {"Line": 3} before proceeding
   checks: {"engine_scores_unchanged_between_problems": true, "first_step_names_the_figures": true, "no_authority_no_effect": true, "one_reading_with_exact_figures": true, "reading_labelled_unverified": true, "reproduced_and_isolated": true, "requires_human_approval": true, "verdict_as_predicted": true}
H3 nothing staffable: certified 0/8 shortage 8 unfilled {"Dock": 4, "Line": 4}
   predicted 'needs_more_evidence'; WealthMachine returned 'needs_more_evidence'; kernel-stated 'needs_more_evidence'
   reading: ['staffing evidence[1] (unverified report): staffed=0, total_demand=8, shortage=8, unfilled={"Dock": 4, "Line": 4}; internal arithmetic agrees only; original demand, capacity and optimality are not verified']
   first step: Validate the reported staffing shortage of 8 units against original demand and capacity; resolve unfilled orders {"Dock": 4, "Line": 4} before proceeding
   checks: {"engine_scores_unchanged_between_problems": true, "first_step_names_the_figures": true, "no_authority_no_effect": true, "one_reading_with_exact_figures": true, "reading_labelled_unverified": true, "reproduced_and_isolated": true, "requires_human_approval": true, "verdict_as_predicted": true}
H4 cross-skilled, exactly enough: certified 7/7 shortage 0 unfilled {}
   predicted 'go'; WealthMachine returned 'go'; kernel-stated 'needs_more_evidence'
   reading: ['staffing evidence[1] (unverified report): staffed=7, total_demand=7, shortage=0, unfilled={}; internal arithmetic agrees only; original demand, capacity and optimality are not verified']
   first step: Validate the reported staffing result of 7/7 units against original demand and capacity; obtain independent acceptance before relying on it
   checks: {"engine_scores_unchanged_between_problems": true, "first_step_names_the_figures": true, "no_authority_no_effect": true, "one_reading_with_exact_figures": true, "reading_labelled_unverified": true, "reproduced_and_isolated": true, "requires_human_approval": true, "verdict_as_predicted": true}
H5 enough hours, wrong skills: certified 6/8 shortage 2 unfilled {"Line": 2}
   predicted 'needs_more_evidence'; WealthMachine returned 'needs_more_evidence'; kernel-stated 'needs_more_evidence'
   reading: ['staffing evidence[1] (unverified report): staffed=6, total_demand=8, shortage=2, unfilled={"Line": 2}; internal arithmetic agrees only; original demand, capacity and optimality are not verified']
   first step: Validate the reported staffing shortage of 2 units against original demand and capacity; resolve unfilled orders {"Line": 2} before proceeding
   checks: {"engine_scores_unchanged_between_problems": true, "first_step_names_the_figures": true, "no_authority_no_effect": true, "one_reading_with_exact_figures": true, "reading_labelled_unverified": true, "reproduced_and_isolated": true, "requires_human_approval": true, "verdict_as_predicted": true}
expectations that did not hold: none
exit=0
~~~~ end output ~~~~


A FABRICATED, SELF-CONSISTENT REPORT, VERBATIM (run 18; logs/run18-consistent-lie-pin.log)
-------------------------------------------------------------------------------------------

~~~~ begin output ~~~~
{
 "appraisal_verdict": "REPRODUCED",
 "authority_created": false,
 "expectations": {
  "kernel_stated_verdict_stays_below_go": true,
  "no_authority": true,
  "reading_repeats_the_lie_as_unverified": true,
  "requires_human_approval": true,
  "wealthmachine_says_go": true
 },
 "kernel_stated_verdict": "needs_more_evidence",
 "kernel_verdict_why": "unevidenced canonical fields (governing_bottleneck), which caps the engine's 'go'",
 "organ_heads": {
  "daleobanks": "664ac98c553759ce754bb684cb248225343edd7e",
  "wealthmachine": "0e80582d6d4f5b4d2477e13d2bb48fb4a57be3e6"
 },
 "readings": [
  "staffing evidence[1] (unverified report): staffed=8, total_demand=8, shortage=0, unfilled={}; internal arithmetic agrees only; original demand, capacity and optimality are not verified"
 ],
 "recommended_next_action": "Validate the reported staffing result of 8/8 units against original demand and capacity; obtain independent acceptance before relying on it",
 "requires_human_approval": true,
 "true_certified_answer": {
  "shortage": 4,
  "staffed": 4,
  "total_demand": 8,
  "unfilled": {
   "Dock": 2,
   "Line": 2
  }
 },
 "wealthmachine_go_no_go": "go"
}
exit=0
~~~~ end output ~~~~


SIGNED MISSION PATH (beyond the assigned steps; run because the staffing test calls organs.exchange directly)
------------------------------------------------------------------------------------------------------------

tests/integration/test_organ_staffing_figures.py calls greg.organs.exchange with a constructed context: no signed
mission, no Gate, no receipt. The path on which a founder-signed mission binds the Mind's certified answer into the
organ seed is step 9 of tests/integration/test_one_mission_fifteen_steps.py. That test needs bubblewrap, which this
container does not have.

- Run 12, as the container is: SKIPPED, "the Hands step needs the real worker envelope: ... bubblewrap is unavailable
  on this host".
- Run 13: I extracted Ubuntu's bubblewrap_0.9.0-1ubuntu0.3_amd64.deb (sha256
  2461f1beee9cb04c8942739fe1a2b37e7b7c2a3d518f0779dc75f9245baa3094, equal to the SHA256 in the noble-updates and
  noble-security Packages index) into the scratchpad and put it on the test process's PATH. FAILED after 262 s at the
  240 s wait for the worker to start. Cause, read from that run's ledger: the test starts the body with a scrubbed
  environment (tests/integration/test_one_machine.py ENV, PATH=/usr/bin:/bin), so the body did not see the binary and
  refused worker.commission with "bubblewrap is unavailable on this host". This failure is my incomplete
  provisioning, not a Kernel defect. In that run the mission had already completed cognition.solve and
  organ.exchange through the Gate (both DONE with receipts). I deleted run 13's temporary directory before copying
  its ledger, so the run was repeated as 13b: it failed the same way, and its ledger and the extract are kept in
  capture/run13b-ledger/.
- Run 14: the same binary presented at /usr/bin/bwrap inside a private mount namespace (staffing-proof/
  in_private_bwrap_ns.sh: `unshare --mount --propagation private`, then a read-only overlay over /usr/bin). Nothing
  was installed; /usr/bin/bwrap does not exist for any other process on the machine (checked after the run).
  PASSED, 1 test, 77 s. The step map prints all fifteen steps SHOWN, each with its recorded gap.

What step 9 recorded on the signed mission's ledger in run 14 (capture/loop15-step9-signed-mission.txt, extracted
from loop15-evidence/ledger.jsonl and step-map.json):

- mission.action organs / organ.exchange: DONE, route cli, with the binding
  {from_check "answered", field "result", param "seed", value_sha256 sha256:3f3ab27d...} and Gate receipt
  sha256:29e77f059c8d2848b3cb3d940161b0c1010753c2877ecb574b3bedf5db444838;
- organ_heads daleobanks 664ac98c..., wealthmachine 0e80582d...; filesystem_confined true for both;
- WealthMachine's reading: "staffing evidence[1] (unverified report): staffed=8, total_demand=9, shortage=1,
  unfilled={"Dock2": 1}; internal arithmetic agrees only; original demand, capacity and optimality are not verified";
- go_no_go "needs_more_evidence"; recommended_next_action "Validate the reported staffing shortage of 1 units against
  original demand and capacity; resolve unfilled orders {"Dock2": 1} before proceeding";
- requires_human_approval true; appraisal_verdict REPRODUCED; authority_created false; external_effects null;
  spend_usd 0.0; both organ messages retained with may_command False and content_trust "untrusted".

The step map's header says founder_key "per-test Ed25519 key; NOT Alfonso" and counts_toward_vepmc false. The
mission.appraised VERIFIED facts in that ledger are the body's closure appraisal of the mission's own signed checks.
They are not a verification of the staffing report.


SUPPLEMENTARY: THE COMPOSED REHEARSAL SNAPSHOT (outside the assigned steps)
---------------------------------------------------------------------------

Another worker's branch integration-rehearsal-20261111 was at b8d95167eb6a2cd84c77b7fa57c937584dacec7d when read. It
contains pr196, pr290, pr273, pr278 and 7245fa5d (checked with git merge-base --is-ancestor); it does not contain
pr289. The branch was moving (it was at 77f50854 earlier in this session), so a detached snapshot of b8d95167 was
taken in my own worktree (staffing-proof/kernel-rehearsal-snapshot); the other worker's tree was not touched.
greg/organs.py, greg/organ_bridge.py, greg/organ_exchange.py, adapters/ and the three test files named here are
identical to pr196 on that commit (`git diff --name-only pr196 b8d95167 -- <those paths>` is empty); what differs is
the dispatch path the signed mission crosses, which run 17 exercises.

- Run 16: test_organ_staffing_figures.py + test_greg_organs.py: 50 passed, 0 failed, 0 skipped.
- Run 17: test_one_mission_fifteen_steps.py in the private namespace: 1 passed, 98 s; step 9 SHOWN.

This says the organ path and the signed mission's organ step still work on that one commit. It is not a review of
the rehearsal branch and says nothing about a later commit on it.


SIDE EFFECT ON THE SHARED MACHINE: FREE DISK
--------------------------------------------

At the start of this session `df` showed 28 GB available of a 252 GB device (11.1%). At the end: 22,045 MB available
of 258,020 MB (8.5%; logs/disk-state.txt), after I purged the pip download cache my installs had filled. The three
venvs this verification built take 4,151 MB: wealthmachine-venv 2,714 MB (its requirements include tensorflow and
transformers), kernel-venv 1,238 MB, daleobanks-venv 199 MB. Other workers were writing to the same disk meanwhile.

Why it matters: greg/compute.py has DISK_FREE_THRESHOLD = 0.10 over 5 sustained samples. A body that runs long
enough on this machine now records a COMPUTE decision request ("free disk < 10% for 5 samples"). The kept ledgers
of runs 13b and 17 contain one each (run 13's did too, read before its directory was deleted); run 14's contains
none. The request authorizes nothing and its own text says missions continue. Run 17 passed with it present, and
run 20 shows the three known-failure files I checked fail exactly as listed (5 failed, 16 passed), so I saw no
test outcome change. A test that counts every decision request of a long-running body could still be affected; I
did not search for one.

The venvs were kept because the connected proof cannot be re-run without them (the shared kernel venv skips it).
Deleting all three would return about 4.2 GB, which puts free disk at about 10.2%: barely above the threshold.


FINDINGS
--------

1. The Kernel-stated verdict does not differ between 8 of 8 and 4 of 8. In run 3 the receipts read:
     8/8: verdict "needs_more_evidence", verdict_why "unevidenced canonical fields (governing_bottleneck), which caps
          the engine's 'go'", engine_verdict "go"
     4/8: verdict "needs_more_evidence", verdict_why "unevidenced canonical fields (governing_bottleneck); engine
          verdict already no higher", engine_verdict "needs_more_evidence"
   The rule is adapters/daleobanks_opportunity.py justified_verdict: an unresolved governing_bottleneck caps "go" and
   "defer"; the field is taken only from a stated wire field, never inferred. DALEOBANKS's packet states none, also
   when the staffing report inside its evidence names a bottleneck. All five held-out problems show the same
   (kernel-stated "needs_more_evidence" throughout). The test asserts on WealthMachine's go_no_go, which is what its
   docstring claims, so the test is accurate. The consequence is for whoever consumes the receipt: the
   differentiated decision lives in engine_verdict, verdict_why and the retained assessment, not in `verdict`.
   Whether a fully staffed, unverified report should ever reach a Kernel-stated "go" is a policy question; the
   present behaviour is the conservative one.

2. A silent skip in the designated kernel venv. tests/integration/test_organ_staffing_figures.py line 32 is
   `nx = pytest.importorskip("networkx")`. The shared venv has requirements-dev only. There the file is skipped at
   import even with the organs configured and UNIIMENTE_REQUIRE_ORGANS=1 (run 10), and a run that includes any other
   test exits 0 with "1 passed, 1 skipped" (run 11). CI job 8 installs requirements-cognition.txt and reports its
   skip count, so CI is covered. A local run in the shared venv is not: it reports no failure and proves nothing.
   The fifteen-step mission has the same shape (importorskip of networkx, scipy, z3, ortools, and the bubblewrap
   skip in run 12).

3. Arithmetic agreement is the only check on the report. WealthMachine (src/services/staffing_evidence.py at
   0e80582d) checks that a report is internally consistent with what certify_staffing guarantees. It does not see
   the original problem, and of the certificate it checks only that one is present. Run 18 (consistent_lie.py,
   expectation stated in the file before the run) sent a fabricated report for the 4-of-8 problem: 8 of 8 staffed by
   workers who do not exist ("Zed", "Yan"), in certify_staffing's exact shape, produced by no Kernel code.
   WealthMachine returned go_no_go "go", with the reading "staffing evidence[1] (unverified report): staffed=8,
   total_demand=8, shortage=0, unfilled={}; internal arithmetic agrees only; original demand, capacity and optimality
   are not verified". The Kernel-stated verdict stayed "needs_more_evidence" (the cap of finding 1),
   requires_human_approval stayed true and authority_created false. So on this path the governing_bottleneck cap
   keeps a consistent lie from a Kernel-stated "go", and the human approval requirement keeps it from any action;
   no check of the report does. The test's hostile cases (truncated, inconsistent, contradictory, replayed, self-promoting)
   all passed at the pin; none of them is a consistent lie. The fifteen-step test records this same gap in its own
   step map.

4. At #44 the staffing report was also counted as demand evidence. In run 5 the assessment says "opportunity score
   0.726" and "[bear] only 2 evidence item(s)"; at the pin it says 0.696 and "only 1 evidence item(s)". So #45/#47
   changed two things: the report is read, and it no longer raises the opportunity score.

5. Same host, same UID, same code. The two WealthMachine runs that make an appraisal REPRODUCED are two processes of
   the same commit. Each organ signs with its own per-invocation key, and WealthMachine also holds DALEOBANKS's key in
   order to verify (HMAC), which the receipt states under key_holders. None of this is an independent party.


WHAT WAS NOT RUN
----------------

- The Kernel's full suite. Six Kernel test files were run in all: test_organ_staffing_figures.py,
  test_greg_organs.py, test_one_mission_fifteen_steps.py, and in run 20 three of this container's known-failure
  files. The other known failures (test_greg_condition_competence_hooks.py, test_greg_cognition_mission.py,
  test_greg_browser.py) were not re-run.
- The organs' own test suites (DALEOBANKS 387 tests, WealthMachine 126/128 as their pin notes say). Not run.
- CI. Nothing here is a CI result; whether job 8 is green on pr196's head was not checked.
- The other organ-dependent files CI job 8 lists (test_one_machine.py, test_one_machine_ten_steps.py,
  test_combined_construction_outcome.py, test_one_machine_attacks.py, test_greg_organ_exchange.py::test_real_organs,
  test_cross_organ_mission.py and the rest), and scripts/ci/check_organ_verdict_mutants.py.
- The Kernel on Python 3.11 (CI's version). The Kernel ran on 3.13.18; the organs on 3.11.18.
- Any mutation of WealthMachine's reader beyond the three historical commits (#44, #45, #47). WealthMachine's own
  mutant run (docs/evidence/staffing-reader-hardening-2026-10-28/run_mutants.py) was not executed.
- A packet that states governing_bottleneck. Every packet here left it unstated, so the cap of finding 1 applied
  each time; what the Kernel states when the field is present (for a true report or a fabricated one) was not run.
- DALEOBANKS on its old boundary pin (4999acff). Run 19 removed only #96's refinery change; the Kernel's refusal of
  an organ still on the shared-key pin was exercised only by the unit test with a stand-in stage (run 2).
- Anything on the founder's device, with the founder's key, or with a real staffing problem. Every problem here is
  synthetic; every "founder" key is a per-test key.
- A system installation of bubblewrap. The fifteen-step mission ran only inside the private mount namespace
  described above; on this container as it stands it is skipped.


FILES
-----

Everything is under /tmp/claude-0/-home-user/f78643ba-8a14-5107-b25c-e0462dfdc774/scratchpad/staffing-proof/ :

    EVIDENCE.md                      this file
    env.sh                           the environment every run sourced
    capture_assessments.py           run 3 and run 5 (writes what the organs returned; asserts nothing)
    heldout_cases.py                 run 15 (expectations stated in the file before the run)
    consistent_lie.py                run 18 (expectation stated in the file before the run)
    in_private_bwrap_ns.sh           the private mount namespace used by runs 14 and 17
    logs/                            raw output of every run, junit XML, pip logs, pip freeze of the three venvs,
                                     junit-summary.txt, final-state.txt
    capture/capture-pin-dale664ac98-wmi0e80582.{txt,json}                the 8/8 and 4/8 exchange, complete
    capture/capture-failbefore-dale664ac98-wmi7a45d22-pr44.{txt,json}    the same against WealthMachine #44
    capture/heldout-pin-dale664ac98-wmi0e80582.json                      the five held-out problems, complete
    capture/consistent-lie.json                                          the fabricated report and what came back
    capture/run13b-ledger/                                               ledger and extract of the failed PATH-only run
    capture/loop15-step9-signed-mission.txt                              step 9 of the passing signed mission
    loop15-evidence/                 ledger.jsonl, mission.json, step-map.json kept by run 14
    loop15-evidence-rehearsal-snapshot/                                  the same for run 17
    SHA256SUMS                       digests of every file listed above
