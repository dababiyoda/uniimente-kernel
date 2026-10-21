"""Write an admission run's README table from its committed results.json (nothing is re-run).

    PYTHONPATH=. python scripts/admission_readme.py docs/evidence/greg-genome-admission/<run-id>
prints the generated section; the human-written reading below it is kept in the README by hand.
"""
from __future__ import annotations

import json
from pathlib import Path
import sys


def _wlt(x: dict) -> str:
    return f"{x['wins']}-{x['losses']}-{x['ties']}"


def table(results: dict) -> str:
    rows = ["| Family | Layer | Version | Status | Candidate correct/wrong/abstain | vs baseline W-L-T (p better) "
            "| vs competitor W-L-T (p better / p worse) | Median s (candidate / baseline / competitor) "
            "| Canonical path |",
            "|---|---|---|---|---|---|---|---|---|"]
    for family, g in sorted(results["genomes"].items()):
        a = g["arms"]
        c, b, k = a["candidate"], a["baseline"], a["competitor"]
        vb, vc = g["vs_baseline"], g["vs_competitor"]
        path = g.get("canonical_path", {})
        rows.append(f"| `{family}` | {g['layer']} | {g['version']} | **{g['status']}** | "
                    f"{c['correct']}/{c['wrong']}/{c['abstain']} | {_wlt(vb)} ({vb['p_better']}) | "
                    f"{_wlt(vc)} ({vc['p_better']} / {vc['p_worse']}) | "
                    f"{c['median_seconds']} / {b['median_seconds']} / {k['median_seconds']} | "
                    f"{path.get('verifier', 'n/a')} |")
    return "\n".join(rows)


def main(argv=None):
    run = Path((argv or sys.argv[1:])[0])
    results = json.loads((run / "results.json").read_text())
    load = results["host_load"]
    print(f"- **Run:** source commit `{results['source_commit'][:8]}`, source dirty {results['source_dirty']}, "
          f"freeze `{results["freeze_sha256"][:23]}…`, finished {results['finished_at']}.")
    print(f"- **Host load:** start {load['start']['loadavg']}, end {load['end']['loadavg']} (diagnostic only).")
    print()
    print(table(results))
    for family, g in sorted(results["genomes"].items()):
        if g.get("subregions"):
            parts = "; ".join(f"{name} (n={s['n']}): vs baseline {_wlt(s['vs_baseline'])}, vs competitor "
                              f"{_wlt(s['vs_competitor'])}" for name, s in sorted(g["subregions"].items()))
            print(f"\n`{family}` by subregion: {parts}.")


if __name__ == "__main__":
    main()
