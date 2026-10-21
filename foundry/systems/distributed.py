"""#23 Distributed-systems controls: idempotency, retries, compensation, reconciliation.

``Operation`` runs a multi-step saga against unreliable providers:

* every external step carries a stable idempotency key derived from the saga
  and step, so a retry can never create a second effect;
* retries use bounded exponential backoff and honour retry-after;
* an unknown outcome (timeout after the effect may have happened) is resolved
  by reconciling against the provider's record, never by guessing;
* if a later step fails permanently, completed steps are compensated in reverse;
* progress is journaled, so after process death the saga resumes where it was.

Proven against #20's emulator: the naive client double-charges on
timeout -> partial write; this one charges exactly once.
"""
from __future__ import annotations

import json
from pathlib import Path

from foundry.systems.emulator import ProviderEmulator, ProviderError, ProviderTimeout


class SagaError(RuntimeError):
    pass


class Journal:
    def __init__(self, path: Path | None):
        self.path, self.rows = path, []
        if path and Path(path).exists():
            self.rows = [json.loads(l) for l in Path(path).read_text().splitlines()]

    def write(self, row: dict) -> None:
        self.rows.append(row)
        if self.path:
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
            with open(self.path, "a") as fh:
                fh.write(json.dumps(row, sort_keys=True) + "\n")

    def done(self, step: str) -> dict | None:
        return next((r for r in self.rows if r.get("step") == step and r.get("status") == "done"), None)


def with_retries(call, *, attempts: int = 5, base_delay: float = 0.5, sleeps: list | None = None):
    """Bounded exponential backoff; honours retry-after; returns (result, tries) or raises the last error."""
    last = None
    for attempt in range(attempts):
        try:
            return call(), attempt + 1
        except ProviderError as exc:
            if exc.status < 500 and exc.status != 429:
                raise
            last = exc
            delay = max(exc.retry_after, base_delay * 2 ** attempt)
        except ProviderTimeout as exc:
            last = exc
            delay = base_delay * 2 ** attempt
        if sleeps is not None:
            sleeps.append(delay)
    raise last


def run_saga(saga_id: str, steps: list[dict], provider: ProviderEmulator, journal: Journal,
             *, crash_after: int | None = None) -> dict:
    """steps: [{name, amount}] charged in order; on permanent failure, refund completed steps."""
    completed = []
    for index, step in enumerate(steps):
        name, key = step["name"], f"{saga_id}:{step['name']}"
        prior = journal.done(name)
        if prior:
            completed.append(prior)
            continue
        if crash_after is not None and index >= crash_after:
            raise SystemExit("simulated process death")
        try:
            result, tries = with_retries(lambda: provider.charge(key, step["amount"]))
        except ProviderTimeout:
            found = provider._by_key.get(key) if provider.honours_idempotency else None  # reconcile with provider record
            if not found:
                return _compensate(saga_id, completed, provider, journal, reason=f"{name}: outcome unknown, not found")
            result, tries = {"charge": found, "amount": step["amount"]}, None
        except ProviderError as exc:
            return _compensate(saga_id, completed, provider, journal, reason=f"{name}: {exc}")
        row = {"saga": saga_id, "step": name, "status": "done", "charge": result["charge"], "tries": tries}
        journal.write(row)
        completed.append(row)
    return {"status": "completed", "steps": [r["step"] for r in completed]}


def _compensate(saga_id, completed, provider, journal, *, reason):
    for row in reversed(completed):
        provider.refund(row["charge"])
        journal.write({"saga": saga_id, "step": row["step"], "status": "compensated"})
    return {"status": "compensated", "reason": reason, "undone": [r["step"] for r in reversed(completed)]}


QUERY_OPS = {"retry_schedule": lambda a, r: _schedule(a)}
APPLY_OPS: dict = {}


def _schedule(args):
    sleeps: list = []
    script = args.get("script", ["server_error", "rate_limited", "ok"])
    provider = ProviderEmulator(script)
    try:
        with_retries(lambda: provider.charge("k", 1), sleeps=sleeps)
        ok = True
    except Exception:
        ok = False
    return {"succeeded": ok, "sleeps": sleeps}


def exercise(root) -> dict:
    root = Path(root)
    # 1. exactly-once despite timeout -> partial write
    p1 = ProviderEmulator(["timeout", "partial_write", "ok"])
    r1 = run_saga("inv-7", [{"name": "charge", "amount": 900}], p1, Journal(root / "j1.jsonl"))
    # 2. process death mid-saga, then resume from the journal
    p2 = ProviderEmulator()
    try:
        run_saga("order-9", [{"name": "deposit", "amount": 100}, {"name": "balance", "amount": 400}], p2,
                 Journal(root / "j2.jsonl"), crash_after=1)
    except SystemExit:
        pass
    r2 = run_saga("order-9", [{"name": "deposit", "amount": 100}, {"name": "balance", "amount": 400}], p2,
                  Journal(root / "j2.jsonl"))
    # 3. permanent failure on step 2 compensates step 1
    p3 = ProviderEmulator(["ok"] + ["server_error"] * 5)
    r3 = run_saga("order-10", [{"name": "deposit", "amount": 100}, {"name": "balance", "amount": 400}], p3,
                  Journal(root / "j3.jsonl"))
    return {"exactly_once": p1.truth()["charges"] == 1 and r1["status"] == "completed",
            "resumed_without_duplicate": r2["status"] == "completed" and p2.truth()["charges"] == 2,
            "compensated": r3["status"] == "compensated" and p3.truth()["net_amount"] == 0,
            "retry_schedule": _schedule({})["sleeps"]}
