"""Synthetic proof reconstitution. Operators see matching offers, not the evaluator."""
from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
import json


TICKS = 6


@dataclass(frozen=True)
class Rule:
    name: str
    role: str
    needs: tuple[str, ...]
    provides: str


@dataclass(frozen=True)
class Proof:
    sources: frozenset[str]
    operators: frozenset[str]

    def live(self, sources, operators):
        return self.sources <= sources.keys() and self.operators <= operators


def join(rule, inputs):
    return Proof(
        frozenset().union(*(proof.sources for proof in inputs)),
        frozenset({rule.name}).union(*(proof.operators for proof in inputs)),
    )


class Local:
    def __init__(self, rules, sources, preferences=()):
        self.rules = {rule.name: rule for rule in rules}
        self.offers = defaultdict(list)
        for name, claim in sources.items():
            self.offers[claim].append(name)
        for rule in rules:
            self.offers[rule.provides].append(rule.name)
        self.bindings = {}
        self.preferences = {(role, slot): provider for role, slot, provider in preferences}
        self.memory = {}
        self.checks = 0
        self.rewires = 0
        self.name_changes = []

    def step(self, sources, operators, frozen=False):
        heard = {
            name: proof for name, proof in self.memory.items()
            if proof.live(sources, operators)
        }
        heard.update({name: Proof(frozenset({name}), frozenset()) for name in sources})
        updated = {}
        for name in sorted(operators):
            rule = self.rules[name]
            self.checks += 1
            inputs = []
            for slot, claim in enumerate(rule.needs):
                identity = (name, slot)
                old = self.bindings.get(identity)
                sender = old
                preferred = self.preferences.get((rule.role, slot))
                choices = [candidate for candidate in self.offers[claim]
                           if candidate != name and (candidate in operators or candidate in sources)]
                if old is None or (not frozen and old not in heard):
                    # Ready offers outrank promises. Keep a valid link by default.
                    # No operator sees siblings' inputs or the evaluator's goal.
                    sender = min(choices, key=lambda candidate: (
                        candidate not in heard, self.role(candidate) != preferred, candidate
                    ), default=None)
                    self.bindings[identity] = sender
                    if old is not None and old != sender:
                        self.rewires += 1
                        self.name_changes.append([name, slot, old, sender])
                if sender in heard:
                    candidate = heard[sender]
                    if name not in candidate.operators:
                        inputs.append(candidate)
            if len(inputs) == len(rule.needs):
                updated[name] = join(rule, inputs)
        self.memory = updated
        return self.claims(sources)

    def claims(self, sources):
        return set(sources.values()) | {self.rules[name].provides for name in self.memory}

    def role(self, name):
        return self.rules[name].role if name in self.rules else "source"

    def recipe(self, result):
        """Export role-level wiring from the verified, actually used proof."""
        proof = self.memory[result]
        return tuple(sorted({
            (self.role(consumer), slot, self.role(producer))
            for consumer, slot, _, producer in self.name_changes
            if consumer in proof.operators and producer in proof.operators
            and self.bindings.get((consumer, slot)) == producer
        }))


class Central:
    """Adaptive worklist with incremental truth maintenance from valid proofs."""
    def __init__(self, rules):
        self.rules = {rule.name: rule for rule in rules}
        self.consumers = defaultdict(set)
        for rule in rules:
            for need in rule.needs:
                self.consumers[need].add(rule.name)
        self.memory = {}
        self.checks = 0

    def solve(self, sources, operators):
        facts = {
            name: proof for name, proof in self.memory.items()
            if proof.live(sources, operators)
        }
        facts.update({claim: Proof(frozenset({name}), frozenset()) for name, claim in sources.items()})
        queue = deque(sorted(operators))
        while queue:
            name = queue.popleft()
            rule = self.rules[name]
            if rule.provides in facts:
                continue
            self.checks += 1
            if all(need in facts for need in rule.needs):
                facts[rule.provides] = join(rule, (facts[need] for need in rule.needs))
                queue.extend(sorted(self.consumers[rule.provides] & operators))
        self.memory = facts
        return set(facts)


def case_one():
    sources = {"report": "reported", "record": "recorded", "check": "checked", "anchor": "independent"}
    rules = (
        Rule("a_fast", "shortcut", ("reported",), "qualified"),
        Rule("b_reconcile", "reconcile", ("recorded", "checked"), "reconciled"),
        Rule("c_certify", "corroborated", ("reconciled",), "qualified"),
        Rule("d_release", "decide", ("qualified",), "release"),
        Rule("e_provisional", "screen", ("reported",), "provisional"),
        Rule("f_unrelated", "observe", ("independent",), "unrelated"),
    )
    return sources, rules


def case_two():
    sources = {"note": "noticed", "meter": "measured", "inspection": "inspected"}
    rules = (
        Rule("g_read", "initial", ("noticed",), "read"),
        Rule("h_derive", "compare", ("read",), "derived"),
        Rule("i_short", "shortcut", ("derived",), "usable"),
        Rule("j_audit", "corroborated", ("measured", "inspected"), "usable"),
        Rule("k_allocate", "decide", ("usable",), "allocate"),
    )
    return sources, rules


def trace(network, sources, operators, *, frozen=False):
    seen = []
    for _ in range(TICKS):
        claims = network.step(sources, operators, frozen=frozen)
        if not all(proof.live(sources, operators) for proof in network.memory.values()):
            raise AssertionError("A published proof used revoked ancestry")
        seen.append(claims)
    return seen


def first(trace_, claim):
    return next((tick for tick, row in enumerate(trace_, 1) if claim in row), None)


def transfer(sources, rules, capsule, target, required_sources=None, controls=()):
    operators = {rule.name for rule in rules}
    results = {}
    for label, preference in (("cold", ()), ("inherited", capsule)):
        arm = Local(rules, sources, preference)
        phases = trace(arm, sources, operators)
        proofs = [proof for name, proof in arm.memory.items() if arm.rules[name].provides == target]
        if not proofs or (required_sources is not None and all(p.sources != required_sources for p in proofs)):
            raise AssertionError(f"{label} missed the independently supported decision: {target}")
        if not set(controls) <= phases[-1]:
            raise AssertionError(f"{label} missed independently supported controls")
        results[label] = {"first_answer_round": first(phases, target),
                          "rewires": arm.rewires, "rule_checks": arm.checks,
                          "binding_changes": arm.name_changes}
    return results


def run():
    sources, rules = case_one()
    alive = {rule.name for rule in rules}
    remaining = {name: fact for name, fact in sources.items() if name != "report"}
    available = alive - {"a_fast"}
    adaptive, frozen = Local(rules, sources), Local(rules, sources)
    for arm in (adaptive, frozen):
        trace(arm, sources, alive)
        assert arm.bindings[("d_release", 0)] == "a_fast"
        assert arm.claims(sources) >= {"release", "provisional", "unrelated"}
    checks_before = adaptive.checks
    seen = trace(adaptive, remaining, available)
    fixed = trace(frozen, remaining, available, frozen=True)

    central = Central(rules)
    central.solve(sources, alive)
    central_before = central.checks
    planned = central.solve(remaining, available)
    expected = {"release", "unrelated"}
    decisions = expected | {"provisional"}
    if not all({"unrelated"} <= row and "provisional" not in row for row in seen + fixed):
        raise AssertionError("Selective retraction or preservation failed")
    if seen[-1] & decisions != expected or planned & decisions != expected:
        raise AssertionError("An adaptive arm disagrees with the fixture oracle")
    if "release" in fixed[-1] or adaptive.memory["d_release"].operators != {
        "b_reconcile", "c_certify", "d_release"
    }:
        raise AssertionError("Rewiring did not restore the intended multi-operator reasoning")
    capsule = adaptive.recipe("d_release")
    transfer_sources, transfer_rules = case_two()
    results = transfer(transfer_sources, transfer_rules, capsule, "allocate", {"meter", "inspection"})
    return {
        "evidence_tier": "synthetic_authored_cases",
        "round_budget_per_phase": TICKS,
        "recovery": {
            "adaptive_local": {"first_answer_round": first(seen, "release"),
                               "rule_checks": adaptive.checks - checks_before,
                               "binding_changes": adaptive.name_changes},
            "frozen_local": {"first_answer_round": first(fixed, "release"), "rewires": frozen.rewires},
            "adaptive_central": {"first_answer_round": 1, "rule_checks": central.checks - central_before},
            "unrelated_kept_every_round": True,
            "withdrawn_support_retracted_at_first_observation": True,
        },
        "capsule": [list(row) for row in capsule],
        "capsule_acquisition_rule_checks": adaptive.checks,
        "transfer": results,
    }


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, sort_keys=True))
