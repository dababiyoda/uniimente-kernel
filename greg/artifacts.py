"""Body-local content-addressed artifacts, exposed only through GREG capabilities.

The object directory holds bytes, not authority or claims about the world. The
canonical Gate receipt binds a successful import to a namespace; subsequent
reads require that receipt and a matching signed target. Hash verification is
integrity, not attribution, epistemology, causality, outcome or legitimacy.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import re
import stat
import tempfile

from greg.capabilities import CapabilityError, InvocationContext, MAX_READ_BYTES, _inside

_DIGEST = re.compile(r"sha256:[0-9a-f]{64}\Z")
_NAMESPACE = re.compile(r"[a-z0-9][a-z0-9._-]{0,63}\Z")
MAX_OBJECTS = 512
MAX_STORE_BYTES = 64 * 1024 * 1024


def _namespace(params: dict, ctx: InvocationContext) -> str:
    name = params.get("namespace")
    if not isinstance(name, str) or not _NAMESPACE.fullmatch(name):
        raise CapabilityError("artifact namespace must be a bounded lowercase identifier")
    if ctx.target != f"artifact:{name}":
        raise CapabilityError("artifact namespace does not match the signed target")
    return name


def _root(ctx: InvocationContext) -> Path:
    if ctx.artifact_root is None:
        raise CapabilityError("this body has no artifact store")
    return Path(ctx.artifact_root)


def _digest(value: str) -> str:
    if not isinstance(value, str) or not _DIGEST.fullmatch(value):
        raise CapabilityError("invalid sha256 artifact address")
    return value[7:]


class ArtifactStore:
    """Small immutable byte store. The older Genesis filename layout is supported."""

    def __init__(self, root: Path, *, legacy_source_suffix: str = ""):
        self.root = Path(root)
        if legacy_source_suffix not in ("", ".py"):
            raise ValueError("unsupported legacy source suffix")
        self.legacy_source_suffix = legacy_source_suffix

    def path(self, address: str) -> Path:
        digest = _digest(address)
        if self.legacy_source_suffix:
            return self.root / f"{digest}{self.legacy_source_suffix}"
        return self.root / "sha256" / digest[:2] / digest

    @staticmethod
    def _read_file(path: Path) -> bytes:
        try:
            info = path.lstat()
            if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_READ_BYTES:
                raise CapabilityError("artifact is not a bounded regular file")
            flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
            with os.fdopen(os.open(path, flags), "rb") as stream:
                data = stream.read(MAX_READ_BYTES + 1)
        except (FileNotFoundError, OSError) as exc:
            raise CapabilityError("artifact is missing or unreadable") from exc
        if len(data) > MAX_READ_BYTES:
            raise CapabilityError("artifact exceeds the size ceiling")
        return data

    def read(self, address: str) -> bytes:
        data = self._read_file(self.path(address))
        if hashlib.sha256(data).hexdigest() != _digest(address):
            raise CapabilityError("artifact bytes disagree with their address")
        return data

    def put(self, data: bytes) -> tuple[str, bool]:
        if not isinstance(data, bytes) or len(data) > MAX_READ_BYTES:
            raise CapabilityError("artifact must be bytes under the size ceiling")
        address = "sha256:" + hashlib.sha256(data).hexdigest()
        path = self.path(address)
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        if path.exists() or path.is_symlink():
            self.read(address)  # a collision or corruption must never be overwritten
            return address, False
        if not self.legacy_source_suffix:
            # A generated model cannot fill the body's disk with unlimited
            # small objects merely because every individual file is bounded.
            objects = list((self.root / "sha256").glob("*/*"))
            if len(objects) >= MAX_OBJECTS or sum(p.lstat().st_size for p in objects) + len(data) > MAX_STORE_BYTES:
                raise CapabilityError("body-local artifact quota exhausted; founder review required")
        fd, temporary = tempfile.mkstemp(prefix=".pending-", dir=path.parent)
        try:
            with os.fdopen(fd, "wb") as stream:
                os.fchmod(stream.fileno(), 0o600)
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            try:
                os.link(temporary, path)  # atomic no-clobber installation, including concurrent writers
                created = True
            except FileExistsError:
                created = False
            self.read(address)
            directory = os.open(path.parent, os.O_RDONLY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
            return address, created
        finally:
            os.unlink(temporary)


def _provenance(ctx: InvocationContext, namespace: str, address: str) -> str | None:
    if ctx.journal is None:
        raise CapabilityError("canonical artifact receipts are unavailable")
    ledger = ctx.journal.ledger
    ok, why = ledger.verify_chain()
    if not ok:
        raise CapabilityError(f"institutional history failed integrity check: {why}")
    witnesses = {r.payload["witness_id"]: r.payload["grant_id"] for r in ledger.by_type("witness")
                 if r.payload.get("action_class") == "greg.artifact.store"
                 and r.payload.get("target") == f"artifact:{namespace}"
                 and r.payload.get("capability") == "artifact.store"}
    dispatches = {(r.payload.get("witness_id"), r.payload.get("grant_id"))
                  for r in ledger.by_type("grant_dispatch")}
    for receipt in reversed(ledger.by_type("receipt")):
        result = receipt.payload.get("result", {})
        if not isinstance(result, dict):
            continue
        output = result.get("output") or {}
        if not isinstance(output, dict):
            continue
        wid = receipt.payload.get("witness_id")
        gid = receipt.payload.get("grant_id")
        if (wid in witnesses and gid and witnesses[wid] == gid and (wid, gid) in dispatches
                and result.get("result_class") == "positive"
                and output.get("namespace") == namespace
                and output.get("address") == address):
            return receipt.hash
    return None


def store(params: dict, ctx: InvocationContext) -> dict:
    if ctx.manifest.capability_id != "artifact.store":
        raise CapabilityError("artifact.store requires its registered manifest")
    if set(params) != {"namespace", "path"}:
        raise CapabilityError("artifact.store requires exactly namespace and path")
    name = _namespace(params, ctx)
    if not isinstance(params["path"], str):
        raise CapabilityError("artifact source path must be a string")
    source = _inside(Path(params["path"]), ctx.read_roots + (ctx.workspace,))
    data = ArtifactStore._read_file(source)
    address, created = ArtifactStore(_root(ctx)).put(data)
    return {"namespace": name, "address": address, "bytes": len(data), "created": created,
            "evidence_scope": "body-local bytes; Gate receipt, not independent factual proof"}


def inspect(params: dict, ctx: InvocationContext) -> dict:
    if ctx.manifest.capability_id != "artifact.inspect":
        raise CapabilityError("artifact.inspect requires its registered manifest")
    if set(params) != {"namespace", "address"}:
        raise CapabilityError("artifact.inspect requires exactly namespace and address")
    name = _namespace(params, ctx)
    address = params["address"]
    _digest(address)
    receipt = _provenance(ctx, name, address)
    if receipt is None:
        return {"namespace": name, "address": address, "present": False,
                "reason": "no successful Gate receipt in this namespace"}
    data = ArtifactStore(_root(ctx)).read(address)
    return {"namespace": name, "address": address, "present": True, "bytes": len(data),
            "import_receipt": receipt, "integrity": "sha256 re-read",
            "evidence_scope": "body-local bytes and Gate receipt; not independent factual proof"}


def materialize(params: dict, ctx: InvocationContext) -> dict:
    if ctx.manifest.capability_id != "artifact.materialize":
        raise CapabilityError("artifact.materialize requires its registered manifest")
    if set(params) != {"namespace", "address", "relative_path"}:
        raise CapabilityError("artifact.materialize requires namespace, address and relative_path")
    name = params["namespace"]
    address = params["address"]
    _digest(address)
    if not isinstance(name, str) or not _NAMESPACE.fullmatch(name):
        raise CapabilityError("invalid artifact namespace")
    relative = params["relative_path"]
    if (not isinstance(relative, str) or not relative or Path(relative).is_absolute()
            or any(part in (".", "..", "") for part in relative.split("/"))):
        raise CapabilityError("invalid relative materialization path")
    if ctx.target != f"workspace:{relative}":
        raise CapabilityError("materialization path does not match the signed target")
    receipt = _provenance(ctx, name, address)
    if receipt is None:
        raise CapabilityError("no successful Gate receipt permits this namespace and address")
    data = ArtifactStore(_root(ctx)).read(address)
    ctx.workspace.mkdir(parents=True, exist_ok=True)
    destination = _inside(ctx.workspace / relative, (ctx.workspace,))
    destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if destination.exists() or destination.is_symlink():
        if ArtifactStore._read_file(destination) != data:
            raise CapabilityError("materialization would replace different bytes")
        created = False
    else:
        fd, temporary = tempfile.mkstemp(prefix=".pending-", dir=destination.parent)
        try:
            with os.fdopen(fd, "wb") as stream:
                os.fchmod(stream.fileno(), 0o600)
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            try:
                os.link(temporary, destination)
                created = True
            except FileExistsError:
                if ArtifactStore._read_file(destination) != data:
                    raise CapabilityError("materialization collided with different bytes")
                created = False
            directory = os.open(destination.parent, os.O_RDONLY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
        finally:
            os.unlink(temporary)
    return {"path": str(destination), "address": address, "bytes": len(data),
            "created": created, "import_receipt": receipt}
