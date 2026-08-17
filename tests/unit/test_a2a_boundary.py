from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path

import pytest

from boundary import A2ABoundary, BoundaryRefused, ProposalBoundary
from moduleloader import FrozenContractSchemas


NOW = datetime(2026, 8, 12, 0, 1, tzinfo=timezone.utc)
SENDER = "spiffe://uniimente.internal/agent/peer-agent"


@dataclass(frozen=True)
class Advertisement:
    capability_id: str

    def within(self, consequence_class: str) -> bool:
        return consequence_class == "read_only"


class Directory:
    def lookup(self, capability_id: str):
        if capability_id != "kernel.capability_discovery":
            raise KeyError(capability_id)
        return Advertisement(capability_id)


class ReplayStore:
    def __init__(self):
        self.seen = set()

    def claim(self, key):
        if key in self.seen:
            return False
        self.seen.add(key)
        return True


def envelope(**updates):
    value = {
        "confers_authority": False,
        "disposition": "PROPOSAL",
        "envelope_id": "a2a-00000001",
        "issued_at": "2026-08-12T00:00:00Z",
        "nonce": "abcdef0123456789abcd",
        "payload": {"question": "status?"},
        "payload_kind": "question",
        "protocol": "a2a",
        "protocol_version": "1.0.0",
        "sender": {
            "authenticated": True,
            "authentication_method": "mtls",
            "identity": SENDER,
            "identity_is_isolated": True,
        },
    }
    value.update(updates)
    return value


def adapter(store=None):
    store = store or ReplayStore()
    return A2ABoundary(
        ProposalBoundary(
            capability_directory=Directory(),
            resolve_sender=lambda identity: (identity == SENDER, "mtls:test-chain"),
            record_replay_key=store.claim,
        )
    )


def test_a2a_is_normalized_to_the_same_inert_proposal_contract():
    admitted = adapter().admit(envelope(), now=NOW)
    assert admitted.protocol == "a2a"
    assert admitted.protocol_version == "1.0.0"
    assert admitted.disposition == "PROPOSAL"
    assert admitted.confers_authority is False
    assert admitted.execution_eligible is False


def test_mcp_document_cannot_cross_a2a_adapter():
    with pytest.raises(BoundaryRefused) as error:
        adapter().admit(envelope(protocol="mcp"), now=NOW)
    assert error.value.code == "PROTOCOL_MISMATCH"


def test_a2a_mtls_must_report_isolated_identity():
    value = envelope()
    value["sender"]["identity_is_isolated"] = False
    with pytest.raises(BoundaryRefused) as error:
        adapter().admit(value, now=NOW)
    assert error.value.code == "ISOLATION_EVIDENCE_REQUIRED"


def test_a2a_untrusted_or_unauthenticated_sender_is_refused():
    value = envelope()
    value["sender"]["authenticated"] = False
    with pytest.raises(BoundaryRefused) as error:
        adapter().admit(value, now=NOW)
    assert error.value.code == "SENDER_NOT_AUTHENTICATED"


def test_a2a_replay_and_version_downgrade_are_refused():
    instance = adapter()
    instance.admit(envelope(), now=NOW)
    with pytest.raises(BoundaryRefused) as error:
        instance.admit(envelope(), now=NOW)
    assert error.value.code == "REPLAY_REFUSED"
    with pytest.raises(BoundaryRefused) as error:
        adapter().admit(envelope(protocol_version="0.9.0"), now=NOW)
    assert error.value.code == "UNSUPPORTED_PROTOCOL_VERSION"


def test_a2a_evidence_is_frozen_schema_valid():
    path = Path(__file__).parents[2] / "boundary" / "A2A_EVIDENCE.json"
    document = json.loads(path.read_text(encoding="utf-8"))
    assert FrozenContractSchemas().validate_evidence_record(document) == document
