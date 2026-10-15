"""Register the Goal Gravity five-closure checks on the integration registry.

Same pattern as the commercial, advantage and developmental registries: the
core Kernel registry stays constitutionally stable and bounded organs extend
it through explicit registration. Registration verifies; it never activates.

Two lineages are registered side by side (ADR-GOAL-GRAVITY-002): the egregore
loop itself (``egregore-goal-gravity``, standalone ledgers) and its binding on
the GREG body (``greg-goal-gravity``: a founder-signed GOAL on the one body
ledger, executed only by founder-signed missions through the Consequence Gate).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import tempfile

from closure.framework import ClosureRegistry, ModuleClosures

MID = "m:gravity-closure"


class _World:
    """A real temporary body, a real Ed25519 test key, a signed mission and (optionally) a signed GOAL."""

    def __init__(self, *, goal: bool = True):
        from greg.body import Body, init_body
        from greg.founder import generate_founder_key, load_founder_key
        self.tmp = Path(tempfile.mkdtemp(prefix="greg-gravity-closure-"))
        (self.tmp / "data").mkdir()
        self.home = self.tmp / "body"
        self.config = init_body(self.home, read_roots=[str(self.tmp / "data")])
        public = generate_founder_key(self.tmp / "k.pem", None)
        self.key = load_founder_key(self.tmp / "k.pem", None)
        self.now = datetime.now(timezone.utc)
        self.Body = Body
        with Body(self.home, clock=self.clock) as body:
            body.enroll_founder(public)
        self.ws = self.home.resolve() / "workspace" / MID.replace(":", "_")
        self.command("MISSION", self.mission())
        self.tick()                                   # inbox order is by file name: the mission first
        if goal:
            self.command("GOAL", self.goal())
            self.tick()

    def clock(self):
        return self.now

    def command(self, kind, body, key=None):
        from greg.founder import sign_command
        env = sign_command(key or self.key, kind, body, body_id=self.config["body_id"], now=self.now)
        (self.home / "inbox" / f"{env['nonce']}.json").write_text(json.dumps(env))
        return env

    def tick(self, n: int = 1):
        out = []
        with self.Body(self.home, clock=self.clock) as body:
            for _ in range(n):
                out.append(body.tick())
                self.now += timedelta(seconds=1)
        return out

    def mission(self):
        def check(cid, name, text):
            return {"check_id": cid, "description": f"{name} contains {text}", "sensor": {
                "capability": "fs.read", "params": {"path": str(self.ws / name)}, "target": f"fs:{name}"},
                "predicate": {"op": "contains", "field": "text", "value": text}}

        def write(aid, name, text, advances):
            return {"action_id": aid, "capability": "fs.write", "params": {"relative_path": name, "content": text},
                    "target": f"workspace:{name}", "advances": advances, "rationale": f"write {name}"}
        return {"mission_id": MID, "founder_expression": "closure check for Goal Gravity on the body",
                "intended_effect": "the watched note stays healthy", "priority": 50,
                # d is on the ladder, so the mission itself runs w2 once the founder approves (a goal may only
                # ask for a move its mission pursues); while that decision is open a goal's pull still lets the
                # mission re-observe and repair c in its cone.
                "closure": {"kind": "infinite", "ladder": [["c"], ["d"]], "cadence_seconds": 86400},
                "success_checks": [check("c", "c.txt", "ok"), check("d", "d.txt", "shipped")],
                "strategies": [write("w", "c.txt", "ok", ["c"]), write("w2", "d.txt", "shipped", ["d"])],
                "light_cone": {"capabilities": ["fs.read", "fs.write"], "targets": ["fs:*", "workspace:c.txt"],
                               "max_consequence_class": "internal_write", "budget_usd": 0.0,
                               "horizon": (self.now + timedelta(days=2)).isoformat()}}

    def goal(self):
        from egregore.goals import GoalSpec, InterventionSpec, PlanNode, WakeCondition
        move = InterventionSpec.build(intervention_id="ship", description="write d.txt (outside the cone)",
                                      action_class="greg.fs.write", requested_capability="fs.write",
                                      consequence_class="internal_write", target="workspace:d.txt",
                                      expected_outcome="d.txt says shipped",
                                      payload={"mission_id": MID, "action_id": "w2"})
        spec = GoalSpec.build(
            founder_intent="keep the note healthy and ship d", desired_state="d shipped", priority=2,
            authority={"authorized_by": "x", "authorization_ref": "x", "legal_principal": "alfonso_lopez",
                       "max_consequence_class": "internal_write"}, time_horizon="weeks",
            plan=[PlanNode.build(node_id="ship", outcome="d shipped", gate="founder decision", sbm=f"{MID}.d",
                                 sbm_direction="eq", sbm_target=True, interventions=(move,))],
            wake_conditions=(WakeCondition.build(kind="subject", match=MID),
                             WakeCondition.build(kind="domain", match="ops")),
            review_cadence_seconds=7 * 86400)
        body = {k: v for k, v in spec.to_dict().items() if k not in ("goal_id", "authority", "execution_authority")}
        return {"goal": body, "missions": [MID], "max_consequence_class": "internal_write"}

    def ingest(self, channel, content):
        from greg import dataplane
        with self.Body(self.home, clock=self.clock) as body:
            dataplane.ingest(body.journal, source=f"feed://{channel}", content=content, channel=channel)

    def view(self, fn):
        with self.Body(self.home, clock=self.clock) as body:
            return fn(body)


def greg_goal_gravity_closures() -> ModuleClosures:
    """Five closures for the GREG-side binding (greg/goal_gravity.py) on a real body."""

    def technical():
        w = _World()
        w.tick(6)                                     # the mission repairs c in its cone, then holds for a day
        (w.ws / "c.txt").write_text("damaged")
        w.ingest("weather", "sunny")                 # noise: wakes nothing, pulls nothing
        noise = w.tick()[0]["gravity"]
        still_damaged = (w.ws / "c.txt").read_text() == "damaged"
        w.ingest("ops", "c.txt looks broken")        # relevant evidence: the goal wakes and pulls its mission
        woken = w.tick(2)[0]["gravity"]
        ok = (not noise.get("woken") and still_damaged and woken.get("missions_pulled") == [MID]
              and (w.ws / "c.txt").read_text() == "ok")
        return ok, "a signed goal sleeps through noise, wakes on relevant evidence and its mission repairs in cone"

    def authority():
        from egregore.contracts import ContractError
        from egregore.resources import ResourceGovernor
        from greg import goal_gravity
        source = Path(goal_gravity.__file__).read_text()
        forbidden = [s for s in ("ConsequenceGate(", "GrantIssuer", "issue_single_action", "EvidenceLedger(",
                                 'record("decision.requested"', 'record("mission.') if s in source]
        w = _World()
        phone = _device(w)
        w.command("GOAL", w.goal() | {"goal": {**w.goal()["goal"], "founder_intent": "from the phone"}}, key=phone)
        w.tick()

        def refuses(body):
            loop = goal_gravity.binding_for(body).loop
            try:
                loop.turn(trigger_id="closure-attack", now=w.now, grants={"g": {"grant_id": "g"}},
                          resources=ResourceGovernor(max_model_calls=1, max_estimated_cost_usd=0.01))
            except ContractError:
                return True
            return False
        rejected = w.view(lambda b: [e.payload["reason"] for e in b.journal.replay("command.rejected")])
        ok = not forbidden and w.view(refuses) and any("may not sign GOAL" in r for r in rejected)
        return ok, ("the binding holds no gate, grant or ledger; a body-hosted loop refuses grants; a device "
                    "key cannot sign a GOAL" if ok else f"forbidden={forbidden} rejected={rejected}")

    def evidence():
        from greg import goal_gravity
        w = _World()
        w.tick(4)
        closure = w.view(lambda b: goal_gravity.ledger_closure(b.journal))
        chain = w.view(lambda b: b.ledger.verify_chain()[0])
        ledgers = sorted(p.name for p in w.home.iterdir() if p.suffix == ".jsonl")
        ok = closure["ok"] and closure["grant_dispatches"] >= 1 and closure["founder_answers"] == 0 \
            and closure["founder_asks"] == 0 and chain and ledgers == ["ledger.jsonl"]
        return ok, ("every Gate dispatch traces to a verified founder MISSION; no unsigned founder answer; one "
                    f"verified chain ({closure['grant_dispatches']} dispatches)")

    def economic():
        idle = _World(goal=False)
        before = idle.view(lambda b: len(b.ledger.records))
        idle_results = idle.tick(3)
        w = _World()
        w.tick(6)
        counted = w.view(lambda b: len(b.ledger.records))
        dormant = w.tick()[0]["gravity"]
        ok = (all("gravity" not in r for r in idle_results)
              and idle.view(lambda b: not [r for r in b.ledger.records if r.record_type.startswith("egregore.")])
              and dormant["state"] == "DORMANT" and w.view(lambda b: len(b.ledger.records)) == counted)
        return ok, (f"no goal: no gravity work or record ({before} records); a dormant goal with no new evidence "
                    "appends nothing")

    def regenerative():
        from egregore.goals import GoalRegistry
        from greg import goal_gravity
        w = _World()
        gid = w.view(lambda b: GoalRegistry(ledger=b.ledger).goals()[0])
        w.command("GOAL_CONTROL", {"goal_id": gid, "kind": "stop_pushing", "value": True, "reason": "quiet"})
        w.tick()

        def forge_resume(body):
            goal_gravity.binding_for(body).loop.registry.record_preference(
                gid, kind="stop_pushing", value=False, actor="alfonso_lopez", reason="unsigned resume", now=w.now)
        w.view(forge_resume)
        w.ingest("ops", "wake up: is c.txt still ok?")      # about the goal: only the signed stop holds it
        result = w.tick()[0]["gravity"]
        status = w.view(lambda b: GoalRegistry(ledger=b.ledger).state(gid).status)
        ok = status == "paused" and gid not in result.get("woken", [])
        return ok, "a signed founder stop survives an unsigned resume; the stopped goal is not woken"

    return ModuleClosures(module="greg-goal-gravity",
                          checks={"technical": technical, "authority": authority, "evidence": evidence,
                                  "economic": economic, "regenerative": regenerative})


def _device(w: _World):
    from greg.founder import generate_founder_key, load_founder_key
    public = generate_founder_key(w.tmp / "phone.pem", None)
    w.command("DEVICE_ENROLL", {"public_key": public, "label": "phone", "kinds": ["DECISION", "GOAL_CONTROL"],
                                "expires_at": (w.now + timedelta(days=30)).isoformat().replace("+00:00", "Z")})
    w.tick()
    return load_founder_key(w.tmp / "phone.pem", None)


def register_goal_gravity_closures(registry: ClosureRegistry) -> ClosureRegistry:
    from egregore.closure import goal_gravity_closures, standing_cognition_closures
    registry.register(standing_cognition_closures())
    registry.register(goal_gravity_closures())
    registry.register(greg_goal_gravity_closures())
    return registry
