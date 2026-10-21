"""Live constitutional integrity: is every protected artifact what Alfonso authorized?

CONTRADICTION-0002 Option A (FOUNDER-RULING-2026-08-23, verbatim in
``docs/deliberations/FOUNDER-RULING-2026-08-23-infinite-goal-chase.md``):

    "Create a separate live constitutional-integrity mechanism whose purpose is
    to detect unauthorized changes to constitutional/authority artifacts. Do
    not use the historical experiment as the live tripwire."

The sealed Package 3 experiment now reads frozen history
(``evolution/repair/continuity``) and answers only "does a historical run
reproduce?". This module answers the live question and nothing else.

## The authorized state

``manifest.json`` lists the protected artifacts: the twelve SR-002 continuity
artifacts, whose baseline is the SR-002 founder-ratified digests (subject
``sr002-0.1.0``, source commit ``07af5758``), and the founder-key file. The
digest each artifact is authorized to have today is computed by replaying
``authorizations.json`` over that baseline. An authorization is an Ed25519
envelope of kind ``INTEGRITY_AUTHORIZE`` naming the artifact, the digest it
moves from, the digest it moves to, a reason, ``issued_at`` and a nonce,
signed by a key listed in ``founder-keys.json``. A path, a caller string, a
document reference, a hash or a workflow's say-so never authorizes anything:
only a signature by an enrolled founder key does.

## Founder keys

``founder-keys.json`` starts empty; no key is invented and none is committed
by an agent. Initial enrollment is a founder act: Alfonso commits his own
public key as ``genesis`` (trust on first use, the same model as
``greg/founder.py``; every check prints the enrolled key ids so a reviewer
sees any change). After that, the key set changes only by an
``INTEGRITY_KEYS`` envelope signed by a key already listed, so a replaced or
added key without such a signature makes the record unsound.

## The records only grow

A record file cannot remember its own past, so the check reads it from git.
In a checkout, every committed version of ``founder-keys.json`` and
``authorizations.json`` reachable from HEAD is read with git plumbing
(``rev-list``, ``cat-file``; no hook, filter or repository code runs): once a
genesis has been committed it never changes, and no committed key change or
authorization may be removed or reordered (each committed list must remain a
subsequence of the current one, so merged concurrent appends pass). This
closes the window in which an edited genesis or a truncated log would
otherwise read as sound: replacing the founder's key before his first
signature, or deleting the latest authorization so that bytes he had since
superseded read as authorized again. A rewrite makes the record unsound; no
signature can authorize one. A shallow checkout in which a record file
already exists at the shallow boundary cannot show that history and is
refused; outside a git checkout (an export, a test tree) the history is not
checked and the report says so.

## Same scheme as greg/founder.py, without importing it at check time

Keys are the PKCS8 Ed25519 keys ``python -m greg founder keygen`` makes; key
ids, canonical JSON and the envelope shape follow ``greg/founder.py`` and
``egregore.contracts.canonical_json`` exactly (``tests/unit/
test_governance_integrity.py`` asserts the equality). This module does not
import them: importing ``greg.founder`` executes ``egregore``, ``policy.engine``
and ``compiler`` code, and a tripwire must not run unprotected repository code
in the process that judges or signs. The check imports only the standard
library and ``cryptography``; the separation is asserted by test. Signatures
use their own domain prefix, so no GREG command can be replayed as an
integrity authorization or the reverse.

## What it does not do

It does not import the sealed experiment and the sealed experiment does not
import it. It does not decide whether a change was wise, and it blocks
nothing: CI fails, a human reads why. It cannot authenticate its own code,
manifest or CI step; edits to those are visible in review, and a unit test
ties the manifest baseline to git history at the SR-002 witness commit.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import PurePosixPath

KERNEL_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

SCOPE = "uniimente-kernel/governance/integrity"
DOMAIN = "uniimente-kernel-integrity-v1\n"
AUTHORIZE = "INTEGRITY_AUTHORIZE"
KEYS = "INTEGRITY_KEYS"
ENVELOPE_FIELDS = frozenset({"version", "kind", "scope", "founder_key_id", "issued_at",
                             "nonce", "body", "signature"})

MANIFEST = "governance/integrity/manifest.json"
FOUNDER_KEYS = "governance/integrity/founder-keys.json"
AUTHORIZATIONS = "governance/integrity/authorizations.json"
#: Governed by their own rules; never moved by an INTEGRITY_AUTHORIZE envelope.
RECORD_FILES = (MANIFEST, FOUNDER_KEYS, AUTHORIZATIONS)
FOUNDER_KEY_LOG = "founder-key-log"
#: Record logs whose committed entries are never removed or reordered.
APPEND_ONLY = {FOUNDER_KEYS: "changes", AUTHORIZATIONS: "authorizations"}

#: A new file here is a constitutional change even though no baseline moved.
WATCHED_TREES = {"constitution": (".ucl",), "authority": (".yaml",), "identity": (".yaml",)}

_HEX64 = re.compile(r"[0-9a-f]{64}")
_NONCE = re.compile(r"[0-9a-f]{32,64}")
_KEY_ID = re.compile(r"ed25519:[0-9a-f]{32}")


class IntegrityRecordError(ValueError):
    """The record of what is authorized is malformed or does not follow from
    itself. Raised, never repaired: no verdict is given on an unsound record."""


class Verdict(str, Enum):
    INTACT = "INTACT"
    UNAUTHORIZED_CHANGE = "UNAUTHORIZED_CHANGE"
    MISSING = "MISSING"
    UNGOVERNED_ADDITION = "UNGOVERNED_ADDITION"


# -- the scheme shared with greg/founder.py -----------------------------------

def canonical_json(value) -> str:
    """Same rule as ``egregore.contracts.canonical_json``."""
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"),
                          ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise IntegrityRecordError(f"value is not canonical JSON: {exc}") from exc


def key_id(public_hex: str) -> str:
    """Same rule as ``greg.founder.key_id``."""
    if not isinstance(public_hex, str) or not _HEX64.fullmatch(public_hex):
        raise IntegrityRecordError("Ed25519 public key must be 64 lowercase hex characters")
    return "ed25519:" + hashlib.sha256(bytes.fromhex(public_hex)).hexdigest()[:32]


def stamp(value: datetime) -> str:
    if value.tzinfo is None:
        raise IntegrityRecordError("timezone-aware clock required")
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _version_one(value) -> bool:
    """Exactly the integer 1: JSON ``true`` and ``1.0`` compare equal to 1 in Python."""
    return type(value) is int and value == 1


def _instant(value) -> datetime:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError as exc:
        raise IntegrityRecordError(f"bad timestamp {value!r}") from exc
    if parsed.tzinfo is None:
        raise IntegrityRecordError("timestamp requires a timezone")
    return parsed


def signing_bytes(envelope: dict) -> bytes:
    unsigned = {k: v for k, v in envelope.items() if k != "signature"}
    return (DOMAIN + canonical_json(unsigned)).encode("utf-8")


def public_hex_of(private_key) -> str:
    from cryptography.hazmat.primitives import serialization
    return private_key.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw).hex()


def sign_envelope(private_key, kind: str, body: dict, *, now: datetime | None = None,
                  nonce: str | None = None) -> dict:
    """Sign one integrity record with a founder key (on the founder's device)."""
    if kind not in (AUTHORIZE, KEYS):
        raise IntegrityRecordError(f"unknown integrity kind {kind!r}")
    envelope = {"version": 1, "kind": kind, "scope": SCOPE,
                "founder_key_id": key_id(public_hex_of(private_key)),
                "issued_at": stamp(now or datetime.now(timezone.utc)),
                "nonce": nonce or secrets.token_hex(16), "body": body}
    envelope["signature"] = private_key.sign(signing_bytes(envelope)).hex()
    return envelope


def verify_envelope(envelope, keys: dict[str, str], kind: str) -> dict:
    """The envelope's body if a listed key signed exactly this record; else raise."""
    if not isinstance(envelope, dict) or set(envelope) != ENVELOPE_FIELDS:
        raise IntegrityRecordError("integrity record needs exactly " + ", ".join(sorted(ENVELOPE_FIELDS)))
    if not _version_one(envelope["version"]) or envelope["kind"] != kind or envelope["scope"] != SCOPE:
        raise IntegrityRecordError(f"not a version-1 {kind} record for {SCOPE}")
    kid = envelope["founder_key_id"]
    if not isinstance(kid, str) or kid not in keys:
        raise IntegrityRecordError(f"signer {kid!r} is not an enrolled founder key")
    if not isinstance(envelope["nonce"], str) or not _NONCE.fullmatch(envelope["nonce"]):
        raise IntegrityRecordError("nonce must be 32-64 lowercase hex characters")
    _instant(envelope["issued_at"])
    if not isinstance(envelope["body"], dict):
        raise IntegrityRecordError("record body must be an object")
    signature = envelope["signature"]
    if not isinstance(signature, str) or not re.fullmatch(r"[0-9a-f]{128}", signature):
        raise IntegrityRecordError("signature must be 128 lowercase hex characters")
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    try:
        Ed25519PublicKey.from_public_bytes(bytes.fromhex(keys[kid])).verify(
            bytes.fromhex(signature), signing_bytes(envelope))
    except (InvalidSignature, ValueError) as exc:
        raise IntegrityRecordError(f"signature by {kid} does not verify") from exc
    return envelope["body"]


# -- reading the records -------------------------------------------------------

def _no_constant(name):
    raise IntegrityRecordError(f"{name} is not JSON")


def _load(root: str, relative: str):
    try:
        with open(os.path.join(root, relative), "rb") as handle:
            return json.loads(handle.read().decode("utf-8"), parse_constant=_no_constant)
    except FileNotFoundError as exc:
        raise IntegrityRecordError(f"{relative} is missing") from exc
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise IntegrityRecordError(f"{relative} is not valid JSON: {exc}") from exc


def _sha256_of(root: str, relative: str) -> str | None:
    try:
        with open(os.path.join(root, relative), "rb") as handle:
            return hashlib.sha256(handle.read()).hexdigest()
    except (FileNotFoundError, IsADirectoryError):
        return None


def _relative_path(value) -> str:
    if not isinstance(value, str) or not value or "\\" in value or "\x00" in value:
        raise IntegrityRecordError(f"bad artifact path {value!r}")
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or "." in path.parts or str(path) != value:
        raise IntegrityRecordError(f"artifact path must be a normalized relative path: {value!r}")
    return value


def _digest(value, what: str) -> str:
    if not isinstance(value, str) or not _HEX64.fullmatch(value):
        raise IntegrityRecordError(f"{what} must be a lowercase sha256 hex digest")
    return value


def _text(value, what: str, limit: int) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise IntegrityRecordError(f"{what} must be non-empty text of at most {limit} characters")
    return value


@dataclass(frozen=True)
class Manifest:
    baseline: dict[str, str]          # path -> SR-002 founder-ratified digest
    founder_keys_genesis_sha256: str  # digest of the key file as first committed (empty)
    source: dict

    @property
    def protected(self) -> tuple[str, ...]:
        return tuple(sorted(self.baseline)) + (FOUNDER_KEYS,)


def load_manifest(root: str = KERNEL_ROOT) -> Manifest:
    raw = _load(root, MANIFEST)
    if not isinstance(raw, dict) or not _version_one(raw.get("version")) or not isinstance(raw.get("artifacts"), list) \
            or set(raw) - {"version", "purpose", "baseline_source", "artifacts"}:
        raise IntegrityRecordError(f"{MANIFEST} must be a version-1 object with an artifacts list")
    baseline: dict[str, str] = {}
    key_log = None
    for entry in raw["artifacts"]:
        if not isinstance(entry, dict):
            raise IntegrityRecordError(f"{MANIFEST}: artifact entries must be objects")
        path = _relative_path(entry.get("path"))
        if path in baseline or path == key_log:
            raise IntegrityRecordError(f"{MANIFEST}: {path} is listed twice")
        if entry.get("rule") == FOUNDER_KEY_LOG:
            if set(entry) != {"path", "rule", "genesis_sha256"} or path != FOUNDER_KEYS or key_log:
                raise IntegrityRecordError(f"{MANIFEST}: the founder-key log entry is malformed")
            key_log = path
            genesis = _digest(entry["genesis_sha256"], "genesis_sha256")
            continue
        if set(entry) != {"path", "baseline_sha256"} or path in RECORD_FILES:
            raise IntegrityRecordError(f"{MANIFEST}: {path} entry must be exactly path and baseline_sha256")
        baseline[path] = _digest(entry["baseline_sha256"], f"{path} baseline_sha256")
    if key_log is None:
        raise IntegrityRecordError(f"{MANIFEST} must protect {FOUNDER_KEYS}")
    if not baseline:
        raise IntegrityRecordError(f"{MANIFEST} protects no artifact")
    return Manifest(baseline=baseline, founder_keys_genesis_sha256=genesis,
                    source=raw.get("baseline_source") or {})


@dataclass(frozen=True)
class FounderKeys:
    keys: dict[str, str]          # key id -> public key hex
    labels: dict[str, str]
    genesis: tuple[str, ...]      # key ids enrolled by the founder's own commit
    changes: int                  # signed INTEGRITY_KEYS records applied
    nonces: frozenset

    @property
    def enrolled(self) -> bool:
        return bool(self.keys)


def _key_entries(entries, what: str) -> dict[str, tuple[str, str]]:
    if not isinstance(entries, list):
        raise IntegrityRecordError(f"{what} must be a list")
    out: dict[str, tuple[str, str]] = {}
    for entry in entries:
        if not isinstance(entry, dict) or set(entry) != {"public_key", "label"}:
            raise IntegrityRecordError(f"{what}: each key needs exactly public_key and label")
        kid = key_id(entry["public_key"])
        if kid in out:
            raise IntegrityRecordError(f"{what}: {kid} appears twice")
        out[kid] = (entry["public_key"], _text(entry["label"], "key label", 64))
    return out


def key_set_digest(keys: dict[str, str], labels: dict[str, str]) -> str:
    listing = [{"key_id": kid, "public_key": keys[kid], "label": labels[kid]} for kid in sorted(keys)]
    return hashlib.sha256(canonical_json(listing).encode("utf-8")).hexdigest()


def load_founder_keys(root: str = KERNEL_ROOT) -> FounderKeys:
    return founder_keys_from(_load(root, FOUNDER_KEYS))


def founder_keys_from(raw) -> FounderKeys:
    """Replay the key log: genesis (the founder's own commit), then signed changes."""
    if not isinstance(raw, dict) or not _version_one(raw.get("version")) or \
            not {"genesis", "changes"} <= set(raw) or set(raw) - {"version", "purpose", "genesis", "changes"}:
        raise IntegrityRecordError(f"{FOUNDER_KEYS} must be a version-1 object with genesis and changes")
    genesis = _key_entries(raw["genesis"], f"{FOUNDER_KEYS} genesis")
    keys = {kid: pub for kid, (pub, _) in genesis.items()}
    labels = {kid: label for kid, (_, label) in genesis.items()}
    if not isinstance(raw["changes"], list):
        raise IntegrityRecordError(f"{FOUNDER_KEYS} changes must be a list")
    if raw["changes"] and not keys:
        raise IntegrityRecordError(f"{FOUNDER_KEYS}: a signed key change needs an enrolled key before it")
    nonces: set[str] = set()
    for index, envelope in enumerate(raw["changes"]):
        body = verify_envelope(envelope, keys, KEYS)
        if envelope["nonce"] in nonces:
            raise IntegrityRecordError(f"{FOUNDER_KEYS} change {index}: nonce reused")
        nonces.add(envelope["nonce"])
        if set(body) != {"previous_keys_sha256", "add", "remove", "reason"}:
            raise IntegrityRecordError(f"{FOUNDER_KEYS} change {index}: body needs exactly "
                                       "previous_keys_sha256, add, remove, reason")
        if body["previous_keys_sha256"] != key_set_digest(keys, labels):
            raise IntegrityRecordError(f"{FOUNDER_KEYS} change {index} does not follow from the key set before it")
        _text(body["reason"], "reason", 1000)
        added = _key_entries(body["add"], f"{FOUNDER_KEYS} change {index} add")
        removed = body["remove"]
        if not isinstance(removed, list) or len(set(removed)) != len(removed) or \
                any(not isinstance(k, str) or k not in keys for k in removed):
            raise IntegrityRecordError(f"{FOUNDER_KEYS} change {index}: remove must list enrolled key ids")
        if not added and not removed:
            raise IntegrityRecordError(f"{FOUNDER_KEYS} change {index} changes nothing")
        for kid in removed:
            del keys[kid], labels[kid]
        for kid, (pub, label) in added.items():
            if kid in keys:
                raise IntegrityRecordError(f"{FOUNDER_KEYS} change {index}: {kid} is already enrolled")
            keys[kid], labels[kid] = pub, label
        if not keys:
            raise IntegrityRecordError(f"{FOUNDER_KEYS} change {index} would leave no founder key")
    return FounderKeys(keys=dict(keys), labels=dict(labels), genesis=tuple(sorted(genesis)),
                       changes=len(raw["changes"]), nonces=frozenset(nonces))


@dataclass(frozen=True)
class AuthorizedState:
    digests: dict[str, str]
    applied: tuple[dict, ...]           # bodies of verified authorizations, in order
    counts: dict[str, int] = field(default_factory=dict)


def load_authorizations(root: str = KERNEL_ROOT) -> list:
    return authorizations_from(_load(root, AUTHORIZATIONS))


def authorizations_from(raw) -> list:
    if not isinstance(raw, dict) or not _version_one(raw.get("version")) or not isinstance(raw.get("authorizations"), list) \
            or set(raw) - {"version", "purpose", "authorizations"}:
        raise IntegrityRecordError(f"{AUTHORIZATIONS} must be a version-1 object with an authorizations list")
    return raw["authorizations"]


def authorized_state(manifest: Manifest, keys: FounderKeys, envelopes: list) -> AuthorizedState:
    """Replay signed authorizations over the SR-002 baseline, in order."""
    digests = dict(manifest.baseline)
    counts: dict[str, int] = {}
    applied = []
    nonces = set(keys.nonces)
    for index, envelope in enumerate(envelopes):
        body = verify_envelope(envelope, keys.keys, AUTHORIZE)
        if envelope["nonce"] in nonces:
            raise IntegrityRecordError(f"authorization {index}: nonce reused")
        nonces.add(envelope["nonce"])
        if set(body) != {"artifact", "previous_sha256", "new_sha256", "reason"}:
            raise IntegrityRecordError(f"authorization {index}: body needs exactly "
                                       "artifact, previous_sha256, new_sha256, reason")
        artifact = _relative_path(body["artifact"])
        if artifact in RECORD_FILES:
            raise IntegrityRecordError(f"authorization {index}: {artifact} is not moved by authorization")
        new = _digest(body["new_sha256"], f"authorization {index} new_sha256")
        previous = body["previous_sha256"]
        if previous is not None:
            _digest(previous, f"authorization {index} previous_sha256")
        current = digests.get(artifact)
        if previous != current:
            raise IntegrityRecordError(
                f"authorization {index} for {artifact} starts from {str(previous)[:12]} but the authorized "
                f"state is {str(current)[:12]}; append a record that follows from it, never edit history")
        if new == previous:
            raise IntegrityRecordError(f"authorization {index} for {artifact} changes nothing")
        _text(body["reason"], "reason", 1000)
        digests[artifact] = new
        counts[artifact] = counts.get(artifact, 0) + 1
        applied.append(dict(body, founder_key_id=envelope["founder_key_id"],
                            issued_at=envelope["issued_at"]))
    return AuthorizedState(digests=digests, applied=tuple(applied), counts=counts)


# -- the committed history of the record files -----------------------------------

@dataclass(frozen=True)
class RecordHistory:
    checked: bool
    versions: int
    note: str


def _git(root: str, *args: str) -> subprocess.CompletedProcess:
    """Run a git plumbing command on ``root``. GIT_* variables are dropped so the
    environment cannot point the reading at another repository."""
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env["GIT_TERMINAL_PROMPT"] = "0"
    try:
        return subprocess.run(["git", "-c", "core.fsmonitor=false", "-C", root, *args],
                              capture_output=True, env=env, timeout=120)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise IntegrityRecordError(f"the git history of the record files is unreadable: {exc}") from exc


def _git_out(root: str, *args: str) -> str:
    proc = _git(root, *args)
    if proc.returncode != 0:
        detail = proc.stderr.decode("utf-8", "replace").strip()[:300]
        raise IntegrityRecordError(f"the git history of the record files is unreadable "
                                   f"(git {args[0]}): {detail}")
    return proc.stdout.decode("utf-8")


def committed_versions(root: str):
    """Every committed version of each append-only record reachable from HEAD,
    oldest first, as ``{path: [(commit, parsed JSON), ...]}``.

    ``None`` when ``root`` is not a git checkout (an export or a test tree).
    Raises when it is one whose record history cannot be read in full: git
    fails, ``root`` is not the top of the checkout, or a record file already
    exists at a shallow boundary, so its earlier versions are not here.
    """
    root = str(root)
    if not os.path.lexists(os.path.join(root, ".git")):
        return None
    top = _git_out(root, "rev-parse", "--show-toplevel").strip()
    if os.path.realpath(top) != os.path.realpath(root):
        raise IntegrityRecordError(f"{root} is not the top of its git checkout ({top})")
    boundary: list[str] = []
    if _git_out(root, "rev-parse", "--is-shallow-repository").strip() == "true":
        shallow = _git_out(root, "rev-parse", "--git-path", "shallow").strip()
        with open(shallow if os.path.isabs(shallow) else os.path.join(root, shallow),
                  encoding="ascii") as handle:
            boundary = handle.read().split()
    if _git(root, "rev-parse", "--verify", "--quiet", "HEAD^{commit}").returncode != 0:
        return {rel: [] for rel in APPEND_ONLY}
    out = {}
    for rel in APPEND_ONLY:
        for commit in boundary:
            if _git(root, "cat-file", "-e", f"{commit}:{rel}").returncode == 0:
                raise IntegrityRecordError(
                    f"{rel} already exists at the shallow boundary {commit[:12]}, so its earlier "
                    "committed versions are not in this checkout; fetch the full history "
                    "(git fetch --unshallow, or actions/checkout with fetch-depth: 0)")
        versions = []
        for commit in _git_out(root, "rev-list", "--full-history", "--reverse", "HEAD", "--", rel).split():
            shown = _git(root, "cat-file", "blob", f"{commit}:{rel}")
            if shown.returncode != 0:
                continue                  # this commit removed the file
            try:
                versions.append((commit, json.loads(shown.stdout.decode("utf-8"), parse_constant=_no_constant)))
            except (UnicodeDecodeError, json.JSONDecodeError, IntegrityRecordError):
                continue                  # never sound at that commit; it constrains nothing
        out[rel] = versions
    return out


def _canonical_items(entries) -> list[str]:
    return [canonical_json(entry) for entry in entries]


def _is_subsequence(earlier: list[str], later: list[str]) -> bool:
    remaining = iter(later)
    return all(any(item == candidate for candidate in remaining) for item in earlier)


def check_record_history(current: dict, versions) -> RecordHistory:
    """Committed records only grow. ``current`` maps each record path to its
    parsed content; ``versions`` is ``committed_versions(root)``.

    Raises when a committed genesis changed, or a committed key change or
    authorization was removed or reordered: the record no longer follows from
    its own history, and no signature can authorize a rewrite.
    """
    if versions is None:
        return RecordHistory(False, 0, "not a git checkout: the append-only history of the "
                                       "record files was not checked")
    seen = 0
    for rel, list_name in APPEND_ONLY.items():
        now = _canonical_items(current[rel][list_name])
        for commit, old in versions.get(rel, []):
            seen += 1
            if not isinstance(old, dict):
                continue
            genesis = old.get("genesis") if rel == FOUNDER_KEYS else None
            if isinstance(genesis, list) and genesis and \
                    canonical_json(genesis) != canonical_json(current[rel]["genesis"]):
                raise IntegrityRecordError(
                    f"{FOUNDER_KEYS}: genesis differs from the genesis committed in {commit[:12]}. "
                    "Genesis is the founder's own first commit and never changes; a key change is a "
                    f"signed {KEYS} record appended to changes. Restore it: git show {commit}:{FOUNDER_KEYS}")
            entries = old.get(list_name)
            if isinstance(entries, list) and not _is_subsequence(_canonical_items(entries), now):
                raise IntegrityRecordError(
                    f"{rel}: a {list_name} record committed in {commit[:12]} was removed or reordered. "
                    "The record is append-only and no signature authorizes a rewrite; restore it "
                    f"(git show {commit}:{rel}) and append instead.")
    return RecordHistory(True, seen, f"append-only: {seen} committed version(s) of the record files "
                                     "checked; none removed, reordered or re-founded")


def record_history(root: str) -> RecordHistory:
    """``check_record_history`` for the records on disk under ``root``."""
    root = str(root)
    current = {rel: _load(root, rel) for rel in APPEND_ONLY}
    founder_keys_from(current[FOUNDER_KEYS])
    authorizations_from(current[AUTHORIZATIONS])
    return check_record_history(current, committed_versions(root))


# -- the live reading -----------------------------------------------------------

@dataclass(frozen=True)
class ArtifactStatus:
    artifact: str
    verdict: Verdict
    authorized_sha256: str | None
    observed_sha256: str | None
    authorizations: int = 0
    note: str = ""

    @property
    def ok(self) -> bool:
        return self.verdict is Verdict.INTACT

    def to_dict(self) -> dict:
        return {"artifact": self.artifact, "verdict": self.verdict.value,
                "authorized_sha256": self.authorized_sha256, "observed_sha256": self.observed_sha256,
                "authorizations": self.authorizations, "note": self.note}


@dataclass(frozen=True)
class IntegrityReport:
    statuses: tuple[ArtifactStatus, ...]
    founder_keys: FounderKeys
    authorizations: int
    manifest: Manifest
    history: RecordHistory = RecordHistory(False, 0, "record history not read")

    @property
    def intact(self) -> bool:
        return all(s.ok for s in self.statuses)

    @property
    def findings(self) -> tuple[ArtifactStatus, ...]:
        return tuple(s for s in self.statuses if not s.ok)

    def to_dict(self) -> dict:
        return {"intact": self.intact, "statuses": [s.to_dict() for s in self.statuses],
                "findings": [s.to_dict() for s in self.findings],
                "founder_keys": {"enrolled": sorted(self.founder_keys.keys),
                                 "genesis_by_commit": list(self.founder_keys.genesis),
                                 "signed_changes": self.founder_keys.changes},
                "authorizations": self.authorizations,
                "record_history": {"checked": self.history.checked, "versions": self.history.versions,
                                   "note": self.history.note},
                "baseline_source": self.manifest.source}


def _ungoverned(root: str, governed: set[str]) -> list[str]:
    found = []
    for tree, suffixes in sorted(WATCHED_TREES.items()):
        directory = os.path.join(root, tree)
        if not os.path.isdir(directory):
            continue
        for name in sorted(os.listdir(directory)):
            rel = f"{tree}/{name}"
            if name.endswith(suffixes) and os.path.isfile(os.path.join(directory, name)) and rel not in governed:
                found.append(rel)
    return found


def verify(root: str = KERNEL_ROOT) -> IntegrityReport:
    """Read the live protected artifacts and compare each with its authorized digest.

    Raises ``IntegrityRecordError`` when the manifest, the key log or the
    authorizations are unsound: no verdict is given on a record that does not
    follow from itself.
    """
    root = str(root)
    manifest = load_manifest(root)
    keys = load_founder_keys(root)
    state = authorized_state(manifest, keys, load_authorizations(root))
    history = record_history(root)
    statuses = []
    for artifact, expected in sorted(state.digests.items()):
        observed = _sha256_of(root, artifact)
        verdict = (Verdict.MISSING if observed is None else
                   Verdict.INTACT if observed == expected else Verdict.UNAUTHORIZED_CHANGE)
        statuses.append(ArtifactStatus(artifact, verdict, expected, observed,
                                       state.counts.get(artifact, 0)))
    observed_keys = _sha256_of(root, FOUNDER_KEYS)
    if keys.enrolled:
        note = (f"{len(keys.keys)} founder key(s): {', '.join(sorted(keys.keys))}; genesis enrolled by "
                f"commit (trust on first use), {keys.changes} signed change(s)")
    else:
        note = "no founder key enrolled; nothing can be authorized" + (
            " (as first committed)" if observed_keys == manifest.founder_keys_genesis_sha256 else "")
    statuses.append(ArtifactStatus(FOUNDER_KEYS, Verdict.INTACT, None, observed_keys, keys.changes, note))
    for rel in _ungoverned(root, set(state.digests)):
        statuses.append(ArtifactStatus(rel, Verdict.UNGOVERNED_ADDITION, None, _sha256_of(root, rel)))
    return IntegrityReport(statuses=tuple(statuses), founder_keys=keys,
                           authorizations=len(state.applied), manifest=manifest, history=history)


def authorization_body(root: str, artifact: str, new_sha256: str, reason: str) -> dict:
    """The body an ``authorize`` signs: from the currently authorized digest to ``new_sha256``."""
    artifact = _relative_path(artifact)
    if artifact in RECORD_FILES:
        raise IntegrityRecordError(f"{artifact} is not moved by authorization")
    manifest = load_manifest(root)
    keys = load_founder_keys(root)
    state = authorized_state(manifest, keys, load_authorizations(root))
    record_history(root)
    previous = state.digests.get(artifact)
    if previous is None and not any(artifact.startswith(f"{t}/") and artifact.endswith(s)
                                    for t, s in WATCHED_TREES.items()):
        raise IntegrityRecordError(f"{artifact} is neither protected nor in a watched tree")
    new = _digest(new_sha256, "--sha256")
    if new == previous:
        raise IntegrityRecordError(f"{artifact} is already authorized at {new}")
    return {"artifact": artifact, "previous_sha256": previous, "new_sha256": new,
            "reason": _text(reason, "reason", 1000)}
