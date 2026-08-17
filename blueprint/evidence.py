"""The evidence binder: a reference resolves against this repository, or not at all.

Doctrine (EVIDENCE BINDING): the blueprint may not award a rung on the strength
of a sentence. Every claim names a locator, and every locator is checked against
the real tree — a file that must exist, a test function that must be defined, a
capability an organ must actually declare, a schema that must be present in the
canonical contracts directory.

Resolution is deliberately static. The binder reads files; it does not import
modules, execute closures, or run tests. An auditor that must run the system to
describe the system cannot be trusted to describe a system that will not run.

Unresolvable is a first-class outcome. It is reported with the reason, and it
lowers the awarded rung. It never becomes a warning that everyone ignores.
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass

import yaml

from blueprint.ladder import EvidenceKind

KERNEL_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONTRACTS_DIR = os.path.join(KERNEL_ROOT, "contracts")
ORGANS_DIR = os.path.join(KERNEL_ROOT, "organs")
CLOSURE_DIR = os.path.join(KERNEL_ROOT, "closure")

#: Which rules were in force when a rung was awarded. Rungs are only comparable
#: across snapshots taken under the same standard — tightening a rule lowers rungs
#: without anything having decayed, and the cycle audit must not read that as
#: regression.
#:
#:   "1"  CLOSURE_MODULE resolved on a textual `ModuleClosures(...)` registration.
#:   "2"  CLOSURE_MODULE requires a commit-pinned report in which the module's
#:        five closures were observed to pass.
EVIDENCE_STANDARD = "2"

_TEST_NODE_RE = re.compile(r"^(?P<path>[\w./-]+\.py)::(?P<name>test_\w+)$")
_MODULE_CLOSURE_RE = re.compile(r"ModuleClosures\(\s*[\"'](?P<name>[\w.-]+)[\"']")


class EvidenceError(ValueError):
    """A malformed evidence reference. Fails closed; never guessed at."""


@dataclass(frozen=True)
class EvidenceRef:
    """One claim, and the locator that must substantiate it.

    `locator` is always interpreted relative to the kernel root, except for
    CONTRACT_SCHEMA (a bare contract name) and MANIFEST_CAPABILITY (a bare
    capability id), which are looked up in their canonical registries.
    """

    kind: EvidenceKind
    locator: str
    note: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.kind, EvidenceKind):
            raise EvidenceError(f"unknown evidence kind {self.kind!r}")
        if not self.locator or not self.locator.strip():
            raise EvidenceError(f"{self.kind.value} reference has an empty locator")
        if os.path.isabs(self.locator):
            raise EvidenceError(
                f"{self.kind.value} locator must be repository-relative, got {self.locator!r}"
            )


@dataclass(frozen=True)
class Resolution:
    ref: EvidenceRef
    ok: bool
    detail: str

    @property
    def kind(self) -> EvidenceKind:
        return self.ref.kind


# --------------------------------------------------------------------------
# Canonical lookups, read once per process from the real tree.
# --------------------------------------------------------------------------

def _safe_join(root: str, rel: str) -> str | None:
    """Join under `root`, refusing anything that escapes it."""
    target = os.path.normpath(os.path.join(root, rel))
    if not (target == root or target.startswith(root + os.sep)):
        return None
    return target


def declared_capability_ids(root: str = KERNEL_ROOT) -> frozenset[str]:
    """Every capability_id any organ manifest actually declares."""
    organs = os.path.join(root, "organs")
    found: set[str] = set()
    if not os.path.isdir(organs):
        return frozenset()
    for name in sorted(os.listdir(organs)):
        if not name.endswith(".manifest.yaml"):
            continue
        with open(os.path.join(organs, name), encoding="utf-8") as fh:
            try:
                doc = yaml.safe_load(fh) or {}
            except yaml.YAMLError:
                continue
        for cap in doc.get("capabilities") or []:
            if isinstance(cap, dict) and cap.get("capability_id"):
                found.add(str(cap["capability_id"]))
    return frozenset(found)


def registered_closure_modules(root: str = KERNEL_ROOT) -> frozenset[str]:
    """Module names registered in any closure registry.

    Parsed textually rather than by import: registering a module must be
    visible in the source, and the binder must not execute the very loops it
    is auditing.
    """
    closure_dir = os.path.join(root, "closure")
    found: set[str] = set()
    if not os.path.isdir(closure_dir):
        return frozenset()
    for name in sorted(os.listdir(closure_dir)):
        if not name.endswith(".py"):
            continue
        with open(os.path.join(closure_dir, name), encoding="utf-8") as fh:
            for match in _MODULE_CLOSURE_RE.finditer(fh.read()):
                found.add(match.group("name"))
    return frozenset(found)


def known_contracts(root: str = KERNEL_ROOT) -> frozenset[str]:
    """Contract names with a real schema file in the canonical contracts dir."""
    contracts = os.path.join(root, "contracts")
    if not os.path.isdir(contracts):
        return frozenset()
    return frozenset(
        n[: -len(".schema.json")]
        for n in os.listdir(contracts)
        if n.endswith(".schema.json")
    )


# --------------------------------------------------------------------------
# Resolution
# --------------------------------------------------------------------------

def _resolve_path(root: str, ref: EvidenceRef) -> Resolution:
    target = _safe_join(root, ref.locator)
    if target is None:
        return Resolution(ref, False, f"locator escapes the repository: {ref.locator}")
    if not os.path.exists(target):
        return Resolution(ref, False, f"path does not exist: {ref.locator}")
    kind = "directory" if os.path.isdir(target) else "file"
    return Resolution(ref, True, f"{kind} present: {ref.locator}")


def _resolve_spec(root: str, ref: EvidenceRef) -> Resolution:
    """A document, optionally required to contain an anchor after '#'."""
    locator, _, anchor = ref.locator.partition("#")
    target = _safe_join(root, locator)
    if target is None:
        return Resolution(ref, False, f"locator escapes the repository: {locator}")
    if not os.path.isfile(target):
        return Resolution(ref, False, f"document does not exist: {locator}")
    if anchor:
        with open(target, encoding="utf-8") as fh:
            if anchor not in fh.read():
                return Resolution(ref, False,
                                  f"document {locator} does not contain {anchor!r}")
        return Resolution(ref, True, f"document {locator} contains {anchor!r}")
    return Resolution(ref, True, f"document present: {locator}")


def _resolve_test(root: str, ref: EvidenceRef) -> Resolution:
    match = _TEST_NODE_RE.match(ref.locator)
    if match is None:
        return Resolution(ref, False,
                          f"malformed test node id (want path.py::test_name): {ref.locator}")
    target = _safe_join(root, match.group("path"))
    if target is None or not os.path.isfile(target):
        return Resolution(ref, False, f"test file does not exist: {match.group('path')}")
    name = match.group("name")
    with open(target, encoding="utf-8") as fh:
        if not re.search(rf"^\s*def {re.escape(name)}\s*\(", fh.read(), re.MULTILINE):
            return Resolution(ref, False,
                              f"{match.group('path')} defines no {name}")
    return Resolution(ref, True, f"test defined: {ref.locator}")


def _resolve_contract(root: str, ref: EvidenceRef) -> Resolution:
    known = known_contracts(root)
    if ref.locator not in known:
        return Resolution(ref, False, f"no contracts/{ref.locator}.schema.json")
    path = os.path.join(root, "contracts", f"{ref.locator}.schema.json")
    try:
        with open(path, encoding="utf-8") as fh:
            json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        return Resolution(ref, False, f"contract {ref.locator} is unreadable: {exc}")
    return Resolution(ref, True, f"contract schema present: {ref.locator}")


def _resolve_manifest_capability(root: str, ref: EvidenceRef) -> Resolution:
    declared = declared_capability_ids(root)
    if ref.locator not in declared:
        return Resolution(ref, False, f"no organ manifest declares {ref.locator}")
    return Resolution(ref, True, f"declared by an organ manifest: {ref.locator}")


def _resolve_closure(root: str, ref: EvidenceRef) -> Resolution:
    """Registration is not passing.

    This check used to succeed on a textual `ModuleClosures("name", ...)` match,
    which meant a registration with five trivially-true stubs would award the
    EXERCISED rung. A rung now requires a commit-pinned report in which the
    module's five closures were observed to pass. The three failure modes are
    reported separately, because "nobody registered it", "nobody proved it" and
    "it was proved to be incomplete" call for different work.
    """
    from closure.report import load as load_closure_proof

    registered = registered_closure_modules(root)
    if ref.locator not in registered:
        return Resolution(ref, False, f"no closure registry registers {ref.locator!r}")

    proof = load_closure_proof(root)
    if proof is None:
        return Resolution(
            ref, False,
            f"{ref.locator} is registered, but no commit-pinned closure report "
            "exists to prove its five closures pass "
            "(regenerate with: python -m closure.report write)")
    if ref.locator not in proof.modules:
        return Resolution(
            ref, False,
            f"{ref.locator} is registered, but the closure report at commit "
            f"{proof.commit[:7]} does not cover it; registration alone does not "
            "earn a rung")
    if ref.locator not in proof.passing:
        return Resolution(
            ref, False,
            f"the closure report at commit {proof.commit[:7]} records "
            f"{ref.locator} as incomplete; open closures: "
            f"{list(proof.open_closures(ref.locator))}")
    return Resolution(
        ref, True,
        f"five closures observed passing at commit {proof.commit[:7]}: {ref.locator}")


def _resolve_external_outcome(root: str, ref: EvidenceRef) -> Resolution:
    """A reconciled real-world consequence.

    Nothing satisfies this today: the Single Bottleneck Metric stands at zero
    verified outcomes. The check is real rather than stubbed so that the first
    genuine outcome resolves without amending the ladder.
    """
    target = _safe_join(root, ref.locator)
    if target is None:
        return Resolution(ref, False, f"locator escapes the repository: {ref.locator}")
    if not os.path.isfile(target):
        return Resolution(ref, False,
                          f"no reconciled outcome record at {ref.locator} "
                          "(verified outcome count is 0)")
    with open(target, encoding="utf-8") as fh:
        body = fh.read()
    if "reconciled" not in body:
        return Resolution(ref, False,
                          f"outcome record {ref.locator} is not marked reconciled")
    return Resolution(ref, True, f"reconciled external outcome: {ref.locator}")


_RESOLVERS = {
    EvidenceKind.SPEC_DOCUMENT: _resolve_spec,
    EvidenceKind.IMPLEMENTATION_PATH: _resolve_path,
    EvidenceKind.TEST_NODE: _resolve_test,
    EvidenceKind.CLOSURE_MODULE: _resolve_closure,
    EvidenceKind.CONTRACT_SCHEMA: _resolve_contract,
    EvidenceKind.MANIFEST_CAPABILITY: _resolve_manifest_capability,
    EvidenceKind.EXTERNAL_OUTCOME: _resolve_external_outcome,
}


def resolve(ref: EvidenceRef, root: str = KERNEL_ROOT) -> Resolution:
    """Check one reference against the real tree. Never raises for a bad locator."""
    resolver = _RESOLVERS.get(ref.kind)
    if resolver is None:  # pragma: no cover - EvidenceKind is closed
        return Resolution(ref, False, f"no resolver for {ref.kind.value}")
    return resolver(root, ref)


def resolve_all(refs, root: str = KERNEL_ROOT) -> tuple[Resolution, ...]:
    return tuple(resolve(ref, root) for ref in refs)


def satisfied_kinds(resolutions) -> frozenset[EvidenceKind]:
    """The evidence kinds that actually resolved. Failures contribute nothing."""
    return frozenset(r.kind for r in resolutions if r.ok)
