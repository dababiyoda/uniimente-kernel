"""#37 Marketplace: independent supply and demand, matched by sealed-bid auction, settled only through verification.

The rules are code, not guidance:

  identity    buyers, suppliers and verifiers are enrolled with Ed25519 keys; every request, bid,
              delivery and verification is a signed message; a party cannot bid on its own request
  sealed bids commit-then-reveal: until a request closes a bid is only a hash commitment; a bid after
              close, a reveal before close, or a reveal that does not match its commitment is refused;
              a commitment never revealed becomes an evidenced failure on that supplier's record
  award       Vickrey procurement (#40): the lowest eligible revealed bid wins and is paid the
              second-lowest eligible bid, capped at the buyer's ceiling (a sole bidder is paid the
              ceiling), so bidding true cost is the dominant strategy
  standing    reputation (#41) from evidenced outcomes only: a rated supplier must clear the buyer's
              minimum lower bound; an unrated newcomer can win only when the buyer sets no minimum,
              and only up to the market's newcomer ceiling
  settlement  nothing moves until the awarded supplier files a delivery receipt hash and a party
              other than the supplier records a verification by an accepted method; REFUTED means no
              charge and a failure on the supplier's record. Settlement charges the buyer on the #38
              rail under a Consequence Gate grant for that exact match and books the supplier's share
              as a payable and the market's take as fee revenue (#39)

Payouts to suppliers are a booked liability here; moving them to connected accounts (Stripe Connect)
needs the founder's account and real supply.

Synthetic is labelled synthetic: a party is synthetic unless enrolled with an identity observation from
an external system of record, a match is synthetic when either side is, and a settlement's money is what
the processor reports (test mode is synthetic). Nothing here is external verification of demand or money.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from business.commercial_loop import ACCEPTED_VERIFICATIONS, observation_problems
from foundry.systems import accounting, mechanism, reputation
from provenance.digests import compact_json_bytes as _canon

DEFAULT_RULES = {"newcomer_ceiling_cents": 25000, "take_bps": 500}
VERDICTS = ("VERIFIED", "REFUTED")


class MarketError(ValueError):
    pass


def _t(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def _load(root: Path) -> dict:
    p = Path(root) / "market.json"
    if p.exists():
        return json.loads(p.read_text())
    return {"rules": dict(DEFAULT_RULES), "parties": {}, "requests": {}, "bids": {}, "matches": {}, "records": []}


def _save(root: Path, state: dict) -> None:
    Path(root).mkdir(parents=True, exist_ok=True)
    tmp = Path(root) / "market.tmp"
    tmp.write_text(json.dumps(state, sort_keys=True, indent=1))
    tmp.replace(Path(root) / "market.json")


def open_market(root: Path, rules: dict | None = None) -> dict:
    state = _load(root)
    if state["requests"] and rules and rules != state["rules"]:
        raise MarketError("rules cannot change under open requests; close them first")
    for key, value in (rules or {}).items():
        if key not in DEFAULT_RULES or not isinstance(value, int) or value < 0:
            raise MarketError(f"rule {key!r} must be one of {sorted(DEFAULT_RULES)} with a non-negative integer")
        state["rules"][key] = value
    _save(root, state)
    return {"rules": state["rules"]}


def _party_mode(state: dict, party_id: str) -> str:
    """A party is synthetic unless it was enrolled with an external identity observation."""
    return (state.get("party_labels") or {}).get(party_id, {}).get("mode", "synthetic")


def enroll(root: Path, party_id: str, public_hex: str, *, identity_observation: dict | None = None) -> dict:
    state = _load(root)
    if state["parties"].get(party_id, public_hex) != public_hex:
        raise MarketError(f"{party_id} is already enrolled with a different key")
    if identity_observation is not None:
        problems = observation_problems(identity_observation, money=False)
        if problems:
            raise MarketError("identity observation refused: " + "; ".join(problems))
    state["parties"][party_id] = public_hex
    label = ({"mode": "observed", "identity_ref": identity_observation["record_ref"],
              "source": identity_observation["source"]} if identity_observation is not None else {"mode": "synthetic"})
    state.setdefault("party_labels", {})[party_id] = label
    _save(root, state)
    return {"party_id": party_id, "enrolled": True, "mode": label["mode"]}


def sign(private_key, body: dict) -> dict:
    return {"body": body, "signature": private_key.sign(_canon(body)).hex()}


def _signed_by(state: dict, signed: dict, party_field: str, fields: set[str]) -> dict:
    body = signed.get("body") or {}
    if set(body) != fields:
        raise MarketError(f"message fields must be exactly {sorted(fields)}")
    public_hex = state["parties"].get(body[party_field])
    if public_hex is None:
        raise MarketError(f"{body[party_field]!r} is not enrolled")
    try:
        Ed25519PublicKey.from_public_bytes(bytes.fromhex(public_hex)).verify(bytes.fromhex(signed["signature"]), _canon(body))
    except (InvalidSignature, ValueError, KeyError, TypeError):
        raise MarketError(f"signature does not verify against {body[party_field]}'s enrolled key") from None
    return body


def commitment(request_id: str, supplier: str, amount_cents: int, nonce: str) -> str:
    return hashlib.sha256(f"{request_id}|{supplier}|{int(amount_cents)}|{nonce}".encode()).hexdigest()


def post_request(root: Path, signed: dict) -> dict:
    from linker.linker import known_contracts
    state = _load(root)
    b = _signed_by(state, signed, "buyer", {"request_id", "buyer", "produces", "ceiling_cents", "closes_at",
                                            "verification_methods", "min_reputation"})
    if b["request_id"] in state["requests"]:
        raise MarketError(f"request {b['request_id']} already exists")
    if b["produces"] not in set(known_contracts()):
        raise MarketError(f"request names untyped contract {b['produces']!r}")
    if not isinstance(b["ceiling_cents"], int) or b["ceiling_cents"] <= 0:
        raise MarketError("ceiling must be a positive integer of cents")
    bad = sorted(set(b["verification_methods"]) - set(ACCEPTED_VERIFICATIONS))
    if bad or not b["verification_methods"]:
        raise MarketError(f"verification methods must be a non-empty subset of {ACCEPTED_VERIFICATIONS}; got {bad or 'none'}")
    if b["min_reputation"] is not None and not (0.0 <= float(b["min_reputation"]) <= 1.0):
        raise MarketError("min_reputation is a lower bound in [0, 1] or null")
    _t(b["closes_at"])
    state["requests"][b["request_id"]] = {**b, "status": "open"}
    _save(root, state)
    return {"request_id": b["request_id"], "status": "open"}


def commit_bid(root: Path, signed: dict, *, now: str) -> dict:
    state = _load(root)
    b = _signed_by(state, signed, "supplier", {"request_id", "supplier", "commitment"})
    req = state["requests"].get(b["request_id"])
    if req is None or req["status"] != "open":
        raise MarketError(f"request {b['request_id']} is not open")
    if _t(now) >= _t(req["closes_at"]):
        raise MarketError(f"request {b['request_id']} closed at {req['closes_at']}; bid refused")
    if b["supplier"] == req["buyer"]:
        raise MarketError("a buyer cannot bid on its own request (self-dealing)")
    bids = state["bids"].setdefault(b["request_id"], {})
    if b["supplier"] in bids:
        raise MarketError(f"{b['supplier']} already committed a bid on {b['request_id']}; one sealed bid per supplier")
    if not isinstance(b["commitment"], str) or len(b["commitment"]) != 64:
        raise MarketError("a commitment is the sha256 hex of request|supplier|amount|nonce")
    bids[b["supplier"]] = {"commitment": b["commitment"], "amount_cents": None, "revealed": False, "committed_at": now}
    _save(root, state)
    return {"request_id": b["request_id"], "supplier": b["supplier"], "sealed": True}


def reveal_bid(root: Path, signed: dict, *, now: str) -> dict:
    state = _load(root)
    b = _signed_by(state, signed, "supplier", {"request_id", "supplier", "amount_cents", "nonce"})
    req = state["requests"].get(b["request_id"])
    if req is None or req["status"] != "open":
        raise MarketError(f"request {b['request_id']} is not open")
    if _t(now) < _t(req["closes_at"]):
        raise MarketError(f"bids on {b['request_id']} stay sealed until {req['closes_at']}")
    bid = state["bids"].get(b["request_id"], {}).get(b["supplier"])
    if bid is None:
        raise MarketError(f"{b['supplier']} committed no bid on {b['request_id']}")
    if not isinstance(b["amount_cents"], int) or b["amount_cents"] <= 0:
        raise MarketError("a revealed amount is a positive integer of cents")
    if commitment(b["request_id"], b["supplier"], b["amount_cents"], str(b["nonce"])) != bid["commitment"]:
        raise MarketError(f"reveal by {b['supplier']} does not match its commitment; refused")
    bid.update(amount_cents=b["amount_cents"], revealed=True)
    _save(root, state)
    return {"request_id": b["request_id"], "supplier": b["supplier"], "amount_cents": b["amount_cents"]}


def _record(state: dict, *, subject: str, context: str, verdict: str, at: str, evidence: list[str], incident: bool) -> None:
    state["records"].append({"subject": subject, "context": context, "verdict": verdict, "at": at,
                             "evidence": evidence, "incident": incident})


def standing(root: Path, *, now: str) -> dict:
    return reputation.score(_load(root)["records"], now=now)


def award(root: Path, request_id: str, *, now: str) -> dict:
    state = _load(root)
    req = state["requests"].get(request_id)
    if req is None or req["status"] != "open":
        raise MarketError(f"request {request_id} is not open")
    if _t(now) < _t(req["closes_at"]):
        raise MarketError(f"request {request_id} is open until {req['closes_at']}; nothing to award yet")
    context = f"market:{req['produces']}"
    bids = state["bids"].get(request_id, {})
    no_reveal = sorted(s for s, b in bids.items() if not b["revealed"])
    for s in no_reveal:   # a sealed bid that never opened is a broken commitment, on the record with its evidence
        _record(state, subject=s, context=context, verdict="FAILED", at=now,
                evidence=[f"commitment:{bids[s]['commitment']}", f"request:{request_id}"], incident=False)
    rows = {r["subject"]: r for r in reputation.score(state["records"], now=now)["subjects"] if r["context"] == context}
    eligible, excluded = {}, {}
    for s, b in sorted(bids.items()):
        if not b["revealed"]:
            excluded[s] = "committed but never revealed"
            continue
        if b["amount_cents"] > req["ceiling_cents"]:
            excluded[s] = f"bid {b['amount_cents']} is over the buyer's ceiling {req['ceiling_cents']}"
            continue
        row = rows.get(s)
        if row is not None and row["status"] == "rated":
            if req["min_reputation"] is not None and row["lower_bound"] < req["min_reputation"]:
                excluded[s] = f"standing lower bound {row['lower_bound']} is below the buyer's minimum {req['min_reputation']}"
                continue
        elif req["min_reputation"] is not None:
            excluded[s] = "unrated; the buyer requires rated standing"
            continue
        elif b["amount_cents"] > state["rules"]["newcomer_ceiling_cents"]:
            excluded[s] = f"unrated newcomer above the newcomer ceiling {state['rules']['newcomer_ceiling_cents']}"
            continue
        eligible[s] = b["amount_cents"]
    if not eligible:
        req["status"] = "unfilled"
        _save(root, state)
        return {"request_id": request_id, "status": "unfilled", "excluded": excluded}
    result = mechanism.vickrey_procurement(eligible)
    price = min(result["paid"] if len(eligible) > 1 else req["ceiling_cents"], req["ceiling_cents"])
    match_id = f"match:{request_id}"
    synthetic = "synthetic" in (_party_mode(state, req["buyer"]), _party_mode(state, result["winner"]))
    state["matches"][match_id] = {"match_id": match_id, "request_id": request_id, "buyer": req["buyer"],
                                  "supplier": result["winner"], "price_cents": price, "produces": req["produces"],
                                  "status": "awarded", "awarded_at": now, "delivery_receipt": None,
                                  "verification": None, "settlement": None, "synthetic": synthetic}
    req["status"] = "awarded"
    _save(root, state)
    return {"request_id": request_id, "status": "awarded", "match_id": match_id, "winner": result["winner"],
            "price_cents": price, "winning_bid_cents": eligible[result["winner"]], "eligible": eligible, "excluded": excluded}


def deliver(root: Path, signed: dict) -> dict:
    state = _load(root)
    b = _signed_by(state, signed, "supplier", {"match_id", "supplier", "delivery_receipt"})
    m = state["matches"].get(b["match_id"])
    if m is None or m["status"] != "awarded":
        raise MarketError(f"{b['match_id']} is not awaiting delivery")
    if m["supplier"] != b["supplier"]:
        raise MarketError(f"{b['supplier']} is not the awarded supplier of {b['match_id']}")
    receipt = str(b["delivery_receipt"])
    if not (receipt.startswith("sha256:") and len(receipt) == 71):
        raise MarketError("a delivery receipt is the sha256 of what was delivered")
    m.update(status="delivered", delivery_receipt=receipt)
    _save(root, state)
    return {"match_id": b["match_id"], "status": "delivered"}


def verify(root: Path, signed: dict, *, now: str) -> dict:
    state = _load(root)
    b = _signed_by(state, signed, "verifier", {"match_id", "verifier", "method", "verdict"})
    m = state["matches"].get(b["match_id"])
    if m is None or m["status"] != "delivered":
        raise MarketError(f"{b['match_id']} has no delivery to verify")
    if b["verifier"] == m["supplier"]:
        raise MarketError("the supplier does not verify its own delivery")
    allowed = state["requests"][m["request_id"]]["verification_methods"]
    if b["method"] not in allowed:
        raise MarketError(f"method {b['method']!r} is not one the buyer accepts ({allowed})")
    if b["verdict"] not in VERDICTS:
        raise MarketError(f"verdict must be one of {VERDICTS}")
    _record(state, subject=m["supplier"], context=f"market:{m['produces']}", verdict=b["verdict"], at=now,
            evidence=[m["delivery_receipt"], f"verifier:{b['verifier']}:{b['method']}"], incident=b["verdict"] == "REFUTED")
    m["verification"] = {"verifier": b["verifier"], "method": b["method"], "verdict": b["verdict"], "at": now}
    m["status"] = "verified" if b["verdict"] == "VERIFIED" else "refuted"
    _save(root, state)
    return {"match_id": b["match_id"], "status": m["status"]}


def settle(root: Path, match_id: str, *, rail, grant: dict) -> dict:
    """Charge the buyer on the #38 rail and book the split; only a verified match can reach here."""
    state = _load(root)
    m = state["matches"].get(match_id)
    if m is None or m["status"] != "verified":
        raise MarketError(f"{match_id} is not verified; settlement refused "
                          f"(status {m['status'] if m else 'unknown'})")
    charge = rail.charge(case_id=match_id, customer=m["buyer"], amount_cents=m["price_cents"],
                         delivery_receipt=m["delivery_receipt"], grant=grant)
    if charge["status"] != "settled":
        m["settlement"] = {"status": charge["status"], "synthetic": True}
        _save(root, state)
        return {"match_id": match_id, **charge}
    take = m["price_cents"] * state["rules"]["take_bps"] // 10000
    accounting.open_account(rail.books, "payable:suppliers", "liability", "USD")
    accounting.open_account(rail.books, "revenue:marketplace_fee", "revenue", "USD")
    accounting.post(rail.books, date="settle", memo=f"{match_id}: {m['supplier']} payable, market take", currency="USD",
                    lines=[{"account": "revenue:services", "debit": m["price_cents"]},
                           {"account": "payable:suppliers", "credit": m["price_cents"] - take},
                           {"account": "revenue:marketplace_fee", "credit": take}])
    money = charge.get("money", "synthetic")
    m["settlement"] = {"status": "settled", "intent": charge["intent"], "supplier_payable_cents": m["price_cents"] - take,
                       "take_cents": take, "processor_fee_cents": charge["fee_cents"], "money": money,
                       "synthetic": m.get("synthetic", True) or money != "observed"}
    m["status"] = "settled"
    _save(root, state)
    return {"match_id": match_id, **m["settlement"]}


def board(root: Path) -> dict:
    state = _load(root)
    public = ("request_id", "buyer", "produces", "ceiling_cents", "closes_at", "verification_methods", "min_reputation", "status")
    return {"rules": state["rules"],
            "requests": [{k: r[k] for k in public} for _, r in sorted(state["requests"].items())],
            "matches": [{**{k: m[k] for k in ("match_id", "supplier", "price_cents", "status")},
                         "synthetic": m.get("synthetic", True)} for _, m in sorted(state["matches"].items())],
            "sealed_bids": {rid: len(b) for rid, b in sorted(state["bids"].items())}}


QUERY_OPS = {"board": lambda a, r: board(r), "standing": lambda a, r: standing(r, now=a["now"])}
APPLY_OPS = {"open_market": lambda a, r: open_market(r, a.get("rules")),
             "enroll": lambda a, r: enroll(r, a["party_id"], a["public_key"],
                                           identity_observation=a.get("identity_observation")),
             "post_request": lambda a, r: post_request(r, a["signed"]),
             "commit_bid": lambda a, r: commit_bid(r, a["signed"], now=a["now"]),
             "reveal_bid": lambda a, r: reveal_bid(r, a["signed"], now=a["now"]),
             "award": lambda a, r: award(r, a["request_id"], now=a["now"]),
             "deliver": lambda a, r: deliver(r, a["signed"]),
             "verify": lambda a, r: verify(r, a["signed"], now=a["now"])}
# settle() is gate-executed (financial consequence) like #38's charge, not a free op.


def exercise(root) -> dict:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from foundry.systems import payments
    from greg.founder import public_bytes
    root = Path(root)
    keys = {name: Ed25519PrivateKey.from_private_bytes(bytes(32 * [seed])) for name, seed in
            (("buyer", 21), ("alpha", 22), ("gamma", 23), ("delta", 24), ("newcomer", 25), ("auditor", 26), ("rogue", 27))}
    pid = {name: f"party:{name}" for name in keys}
    open_market(root, {"newcomer_ceiling_cents": 25000, "take_bps": 500})
    for name in ("buyer", "alpha", "gamma", "delta", "newcomer", "auditor"):
        enroll(root, pid[name], public_bytes(keys[name].public_key()).hex())
    refusals = {}

    def refused(label, fn):
        try:
            fn()
            refusals[label] = None
        except (MarketError, payments.PaymentError) as exc:
            refusals[label] = str(exc)[:80]

    def request(rid, ceiling, closes_at, *, min_rep=None, produces="evidence", methods=("external_receipt", "human_review"), by="buyer"):
        return post_request(root, sign(keys[by], {"request_id": rid, "buyer": pid[by], "produces": produces, "ceiling_cents": ceiling,
                                                   "closes_at": closes_at, "verification_methods": list(methods), "min_reputation": min_rep}))

    def bid(rid, who, amount, *, at, nonce="n"):
        return commit_bid(root, sign(keys[who], {"request_id": rid, "supplier": pid[who],
                                                  "commitment": commitment(rid, pid[who], amount, nonce)}), now=at)

    def reveal(rid, who, amount, *, at, nonce="n"):
        return reveal_bid(root, sign(keys[who], {"request_id": rid, "supplier": pid[who], "amount_cents": amount, "nonce": nonce}), now=at)

    def finish(mid, who, *, verdict, at, verifier="auditor", method="external_receipt"):
        receipt = "sha256:" + hashlib.sha256(f"{mid}:{who}".encode()).hexdigest()
        deliver(root, sign(keys[who], {"match_id": mid, "supplier": pid[who], "delivery_receipt": receipt}))
        return verify(root, sign(keys[verifier], {"match_id": mid, "verifier": pid[verifier], "method": method, "verdict": verdict}), now=at)

    # day 1: standing is earned on small jobs (newcomers may win only up to the newcomer ceiling)
    d1 = {"open": "2026-10-13T09:00:00Z", "close": "2026-10-13T10:00:00Z", "award": "2026-10-13T10:05:00Z", "verify": "2026-10-13T11:00:00Z"}
    day1 = []
    for who, verdicts in (("alpha", ["VERIFIED"] * 4), ("gamma", ["VERIFIED"] * 3 + ["REFUTED"])):
        for i, verdict in enumerate(verdicts):
            rid = f"r-{who}-{i}"
            request(rid, 20000, d1["close"])
            bid(rid, who, 18000, at=d1["open"])
            reveal(rid, who, 18000, at=d1["award"])
            awarded = award(root, rid, now=d1["award"])
            day1.append((rid, awarded["price_cents"], finish(awarded["match_id"], who, verdict=verdict, at=d1["verify"])["status"]))
    refused("settle_refuted", lambda: settle(root, "match:r-gamma-3", rail=None, grant={}))

    # day 2: a large request; the cheapest bidder is an unrated newcomer, one bidder never reveals
    d2 = {"open": "2026-10-14T09:00:00Z", "close": "2026-10-14T10:00:00Z", "award": "2026-10-14T10:05:00Z", "verify": "2026-10-14T12:00:00Z"}
    request("r-big", 100000, d2["close"])
    bid("r-big", "alpha", 80000, at=d2["open"]); bid("r-big", "gamma", 95000, at=d2["open"])
    bid("r-big", "newcomer", 60000, at=d2["open"]); bid("r-big", "delta", 70000, at=d2["open"])
    refused("self_dealing", lambda: bid("r-big", "buyer", 1000, at=d2["open"]))
    refused("duplicate_commit", lambda: bid("r-big", "alpha", 79000, at=d2["open"]))
    refused("reveal_before_close", lambda: reveal("r-big", "alpha", 80000, at="2026-10-14T09:30:00Z"))
    refused("bid_after_close", lambda: bid("r-big", "gamma", 50000, at=d2["award"], nonce="late"))
    refused("award_before_close", lambda: award(root, "r-big", now="2026-10-14T09:59:00Z"))
    refused("reveal_mismatch", lambda: reveal("r-big", "gamma", 90000, at=d2["award"]))
    for who, amount in (("alpha", 80000), ("gamma", 95000), ("newcomer", 60000)):
        reveal("r-big", who, amount, at=d2["award"])
    big = award(root, "r-big", now=d2["award"])
    refused("verify_before_delivery", lambda: verify(root, sign(keys["auditor"], {"match_id": big["match_id"], "verifier": pid["auditor"],
                                                                                  "method": "external_receipt", "verdict": "VERIFIED"}), now=d2["verify"]))
    refused("deliver_by_other", lambda: deliver(root, sign(keys["gamma"], {"match_id": big["match_id"], "supplier": pid["gamma"],
                                                                           "delivery_receipt": "sha256:" + "0" * 64})))
    refused("settle_before_verification", lambda: settle(root, big["match_id"], rail=None, grant={}))
    receipt = "sha256:" + hashlib.sha256(b"r-big deliverable").hexdigest()
    deliver(root, sign(keys["alpha"], {"match_id": big["match_id"], "supplier": pid["alpha"], "delivery_receipt": receipt}))
    refused("verify_by_supplier", lambda: verify(root, sign(keys["alpha"], {"match_id": big["match_id"], "verifier": pid["alpha"],
                                                                            "method": "external_receipt", "verdict": "VERIFIED"}), now=d2["verify"]))
    refused("unaccepted_method", lambda: verify(root, sign(keys["auditor"], {"match_id": big["match_id"], "verifier": pid["auditor"],
                                                                             "method": "independent_model", "verdict": "VERIFIED"}), now=d2["verify"]))
    verify(root, sign(keys["auditor"], {"match_id": big["match_id"], "verifier": pid["auditor"], "method": "human_review", "verdict": "VERIFIED"}),
           now=d2["verify"])

    # a strict buyer: rated standing required; gamma's refuted job keeps it below the floor
    request("r-strict", 50000, d2["close"], min_rep=0.6)
    bid("r-strict", "alpha", 40000, at=d2["open"]); bid("r-strict", "gamma", 30000, at=d2["open"]); bid("r-strict", "newcomer", 10000, at=d2["open"])
    for who, amount in (("alpha", 40000), ("gamma", 30000), ("newcomer", 10000)):
        reveal("r-strict", who, amount, at=d2["award"])
    strict = award(root, "r-strict", now=d2["award"])

    # messages the market refuses at the door
    refused("unenrolled_signer", lambda: request("r-rogue", 100, d2["close"], by="rogue"))
    forged = sign(keys["alpha"], {"request_id": "r-big", "supplier": pid["gamma"], "commitment": "0" * 64})
    refused("forged_signature", lambda: commit_bid(root, forged, now=d2["open"]))
    refused("untyped_contract", lambda: request("r-untyped", 100, d2["close"], produces="miracle-contract"))
    refused("unaccepted_verification", lambda: request("r-vibes", 100, d2["close"], methods=("vibes",)))
    refused("rules_under_open_requests", lambda: open_market(root, {"take_bps": 0}))

    # settlement: only the verified match, only through the rail, only under a grant for this exact match
    from foundry.systems.kernel_stack import gate_stack
    server, emulator = payments.start_emulator()
    try:
        gate = gate_stack()[0]                  # the Gate governing the rail: only its grants settle a match
        rail = payments.Rail(root / "rail", api_key="sk_test_emulator", base=f"http://127.0.0.1:{server.server_address[1]}",
                             gate=gate)
        refused("settle_grant_for_other_match", lambda: settle(root, big["match_id"], rail=rail,
                                                               grant=payments.charge_grant("match:r-other", big["price_cents"],
                                                                                           gate=gate)))
        refused("settle_forged_grant", lambda: settle(root, big["match_id"], rail=rail,
                                                      grant={"grant_id": "forged", "objective": f"charge:{big['match_id']}"}))
        settled = settle(root, big["match_id"], rail=rail, grant=payments.charge_grant(big["match_id"], big["price_cents"], gate=gate))
        refused("settle_twice", lambda: settle(root, big["match_id"], rail=rail,
                                               grant=payments.charge_grant(big["match_id"], big["price_cents"], gate=gate)))
        books = accounting.trial_balance(rail.books)
        processor = emulator.balance()
    finally:
        server.shutdown()
        server.server_close()
    rank = standing(root, now=d2["verify"])
    rows = {r["subject"]: (r["status"], r["lower_bound"], r["incidents"]) for r in rank["subjects"]}
    grid = [x * 5000.0 for x in range(1, 41)]
    return {"day1_small_jobs": day1,
            "big": {"winner": big["winner"], "winning_bid_cents": big["winning_bid_cents"], "price_cents": big["price_cents"],
                    "eligible": big["eligible"], "excluded": big["excluded"]},
            "cheapest_bid_did_not_win": big["winner"] != pid["newcomer"] and min(60000, 80000, 95000) == 60000,
            "paid_second_price_not_own_bid": big["price_cents"] == 95000,
            "no_reveal_on_record": any(r["subject"] == pid["delta"] and r["verdict"] == "FAILED" for r in _load(root)["records"]),
            "strict": {"winner": strict["winner"], "price_cents": strict["price_cents"], "excluded": strict["excluded"]},
            "sole_eligible_bidder_paid_ceiling": strict["price_cents"] == 50000,
            "standing": rows,
            "truthful_bidding_dominant": mechanism.bid_gain(80000.0, grid, grid) <= 0,
            "settlement": {k: settled[k] for k in ("status", "supplier_payable_cents", "take_cents", "processor_fee_cents",
                                                   "money", "synthetic")},
            "synthetic_labels": {"parties": sorted({_party_mode(_load(root), p) for p in _load(root)["parties"]}),
                                 "matches": sorted({m["synthetic"] for m in _load(root)["matches"].values()}),
                                 "rail_charges": sorted({c.get("money") for c in json.loads(
                                     (root / "rail" / "rail.json").read_text())["charges"].values()
                                     if c["status"] == "settled"})},
            "refuted_never_charged": "match:r-gamma-3" not in json.loads((root / "rail" / "rail.json").read_text())["charges"],
            "books": {"equation_holds": books["equation_holds"], "payable_to_suppliers": books["balances"]["payable:suppliers"],
                      "market_fee_revenue": books["balances"]["revenue:marketplace_fee"], "processor_net_cents": processor["net_cents"],
                      "cash_plus_reserve_matches_processor": books["balances"]["cash:processor"] + books["balances"]["reserve:disputes"]
                      == processor["net_cents"]},
            "refusals": refusals}
