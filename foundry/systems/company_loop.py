"""#49 Synthetic media company loop: identity, canon, production, distribution, products, community, finance and
performance memory, operated end to end in the sandbox as governed cycles.

A persona with an account is not a company. One cycle here is:

  charter      a MediaCompanyCharter (foundry/company.py) carrying the DALEOBANKS persona and the editorial
               constitution, validated and ratified through the Loom Ratifier by the operator; an unratified or
               edited charter does not speak
  compliance   structural, extracted from WMI's influencer company (src/services/influencer_company.py): the
               disclosure on every artifact, topic bounds, prohibited patterns, legal/medical escalation, kill
               criteria that pause the persona; a draft either passes or is refused with the reason recorded
  production   the #35 engine renders each node's artifact from the canon; the provenance manifest travels with
               the publish
  distribution every publish is CompanyFoundry.publish through the Consequence Gate (external_contact) under a
               single-use grant; the executor posts to the company's own actor on the owned #33 instance, so the
               canonical copy lives on owned ground and reaches followers' inboxes; the #50 territory routes
               visitors and records their journeys
  community    visitors who take the owned exit become #32 members: owned relationships, not followers
  products     a purchase is a #38 charge against a delivery receipt and a grant (test mode); revenue books in #39
  finance      the cycle's surplus runs the #55 treasury waterfall, versioned and reconciled to the cent
  memory       the cycle closes with a DistributionWindow (foundry/distribution.py: owned relationships and useful
               actions, never impressions), #34 attribution over the observed journeys, and a decision: continue,
               revise or kill. Two consecutive windows of growing impressions without behavior change trip the
               kill and the company stops publishing. Every cycle's lessons are appended to the company's memory,
               and the next cycle's plan is read from it

Everything external is sandboxed: the fediverse is three loopback instances, the rail is the #38 emulator, visitors
are scripted journeys. Nothing here contacts a real platform or moves real money.
"""
from __future__ import annotations

import json
from pathlib import Path

from foundry.company import REQUIRED_EDITORIAL_RULES, CompanyFoundry, FoundryError, MediaCompanyCharter
from foundry.distribution import DistributionLoop
from foundry.systems import attribution, federation, payments, rabbit_hole, treasury
from foundry.systems import commons as community
from foundry.systems import media_engine as media
from foundry.territory import ContentNode, TerritoryGraph

PROHIBITED_PATTERNS = ("guaranteed income", "risk-free", "act now", "limited time", "secret method", "you will get rich")
ESCALATION_TOPICS = {"legal_advice", "medical_advice", "regulated_product"}
PRODUCTION_COST_USD = 5.0


class CompanyLoopError(RuntimeError):
    pass


def _canon(v) -> bytes:
    return json.dumps(v, sort_keys=True, separators=(",", ":")).encode()


class CompanyLoop:
    def __init__(self, root: Path, *, clock, persona: dict, allowed_topics: list[str], kill_criteria: dict | None = None):
        from foundry.systems.kernel_stack import agent, gate_stack
        self.root, self.clock, self.persona = Path(root), clock, persona
        self.root.mkdir(parents=True, exist_ok=True)
        self.gate, self.passports, self.ledger = gate_stack(self.root / "ledger.jsonl")
        self.actor = agent(self.passports, capabilities=("media.publish",), budget=50.0)
        self.foundry = CompanyFoundry(self.ledger)
        self.allowed_topics = set(allowed_topics)
        self.kill_criteria = kill_criteria or {"max_complaint_rate": 0.05, "min_engagement_quality": 0.3}
        self.disclosure = "Synthetic identity: machine-authored under a human legal operator."
        self.canon = media.canon_from_persona(persona, palette={"bg": "#0b1f3a", "fg": "#f5f1e8", "accent": "#e3a72f"}, mark="GREG",
                                              editorial_rules=list(REQUIRED_EDITORIAL_RULES))
        self.engine = media.Engine(self.root / "media", key_seed=bytes(32 * [81]), canon=self.canon, clock=clock)
        self.territory_root = self.root / "territory"
        if not (self.territory_root / "territory.json").exists():
            rabbit_hole.demo_territory(self.territory_root)
        self.distribution = DistributionLoop(persona.get("handle", "company"), ledger=self.ledger)
        self.charter_hash = None
        self.instance = None
        self.actor_name = "company"
        self.commons = None
        self.rail = None
        self.paused = None

    # -- memory ----------------------------------------------------------------------------------
    def memory(self) -> dict:
        p = self.root / "memory.json"
        return json.loads(p.read_text()) if p.exists() else {"cycles": [], "kill": None, "compliance": []}

    def _remember(self, update) -> dict:
        m = self.memory()
        update(m)
        (self.root / "memory.json").write_text(json.dumps(m, indent=1, sort_keys=True))
        return m

    # -- charter and compliance ------------------------------------------------------------------
    def territory_graph(self) -> TerritoryGraph:
        """The #50 territory as the charter's governed TerritoryGraph (publish floor, staleness, owned exit)."""
        store = json.loads((self.territory_root / "territory.json").read_text())
        graph = TerritoryGraph("proof-territory", ledger=self.ledger)
        for nid, n in store["nodes"].items():
            graph.add(ContentNode(node_id=nid, question=n["question"], artifact="interactive", capability_taught=n["value_offered"],
                                  evidence_level=n["evidence_level"], evidence_refs=["sha256:" + "a" * 64], next_doors=list(n["next_doors"]),
                                  owned_exit=bool(n.get("owned_exit")), owned_ground=n.get("owned_ground", "")), entry=(nid == store["entry"]))
        return graph

    def charter(self, *, products: list[str]) -> str:
        charter = MediaCompanyCharter(name=f"{self.persona['handle']}-media", persona=self.persona["handle"], synthetic_disclosure=True,
                                      visual_canon=self.canon["palette"], editorial_rules=list(REQUIRED_EDITORIAL_RULES),
                                      narrative_world=self.persona.get("mission", ""), owned_hub="instance:company", subscriber_list="community:members",
                                      products=products, community="greg-commons")
        self.charter_hash = self.foundry.submit_charter(charter, self.territory_graph())
        return self.charter_hash

    def ratify(self, *, reason: str) -> dict:
        return self.foundry.ratifier.decide(self.charter_hash, ratified=True, reason=reason)

    def check_draft(self, *, topic: str, body: str) -> list[str]:
        notes = []
        if self.paused:
            raise CompanyLoopError(f"company paused: {self.paused}")
        if topic not in self.allowed_topics:
            raise CompanyLoopError(f"topic {topic!r} outside the persona's bounds {sorted(self.allowed_topics)}")
        if self.disclosure not in body:
            raise CompanyLoopError("draft lacks the synthetic-identity disclosure; disclosure is mandatory")
        for pattern in PROHIBITED_PATTERNS + rabbit_hole.PROHIBITED:
            if pattern in body.lower():
                raise CompanyLoopError(f"prohibited pattern in draft: {pattern!r}")
        if topic in ESCALATION_TOPICS:
            raise CompanyLoopError(f"topic {topic!r} forces escalation; it never publishes")
        notes.append("disclosure present")
        return notes

    # -- owned ground ------------------------------------------------------------------------------
    def open_ground(self, *, readers: list[federation.Instance]) -> dict:
        self.instance = federation.Instance(self.root / "instance", clock=self.clock).serve()
        actor = self.instance.create_actor(self.actor_name, summary=self.disclosure)
        for i, reader in enumerate(readers):
            reader.create_actor(f"reader{i}")
            reader.follow(f"reader{i}", actor["id"])
        self.commons = community.Community(self.root / "commons", name="greg-commons", key_seed=bytes(32 * [82]),
                                           owner_public_hex=self.engine.public_key)
        return {"actor": actor["id"], "followers": len(self.instance._state()["actors"][self.actor_name]["followers"])}

    def open_rail(self, base: str) -> None:
        self.rail = payments.Rail(self.root / "rail", api_key="sk_test_emulator", base=base)

    # -- one cycle -------------------------------------------------------------------------------
    def publish_node(self, node_id: str, *, topic: str) -> dict:
        store = json.loads((self.territory_root / "territory.json").read_text())
        node = store["nodes"][node_id]
        body = f"{node['question']} {node['value_offered']}. {self.disclosure}"
        self.check_draft(topic=topic, body=body)
        asset = self.engine.produce("interactive", {"title": node["question"], "lines": [node["value_offered"], "Evidence before claims."]})
        proposal = self.foundry.prepare_publish(self.charter_hash, node_id, actor=self.actor.passport_id, platform=f"activitypub:{self.instance.host}")
        grant = self.gate.grants.issue_single_action(proposal=proposal, policy_version="1.0.0")
        posted = {}

        def executor(p):
            posted.update(self.instance.publish(self.actor_name, f"{body} Asset {asset['asset']} (manifest {asset['manifest_address']})."))
            return {"observed_outcome": "artifact live on owned actor", "result_class": "positive",
                    "deliveries": sum(1 for d in posted["deliveries"].values() if d["delivered"])}
        rec = self.foundry.publish(self.charter_hash, node_id, gate=self.gate, actor=self.actor.passport_id, executor=executor,
                                   platform=f"activitypub:{self.instance.host}", standing_grant=grant)
        if not posted:
            raise CompanyLoopError(f"Consequence Gate {rec.state}: {node_id} was not published")
        return {"node": node_id, "gate_state": rec.state, "asset": asset["asset"], "deliveries": sum(1 for d in posted["deliveries"].values() if d["delivered"])}

    def _visitor(self, session: str, path: list[str], end: str, *, at: str, seed: int) -> dict:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        from greg.founder import public_bytes
        for nid in path:
            rabbit_hole.observe(self.territory_root, session=session, kind="consume", node_id=nid, at=at)
        if path and end in ("complete", "join", "buy"):
            rabbit_hole.observe(self.territory_root, session=session, kind="complete", node_id=path[-1], at=at)
        out = {"session": session, "end": end}
        if end == "join":
            rabbit_hole.observe(self.territory_root, session=session, kind="join", node_id=path[-1], at=at)
            key = Ed25519PrivateKey.from_private_bytes(bytes(32 * [seed]))
            out["member"] = self.commons.join(community.sign(key, {"public_key": public_bytes(key.public_key()).hex(), "display": session}), now=at)["member_id"]
        elif end == "buy":
            rabbit_hole.observe(self.territory_root, session=session, kind="buy", node_id=path[-1], at=at)
            case = f"{session}-audit"
            receipt = "sha256:" + __import__("hashlib").sha256(f"{case}:delivered".encode()).hexdigest()
            out["charge"] = self.rail.charge(case_id=case, customer=session, amount_cents=9000, delivery_receipt=receipt,
                                             grant=payments.charge_grant(case, 9000))["status"]
        elif end == "leave":
            rabbit_hole.observe(self.territory_root, session=session, kind="leave", node_id=path[-1], at=at)
        return out

    def cycle(self, *, cycle_id: str, publish: list[tuple[str, str]], visitors: list[tuple[str, list[str], str]], at: str) -> dict:
        if self.paused:
            raise CompanyLoopError(f"company paused: {self.paused}")
        window = self.distribution.open_window(cycle_id)
        published, refused = [], {}
        for node_id, topic in publish:
            try:
                published.append(self.publish_node(node_id, topic=topic))
            except (CompanyLoopError, FoundryError) as exc:
                refused[node_id] = str(exc)[:90]
        window.record_impressions(sum(p["deliveries"] for p in published))
        outcomes = [self._visitor(s, path, end, at=at, seed=100 + i) for i, (s, path, end) in enumerate(visitors)]
        for o in outcomes:
            window.record_qualified_visit()
            if o["end"] in ("complete", "join", "buy"):
                window.record_useful_action("completed_node")
            if o["end"] == "join":
                window.record_owned_relationship(); window.record_useful_action("joined_community")
            if o["end"] == "buy":
                window.record_owned_relationship(); window.record_useful_action("purchased")
        window.record_returning_visitor(sum(1 for o in outcomes if o["end"] != "leave"))
        closure = self.distribution.evaluate(window)
        revenue_cents = sum(9000 for o in outcomes if o.get("charge") == "settled")
        cost_usd = PRODUCTION_COST_USD * len(published)
        surplus_usd = revenue_cents / 100 - cost_usd
        allocation = None
        if surplus_usd > 0:
            from capital.treasury import RegenerativeTreasury
            from provenance.ledger import EvidenceLedger
            tiers = RegenerativeTreasury(EvidenceLedger("sha256:" + "0" * 64)).waterfall
            allocation = treasury.run(self.root / "treasury", surplus_usd, {tiers[0]: round(surplus_usd * 0.4, 2), tiers[1]: round(surplus_usd * 0.3, 2),
                                                                             tiers[2]: round(surplus_usd * 0.3, 2)})
        steps = json.loads((self.territory_root / "territory.json").read_text())["steps"]
        report = attribution.report([s for s in steps if s["session"] in {o["session"] for o in outcomes}])
        killed = self.distribution.kill_condition_met(consecutive=2)
        decision = "kill" if killed else ("continue" if closure.overall == "CLOSED" else "revise")
        record = {"cycle": cycle_id, "published": [p["node"] for p in published], "publish_refused": refused, "impressions": window.impressions,
                  "owned_relationships": window.owned_relationships, "useful_actions": dict(window.useful_actions),
                  "informed_return": round(window.informed_return(), 3), "closure": closure.overall, "revenue_cents": revenue_cents,
                  "surplus_usd": round(surplus_usd, 2), "treasury_policy_version": allocation["policy_version"] if allocation else None,
                  "treasury_reconciled": allocation["reconciled_to_the_cent"] if allocation else None,
                  "attribution": report["removal"]["attributed_conversions"], "decision": decision}
        if killed:
            self.paused = f"kill condition at {cycle_id}: impressions without behavior change for two windows"
            self._remember(lambda m: m.__setitem__("kill", {"cycle": cycle_id, "why": self.paused}))
        self._remember(lambda m: m["cycles"].append(record))
        return record

    def next_plan(self) -> dict:
        """What the next cycle should do, read from memory rather than from hope."""
        return plan_from_memory(self.memory())


def plan_from_memory(m: dict) -> dict:
    if m["kill"]:
        return {"action": "stopped", "why": m["kill"]["why"], "what_survives": "charter, canon, assets, community export, books, memory"}
    if not m["cycles"]:
        return {"action": "start", "why": "no cycle has run"}
    last = m["cycles"][-1]
    weakest = min(last["attribution"], key=lambda k: (last["attribution"][k], k)) if last["attribution"] else None
    if last["decision"] == "continue":
        return {"action": "continue", "why": f"informed return {last['informed_return']} with {last['owned_relationships']} owned relationships",
                "least_attributed_node": weakest}
    return {"action": "revise", "why": "impressions without owned relationships or behavior change", "least_attributed_node": weakest}


def _store(root: Path) -> dict:
    p = Path(root) / "company" / "memory.json"
    return json.loads(p.read_text()) if p.exists() else {"cycles": [], "kill": None, "compliance": []}


QUERY_OPS = {"memory": lambda a, r: _store(r), "plan": lambda a, r: plan_from_memory(_store(r))}
APPLY_OPS: dict = {}      # chartering, publishing and selling are gate-executed acts on an operated company, not free ops


def exercise(root) -> dict:
    root = Path(root)
    clock = {"now": "2026-10-13T17:00:00Z"}
    tick = lambda: clock["now"]
    loop = CompanyLoop(root / "company", clock=tick, persona=media.demo_persona(), allowed_topics=["proof", "payments", "operations"])
    readers = [federation.Instance(root / f"reader{i}", clock=tick).serve() for i in range(2)]
    server, emulator = payments.start_emulator()
    try:
        loop.open_rail(f"http://127.0.0.1:{server.server_address[1]}")
        ground = loop.open_ground(readers=readers)
        charter_hash = loop.charter(products=["operated delivery audit"])
        refusals = {}

        def refused(label, fn):
            try:
                fn()
                refusals[label] = None
            except (CompanyLoopError, FoundryError) as exc:
                refusals[label] = str(exc)[:80]
        refused("publish_before_ratification", lambda: loop.publish_node("why-proof", topic="proof"))
        loop.ratify(reason="charter reviewed by the operator in sandbox")
        refused("off_topic_draft", lambda: loop.check_draft(topic="crypto", body=f"x {loop.disclosure}"))
        refused("undisclosed_draft", lambda: loop.check_draft(topic="proof", body="no disclosure here"))
        refused("prohibited_pattern", lambda: loop.check_draft(topic="proof", body=f"risk-free returns {loop.disclosure}"))
        refused("escalation_topic", lambda: loop.check_draft(topic="legal_advice", body=f"x {loop.disclosure}"))
        loop.allowed_topics.add("legal_advice")
        refused("escalation_topic_even_if_allowed", lambda: loop.check_draft(topic="legal_advice", body=f"x {loop.disclosure}"))
        loop.allowed_topics.discard("legal_advice")
        # cycle 1: owned relationships and purchases follow the published nodes
        c1 = loop.cycle(cycle_id="w1", publish=[("why-proof", "proof"), ("pod-basics", "proof"), ("audit-kit", "operations"), ("weak", "proof")],
                        visitors=[("v1", ["why-proof", "pod-basics", "audit-kit", "offer"], "buy"), ("v2", ["why-proof", "pod-basics", "audit-kit", "offer"], "join"),
                                  ("v3", ["why-proof", "pod-basics"], "leave"), ("v4", ["why-proof", "pod-basics", "audit-kit", "offer"], "buy"),
                                  ("v5", ["why-proof", "disputes"], "leave"), ("v6", ["why-proof", "pod-basics", "audit-kit"], "complete")],
                        at="2026-10-13T17:10:00Z")
        plan_after_1 = loop.next_plan()
        # cycles 2 and 3: more impressions, nobody does anything; the kill condition trips on the second hollow window
        clock["now"] = "2026-10-14T17:00:00Z"
        c2 = loop.cycle(cycle_id="w2", publish=[("why-proof", "proof"), ("pod-basics", "proof"), ("audit-kit", "operations")],
                        visitors=[(f"h{i}", ["why-proof"], "leave") for i in range(8)], at="2026-10-14T17:10:00Z")
        clock["now"] = "2026-10-15T17:00:00Z"
        c3 = loop.cycle(cycle_id="w3", publish=[("why-proof", "proof"), ("pod-basics", "proof"), ("audit-kit", "operations")],
                        visitors=[(f"g{i}", ["why-proof", "disputes"], "leave") for i in range(10)], at="2026-10-15T17:10:00Z")
        refused("cycle_after_kill", lambda: loop.cycle(cycle_id="w4", publish=[("why-proof", "proof")], visitors=[], at="2026-10-16T17:00:00Z"))
        refused("publish_after_kill", lambda: loop.publish_node("why-proof", topic="proof"))
        plan_after_kill = loop.next_plan()
        outbox = loop.instance.read_remote_outbox(ground["actor"])
        reader_inbox = readers[0].inbox_stream("reader0")
        books = loop.rail.reconcile(emulator.balance())
        commons_export = loop.commons.export_all(now=clock["now"])
    finally:
        loop.instance.shutdown()
        for r in readers:
            r.shutdown()
        server.shutdown(); server.server_close()
    ledger_kinds = {}
    for rec in loop.ledger.by_type("event"):
        k = rec.payload.get("type", "?"); ledger_kinds[k] = ledger_kinds.get(k, 0) + 1
    memory = loop.memory()
    return {"charter_ratified": loop.foundry.is_operational(charter_hash), "followers_on_owned_actor": ground["followers"],
            "cycles": [{k: c[k] for k in ("cycle", "published", "impressions", "owned_relationships", "useful_actions", "informed_return", "closure",
                                          "revenue_cents", "surplus_usd", "treasury_policy_version", "treasury_reconciled", "decision")} for c in (c1, c2, c3)],
            "weak_node_refused_at_publish": "weak" in c1["publish_refused"] and "below publish floor" in c1["publish_refused"]["weak"],
            "cycle1_attribution": c1["attribution"], "plan_after_cycle1": plan_after_1, "plan_after_kill": plan_after_kill,
            "killed": memory["kill"] is not None and memory["kill"]["cycle"] == "w3", "memory_cycles": len(memory["cycles"]),
            "owned_copies_in_outbox": len(outbox), "reader_inbox_posts": len(reader_inbox),
            "every_post_discloses": all(loop.disclosure in a["activity"]["object"]["content"] for a in reader_inbox),
            "assets_with_provenance": len(loop.engine._index()), "community_members": len(commons_export["bundle"]["members"]),
            "community_export_verifies": community.Community.verify_export(commons_export),
            "books": {"reconciled_to_processor": books["reconciled"], "equation_holds": books["equation_holds"], "gross_cents": books["books"]["gross_cents"]},
            "ledger": {k: ledger_kinds.get(k, 0) for k in ("foundry.charter_submitted", "foundry.charter_ratified", "foundry.distribution_evaluated")},
            "refusals": refusals}
