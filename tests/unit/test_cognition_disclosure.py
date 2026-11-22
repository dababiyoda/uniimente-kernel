"""Selective-disclosure evidence packages (directive section 9) over receipts from a real body run."""
from __future__ import annotations

import json

import pytest

from greg.body import Body
from greg.cognition import disclosure as D
from greg.cognition.contracts import CognitionError, digest
from tests.greg_fixtures import drop, make_body, mission, signed

PARAMS = {"problem_id": "pkg:numeric", "operation": "calculate", "data": {"expression": "1/4"}}


@pytest.fixture(scope="module")
def body(tmp_path_factory):
    home, key, body_id, _ = make_body(tmp_path_factory.mktemp("disclosure"))
    spec = mission("m:package", checks=[{
        "check_id": "exact", "description": "exact arithmetic",
        "sensor": {"capability": "cognition.solve", "target": "cognition:arithmetic", "params": PARAMS},
        "predicate": {"op": "equals", "field": "output.exact", "value": "1/4"}}],
        strategies=[], capabilities=["cognition.solve"], targets=("cognition:*",), ceiling="read_only")
    drop(home, signed(key, body_id, "MISSION", spec))
    with Body(home) as b:
        b.boot()
        b.tick()
        yield b


def _package(body, **kw):
    refs = D.receipts_for_mission(body.journal, "m:package")
    assert len(refs) == 1
    return refs, D.build_package(body.journal, refs, recipient="Example Clerk", purpose="show one computation", **kw)


def test_the_digest_rule_reproduces_the_rfc_9901_worked_example():
    example = "WyIyR0xDNDJzS1F2ZUNmR2ZyeU5STjl3IiwgImdpdmVuX25hbWUiLCAiSm9obiJd"
    assert D.disclosure_digest(example) == "jsu9yVulwQQlhFlM_3JlzMaSFzglhQG0DpfayQwLUK4"


def test_a_real_receipt_is_packaged_and_the_default_view_withholds_inputs_and_outputs(body):
    refs, holder = _package(body)
    shown = D.present(holder)
    checked = D.verify_presentation(shown)
    assert checked["valid"], checked["problems"]
    revealed = checked["items"][0]["revealed"]
    assert revealed["authority_created"] is False and revealed["abstention_state"] == "NONE"
    text = json.dumps(shown["revealed"])
    for withheld in ("output", "problem_id", "input_digest", "proof_artifact", "evidence_refs"):
        assert withheld not in revealed
    assert "1/4" not in text and "pkg:numeric" not in text
    assert holder["package"]["items"][0]["receipt_record"] == refs[0]
    assert holder["package"]["authority_created"] is False
    # Revealing the output on purpose verifies against the same commitments.
    full = D.verify_presentation(D.present(holder, reveal=list(holder["disclosures"][0])))
    assert full["valid"] and full["items"][0]["revealed"]["output"]["exact"] == "1/4"


def test_tampering_is_detected_on_the_recipient_side(body):
    _, holder = _package(body)
    shown = D.present(holder, reveal=["method", "output"])
    forged = json.loads(json.dumps(shown))
    salt, name, value = json.loads(D._unb64(forged["revealed"][0][0]))
    forged["revealed"][0][0] = D.disclosure(name, "a different value", salt)
    assert not D.verify_presentation(forged)["valid"]
    edited = json.loads(json.dumps(shown))
    edited["package"]["recipient"] = "Someone Else"
    assert "package digest does not match the package" in D.verify_presentation(edited)["problems"]
    weak = json.loads(json.dumps(shown))
    weak["revealed"][0].append(D.disclosure("method", "x", D._b64(b"short")))
    assert any("under 128 bits" in p for p in D.verify_presentation(weak)["problems"])
    doubled = json.loads(json.dumps(shown))
    doubled["revealed"][0].append(doubled["revealed"][0][0])
    assert any("revealed twice" in p for p in D.verify_presentation(doubled)["problems"])
    for malformed in ([], {"package": {"items": "x"}, "revealed": 3}, {"package": None, "revealed": [[1]]}):
        assert D.verify_presentation(malformed)["valid"] is False   # untrusted input never crashes the check
    _, other = _package(body)
    foreign = json.loads(json.dumps(shown))
    foreign["revealed"][0] = D.present(other, reveal=["method"])["revealed"][0]
    assert any("not committed" in p for p in D.verify_presentation(foreign)["problems"])


def test_an_unsigned_package_reports_the_verifiers_own_limits(body):
    # Anyone can re-digest an unsigned package, so a self-consistent edit still verifies. That is why
    # attribution to GREG is not claimed, and why the check reports its own limits, not the package's.
    from provenance.ledger import sha256_json
    _, holder = _package(body)
    shown = json.loads(json.dumps(D.present(holder)))
    shown["package"]["limitations"] = []
    shown["package_digest"] = sha256_json(shown["package"])
    checked = D.verify_presentation(shown)
    assert checked["valid"] and checked["does_not_prove"] == list(D.LIMITATIONS)
    assert "GREG" not in checked["proves"] and any("unsigned" in line for line in checked["does_not_prove"])


def test_decoys_hide_how_many_fields_were_withheld(body):
    _, plain = _package(body, decoys=0)
    _, padded = _package(body, decoys=5)
    n = len(plain["disclosures"][0])
    assert len(plain["package"]["items"][0]["digests"]) == n
    assert len(padded["package"]["items"][0]["digests"]) == n + 5
    with pytest.raises(CognitionError):
        _package(body, decoys=9)


def test_a_disagreeing_receipt_over_the_same_input_cannot_be_left_out(body, monkeypatch):
    import subprocess
    from greg.cognition import cortex
    refs, _ = _package(body)
    original = D._receipt(body.journal.ledger.find(refs[0]))
    request = {k: v for k, v in PARAMS.items()}

    def timed_out(*a, **k):
        raise subprocess.TimeoutExpired("solver", 0.01)
    monkeypatch.setattr(cortex, "_numeric", timed_out)  # a later recomputation of the same input times out
    rival = cortex.reason(request, registry=cortex.registry_view(body.journal))
    assert rival["input_digest"] == original["input_digest"] and rival["abstention_state"] == "UNKNOWN"
    body.journal.ledger.append("receipt", {"result": {"output": rival}})
    holder = D.build_package(body.journal, refs, recipient="Example Clerk", purpose="show one computation")
    assert [i["role"] for i in holder["package"]["items"]] == ["requested", "same_input"]
    (contradiction,) = holder["package"]["contradictions"]
    assert contradiction["items"] == [0, 1] and set(contradiction["disagree_on"]) == {"output", "abstention_state",
                                                                                       "formal_validity"}
    assert D.verify_presentation(D.present(holder))["contradictions"] == [contradiction]
    # A forged copy fails the receipt validator and is not admitted as a rival either.
    forged = {**rival, "output": {"exact": "1/3"}}
    forged["receipt_id"] = digest({k: v for k, v in forged.items() if k != "receipt_id"})
    body.journal.ledger.append("receipt", {"result": {"output": forged}})
    holder = D.build_package(body.journal, refs, recipient="Example Clerk", purpose="show one computation")
    assert len(holder["package"]["items"]) == 2


def test_only_valid_retained_receipts_and_real_action_records_are_accepted(body):
    refs, _ = _package(body)
    with pytest.raises(CognitionError, match="not a retained, valid cognitive receipt"):
        D.build_package(body.journal, ["sha256:" + "0" * 64], recipient="C", purpose="p")
    forged = dict(D._receipt(body.journal.ledger.find(refs[0])), output={"exact": "9"})  # identity no longer holds
    bad = body.journal.ledger.append("receipt", {"result": {"output": forged}})
    with pytest.raises(CognitionError):
        D.build_package(body.journal, [bad.hash], recipient="C", purpose="p")
    with pytest.raises(CognitionError, match="authorized-action reference"):
        D.build_package(body.journal, refs, recipient="C", purpose="p", authorized_action_ref="sha256:" + "1" * 64)
    with pytest.raises(CognitionError, match="recipient and purpose"):
        D.build_package(body.journal, refs, recipient=" ", purpose="p")
    event = body.journal.replay("mission.observed")[-1]
    record = body.journal.event_hash(event.event_id)
    holder = D.build_package(body.journal, refs, recipient="C", purpose="p", authorized_action_ref=record,
                             requested_remedy="correct the published figure")
    assert holder["package"]["authorized_action_record"]["ref"] == record
    assert holder["package"]["requested_remedy"]["status"] == "requested by the issuer; not a finding"


def test_custody_is_stated_and_a_broken_chain_issues_nothing(body):
    refs, holder = _package(body)
    custody = holder["package"]["custody"]
    assert custody["ledger_head"] == body.journal.ledger.head and custody["chain_verified_at_packaging"].startswith("chain intact")
    assert custody["anchoring"]["configured"] in (False, None) or custody["anchoring"]["configured"] is not True
    assert custody["inclusion"].startswith("not checkable from this package") and "witness bundle" in custody["inclusion"]
    copy = body.journal.ledger.records[2]
    copy.payload["tampered"] = True                    # a reader's copy: retained evidence is unchanged
    again = D.build_package(body.journal, refs, recipient="C", purpose="p")
    assert again["package"]["custody"]["chain_verified_at_packaging"].startswith("chain intact")
    record = body.journal.ledger._records[2]           # the ledger's own retained record: tampering is caught
    saved = json.loads(json.dumps(record.payload))
    record.payload["tampered"] = True
    try:
        with pytest.raises(CognitionError, match="chain does not verify"):
            D.build_package(body.journal, refs, recipient="C", purpose="p")
    finally:
        record.payload.clear()
        record.payload.update(saved)
    assert body.journal.ledger.verify_chain()[0]


def test_an_institutional_response_is_appended_never_edited_in_and_grants_nothing(body):
    _, holder = _package(body)
    before = json.dumps(holder["package"], sort_keys=True)
    with pytest.raises(CognitionError, match="grounds or a note"):
        D.record_response(body.journal, holder["package_digest"], actor="Example Clerk", response="disputed",
                          scope="figure 2", reported_by="founder")
    with pytest.raises(CognitionError, match="grounds must come from"):
        D.record_response(body.journal, holder["package_digest"], actor="Example Clerk", response="disputed",
                          scope="figure 2", reported_by="founder", grounds=["vibes"])
    with pytest.raises(CognitionError, match="one of"):
        D.record_response(body.journal, holder["package_digest"], actor="Example Clerk", response="obeyed",
                          scope="figure 2", reported_by="founder")
    D.record_response(body.journal, holder["package_digest"], actor="Example Clerk", response="disputed",
                      scope="figure 2", reported_by="founder", grounds=["jurisdiction", "relevance"])
    recorded = D.responses(body.journal, holder["package_digest"])
    assert [r["response"] for r in recorded] == ["disputed"]
    assert recorded[0]["authority_created"] is False and recorded[0]["grounds"] == ["jurisdiction", "relevance"]
    assert json.dumps(holder["package"], sort_keys=True) == before


def test_the_cli_exports_without_sending_and_the_recipient_check_needs_no_greg_state(tmp_path, capsys):
    from greg.cli import main
    (tmp_path / "body").mkdir()
    home, key, body_id, _ = make_body(tmp_path / "body")
    spec = mission("m:cli-package", checks=[{
        "check_id": "exact", "description": "exact arithmetic",
        "sensor": {"capability": "cognition.solve", "target": "cognition:arithmetic", "params": PARAMS},
        "predicate": {"op": "equals", "field": "output.exact", "value": "1/4"}}],
        strategies=[], capabilities=["cognition.solve"], targets=("cognition:*",), ceiling="read_only")
    drop(home, signed(key, body_id, "MISSION", spec))
    with Body(home) as b:
        b.boot()
        b.tick()
        records = len(b.journal.ledger.records)
    out = tmp_path / "package"
    assert main(["--home", str(home), "cognition", "package", "--mission", "m:cli-package",
                 "--recipient", "Example Clerk", "--purpose", "show one computation", "--out", str(out)]) == 0
    summary = json.loads(capsys.readouterr().out)
    assert summary["sent"] is False and summary["presentation_verifies"] is True and summary["items"] == 1
    assert (out / "holder.json").stat().st_mode & 0o077 == 0
    with Body(home) as b:
        assert len(b.journal.ledger.records) >= records  # read-only export: nothing appended by the CLI
        assert not b.journal.replay("disclosure.")
    assert main(["--home", str(home), "cognition", "verify-package", str(out / "presentation.json")]) == 0
    shown = json.loads((out / "presentation.json").read_text())
    shown["package"]["purpose"] = "something else"
    (out / "tampered.json").write_text(json.dumps(shown))
    capsys.readouterr()
    assert main(["--home", str(home), "cognition", "verify-package", str(out / "tampered.json")]) == 1
    capsys.readouterr()
    assert main(["--home", str(home), "cognition", "challenges", str(out / "holder.json")]) == 0
    view = json.loads(capsys.readouterr().out)
    assert view["contested_claims"] == 0 and view["authority_created"] is False
    assert "assumptions" in view["items"][0]["not_contested"]
    with Body(home) as b:
        assert not b.journal.replay("disclosure.")      # reading the challenge map records nothing


def _digest_of(holder, field):
    return D.disclosure_digest(holder["disclosures"][0][field])


def test_a_dispute_names_the_committed_claim_it_attacks_and_the_map_shows_what_stands(tmp_path):
    home, key, body_id, _ = make_body(tmp_path)
    spec = mission("m:challenge", checks=[{
        "check_id": "exact", "description": "exact arithmetic",
        "sensor": {"capability": "cognition.solve", "target": "cognition:arithmetic", "params": PARAMS},
        "predicate": {"op": "equals", "field": "output.exact", "value": "1/4"}}],
        strategies=[], capabilities=["cognition.solve"], targets=("cognition:*",), ceiling="read_only")
    drop(home, signed(key, body_id, "MISSION", spec))
    with Body(home) as b:
        b.boot()
        b.tick()
        journal = b.journal
        refs = D.receipts_for_mission(journal, "m:challenge")
        holder = D.build_package(journal, refs, recipient="Example Clerk", purpose="p")
        before = json.dumps(holder["package"], sort_keys=True)
        assumption, output = _digest_of(holder, "assumptions"), _digest_of(holder, "output")
        decoys = set(holder["package"]["items"][0]["digests"]) - set(D.committed_claims(holder))
        assert len(decoys) == 2                          # decoys commit to nothing and cannot be targeted
        with pytest.raises(CognitionError, match="not a committed claim"):
            D.record_response(journal, holder["package_digest"], actor="Example Clerk", response="disputed",
                              scope="s", reported_by="founder", grounds=["data"], targets=[sorted(decoys)[0]],
                              holder=holder)
        with pytest.raises(CognitionError, match="holder file"):
            D.record_response(journal, holder["package_digest"], actor="Example Clerk", response="disputed",
                              scope="s", reported_by="founder", grounds=["data"], targets=[assumption])
        other = D.build_package(journal, refs, recipient="Someone else", purpose="p")
        with pytest.raises(CognitionError, match="holder file"):     # another package's holder does not vouch
            D.record_response(journal, holder["package_digest"], actor="Example Clerk", response="disputed",
                              scope="s", reported_by="founder", grounds=["data"], targets=[assumption],
                              holder=other)
        with pytest.raises(CognitionError, match="addresses no claim"):
            D.record_response(journal, holder["package_digest"], actor="Example Clerk", response="no_response",
                              scope="s", reported_by="founder", targets=[assumption], holder=holder)
        D.record_response(journal, holder["package_digest"], actor="Example Clerk", response="disputed",
                          scope="the assumption list", reported_by="founder", grounds=["model"],
                          targets=[assumption], holder=holder)
        D.record_response(journal, holder["package_digest"], actor="Auditor", response="accepted",
                          scope="the result", reported_by="founder", targets=[output], holder=holder)
        D.record_response(journal, holder["package_digest"], actor="Third Party", response="disputed",
                          scope="all of it", reported_by="founder", grounds=["relevance"])
        view = D.challenge_map(journal, holder)
        item = view["items"][0]
        assert [(r["field"], r["claim_kind"]) for r in item["contested"]] == [("assumptions", "assumption")]
        assert item["contested"][0]["contested_by"][0]["actor"] == "Example Clerk"
        assert item["contested"][0]["contested_by"][0]["grounds"] == ["model"]
        assert "output" in item["not_contested"] and "assumptions" not in item["not_contested"]
        assert [d["actor"] for d in view["untargeted_disputes"]] == ["Third Party"]
        assert view["contested_claims"] == 1 and view["authority_created"] is False
        foreign = D.challenge_map(journal, other)                          # responses stay with their package
        assert foreign["contested_claims"] == 0 and foreign["untargeted_disputes"] == []
        assert D.contested_receipts(journal) == [{"receipt_record": refs[0], "claims": ["assumption:assumptions"],
                                                  "actors": ["Example Clerk"], "authority_created": False}]
        assert json.dumps(holder["package"], sort_keys=True) == before      # nothing is edited into the package
        tampered = json.loads(json.dumps(holder))
        tampered["package"]["purpose"] = "changed"
        with pytest.raises(CognitionError, match="does not match its digest"):
            D.challenge_map(journal, tampered)
        from greg.gravity import _measured_trust
        assert _measured_trust(journal)["contested_receipts"] == 1
