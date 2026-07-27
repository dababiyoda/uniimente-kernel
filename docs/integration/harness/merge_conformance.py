#!/usr/bin/env python3
"""Merge the three runner outputs into DIFFERENTIAL_AUTHORITY_CONFORMANCE.json."""
import json
import pathlib
import collections

W = pathlib.Path("/tmp/claude-0/-home-user/cae04d8c-db77-5252-86ff-7ce47d4772c5/scratchpad/gateB")
OUT = pathlib.Path("/home/user/uniimente-kernel/docs/integration/DIFFERENTIAL_AUTHORITY_CONFORMANCE.json")

rows = []
for f in ("res_main.json", "res_pr21.json", "res_sdk.json"):
    rows += json.loads((W / f).read_text())

# PR21 cases 22/23 were raised as GateRefusal by the runner itself to carry a
# message; they are honestly ABSENT, not refusals earned by the engine.
for r in rows:
    if r["implementation"].startswith("pr21") and r["case_id"] in (22, 23):
        r["verdict"] = "ABSENT"
        r["note"] = "structurally inexpressible in this implementation"

IMPLS = ["main_root_policy_consequence_gate",
         "pr21_build_consequence_gate",
         "phase7_sdk_uniimente_kernel_gate"]
SHORT = {IMPLS[0]: "main", IMPLS[1]: "pr21", IMPLS[2]: "sdk"}

by_case = collections.defaultdict(dict)
name = {}
expect = {}
for r in rows:
    by_case[r["case_id"]][r["implementation"]] = r
    name[r["case_id"]] = r["case"]
    expect[r["case_id"]] = r["doctrinal_expectation"]

# Divergences that are retained with an explicit justification.
JUSTIFIED = {
    21: ("deliberate policy difference",
         "Both main and PR21 PERMIT the effect and RECORD reconciled=false rather than "
         "refusing. This is correct doctrine: at reconciliation the external effect has "
         "already happened, and a gate cannot retroactively refuse it. The obligation is "
         "to record the mismatch, which both do."),
    8:  ("stronger safety, different mechanism",
         "The SDK returns `deduplicated` rather than refusing: an identical fingerprint "
         "resolves to the existing receipt WITHOUT consuming a grant use and WITHOUT "
         "re-running the executor. That is a stronger idempotency guarantee than a bare "
         "refusal, and it is why executor_ran stays at 1."),
    9:  ("stronger safety, different mechanism", "Same dedup path as case 8."),
}

cases = []
for cid in sorted(by_case):
    per = {}
    for impl in IMPLS:
        r = by_case[cid].get(impl)
        per[SHORT[impl]] = None if r is None else {
            "verdict": r["verdict"],
            "refusal_reason": r["refusal_reason"],
            "executor_ran": r["executor_ran"],
            "chain_verifies": r["chain_verifies"],
        }
    verdicts = {k: (v["verdict"] if v else "NOT_RUN") for k, v in per.items()}
    exp = expect[cid]
    # A divergence exists when the engines that CAN express the case disagree.
    expressed = {k: v for k, v in verdicts.items() if v not in ("ABSENT", "NOT_RUN")}
    divergent = len(set(expressed.values())) > 1
    wrong = {k for k, v in expressed.items()
             if (v == "PERMIT") != (exp == "PERMIT")}
    # Case 2 on main: verified separately as a correct ALLOW, not a bypass.
    # evaluate() returns ALLOW for this consequence class, so no approver is
    # required; forcing REQUIRE_HUMAN makes it fail closed (executor_ran=0).
    if cid == 2:
        wrong.discard("main")

    if cid in JUSTIFIED:
        cls, why = JUSTIFIED[cid]
    elif wrong:
        cls = "unexplained_divergence" if divergent else "shared_gap"
        why = ("engine(s) " + ", ".join(sorted(wrong)) +
               " reached the doctrinally wrong verdict")
    elif divergent:
        cls = "coverage_divergence"
        why = "engines that express the case agree; others cannot express it"
    else:
        cls = "equivalent"
        why = "all expressing engines agree with doctrine"

    cases.append({
        "case_id": cid, "case": name[cid], "doctrinal_expectation": exp,
        "results": per, "verdicts": verdicts,
        "divergence_classification": cls, "divergence_note": why,
        "engines_reaching_wrong_verdict": sorted(wrong),
    })

summary = {impl: collections.Counter() for impl in SHORT.values()}
for c in cases:
    for k, v in c["verdicts"].items():
        summary[k][v] += 1

doc = {
    "artifact": "DIFFERENTIAL_AUTHORITY_CONFORMANCE",
    "gate": "Gate A - ACTIVE_CANONICAL_CONSEQUENCE_ENGINES",
    "date": "2026-07-27",
    "method": (
        "One shared 30-case corpus of valid and hostile scenarios, executed against "
        "three authority implementations in three separate git worktrees. Drift is "
        "injected at the SAME pipeline position in each engine: PR21 via its native "
        "stage interceptors at WITNESS, main via a wrapper on signer.sign (which fires "
        "between witness creation and _reauthorize_at_commit). A case an engine cannot "
        "structurally express is recorded ABSENT with the reason; no verdict is fabricated."
    ),
    "implementations": {
        "main": {"id": IMPLS[0], "path": "policy/consequence_gate.py",
                 "ref": "origin/main 8cb3074", "entrypoint": "ConsequenceGate.run()",
                 "signing": "HMAC-SHA256, symmetric; dev key is the literal b'uniimente-dev-witness-key'"},
        "pr21": {"id": IMPLS[1], "path": "kernel/gate/pipeline.py",
                 "ref": "origin/build/consequence-gate 5b70e24",
                 "entrypoint": "Gate.run() - 15 stages",
                 "signing": "Ed25519 asymmetric, fail-closed verify",
                 "undeclared_dependencies": ["pydantic", "cryptography", "cffi"]},
        "sdk": {"id": IMPLS[2], "path": "sdk-python/uniimente_kernel/gate.py",
                "ref": "origin/phase7/fast-capability-evolution 640ec9d",
                "entrypoint": "ConsequenceGate.execute()",
                "signing": "none; receipts are unsigned in-process objects"},
    },
    "summary_by_implementation": {k: dict(v) for k, v in summary.items()},
    "headline": {
        "genuine_refusals_earned": {
            k: sum(1 for c in cases
                   if c["verdicts"][k] == "REFUSE") for k in SHORT.values()},
        "doctrinally_wrong_verdicts": {
            k: sorted(c["case_id"] for c in cases if k in c["engines_reaching_wrong_verdict"])
            for k in SHORT.values()},
        "cases_inexpressible": {
            k: sorted(c["case_id"] for c in cases if c["verdicts"][k] == "ABSENT")
            for k in SHORT.values()},
    },
    "verified_defects": [
        {"engine": "main", "case_id": 26,
         "finding": "an actor whose passport declares only ['draft.publish'] executed "
                    "requested_capability='funds.transfer' and reached state='recorded'",
         "verification": "verify_main_holes.py, executed directly, not via the harness",
         "root_cause": "no check binds requested_capability to the passport's declared_capabilities"},
        {"engine": "main", "case_id": 27,
         "finding": "consequence_class escalated from 'external_contact' to 'irreversible' "
                    "inside the commit window; the action still reached state='recorded'",
         "verification": "verify_main_holes.py",
         "root_cause": "_reauthorize_at_commit refuses only on Verdict.DENY. A commit-time "
                        "re-evaluation returning REQUIRE_HUMAN is discarded, so escalating "
                        "into a class that mandates a human bypasses the human."},
        {"engine": "main", "case_id": 28,
         "finding": "a grant issued to actor A was redeemed by actor B and reached state='recorded'",
         "verification": "verify_main_holes.py",
         "root_cause": "bound_effect_hash = sha256({payload, target, action_class}). It omits "
                        "the grantee, so nothing ties a grant to the actor it was issued to."},
        {"engine": "sdk", "case_id": 23,
         "finding": "the gate executed with the KillSwitch disarmed",
         "verification": "grep of commit_witness.py: kill_switch is referenced only at "
                         "line 233-234, where it is SET on postcondition failure",
         "root_cause": "CommitWitness writes to the KillSwitch but never reads .armed to "
                        "block execution. The switch is a one-way failure signal, not a veto."},
    ],
    "verified_non_defects": [
        {"engine": "main", "case_id": 2,
         "finding": "main PERMITs with approver=None, but this is not a bypass",
         "verification": "evaluate() returns Verdict.ALLOW for external_contact at 0.9 "
                         "evidence confidence, so no approver is required. Re-run with "
                         "consequence_class='irreversible' returns REQUIRE_HUMAN and the "
                         "gate reaches state='expired' with executor_ran=0. Fails closed."},
    ],
    "shared_gaps": [
        {"case_id": 25, "engines": ["main", "pr21"],
         "finding": "neither validates the target against any allowlist; the SDK does, via "
                    "named_targets, and is the only engine that refuses this case"},
        {"case_id": 26, "engines": ["main", "pr21"],
         "finding": "neither validates the capability against a registry; the SDK does, via "
                    "permitted_actions, and is the only engine that refuses this case. On "
                    "main this is additionally a verified defect (see verified_defects)."},
    ],
    "cases": cases,
}

OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(doc, indent=2) + "\n")
print(f"wrote {OUT}")
for k, v in doc["headline"]["genuine_refusals_earned"].items():
    print(f"  {k:<5} refusals={v:<3} wrong={doc['headline']['doctrinally_wrong_verdicts'][k]} "
          f"absent={len(doc['headline']['cases_inexpressible'][k])}")
