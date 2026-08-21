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

import ast
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
#:   "5"  IMPLEMENTATION_PATH additionally accepts `peer:<organ>/<path>`, resolved
#:        against a commit-pinned peer attestation. This *widens* what can
#:        resolve, which is why it is a standard change: it corrects the
#:        understatement BLK-6 records rather than tightening anything.
#:   "4"  TEST_NODE requires a body capable of failing; IMPLEMENTATION_PATH
#:        refuses an empty file or directory; CONTRACT_SCHEMA refuses a schema
#:        that constrains nothing.
#:   "3"  EXTERNAL_OUTCOME requires an `OutcomeRecord` conforming to
#:        `contracts/outcome.schema.json`, with `validation_status:
#:        externally_verified` and at least one evidence reference. Previously any
#:        file containing the word "reconciled" satisfied it, which made HARDENED
#:        — and the Single Bottleneck Metric — reachable by a sentence.
EVIDENCE_STANDARD = "5"

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


def weak_spec_anchors(root: str = KERNEL_ROOT) -> tuple[tuple[int, str], ...]:
    """Spec anchors that appear only in prose, never as a heading.

    Reporting only: this changes no rung. `_resolve_spec` accepts an anchor found
    anywhere in the document, so "the document mentions this phrase" and "the
    document has a section on this" resolve identically. The second is a
    specification; the first may be a passing sentence.

    Tightening it to require a heading would drop the technologies listed here to
    UNSUPPORTED, which is a material change to what the institution claims to
    have specified. Whether prose mention counts as a specification is a
    documentation-standard question, so it is surfaced rather than decided here.
    """
    from blueprint.registry import BINDINGS

    weak: list[tuple[int, str]] = []
    for technology_id, binding in sorted(BINDINGS.items()):
        for ref in binding.evidence:
            if ref.kind is not EvidenceKind.SPEC_DOCUMENT:
                continue
            document, _, anchor = ref.locator.partition("#")
            if not anchor:
                continue
            target = _safe_join(root, document)
            if target is None or not os.path.isfile(target):
                continue
            with open(target, encoding="utf-8") as fh:
                lines = fh.read().splitlines()
            if not any(line.lstrip().startswith("#") and anchor in line for line in lines):
                weak.append((technology_id, ref.locator))
    return tuple(weak)


# --------------------------------------------------------------------------
# Resolution
# --------------------------------------------------------------------------

def _resolve_peer_path(root: str, ref: EvidenceRef) -> Resolution:
    """A path in a peer organ's repository, via a commit-pinned attestation.

    Closes the understatement BLK-6 records: capabilities implemented in
    DALEOBANKS or WealthMachineIntelligence stood at BLUEPRINT here because the
    binder can only see this repository.

    The wording of a successful resolution matters. It says *attested*, not
    *present*: the binder did not look at the peer tree, it read a record stating
    what was there at a named commit with a named digest. That claim is refutable
    by anyone who fetches the commit, which is the difference between an
    unverifiable assertion and evidence.
    """
    from blueprint.peer_evidence import load_all, split_locator

    split = split_locator(ref.locator)
    if split is None:
        return Resolution(ref, False,
                          f"malformed peer locator (want peer:<organ>/<path>): "
                          f"{ref.locator}")
    organ, path = split
    attestations = load_all(root)
    attestation = attestations.get(organ)
    if attestation is None:
        return Resolution(
            ref, False,
            f"no attestation on record for peer organ {organ!r}; a peer path "
            "cannot be evidence until a commit-pinned attestation exists "
            "(generate with: python -m blueprint.peer_evidence)")
    recorded = attestation.by_path().get(path)
    if recorded is None:
        return Resolution(
            ref, False,
            f"the {organ} attestation at commit {attestation.commit[:7]} does not "
            f"cover {path!r}; attesting a repository does not attest every path in it")
    return Resolution(
        ref, True,
        f"attested in {attestation.repository} at commit "
        f"{attestation.commit[:7]}: {recorded.kind} {path} "
        f"({recorded.digest or str(recorded.size) + ' entries'})")


def _resolve_path(root: str, ref: EvidenceRef) -> Resolution:
    if ref.locator.startswith("peer:"):
        return _resolve_peer_path(root, ref)
    target = _safe_join(root, ref.locator)
    if target is None:
        return Resolution(ref, False, f"locator escapes the repository: {ref.locator}")
    if not os.path.exists(target):
        return Resolution(ref, False, f"path does not exist: {ref.locator}")
    if os.path.isdir(target):
        if not any(name for name in os.listdir(target) if not name.startswith(".")):
            return Resolution(ref, False,
                              f"directory {ref.locator} is empty; SKETCHED means code "
                              "exists on disk, and an empty directory is not code")
        return Resolution(ref, True, f"directory present: {ref.locator}")
    if os.path.getsize(target) == 0:
        return Resolution(ref, False,
                          f"file {ref.locator} is zero bytes; SKETCHED means code "
                          "exists on disk, and an empty file is not code")
    return Resolution(ref, True, f"file present: {ref.locator}")


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


def _body_can_fail(function: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    """Does this test body contain at least one statement capable of failing?

    This is the honest bar, and it is narrower than "the test is any good".
    `assert True` asserts nothing and is skipped; a bare `pass` or a
    docstring-only body cannot fail at all. Any call counts, because a call can
    raise — `jsonschema.validate(record, schema)` is a real check with no
    `assert` in sight, and an assertion detector that only knows the `assert`
    keyword misjudges it. What this cannot prove is that the statement tests the
    *right* thing: `print("ok")` is a call and would pass. The floor moves from
    "a function named test_ exists" to "a function whose body can fail exists".
    """
    for node in ast.walk(function):
        if isinstance(node, ast.Assert):
            if isinstance(node.test, ast.Constant) and bool(node.test.value):
                continue                     # assert True / assert 1 / assert "x"
            return True
        if isinstance(node, (ast.Call, ast.Raise, ast.With, ast.AsyncWith)):
            return True
    return False


def _resolve_test(root: str, ref: EvidenceRef) -> Resolution:
    """A named test that exists and whose body could actually fail.

    Existence alone used to be enough, which is the thin-test vector this
    ladder's own adversarial pass recorded as unresolved: a session could lift a
    rung by adding `def test_x(): pass`. Requiring a body capable of failing
    narrows that. It does not close it, and the module docstring says so.
    """
    match = _TEST_NODE_RE.match(ref.locator)
    if match is None:
        return Resolution(ref, False,
                          f"malformed test node id (want path.py::test_name): {ref.locator}")
    target = _safe_join(root, match.group("path"))
    if target is None or not os.path.isfile(target):
        return Resolution(ref, False, f"test file does not exist: {match.group('path')}")
    name = match.group("name")
    try:
        with open(target, encoding="utf-8") as fh:
            tree = ast.parse(fh.read(), filename=target)
    except (OSError, SyntaxError) as exc:
        return Resolution(ref, False,
                          f"{match.group('path')} could not be parsed: {exc}")
    found = None
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            found = node
            break
    if found is None:
        return Resolution(ref, False, f"{match.group('path')} defines no {name}")
    if not _body_can_fail(found):
        return Resolution(
            ref, False,
            f"{ref.locator} is defined but its body cannot fail: no assertion, "
            "call, raise or context manager. A test that cannot fail does not "
            "exercise anything")
    return Resolution(ref, True, f"test defined and able to fail: {ref.locator}")


def _resolve_contract(root: str, ref: EvidenceRef) -> Resolution:
    known = known_contracts(root)
    if ref.locator not in known:
        return Resolution(ref, False, f"no contracts/{ref.locator}.schema.json")
    path = os.path.join(root, "contracts", f"{ref.locator}.schema.json")
    try:
        with open(path, encoding="utf-8") as fh:
            schema = json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        return Resolution(ref, False, f"contract {ref.locator} is unreadable: {exc}")
    if not isinstance(schema, dict) or not (
            schema.get("properties") or schema.get("required")
            or schema.get("$defs") or schema.get("items")
            or schema.get("oneOf") or schema.get("allOf") or schema.get("anyOf")):
        return Resolution(
            ref, False,
            f"contract {ref.locator} constrains nothing; PROVEN requires a typed "
            "boundary, and a schema that admits every document is not one")
    return Resolution(ref, True, f"contract schema present and constraining: {ref.locator}")


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


#: The only `validation_status` that means reality confirmed it. The contract
#: admits three values and the distinction is the whole point: an outcome the
#: institution observed itself, or reported about itself, is not a reconciled
#: external consequence however sincerely it is written down.
_EXTERNALLY_VERIFIED = "externally_verified"


def _resolve_external_outcome(root: str, ref: EvidenceRef) -> Resolution:
    """A reconciled real-world consequence, typed against the canonical contract.

    This check used to read any file and pass if the word "reconciled" appeared
    anywhere in it. A markdown note reading "we discussed how invoices are
    reconciled in general; nothing happened" satisfied it — and EXTERNAL_OUTCOME
    is the sole requirement of HARDENED, so a passing sentence would have
    awarded the top rung and moved the Single Bottleneck Metric off zero. That
    was the most consequential ceremony vector in the ladder, and it was in the
    binder's own code.

    A reconciled outcome must now be a structured `OutcomeRecord` conforming to
    `contracts/outcome.schema.json`, carrying `validation_status:
    externally_verified` and citing at least one piece of evidence. Prose cannot
    satisfy it, a self-report cannot satisfy it, and a record that cites nothing
    cannot satisfy it.

    Nothing satisfies it today, which is the honest state. The point of the
    tightening is that when the first real outcome arrives, the kernel asks for
    proof rather than for a word.
    """
    target = _safe_join(root, ref.locator)
    if target is None:
        return Resolution(ref, False, f"locator escapes the repository: {ref.locator}")
    if not ref.locator.endswith(".json"):
        return Resolution(
            ref, False,
            f"{ref.locator} is not a JSON outcome record; a reconciled external "
            "outcome is a typed artifact validated against "
            "contracts/outcome.schema.json, never prose")
    if not os.path.isfile(target):
        return Resolution(ref, False,
                          f"no outcome record at {ref.locator} "
                          "(verified outcome count is 0)")
    try:
        with open(target, encoding="utf-8") as fh:
            record = json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        return Resolution(ref, False, f"outcome record {ref.locator} is unreadable: {exc}")
    if not isinstance(record, dict):
        return Resolution(ref, False,
                          f"outcome record {ref.locator} is not an object")

    schema_path = os.path.join(root, "contracts", "outcome.schema.json")
    if not os.path.isfile(schema_path):
        return Resolution(ref, False,
                          "contracts/outcome.schema.json is absent, so no outcome "
                          "can be typed; failing closed rather than accepting it")
    try:
        with open(schema_path, encoding="utf-8") as fh:
            schema = json.load(fh)
        from jsonschema import Draft202012Validator, FormatChecker
        validator = Draft202012Validator(schema, format_checker=FormatChecker())
        errors = sorted(validator.iter_errors(record), key=lambda e: list(e.path))
    except (OSError, json.JSONDecodeError, ImportError) as exc:
        return Resolution(ref, False,
                          f"outcome contract could not be applied ({exc}); "
                          "failing closed")
    if errors:
        first = errors[0]
        where = "/".join(str(p) for p in first.path) or "$"
        return Resolution(
            ref, False,
            f"outcome record {ref.locator} violates contracts/outcome.schema.json "
            f"at {where}: {first.message} ({len(errors)} problem(s))")

    # Backstop, deliberately redundant. `format` keywords are advisory in JSON
    # Schema — a validator without a FormatChecker ignores them entirely, and a
    # FormatChecker silently skips any format whose optional library is absent.
    # Either is a fail-open on the rung that matters most, so the two identity
    # fields and the timestamp are re-checked here. In a normal environment the
    # schema layer above catches these first; this exists for the environment
    # where it quietly does not.
    import uuid as _uuid
    from datetime import datetime as _datetime

    for field in ("outcome_id", "action_ref"):
        try:
            _uuid.UUID(str(record.get(field)))
        except (ValueError, AttributeError, TypeError):
            return Resolution(
                ref, False,
                f"outcome record {ref.locator} has {field}={record.get(field)!r}, "
                "which is not a UUID; the contract declares format uuid and a "
                "default validator does not enforce it")
    stamp = str(record.get("recorded_at", ""))
    try:
        parsed = _datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    except ValueError:
        return Resolution(ref, False,
                          f"outcome record {ref.locator} has recorded_at={stamp!r}, "
                          "which is not an RFC 3339 timestamp")
    if parsed.tzinfo is None:
        return Resolution(ref, False,
                          f"outcome record {ref.locator} has a naive recorded_at; "
                          "an outcome without a timezone cannot be reconciled "
                          "against an external event")

    status = record.get("validation_status")
    if status != _EXTERNALLY_VERIFIED:
        return Resolution(
            ref, False,
            f"outcome record {ref.locator} carries validation_status "
            f"{status!r}; HARDENED requires {_EXTERNALLY_VERIFIED!r}, because an "
            "outcome the institution observed or reported about itself is not a "
            "reconciled external consequence")

    if not record.get("evidence_refs"):
        return Resolution(
            ref, False,
            f"outcome record {ref.locator} cites no evidence_refs; an outcome "
            "that points at nothing checkable is a claim, not a reconciliation")

    return Resolution(
        ref, True,
        f"externally verified outcome {record.get('outcome_id')!r} against action "
        f"{record.get('action_ref')!r}, citing "
        f"{len(record['evidence_refs'])} evidence reference(s): {ref.locator}")


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
