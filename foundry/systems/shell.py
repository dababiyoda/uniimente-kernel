"""#14 Institutional shell: one scriptable command surface with an audit chain.

Verbs: inspect, propose, simulate, authorize, execute, revoke, reconcile,
fork, promote, regress, terminate. Every verb, accepted or refused, appends a
record to a hash-chained audit log (``verify_audit`` re-derives the chain).

A proposal is a Foundry op (system, op, args). ``simulate`` runs it against a
disposable copy of that system's store and reports the result and the files it
would change; the real store is untouched. A write op executes only after a
founder-signed DECISION (greg/founder.py) naming the proposal's exact hash;
revocation before execution voids it; nonces cannot be replayed. ``reconcile``
compares the store with the digest recorded after execution. ``fork`` takes a
content-addressed snapshot (#21); ``promote`` needs a founder-signed
SOP_RATIFY and commits a versioned object (#3) citing executed proposals as
evidence; ``regress`` rolls it back. ``terminate`` is final: afterwards only
inspect answers.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
from datetime import datetime
from pathlib import Path

from foundry.systems import cas, snapshots, versions


class ShellError(RuntimeError):
    pass


def _canon(value) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def _digest_dir(d: Path) -> str:
    h = hashlib.sha256()
    for p in sorted(Path(d).rglob("*")) if Path(d).exists() else []:
        if p.is_file():
            h.update(str(p.relative_to(d)).encode() + b"\0" + hashlib.sha256(p.read_bytes()).digest())
    return h.hexdigest()


class Shell:
    def __init__(self, root: Path, *, body_id: str, enrolled: dict[str, str]):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.body_id, self.enrolled = body_id, dict(enrolled)
        self._state_path = self.root / "shell.json"
        self._audit_path = self.root / "audit.jsonl"

    # -- state and audit -----------------------------------------------------------
    def _state(self) -> dict:
        if self._state_path.exists():
            return json.loads(self._state_path.read_text())
        return {"proposals": {}, "nonces": [], "terminated": False, "forks": {}}

    def _save(self, state: dict) -> None:
        tmp = self._state_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(state, sort_keys=True, indent=1))
        tmp.replace(self._state_path)

    def _audit(self, verb: str, args: dict, outcome: str, detail) -> None:
        lines = self._audit_path.read_text().splitlines() if self._audit_path.exists() else []
        prev = json.loads(lines[-1])["hash"] if lines else "0" * 64
        record = {"n": len(lines), "verb": verb, "args": args, "outcome": outcome, "detail": detail, "prev": prev}
        record["hash"] = hashlib.sha256(_canon(record)).hexdigest()
        with self._audit_path.open("a") as fh:
            fh.write(json.dumps(record, sort_keys=True) + "\n")

    def audit(self) -> list[dict]:
        return [json.loads(line) for line in self._audit_path.read_text().splitlines()] if self._audit_path.exists() else []

    def verify_audit(self) -> dict:
        prev = "0" * 64
        for i, rec in enumerate(self.audit()):
            body = {k: v for k, v in rec.items() if k != "hash"}
            if rec["n"] != i or rec["prev"] != prev or hashlib.sha256(_canon(body)).hexdigest() != rec["hash"]:
                return {"valid": False, "broken_at": i}
            prev = rec["hash"]
        return {"valid": True, "records": len(self.audit()), "head": prev}

    def command(self, verb: str, **args):
        """The one entry point: dispatch, audit, and never let a refusal go unrecorded."""
        if verb not in VERBS:
            self._audit(verb, args, "refused", "unknown verb")
            raise ShellError(f"unknown verb {verb!r}; verbs are {sorted(VERBS)}")
        if verb != "inspect" and self._state()["terminated"]:
            self._audit(verb, _loggable(args), "refused", "shell terminated")
            raise ShellError("shell terminated; only inspect is available")
        try:
            result = getattr(self, "_" + verb)(**args)
        except Exception as exc:
            self._audit(verb, _loggable(args), "refused", f"{type(exc).__name__}: {exc}")
            raise ShellError(f"{verb} refused: {exc}") from None
        self._audit(verb, _loggable(args), "ok", result)
        return result

    # -- verbs ---------------------------------------------------------------------
    def _inspect(self, proposal: str | None = None):
        state = self._state()
        if proposal:
            return state["proposals"][proposal]
        return {"terminated": state["terminated"], "proposals": {k: v["status"] for k, v in state["proposals"].items()},
                "forks": sorted(state["forks"]), "audit": self.verify_audit()}

    def _propose(self, system: int, op: str, args: dict, reason: str):
        from foundry.systems.linking import _op_class
        consequence = _op_class(int(system), op)
        body = {"system": int(system), "op": op, "args": args, "reason": reason, "consequence": consequence}
        pid = "p-" + hashlib.sha256(_canon(body)).hexdigest()[:16]
        state = self._state()
        if pid in state["proposals"]:
            raise ShellError(f"proposal {pid} already exists")
        state["proposals"][pid] = {**body, "hash": hashlib.sha256(_canon(body)).hexdigest(), "status": "PROPOSED"}
        self._save(state)
        return {"proposal": pid, "consequence": consequence}

    def _store(self, system: int) -> Path:
        return self.root / "stores" / f"system-{int(system):02d}"

    def _run(self, p: dict, store: Path):
        from foundry.systems import module
        mod = module(p["system"])
        op = mod.QUERY_OPS.get(p["op"]) or mod.APPLY_OPS[p["op"]]
        return op(json.loads(json.dumps(p["args"])), store)

    def _simulate(self, proposal: str):
        p = self._state()["proposals"][proposal]
        real = self._store(p["system"])
        with tempfile.TemporaryDirectory() as tmp:
            copy = Path(tmp) / "store"
            if real.exists():
                shutil.copytree(real, copy)
            else:
                copy.mkdir()
            before = {str(f.relative_to(copy)) for f in copy.rglob("*") if f.is_file()}
            result = self._run(p, copy)
            after = {str(f.relative_to(copy)) for f in copy.rglob("*") if f.is_file()}
            changed = snapshots.compare(real, copy) if real.exists() else {"only_b": sorted(after - before)}
        return {"result": result, "would_change": changed, "real_store_unchanged": True}

    def _authorize(self, proposal: str, envelope: dict, now: str):
        from greg.founder import FounderVerifier, instant
        state = self._state()
        p = state["proposals"][proposal]
        if p["status"] != "PROPOSED":
            raise ShellError(f"proposal is {p['status']}, not PROPOSED")
        verifier = FounderVerifier(body_id=self.body_id, enrolled=self.enrolled,
                                   seen_nonce=lambda n: n in state["nonces"])
        env = verifier.verify(envelope, now=instant(now), expected_kind="DECISION")
        if env["body"] != {"proposal": proposal, "proposal_hash": p["hash"], "approve": True}:
            raise ShellError("signed decision does not name this proposal's exact hash")
        state["nonces"].append(env["nonce"])
        p.update(status="AUTHORIZED", authorized_by=env["founder_key_id"], authorized_at=now)
        self._save(state)
        return {"proposal": proposal, "status": "AUTHORIZED"}

    def _execute(self, proposal: str):
        state = self._state()
        p = state["proposals"][proposal]
        if p["consequence"] != "read_only" and p["status"] != "AUTHORIZED":
            raise ShellError(f"{p['consequence']} proposal needs founder authorization (status {p['status']})")
        if p["status"] not in ("PROPOSED", "AUTHORIZED"):
            raise ShellError(f"proposal is {p['status']}")
        store = self._store(p["system"])
        store.mkdir(parents=True, exist_ok=True)
        result = self._run(p, store)
        state = self._state()
        state["proposals"][proposal].update(status="EXECUTED", result=result, store_digest=_digest_dir(store))
        self._save(state)
        return {"proposal": proposal, "status": "EXECUTED", "result": result}

    def _revoke(self, proposal: str, reason: str):
        state = self._state()
        p = state["proposals"][proposal]
        if p["status"] == "EXECUTED":
            raise ShellError("already executed; use reconcile/regress, not revoke")
        p.update(status="REVOKED", revoked_reason=reason)
        self._save(state)
        return {"proposal": proposal, "status": "REVOKED"}

    def _reconcile(self, proposal: str):
        p = self._state()["proposals"][proposal]
        if p["status"] != "EXECUTED":
            raise ShellError("only executed proposals reconcile")
        current = _digest_dir(self._store(p["system"]))
        return {"proposal": proposal, "consistent": current == p["store_digest"],
                "recorded": p["store_digest"][:16], "current": current[:16]}

    def _fork(self, name: str):
        state = self._state()
        if name in state["forks"]:
            raise ShellError(f"fork {name} exists")
        stores = self.root / "stores"
        stores.mkdir(exist_ok=True)
        snap = snapshots.snapshot(stores, self.root / "cas")
        state["forks"][name] = snap
        self._save(state)
        return {"fork": name, "snapshot": snap}

    def _promote(self, name: str, content, evidence: list[str], envelope: dict, now: str):
        from greg.founder import FounderVerifier, instant
        state = self._state()
        executed = {k for k, v in state["proposals"].items() if v["status"] == "EXECUTED"}
        if not evidence or set(evidence) - executed:
            raise ShellError(f"promotion evidence must name executed proposals; not executed: {sorted(set(evidence) - executed)}")
        verifier = FounderVerifier(body_id=self.body_id, enrolled=self.enrolled,
                                   seen_nonce=lambda n: n in state["nonces"])
        env = verifier.verify(envelope, now=instant(now), expected_kind="SOP_RATIFY")
        digest = hashlib.sha256(_canon(content)).hexdigest()
        if env["body"] != {"name": name, "content_hash": digest}:
            raise ShellError("ratification does not name this content")
        state["nonces"].append(env["nonce"])
        self._save(state)
        out = versions.commit(self.root / "promoted", name, content, reason="promoted", evidence=sorted(evidence))
        return {"name": name, "n": out["n"], "address": out["address"]}

    def _regress(self, name: str, to: int, reason: str):
        out = versions.rollback(self.root / "promoted", name, int(to), reason=reason)
        return {"name": name, "n": out["n"], "restores": int(to)}

    def _terminate(self, reason: str):
        state = self._state()
        state["terminated"] = True
        state["terminated_reason"] = reason
        self._save(state)
        return {"terminated": True}


VERBS = ("inspect", "propose", "simulate", "authorize", "execute", "revoke", "reconcile", "fork", "promote",
         "regress", "terminate")


def _loggable(args: dict) -> dict:
    return {k: ({"kind": v.get("kind"), "nonce": v.get("nonce")} if k == "envelope" and isinstance(v, dict) else v)
            for k, v in args.items()}


def _shell(r: Path, a: dict) -> Shell:
    return Shell(r, body_id=a["body_id"], enrolled=a["enrolled"])


QUERY_OPS = {"inspect": lambda a, r: _shell(r, a).command("inspect", proposal=a.get("proposal")),
             "simulate": lambda a, r: _shell(r, a).command("simulate", proposal=a["proposal"]),
             "verify_audit": lambda a, r: _shell(r, a).verify_audit()}
APPLY_OPS = {verb: (lambda v: lambda a, r: _shell(r, a).command(v, **a.get("params", {})))(verb)
             for verb in VERBS if verb not in ("inspect", "simulate")}


def exercise(root) -> dict:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from greg.founder import instant, key_id, public_bytes, sign_command
    now = "2026-09-27T12:00:00Z"
    founder = Ed25519PrivateKey.from_private_bytes(bytes(32 * [7]))
    intruder = Ed25519PrivateKey.from_private_bytes(bytes(32 * [3]))
    f_hex = public_bytes(founder.public_key()).hex()
    sh = Shell(Path(root) / "shell", body_id="body-a", enrolled={key_id(f_hex): f_hex})
    nonce = iter(f"{c}" * 16 for c in "abcdefghijk")
    sign = lambda key, kind, body: sign_command(key, kind, body, body_id="body-a", now=instant(now), nonce=next(nonce))

    refused = {}
    def attempt(label, verb, **kw):
        try:
            sh.command(verb, **kw)
            refused[label] = False
        except ShellError as exc:
            refused[label] = str(exc)

    open_acct = sh.command("propose", system=39, op="open_account", reason="book quotes",
                           args={"account": "revenue:quotes", "type": "revenue", "currency": "USD"})["proposal"]
    sim = sh.command("simulate", proposal=open_acct)
    attempt("execute_unauthorized_write", "execute", proposal=open_acct)
    p = sh.command("inspect", proposal=open_acct)
    attempt("intruder_signature", "authorize", proposal=open_acct, now=now,
            envelope=sign(intruder, "DECISION", {"proposal": open_acct, "proposal_hash": p["hash"], "approve": True}))
    attempt("wrong_hash", "authorize", proposal=open_acct, now=now,
            envelope=sign(founder, "DECISION", {"proposal": open_acct, "proposal_hash": "0" * 64, "approve": True}))
    good = sign(founder, "DECISION", {"proposal": open_acct, "proposal_hash": p["hash"], "approve": True})
    sh.command("authorize", proposal=open_acct, envelope=good, now=now)
    executed = sh.command("execute", proposal=open_acct)
    reconciled = sh.command("reconcile", proposal=open_acct)

    second = sh.command("propose", system=39, op="open_account", reason="book cash",
                        args={"account": "asset:cash", "type": "asset", "currency": "USD"})["proposal"]
    attempt("replayed_nonce", "authorize", proposal=second, envelope=good, now=now)
    sh.command("revoke", proposal=second, reason="founder changed plan")
    attempt("execute_revoked", "execute", proposal=second)

    read = sh.command("propose", system=39, op="trial_balance", reason="check books", args={})["proposal"]
    read_result = sh.command("execute", proposal=read)   # read-only needs no authorization
    fork = sh.command("fork", name="before-policy")

    policy = {"reserve_pct": 0.2}
    attempt("promote_without_evidence", "promote", name="quote-policy", content=policy, evidence=["p-nope"], now=now,
            envelope=sign(founder, "SOP_RATIFY", {"name": "quote-policy", "content_hash": "x"}))
    ratify = lambda c: sign(founder, "SOP_RATIFY", {"name": "quote-policy",
                                                    "content_hash": hashlib.sha256(_canon(c)).hexdigest()})
    v1 = sh.command("promote", name="quote-policy", content=policy, evidence=[open_acct], envelope=ratify(policy), now=now)
    v2 = sh.command("promote", name="quote-policy", content={"reserve_pct": 0.05}, evidence=[open_acct],
                    envelope=ratify({"reserve_pct": 0.05}), now=now)
    regressed = sh.command("regress", name="quote-policy", to=v1["n"], reason="reserve too thin")

    # tampering with the store outside the shell is caught by reconcile
    (sh._store(39) / "intruder.txt").write_text("x")
    drift = sh.command("reconcile", proposal=open_acct)
    sh.command("terminate", reason="exercise complete")
    attempt("after_terminate", "propose", system=39, op="trial_balance", reason="late", args={})
    status = sh.command("inspect")
    return {"simulated_changes": sim["would_change"], "executed": executed["status"], "reconciled": reconciled["consistent"],
            "drift_detected": not drift["consistent"], "trial_balance": read_result["result"],
            "fork_snapshot": fork["snapshot"][:16], "promoted": [v1["n"], v2["n"]], "regressed_to": regressed["n"],
            "refused": refused, "audit": sh.verify_audit(),
            "audit_outcomes": [(r["verb"], r["outcome"]) for r in sh.audit()], "status": status["proposals"]}
