"""Frozen cross-geometry comparison runner (directive section 15).

    python -m cortex.evaluation.crossgeo --partition dev --out dev.json          # development, no freeze
    python -m cortex.evaluation.crossgeo --partition selection --out sel.json    # selection, no freeze
    python -m cortex.evaluation.crossgeo --freeze --planning sel.json            # freeze + sample-size plan
    python -m cortex.evaluation.crossgeo --partition heldout --out results.json  # refused unless frozen

The held-out and adversarial partitions run fully automated, with no human input during the
run, and are refused unless every frozen input still hashes to the manifest: suites, loss,
arms, adapters, runner, router and organ code, GREG bridge and worker, and the decision rule.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path

from ..contracts import CORTEX_VERSION
from . import crossgeo_arms as A
from . import crossgeo_loss as L
from .generators import expand

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
# v0.3 is the next bounded test after the v0.2 GAIN_ABSENT result: development and selection are the
# v0.2 splits unchanged; held-out and adversarial are fresh samples. v0.2 freeze and results are kept.
SUITE_VERSION = "0.3"
SUITES = {"dev": HERE / "suites" / "crossgeo-dev-v0.2.json",
          "selection": HERE / "suites" / "crossgeo-selection-v0.2.json",
          "heldout": HERE / "suites" / f"crossgeo-heldout-v{SUITE_VERSION}.json",
          "adversarial": HERE / "suites" / f"crossgeo-adversarial-v{SUITE_VERSION}.json"}
MANIFEST = HERE / f"freeze-crossgeo-v{SUITE_VERSION}.json"
FROZEN_CODE = ["cortex/evaluation/crossgeo.py", "cortex/evaluation/crossgeo_arms.py",
               "cortex/evaluation/crossgeo_loss.py", "cortex/evaluation/crossgeo_suite.py",
               "cortex/evaluation/build_suites.py", "cortex/evaluation/generators.py", "cortex/evaluation/arms.py",
               "cortex/routing.py", "cortex/gates.py", "cortex/genome.py", "cortex/contracts.py", "cortex/outcomes.py",
               "cortex/organs/formal.py", "cortex/organs/formal_eval.py", "cortex/organs/cpsat.py",
               "cortex/organs/estimation.py", "cortex/organs/evidence_causal.py", "cortex/organs/semantic.py",
               "cortex/organs/adversarial.py", "cortex/organs/deterrence.py", "cortex/organs/schedule_extraction.py",
               "cortex/organs/formed.py", "cortex/organs/graphsearch.py", "cortex/organs/continuous.py",
               "greg/cognition/bridge.py", "greg/cognition/worker.py", "greg/cognition/cortex.py",
               "greg/cognition/catalog.py", "greg/cognition/contracts.py", "greg/cognition/solvers.py",
               "greg/cognition/verification.py", "greg/cognition/settlement.py"]
ARMS = ("routed_greg", "existing_greg", "static_router", "always_llm", "tool_llm", "always_abstain")
REPORTED = ("heldout", "adversarial")


def _sha(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def freeze_inputs() -> dict:
    return {"suites": {k: _sha(v) for k, v in SUITES.items()},
            "code": {p: _sha(ROOT / p) for p in FROZEN_CODE},
            "loss_version": L.LOSS_VERSION, "weights": L.WEIGHTS, "decision": L.DECISION,
            "declared_baselines": list(L.DECLARED_BASELINES), "routed": L.ROUTED, "cortex_version": CORTEX_VERSION,
            "partitions": {"development": ["dev"], "selection": ["selection"], "reported": list(REPORTED)},
            "permitted_exclusions": "none: every item in a reported partition is scored",
            "stopping": "one pass over every item; no early stopping"}


def load(partition: str) -> list[dict]:
    data = json.loads(SUITES[partition].read_text(encoding="utf-8"))
    items = []
    for it in data["items"]:
        it = copy.deepcopy(it)
        if it["partition"] != partition:
            raise SystemExit(f"{it['item_id']} is labelled {it['partition']}, not {partition}")
        it["problem"]["payload"] = expand(it["problem"].get("payload", {}))
        items.append(it)
    if len({i["item_id"] for i in items}) != len(items):
        raise SystemExit("duplicate item ids")
    return items


def _check_freeze(partition):
    if partition not in REPORTED:
        return None
    if not MANIFEST.exists():
        raise SystemExit(f"{partition} refused: no freeze manifest")
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    current = freeze_inputs()
    if manifest["inputs"] != current:
        changed = sorted(k for k in current if manifest["inputs"].get(k) != current[k])
        detail = sorted(p for p in current["code"] if manifest["inputs"]["code"].get(p) != current["code"][p])
        raise SystemExit(f"{partition} refused: frozen inputs changed: {changed} {detail}")
    return manifest


def run_partition(partition: str, arms=ARMS) -> dict:
    manifest = _check_freeze(partition)
    items = load(partition)
    client, reason = (None, None)
    if {"always_llm", "tool_llm"} & set(arms):
        client, reason = A.model_probe()
    out = {"partition": partition, "item_count": len(items), "arms": {}, "rows": {}}
    for name in arms:
        if name in ("always_llm", "tool_llm"):
            if client is None:
                out["arms"][name] = {"status": "NOT_RUN", "reason": f"no founder-selected loopback model "
                                     f"answered the probe ({reason}); model downloads are egress-blocked in this "
                                     "environment and no paid fallback is authorized"}
                continue
            if name == "tool_llm":
                out["arms"][name] = {"status": "NOT_RUN", "reason": "tool-enabled model workflow not built for "
                                     "this seed; a model is reachable, so this is a build gap, not a blocker"}
                continue
        rows, decisions = [], []
        for it in items:
            try:
                if name == "routed_greg":
                    d = A.routed_greg(it)
                elif name == "existing_greg":
                    d = A.existing_greg(it)
                elif name == "static_router":
                    d = A.static_router(it)
                elif name == "always_llm":
                    d = A.always_llm(it, client)
                else:
                    d = A.always_abstain(it)
            except Exception as exc:   # noqa: BLE001 - an arm crash is a scored task failure
                d = {"disposition": "error", "answer": None, "latency_s": 0.0, "cost_usd": 0.0,
                     "error": f"{type(exc).__name__}: {exc}"[:300]}
            row = L.item_loss(it, d)
            row["answer"] = d.get("answer")
            row["latency_s"] = round(float(d.get("latency_s") or 0.0), 6)
            for k in ("note", "error", "receipt_id", "outcome", "method", "operations", "states"):
                if d.get(k) is not None:
                    row[k] = d[k]
            rows.append(row)
        out["rows"][name] = rows
        out["arms"][name] = {"status": "RUN", "summary": L.summarize(rows)}
    out["freeze_manifest_sha256"] = _sha(MANIFEST) if manifest else None
    out["frozen_at"] = manifest.get("frozen_at") if manifest else None
    return out


def compare(part: dict) -> dict:
    rows = part["rows"]
    if L.ROUTED not in rows:
        return {}
    return {name: L.paired_gain(r, rows[L.ROUTED]) for name, r in rows.items() if name != L.ROUTED}


def determinism(items: list[dict], k: int = 12) -> dict:
    """Re-run the routed system on k items; dispositions and answers must match the first pass."""
    first = [A.routed_greg(it) for it in items[:k]]
    second = [A.routed_greg(it) for it in items[:k]]
    same = [a["disposition"] == b["disposition"] and json.dumps(a["answer"], sort_keys=True, default=str) ==
            json.dumps(b["answer"], sort_keys=True, default=str) for a, b in zip(first, second)]
    return {"items": k, "identical": sum(same), "note": "deterministic organs and seeded sampling; repeated "
            "outputs of one problem are not counted as independent tasks"}


def report(heldout: dict, adversarial: dict) -> dict:
    planning = json.loads(MANIFEST.read_text(encoding="utf-8")).get("planning") if MANIFEST.exists() else None
    ver = L.verdict(heldout["arms"], heldout["rows"], adversarial["rows"], planning)
    return {"schema": "greg-crossgeo-results/0.1", "cortex_version": CORTEX_VERSION,
            "run_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "environment": {"python": sys.version.split()[0], "platform": platform.platform()},
            "freeze_manifest_sha256": heldout["freeze_manifest_sha256"], "frozen_at": heldout["frozen_at"],
            "loss": {"version": L.LOSS_VERSION, "weights": L.WEIGHTS, "decision": L.DECISION},
            "planning": planning,
            "adapter_information_lost": list(A.ADAPTER_INFORMATION_LOST),
            "verdict": ver,
            "heldout": {"arms": heldout["arms"], "paired_gain_vs_routed": compare(heldout),
                        "regret": L.regret({k: v for k, v in heldout["rows"].items()}),
                        "rows": heldout["rows"]},
            "adversarial": {"arms": adversarial["arms"], "paired_gain_vs_routed": compare(adversarial),
                            "rows": adversarial["rows"]},
            "determinism": determinism(load("heldout"))}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--freeze", action="store_true")
    ap.add_argument("--planning", help="selection results used for the predeclared sample-size plan")
    ap.add_argument("--partition", choices=sorted(SUITES) + ["reported"], default="dev")
    ap.add_argument("--arms", default=",".join(ARMS))
    ap.add_argument("--out")
    args = ap.parse_args(argv)
    if args.freeze:
        planning = None
        if args.planning:
            sel = json.loads(Path(args.planning).read_text(encoding="utf-8"))
            run = [b for b in L.DECLARED_BASELINES if sel["arms"].get(b, {}).get("status") == "RUN"]
            strongest = min(run, key=lambda b: sel["arms"][b]["summary"]["mean_loss"])
            gain = L.paired_gain(sel["rows"][strongest], sel["rows"][L.ROUTED])
            planning = {"source": "selection partition (never held-out)", "strongest_baseline": strongest,
                        "baseline_mean_loss": gain["baseline_mean_loss"], "sd_paired_difference": gain["sd_diff"],
                        "required_heldout_n_for_10pct_at_power_0.8": L.required_n(gain["sd_diff"],
                                                                                  gain["baseline_mean_loss"]),
                        "planned_heldout_n": len(load("heldout"))}
        manifest = {"schema": "greg-crossgeo-freeze/0.1",
                    "frozen_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "inputs": freeze_inputs(), "planning": planning}
        MANIFEST.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"frozen: {MANIFEST.relative_to(ROOT)} {_sha(MANIFEST)}")
        print(json.dumps(planning, indent=2))
        return 0
    arms = tuple(a for a in args.arms.split(",") if a)
    if args.partition == "reported":
        result = report(run_partition("heldout", arms), run_partition("adversarial", arms))
        brief = {"verdict": result["verdict"]["verdict"], "reasons": result["verdict"]["reasons"],
                 "strongest": result["verdict"].get("strongest_run_baseline"),
                 "gain": result["verdict"].get("gain")}
    else:
        result = run_partition(args.partition, arms)
        result["paired_gain_vs_routed"] = compare(result)
        brief = {k: (v.get("status"), (v.get("summary") or {}).get("mean_loss"),
                     (v.get("summary") or {}).get("hard_failures")) for k, v in result["arms"].items()}
    text = json.dumps(result, indent=2, sort_keys=True, default=str) + "\n"
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(text, encoding="utf-8")
    print(json.dumps(brief, indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
