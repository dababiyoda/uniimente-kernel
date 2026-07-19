"""WP-03 HttpResearchAdapter suite — stub fetcher only, NO network.

Every test drives the full WP-01 Consequence Gate under the WP-02 compiled
constitution (or the adapter directly, where the SPEC demands it). The
transport is always an injected ``StubFetcher``; no socket is ever opened.

Reconciliation craft: the WP-01 RECONCILE stage compares
``sha256(canonical_json(expected_outcome))`` with the receipt's
``provider_response_hash``. The adapter returns the outcome-attestation hash
(see the ADR in ``kernel/adapters/http_research.py``), so the stub body is
crafted as ``canonical_json(expected_outcome).encode()`` — which makes the
SPEC section 4 assertion "receipt hash = sha256(body)" hold literally.

Hostile tests (5–15) must all fail closed: no ExecutionReceipt on the spine,
zero attacker bytes anywhere in the spine, the refusal recorded as a
GATE_REFUSAL event, the episode closed as failed, and the chain still
verifying.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest

from kernel.adapters.http_research import (
    ADAPTER_ID,
    DEFAULT_MAX_BYTES,
    FetchResult,
    HttpResearchAdapter,
    host_allowed,
)
from kernel.authority.approvals import ApprovalService
from kernel.contracts.institutional import EvidencePacket
from kernel.crypto.hashing import canonical_json, sha256_hex
from kernel.gate import errors
from kernel.gate.pipeline import Gate
from kernel.spine import Spine
from kernel.ucl import Constitution, compile_policy_fn
from kernel.ucl.version import constitution_version_from_dir, policy_version

from tests.ucl.conftest import make_intent

EXPECTED = "bounded research fetch of the approved https target"
ATTACKER_MARKER = "ATTACKER-CONTROLLED-BYTES"


def fresh_evidence(hours: float = 1.0) -> EvidencePacket:
    return EvidencePacket(
        source_uri="file://research/market-brief",
        source_hash=sha256_hex(b"market brief"),
        authority_class="simulated",
        claims=["competitor pricing is observable"],
        freshness_deadline=datetime.now(timezone.utc) + timedelta(hours=hours),
    )


class StubFetcher:
    """Scripted transport matching the Fetcher signature (url, timeout, max_bytes).

    Each entry maps a URL to a FetchResult, an Exception to raise, or a list
    of per-call results (for redirect chains). Records every URL it was asked
    to fetch so tests can prove which bytes never crossed the wire.
    """

    def __init__(self, script: dict):
        self._script = {url: (list(v) if isinstance(v, list) else [v]) for url, v in script.items()}
        self.calls: list[str] = []

    def __call__(self, url: str, timeout: float, max_bytes: int) -> FetchResult:
        self.calls.append(url)
        entries = self._script[url]
        entry = entries.pop(0) if len(entries) > 1 else entries[0]
        if isinstance(entry, Exception):
            raise entry
        return entry


def success_body(expected: str = EXPECTED) -> bytes:
    """Body whose sha256 equals the attestation hash (reconcile craft, above)."""
    return canonical_json(expected).encode("utf-8")


def ok(url: str, body: bytes | None = None) -> FetchResult:
    return FetchResult(status_code=200, body=body if body is not None else success_body(), final_url=url)


def build_world(tmp_path, constitution_dir, *, fetcher, allowlist=None, interceptors=None):
    """Wire the compiled constitution + gate + HttpResearchAdapter, end to end."""
    model = Constitution.from_directory(constitution_dir, current_state="normal")
    versions = {
        "policy_version": policy_version(model),
        "constitution_version": constitution_version_from_dir(constitution_dir),
    }
    policy_fn = compile_policy_fn(model, **versions)
    spine = Spine(tmp_path / "spine")
    authority = ApprovalService(approver_id="founder")
    evidence = fresh_evidence()
    gate = Gate(
        versions["policy_version"],
        versions["constitution_version"],
        authority,
        spine,
        policy_fn=policy_fn,
        evidence_store={evidence.id: evidence},
        interceptors=interceptors,
    )
    adapter_kwargs = {"witness_public_key": authority.public_key, "fetcher": fetcher}
    if allowlist is not None:
        adapter_kwargs["allowlist"] = allowlist
    adapter = HttpResearchAdapter(**adapter_kwargs)
    gate.register_adapter(adapter.adapter_id, adapter.public_key_hex)
    return {
        "spine": spine,
        "authority": authority,
        "gate": gate,
        "adapter": adapter,
        "evidence": evidence,
        "versions": versions,
    }


def http_intent(evidence: EvidencePacket, **overrides):
    fields = dict(
        action_type="research_fetch",
        target="https://example.com/",
        expected_outcome=EXPECTED,
        evidence_ids=[evidence.id],
    )
    fields.update(overrides)
    return make_intent(**fields)


def spine_payload(spine, kind):
    return [r["payload"] for r in spine.iter() if r["kind"] == kind]


def spine_records(spine, kind):
    return [r for r in spine.iter() if r["kind"] == kind]


def assert_failed_closed(w):
    """Hostile invariant: refusal recorded at EXECUTE, episode closed failed,
    no receipt, zero attacker bytes in the spine, and the chain still verifies.
    Fetcher-call expectations are asserted by each caller."""
    spine = w["spine"]
    assert spine_payload(spine, "ExecutionReceipt") == []
    (refusal,) = spine_records(spine, "GATE_REFUSAL")
    assert refusal["refs"]["stage"] == "EXECUTE"
    episode = spine_payload(spine, "DecisionEpisode")[-1]
    assert episode["closed"] is True
    assert episode["close_reason"] != "completed"
    assert w["adapter"].calls == 0
    assert ATTACKER_MARKER not in json.dumps(list(spine.iter()))
    assert spine.verify_chain() is True


# ------------------------------------------------------------- happy path


def test_01_allowlisted_host_fetch_succeeds_receipt_hash_and_episode_closes(
    tmp_path, constitution_dir
):
    body = success_body()
    fetcher = StubFetcher({"https://example.com/": ok("https://example.com/", body)})
    w = build_world(tmp_path, constitution_dir, fetcher=fetcher)
    gate, authority, adapter = w["gate"], w["authority"], w["adapter"]

    intent = http_intent(w["evidence"])
    approval = authority.issue_approval(gate.fingerprint(intent))
    episode = gate.run(intent, adapter=adapter, approval=approval)

    assert episode.closed is True and episode.close_reason == "completed"
    assert adapter.calls == 1
    assert fetcher.calls == ["https://example.com/"]

    (receipt,) = spine_payload(w["spine"], "ExecutionReceipt")
    # SPEC section 4 test 1: receipt hash = sha256(body).
    assert receipt["provider_response_hash"] == sha256_hex(body)
    facts = json.loads(receipt["external_id"])
    assert facts["status_code"] == 200
    assert facts["bytes_fetched"] == len(body)
    assert facts["final_url"] == "https://example.com/"
    assert facts["body_sha256"] == sha256_hex(body)
    assert facts["allowlist_version"] == adapter.allowlist_version


def test_02_full_gate_loop_with_stub_fetcher_reconciles_and_chain_verifies(
    tmp_path, constitution_dir
):
    body = success_body()
    fetcher = StubFetcher({"https://example.com/": ok("https://example.com/", body)})
    w = build_world(tmp_path, constitution_dir, fetcher=fetcher)
    gate, authority, adapter, spine = w["gate"], w["authority"], w["adapter"], w["spine"]

    intent = http_intent(w["evidence"])
    approval = authority.issue_approval(gate.fingerprint(intent))
    episode = gate.run(intent, adapter=adapter, approval=approval)

    # C2 -> REQUIRE_HUMAN -> approval -> witness -> execute -> receipt ->
    # reconciled -> closed episode, with the full artifact chain on the spine.
    assert episode.closed is True and episode.close_reason == "completed"
    assert episode.approval_id == approval.id
    kinds = [r["kind"] for r in spine.iter()]
    assert kinds == [
        "ActionIntent",
        "PolicyDecision",
        "ApprovalRecord",
        "CapabilityGrant",
        "CommitWitness",
        "EXECUTE_BEGIN",
        "ExecutionReceipt",
        "ReconciliationRecord",
        "OutcomeRecord",
        "DecisionEpisode",
    ]
    (decision,) = spine_payload(spine, "PolicyDecision")
    assert decision["effect"] == "REQUIRE_HUMAN"
    assert decision["governing_clauses"] == ["consequence_default:C2:REQUIRE_HUMAN"]
    (reconciliation,) = spine_payload(spine, "ReconciliationRecord")
    assert reconciliation["reconciled"] is True
    assert reconciliation["expected_hash"] == sha256_hex(canonical_json(EXPECTED).encode("utf-8"))
    assert reconciliation["actual_hash"] == sha256_hex(body)
    assert spine.verify_chain() is True


def test_03_trailing_dot_host_normalizes_and_matches(tmp_path, constitution_dir):
    fetcher = StubFetcher({"https://example.com./": ok("https://example.com./")})
    w = build_world(tmp_path, constitution_dir, fetcher=fetcher)
    gate, authority, adapter = w["gate"], w["authority"], w["adapter"]

    intent = http_intent(w["evidence"], target="https://example.com./")
    approval = authority.issue_approval(gate.fingerprint(intent))
    episode = gate.run(intent, adapter=adapter, approval=approval)

    assert episode.closed is True and episode.close_reason == "completed"
    # The URL fetched is the original witness target; only the allowlist
    # match used the normalized (single-dot-stripped) host.
    assert fetcher.calls == ["https://example.com./"]


def test_04_subdomain_of_allowlisted_domain_matches(tmp_path, constitution_dir):
    fetcher = StubFetcher({"https://data.example.com/": ok("https://data.example.com/")})
    w = build_world(tmp_path, constitution_dir, fetcher=fetcher)
    gate, authority, adapter = w["gate"], w["authority"], w["adapter"]

    intent = http_intent(w["evidence"], target="https://data.example.com/")
    approval = authority.issue_approval(gate.fingerprint(intent))
    episode = gate.run(intent, adapter=adapter, approval=approval)

    assert episode.closed is True and episode.close_reason == "completed"
    assert fetcher.calls == ["https://data.example.com/"]


# -------------------------------------------------------------- hostile


def test_05_f1_suffix_bypass_notgov_refused(tmp_path, constitution_dir):
    # DALEOBANKS finding F1: endswith("gov") matched notgov.example.
    # Label-exact matching refuses it before any byte crosses the wire.
    assert host_allowed("notgov.example", ("gov",)) is False
    fetcher = StubFetcher({"https://notgov.example/": ok("https://notgov.example/", ATTACKER_MARKER.encode())})
    w = build_world(tmp_path, constitution_dir, fetcher=fetcher, allowlist=("gov",))
    gate, authority, adapter = w["gate"], w["authority"], w["adapter"]

    intent = http_intent(w["evidence"], target="https://notgov.example/")
    approval = authority.issue_approval(gate.fingerprint(intent))
    with pytest.raises(errors.ExecutionRefusal, match="allowlist"):
        gate.run(intent, adapter=adapter, approval=approval)

    assert fetcher.calls == []  # refused before the socket
    assert_failed_closed(w)


def test_06_evil_example_com_refused(tmp_path, constitution_dir):
    assert host_allowed("evil-example.com", ("example.com",)) is False
    fetcher = StubFetcher({"https://evil-example.com/": ok("https://evil-example.com/", ATTACKER_MARKER.encode())})
    w = build_world(tmp_path, constitution_dir, fetcher=fetcher)
    gate, authority, adapter = w["gate"], w["authority"], w["adapter"]

    intent = http_intent(w["evidence"], target="https://evil-example.com/")
    approval = authority.issue_approval(gate.fingerprint(intent))
    with pytest.raises(errors.ExecutionRefusal, match="allowlist"):
        gate.run(intent, adapter=adapter, approval=approval)

    assert fetcher.calls == []
    assert_failed_closed(w)


def test_07_http_scheme_downgrade_refused(tmp_path, constitution_dir):
    fetcher = StubFetcher({"http://example.com/": ok("http://example.com/", ATTACKER_MARKER.encode())})
    w = build_world(tmp_path, constitution_dir, fetcher=fetcher)
    gate, authority, adapter = w["gate"], w["authority"], w["adapter"]

    intent = http_intent(w["evidence"], target="http://example.com/")
    approval = authority.issue_approval(gate.fingerprint(intent))
    with pytest.raises(errors.ExecutionRefusal, match="https-only"):
        gate.run(intent, adapter=adapter, approval=approval)

    assert fetcher.calls == []
    assert_failed_closed(w)


def test_08_redirect_to_non_allowlisted_host_refused(tmp_path, constitution_dir):
    fetcher = StubFetcher(
        {
            "https://example.com/": FetchResult(
                status_code=302, body=b"", final_url="https://evil.example/steal"
            ),
            "https://evil.example/steal": ok("https://evil.example/steal", ATTACKER_MARKER.encode()),
        }
    )
    w = build_world(tmp_path, constitution_dir, fetcher=fetcher)
    gate, authority, adapter = w["gate"], w["authority"], w["adapter"]

    intent = http_intent(w["evidence"])
    approval = authority.issue_approval(gate.fingerprint(intent))
    with pytest.raises(errors.ExecutionRefusal, match="allowlist"):
        gate.run(intent, adapter=adapter, approval=approval)

    # The redirect target was re-checked against the allowlist and NEVER fetched.
    assert fetcher.calls == ["https://example.com/"]
    assert_failed_closed(w)


def test_09_redirect_chain_length_4_refused(tmp_path, constitution_dir):
    hops = "abcde"
    chain = {
        f"https://example.com/{hops[i]}": FetchResult(
            status_code=302, body=b"", final_url=f"https://example.com/{hops[i + 1]}"
        )
        for i in range(len(hops) - 1)
    }
    fetcher = StubFetcher(chain)
    w = build_world(tmp_path, constitution_dir, fetcher=fetcher)
    gate, authority, adapter = w["gate"], w["authority"], w["adapter"]

    intent = http_intent(w["evidence"], target="https://example.com/a")
    approval = authority.issue_approval(gate.fingerprint(intent))
    with pytest.raises(errors.ExecutionRefusal, match="exceeds 3 hops"):
        gate.run(intent, adapter=adapter, approval=approval)

    # 3 hops followed, the 4th redirect refused; the 5th URL never fetched.
    assert fetcher.calls == [f"https://example.com/{hop}" for hop in "abcd"]
    assert_failed_closed(w)


def test_10_oversize_body_refused_not_truncated(tmp_path, constitution_dir):
    oversize = ATTACKER_MARKER.encode() + b"x" * (DEFAULT_MAX_BYTES + 1)
    fetcher = StubFetcher({"https://example.com/": ok("https://example.com/", oversize)})
    w = build_world(tmp_path, constitution_dir, fetcher=fetcher)
    gate, authority, adapter = w["gate"], w["authority"], w["adapter"]

    intent = http_intent(w["evidence"])
    approval = authority.issue_approval(gate.fingerprint(intent))
    with pytest.raises(errors.ExecutionRefusal, match="cap"):
        gate.run(intent, adapter=adapter, approval=approval)

    assert fetcher.calls == ["https://example.com/"]
    assert_failed_closed(w)


def test_11_non_2xx_status_refused(tmp_path, constitution_dir):
    fetcher = StubFetcher(
        {"https://example.com/": FetchResult(status_code=404, body=ATTACKER_MARKER.encode(), final_url="https://example.com/")}
    )
    w = build_world(tmp_path, constitution_dir, fetcher=fetcher)
    gate, authority, adapter = w["gate"], w["authority"], w["adapter"]

    intent = http_intent(w["evidence"])
    approval = authority.issue_approval(gate.fingerprint(intent))
    with pytest.raises(errors.ExecutionRefusal, match="non-2xx"):
        gate.run(intent, adapter=adapter, approval=approval)

    assert fetcher.calls == ["https://example.com/"]
    assert_failed_closed(w)


def test_12_wrong_action_type_refused_by_adapter(tmp_path, constitution_dir):
    # The CommitWitness carries no action_type (WP-01 shape), so the adapter
    # enforces the research_fetch family by target shape: a witness minted
    # for shell_exec holds a non-https target and is refused by the ADAPTER —
    # proven by the refusal landing at stage EXECUTE with a witness on record.
    fetcher = StubFetcher({})
    w = build_world(tmp_path, constitution_dir, fetcher=fetcher)
    gate, authority, adapter = w["gate"], w["authority"], w["adapter"]

    intent = http_intent(
        w["evidence"], action_type="shell_exec", target="subprocess:rm-rf-home"
    )
    approval = authority.issue_approval(gate.fingerprint(intent))
    with pytest.raises(errors.ExecutionRefusal, match="https-only"):
        gate.run(intent, adapter=adapter, approval=approval)

    assert spine_payload(w["spine"], "CommitWitness") != []  # reached EXECUTE
    assert fetcher.calls == []
    assert_failed_closed(w)


def test_13_direct_adapter_call_without_witness_refused(tmp_path, constitution_dir):
    captured = {}

    def capture(gate, ctx):
        captured["witness"] = ctx.witness

    fetcher = StubFetcher({"https://example.com/": ok("https://example.com/")})
    w = build_world(
        tmp_path, constitution_dir, fetcher=fetcher, interceptors={"WITNESS": [capture]}
    )
    gate, authority, adapter = w["gate"], w["authority"], w["adapter"]

    # (a) Protocol level: witness is a required argument.
    with pytest.raises(TypeError):
        adapter.execute()
    # (b) No witness, no execute (Hard Rule 1).
    with pytest.raises(errors.WitnessMissing):
        adapter.execute(None)
    # (c) A non-witness object is refused.
    with pytest.raises(errors.WitnessRefusal):
        adapter.execute({"intent_fingerprint": "f" * 64})

    # One legitimate gate-driven execution to mint a real witness...
    intent = http_intent(w["evidence"])
    approval = authority.issue_approval(gate.fingerprint(intent))
    episode = gate.run(intent, adapter=adapter, approval=approval)
    assert episode.closed is True and adapter.calls == 1
    real_witness = captured["witness"]

    # (d) ...then a tampered or forged witness is refused without any fetch.
    tampered = real_witness.model_copy(update={"exact_target": "https://example.com/other"})
    with pytest.raises(errors.WitnessRefusal):
        adapter.execute(tampered)
    forged_sig = real_witness.model_copy(update={"witness_signature": "00" * 64})
    with pytest.raises(errors.WitnessRefusal):
        adapter.execute(forged_sig)
    # (e) Replaying the already-spent real witness is refused (one_use).
    with pytest.raises(errors.DuplicateExecution):
        adapter.execute(real_witness)

    assert adapter.calls == 1  # only the gate-driven execution ran
    assert fetcher.calls == ["https://example.com/"]
    assert w["spine"].verify_chain() is True


def test_14_witness_for_url_a_intent_for_url_b_refused(tmp_path, constitution_dir):
    # Target substitution regression: mutate the intent target AFTER the
    # witness (for URL A) was issued; REAUTHORIZE catches the fingerprint
    # drift before the adapter is ever invoked.
    def tamper(gate, ctx):
        ctx.intent = ctx.intent.model_copy(update={"target": "https://example.com/b"})

    fetcher = StubFetcher(
        {
            "https://example.com/a": ok("https://example.com/a", ATTACKER_MARKER.encode()),
            "https://example.com/b": ok("https://example.com/b", ATTACKER_MARKER.encode()),
        }
    )
    w = build_world(
        tmp_path, constitution_dir, fetcher=fetcher, interceptors={"WITNESS": [tamper]}
    )
    gate, authority, adapter = w["gate"], w["authority"], w["adapter"]

    intent = http_intent(w["evidence"], target="https://example.com/a")
    approval = authority.issue_approval(gate.fingerprint(intent))
    with pytest.raises(errors.ReauthorizationRefusal):
        gate.run(intent, adapter=adapter, approval=approval)

    assert adapter.calls == 0
    assert fetcher.calls == []  # adapter never invoked
    (refusal,) = spine_records(w["spine"], "GATE_REFUSAL")
    assert refusal["refs"]["stage"] == "REAUTHORIZE"
    assert spine_payload(w["spine"], "ExecutionReceipt") == []
    assert ATTACKER_MARKER not in json.dumps(list(w["spine"].iter()))
    assert w["spine"].verify_chain() is True


def test_15_transport_timeout_refused_episode_failed_chain_verifies(tmp_path, constitution_dir):
    fetcher = StubFetcher({"https://example.com/": TimeoutError("timed out")})
    w = build_world(tmp_path, constitution_dir, fetcher=fetcher)
    gate, authority, adapter = w["gate"], w["authority"], w["adapter"]

    intent = http_intent(w["evidence"])
    approval = authority.issue_approval(gate.fingerprint(intent))
    with pytest.raises(errors.ExecutionRefusal, match="transport failed"):
        gate.run(intent, adapter=adapter, approval=approval)

    assert fetcher.calls == ["https://example.com/"]
    assert_failed_closed(w)
    episode = spine_payload(w["spine"], "DecisionEpisode")[-1]
    assert "transport failed" in episode["close_reason"]
