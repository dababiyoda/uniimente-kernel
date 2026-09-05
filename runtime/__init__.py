"""The institution as something that boots, remembers, and can be stopped.

The Infinite Goal Chase recompute (2026-08-23) named this the Alpha bottleneck,
and named it precisely:

    The bottleneck is not "build persistence". It is "compose a durable runtime
    that uses the persistence that exists." Every entry point still constructs a
    fresh in-memory `EvidenceLedger("sha256:" + "0" * 64)`. Nothing boots the
    institution from a state directory.

Under that constraint a standing mandate had nothing to stand in, a cockpit
would command a body that forgets between commands, and a reasoning organ's
output would not accumulate into anything. All three are downstream of one
missing composition, which is this module.

## What boot restores, and what it deliberately does not

This is the load-bearing distinction, and it is not a detail of implementation:

    evidence      RESTORED   the chain, the witnesses, the causal record, the
                             idempotent inbox, the outstanding outbox
    identity      RE-ISSUED  passports are short-lived by construction
                             (`PassportRegistry` caps TTL at one hour)

Restoring a passport across a restart would resurrect an identity past the
lifetime the institution gave it, using a process boundary as a way to extend an
authority that was meant to expire. So `boot` deliberately starts with an empty
`PassportRegistry`: whoever wants to act after a restart presents identity
again. Memory persists; permission does not.

That asymmetry is the whole point. A body that remembers everything it did and
must re-establish who it is on every boot is the shape the founder's ruling
asks for — `capability may recursively expand; authority may not`.

## Fail-closed boot

`boot` refuses in three situations rather than starting a degraded institution:

  * the state directory's chain does not verify (`EvidenceLedger` re-verifies
    every link on load, and raises rather than trusting the file);
  * the chain was written under a different constitution and no transition
    record explains the move (`ConstitutionMismatch`);
  * the live constitution does not match the authorised baseline replayed by
    `governance.integrity` — a silent constitutional edit.

The third has no opt-out argument, on purpose. A `verify_constitution=False`
would be exactly the "founder exception because the check is inconvenient"
mechanism the ruling prohibits. The lawful way past it is the one already
exercised in this repository: record the amendment.

## What this is not

It is not a scheduler, a daemon, a server, or a network listener. It opens no
socket and reaches nothing outside the state directory. `run` is the existing
`ConsequenceGate.run`, unchanged and still the sole path to external effect.
This module composes; it does not grant.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field

__all__ = ["InstitutionalRuntime", "BootReport", "BootRefused"]

LEDGER_FILENAME = "ledger.jsonl"


class BootRefused(RuntimeError):
    """The institution declined to start on the state it was given."""


@dataclass(frozen=True)
class BootReport:
    """What the boot found, recorded so a restart is itself institutional memory."""

    state_dir: str
    constitution_hash: str
    #: False on a fresh state directory, True when an existing chain was resumed.
    resumed: bool
    ledger_records: int
    chain_verified: bool
    chain_detail: str
    events_replayed: int
    #: Event ids the idempotent inbox already knows — replay protection depth.
    inbox_depth: int
    #: Deliveries the ledger says are staged and not yet flushed.
    outbox_depth: int
    constitution_verdict: str
    #: Identities are re-issued, never restored. Always 0 at boot.
    identities_restored: int = 0
    findings: tuple[str, ...] = field(default_factory=tuple)

    def summary(self) -> str:
        state = "resumed" if self.resumed else "fresh"
        return (f"{state} from {self.state_dir}: {self.ledger_records} records, "
                f"{self.events_replayed} events, inbox {self.inbox_depth}, "
                f"outbox {self.outbox_depth}, constitution {self.constitution_verdict}")


class InstitutionalRuntime:
    """One composed body: durable ledger, gate, spine and causal memory."""

    def __init__(self, *, state_dir: str, compiled, passports, ledger, signer,
                 gate, spine, memory, report: BootReport):
        self.state_dir = state_dir
        self.compiled = compiled
        self.passports = passports
        self.ledger = ledger
        self.signer = signer
        self.gate = gate
        self.spine = spine
        self.memory = memory
        self.report = report

    # ------------------------------------------------------------------ boot
    @classmethod
    def boot(cls, state_dir, *, env: str = "development") -> "InstitutionalRuntime":
        """Compose the institution over a durable state directory.

        Idempotent across processes: booting twice against the same directory
        resumes the same chain rather than starting a second one.
        """
        from compiler.ucl_compiler import compile_constitution
        from events.spine import EventSpine
        from governance import integrity
        from identity.machine_passport import PassportRegistry
        from memory.causal import CausalMemory
        from policy.consequence_gate import ConsequenceGate
        from provenance.commit_witness import WitnessSigner
        from provenance.ledger import ConstitutionMismatch, EvidenceLedger

        state_dir = os.fspath(state_dir)
        os.makedirs(state_dir, exist_ok=True)
        path = os.path.join(state_dir, LEDGER_FILENAME)
        resumed = os.path.exists(path)

        # 1. The live constitution must be where the founder authorised it.
        #    Checked BEFORE the ledger opens: booting far enough to append a
        #    record under silently-edited law is already too far.
        report = integrity.verify()
        if not report.intact:
            raise BootRefused(
                "refusing to boot on a constitution that does not match the "
                "authorised baseline: "
                + "; ".join(f"{s.artifact} {s.verdict.value}" for s in report.findings)
                + ". Record the amendment in governance.integrity.AMENDMENTS, "
                  "citing the founder decision that authorises it.")

        compiled = compile_constitution(integrity.KERNEL_ROOT)

        # 2. The chain. Refuses a corrupted chain, and (since 2026-08-24) a
        #    chain written under different law.
        try:
            ledger = EvidenceLedger(compiled.constitution_hash, path=path)
        except ConstitutionMismatch as exc:
            raise BootRefused(str(exc)) from exc
        except ValueError as exc:                      # chain failed re-verification
            raise BootRefused(f"state directory {state_dir} is not trustworthy: {exc}") from exc

        chain_ok, chain_detail = ledger.verify_chain()
        if not chain_ok:                                # defence in depth
            raise BootRefused(f"chain verification failed after load: {chain_detail}")

        # 3. Views over the chain. Each rebuilds; none is trusted from memory.
        spine = EventSpine(ledger)
        memory = CausalMemory(ledger)

        # 4. Identity is re-issued, not restored. See the module docstring.
        passports = PassportRegistry()

        signer = WitnessSigner(env=env)
        gate = ConsequenceGate(compiled=compiled, passports=passports,
                               ledger=ledger, signer=signer)

        boot_report = BootReport(
            state_dir=state_dir,
            constitution_hash=compiled.constitution_hash,
            resumed=resumed,
            ledger_records=len(ledger.records),
            chain_verified=chain_ok,
            chain_detail=chain_detail,
            events_replayed=len(spine.replay()),
            inbox_depth=len(spine._seen_ids),
            outbox_depth=len(spine._outbox),
            constitution_verdict=report.headline,
        )

        # 5. The boot itself becomes a fact in the chain it just verified, so a
        #    restart is auditable rather than invisible between two records.
        ledger.append("event", {
            "type": "runtime.booted",
            "resumed": resumed,
            "records_at_boot": boot_report.ledger_records,
            "inbox_depth": boot_report.inbox_depth,
            "outbox_depth": boot_report.outbox_depth,
            "constitution_hash": compiled.constitution_hash,
            "constitution_verdict": report.headline,
            "identities_restored": 0,
        })

        return cls(state_dir=state_dir, compiled=compiled, passports=passports,
                   ledger=ledger, signer=signer, gate=gate, spine=spine,
                   memory=memory, report=boot_report)

    def compose_cathedral_metabolism(
        self,
        *,
        cognition=None,
        router=None,
        compiler=None,
        source_identity=None,
    ):
        """Bind mission metabolism to this runtime's canonical EventSpine.

        Composition is explicit and dependency-injected. It does not select a
        permanent runtime implementation, start a scheduler, restore identity,
        issue a grant, or authorize a consequence.
        """
        from egregore.cathedral_runtime import (
            CathedralMetabolismRuntime,
            SOURCE_IDENTITY,
        )

        return CathedralMetabolismRuntime.from_institutional_runtime(
            self,
            cognition=cognition,
            router=router,
            compiler=compiler,
            source_identity=source_identity or SOURCE_IDENTITY,
        )

    # -------------------------------------------------------------- lifecycle
    @property
    def outstanding_deliveries(self):
        """External-bound events the ledger says are staged and unsettled."""
        return list(self.spine._outbox)

    def shutdown(self, *, sealed_by: str, reason: str):
        """Seal the head so the chain records where this process stopped.

        Not a kill switch and not a revocation — it is the closing bracket that
        makes the next boot's resume point explicit.
        """
        return self.ledger.seal(sealed_by=sealed_by, reason=reason)
