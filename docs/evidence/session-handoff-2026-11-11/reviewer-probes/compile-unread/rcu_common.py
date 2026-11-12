"""Reviewer's harness: runs on base and head (cwd = a tree)."""
import os, subprocess, sys, tempfile, json
from datetime import datetime
from pathlib import Path
sys.path.insert(0, ".")
import greg.capabilities as caps
from greg.body import Body
from tests.greg_fixtures import Clock, make_body, mission, note_check, signed, write_strategy

METHOD = "cognition.swarm"
SPHERE = {"function": "sphere", "bounds": [[-5.12, 5.12]] * 3, "budget": 300, "shift": [0.5, -0.25, 1.0], "seed": 3}
STEP = 31.0
TMP = os.environ.get("RC_TMP", "/tmp/claude-0/-home-user/f78643ba-8a14-5107-b25c-e0462dfdc774/scratchpad/rcu-tmp")

def tmp():
    return Path(tempfile.mkdtemp(dir=TMP))

def compile_params(problem="real:q", **extra):
    return {"problem_id": problem, "compile": {"geometry": {"geometry": "optimization"}, "data": dict(SPHERE), **extra}}

def fitness_check(check_id="good", *, value=1e6, problem="real:q", **extra):
    return {"check_id": check_id, "description": "fitness bound",
            "sensor": {"capability": "cognition.solve", "target": "cognition:bb", "params": compile_params(problem, **extra)},
            "predicate": {"op": "lte", "field": "result.fitness", "value": value}}

def question(mid, *checks, strategies=(), capabilities=("cognition.solve",), targets=("cognition:*",), ceiling="read_only", **kw):
    return mission(mid, checks=list(checks), strategies=list(strategies), capabilities=list(capabilities), targets=targets, ceiling=ceiling, **kw)

class Host:
    def __init__(self):
        self.real, self.mode, self.only, self.after, self.calls = caps.run_isolated, None, None, 0, 0
        caps.run_isolated = self.launch
    def stall(self, mode, *, only=None, after=0):
        self.mode, self.only, self.after, self.calls = mode, only, after, 0
    def recover(self):
        self.mode = None
    def launch(self, argv, *args, **kwargs):
        worker = any("worker.py" in str(a) for a in argv)
        if worker and self.mode and (self.only is None or self.only in argv):
            self.calls += 1
            if self.calls > self.after:
                if self.mode == "timeout":
                    raise subprocess.TimeoutExpired(argv, kwargs.get("timeout", 5))
                return subprocess.CompletedProcess(argv, 137, b"", b"killed")
        return self.real(argv, *args, **kwargs)

class Run:
    def __init__(self, attach=(METHOD,), **kw):
        self.tmp = tmp()
        self.home, self.key, self.body_id, self.data = make_body(self.tmp, **kw)
        self.clock = Clock(); self.start = self.clock()
        self.body = Body(self.home, clock=self.clock).open(); self.body.boot()
        for cid in attach:
            self.sign("CAPABILITY_ATTACH", {"capability_id": cid})
    def __enter__(self): return self
    def __exit__(self, *exc): self.body.close()
    def sign(self, kind, payload): return self.body.apply(signed(self.key, self.body_id, kind, payload))
    def tick(self, mid, step=STEP):
        row = next((r for r in self.body.tick()["missions"] if r.get("mission_id", mid) == mid), None)
        self.clock.advance(step)
        return row["state"] if row else None
    def events(self, kind, mid=None):
        return [e.payload for e in self.body.journal.replay(kind) if mid is None or e.payload.get("mission_id") == mid]
    def offset(self, at=None):
        when = self.clock() if at is None else datetime.fromisoformat(at.replace("Z", "+00:00"))
        return round((when - self.start).total_seconds())
    def output(self, obs): return self.body.journal.ledger.find(obs["receipt"]).payload["result"]["output"]
    def mission(self, mid): return self.body.engine.book.missions[mid]
    def report(self, mid, label=""):
        m = self.mission(mid)
        print("  observed:", [(self.offset(o["at"]), o["check_id"], o["passed"], o.get("declined"), o.get("failure_class"), o["detail"][:60]) for o in self.events("mission.observed", mid)])
        print("  actions:", [(a["action_id"], a["status"]) for a in self.events("mission.action", mid)])
        print("  asks:", [(self.offset(a["created_at"]), a["kind"], (a.get("why_now") or "")[:150], a.get("authority_requested")) for a in self.events("decision.requested")])
        print("  withdrawn:", [(self.offset(w["at"]), w["why"][:60]) for w in self.events("decision.withdrawn")])
        print("  failed:", {k: v[:110] for k, v in m.failed.items()})
        print("  routing.outcome:", [(o["action_id"], o["capability"], o["verdict"]) for o in self.events("routing.outcome")])
        print("  mission.unmet:", [(u["failing_checks"], u.get("unmeasured_checks")) for u in self.events("mission.unmet")])
        print("  appraised:", [(a["verdict"], [f[:90] for f in (a.get("findings") or [])][:3]) for a in self.events("mission.appraised")])
        print("  deficits:", [(d.get("function"), d.get("purpose", "")[:40]) for d in self.events("deficit.opened")])
        print("  status:", m.status, "| blocker:", (m.blocker or {}).get("type"), (m.blocker or {}).get("why"), (m.blocker or {}).get("failing_checks"), "| next_observe_at:", self.offset(m.next_observe_at) if m.next_observe_at else None)
