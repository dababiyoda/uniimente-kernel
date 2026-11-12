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

After this change (greg/missions.py ``_pursue``: a candidate whose signed capability the founder detached is passed
over while another candidate remains), both cases run B2 on the tick after the detach, under B2's own scope, ask
nothing about the detached tool, and record in B2's action why B was passed over. The unreadable gauge is still an
unmeasured reading: SENSOR_RETRY, then a SENSOR_FAILURE ask, and nothing closes until the gauge reads again. The tests
below pin what the founder named: the detached tool is never invoked, an alternative outside the cone stops at its
own approval, an approval voided by a device revocation is asked for again and not routed around, a quarantined tool
is not passed over, and the completed effect runs once. One gap stays, as a strict expected failure: with no signed
alternative left, the same-function case still blocks without telling the founder.
"""
from __future__ import annotations

from datetime import timedelta
import hashlib

import pytest

from greg.artifacts import ArtifactStore
from greg.body import Body
from greg.capabilities import BUILTINS, CapabilityError, CapabilityManifest
from greg.founder import generate_founder_key, key_id, load_founder_key, sign_command, stamp
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


def spec(home, data, *, alternative: str, inside: bool, a_inside: bool = False) -> dict:
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
        "light_cone": {"capabilities": ["fs.read", "fs.search", "artifact.inspect"] + ([alternative] if inside else [])
                       + (["artifact.store"] if a_inside else []),
                       "targets": ["fs:*", f"artifact:{NAMESPACE}", "workspace:*"],
                       "max_consequence_class": "internal_write", "budget_usd": 1.0, "horizon": horizon()}}


class Run:
    """One body, its founder key and the mission; ``tick`` keeps the state the mission reported each turn."""

    def __init__(self, tmp_path, *, alternative: str = "fs.write", inside: bool = True, a_inside: bool = False,
                 strategies=None):
        self.home, self.key, self.body_id, self.data = make_body(tmp_path)
        (self.data / "note.txt").write_text(NOTE)
        self.gauge = self.data / "gauge.txt"
        self.gauge.write_text("gauge: green\n")
        self.clock, self.calls, self.states = Clock(), [], []
        self.spec = spec(self.home, self.data, alternative=alternative, inside=inside, a_inside=a_inside)
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

    def a_done(self):
        ask = self.until(lambda: self.asks("APPROVAL", "a"), "the approval ask for A")[0]
        self.answer(ask)
        self.until(lambda: [a for a in self.actions("a") if a["status"] == "DONE"], "A done")

    def remove_tool(self):
        """The founder detaches B's tool and the gauge becomes unreadable (a directory where the file was: the
        sensor's read is refused)."""
        self.apply("CAPABILITY_DETACH", {"capability_id": "artifact.materialize"})
        self.gauge.unlink()
        self.gauge.mkdir()

    def gauge_readable(self):
        self.gauge.rmdir()
        self.gauge.write_text("gauge: green\n")

    def a_done_then_tool_removed(self):
        """A approved and completed; then the founder detaches B's tool and the gauge becomes unreadable."""
        self.a_done()
        self.remove_tool()

    def device(self, label="phone"):
        """A device key the founder delegates DECISION to (its own Ed25519 key, not Alfonso's)."""
        public = generate_founder_key(self.home.parent / f"{label}.pem", None)
        self.apply("DEVICE_ENROLL", {"public_key": public, "label": label, "kinds": ["DECISION"],
                                     "expires_at": stamp(self.clock() + timedelta(days=30))})
        return load_founder_key(self.home.parent / f"{label}.pem", None), key_id(public)

    def device_answer(self, device_key, request, answer="approve"):
        self.clock.advance(1)
        return self.body.apply(sign_command(device_key, "DECISION", {"request_id": request["request_id"],
                                                                      "answer": answer, "reason": "from the phone"},
                                            body_id=self.body_id, now=self.clock()))

    def refusals(self):
        """The office's records that it ran nothing for a capability that is not ATTACHED."""
        return [e.payload for e in self.body.ledger.by_type("event")
                if e.payload.get("type") == "greg.authority.refused_unattached"]

    def close(self):
        self.body.close()


@pytest.fixture
def run(tmp_path):
    made = []

    def make(**kw):
        home = tmp_path / str(len(made))
        home.mkdir()
        made.append(Run(home, **kw))
        return made[-1]
    yield make
    for r in made:
        r.close()


def finished_through_the_alternative(r: Run) -> None:
    """What the founder asked for, in the order it must hold."""
    r.a_done_then_tool_removed()
    r.until(lambda: [a for a in r.actions("b2") if a["status"] == "DONE"], "the alternative B2 done")
    # the detached tool was never called, and the engine never handed it to the office
    assert [c for c in r.calls if c[0] == "artifact.materialize"] == [] and r.actions("b") == []
    assert r.refusals() == []
    # no attach was asked for while the alternative could serve
    assert r.asks("CAPABILITY_ATTACH") == []
    # with the gauge unreadable the mission closes nothing; the reading stays unmeasured
    r.tick(2)
    assert r.events("mission.achieved") == [] and r.events("mission.unmet") == []
    unreadable = [o for o in r.events("mission.observed") if o["check_id"] == "c" and not o["passed"]]
    assert unreadable and all(o["detail"].startswith("sensor REFUSED") for o in unreadable)
    r.gauge_readable()
    [achieved] = r.until(lambda: r.events("mission.achieved"), "the achievement")
    # it closes on a reading taken after the unreadable ones, never on an earlier pass
    readings = [o for o in r.events("mission.observed") if o["check_id"] == "c"]
    cited = [o for o in readings if o["receipt"] in achieved["evidence"]]
    assert len(cited) == 1 and cited[0]["passed"] and readings.index(cited[0]) > readings.index(unreadable[-1])
    # effect A ran once and its cost is booked once; B2's cost is the only other spend
    assert len([c for c in r.calls if c[0] == "artifact.store"]) == 1
    assert [(a["action_id"], a["status"], a["cost_usd"]) for a in r.actions()] == [
        ("a", "DONE", COST_A), ("b2", "DONE", COST_ALT)]
    assert r.mission().spent_usd == pytest.approx(COST_A + COST_ALT)
    assert (workspace(r.home, MID) / "copy.txt").read_text() == NOTE


def test_same_function_the_signed_alternative_finishes_the_mission(run):
    r = run(alternative=SECOND)
    finished_through_the_alternative(r)
    assert [c[0] for c in r.calls] == ["artifact.store", SECOND]
    # the separate appraiser is a process of its own: it does not know a capability registered only in this one, so
    # it cannot re-derive B2's admission or receipt and does not verify the closure
    [appraised] = r.events("mission.appraised")
    assert appraised["verdict"] == "REFUTED"
    assert "b2: its admission to the signed cone cannot be re-derived" in appraised["findings"]


def test_another_function_the_signed_alternative_finishes_and_is_appraised_verified(run):
    r = run(alternative="fs.write")
    finished_through_the_alternative(r)
    assert [c[0] for c in r.calls] == ["artifact.store", "fs.write"]
    [appraised] = r.events("mission.appraised")
    assert appraised["verdict"] == "VERIFIED" and appraised["findings"] == []
    assert "closure_event" not in appraised            # the achievement's own appraisal
    assert all(appraised["checks"][k] for k in ("closure_evidence_bound", "checks_rederived_from_receipts",
                                                 "world_reobserved", "exactly_once", "approval_boundaries_honored"))
    # bound to the closure it judged: it read a ledger head at or after the achievement
    seq = {e.payload.get("event_id"): e.seq for e in r.body.ledger.by_type("event")}
    assert seq[r.body.journal.replay("mission.achieved")[0].event_id] <= r.body.ledger.find(appraised["head"]).seq


def test_the_record_says_the_alternative_ran_because_the_preferred_tool_is_detached(run):
    r = run(alternative="fs.write")
    r.a_done_then_tool_removed()
    r.until(lambda: r.actions("b2"), "B2")
    [b2] = r.actions("b2")
    [passed] = b2["routing"]["passed_over"]
    assert (b2["routing"]["chosen"], passed["action_id"], passed["capability"]) == ("b2", "b", "artifact.materialize")
    assert "the founder detached artifact.materialize" in passed["why"]
    # the ranking alone would have run B: it was passed over only because its tool is detached
    assert passed["expected_value"] > b2["routing"]["expected_value"]


def test_state_sequence_after_the_detach(run):
    """The sequence that replaced the measured one in the module docstring (same function: BLOCKED with no blocker
    every tick; another function: one attach ask, then WAITING)."""
    for alternative in (SECOND, "fs.write"):
        r = run(alternative=alternative)
        r.a_done_then_tool_removed()
        assert r.tick(4) == ["ACTED", "SENSOR_RETRY", "BLOCKED", "WAITING"]
        assert [(q["kind"], q.get("action_id")) for q in r.asks()] == [("APPROVAL", "a"), ("SENSOR_FAILURE", None)]
        assert r.mission().blocker["sensing"] is True
        r.gauge_readable()
        assert r.tick(2) == ["RESUMED", "ACHIEVED"]


def test_an_alternative_outside_the_cone_stops_at_its_own_approval(run):
    """B is approved, then its tool detached before it runs. B2 lies outside the cone: it is asked for under its own
    scope; B's approval is not its approval, and nothing runs until the founder answers."""
    r = run(alternative="fs.write", inside=False)
    r.a_done()
    ask_b = r.until(lambda: r.asks("APPROVAL", "b"), "the approval ask for B")[0]
    r.answer(ask_b)
    r.remove_tool()                        # before the tick that would dispatch B
    ask_b2 = r.until(lambda: r.asks("APPROVAL", "b2"), "the approval ask for B2")[0]
    m = r.mission()
    assert ask_b["scope_digest"] in m.approved_scopes and ask_b2["scope_digest"] not in m.approved_scopes
    assert ask_b2["scope_digest"] != ask_b["scope_digest"]
    assert ask_b2["authority_requested"]["capability"] == "fs.write"
    assert ask_b2["evidence"]["routing"]["passed_over"][0]["action_id"] == "b"
    r.tick(3)
    assert r.actions("b2") == [] and [c[0] for c in r.calls] == ["artifact.store"]
    assert r.mission().blocker["request_id"] == ask_b2["request_id"]
    r.answer(ask_b2)
    r.until(lambda: [a for a in r.actions("b2") if a["status"] == "DONE"], "B2 done")
    assert [c[0] for c in r.calls] == ["artifact.store", "fs.write"] and r.actions("b") == []


def test_with_only_the_detached_strategy_left_its_attach_is_asked_for(run):
    """The founder rejects the alternative: B is the only route left, and the mission asks for its tool as before. The
    detached tool is still never called."""
    r = run(alternative="fs.write", inside=False)
    r.a_done_then_tool_removed()
    ask_b2 = r.until(lambda: r.asks("APPROVAL", "b2"), "the approval ask for B2")[0]
    r.answer(ask_b2, "reject")
    [attach] = r.until(lambda: r.asks("CAPABILITY_ATTACH"), "the attach ask")
    assert attach["authority_requested"]["function"] == "artifact.materialize"
    m = r.mission()
    assert m.blocker["type"] == "capability" and m.blocker["capability_id"] == "artifact.materialize"
    assert m.failed["b2"].startswith("founder rejected")
    assert [c[0] for c in r.calls] == ["artifact.store"] and r.actions("b") == [] and r.refusals() == []


def test_an_approval_voided_by_a_device_revocation_is_asked_again_not_routed_around(run):
    """Capability repair cannot restore revoked authority, and revoked authority is not repaired by an alternative:
    the phone approved B and was revoked before B ran. B's tool is attached; the mission asks for B again, and B2,
    attached and inside the cone, does not run in its place."""
    r = run(alternative="fs.write", inside=True)
    phone, phone_id = r.device()
    r.a_done()
    ask_b = r.until(lambda: r.asks("APPROVAL", "b"), "the approval ask for B")[0]
    r.device_answer(phone, ask_b)
    r.apply("DEVICE_REVOKE", {"device_key_id": phone_id})
    again = r.until(lambda: [q for q in r.asks("APPROVAL", "b") if q["request_id"] != ask_b["request_id"]],
                    "the second approval ask for B")[0]
    r.tick(3)
    assert again["scope_digest"] == ask_b["scope_digest"]
    assert r.actions("b2") == [] and r.actions("b") == [] and [c[0] for c in r.calls] == ["artifact.store"]
    assert r.mission().blocker["request_id"] == again["request_id"]
    assert r.asks("CAPABILITY_ATTACH") == []


def test_only_a_founder_detach_is_passed_over(run):
    """A quarantined tool is not a founder detach: B is pursued as before (its function is searched for and the
    founder asked), and B2 does not run in its place."""
    r = run(alternative="fs.write", inside=True)
    r.a_done()
    r.body.registry.set_state("artifact.materialize", "QUARANTINED")
    r.tick(4)
    assert r.actions("b2") == [] and r.actions("b") == []
    assert [q["kind"] for q in r.asks()] == ["APPROVAL", "CAPABILITY_ATTACH"]
    assert [c[0] for c in r.calls] == ["artifact.store"]


def test_no_goal_is_asked_ahead_about_the_detached_strategy(run):
    """``first_choice`` is the mission's own selection for an ask made ahead of its loop: once B's tool is detached
    it names B2, so an approve of B could change nothing and is not asked for."""
    r = run(alternative="fs.write", inside=False)
    r.a_done()
    assert r.body.engine.ask_refusal(MID, "b", now=r.clock()) is None
    r.remove_tool()
    refusal = r.body.engine.ask_refusal(MID, "b", now=r.clock())
    assert refusal is not None and "runs b2 first" in refusal
    assert r.body.engine.ask_refusal(MID, "b2", now=r.clock()) is None


def test_the_completed_effect_is_not_chosen_again_when_the_tool_is_removed(run):
    """A lies inside the cone here, so nothing but its passing check keeps it from running again: the alternative is
    chosen among the strategies that advance a failing check, never by signed order alone."""
    r = run(alternative="fs.write", inside=True, a_inside=True)
    r.until(lambda: [a for a in r.actions("a") if a["status"] == "DONE"], "A done without an ask")
    r.remove_tool()
    r.until(lambda: [a for a in r.actions("b2") if a["status"] == "DONE"], "B2 done")
    r.tick(2)
    assert [(a["action_id"], a["status"]) for a in r.actions()] == [("a", "DONE"), ("b2", "DONE")]
    assert [c[0] for c in r.calls] == ["artifact.store", "fs.write"]
    assert r.mission().spent_usd == pytest.approx(COST_A + COST_ALT) and r.asks("APPROVAL") == []


@pytest.mark.xfail(strict=True, raises=AssertionError, reason=(
    "greg/missions.py _pursue: with no signed alternative left, B's detached capability goes to _deficit; "
    "Genesis.resolve returns the other attached implementation of the function, which B does not name, so _resolve "
    "stays None and _pursue returns BLOCKED with no blocker and no ask on every tick. The founder is never told"))
def test_gap_with_no_signed_alternative_the_founder_is_told(run):
    r = run(alternative=SECOND, strategies=("a", "b"))
    r.a_done_then_tool_removed()
    r.tick(6)
    assert r.asks("CAPABILITY_ATTACH") or r.mission().blocker is not None, r.states
