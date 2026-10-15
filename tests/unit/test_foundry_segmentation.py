"""#26 per-identity egress through one governed relay; kernel socket denial; loopback and TEST-NET only."""
import json
import socket
import sys

import pytest

from foundry.systems import module
from foundry.systems.segmentation import (Journal, Relay, SegmentationError, exercise, normalize_policy,
                                          policy_from_manifests, run_confined)


def test_confined_components_reach_only_their_allowlisted_endpoints(tmp_path):
    r = exercise(tmp_path)
    assert r["reader"]["direct_socket"] == r["reader"]["unix_socket"] == "EPERM"      # kernel, not Python
    assert r["reader"]["allowed"] == "OK organ-reply"
    assert r["reader"]["undeclared_testnet"] == r["reader"]["undeclared_port"] == "DENIED"
    assert r["other_identity"]["allowed"] == "DENIED"                                 # per identity
    assert r["never_connected_to_denied"] and r["upstream_connections"] == 1
    assert r["journal_chain"] is True
    assert exercise(tmp_path / "again") == r                                           # re-derivable


def test_journal_tamper_and_removal_are_detected(tmp_path):
    j = Journal(tmp_path / "j.jsonl")
    for i in range(3):
        j.append({"identity": "a", "verdict": "DENIED", "n": i})
    assert j.verify()["intact"]
    lines = j.path.read_text().splitlines()
    j.path.write_text("\n".join([lines[0], lines[2]]) + "\n")
    assert j.verify() == {"intact": False, "broken_at": 1}
    j.path.write_text("\n".join(lines).replace('"DENIED"', '"ALLOWED"', 1) + "\n")
    assert j.verify()["intact"] is False


def test_policy_refuses_wildcards_and_bad_ports_and_external_needs_declaration(tmp_path):
    for bad in ({"x": {"allow": [["*.example", 443]]}}, {"x": {"allow": [["h", 0]]}}, {"": {}}):
        with pytest.raises(SegmentationError):
            normalize_policy(bad)
    relay = Relay({"x": {"allow": [["example.org", 443]]}}, Journal(tmp_path / "j"))
    assert relay.decide("x", "example.org", 443) == "external upstream not declared for this identity"
    assert relay.decide("y", "example.org", 443) == "identity has no egress policy"
    manifests = policy_from_manifests()
    assert manifests["github.pulls"]["allow"] == [["api.github.com", 443]] and manifests["github.pulls"]["external"]


def test_denied_request_never_connects_and_malformed_requests_are_journaled(tmp_path):
    calls = []
    relay = Relay({"x": {"allow": [["127.0.0.1", 9]]}}, Journal(tmp_path / "j"),
                  connect=lambda *a, **k: calls.append(a) or (_ for _ in ()).throw(OSError("no")))
    mine, theirs = socket.socketpair()
    import threading
    t = threading.Thread(target=relay.serve, args=("x", theirs), daemon=True)
    t.start()
    for line in (b"CONNECT 192.0.2.1 443\n", b"GET / HTTP/1.1\n", b"CONNECT 127.0.0.1 9\n"):
        mine.sendall(line)
        assert mine.recv(512)
    mine.close()
    t.join(timeout=5)
    assert calls == [(("127.0.0.1", 9),)]                 # only the allowlisted endpoint was ever attempted
    verdicts = [r["verdict"] for r in relay.journal.read()]
    assert verdicts == ["DENIED", "DENIED", "UPSTREAM_FAILED"]


def test_fail_closed_without_confinement(tmp_path, monkeypatch):
    from foundry.systems import segmentation
    relay = Relay({}, Journal(tmp_path / "j"))
    monkeypatch.setattr(segmentation, "_confine", lambda: segmentation.os._exit(97))
    with pytest.raises(SegmentationError, match="refused"):
        run_confined([sys.executable, "-c", "print(1)"], identity="x", relay=relay, cwd=tmp_path)
    monkeypatch.setattr(segmentation.sys, "platform", "darwin")
    with pytest.raises(SegmentationError, match="Linux"):
        run_confined([sys.executable, "-c", "print(1)"], identity="x", relay=relay, cwd=tmp_path)


def test_registered_on_the_foundry_with_read_only_ops():
    mod = module(26)
    assert set(mod.QUERY_OPS) == {"policy", "journal"} and mod.APPLY_OPS == {}


def test_a_confined_fetch_refuses_header_injection_before_launch(tmp_path):
    from foundry.systems.segmentation import Journal, Relay, SegmentationError, confined_fetch
    relay = Relay({"github.pulls": {"allow": [["api.github.com", 443]], "external": True}}, Journal(tmp_path / "j"))
    for headers in ({"Authorization": "Bearer x\r\nX-Evil: 1"}, {"Host": "elsewhere.test"},
                    {"Bad Name": "x"}, {"Transfer-Encoding": "chunked"}):
        try:
            confined_fetch("https://api.github.com/x", identity="github.pulls", relay=relay, cwd=tmp_path,
                           max_bytes=100, headers=headers)
            raise AssertionError(f"header accepted: {headers}")
        except SegmentationError as exc:
            assert "refused" in str(exc)
    assert Journal(tmp_path / "j").read() == []                 # refused before any connection was asked for
