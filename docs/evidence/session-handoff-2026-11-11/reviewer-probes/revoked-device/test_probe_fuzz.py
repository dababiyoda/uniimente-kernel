"""Reviewer probe: random interleavings of approve / revoke / re-enrol / restart / pause / drift on a real body,
checked against an oracle re-derived from the ledger alone.

Oracle (independent of greg.missions and greg.appraisal): a Gate grant marked ``founder_approved_scope`` at ledger
position g for scope S is legitimate only if some accepted DECISION approving a request of scope S, accepted at a < g,
was signed by the founder key, or by a device key with no ``device.revoked`` record at r with a < r < g.
Liveness: at the end the founder approves whatever is open and every note is written.
"""
import os
import random

import pytest

from greg.body import Body
from greg.founder import FounderAuthError
from greg.missions import MissionError
from tests.greg_fixtures import drop, mission, note_check, workspace, write_strategy
from tests.unit.test_greg_revoked_device_authority import World

MIDS = ("m:one", "m:two", "m:three")
DEVICES = ("phone", "laptop")
SEEDS = int(os.environ.get("RDR_FUZZ_SEEDS", "40"))
OPS = int(os.environ.get("RDR_FUZZ_OPS", "45"))


def ledger_events(body):
    return [(r.seq, r.payload) for r in body.ledger.by_type("event")]


def violations(body, founder_kid):
    rows = ledger_events(body)
    requests, accepted, revoked, grants = {}, [], [], []
    for seq, p in rows:
        t, d = p.get("type"), p.get("payload") or {}
        if t == "greg.decision.requested":
            requests[d.get("request_id")] = d
        elif t == "greg.command.accepted" and d.get("kind") == "DECISION":
            env = d.get("envelope") or {}
            body_ = env.get("body") or {}
            if body_.get("answer") == "approve":
                accepted.append((seq, env.get("founder_key_id"), body_.get("request_id")))
        elif t == "greg.device.revoked":
            revoked.append((seq, d.get("device_key_id")))
        elif t == "greg.authority.grant_issued" and p.get("founder_approved_scope"):
            grants.append((seq, p.get("scope_digest"), p.get("grant_id")))
    bad = []
    for g, scope, gid in grants:
        ok = False
        for a, kid, rid in accepted:
            if a >= g or (requests.get(rid) or {}).get("scope_digest") != scope:
                continue
            if kid == founder_kid or not any(k == kid and a < r < g for r, k in revoked):
                ok = True
                break
        if not ok:
            bad.append((g, scope, gid))
    return bad


def run(seed, tmp_path):
    rng = random.Random(seed)
    world = World(tmp_path)
    log = []
    body = world.body().__enter__()
    keys = {}
    try:
        notes = {}
        for mid in MIDS:
            note = workspace(world.home, mid) / "n.txt"
            notes[mid] = note
            body.apply(world.sign("MISSION", mission(
                mid, checks=[note_check("n", note, "ok")], strategies=[write_strategy("w", "n.txt", "ok", ["n"])],
                capabilities=["fs.read"], ceiling="read_only",
                closure={"kind": "infinite", "ladder": [["n"]], "cadence_seconds": 60})))
        for name in DEVICES:
            keys[name] = world.enroll(body, name, ("DECISION", "LIFECYCLE", "BODY_PAUSE", "BODY_RESUME"))
        founder_kid = body.apply.__self__.enrolled_keys() if False else None
        from greg.founder import key_id, public_bytes
        founder_kid = key_id(public_bytes(world.key.public_key()).hex())
        inbox_n = [0]

        def send(env, via_inbox):
            if via_inbox:
                inbox_n[0] += 1
                drop(world.home, env, f"{inbox_n[0]:05d}.json")
                return "DROPPED"
            try:
                body.apply(env)
                return "APPLIED"
            except (MissionError, FounderAuthError) as exc:
                return f"REFUSED {type(exc).__name__}: {str(exc)[:60]}"

        for step in range(OPS):
            op = rng.choice(["tick", "tick", "tick", "drift", "approve", "approve", "approve", "revoke", "enroll",
                             "restart", "pause", "resume", "mpause", "mresume"])
            via_inbox = rng.random() < 0.4
            if op == "tick":
                world.clock.advance(61)
                out = world.tick(body, rng.choice([1, 2]))
                log.append((step, op, [(c.get("status")) for c in (out or {}).get("commands", [])]))
            elif op == "drift":
                mid = rng.choice(MIDS)
                if notes[mid].exists():
                    notes[mid].unlink()
                log.append((step, op, mid))
            elif op == "approve":
                open_ = [r for r in body.engine.book.open_requests() if r["kind"] == "APPROVAL"]
                everything = list(body.engine.book.requests.values())
                pool = open_ if (open_ and rng.random() < 0.8) else [r for r in everything if r.get("kind") == "APPROVAL"]
                if not pool:
                    continue
                r = rng.choice(pool)
                who = rng.choice(["founder", "phone", "laptop", "phone", "laptop"])
                env = world.approve(r["request_id"], key=None if who == "founder" else keys[who],
                                    answer=rng.choice(["approve", "approve", "approve", "reject"]))
                log.append((step, op, who, r["request_id"][-6:], send(env, via_inbox)))
            elif op == "revoke":
                name = rng.choice(DEVICES)
                extra = {"suspected_compromise": True} if rng.random() < 0.4 else {}
                log.append((step, op, name, extra, send(world.revoke(name, **extra), via_inbox)))
            elif op == "enroll":
                name = rng.choice(DEVICES)
                env = world.sign("DEVICE_ENROLL", world.grant(name, ("DECISION", "LIFECYCLE", "BODY_PAUSE", "BODY_RESUME")))
                log.append((step, op, name, send(env, via_inbox)))
            elif op == "restart":
                body.__exit__(None, None, None)
                body = world.body().__enter__()
                log.append((step, op))
            elif op in ("pause", "resume"):
                who = rng.choice(["founder", "phone", "laptop"])
                env = world.sign("BODY_PAUSE" if op == "pause" else "BODY_RESUME", {},
                                 key=None if who == "founder" else keys[who])
                log.append((step, op, who, send(env, via_inbox)))
            elif op in ("mpause", "mresume"):
                who = rng.choice(["founder", "phone", "laptop"])
                env = world.sign("LIFECYCLE", {"mission_id": rng.choice(MIDS), "state": "PAUSED" if op == "mpause" else "ACTIVE",
                                               "reason": "fuzz"}, key=None if who == "founder" else keys[who])
                log.append((step, op, who, send(env, via_inbox)))
            bad = violations(body, founder_kid)
            assert not bad, (seed, step, bad, log[-12:])
            ok, why = body.ledger.verify_chain()
            assert ok, (seed, step, why)
        # liveness: nothing is stranded. The founder resumes everything and answers whatever is open.
        world.tick(body)
        try:
            body.apply(world.sign("BODY_RESUME", {}))
        except (MissionError, FounderAuthError):
            pass
        for mid in MIDS:
            try:
                body.apply(world.sign("LIFECYCLE", {"mission_id": mid, "state": "ACTIVE", "reason": "end"}))
            except (MissionError, FounderAuthError):
                pass
            if notes[mid].exists():
                notes[mid].unlink()
        for _ in range(8):
            world.clock.advance(61)
            world.tick(body, 2)
            for r in body.engine.book.open_requests():
                if r["kind"] == "APPROVAL":
                    body.apply(world.approve(r["request_id"]))
        missing = [mid for mid in MIDS if not notes[mid].exists()]
        book = body.engine.book
        state = {mid: (book.missions[mid].status, book.missions[mid].paused, book.missions[mid].blocker,
                       sorted(book.missions[mid].rejected_scopes)[:1], dict(book.missions[mid].failed)) for mid in missing}
        # a founder rejection legitimately ends a route; only a mission with no rejection and no ask is stranded
        stranded = {mid: s for mid, s in state.items() if not s[3] and not s[4]}
        assert not stranded, (seed, stranded, log[-15:])
        assert not violations(body, founder_kid)
        # the trail is written once per (request, revocation)
        trails = [(e.payload["request_id"], e.payload["voided_by"]["revocation_event"])
                  for e in body.journal.replay("decision.withdrawn") if e.payload.get("voided_by")]
        assert len(trails) == len(set(trails)), (seed, trails)
        # three folds agree
        from greg import goal_gravity
        from greg.missions import MissionBook
        full = MissionBook(body.journal)
        facts = goal_gravity.founder_facts(body.ledger).book
        body.engine.book.rebuild()
        for other in (full, facts):
            for mid in MIDS:
                assert other.missions[mid].approved_scopes == body.engine.book.missions[mid].approved_scopes, (seed, mid)
            assert set(other.voided) == set(body.engine.book.voided), seed
            assert other.consumed == body.engine.book.consumed, seed
    finally:
        body.__exit__(None, None, None)
    return log


@pytest.mark.parametrize("seed", range(SEEDS))
def test_fuzz(seed, tmp_path):
    run(seed, tmp_path)
