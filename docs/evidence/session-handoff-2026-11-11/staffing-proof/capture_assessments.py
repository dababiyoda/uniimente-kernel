"""Capture what the real organs return for GREG's 8/8 and 4/8 certified staffing answers.

Verification instrument, kept outside every repository. It drives the same path as the Kernel's
tests/integration/test_organ_staffing_figures.py (the test module's own ``certified``, ``seed_for`` and ``run``
helpers, hence ``greg.organs.exchange``) and writes down what came back instead of asserting on it, so the same
script records a pass and a fail-before control alike.

Usage (cwd = the Kernel worktree, PYTHONPATH = the Kernel worktree, the four UNIIMENTE_* organ variables set):
    python capture_assessments.py <output-dir> <label>
"""
from __future__ import annotations

import difflib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

from events.spine import EventSpine
from greg import organs
from greg.journal import Journal
from provenance.ledger import EvidenceLedger
import tests.integration.test_organ_staffing_figures as t
from tests.unit.test_greg_organs import live_organs

OUT = Path(sys.argv[1])
LABEL = sys.argv[2]
OUT.mkdir(parents=True, exist_ok=True)
VOLATILE = ("id", "created_at", "opportunity_packet_id")          # differ on every run by construction
SHOWN = ("go_no_go", "reasons", "validation_plan", "recommended_next_action", "requires_human_approval")
SCORES = ("opportunity_score", "market_alignment", "risk_level", "legal_readiness", "expected_roi",
          "pricing_hypothesis")


def head(path: str) -> str:
    return subprocess.run(["git", "-C", path, "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()


def main() -> int:
    params = live_organs()
    work = Path(tempfile.mkdtemp(prefix=f"capture-{LABEL}-", dir=OUT))
    journal = Journal(EventSpine(EvidenceLedger("sha256:" + "1" * 64, path=str(work / "l.jsonl"))),
                      actor="spiffe://uniimente.internal/test/organs")
    answers = {"full_8_of_8": t.certified(t.FULL), "short_4_of_8": t.certified(t.SHORT)}
    record = {"label": LABEL, "kernel_head": head(os.getcwd()),
              "organ_roots": {"daleobanks": params["daleobanks_root"], "wealthmachine": params["wealthmachine_root"]},
              "organ_heads_git": {"daleobanks": head(params["daleobanks_root"]),
                                  "wealthmachine": head(params["wealthmachine_root"])},
              "interpreters": {"kernel": sys.executable, "daleobanks": params["daleobanks_python"],
                               "wealthmachine": params["wealthmachine_python"]},
              "cases": {}}
    for name, answer in answers.items():
        seed = t.seed_for(answer)
        out, packet, wmi = t.run(work / name, journal, params, seed, f"m:capture-{name}")
        record["cases"][name] = {"certified_answer": answer, "seed": seed, "exchange_receipt": out,
                                 "daleobanks_packet": packet, "wealthmachine_assessment": wmi}

    observed = [e.payload for e in journal.replay("organ.observed")]
    appraised = [e.payload for e in journal.replay("organ.appraised")]
    record["journal"] = {
        "organ_observed": observed, "organ_appraised": appraised,
        "event_type_counts": {kind: sum(1 for e in journal.replay("") if e.type == kind)
                              for kind in sorted({e.type for e in journal.replay("")})},
        "mission_appraised": len(journal.replay("mission.appraised")),
        "mission_achieved": len(journal.replay("mission.achieved")),
        "mission_observed": len(journal.replay("mission.observed")),
    }

    full, short = (record["cases"][k] for k in ("full_8_of_8", "short_4_of_8"))
    wf, ws = full["wealthmachine_assessment"], short["wealthmachine_assessment"]
    pf, ps = full["daleobanks_packet"], short["daleobanks_packet"]
    readings = {k: [r for r in w["reasons"] if r.startswith("staffing evidence[")]
                for k, w in (("full_8_of_8", wf), ("short_4_of_8", ws))}
    record["comparison"] = {
        "assessment_fields_that_differ": sorted(k for k in set(wf) | set(ws)
                                                if k not in VOLATILE and wf.get(k) != ws.get(k)),
        "assessment_fields_identical": sorted(k for k in set(wf) | set(ws)
                                              if k not in VOLATILE and wf.get(k) == ws.get(k)),
        "packet_fields_that_differ": sorted(k for k in set(pf) | set(ps) if pf.get(k) != ps.get(k)),
        "packet_evidence_counts": {"full_8_of_8": len(pf["evidence"]), "short_4_of_8": len(ps["evidence"])},
        "engine_scores_identical": all(wf.get(k) == ws.get(k) for k in SCORES),
        "verdicts": {"full_8_of_8": wf["go_no_go"], "short_4_of_8": ws["go_no_go"]},
        "staffing_readings": readings,
    }
    record["not_treated_as_verified"] = {
        "requires_human_approval_in_both_assessments": wf["requires_human_approval"] is True
                                                        and ws["requires_human_approval"] is True,
        "requires_human_approval_in_both_receipts": all(
            c["exchange_receipt"]["assessment"]["requires_human_approval"] is True for c in (full, short)),
        "every_reading_says_unverified_report": bool(readings["full_8_of_8"]) and bool(readings["short_4_of_8"])
                                                and all("unverified report" in r for rs in readings.values()
                                                        for r in rs),
        "every_reading_says_not_verified": bool(readings["full_8_of_8"]) and bool(readings["short_4_of_8"])
                                           and all("not verified" in r for rs in readings.values() for r in rs),
        "every_retained_organ_message_content_trust": sorted({o.get("content_trust") for o in observed}),
        "organ_appraisal_verdicts": sorted({a["verdict"] for a in appraised}),
        "organ_appraisal_tiers": sorted({a["tier"] for a in appraised}),
        "authority_created_in_any_receipt": any(c["exchange_receipt"]["authority_created"] for c in (full, short)),
        "external_effects_in_receipts": [c["exchange_receipt"]["external_effects"] for c in (full, short)],
        "spend_usd_in_receipts": [c["exchange_receipt"]["spend_usd"] for c in (full, short)],
        "mission_appraised_or_achieved_events": record["journal"]["mission_appraised"]
                                                + record["journal"]["mission_achieved"],
        "phrases_absent_from_both_assessments": {
            phrase: all(phrase not in json.dumps(w).lower() for w in (wf, ws))
            for phrase in ("verified optimal", "certified plan verified", "externally verified",
                           "independently accepted")},
    }
    (OUT / f"capture-{LABEL}.json").write_text(json.dumps(record, indent=1, sort_keys=True, ensure_ascii=False))

    lines = [f"CAPTURE {LABEL}",
             f"kernel HEAD        {record['kernel_head']}",
             f"DALEOBANKS HEAD    {record['organ_heads_git']['daleobanks']}",
             f"WealthMachine HEAD {record['organ_heads_git']['wealthmachine']}", ""]
    for name, case in record["cases"].items():
        a, r, w, p = (case[k] for k in ("certified_answer", "exchange_receipt", "wealthmachine_assessment",
                                        "daleobanks_packet"))
        lines += [f"=== {name}: GREG certified staffed={a['staffed']} total_demand={a['total_demand']} "
                  f"shortage={a['shortage']} unfilled={json.dumps(a.get('unfilled'), sort_keys=True)}",
                  f"exchange: appraisal_verdict={r['appraisal_verdict']} transport_verified={r['transport_verified']} "
                  f"sender_identity_isolated={r['sender_identity_isolated']} authority_created={r['authority_created']} "
                  f"external_effects={r['external_effects']} spend_usd={r['spend_usd']}",
                  f"organ code that ran: " + json.dumps({o: {"head": c["head"], "tree_sha256": c["tree_sha256"],
                                                             "filesystem_confined": c["filesystem_confined"],
                                                             "uncommitted_changes_ignored":
                                                                 c["uncommitted_changes_ignored"]}
                                                         for o, c in r["organ_code"].items()}, sort_keys=True),
                  f"kernel-stated verdict={r['verdict']!r} (why: {r['verdict_why']!r}); engine_verdict="
                  f"{r['engine_verdict']!r}",
                  f"DALEOBANKS packet evidence ({len(p['evidence'])} items):"]
        lines += [f"  [{i}] {e}" for i, e in enumerate(p["evidence"])]
        lines += ["WealthMachine assessment (verbatim fields):"]
        for field in SHOWN:
            lines.append(f"  {field} = {json.dumps(w[field], indent=2, ensure_ascii=False)}")
        for field in SCORES:
            lines.append(f"  {field} = {json.dumps(w[field], ensure_ascii=False)}")
        lines.append("")
    strip = lambda w: json.dumps({k: v for k, v in w.items() if k not in VOLATILE}, indent=1, sort_keys=True,   # noqa: E731
                                 ensure_ascii=False).splitlines()
    diff = list(difflib.unified_diff(strip(wf), strip(ws), "assessment for 8/8", "assessment for 4/8", lineterm="",
                                     n=1))
    lines += ["=== unified diff of the two assessments (ids and created_at removed)"] + (diff or ["(no difference)"])
    lines += ["", "=== comparison", json.dumps(record["comparison"], indent=1, sort_keys=True, ensure_ascii=False),
              "", "=== not treated as verified", json.dumps(record["not_treated_as_verified"], indent=1,
                                                            sort_keys=True, ensure_ascii=False)]
    text = "\n".join(lines) + "\n"
    (OUT / f"capture-{LABEL}.txt").write_text(text)
    sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
