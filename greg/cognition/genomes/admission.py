"""Admission harness: a method earns a place in the repertoire by native competence (directive section 15).

    native problem family -> simple baseline -> candidate -> strongest reasonable competitor
      -> held-out evaluation -> cost/latency normalisation -> falsification -> admission outcome

Protocol (frozen by ``--freeze`` before any held-out instance runs; ``--run`` refuses changed code):

* Development seeds ``DEV_SEEDS`` are for builders (``--dev``). Held-out seeds ``HELDOUT_SEEDS`` are run
  once, by this harness, for every genome in the freeze.
* Every arm (candidate ``solve``, ``baseline``, ``competitor``) runs every held-out instance in-process
  with wall-clock timing; the candidate's output is also passed through the genome's independent
  ``verify``, and a refuted candidate output is scored ``wrong`` (a false answer) with a quality one unit
  below abstaining, so it can never win a comparison.
* Quality is the genome's native score (higher is better); differences at or below the genome's
  tolerance are ties. Paired one-sided exact sign tests compare candidate with each other arm.
* One canonical-path smoke run per genome sends a held-out instance through
  ``greg.cognition.cortex.reason`` (isolated worker, verifier, CognitiveReceipt) with the family attached
  in an evaluation-only registry view - the same founder-pin mechanism P4 used; no body is changed.

Admission rule (``RULE``; recorded in every evidence file):
  COMPOSITION_ONLY  the genome declares no standalone decision (intermediate representation only);
  REJECTED          more wrong answers than the baseline, or significantly worse than the baseline;
  EXPERIMENTAL      no demonstrated edge over the simple baseline (quality not significantly better
                    and not an equal-quality, >=1.25x cheaper answer);
  SUPERSEDED        the competitor is significantly better and the candidate wins no instance, or the
                    two tie on every instance and the competitor is >=1.25x cheaper;
  NICHE_CAPABILITY  beats the baseline but is significantly worse than the competitor while winning
                    some instances, or adds wrong answers relative to the competitor, or ties the
                    competitor on quality while costing >=1.25x more;
  DEFAULT_FOR_GEOMETRY beats the baseline and is not significantly worse than the competitor, with no more
                    wrong answers and either significantly better quality or no worse than 1.25x the
                    competitor's median latency.
Latency is wall-clock in this container; the rule uses medians so one slow run cannot flip it.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import platform
import statistics
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from greg.cognition.genomes import library  # noqa: E402
from greg.cognition.genomes.contract import CATEGORIES, GenomeError  # noqa: E402

DEV_SEEDS = tuple(range(0, 10))
HELDOUT_SEEDS = tuple(range(1000, 1030))
COST_RATIO = 1.25
ALPHA = 0.05
RULE = ("COMPOSITION_ONLY if no standalone decision; REJECTED if more wrong than baseline or significantly worse "
        "than baseline; EXPERIMENTAL if no significant edge over baseline (nor equal quality at >=1.25x lower "
        "median latency); SUPERSEDED if competitor significantly better and candidate wins none, or all ties and "
        "competitor >=1.25x cheaper; NICHE_CAPABILITY if beats baseline but significantly worse than competitor "
        "with some wins, or more wrong than competitor, or ties competitor at >=1.25x cost; DEFAULT_FOR_GEOMETRY "
        "if beats baseline, not significantly worse than competitor, no more wrong, and significantly better or "
        "<=1.25x competitor median latency. One-sided exact sign tests, alpha 0.05, 30 held-out seeds.")
EVIDENCE = ROOT / "docs" / "evidence" / "greg-genome-admission"


def sign_test(wins: int, losses: int) -> float:
    n = wins + losses
    return 1.0 if n == 0 else sum(math.comb(n, k) for k in range(wins, n + 1)) / 2 ** n


def _candidate(item, data):
    started = time.perf_counter()
    try:
        out = item.solve(data, {"latency_s": 5.0, "compute": 100000})
    except (GenomeError, ValueError, TypeError, KeyError, ZeroDivisionError) as exc:
        return None, time.perf_counter() - started, {"error": f"{type(exc).__name__}: {str(exc)[:200]}"}
    seconds = time.perf_counter() - started
    if out["status"] != "ANSWER":
        return None, seconds, {"status": out["status"], "missing": out["missing"]}
    try:
        checks = item.verify(data, out["output"], out["certificate"])
    except Exception as exc:          # a verifier crash is a failed check, never a pass
        checks = {"verifier_error": False, "detail": f"{type(exc).__name__}"}
    refuted = not all(bool(v) for k, v in checks.items() if k != "detail")
    return out["output"], seconds, {"refuted": refuted, "checks": {k: bool(v) for k, v in checks.items()
                                                                     if k != "detail"}}


def _arm(fn, data):
    started = time.perf_counter()
    try:
        out = fn(data)
    except (GenomeError, ValueError, TypeError, KeyError, ZeroDivisionError) as exc:
        return None, time.perf_counter() - started, {"error": f"{type(exc).__name__}: {str(exc)[:200]}"}
    return out, time.perf_counter() - started, {}


def evaluate(item, seeds) -> list[dict]:
    rows = []
    for seed in seeds:
        data, truth = item.instance(seed)
        row = {"seed": seed, "subregion": item.subregion(data) if item.subregion else None, "arms": {}}
        for arm in ("candidate", "baseline", "competitor"):
            if arm == "candidate":
                out, seconds, info = _candidate(item, data)
            else:
                out, seconds, info = _arm(getattr(item, arm), data)
            s = item.score(data, truth, out)
            if s["category"] not in CATEGORIES:
                raise GenomeError(f"{item.genome.intelligence_id}: score category {s['category']!r}")
            if info.get("refuted"):
                # A refuted answer is a false answer: strictly worse than abstaining, never a win.
                s = {"quality": float(item.score(data, truth, None)["quality"]) - 1.0, "category": "wrong"}
            row["arms"][arm] = {"quality": float(s["quality"]), "category": s["category"],
                                "seconds": round(seconds, 6), **({"refuted": True} if info.get("refuted") else {}),
                                **({"info": info} if info else {})}
        rows.append(row)
    return rows


def compare(rows, a, b, tol) -> dict:
    wins = sum(1 for r in rows if r["arms"][a]["quality"] > r["arms"][b]["quality"] + tol)
    losses = sum(1 for r in rows if r["arms"][b]["quality"] > r["arms"][a]["quality"] + tol)
    return {"wins": wins, "losses": losses, "ties": len(rows) - wins - losses,
            "p_better": round(sign_test(wins, losses), 6), "p_worse": round(sign_test(losses, wins), 6)}


def decide(item, rows) -> tuple[str, dict]:
    tol = item.tolerance
    stats = {}
    for arm in ("candidate", "baseline", "competitor"):
        cats = [r["arms"][arm]["category"] for r in rows]
        stats[arm] = {**{c: cats.count(c) for c in CATEGORIES},
                      "mean_quality": round(statistics.fmean(r["arms"][arm]["quality"] for r in rows), 6),
                      "median_seconds": round(statistics.median(r["arms"][arm]["seconds"] for r in rows), 6)}
    vb, vk = compare(rows, "candidate", "baseline", tol), compare(rows, "candidate", "competitor", tol)
    c, b, k = stats["candidate"], stats["baseline"], stats["competitor"]
    lat_c, lat_b, lat_k = c["median_seconds"], b["median_seconds"], k["median_seconds"]
    cheaper_than_baseline = vb["wins"] == vb["losses"] == 0 and lat_c * COST_RATIO <= lat_b
    beats_baseline = vb["p_better"] < ALPHA or cheaper_than_baseline
    if not item.genome.standalone_decision:
        status = "COMPOSITION_ONLY"
    elif c["wrong"] > b["wrong"] or vb["p_worse"] < ALPHA:
        status = "REJECTED"
    elif not beats_baseline:
        status = "EXPERIMENTAL"
    elif vk["p_worse"] < ALPHA:
        status = "NICHE_CAPABILITY" if vk["wins"] > 0 else "SUPERSEDED"
    elif vk["wins"] == vk["losses"] == 0 and lat_k * COST_RATIO <= lat_c:
        status = "SUPERSEDED"
    elif c["wrong"] > k["wrong"]:
        status = "NICHE_CAPABILITY"
    elif vk["p_better"] < ALPHA or lat_c <= lat_k * COST_RATIO:
        status = "DEFAULT_FOR_GEOMETRY"
    else:
        status = "NICHE_CAPABILITY"
    subregions = {}
    if item.subregion:
        for name in sorted({r["subregion"] for r in rows}):
            sub = [r for r in rows if r["subregion"] == name]
            subregions[name] = {"n": len(sub), "vs_baseline": compare(sub, "candidate", "baseline", tol),
                                "vs_competitor": compare(sub, "candidate", "competitor", tol)}
    return status, {"arms": stats, "vs_baseline": vb, "vs_competitor": vk, "subregions": subregions}


def _sha(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _module_file(family: str) -> Path:
    item = library.executables()[family]
    module = sys.modules[item.solve.__module__]
    return Path(module.__file__)


def inputs(families) -> dict:
    files = {str(_module_file(f).relative_to(ROOT)) for f in families}
    files |= {str((HERE / n).relative_to(ROOT)) for n in ("contract.py", "admission.py", "library.py")}
    return {"rule": RULE, "dev_seeds": list(DEV_SEEDS), "heldout_seeds": list(HELDOUT_SEEDS),
            "families": sorted(families), "code": {p: _sha(ROOT / p) for p in sorted(files)}}


def smoke(family: str) -> dict:
    """One held-out instance through GREG's canonical cognition path, family attached for evaluation only."""
    from greg.cognition.cortex import reason, registry_view
    item = library.executables()[family]
    data, _ = item.instance(HELDOUT_SEEDS[0])
    registry = registry_view()
    cid = f"cognition.{family}"
    if cid not in registry.manifests:
        return {"state": "NOT_REGISTERED", "capability": cid}
    registry.set_state(cid, "ATTACHED")
    receipt = reason({"problem_id": f"admission:{family}", "operation": item.genome.operation, "data": data,
                      "geometry": {"latency_limit": 30}}, registry=registry)
    return {"capability": cid, "abstention_state": receipt["abstention_state"], "method": receipt["method"],
            "verifier": receipt["evaluator_result"].get("verdict"), "proof_type": receipt["proof_type"],
            "latency_s": round(receipt["latency"], 4), "authority_created": receipt["authority_created"],
            "receipt_id": receipt["receipt_id"]}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--dev", metavar="FAMILY", help="run development seeds for one family (builders)")
    ap.add_argument("--freeze", metavar="RUN_ID", help="freeze code and protocol for every library family")
    ap.add_argument("--run", metavar="RUN_ID", help="run the frozen held-out admission")
    ap.add_argument("--only", nargs="*", help="restrict --freeze to these families")
    args = ap.parse_args(argv)
    families = sorted(library.executables())
    if args.dev:
        item = library.executables()[args.dev]
        rows = evaluate(item, DEV_SEEDS)
        status, detail = decide(item, rows)
        print(json.dumps({"family": args.dev, "partition": "dev", "status_if_heldout_matched": status,
                          **detail}, indent=1))
        return
    if args.freeze:
        target = EVIDENCE / args.freeze
        manifest = target / "freeze.json"
        if manifest.exists():
            raise SystemExit("refusing to overwrite an existing admission freeze; use a new run id")
        target.mkdir(parents=True, exist_ok=True)
        chosen = sorted(args.only) if args.only else families
        manifest.write_text(json.dumps({"frozen_at": datetime.now(timezone.utc).isoformat(),
                                        "inputs": inputs(chosen)}, indent=2) + "\n")
        print(manifest)
        return
    if not args.run:
        raise SystemExit("--dev, --freeze or --run required")
    target = EVIDENCE / args.run
    frozen = json.loads((target / "freeze.json").read_text())
    chosen = frozen["inputs"]["families"]
    if frozen["inputs"] != inputs(chosen):
        raise SystemExit("FROZEN_INPUT_CHANGED: admission results cannot be reported")
    if (target / "results.json").exists():
        raise SystemExit("refusing to overwrite admission results")
    report = {"schema": "greg-genome-admission/1", "freeze_sha256": _sha(target / "freeze.json"),
              "source_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
              "platform": platform.platform(), "python": sys.version.split()[0], "rule": RULE, "genomes": {}}
    for family in chosen:
        item = library.executables()[family]
        rows = evaluate(item, HELDOUT_SEEDS)
        status, detail = decide(item, rows)
        try:
            canonical = smoke(family)
        except Exception as exc:       # recorded, never hidden; a failing smoke blocks DEFAULT below
            canonical = {"state": "SMOKE_FAILED", "error": f"{type(exc).__name__}: {str(exc)[:300]}"}
        if canonical.get("verifier") not in ("STRUCTURALLY_VERIFIED", None) or canonical.get("state") == "SMOKE_FAILED":
            status = {"DEFAULT_FOR_GEOMETRY": "NICHE_CAPABILITY"}.get(status, status)
        report["genomes"][family] = {"intelligence_id": item.genome.intelligence_id, "layer": item.genome.layer,
                                     "version": item.genome.version, "baseline": item.genome.baseline,
                                     "competitor": item.genome.competitor, "status": status, **detail,
                                     "canonical_path": canonical, "heldout": rows}
        print(json.dumps({"family": family, "status": status, "vs_baseline": detail["vs_baseline"],
                          "vs_competitor": detail["vs_competitor"]}), flush=True)
    report["finished_at"] = datetime.now(timezone.utc).isoformat()
    (target / "results.json").write_text(json.dumps(report, indent=1) + "\n")
    print(json.dumps({f: g["status"] for f, g in report["genomes"].items()}, indent=1))


if __name__ == "__main__":
    main()
