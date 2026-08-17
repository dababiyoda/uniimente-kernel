from __future__ import annotations

import ast
import copy
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import pytest

from boundary import BoundaryRefused, MCPBoundary, ProposalBoundary
from moduleloader import FrozenContractSchemas


NOW = datetime(2026, 8, 12, 0, 1, tzinfo=timezone.utc)
SENDER = "spiffe://uniimente.internal/agent/external-tool"


@dataclass(frozen=True)
class Advertisement:
    capability_id: str
    ceiling: str = "internal_write"

    def within(self, consequence_class: str) -> bool:
        order = ("read_only", "internal_write", "external_contact", "financial", "irreversible")
        return order.index(consequence_class) <= order.index(self.ceiling)


class Directory:
    def __init__(self, advertisements=(Advertisement("kernel.capability_discovery"),)):
        self._items = {item.capability_id: item for item in advertisements}

    def lookup(self, capability_id: str):
        return self._items[capability_id]


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
        "envelope_id": "env-00000001",
        "issued_at": "2026-08-12T00:00:00Z",
        "nonce": "0123456789abcdef0123",
        "payload": {"text": "a reading"},
        "payload_kind": "observation",
        "protocol": "mcp",
        "protocol_version": "1.0.0",
        "sender": {
            "authenticated": True,
            "authentication_method": "hmac_shared_secret",
            "identity": SENDER,
            "identity_is_isolated": False,
        },
    }
    value.update(updates)
    return value


def boundary(directory=None, resolver=None, store=None):
    store = store or ReplayStore()
    core = ProposalBoundary(
        capability_directory=directory or Directory(),
        resolve_sender=resolver or (lambda identity: (identity == SENDER, "identity:test-registry")),
        record_replay_key=store.claim,
    )
    return MCPBoundary(core), store


def test_well_formed_mcp_is_an_inert_proposal_and_shared_hmac_is_not_isolated():
    adapter, _ = boundary()
    source = envelope()
    admitted = adapter.admit(source, now=NOW)
    source["payload"]["text"] = "mutated after admission"
    assert admitted.disposition == "PROPOSAL"
    assert admitted.confers_authority is False
    assert admitted.execution_eligible is False
    assert admitted.requires_kernel_validation is True
    assert admitted.payload == {"text": "a reading"}
    assert admitted.envelope["sender"]["identity_is_isolated"] is False
    for method in ("execute", "run", "invoke", "call", "authorize", "grant"):
        assert not hasattr(admitted, method)


def test_replay_is_refused_by_mandatory_store():
    adapter, _ = boundary()
    adapter.admit(envelope(), now=NOW)
    with pytest.raises(BoundaryRefused) as error:
        adapter.admit(envelope(), now=NOW)
    assert error.value.code == "REPLAY_REFUSED"


@pytest.mark.parametrize("version", ["0.9.0", "1.1.0", "2026-07-28", None])
def test_protocol_version_is_exact_and_never_downgraded(version):
    adapter, _ = boundary()
    with pytest.raises(BoundaryRefused) as error:
        adapter.admit(envelope(protocol_version=version), now=NOW)
    assert error.value.code == "UNSUPPORTED_PROTOCOL_VERSION"


@pytest.mark.parametrize(
    ("mutation", "code"),
    [
        (lambda value: value.update(disposition="INSTRUCTION"), "ENVELOPE_SCHEMA_REFUSED"),
        (lambda value: value.update(confers_authority=True), "ENVELOPE_SCHEMA_REFUSED"),
        (lambda value: value.update(nonce="short"), "ENVELOPE_SCHEMA_REFUSED"),
        (lambda value: value.update(surprise="field"), "ENVELOPE_SCHEMA_REFUSED"),
        (lambda value: value["sender"].update(identity="https://unknown.example"), "ENVELOPE_SCHEMA_REFUSED"),
    ],
)
def test_frozen_negative_vector_shapes_are_refused(mutation, code):
    adapter, _ = boundary()
    value = envelope()
    mutation(value)
    with pytest.raises(BoundaryRefused) as error:
        adapter.admit(value, now=NOW)
    assert error.value.code == code


def test_unknown_sender_and_authentication_contradictions_fail_closed():
    adapter, _ = boundary(resolver=lambda identity: (False, "not registered"))
    with pytest.raises(BoundaryRefused) as error:
        adapter.admit(envelope(), now=NOW)
    assert error.value.code == "UNKNOWN_SENDER"

    adapter, _ = boundary()
    value = envelope()
    value["sender"]["identity_is_isolated"] = True
    with pytest.raises(BoundaryRefused) as error:
        adapter.admit(value, now=NOW)
    assert error.value.code == "SHARED_SECRET_NOT_ISOLATED"


def test_capability_request_is_validated_against_schema_identity_and_discovery():
    payload = {
        "request_version": "1.0.0",
        "capability_id": "kernel.capability_discovery",
        "requested_by": SENDER,
        "consequence_class": "read_only",
        "legal_principal": "alfonso_lopez",
        "reversible": True,
        "grant_reference": None,
    }
    adapter, _ = boundary()
    admitted = adapter.admit(
        envelope(payload_kind="capability_request", payload=payload), now=NOW
    )
    assert admitted.payload == payload

    adapter, _ = boundary()
    mismatched = copy.deepcopy(payload)
    mismatched["requested_by"] = "spiffe://uniimente.internal/agent/other"
    with pytest.raises(BoundaryRefused) as error:
        adapter.admit(envelope(payload_kind="capability_request", payload=mismatched), now=NOW)
    assert error.value.code == "REQUESTER_IDENTITY_MISMATCH"

    adapter, _ = boundary(directory=Directory(()))
    unknown = copy.deepcopy(payload)
    unknown["capability_id"] = "unknown.capability"
    with pytest.raises(BoundaryRefused) as error:
        adapter.admit(envelope(payload_kind="capability_request", payload=unknown), now=NOW)
    assert error.value.code == "UNKNOWN_CAPABILITY"


def test_stale_and_future_envelopes_are_refused_before_replay_claim():
    adapter, store = boundary()
    with pytest.raises(BoundaryRefused) as error:
        adapter.admit(envelope(issued_at="2026-08-11T23:00:00Z"), now=NOW)
    assert error.value.code == "STALE_ENVELOPE"
    assert store.seen == set()
    with pytest.raises(BoundaryRefused) as error:
        adapter.admit(envelope(issued_at="2026-08-12T00:02:00Z"), now=NOW)
    assert error.value.code == "FUTURE_ENVELOPE"
    assert store.seen == set()


def test_boundary_source_has_no_execution_authority_or_network_primitive():
    source = Path(__file__).parents[2] / "boundary" / "core.py"
    tree = ast.parse(source.read_text(encoding="utf-8"))
    forbidden_imports = {"requests", "httpx", "socket", "subprocess", "importlib"}
    observed = set()
    forbidden_calls = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            observed.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            observed.add(node.module.split(".")[0])
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in {
            "exec", "eval", "compile", "__import__"
        }:
            forbidden_calls.append(node.func.id)
    assert observed.isdisjoint(forbidden_imports)
    assert forbidden_calls == []


def test_mcp_evidence_is_frozen_schema_valid():
    path = Path(__file__).parents[2] / "boundary" / "MCP_EVIDENCE.json"
    document = json.loads(path.read_text(encoding="utf-8"))
    assert FrozenContractSchemas().validate_evidence_record(document) == document
