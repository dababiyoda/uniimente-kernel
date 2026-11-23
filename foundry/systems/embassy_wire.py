"""#29 Embassy wire protocol: foreign agents discover, negotiate and perform bounded work over the wire; results are
verified before acceptance; the interior is unreachable.

The embassy core (embassy/gate.py: minimum-privilege guest passports, every request re-expressed as a Proposal
through the Consequence Gate) was in-process only. This puts it on a wire, A2A-shaped and loopback-bound:

  card       the embassy's own Agent Card at /.well-known/agent.json, served by the #31 site (versioned, Merkle-
             rooted, signed), lists the bounded work kinds it accepts, each with its acceptance method and price
             ceiling, and the protocol rules below
  admission  challenge-response, never a static message: a foreign agent presents its self-signed Agent Card,
             receives a fresh single-use nonce bound to its key, and signs {nonce, audience, card hash}. The
             PumpStation wallet-connect lesson (one fixed message, `ethers.verifyMessage(CONNECT_MESSAGE, sig)`)
             is a replayable credential; here a captured signature is worthless after one use, at another embassy,
             or after the nonce expires. Admission issues the core's guest passport: zero budget, internal_write
             ceiling, bounded TTL
  requests   every later JSON-RPC call is signed by the foreign key over {audience, method, params, passport, seq}
             with a strictly increasing sequence; replayed, forged or unsigned calls are refused before any state
             is read. There is no bearer token to steal
  negotiate  tasks/list shows open work; tasks/claim at a price above the ceiling is countered at the ceiling, and
             a claim at or under it is accepted — the claim itself is routed through the core embassy and the gate
             as a bounded internal write under a single-use grant
  verify     tasks/submit is accepted only after verification: a deterministic invariant that is cheaper than the
             work (factors multiply back and are prime; a sort is a non-decreasing permutation) or two independent
             scripted models that agree with the result. A rejected result is an evidenced failure on the agent's
             record (#41) and suspends further claims; models that disagree with each other make the task
             undecidable, which is not the agent's fault and earns no verdict. Accepted work yields a receipt
             signed by the embassy and a payable booked in #39; paying it out is an operator act on #38
  interior   the wire knows seven methods; anything else is -32601. No ledger, Foundry op, store or capability is
             reachable, and the server binds loopback only

The wire is JSON-RPC 2.0 over HTTP with A2A-style method names and cards; it is not a claim of A2A conformance.
"""
from __future__ import annotations

import hashlib
import http.server
import json
import math
import threading
import urllib.error
import urllib.request
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

from embassy.gate import GUEST_CEILING, AgentEmbassy, EmbassyRefused
from foundry.systems import accounting, reputation
from foundry.systems.webserver import Site
from provenance.digests import compact_json_bytes as _canon, sha256_json as _sha

CARD_PATH = "/.well-known/agent.json"
NONCE_TTL = timedelta(seconds=120)
CARD_FIELDS = {"name", "url", "version", "skills", "signing_key"}
METHODS = ("embassy/challenge", "embassy/present", "tasks/list", "tasks/claim", "tasks/submit", "tasks/get", "embassy/standing")
WORK = {"factor": {"acceptance": "deterministic_invariant", "describe": "prime factors of n; verified by multiplying back and primality"},
        "sort": {"acceptance": "deterministic_invariant", "describe": "sorted items; verified as a non-decreasing permutation"},
        "classify": {"acceptance": "independent_model", "describe": "a label; accepted only when two independent models agree"}}


class RpcError(Exception):
    def __init__(self, code: int, message: str):
        super().__init__(message)
        self.code, self.message = code, message


def _t(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def _stamp(d: datetime) -> str:
    return d.strftime("%Y-%m-%dT%H:%M:%SZ")


def _verify(public_hex: str, signature_hex: str, body) -> bool:
    try:
        Ed25519PublicKey.from_public_bytes(bytes.fromhex(public_hex)).verify(bytes.fromhex(signature_hex), _canon(body))
        return True
    except (InvalidSignature, ValueError, TypeError):
        return False


def _is_prime(n: int) -> bool:
    if n < 2:
        return False
    return all(n % d for d in range(2, int(math.isqrt(n)) + 1))


def _model_a(text: str) -> str:
    return "risk" if any(w in text.lower() for w in ("breach", "fraud", "lawsuit", "outage")) else "routine"


def _model_b(text: str) -> str:
    score = sum(text.lower().count(w) for w in ("breach", "fraud", "lawsuit", "outage", "incident"))
    return "risk" if score >= 1 else "routine"


def verify_result(kind: str, inputs: dict, result: dict) -> dict:
    """Acceptance check for a submitted result: cheaper than the work, or two independent models."""
    if kind == "factor":
        f = result.get("factors")
        ok = (isinstance(f, list) and f and all(isinstance(x, int) and x > 1 for x in f) and f == sorted(f)
              and math.prod(f) == inputs["n"] and all(_is_prime(x) for x in f))
        return {"verdict": "VERIFIED" if ok else "REFUTED", "method": "deterministic_invariant", "why": "product and primality"}
    if kind == "sort":
        s = result.get("sorted")
        ok = isinstance(s, list) and Counter(s) == Counter(inputs["items"]) and all(a <= b for a, b in zip(s, s[1:]))
        return {"verdict": "VERIFIED" if ok else "REFUTED", "method": "deterministic_invariant", "why": "non-decreasing permutation"}
    if kind == "classify":
        a, b = _model_a(inputs["text"]), _model_b(inputs["text"])
        if a != b:
            return {"verdict": "UNDECIDABLE", "method": "independent_model", "why": f"models disagree ({a} vs {b})"}
        return {"verdict": "VERIFIED" if result.get("label") == a else "REFUTED", "method": "independent_model", "why": "two models agree"}
    raise RpcError(-32602, f"unknown work kind {kind!r}")


class Embassy:
    def __init__(self, root: Path, *, embassy_id: str, key_seed: bytes, clock, base_url: str = "https://embassy.invalid"):
        from foundry.systems.kernel_stack import gate_stack
        from greg.founder import public_bytes
        self.root, self.embassy_id, self.clock, self.base_url = Path(root), embassy_id, clock, base_url
        self.root.mkdir(parents=True, exist_ok=True)
        self.key = Ed25519PrivateKey.from_private_bytes(key_seed)
        self.public_key = public_bytes(self.key.public_key()).hex()
        self.gate, self.passports, self.ledger = gate_stack(self.root / "ledger.jsonl")
        self.core = AgentEmbassy(self.passports, self.gate, self.ledger)
        self.site = Site(self.root / "site", key_seed=key_seed)
        self.books = self.root / "books"
        accounting.open_account(self.books, "expense:bounded_work", "expense", "USD")
        accounting.open_account(self.books, "payable:foreign_agents", "liability", "USD")

    def _state(self) -> dict:
        p = self.root / "embassy.json"
        return json.loads(p.read_text()) if p.exists() else {"nonces": {}, "guests": {}, "tasks": {}, "records": [], "receipts": []}

    def _save(self, s: dict) -> None:
        (self.root / "embassy.tmp").write_text(json.dumps(s, sort_keys=True))
        (self.root / "embassy.tmp").replace(self.root / "embassy.json")

    # -- operator side -------------------------------------------------------------------------
    def publish_card(self, *, version: str) -> dict:
        card = {"name": self.embassy_id, "description": "UNIIMENTE embassy: bounded work for foreign agents, verified before acceptance",
                "url": f"{self.base_url}/rpc", "version": version, "provider": {"organization": "uniimente-kernel"},
                "capabilities": {"streaming": False, "pushNotifications": False},
                "skills": [{"id": k, "name": k, "description": v["describe"], "tags": ["bounded-work", v["acceptance"]]} for k, v in WORK.items()],
                "x-uniimente": {"signing_key": self.public_key, "protocol": {"rpc": "/rpc", "methods": list(METHODS),
                                "admission": "embassy/challenge then embassy/present: single-use nonce bound to the agent key and this audience",
                                "requests": "Ed25519 over {audience, method, params, passport, seq}; seq strictly increasing; no bearer tokens",
                                "guest_ceiling": GUEST_CEILING, "guest_budget_usd": 0.0, "interior_access": False},
                                "acceptance": {k: v["acceptance"] for k, v in WORK.items()}}}
        return self.site.publish(CARD_PATH, _canon(card), reason=f"embassy card v{version}", evidence=[f"methods:{len(METHODS)}"])

    def post_task(self, task_id: str, *, kind: str, inputs: dict, ceiling_cents: int) -> dict:
        if kind not in WORK:
            raise RpcError(-32602, f"unknown work kind {kind!r}")
        s = self._state()
        if task_id in s["tasks"]:
            raise RpcError(-32602, f"task {task_id} exists")
        s["tasks"][task_id] = {"task_id": task_id, "kind": kind, "inputs": inputs, "ceiling_cents": ceiling_cents, "status": "open",
                               "claimed_by": None, "price_cents": None, "result_sha256": None, "verification": None}
        self._save(s)
        return {"task_id": task_id, "status": "open"}

    def standing(self) -> dict:
        return reputation.score(self._state()["records"], now=self.clock())

    # -- wire ----------------------------------------------------------------------------------
    def rpc(self, request: dict) -> dict:
        rid = request.get("id") if isinstance(request, dict) else None
        try:
            if not isinstance(request, dict) or request.get("jsonrpc") != "2.0" or not isinstance(request.get("method"), str):
                raise RpcError(-32600, "invalid JSON-RPC 2.0 request")
            method, params = request["method"], request.get("params") or {}
            if method not in METHODS:
                raise RpcError(-32601, f"method not found: {method!r}; the embassy exposes {list(METHODS)} and nothing interior")
            if method == "embassy/challenge":
                result = self._challenge(params)
            elif method == "embassy/present":
                result = self._present(params)
            else:
                guest = self._authenticate(method, params)
                result = {"tasks/list": self._list, "tasks/claim": self._claim, "tasks/submit": self._submit,
                          "tasks/get": self._get, "embassy/standing": lambda g, p: self.standing()}[method](guest, params)
            return {"jsonrpc": "2.0", "id": rid, "result": result}
        except RpcError as exc:
            return {"jsonrpc": "2.0", "id": rid, "error": {"code": exc.code, "message": exc.message}}
        except EmbassyRefused as exc:
            return {"jsonrpc": "2.0", "id": rid, "error": {"code": -32001, "message": f"embassy refused: {exc}"}}

    def _challenge(self, params: dict) -> dict:
        card, signature = params.get("card"), params.get("signature")
        if not isinstance(card, dict) or set(card) != CARD_FIELDS:
            raise RpcError(-32602, f"an Agent Card has exactly the fields {sorted(CARD_FIELDS)}")
        if not _verify(card["signing_key"], str(signature), card):
            raise RpcError(-32001, "the card is not signed by the key it names")
        s = self._state()
        now = _t(self.clock())
        nonce = hashlib.sha256(_canon([card["signing_key"], len(s["nonces"]), self.public_key])).hexdigest()[:32]
        s["nonces"][nonce] = {"key": card["signing_key"], "card_sha256": _sha(card), "name": card["name"],
                              "expires_at": _stamp(now + NONCE_TTL), "used": False}
        self._save(s)
        return {"nonce": nonce, "audience": self.embassy_id, "expires_at": s["nonces"][nonce]["expires_at"],
                "sign": "Ed25519 over {audience, card_sha256, nonce}"}

    def _present(self, params: dict) -> dict:
        s = self._state()
        n = s["nonces"].get(str(params.get("nonce")))
        if n is None:
            raise RpcError(-32001, "unknown nonce; ask for a challenge first")
        if n["used"]:
            raise RpcError(-32001, "nonce already used; a presentation is not replayable")
        if _t(self.clock()) > _t(n["expires_at"]):
            raise RpcError(-32001, f"nonce expired at {n['expires_at']}")
        body = {"audience": self.embassy_id, "card_sha256": n["card_sha256"], "nonce": params.get("nonce")}
        if not _verify(n["key"], str(params.get("signature")), body):
            raise RpcError(-32001, "presentation signature does not verify for this audience, card and nonce")
        n["used"] = True
        passport = self.core.present(foreign_id=f"a2a://{n['name']}", origin="a2a", declared_capabilities=["embassy.task"],
                                     requested_ttl_s=int(params.get("ttl_s") or 1800))
        s["guests"][passport.passport_id] = {"agent": n["name"], "key": n["key"], "seq": 0, "suspended": None}
        self._save(s)
        return {"passport_id": passport.passport_id, "expires_at": passport.expires_at, "ceiling": GUEST_CEILING, "budget_usd": 0.0,
                "requests": "sign {audience, method, params, passport_id, seq} with your card key; seq must increase"}

    def _authenticate(self, method: str, params: dict) -> dict:
        auth = params.get("auth")
        if not isinstance(auth, dict):
            raise RpcError(-32001, "unsigned request; every call after admission is signed by the agent's key")
        s = self._state()
        guest = s["guests"].get(str(auth.get("passport_id")))
        if guest is None:
            raise RpcError(-32001, "unknown passport")
        valid, why = self.passports.verify(auth["passport_id"])
        if not valid:
            raise RpcError(-32001, f"passport {why}")
        seq = auth.get("seq")
        if not isinstance(seq, int) or seq <= guest["seq"]:
            raise RpcError(-32001, f"sequence {seq!r} is not after {guest['seq']}; replay refused")
        body = {"audience": self.embassy_id, "method": method, "params": {k: v for k, v in params.items() if k != "auth"},
                "passport_id": auth["passport_id"], "seq": seq}
        if not _verify(guest["key"], str(auth.get("signature")), body):
            raise RpcError(-32001, "request signature does not verify against the admitted key")
        guest["seq"] = seq
        self._save(s)
        return {"passport_id": auth["passport_id"], **guest}

    def _list(self, guest: dict, params: dict) -> dict:
        return {"tasks": [{"task_id": t["task_id"], "kind": t["kind"], "inputs": t["inputs"], "ceiling_cents": t["ceiling_cents"],
                           "acceptance": WORK[t["kind"]]["acceptance"]} for _, t in sorted(self._state()["tasks"].items()) if t["status"] == "open"]}

    def _gated(self, guest: dict, *, objective: str, task_id: str, payload: dict, effect) -> None:
        """Route a guest's bounded write through the core embassy and the Consequence Gate under a single-use grant."""
        from foundry.systems.kernel_stack import proposal
        p = proposal(guest["passport_id"], action_class="embassy.task", requested_capability="embassy.task", objective=objective,
                     consequence_class="internal_write", target=f"task:{task_id}", estimated_cost_usd=0.0, payload=payload,
                     expected_outcome=objective)
        grant = self.gate.grants.issue_single_action(proposal=p, policy_version="1.0.0")
        done = {}

        def executor(_):
            done.update(effect())
            return {"observed_outcome": objective, "result_class": "positive"}
        rec = self.core.request(guest["passport_id"], p, executor=executor, standing_grant=grant)
        if not done:
            raise RpcError(-32001, f"Consequence Gate {rec.state}: {objective} did not execute")

    def _claim(self, guest: dict, params: dict) -> dict:
        s = self._state()
        t = s["tasks"].get(str(params.get("task_id")))
        if t is None or t["status"] != "open":
            raise RpcError(-32602, f"task {params.get('task_id')!r} is not open")
        if guest["suspended"]:
            raise RpcError(-32001, f"claims suspended: {guest['suspended']}")
        price = params.get("price_cents")
        if not isinstance(price, int) or price <= 0:
            raise RpcError(-32602, "price_cents is a positive integer")
        if price > t["ceiling_cents"]:
            return {"task_id": t["task_id"], "status": "countered", "counter_cents": t["ceiling_cents"],
                    "why": f"{price} exceeds the ceiling; claim again at or under {t['ceiling_cents']}"}

        def effect():
            s2 = self._state()
            s2["tasks"][t["task_id"]].update(status="claimed", claimed_by=guest["passport_id"], price_cents=price)
            self._save(s2)
            return {"claimed": True}
        self._gated(guest, objective=f"claim:{t['task_id']}", task_id=t["task_id"], payload={"price_cents": price}, effect=effect)
        return {"task_id": t["task_id"], "status": "accepted", "price_cents": price}

    def _submit(self, guest: dict, params: dict) -> dict:
        s = self._state()
        t = s["tasks"].get(str(params.get("task_id")))
        if t is None or t["claimed_by"] != guest["passport_id"]:
            raise RpcError(-32001, f"task {params.get('task_id')!r} is not claimed by you")
        if t["status"] != "claimed":
            raise RpcError(-32001, f"task {t['task_id']} is {t['status']}; a result is submitted once")
        result = params.get("result")
        if not isinstance(result, dict):
            raise RpcError(-32602, "result is an object")
        v = verify_result(t["kind"], t["inputs"], result)
        now = self.clock()
        out = {"task_id": t["task_id"], "verification": v}
        if v["verdict"] == "UNDECIDABLE":
            return {**out, "status": "claimed", "why": "the embassy cannot accept or refute this result; no verdict recorded"}

        def effect():
            s2 = self._state()
            t2, g2 = s2["tasks"][t["task_id"]], s2["guests"][guest["passport_id"]]
            t2.update(result_sha256=_sha(result), verification={**v, "at": now})
            s2["records"].append({"subject": guest["agent"], "context": f"embassy:{t['kind']}", "verdict": v["verdict"], "at": now,
                                  "evidence": [_sha(result), f"{v['method']}:{v['why']}"], "incident": v["verdict"] == "REFUTED"})
            if v["verdict"] == "VERIFIED":
                t2["status"] = "accepted"
                receipt = {"task_id": t["task_id"], "agent": guest["agent"], "result_sha256": _sha(result), "price_cents": t["price_cents"],
                           "verified_by": v["method"], "at": now, "embassy": self.embassy_id}
                receipt["signature"] = self.key.sign(_canon({k: x for k, x in receipt.items() if k != "signature"})).hex()
                s2["receipts"].append(receipt)
                accounting.post(self.books, date=now, memo=f"{t['task_id']} accepted from {guest['agent']}", currency="USD",
                                lines=[{"account": "expense:bounded_work", "debit": t["price_cents"]},
                                       {"account": "payable:foreign_agents", "credit": t["price_cents"]}])
                out.update(status="accepted", receipt=receipt)
            else:
                t2.update(status="open", claimed_by=None, price_cents=None)
                g2["suspended"] = f"result for {t['task_id']} refuted ({v['why']}); an operator must clear the suspension"
                out.update(status="rejected", suspended=g2["suspended"])
            self._save(s2)
            return {"submitted": True}
        self._gated(guest, objective=f"submit:{t['task_id']}", task_id=t["task_id"], payload={"result_sha256": _sha(result)}, effect=effect)
        return out

    def _get(self, guest: dict, params: dict) -> dict:
        t = self._state()["tasks"].get(str(params.get("task_id")))
        if t is None:
            raise RpcError(-32602, "unknown task")
        return {k: t[k] for k in ("task_id", "kind", "status", "price_cents", "result_sha256", "verification")}

    @staticmethod
    def verify_receipt(public_key_hex: str, receipt: dict) -> bool:
        return _verify(public_key_hex, receipt.get("signature", ""), {k: v for k, v in receipt.items() if k != "signature"})


class _Handler(http.server.BaseHTTPRequestHandler):
    embassy: Embassy = None

    def _send(self, status: int, headers: dict, body: bytes) -> None:
        self.send_response(status)
        for k, v in {**headers, "Content-Length": str(len(body))}.items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):  # noqa: N802
        status, headers, body = self.embassy.site.render(self.path, dict(self.headers), now=_t(self.embassy.clock()).timestamp())
        self._send(status, headers, body)

    def do_POST(self):  # noqa: N802
        if self.path != "/rpc":
            return self._send(404, {"Content-Type": "text/plain"}, b"only /rpc accepts requests")
        raw = self.rfile.read(int(self.headers.get("Content-Length") or 0))
        try:
            request = json.loads(raw.decode())
        except ValueError:
            request = None
        self._send(200, {"Content-Type": "application/json"}, json.dumps(self.embassy.rpc(request), sort_keys=True).encode())

    def log_message(self, *args):
        pass


def serve(embassy: Embassy) -> http.server.ThreadingHTTPServer:
    """Loopback only: the embassy is reached through the operator's own perimeter, never bound to a public interface here."""
    handler = type("EmbassyHandler", (_Handler,), {"embassy": embassy})
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


class ForeignAgent:
    """A foreign agent's side of the wire: its own key, card and signed calls. Knows nothing but the URL."""

    def __init__(self, name: str, *, key_seed: bytes, base: str):
        from greg.founder import public_bytes
        self.name, self.base = name, base
        self.key = Ed25519PrivateKey.from_private_bytes(key_seed)
        self.public_key = public_bytes(self.key.public_key()).hex()
        self.card = {"name": name, "url": f"https://{name}.invalid/a2a", "version": "1", "skills": [{"id": "general"}], "signing_key": self.public_key}
        self.passport_id, self.seq, self.n = None, 0, 0

    def http(self, method: str, path: str, body: dict | None = None) -> tuple[int, dict, bytes]:
        req = urllib.request.Request(self.base + path, data=_canon(body) if body is not None else None, method=method,
                                     headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                return resp.status, dict(resp.headers), resp.read()
        except urllib.error.HTTPError as exc:
            return exc.code, dict(exc.headers), exc.read()

    def rpc(self, method: str, params: dict | None = None, *, signed: bool = True, seq: int | None = None, key=None) -> dict:
        self.n += 1
        params = dict(params or {})
        if signed and self.passport_id:
            seq = self.seq + 1 if seq is None else seq
            body = {"audience": self.audience, "method": method, "params": params, "passport_id": self.passport_id, "seq": seq}
            params["auth"] = {"passport_id": self.passport_id, "seq": seq, "signature": (key or self.key).sign(_canon(body)).hex()}
            if seq > self.seq and key is None:
                self.seq = seq
        _, _, raw = self.http("POST", "/rpc", {"jsonrpc": "2.0", "id": self.n, "method": method, "params": params})
        return json.loads(raw)

    def admit(self, *, audience: str | None = None, reuse_nonce: str | None = None) -> dict:
        self.audience = audience
        ch = self.rpc("embassy/challenge", {"card": self.card, "signature": self.key.sign(_canon(self.card)).hex()}, signed=False)
        if "error" in ch:
            return ch
        self.audience = audience or ch["result"]["audience"]
        nonce = reuse_nonce or ch["result"]["nonce"]
        body = {"audience": self.audience, "card_sha256": _sha(self.card), "nonce": nonce}
        out = self.rpc("embassy/present", {"nonce": nonce, "signature": self.key.sign(_canon(body)).hex()}, signed=False)
        if "result" in out:
            self.passport_id, self.seq = out["result"]["passport_id"], 0
        return out


QUERY_OPS = {"standing": lambda a, r: reputation.score(_store(r)["records"], now=a["now"]),
             "tasks": lambda a, r: {"tasks": [{k: t[k] for k in ("task_id", "kind", "status", "price_cents")} for _, t in sorted(_store(r)["tasks"].items())]},
             "receipts": lambda a, r: {"receipts": _store(r)["receipts"]}}
APPLY_OPS: dict = {}      # posting work and admitting foreign agents are operator acts on a running embassy, not free ops


def _store(root: Path) -> dict:
    p = Path(root) / "embassy" / "embassy.json"
    return json.loads(p.read_text()) if p.exists() else {"records": [], "tasks": {}, "receipts": []}


def exercise(root) -> dict:
    from foundry.systems.webserver import verify_served
    root = Path(root)
    clock = {"now": "2026-10-13T15:00:00Z"}
    embassy = Embassy(root / "embassy", embassy_id="embassy:uniimente", key_seed=bytes(32 * [41]), clock=lambda: clock["now"])
    embassy.publish_card(version="1.0.0")
    embassy.post_task("t-factor", kind="factor", inputs={"n": 221}, ceiling_cents=500)
    embassy.post_task("t-sort", kind="sort", inputs={"items": [5, 3, 9, 1, 3]}, ceiling_cents=300)
    embassy.post_task("t-classify", kind="classify", inputs={"text": "Vendor reports a data breach affecting two accounts"}, ceiling_cents=200)
    embassy.post_task("t-undecidable", kind="classify", inputs={"text": "Minor incident, nothing else"}, ceiling_cents=200)
    embassy.post_task("t-factor-2", kind="factor", inputs={"n": 8051}, ceiling_cents=500)
    server = serve(embassy)
    try:
        base = f"http://127.0.0.1:{server.server_address[1]}"
        atlas = ForeignAgent("atlas", key_seed=bytes(32 * [42]), base=base)
        loki = ForeignAgent("loki", key_seed=bytes(32 * [43]), base=base)
        refusals = {}

        def refused(label, resp):
            refusals[label] = (resp.get("error") or {}).get("message", "")[:80] or None

        # discovery: the card is served with provenance any agent can check against the embassy's public key
        status, _, body = atlas.http("GET", CARD_PATH)
        card = json.loads(body)
        proof = verify_served(embassy.public_key, embassy.site.site_root(), embassy.site.provenance(CARD_PATH), body)
        refused("interior_path", json.loads(atlas.http("POST", "/rpc", {"jsonrpc": "2.0", "id": 0, "method": "ledger/read"})[2]))
        refused("foundry_op_over_the_wire", atlas.rpc("foundry/apply", {"system": 36, "op": "put"}, signed=False))
        refused("unsigned_before_admission", atlas.rpc("tasks/list", signed=False))

        # admission: challenge-response; the captured presentation is worthless a second time or for another audience
        forged_card = dict(atlas.card, signing_key=loki.public_key)
        refused("card_not_signed_by_its_key", atlas.rpc("embassy/challenge", {"card": forged_card, "signature": atlas.key.sign(_canon(forged_card)).hex()},
                                                       signed=False))
        refused("wrong_audience", atlas.admit(audience="embassy:someone-else"))
        first = atlas.rpc("embassy/challenge", {"card": atlas.card, "signature": atlas.key.sign(_canon(atlas.card)).hex()}, signed=False)
        clock["now"] = "2026-10-13T15:03:00Z"
        stale_body = {"audience": "embassy:uniimente", "card_sha256": _sha(atlas.card), "nonce": first["result"]["nonce"]}
        refused("expired_nonce", atlas.rpc("embassy/present", {"nonce": first["result"]["nonce"],
                                                               "signature": atlas.key.sign(_canon(stale_body)).hex()}, signed=False))
        admitted = atlas.admit()
        used_nonce = json.loads(atlas.http("POST", "/rpc", {"jsonrpc": "2.0", "id": 1, "method": "embassy/challenge",
                                                            "params": {"card": atlas.card, "signature": atlas.key.sign(_canon(atlas.card)).hex()}})[2])
        atlas.rpc("embassy/present", {"nonce": used_nonce["result"]["nonce"], "signature": atlas.key.sign(_canon(
            {"audience": "embassy:uniimente", "card_sha256": _sha(atlas.card), "nonce": used_nonce["result"]["nonce"]})).hex()}, signed=False)
        refused("replayed_nonce", atlas.rpc("embassy/present", {"nonce": used_nonce["result"]["nonce"], "signature": atlas.key.sign(_canon(
            {"audience": "embassy:uniimente", "card_sha256": _sha(atlas.card), "nonce": used_nonce["result"]["nonce"]})).hex()}, signed=False))
        atlas.passport_id = admitted["result"]["passport_id"]; atlas.seq = 0

        # signed requests: replay and forgery are refused before any state is read
        listed = atlas.rpc("tasks/list")
        refused("replayed_sequence", atlas.rpc("tasks/list", seq=atlas.seq))
        refused("forged_request_signature", atlas.rpc("tasks/list", key=loki.key))
        refused("unknown_method_signed", atlas.rpc("tasks/delete", {"task_id": "t-sort"}))

        # negotiation: above the ceiling is countered, at the ceiling is accepted (through the core embassy and the gate)
        countered = atlas.rpc("tasks/claim", {"task_id": "t-factor", "price_cents": 900})["result"]
        claimed = atlas.rpc("tasks/claim", {"task_id": "t-factor", "price_cents": countered["counter_cents"]})["result"]
        refused("claim_already_claimed_task", atlas.rpc("tasks/claim", {"task_id": "t-factor", "price_cents": 100}))
        refused("submit_unclaimed", atlas.rpc("tasks/submit", {"task_id": "t-sort", "result": {"sorted": []}}))
        accepted = atlas.rpc("tasks/submit", {"task_id": "t-factor", "result": {"factors": [13, 17]}})["result"]
        refused("submit_twice", atlas.rpc("tasks/submit", {"task_id": "t-factor", "result": {"factors": [13, 17]}}))
        atlas.rpc("tasks/claim", {"task_id": "t-sort", "price_cents": 300})
        sorted_ok = atlas.rpc("tasks/submit", {"task_id": "t-sort", "result": {"sorted": [1, 3, 3, 5, 9]}})["result"]
        atlas.rpc("tasks/claim", {"task_id": "t-classify", "price_cents": 150})
        classified = atlas.rpc("tasks/submit", {"task_id": "t-classify", "result": {"label": "risk"}})["result"]
        atlas.rpc("tasks/claim", {"task_id": "t-undecidable", "price_cents": 100})
        undecidable = atlas.rpc("tasks/submit", {"task_id": "t-undecidable", "result": {"label": "risk"}})["result"]

        # a wrong result is refuted before acceptance, recorded, and suspends the agent's claims
        loki.admit()
        loki.rpc("tasks/claim", {"task_id": "t-factor-2", "price_cents": 500})
        rejected = loki.rpc("tasks/submit", {"task_id": "t-factor-2", "result": {"factors": [7, 1150]}})["result"]
        refused("claim_while_suspended", loki.rpc("tasks/claim", {"task_id": "t-factor-2", "price_cents": 100}))
        reopened = atlas.rpc("tasks/get", {"task_id": "t-factor-2"})["result"]
        standing = atlas.rpc("embassy/standing")["result"]
    finally:
        server.shutdown()
        server.server_close()
    ledger_types = Counter(r.payload["type"] for r in embassy.ledger.by_type("event"))
    books = accounting.trial_balance(embassy.books)
    return {"card_served": status == 200 and [s["id"] for s in card["skills"]] == ["factor", "sort", "classify"],
            "card_proof": proof, "methods_exposed": card["x-uniimente"]["protocol"]["methods"],
            "admitted_ceiling": admitted["result"]["ceiling"], "admitted_budget_usd": admitted["result"]["budget_usd"],
            "open_tasks_listed": len(listed["result"]["tasks"]),
            "negotiation": {"countered": countered["status"], "counter_cents": countered["counter_cents"], "then": claimed["status"]},
            "accepted": {"status": accepted["status"], "verification": accepted["verification"]["verdict"], "method": accepted["verification"]["method"]},
            "receipt_verifies": Embassy.verify_receipt(embassy.public_key, accepted["receipt"]),
            "sort_accepted": sorted_ok["status"], "classify_accepted": classified["status"],
            "undecidable": {"status": undecidable["status"], "verdict": undecidable["verification"]["verdict"]},
            "rejected": {"status": rejected["status"], "why": rejected["verification"]["why"], "suspended": bool(rejected["suspended"])},
            "refuted_task_reopened": reopened["status"] == "open" and reopened["price_cents"] is None,
            "standing": {f"{r['subject']}@{r['context']}": {"status": r["status"], "incidents": r["incidents"]} for r in standing["subjects"]},
            "undecidable_earned_no_verdict": not any(r["subject"] == "atlas" and r["context"] == "embassy:classify" and r["verdict"] != "VERIFIED"
                                                     for r in embassy._state()["records"]) and len(embassy._state()["records"]) == 4,
            "ledger": {"admitted": ledger_types["embassy.admitted"], "routed_through_gate": ledger_types["embassy.request_routed"]},
            "books": {"equation_holds": books["equation_holds"], "payable_to_agents_cents": books["balances"]["payable:foreign_agents"]},
            "refusals": refusals}
