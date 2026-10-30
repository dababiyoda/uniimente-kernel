"""Directive section 29: "Blocked goals remain durable. Store: blocker, why blocked, reconsideration condition,
required evidence, required authority, next possible move."

The engine already keeps every blocker on the journal and already decides when one is resolved
(``MissionEngine._blocker_resolved``); ``greg.blockers`` types each open one into those six fields plus its mission,
kind, recording time and source event. Every blocker type greg/missions.py raises is built here on a real body the
way the other mission tests build them (signed commands with a per-test key, an in-process Body with a test clock),
and its record must carry every field, an explicit "none required: <reason>" where a field does not apply. A
blocker the engine's own rule treats as resolved is not listed; the CLI, the morning report and Mission Control show
the module's records. The founder key is a per-test key, not Alfonso's. Reality: UNIT-TESTED (SANDBOX body).
"""
from __future__ import annotations

import contextlib
import io
import json

import pytest

from greg.body import Body, Layout, morning_projection, observe
from greg.capabilities import CapabilityError, SecretBroker
from greg.templates import human_work
from tests.greg_fixtures import Clock, drop, make_body, mission, note_check, signed, workspace, write_strategy

FIELDS = ("mission_id", "kind", "blocker", "why", "reconsider_when", "required_evidence", "required_authority",
          "next_move", "since", "source_event")
SECRET = "sk-test-PLANTED-0b6d2c1f9e8a7d6c5b4a3928"


def records(home, **kw):
    from greg import blockers
    with observe(home, actor="spiffe://uniimente.internal/greg/test-reader") as journal:
        return blockers.open_blockers(journal, home=home, **kw)


def ticks(home, clock, n, *, step=1, setup=None):
    with Body(home, clock=clock) as body:
        if setup is not None:
            setup(body)
        for _ in range(n):
            body.tick()
            clock.advance(step)


def sub(tmp_path, name):
    path = tmp_path / name
    path.mkdir()
    return path


def complete(record):
    assert tuple(record) == FIELDS
    for name, value in record.items():
        assert isinstance(value, str) and value.strip(), name
        if value.startswith("none required"):
            assert value.startswith("none required: ") and len(value) > len("none required: ") + 10, name


# -- one real body per blocker type ---------------------------------------------------------------------------

def paid_approval(tmp_path):
    """decision / APPROVAL with resource spend: the budget stop (greg/missions.py _spend_ask)."""
    home, key, body_id, _ = make_body(tmp_path)
    ws = workspace(home, "m:paid")
    drop(home, signed(key, body_id, "MISSION", mission(
        "m:paid", checks=[note_check("filed", ws / "f.txt", "filed")],
        strategies=[write_strategy("file", "f.txt", "filed", ["filed"], cost_usd=0.5)],
        capabilities=["fs.read"], budget=1.0)))                             # fs.write is outside the cone
    clock = Clock()
    ticks(home, clock, 4)
    return home, key, body_id, clock, "m:paid"


def expired_mandate(tmp_path):
    """decision / SCOPE_RENEWAL, a kind no DECISION can lift."""
    home, key, body_id, _ = make_body(tmp_path)
    ws = workspace(home, "m:old")
    drop(home, signed(key, body_id, "MISSION", mission(
        "m:old", checks=[note_check("c", ws / "c.txt", "x")], strategies=[], capabilities=["fs.read"])))
    clock = Clock()
    ticks(home, clock, 1)
    clock.advance(3 * 86400)                                              # past the 2-day horizon
    ticks(home, clock, 1)
    return home, key, body_id, clock, "m:old"


def interrupted_write(tmp_path):
    """reconciliation: a non-retry-safe dispatch whose completion is unknown."""
    home, key, body_id, _ = make_body(tmp_path)
    note = workspace(home, "m:twice") / "c.txt"
    drop(home, signed(key, body_id, "MISSION", mission(
        "m:twice", checks=[note_check("c", note, "ok")], strategies=[write_strategy("w", "c.txt", "ok", ["c"])],
        capabilities=["fs.read", "fs.write"])))
    clock = Clock()

    def explode(body):
        def adapter(params, ctx):
            raise RuntimeError("power lost mid-effect")
        body.registry.adapters["fs.write"] = adapter
    ticks(home, clock, 3, setup=explode)
    return home, key, body_id, clock, "m:twice"


def missing_capability(tmp_path):
    """capability: a sensor function nothing on the body serves (the Genesis search fails)."""
    home, key, body_id, data = make_body(tmp_path)
    (data / "e.bin").write_bytes(b"x")
    check = {"check_id": "h", "description": "d", "sensor": {"function": "no.such.function",
             "params": {"path": str(data / "e.bin")}, "target": "fs:e.bin"},
             "predicate": {"op": "exists", "field": "x"}}
    drop(home, signed(key, body_id, "MISSION", mission("m:cap", checks=[check], strategies=[],
                                                          capabilities=["fs.read"], ceiling="read_only")))
    clock = Clock()
    ticks(home, clock, 3)
    return home, key, body_id, clock, "m:cap"


def person_step(tmp_path):
    """human_work: work only a person may do."""
    home, key, body_id, _ = make_body(tmp_path)
    spec = human_work(function="professional.legal_review", purpose="Have my lease reviewed before I sign it",
                      deliverable="lease-review.pdf", workspace_root=Layout(home).workspace)
    drop(home, signed(key, body_id, "MISSION", spec))
    clock = Clock()
    ticks(home, clock, 4)
    return home, key, body_id, clock, spec["mission_id"]


def host_outage(tmp_path, outages=1):
    """outage: the host failed while Genesis was forming the missing function (a back-off, then a re-run)."""
    home, key, body_id, data = make_body(tmp_path)
    (data / "e.bin").write_bytes(b"x")
    check = {"check_id": "h", "description": "d", "sensor": {"function": "no.such.function",
             "params": {"path": str(data / "e.bin")}, "target": "fs:e.bin"},
             "predicate": {"op": "exists", "field": "x"}}
    drop(home, signed(key, body_id, "MISSION", mission("m:outage", checks=[check], strategies=[],
                                                          capabilities=["fs.read"], ceiling="read_only")))
    clock = Clock()

    def down(body):
        def resolve(**kw):
            raise CapabilityError("runner timed out (host under load)", failure_class="transient")
        body.engine.genesis.resolve = resolve
    ticks(home, clock, outages, step=3601, setup=down)          # each tick past the back-off re-runs the search
    return home, key, body_id, clock, "m:outage"


def unobservable_sensor(tmp_path):
    """no_strategy: a check whose sensor is not read-only (greg/missions.py _observe)."""
    home, key, body_id, _ = make_body(tmp_path)
    check = {"check_id": "c", "description": "d", "predicate": {"op": "exists", "field": "path"},
             "sensor": {"capability": "fs.write", "params": {"relative_path": "s.txt", "content": "x"},
                        "target": "workspace:s.txt"}}
    drop(home, signed(key, body_id, "MISSION", mission("m:nostrat", checks=[check], strategies=[],
                                                          capabilities=["fs.read", "fs.write"])))
    clock = Clock()
    ticks(home, clock, 1)
    return home, key, body_id, clock, "m:nostrat"


SHOWN = [(paid_approval, "decision"), (expired_mandate, "decision"), (interrupted_write, "reconciliation"),
         (missing_capability, "capability"), (person_step, "human_work"), (host_outage, "outage")]


# -- fail-before: the outage blocker had no required authority anywhere --------------------------------------

def test_an_outage_blocker_names_its_required_authority_in_the_morning_report(tmp_path):
    home, *_, mid = host_outage(tmp_path)
    report = morning_projection(home)
    [shown] = [r for r in report["blockers"] if r["mission_id"] == mid]
    assert shown["kind"] == "outage"
    assert shown["required_authority"].startswith("none required: ")
    assert "asks for no new authority" in shown["required_authority"]
    assert shown["required_evidence"].startswith("none required: ")
    assert "retry_at" not in shown and "after 20" in shown["reconsider_when"]   # the back-off time, typed


def test_a_long_outage_still_needs_no_authority_and_names_the_ask_the_founder_was_told_of(tmp_path):
    from greg.missions import MissionEngine
    home, *_, mid = host_outage(tmp_path, outages=MissionEngine.OUTAGE_DEFERRALS)
    [record] = records(home)
    complete(record)
    assert f"consecutive outage {MissionEngine.OUTAGE_DEFERRALS}" in record["blocker"]
    rid = record["next_move"].split("ask ", 1)[1].split()[0]
    assert rid.startswith("req-") and rid in record["required_authority"]
    assert record["required_authority"].startswith("none required: ")
    with observe(home, actor="spiffe://uniimente.internal/greg/test-reader") as journal:
        blocked = [e for e in journal.replay("mission.blocked") if e.payload["mission_id"] == mid]
    assert len(blocked) == MissionEngine.OUTAGE_DEFERRALS            # one per outage: the record cites the latest
    assert record["source_event"] == blocked[-1].event_id and record["since"] == blocked[-1].occurred_at


# -- every blocker type: one record, every field ----------------------------------------------------------------

@pytest.mark.parametrize("build,kind", SHOWN, ids=[k + ":" + b.__name__ for b, k in SHOWN])
def test_each_blocker_type_yields_one_record_with_every_field(tmp_path, build, kind):
    home, *_, mid = build(tmp_path)
    rows = records(home)
    [record] = [r for r in rows if r["mission_id"] == mid]
    assert record["kind"] == kind
    complete(record)
    with observe(home, actor="spiffe://uniimente.internal/greg/test-reader") as journal:
        [blocked] = [e for e in journal.replay("mission.blocked") if e.event_id == record["source_event"]]
        assert blocked.payload["mission_id"] == mid and blocked.occurred_at == record["since"]
        from greg.missions import MissionBook
        assert MissionBook(journal).missions[mid].blocker == blocked.payload["blocker"]
    assert records(home, mission_id=mid) == [record] and records(home, mission_id="m:nobody") == []


def test_the_typed_fields_say_what_each_kind_needs(tmp_path):
    home, *_, mid = paid_approval(tmp_path)
    [paid] = records(home, mission_id=mid)
    assert "APPROVAL" in paid["blocker"] and "$0.50 for this one action" in paid["blocker"]
    assert "founder-signed DECISION" in paid["required_authority"] and '"cost_usd": 0.5' in paid["required_authority"]
    assert "greg decide" in paid["next_move"] and "awaiting founder" in paid["required_evidence"]

    home, *_, mid = expired_mandate(sub(tmp_path, "renewal"))
    [renew] = records(home, mission_id=mid)
    assert "SCOPE_RENEWAL" in renew["blocker"] and renew["required_evidence"].startswith("none required: ")
    assert "sign a new MISSION" in renew["required_authority"] and "Approve or Reject cannot renew" in renew["next_move"]

    home, *_, mid = person_step(sub(tmp_path, "person"))
    [person] = records(home, mission_id=mid)
    assert person["required_authority"].startswith("none required: ") and "pays no one" in person["required_authority"]
    assert "deliverable_present" in person["required_evidence"]

    home, *_, mid = missing_capability(sub(tmp_path, "cap"))
    [cap] = records(home, mission_id=mid)
    assert "no.such.function" in cap["blocker"] and "CAPABILITY_ATTACH" in cap["required_authority"]

    home, *_, mid = interrupted_write(sub(tmp_path, "rec"))
    [rec] = records(home, mission_id=mid)
    assert "reconcile_executed" in rec["required_evidence"] and "attempt 0" in rec["blocker"]


def test_a_paused_mission_says_so_first(tmp_path):
    home, key, body_id, clock, mid = paid_approval(tmp_path)
    drop(home, signed(key, body_id, "LIFECYCLE", {"mission_id": mid, "state": "PAUSED", "reason": "not now"}))
    with Body(home, clock=clock) as body:
        body.ingest_inbox()
    [record] = records(home)
    assert record["next_move"].startswith("the mission is paused; nothing moves until a signed LIFECYCLE ACTIVE")


def test_a_self_clearing_no_strategy_blocker_is_typed_but_not_listed(tmp_path):
    """greg/missions.py ``_blocker_resolved`` treats no_strategy as resolved ("re-evaluate strategies at cadence"):
    the next tick lifts it and re-observes, and re-raises it while the sensor is still not read-only. The
    projection reuses that rule, so the blocker is not listed; its typing is still complete."""
    from greg import blockers
    home, *_, mid = unobservable_sensor(tmp_path)
    assert [r for r in records(home) if r["mission_id"] == mid] == []
    with observe(home, actor="spiffe://uniimente.internal/greg/test-reader") as journal:
        engine = blockers.resolution_engine(journal, home)
        m = engine.book.missions[mid]
        assert m.blocker["type"] == "no_strategy"
        assert engine._blocker_resolved(m) == (True, "re-evaluate strategies at cadence")
        event = [e for e in journal.replay("mission.blocked") if e.payload["mission_id"] == mid][-1]
        record = blockers.typed(m, engine.book, "re-evaluate strategies at cadence", event)
    complete(record)
    assert record["kind"] == "no_strategy" and "not read-only" in record["why"]


# -- a resolved blocker disappears ------------------------------------------------------------------------------

def test_an_answered_decision_disappears_before_the_next_tick_lifts_it(tmp_path):
    home, key, body_id, clock, mid = paid_approval(tmp_path)
    [record] = records(home)
    rid = record["blocker"].split("ask ", 1)[1].split()[0]
    drop(home, signed(key, body_id, "DECISION", {"request_id": rid, "answer": "approve"}))
    with Body(home, clock=clock) as body:
        body.ingest_inbox()
        assert body.engine.book.missions[mid].blocker["request_id"] == rid      # still held in the fold
    assert records(home) == []                                                  # but the engine's rule resolves it
    ticks(home, clock, 4)
    assert records(home) == []


def test_an_observed_deliverable_lifts_the_person_step(tmp_path):
    home, key, body_id, clock, mid = person_step(tmp_path)
    assert [r["kind"] for r in records(home)] == ["human_work"]
    deliverable = Layout(home).workspace / mid.replace(":", "_") / "lease-review.pdf"
    deliverable.parent.mkdir(parents=True, exist_ok=True)
    deliverable.write_bytes(b"%PDF reviewed")
    ticks(home, clock, 3, step=3700)
    assert records(home) == []


def test_the_engines_own_resolution_rule_decides_what_is_listed(tmp_path, monkeypatch):
    """No copy of the rule: ``MissionEngine._blocker_resolved`` is called once per held blocker, and whatever it
    answers decides whether the record is listed."""
    from greg import blockers
    from greg.missions import MissionEngine
    home, *_, mid = missing_capability(tmp_path)
    assert [r["kind"] for r in records(home)] == ["capability"]
    real = MissionEngine._blocker_resolved
    calls = []

    def counted(self, m):
        calls.append(m.mission_id)
        return real(self, m)
    monkeypatch.setattr(MissionEngine, "_blocker_resolved", counted)
    assert len(records(home)) == 1 and calls == [mid]                          # the engine's own rule decides
    monkeypatch.setattr(MissionEngine, "_blocker_resolved", lambda self, m: (True, "served"))
    assert records(home) == []
    with observe(home, actor="spiffe://uniimente.internal/greg/test-reader") as journal:
        assert blockers.open_blockers(journal, home=home) == []


def test_an_abandoned_mission_is_no_blocked_goal(tmp_path):
    home, key, body_id, clock, mid = paid_approval(tmp_path)
    drop(home, signed(key, body_id, "LIFECYCLE", {"mission_id": mid, "state": "ABANDONED", "reason": "not needed"}))
    with Body(home, clock=clock) as body:
        body.ingest_inbox()
        assert body.engine.book.missions[mid].blocker is not None              # the fold still holds it
    assert records(home) == []


def test_a_capability_the_founder_attaches_resolves_the_blocker_through_genesis_on_every_surface(tmp_path):
    """The blocker names no capability, only a function; the engine's rule finds the attached one through
    ``Genesis.serving``. The read-only view must hold the body's Genesis (its home found from the ledger when the
    caller gives none), or the morning report keeps listing a blocker the body is about to lift."""
    home, key, body_id, data = make_body(tmp_path)
    (data / "d").mkdir()
    check = {"check_id": "listed", "description": "the folder is listed", "predicate": {"op": "exists",
             "field": "entries"}, "sensor": {"function": "filesystem.list", "params": {"path": str(data / "d")},
                                             "target": "fs:d"}}
    clock = Clock()
    with Body(home, clock=clock) as body:
        body.apply(signed(key, body_id, "CAPABILITY_DETACH", {"capability_id": "fs.list"}))
    drop(home, signed(key, body_id, "MISSION", mission("m:list", checks=[check], strategies=[],
                                                          capabilities=["fs.list"], ceiling="read_only")))
    ticks(home, clock, 3)
    [record] = records(home)
    assert record["kind"] == "capability" and "filesystem.list" in record["blocker"]
    assert [r["mission_id"] for r in morning_projection(home)["blockers"]] == ["m:list"]
    drop(home, signed(key, body_id, "CAPABILITY_ATTACH", {"capability_id": "fs.list"}))
    with Body(home, clock=clock) as body:
        body.ingest_inbox()
        b = body.engine.book.missions["m:list"].blocker
        assert b["type"] == "capability" and b.get("capability_id") is None   # held in the fold until the tick
    assert records(home) == [] and morning_projection(home)["blockers"] == []


def test_a_capability_blocker_that_names_a_detached_capability_says_how_to_attach_it(tmp_path):
    home, key, body_id, data = make_body(tmp_path)
    (data / "d").mkdir()
    check = {"check_id": "listed", "description": "the folder is listed", "predicate": {"op": "exists",
             "field": "entries"}, "sensor": {"capability": "fs.list", "params": {"path": str(data / "d")},
                                             "target": "fs:d"}}
    clock = Clock()
    with Body(home, clock=clock) as body:
        body.apply(signed(key, body_id, "CAPABILITY_DETACH", {"capability_id": "fs.list"}))
    drop(home, signed(key, body_id, "MISSION", mission("m:named", checks=[check], strategies=[],
                                                          capabilities=["fs.list"], ceiling="read_only")))
    ticks(home, clock, 3)
    [record] = records(home)
    complete(record)
    assert record["next_move"].startswith("this blocker names fs.list (now: state DETACHED): attach it with "
                                          "greg attach fs.list")
    assert record["required_evidence"].endswith("now: state DETACHED")


def test_an_incomplete_record_is_refused_never_shown(tmp_path, monkeypatch):
    from greg import blockers
    home, *_ = host_outage(tmp_path)
    good = blockers.TYPES["outage"]
    monkeypatch.setitem(blockers.TYPES, "outage", lambda *a: {**good(*a), "required_authority": "  "})
    with pytest.raises(blockers.BlockerError, match="required_authority"):
        records(home)
    monkeypatch.setitem(blockers.TYPES, "outage", lambda *a: {k: v for k, v in good(*a).items() if k != "why"})
    with pytest.raises(blockers.BlockerError, match="why"):
        records(home)
    with pytest.raises(blockers.BlockerError):
        blockers._none("   ")


# -- no secret value, no secret store ---------------------------------------------------------------------------

def test_no_secret_value_reaches_a_record_and_the_secret_store_is_never_opened(tmp_path, monkeypatch):
    home, *_, mid = host_outage(tmp_path)
    SecretBroker(Layout(home).secrets).put("github_token", SECRET)
    monkeypatch.setenv("GREG_TEST_PLANTED_SECRET", SECRET)
    rows = records(home)
    assert rows and SECRET not in json.dumps(rows)

    def refuse(self, *a, **kw):
        raise AssertionError("the blocker projection opened the secret broker")
    monkeypatch.setattr(SecretBroker, "_file", refuse)
    monkeypatch.setattr(SecretBroker, "resolve", refuse)
    assert records(home) == rows
    out = cli(home)
    assert SECRET not in out and json.loads(out) == rows


# -- the same records on every surface --------------------------------------------------------------------------

def cli(home, *extra) -> str:
    from greg import cli as greg_cli
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        assert greg_cli.main(["--home", str(home), "blockers", *extra]) == 0
    return buffer.getvalue()


def test_the_cli_returns_the_module_records(tmp_path):
    home, *_, mid = person_step(tmp_path)
    rows = records(home)
    assert len(rows) == 1 and json.loads(cli(home)) == rows
    assert json.loads(cli(home, "--mission", mid)) == rows
    assert json.loads(cli(home, "--mission", "m:none")) == []


def test_the_morning_report_and_mission_control_show_the_module_records(tmp_path):
    from greg.console import Console
    from greg.mission_control import projection
    home, *_ = person_step(tmp_path)
    rows = records(home)
    assert morning_projection(home)["blockers"] == rows
    assert projection(Console(home))["blockers"] == rows
    from greg.mission_control import render_view
    page = render_view(Console(home), "goals", {})
    assert "Blocked goals" in page and "professional.legal_review" in page and "deliverable_present" in page
    with Body(home) as body:                                    # the report written from a running body's engine
        from greg.tribunal import morning_report
        assert morning_report(body.journal, body.engine)["blockers"] == rows
