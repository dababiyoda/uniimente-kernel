"""External RFC 3161 anchoring of the GREG ledger head.

The TSA here is OpenSSL's own RFC 3161 implementation (`openssl ts -reply`) with a
throwaway root, reached through the same transport seam the body uses for an HTTPS
TSA. Responses are real signed timestamp tokens verified by rfc3161-client.
"""
import base64
import json
from pathlib import Path
import shutil
import subprocess

import pytest

from greg import anchor
from greg.body import Body, Layout, status
from provenance.ledger import sha256_json
from tests.greg_fixtures import Clock, drop, make_body, signed

pytestmark = pytest.mark.skipif(shutil.which("openssl") is None, reason="needs the openssl CLI as a real TSA")

TSA_CNF = """
[ req ]
distinguished_name = dn
[ dn ]
[ root_ext ]
basicConstraints = critical,CA:true
keyUsage = critical,keyCertSign,cRLSign
subjectKeyIdentifier = hash
[ tsa_ext ]
basicConstraints = critical,CA:false
keyUsage = critical,digitalSignature
extendedKeyUsage = critical,timeStamping
subjectKeyIdentifier = hash
authorityKeyIdentifier = keyid
[ tsa ]
default_tsa = tsa_config
[ tsa_config ]
dir = .
serial = ./serial
crypto_device = builtin
signer_cert = ./tsa.crt
certs = ./tsa.crt
signer_key = ./tsa.key
signer_digest = sha256
default_policy = 1.2.3.4.1
other_policies = 1.2.3.4.2
digests = sha256
accuracy = secs:1
ordering = no
tsa_name = no
ess_cert_id_chain = no
ess_cert_id_alg = sha256
"""


def _openssl(cwd, *args):
    subprocess.run(["openssl", *args], cwd=cwd, check=True, capture_output=True)


def _make_tsa(directory: Path, name: str) -> Path:
    directory.mkdir()
    (directory / "tsa.cnf").write_text(TSA_CNF)
    (directory / "serial").write_text("01\n")
    ec = ["-newkey", "ec", "-pkeyopt", "ec_paramgen_curve:P-256", "-nodes"]
    _openssl(directory, "req", "-x509", "-new", *ec, "-keyout", "root.key", "-out", "root.crt", "-days", "2",
             "-subj", f"/CN={name} root", "-config", "tsa.cnf", "-extensions", "root_ext")
    _openssl(directory, "req", "-new", *ec, "-keyout", "tsa.key", "-out", "tsa.csr", "-subj", f"/CN={name}",
             "-config", "tsa.cnf")
    _openssl(directory, "x509", "-req", "-in", "tsa.csr", "-CA", "root.crt", "-CAkey", "root.key",
             "-CAcreateserial", "-out", "tsa.crt", "-days", "2", "-extfile", "tsa.cnf", "-extensions", "tsa_ext")
    return directory


class OpenSSLTSA:
    """Transport that hands the request to OpenSSL's RFC 3161 responder."""

    def __init__(self, directory: Path):
        self.directory, self.calls = directory, 0

    def __call__(self, url: str, request: bytes) -> bytes:
        self.calls += 1
        (self.directory / "q.tsq").write_bytes(request)
        _openssl(self.directory, "ts", "-reply", "-config", "tsa.cnf", "-queryfile", "q.tsq", "-out", "r.tsr")
        return (self.directory / "r.tsr").read_bytes()


def _down(url, request):
    raise OSError("TSA unreachable")


@pytest.fixture
def tsa(tmp_path):
    return OpenSSLTSA(_make_tsa(tmp_path / "tsa", "GREG test TSA"))


@pytest.fixture
def body_home(tmp_path):
    return make_body(tmp_path)


def _configure(home, key, body_id, tsa_dir, **extra):
    body = {"tsa_url": "https://tsa.example/", "tsa_roots_pem": (tsa_dir / "root.crt").read_text(), **extra}
    drop(home, signed(key, body_id, "ANCHOR_CONFIGURE", body))


def test_anchoring_is_off_until_the_founder_signs_it(body_home, tsa, monkeypatch):
    home, key, body_id, _ = body_home
    monkeypatch.setattr(anchor, "_post", tsa)
    clock = Clock()
    with Body(home, clock=clock) as body:
        body.boot()
        body.tick()
        assert tsa.calls == 0 and not body.journal.replay("proof.anchor")
        _configure(home, key, body_id, tsa.directory)
        result = body.tick()
    assert result["anchor"]["anchored"] is True and tsa.calls == 1


def test_anchor_verifies_and_detects_a_rewritten_history(body_home, tsa, monkeypatch):
    home, key, body_id, _ = body_home
    monkeypatch.setattr(anchor, "_post", tsa)
    _configure(home, key, body_id, tsa.directory)
    with Body(home, clock=Clock()) as body:
        body.boot()
        anchored = body.tick()["anchor"]
        report = anchor.verify(body.journal)
    assert anchored["anchored"] and report["verified"] == 1 and not report["rewritten"] and not report["invalid"]

    # An adversary holding the ledger (the body itself included) edits a record inside the anchored
    # prefix and re-chains every later record so the local hash chain still verifies.
    ledger_path = Layout(home).ledger
    records = [json.loads(line) for line in ledger_path.read_text().splitlines()]
    index = next(i for i, r in enumerate(records) if r["payload"].get("type") == "greg.body.booted")
    records[index]["payload"]["boot_number"] = 99
    _rechain(records, index)
    ledger_path.write_text("".join(json.dumps(r) + "\n" for r in records))

    with Body(home, clock=Clock()) as body:
        assert body.ledger.verify_chain()[0], "the rewrite is locally consistent"
        report = anchor.verify(body.journal)
    assert report["rewritten"] and report["verified"] == 0


def _rechain(records, start):
    """Recompute hashes exactly as the ledger does, so only an external anchor can catch the rewrite."""
    for i in range(start, len(records)):
        r = records[i]
        assert r["hash_version"] == 2
        r["prev_hash"] = records[i - 1]["hash"]
        r["hash"] = sha256_json({k: r[k] for k in ("seq", "record_type", "payload", "prev_hash", "corrects",
                                                   "ts_utc", "hash_version")})


def test_tsa_outage_is_recorded_and_never_blocks_the_body(body_home, tsa, monkeypatch):
    home, key, body_id, _ = body_home
    monkeypatch.setattr(anchor, "_post", _down)
    _configure(home, key, body_id, tsa.directory)
    clock = Clock()
    with Body(home, clock=clock) as body:
        body.boot()
        first = body.tick()
        assert first["anchor"]["anchored"] is False and "TSA unreachable" in first["anchor"]["error"]
        assert body.tick()["anchor"] is None, "no retry storm inside the interval"
        clock.advance(61 * 60)
        monkeypatch.setattr(anchor, "_post", tsa)
        assert body.tick()["anchor"]["anchored"] is True


def test_a_token_from_an_unpinned_tsa_is_refused(body_home, tsa, tmp_path, monkeypatch):
    home, key, body_id, _ = body_home
    impostor = OpenSSLTSA(_make_tsa(tmp_path / "impostor", "Impostor TSA"))
    monkeypatch.setattr(anchor, "_post", impostor)
    _configure(home, key, body_id, tsa.directory)  # pins the real TSA root, impostor answers
    with Body(home, clock=Clock()) as body:
        body.boot()
        result = body.tick()["anchor"]
        assert result["anchored"] is False and not body.journal.replay("proof.anchored")


def test_idle_body_does_not_anchor_its_own_bookkeeping(body_home, tsa, monkeypatch):
    home, key, body_id, _ = body_home
    monkeypatch.setattr(anchor, "_post", tsa)
    _configure(home, key, body_id, tsa.directory, interval_minutes=5)
    clock = Clock()
    with Body(home, clock=clock) as body:
        body.boot()
        body.tick()
        clock.advance(6 * 60)
        assert body.tick()["anchor"] is None  # only the anchor fact itself was appended since
        assert tsa.calls == 1


def test_tampered_token_is_invalid(body_home, tsa, monkeypatch):
    home, key, body_id, _ = body_home
    monkeypatch.setattr(anchor, "_post", tsa)
    _configure(home, key, body_id, tsa.directory)
    with Body(home, clock=Clock()) as body:
        body.boot()
        body.tick()
        event = body.journal.replay("proof.anchored")[0]
    token = bytearray(base64.b64decode(event.payload["token_b64"]))
    token[-5] ^= 0xFF

    class Replayed:
        def replay(self, kind=""):
            if kind == "proof.anchored":
                return [type(event)(**{**event.__dict__,
                                       "payload": {**event.payload, "token_b64": base64.b64encode(bytes(token)).decode()}})]
            return journal.replay(kind)

    with Body(home, clock=Clock()) as body:
        journal = body.journal
        fake = Replayed()
        fake.ledger = journal.ledger
        report = anchor.verify(fake)
    assert report["invalid"] and report["verified"] == 0


@pytest.mark.parametrize("body,message", [
    ({"tsa_url": "http://tsa.example/", "tsa_roots_pem": "x"}, "https"),
    ({"tsa_url": "https://tsa.example/"}, "pin"),
    ({"tsa_url": "https://tsa.example/", "tsa_roots_pem": "not a cert"}, "PEM"),
    ({"tsa_url": "https://tsa.example/", "tsa_roots_pem": "x", "extra": 1}, "takes"),
])
def test_configuration_refusals(body, message):
    with pytest.raises(anchor.AnchorError, match=message):
        anchor.validate_config(body)


def test_status_reports_the_anchor(body_home, tsa, monkeypatch):
    home, key, body_id, _ = body_home
    monkeypatch.setattr(anchor, "_post", tsa)
    _configure(home, key, body_id, tsa.directory)
    with Body(home, clock=Clock()) as body:
        body.boot()
        body.tick()
    projection = status(home)["external_anchor"]
    assert projection["configured"] and projection["verified"] == 1 and projection["latest_gen_time"]
