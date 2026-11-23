"""Dev probe (not a declared experiment): after the founder detaches what a construction mission formed, what does a
later same-family mission do? Namespace greg-detach-probe (never the spent greg-transfer-2026-10-28)."""
import json, sys, tempfile
from pathlib import Path
ROOT = Path(__file__).resolve().parents[5]; sys.path[:0] = [str(ROOT), str(ROOT / "scripts")]
import greg_transfer_eval as T
from tests.greg_fixtures import Clock, make_body, drop, signed
from greg.body import Body

def caps(home):
    with Body(home, clock=Clock()) as b:
        return {cid: b.registry.state[cid] for cid in b.registry.manifests
                if cid.startswith(("composed.", "acquired.")) or "max_flow" in cid}

problem = T.instances("greg-detach-probe", {"same_family": 1})["same_family"][0]
work = Path(tempfile.mkdtemp(prefix="detach-probe-"))
out = {}
for variant in ("detach_construction", "detach_construction_and_engine"):
    root = Path(tempfile.mkdtemp(prefix=variant + "-", dir=work))
    home, key, body_id, _ = make_body(root)
    clock = Clock()
    built = T.run_mission(home, key, body_id, T.task_spec("construction", 0, T.CONSTRUCTION, "probe-" + variant), clock)
    before = caps(home)
    targets = [c for c, s in before.items() if s == "ATTACHED" and (c.startswith("composed.") or variant.endswith("engine"))]
    for cid in targets:
        drop(home, signed(key, body_id, "CAPABILITY_DETACH", {"capability_id": cid}))
    task = T.run_mission(home, key, body_id, T.task_spec("same_family", 0, problem, "probe-" + variant), clock)
    out[variant] = {"construction": {k: built[k] for k in ("state", "work", "attach_asks", "qualifications", "deficits")},
                    "caps_before_detach": before, "detached": targets, "caps_after_task": caps(home),
                    "task": {k: task[k] for k in ("state", "ticks", "work", "attach_asks", "asks_by_kind", "qualifications",
                                                  "deficits", "first_compile_state", "method", "appraisal", "self_attached")},
                    "task_correct": task["state"] == "ACHIEVED" and T.judge("same_family", task["answer"],
                                                                             T.expected("same_family", problem))}
print(json.dumps(out, indent=1, default=str))
