"""Attacker with total write access to GREG's ledger vs. a witness kept outside GREG.

The attacker may rewrite, delete, reorder or fabricate any record and recompute every
internal hash (the ledger's own v2 formula), and may append records directly, bypassing
founder signatures. The attacker wins if a presented ledger returns VERIFIED against the
witness bundle and TSA root that the verifier retained independently.

Each attack also runs the ledger-internal ``anchor.verify`` to preserve the negative
evidence: that check reads anchors and roots from the ledger under attack, so a complete
rewriter defeats it.
"""
import json
from pathlib import Path
import shutil

import pytest

from greg import anchor
from greg.body import Body, Layout, observe
from provenance.ledger import sha256_json
from tests.greg_fixtures import Clock, drop, make_body, mission, note_check, signed, workspace, write_strategy
from tests.unit.test_greg_anchor import OpenSSLTSA, _configure, _make_tsa

pytestmark = pytest.mark.skipif(shutil.which("openssl") is None, reason="needs the openssl CLI as a real TSA")

HASHED = ("seq", "record_type", "payload", "prev_hash", "corrects", "ts_utc", "hash_version")


def _read(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines()]


def _write_rechained(path: Path, records: list[dict]) -> None:
    """Renumber and re-hash everything after genesis exactly as the ledger does."""
    for i in range(1, len(records)):
        r = records[i]
        r["seq"], r["prev_hash"], r["hash_version"] = i, records[i - 1]["hash"], 2
        r.setdefault("ts_utc", "2026-09-26T00:00:00Z")
        r.setdefault("corrects", None)
        r["hash"] = sha256_json({k: r[k] for k in HASHED})
    path.write_text("".join(json.dumps(r) + "\n" for r in records))


def _event(records, event_type):
    return [i for i, r in enumerate(records) if r["payload"].get("type") == event_type]


@pytest.fixture
def world(tmp_path, monkeypatch):
    """A body with two externally witnessed heads, a founder-held root, and snapshots."""
    home, key, body_id, _ = make_body(tmp_path)
    tsa = OpenSSLTSA(_make_tsa(tmp_path / "tsa", "Founder-pinned TSA"))
    impostor = OpenSSLTSA(_make_tsa(tmp_path / "impostor", "Attacker TSA"))
    monkeypatch.setattr(anchor, "_post", tsa)
    _configure(home, key, body_id, tsa.directory)
    ledger = Layout(home).ledger
    clock = Clock()
    with Body(home, clock=clock) as body:
        body.boot()
        assert body.tick()["anchor"]["anchored"]
    snapshot_1 = ledger.read_bytes()  # a legitimate ledger holding only the first witnessed head

    note = workspace(home, "m:note") / "note.txt"
    spec = mission("m:note", checks=[note_check("note", note, "alive")],
                   strategies=[write_strategy("write", "note.txt", "alive", ["note"])],
                   capabilities=["fs.read", "fs.write"])
    drop(home, signed(key, body_id, "MISSION", spec))
    clock.advance(61 * 60)
    with Body(home, clock=clock) as body:
        body.boot()
        assert body.tick()["anchor"]["anchored"]

    roots_pem = (tsa.directory / "root.crt").read_text()  # the verifier's own copy, never from the ledger
    with observe(home) as journal:
        exported = anchor.export_witness(journal, roots_pem)
    witness = exported["bundle"]
    assert exported["admitted"] == 2 and len(witness["witnesses"]) == 2
    (tmp_path / "outside").mkdir()
    (tmp_path / "outside" / "witness.json").write_text(json.dumps(witness))  # retained outside GREG
    return {"home": home, "key": key, "body_id": body_id, "ledger": ledger, "clock": clock, "tsa": tsa,
            "impostor": impostor, "roots_pem": roots_pem, "witness": witness, "snapshot_1": snapshot_1,
            "snapshot_2": ledger.read_bytes(), "tmp": tmp_path}


def _witness_verdict(w):
    with observe(w["home"]) as journal:
        return anchor.verify_witness(journal, w["witness"], w["roots_pem"])


def _internal(w):
    with observe(w["home"]) as journal:
        return anchor.verify(journal)


def _internally_clean(report):
    return report["chain_intact"] and not report["rewritten"] and not report["invalid"]


def test_control_untampered_ledger_verifies(world):
    report = _witness_verdict(world)
    assert report["verdict"] == "VERIFIED" and [r["status"] for r in report["witnesses"]] == ["VERIFIED"] * 2


def test_control_legitimate_growth_verifies_with_an_uncovered_tail(world, monkeypatch):
    monkeypatch.setattr(anchor, "_post", world["tsa"])
    with Body(world["home"], clock=world["clock"]) as body:
        body.boot()  # appends real history after the last witnessed head
    report = _witness_verdict(world)
    assert report["verdict"] == "VERIFIED" and report["unwitnessed_tail_records"] > 0


def test_attack_a_prefix_rewrite(world):
    records = _read(world["ledger"])
    i = _event(records, "greg.body.booted")[0]
    records[i]["payload"]["payload"]["boot_number"] = 99
    _write_rechained(world["ledger"], records)
    report = _witness_verdict(world)
    assert report["chain_intact"], "the rewrite is locally consistent"
    assert report["verdict"] == "FAILED" and {r["status"] for r in report["witnesses"]} == {"DIVERGED"}


def test_attack_b_anchor_deletion(world):
    records = [r for r in _read(world["ledger"]) if not r["payload"].get("type", "").startswith("greg.proof.anchor")]
    _write_rechained(world["ledger"], records)
    internal = _internal(world)
    assert _internally_clean(internal) and internal["anchors"] == 0, \
        "negative evidence: the ledger-internal check sees nothing wrong once anchors are gone"
    assert _witness_verdict(world)["verdict"] == "FAILED"


def test_attack_c_rollback_to_an_older_legitimate_snapshot(world):
    world["ledger"].write_bytes(world["snapshot_1"])
    internal = _internal(world)
    assert _internally_clean(internal) and internal["verified"] == 1, \
        "negative evidence: an old genuine ledger passes the ledger-internal check"
    report = _witness_verdict(world)
    assert report["verdict"] == "FAILED"
    assert [r["status"] for r in report["witnesses"]] == ["VERIFIED", "ROLLED_BACK"]


def _attacker_reanchor(w, from_bytes: bytes, filler: int):
    """Roll back, substitute the TSA root, fabricate history, anchor it with the attacker's TSA."""
    w["ledger"].write_bytes(from_bytes)
    with Body(w["home"], clock=w["clock"]) as body:
        body.journal.record("proof.anchor_configured", {  # written directly, no founder signature
            "enabled": True, "tsa_url": "https://attacker.example/",
            "tsa_roots_pem": (w["impostor"].directory / "root.crt").read_text(),
            "roots_sha256": sha256_json((w["impostor"].directory / "root.crt").read_text()),
            "interval_minutes": 60, "command_digest": "forged"}, key="forged")
        for n in range(filler):
            body.journal.record("attacker.history", {"n": n}, key=n)
        w["clock"].advance(2 * 3600)
        result = anchor.anchor_once(body.journal, w["clock"](), transport=w["impostor"])
    assert result["anchored"], result


def test_attack_d_trust_root_substitution(world):
    _attacker_reanchor(world, world["snapshot_1"], filler=len(_read(world["ledger"])))
    internal = _internal(world)
    assert _internally_clean(internal) and internal["verified"] == 2, \
        "negative evidence: substituted root and anchor verify inside the ledger"
    report = _witness_verdict(world)
    assert report["verdict"] == "FAILED" and report["witnesses"][1]["status"] == "DIVERGED"
    # The attacker's anchor never becomes witness state: export under the founder's root refuses.
    with observe(world["home"]) as journal:
        with pytest.raises(anchor.AnchorError, match="contradicts the retained witness"):
            anchor.export_witness(journal, world["roots_pem"], world["witness"])


def test_attack_e_anchor_substitution(world, tmp_path):
    # E1: the anchor inside the witnessed prefix is replaced by attacker material and re-chained.
    records = _read(world["ledger"])
    first = _event(records, "greg.proof.anchored")[0]
    forged = OpenSSLTSA(_make_tsa(tmp_path / "e-tsa", "Attacker TSA 2"))
    from rfc3161_client import TimestampRequestBuilder, HashAlgorithm
    head = records[first]["payload"]["payload"]["head"]
    request = (TimestampRequestBuilder().data(anchor._message(head)).hash_algorithm(HashAlgorithm.SHA256)
               .nonce(nonce=True).cert_request(cert_request=True).build())
    import base64
    records[first]["payload"]["payload"]["token_b64"] = base64.b64encode(
        forged("", request.as_bytes())).decode()
    _write_rechained(world["ledger"], records)
    assert _witness_verdict(world)["verdict"] == "FAILED"

    # E2: the presented witness entry itself carries a substituted token; the verifier's root refuses it.
    world["ledger"].write_bytes(world["snapshot_2"])
    tampered = json.loads(json.dumps(world["witness"]))
    tampered["witnesses"][1]["token_b64"] = records[first]["payload"]["payload"]["token_b64"]
    tampered["witnesses"][1]["head"] = head
    with observe(world["home"]) as journal:
        report = anchor.verify_witness(journal, tampered, world["roots_pem"])
    assert report["verdict"] == "FAILED" and report["witnesses"][1]["status"] == "INVALID_TOKEN"


def test_attack_f_total_ledger_reconstruction(world, tmp_path):
    # A different body with a different history, extended past every witnessed position.
    (tmp_path / "other").mkdir()
    other_home, key, body_id, _ = make_body(tmp_path / "other")
    with Body(other_home, clock=Clock()) as body:
        body.boot()
        for n in range(len(_read(world["ledger"]))):
            body.journal.record("attacker.history", {"n": n}, key=n)
    world["ledger"].write_bytes(Layout(other_home).ledger.read_bytes())
    report = _witness_verdict(world)
    assert report["chain_intact"] and report["verdict"] == "FAILED"
    assert {r["status"] for r in report["witnesses"]} == {"DIVERGED"}


def test_export_admits_only_anchors_valid_under_the_verifiers_root(world):
    _attacker_reanchor(world, world["snapshot_2"], filler=1)  # appends an attacker-root anchor
    with observe(world["home"]) as journal:
        result = anchor.export_witness(journal, world["roots_pem"], world["witness"])
    assert result["admitted"] == 0 and len(result["rejected"]) == 1


def test_cli_refuses_a_witness_inside_greg_home(world):
    from greg import cli
    roots = world["tmp"] / "outside" / "roots.pem"
    roots.write_text(world["roots_pem"])
    code = cli.main(["--home", str(world["home"]), "anchor", "export", "--roots", str(roots),
                     "--out", str(Path(world["home"]) / "witness.json")])
    assert code != 0
    assert cli.main(["--home", str(world["home"]), "anchor", "verify", "--witness",
                     str(world["tmp"] / "outside" / "witness.json"), "--roots", str(roots)]) == 0
