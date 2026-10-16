"""Fourth review of the Track B merge (V1): a venture memo answers only the mission whose economics it was
computed from.

Track B made a memo's revenue section depend on the signed economics, but the ``assessed`` check still matched
any memo for the manifest. A mission signed with economics closed on a memo that stated no revenue figure (or
on a memo another mission built from different economics), and its appraisal passed vacuously because it never
ran ``assess-venture`` itself.
"""
from __future__ import annotations

import json
from pathlib import Path

from greg import ventures
from greg.body import Body, Layout
from greg.templates import venture_assessment
from tests.greg_fixtures import Clock, drop, make_body, signed
from tests.unit.test_greg_ventures import ECONOMICS, _ctx, _tick_until, _write, organs  # noqa: F401 (fixture)

OTHER = {**ECONOMICS, "revenue": {**ECONOMICS["revenue"], "factors": [
    {"name": "brokers", "low": 2000, "central": 6000, "high": 15000, "units": {"broker": 1}},
    *ECONOMICS["revenue"]["factors"][1:]]}}


def memos(home):
    folder = Layout(home).home / "deliveries" / "ventures"
    return {p.name: p.read_text() for p in sorted(folder.glob("venture-*.md"))} if folder.is_dir() else {}


def assessed_runs(body, mission_id):
    return [e.payload for e in body.journal.replay("mission.action") if e.payload.get("mission_id") == mission_id
            and e.payload.get("action_id") == "assess-venture" and e.payload.get("status") == "DONE"]


def test_missions_with_different_economics_are_different_missions_with_their_own_questions(organs):
    plain, priced, other = (venture_assessment(**organs), venture_assessment(**organs, economics=ECONOMICS),
                            venture_assessment(**organs, economics=OTHER))
    assert len({plain["mission_id"], priced["mission_id"], other["mission_id"]}) == 3
    ask = lambda spec: {s["params"]["problem_id"] for s in spec["strategies"] if s["capability"] == "cognition.solve"}
    assert ask(priced) and ask(other) and not ask(priced) & ask(other)
    status = lambda spec: next(c for c in spec["success_checks"] if c["check_id"] == "assessed")["sensor"]["params"]
    assert status(plain)["economics_sha256"] is None
    assert status(priced)["economics_sha256"] != status(other)["economics_sha256"]


def test_economics_added_later_get_their_own_memo_instead_of_closing_on_the_old_one(tmp_path, organs):
    home, key, body_id, _ = make_body(tmp_path)
    clock = Clock()
    plain = venture_assessment(**organs, preauthorize_delivery=True)
    drop(home, signed(key, body_id, "MISSION", plain))
    with Body(home, clock=clock) as body:
        body.boot()
        _tick_until(body, clock, "ACHIEVED")
    [first] = memos(home).values()
    assert "no revenue figure is stated" in first and "- Economics: none stated" in first
    _write(Path(organs["manifest"]).with_name("economics.json"), json.dumps(ECONOMICS))
    standing = venture_assessment(**organs, standing=True, cadence_seconds=60, preauthorize_delivery=True)
    drop(home, signed(key, body_id, "MISSION", standing))
    with Body(home, clock=clock) as body:
        for _ in range(8):
            clock.advance(30)
            body.tick()
            if assessed_runs(body, standing["mission_id"]):
                break
        assert assessed_runs(body, standing["mission_id"]), "the economics mission never assessed its own memo"
    texts = list(memos(home).values())
    assert len(texts) == 2 and first in texts
    priced = next(t for t in texts if t != first)
    assert "Estimate: 24000 to 720000 USD year^-1" in priced
    basis = next(c for c in standing["success_checks"] if c["check_id"] == "assessed")["sensor"]["params"]
    assert f"- Economics: {basis['economics_sha256']}" in priced


def test_a_memo_from_other_economics_does_not_close_a_mission(tmp_path, organs):
    home, key, body_id, _ = make_body(tmp_path)
    clock = Clock()
    standing = venture_assessment(**organs, economics=ECONOMICS, standing=True, cadence_seconds=60,
                                  preauthorize_delivery=True)
    drop(home, signed(key, body_id, "MISSION", standing))
    with Body(home, clock=clock) as body:
        body.boot()
        for _ in range(8):
            clock.advance(30)
            body.tick()
            if assessed_runs(body, standing["mission_id"]):
                break
    bounded = venture_assessment(**organs, economics=OTHER, preauthorize_delivery=True)
    drop(home, signed(key, body_id, "MISSION", bounded))
    with Body(home, clock=clock) as body:
        for _ in range(10):
            clock.advance(30)
            body.tick()
            body.engine.book.rebuild()
            if body.engine.book.missions[bounded["mission_id"]].status == "ACHIEVED":
                break
        assert body.engine.book.missions[bounded["mission_id"]].status == "ACHIEVED"
        assert assessed_runs(body, bounded["mission_id"]), "closed on a memo it never assessed"
        appraisal = [e.payload for e in body.journal.replay("mission.appraised")
                     if e.payload["mission_id"] == bounded["mission_id"]][-1]
        assert appraisal["verdict"] == "VERIFIED", appraisal["findings"]
    texts = list(memos(home).values())
    assert len(texts) == 2
    assert sum("Estimate: 24000 to 720000 USD year^-1" in t for t in texts) == 1


def test_a_mission_signed_before_the_binding_still_matches_by_manifest(tmp_path, organs):
    """Specs already on a body carry no economics_sha256: the sensor keeps matching them by manifest alone."""
    ctx = _ctx(tmp_path, [Path(organs["manifest"]).parent])
    folder = tmp_path / "out" / "ventures"
    folder.mkdir(parents=True)
    import hashlib
    digest = hashlib.sha256(Path(organs["manifest"]).read_bytes()).hexdigest()
    (folder / "venture-legacy.md").write_text(f"**Binding verdict: kill**\n- Signal: manifest {digest}\n")
    assert ventures.status({"manifest": organs["manifest"]}, ctx)["assessed"] is True
    assert ventures.status({"manifest": organs["manifest"], "economics_sha256": None}, ctx)["assessed"] is True
    assert ventures.status({"manifest": organs["manifest"], "economics_sha256": "sha256:" + "1" * 64},
                           ctx)["assessed"] is False
