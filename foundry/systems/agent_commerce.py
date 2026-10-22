"""#54 Agent-native commerce: capabilities published as signed, machine-readable offers that another agent
can discover, price, pay for and redeem in test mode, with receipts that feed reputation.

Three adopted shapes, recombined over owned rails rather than cloned:

  card      an A2A-style Agent Card (name, description, url, version, skills[]) is served at
            /.well-known/agent.json by the #31 site, so every byte of the offer is versioned and
            provable, and announced in the #27 directory under the seller's signing key. Each skill
            names the typed contracts it consumes and produces and a #2 pricing rule with the seller's
            constants; a buyer evaluates the rule itself, and the quote is the rule's value or there is
            no sale
  402       an x402-shaped flow: asking for a priced resource without payment answers 402 with the
            requirement (amount, currency, pay-to, resource, nonce, expiry); the buyer pays on the #38
            rail in test mode with the order bound into the payment's metadata and presents the payment
            id; the seller verifies with the processor, never the buyer: succeeded, exact amount, nonce
            and order bound, never redeemed before. Only then does it deliver, under a Consequence Gate
            grant for that order (delivery to a third party is contact), and book the sale (#39). The
            grant must be one the storefront's own Gate issued (registered, unaltered, unused, unexpired,
            bound to this order), and the delivery runs through that Gate, which consumes it
  receipts  a delivered order is a signed receipt (payment id, delivery hash, order, amount). The
            buyer's verification by an accepted method turns it into an evidenced reputation record for
            the skill (#41); a verified payment the seller cannot fulfil is refunded on the rail and
            recorded as the skill's failure. An unverified receipt earns nothing. Money the processor
            holds for an order the seller refused (wrong amount, wrong order) is booked as a refund due
            and swept back to the payer, so the books reconcile to the processor to the cent

The money is test-mode card money on #38's emulator, not an on-chain asset; nothing here reaches a real
network, and no key is read from the environment.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

from business.commercial_loop import ACCEPTED_VERIFICATIONS
from foundry.systems import accounting, cas, discovery, dsl, reputation
from foundry.systems.webserver import Site, verify_served

CARD_PATH = "/.well-known/agent.json"
CHALLENGE_TTL = timedelta(minutes=15)
SKILL_FIELDS = {"id", "name", "description", "tags", "consumes", "produces", "pricing", "latency_ms"}
PRICING_FIELDS = {"rule", "constants", "buyer_variables", "example"}


class CommerceError(ValueError):
    pass


def _canon(value) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def _t(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def _stamp(d: datetime) -> str:
    return d.strftime("%Y-%m-%dT%H:%M:%SZ")


def _intent(pi) -> dict:
    return pi.to_dict() if hasattr(pi, "to_dict") else dict(pi)


class Storefront:
    def __init__(self, root: Path, *, seller_id: str, key_seed: bytes, rail, base_url: str = "https://seller.invalid",
                 gate=None):
        from greg.founder import public_bytes
        self.root, self.seller_id, self.rail, self.base_url = Path(root), seller_id, rail, base_url
        self.gate = gate          # the Consequence Gate whose grants this storefront honours; without one it delivers nothing
        self.root.mkdir(parents=True, exist_ok=True)
        self.key = Ed25519PrivateKey.from_private_bytes(key_seed)
        self.public_key = public_bytes(self.key.public_key()).hex()
        self.site = Site(self.root / "site", key_seed=key_seed)
        self.directory = self.root / "directory"
        discovery.enroll(self.directory, seller_id, self.public_key)
        self.books = rail.books
        for account, kind in (("cash:processor", "asset"), ("fees:processor", "expense"), ("revenue:services", "revenue"),
                              ("refunds", "expense"), ("payable:refunds_due", "liability")):
            accounting.open_account(self.books, account, kind, "USD")
        self.handlers: dict = {}

    # -- state ---------------------------------------------------------------------------------
    def _state(self) -> dict:
        p = self.root / "store.json"
        return json.loads(p.read_text()) if p.exists() else {"card": None, "sequence": 0, "counter": 0, "orders": {},
                                                             "redeemed": {}, "stray": {}, "records": [], "booked_cents": 0}

    def _save(self, s: dict) -> None:
        (self.root / "store.tmp").write_text(json.dumps(s, sort_keys=True))
        (self.root / "store.tmp").replace(self.root / "store.json")

    # -- the offer -----------------------------------------------------------------------------
    def publish_card(self, *, name: str, description: str, version: str, skills: list[dict], now: str) -> dict:
        from linker.linker import known_contracts
        contracts = set(known_contracts())
        for s in skills:
            if set(s) != SKILL_FIELDS or set(s["pricing"]) != PRICING_FIELDS:
                raise CommerceError(f"skill fields must be exactly {sorted(SKILL_FIELDS)} with pricing {sorted(PRICING_FIELDS)}")
            untyped = sorted((set(s["consumes"]) | set(s["produces"])) - contracts)
            if untyped:
                raise CommerceError(f"skill {s['id']} names untyped contracts {untyped}")
            try:
                dsl.parse("pricing", s["pricing"]["rule"])
            except dsl.RuleError as exc:
                raise CommerceError(f"skill {s['id']} pricing rule refused: {exc}") from None
            if set(s["pricing"]["constants"]) & set(s["pricing"]["buyer_variables"]):
                raise CommerceError(f"skill {s['id']}: a buyer variable cannot also be a seller constant")
            self._quote(s, s["pricing"]["example"])       # the example must price under the rule, or the offer is not publishable
        card = {"name": name, "description": description, "url": f"{self.base_url}/a2a", "version": version,
                "provider": {"organization": self.seller_id}, "capabilities": {"streaming": False, "pushNotifications": False},
                "defaultInputModes": ["application/json"], "defaultOutputModes": ["application/json"],
                "skills": [{"id": s["id"], "name": s["name"], "description": s["description"], "tags": s["tags"],
                            "inputModes": ["application/json"], "outputModes": ["application/json"]} for s in skills],
                "x-uniimente": {"signing_key": self.public_key,
                                "contracts": {s["id"]: {"consumes": s["consumes"], "produces": s["produces"]} for s in skills},
                                "pricing": {s["id"]: {"language": "pricing", "currency": "usd", **s["pricing"]} for s in skills},
                                "settlement": {"scheme": "card-test", "network": "stripe-test-emulator", "challenge": 402,
                                               "pay_to": self.seller_id},
                                "verification_methods": list(ACCEPTED_VERIFICATIONS)}}
        published = self.site.publish(CARD_PATH, _canon(card), reason=f"offer v{version}", evidence=[f"skills:{len(skills)}"])
        s_ = self._state()
        s_["sequence"] += 1
        descriptor = {"organ_id": self.seller_id, "sequence": s_["sequence"], "published_at": now, "ttl_s": 86400,
                      "capabilities": [{"capability_id": f"{self.seller_id}/{s['id']}", "consumes": s["consumes"], "produces": s["produces"],
                                        "consequence_class": "external_contact", "health": "up",
                                        "cost_usd": self._quote(s, s["pricing"]["example"]) / 100, "latency_ms": s["latency_ms"],
                                        "card_url": f"{self.base_url}{CARD_PATH}"} for s in skills]}
        discovery.publish(self.directory, discovery.sign(self.key, descriptor))
        s_["card"] = card
        self._save(s_)
        return {"version": published["version"], "address": published["address"], "site_root": published["site_root"],
                "skills": len(skills), "directory_sequence": s_["sequence"]}

    def card(self, *, now: str) -> tuple[int, dict]:
        status, headers, body = self.site.render(CARD_PATH, {}, now=_t(now).timestamp())
        return status, (json.loads(body) if status == 200 else {"error": body.decode()})

    def proof(self) -> dict:
        """What a buyer holding only the seller's public key can check about the card it was served."""
        _, _, body = self.site.render(CARD_PATH, {}, now=0.0)
        return verify_served(self.public_key, self.site.site_root(), self.site.provenance(CARD_PATH), body)

    @staticmethod
    def _quote(skill: dict, inputs: dict) -> int:
        pricing = skill["pricing"]
        extra = sorted(set(inputs) - set(pricing["buyer_variables"]))
        if extra:
            raise CommerceError(f"buyer may set only {sorted(pricing['buyer_variables'])}, not {extra}")
        value = dsl.run("pricing", pricing["rule"], {**pricing["constants"], **inputs})
        cents = int(round(value * 100))
        if cents <= 0:
            raise CommerceError("the rule priced this at zero; nothing is sold for nothing")
        return cents

    def quote(self, skill_id: str, inputs: dict) -> int:
        s = self._state()
        if not s["card"] or skill_id not in s["card"]["x-uniimente"]["pricing"]:
            raise CommerceError(f"no published skill {skill_id!r}")
        return self._quote({"pricing": {k: v for k, v in s["card"]["x-uniimente"]["pricing"][skill_id].items()
                                        if k in PRICING_FIELDS}}, inputs)

    @staticmethod
    def buyer_quote(card: dict, skill_id: str, inputs: dict) -> int:
        """The buyer's own evaluation of the published rule; must equal the seller's or there is no sale."""
        return Storefront._quote({"pricing": {k: v for k, v in card["x-uniimente"]["pricing"][skill_id].items()
                                              if k in PRICING_FIELDS}}, inputs)

    # -- 402 challenge -------------------------------------------------------------------------
    def challenge(self, *, skill_id: str, buyer: str, inputs: dict, now: str) -> dict:
        amount = self.quote(skill_id, inputs)
        s = self._state()
        s["counter"] += 1
        order_id = f"order-{s['counter']:04d}"
        nonce = hashlib.sha256(f"{self.seller_id}|{order_id}|{self.public_key}".encode()).hexdigest()[:32]
        requirement = {"scheme": "card-test", "network": "stripe-test-emulator", "amount_cents": amount, "currency": "usd",
                       "pay_to": self.seller_id, "resource": f"/skills/{skill_id}", "order_id": order_id, "nonce": nonce,
                       "expires_at": _stamp(_t(now) + CHALLENGE_TTL)}
        s["orders"][order_id] = {"order_id": order_id, "skill_id": skill_id, "buyer": buyer, "inputs": inputs, "amount_cents": amount,
                                 "nonce": nonce, "created_at": now, "expires_at": requirement["expires_at"], "status": "challenged",
                                 "payment_intent": None, "receipt": None}
        self._save(s)
        return {"status": 402, "payment_required": requirement}

    @staticmethod
    def pay(requirement: dict, *, payer, payment_method: str = "pm_card_visa", amount_cents: int | None = None) -> dict:
        """Buyer side: pay the requirement on the buyer's own rail client; the order is bound in the payment's metadata."""
        amount = requirement["amount_cents"] if amount_cents is None else amount_cents
        pi = payer.v1.payment_intents.create(
            params={"amount": amount, "currency": requirement["currency"], "payment_method": payment_method, "confirm": True,
                    "metadata": {"order_id": requirement["order_id"], "nonce": requirement["nonce"], "resource": requirement["resource"]}},
            options={"idempotency_key": f"x402-{requirement['order_id']}-{amount}"})
        return {"payment_intent": _intent(pi)["id"], "order_id": requirement["order_id"]}

    def _stray(self, s: dict, pi: dict, reason: str) -> None:
        """Money at the processor for nothing sold: booked as a refund due, never kept."""
        if pi["id"] in s["stray"] or pi["id"] in s["redeemed"]:
            return
        fee = int(pi.get("fee") or 0)
        accounting.post(self.books, date="stray", memo=f"{pi['id']} received for nothing sold: {reason}", currency="USD",
                        lines=[{"account": "cash:processor", "debit": pi["amount"] - fee}, {"account": "fees:processor", "debit": fee},
                               {"account": "payable:refunds_due", "credit": pi["amount"]}])
        s["stray"][pi["id"]] = {"amount_cents": pi["amount"], "reason": reason, "swept": None}
        s["booked_cents"] += pi["amount"]

    def redeem(self, payment: dict, *, grant: dict, now: str) -> dict:
        import stripe
        s = self._state()
        order = s["orders"].get(payment.get("order_id"))
        if order is None:
            raise CommerceError(f"unknown order {payment.get('order_id')!r}")
        if order["status"] != "challenged":
            raise CommerceError(f"{order['order_id']} is {order['status']}; a payment is redeemed once")
        if _t(now) > _t(order["expires_at"]):
            raise CommerceError(f"challenge for {order['order_id']} expired at {order['expires_at']}; ask again for a fresh price")
        if not grant or grant.get("grant_id") is None or grant.get("objective") != f"deliver:{order['order_id']}":
            raise CommerceError("delivery to another agent needs a Consequence Gate grant for this exact order")
        from foundry.systems.kernel_stack import grant_problems, run_under_grant
        effect = dict(action_class="business.deliver", objective=f"deliver:{order['order_id']}",
                      target=f"buyer:{order['order_id']}", payload={"order_id": order["order_id"]})
        problems = grant_problems(self.gate, grant, **effect)
        if problems:
            raise CommerceError("grant not honoured: " + "; ".join(problems))
        pi_id = str(payment.get("payment_intent"))
        if pi_id in s["redeemed"]:
            raise CommerceError(f"{pi_id} was already redeemed for {s['redeemed'][pi_id]}; replay refused")
        try:
            pi = _intent(self.rail.stripe.v1.payment_intents.retrieve(pi_id))
        except stripe.InvalidRequestError:
            raise CommerceError(f"the processor knows no payment {pi_id}; nothing to redeem") from None
        if pi.get("status") != "succeeded":
            raise CommerceError(f"{pi_id} is {pi.get('status')}, not succeeded")
        meta = pi.get("metadata") or {}
        if meta.get("order_id") != order["order_id"] or meta.get("nonce") != order["nonce"]:
            self._stray(s, pi, f"bound to {meta.get('order_id')}, presented for {order['order_id']}")
            self._save(s)
            raise CommerceError(f"{pi_id} is bound to another order; refused and booked for refund")
        if pi["amount"] != order["amount_cents"] or pi.get("currency") != "usd":
            self._stray(s, pi, f"paid {pi['amount']} for a {order['amount_cents']} quote")
            self._save(s)
            raise CommerceError(f"{pi_id} paid {pi['amount']} cents; the quote was {order['amount_cents']}; refused and booked for refund")
        s["redeemed"][pi_id] = order["order_id"]            # marked before delivering: a failed delivery cannot be replayed either
        fee = int(pi.get("fee") or 0)
        accounting.post(self.books, date="sale", memo=f"{order['order_id']} {order['skill_id']} paid by {pi_id}", currency="USD",
                        lines=[{"account": "cash:processor", "debit": pi["amount"] - fee}, {"account": "fees:processor", "debit": fee},
                               {"account": "revenue:services", "credit": pi["amount"]}])
        s["booked_cents"] += pi["amount"]
        order["payment_intent"] = pi_id
        made: dict = {}

        def deliver(_proposal):                 # runs only after the Gate admitted the grant and claimed dispatch
            try:
                made["body"] = self.handlers[order["skill_id"]](order["inputs"])
            except Exception as exc:            # nothing was delivered: a negative, receipted result
                made["error"] = exc
                return {"observed_outcome": "undeliverable", "result_class": "negative",
                        "output": {"error": str(exc)[:200]}, "validation_status": "self_reported"}
            made["address"] = cas.put(self.root / "deliveries", made["body"])
            return {"observed_outcome": "delivered", "result_class": "positive",
                    "output": {"delivery_receipt": made["address"]}, "validation_status": "self_reported"}

        record = run_under_grant(self.gate, grant, consequence_class="external_contact",
                                 evidence_refs=["sha256:" + hashlib.sha256(pi_id.encode()).hexdigest()],
                                 expected_outcome="delivered", executor=deliver, **effect)
        if record.state != "recorded" and (made or record.state == "reconciliation_required"):
            self._save(s)
            raise CommerceError(f"delivery of {order['order_id']} has an unknown outcome ({record.state}); "
                                "reconcile, never redeliver")
        if record.state != "recorded":
            made["error"] = CommerceError(f"the Consequence Gate refused the delivery ({record.state}): "
                                          f"{record.refusal_reasons}")
        try:
            if "error" in made:
                raise made["error"]
            deliverable = made["body"]
        except Exception as exc:
            refund = _intent(self.rail.stripe.v1.refunds.create(params={"payment_intent": pi_id, "amount": pi["amount"],
                                                                        "reason": "requested_by_customer", "metadata": {"why": str(exc)[:200]}}))
            accounting.post(self.books, date="refund", memo=f"{order['order_id']} undeliverable: {exc}", currency="USD",
                            lines=[{"account": "refunds", "debit": pi["amount"]}, {"account": "cash:processor", "credit": pi["amount"]}])
            order["status"] = "refunded"
            s["records"].append({"subject": order["skill_id"], "context": "agent-commerce", "verdict": "FAILED", "at": now,
                                 "evidence": [pi_id, refund["id"]], "incident": True})
            self._save(s)
            return {"status": 409, "order_id": order["order_id"], "refunded_cents": pi["amount"], "reason": str(exc)}
        address = made["address"]
        receipt = {"order_id": order["order_id"], "skill_id": order["skill_id"], "buyer": order["buyer"], "payment_intent": pi_id,
                   "amount_cents": pi["amount"], "delivery_receipt": address, "at": now}
        order.update(status="delivered", receipt=receipt, grant_id=grant["grant_id"], gate_receipt=record.receipt_hash)
        self._save(s)
        return {"status": 200, "receipt": receipt, "signature": self.key.sign(_canon(receipt)).hex(), "body": deliverable}

    @staticmethod
    def verify_receipt(public_key_hex: str, receipt: dict, signature: str) -> bool:
        try:
            Ed25519PublicKey.from_public_bytes(bytes.fromhex(public_key_hex)).verify(bytes.fromhex(signature), _canon(receipt))
            return True
        except (InvalidSignature, ValueError):
            return False

    # -- receipts into reputation --------------------------------------------------------------
    def confirm(self, order_id: str, *, verifier: str, method: str, verdict: str, now: str) -> dict:
        s = self._state()
        order = s["orders"].get(order_id)
        if order is None or order["status"] != "delivered":
            raise CommerceError(f"{order_id} has no delivery to confirm")
        if verifier == self.seller_id:
            raise CommerceError("the seller does not grade its own delivery")
        if method not in ACCEPTED_VERIFICATIONS:
            raise CommerceError(f"method must be one of {ACCEPTED_VERIFICATIONS}")
        if verdict not in ("VERIFIED", "REFUTED"):
            raise CommerceError("verdict is VERIFIED or REFUTED")
        s["records"].append({"subject": order["skill_id"], "context": "agent-commerce", "verdict": verdict, "at": now,
                             "evidence": [order["payment_intent"], order["receipt"]["delivery_receipt"], f"verifier:{verifier}:{method}"],
                             "incident": verdict == "REFUTED"})
        order["status"] = "confirmed" if verdict == "VERIFIED" else "disputed"
        self._save(s)
        return {"order_id": order_id, "status": order["status"]}

    def standing(self, *, now: str) -> dict:
        return reputation.score(self._state()["records"], now=now)

    # -- money hygiene -------------------------------------------------------------------------
    def sweep(self, *, reason: str) -> dict:
        """Refund every payment received for nothing sold (operator act on the rail)."""
        s = self._state()
        swept = []
        for pi_id, row in sorted(s["stray"].items()):
            if row["swept"]:
                continue
            refund = _intent(self.rail.stripe.v1.refunds.create(params={"payment_intent": pi_id, "amount": row["amount_cents"],
                                                                        "reason": "requested_by_customer", "metadata": {"why": reason}}))
            accounting.post(self.books, date="sweep", memo=f"{pi_id} returned: {reason}", currency="USD",
                            lines=[{"account": "payable:refunds_due", "debit": row["amount_cents"]},
                                   {"account": "cash:processor", "credit": row["amount_cents"]}])
            row["swept"] = refund["id"]
            swept.append(row["amount_cents"])
        self._save(s)
        return {"swept_cents": sum(swept), "payments": len(swept)}

    def reconcile(self, processor_balance: dict) -> dict:
        tb = accounting.trial_balance(self.books)
        b = tb["balances"]
        books = {"gross_cents": self._state()["booked_cents"], "fees_cents": b["fees:processor"],
                 "refunds_cents": b["refunds"] + sum(r["amount_cents"] for r in self._state()["stray"].values() if r["swept"]),
                 "net_cents": b["cash:processor"]}
        return {"books": books, "processor": processor_balance, "reconciled": books == processor_balance,
                "equation_holds": tb["equation_holds"], "refunds_due_cents": b["payable:refunds_due"]}


def deliver_grant(order_id: str, *, gate):
    """A single-use grant, issued by ``gate`` (the Gate that governs the storefront), for delivering this exact order
    to another agent (external contact). A grant from any other issuer is not honoured by that storefront."""
    from foundry.systems.kernel_stack import agent, proposal
    passports = gate.passports
    actor = agent(passports, capabilities=("business.deliver",), budget=0.0)
    p = proposal(actor.passport_id, action_class="business.deliver", requested_capability="business.deliver",
                 objective=f"deliver:{order_id}", consequence_class="external_contact", target=f"buyer:{order_id}",
                 estimated_cost_usd=0.0, payload={"order_id": order_id})
    return gate.grants.issue_single_action(proposal=p, policy_version="1.0.0")


def _store(root: Path) -> dict:
    p = Path(root) / "shop" / "store.json"
    return json.loads(p.read_text()) if p.exists() else {"card": None, "orders": {}, "records": []}


QUERY_OPS = {"card": lambda a, r: {"card": _store(r)["card"]},
             "orders": lambda a, r: {"orders": [{k: o[k] for k in ("order_id", "skill_id", "status", "amount_cents")}
                                                for _, o in sorted(_store(r)["orders"].items())]},
             "standing": lambda a, r: reputation.score(_store(r)["records"], now=a["now"])}
APPLY_OPS: dict = {}      # publishing an offer and delivering to another agent are gate-executed external acts, not free ops


def demo_skills() -> list[dict]:
    rule = "max(base_price * units * (0.8 if customer_tier == 2 else 1), cost_per_unit * units * 1.2)"
    return [{"id": "audit", "name": "Evidence audit", "description": "Audits a context packet and returns evidence records",
             "tags": ["audit", "evidence"], "consumes": ["context-packet"], "produces": ["evidence"], "latency_ms": 1500,
             "pricing": {"rule": rule, "constants": {"base_price": 49, "cost_per_unit": 30}, "buyer_variables": ["units", "customer_tier"],
                         "example": {"units": 1, "customer_tier": 1}}},
            {"id": "report", "name": "Outcome report", "description": "Compiles outcome records into a report",
             "tags": ["report"], "consumes": ["outcome"], "produces": ["evidence"], "latency_ms": 4000,
             "pricing": {"rule": "base_price * units", "constants": {"base_price": 120, "cost_per_unit": 0},
                         "buyer_variables": ["units", "customer_tier"], "example": {"units": 1, "customer_tier": 1}}}]


def exercise(root) -> dict:
    import stripe
    from foundry.systems import payments
    root = Path(root)
    t = {"publish": "2026-10-13T12:00:00Z", "buy": "2026-10-13T12:05:00Z", "late": "2026-10-13T13:30:00Z", "confirm": "2026-10-13T14:00:00Z"}
    from foundry.systems.kernel_stack import gate_stack
    issue = deliver_grant
    server, emulator = payments.start_emulator()
    try:
        base = f"http://127.0.0.1:{server.server_address[1]}"
        gate, _, gate_ledger = gate_stack()      # the Gate that governs the shop: only its grants deliver
        rail = payments.Rail(root / "rail", api_key="sk_test_emulator", base=base, gate=gate)
        buyer_rail = payments.client("sk_test_buyer", base)       # the buying agent's own test-mode client
        shop = Storefront(root / "shop", seller_id="organ:greg-shop", key_seed=bytes(32 * [31]), rail=rail, gate=gate)

        def grant_for(order_id):
            return issue(order_id, gate=gate)
        shop.handlers["audit"] = lambda inputs: _canon({"audited_units": inputs["units"], "finding": "no discrepancies"})

        def report(inputs):
            if inputs["units"] > 5:
                raise RuntimeError("capacity is 5 reports per order")
            return _canon({"reports": inputs["units"]})
        shop.handlers["report"] = report
        refusals = {}

        def refused(label, fn):
            try:
                fn()
                refusals[label] = None
            except (CommerceError, discovery.DiscoveryError) as exc:
                refusals[label] = str(exc)[:80]

        skills = demo_skills()
        unpriced = json.loads(json.dumps(skills[0])); unpriced["pricing"]["rule"] = "__import__('os').system('id')"
        refused("unpriced_skill", lambda: shop.publish_card(name="x", description="x", version="0", skills=[unpriced], now=t["publish"]))
        untyped = json.loads(json.dumps(skills[0])); untyped["produces"] = ["miracle-contract"]
        refused("untyped_contract", lambda: shop.publish_card(name="x", description="x", version="0", skills=[untyped], now=t["publish"]))
        published = shop.publish_card(name="GREG shop", description="Governed capabilities, priced by rule, settled through verification",
                                      version="1.0.0", skills=skills, now=t["publish"])
        found = discovery.discover(shop.directory, now=t["buy"], produces="evidence")["matches"]
        status, card = shop.card(now=t["buy"])
        proof = shop.proof()
        inputs = {"units": 10, "customer_tier": 2}
        seller_quote = shop.quote("audit", inputs)
        buyer_quote = Storefront.buyer_quote(card, "audit", inputs)
        refused("buyer_overrides_constant", lambda: Storefront.buyer_quote(card, "audit", {"units": 1, "customer_tier": 1, "base_price": 0}))

        # the happy path: 402 -> pay -> redeem under a delivery grant -> signed receipt -> buyer verifies -> reputation
        ch1 = shop.challenge(skill_id="audit", buyer="agent:acme", inputs=inputs, now=t["buy"])
        pay1 = Storefront.pay(ch1["payment_required"], payer=buyer_rail)
        refused("no_grant", lambda: shop.redeem(pay1, grant={}, now=t["buy"]))
        refused("grant_for_other_order", lambda: shop.redeem(pay1, grant=grant_for("order-9999"), now=t["buy"]))
        # A dict shaped like a grant is not authority (Mission G: redeem honoured any dict with an id and objective).
        order1 = ch1["payment_required"]["order_id"]
        refused("forged_grant", lambda: shop.redeem(pay1, grant={"grant_id": "forged", "objective": f"deliver:{order1}"},
                                                    now=t["buy"]))
        refused("grant_from_another_gate", lambda: shop.redeem(pay1, grant=issue(order1, gate=gate_stack()[0]), now=t["buy"]))
        served = shop.redeem(pay1, grant=grant_for(ch1["payment_required"]["order_id"]), now=t["buy"])
        refused("replay_same_payment", lambda: shop.redeem(pay1, grant=grant_for(ch1["payment_required"]["order_id"]), now=t["buy"]))
        ch7 = shop.challenge(skill_id="audit", buyer="agent:acme", inputs=inputs, now=t["buy"])
        refused("replay_under_new_order", lambda: shop.redeem({**pay1, "order_id": ch7["payment_required"]["order_id"]},
                                                              grant=grant_for(ch7["payment_required"]["order_id"]), now=t["buy"]))
        refused("confirm_by_seller", lambda: shop.confirm(ch1["payment_required"]["order_id"], verifier="organ:greg-shop",
                                                          method="external_receipt", verdict="VERIFIED", now=t["confirm"]))
        confirmed = shop.confirm(ch1["payment_required"]["order_id"], verifier="agent:acme", method="external_receipt",
                                 verdict="VERIFIED", now=t["confirm"])

        # a payment that does not match the quote, and a payment bound to a different order: refused and booked for refund
        ch2 = shop.challenge(skill_id="audit", buyer="agent:acme", inputs=inputs, now=t["buy"])
        pay2 = Storefront.pay(ch2["payment_required"], payer=buyer_rail, amount_cents=100)
        refused("underpaid", lambda: shop.redeem(pay2, grant=grant_for(ch2["payment_required"]["order_id"]), now=t["buy"]))
        refused("confirm_before_delivery", lambda: shop.confirm(ch2["payment_required"]["order_id"], verifier="agent:acme",
                                                                method="external_receipt", verdict="VERIFIED", now=t["confirm"]))
        ch3 = shop.challenge(skill_id="audit", buyer="agent:acme", inputs=inputs, now=t["buy"])
        ch4 = shop.challenge(skill_id="audit", buyer="agent:acme", inputs=inputs, now=t["buy"])
        pay3 = Storefront.pay(ch3["payment_required"], payer=buyer_rail)
        refused("payment_bound_to_other_order", lambda: shop.redeem({**pay3, "order_id": ch4["payment_required"]["order_id"]},
                                                                    grant=grant_for(ch4["payment_required"]["order_id"]), now=t["buy"]))
        refused("unknown_payment", lambda: shop.redeem({"payment_intent": "pi_999999", "order_id": ch4["payment_required"]["order_id"]},
                                                       grant=grant_for(ch4["payment_required"]["order_id"]), now=t["buy"]))
        refused("expired_challenge", lambda: shop.redeem({**pay3, "order_id": ch3["payment_required"]["order_id"]},
                                                         grant=grant_for(ch3["payment_required"]["order_id"]), now=t["late"]))
        try:
            Storefront.pay(ch4["payment_required"], payer=buyer_rail, payment_method="pm_card_chargeDeclined")
            declined_no_payment = False
        except stripe.CardError:
            declined_no_payment = True

        # an order the seller cannot fulfil: the verified payment is refunded and the skill takes the failure
        ch5 = shop.challenge(skill_id="report", buyer="agent:initech", inputs={"units": 9, "customer_tier": 1}, now=t["buy"])
        undeliverable = shop.redeem(Storefront.pay(ch5["payment_required"], payer=buyer_rail),
                                    grant=grant_for(ch5["payment_required"]["order_id"]), now=t["buy"])
        # a delivered but never-verified order earns the skill nothing
        ch6 = shop.challenge(skill_id="audit", buyer="agent:initech", inputs={"units": 2, "customer_tier": 1}, now=t["buy"])
        silent = shop.redeem(Storefront.pay(ch6["payment_required"], payer=buyer_rail), grant=grant_for(ch6["payment_required"]["order_id"]), now=t["buy"])

        swept = shop.sweep(reason="payments received for nothing sold")
        recon = shop.reconcile(emulator.balance())
        standing = shop.standing(now=t["confirm"])
        gate_receipts = {r.payload["grant_id"] for r in gate_ledger.by_type("receipt")}
    finally:
        server.shutdown()
        server.server_close()
    orders = shop._state()["orders"]
    return {"published": {"skills": published["skills"], "version": published["version"], "directory_sequence": published["directory_sequence"]},
            "discovered": [{"capability_id": m["capability_id"], "grants_access": m["grants_access"], "card_url": m["card_url"]} for m in found],
            "card_served": status == 200 and [s["id"] for s in card["skills"]] == ["audit", "report"],
            "card_proof": proof,
            "quote_cents": seller_quote, "buyer_recomputes_same_quote": buyer_quote == seller_quote,
            "challenge_status": ch1["status"], "payment_required": {k: ch1["payment_required"][k] for k in ("amount_cents", "currency", "scheme", "pay_to", "resource")},
            "redeemed": served["status"],
            "receipt_signature_verifies": Storefront.verify_receipt(shop.public_key, served["receipt"], served["signature"]),
            "forged_receipt_rejected": not Storefront.verify_receipt(shop.public_key, {**served["receipt"], "amount_cents": 1}, served["signature"]),
            "delivery_in_cas": cas.get(root / "shop" / "deliveries", served["receipt"]["delivery_receipt"]) == served["body"],
            "confirmed": confirmed["status"],
            "undeliverable": {"status": undeliverable["status"], "refunded_cents": undeliverable["refunded_cents"]},
            "silent_delivery": silent["status"],
            "declined_card_yields_no_payment": declined_no_payment,
            "standing": {r["subject"]: {"status": r["status"], "incidents": r["incidents"], "effective_outcomes": r["effective_outcomes"]}
                         for r in standing["subjects"]},
            "receipts_without_verification_earn_nothing": sum(1 for o in orders.values() if o["status"] in ("delivered", "confirmed")) == 2
            and sum(1 for r in shop._state()["records"] if r["verdict"] == "VERIFIED") == 1,
            "stray_swept": swept, "reconciled_to_processor": recon["reconciled"], "books_balance": recon["equation_holds"],
            "refunds_due_after_sweep": recon["refunds_due_cents"], "books_vs_processor": {"books": recon["books"], "processor": recon["processor"]},
            "every_delivery_receipted_by_the_gate": {o["grant_id"] for o in orders.values() if o.get("grant_id")} <= gate_receipts
            and all(o.get("gate_receipt") for o in orders.values() if o.get("grant_id")),
            "refusals": refusals}
