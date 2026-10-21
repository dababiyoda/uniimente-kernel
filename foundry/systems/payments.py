"""#38 Payments: billing, metering, refunds and reserves on a real payment rail's own SDK, in test mode.

The rail is Stripe's official Python SDK (adopted, not rebuilt). In the sandbox
the SDK is pointed, through its ``base_addresses`` option, at a local server that
speaks Stripe's API shape (PaymentIntents, Refunds, idempotency keys, test-card
declines) so every code path the live rail will exercise runs here without a
key or a network. Live test mode uses the identical code with the founder's
``sk_test_`` key and Stripe's real base address; a key is never read from the
environment and a live key (``sk_live_``) is refused outright.

What UNIIMENTE owns above the rail:

  trace      a charge is created only against a delivery receipt hash and a
             Consequence Gate grant for that exact case and amount (#30): no
             delivery receipt, no charge; no grant, no charge. A grant is honoured
             only if the Gate that governs this rail issued it (registered there,
             unaltered, unrevoked, unused, unexpired, bound to this case and
             amount), and the charge itself runs through that Gate, which consumes
             the grant: a forged or borrowed grant dict moves no money
  metering   usage records per customer and metered unit, settled into one
             invoice-sized charge whose line items cite the usage ids
  books      every movement posts a balanced entry to the #39 journal in integer
             cents: receivable, settled cash, processor fee, refunds, and a
             reserve tier (a configured share of each settlement held back for
             disputes); the trial balance reconciles to the processor to the cent
  refunds    a refund is a reversal that needs the original charge id and a
             recorded reason; it can never exceed the charge
  idempotent charge creation carries an idempotency key derived from the case,
             so a retry after a timeout cannot double-charge (the rail's own
             guarantee, exercised through #23's retry discipline)

Money is only ever moved by the rail under the founder's key; here it is the
emulator's ledger. The reserve is a bookkeeping tier, not a bank account.
"""
from __future__ import annotations

import hashlib
import http.server
import json
import threading
import urllib.parse
from pathlib import Path

from foundry.systems import accounting

RESERVE_SHARE = 0.10
FEE_BPS = 290          # 2.9% + 30c, Stripe's published card rate, used only by the emulator
FEE_FIXED_CENTS = 30
DECLINE_CARDS = {"pm_card_chargeDeclined": "card_declined", "pm_card_chargeDeclinedInsufficientFunds": "insufficient_funds"}


class PaymentError(RuntimeError):
    pass


# -- a Stripe-API-shaped emulator (sandbox only) ---------------------------------------------

class StripeEmulator:
    """Enough of https://api.stripe.com/v1 for PaymentIntents and Refunds, with idempotency keys."""

    def __init__(self):
        self.intents: dict[str, dict] = {}
        self.refunds: dict[str, dict] = {}
        self.idempotency: dict[str, tuple[str, dict]] = {}
        self.counter = 0
        self.lock = threading.Lock()

    def _id(self, prefix: str) -> str:
        self.counter += 1
        return f"{prefix}_{self.counter:06d}"

    def handle(self, method: str, path: str, form: dict, idem: str | None) -> tuple[int, dict]:
        with self.lock:
            if idem and idem in self.idempotency:
                prior_path, prior = self.idempotency[idem]
                if prior_path != path:
                    return 400, {"error": {"type": "idempotency_error", "message": "key reused with a different request"}}
                return 200, prior
            status, body = self._route(method, path, form)
            if idem and status == 200:
                self.idempotency[idem] = (path, body)
            return status, body

    def _route(self, method, path, form):
        if method == "POST" and path == "/v1/payment_intents":
            amount, currency = int(form["amount"]), form.get("currency", "usd")
            if amount <= 0:
                return 400, {"error": {"type": "invalid_request_error", "message": "amount must be positive"}}
            pm = form.get("payment_method", "pm_card_visa")
            pi = {"id": self._id("pi"), "object": "payment_intent", "amount": amount, "currency": currency,
                  "metadata": {k[9:-1]: v for k, v in form.items() if k.startswith("metadata[")},
                  "amount_received": 0, "status": "requires_confirmation", "latest_charge": None}
            if form.get("confirm") in ("true", "True", True):
                if pm in DECLINE_CARDS:
                    pi["status"] = "requires_payment_method"
                    self.intents[pi["id"]] = pi
                    return 402, {"error": {"type": "card_error", "code": "card_declined", "decline_code": DECLINE_CARDS[pm],
                                           "message": "Your card was declined.", "payment_intent": pi}}
                fee = amount * FEE_BPS // 10000 + FEE_FIXED_CENTS
                pi.update(status="succeeded", amount_received=amount, latest_charge=self._id("ch"),
                          fee=fee, net=amount - fee)
            self.intents[pi["id"]] = pi
            return 200, pi
        if method == "GET" and path.startswith("/v1/payment_intents/"):
            pi = self.intents.get(path.rsplit("/", 1)[1])
            return (200, pi) if pi else (404, {"error": {"type": "invalid_request_error", "message": "No such payment_intent"}})
        if method == "POST" and path == "/v1/refunds":
            pi = self.intents.get(form.get("payment_intent", ""))
            if not pi or pi["status"] != "succeeded":
                return 400, {"error": {"type": "invalid_request_error", "message": "No such succeeded payment_intent"}}
            refunded = sum(r["amount"] for r in self.refunds.values() if r["payment_intent"] == pi["id"])
            amount = int(form.get("amount", pi["amount"] - refunded))
            if amount <= 0 or refunded + amount > pi["amount"]:
                return 400, {"error": {"type": "invalid_request_error", "code": "charge_already_refunded",
                                       "message": "Refund exceeds the charge"}}
            r = {"id": self._id("re"), "object": "refund", "amount": amount, "payment_intent": pi["id"],
                 "status": "succeeded", "reason": form.get("reason", "requested_by_customer")}
            self.refunds[r["id"]] = r
            return 200, r
        return 404, {"error": {"type": "invalid_request_error", "message": f"Unrecognized request URL ({method}: {path})"}}

    def balance(self) -> dict:
        gross = sum(p["amount"] for p in self.intents.values() if p["status"] == "succeeded")
        fees = sum(p["fee"] for p in self.intents.values() if p["status"] == "succeeded")
        refunds = sum(r["amount"] for r in self.refunds.values())
        return {"gross_cents": gross, "fees_cents": fees, "refunds_cents": refunds, "net_cents": gross - fees - refunds}


class _Handler(http.server.BaseHTTPRequestHandler):
    emulator: StripeEmulator = None

    def _serve(self, method):
        auth = self.headers.get("Authorization", "")
        if not auth.startswith("Bearer sk_test_"):
            status, body = 401, {"error": {"type": "invalid_request_error", "message": "test-mode key required"}}
        else:
            length = int(self.headers.get("Content-Length") or 0)
            raw = self.rfile.read(length).decode() if length else ""
            form = {k: v[0] for k, v in urllib.parse.parse_qs(raw).items()}
            status, body = self.emulator.handle(method, urllib.parse.urlsplit(self.path).path, form,
                                                self.headers.get("Idempotency-Key"))
        data = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self):  # noqa: N802
        self._serve("POST")

    def do_GET(self):  # noqa: N802
        self._serve("GET")

    def log_message(self, *a):
        pass


def start_emulator() -> tuple[http.server.ThreadingHTTPServer, StripeEmulator]:
    emulator = StripeEmulator()
    handler = type("StripeHandler", (_Handler,), {"emulator": emulator})
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, emulator


# -- the rail -----------------------------------------------------------------------------------

def client(api_key: str, base: str | None):
    """The official SDK. A live key is refused; a test key reaches either the emulator or Stripe test mode."""
    import stripe
    if not api_key.startswith("sk_test_"):
        raise PaymentError("only a test-mode key (sk_test_...) may be used here; live mode is a founder decision")
    kwargs = {"max_network_retries": 0}
    if base:
        kwargs["base_addresses"] = {"api": base, "connect": base, "files": base, "meter_events": base}
    return stripe.StripeClient(api_key, **kwargs)


def money_label(intent: dict) -> dict:
    """The processor's own word on whether money moved: only a live-mode intent is observed money. This rail
    runs test mode only (live keys are refused), so every charge on it is labelled synthetic."""
    live = intent.get("livemode") is True
    return {"livemode": live, "money": "observed" if live else "synthetic"}


class Rail:
    def __init__(self, root: Path, *, api_key: str, base: str | None, reserve_share: float = RESERVE_SHARE,
                 gate=None):
        self.root, self.reserve_share = Path(root), reserve_share
        self.gate = gate          # the Consequence Gate whose grants this rail honours; without one it charges nothing
        self.stripe = client(api_key, base)
        self.books = self.root / "books"
        for account, kind in (("receivable", "asset"), ("cash:processor", "asset"), ("reserve:disputes", "asset"),
                              ("fees:processor", "expense"), ("refunds", "expense"), ("revenue:services", "revenue"),
                              ("usage:unbilled", "asset")):
            accounting.open_account(self.books, account, kind, "USD")

    def _state(self) -> dict:
        p = self.root / "rail.json"
        return json.loads(p.read_text()) if p.exists() else {"charges": {}, "usage": [], "refunds": {}}

    def _save(self, s: dict) -> None:
        (self.root / "rail.tmp").write_text(json.dumps(s, sort_keys=True))
        (self.root / "rail.tmp").replace(self.root / "rail.json")

    def meter(self, *, customer: str, unit: str, quantity: int, unit_cents: int, evidence: str) -> dict:
        if quantity <= 0 or unit_cents <= 0 or not evidence:
            raise PaymentError("usage needs positive quantity, a positive unit price and evidence of the work")
        s = self._state()
        row = {"id": f"use-{len(s['usage']) + 1}", "customer": customer, "unit": unit, "quantity": quantity,
               "unit_cents": unit_cents, "evidence": evidence, "billed": None}
        s["usage"].append(row)
        self._save(s)
        accounting.post(self.books, date="meter", memo=f"usage {row['id']} {quantity} x {unit}", currency="USD",
                        lines=[{"account": "usage:unbilled", "debit": quantity * unit_cents},
                               {"account": "revenue:services", "credit": quantity * unit_cents}])
        return row

    def charge(self, *, case_id: str, customer: str, amount_cents: int, delivery_receipt: str, grant: dict,
               payment_method: str = "pm_card_visa", usage_ids: list[str] | None = None) -> dict:
        import stripe
        if not (delivery_receipt or "").startswith("sha256:"):
            raise PaymentError("a charge needs the delivery receipt hash it bills for")
        if not grant or grant.get("grant_id") is None or grant.get("objective") != f"charge:{case_id}":
            raise PaymentError("a charge needs a Consequence Gate grant issued for this exact case")
        from foundry.systems.kernel_stack import grant_problems
        effect = dict(action_class="business.charge", objective=f"charge:{case_id}", target=f"buyer:{case_id}",
                      payload={"case_id": case_id, "amount_cents": amount_cents})
        problems = grant_problems(self.gate, grant, **effect)
        if problems:
            raise PaymentError("grant not honoured: " + "; ".join(problems))
        s = self._state()
        if case_id in s["charges"]:
            raise PaymentError(f"case {case_id} is already charged; refunds are the only way back")
        usage_ids = usage_ids or []
        usage_total = sum(u["quantity"] * u["unit_cents"] for u in s["usage"] if u["id"] in usage_ids)
        if usage_ids and usage_total != amount_cents:
            raise PaymentError(f"metered amount {usage_total} does not match charge {amount_cents}")
        idem = "case-" + hashlib.sha256(f"{case_id}:{amount_cents}".encode()).hexdigest()[:24]
        from foundry.systems.kernel_stack import run_under_grant
        moved: dict = {}

        def execute(_proposal):                 # runs only after the Gate admitted the grant and claimed dispatch
            try:
                created = self.stripe.payment_intents.create(
                    params={"amount": amount_cents, "currency": "usd", "payment_method": payment_method,
                            "confirm": True, "metadata": {"case_id": case_id, "delivery_receipt": delivery_receipt,
                                                          "grant_id": grant["grant_id"]}},
                    options={"idempotency_key": idem})
            except stripe.CardError as exc:
                moved["declined"] = getattr(exc, "code", None) or str(exc)[:40]
                return {"observed_outcome": "card declined", "result_class": "negative",
                        "output": {"decline_code": moved["declined"]}, "validation_status": "processor_reported"}
            moved["intent"] = created.to_dict() if hasattr(created, "to_dict") else dict(created)
            return {"observed_outcome": "payment settled", "result_class": "positive",
                    "output": {"intent": moved["intent"]["id"]}, "validation_status": "processor_reported"}

        record = run_under_grant(self.gate, grant, consequence_class="financial", evidence_refs=[delivery_receipt],
                                 expected_outcome="payment settled", executor=execute, **effect)
        if record.state != "recorded":
            if moved or record.state == "reconciliation_required":
                raise PaymentError(f"charge outcome unknown ({record.state}); reconcile with the processor, never "
                                   f"retry: {record.refusal_reasons}")
            raise PaymentError(f"the Consequence Gate refused the charge ({record.state}): {record.refusal_reasons}")
        if "declined" in moved:
            s["charges"][case_id] = {"status": "declined", "decline_code": moved["declined"], "amount_cents": amount_cents,
                                     "grant_id": grant["grant_id"], "gate_receipt": record.receipt_hash}
            self._save(s)
            return {"status": "declined", "decline_code": moved["declined"]}
        pi = moved["intent"]
        fee = int(pi.get("fee") or 0)
        accounting.post(self.books, date="charge", memo=f"{case_id} settled {pi['id']}", currency="USD",
                        lines=[{"account": "cash:processor", "debit": amount_cents - fee},
                               {"account": "fees:processor", "debit": fee},
                               {"account": "usage:unbilled" if usage_ids else "revenue:services", "credit": amount_cents}])
        reserve = int(round((amount_cents - fee) * self.reserve_share))
        if reserve:
            accounting.post(self.books, date="charge", memo=f"{case_id} dispute reserve", currency="USD",
                            lines=[{"account": "reserve:disputes", "debit": reserve}, {"account": "cash:processor", "credit": reserve}])
        for u in s["usage"]:
            if u["id"] in usage_ids:
                u["billed"] = pi["id"]
        money = money_label(pi)
        s["charges"][case_id] = {"status": "settled", "intent": pi["id"], "amount_cents": amount_cents, "fee_cents": fee,
                                 "reserve_cents": reserve, "delivery_receipt": delivery_receipt, "grant_id": grant["grant_id"],
                                 "gate_receipt": record.receipt_hash, "idempotency_key": idem, "usage": usage_ids, **money}
        self._save(s)
        return {"status": "settled", "intent": pi["id"], "fee_cents": fee, "reserve_cents": reserve, **money}

    def refund(self, *, case_id: str, amount_cents: int, reason: str) -> dict:
        import stripe
        s = self._state()
        ch = s["charges"].get(case_id)
        if not ch or ch["status"] != "settled":
            raise PaymentError(f"no settled charge for {case_id}")
        if not reason:
            raise PaymentError("a refund needs a recorded reason")
        try:
            r = self.stripe.refunds.create(params={"payment_intent": ch["intent"], "amount": amount_cents,
                                                   "reason": "requested_by_customer", "metadata": {"why": reason}})
        except stripe.InvalidRequestError as exc:
            raise PaymentError(f"rail refused the refund: {getattr(exc, 'code', None) or exc}") from None
        r = r.to_dict() if hasattr(r, "to_dict") else dict(r)
        released = min(amount_cents, ch["reserve_cents"] - sum(x["reserve_released"] for x in s["refunds"].values()
                                                               if x["case_id"] == case_id))
        lines = [{"account": "refunds", "debit": amount_cents}]
        if released > 0:
            lines += [{"account": "reserve:disputes", "credit": released}]
        if amount_cents - released > 0:
            lines += [{"account": "cash:processor", "credit": amount_cents - released}]
        accounting.post(self.books, date="refund", memo=f"{case_id} refund {r['id']}: {reason}", currency="USD", lines=lines)
        s["refunds"][r["id"]] = {"case_id": case_id, "amount_cents": amount_cents, "reason": reason, "reserve_released": max(released, 0)}
        self._save(s)
        return {"refund": r["id"], "amount_cents": amount_cents}

    def reconcile(self, processor_balance: dict) -> dict:
        tb = accounting.trial_balance(self.books)
        b = tb["balances"]
        ours = {"gross_cents": sum(c["amount_cents"] for c in self._state()["charges"].values() if c["status"] == "settled"),
                "fees_cents": b["fees:processor"], "refunds_cents": b["refunds"],
                "net_cents": b["cash:processor"] + b["reserve:disputes"]}
        return {"books": ours, "processor": processor_balance, "reconciled": ours == processor_balance,
                "equation_holds": tb["equation_holds"], "reserve_cents": b["reserve:disputes"]}


def _grant_for(case_id: str, amount_cents: int, *, gate):
    """A single-use grant, issued by ``gate`` (the Gate that governs the rail), for charging this exact case and
    amount (financial consequence). A grant from any other issuer is not honoured by that rail."""
    from foundry.systems.kernel_stack import agent, proposal
    passports = gate.passports
    actor = agent(passports, capabilities=("business.charge",), budget=amount_cents / 100 + 1)
    p = proposal(actor.passport_id, action_class="business.charge", requested_capability="business.charge",
                 objective=f"charge:{case_id}", consequence_class="financial", target=f"buyer:{case_id}",
                 estimated_cost_usd=0.0, payload={"case_id": case_id, "amount_cents": amount_cents})
    return gate.grants.issue_single_action(proposal=p, policy_version="1.0.0")


charge_grant = _grant_for   # public name for #37 and #54, which settle through this rail


QUERY_OPS = {"books": lambda a, r: accounting.trial_balance(Path(r) / "books")}
APPLY_OPS: dict = {}       # charging is a gate-executed act, not a free op: see business/commercial_loop.py


def exercise(root) -> dict:
    root = Path(root)
    from foundry.systems.kernel_stack import gate_stack
    server, emulator = start_emulator()
    try:
        base = f"http://127.0.0.1:{server.server_address[1]}"
        gate, _, gate_ledger = gate_stack()      # the Gate that governs this rail; only its grants move money
        rail = Rail(root / "rail", api_key="sk_test_emulator", base=base, gate=gate)

        def _grant_for(case_id, amount_cents):
            return charge_grant(case_id, amount_cents, gate=gate)
        receipt = "sha256:" + "ab" * 32
        refusals = {}
        def refused(label, fn):
            try:
                fn()
                refusals[label] = None
            except PaymentError as exc:
                refusals[label] = str(exc)[:70]
        refused("live_key", lambda: Rail(root / "live", api_key="sk_live_nope", base=base))
        refused("no_delivery_receipt", lambda: rail.charge(case_id="c0", customer="acme", amount_cents=90000,
                                                           delivery_receipt="", grant=_grant_for("c0", 90000)))
        refused("no_grant", lambda: rail.charge(case_id="c0", customer="acme", amount_cents=90000, delivery_receipt=receipt, grant={}))
        refused("grant_for_other_case", lambda: rail.charge(case_id="c0", customer="acme", amount_cents=90000,
                                                            delivery_receipt=receipt, grant=_grant_for("c9", 90000)))
        # A dict shaped like a grant is not authority: forged, borrowed from another issuer, altered, or bound
        # to a smaller amount, it moves no money (Mission G probe: a forged dict settled 5000 cents before).
        refused("forged_grant", lambda: rail.charge(case_id="c0", customer="acme", amount_cents=5000, delivery_receipt=receipt,
                                                    grant={"grant_id": "forged-not-issued-by-any-gate", "objective": "charge:c0"}))
        refused("grant_from_another_gate", lambda: rail.charge(case_id="c0", customer="acme", amount_cents=5000,
                                                               delivery_receipt=receipt,
                                                               grant=charge_grant("c0", 5000, gate=gate_stack()[0])))
        refused("altered_grant", lambda: rail.charge(case_id="c0", customer="acme", amount_cents=5000, delivery_receipt=receipt,
                                                     grant={**_grant_for("c0", 5000), "spending_limit_usd": 1e9}))
        refused("amount_above_grant", lambda: rail.charge(case_id="c0", customer="acme", amount_cents=90000,
                                                          delivery_receipt=receipt, grant=_grant_for("c0", 5000)))
        first = rail.charge(case_id="c1", customer="acme", amount_cents=90000, delivery_receipt=receipt, grant=_grant_for("c1", 90000))
        # The Gate, not the rail's own file, holds single use: a second rail on fresh books under the same Gate
        # cannot spend the consumed grant again.
        used = rail._state()["charges"]["c1"]["grant_id"]
        refused("grant_reused", lambda: Rail(root / "rail-replay", api_key="sk_test_emulator", base=base, gate=gate).charge(
            case_id="c1", customer="acme", amount_cents=90000, delivery_receipt=receipt, grant=gate.grants.get(used)))
        # the same create, retried after a "timeout": the rail's idempotency key makes it the same intent
        import stripe
        retried = rail.stripe.payment_intents.create(params={"amount": 90000, "currency": "usd", "payment_method": "pm_card_visa",
                                                             "confirm": True}, options={"idempotency_key": rail._state()["charges"]["c1"]["idempotency_key"]})
        refused("double_charge_same_case", lambda: rail.charge(case_id="c1", customer="acme", amount_cents=90000,
                                                               delivery_receipt=receipt, grant=_grant_for("c1", 90000)))
        declined = rail.charge(case_id="c2", customer="globex", amount_cents=5000, delivery_receipt=receipt,
                               grant=_grant_for("c2", 5000), payment_method="pm_card_chargeDeclined")
        u1 = rail.meter(customer="initech", unit="audit", quantity=3, unit_cents=20000, evidence="receipt:a1")
        u2 = rail.meter(customer="initech", unit="report", quantity=1, unit_cents=15000, evidence="receipt:r1")
        refused("metered_mismatch", lambda: rail.charge(case_id="c3", customer="initech", amount_cents=1, delivery_receipt=receipt,
                                                        grant=_grant_for("c3", 1), usage_ids=[u1["id"], u2["id"]]))
        metered = rail.charge(case_id="c3", customer="initech", amount_cents=75000, delivery_receipt=receipt,
                              grant=_grant_for("c3", 75000), usage_ids=[u1["id"], u2["id"]])
        refund = rail.refund(case_id="c1", amount_cents=30000, reason="one of three audits disputed")
        refused("refund_over_charge", lambda: rail.refund(case_id="c1", amount_cents=90000, reason="x"))
        refused("refund_without_reason", lambda: rail.refund(case_id="c3", amount_cents=100, reason=""))
        recon = rail.reconcile(emulator.balance())
        receipts = [r.payload for r in gate_ledger.by_type("receipt")]
        honoured = {c["grant_id"] for c in rail._state()["charges"].values() if c.get("grant_id")}
    finally:
        server.shutdown()
        server.server_close()
    return {"settled": first["status"], "fee_cents": first["fee_cents"], "reserve_cents": first["reserve_cents"],
            "every_charge_receipted_by_the_gate": honoured == {r["grant_id"] for r in receipts}
            and len(receipts) == len(honoured) and all(gate.grants.get_meta(g)["used"] for g in honoured),
            "idempotent_retry_same_intent": retried["id"] == rail._state()["charges"]["c1"]["intent"],
            "declined": declined, "metered_settled": metered["status"], "usage_billed": all(u["billed"] for u in rail._state()["usage"]),
            "refund": refund["amount_cents"], "refusals": refusals, "reconciled_to_processor": recon["reconciled"],
            "books_balance": recon["equation_holds"], "reserve_after_refund_cents": recon["reserve_cents"],
            "books_vs_processor": {"books": recon["books"], "processor": recon["processor"]}}
