"""Guards of #173's builder-call reservation (acceptance H.G7) that each survived a mutation, now pinned.

Carried from the PR #184 port branch's review (f63f218), whose port of #173's mechanism onto an older Genesis found
these guards unpinned; on #173's own code they were unpinned too. Each test below fails when its guard is removed:
- a builder that declares no per-call ceiling is reserved all that remains of the signed build budget (deliberate,
  greg/README.md interruption residuals);
- the separate appraiser's read-only restore (Genesis.restore(record=False)) never completes an unresolved
  auto-attach, which would be a write;
- a build budget, or a light cone, left only by binary rounding is used up and buys no further call;
- the cone books exactly what the builds billed once their reservations settle.
In-process bodies; the death is a BaseException raised inside the call (the real SIGKILL is in
tests/integration/test_greg_genesis_kill_process.py). The builders are test doubles; the founder key is a per-test key.
"""
from __future__ import annotations

from greg.body import Body, observe
from greg.journal import Journal
from greg import mission_control
from greg.console import Console
from greg.missions import MissionBook
from tests.greg_fixtures import Clock, drop, make_body, signed
from tests.unit.test_greg_genesis_builder import CONTRACT, FUNCTION, GOOD, WRONG, _mission

CEILING = 0.60


class Killed(BaseException):
    """The body dies here: nothing after this point in the process runs."""


class PaidAgent:
    """A paid coding agent's stand-in, bounded per call by max_budget_usd (Genesis sets it)."""
    identity = "test-agent"

    def __init__(self, plan, calls):
        self.max_budget_usd, self.plan, self.calls = CEILING, list(plan), calls

    def build(self, request, feedback=None):
        self.calls.append(round(self.max_budget_usd, 6))
        if (self.plan.pop(0) if self.plan else "ok") == "die":
            raise Killed()
        return {"source": GOOD, "builder": "test-agent", "prompt_sha256": "sha256:" + "0" * 64,
                "cost_usd": round(0.30 + 0.01 * len(self.calls), 2)}


class FreeAgent:
    """A builder that declares no per-call ceiling (no max_budget_usd), like builders.StaticBuilder."""
    identity = "free-agent"

    def __init__(self, plan, calls):
        self.plan, self.calls = list(plan), calls

    def build(self, request, feedback=None):
        self.calls.append(hasattr(self, "max_budget_usd"))
        if (self.plan.pop(0) if self.plan else "ok") == "die":
            raise Killed()
        return {"source": GOOD, "builder": self.identity, "prompt_sha256": "sha256:" + "0" * 64, "cost_usd": 0.0}


class BilledAgent:
    """A paid agent that bills a planned cost per call and returns the planned source, or dies inside the call."""
    identity = "billed-agent"

    def __init__(self, plan, calls, ceiling):
        self.max_budget_usd, self.plan, self.calls = ceiling, list(plan), calls

    def build(self, request, feedback=None):
        self.calls.append(self.max_budget_usd)
        step = self.plan.pop(0)
        if step == "die":
            raise Killed()
        source, cost = step
        return {"source": source, "builder": self.identity, "prompt_sha256": "sha256:" + "0" * 64, "cost_usd": cost}


def boot(home, builder, ticks=4):
    """One body life: open, boot, tick until it dies (Killed) or the ticks run out; return the states seen."""
    clock = Clock()
    body = Body(home, clock=clock, builder=builder).open()
    states = []
    try:
        body.boot()
        for _ in range(ticks):
            clock.advance(30)
            states.append(body.tick()["missions"][0]["state"])
    except Killed:
        states.append("KILLED")
    finally:
        body.close()
    return states


def facts(home, kind):
    with observe(home) as journal:          # read-only: opening a Body would itself restore and record
        return [e.payload for e in journal.replay(kind)]


def books(home):
    """The mission's spend as its light cone books it, and its row in Mission Control's real cost projection."""
    with observe(home) as j:
        spent = MissionBook(j).missions["m:runbook"].committed_usd
    [row] = [r for r in mission_control.projection(Console(home))["costs"] if r["mission_id"] == "m:runbook"]
    return round(spent, 6), row


def setup(tmp_path, budget=1.0, build_budget=None):
    """A mission whose light cone holds ``budget`` and whose signed build budget is ``build_budget`` (default: all)."""
    home, key, body_id, data = make_body(tmp_path)
    build_budget = budget if build_budget is None else build_budget
    spec = _mission(data, budget=budget, contract=dict(CONTRACT, build_budget_usd=build_budget))
    drop(home, signed(key, body_id, "MISSION", spec))
    return home


def test_an_interrupted_call_by_a_builder_with_no_ceiling_is_charged_all_that_remained(tmp_path):
    # Deliberate (greg/README.md, interruption residuals): a builder that declares no ceiling may have spent anything
    # up to what the founder signed, so its interrupted call holds all of it. No retry follows; the founder is asked.
    home = setup(tmp_path, budget=3.0, build_budget=1.0)
    calls = []
    assert boot(home, FreeAgent(["die"], calls))[-1] == "KILLED"
    boot(home, FreeAgent(["ok"], calls))
    assert calls == [False], "Genesis never invents a ceiling, and nothing remains for a second call"
    [started] = facts(home, "genesis.build_started")
    assert started["reserved_usd"] == 1.0 and "declares no ceiling" in started["reserved_as"]
    routes = facts(home, "genesis.route")
    assert any(r["result"] == "no founder-signed build budget remains" for r in routes)
    assert any(r["result"] == "escalated" and r["route"] == "founder" for r in routes)
    committed, row = books(home)
    assert committed == 1.0 and row["unknown_at_cap_usd"] == 1.0, "the cone books the whole reservation"


def test_restore_for_the_appraiser_never_completes_an_unresolved_auto_attach(tmp_path, monkeypatch):
    # The separate appraiser re-pins formed capabilities with Genesis.restore(record=False) over a read-only ledger;
    # completing the deficit.resolved there would be a write, refused by that ledger, and the appraisal would fail.
    from greg.appraisal import _formed_registry
    home = setup(tmp_path, budget=1.0)
    record = Journal.record

    def dies_before_resolving(self, kind, data, **kwargs):
        if kind == "deficit.resolved":
            raise Killed()
        return record(self, kind, data, **kwargs)
    monkeypatch.setattr(Journal, "record", dies_before_resolving)
    assert boot(home, PaidAgent(["ok"], []))[-1] == "KILLED"
    monkeypatch.setattr(Journal, "record", record)
    with observe(home) as journal:
        before = len(journal.replay())
        registry = _formed_registry(journal, home / "workspace" / "m_runbook")
        assert len(journal.replay()) == before
    assert any(cid.startswith(f"built.{FUNCTION}.") for cid in registry.state)
    assert facts(home, "deficit.resolved") == [], "left for the body's own restore to complete"


def test_reservations_released_around_costs_that_do_not_sum_exactly_book_what_was_billed(tmp_path):
    # Two settled calls billed 0.1 and 0.2: the cone carries exactly those bills and no reservation of either call.
    home = setup(tmp_path, budget=1.0)
    calls = []
    assert "ACHIEVED" in boot(home, BilledAgent([(WRONG, 0.1), (GOOD, 0.2)], calls, CEILING))
    assert calls == [CEILING, CEILING]
    with observe(home) as j:
        m = MissionBook(j).missions["m:runbook"]
        assert m.spent_usd == 0.1 + 0.2 and m.reserved == {}, "exactly the billed costs, nothing still reserved"


def test_a_build_budget_left_only_by_binary_rounding_is_used_up(tmp_path, monkeypatch):
    # 0.8 - (0.1 + 0.7) is 1.1e-16 in binary: the founder signed 0.8, a billed attempt took 0.1 and an interrupted one
    # holds its 0.7 ceiling, so nothing remains and the restart says so. It says so at entry, before the host check:
    # past the entry the per-attempt check would also find nothing left, but a host outage there defers the deficit
    # as an outage instead of telling the founder the signed budget is used up.
    from greg import builders
    from greg.capabilities import CapabilityError
    home = setup(tmp_path, budget=2.0, build_budget=0.8)
    calls = []
    assert boot(home, BilledAgent([(WRONG, 0.1), "die"], calls, 0.7))[-1] == "KILLED"
    assert calls == [0.7, 0.7] and not any("budget remains" in r["result"] for r in facts(home, "genesis.route"))

    def outage(*args, **kwargs):
        raise CapabilityError("the isolated build verifier did not start in time", failure_class="transient")
    monkeypatch.setattr(builders, "isolation_ready", outage)
    boot(home, BilledAgent([], calls, 0.7), ticks=2)
    assert len(calls) == 2
    routes = facts(home, "genesis.route")
    assert any(r["result"] == "no founder-signed build budget remains" for r in routes)
    assert any(r["result"] == "escalated" and r["route"] == "founder" for r in routes)
    assert not any("host outage" in r["result"] for r in routes), "a spent budget is never deferred as an outage"


def test_a_cone_left_only_by_binary_rounding_buys_no_further_call(tmp_path):
    # The mission's cone is 0.8 and 0.1 of it went to an earlier paid action, so a build may take 0.7: 0.8 - 0.1 is
    # 0.7000000000000001 in binary. After a 0.7 attempt the cone has 1.1e-16 left, which buys no second call.
    from tests.greg_fixtures import mission, note_check, workspace, write_strategy
    home, key, body_id, data = make_body(tmp_path)
    doc = data / "FIRST_MISSION.md"
    doc.write_text("# Runbook\n- [x] install\n- [ ] enroll key\n  - [ ] load launchd\n* [ ] accept closure\n")
    note = workspace(home, "m:order") / "c.txt"
    counted = {"check_id": "counted", "description": "open steps known",
               "sensor": {"function": FUNCTION, "params": {"path": str(doc)}, "target": "fs:FIRST_MISSION.md"},
               "predicate": {"op": "equals", "field": "unchecked", "value": 3}}
    spec = mission("m:order", checks=[note_check("note", note, "ok"), counted],
                   strategies=[write_strategy("w", "c.txt", "ok", ["note"], cost_usd=0.1)],
                   capabilities=["fs.read", "fs.write", f"built.{FUNCTION}.*"], budget=0.8, auto_attach=True,
                   closure={"kind": "infinite", "ladder": [["note"], ["note", "counted"]]})
    spec["capability_specs"] = [dict(CONTRACT, build_budget_usd=0.8)]
    drop(home, signed(key, body_id, "MISSION", spec))
    calls = []
    boot(home, BilledAgent([(WRONG, 0.7), (GOOD, 0.0)], calls, 0.7), ticks=12)
    assert calls == [0.7], "the attempt took what the cone had left, and nothing was left for another"
    assert any(r["result"] == "no founder-signed build budget remains" for r in facts(home, "genesis.route"))


class BillsThenFails:
    """A paid agent whose call is billed at its ceiling and returns no candidate (BuildError with cost_usd, as a
    Claude Code timeout is billed)."""
    identity = "billed-fail"

    def __init__(self, calls):
        self.max_budget_usd, self.calls = CEILING, calls

    def build(self, request, feedback=None):
        from greg import builders
        self.calls.append(round(self.max_budget_usd, 6))
        raise builders.BuildError("timed out", cost_usd=self.max_budget_usd)


def test_a_billed_failure_survives_a_kill_between_its_two_records_and_the_budget_bounds_the_next_call(tmp_path,
                                                                                                    monkeypatch):
    """Merge review of e410977: a billed failed call writes genesis.build_failed and genesis.unbuilt (its bill). The
    body dies between the two writes, whichever comes second. The bill stays booked (the reservation is never
    released at $0), Mission Control books the same, and the restarted body's next call fits in what the signed
    $1.00 budget has left (before the fix: two calls billed $1.20, $0.60 booked)."""
    home = setup(tmp_path, budget=1.0)
    record, seen = Journal.record, []

    def dies_at_the_second_write(self, kind, data, **kw):
        if kind in ("genesis.build_failed", "genesis.unbuilt"):
            seen.append(kind)
            if len(seen) == 2:
                raise Killed()
        return record(self, kind, data, **kw)
    monkeypatch.setattr(Journal, "record", dies_at_the_second_write)
    calls = []
    assert boot(home, BillsThenFails(calls))[-1] == "KILLED"
    monkeypatch.setattr(Journal, "record", record)
    boot(home, BillsThenFails(calls), ticks=3)
    committed, row = books(home)
    billed = round(sum(calls), 6)
    assert len(calls) >= 1 and calls[0] == CEILING
    assert committed == billed == row["booked_usd"] == row["build_usd"], (committed, billed, row, calls)
    assert billed <= 1.0 + 1e-9, f"the builder was paid past the signed budget: {calls}"
