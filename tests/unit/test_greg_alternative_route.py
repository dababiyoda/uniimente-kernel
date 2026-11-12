"""A preferred tool removed after a completed effect: does GREG finish through a signed alternative?

The founder, 2026-11-12, verbatim: "Combine these capabilities in one experiment: interrupt a mission, invalidate one
supporting observation, remove its preferred tool, and preserve an already completed effect. Determine whether GREG
can repair the missing function through an allowed alternative, obtain appraisal, and finish." And: "Capability
repair cannot restore revoked authority."

These tests measure the mission engine on a real in-process Body (test clock, per-test Ed25519 key, not Alfonso's).
One mission, three checks:

  a  the note is retained by digest       effect A: artifact.store of data/note.txt, outside the cone ($0.10)
  b  a working copy of the note exists    B, preferred: artifact.materialize of the retained bytes ($0.25)
                                          B2, the signed alternative: another capability writes the same copy ($0.50)
  c  the gauge reads green                 no strategy; its file is made unreadable, then readable

B ranks above B2 (it costs less for the same check). After A completes, the founder detaches artifact.materialize
and the gauge becomes unreadable. The alternative is either a second implementation of artifact.materialize's own
function, which this test registers (the tree holds no two built-in capabilities with one function), or fs.write, a
built-in with another function that writes the same copy.

Measured on the composed candidate 98df0260, before any change to greg/missions.py:

- same function: from the tick after A, every tick returns BLOCKED with no blocker, no ask and no action. _pursue
  resolves only its top candidate; B's detached capability goes to _deficit, Genesis finds the other attached
  implementation of the function and returns it, B's own capability still does not resolve, and the mission returns
  BLOCKED without recording anything. B2 never runs and the founder is never told.
- another function: one CAPABILITY_ATTACH ask for artifact.materialize, then WAITING on it for as long as the test
  ran. B2 never runs.
"""
from __future__ import annotations

import hashlib

import pytest

from greg.artifacts import ArtifactStore
from greg.body import Body
from greg.capabilities import BUILTINS, CapabilityError, CapabilityManifest
from tests.greg_fixtures import Clock, make_body, signed, workspace, horizon

MID = "m:alternative-route"
NOTE = "alpha: the note the mission retains\n"
ADDRESS = "sha256:" + hashlib.sha256(NOTE.encode()).hexdigest()
NAMESPACE = "retained"
COST_A, COST_B, COST_ALT = 0.10, 0.25, 0.50
SECOND = "artifact.restore"          # the test's second implementation of artifact.materialize's function
TICK = 61


def second_implementation(body, calls: list) -> None:
    """A second implementation of the function ``artifact.materialize`` serves, registered by this test: it writes
    the retained bytes to the signed workspace path by its own code (no manifest check, plain write). The separate
    appraiser, a process of its own, does not know it."""
    manifest = BUILTINS["artifact.materialize"][0]
    second = CapabilityManifest(
        capability_id=SECOND, version="1.0.0", provider="test-second-implementation", function=manifest.function,
        description="Write retained bytes to the mission workspace (a second implementation, registered by a test)",
        route="api", consequence_class="internal_write", inputs=manifest.inputs, outputs=manifest.outputs,
        target_prefix="workspace:", filesystem="workspace-write", strengthens=("reliability",))

    def adapter(params, ctx):
        calls.append((SECOND, ctx.grant_id))
        if ctx.target != "workspace:" + params["relative_path"]:
            raise CapabilityError("path does not match the signed target")
        data = ArtifactStore(ctx.artifact_root).read(params["address"])
        out = ctx.workspace / params["relative_path"]
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(data)
        return {"path": str(out), "address": params["address"], "created": True}
    body.registry.register(second, adapter, state="ATTACHED")


def counted(body, calls: list, *capabilities: str) -> None:
    """Every call that reaches a capability's registered adapter, counted (the adapter itself, wrapped)."""
    for cid in capabilities:
        real = body.registry.adapters[cid]

        def adapter(params, ctx, real=real, cid=cid):
            calls.append((cid, ctx.grant_id))
            return real(params, ctx)
        body.registry.adapters[cid] = adapter


def spec(home, data, *, alternative: str, inside: bool) -> dict:
    copy = workspace(home, MID) / "copy.txt"
    materialize = {"namespace": NAMESPACE, "address": ADDRESS, "relative_path": "copy.txt"}
    alt_params = {"relative_path": "copy.txt", "content": NOTE} if alternative == "fs.write" else dict(materialize)
    return {
        "mission_id": MID, "priority": 50, "founder_expression": "Retain the note, keep a working copy of it, and "
                                                                "close only while the gauge reads green.",
        "intended_effect": "the note is retained by digest, copy.txt holds it, and the gauge reads green",
        "closure": {"kind": "bounded", "cadence_seconds": 60},
        "success_checks": [
            {"check_id": "a", "description": "the note is retained by digest",
             "sensor": {"capability": "artifact.inspect", "params": {"namespace": NAMESPACE, "address": ADDRESS},
                        "target": f"artifact:{NAMESPACE}"},
             "predicate": {"op": "equals", "field": "present", "value": True}},
            {"check_id": "b", "description": "a working copy of the note exists",
             "sensor": {"capability": "fs.read", "params": {"path": str(copy)}, "target": "fs:copy.txt"},
             "predicate": {"op": "contains", "field": "text", "value": "alpha"}},
            {"check_id": "c", "description": "the gauge reads green",
             "sensor": {"capability": "fs.search", "target": "fs:gauge.txt",
                        "params": {"path": str(data / "gauge.txt"), "phrases": ["green"], "max_seconds": 1}},
             "predicate": {"op": "equals", "field": "queries.0.found", "value": True}}],
        "strategies": [
            {"action_id": "a", "capability": "artifact.store", "params": {"namespace": NAMESPACE,
                                                                         "path": str(data / "note.txt")},
             "target": f"artifact:{NAMESPACE}", "advances": ["a"], "rationale": "retain the note",
             "cost_usd": COST_A},
            {"action_id": "b", "capability": "artifact.materialize", "params": materialize,
             "target": "workspace:copy.txt", "advances": ["b"], "requires": ["a"],
             "rationale": "restore the retained bytes as the working copy (preferred)", "cost_usd": COST_B},
            {"action_id": "b2", "capability": alternative, "params": alt_params, "target": "workspace:copy.txt",
             "advances": ["b"], "requires": ["a"], "rationale": "write the working copy another way (alternative)",
             "cost_usd": COST_ALT}],
        "light_cone": {"capabilities": ["fs.read", "fs.search", "artifact.inspect"] + ([alternative] if inside else []),
                       "targets": ["fs:*", f"artifact:{NAMESPACE}", "workspace:*"],
                       "max_consequence_class": "internal_write", "budget_usd": 1.0, "horizon": horizon()}}


class Run:
    """One body, its founder key and the mission; ``tick`` keeps the state the mission reported each turn."""

    def __init__(self, tmp_path, *, alternative: str = "fs.write", inside: bool = True, strategies=None):
        self.home, self.key, self.body_id, self.data = make_body(tmp_path)
        (self.data / "note.txt").write_text(NOTE)
        self.gauge = self.data / "gauge.txt"
        self.gauge.write_text("gauge: green\n")
        self.clock, self.calls, self.states = Clock(), [], []
        self.alternative = alternative
        self.spec = spec(self.home, self.data, alternative=alternative, inside=inside)
        if strategies is not None:
            self.spec["strategies"] = [s for s in self.spec["strategies"] if s["action_id"] in strategies]
        self.body = Body(self.home, clock=self.clock).open()
        if alternative == SECOND:
            second_implementation(self.body, self.calls)
        counted(self.body, self.calls, "artifact.store", "artifact.materialize", "fs.write")
        self.body.boot()
        self.apply("MISSION", self.spec)

    def apply(self, kind, payload):
        self.clock.advance(1)
        return self.body.apply(signed(self.key, self.body_id, kind, payload, now=self.clock()))

    def tick(self, n=1):
        for _ in range(n):
            self.clock.advance(TICK)
            rows = [r for r in self.body.tick()["missions"] if r.get("mission_id", MID) == MID]
            self.states.append(rows[0]["state"] if rows else None)
        return self.states[-n:]

    def events(self, kind):
        return [e.payload for e in self.body.journal.replay(kind) if e.payload.get("mission_id", MID) == MID]

    def asks(self, kind=None, action=None):
        return [r for r in self.events("decision.requested") if (kind is None or r["kind"] == kind)
                and (action is None or r.get("action_id") == action)]

    def actions(self, action=None):
        return [a for a in self.events("mission.action") if action is None or a["action_id"] == action]

    def answer(self, request, answer="approve"):
        return self.apply("DECISION", {"request_id": request["request_id"], "answer": answer, "reason": "test"})

    def until(self, predicate, what, limit=12):
        for _ in range(limit):
            found = predicate()
            if found:
                return found
            self.tick()
        raise AssertionError(f"{what} did not happen in {limit} turns: states {self.states}, asks "
                             f"{[(r['kind'], r.get('action_id')) for r in self.asks()]}, actions "
                             f"{[(a['action_id'], a['status']) for a in self.actions()]}")

    def mission(self):
        self.body.engine.book.rebuild()
        return self.body.engine.book.missions[MID]

    def a_done_then_tool_removed(self):
        """A approved and completed; then the founder detaches B's tool and the gauge becomes unreadable."""
        ask = self.until(lambda: self.asks("APPROVAL", "a"), "the approval ask for A")[0]
        self.answer(ask)
        self.until(lambda: [a for a in self.actions("a") if a["status"] == "DONE"], "A done")
        self.apply("CAPABILITY_DETACH", {"capability_id": "artifact.materialize"})
        self.gauge.unlink()
        self.gauge.mkdir()                # a directory where the file was: the sensor's read is refused

    def close(self):
        self.body.close()


@pytest.fixture
def run(tmp_path):
    made = []

    def make(**kw):
        made.append(Run(tmp_path, **kw))
        return made[-1]
    yield make
    for r in made:
        r.close()


def finished_through_the_alternative(r: Run) -> None:
    """What the founder asked for, in the order it must hold."""
    r.a_done_then_tool_removed()
    r.until(lambda: [a for a in r.actions("b2") if a["status"] == "DONE"], "the alternative B2 done")
    # the detached tool was never called, and the engine never handed it to the office
    assert [c for c in r.calls if c[0] == "artifact.materialize"] == []
    assert r.actions("b") == []
    assert not [e for e in r.body.ledger.by_type("event") if e.payload.get("type") == "greg.authority.refused_unattached"]
    # no attach was asked for while the alternative could serve
    assert r.asks("CAPABILITY_ATTACH") == []
    # with the gauge unreadable the mission closes nothing; the reading stays unmeasured
    r.tick(2)
    assert r.events("mission.achieved") == [] and r.events("mission.unmet") == []
    r.gauge.rmdir()
    r.gauge.write_text("gauge: green\n")
    r.until(lambda: r.events("mission.achieved"), "the achievement")
    # effect A ran once and its cost is booked once; B2's cost is the only other spend
    assert len([c for c in r.calls if c[0] == "artifact.store"]) == 1
    assert [(a["action_id"], a["status"], a["cost_usd"]) for a in r.actions()] == [
        ("a", "DONE", COST_A), ("b2", "DONE", COST_ALT)]
    assert r.mission().spent_usd == pytest.approx(COST_A + COST_ALT)


@pytest.mark.xfail(strict=True, raises=AssertionError, reason=(
    "measured on 98df0260: greg/missions.py _pursue resolves only its top candidate. B's detached capability goes "
    "to _deficit; Genesis.resolve finds the other attached implementation of the function and returns it; B's own "
    "capability still does not resolve, and _pursue returns BLOCKED with no blocker, no ask and no action, every tick"))
def test_same_function_the_signed_alternative_finishes_the_mission(run):
    r = run(alternative=SECOND)
    finished_through_the_alternative(r)


@pytest.mark.xfail(strict=True, raises=AssertionError, reason=(
    "measured on 98df0260: greg/missions.py _pursue resolves only its top candidate, so B's detached capability "
    "raises a CAPABILITY_ATTACH ask and the mission waits on it; the signed alternative B2 never runs"))
def test_another_function_the_signed_alternative_finishes_the_mission(run):
    r = run(alternative="fs.write")
    finished_through_the_alternative(r)


def test_measured_today_same_function(run):
    """What the engine does on 98df0260 when the alternative is a second implementation of the same function."""
    r = run(alternative=SECOND)
    r.a_done_then_tool_removed()
    states = r.tick(6)
    assert states == ["BLOCKED"] * 6 and r.mission().blocker is None
    assert [(q["kind"], q.get("action_id")) for q in r.asks()] == [("APPROVAL", "a")]
    assert [a["action_id"] for a in r.actions()] == ["a"] and [c[0] for c in r.calls] == ["artifact.store"]


def test_measured_today_another_function(run):
    """What the engine does on 98df0260 when the alternative is fs.write."""
    r = run(alternative="fs.write")
    r.a_done_then_tool_removed()
    states = r.tick(6)
    assert states[0] == "BLOCKED" and set(states[1:]) == {"WAITING"}
    [ask] = r.asks("CAPABILITY_ATTACH")
    assert r.mission().blocker["type"] == "capability"
    assert r.mission().blocker["capability_id"] == "artifact.materialize"
    assert ask["authority_requested"]["function"] == "artifact.materialize"
    assert [a["action_id"] for a in r.actions()] == ["a"] and [c[0] for c in r.calls] == ["artifact.store"]
