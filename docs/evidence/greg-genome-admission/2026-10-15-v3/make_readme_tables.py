"""Scripted tables for an admission README, read only from results.json (and the previous verdicts in the index
as committed before the run). Usage: make_readme_tables.py RESULTS.json PRIOR_INDEX.json"""
import json, sys
res = json.load(open(sys.argv[1])); prior = json.load(open(sys.argv[2]))["genomes"]

def pair(c):
    return f"{c['wins']}-{c['losses']}" + (f" (p={c['p_better']:.3g})" if "p_better" in c else "")

print(f"- **Source commit:** `{res['source_commit'][:7]}`; freeze `{res['freeze_sha256'][:23]}...`; {res['platform']}, "
      f"Python {res['python']}; finished {res['finished_at']}.\n")
print("| Layer | Genome | Version | Status | Cand c/w/a | Base wrong | Comp wrong | vs baseline | vs competitor | ms cand / comp | Smoke |")
print("|---|---|---|---|---|---|---|---|---|---|---|")
for f, g in sorted(res["genomes"].items(), key=lambda kv: (kv[1]["layer"], kv[0])):
    a = g["arms"]; c = a["candidate"]
    vb, vc = g["vs_baseline"], g["vs_competitor"]
    smoke = g["canonical_path"].get("verifier") or g["canonical_path"].get("state") or g["canonical_path"].get("abstention_state")
    print(f"| L{g['layer']} | `{f}` | {g['version']} | **{g['status']}** | {c['correct']}/{c['wrong']}/{c['abstain']} | "
          f"{a['baseline']['wrong']} | {a['competitor']['wrong']} | {vb['wins']}-{vb['losses']} (p={vb['p_better']:.3g}) | "
          f"{vc['wins']}-{vc['losses']} (p_worse={vc['p_worse']:.3g}) | {c['median_seconds']*1000:.2f} / "
          f"{a['competitor']['median_seconds']*1000:.2f} | {smoke} |")
print("\nAgainst each genome's previous verdict (from the evidence index committed before this run):\n")
print("| Genome | previous version | previous status | previous evidence | v3 version | v3 status |")
print("|---|---|---|---|---|---|")
for f, g in sorted(res["genomes"].items()):
    p = prior.get(f)
    if p:
        print(f"| `{f}` | {p.get('version')} | {p.get('status')} | `{p.get('evidence','').split('/')[-2]}` | {g['version']} | {g['status']} |")
    else:
        print(f"| `{f}` | - | no verdict | - | {g['version']} | {g['status']} |")
print("\nNative subregions against the competitor (reported in receipts, never a status):\n")
print("| Genome | Subregion | n | wins-losses-ties | p_better | p_worse |\n|---|---|---:|---|---:|---:|")
for f, g in sorted(res["genomes"].items()):
    for name, s in sorted((g.get("subregions") or {}).items()):
        v = s["vs_competitor"]
        print(f"| `{f}` | {name} | {s['n']} | {v['wins']}-{v['losses']}-{v['ties']} | {v['p_better']:.3g} | {v['p_worse']:.3g} |")
refuted = {f: sum(1 for r in g["heldout"] if r["arms"]["candidate"].get("info", {}).get("refuted")) for f, g in res["genomes"].items()}
print("\nRefuted candidate outputs per genome:", {f: n for f, n in sorted(refuted.items()) if n} or "none")
from collections import Counter
print("Status counts:", dict(Counter(g["status"] for g in res["genomes"].values())))
