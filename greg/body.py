"""The GREG body: a persistent host process on hardware Alfonso owns.

HARDWARE -> macOS/Linux -> supervisor (launchd/systemd/supervisord) -> THIS HOST
         -> Kernel (ledger, spine, policy, Gate) -> capabilities -> authorized effects

The host owns process lifecycle, scheduling, waiting and recovery. It owns no
policy. Its durable identity is the retained ledger + enrolled founder key +
missions, so the host process, the disk or the whole machine can be replaced and
the institution resumes from history ("immortality" as continuity, not a claim).

Interfaces never need to stay open: the founder CLI (or a future Mac/phone
client) drops Ed25519-signed commands into ``inbox/``; the host verifies and
applies them on its next tick. Exit codes are the supervisor contract:

    0   deliberate stop (founder BODY_STOP or local STOP file): do not restart
    !=0 crash: the supervisor restarts the host, which reconciles and resumes

Shutdown authority is never conditioned: STOP, SIGTERM and SIGKILL always win.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import secrets
import shutil
import signal
import time

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from compiler.ucl_compiler import compile_constitution
from events.spine import EventSpine
from greg import compute, dataplane, metrics, sop, tribunal
from greg.authority import AuthorityOffice
from greg.capabilities import BUILTINS, CapabilityRegistry, SecretBroker
from greg.founder import FounderAuthError, FounderVerifier, key_id, validate_device_grant
from greg.genesis import Genesis
from greg.journal import Journal, iso, utcnow
from greg.missions import MissionEngine, MissionError
from identity.machine_passport import PassportRegistry
from provenance.commit_witness import WitnessSigner
from provenance.ledger import EvidenceLedger, sha256_json

KERNEL_ROOT = Path(__file__).resolve().parents[1]
BODY_VERSION = "greg-body/0.1.0"


class BodyError(RuntimeError):
    pass


def device_delegations(journal: Journal) -> dict[str, dict]:
    """Currently delegated device keys (enrolled by the founder key, not revoked).
    Expiry is enforced at verification time, so an expired delegation is listed but unusable."""
    devices = {}
    for event in journal.replay("device."):
        if event.type == "greg.device.enrolled":
            devices[event.payload["device_key_id"]] = event.payload
        elif event.type == "greg.device.revoked":
            devices.pop(event.payload["device_key_id"], None)
    return devices


class Layout:
    def __init__(self, home: str | Path):
        self.home = Path(home).expanduser().resolve()
        self.config = self.home / "body.json"
        self.device_key = self.home / "device_ed25519.pem"
        self.witness_key = self.home / "witness.key"
        self.ledger = self.home / "ledger.jsonl"
        self.inbox = self.home / "inbox"
        self.processed = self.inbox / "processed"
        self.rejected = self.inbox / "rejected"
        self.outbox = self.home / "outbox"
        self.workspace = self.home / "workspace"
        self.secrets = self.home / "secrets.json"
        self.heartbeat = self.home / "heartbeat.json"
        self.stop_file = self.home / "STOP"
        self.pause_file = self.home / "PAUSE"


def _private_write(path: Path, data: bytes):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as fh:
        fh.write(data)


def init_body(home: str | Path, *, read_roots: list[str]) -> dict:
    """Create a new body directory. Refuses to overwrite an existing body."""
    layout = Layout(home)
    if layout.config.exists():
        raise BodyError(f"a body already exists at {layout.home}")
    for d in (layout.home, layout.inbox, layout.processed, layout.rejected, layout.outbox, layout.workspace):
        d.mkdir(parents=True, exist_ok=True)
    os.chmod(layout.home, 0o700)
    device = Ed25519PrivateKey.generate()
    _private_write(layout.device_key, device.private_bytes(serialization.Encoding.PEM,
                                                           serialization.PrivateFormat.PKCS8,
                                                           serialization.NoEncryption()))
    _private_write(layout.witness_key, secrets.token_bytes(32))
    public = device.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw).hex()
    compiled = compile_constitution(str(KERNEL_ROOT))
    config = {"body_id": "body-" + key_id(public)[8:24], "device_public_key": public,
              "created_at": iso(utcnow()), "constitution_hash": compiled.constitution_hash,
              "read_roots": [str(Path(r).expanduser().resolve()) for r in read_roots],
              "version": BODY_VERSION}
    _private_write(layout.config, json.dumps(config, indent=2).encode())
    return config


class Body:
    def __init__(self, home: str | Path, *, clock=None, builder=None):
        self.layout = Layout(home)
        if not self.layout.config.exists():
            raise BodyError("no body here; run `greg init` first")
        self.config = json.loads(self.layout.config.read_text())
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.builder = builder
        self.stop_requested = False
        self.ledger = None

    # -- open / close ------------------------------------------------------------
    def open(self):
        self.compiled = compile_constitution(str(KERNEL_ROOT))
        if self.compiled.constitution_hash != self.config["constitution_hash"]:
            raise BodyError("Constitution changed since this body was created; an explicit founder-approved "
                            "migration is required (history is bound to the old constitution)")
        self.ledger = EvidenceLedger(self.compiled.constitution_hash, str(self.layout.ledger))  # one writer
        self.spine = EventSpine(self.ledger)
        self.passports = PassportRegistry()
        self.identity = self.passports.issue(kind="process", creator="greg-body", owner_organ="uniimente-kernel",
                                             legal_principal="alfonso_lopez", declared_capabilities=[],
                                             budget_ceiling_usd=0.0, consequence_class="read_only")
        self.journal = Journal(self.spine, actor=self.identity.passport_id)
        signer = WitnessSigner(key=self.layout.witness_key.read_bytes(), env="production")
        self.office = AuthorityOffice(compiled=self.compiled, passports=self.passports, signer=signer,
                                      ledger=self.ledger)
        self.registry = CapabilityRegistry()
        for manifest, adapter in BUILTINS.values():
            self.registry.register(manifest, adapter, state="ATTACHED")
        self._apply_capability_states()
        self.secrets = SecretBroker(self.layout.secrets)
        self.genesis = Genesis(journal=self.journal, registry=self.registry, workspace_root=self.layout.workspace,
                               builder=self.builder)
        self.genesis.restore()
        self.engine = MissionEngine(journal=self.journal, office=self.office, registry=self.registry,
                                    secrets=self.secrets, workspace_root=self.layout.workspace,
                                    read_roots=tuple(self.config["read_roots"]), genesis=self.genesis)
        return self

    def close(self):
        if self.ledger is not None:
            self.ledger.close()
            self.ledger = None

    def __enter__(self):
        return self.open()

    def __exit__(self, *exc):
        self.close()

    def _apply_capability_states(self):
        for event in self.spine.replay("greg.capability.state"):
            cid = event.payload["capability_id"]
            if cid in self.registry.manifests:
                self.registry.set_state(cid, event.payload["state"])

    # -- founder identity ----------------------------------------------------------
    def enrolled_keys(self) -> dict[str, str]:
        keys = {}
        for event in self.journal.replay("founder."):
            data = event.payload
            if event.type == "greg.founder.enrolled":
                keys[data["key_id"]] = data["public_key"]
            elif event.type == "greg.founder.key_rotated":
                keys.pop(data["old_key_id"], None)
                keys[data["new_key_id"]] = data["new_public_key"]
        return keys

    def enroll_founder(self, public_hex: str) -> dict:
        """Trust-on-first-use by whoever controls this body's filesystem."""
        if self.enrolled_keys():
            raise BodyError("a founder key is already enrolled; rotation needs a signed ROTATE_FOUNDER_KEY")
        kid = key_id(public_hex)
        record = {"key_id": kid, "public_key": public_hex, "ceremony": "trust-on-first-use (local filesystem)",
                  "at": iso(self.clock()), "body_id": self.config["body_id"]}
        self.journal.record("founder.enrolled", record, key=kid)
        return record

    def device_keys(self) -> dict[str, dict]:
        return device_delegations(self.journal)

    def _seen_nonce(self, nonce: str) -> bool:
        return any(e.payload["nonce"] == nonce for e in self.journal.replay("command.accepted"))

    def verifier(self) -> FounderVerifier:
        return FounderVerifier(body_id=self.config["body_id"], enrolled=self.enrolled_keys(),
                               seen_nonce=self._seen_nonce, devices=self.device_keys())

    # -- commands ------------------------------------------------------------------
    def apply(self, envelope: dict, *, channel: str = "direct") -> dict:
        """Verify one signed founder command and apply it (idempotent on replay of the same file)."""
        digest = sha256_json(envelope)
        prior = [e.payload for e in self.journal.replay("command.accepted") if e.payload["digest"] == digest]
        if prior:
            return {"status": "ALREADY_APPLIED", "digest": digest}
        verifier = self.verifier()
        env = verifier.verify(envelope, now=self.clock())
        principal = verifier.principal(env, now=self.clock())
        kind, body = env["kind"], env["body"]
        # Commands are applied before the next tick's rebuild; a request raised during the
        # previous tick must already be visible, or a fast approval is refused as "unknown".
        self.engine.book.rebuild()
        result = self._dispatch(kind, body, digest)
        self.journal.record("command.accepted", {"kind": kind, "digest": digest, "nonce": env["nonce"],
                                                  "founder_key_id": env["founder_key_id"], "signer": principal,
                                                  "issued_at": env["issued_at"], "body": body,
                                                  "envelope": env, "channel": channel,
                                                  "result": result}, key=digest)
        return {"status": "APPLIED", "digest": digest, "result": result}

    def _dispatch(self, kind: str, body: dict, digest: str):
        if kind == "MISSION":
            return {"mission_id": self.engine.register(body, digest)}
        if kind == "DECISION":
            self.engine.answer(body, digest)
            return {"request_id": body["request_id"]}
        if kind == "LIFECYCLE":
            self.engine.lifecycle(body, digest)
            return {"mission_id": body["mission_id"], "state": body["state"]}
        if kind == "CRITIQUE":
            return tribunal.critique(self.journal, self.engine, body, digest)
        if kind in ("CAPABILITY_ATTACH", "CAPABILITY_DETACH"):
            cid = body.get("capability_id")
            if cid not in self.registry.manifests:
                raise MissionError("unknown capability")
            if kind == "CAPABILITY_ATTACH" and self.registry.state[cid] not in ("VERIFIED", "DETACHED", "ATTACHED"):
                raise MissionError("only verified capabilities may be attached")
            state = "ATTACHED" if kind == "CAPABILITY_ATTACH" else "DETACHED"
            self.registry.set_state(cid, state)
            self.journal.record("capability.state", {"capability_id": cid, "state": state, "by": "founder command",
                                                     "command_digest": digest}, key=[cid, state, digest])
            return {"capability_id": cid, "state": state}
        if kind == "BODY_PAUSE":
            self.journal.record("body.paused", {"command_digest": digest}, key=digest)
            return {"paused": True}
        if kind == "BODY_RESUME":
            self.journal.record("body.resumed", {"command_digest": digest}, key=digest)
            return {"paused": False}
        if kind == "BODY_STOP":
            # A founder stop is terminal until a human on this machine clears it: it must survive
            # login, reboot and supervisor restarts (launchd RunAtLoad would otherwise resume all
            # missions). A plain SIGTERM (e.g. an OS shutdown) is not a founder stop and is not persisted.
            self.stop_requested = True
            record = {"command_digest": digest, "at": iso(self.clock()),
                      "clear_with": "greg run --clear-stop  (or: greg start --local)"}
            tmp = self.layout.stop_file.with_suffix(".tmp")
            tmp.write_text(json.dumps({"reason": "signed founder BODY_STOP", **record}))
            tmp.replace(self.layout.stop_file)
            self.journal.record("body.stop_persisted", record, key=[digest, "stop"])
            return {"stop": True, "persisted": True}
        if kind == "NODE_ENROLL":
            return compute.enroll_node(self.journal, body, digest)
        if kind == "SOP_RATIFY":
            return sop.ratify(self.journal, body, digest)
        if kind == "DEVICE_ENROLL":  # only the founder key can sign this kind (DEVICE_KINDS excludes it)
            grant = validate_device_grant(body, now=self.clock())
            if grant["device_key_id"] in self.enrolled_keys() or grant["device_key_id"] in self.device_keys():
                raise MissionError("key already enrolled; revoke before re-delegating")
            self.journal.record("device.enrolled", {**grant, "command_digest": digest, "at": iso(self.clock())},
                                key=[grant["device_key_id"], digest])
            return {"device_key_id": grant["device_key_id"], "kinds": grant["kinds"], "expires_at": grant["expires_at"]}
        if kind == "DEVICE_REVOKE":
            kid = body.get("device_key_id")
            if set(body) != {"device_key_id"} or kid not in self.device_keys():
                raise MissionError("revocation needs exactly one currently delegated device_key_id")
            self.journal.record("device.revoked", {"device_key_id": kid, "command_digest": digest,
                                                   "at": iso(self.clock())}, key=[kid, digest])
            return {"device_key_id": kid, "revoked": True}
        if kind == "ROTATE_FOUNDER_KEY":
            new_hex = body["new_public_key"]
            old = next(iter(self.enrolled_keys()))
            self.journal.record("founder.key_rotated", {"old_key_id": old, "new_key_id": key_id(new_hex),
                                                        "new_public_key": new_hex, "command_digest": digest},
                                key=digest)
            return {"new_key_id": key_id(new_hex)}
        raise MissionError(f"unsupported command kind {kind}")

    def paused(self) -> bool:
        if self.layout.pause_file.exists():
            return True
        state = [e.type for e in self.journal.replay("body.") if e.type in ("greg.body.paused", "greg.body.resumed")]
        return bool(state) and state[-1] == "greg.body.paused"

    def ingest_inbox(self) -> list[dict]:
        results = []
        for path in sorted(self.layout.inbox.glob("*.json")):
            try:
                envelope = json.loads(path.read_text())
                outcome = self.apply(envelope, channel="inbox")
                shutil.move(str(path), self.layout.processed / path.name)
            except (FounderAuthError, MissionError, ValueError, KeyError, TypeError,
                    tribunal.CritiqueError) as exc:
                raw = path.read_bytes()
                self.journal.record("command.rejected", {"file": path.name, "sha256": sha256_json(raw.hex()),
                                                          "reason": f"{type(exc).__name__}: {exc}"[:500],
                                                          "instruction_status": "data_only"},
                                    key=[path.name, sha256_json(raw.hex())])
                shutil.move(str(path), self.layout.rejected / path.name)
                outcome = {"status": "REJECTED", "file": path.name, "reason": str(exc)[:300]}
            results.append(outcome)
        return results

    # -- lifecycle -----------------------------------------------------------------
    def boot(self) -> dict:
        boots = self.journal.replay("body.booted")
        stops = {e.payload["boot_id"] for e in self.journal.replay("body.stopped")}
        unfinished = [b.payload["boot_id"] for b in boots if b.payload["boot_id"] not in stops]
        boot_id = "boot-" + secrets.token_hex(8)
        record = {"boot_id": boot_id, "pid": os.getpid(), "at": iso(self.clock()), "version": BODY_VERSION,
                  "body_id": self.config["body_id"], "boot_number": len(boots) + 1,
                  "platform": os.uname().sysname, "ledger_head_at_boot": self.ledger.head}
        self.journal.record("body.booted", record, key=boot_id)
        if unfinished:
            self.journal.record("body.recovered", {"boot_id": boot_id, "previous_unfinished_boots": unfinished,
                                                   "action": "missions reconstructed from retained history; "
                                                             "uncertain dispatches reconcile, never blind-retry"},
                                key=[boot_id, "recovered"])
        self.boot_id = boot_id
        return record

    def tick(self) -> dict:
        now = self.clock()
        commands = self.ingest_inbox()
        if self.stop_requested:
            return {"commands": commands, "stopped": True}
        if self.paused():
            self._heartbeat("PAUSED", [])
            return {"commands": commands, "paused": True}
        summary = self.engine.tick(now)
        self._close_out(now)
        sop.propose(self.journal)
        return {"commands": commands, "missions": summary}

    def _close_out(self, now):
        """Record where each closure happened and have it appraised by a separate process."""
        contexts = {e.payload["mission_id"] for e in self.journal.replay("mission.closure_context")}
        appraised = {e.payload["mission_id"] for e in self.journal.replay("mission.appraised")}
        for event in self.journal.replay("mission.achieved"):
            mid = event.payload["mission_id"]
            if mid not in contexts:
                self.journal.record("mission.closure_context", {
                    "mission_id": mid, "boot_id": getattr(self, "boot_id", None), "pid": os.getpid(),
                    "platform": os.uname().sysname, "hosted": getattr(self, "boot_id", None) is not None,
                    "at": iso(now)}, key=[mid, "context"])
            if mid not in appraised:
                verdict = self.appraise(mid)
                self.journal.record("mission.appraised", verdict, key=[mid, "appraised", verdict["head"]])

    def appraise(self, mission_id: str) -> dict:
        import subprocess
        import sys
        request = {"ledger": str(self.layout.ledger), "constitution": self.compiled.constitution_hash,
                   "head": self.ledger.head, "mission_id": mission_id, "read_roots": self.config["read_roots"],
                   "workspace": str(self.layout.workspace / mission_id.replace(":", "_"))}
        env = {"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8", "PYTHONDONTWRITEBYTECODE": "1",
               "PYTHONPATH": os.pathsep.join([str(KERNEL_ROOT)] + [p for p in sys.path if "-packages" in p])}
        child = subprocess.run([sys.executable, "-m", "greg.appraisal"], input=json.dumps(request),
                               capture_output=True, text=True, timeout=120, env=env, cwd=KERNEL_ROOT)
        if child.returncode:
            return {"mission_id": mission_id, "head": request["head"], "verdict": "APPRAISAL_FAILED",
                    "checks": {}, "findings": [child.stderr[-500:]], "appraiser": "separate process"}
        return json.loads(child.stdout)

    def next_wake(self, tick_seconds: float) -> float:
        now = self.clock()
        horizon = now + timedelta(seconds=tick_seconds)
        for m in self.engine.book.missions.values():
            if m.next_observe_at and m.status not in ("ACHIEVED", "ABANDONED", "SUPERSEDED") and not m.blocker:
                at = datetime.fromisoformat(m.next_observe_at.replace("Z", "+00:00"))
                horizon = min(horizon, max(at, now))
        return max(0.05, (horizon - now).total_seconds())

    def _heartbeat(self, state: str, summary: list):
        data = {"pid": os.getpid(), "boot_id": getattr(self, "boot_id", None), "at": iso(self.clock()),
                "state": state, "ledger_head": self.ledger.head, "missions": summary}
        tmp = self.layout.heartbeat.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=1, default=str))
        tmp.replace(self.layout.heartbeat)

    def run(self, *, tick_seconds: float = 30.0, max_ticks: int | None = None,
            telemetry_every: int = 20) -> int:
        """Main loop. Returns the process exit code for the supervisor."""
        def on_signal(signum, frame):
            self.stop_requested = True
        import threading
        if threading.current_thread() is threading.main_thread():  # embedded hosts keep their own handlers
            signal.signal(signal.SIGTERM, on_signal)
            signal.signal(signal.SIGINT, on_signal)
        reason = "unknown"
        self.open()
        try:
            self.boot()
            ticks = 0
            while True:
                if self.layout.stop_file.exists():
                    reason = "local STOP file"
                    break
                result = self.tick()
                if self.stop_requested:
                    reason = "founder BODY_STOP or signal"
                    break
                ticks += 1
                if ticks % telemetry_every == 1:
                    compute.record_telemetry(self.journal, self.layout.home)
                    compute.recommend(self.journal)
                self._heartbeat("PAUSED" if result.get("paused") else "RUNNING", result.get("missions", []))
                if max_ticks is not None and ticks >= max_ticks:
                    reason = "max_ticks reached"
                    break
                deadline = time.monotonic() + self.next_wake(tick_seconds)
                while time.monotonic() < deadline and not self.stop_requested:
                    if self.layout.stop_file.exists() or any(self.layout.inbox.glob("*.json")):
                        break
                    time.sleep(min(0.2, max(0.0, deadline - time.monotonic())))
            self.journal.record("body.stopped", {"boot_id": self.boot_id, "reason": reason,
                                                 "at": iso(self.clock()), "ledger_head": self.ledger.head},
                                key=[self.boot_id, "stopped"])
            self._heartbeat("STOPPED", [])
            return 0
        finally:
            self.close()


def status(home: str | Path) -> dict:
    """Read-only projection for the founder; safe while the body runs."""
    layout = Layout(home)
    config = json.loads(layout.config.read_text())
    ledger = EvidenceLedger(config["constitution_hash"], str(layout.ledger), read_only=True) \
        if layout.ledger.exists() else None
    heartbeat = json.loads(layout.heartbeat.read_text()) if layout.heartbeat.exists() else None
    if ledger is None:
        return {"body_id": config["body_id"], "state": "NEVER_STARTED", "heartbeat": heartbeat}
    try:
        spine = EventSpine(ledger)
        journal = Journal(spine, actor="spiffe://uniimente.internal/greg/status-reader")
        registered = {e.payload["mission_id"]: e.payload["spec"] for e in journal.replay("mission.registered")}
        achieved = {e.payload["mission_id"] for e in journal.replay("mission.achieved")}
        answered = {e.payload["request_id"] for e in journal.replay("decision.answered")}
        answered |= {e.payload["request_id"] for e in journal.replay("decision.withdrawn")}
        requests = [e.payload for e in journal.replay("decision.requested") if e.payload["request_id"] not in answered]
        founder = [e.payload["key_id"] for e in journal.replay("founder.enrolled")]
        boots = journal.replay("body.booted")
        registry = CapabilityRegistry()
        for manifest, adapter in BUILTINS.values():
            registry.register(manifest, adapter, state="ATTACHED")
        ok, chain = ledger.verify_chain()
        return {
            "body_id": config["body_id"], "version": config["version"],
            "background": heartbeat, "boots": len(boots),
            "security": {"founder_keys_enrolled": founder, "chain_verified": ok, "chain": chain,
                         "devices": [{k: d[k] for k in ("device_key_id", "label", "kinds", "expires_at")}
                                     for d in device_delegations(journal).values()],
                         "stop_file_present": layout.stop_file.exists(),
                         "pause_file_present": layout.pause_file.exists()},
            "goals": [{"mission_id": mid, "intended_effect": spec["intended_effect"],
                       "closure": spec["closure"]["kind"], "achieved": mid in achieved}
                      for mid, spec in registered.items()],
            "decisions_required": [{"request_id": r["request_id"], "kind": r["kind"], "why_now": r["why_now"],
                                    "recommendation": r["recommendation"]} for r in requests],
            "capabilities": registry.inventory(), "permissions": {"read_roots": config["read_roots"]},
            "compute": compute.sample(layout.home),
            "secret_handles": SecretBroker(layout.secrets).names(),
            "external_items_quarantined": sum(1 for e in journal.replay("external.ingested")
                                              if e.payload["quarantined"]),
            "single_bottleneck_metric": metrics.vepmc(journal),
        }
    finally:
        ledger.close()


def ingest_external(home: str | Path, *, source: str, content: str, channel: str) -> dict:
    """Local intake of untrusted content (e.g. community replies) while the body is stopped."""
    with Body(home) as body:
        return dataplane.ingest(body.journal, source=source, content=content, channel=channel)
