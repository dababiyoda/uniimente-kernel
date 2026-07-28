"""The effector side of the Reality Aperture: independent verification + local veto.

An effector holds a VerificationRegistry (public keys only) and its own local
safety state. It can verify a certificate with no network call to the Kernel,
which is what makes the aperture safe under partition: an effector that cannot
reach the Kernel can still check attribution, and an effector that cannot check
refuses.

Execution requires an AND of independent conditions:

    valid certificate
  AND presenter identity == certificate identity
  AND policy and constitution versions still current
  AND certificate unexpired and unspent
  AND local veto clear
  AND independent readback confirms the effect

Any one of them false means no execution. The local veto is a real veto here:
`LocalVeto.blocks()` is READ before the executor runs. The previous SDK held a
KillSwitch that was only ever written to, so it could not stop anything.
"""
from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Optional

from .certificate import (AuthorizationCertificate, CertificateError,
                          hash_payload, rfc3339)
from .verification import VerificationRegistry


class VerificationRefusal(CertificateError):
    pass


class IdentityMismatch(CertificateError):
    pass


class VersionDrift(CertificateError):
    pass


class Expired(CertificateError):
    pass


class Replay(CertificateError):
    pass


class VetoRefusal(CertificateError):
    pass


class ReadbackMismatch(CertificateError):
    pass


@dataclass
class Presenter:
    """Who is actually presenting the certificate at the aperture.

    Compared field-by-field against the signed certificate. A certificate is
    not a bearer token: holding the bytes is necessary and not sufficient.
    """
    actor_id: str
    organ_id: str
    workload_identity: str


class LocalVeto:
    """Organ-local fail-closed refusal. Starts engaged; never self-clears.

    Deliberately NOT reachable by the Kernel. A veto that requires a network
    call to release or to consult fails OPEN under partition - exactly when it
    is most needed. The organ owns this and the Kernel cannot override it.
    """

    def __init__(self, *, engaged: bool = True, reason: str = "default-closed"):
        self._engaged = bool(engaged)
        self._reason = reason
        self.transitions: list[dict] = []

    @property
    def engaged(self) -> bool:
        return self._engaged

    def blocks(self) -> tuple[bool, str]:
        return self._engaged, self._reason

    def engage(self, reason: str) -> None:
        self._engaged = True
        self._reason = reason
        self.transitions.append({"engaged": True, "reason": reason,
                                 "at": rfc3339(datetime.now(timezone.utc))})

    def release(self, reason: str, *, authorized_by: str) -> None:
        """Release requires a named local operator. Never automatic."""
        if not authorized_by:
            raise VetoRefusal("releasing a local veto requires a named operator",
                              code="veto_release_unattributed")
        self._engaged = False
        self._reason = ""
        self.transitions.append({"engaged": False, "reason": reason,
                                 "authorized_by": authorized_by,
                                 "at": rfc3339(datetime.now(timezone.utc))})


@dataclass
class ExecutionReceipt:
    authority_record_id: str
    request_id: str
    effect_binding_hash: str
    status: str
    observed_state: Any = None
    readback_verified: bool = False
    error: str = ""
    recorded_at: str = field(
        default_factory=lambda: rfc3339(datetime.now(timezone.utc)))


class Aperture:
    """The external consequence boundary for one organ."""

    def __init__(
        self,
        *,
        registry: VerificationRegistry,
        organ_id: str,
        current_policy_version: str,
        current_constitution_version: str,
        veto: Optional[LocalVeto] = None,
        budget: Any = None,
        revocation: Any = None,
    ) -> None:
        self.registry = registry
        self.organ_id = organ_id
        self.current_policy_version = current_policy_version
        self.current_constitution_version = current_constitution_version
        self.veto = veto or LocalVeto(engaged=False, reason="")
        self.budget = budget
        self.revocation = revocation
        self._spent: dict[str, int] = {}
        self.receipts: list[ExecutionReceipt] = []
        self._lease = threading.Lock()
        self.veto_checks: list[str] = []

    # -- verification only: no side effects, safe for auditors -------------
    def verify(self, cert: AuthorizationCertificate,
               presenter: Optional[Presenter] = None,
               *, now: Optional[datetime] = None) -> None:
        """Raise on any problem. Returns None when the certificate is sound."""
        ok = self.registry.verify(cert.key_id, cert.signing_input(),
                                  cert.signature, algorithm=cert.algorithm)
        if not ok:
            raise VerificationRefusal(
                "certificate signature does not verify against the registered "
                f"public key for {cert.key_id!r}", code="bad_signature")

        if cert.is_expired(now):
            raise Expired(f"certificate expired at {cert.expires_at}",
                          code="certificate_expired")

        if cert.policy_version != self.current_policy_version:
            raise VersionDrift(
                f"certificate carries policy {cert.policy_version!r}; the organ is "
                f"running {self.current_policy_version!r}. Re-authorization required.",
                code="policy_version_drift")
        if cert.constitution_version != self.current_constitution_version:
            raise VersionDrift(
                f"certificate carries constitution {cert.constitution_version!r}; "
                f"the organ is running {self.current_constitution_version!r}. "
                "Re-authorization required.", code="constitution_version_drift")

        if presenter is not None:
            if presenter.actor_id != cert.actor_id:
                raise IdentityMismatch(
                    f"certificate authorizes {cert.actor_id!r}; presented by "
                    f"{presenter.actor_id!r}", code="actor_mismatch")
            if presenter.organ_id != cert.organ_id:
                raise IdentityMismatch(
                    f"certificate authorizes organ {cert.organ_id!r}; presented by "
                    f"{presenter.organ_id!r}", code="organ_mismatch")
            if presenter.workload_identity != cert.workload_identity:
                raise IdentityMismatch(
                    f"certificate authorizes workload {cert.workload_identity!r}; "
                    f"presented by {presenter.workload_identity!r}",
                    code="workload_mismatch")

    # -- the AND-gate ------------------------------------------------------
    def execute(
        self,
        cert: AuthorizationCertificate,
        presenter: Presenter,
        *,
        payload: Any,
        executor: Callable[[], Any],
        readback: Callable[[], Any],
        expected_state: Callable[[Any], bool],
        now: Optional[datetime] = None,
    ) -> ExecutionReceipt:
        """One authorized, vetoable, independently verified external effect."""

        def refuse(code: str, msg: str) -> ExecutionReceipt:
            if self.budget is not None:
                self.budget.release(cert.budget_reservation_id)
            r = ExecutionReceipt(
                authority_record_id=cert.authority_record_id,
                request_id=cert.request_id,
                effect_binding_hash=cert.effect_binding_hash(),
                status=code, error=msg)
            self.receipts.append(r)
            return r

        # Veto check 1 of 3: before ANY preparation work is done.
        self.veto_checks.append("before_preparation")
        blocked, why = self.veto.blocks()
        if blocked:
            return refuse("local_veto", f"local veto engaged ({why}) before preparation")

        try:
            self.verify(cert, presenter, now=now)
        except CertificateError as e:
            return refuse(e.code, str(e))

        # Revocation, per the manifest's policy for this consequence class.
        if self.revocation is not None:
            try:
                self.revocation.check(cert, now=now)
            except CertificateError as e:
                return refuse(e.code, str(e))

        # The payload actually handed to the executor must be the one that was
        # authorized. A mutated payload is a different effect.
        if hash_payload(payload) != cert.payload_hash:
            return refuse("payload_mismatch",
                          "payload does not match the authorized payload hash")

        # Use limit, checked before the veto so a replay is named as a replay.
        spent = self._spent.get(cert.authority_record_id, 0)
        if spent >= cert.use_limit:
            return refuse("replay",
                          f"certificate {cert.authority_record_id} already used "
                          f"{spent} of {cert.use_limit} permitted times")

        # Veto check 2 of 3: after preparation, before commit.
        self.veto_checks.append("after_preparation_before_commit")
        blocked, why = self.veto.blocks()
        if blocked:
            return refuse("local_veto",
                          f"local veto engaged ({why}); valid constitutional "
                          "authority does not override an organ's refusal")

        # EXECUTION LEASE. The smallest enforceable critical section: the final
        # veto read and the adapter invocation happen under one lock, so the
        # veto cannot flip between the last check and the effect.
        #
        # Residual race, stated rather than hidden: an operator engaging the
        # veto DURING the executor call cannot retract an effect already in
        # flight. Nothing in software can. The lease bounds the window to the
        # duration of a single adapter invocation and no wider.
        with self._lease:
            # Veto check 3 of 3: immediately before adapter invocation.
            self.veto_checks.append("immediately_before_adapter")
            blocked, why = self.veto.blocks()
            if blocked:
                return refuse("local_veto",
                              f"local veto engaged ({why}) inside the execution "
                              "lease; no adapter was invoked")

            self._spent[cert.authority_record_id] = spent + 1
            try:
                executor()
            except Exception as e:  # noqa: BLE001
                return refuse("executor_failed",
                              f"executor raised {type(e).__name__}: {e}")
            except BaseException as e:  # noqa: BLE001
                # Shutdown during commit (KeyboardInterrupt, SystemExit).
                # `except Exception` does not catch these, and an uncaught one
                # would leave the budget reserved and no receipt written - the
                # institution would have spent authority with no record of it.
                # Unwind and record, then RE-RAISE: a shutdown must still
                # shut down. Swallowing it would be worse than the leak.
                refuse("shutdown_during_commit",
                       f"shutdown during commit: {type(e).__name__}: {e}")
                raise

        # Independent readback. The executor's own claim is not evidence.
        observed = readback()
        verified = bool(expected_state(observed))
        if not verified:
            r = ExecutionReceipt(
                authority_record_id=cert.authority_record_id,
                request_id=cert.request_id,
                effect_binding_hash=cert.effect_binding_hash(),
                status="reconciliation_mismatch", observed_state=observed,
                readback_verified=False,
                error="independent readback does not match the authorized effect")
            self.receipts.append(r)
            if self.budget is not None:
                self.budget.release(cert.budget_reservation_id)
            return r

        if self.budget is not None:
            self.budget.commit(cert.budget_reservation_id)
        r = ExecutionReceipt(
            authority_record_id=cert.authority_record_id,
            request_id=cert.request_id,
            effect_binding_hash=cert.effect_binding_hash(),
            status="committed", observed_state=observed, readback_verified=True)
        self.receipts.append(r)
        return r
