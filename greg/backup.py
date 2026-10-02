"""Encrypted offline continuity for the existing body, not another authority plane.

An export is a bounded encrypted copy of one stopped body's durable files.
Restore requires an independently retained founder public key and signed
checkpoint matching the complete snapshot. A restored body remains blocked
until a fresh, restoration-specific checkpoint from the authoritative source
matches its files. Old archives/approvals cannot silently resurrect authority.

The operator must identify the authoritative current source. Cryptography
cannot detect a newer, inaccessible revocation that the operator withholds.
This protocol does not provide consensus between independently running bodies.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import base64
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import secrets
import stat

from cryptography.exceptions import InvalidSignature, InvalidTag
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

from compiler.ucl_compiler import compile_constitution
from events.spine import EventSpine
from greg.founder import key_id, public_bytes
from greg.journal import Journal, iso
from provenance.ledger import EvidenceLedger, WriterConflict

SCHEMA = "greg-encrypted-backup/1"
CHECKPOINT_SCHEMA = "greg-continuity-checkpoint/1"
DOMAIN = b"uniimente-greg-continuity-checkpoint-v1\n"
AAD = b"uniimente-greg-encrypted-backup-v1;AES-256-GCM;scrypt-N32768-r8-p1"
MAX_FILES = 512
MAX_PLAINTEXT_BYTES = 16 * 1024 * 1024
MAX_FILE_BYTES = 4 * 1024 * 1024
MAX_ARCHIVE_BYTES = 32 * 1024 * 1024
FRESHNESS = timedelta(minutes=15)
GUARD = "RESTORE_PENDING"
TRANSIENT = {"ledger.jsonl.lock", "heartbeat.json", GUARD}


class BackupError(ValueError):
    pass


def _canonical(value) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def _sha(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _now():
    return datetime.now(timezone.utc)


def _read(path: Path, limit: int) -> bytes:
    try:
        info = path.lstat()
        if not stat.S_ISREG(info.st_mode) or info.st_size > limit:
            raise BackupError("continuity input is not a bounded regular file")
        with os.fdopen(os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)), "rb") as fh:
            data = fh.read(limit + 1)
        if len(data) > limit:
            raise BackupError("continuity input exceeds its byte ceiling")
        return data
    except OSError as exc:
        raise BackupError("continuity file is missing, changed or unreadable") from exc


def _write_new(path: Path, data: bytes):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600)
    with os.fdopen(fd, "wb") as fh:
        fh.write(data); fh.flush(); os.fsync(fh.fileno())


def _outside(path: Path, home: Path):
    path = path.expanduser().absolute()
    if path.resolve().is_relative_to(home):
        raise BackupError("backup and authority checkpoint must be retained outside the body")
    return path


def _path(name: str):
    if (not isinstance(name, str) or not name or len(name) > 512 or "\\" in name
            or name.startswith("/") or any(p in ("", ".", "..") for p in name.split("/"))):
        raise BackupError("invalid backup member path")
    return PurePosixPath(name)


def _snapshot(home: Path) -> tuple[dict[str, bytes], str]:
    files = {}
    total = 0
    for path in sorted(home.rglob("*")):
        relative = path.relative_to(home).as_posix()
        if relative in TRANSIENT:
            continue
        if path.is_symlink():
            raise BackupError("body symlinks require explicit operator migration; no implicit dereference")
        if path.is_dir():
            continue
        _path(relative)
        data = _read(path, MAX_FILE_BYTES)
        total += len(data)
        if len(files) >= MAX_FILES or total > MAX_PLAINTEXT_BYTES:
            raise BackupError("body exceeds the bounded backup scope; nothing silently omitted")
        files[relative] = data
    if not {"body.json", "ledger.jsonl", "device_ed25519.pem", "witness.key"} <= set(files):
        raise BackupError("body continuity files are incomplete")
    digest = _sha(_canonical({name: _sha(data) for name, data in files.items()}))
    return files, digest


@contextmanager
def _state(home: Path, *, allow_pending=False):
    home = Path(home).expanduser().resolve()
    if (home / GUARD).exists() and not allow_pending:
        raise BackupError("restored authority is pending; cannot export or certify it as current")
    config = json.loads(_read(home / "body.json", MAX_FILE_BYTES))
    expected = compile_constitution(str(Path(__file__).resolve().parents[1])).constitution_hash
    if config.get("constitution_hash") != expected:
        raise BackupError("constitution differs; a separate authenticated migration is required")
    if not (home / "ledger.jsonl").is_file():
        raise BackupError("canonical ledger is absent")
    # Reuse the native single-writer lock. No Body/Genesis open, service start,
    # model call, inbox command or constitutional effect occurs here.
    try:
        ledger = EvidenceLedger(expected, str(home / "ledger.jsonl"), tail="refuse")
    except WriterConflict as exc:
        raise BackupError("body is running; stop its writer before offline continuity work") from exc
    try:
        ok, why = ledger.verify_chain()
        if not ok:
            raise BackupError("canonical ledger integrity failed: " + why)
        journal = Journal(EventSpine(ledger), actor="spiffe://uniimente.internal/greg/continuity")
        keys = {}
        for event in journal.replay("founder."):
            d = event.payload
            if event.type == "greg.founder.enrolled":
                keys[d["key_id"]] = d["public_key"]
            elif event.type == "greg.founder.key_rotated":
                keys.pop(d["old_key_id"], None); keys[d["new_key_id"]] = d["new_public_key"]
        yield home, config, ledger, journal, keys
    finally:
        ledger.close()


def _signed_checkpoint(home, config, ledger, files, digest, key, *, challenge=None, now=None):
    now = now or _now()
    data = {"schema": CHECKPOINT_SCHEMA, "body_id": config["body_id"],
            "constitution_hash": config["constitution_hash"], "ledger_head": ledger.head,
            "ledger_records": len(ledger.records), "ledger_bytes_digest": _sha(files["ledger.jsonl"]),
            "snapshot_digest": digest, "issued_at": iso(now), "expires_at": iso(now + FRESHNESS),
            "restore_challenge": challenge, "stopped": "STOP" in files, "local_pause": "PAUSE" in files,
            "signer_public_key": public_bytes(key.public_key()).hex()}
    return {**data, "signature": key.sign(DOMAIN + _canonical(data)).hex()}


def checkpoint(home, key: Ed25519PrivateKey, *, challenge: str | None = None, now=None) -> dict:
    """Founder-authenticated checkpoint of the designated current source.

    A challenge is obtained from the restored body's RESTORE_PENDING file.
    This function cannot certify another pending restoration as a source.
    """
    if challenge is not None and (not isinstance(challenge, str) or len(challenge) != 64
                                  or any(c not in "0123456789abcdef" for c in challenge)):
        raise BackupError("restore challenge must be the exact 32-byte restoration nonce")
    with _state(Path(home)) as (home, config, ledger, journal, keys):
        public = public_bytes(key.public_key()).hex()
        if keys.get(key_id(public)) != public:
            raise BackupError("checkpoint needs the currently enrolled founder key; a phone delegation is insufficient")
        if challenge is not None and not (home / "STOP").exists():
            raise BackupError("authoritative source must retain STOP during restoration authority transfer")
        files, digest = _snapshot(home)
        return _signed_checkpoint(home, config, ledger, files, digest, key, challenge=challenge, now=now)


def _verify_checkpoint(reference, trusted_public_key, *, challenge=None, now=None):
    fields = {"schema", "body_id", "constitution_hash", "ledger_head", "ledger_records", "ledger_bytes_digest",
              "snapshot_digest", "issued_at", "expires_at", "restore_challenge", "stopped", "local_pause",
              "signer_public_key", "signature"}
    if not isinstance(reference, dict) or set(reference) != fields or reference["schema"] != CHECKPOINT_SCHEMA:
        raise BackupError("invalid continuity checkpoint schema")
    if reference["signer_public_key"] != trusted_public_key:
        raise BackupError("checkpoint signer differs from the independently retained founder public key")
    try:
        signature = bytes.fromhex(reference["signature"])
        public = Ed25519PublicKey.from_public_bytes(bytes.fromhex(trusted_public_key))
        public.verify(signature, DOMAIN + _canonical({k: v for k, v in reference.items() if k != "signature"}))
        issued = datetime.fromisoformat(reference["issued_at"].replace("Z", "+00:00"))
        expires = datetime.fromisoformat(reference["expires_at"].replace("Z", "+00:00"))
        if issued.tzinfo is None or expires.tzinfo is None or not timedelta(0) < expires - issued <= FRESHNESS:
            raise ValueError("invalid checkpoint time window")
    except (ValueError, InvalidSignature, TypeError) as exc:
        raise BackupError("checkpoint signature or time window is invalid") from exc
    if challenge is not None:
        now = now or _now()
        if reference["restore_challenge"] != challenge or not issued <= now < expires:
            raise BackupError("fresh restoration-specific authority checkpoint required; replay/expiry refused")
    return reference


def _derive(passphrase: bytes, salt: bytes):
    if not isinstance(passphrase, bytes) or not 12 <= len(passphrase) <= 1024:
        raise BackupError("backup passphrase must contain 12..1024 bytes")
    return Scrypt(salt=salt, length=32, n=32768, r=8, p=1).derive(passphrase)


def export_backup(home, archive_path, reference_path, key: Ed25519PrivateKey, passphrase: bytes, *, now=None):
    home = Path(home).expanduser().resolve()
    archive_path, reference_path = _outside(Path(archive_path), home), _outside(Path(reference_path), home)
    if archive_path == reference_path or archive_path.exists() or reference_path.exists():
        raise BackupError("export requires two distinct new off-body files")
    with _state(home) as (home, config, ledger, journal, keys):
        if not (home / "STOP").exists():
            raise BackupError("offline export requires a persisted local or founder STOP; no automatic replica activation")
        public = public_bytes(key.public_key()).hex()
        if keys.get(key_id(public)) != public:
            raise BackupError("encrypted export requires the currently enrolled founder key")
        files, digest = _snapshot(home)
        reference = _signed_checkpoint(home, config, ledger, files, digest, key, now=now)
        plain = _canonical({"schema": SCHEMA, "checkpoint": reference,
                            "files": {name: base64.b64encode(data).decode() for name, data in files.items()}})
        salt, nonce = secrets.token_bytes(16), secrets.token_bytes(12)
        encrypted = AESGCM(_derive(passphrase, salt)).encrypt(nonce, plain, AAD)
        archive = _canonical({"schema": SCHEMA, "salt": base64.b64encode(salt).decode(),
                              "nonce": base64.b64encode(nonce).decode(),
                              "ciphertext": base64.b64encode(encrypted).decode()})
        if len(archive) > MAX_ARCHIVE_BYTES:
            raise BackupError("encrypted archive ceiling exceeded; nothing written")
        _write_new(archive_path, archive)
        try:
            _write_new(reference_path, _canonical(reference))
        except Exception:
            archive_path.unlink()
            raise
    return {"archive": str(archive_path), "checkpoint": str(reference_path), "body_id": config["body_id"],
            "files": len(files), "encrypted_bytes": len(archive), "snapshot_digest": digest,
            "archive_digest": _sha(archive), "authority_created": False, "service_started": False,
            "excluded_scope": ["external read roots and deliveries", "transient heartbeat and writer lock"]}


def _decrypt(archive_path, passphrase):
    try:
        archive = json.loads(_read(Path(archive_path), MAX_ARCHIVE_BYTES))
        if set(archive) != {"schema", "salt", "nonce", "ciphertext"} or archive["schema"] != SCHEMA:
            raise BackupError("invalid encrypted archive schema")
        salt, nonce = (base64.b64decode(archive[k], validate=True) for k in ("salt", "nonce"))
        if len(salt) != 16 or len(nonce) != 12:
            raise BackupError("invalid fixed encryption parameters")
        encrypted = base64.b64decode(archive["ciphertext"], validate=True)
        plain = AESGCM(_derive(passphrase, salt)).decrypt(nonce, encrypted, AAD)
        snapshot = json.loads(plain)
        if set(snapshot) != {"schema", "checkpoint", "files"} or snapshot["schema"] != SCHEMA:
            raise BackupError("invalid decrypted snapshot schema")
        return snapshot
    except (ValueError, TypeError, KeyError, InvalidTag) as exc:
        raise BackupError("backup authentication/decryption failed") from exc


def restore_backup(archive_path, destination, passphrase: bytes, reference: dict,
                   trusted_public_key: str, *, now=None) -> dict:
    """Create a new inactive body. A matching retained checkpoint is integrity evidence only."""
    destination = Path(destination).expanduser().absolute()
    if destination.exists() or destination.is_symlink():
        raise BackupError("restore destination must not exist; existing bodies are never overwritten")
    _verify_checkpoint(reference, trusted_public_key)
    snapshot = _decrypt(archive_path, passphrase)
    archived = snapshot["checkpoint"]
    _verify_checkpoint(archived, trusted_public_key)
    # Require the exact complete snapshot: an older prefix, even with a valid
    # historical signature, cannot replace the supplied latest authority.
    if archived != reference:
        raise BackupError("backup differs from the supplied current checkpoint; stale authority restoration refused")
    encoded = snapshot["files"]
    if not isinstance(encoded, dict) or len(encoded) > MAX_FILES:
        raise BackupError("invalid snapshot member count")
    files, total = {}, 0
    for name, value in encoded.items():
        _path(name)
        if name in TRANSIENT or name == GUARD:
            raise BackupError("transient or restoration control member is prohibited")
        try:
            data = base64.b64decode(value, validate=True)
        except (ValueError, TypeError) as exc:
            raise BackupError("invalid backup member encoding") from exc
        total += len(data)
        if len(data) > MAX_FILE_BYTES or total > MAX_PLAINTEXT_BYTES:
            raise BackupError("backup member byte ceiling exceeded")
        files[name] = data
    if not {"body.json", "ledger.jsonl", "device_ed25519.pem", "witness.key"} <= set(files):
        raise BackupError("required body continuity members are absent")
    digest = _sha(_canonical({name: _sha(data) for name, data in files.items()}))
    config = json.loads(files["body.json"])
    if (digest != reference["snapshot_digest"] or _sha(files["ledger.jsonl"]) != reference["ledger_bytes_digest"]
            or config["body_id"] != reference["body_id"] or config["constitution_hash"] != reference["constitution_hash"]):
        raise BackupError("snapshot integrity/identity does not match its authenticated checkpoint")
    challenge = secrets.token_hex(32)
    guard = {"schema": "greg-restore-pending/1", "body_id": config["body_id"], "challenge": challenge,
             "checkpoint": reference, "trusted_founder_public_key": trusted_public_key,
             "status": "AUTHORITY_VERIFICATION_REQUIRED", "created_at": iso(now or _now())}
    destination.mkdir(mode=0o700)
    _write_new(destination / GUARD, _canonical(guard))  # guard exists before any runnable body state
    try:
        for name, data in files.items():
            path = destination.joinpath(*_path(name).parts)
            path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            _write_new(path, data)
        with _state(destination, allow_pending=True) as (_, _, ledger, _, keys):
            if ledger.head != reference["ledger_head"] or len(ledger.records) != reference["ledger_records"]:
                raise BackupError("restored canonical ledger differs from the checkpoint")
            if keys.get(key_id(trusted_public_key)) != trusted_public_key:
                raise BackupError("trusted founder is not currently enrolled in restored history")
    except Exception:
        # Retain guarded partial state for diagnosis; never launch it.
        raise
    return {"body_id": config["body_id"], "destination": str(destination), "files": len(files),
            "restore_challenge": challenge, "status": "AUTHORITY_VERIFICATION_REQUIRED",
            "service_started": False, "authority_created": False}


def verify_restored_authority(home, fresh_reference: dict, trusted_public_key: str, *, now=None) -> dict:
    """Release the restoration guard only after a fresh source-specific founder signature.

    No service is started, no STOP/PAUSE is removed, and no mission budget or
    grant is renewed. A missing source/current-authority reference blocks.
    """
    home = Path(home).expanduser().resolve()
    guard = json.loads(_read(home / GUARD, 16384))
    if guard.get("trusted_founder_public_key") != trusted_public_key:
        raise BackupError("independent founder trust root differs from the restoration ceremony")
    _verify_checkpoint(fresh_reference, trusted_public_key, challenge=guard["challenge"], now=now)
    original = guard["checkpoint"]
    immutable = ("body_id", "constitution_hash", "ledger_head", "ledger_records", "ledger_bytes_digest",
                 "snapshot_digest", "stopped", "local_pause", "signer_public_key")
    if any(fresh_reference[k] != original[k] for k in immutable):
        raise BackupError("current source differs from the restoration snapshot; obtain a current complete backup")
    with _state(home, allow_pending=True) as (home, config, ledger, journal, keys):
        if keys.get(key_id(trusted_public_key)) != trusted_public_key:
            raise BackupError("only the current founder root may verify a restoration")
        verification_digest = _sha(_canonical(fresh_reference))
        prior = [e for e in journal.replay("body.restore_authority_verified")
                 if e.payload.get("challenge") == guard["challenge"]]
        files, _ = _snapshot(home)
        if prior:
            if len(prior) != 1 or prior[0].payload["checkpoint_digest"] != verification_digest:
                raise BackupError("conflicting restoration verification history")
            # Resume only the exact interrupted verification. Do not let a
            # prior success mask later file corruption or an appended event.
            if (len(ledger.records) != original["ledger_records"] + 1
                    or ledger.head != journal.event_hash(prior[0].event_id)):
                raise BackupError("restoration history changed after interrupted verification")
            lines = files["ledger.jsonl"].splitlines(keepends=True)
            files["ledger.jsonl"] = b"".join(lines[:original["ledger_records"]])
            if _sha(files["ledger.jsonl"]) != original["ledger_bytes_digest"]:
                raise BackupError("restored authority prefix changed during verification recovery")
        else:
            if ledger.head != original["ledger_head"]:
                raise BackupError("restored history changed before current authority verification")
        digest = _sha(_canonical({name: _sha(data) for name, data in files.items()}))
        if digest != original["snapshot_digest"]:
            raise BackupError("restored state changed before current authority verification")
        if not prior:
            journal.record("body.restore_authority_verified", {
                "body_id": config["body_id"], "challenge": guard["challenge"],
                "checkpoint_digest": verification_digest, "source_ledger_head": original["ledger_head"],
                "signer_public_key": trusted_public_key, "authority_created": False,
                "service_started": False, "checkpoint": fresh_reference}, key=guard["challenge"])
        (home / GUARD).unlink()
        directory = os.open(home, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    return {"status": "CURRENT_AUTHORITY_VERIFIED", "body_id": config["body_id"],
            "shutdown_preserved": True, "service_started": False, "authority_created": False,
            "next_step": "operator starts the body explicitly; existing STOP/PAUSE, expiry and grants still apply"}
