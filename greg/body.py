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

from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import secrets
import shutil
import signal
import stat
import time

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from compiler.ucl_compiler import compile_constitution
from events.spine import EventSpine
from greg import anchor, asks, compute, dataplane, doctor, gravity, improvement, metrics, models, presence, sop, tribunal
from greg.authority import AuthorityOffice
from greg.capabilities import BUILTINS, CapabilityRegistry, SecretBroker
from greg.founder import FounderAuthError, FounderVerifier, instant, key_id, spent_nonce, validate_device_grant
from greg.genesis import Genesis
from greg.journal import Journal, iso, utcnow
from greg.missions import MissionEngine, MissionError
from greg.workers import WORKER_CONFINEMENT, confinement_mode
from identity.machine_passport import PassportRegistry
from provenance.commit_witness import WitnessSigner
from provenance.ledger import EvidenceLedger, sha256_json

KERNEL_ROOT = Path(__file__).resolve().parents[1]
BODY_VERSION = "greg-body/0.1.0"


class BodyError(RuntimeError):
    pass


def founder_keys(journal: Journal) -> dict[str, str]:
    """Current founder keys from the one retained enrollment/rotation history (#138 b8a0ccd)."""
    keys = {}
    for event in journal.replay("founder."):
        data = event.payload
        if event.type == "greg.founder.enrolled":
            keys[data["key_id"]] = data["public_key"]
        elif event.type == "greg.founder.key_rotated":
            keys.pop(data["old_key_id"], None)
            keys[data["new_key_id"]] = data["new_public_key"]
    return keys


# Crash-loop breaker (acceptance H.G5). supervisord, systemd and launchd restart a crashing body forever. Once
# CRASH_LOOP_BOOTS main-loop boots in a row (no clean stop between them) ended without a clean stop within
# CRASH_LOOP_WINDOW_SECONDS, the next boot holds the body: it keeps running, stays observable and reads its inbox,
# ticks no mission, and raises one founder ask. Only a signed BODY_RESUME lifts the hold (RESUME_LIFTS: the founder
# key, or a device key delegated BODY_RESUME, greg/founder.py DEVICE_KINDS). The hold is the breaker's own record,
# never shown as the founder's.
CRASH_LOOP_BOOTS = 5          # above deliberate use: the founder runbook kill -9s a body three times in minutes
CRASH_LOOP_WINDOW_SECONDS = 600
BREAKER = "crash-loop breaker"
RESUME_LIFTS = "a signed BODY_RESUME: the founder key, or a device key the founder delegated BODY_RESUME to"
HOLD_ASK = "CRASH_LOOP_HOLD"  # no DECISION answers it (greg/missions.py NOT_ANSWERABLE); BODY_RESUME withdraws it
# A body restored from a backup (greg/recovery.py) holds itself; Body._after_restore lets only the founder key lift it.
RESTORE_LIFTS = "a BODY_RESUME signed by the founder key and issued after the restore (a device key cannot lift it)"

# The separate-process appraiser (greg/appraisal.py) judges a closure VERIFIED or REFUTED, and a failure closure
# (mission.unmet) VERIFIED_UNMET or REFUTED. A run killed, timed out or without a readable verdict judged nothing
# (acceptance H.G7): it is one unavailable attempt, retried on a later tick, and after APPRAISAL_ATTEMPTS of them the
# closure is recorded appraised UNAVAILABLE (final, never VERIFIED).
APPRAISER_VERDICTS = ("VERIFIED", "VERIFIED_UNMET", "REFUTED")
APPRAISAL_ATTEMPTS = 3
APPRAISAL_TIMEOUT_SECONDS = 120


def unfinished_main_loop_boots(journal: Journal, now: datetime) -> list[str]:
    """Main-loop boots in a row that never recorded a clean stop, within the window.

    The run restarts at a pause or resume, and at a main-loop boot that recorded a clean stop: "in a row" means
    no clean stop between them. Only boots made by ``Body.run`` count: an embedded or test host that opens the body
    and boots it without the main loop is not a process lifetime under a supervisor."""
    stopped = {e.payload["boot_id"] for e in journal.replay("body.stopped")}
    recent: list[dict] = []
    for event in journal.replay("body."):
        if event.type in ("greg.body.paused", "greg.body.resumed"):
            recent = []
        elif event.type == "greg.body.booted" and event.payload.get("main_loop"):
            if event.payload["boot_id"] in stopped:
                recent = []           # a clean lifetime ends the run
            else:
                recent.append(event.payload)
    floor = now - timedelta(seconds=CRASH_LOOP_WINDOW_SECONDS)
    return [b["boot_id"] for b in recent if datetime.fromisoformat(b["at"].replace("Z", "+00:00")) >= floor]


def crash_loop_hold(journal: Journal) -> dict | None:
    """The breaker's hold when it is the pause in force; None otherwise (a founder pause is not a hold)."""
    toggles = [e for e in journal.replay("body.") if e.type in ("greg.body.paused", "greg.body.resumed")]
    last = toggles[-1] if toggles else None
    if last is not None and last.type == "greg.body.paused" and last.payload.get("by") == BREAKER:
        return last.payload
    return None


def body_pauses(journal: Journal, *, pause_file: bool) -> list[dict]:
    """Every body-level pause in force, each with what lifts it: the active constraint of every active mission."""
    toggles = [e for e in journal.replay("body.") if e.type in ("greg.body.paused", "greg.body.resumed")]
    out = []
    if toggles and toggles[-1].type == "greg.body.paused":
        hold = toggles[-1].payload
        out.append({"by": BREAKER, "why": hold.get("why"), "lifted_by": RESUME_LIFTS} if hold.get("by") == BREAKER
                   else {"by": "restore hold", "why": hold.get("reason"), "lifted_by": RESTORE_LIFTS}
                   if "restore_id" in hold
                   else {"by": "body paused (signed BODY_PAUSE)", "lifted_by": RESUME_LIFTS})
    if pause_file:
        out.append({"by": "PAUSE file in the body home", "lifted_by": "removing that file on this machine"})
    return out


def hold_ask(hold: dict) -> dict:
    """The one founder ask a crash-loop hold raises, derived only from the hold record (greg/asks.py contract).

    Asking grants nothing: no DECISION answers it, and only a signed BODY_RESUME lifts the hold (which withdraws
    this ask). Deterministic, so a boot after a crash between the hold and its ask records the same ask."""
    boot_id = hold["boot_id"]
    return {"request_id": "req-hold-" + sha256_json({"crash_loop_hold": boot_id})[7:23], "kind": HOLD_ASK,
            "mission_id": None, "action_id": None, "scope_digest": sha256_json({"crash_loop_hold": boot_id}),
            "why_now": hold["why"],
            "recommendation": "read the repeated failure in the body's error log (logs/body.err.log in the body "
                              "home under launchd or supervisord; journalctl --user under systemd), fix its "
                              "cause, then sign BODY_RESUME",
            "alternatives": ["fix the cause, then sign BODY_RESUME (greg resume, or Resume in Mission Control)",
                             f"sign BODY_RESUME as is: if the cause remains, the breaker holds again after "
                             f"{CRASH_LOOP_BOOTS} more unfinished boots",
                             "sign BODY_STOP: the body exits and its supervisor does not restart it",
                             "do nothing: the body stays held"],
            "authority_requested": {"body": "resume (a signed BODY_RESUME)", "spend": "none"},
            "consequence_of_no_response": "the body stays held: it reads its inbox and runs no mission step; "
                                          "missions stay durable",
            "evidence": {"hold_boot_id": boot_id, "unfinished_boots": hold.get("unfinished_boots", []),
                         "window_seconds": hold.get("window_seconds")},
            "created_at": hold["at"], "reality_status": "RECORDED_LOCAL_MESSAGE"}


# What a paused or held body contains instead of exiting (Body._contained, Body._set_aside), and how each clears.
# Neither clearing lifts anything: only a signed BODY_RESUME lifts a pause or a hold.
FAULT_CLEARS = ("fix the cause named by error and site; while it lasts it is recorded again at each boot, and a "
                "body that is not paused exits on it (the breaker counts that boot)")
FAULTED_CLEARS = ("not accepted as a command: read the file, sign the command again if you meant one, then remove "
                  "the file this entry names, on this machine")
FAULTED_APPLIED_CLEARS = ("accepted and applied (the ledger has it); only moving the file to inbox/processed failed: "
                          "do not sign it again; remove the file this entry names, on this machine")
FAULTED_UNREADABLE_CLEARS = ("inbox/faulted cannot be listed: restore its permissions on this machine; until then "
                             "files set aside there are not shown")


FAULTED_SUFFIX = ".faulted"   # a file set aside in place when inbox/faulted cannot take it: outside the *.json read


def contained_faults(journal: Journal, layout: "Layout") -> list[dict]:
    """The faults a paused or held body contained and that still stand, each with how to clear it (greg status).

    A turn fault stands for the latest boot until a resume (each boot records it again while its cause lasts,
    and a running body exits on it instead). A file set aside stands while it is in inbox/faulted, recorded or
    not (the body moves it before it records it)."""
    turn: list[dict] = []
    for event in journal.replay("body."):
        if event.type in ("greg.body.booted", "greg.body.resumed"):
            turn = []
        elif event.type == "greg.body.fault_contained":
            turn.append({"fault": "turn", **{k: event.payload.get(k) for k in ("error", "site", "state", "boot_id",
                                                                               "at")},
                         "clear_with": FAULT_CLEARS})
    recorded = {e.payload["kept_as"]: e.payload for e in journal.replay("command.faulted")}
    files, unreadable = [], []
    try:
        files = [f"inbox/faulted/{p.name}" for p in sorted(layout.faulted.iterdir())] if layout.faulted.is_dir() else []
    except OSError as exc:   # the case a set-aside falls back from; status must still answer
        unreadable = [{"fault": "inbox/faulted unreadable", "error": f"{type(exc).__name__}: {exc}"[:300],
                       "clear_with": FAULTED_UNREADABLE_CLEARS}]
    files += [f"inbox/{p.name}" for p in sorted(layout.inbox.glob("*" + FAULTED_SUFFIX))]   # set aside in place
    return turn + unreadable + [{"fault": "inbox file set aside", "file": name,
                    **{k: (recorded.get(name) or {}).get(k) for k in ("sha256", "error", "state", "at")},
                    **({"applied": True} if (recorded.get(name) or {}).get("applied") else {}),
                    "clear_with": FAULTED_APPLIED_CLEARS if (recorded.get(name) or {}).get("applied")
                    else FAULTED_CLEARS} for name in files]


def device_delegations(journal: Journal) -> dict[str, dict]:
    """Currently delegated device keys (enrolled by the founder key, not revoked).
    Expiry is enforced at verification time, so an expired delegation is listed but unusable.

    A key delegated again after a revocation carries ``signed_not_before``: this body's clock when it recorded the
    re-delegation (``at``). A command whose ``issued_at`` is earlier never verifies again (FounderVerifier), so
    neither a token signed under the revoked delegation nor one signed while the key stood revoked reactivates.
    The anchor is that processing time, not the enrollment envelope's ``issued_at``: the founder may sign the
    re-delegation before the revocation, and an envelope anchor would then reactivate tokens signed between that
    envelope and the revocation; subtracting the founder clock-skew allowance (five minutes) would reactivate
    tokens signed in the five minutes before the re-delegation. The body records a re-delegation only after the
    revocation and after the founder signed it, so on one clock the processing time is the latest of these
    instants and refuses every token they refuse (a founder clock ahead of the body's, within the allowed skew,
    is the exception). Its cost: a command signed after the founder signed the
    re-delegation but before this body recorded it, or by a device whose clock runs behind this body's, is
    refused and must be signed again. A token whoever held the key forward-dated is not one this rule can tell
    from a new one: re-delegate only a key that was not compromised; a compromised device gets a new key.
    greg.appraisal._devices_before re-derives the same rule."""
    devices, revoked = {}, set()
    for event in journal.replay("device."):
        if event.type == "greg.device.enrolled":
            kid = event.payload["device_key_id"]
            devices[kid] = ({**event.payload, "signed_not_before": event.payload["at"]} if kid in revoked
                            else event.payload)
        elif event.type == "greg.device.revoked":
            revoked.add(event.payload["device_key_id"])
            devices.pop(event.payload["device_key_id"], None)
    return devices


# A founder-signed GOAL or GOAL_CONTROL the body verified and then rejected (it would widen authority, it
# duplicates a goal, ...) consumes its nonce: re-dropping the retained file later, after the state that
# refused it changed (a revoke, a supersede), must not apply it without a new signature.
NONCE_CONSUMED_ON_REJECT = ("GOAL", "GOAL_CONTROL")


def consumed_nonces(journal: Journal) -> set[str]:
    """Nonces a command may not reuse: every accepted command's, and every verified-then-rejected
    GOAL / GOAL_CONTROL's (``command.rejected`` carrying ``consumed``). ``spent_nonce`` is the per-record
    rule, shared with the goal tick's re-derivation (greg/goal_gravity.py ``founder_facts``)."""
    out = set()
    for e in journal.replay("command.accepted") + journal.replay("command.rejected"):
        nonce = spent_nonce(e.type, e.payload)
        if nonce is not None:
            out.add(nonce)
    return out


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
        self.faulted = self.inbox / "faulted"   # files a paused or held body could not ingest; made when needed
        self.outbox = self.home / "outbox"
        # Untrusted data a running body reads on each tick (dataplane.ingest): never a command, never authority.
        # Made by the first drop_intake; a body without it simply has nothing to read.
        self.intake = self.home / "intake"
        self.intake_done = self.intake / "ingested"
        self.intake_refused = self.intake / "refused"
        self.workspace = self.home / "workspace"
        self.artifacts = self.home / "artifacts"
        self.secrets = self.home / "secrets.json"
        self.heartbeat = self.home / "heartbeat.json"
        self.stop_file = self.home / "STOP"
        self.pause_file = self.home / "PAUSE"


def _private_write(path: Path, data: bytes):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as fh:
        fh.write(data)


def init_body(home: str | Path, *, read_roots: list[str], deliver_root: str | Path | None = None,
              local_model: str | None = None, confined_egress: bool = False,
              worker_confinement: str = "required") -> dict:
    """Create a new body directory. Refuses to overwrite an existing body.

    ``deliver_root`` is the founder-visible folder where deliverables (briefs,
    reports) land; it defaults to ``<home>/deliveries``. GREG never writes
    anywhere else outside its own workspace.
    """
    if local_model is not None:
        from greg.models import OllamaRoute
        OllamaRoute(local_model)  # validate before creating any body files or identity
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
              "deliver_root": str(Path(deliver_root or layout.home / "deliveries").expanduser().resolve()),
              "version": BODY_VERSION}
    if local_model is not None:
        config["models"] = {"order": ["ollama"], "ollama_model": local_model}
    if confined_egress:
        config["confined_egress"] = True
    if worker_confinement not in WORKER_CONFINEMENT:
        raise ValueError(f"worker_confinement must be one of {', '.join(WORKER_CONFINEMENT)}")
    if worker_confinement == "supervised":
        # The founder's choice, made once at init: a worker the #157 envelope cannot confine runs under process
        # supervision instead of being refused. Every such run's report says what was not confined.
        config["worker_confinement"] = "supervised"
    _private_write(layout.config, json.dumps(config, indent=2).encode())
    return config


def egress_relay(home: Path, config: dict):
    """#26: the body's one relay when the founder enabled confined egress, else None. Chained through a mandated proxy
    when the environment declares one. The console process builds the same relay over the same hash-chained journal
    (appends are locked across processes) so its model calls are decided and journaled alike.

    Every namespace this process builds from now on hides this body's home (its secrets, keys and ledger)."""
    from foundry.systems.relay_door import hide_from_namespaces
    hide_from_namespaces(home)
    if not config.get("confined_egress"):
        return None
    from foundry.systems.segmentation import Journal as EgressJournal, Relay, policy_from_manifests, \
        proxy_from_environment
    return Relay(policy_from_manifests(), EgressJournal(Path(home) / "egress-journal.jsonl"),
                 proxy=proxy_from_environment())


class Body:
    def __init__(self, home: str | Path, *, clock=None, builder=None, monotonic=None):
        self.layout = Layout(home)
        self.monotonic = monotonic or time.monotonic   # excludes host sleep: presence.note_gap compares it
        if not self.layout.config.exists():
            raise BodyError("no body here; run `greg init` first")
        self.config = json.loads(self.layout.config.read_text())
        # Bodies created before deliverables existed deliver inside their own home.
        self.deliver_root = Path(self.config.get("deliver_root") or self.layout.home / "deliveries")
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self._builder_factory = builder if callable(builder) and not hasattr(builder, "build") else None
        self.builder = builder
        self.stop_requested = False
        self.ledger = None

    # -- open / close ------------------------------------------------------------
    def open(self):
        self.compiled = compile_constitution(str(KERNEL_ROOT))
        if self.compiled.constitution_hash != self.config["constitution_hash"]:
            raise BodyError("Constitution changed since this body was created; an explicit founder-approved "
                            "migration is required (history is bound to the old constitution)")
        self._require_published_head()
        # One writer. A final line torn by power loss or SIGKILL was never acknowledged:
        # quarantine its bytes and continue instead of crash-looping under the supervisor.
        self.ledger = EvidenceLedger(self.compiled.constitution_hash, str(self.layout.ledger), tail="quarantine")
        self.spine = EventSpine(self.ledger)
        self.passports = PassportRegistry()
        self.identity = self.passports.issue(kind="process", creator="greg-body", owner_organ="uniimente-kernel",
                                             legal_principal="alfonso_lopez", declared_capabilities=[],
                                             budget_ceiling_usd=0.0, consequence_class="read_only")
        self.journal = Journal(self.spine, actor=self.identity.passport_id)
        # As the one writer, before any capability can read a workspace: remove the credential files and scratch
        # homes a call left when the process running it was killed mid-call.
        from greg.mcp_tools import sweep_leftovers
        removed = sweep_leftovers(self.layout.workspace)
        if removed:
            self.journal.record("mcp.leftovers_removed", {
                "directories": removed, "why": "a call ended with its process killed; its credential files and "
                                               "scratch home were removed before anything could read them"},
                key=["leftovers", sha256_json(removed), len(self.journal.replay("mcp.leftovers_removed"))])
        signer = WitnessSigner(key=self.layout.witness_key.read_bytes(), env="production")
        self.office = AuthorityOffice(compiled=self.compiled, passports=self.passports, signer=signer,
                                      ledger=self.ledger)
        self.registry = CapabilityRegistry()
        from greg.cognition.catalog import initial_state
        for manifest, adapter in BUILTINS.values():
            self.registry.register(manifest, adapter, state=initial_state(manifest.capability_id))
        self._apply_capability_states()
        self.secrets = SecretBroker(self.layout.secrets)
        self.egress = self._egress_relay()      # before the builder: paid model routes reach providers through it
        if self._builder_factory is None and self.egress is not None and hasattr(self.builder, "egress"):
            self.builder.egress = self.egress   # a ready builder that reaches a provider (Claude Code) gets it too
        self._refresh_builder()
        self.genesis = Genesis(journal=self.journal, registry=self.registry, workspace_root=self.layout.workspace,
                               builder=self.builder, read_roots=self.config["read_roots"])
        self.genesis.restore()
        self.engine = MissionEngine(journal=self.journal, office=self.office, registry=self.registry,
                                    secrets=self.secrets, workspace_root=self.layout.workspace,
                                    read_roots=tuple(self.config["read_roots"]), genesis=self.genesis,
                                    deliver_root=self.deliver_root, artifact_root=self.layout.artifacts)
        self.engine.cognition_model = models.effective_route_config(self.config.get("models"), self.journal)
        self.engine.egress = self.egress
        self.engine.worker_confinement = confinement_mode(self.config.get("worker_confinement"))
        self.engine.selector = self._gravity_order
        return self

    def _gravity_order(self, missions) -> list[str]:
        """Goal Gravity orders this tick's signed missions; each change of the ranking (order, learned
        reliability or exclusions) is a ledger fact a verifier can re-derive from the ledger before it.

        This is #178's ordering (``greg.gravity.select``). #175's persistent-goal binding
        (``greg/goal_gravity.py``) is a separate mechanism that caches itself on ``body._goal_gravity``;
        both run, and neither adds, drops or widens a mission.

        A failure here never stops the missions: the engine keeps its static order and every
        unselected tick is recorded, so it is visible rather than silent."""
        try:
            selection = gravity.select(missions, self.journal)
        except Exception as exc:
            why = f"{type(exc).__name__}: {exc}"[:300]
            prior = len(self.journal.replay("gravity.unavailable"))
            self.journal.record("gravity.unavailable", {"why": why}, key=["unavailable", prior, why])
            return []
        recorded = self.journal.replay("gravity.ranked")
        last = recorded[-1].payload if recorded else None
        if selection["ranking"] and (last is None or last["ranking"] != selection["ranking"]
                                     or last["excluded"] != selection["excluded"]):
            self.journal.record("gravity.ranked", selection, key=["ranked", len(recorded), sha256_json(selection)])
        return [row["mission_id"] for row in selection["ranking"]]

    def _egress_relay(self):
        return egress_relay(self.layout.home, self.config)

    def _require_published_head(self):
        """Refuse history rolled back behind the ledger head this body last published (heartbeat.json).

        Recovery stage 2 (workflows/shutdown-recovery.yaml) needs the chain valid up to the sealed head, and on
        failure no normal-state restoration. The heartbeat names the head of the last turn, or the clean stop, of
        the previous process. That record was fsynced into the ledger before the heartbeat was written, and a
        torn-tail quarantine only removes bytes no append acknowledged, so it is in every honest history of this
        body. A ledger without it was truncated, restored from an older copy or forked; it is refused before
        anything is written to it, on every start, until a person on this machine restores the history or removes
        the heartbeat. Whatever state the heartbeat reports counts alike: RUNNING after a SIGKILL or power loss,
        STOPPED after a clean stop, PAUSED or HELD (the tests pin RUNNING and STOPPED, and a truncated ledger; a
        PAUSED or HELD heartbeat and a deleted ledger take the same path but are not tested on their own).

        Window: Body.run writes the heartbeat once per turn, so the head it names trails the ledger by the records
        appended since: at most one turn's, or a boot's and its first turn's. A rollback that removes only those
        records is not detected here. A guard against rollback by accident or a stale copy, not against someone
        who can rewrite both files (greg/anchor.py witnesses cover that). An unreadable heartbeat is not evidence
        (presence). Cost: a start reads and verifies the whole chain twice, here and in the writer's own open."""
        try:
            published = json.loads(self.layout.heartbeat.read_text()).get("ledger_head")
        except (OSError, ValueError, AttributeError):
            return
        if not isinstance(published, str):
            return
        if self.layout.ledger.exists():
            reader = EvidenceLedger(self.compiled.constitution_hash, str(self.layout.ledger), read_only=True,
                                    tail="ignore")
            try:
                if reader.find(published) is not None:
                    return
            finally:
                reader.close()
        raise BodyError(f"the ledger head {published} this body last published (heartbeat.json) is not in this "
                        "ledger: its history was rolled back, truncated or replaced. The body stays down and "
                        "writes nothing; restore the ledger that contains that head, or, if this history is the "
                        "one to keep, remove heartbeat.json on this machine")

    def _refresh_builder(self):
        """Replace the model adapter, never the mission engine, ledger or authority office."""
        if self._builder_factory is not None:
            try:
                config = {**self.config, "models": models.effective_route_config(self.config.get("models"), self.journal)}
                # A confined body hands its relay to the factory; one that cannot take it builds nothing (fail closed).
                extra = {"egress": self.egress} if getattr(self, "egress", None) is not None else {}
                self.builder = self._builder_factory(self.secrets, config, **extra)
            except Exception as exc:
                why = f"{type(exc).__name__}: {exc}"[:300]
                self.builder = None
                self.journal.record("genesis.builder", {"available": False, "why": why}, key=["unavailable", why])
        router = getattr(self.builder, "router", None)
        if router is not None and hasattr(router, "observe"):
            for event in self.journal.replay("model.route"):
                router.observe(event.payload)
            from greg import model_keys        # a refused key is benched until a new one is stored, and recorded
            model_keys.attach(router, self.journal)
        if hasattr(self, "genesis"):
            self.genesis.builder = self.builder

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
        return founder_keys(self.journal)

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
        return nonce in consumed_nonces(self.journal)

    def verifier(self) -> FounderVerifier:
        return FounderVerifier(body_id=self.config["body_id"], enrolled=self.enrolled_keys(),
                               seen_nonce=self._seen_nonce, devices=self.device_keys())

    # -- commands ------------------------------------------------------------------
    def apply(self, envelope: dict, *, channel: str = "direct") -> dict:
        """Verify one signed founder command and apply it (idempotent on replay of the same file)."""
        digest = sha256_json(envelope)
        # Only a record carrying this very envelope and its nonce, as this method writes one, makes a replay of the
        # file a no-op: a bare record naming the digest cannot silently drop the founder's command.
        prior = [e.payload for e in self.journal.replay("command.accepted") if e.payload.get("digest") == digest
                 and isinstance(e.payload.get("envelope"), dict) and sha256_json(e.payload["envelope"]) == digest
                 and e.payload.get("nonce") == envelope.get("nonce")]
        if prior:
            if envelope.get("kind") == "DECISION":
                self.engine.book.rebuild()
                if not any(a.get("command_digest") == digest for a in self.engine.book.answers.values()):
                    # an acceptance someone else wrote for this very envelope, with no answer the book counts: its
                    # nonce is spent there, so re-applying cannot help; say so instead of dropping it silently
                    raise MissionError("this signed decision is already recorded as accepted, but no answer counts "
                                       "for it; sign your answer again")
            return {"status": "ALREADY_APPLIED", "digest": digest}
        now = self.clock()
        verifier = self.verifier()
        env = verifier.verify(envelope, now=now)
        principal = verifier.principal(env, now=now)
        kind, body = env["kind"], env["body"]
        self._after_restore(env, kind, principal)
        # Commands are applied before the next tick's rebuild; a request raised during the
        # previous tick must already be visible, or a fast approval is refused as "unknown".
        # A STOP authenticated mid-tick (while a worker runs) must not rebuild in-flight state.
        if kind != "BODY_STOP":
            self.engine.book.rebuild()
        try:
            result = self._dispatch(kind, body, digest, principal=principal, envelope=env, now=now)
        except (MissionError, ValueError, KeyError, TypeError) as exc:
            if kind in NONCE_CONSUMED_ON_REJECT:   # verified, then refused: the nonce is spent (ingest_inbox records it)
                exc.consumed = {"kind": kind, "digest": digest, "nonce": env["nonce"], "signer": principal}
            raise
        self.journal.record("command.accepted", {"kind": kind, "digest": digest, "nonce": env["nonce"],
                                                  "founder_key_id": env["founder_key_id"], "signer": principal,
                                                  "issued_at": env["issued_at"], "accepted_at": iso(now),
                                                  "envelope": env, "channel": channel,   # body: env["body"]
                                                  "result": result}, key=digest)
        if kind == "DECISION":   # the answer counts from its acceptance (MissionBook): Goal Gravity reads it this tick
            self.engine.book.rebuild()
        return {"status": "APPLIED", "digest": digest, "result": result}

    def _after_restore(self, env: dict, kind: str, principal: str) -> None:
        """A body restored from a backup (greg/recovery.py) knows nothing after its recovery point: it refuses any
        command issued before the restore, which the original may already have applied, and only the founder key
        releases the restore hold."""
        restores = self.journal.replay("body.restored")
        if not restores:
            return
        restore = restores[-1].payload
        if instant(env["issued_at"]) < instant(restore["restored_at"]):
            raise FounderAuthError(f"issued before this body was restored from a backup at {restore['restored_at']}: "
                                   "the original may already have applied it; sign it again if it is still wanted")
        if kind == "BODY_RESUME" and principal != "founder" and self._restore_hold():
            raise FounderAuthError("only the founder key releases a restore hold")

    def _restore_hold(self) -> bool:
        state = [e for e in self.journal.replay("body.") if e.type in ("greg.body.paused", "greg.body.resumed")]
        return bool(state) and state[-1].type == "greg.body.paused" and "restore_id" in state[-1].payload

    def _dispatch(self, kind: str, body: dict, digest: str, *, principal: str = "founder",
                  envelope: dict | None = None, now: datetime | None = None):
        if kind == "MISSION":
            return {"mission_id": self.engine.register(body, digest)}
        if kind == "DECISION":
            self.engine.answer(body, digest)
            return {"request_id": body["request_id"]}
        if kind == "LIFECYCLE":
            self.engine.lifecycle(body, digest)
            return {"mission_id": body["mission_id"], "state": body["state"]}
        if kind == "REALIZATION":
            # evidence only: the observed values of one retained forecast, or the realized objective of one
            # construction answer, labelled by source; it scores the method's calibration or world competence and
            # changes no mission, capability or authority
            from greg.cognition.settlement import record_realization, record_resolution
            if "resolves" in body:
                # a correction of a disputed construction outcome: it accepts one independent observation already
                # recorded, or invalidates the named reports; every fact stays on the record
                if set(body) - {"receipt", "resolves", "accept", "note"}:
                    raise MissionError("a resolution takes receipt, resolves, accept and note")
                payload = record_resolution(self.journal, receipt=body.get("receipt"), resolves=body.get("resolves"),
                                            accept=body.get("accept"), note=body.get("note", ""),
                                            command_digest=digest)
                return {"receipt": payload["receipt"], "resolves": payload["resolves"], "accept": payload["accept"]}
            if set(body) - {"receipt", "realized", "source", "note"}:
                raise MissionError("a realization takes receipt, realized, source and note")
            payload = record_realization(self.journal, receipt=body.get("receipt"), realized=body.get("realized"),
                                         source=body.get("source", "founder_reported"), note=body.get("note", ""),
                                         command_digest=digest)
            return {"receipt": payload["receipt"], "cognitive_receipt": payload.get("cognitive_receipt"),
                    **({"compile_receipt": payload["compile_receipt"]} if "compile_receipt" in payload else {}),
                    **({"met": payload["met"]} if "met" in payload else {})}
        if kind == "CRITIQUE":
            record = tribunal.critique(self.journal, self.engine, body, digest)
            if record.get("epistemic"):   # founder evidence advances the held-out learning loop now
                improvement.learn(self.journal, self.ledger, self.clock())
            return record
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
            answered = {e.payload["request_id"] for e in self.journal.replay("decision.")
                        if e.type in ("greg.decision.answered", "greg.decision.withdrawn")}
            for ask in self.journal.replay("decision.requested"):   # the resume lifted the hold its ask was about
                rid = ask.payload["request_id"]
                if ask.payload.get("kind") == HOLD_ASK and rid not in answered:
                    self.journal.record("decision.withdrawn", {
                        "request_id": rid, "mission_id": None, "why": "a signed BODY_RESUME lifted the hold",
                        "evidence": {"command_digest": digest}, "at": iso(self.clock())}, key=[rid, "withdrawn"])
            return {"paused": False}
        if kind == "BODY_DESIGNATE":
            if body != {"purpose": "first_founder_body"}:
                raise MissionError("body designation must name exactly the first founder body purpose")
            prior = self.journal.replay("body.designated")
            if prior:
                if len(prior) == 1 and prior[0].payload["command_digest"] == digest:
                    # Power loss after the designation event but before command.accepted:
                    # the same signed envelope can finish its acceptance on replay.
                    return prior[0].payload
                raise MissionError("the first body is already designated; do not silently replace it")
            record = {"body_id": self.config["body_id"], "platform": os.uname().sysname,
                      "device_class": doctor.device_class(),   # informational; never part of founder_body
                      "purpose": body["purpose"], "command_digest": digest, "at": iso(self.clock())}
            self.journal.record("body.designated", record, key=[self.config["body_id"], "first"])
            return record
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
        if kind == "FOUNDER_TIER":               # founder key only (DEVICE_KINDS excludes it)
            from greg.founder import FOUNDER_TIER_BODY
            if body != FOUNDER_TIER_BODY:
                raise MissionError(f"a founder-tier attestation is exactly {FOUNDER_TIER_BODY}")
            # The accepted command (its signer and key id) is the record greg.metrics.founder_tier reads.
            return {**FOUNDER_TIER_BODY, "authority_changed": False}
        if kind == "TREASURY_REQUIREMENTS":      # founder key only (DEVICE_KINDS excludes it)
            from greg.venture_books import validate_requirements
            declared = validate_requirements(body)
            self.journal.record("treasury.requirements", {**declared, "command_digest": digest}, key=digest)
            return {**declared, "money_moved": False, "authority_changed": False}
        if kind == "MODEL_ROUTE_SET":
            selection = models.validate_route_selection(body)
            self.journal.record("model.configured", {"selection": selection, "command_digest": digest}, key=digest)
            self._refresh_builder()
            return {"selection": selection, "builder_configured": self.builder is not None,
                    "console_refreshes_before_draft_or_sign": True, "authority_changed": False}
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
        if kind == "ANCHOR_CONFIGURE":
            try:
                return anchor.configure(self.journal, body, digest)
            except anchor.AnchorError as exc:
                raise MissionError(str(exc)) from None
        if kind == "ROTATE_FOUNDER_KEY":
            new_hex = body["new_public_key"]
            old = next(iter(self.enrolled_keys()))
            self.journal.record("founder.key_rotated", {"old_key_id": old, "new_key_id": key_id(new_hex),
                                                        "new_public_key": new_hex, "command_digest": digest},
                                key=digest)
            return {"new_key_id": key_id(new_hex)}
        if kind in ("GOAL", "GOAL_CONTROL"):
            # A persistent goal bound to signed missions (ADR-GOAL-GRAVITY-002). GOAL is founder-key only;
            # a device may sign GOAL_CONTROL only to narrow a goal (the binding checks the principal).
            from greg import goal_gravity
            return goal_gravity.command(self, kind, body, digest, signer=principal, envelope=envelope, now=now)
        raise MissionError(f"unsupported command kind {kind}")

    def _stop_now(self) -> bool:
        if not self.stop_requested and not self.layout.stop_file.exists() and self.ledger is not None:
            # Extracted from #157: a paid worker can run for minutes. While it is supervised, only pending
            # founder-signed STOP commands are authenticated; every other command waits for the next tick
            # and cannot change in-flight strategy or approval state.
            self.ingest_inbox(only_kind="BODY_STOP")
        return self.stop_requested or self.layout.stop_file.exists()

    def paused(self) -> bool:
        if self.layout.pause_file.exists():
            return True
        state = [e.type for e in self.journal.replay("body.") if e.type in ("greg.body.paused", "greg.body.resumed")]
        return bool(state) and state[-1] == "greg.body.paused"

    def ingest_inbox(self, *, only_kind: str | None = None) -> list[dict]:
        results = []
        stuck = self.__dict__.setdefault("_stuck", set())   # files this process could neither ingest nor set aside
        for path in sorted(self.layout.inbox.glob("*.json")):
            if path.name in stuck:
                continue
            try:
                outcome = self._ingest_one(path, only_kind=only_kind)
            except Exception as exc:   # anywhere in the file's handling, its rejection path included
                if not self.paused():
                    raise     # a running body exits on it: its supervisor restarts it and the breaker counts the boot
                try:
                    outcome = self._set_aside(path, exc)
                except Exception as failed:
                    # it can be neither read nor moved (a name too long to extend, no permission): skip it for the
                    # life of this process, so the files behind it, a signed resume among them, are still read
                    stuck.add(path.name)
                    outcome = self._stuck_file(path, exc, failed)
            if outcome is None:          # another kind, while only ``only_kind`` is read: left in the inbox
                continue
            results.append(outcome)
        return results

    def _dropped(self) -> set:
        """Signed commands and untrusted intake items waiting: a new one wakes the run loop before its tick."""
        return set(self.layout.inbox.glob("*.json")) | set(self.layout.intake.glob("*.json"))

    def ingest_intake(self) -> list[dict]:
        """Read up to INTAKE_PER_TICK untrusted items dropped into intake/ into the data plane, oldest name first.

        Each item is one JSON file {"source", "channel", "content"}. It is retained as evidence exactly as the
        stopped-body intake retains it (dataplane.ingest: may_command and may_grant false, instruction-shaped text
        quarantined), then moved to intake/ingested. A file that is not one regular, bounded, well-formed item is
        moved to intake/refused with a recorded reason. A crash between retaining and moving re-reads the file,
        and the data plane returns the retained fact instead of recording it twice."""
        if not self.layout.intake.is_dir():
            return []
        results = []
        for path in sorted(self.layout.intake.glob("*.json"))[:INTAKE_PER_TICK]:
            raw, why = _read_intake(path)
            item = None
            if why is None:
                try:
                    item = json.loads(raw)
                except ValueError:
                    why = "not JSON"
            if why is None:
                why = _intake_shape(item)
            if why is None:
                results.append(dataplane.ingest(self.journal, source=item["source"], content=item["content"],
                                                channel=item["channel"]))
                _move(path, self.layout.intake_done)
                continue
            digest = hashlib.sha256(raw).hexdigest() if raw is not None else None
            self.journal.record("external.intake_refused", {"file": path.name[:120], "why": why,
                                                             "content_sha256": digest},
                                key=[path.name[:120], digest, why])
            _move(path, self.layout.intake_refused)
        return results

    def _stuck_file(self, path: Path, exc: Exception, failed: Exception) -> dict:
        error = f"{type(exc).__name__}: {exc}"[:300] + f"; set-aside failed: {type(failed).__name__}: {failed}"[:200]
        site = f"inbox file {path.name[:120]} (skipped by this process)"
        digest = sha256_json({"error": type(failed).__name__, "site": site})
        try:
            self.journal.record("body.fault_contained", {
                "boot_id": getattr(self, "boot_id", None), "fault_digest": digest, "error": error, "site": site,
                "state": "HELD" if crash_loop_hold(self.journal) else "PAUSED",
                "inbox_waiting": sorted(p.name for p in self.layout.inbox.glob("*.json")), "at": iso(self.clock()),
                "action": "contained: the file stays in the inbox, unread, and this process reads the files behind "
                          "it; it is tried again after a restart"},
                key=[getattr(self, "boot_id", None), digest])
        except Exception:
            pass   # the skip stands even when the ledger cannot take the record; the heartbeat still shows HELD
        return {"status": "SKIPPED", "file": path.name, "reason": error}

    def _ingest_one(self, path: Path, *, only_kind: str | None = None) -> dict | None:
        envelope = None
        try:
            envelope = json.loads(path.read_text())
            if only_kind is not None and (not isinstance(envelope, dict) or envelope.get("kind") != only_kind):
                return None
            outcome = self.apply(envelope, channel="inbox")
        except (FounderAuthError, MissionError, ValueError, KeyError, TypeError,
                tribunal.CritiqueError) as exc:
            raw = path.read_bytes()
            consumed = getattr(exc, "consumed", None)
            # the reason is part of the fact: the same file rejected again for another reason (re-dropped after the
            # state that refused it changed) is a second rejection, not a reused fact identity the ledger refuses
            # (which crashed the body)
            key = [path.name, sha256_json(raw.hex()), sha256_json(f"{type(exc).__name__}: {exc}")]
            # When and which command it refused, by the body's clock: an acceptance of the same command claiming an
            # earlier time is a backdated record (greg.goal_gravity.founder_facts). Recorded once, so a retry after a
            # crash finds the retained refusal instead of a different time.
            if self.journal.retained("command.rejected", key) is None:
                self.journal.record("command.rejected", {
                    "file": path.name, "sha256": sha256_json(raw.hex()),
                    "reason": f"{type(exc).__name__}: {exc}"[:500], "instruction_status": "data_only",
                    "at": iso(self.clock()),
                    **({"digest": sha256_json(envelope)} if isinstance(envelope, dict) else {}),
                    **({"consumed": consumed} if consumed else {})}, key=key)
            shutil.move(str(path), self.layout.rejected / path.name)
            return {"status": "REJECTED", "file": path.name, "reason": str(exc)[:300]}
        try:
            shutil.move(str(path), self.layout.processed / path.name)
        except OSError as exc:
            exc.applied = outcome     # the command was accepted and applied; only its file could not be filed
            raise
        return outcome

    def _set_aside(self, path: Path, exc: Exception) -> dict:
        """An inbox file whose ingestion raised while the body is paused or held: kept under inbox/faulted, unread.

        The inbox is read in name order, so one such file failed every turn and kept every later file, a signed
        BODY_RESUME among them, from ever being read: the held body could not be resumed. It is moved aside byte
        for byte (never deleted, never accepted as a command) and recorded once with its digest and error, and the
        turn goes on to the next file. Setting a file aside lifts nothing; only a valid signed command does."""
        try:
            raw = path.read_bytes()
        except OSError:
            raw = None
        recorded = {e.payload["kept_as"] for e in self.journal.replay("command.faulted")}
        try:
            self.layout.faulted.mkdir(exist_ok=True)
            target = self.layout.faulted / path.name
            if target.exists() or f"inbox/faulted/{target.name}" in recorded:
                # never overwrite a file set aside earlier, nor reuse the name of one recorded (and since removed)
                target = target.with_name(f"{path.stem}.{secrets.token_hex(4)}{path.suffix}")
            shutil.move(str(path), target)       # first, so a crash before the record loses no bytes
            kept_as = f"inbox/faulted/{target.name}"
        except OSError:
            # inbox/faulted cannot take it (missing permission, a file in its place): set it aside in place, out of
            # the *.json read, so it still cannot keep a later signed command from being read
            target = path.with_name(f"{path.name}.{secrets.token_hex(4)}{FAULTED_SUFFIX}")
            path.rename(target)
            kept_as = f"inbox/{target.name}"
        applied = getattr(exc, "applied", None)
        record = {"file": path.name, "kept_as": kept_as,
                  "sha256": sha256_json(raw.hex()) if raw is not None else None,
                  "error": f"{type(exc).__name__}: {exc}"[:500], "boot_id": getattr(self, "boot_id", None),
                  "state": "HELD" if crash_loop_hold(self.journal) else "PAUSED", "at": iso(self.clock()),
                  "instruction_status": "applied" if applied else "data_only",
                  **({"applied": True} if applied else {})}
        self.journal.record("command.faulted", record, key=[kept_as, "faulted"])
        return {"status": "SET_ASIDE", "file": path.name, "kept_as": kept_as, "reason": record["error"][:300],
                **({"applied": applied} if applied else {})}

    # -- lifecycle -----------------------------------------------------------------
    def boot(self, *, main_loop: bool = False) -> dict:
        crashed = unfinished_main_loop_boots(self.journal, self.clock()) if main_loop else []
        boots = self.journal.replay("body.booted")
        stops = {e.payload["boot_id"] for e in self.journal.replay("body.stopped")}
        unfinished = [b.payload["boot_id"] for b in boots if b.payload["boot_id"] not in stops]
        boot_id = "boot-" + secrets.token_hex(8)
        record = {"boot_id": boot_id, "pid": os.getpid(), "at": iso(self.clock()), "version": BODY_VERSION,
                  "body_id": self.config["body_id"], "boot_number": len(boots) + 1,
                  "platform": os.uname().sysname, "ledger_head_at_boot": self.ledger.head}
        if self.ledger.unacknowledged_tail:
            record["ledger_recovery"] = dict(self.ledger.unacknowledged_tail)
        try:   # read before this process overwrites it: bounds the absence since the previous process
            last = presence.previous_heartbeat(json.loads(self.layout.heartbeat.read_text()))
        except (OSError, ValueError):
            last = None
        if last is not None:
            record["previous_heartbeat"] = last
        if main_loop:
            record["main_loop"] = True
        self.journal.record("body.booted", record, key=boot_id)
        if unfinished:
            self.journal.record("body.recovered", {"boot_id": boot_id, "previous_unfinished_boots": unfinished,
                                                   "action": "missions reconstructed from retained history; "
                                                             "uncertain dispatches reconcile, never blind-retry"},
                                key=[boot_id, "recovered"])
        if len(crashed) >= CRASH_LOOP_BOOTS and not self.paused():   # a pause in force (yours or a hold) stays
            hold = {"by": BREAKER, "boot_id": boot_id, "unfinished_boots": crashed,
                    "window_seconds": CRASH_LOOP_WINDOW_SECONDS, "at": iso(self.clock()),
                    "why": f"{len(crashed)} main-loop boots in a row ended without a clean stop within "
                           f"{CRASH_LOOP_WINDOW_SECONDS} s; no mission runs until a signed BODY_RESUME",
                    "lifted_by": RESUME_LIFTS}
            self.journal.record("body.paused", hold, key=[boot_id, "crash-loop"])
            record["held"] = hold["why"]
        hold = crash_loop_hold(self.journal)
        if hold is not None:   # one ask per hold; re-derived here, so a crash between the two records loses none
            ask = hold_ask(hold)
            if all(e.payload["request_id"] != ask["request_id"] for e in self.journal.replay("decision.requested")):
                asks.record(self.journal, ask)
        self.boot_id = boot_id
        return record

    def tick(self) -> dict:
        now = self.clock()
        commands = self.ingest_inbox()
        if self.stop_requested:
            return {"commands": commands, "stopped": True}
        if self.paused():
            hold = crash_loop_hold(self.journal)
            self._heartbeat("HELD" if hold else "PAUSED", [])
            return {"commands": commands, "paused": True, **({"held": hold["why"]} if hold else {})}
        # untrusted observations dropped while the body runs, read before Goal Gravity so a goal they wake is
        # served this tick; reading them is data only and changes what a mission may do in no way
        self.ingest_intake()
        # Goal Gravity first, so an awake goal's pulled observation is stepped in this same tick. Without a
        # founder-signed goal on the ledger it does no work and writes nothing (None).
        from greg import autonomy, goal_gravity
        autonomy.regress(self.journal, self.engine.book, now)   # failure evidence withdraws a standing approval first
        gravity = goal_gravity.tick(self, now)
        self.engine.cognition_model = models.effective_route_config(self.config.get("models"), self.journal)
        recovered = self.genesis.recover(now)     # quarantined capabilities may earn back eligibility (sandbox)
        summary = self.engine.tick(now, should_stop=self._stop_now)
        if self._stop_now():
            return {"commands": commands, "missions": summary, "stopped": True}
        self._close_out(now)
        from greg.cognition.settlement import reconcile as settle_cognition
        settle_cognition(self.journal)
        improvement.learn(self.journal, self.ledger, now)   # held-out evidence from this tick's briefs
        sop.propose(self.journal)
        transport = (anchor.relay_transport(self.egress, self.layout.workspace / ".anchor")
                     if getattr(self, "egress", None) is not None else None)
        anchored = anchor.anchor_once(self.journal, now, transport=transport) if anchor.due(self.journal, now) else None
        result = {"commands": commands, "missions": summary, "anchor": anchored, "recovery": recovered}
        if gravity is not None:
            result["gravity"] = gravity
        return result

    def _close_out(self, now):
        """Record where each closure happened and have it appraised by a separate process."""
        contexts = {e.payload["mission_id"] for e in self.journal.replay("mission.closure_context")}
        # an achievement is judged as its own closure: an appraisal of an earlier failure or hold of the same
        # mission (it names that closure_event) never stands in for the appraisal of its success (TXT-R4-1)
        appraised = {e.payload["mission_id"] for e in self.journal.replay("mission.appraised")
                     if not e.payload.get("closure_event")}
        for event in self.journal.replay("mission.achieved"):
            mid = event.payload["mission_id"]
            if mid not in contexts:
                self.journal.record("mission.closure_context", {
                    "mission_id": mid, "boot_id": getattr(self, "boot_id", None), "pid": os.getpid(),
                    "platform": os.uname().sysname, "body_id": self.config["body_id"],
                    "hosted": getattr(self, "boot_id", None) is not None,
                    "device_class": doctor.device_class(),   # informational; never part of founder_body
                    "at": iso(now)}, key=[mid, "context"])
            if mid not in appraised:
                self._appraise_closure(mid, None, now)
        judged = {e.payload.get("closure_event") for e in self.journal.replay("mission.appraised")}
        for event in self.journal.replay("mission.held") + self.journal.replay("mission.unmet"):
            if event.event_id not in judged:
                self._appraise_closure(event.payload["mission_id"], event.event_id, now)

    def _appraise_closure(self, mid: str, closure_event: str | None, now):
        """One appraiser run for one closure, recorded; a run that gave no verdict is retried on a later tick.

        The appraiser is a separate process. When it is killed, times out or writes no readable verdict, it judged
        nothing, so nothing is recorded as its verdict (acceptance H.G7): the run is one unavailable attempt and
        the closure is appraised again on the next tick. After APPRAISAL_ATTEMPTS such runs the closure is recorded
        appraised UNAVAILABLE, which is final: it is never VERIFIED and the closure is not appraised again."""
        unavailable = [e.payload for e in self.journal.replay("mission.appraisal_unavailable")
                       if e.payload["mission_id"] == mid and e.payload.get("closure_event") == closure_event]
        prior = [u["why"] for u in unavailable]
        if len(prior) >= APPRAISAL_ATTEMPTS:
            # the body died between the last unavailable run and its final record: finish it, run nothing more
            last = unavailable[-1]
            self.journal.record("mission.appraised", {
                "mission_id": mid, "head": last["head"], "verdict": "UNAVAILABLE", "checks": {},
                "findings": prior, "appraiser": "separate process", "attempts": len(prior),
                **({"closure_event": closure_event} if closure_event else {})},
                key=[mid, "appraised", closure_event or last["head"]])
            return
        verdict = self.appraise(mid, closure_event=closure_event)
        key = [mid, "appraised", closure_event or verdict["head"]]
        if verdict["verdict"] in APPRAISER_VERDICTS:
            self.journal.record("mission.appraised", verdict, key=key)
            return
        attempt, why = len(prior) + 1, verdict["findings"][0]
        self.journal.record("mission.appraisal_unavailable", {
            "mission_id": mid, **({"closure_event": closure_event} if closure_event else {}), "attempt": attempt,
            "of": APPRAISAL_ATTEMPTS, "head": verdict["head"], "why": why, "boot_id": getattr(self, "boot_id", None),
            "at": iso(now)}, key=[mid, closure_event, "appraisal_unavailable", attempt])
        if attempt >= APPRAISAL_ATTEMPTS:
            self.journal.record("mission.appraised", {**verdict, "attempts": attempt, "findings": prior + [why]},
                                key=key)

    def appraisal_request(self, mission_id: str, *, closure_event: str | None = None) -> dict:
        """What the separate appraiser re-derives from: the head, the scope, and the postures the original ran in
        (worker confinement, confined egress), so a re-run is exactly as confined as the original."""
        request = {"ledger": str(self.layout.ledger), "constitution": self.compiled.constitution_hash,
                   "head": self.ledger.head, "mission_id": mission_id, "read_roots": self.config["read_roots"],
                   "deliver_root": str(self.deliver_root),
                   "artifact_root": str(self.layout.artifacts),
                   "workspace": str(self.layout.workspace / mission_id.replace(":", "_")),
                   "worker_confinement": confinement_mode(self.config.get("worker_confinement")),
                   "confined_egress": bool(self.config.get("confined_egress"))}
        if closure_event:
            request["closure_event"] = closure_event
        return request

    def appraise(self, mission_id: str, *, closure_event: str | None = None) -> dict:
        import subprocess
        import sys
        request = self.appraisal_request(mission_id, closure_event=closure_event)
        env = {"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8", "PYTHONDONTWRITEBYTECODE": "1",
               "PYTHONPATH": os.pathsep.join([str(KERNEL_ROOT)] + [p for p in sys.path if "-packages" in p])}
        def unavailable(why: str) -> dict:   # the appraiser judged nothing: not a verdict (see _appraise_closure)
            return {"mission_id": mission_id, "head": request["head"], "verdict": "UNAVAILABLE",
                    "checks": {}, "findings": [why[:600]], "appraiser": "separate process",
                    **({"closure_event": closure_event} if closure_event else {})}
        try:
            child = subprocess.run([sys.executable, "-m", "greg.appraisal"], input=json.dumps(request),
                                   capture_output=True, text=True, timeout=APPRAISAL_TIMEOUT_SECONDS, env=env,
                                   cwd=KERNEL_ROOT)
        except subprocess.TimeoutExpired as exc:   # subprocess.run killed it; a hung appraiser never crashes the body
            return unavailable(f"the appraiser gave no verdict within {exc.timeout:g} s and was killed")
        if child.returncode:
            return unavailable(f"the appraiser exited {child.returncode} without a verdict: {child.stderr[-500:]}")
        try:
            verdict = json.loads(child.stdout)
        except ValueError:
            return unavailable("the appraiser exited 0 without a readable verdict")
        if not isinstance(verdict, dict) or verdict.get("verdict") not in APPRAISER_VERDICTS:
            return unavailable("the appraiser exited 0 without a readable verdict")
        return verdict

    def next_wake(self, tick_seconds: float) -> float:
        """Seconds until the next turn: a full tick, or sooner when a mission the next tick steps is due.

        Only a mission the engine will step pulls the wake forward. A paused or held body steps none, and a
        LIFECYCLE-paused or blocked mission is not stepped toward its observation (MissionEngine._step returns
        before it schedules one), so its past next_observe_at stays past: counted as due, it turned the loop
        every 0.05 s, running the whole tick and sampling telemetry about once a second."""
        if self.paused():
            return tick_seconds
        now = self.clock()
        horizon = now + timedelta(seconds=tick_seconds)
        for m in self.engine.book.missions.values():
            if m.next_observe_at and m.status not in ("ACHIEVED", "ABANDONED", "SUPERSEDED") and not m.blocker \
                    and not m.paused:
                at = datetime.fromisoformat(m.next_observe_at.replace("Z", "+00:00"))
                horizon = min(horizon, max(at, now))
        return max(0.05, (horizon - now).total_seconds())

    def _contained(self, work, *args):
        """One piece of the work a paused or held body still does each turn (read its inbox, note a gap).

        A failure there would otherwise kill every restart with no further signal (a held body exists because
        restarts did not help). While the body is paused or held it is recorded once per boot and failure site,
        and the body stays up, observable and reading its inbox; None is returned. A body that is not paused
        fails as before: the process dies, the supervisor restarts it and the breaker counts the boot."""
        try:
            return work(*args)
        except Exception as exc:
            if not self.paused():
                raise
            import traceback
            frames = traceback.extract_tb(exc.__traceback__)
            site = f"{Path(frames[-1].filename).name}:{frames[-1].lineno} {frames[-1].name}" if frames else "unknown"
            digest = sha256_json({"error": type(exc).__name__, "site": site})
            if all(e.payload["boot_id"] != self.boot_id or e.payload["fault_digest"] != digest
                   for e in self.journal.replay("body.fault_contained")):
                self.journal.record("body.fault_contained", {
                    "boot_id": self.boot_id, "fault_digest": digest, "error": f"{type(exc).__name__}: {exc}"[:500],
                    "site": site, "state": "HELD" if crash_loop_hold(self.journal) else "PAUSED",
                    "inbox_waiting": sorted(p.name for p in self.layout.inbox.glob("*.json")),
                    "at": iso(self.clock()), "action": "contained: the paused body stays up, observable and "
                                                       "reading its inbox; recorded once per boot and site"},
                    key=[self.boot_id, digest])
            return None

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
            self.boot(main_loop=True)
            ticks = active = 0
            last_seen = None
            while True:
                if self.layout.stop_file.exists():
                    reason = "local STOP file"
                    break
                waiting = self._dropped()   # one still here after this turn wakes nothing
                seen = (self.clock(), self.monotonic())
                if last_seen is not None:
                    self._contained(presence.note_gap, self.journal, self.boot_id, last_seen, seen)
                last_seen = seen
                result = self._contained(self.tick)
                if result is None:                # a paused body's turn failed, contained: it is still paused
                    hold = crash_loop_hold(self.journal)
                    result = {"paused": True, **({"held": hold["why"]} if hold else {})}
                if self.stop_requested:
                    reason = "founder BODY_STOP or signal"
                    break
                ticks += 1
                idle = bool(result.get("paused"))  # paused or held: no mission steps, so nothing is measured or due
                if not idle:
                    active += 1
                    if active % telemetry_every == 1:
                        compute.record_telemetry(self.journal, self.layout.home)
                        compute.recommend(self.journal)
                        presence.recommend(self.journal, now=self.clock(),
                                           platform_hint="chromeos" if doctor.is_crostini() else None)
                self._heartbeat("HELD" if result.get("held") else "PAUSED" if result.get("paused") else "RUNNING",
                                result.get("missions", []))
                if max_ticks is not None and ticks >= max_ticks:
                    reason = "max_ticks reached"
                    break
                # A paused or held body, or a paused mission, serves no due observation, so it waits a full tick
                # instead of spinning on one (next_wake); a new inbox file (a signed resume, say), a new intake
                # item or a stop wakes the body sooner.
                deadline = time.monotonic() + self.next_wake(tick_seconds)
                while time.monotonic() < deadline and not self.stop_requested:
                    if self.layout.stop_file.exists() or self._dropped() - waiting:
                        break
                    time.sleep(min(0.2, max(0.0, deadline - time.monotonic())))
            self.journal.record("body.stopped", {"boot_id": self.boot_id, "reason": reason,
                                                 "at": iso(self.clock()), "ledger_head": self.ledger.head},
                                key=[self.boot_id, "stopped"])
            self._heartbeat("STOPPED", [])
            return 0
        finally:
            self.close()


@contextmanager
def observe(home: str | Path, *, actor: str = "spiffe://uniimente.internal/greg/observer"):
    """Read-only view of retained history, safe while the body runs.

    Never takes the writer lock. A line the body is still writing (or one torn by
    a crash) was never acknowledged and is left out rather than failing the read.
    """
    layout = Layout(home)
    config = json.loads(layout.config.read_text())
    ledger = EvidenceLedger(config["constitution_hash"], str(layout.ledger), read_only=True, tail="ignore")
    try:
        yield Journal(EventSpine(ledger), actor=actor)
    finally:
        ledger.close()


INTAKE_PER_TICK = 32                 # a flood of drops cannot starve a tick; the rest wait for the next ones
INTAKE_MAX_BYTES = 64 * 1024         # one item; the data plane retains its first MAX_RETAINED characters


def _read_intake(path: Path) -> tuple[bytes | None, str | None]:
    """The bytes of one dropped item, or why it is refused unread: never a link, a FIFO or a device."""
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except OSError as exc:
        return None, f"unreadable: {type(exc).__name__}"
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode):
            return None, "not a regular file"
        if info.st_size > INTAKE_MAX_BYTES:
            return None, f"larger than {INTAKE_MAX_BYTES} bytes"
        raw = os.read(fd, INTAKE_MAX_BYTES + 1)
        return (raw, None) if len(raw) <= INTAKE_MAX_BYTES else (None, f"larger than {INTAKE_MAX_BYTES} bytes")
    finally:
        os.close(fd)


def _intake_shape(item) -> str | None:
    if not isinstance(item, dict) or set(item) != {"source", "channel", "content"}:
        return "not one {source, channel, content} item"
    if not all(isinstance(item[k], str) for k in item) or not item["source"].strip() or not item["channel"].strip():
        return "source, channel and content must be text, source and channel non-empty"
    return None


def _move(path: Path, folder: Path):
    folder.mkdir(mode=0o700, exist_ok=True)
    os.replace(path, folder / path.name)


def drop_intake(home: str | Path, *, source: str, content: str, channel: str) -> Path:
    """Hand one untrusted item to the body, running or stopped: it is read on the next tick (Body.ingest_intake).
    This writes data only. Nothing in intake/ can become a command."""
    layout = Layout(home)
    if not layout.config.exists():
        raise BodyError(f"no body at {layout.home}")
    layout.intake.mkdir(mode=0o700, exist_ok=True)
    data = json.dumps({"source": source, "channel": channel, "content": content}).encode()
    if len(data) > INTAKE_MAX_BYTES:
        raise BodyError(f"an intake item holds at most {INTAKE_MAX_BYTES} bytes")
    target = layout.intake / f"{iso(utcnow()).replace(':', '')}-{secrets.token_hex(4)}.json"
    temporary = target.with_suffix(".tmp")       # not *.json: the body never reads a half-written item
    temporary.write_bytes(data)
    temporary.replace(target)
    return target


def send_signed(home: str | Path, key, kind: str, body: dict, *, ttl: timedelta = timedelta(hours=24)) -> Path:
    """Sign one founder command and drop it into the body inbox (any interface, then close)."""
    from greg.founder import sign_command
    layout = Layout(home)
    config = json.loads(layout.config.read_text())
    envelope = sign_command(key, kind, body, body_id=config["body_id"], ttl=ttl)
    target = layout.inbox / f"{envelope['issued_at'].replace(':', '')}-{kind.lower()}-{envelope['nonce'][:8]}.json"
    temporary = target.with_suffix(".tmp")
    temporary.write_text(json.dumps(envelope, indent=1))
    temporary.replace(target)
    return target


def inbox_digests(layout: "Layout") -> set[str]:
    """Digests of the signed commands still waiting in the inbox: an answer row citing one is the founder's own
    answer being applied, not an unsigned one."""
    out = set()
    for path in layout.inbox.glob("*.json"):
        try:
            out.add(sha256_json(json.loads(path.read_text())))
        except (OSError, ValueError):
            continue
    return out


def morning_projection(home: str | Path) -> dict:
    """The morning report from a read-only view; works while the body runs."""
    from types import SimpleNamespace
    from greg.missions import MissionBook
    layout = Layout(home)
    try:
        heartbeat = json.loads(layout.heartbeat.read_text())
    except (OSError, ValueError):
        heartbeat = None
    with observe(home, actor="spiffe://uniimente.internal/greg/morning-reader") as journal:
        return tribunal.morning_report(journal, SimpleNamespace(book=MissionBook(journal)), heartbeat=heartbeat,
                                       pending=inbox_digests(layout))


def _attach_waiting(journal, achieved: set) -> list[dict]:
    """Verified capabilities Genesis is waiting for the founder to attach, whatever the ask's answer.

    Ported from #168 (``8531595``). An Approve on a capability ask only records an answer (greg/asks.py);
    attaching is its own signed command. Derived from the ledger, so a mission stays unblockable from the console
    after an answer given there or on the phone (which can never attach)."""
    mission_of = {e.payload["deficit_id"]: e.payload.get("mission_id") for e in journal.replay("deficit.opened")}
    resolved = {e.payload["deficit_id"] for e in journal.replay("deficit.resolved")}
    latest = {}
    for e in journal.replay("capability.state"):
        latest[e.payload["capability_id"]] = e.payload["state"]
    waiting = {}
    for e in journal.replay("deficit.awaiting_attach"):
        p = e.payload
        mission_id = mission_of.get(p["deficit_id"])
        if p["deficit_id"] in resolved or mission_id in achieved or latest.get(p["capability_id"]) in (
                "ATTACHED", "QUARANTINED", "DETACHED"):
            continue
        waiting[(p["deficit_id"], p["capability_id"])] = {"deficit_id": p["deficit_id"],
                                                          "capability_id": p["capability_id"],
                                                          "mission_id": mission_id, "why": p.get("why")}
    return list(waiting.values())


def status(home: str | Path) -> dict:
    """Read-only projection for the founder; safe while the body runs."""
    layout = Layout(home)
    config = json.loads(layout.config.read_text())
    ledger = EvidenceLedger(config["constitution_hash"], str(layout.ledger), read_only=True, tail="ignore") \
        if layout.ledger.exists() else None
    heartbeat = json.loads(layout.heartbeat.read_text()) if layout.heartbeat.exists() else None
    if ledger is None:
        return {"body_id": config["body_id"], "state": "NEVER_STARTED", "heartbeat": heartbeat}
    try:
        spine = EventSpine(ledger)
        journal = Journal(spine, actor="spiffe://uniimente.internal/greg/status-reader")
        registered = {e.payload["mission_id"]: e.payload["spec"] for e in journal.replay("mission.registered")}
        achieved = {e.payload["mission_id"] for e in journal.replay("mission.achieved")}
        from greg.missions import MissionBook
        book = MissionBook(journal)
        requests = asks.open_requests(journal.replay("decision.") + journal.replay("mission.achieved")
                                      + journal.replay("mission.lifecycle"), counted=book.answers,
                                      uncounted=book.unverified, pending=inbox_digests(layout))
        founder = list(founder_keys(journal))     # rotation honored: only the currently enrolled keys
        boots = journal.replay("body.booted")
        # The same states the body uses: catalog initial state, then every recorded transition.
        from greg.cognition.catalog import initial_state
        registry = CapabilityRegistry()
        for manifest, adapter in BUILTINS.values():
            registry.register(manifest, adapter, state=initial_state(manifest.capability_id))
        for event in journal.replay("capability.state"):
            if event.payload["capability_id"] in registry.manifests:
                registry.set_state(event.payload["capability_id"], event.payload["state"])
        ok, chain = ledger.verify_chain()
        from greg.missions import MissionBook, active_constraint
        book = MissionBook(journal)
        paused = body_pauses(journal, pause_file=layout.pause_file.exists())
        missions = [{"mission_id": mid, "intended_effect": spec["intended_effect"],
                     "closure": spec["closure"]["kind"], "achieved": mid in achieved,
                     "active_constraint": active_constraint(book.missions[mid], book, body_paused=paused)
                     if mid in book.missions else None}
                    for mid, spec in registered.items()]
        from greg import goal_gravity
        return {
            "body_id": config["body_id"], "version": config["version"],
            "background": heartbeat, "boots": len(boots),
            "security": {"founder_keys_enrolled": founder, "chain_verified": ok, "chain": chain,
                         "devices": [{k: d[k] for k in ("device_key_id", "label", "kinds", "expires_at")}
                                     for d in device_delegations(journal).values()],
                         "stop_file_present": layout.stop_file.exists(),
                         "pause_file_present": layout.pause_file.exists(),
                         "crash_loop_hold": (crash_loop_hold(journal) or {}).get("why"),
                         "contained_faults": contained_faults(journal, layout)},
            # Missions and persistent goals are different objects: missions under "missions" (and under
            # "goals", the legacy key older phone/Mac clients read), founder-signed Goal Gravity goals under
            # "gravity". Neither key is ambiguous once "keys" is read.
            "missions": missions,
            "goals": missions,
            "keys": {"missions": "founder-signed MISSION commands (one light cone each)",
                     "goals": "legacy alias of 'missions' for older clients; these are missions, not Goal "
                              "Gravity goals",
                     "gravity": "persistent Goal Gravity goals (founder-signed GOAL commands bound to missions)"},
            "gravity": goal_gravity.status_summary(journal),
            "decisions_required": [asks.surface(r) for r in requests],
            "attach_waiting": _attach_waiting(journal, achieved),
            "capabilities": registry.inventory(), "permissions": {"read_roots": config["read_roots"]},
            "compute": compute.sample(layout.home),
            "secret_handles": SecretBroker(layout.secrets).names(),
            "refused_model_keys": __import__("greg.model_keys", fromlist=["summary"]).summary(
                journal, SecretBroker(layout.secrets)),
            "external_items_quarantined": sum(1 for e in journal.replay("external.ingested")
                                              if e.payload["quarantined"]),
            "single_bottleneck_metric": metrics.vepmc(journal),
            "founder_tier": metrics.tier_status(journal, founder),
            "external_anchor": anchor.summary(journal),
            "egress": _egress_summary(layout.home, config),
            "presence": presence.summary(journal, now=utcnow(), since=utcnow() - presence.REVIEW_WINDOW,
                                         heartbeat=heartbeat),
            "designation": [e.payload for e in journal.replay("body.designated")],
            "developmental_position": _path_summary(journal),
            "cognition": {
                "receipts": [{k: e.payload[k] for k in
                    ("receipt_id", "mission_id", "problem_id", "answered", "outcome", "next_step", "claims", "elapsed_ms", "cost_limits")}
                    for e in journal.replay("cognition.receipt")],
                "outcomes": __import__('greg.routing', fromlist=['cognitive_knowledge']).cognitive_knowledge(journal),
                "scope": "conditional computation; no external acceptance or authority",
            },
        }
    finally:
        ledger.close()


def _egress_summary(home: Path, config: dict) -> dict:
    """#26 as the founder sees it: is the network confined, and what has the relay decided (read-only)."""
    if not config.get("confined_egress"):
        return {"confined": False, "why": "this body was created without confined egress (greg init --confined-egress)"}
    from foundry.systems.segmentation import Journal as EgressJournal
    journal = EgressJournal(Path(home) / "egress-journal.jsonl")
    check = journal.verify()                     # a damaged row is reported as a broken chain, never a crash
    rows = [] if check.get("malformed") else journal.read()
    return {"confined": True, "decisions": len(rows), "denied": sum(1 for r in rows if r.get("verdict") == "DENIED"),
            "chain_intact": check["intact"], **({"broken_at": check["broken_at"]} if "broken_at" in check else {}),
            "scope": "every mission-path connection crosses the relay or has no network"}


def _path_summary(journal: Journal) -> dict:
    from greg import path as devpath
    where = devpath.position(journal)
    active = where["active"] or {}
    return {"achieved": where["achieved"], "active": active.get("id"), "title": active.get("title"),
            "gate": active.get("gate"), "measurement": active.get("measurement"),
            "next": (where["next"] or {}).get("id"), "pull_forward_seams": where["pull_forward_seams"],
            "met_ahead": [n["id"] for n in where["met_ahead"]]}


def ingest_external(home: str | Path, *, source: str, content: str, channel: str) -> dict:
    """Local intake of untrusted content (e.g. community replies) while the body is stopped."""
    with Body(home) as body:
        return dataplane.ingest(body.journal, source=source, content=content, channel=channel)
