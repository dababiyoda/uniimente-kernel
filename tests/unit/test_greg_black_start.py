"""greg/black_start.py in-process (acceptance H.G13). The real-process scenario is
tests/integration/test_greg_recovery_scenarios_process.py::test_black_start_environment."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from types import SimpleNamespace

import pytest

from greg import black_start
from greg.founder import generate_founder_key, stamp
from tests.greg_fixtures import make_body


def test_a_checkout_whose_constitution_is_not_the_ratified_one_escalates(tmp_path, monkeypatch):
    """The ledger and body.json agree with each other, but the constitution this checkout compiles is another one:
    stage 2's constitution_hash_matches_ratified_version fails, so the outcome is to escalate, exit 3."""
    home, *_ = make_body(tmp_path)
    import compiler.ucl_compiler as ucl
    monkeypatch.setattr(ucl, "compile_constitution",
                        lambda root: SimpleNamespace(constitution_hash="sha256:" + "1" * 64))
    report = black_start.assess(home)
    assert report["integrity"]["chain_verified"] and not report["integrity"]["constitution_matches"]
    assert report["outcome"] == black_start.ESCALATE and black_start.exit_code(report) == 3
    assert "constitution this checkout compiles" in black_start.notification(report)["text"]


def test_a_body_that_never_ran_is_shown_down_with_nothing_to_revoke(tmp_path):
    home, *_ = make_body(tmp_path)
    report = black_start.assess(home)
    assert report["outcome"] == "shown_down" and black_start.exit_code(report) == 0
    assert report["shutdown"]["why"] == "the body never ran a main loop"
    assert report["credentials"]["device_delegations"] == [] and report["credentials"]["nodes"] == []
    assert len(report["credentials"]["founder_keys"]) == 1


def test_an_expired_delegation_is_still_listed_for_revocation(tmp_path):
    """Expiry is enforced at verification, on a clock a recovered copy may not trust: the core lists it anyway."""
    from greg.body import Body
    from tests.greg_fixtures import signed
    now = datetime.now(timezone.utc)
    home, key, body_id, _ = make_body(tmp_path)
    phone = generate_founder_key(tmp_path / "phone.pem", None)
    with Body(home) as body:
        body.apply(signed(key, body_id, "DEVICE_ENROLL", {"public_key": phone, "label": "old phone",
                                                          "kinds": ["DECISION"],
                                                          "expires_at": stamp(now + timedelta(days=1))}))
    listed = black_start.assess(home, now=now + timedelta(days=60))["credentials"]["device_delegations"]
    assert [d["label"] for d in listed] == ["old phone"]


def test_not_a_body_home_is_refused(tmp_path):
    with pytest.raises(black_start.BlackStartError, match="not a body home"):
        black_start.assess(tmp_path)


def test_the_notification_never_lands_in_the_home(tmp_path):
    home, *_ = make_body(tmp_path)
    report = black_start.assess(home)
    for inside in (home / "n.json", home / "inbox" / "n.json"):
        with pytest.raises(black_start.BlackStartError, match="outside the assessed home"):
            black_start.write_notification(report, inside)
    written = black_start.write_notification(report, tmp_path / "n.json")
    assert json.loads(written.read_text())["reality_status"] == black_start.NOT_SENT
    with pytest.raises(FileExistsError):
        black_start.write_notification(report, written)
