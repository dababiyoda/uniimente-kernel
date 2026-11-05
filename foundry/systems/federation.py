"""#33 Federated protocol: an owned ActivityPub instance with portable identity and follower export.

DALEOBANKS reaches the fediverse through a client stub against rented instances (services/mastodon_client.py):
it owns no actor, no inbox and no follower list. This is an instance on the protocol itself; the exercise runs
three of them on loopback and federates between them.

  identity    an actor document (/users/<name>) carrying an RSA public key, which is what the fediverse
              verifies today, and a WebFinger record (/.well-known/webfinger?resource=acct:name@host)
  signing     every delivery is an HTTP POST with a Digest header and an HTTP Signature over
              (request-target) host date digest, made with the actor's key. The receiving inbox fetches the
              sender's actor document, verifies the signature against the published key, checks the digest, the
              date window and that the activity's actor owns the key, and refuses anything else before it
              reads the body as a claim
  follow      Follow -> Accept handshake; the followers collection is the instance's own record, exportable
  publish     Create(Note) is appended to the outbox (an OrderedCollection) and delivered to every follower's
              inbox; a dead inbox is retried and then dead-lettered, never silently dropped
  read        the instance reads any remote actor's outbox and its own verified inbox stream; a Create from an
              actor it does not follow is refused rather than displayed
  portability the account exports as a bundle signed by its own key (actor, followers, following, outbox).
              Importing it on another instance republishes the actor with alsoKnownAs naming the old one; the
              old instance then marks movedTo and sends Move to every follower, whose instances verify the
              alias both ways before they follow the new actor and drop the old one. The follower list
              survives the move

Loopback only; nothing here reaches a real server. The private key never leaves the instance (the export
carries the public key and the signature, not the private key).
"""
from __future__ import annotations

import base64
import hashlib
import http.server
import json
import threading
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime, parsedate_to_datetime
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from provenance.digests import compact_json_bytes as _canon

CONTEXT = ["https://www.w3.org/ns/activitystreams", "https://w3id.org/security/v1"]
AS_TYPE = "application/activity+json"
DATE_WINDOW = timedelta(minutes=5)
DELIVERY_ATTEMPTS = 3


class FederationError(RuntimeError):
    pass


def _t(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def _digest(body: bytes) -> str:
    return "SHA-256=" + base64.b64encode(hashlib.sha256(body).digest()).decode()


def _http(method: str, url: str, *, body: bytes | None = None, headers: dict | None = None, timeout: float = 5) -> tuple[int, dict, bytes]:
    req = urllib.request.Request(url, data=body, method=method, headers={"Accept": AS_TYPE, **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, dict(resp.headers), resp.read()
    except urllib.error.HTTPError as exc:
        return exc.code, dict(exc.headers), exc.read()
    except (urllib.error.URLError, OSError) as exc:
        raise FederationError(f"{method} {url}: {exc}") from None


class Instance:
    def __init__(self, root: Path, *, clock):
        self.root, self.clock = Path(root), clock
        self.root.mkdir(parents=True, exist_ok=True)
        self.server = None
        self.base = None

    # -- state ---------------------------------------------------------------------------------
    def _state(self) -> dict:
        p = self.root / "instance.json"
        return json.loads(p.read_text()) if p.exists() else {"actors": {}, "journal": [], "dead_letters": []}

    def _save(self, s: dict) -> None:
        (self.root / "instance.tmp").write_text(json.dumps(s, sort_keys=True))
        (self.root / "instance.tmp").replace(self.root / "instance.json")

    def _journal(self, s: dict, kind: str, **fields) -> None:
        s["journal"].append({"at": self.clock(), "kind": kind, **fields})

    @property
    def host(self) -> str:
        return urllib.parse.urlsplit(self.base).netloc

    def actor_id(self, name: str) -> str:
        return f"{self.base}/users/{name}"

    # -- accounts ------------------------------------------------------------------------------
    def create_actor(self, name: str, *, summary: str = "", also_known_as: list[str] | None = None, key_pem: bytes | None = None) -> dict:
        s = self._state()
        if name in s["actors"]:
            raise FederationError(f"actor {name} exists")
        key = (serialization.load_pem_private_key(key_pem, password=None) if key_pem
               else rsa.generate_private_key(public_exponent=65537, key_size=2048))
        s["actors"][name] = {"name": name, "summary": summary,
                             "private_pem": key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                                              serialization.NoEncryption()).decode(),
                             "public_pem": key.public_key().public_bytes(serialization.Encoding.PEM,
                                                                         serialization.PublicFormat.SubjectPublicKeyInfo).decode(),
                             "followers": [], "following": [], "pending_follows": {}, "outbox": [], "inbox": [],
                             "also_known_as": list(also_known_as or []), "moved_to": None, "seq": 0}
        self._journal(s, "actor.created", actor=name)
        self._save(s)
        return self.actor_document(name)

    def actor_document(self, name: str) -> dict:
        a = self._state()["actors"][name]
        doc = {"@context": CONTEXT, "id": self.actor_id(name), "type": "Person", "preferredUsername": name, "summary": a["summary"],
               "inbox": f"{self.actor_id(name)}/inbox", "outbox": f"{self.actor_id(name)}/outbox",
               "followers": f"{self.actor_id(name)}/followers", "following": f"{self.actor_id(name)}/following",
               "publicKey": {"id": f"{self.actor_id(name)}#main-key", "owner": self.actor_id(name), "publicKeyPem": a["public_pem"]},
               "alsoKnownAs": a["also_known_as"]}
        if a["moved_to"]:
            doc["movedTo"] = a["moved_to"]
        return doc

    def _key(self, name: str):
        return serialization.load_pem_private_key(self._state()["actors"][name]["private_pem"].encode(), password=None)

    def _next_id(self, s: dict, name: str, kind: str) -> str:
        s["actors"][name]["seq"] += 1
        return f"{self.actor_id(name)}/{kind}/{s['actors'][name]['seq']}"

    # -- signing and delivery ------------------------------------------------------------------
    def _signed_headers(self, name: str, method: str, url: str, body: bytes) -> dict:
        parts = urllib.parse.urlsplit(url)
        date = format_datetime(_t(self.clock()).astimezone(timezone.utc), usegmt=True)
        digest = _digest(body)
        signing = "\n".join([f"(request-target): {method.lower()} {parts.path}", f"host: {parts.netloc}", f"date: {date}", f"digest: {digest}"])
        sig = self._key(name).sign(signing.encode(), padding.PKCS1v15(), hashes.SHA256())
        return {"Host": parts.netloc, "Date": date, "Digest": digest, "Content-Type": AS_TYPE,
                "Signature": f'keyId="{self.actor_id(name)}#main-key",algorithm="rsa-sha256",headers="(request-target) host date digest",'
                             f'signature="{base64.b64encode(sig).decode()}"'}

    def deliver(self, name: str, inbox: str, activity: dict) -> dict:
        body = _canon(activity)
        last = None
        for attempt in range(1, DELIVERY_ATTEMPTS + 1):
            try:
                status, _, out = _http("POST", inbox, body=body, headers=self._signed_headers(name, "POST", inbox, body))
                last = f"{status} {out[:80].decode(errors='replace')}"
                if status < 300:
                    s = self._state()                  # loaded after the round trip: the receiving side may have written our state meanwhile
                    self._journal(s, "delivered", actor=name, inbox=inbox, activity=activity["type"], attempt=attempt)
                    self._save(s)
                    return {"delivered": True, "attempts": attempt}
                if status < 500:
                    break                              # the inbox refused it; retrying cannot change that
            except FederationError as exc:
                last = str(exc)[:120]
        s = self._state()
        s["dead_letters"].append({"actor": name, "inbox": inbox, "activity": activity, "last_error": last, "attempts": attempt})
        self._journal(s, "dead_lettered", actor=name, inbox=inbox, activity=activity["type"], last_error=last)
        self._save(s)
        return {"delivered": False, "attempts": attempt, "last_error": last}

    @staticmethod
    def fetch_actor(url: str) -> dict:
        status, _, body = _http("GET", url.split("#", 1)[0])
        if status != 200:
            raise FederationError(f"actor {url} not fetchable ({status})")
        return json.loads(body)

    # -- inbound verification ------------------------------------------------------------------
    def verify_request(self, method: str, path: str, headers: dict, body: bytes) -> tuple[bool, str, dict | None]:
        sig_header = headers.get("Signature")
        if not sig_header:
            return False, "unsigned", None
        try:
            fields = dict(part.split("=", 1) for part in sig_header.split(","))
            fields = {k.strip(): v.strip().strip('"') for k, v in fields.items()}
            key_id, signed_headers, signature = fields["keyId"], fields["headers"].split(), base64.b64decode(fields["signature"])
        except (ValueError, KeyError):
            return False, "malformed signature header", None
        if {"(request-target)", "host", "date", "digest"} - set(signed_headers):
            return False, "signature must cover (request-target) host date digest", None
        if headers.get("Digest") != _digest(body):
            return False, "digest does not match body", None
        try:
            sent = parsedate_to_datetime(headers.get("Date", ""))
        except (TypeError, ValueError):
            return False, "missing or malformed Date", None
        if abs(_t(self.clock()) - sent) > DATE_WINDOW:
            return False, "date outside the acceptance window (replay or clock skew)", None
        try:
            actor = self.fetch_actor(key_id)
        except FederationError as exc:
            return False, f"cannot fetch signing key: {exc}"[:120], None
        if actor.get("publicKey", {}).get("id") != key_id:
            return False, "keyId is not the actor's published key", None
        signing = "\n".join(f"(request-target): {method.lower()} {path}" if h == "(request-target)" else f"{h}: {headers.get(h.title(), headers.get(h, ''))}"
                            for h in signed_headers)
        try:
            serialization.load_pem_public_key(actor["publicKey"]["publicKeyPem"].encode()).verify(signature, signing.encode(),
                                                                                                   padding.PKCS1v15(), hashes.SHA256())
        except (InvalidSignature, ValueError):
            return False, "signature does not verify against the published key", None
        return True, "verified", actor

    def inbox(self, name: str, headers: dict, body: bytes) -> tuple[int, dict]:
        s = self._state()
        if name not in s["actors"]:
            return 404, {"error": "no such actor"}
        ok, why, sender = self.verify_request("POST", f"/users/{name}/inbox", headers, body)
        if not ok:
            self._journal(s, "inbox.refused", actor=name, why=why)
            self._save(s)
            return 401, {"error": why}
        try:
            activity = json.loads(body)
        except ValueError:
            return 400, {"error": "body is not JSON"}
        if activity.get("actor") != sender["id"]:
            self._journal(s, "inbox.refused", actor=name, why="activity actor is not the signer")
            self._save(s)
            return 401, {"error": "activity actor is not the signer"}
        a = s["actors"][name]
        kind = activity.get("type")
        if kind == "Follow" and activity.get("object") == self.actor_id(name):
            if sender["id"] not in a["followers"]:
                a["followers"].append(sender["id"])
            self._journal(s, "follower.added", actor=name, follower=sender["id"])
            self._save(s)
            s2 = self._state()
            accept = {"@context": CONTEXT, "id": self._next_id(s2, name, "accept"), "type": "Accept", "actor": self.actor_id(name), "object": activity}
            self._save(s2)
            self.deliver(name, sender["inbox"], accept)
            return 202, {"accepted": True}
        if kind == "Accept" and isinstance(activity.get("object"), dict) and activity["object"].get("type") == "Follow":
            target = activity["object"].get("object")
            if a["pending_follows"].pop(target, None) is not None or target in a["following"]:
                if target not in a["following"]:
                    a["following"].append(target)
                self._journal(s, "following.confirmed", actor=name, target=target)
                self._save(s)
                return 202, {"accepted": True}
            return 400, {"error": "Accept for a Follow this actor never sent"}
        if kind == "Undo" and isinstance(activity.get("object"), dict) and activity["object"].get("type") == "Follow":
            if sender["id"] in a["followers"]:
                a["followers"].remove(sender["id"])
            self._journal(s, "follower.removed", actor=name, follower=sender["id"])
            self._save(s)
            return 202, {"accepted": True}
        if kind == "Create":
            if sender["id"] not in a["following"]:
                self._journal(s, "inbox.refused", actor=name, why="Create from an actor not followed")
                self._save(s)
                return 403, {"error": "not following this actor"}
            a["inbox"].append({"activity": activity, "verified_signer": sender["id"], "received_at": self.clock()})
            self._save(s)
            return 202, {"accepted": True}
        if kind == "Move" and activity.get("object") == sender["id"]:
            return self._handle_move(s, name, sender, activity)
        return 400, {"error": f"unsupported activity {kind!r}"}

    def _handle_move(self, s: dict, name: str, sender: dict, activity: dict) -> tuple[int, dict]:
        a = s["actors"][name]
        target_id = activity.get("target")
        if sender["id"] not in a["following"]:
            return 403, {"error": "not following the moving actor"}
        try:
            target = self.fetch_actor(target_id)
        except FederationError as exc:
            return 400, {"error": str(exc)[:120]}
        if sender["id"] not in target.get("alsoKnownAs", []) or sender.get("movedTo") != target_id:
            self._journal(s, "move.refused", actor=name, why="alias not confirmed on both actors")
            self._save(s)
            return 403, {"error": "move not confirmed by both actors (alsoKnownAs and movedTo)"}
        a["following"].remove(sender["id"])
        self._journal(s, "move.accepted", actor=name, old=sender["id"], new=target_id)
        self._save(s)
        self.follow(name, target_id)
        s2 = self._state()
        undo = {"@context": CONTEXT, "id": self._next_id(s2, name, "undo"), "type": "Undo", "actor": self.actor_id(name),
                "object": {"type": "Follow", "actor": self.actor_id(name), "object": sender["id"]}}
        self._save(s2)
        self.deliver(name, sender["inbox"], undo)
        return 202, {"accepted": True, "now_following": target_id}

    # -- client side ---------------------------------------------------------------------------
    def follow(self, name: str, remote_actor: str) -> dict:
        actor = self.fetch_actor(remote_actor)
        s = self._state()
        activity = {"@context": CONTEXT, "id": self._next_id(s, name, "follow"), "type": "Follow", "actor": self.actor_id(name), "object": actor["id"]}
        s["actors"][name]["pending_follows"][actor["id"]] = activity["id"]
        self._save(s)
        return self.deliver(name, actor["inbox"], activity)

    def publish(self, name: str, content: str) -> dict:
        s = self._state()
        a = s["actors"][name]
        if a["moved_to"]:
            raise FederationError(f"{name} has moved to {a['moved_to']}; publish there")
        note_id = self._next_id(s, name, "notes")
        create = {"@context": CONTEXT, "id": note_id + "/activity", "type": "Create", "actor": self.actor_id(name), "published": self.clock(),
                  "to": ["https://www.w3.org/ns/activitystreams#Public"], "cc": [f"{self.actor_id(name)}/followers"],
                  "object": {"id": note_id, "type": "Note", "attributedTo": self.actor_id(name), "content": content, "published": self.clock()}}
        a["outbox"].append(create)
        self._save(s)
        results = {}
        for follower in list(a["followers"]):
            try:
                inbox = self.fetch_actor(follower)["inbox"]
            except FederationError as exc:
                s2 = self._state()
                s2["dead_letters"].append({"actor": name, "inbox": follower, "activity": create, "last_error": str(exc)[:120], "attempts": 0})
                self._journal(s2, "dead_lettered", actor=name, inbox=follower, activity="Create", last_error=str(exc)[:120])
                self._save(s2)
                results[follower] = {"delivered": False, "attempts": 0}
                continue
            results[follower] = self.deliver(name, inbox, create)
        return {"note": note_id, "deliveries": results}

    def read_remote_outbox(self, actor_url: str) -> list[dict]:
        actor = self.fetch_actor(actor_url)
        status, _, body = _http("GET", actor["outbox"])
        if status != 200:
            raise FederationError(f"outbox {actor['outbox']} returned {status}")
        return json.loads(body)["orderedItems"]

    def inbox_stream(self, name: str) -> list[dict]:
        return self._state()["actors"][name]["inbox"]

    def collection(self, name: str, which: str) -> dict:
        a = self._state()["actors"][name]
        items = a[which]
        return {"@context": CONTEXT[0], "id": f"{self.actor_id(name)}/{which}", "type": "OrderedCollection", "totalItems": len(items),
                "orderedItems": items}

    # -- portability ---------------------------------------------------------------------------
    def export_account(self, name: str) -> dict:
        a = self._state()["actors"][name]
        bundle = {"actor": self.actor_document(name), "followers": list(a["followers"]), "following": list(a["following"]),
                  "outbox": list(a["outbox"]), "exported_at": self.clock()}
        sig = self._key(name).sign(_canon(bundle), padding.PKCS1v15(), hashes.SHA256())
        return {"bundle": bundle, "signature": base64.b64encode(sig).decode()}

    @staticmethod
    def verify_export(export: dict) -> bool:
        try:
            pem = export["bundle"]["actor"]["publicKey"]["publicKeyPem"].encode()
            serialization.load_pem_public_key(pem).verify(base64.b64decode(export["signature"]), _canon(export["bundle"]),
                                                          padding.PKCS1v15(), hashes.SHA256())
            return True
        except (InvalidSignature, ValueError, KeyError):
            return False

    def import_account(self, export: dict, *, name: str) -> dict:
        if not self.verify_export(export):
            raise FederationError("export bundle signature does not verify; refusing to import a forged account")
        old = export["bundle"]["actor"]
        doc = self.create_actor(name, summary=old.get("summary", ""), also_known_as=[old["id"]])
        s = self._state()
        s["actors"][name]["outbox"] = []          # history stays at the old actor's id; the new actor starts its own outbox
        self._journal(s, "account.imported", actor=name, from_actor=old["id"], followers_expected=len(export["bundle"]["followers"]))
        self._save(s)
        for target in export["bundle"]["following"]:
            try:
                self.follow(name, target)
            except FederationError:
                pass
        return doc

    def move(self, name: str, new_actor_id: str) -> dict:
        new = self.fetch_actor(new_actor_id)
        if self.actor_id(name) not in new.get("alsoKnownAs", []):
            raise FederationError("the new actor does not name this one in alsoKnownAs; move refused")
        s = self._state()
        a = s["actors"][name]
        a["moved_to"] = new_actor_id
        self._journal(s, "account.moved", actor=name, to=new_actor_id)
        self._save(s)
        results = {}
        for follower in list(a["followers"]):
            s2 = self._state()
            move = {"@context": CONTEXT, "id": self._next_id(s2, name, "move"), "type": "Move", "actor": self.actor_id(name),
                    "object": self.actor_id(name), "target": new_actor_id}
            self._save(s2)
            try:
                results[follower] = self.deliver(name, self.fetch_actor(follower)["inbox"], move)
            except FederationError as exc:
                results[follower] = {"delivered": False, "last_error": str(exc)[:120]}
        return {"moved_to": new_actor_id, "notified": results}

    # -- HTTP surface --------------------------------------------------------------------------
    def handle_get(self, path: str, query: dict) -> tuple[int, dict]:
        s = self._state()
        if path == "/.well-known/webfinger":
            resource = (query.get("resource") or [""])[0]
            if not resource.startswith("acct:") or "@" not in resource:
                return 400, {"error": "resource must be acct:name@host"}
            name, host = resource[5:].split("@", 1)
            if host != self.host or name not in s["actors"]:
                return 404, {"error": "no such account"}
            return 200, {"subject": resource, "aliases": [self.actor_id(name)],
                         "links": [{"rel": "self", "type": AS_TYPE, "href": self.actor_id(name)}]}
        parts = path.strip("/").split("/")
        if len(parts) >= 2 and parts[0] == "users" and parts[1] in s["actors"]:
            name = parts[1]
            if len(parts) == 2:
                return 200, self.actor_document(name)
            if parts[2] in ("outbox", "followers", "following"):
                return 200, self.collection(name, parts[2])
        return 404, {"error": "not found"}

    def serve(self) -> "Instance":
        instance = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def _send(self, status, payload):
                data = json.dumps(payload, sort_keys=True).encode()
                self.send_response(status)
                self.send_header("Content-Type", AS_TYPE)
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def do_GET(self):  # noqa: N802
                parts = urllib.parse.urlsplit(self.path)
                self._send(*instance.handle_get(parts.path, urllib.parse.parse_qs(parts.query)))

            def do_POST(self):  # noqa: N802
                parts = urllib.parse.urlsplit(self.path).path.strip("/").split("/")
                body = self.rfile.read(int(self.headers.get("Content-Length") or 0))
                if len(parts) == 3 and parts[0] == "users" and parts[2] == "inbox":
                    self._send(*instance.inbox(parts[1], dict(self.headers), body))
                else:
                    self._send(404, {"error": "not found"})

            def log_message(self, *a):
                pass

        self.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.base = f"http://127.0.0.1:{self.server.server_address[1]}"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        return self

    def shutdown(self) -> None:
        if self.server:
            self.server.shutdown()
            self.server.server_close()


def _store(root: Path) -> dict:
    p = Path(root) / "alpha" / "instance.json"
    return json.loads(p.read_text()) if p.exists() else {"actors": {}, "journal": [], "dead_letters": []}


QUERY_OPS = {"actors": lambda a, r: {"actors": [{"name": n, "followers": len(x["followers"]), "following": len(x["following"]),
                                                 "outbox": len(x["outbox"]), "moved_to": x["moved_to"]} for n, x in sorted(_store(r)["actors"].items())]},
             "journal": lambda a, r: {"journal": _store(r)["journal"]},
             "dead_letters": lambda a, r: {"dead_letters": [{k: d[k] for k in ("actor", "inbox", "attempts", "last_error")}
                                                            for d in _store(r)["dead_letters"]]}}
APPLY_OPS: dict = {}      # publishing to and following on the fediverse are external acts; a running instance is operated, not a free op


def exercise(root) -> dict:
    root = Path(root)
    clock = {"now": "2026-10-13T15:00:00Z"}
    tick = lambda: clock["now"]
    alpha, beta, gamma, dead = (Instance(root / n, clock=tick).serve() for n in ("alpha", "beta", "gamma", "dead"))
    try:
        greg = alpha.create_actor("greg", summary="GREG, an owned actor")
        beta.create_actor("reader")
        dead.create_actor("ghost")
        # discovery and the follow handshake
        wf_status, wf = _http("GET", f"{alpha.base}/.well-known/webfinger?resource=acct:greg@{alpha.host}")[0::2]
        unknown = _http("GET", f"{alpha.base}/.well-known/webfinger?resource=acct:nobody@{alpha.host}")[0]
        followed = beta.follow("reader", greg["id"])
        dead.follow("ghost", greg["id"])
        # publish: delivered to followers, readable from the outbox, verified in the inbox
        dead.shutdown()
        first = alpha.publish("greg", "First note from an owned instance.")
        remote_outbox = beta.read_remote_outbox(greg["id"])
        stream = beta.inbox_stream("reader")
        # attacks on the inbox, all refused before the body counts as anything
        refusals = {}
        body = _canon({"@context": CONTEXT, "id": f"{alpha.base}/users/greg/notes/x/activity", "type": "Create", "actor": greg["id"],
                       "object": {"type": "Note", "content": "forged"}})
        inbox = f"{beta.base}/users/reader/inbox"
        refusals["unsigned"] = _http("POST", inbox, body=body, headers={"Content-Type": AS_TYPE})[0]
        good = alpha._signed_headers("greg", "POST", inbox, body)
        refusals["digest_mismatch"] = _http("POST", inbox, body=body + b" ", headers=good)[0]
        gamma.create_actor("impostor")
        forged = gamma._signed_headers("impostor", "POST", inbox, body)
        forged["Signature"] = forged["Signature"].replace(f"{gamma.actor_id('impostor')}#main-key", f"{greg['id']}#main-key")
        refusals["forged_key_claim"] = _http("POST", inbox, body=body, headers=forged)[0]
        stranger_body = _canon({"@context": CONTEXT, "id": f"{gamma.base}/x", "type": "Create", "actor": gamma.actor_id("impostor"),
                                "object": {"type": "Note", "content": "unsolicited"}})
        refusals["create_from_unfollowed_actor"] = _http("POST", inbox, body=stranger_body,
                                                         headers=gamma._signed_headers("impostor", "POST", inbox, stranger_body))[0]
        clock["now"] = "2026-10-13T15:10:00Z"
        refusals["replayed_after_window"] = _http("POST", inbox, body=body, headers=good)[0]
        clock["now"] = "2026-10-13T15:11:00Z"
        unreachable = alpha._signed_headers("greg", "POST", inbox, body)
        unreachable["Signature"] = unreachable["Signature"].replace(alpha.base, "http://127.0.0.1:1")
        refusals["unfetchable_key"] = _http("POST", inbox, body=body, headers=unreachable)[0]
        # portability: export, verify, import elsewhere, move; the follower follows the new actor
        export = alpha.export_account("greg")
        tampered = json.loads(json.dumps(export)); tampered["bundle"]["followers"].append("https://evil.invalid/users/x")
        try:
            gamma.import_account(tampered, name="greg-forged")
            forged_import = "accepted"
        except FederationError as exc:
            forged_import = str(exc)[:60]
        try:
            alpha.move("greg", gamma.actor_id("impostor"))
            move_without_alias = "accepted"
        except FederationError as exc:
            move_without_alias = str(exc)[:60]
        gamma.import_account(export, name="greg")
        moved = alpha.move("greg", gamma.actor_id("greg"))
        try:
            alpha.publish("greg", "after the move")
            publish_after_move = "accepted"
        except FederationError as exc:
            publish_after_move = str(exc)[:40]
        second = gamma.publish("greg", "Same person, new instance.")
        beta_following = beta._state()["actors"]["reader"]["following"]
        stream_after = beta.inbox_stream("reader")
    finally:
        for i in (alpha, beta, gamma):
            i.shutdown()
    a_journal = [j["kind"] for j in alpha._state()["journal"]]
    return {"webfinger": {"status": wf_status, "self_link_is_actor": json.loads(wf)["links"][0]["href"] == greg["id"], "unknown": unknown},
            "follow": {"delivered": followed["delivered"], "alpha_followers": len(alpha._state()["actors"]["greg"]["followers"]),
                       "beta_following_confirmed": greg["id"] in beta._state()["actors"]["reader"]["following"] or gamma.actor_id("greg") in beta_following},
            "publish": {"delivered_to_reader": first["deliveries"][beta.actor_id("reader")]["delivered"],
                        "dead_inbox_dead_lettered": not first["deliveries"][dead.actor_id("ghost")]["delivered"],
                        "dead_letters": len(alpha._state()["dead_letters"]),
                        "remote_outbox_items": len(remote_outbox), "inbox_verified_signer": stream[0]["verified_signer"] == greg["id"],
                        "inbox_content": stream[0]["activity"]["object"]["content"]},
            "refusals": refusals,
            "portability": {"export_verifies": Instance.verify_export(export), "tampered_export_rejected": not Instance.verify_export(tampered),
                            "forged_import": forged_import, "move_without_alias": move_without_alias,
                            "new_actor_also_known_as_old": greg["id"] in gamma.actor_document("greg")["alsoKnownAs"],
                            "old_actor_moved_to_new": alpha.actor_document("greg").get("movedTo") == gamma.actor_id("greg"),
                            "move_delivered_to_follower": moved["notified"][beta.actor_id("reader")]["delivered"],
                            "follower_now_follows_new": gamma.actor_id("greg") in beta_following and greg["id"] not in beta_following,
                            "new_instance_followers": [f == beta.actor_id("reader") for f in gamma._state()["actors"]["greg"]["followers"]],
                            "old_instance_lost_follower": beta.actor_id("reader") not in alpha._state()["actors"]["greg"]["followers"],
                            "publish_after_move_refused": publish_after_move.startswith("greg has moved"),
                            "post_from_new_instance_reached_follower": second["deliveries"][beta.actor_id("reader")]["delivered"]
                            and stream_after[-1]["activity"]["object"]["content"] == "Same person, new instance."},
            "alpha_journal_kinds": sorted(set(a_journal)), "private_key_in_export": "private" in json.dumps(export).lower()}
