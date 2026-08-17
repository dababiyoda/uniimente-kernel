from __future__ import annotations

import ast
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import pytest

from moduleloader import (
    ComparisonEvidence,
    GovernedModuleLoader,
    Lifecycle,
    LoaderRefused,
    ModuleDescriptor,
    PinnedModule,
    FrozenContractSchemas,
)
from moduleloader.integrity import sha256_bytes


NOW = datetime(2026, 8, 12, 0, 1, tzinfo=timezone.utc)
PRINCIPAL = "spiffe://uniimente.internal/agent/module-owner"
OPERATOR = "spiffe://uniimente.internal/organ/constitutional-controller"


@dataclass(frozen=True)
class Advertisement:
    capability_id: str
    ceiling: str = "internal_write"
    organ_status: str = "active"

    def within(self, consequence_class: str) -> bool:
        order = ("read_only", "internal_write", "external_contact", "financial", "irreversible")
        return order.index(consequence_class) <= order.index(self.ceiling)


class Directory:
    def __init__(self, advertisements: tuple[Advertisement, ...]):
        self._by_id = {item.capability_id: item for item in advertisements}

    def lookup(self, capability_id: str) -> Advertisement:
        return self._by_id[capability_id]

    def offers(self, query=None) -> tuple[Advertisement, ...]:
        return tuple(item for item in self._by_id.values() if item.organ_status in {"active", "this_repository"})


def request(capability_id: str = "kernel.capability_discovery") -> dict:
    return {
        "request_version": "1.0.0",
        "capability_id": capability_id,
        "requested_by": PRINCIPAL,
        "consequence_class": "read_only",
        "legal_principal": "alfonso_lopez",
        "reversible": True,
        "grant_reference": None,
    }


def descriptor(version: str, artifact: bytes, capability_id: str = "kernel.capability_discovery") -> ModuleDescriptor:
    return ModuleDescriptor(
        module_id="candidate-reader",
        module_principal=PRINCIPAL,
        version=version,
        artifact_digest=sha256_bytes(artifact),
        genome_ref=f"genome:{version}",
        state_schema_digest=sha256_bytes(b"state-v1"),
        requested_consequence_class="read_only",
        containment_tier="in_process",
        capability_ids=(capability_id,),
        capability_requests=(request(capability_id),),
    )


def make_loader(*pairs: tuple[ModuleDescriptor, bytes], directory: Directory | None = None):
    allowlist = tuple(
        PinnedModule(item.key, item.descriptor_digest, item.artifact_digest)
        for item, _ in pairs
    )
    return GovernedModuleLoader(
        verify_authority=lambda actor, ref, operation, target: (True, f"checked:{ref}"),
        verify_genome=lambda item: (True, f"genome-evidence:{item.genome_ref}"),
        resolve_containment=lambda item: (True, "policy-only:test-evidence"),
        capability_directory=directory or Directory((Advertisement("kernel.capability_discovery"),)),
        allowlist=allowlist,
        clock=lambda: NOW,
    )


def install(loader: GovernedModuleLoader, item: ModuleDescriptor, artifact: bytes):
    receipt = loader.validate(item, artifact)
    return loader.install(item, artifact, receipt, actor=OPERATOR, authority_ref="approval:1")


def test_full_lifecycle_is_eligibility_only_and_event_chain_is_intact():
    artifact = b"opaque candidate bytes"
    item = descriptor("1.0.0", artifact)
    loader = make_loader((item, artifact))
    assert install(loader, item, artifact).lifecycle == Lifecycle.INSTALLED
    loader.attach(item.key, "organ:kernel", actor=OPERATOR, authority_ref="approval:2")
    active = loader.activate(item.key, actor=OPERATOR, authority_ref="approval:3")
    assert active.lifecycle == Lifecycle.ACTIVE
    assert loader.events[-1].detail == {
        "containment_attestation_ref": "policy-only:test-evidence",
        "authority_created": False,
        "execution": "none",
    }
    loader.pause(item.key, actor=OPERATOR, authority_ref="approval:4")
    loader.detach(item.key, actor=OPERATOR, authority_ref="approval:5")
    loader.archive(item.key, actor=OPERATOR, authority_ref="approval:6")
    assert loader.restore(item.key, actor=OPERATOR, authority_ref="approval:7").lifecycle == Lifecycle.DETACHED
    assert loader.verify_event_chain()[0] is True


def test_detach_always_succeeds():
    """A valid operator can force quiescence; candidate code has no veto path."""
    for initial in (Lifecycle.INSTALLED, Lifecycle.ATTACHED, Lifecycle.ACTIVE, Lifecycle.PAUSED, Lifecycle.SHADOW):
        artifact = f"artifact:{initial.value}".encode()
        item = descriptor(initial.value, artifact)
        loader = make_loader((item, artifact))
        install(loader, item, artifact)
        if initial != Lifecycle.INSTALLED:
            loader.attach(item.key, "organ:kernel", actor=OPERATOR, authority_ref="attach")
        if initial == Lifecycle.ACTIVE:
            loader.activate(item.key, actor=OPERATOR, authority_ref="activate")
        elif initial == Lifecycle.PAUSED:
            loader.activate(item.key, actor=OPERATOR, authority_ref="activate")
            loader.pause(item.key, actor=OPERATOR, authority_ref="pause")
        elif initial == Lifecycle.SHADOW:
            loader.shadow(item.key, actor=OPERATOR, authority_ref="shadow")
        detached = loader.detach(item.key, actor=OPERATOR, authority_ref="detach")
        assert detached.lifecycle == Lifecycle.DETACHED
        assert detached.attachments == set()
        assert loader.detach(item.key, actor=OPERATOR, authority_ref="detach").lifecycle == Lifecycle.DETACHED


def test_allowlist_is_exact_and_checked_before_genome_or_storage():
    artifact = b"pinned"
    item = descriptor("1.0.0", artifact)
    calls = []
    loader = GovernedModuleLoader(
        verify_authority=lambda *args: (True, "authority"),
        verify_genome=lambda value: (calls.append(value.key) or True, "genome"),
        resolve_containment=lambda value: (True, "containment"),
        capability_directory=Directory((Advertisement("kernel.capability_discovery"),)),
        allowlist=(PinnedModule(item.key, item.descriptor_digest, item.artifact_digest),),
        clock=lambda: NOW,
    )
    altered = descriptor("1.0.0", b"not pinned")
    with pytest.raises(LoaderRefused) as error:
        loader.validate(altered, b"not pinned")
    assert error.value.code == "ALLOWLIST_DESCRIPTOR_MISMATCH"
    assert calls == []


def test_unknown_and_unattached_capabilities_fail_closed():
    artifact = b"candidate"
    unknown = descriptor("1.0.0", artifact, "unknown.capability")
    loader = make_loader((unknown, artifact), directory=Directory(()))
    with pytest.raises(LoaderRefused) as error:
        loader.validate(unknown, artifact)
    assert error.value.code == "UNKNOWN_CAPABILITY"

    planned = descriptor("1.0.1", artifact, "planned.capability")
    planned_directory = Directory((Advertisement("planned.capability", organ_status="planned"),))
    loader = make_loader((planned, artifact), directory=planned_directory)
    with pytest.raises(LoaderRefused) as error:
        loader.validate(planned, artifact)
    assert error.value.code == "CAPABILITY_NOT_ATTACHED"


def test_capability_request_is_exact_frozen_schema_and_not_a_grant():
    artifact = b"candidate"
    item = descriptor("1.0.0", artifact)
    item.capability_requests[0]["surprise"] = "not sealed"
    loader = make_loader((item, artifact))
    with pytest.raises(LoaderRefused) as error:
        loader.validate(item, artifact)
    assert error.value.code == "CAPABILITY_REQUEST_REFUSED"


def test_module_cannot_manage_itself():
    artifact = b"candidate"
    item = descriptor("1.0.0", artifact)
    loader = make_loader((item, artifact))
    receipt = loader.validate(item, artifact)
    with pytest.raises(LoaderRefused) as error:
        loader.install(item, artifact, receipt, actor=PRINCIPAL, authority_ref="self")
    assert error.value.code == "SELF_MANAGEMENT_REFUSED"


def test_replace_rollback_and_state_roundtrip_preserve_both_versions():
    old_artifact, new_artifact = b"old", b"new"
    old, new = descriptor("1.0.0", old_artifact), descriptor("2.0.0", new_artifact)
    loader = make_loader((old, old_artifact), (new, new_artifact))
    install(loader, old, old_artifact)
    install(loader, new, new_artifact)
    for item in (old, new):
        loader.attach(item.key, "organ:kernel", actor=OPERATOR, authority_ref="attach")
    loader.activate(old.key, actor=OPERATOR, authority_ref="activate")
    loader.shadow(new.key, actor=OPERATOR, authority_ref="shadow")
    evidence = ComparisonEvidence.create(
        incumbent_key=old.key,
        candidate_key=new.key,
        qualified=True,
        evidence_refs=("test:qualified",),
    )
    loader.compare(evidence, actor=OPERATOR, authority_ref="compare")
    old_record, new_record = loader.replace(old.key, new.key, actor=OPERATOR, authority_ref="replace")
    assert old_record.lifecycle == Lifecycle.SUPERSEDED
    assert new_record.lifecycle == Lifecycle.ACTIVE
    failed, restored = loader.rollback(new.key, actor=OPERATOR, authority_ref="rollback")
    assert failed.lifecycle == Lifecycle.SUPERSEDED
    assert restored.lifecycle == Lifecycle.ACTIVE

    loader.pause(old.key, actor=OPERATOR, authority_ref="pause")
    snapshot = loader.export_state(old.key, b'{"count":1}', actor=OPERATOR, authority_ref="export")
    assert loader.import_state(old.key, snapshot, actor=OPERATOR, authority_ref="import") == b'{"count":1}'


def test_loader_has_no_candidate_import_or_execution_primitive():
    source = Path(__file__).parents[2] / "moduleloader" / "loader.py"
    tree = ast.parse(source.read_text(encoding="utf-8"))
    forbidden = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id in {"__import__", "eval", "exec", "compile"}:
                forbidden.append(node.func.id)
            if isinstance(node.func, ast.Attribute) and node.func.attr in {"import_module", "load_module", "exec_module"}:
                forbidden.append(node.func.attr)
    assert forbidden == []
    public = {node.name for node in tree.body if isinstance(node, ast.FunctionDef)}
    assert not ({"execute", "run", "invoke", "call"} & public)


def test_moduleloader_evidence_is_frozen_schema_valid():
    path = Path(__file__).parents[2] / "moduleloader" / "EVIDENCE.json"
    document = json.loads(path.read_text(encoding="utf-8"))
    assert FrozenContractSchemas().validate_evidence_record(document) == document
