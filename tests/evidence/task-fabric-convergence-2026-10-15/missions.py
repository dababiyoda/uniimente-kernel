"""Signed body missions after the change (run from the repository root).

``daleobanks_post`` with the bound-claims contract: a scripted worker (a test double, never presented as a frontier
worker) writes a draft and its claims file; DALEOBANKS verifies the draft; the Task Fabric's evaluator asks the Mind
about every sentence against GREG's copy of the source. The publish request requires both and lies outside the light
cone, so even a draft that passes both waits for a founder decision that is never given here. Nothing is posted.

``GREG_TEST_DALEOBANKS=<checkout>`` runs DALEOBANKS's own EthicsGuard, Critic and PromptFirewall from that
checkout, in its own process, with this interpreter (``python``); otherwise a stub that approves every draft.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import tempfile

sys.path.insert(0, os.getcwd())
from greg import templates, workers                                   # noqa: E402
from greg.body import Body                                            # noqa: E402
from tests.greg_fixtures import Clock, drop, make_body, signed       # noqa: E402

sys.path.insert(0, str(Path(__file__).parent))
from reproduce import SOURCE, Scripted, stub                          # noqa: E402

STUDY = "A study at two depots found the new routing method may reduce delays by 12%"
FUEL = "It did not lower fuel costs."
NAME = "Drivers at Northgate reported fewer missed windows."
CASES = {
    "faithful": [("A two-depot study found the routing method may cut delays by 12%.", STUDY),
                 ("Fuel costs did not fall.", FUEL)],
    "hedge dropped": [("A two-depot study found the routing method cuts delays by 12%.", STUDY),
                      ("Fuel costs did not fall.", FUEL)],
    "negation removed": [("A two-depot study found the routing method may cut delays by 12%.", STUDY),
                         ("It lowered fuel costs.", FUEL)],
    "scope widened": [("A study at all depots found the routing method may cut delays by 12%.", STUDY)],
    "direction reversed": [("A two-depot study found the routing method may increase delays by 12%.", STUDY)],
    "name substituted": [("Drivers at Southgate reported fewer missed windows.", NAME)],
}


def files(claims, extra=""):
    draft = " ".join(text for text, _ in claims) + extra
    bindings = [{"text": text, "quotes": [{"input": "source.txt", "quote": quote}]} for text, quote in claims]
    return {"post.txt": draft, "post.claims.json": json.dumps(bindings)}


def run(name: str, worker_files: dict, daleobanks: Path | None = None) -> dict:
    tmp = Path(tempfile.mkdtemp(prefix="greg-fabric-"))
    data = tmp / "data"
    data.mkdir()
    real = daleobanks is not None
    daleobanks = daleobanks or stub(tmp / "daleobanks")
    home, key, body_id, _ = make_body(tmp, read_roots=[data, daleobanks])
    (data / "source.txt").write_text(SOURCE)
    workers.PROVIDERS["scripted"] = Scripted(worker_files)
    spec = templates.daleobanks_post(daleobanks_root=str(daleobanks), source=str(data / "source.txt"),
                                     brief="Summarise the depot study.", order="depot-note", budget_usd=1.0,
                                     max_chars=280, python=sys.executable if real else None)
    for s in spec["strategies"]:
        if s["capability"] == "worker.commission":
            s["params"]["provider"] = "scripted"
    drop(home, signed(key, body_id, "MISSION", spec))
    clock, states = Clock(), []
    with Body(home, clock=clock) as body:
        body.boot()
        for _ in range(8):
            clock.advance(30)
            states.append(body.tick()["missions"][0]["state"])
            if states[-1] in ("ACHIEVED", "BLOCKED", "EXHAUSTED", "FAILED"):
                break
        observed = {}
        for e in body.journal.replay("mission.observed"):
            observed[e.payload["check_id"]] = e.payload["passed"]
        outputs = [r.payload["result"]["output"] for r in body.ledger.by_type("receipt")
                   if isinstance(r.payload["result"].get("output"), dict)]
        appraisal = [o for o in outputs if "truth_preservation" in o and "independence" in o][-1:]
        verify = [o for o in outputs if "daleobanks" in o][-1:]
        asks = [e.payload for e in body.journal.replay("mission.") if "publish" in json.dumps(e.payload)
                and "outside scope" in json.dumps(e.payload)]
        commissions = sum(1 for o in outputs if o.get("work_order") == "depot-note")
        blocked = [e.payload for e in body.journal.replay("mission.blocked")]
    a = appraisal[0] if appraisal else {}
    return {"draft": name, "daleobanks": "real" if real else "stub", "states": states, "checks": observed,
            "worker_runs": commissions,
            "appraisal": a.get("verdict"), "mind_findings": [f[:160] for f in a.get("findings", []) if not f.startswith("worker self-report")][:3],
            "distortion_classes": sorted({d["class"] for d in a.get("truth_preservation", {}).get("distortions", [])}),
            "receipts": len(a.get("cognition_receipts", {})),
            "daleobanks_verify": verify[0]["verdict"] if verify else None,
            "daleobanks_own_checks": ({"ethics": verify[0]["daleobanks"]["ethics"]["approved"],
                                       "critic_blocking": verify[0]["daleobanks"]["critic"]["blocking_issues"],
                                       "firewall_risk": verify[0]["daleobanks"]["firewall"].get("risk")}
                                      if verify else None),
            "publish_request_reached": bool(asks),
            "blocked_because": [(b.get("blocker") or {}).get("why") or b.get("why") for b in blocked][-1:]}


if __name__ == "__main__":
    root = os.environ.get("GREG_TEST_DALEOBANKS")
    for name, claims in CASES.items():
        print(json.dumps(run(name, files(claims), Path(root) if root else None), sort_keys=True))
    print(json.dumps(run("uncovered sentence", files(CASES["faithful"], " Drivers at Northgate loved it."),
                         Path(root) if root else None), sort_keys=True))
    print(json.dumps(run("no claims file", {"post.txt": files(CASES["faithful"])["post.txt"]},
                         Path(root) if root else None), sort_keys=True))
