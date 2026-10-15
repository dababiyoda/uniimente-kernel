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


@pytest.mark.skipif(sys.platform != "linux", reason="seccomp is Linux")
def test_a_replaced_filter_file_cannot_open_sockets_for_a_later_component(tmp_path, monkeypatch):
    """Same class as the run_isolated finding: the component's preexec imported tools/offline_test.py from
    disk at fork time, so whoever could write that file decided whether the next component had sockets.
    The filter is now the one loaded into the body's memory at import."""
    from foundry.systems import segmentation
    kernel = tmp_path / "kernel"
    (kernel / "tools").mkdir(parents=True)
    (kernel / "tools" / "offline_test.py").write_text("def install_filter():\n    pass\n")
    monkeypatch.setattr(segmentation, "ROOT", kernel)
    monkeypatch.delitem(sys.modules, "offline_test", raising=False)     # nothing cached for a child to reuse
    probe = "import socket\ntry:\n    socket.socket()\n    print('NETWORK OPEN')\nexcept OSError:\n    print('denied')\n"
    relay = Relay(policy={}, journal=Journal(tmp_path / "journal.jsonl"))
    proc = run_confined([sys.executable, "-c", probe], identity="probe", relay=relay, cwd=tmp_path)
    assert proc.stdout.decode().strip() == "denied"
