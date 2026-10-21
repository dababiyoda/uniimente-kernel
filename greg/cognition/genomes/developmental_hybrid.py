"""Layer 4 developmental intelligence, recombined: a central plan audited by the local repair rules.

Directive 2026-10-21 (``docs/intent/sources/MIND-MAXIMUM-CONTINUATION-2026-10-21-source.md``, section 7): where
existing mechanisms leave a verified deficit, extract their causal mechanisms, change their roles where justified,
recombine them and show that the interaction gives something neither component gives alone.

The verified deficit (``docs/evidence/greg-protected-evolution/2026-10-21-repair-1/pilot/README.md``, 640 review
items): the centralized replanner beats the local-rule genome ``develop_repair`` 467-173, 320-0 where the controller
is reliable, but the local rules win 173-147 where it is unreliable, and the replanner makes 50 of 640 FALSE
restoration claims, all from stale views (the local rules make 0). ``develop_repair``'s own failure notes name "a
hybrid (central plan plus this local fallback)" as the obvious stronger design, never evaluated. This is that hybrid.

Mechanisms, unchanged code, changed roles (composition only; no new simulation substrate):

* **Planner** (``developmental.repair_central_replanner``, unchanged role): the controller computes and pushes the
  forwarding field. The hybrid replays it step by step (the same function on the world script truncated at each
  step), so each step's installed pointers are exactly the ones the replanner would have pushed by then.
* **Auditor** (the local protocol's link-sensing / retraction test, new role): at the end of every step each
  functioning unit checks its own installed planner pointer against its own sensed links. A pointer into a failed
  unit or a blocked link is a discrepancy: the plan does not match the world the units sense. A fresh controller
  repairs within the step it learns of a failure, so it never leaves one; a stale or crashed controller does. The
  check needs no message and never reads the controller's declared condition (mode, view lag or crash time).
* **Standby** (``developmental._local_repair`` under ``REPAIR_DEFAULT_CONFIG``, new role): the local protocol stays
  dormant on its pre-damage soft state. At the first discrepancy, at step ``t0``, an activation flood wakes it and
  it runs on the remaining world script (failures up to ``t0`` are sensed at activation; later ones arrive on
  schedule). It is not run at all while the plan audits clean.
* **Owner rule.** At the budget's end the planner's field is used if it audits clean on every functioning unit;
  otherwise the local field is. A clean planner field is exact and its claims are true: every functioning unit's
  pointer is a live, unblocked link, the field is the shortest-path tree of a view whose failed set is a subset of
  the real one, so every chain strictly descends to a functioning sink in real-shortest hops.
* **Vouching** (new role for the local rules): a planner claim stands only for a functioning source (a failed
  source cannot vouch for itself). A local-field claim needs the local rules' expiry-bounded vouching AND an
  end-to-end probe: each hop's unit applies its own link test, the probe is retransmitted at most ``REPEATS`` times
  per hop under the declared message loss and acknowledged back; a probe that does not return withdraws the claim.

Accounting (unit-actions, the same score as ``develop_repair``): planner pushes and telemetry (the replanner's own
count over the whole budget; the controller keeps running), plus, only after a discrepancy, the activation flood
(one message per live link), the local protocol's messages and every probe transmission.

Ablations shipped for the emergence test (evaluation only, never routed): ``hybrid_naive_switch`` switches to the
local protocol only when the controller's heartbeat stops (crash), with no audit and no probe, and
``hybrid_vouch_only`` keeps the planner's field and filters its claims by the probe, with no fallback.

Everything is a pure, bounded computation of a declared simulation: no files, network, subprocesses or environment
access, and nothing here creates authority.
"""
from __future__ import annotations

import hashlib
import json
import random

from . import developmental as dv
from .contract import Executable, GenomeError, IntelligenceGenome, answer

LINEAGE = ("INTENT-20261007-POLYINTELLIGENCE-MIND-CONTINUATION", "INTENT-20261007-VERIFIED-POLYINTELLIGENCE-LIFT",
           "INTENT-20261021-MIND-MAXIMUM-CONTINUATION section 7 (convert missing capability into executable "
           "cognition; Mechanism Recombination Foundry)",
           "docs/evidence/greg-protected-evolution/2026-10-21-repair-1/pilot/README.md (the verified deficit)",
           "develop_repair 1.1.2 known failure mode: 'a hybrid (central plan plus this local fallback) is the "
           "obvious stronger design and is not evaluated here'")
VERSION = "1.0.0"
PROBE_SALT = "develop_repair_hybrid:probe"


# ------------------------------------------------------------------ composition primitives
def _truncated(data, t):
    """The world script cut at the end of step ``t``: what the controller has done by then (replay input)."""
    cut = dict(data)
    cut["steps"] = t + 1
    cut["events"] = [ev for ev in data.get("events", []) if ev["step"] <= t]
    return cut


def _dead_by(inp, t):
    """Units failed by the end of step ``t`` (what each unit's link sensing reports locally at that step)."""
    dead = set(inp["removed"])
    for step, cells in inp["events"].items():
        if step <= t:
            dead.update(cells)
    return dead


def _table(planner_output, inp):
    """index -> index pointer table of the planner's output (functioning or not)."""
    W, H = inp["W"], inp["H"]
    out = {}
    for k, v in planner_output["next_hop"].items():
        a, b = dv._parse_key(k, W, H), dv._parse_key(v, W, H)
        if a is not None and b is not None:
            out[a] = b
    return out


def _audit(table, inp, dead):
    """Functioning units whose installed pointer fails their own link test (a discrepancy each)."""
    H = inp["H"]
    bad = []
    for u, v in table.items():
        if u in dead:
            continue
        adjacent = abs(u // H - v // H) + abs(u % H - v % H) == 1
        if v in dead or not adjacent or (min(u, v), max(u, v)) in inp["blocked"]:
            bad.append(u)
    return sorted(bad)


def first_discrepancy(data, inp):
    """The first step whose installed planner pointers fail the units' own link test, or None (clean throughout)."""
    for t in range(inp["steps"]):
        dead = _dead_by(inp, t)
        if _audit(_table(dv.repair_central_replanner(_truncated(data, t)), inp), inp, dead):
            return t
    return None


def _derived_inputs(inp, t0):
    """The local protocol woken at ``t0`` from its dormant pre-damage state on the remaining world script."""
    out = dict(inp)
    out["removed"] = sorted(_dead_by(inp, t0))
    out["events"] = {s - t0: list(cells) for s, cells in inp["events"].items() if s > t0}
    out["steps"] = inp["steps"] - t0
    return out


def _activation_flood(inp, t0):
    """One message per live link at ``t0``: every functioning unit relays the wake-up once to its live neighbours."""
    dead = _dead_by(inp, t0)
    adj = dv._lattice(inp["W"], inp["H"])
    return sum(1 for u in range(inp["N"]) if u not in dead for v in adj[u]
               if v not in dead and (min(u, v), max(u, v)) not in inp["blocked"])


def _probe(inp, field, sources, dead):
    """End-to-end probes over ``field`` (index -> index). Each hop's unit applies its own link test; a hop is
    retransmitted at most REPEATS times under the declared message loss, and the sink's acknowledgement returns
    the same way. Returns (confirmed source indices, transmissions)."""
    H = inp["H"]
    sinks = set(inp["sinks"])
    rng = random.Random(f"{PROBE_SALT}:{inp['seed']}")
    confirmed, sent = [], 0

    def hop(u, v):
        nonlocal sent
        if v is None or v in dead or abs(u // H - v // H) + abs(u % H - v % H) != 1 \
                or (min(u, v), max(u, v)) in inp["blocked"]:
            return False                                         # the unit's own link test fails: nothing sent
        for _ in range(dv.REPEATS):
            sent += 1
            if inp["loss"] == 0.0 or rng.random() >= inp["loss"]:
                return True
        return False

    for s in sorted(sources):
        if s in dead:
            continue
        path, cur, ok = [s], s, True
        while cur not in sinks:
            nxt = field.get(cur)
            if nxt in path or len(path) > inp["N"] or not hop(cur, nxt):
                ok = False
                break
            path.append(nxt)
            cur = nxt
        if ok:
            for a, b in zip(reversed(path[1:]), reversed(path[:-1])):  # acknowledgement back to the source
                if not hop(a, b):
                    ok = False
                    break
        if ok:
            confirmed.append(s)
    return confirmed, sent


def _local_from(inp, t0):
    """Run the standby local protocol from ``t0``. Returns (field index -> index, vouched source indices, trace)."""
    sub = _derived_inputs(inp, t0)
    state, stats = dv._local_repair(sub, dv.REPAIR_DEFAULT_CONFIG)
    field = {u: state["nh"][u] for u in range(inp["N"]) if not state["dead"][u] and state["nh"][u] is not None}
    vouched = [u for u in inp["sources"]
               if dv._vouched(state, u, sub["steps"], inp["W"], inp["H"], dv.REPAIR_DEFAULT_CONFIG)]
    return field, vouched, stats["messages_per_step"]


def _keys(field, H):
    return {dv._key(u, H): dv._key(v, H) for u, v in sorted(field.items())}


# ------------------------------------------------------------------ the genome
def hybrid_solve(data, budget):
    inp = dv._repair_inputs(data)
    W, H, N, T = inp["W"], inp["H"], inp["N"], inp["steps"]
    if inp["loss"] > dv.MAX_LOSS:
        return answer(None, {"message_loss": inp["loss"], "validated_max": dv.MAX_LOSS}, status="ABSTAIN",
                      missing=["message loss above the local protocol's validated range"])
    removed = set(inp["removed"])
    if all(z in removed for z in inp["sinks"]) or all(s in removed for s in inp["sources"]):
        return answer(None, {"functioning_sinks": sum(z not in removed for z in inp["sinks"])}, status="ABSTAIN",
                      missing=["no functioning source or sink region: no target state to hold"])
    final_dead = _dead_by(inp, T)
    planner = dv.repair_central_replanner(data)
    planner_table = _table(planner, inp)
    planner_field = {u: v for u, v in planner_table.items() if u not in final_dead}
    planner_clean = not _audit(planner_table, inp, final_dead)
    t0 = first_discrepancy(data, inp)
    flood = local_actions = probe_actions = 0
    local_trace = []
    if t0 is None or planner_clean:
        owner = "planner"
        field = planner_field
        claimed_idx = [dv._parse_key(k, W, H) for k in planner["claimed"]]
        claimed_idx = sorted(u for u in claimed_idx if u is not None and u not in final_dead)
    else:
        owner = "local"
    if t0 is not None:
        flood = _activation_flood(inp, t0)
        local_field, vouched, local_trace = _local_from(inp, t0)
        local_actions = sum(local_trace)
        if owner == "local":
            field = local_field
            claimed_idx, probe_actions = _probe(inp, field, vouched, final_dead)
    actions = planner["actions"] + flood + local_actions + probe_actions
    next_hop = _keys(field, H)
    claimed = sorted(dv._key(u, H) for u in claimed_idx)
    certificate = {
        "mechanism": "central plan audited every step by each unit's own link test; dormant local protocol "
                     "activated at the first discrepancy; owner = planner if its final field audits clean, else "
                     "the local field with claims vouched by the local rules and confirmed by end-to-end probes",
        "seed": inp["seed"], "message_loss": inp["loss"], "steps": T, "owner": owner,
        "first_discrepancy_step": t0, "planner_final_clean": planner_clean,
        "actions_breakdown": {"planner": planner["actions"], "activation_flood": flood, "local": local_actions,
                              "probe": probe_actions},
        "local_messages_per_step": local_trace, "vouched_sources": len(claimed),
        "field_digest": "sha256:" + hashlib.sha256(json.dumps(next_hop, sort_keys=True).encode()).hexdigest(),
        "external_effects": 0, "authorization_state": "SIMULATED_NOT_AUTHORIZED",
        "limits": "simulation of the declared world script; the audit never reads the controller's declared "
                  "condition; a claim is a clean-audited plan chain or a probe-confirmed local route"}
    return answer({"next_hop": next_hop, "claimed": claimed, "actions": actions, "steps": T}, certificate)


def hybrid_verify(data, output, certificate):
    """Outcome-based and stricter than ``repair_verify``: rebuild the realized final topology from the world script,
    check every pointer and follow every claim on it (independent of the solver's state), and re-derive the
    accounting by replaying the planner, the units' audit, the activation step and the standby run (these replays
    reuse the composition primitives, so they bind the accounting; they are not an independent implementation)."""
    inp = dv._repair_inputs(data)
    W, H = inp["W"], inp["H"]
    dead, blocked = dv._realized(inp)
    if not isinstance(output, dict) or not isinstance(certificate, dict):
        return {"output_shape": False}
    hop, claimed = output.get("next_hop"), output.get("claimed")
    if not isinstance(hop, dict) or not isinstance(claimed, list):
        return {"output_shape": False}
    parsed = [(dv._parse_key(k, W, H), dv._parse_key(v, W, H)) for k, v in hop.items()]
    lattice_ok = all(a is not None and b is not None and abs(a // H - b // H) + abs(a % H - b % H) == 1
                     for a, b in parsed)
    pointers_ok = lattice_ok and all(a not in dead and b not in dead and (min(a, b), max(a, b)) not in blocked
                                     for a, b in parsed)
    source_keys = {dv._key(s, H) for s in inp["sources"]}
    claims_are_sources = (all(isinstance(k, str) and k in source_keys for k in claimed)
                          and len(set(claimed)) == len(claimed))
    claims_deliver = claims_are_sources and all(
        dv._follow(dv._parse_key(k, W, H), hop, inp, dead, blocked) is not None for k in claimed)
    breakdown = certificate.get("actions_breakdown")
    parts_ok = (isinstance(breakdown, dict) and set(breakdown) == {"planner", "activation_flood", "local", "probe"}
                and all(type(x) is int and x >= 0 for x in breakdown.values()))
    planner_actions = dv.repair_central_replanner(data)["actions"]
    trace = certificate.get("local_messages_per_step")
    t0 = certificate.get("first_discrepancy_step")
    t0_ok = t0 is None or (type(t0) is int and 0 <= t0 < inp["steps"])
    trace_ok = (isinstance(trace, list) and all(type(m) is int and m >= 0 for m in trace) and t0_ok
                and len(trace) == (0 if t0 is None else inp["steps"] - t0))
    replayed_t0 = first_discrepancy(data, inp)                      # the units' audit, replayed
    replayed_trace = [] if replayed_t0 is None else _local_from(inp, replayed_t0)[2]
    accounting = (parts_ok and trace_ok and t0 == replayed_t0 and trace == replayed_trace
                  and breakdown["planner"] == planner_actions
                  and breakdown["local"] == sum(trace)
                  and breakdown["activation_flood"] == (0 if t0 is None else _activation_flood(inp, t0))
                  and type(output.get("actions")) is int and output["actions"] == sum(breakdown.values()))
    owner = certificate.get("owner")
    owner_ok = owner in ("planner", "local") and (owner == "planner" or (t0 is not None and parts_ok))
    return {"pointers_are_lattice_edges": lattice_ok,
            "steps_match_input": type(output.get("steps")) is int and output["steps"] == inp["steps"]
            and certificate.get("steps") == inp["steps"],
            "claims_match_certificate_count": certificate.get("vouched_sources") == len(claimed),
            "no_pointer_into_removed_unit_or_blocked_link": pointers_ok,
            "claims_are_distinct_sources": claims_are_sources,
            "every_claimed_source_delivers_on_realized_topology": claims_deliver,
            "actions_match_replayed_accounting": accounting,
            "owner_declared": owner_ok,
            "seed_bound": certificate.get("seed") == inp["seed"],
            "no_external_effect": certificate.get("external_effects") == 0}


def hybrid_subregion(data):
    """Evaluation-side niche label from the declared controller condition (never read by the solver)."""
    mode = (data.get("controller") or {}).get("mode", "reliable") if isinstance(data, dict) else "reliable"
    return {"reliable": "reliable_controller", "crash": "crashed_controller"}.get(mode, "stale_controller")


def hybrid_local_only(data):
    """Baseline: the local-rule genome develop_repair (its admitted default protocol), output or None."""
    return dv.repair_solve_with(dv.REPAIR_DEFAULT_CONFIG, data)["output"]


# ------------------------------------------------------------------ ablations (evaluation only)
def hybrid_naive_switch(data):
    """Ablation without cross-verification: the planner's output while the controller's heartbeat lasts; if it
    stops (crash), the local protocol wakes at the crash step and its own vouched claims are used. No audit, no
    probe. Reads only the heartbeat (crash step), as a liveness monitor would."""
    inp = dv._repair_inputs(data)
    planner = dv.repair_central_replanner(data)
    crash = inp["crash_at"]
    if crash is None or crash >= inp["steps"]:
        return planner
    final_dead = _dead_by(inp, inp["steps"])
    field, vouched, trace = _local_from(inp, crash)
    H = inp["H"]
    return {"next_hop": _keys(field, H), "claimed": sorted(dv._key(u, H) for u in vouched if u not in final_dead),
            "actions": planner["actions"] + _activation_flood(inp, crash) + sum(trace), "steps": inp["steps"]}


def hybrid_vouch_only(data):
    """Ablation without fallback: the planner's field always; its claims kept only if an end-to-end probe over
    that field returns (probe transmissions counted)."""
    inp = dv._repair_inputs(data)
    planner = dv.repair_central_replanner(data)
    final_dead = _dead_by(inp, inp["steps"])
    field = {u: v for u, v in _table(planner, inp).items() if u not in final_dead}
    H = inp["H"]
    claimed_idx = [dv._parse_key(k, inp["W"], H) for k in planner["claimed"]]
    confirmed, sent = _probe(inp, field, [u for u in claimed_idx if u is not None], final_dead)
    return {"next_hop": _keys(field, H), "claimed": sorted(dv._key(u, H) for u in confirmed),
            "actions": planner["actions"] + sent, "steps": inp["steps"]}


def _genome():
    return IntelligenceGenome(
        intelligence_id="developmental.repair.plan_audit_fallback", version=VERSION, family="develop_repair_hybrid",
        layer=4, buildability="BUILDABLE_NOW", lineage=LINEAGE, operation="target_state_repair_hybrid",
        epistemic_class="physical",
        subgeometry="hold a source-region -> sink-region transport target on a damaged 4-neighbour lattice that "
                    "also has a central controller of unknown freshness (it may be fresh, stale or crash), under "
                    "region removal, unit failures, link blocking, mid-repair failures and lossy messages",
        source_provenance="recombination of develop_repair 1.1.2 (local rules: DSDV waves, Babel feasibility, "
                          "link sensing, retraction, expiry vouching) and its competitor repair_central_replanner "
                          "(global BFS rebuild, reliable pushes); fast-reroute / SDN controller-with-local-fallback "
                          "practice; end-to-end probing (traceroute-style)",
        native_representation="develop_repair's lattice instance plus the controller condition the planner "
                              "replays under (the hybrid itself never reads that condition)",
        required_inputs=("width", "height", "sources", "sinks", "removed", "blocked", "events", "steps",
                         "message_loss", "seed", "controller"),
        output_contract={"next_hop": "{'x,y': 'x,y'} forwarding pointer of every functioning unit",
                         "claimed": "[source keys the plan audit or the local vouching + probe confirms]",
                         "actions": "int unit-actions (planner + activation + local + probe)", "steps": "int"},
        algorithm_or_runtime="step-by-step replay of the central replanner with a per-unit link audit; on the "
                             "first discrepancy an activation flood wakes the dormant local protocol on the "
                             "remaining world script; the final field is the planner's if it audits clean, else "
                             "the local one with vouched, probe-confirmed claims",
        parameters={"local_protocol": dict(dv.REPAIR_DEFAULT_CONFIG), "probe_retransmissions": dv.REPEATS,
                    "max_message_loss": dv.MAX_LOSS, "action_cost": dv.ACTION_COST,
                    "wrong_penalty": dv.WRONG_PENALTY},
        memory_model="per-unit soft state of both layers inside one call; nothing persists",
        learning_rule="none; competence settles per geometry from receipts",
        composition_inputs=("damaged_topology", "disturbance_schedule", "controller_plan"),
        composition_outputs=("forwarding_field", "restoration_claims"),
        evidence_type="developmental_trace",
        verification_method="independent and outcome-based: rebuild the realized final topology from the world "
                             "script, check every pointer is a lattice edge between functioning units over an "
                             "unblocked link, follow every claimed source to the sink region without loops, and "
                             "re-derive the action count from independent replays of the planner, the activation "
                             "step and the standby trace",
        confidence_semantics="a claim means either a plan whose every pointer passed its unit's link test at the "
                             "budget's end (then exact), or a locally vouched route an end-to-end probe confirmed; "
                             "the probe is simulated, not a physical measurement",
        resource_profile="O(steps^2) planner replays plus at most one local protocol run; <= 200 units, <= 400 steps",
        latency_profile="tens to hundreds of milliseconds (the replay dominates)",
        known_strengths=("a fresh controller's exact, cheap plan is kept untouched: no local messages while the "
                         "plan audits clean",
                         "a stale or crashed controller is detected by the units' own link tests, without reading "
                         "the controller's condition, and the local protocol takes over",
                         "claims are proven by a clean audit or confirmed by an end-to-end probe"),
        known_failure_modes=("once woken the local protocol runs to the end of the budget even if the planner "
                             "catches up, so a briefly stale controller costs the full local message bill",
                             "a discrepancy late in the budget leaves the local protocol too little time to "
                             "settle; it then claims less",
                             "activation flood and probes add messages the planner alone does not pay",
                             "the probe is a simulated retransmission model; physical probes can disagree",
                             "measured only on simulated TARGET_FORM_001 lattices") + dv.FRONTIER,
        counterindications=("no central controller exists (use develop_repair)",
                            "a controller known to be fresh and reliable (the planner alone is as good and "
                            "replays nothing)", "message loss above 0.5",
                            "substrates without local link sensing") + dv.FRONTIER,
        abstention_conditions=("message loss above 0.5", "no functioning source or sink at the start"),
        benchmark_suite="develop_repair's suite (repair_instance): TARGET_FORM_001 lattices, seeded damage, 1-3 "
                        "mid-repair failure events, loss 0-0.3, even seeds reliable controller, odd seeds crash "
                        "(q = 0.5) or 36-84-step stale view; same score (false claim -1.5); dev 0-9",
        baseline="develop_repair 1.1.2: the local rules alone (default protocol)",
        competitor="adaptive centralized replanner alone (repair_central_replanner)")


INTELLIGENCES = [
    Executable(
        genome=_genome(), solve=hybrid_solve, verify=hybrid_verify, instance=dv.repair_instance,
        score=dv.repair_score, baseline=hybrid_local_only, competitor=dv.repair_central_replanner,
        subregion=hybrid_subregion, tolerance=1e-9,
        notes={"ablations": "hybrid_naive_switch (heartbeat switch, no audit, no probe) and hybrid_vouch_only "
                            "(probe-filtered planner claims, no fallback) are evaluation arms, never routed",
               "status": "withheld; EXPLORATORY measurement only; admission is a separate pre-registered run"}),
]
