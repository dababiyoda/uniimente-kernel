"""A body made by `greg rehearse` never reaches the founder tier, whatever its throwaway key signs.

greg/metrics.py admits that any holder of an enrolled key can sign FOUNDER_TIER directly. The rehearsal key sits on
disk with no passphrase, so a rehearsal could attest itself, and its next closure would then read FOUNDER_TIER and
move `achieved`. greg/rehearsal.py now marks the body in body.json before any key is enrolled, and every MISSION it
signs opens its founder_expression with the [REHEARSAL] label, as it always has. metrics.founder_tier, with
everything it feeds (the path predicates, `achieved`, VEPMC's evidence level, the status surfaces), keeps every
mission of a body marked or labelled either way below the tier: the label also covers a rehearsal body made before
the mark existed, or whose body.json was edited since. The rule is read-side only, and a body that is neither is
unchanged, its residual included. VEPMC's rows are stubbed as in test_path_build_frontier.py, so that what moves
`achieved` is the founder tier alone.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
import stat
from types import SimpleNamespace

from greg import metrics, rehearsal
from greg import path as devpath
from greg.body import Body, send_signed, status
from greg.console import Console, home_parts, render_mission_control
from greg.founder import FOUNDER_TIER_BODY, load_founder_key
from tests.greg_fixtures import make_body, mission, note_check, workspace

ROOT = Path(__file__).resolve().parents[2]


def note(home, mid: str) -> dict:
    target = workspace(home, mid) / "n.txt"
    return mission(mid, checks=[note_check("n", target, "x")], strategies=[], capabilities=["fs.read"],
                   ceiling="read_only")


def counted(monkeypatch, *missions):
    """VEPMC's rows stubbed so each mission is a structurally complete closure."""
    rows = {"VEPMC": len(missions), "external_confirmation_required": "x",
            "missions": [{"mission_id": m, "counts": True, "missing": []} for m in missions]}
    monkeypatch.setattr(metrics, "vepmc", lambda journal: rows)


def self_attest_then_sign(home, key, mid: str, monkeypatch) -> dict:
    """The body's own key signs FOUNDER_TIER directly (no CLI, no passphrase), then a MISSION; what the ledger says."""
    with Body(home) as body:
        body.boot()
        send_signed(home, key, "FOUNDER_TIER", dict(FOUNDER_TIER_BODY))
        body.tick()
        send_signed(home, key, "MISSION", note(home, mid))
        body.tick()
        journal = body.journal
        counted(monkeypatch, mid)
        return {"attested": [c for c in (e.payload for e in journal.replay("command.accepted"))
                             if c.get("kind") == "FOUNDER_TIER"],
                "tiers": metrics.founder_tier(journal), "where": devpath.position(journal),
                "built": devpath.build_status(journal), "journal": journal}


def test_a_rehearsal_body_never_reaches_the_founder_tier_and_achieved_does_not_move(tmp_path, monkeypatch):
    marked_at_enrolment, enroll = [], Body.enroll_founder

    def watched_enroll(self, public_hex):
        marked_at_enrolment.append(bool(json.loads(self.layout.config.read_text()).get("rehearsal")))
        return enroll(self, public_hex)
    monkeypatch.setattr(Body, "enroll_founder", watched_enroll)
    umask = os.umask(0o022)                       # the mark keeps body.json private whatever the umask
    try:
        result = rehearsal.rehearse(directory=tmp_path / "r", kernel_root=ROOT, with_venture=False)
    finally:
        os.umask(umask)
    assert result["state"] == "ACHIEVED" and result["appraisal"] == "VERIFIED"    # the rehearsal itself still runs
    home, mid = Path(result["home"]), "m:self-attested"
    seen = self_attest_then_sign(home, load_founder_key(result["throwaway_key"], None), mid, monkeypatch)
    assert seen["attested"]                       # read-side only: the body still accepts the attestation
    assert seen["tiers"][mid]["tier"] == metrics.STRUCTURAL_CANDIDATE, seen["tiers"][mid]
    where, built = seen["where"], seen["built"]
    assert where["achieved"] == built["achieved"] == ["N0"] and where["active"]["id"] == "N1"
    n1 = where["active"]["measurement"]
    assert n1["structurally_met"] and not n1["met"] and n1["evidence_level"] == metrics.STRUCTURAL_CANDIDATE
    assert built["build_frontier"]["id"] == "N2"   # the build axis still counts the structure
    assert seen["tiers"][mid]["why_not"] == metrics.REHEARSAL_BODY
    assert n1["not_founder_tier"] == {mid: metrics.REHEARSAL_BODY}
    assert {t["why_not"] for t in seen["tiers"].values()} == {metrics.REHEARSAL_BODY}   # the rehearsal's own too
    # The mark: written by the rehearsal path before the key was enrolled, and body.json stays private.
    assert metrics.rehearsal_body(seen["journal"]) and marked_at_enrolment == [True]
    config = json.loads((home / "body.json").read_text())
    assert config[metrics.REHEARSAL_MARK]["created_by"] == "greg rehearse"
    assert stat.S_IMODE((home / "body.json").stat().st_mode) == 0o600
    assert not (home / "body.json.rehearsal-tmp").exists()
    tier = status(home)["founder_tier"]           # the status surface says why, and points at another body
    assert tier["enrolled_key_attested"] is True and tier["rehearsal_body"] is True
    assert tier["consequence"] == metrics.REHEARSAL_BODY and tier["how"] == metrics.REHEARSAL_HOW


def test_a_rehearsal_body_made_before_the_mark_is_known_by_the_label_in_its_ledger(tmp_path, monkeypatch):
    """Every `greg rehearse` body signs its First Mission as "[REHEARSAL] ...". A body made before the body.json mark
    existed has no mark (nor has one whose body.json was edited), and its own key's self-attestation still leaves it
    below the tier, because the label sits in the hash-chained ledger (review finding MWA-ATK-1)."""
    result = rehearsal.rehearse(directory=tmp_path / "r", kernel_root=ROOT, with_venture=False)
    home, mid = Path(result["home"]), "m:self-attested-old-rehearsal"
    config = json.loads((home / "body.json").read_text())
    config.pop(metrics.REHEARSAL_MARK)            # body.json exactly as init_body wrote it, before this change
    (home / "body.json").write_text(json.dumps(config, indent=2))
    seen = self_attest_then_sign(home, load_founder_key(result["throwaway_key"], None), mid, monkeypatch)
    assert seen["attested"] and seen["tiers"][mid]["tier"] == metrics.STRUCTURAL_CANDIDATE, seen["tiers"][mid]
    assert seen["where"]["achieved"] == seen["built"]["achieved"] == ["N0"] and seen["where"]["active"]["id"] == "N1"
    tier = status(home)["founder_tier"]
    assert tier["enrolled_key_attested"] is True and tier.get("rehearsal_body") is True, tier
    assert tier["consequence"] == metrics.REHEARSAL_BODY and tier["how"] == metrics.REHEARSAL_HOW
    assert seen["tiers"][mid]["why_not"] == metrics.REHEARSAL_BODY
    journal = seen["journal"]
    assert not metrics.rehearsal_marked(journal) and metrics.rehearsal_body(journal)


def sign_mission(home, key, mid: str, expression: str) -> None:
    spec = note(home, mid)
    spec["founder_expression"] = expression
    with Body(home) as body:
        body.boot()
        send_signed(home, key, "MISSION", spec)
        body.tick()


def test_the_label_marks_the_whole_body_only_when_it_opens_a_missions_expression(tmp_path):
    """The label is the founder key's own signed word that a MISSION is a rehearsal, so it settles the body, every
    mission before it included. The same text anywhere else in an expression is prose, and marks nothing. The label
    is spelled out, not read from greg.rehearsal: it is what bodies made earlier carry, so it must never change."""
    (tmp_path / "labelled").mkdir()
    home, key, _, _ = make_body(tmp_path / "labelled")
    with Body(home) as body:
        body.boot()
        send_signed(home, key, "FOUNDER_TIER", dict(FOUNDER_TIER_BODY))
        body.tick()
    sign_mission(home, key, "m:before", "an ordinary mission, signed after the attestation")
    with Body(home) as body:
        assert metrics.founder_tier(body.journal)["m:before"]["tier"] == metrics.FOUNDER_TIER
    sign_mission(home, key, "m:rehearsal", "[REHEARSAL] Run the Founder's First Mission with a throwaway key.")
    with Body(home) as body:
        journal = body.journal
        tiers = metrics.founder_tier(journal)
        assert {m: t["tier"] for m, t in tiers.items()} == {"m:before": metrics.STRUCTURAL_CANDIDATE,
                                                            "m:rehearsal": metrics.STRUCTURAL_CANDIDATE}, tiers
        assert {m: t["why_not"] for m, t in tiers.items()} == {"m:before": metrics.REHEARSAL_BODY,
                                                               "m:rehearsal": metrics.REHEARSAL_BODY}
        assert not metrics.rehearsal_marked(journal) and metrics.rehearsal_body(journal)
    assert status(home)["founder_tier"]["rehearsal_body"] is True

    (tmp_path / "prose").mkdir()
    prose, key2, _, _ = make_body(tmp_path / "prose")
    with Body(prose) as body:
        body.boot()
        send_signed(prose, key2, "FOUNDER_TIER", dict(FOUNDER_TIER_BODY))
        body.tick()
    sign_mission(prose, key2, "m:prose", "Explain what the [REHEARSAL] label on a rehearsal means")
    with Body(prose) as body:
        assert metrics.rehearsal_body(body.journal) is False
        assert metrics.founder_tier(body.journal)["m:prose"]["tier"] == metrics.FOUNDER_TIER
    assert "rehearsal_body" not in status(prose)["founder_tier"]


def test_every_founder_surface_says_a_rehearsal_body_is_one_and_never_shows_an_empty_command(tmp_path):
    """The home banner (greg/console.py) renders ``how`` as the command to run, and Mission Control's Proof row
    renders the tier (review findings MWA-ATK-2 and MWA-FID-1: both printed ``Run <code></code>``)."""
    home, key, _, _ = make_body(tmp_path)
    rehearsal.mark_body(home)
    for attested in (False, True):
        if attested:                              # the throwaway key attests itself; nothing on the surface changes
            with Body(home) as body:
                body.boot()
                send_signed(home, key, "FOUNDER_TIER", dict(FOUNDER_TIER_BODY))
                body.tick()
        console = Console(home, key=None)
        banner = home_parts(console).get("founder_tier", "")
        proof = render_mission_control(console, "proof").decode()
        row = re.search(r"<td>Founder tier</td><td>(.*?)</td></tr>", proof).group(1)    # the Proof table's row
        assert "<code></code>" not in banner + row, (attested, banner, row)
        assert "greg founder attest --key ~/.greg-founder.pem (asks your passphrase)" not in banner + row
        assert "rehearsal body" in row and "attested since" not in row and "not attested" not in row
        assert ("signed FOUNDER_TIER" in row) is attested
        if attested:
            assert banner == ""                   # the banner is for an unattested key only (greg/console.py)
        else:
            assert "never reaches the founder tier" in banner
        for text in (banner, row) if not attested else (row,):
            assert "greg --home &lt;a new home&gt; init" in text


def test_a_body_that_is_not_marked_is_unchanged_residual_included(tmp_path, monkeypatch):
    """The same direct self-attestation on an unmarked body still reaches the tier (the residual
    test_greg_closure_integrity.py pins): this rule narrows rehearsal bodies only."""
    home, key, _, _ = make_body(tmp_path)
    assert "rehearsal" not in json.loads((home / "body.json").read_text())
    seen = self_attest_then_sign(home, key, "m:unmarked", monkeypatch)
    assert seen["tiers"]["m:unmarked"]["tier"] == metrics.FOUNDER_TIER
    assert seen["where"]["achieved"] == ["N0", "N1"] and seen["where"]["active"]["id"] == "N2"
    assert metrics.rehearsal_body(seen["journal"]) is False
    tier = status(home)["founder_tier"]
    assert tier["enrolled_key_attested"] is True and "rehearsal_body" not in tier and "consequence" not in tier


def at(folder: Path, body_json: str | bytes | None):
    """A journal stand-in whose ledger file sits in ``folder`` beside ``body_json`` (None: no body.json there)."""
    folder.mkdir(parents=True)
    if isinstance(body_json, str):
        (folder / "body.json").write_text(body_json)
    elif isinstance(body_json, bytes):
        (folder / "body.json").write_bytes(body_json)
    return SimpleNamespace(ledger=SimpleNamespace(path=str(folder / "ledger.jsonl")))


def test_the_mark_is_read_beside_the_ledger_and_an_unreadable_config_never_grants_the_tier(tmp_path):
    assert metrics.rehearsal_body(None) is False and metrics.rehearsal_marked(None) is False
    assert metrics.rehearsal_marked(SimpleNamespace(ledger=SimpleNamespace(path=None))) is False   # in memory
    assert metrics.rehearsal_marked(SimpleNamespace(ledger=SimpleNamespace())) is False
    cases = {"no body.json": (None, False), "plain": ('{"body_id": "b"}', False),
             "marked": ('{"rehearsal": {"created_by": "greg rehearse"}}', True),
             "not json": ("{not json", True), "not an object": ("[1, 2]", True), "not text": (b"\xff\xfe\x00", True)}
    for i, (name, (content, marked)) in enumerate(cases.items()):
        assert metrics.rehearsal_marked(at(tmp_path / str(i), content)) is marked, name
    unreadable = at(tmp_path / "dir", None)
    (Path(unreadable.ledger.path).parent / "body.json").mkdir()          # read_text raises an OSError
    assert metrics.rehearsal_marked(unreadable) is True
