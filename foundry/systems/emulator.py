"""#20 Emulators: external providers and their failures, reproduced deterministically.

A provider emulator serves a declared API from a script of behaviors keyed by
call number: ``ok``, ``timeout``, ``rate_limited`` (with retry-after),
``server_error``, ``partial_write`` (effect applied, response lost) and
``duplicate_delivery``. The same script always yields the same run, so a costly
or dangerous outage becomes a cheap regression test. The emulator keeps the
provider's true side-effect log, so a client can be judged on what it actually
caused, not on what it believed.
"""
from __future__ import annotations

FAULTS = ("ok", "timeout", "rate_limited", "server_error", "partial_write", "duplicate_delivery")


class ProviderTimeout(RuntimeError):
    pass


class ProviderError(RuntimeError):
    def __init__(self, status: int, retry_after: float = 0.0):
        super().__init__(f"provider returned {status}")
        self.status, self.retry_after = status, retry_after


class ProviderEmulator:
    """A payments-style provider: POST /charge {idempotency_key, amount} -> charge id."""

    def __init__(self, script: list[str] | None = None, *, honours_idempotency: bool = True):
        for fault in script or []:
            if fault not in FAULTS:
                raise ValueError(f"unknown fault {fault!r}")
        self.script, self.calls, self.effects = list(script or []), 0, []
        self.honours_idempotency = honours_idempotency
        self._by_key: dict[str, str] = {}

    def _effect(self, key: str, amount: int) -> str:
        if self.honours_idempotency and key in self._by_key:
            return self._by_key[key]
        charge = f"ch_{len(self.effects) + 1}"
        self.effects.append({"charge": charge, "key": key, "amount": amount})
        self._by_key[key] = charge
        return charge

    def charge(self, idempotency_key: str, amount: int) -> dict:
        fault = self.script[self.calls] if self.calls < len(self.script) else "ok"
        self.calls += 1
        if fault == "timeout":
            raise ProviderTimeout("no response")
        if fault == "rate_limited":
            raise ProviderError(429, retry_after=2.0)
        if fault == "server_error":
            raise ProviderError(500)
        charge = self._effect(idempotency_key, amount)
        if fault == "partial_write":
            raise ProviderTimeout("effect applied, response lost")
        if fault == "duplicate_delivery":
            self._effect(idempotency_key, amount)
        return {"charge": charge, "amount": amount}

    def refund(self, charge: str) -> dict:
        self.effects.append({"refund": charge})
        return {"refunded": charge}

    def truth(self) -> dict:
        charged = [e for e in self.effects if "charge" in e]
        refunded = {e["refund"] for e in self.effects if "refund" in e}
        return {"charges": len(charged), "net_amount": sum(e["amount"] for e in charged if e["charge"] not in refunded),
                "refunds": len(refunded)}


def naive_client(provider: ProviderEmulator, key: str, amount: int, attempts: int = 4) -> dict:
    """What an unprotected integration does: retry with a fresh request id each time."""
    for attempt in range(attempts):
        try:
            return provider.charge(f"{key}-attempt-{attempt}", amount)
        except (ProviderTimeout, ProviderError):
            continue
    return {"failed": True}


QUERY_OPS = {"replay": lambda a, r: _replay(a)}
APPLY_OPS: dict = {}


def _replay(args: dict) -> dict:
    provider = ProviderEmulator(args.get("script", []), honours_idempotency=args.get("honours_idempotency", True))
    naive_client(provider, args.get("key", "k"), int(args.get("amount", 100)))
    return {"calls": provider.calls, "truth": provider.truth()}


def exercise(root) -> dict:
    script = ["timeout", "partial_write", "ok"]
    a, b = ProviderEmulator(script), ProviderEmulator(script)
    naive_client(a, "invoice-7", 900)
    naive_client(b, "invoice-7", 900)
    try:
        ProviderEmulator(["meteor"])
        unknown_refused = False
    except ValueError:
        unknown_refused = True
    return {"deterministic": a.effects == b.effects and a.calls == b.calls,
            "naive_client_double_charged": a.truth()["charges"] == 2, "naive_truth": a.truth(),
            "unknown_fault_refused": unknown_refused}
