"""Reviewer probe helpers. Run from a tree root: cd <tree> && PYTHONPATH=.:<probes> python <probes>/pN.py"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

from greg.body import Body
from tests.greg_fixtures import Clock, drop, make_body, mission, note_check, signed, workspace, write_strategy

MID = "m:note"

COUNTING_CHILD = '''
import importlib, json, sys
import greg.appraisal as appraisal
from greg.capabilities import BUILTINS

LOG = sys.argv[1]


def note(line):
    with open(LOG, "a") as out:
        out.write(line + "\\n")


def counted(cid, real):
    def adapter(params, ctx):
        note("adapter " + cid)
        return real(params, ctx)
    return adapter


for cid, (manifest, adapter) in list(BUILTINS.items()):
    BUILTINS[cid] = (manifest, counted(cid, adapter))
load = importlib.import_module


def counting_load(name, *args, **kwargs):
    module = load(name, *args, **kwargs)
    for cid, owner in appraisal.DELIVERING.items():
        if owner == name and not getattr(module.verify_delivery, "counted", False):
            real = module.verify_delivery

            def verify(*a, _cid=cid, _real=real, **k):
                note("delivery " + _cid)
                return _real(*a, **k)
            verify.counted = True
            module.verify_delivery = verify
    return module


importlib.import_module = counting_load
print(json.dumps(appraisal.appraise(json.loads(sys.stdin.read(1 << 20))), sort_keys=True))
'''

_real_run = subprocess.run


class Child:
    """Counts the body's appraiser child processes and which adapters / deliveries each ran.

    NOTE: on base the counted adapter is a wrapper, so identity checks on head (`_withheld`) would see a
    non-registered adapter. To keep the head's identity rule satisfied the wrapper replaces BUILTINS *before*
    registry_view registers them (registry_view reads BUILTINS at call time), so manifests/adapters match."""

    def __init__(self, tmp: Path):
        self.log, self.requests, self.fail_next = tmp / "appraiser-ran.log", [], 0
        self.stub = tmp / "counting_appraiser.py"
        self.stub.write_text(COUNTING_CHILD)
        child = self

        def run(argv, *args, **kwargs):
            if list(argv[1:]) == ["-m", "greg.appraisal"]:
                child.requests.append(json.loads(kwargs["input"]))
                if child.fail_next:
                    child.fail_next -= 1
                    return subprocess.CompletedProcess(argv, 137, "", "killed")
                argv = [argv[0], str(child.stub), str(child.log)]
            return _real_run(argv, *args, **kwargs)

        subprocess.run = run

    @property
    def ran(self):
        return self.log.read_text().split("\n")[:-1] if self.log.exists() else []


def facts(body, kind, mid=MID):
    return [e.payload for e in body.journal.replay(kind) if e.payload.get("mission_id") == mid]


def note_mission(tmp, *, sensors=("fs.read",), mid=MID, closure=None):
    home, key, body_id, _ = make_body(tmp)
    note = workspace(home, mid) / "note.txt"
    note.parent.mkdir(parents=True, exist_ok=True)
    note.write_text("original")
    checks = [note_check("c", note, "final")]
    if "fs.list" in sensors:
        checks.append({"check_id": "listed", "description": "the folder holds the note",
                       "sensor": {"capability": "fs.list", "params": {"path": str(note.parent)}, "target": "fs:folder"},
                       "predicate": {"op": "count_gte", "field": "entries", "value": 1}})
    drop(home, signed(key, body_id, "MISSION", mission(
        mid, checks=checks, strategies=[write_strategy("w", "note.txt", "final", ["c"])],
        capabilities=[*sensors, "fs.write"], **({"closure": closure} if closure else {}))))
    return home, key, body_id, note


def close_then_stop(home, clock, *, closure="mission.achieved", mid=MID, ticks=8, step=1.0):
    with Body(home, clock=clock) as body:
        engine_tick = body.engine.tick

        def tick_then_stop(now, **kw):
            out = engine_tick(now, **kw)
            if facts(body, closure, mid):
                body.layout.stop_file.touch()
            return out

        body.engine.tick = tick_then_stop
        result = {}
        for _ in range(ticks):
            result = body.tick()
            clock.advance(step)
            if result.get("stopped"):
                break
        assert result.get("stopped") is True, result
        assert facts(body, closure, mid) and not facts(body, "mission.appraised", mid)
    (Path(home) / "STOP").unlink()


def detach(home, key, body_id, cid="fs.read"):
    drop(home, signed(key, body_id, "CAPABILITY_DETACH", {"capability_id": cid}))


def attach(home, key, body_id, cid="fs.read"):
    drop(home, signed(key, body_id, "CAPABILITY_ATTACH", {"capability_id": cid}))


def tmpdir(name):
    return Path(tempfile.mkdtemp(prefix=f"ra-{name}-", dir=str(Path(__file__).resolve().parent.parent / "ra-tmp")))


def tree():
    import greg
    return Path(greg.__file__).resolve().parents[1].name


def verdicts(body, mid=MID):
    return [(a["verdict"], a.get("closure_event", None) and "closure") for a in facts(body, "mission.appraised", mid)]


def show(label, value):
    print(f"[{tree()}] {label}: {value}")
    sys.stdout.flush()
