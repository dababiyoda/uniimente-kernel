"""Scripted tables for the operation re-admission README, read only from results.json (and the previous operation
verdicts in the evidence index as committed before the run). Usage: make_readme_tables.py RESULTS.json PRIOR_INDEX.json"""
import json, sys
from collections import Counter
res = json.load(open(sys.argv[1])); prior = json.load(open(sys.argv[2]))["operations"]

print(f"- **Source commit:** `{res['source_commit'][:7]}` (pre-registered: {res['pre_registered']}, freeze committed at "
      f"`{res['freeze_commit'][:7]}`); freeze `{res['freeze_sha256'][:23]}...`; {res['platform']}, Python "
      f"{res['python']}; finished {res['finished_at']}.\n")
print("| Family | Candidate | Status | #155 rule | Cand c/w/a | Base wrong | Comp wrong | vs baseline | vs competitor | "
      "mean quality cand / base / comp | ms cand / comp | Smoke |")
print("|---|---|---|---|---|---|---|---|---|---|---|---|")
for f, g in res["families"].items():
    a = g["arms"]; c = a["candidate"]
    vb, vc = g["vs_baseline"], g["vs_competitor"]
    smoke = g["canonical_path"].get("verifier") or g["canonical_path"].get("state")
    print(f"| `{f}` | {g['candidate']} | **{g['status']}** | {g['rule_155_status']} | {c['correct']}/{c['wrong']}/"
          f"{c['abstain']} | {a['baseline']['wrong']} | {a['competitor']['wrong']} | {vb['wins']}-{vb['losses']}-"
          f"{vb['ties']} (p={vb['p_better']:.3g}) | {vc['wins']}-{vc['losses']}-{vc['ties']} (p={vc['p_better']:.3g}) | "
          f"{c['mean_quality']:.4g} / {a['baseline']['mean_quality']:.4g} / {a['competitor']['mean_quality']:.4g} | "
          f"{c['median_seconds']*1000:.3f} / {a['competitor']['median_seconds']*1000:.3f} | {smoke} |")
print("\nArms (#155's, verbatim): baseline / competitor per family:\n")
for f, g in res["families"].items():
    print(f"- `{f}`: baseline {g['baseline']}; competitor {g['competitor']}.")
print("\nAgainst each family's previous verdict (from the evidence index committed before this run):\n")
print("| Family | previous raw status | previous indexed status | previous evidence | this run |")
print("|---|---|---|---|---|")
for f, g in res["families"].items():
    p = prior.get(f) or {}
    print(f"| `{f}` | {p.get('raw_status')} | {p.get('status')} | `{p.get('evidence', '').partition('#')[0]}` | "
          f"{g['status']} |")
refuted = {f: sum(1 for r in g["heldout"] if r["arms"]["candidate"].get("info", {}).get("refuted"))
           for f, g in res["families"].items()}
print("\nRefuted candidate outputs per family:", {f: n for f, n in refuted.items() if n} or "none")
print("Status counts:", dict(Counter(g["status"] for g in res["families"].values())))
