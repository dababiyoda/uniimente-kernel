"""Bounded delivery into the existing command inbox, without command authority.

Callers authenticate/sign first; Body independently verifies again. The POSIX
lock serializes local producers, not replicas or policy. Existing accepted nonce
history remains the authority for replay. Queue delivery is not command success.
"""
from __future__ import annotations

import fcntl
import hashlib
import json
import os
from datetime import datetime, timezone
import re
from pathlib import Path
import tempfile

MAX_PENDING = 100
MAX_COMMAND_BYTES = 64 * 1024


class CommandQueueError(ValueError):
    pass


def enqueue(inbox: Path, envelope: dict, *, max_pending: int = MAX_PENDING) -> Path:
    """Atomically deduplicate pending envelopes and enforce local backpressure."""
    if type(max_pending) is not int or not 1 <= max_pending <= MAX_PENDING:
        raise CommandQueueError("invalid bounded inbox capacity")
    if not isinstance(envelope, dict) or not isinstance(envelope.get("nonce"), str):
        raise CommandQueueError("signed command envelope with nonce required")
    kind = envelope.get("kind", "COMMAND")
    if not isinstance(kind, str) or not re.fullmatch(r"[A-Z_]{1,40}", kind):
        raise CommandQueueError("bounded command kind required")
    try:
        issued = datetime.fromisoformat(envelope["issued_at"].replace("Z", "+00:00"))
        if issued.tzinfo is None:
            raise ValueError("timezone required")
        ordering = issued.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    except (KeyError, AttributeError, TypeError, ValueError) as exc:
        raise CommandQueueError("command timestamp with timezone required") from exc
    raw = json.dumps(envelope, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    if len(raw) > MAX_COMMAND_BYTES:
        raise CommandQueueError("command too large")
    if inbox.is_symlink() or not inbox.is_dir():
        raise CommandQueueError("existing body inbox directory required")
    flags = os.O_RDWR | os.O_CREAT | os.O_CLOEXEC | os.O_NOFOLLOW
    lock_fd = os.open(inbox / ".delivery.lock", flags, 0o600)
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX)
        pending = sorted(inbox.glob("*.json"))
        for path in pending:
            if path.is_symlink():
                raise CommandQueueError("inbox contains an unsafe entry")
            try:
                existing = json.loads(path.read_bytes())
            except (ValueError, OSError):
                continue  # Invalid envelopes still occupy capacity until Body rejects them.
            if isinstance(existing, dict) and existing.get("nonce") == envelope["nonce"]:
                if json.dumps(existing, sort_keys=True, separators=(",", ":"), allow_nan=False).encode() != raw:
                    raise CommandQueueError("pending nonce reused with a different envelope")
                return path
        if len(pending) >= max_pending:
            raise CommandQueueError("inbox full; the body is not keeping up")
        # Preserve discoverable kind names with a restricted alphabet; all other
        # identity is the native digest. Publication follows fsync of content.
        target = inbox / (ordering + "-" + kind.lower() + "-" + hashlib.sha256(raw).hexdigest() + ".json")
        fd, name = tempfile.mkstemp(prefix=".delivery-", suffix=".tmp", dir=inbox)
        try:
            with os.fdopen(fd, "wb") as stream:
                stream.write(raw)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(name, target)
            directory = os.open(inbox, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
        finally:
            Path(name).unlink(missing_ok=True)
        return target
    finally:
        os.close(lock_fd)
