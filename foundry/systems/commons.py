"""#32 Owned community: member identity, posts and interaction history that UNIIMENTE holds and can export.

DALEOBANKS builds audience on rented platforms, where the relationship, the history and the export format belong
to the platform. This is the owned ground those relationships move to, recombined from systems already built
rather than a forum clone:

  identity    a member is an Ed25519 key the member holds; every post, reaction, report and moderation act is a
              signed message, so the history is attributable without accounts or passwords. A member may link a
              fediverse actor (#33) by having that actor name the member key in alsoKnownAs; the link is verified
              by fetching the actor, never by assertion
  rules       enforced in code: one signature per write, a posting rate limit per member, a report threshold
              that holds a member's posting until a moderator acts, roles (owner, moderator, member) with least
              privilege, and no deletion: a removed post becomes a tombstone that keeps its hash
  standing    helpful marks from other members are evidenced outcomes for #41; a member's standing is a lower
              bound over them, insufficient evidence says so, and self-marks count for nothing
  memberships tiers (free, supporter) are granted against a settled #38 charge, read from the rail's own store,
              never from a claim
  export      everything about one member (their posts, reactions, reports, moderation they received) or the
              whole community (members' public keys, posts, interactions, moderation log, tombstones) leaves as a
              bundle signed by the community key, verifiable by anyone holding the public key; a platform's
              follower export (Mastodon CSV) imports as invitations, so rented relationships can be walked over
  surface     each space's feed is published to the #31 site, so the owned destination serves it with provenance

Adoption note: Discourse and Ghost remain the mature alternatives for a hosted community; this is the substrate
that keeps identity, history and export under UNIIMENTE whichever front end sits on it.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
from datetime import datetime, timedelta
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

from foundry.systems import reputation
from foundry.systems.webserver import Site
from provenance.digests import compact_json_bytes as _canon, sha256_json as _sha

POST_LIMIT = 5
POST_WINDOW = timedelta(hours=1)
REPORT_HOLD = 3
ROLES = ("owner", "moderator", "member")
REACTIONS = ("like", "helpful", "boost")
TIERS = ("free", "supporter")


class CommunityError(ValueError):
    pass


def _t(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def fingerprint(public_hex: str) -> str:
    return "ed25519:" + hashlib.sha256(bytes.fromhex(public_hex)).hexdigest()[:24]


def sign(private_key: Ed25519PrivateKey, body: dict) -> dict:
    return {"body": body, "signature": private_key.sign(_canon(body)).hex()}


class Community:
    def __init__(self, root: Path, *, name: str, key_seed: bytes, owner_public_hex: str):
        from greg.founder import public_bytes
        self.root, self.name = Path(root), name
        self.root.mkdir(parents=True, exist_ok=True)
        self.key = Ed25519PrivateKey.from_private_bytes(key_seed)
        self.public_key = public_bytes(self.key.public_key()).hex()
        self.site = Site(self.root / "site", key_seed=key_seed)
        if not (self.root / "community.json").exists():
            s = {"name": name, "members": {}, "posts": {}, "interactions": [], "reports": [], "moderation": [], "invitations": {}, "seq": 0}
            self._save(s)
            self._admit(s, owner_public_hex, "owner", "founder", "1970-01-01T00:00:00Z")
            self._save(s)

    def _state(self) -> dict:
        return json.loads((self.root / "community.json").read_text())

    def _save(self, s: dict) -> None:
        (self.root / "community.tmp").write_text(json.dumps(s, sort_keys=True))
        (self.root / "community.tmp").replace(self.root / "community.json")

    # -- identity --------------------------------------------------------------------------------
    def _admit(self, s: dict, public_hex: str, role: str, display: str, at: str) -> str:
        member_id = fingerprint(public_hex)
        if member_id in s["members"]:
            raise CommunityError(f"{member_id} is already a member")
        s["members"][member_id] = {"member_id": member_id, "public_key": public_hex, "display": display, "role": role, "tier": "free",
                                   "joined_at": at, "held": None, "linked_actor": None, "invited_from": None}
        return member_id

    def join(self, signed: dict, *, now: str) -> dict:
        body = signed.get("body") or {}
        if set(body) != {"public_key", "display"}:
            raise CommunityError("a registration has exactly public_key and display")
        self._verify(body["public_key"], signed)
        s = self._state()
        member_id = self._admit(s, body["public_key"], "member", body["display"], now)
        for handle, inv in s["invitations"].items():
            if inv.get("claimed_by") is None and inv.get("claim_code") == body.get("display"):
                inv["claimed_by"] = member_id
                s["members"][member_id]["invited_from"] = handle
        self._save(s)
        return {"member_id": member_id, "role": "member"}

    def _verify(self, public_hex: str, signed: dict) -> dict:
        try:
            Ed25519PublicKey.from_public_bytes(bytes.fromhex(public_hex)).verify(bytes.fromhex(signed["signature"]), _canon(signed["body"]))
        except (InvalidSignature, ValueError, KeyError, TypeError):
            raise CommunityError("signature does not verify against the member's key") from None
        return signed["body"]

    def _member(self, s: dict, signed: dict, fields: set[str]) -> dict:
        body = signed.get("body") or {}
        if set(body) != fields:
            raise CommunityError(f"message fields must be exactly {sorted(fields)}")
        m = s["members"].get(body["member"])
        if m is None:
            raise CommunityError(f"{body['member']!r} is not a member")
        self._verify(m["public_key"], signed)
        return m

    def link_actor(self, signed: dict) -> dict:
        from foundry.systems.federation import Instance
        s = self._state()
        m = self._member(s, signed, {"member", "actor"})
        actor = Instance.fetch_actor(signed["body"]["actor"])
        if m["member_id"] not in actor.get("alsoKnownAs", []):
            raise CommunityError("the actor does not name this member key in alsoKnownAs; link refused")
        m["linked_actor"] = actor["id"]
        self._save(s)
        return {"member_id": m["member_id"], "linked_actor": actor["id"]}

    # -- posts and interactions ------------------------------------------------------------------
    def post(self, signed: dict, *, now: str) -> dict:
        s = self._state()
        m = self._member(s, signed, {"member", "space", "content", "in_reply_to"})
        if m["held"]:
            raise CommunityError(f"{m['member_id']} is held: {m['held']}")
        body = signed["body"]
        recent = [p for p in s["posts"].values() if p["member"] == m["member_id"] and _t(now) - _t(p["at"]) < POST_WINDOW]
        if len(recent) >= POST_LIMIT:
            raise CommunityError(f"rate limit: {POST_LIMIT} posts per {POST_WINDOW}")
        if body["in_reply_to"] and body["in_reply_to"] not in s["posts"]:
            raise CommunityError("reply to an unknown post")
        s["seq"] += 1
        post_id = f"post-{s['seq']:05d}"
        s["posts"][post_id] = {"post_id": post_id, "member": m["member_id"], "space": body["space"], "content": body["content"],
                               "in_reply_to": body["in_reply_to"], "at": now, "content_sha256": _sha(body["content"]),
                               "signature": signed["signature"], "removed": None}
        self._save(s)
        return {"post_id": post_id}

    def react(self, signed: dict, *, now: str) -> dict:
        s = self._state()
        m = self._member(s, signed, {"member", "post_id", "kind"})
        body = signed["body"]
        p = s["posts"].get(body["post_id"])
        if p is None or p["removed"]:
            raise CommunityError("no such post")
        if body["kind"] not in REACTIONS:
            raise CommunityError(f"kind must be one of {REACTIONS}")
        if p["member"] == m["member_id"]:
            raise CommunityError("a member does not mark their own post")
        if any(i["member"] == m["member_id"] and i["post_id"] == p["post_id"] and i["kind"] == body["kind"] for i in s["interactions"]):
            raise CommunityError("already reacted that way")
        s["interactions"].append({"member": m["member_id"], "post_id": p["post_id"], "kind": body["kind"], "at": now, "signature": signed["signature"]})
        self._save(s)
        return {"post_id": p["post_id"], "kind": body["kind"]}

    def report(self, signed: dict, *, now: str) -> dict:
        s = self._state()
        m = self._member(s, signed, {"member", "post_id", "reason"})
        body = signed["body"]
        p = s["posts"].get(body["post_id"])
        if p is None:
            raise CommunityError("no such post")
        if not body["reason"]:
            raise CommunityError("a report needs a reason")
        s["reports"].append({"by": m["member_id"], "post_id": p["post_id"], "reason": body["reason"], "at": now, "resolved": None})
        reporters = {r["by"] for r in s["reports"] if r["post_id"] in {q["post_id"] for q in s["posts"].values() if q["member"] == p["member"]}
                     and r["resolved"] is None}
        if len(reporters) >= REPORT_HOLD and not s["members"][p["member"]]["held"]:
            s["members"][p["member"]]["held"] = f"{len(reporters)} open reports; awaiting a moderator"
            s["moderation"].append({"act": "hold", "member": p["member"], "by": "rule:report-threshold", "at": now})
        self._save(s)
        return {"post_id": p["post_id"], "open_reports_on_author": len(reporters), "author_held": bool(s["members"][p["member"]]["held"])}

    def moderate(self, signed: dict, *, now: str) -> dict:
        s = self._state()
        mod = self._member(s, signed, {"member", "act", "target", "reason"})
        if mod["role"] not in ("owner", "moderator"):
            raise CommunityError("moderation needs the moderator or owner role")
        body = signed["body"]
        if body["act"] == "release":
            target = s["members"].get(body["target"])
            if target is None:
                raise CommunityError("no such member")
            target["held"] = None
            for r in s["reports"]:
                if r["resolved"] is None and s["posts"][r["post_id"]]["member"] == target["member_id"]:
                    r["resolved"] = {"by": mod["member_id"], "at": now, "outcome": "released"}
        elif body["act"] == "remove":
            p = s["posts"].get(body["target"])
            if p is None:
                raise CommunityError("no such post")
            p["removed"] = {"by": mod["member_id"], "at": now, "reason": body["reason"]}     # tombstone: hash and lineage stay
            p["content"] = None
        elif body["act"] == "promote":
            target = s["members"].get(body["target"])
            if target is None or mod["role"] != "owner":
                raise CommunityError("only the owner promotes, and only members")
            target["role"] = "moderator"
        else:
            raise CommunityError("act must be release, remove or promote")
        s["moderation"].append({"act": body["act"], "target": body["target"], "by": mod["member_id"], "reason": body["reason"], "at": now})
        self._save(s)
        return {"act": body["act"], "target": body["target"]}

    # -- memberships, standing, feed -------------------------------------------------------------
    def grant_tier(self, member_id: str, *, tier: str, rail_root: Path, case_id: str) -> dict:
        if tier not in TIERS:
            raise CommunityError(f"tier must be one of {TIERS}")
        rail = Path(rail_root) / "rail.json"
        charges = json.loads(rail.read_text())["charges"] if rail.exists() else {}
        charge = charges.get(case_id)
        if tier != "free" and not (charge and charge.get("status") == "settled" and charge.get("delivery_receipt")):
            raise CommunityError(f"no settled charge {case_id} on the rail; a tier is not granted on a claim")
        s = self._state()
        if member_id not in s["members"]:
            raise CommunityError("no such member")
        s["members"][member_id]["tier"] = tier
        s["members"][member_id]["tier_evidence"] = {"case_id": case_id, "intent": charge["intent"]} if tier != "free" else None
        self._save(s)
        return {"member_id": member_id, "tier": tier}

    def standing(self, *, now: str) -> dict:
        s = self._state()
        records = [{"subject": s["posts"][i["post_id"]]["member"], "context": "community:helpful", "verdict": "VERIFIED", "at": i["at"],
                    "evidence": [i["signature"][:16], i["post_id"]]} for i in s["interactions"] if i["kind"] == "helpful"]
        return reputation.score(records, now=now)

    def feed(self, space: str) -> list[dict]:
        s = self._state()
        return [{k: p[k] for k in ("post_id", "member", "content", "in_reply_to", "at", "content_sha256", "removed")}
                for p in sorted(s["posts"].values(), key=lambda p: p["post_id"]) if p["space"] == space]

    def publish_feed(self, space: str, *, now: str) -> dict:
        page = {"community": self.name, "space": space, "generated_at": now, "posts": self.feed(space)}
        return self.site.publish(f"/community/{space}.json", _canon(page), reason=f"feed {space} at {now}", evidence=[f"posts:{len(page['posts'])}"])

    # -- export and import -----------------------------------------------------------------------
    def _bundle(self, payload: dict, *, now: str) -> dict:
        bundle = {"community": self.name, "exported_at": now, "public_key": self.public_key, **payload}
        return {"bundle": bundle, "signature": self.key.sign(_canon(bundle)).hex()}

    @staticmethod
    def verify_export(export: dict) -> bool:
        try:
            Ed25519PublicKey.from_public_bytes(bytes.fromhex(export["bundle"]["public_key"])).verify(bytes.fromhex(export["signature"]),
                                                                                                    _canon(export["bundle"]))
            return True
        except (InvalidSignature, ValueError, KeyError, TypeError):
            return False

    def export_member(self, member_id: str, *, now: str) -> dict:
        s = self._state()
        if member_id not in s["members"]:
            raise CommunityError("no such member")
        mine = {p for p, x in s["posts"].items() if x["member"] == member_id}
        return self._bundle({"member": s["members"][member_id], "posts": [s["posts"][p] for p in sorted(mine)],
                             "interactions": [i for i in s["interactions"] if i["member"] == member_id],
                             "interactions_received": [i for i in s["interactions"] if i["post_id"] in mine],
                             "reports_made": [r for r in s["reports"] if r["by"] == member_id],
                             "reports_received": [r for r in s["reports"] if r["post_id"] in mine],
                             "moderation_received": [m for m in s["moderation"] if m.get("target") in mine or m.get("target") == member_id
                                                     or m.get("member") == member_id]}, now=now)

    def export_all(self, *, now: str) -> dict:
        s = self._state()
        return self._bundle({"members": [{k: m[k] for k in ("member_id", "public_key", "display", "role", "tier", "joined_at", "linked_actor")}
                                         for _, m in sorted(s["members"].items())],
                             "posts": [s["posts"][p] for p in sorted(s["posts"])], "interactions": s["interactions"], "reports": s["reports"],
                             "moderation": s["moderation"], "invitations": s["invitations"]}, now=now)

    def import_followers_csv(self, text: str, *, source: str, now: str) -> dict:
        """A rented platform's follower export (Mastodon: 'Account address' column) becomes invitations, never members."""
        rows = list(csv.DictReader(io.StringIO(text)))
        if not rows or "Account address" not in rows[0]:
            raise CommunityError("expected a Mastodon-style export with an 'Account address' column")
        s = self._state()
        added = 0
        for row in rows:
            handle = row["Account address"].strip().lstrip("@")
            if "@" not in handle or handle in s["invitations"]:
                continue
            s["invitations"][handle] = {"source": source, "imported_at": now, "claimed_by": None,
                                        "claim_code": "inv-" + hashlib.sha256(f"{self.name}|{handle}".encode()).hexdigest()[:12]}
            added += 1
        self._save(s)
        return {"invitations_added": added, "invitations_total": len(s["invitations"])}


def _store(root: Path) -> dict:
    p = Path(root) / "community" / "community.json"
    return json.loads(p.read_text()) if p.exists() else {"members": {}, "posts": {}, "interactions": [], "moderation": []}


QUERY_OPS = {"members": lambda a, r: {"members": [{k: m[k] for k in ("member_id", "display", "role", "tier", "held", "linked_actor")}
                                                  for _, m in sorted(_store(r)["members"].items())]},
             "feed": lambda a, r: {"posts": [{k: p[k] for k in ("post_id", "member", "content", "at", "removed")}
                                             for _, p in sorted(_store(r)["posts"].items()) if p["space"] == a["space"]]},
             "moderation": lambda a, r: {"moderation": _store(r)["moderation"]}}
APPLY_OPS: dict = {}      # joining, posting and moderating are signed member acts on an operated community, not free ops


def exercise(root) -> dict:
    from foundry.systems import federation
    from greg.founder import public_bytes
    root = Path(root)
    keys = {n: Ed25519PrivateKey.from_private_bytes(bytes(32 * [seed])) for n, seed in (("owner", 61), ("alice", 62), ("bob", 63), ("carol", 64), ("mallory", 65))}
    pub = {n: public_bytes(k.public_key()).hex() for n, k in keys.items()}
    t = lambda m: f"2026-10-13T{15 + m // 60:02d}:{m % 60:02d}:00Z"
    c = Community(root / "community", name="greg-commons", key_seed=bytes(32 * [60]), owner_public_hex=pub["owner"])
    refusals = {}

    def refused(label, fn):
        try:
            fn()
            refusals[label] = None
        except CommunityError as exc:
            refusals[label] = str(exc)[:80]

    reg = lambda who, display: sign(keys[who], {"public_key": pub[who], "display": display})
    ids = {"owner": fingerprint(pub["owner"])}
    for who in ("alice", "bob", "carol"):
        ids[who] = c.join(reg(who, who.title()), now=t(0))["member_id"]
    refused("join_twice", lambda: c.join(reg("alice", "Alice again"), now=t(1)))
    refused("join_forged", lambda: c.join({"body": {"public_key": pub["mallory"], "display": "M"}, "signature": "00" * 64}, now=t(1)))

    def msg(who, **body):
        return sign(keys[who], {"member": ids[who], **body})
    # a member links a fediverse actor that names the member key; one that does not is refused
    clock = {"now": t(2)}
    inst = federation.Instance(root / "fedi", clock=lambda: clock["now"]).serve()
    try:
        carol_actor = inst.create_actor("carol", also_known_as=[ids["carol"]])
        other_actor = inst.create_actor("someone")
        linked = c.link_actor(msg("carol", actor=carol_actor["id"]))
        refused("link_actor_without_alias", lambda: c.link_actor(msg("carol", actor=other_actor["id"])))
    finally:
        inst.shutdown()
    # posts, replies, reactions, the rate limit, self-marks and forgeries
    p1 = c.post(msg("alice", space="proof", content="Why receipts beat promises", in_reply_to=None), now=t(3))["post_id"]
    p2 = c.post(msg("bob", space="proof", content="Agreed; show the hash", in_reply_to=p1), now=t(4))["post_id"]
    for i in range(POST_LIMIT - 1):
        c.post(msg("alice", space="proof", content=f"note {i}", in_reply_to=None), now=t(5 + i))
    refused("rate_limit", lambda: c.post(msg("alice", space="proof", content="one more", in_reply_to=None), now=t(20)))
    after_window = c.post(msg("alice", space="proof", content="an hour later", in_reply_to=None), now=t(70))
    refused("reply_to_unknown", lambda: c.post(msg("bob", space="proof", content="?", in_reply_to="post-99999"), now=t(21)))
    refused("non_member_post", lambda: c.post({"body": {"member": fingerprint(pub["mallory"]), "space": "proof", "content": "x", "in_reply_to": None},
                                               "signature": "00" * 64}, now=t(21)))
    forged = sign(keys["mallory"], {"member": ids["alice"], "space": "proof", "content": "not alice", "in_reply_to": None})
    refused("forged_member_signature", lambda: c.post(forged, now=t(21)))
    for who in ("bob", "carol", "owner"):
        c.react(msg(who, post_id=p1, kind="helpful"), now=t(22))
    c.react(msg("alice", post_id=p2, kind="like"), now=t(23))
    refused("self_mark", lambda: c.react(msg("alice", post_id=p1, kind="helpful"), now=t(23)))
    refused("duplicate_reaction", lambda: c.react(msg("bob", post_id=p1, kind="helpful"), now=t(23)))
    # reports hold an author until a moderator acts; moderation is role-gated and leaves tombstones, not holes
    spam = c.post(msg("carol", space="proof", content="buy followers here", in_reply_to=None), now=t(24))["post_id"]
    reports = [c.report(msg(who, post_id=spam, reason="spam"), now=t(25)) for who in ("alice", "bob", "owner")]
    refused("post_while_held", lambda: c.post(msg("carol", space="proof", content="more", in_reply_to=None), now=t(26)))
    refused("moderate_without_role", lambda: c.moderate(msg("alice", act="remove", target=spam, reason="spam"), now=t(27)))
    c.moderate(msg("owner", act="promote", target=ids["bob"], reason="trusted"), now=t(27))
    refused("moderator_cannot_promote", lambda: c.moderate(msg("bob", act="promote", target=ids["alice"], reason="x"), now=t(27)))
    c.moderate(msg("bob", act="remove", target=spam, reason="spam"), now=t(28))
    c.moderate(msg("bob", act="release", target=ids["carol"], reason="first offence, post removed"), now=t(29))
    released = c.post(msg("carol", space="proof", content="understood", in_reply_to=None), now=t(30))
    refused("react_to_tombstone", lambda: c.react(msg("alice", post_id=spam, kind="like"), now=t(31)))
    # memberships only against a settled rail charge
    rail = root / "rail"; rail.mkdir()
    (rail / "rail.json").write_text(json.dumps({"charges": {"c-alice": {"status": "settled", "intent": "pi_000001", "amount_cents": 500,
                                                                        "delivery_receipt": "sha256:" + "ab" * 32},
                                                            "c-bob": {"status": "declined", "amount_cents": 500}}}))
    supporter = c.grant_tier(ids["alice"], tier="supporter", rail_root=rail, case_id="c-alice")
    refused("tier_on_declined_charge", lambda: c.grant_tier(ids["bob"], tier="supporter", rail_root=rail, case_id="c-bob"))
    refused("tier_on_claimed_charge", lambda: c.grant_tier(ids["bob"], tier="supporter", rail_root=rail, case_id="c-nope"))
    # standing, feed with provenance, exports, platform import
    published = c.publish_feed("proof", now=t(41))
    status, _, body = c.site.render("/community/proof.json", {}, now=0.0)
    alice_export = c.export_member(ids["alice"], now=t(42))
    everything = c.export_all(now=t(42))
    tampered = json.loads(json.dumps(everything)); tampered["bundle"]["members"].append({"member_id": "ed25519:forged", "role": "owner"})
    imported = c.import_followers_csv("Account address,Show boosts,Notify on new posts,Languages\n@dana@mastodon.example,true,false,\n"
                                      "erin@other.example,true,false,\nnot-a-handle,true,false,\n", source="mastodon-export", now=t(43))
    code = c._state()["invitations"]["dana@mastodon.example"]["claim_code"]
    dana_key = Ed25519PrivateKey.from_private_bytes(bytes(32 * [66]))
    dana = c.join(sign(dana_key, {"public_key": public_bytes(dana_key.public_key()).hex(), "display": code}), now=t(44))
    ids["dana"] = dana["member_id"]; keys["dana"] = dana_key
    c.react(msg("dana", post_id=p1, kind="helpful"), now=t(45))
    standing = c.standing(now=t(45))
    feed = c.feed("proof")
    tomb = next(p for p in feed if p["post_id"] == spam)
    return {"members": len(c._state()["members"]), "linked_actor_verified": linked["linked_actor"].endswith("/users/carol"),
            "posts": len(feed), "rate_limit_resets": after_window["post_id"].startswith("post-"),
            "reports": [r["open_reports_on_author"] for r in reports], "held_at_third_report": reports[-1]["author_held"],
            "released_can_post": released["post_id"].startswith("post-"),
            "tombstone_keeps_hash": tomb["content"] is None and tomb["content_sha256"] is not None and tomb["removed"]["by"] == ids["bob"],
            "standing": {r["subject"]: (r["status"], r["effective_outcomes"]) for r in standing["subjects"]},
            "alice_rated_by_four_helpful_marks": any(r["subject"] == ids["alice"] and r["status"] == "rated" for r in standing["subjects"]),
            "supporter_tier_from_settled_charge": supporter["tier"] == "supporter",
            "feed_served_with_provenance": status == 200 and json.loads(body)["posts"][0]["post_id"] == p1 and published["version"] == 1,
            "member_export": {"verifies": Community.verify_export(alice_export), "posts": len(alice_export["bundle"]["posts"]),
                              "received": len(alice_export["bundle"]["interactions_received"]), "reports_made": len(alice_export["bundle"]["reports_made"])},
            "full_export": {"verifies": Community.verify_export(everything), "tampered_rejected": not Community.verify_export(tampered),
                            "members": len(everything["bundle"]["members"]), "posts": len(everything["bundle"]["posts"]),
                            "moderation_acts": len(everything["bundle"]["moderation"]), "private_keys_absent": "private" not in json.dumps(everything)},
            "platform_import": {**imported, "invited_member_claimed": c._state()["members"][dana["member_id"]]["invited_from"] == "dana@mastodon.example"},
            "refusals": refusals}
