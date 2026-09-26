"""Verified learning on the real mission path: a learned change is kept only if it wins later.

A daily engineering-brief mission runs through the body. Each morning the founder (a
test key: real Ed25519, not Alfonso's) signs a CRITIQUE labelling what the brief missed
and what was noise. GREG derives the smallest change in what the brief flags, holds it
in shadow, replays it exactly on later briefs' receipted inputs, and keeps it only on a
strict held-out gain. Rejections and reversions stay in the ledger.
"""
from datetime import datetime, timedelta, timezone
import os

import pytest

from greg import briefs, improvement
from greg.body import Body, Layout
from tests.greg_fixtures import Clock, drop, make_body, signed
from tests.unit.test_greg_briefs import _brief_mission, _open_request, _run, github, repo  # noqa: F401 (fixtures)

DRAFT = "acme/kernel#5"          # a draft pull request idle for 30 days: flagged by the baseline brief


class Morning:
    """One founder, one body, one daily brief mission; each call is one morning."""

    def __init__(self, tmp_path, repo_path):
        self.home, self.key, self.body_id, _ = make_body(tmp_path)
        drop(self.home, signed(self.key, self.body_id, "MISSION", _brief_mission(repo_path, daily=True)))
        self.clock = Clock()
        self.body = Body(self.home, clock=self.clock).open()
        self.body.boot()
        _run(self.body, self.clock)
        request = _open_request(self.body)
        drop(self.home, signed(self.key, self.body_id, "DECISION",
                               {"request_id": request["request_id"], "answer": "approve"}))
        self.day = 0

    def brief(self):
        folder = Layout(self.home).home / "deliveries" / "briefs"
        if self.day:
            for path in folder.glob("*.md"):                    # yesterday's brief is a day old
                aged = (datetime.now(timezone.utc) - timedelta(hours=21 + self.day)).timestamp()
                os.utime(path, (aged, aged))
            self.clock.advance(21 * 3600)
        self.day += 1
        states = [t["missions"][0]["state"] for t in _run(self.body, self.clock, 2)]
        assert states[0] == "ACTED", states
        action = [e for e in self.body.journal.replay("mission.action") if e.payload["status"] == "DONE"][-1]
        output = self.body.ledger.find(action.payload["receipt"]).payload["result"]["output"]
        return action, output

    def label(self, action, *, missed=(), noise=()):
        drop(self.home, signed(self.key, self.body_id, "CRITIQUE", {
            "target_event_id": action.event_id, "verdict": "note", "evidence_type": "founder_judgment",
            "text": "morning review of the brief", "attention": {"missed": list(missed), "noise": list(noise)}},
            now=self.clock.now))                                         # signed that morning, by the body's clock
        self.body.tick()
        assert not [e for e in self.body.journal.replay("command.rejected")], "the founder's label was refused"

    def events(self, kind):
        return [e.payload for e in self.body.journal.replay(kind)]


def test_a_correction_becomes_a_change_that_is_kept_only_after_it_wins_on_later_briefs(tmp_path, repo, github):
    m = Morning(tmp_path, repo)
    action, output = m.brief()
    assert DRAFT in briefs.flagged_keys(output["inputs"])            # baseline flags the idle draft
    m.label(action, noise=[DRAFT])                                    # "drafts are noise to me"
    proposed = m.events("improvement.proposed")
    assert len(proposed) == 1 and proposed[0]["state"] == "SHADOW" and proposed[0]["authority_changed"] is False
    assert proposed[0]["policy"]["idle_includes_drafts"] is False
    assert proposed[0]["training"] == {"current_errors": 1, "candidate_errors": 0, "fields_changed": 1}

    for day in range(3):                                              # held out: briefs it was not derived from
        action, output = m.brief()
        assert "attention_policy" not in output["inputs"]            # production still uses the unchanged policy
        assert not m.events("improvement.retained")
        m.label(action, noise=[DRAFT])
    retained = m.events("improvement.retained")
    assert len(retained) == 1 and retained[0]["errors"] == {"current": 3, "candidate": 0}
    assert len(retained[0]["held_out"]) == 3
    assert not set(retained[0]["held_out"]) & set(proposed[0]["derived_from"])

    action, output = m.brief()                                        # the next morning uses what was learned
    assert output["inputs"]["attention_policy"]["idle_includes_drafts"] is False
    assert DRAFT not in briefs.flagged_keys(output["inputs"]) and "local:kernel" in briefs.flagged_keys(output["inputs"])
    text = open(output["path"]).read()
    assert "attention policy:" in text and "(learned;" in text
    ok, detail = briefs.verify_delivery(output, Layout(m.home).home / "deliveries")
    assert ok, detail          # the appraiser's own check: the file is the render of its receipted inputs
    assert len(m.events("decision.requested")) == 1                    # no new approval: same signed scope
    m.label(action)                                                    # founder: this one was right

    report = improvement.report(m.body.journal, m.body.ledger)
    rows = {r["policy"]["idle_includes_drafts"]: r for r in report["by_policy"].values()}
    assert rows[True]["corrections_per_brief"] == 1.0 and rows[True]["briefs"] == 4
    assert rows[False]["corrections_per_brief"] == 0.0 and rows[False]["briefs"] == 1
    m.body.close()


def test_a_change_that_does_not_win_on_later_briefs_is_rejected_and_the_rejection_is_kept(tmp_path, repo, github):
    m = Morning(tmp_path, repo)
    action, _ = m.brief()
    m.label(action, noise=[DRAFT])                                    # one idiosyncratic morning
    for _ in range(3):
        action, _ = m.brief()
        m.label(action)                                               # later mornings: the draft was worth seeing
    rejected = m.events("improvement.rejected")
    assert len(rejected) == 1 and rejected[0]["errors"] == {"current": 0, "candidate": 3}
    assert not m.events("improvement.retained")
    _, output = m.brief()
    assert "attention_policy" not in output["inputs"] and DRAFT in briefs.flagged_keys(output["inputs"])
    assert improvement.report(m.body.journal, m.body.ledger)["rejected"] == [rejected[0]["candidate_id"]]
    m.body.close()


def test_a_kept_change_that_later_loses_is_reverted_and_not_immediately_retried(tmp_path, repo, github):
    m = Morning(tmp_path, repo)
    for _ in range(4):
        action, _ = m.brief()
        m.label(action, noise=[DRAFT])
    assert m.events("improvement.retained")
    for _ in range(3):                                                # the founder's needs changed
        action, output = m.brief()
        assert output["inputs"]["attention_policy"]["idle_includes_drafts"] is False
        m.label(action, missed=[DRAFT])
    reverted = m.events("improvement.reverted")
    assert len(reverted) == 1 and reverted[0]["errors"] == {"retained": 3, "restored": 0}
    action, output = m.brief()
    assert "attention_policy" not in output["inputs"]                 # back to the policy that was replaced
    m.label(action)
    assert len(m.events("improvement.proposed")) == 1                 # the lost change waits for new evidence
    m.body.close()


def test_labels_are_bounded_and_cannot_express_authority(tmp_path, repo, github):
    with pytest.raises(improvement.ImprovementError):
        improvement.validate_labels({"missed": ["a"], "noise": ["a"]})
    with pytest.raises(improvement.ImprovementError):
        improvement.validate_labels({"missed": ["x"] * 51})
    with pytest.raises(improvement.ImprovementError):
        improvement.validate_policy({**briefs.ATTENTION_BASELINE, "budget_usd": 100})
    with pytest.raises(improvement.ImprovementError):
        improvement.validate_policy({**briefs.ATTENTION_BASELINE, "uncommitted_min": 0})
    m = Morning(tmp_path, repo)
    m.brief()
    registered = [e for e in m.body.journal.replay("mission.registered")][0]
    drop(m.home, signed(m.key, m.body_id, "CRITIQUE", {
        "target_event_id": registered.event_id, "verdict": "note", "evidence_type": "founder_judgment",
        "text": "not a brief", "attention": {"missed": [], "noise": []}}, now=m.clock.now))
    m.body.tick()
    assert not m.events("critique.recorded") and not m.events("improvement.proposed")
    m.body.close()


def test_the_founder_labels_from_the_cli_and_reads_the_learning_report(tmp_path, repo, github, capsys):
    import json as _json
    from greg import cli
    m = Morning(tmp_path, repo)
    action, _ = m.brief()
    m.body.close()
    assert cli.main(["--home", str(m.home), "critique", action.event_id, "--verdict", "note",
                     "--evidence-type", "founder_judgment", "--text", "drafts are noise",
                     "--noise", DRAFT, "--key", str(tmp_path / "founder.pem"), "--no-passphrase"]) == 0
    body = Body(m.home, clock=m.clock).open()
    body.tick()
    body.close()
    capsys.readouterr()
    assert cli.main(["--home", str(m.home), "learning"]) == 0
    report = _json.loads(capsys.readouterr().out)
    assert report["labelled_briefs"] == 1 and len(report["proposed"]) == 1
