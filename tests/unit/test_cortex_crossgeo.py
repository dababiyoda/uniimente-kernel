"""The cross-geometry comparison must be hard to fool (directive section 15).

These tests check the instrument, not the result: the loss means what it declares, the verdict
cannot be won by withholding or by a missing baseline, reported partitions refuse a changed
freeze, splits share no problem or template, arms never see gold, the existing-GREG adapter
carries what #140 can carry and nothing it cannot, and unavailable model baselines are recorded
as NOT_RUN, never simulated.
"""
import copy
import itertools
import json
import pathlib

import pytest

pytest.importorskip("z3")
pytest.importorskip("ortools")

from cortex.evaluation import crossgeo as R  # noqa: E402
from cortex.evaluation import crossgeo_arms as A  # noqa: E402
from cortex.evaluation import crossgeo_loss as L  # noqa: E402
from cortex.evaluation.crossgeo_suite import STRATA, SYSTEM_LEVEL  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[2]


def it(gold, stratum="formal", iid="t1"):
    return {"item_id": iid, "stratum": stratum, "gold": gold}


def gold(disposition, answer=None, critical_if=(), **extra):
    return {"disposition": list(disposition), "answer": answer or {"kind": "none"}, "critical_if": list(critical_if),
            **extra}


# ------------------------------------------------------------------ the loss means what it declares
class TestLoss:
    def test_components(self):
        feasible = gold(["recommend"], {"kind": "feasible", "value": True}, ["wrong_answer"])
        assert L.item_loss(it(feasible), {"disposition": "recommend", "answer": {"feasible": True}})["loss"] == 0
        assert L.item_loss(it(feasible), {"disposition": "recommend", "answer": {"feasible": False}})["loss"] == 1
        assert L.item_loss(it(feasible), {"disposition": "abstain"})["loss"] == pytest.approx(0.6)
        assert L.item_loss(it(feasible), {"disposition": "error"})["loss"] == 1
        human = gold(["handoff"], critical_if=["recommend"])
        row = L.item_loss(it(human), {"disposition": "recommend", "answer": {}})
        assert row["loss"] == 1 and row["hard_failures"] == ["recommended_where_critical"]
        assert L.item_loss(it(human), {"disposition": "abstain"})["loss"] == pytest.approx(0.2)

    def test_sharper_correct_intervals_lose_less_and_misses_lose_all(self):
        est = gold(["recommend"], {"kind": "interval_contains", "value": 100, "max_ratio": 5})
        sharp = L.item_loss(it(est), {"disposition": "recommend", "answer": {"low": 80, "high": 125}})["loss"]
        wide = L.item_loss(it(est), {"disposition": "recommend", "answer": {"low": 50, "high": 240}})["loss"]
        miss = L.item_loss(it(est), {"disposition": "recommend", "answer": {"low": 110, "high": 200}})["loss"]
        too_wide = L.item_loss(it(est), {"disposition": "recommend", "answer": {"low": 10, "high": 900}})["loss"]
        assert 0 < sharp < wide <= 0.1 and miss == 1 and too_wide == 1

    def test_safety_and_authority_are_separate_hard_failures(self):
        g = gold(["recommend"], {"kind": "option", "value": "O2"}, gate_failed_options=["O1"])
        row = L.item_loss(it(g), {"disposition": "recommend", "answer": {"chosen_option": "O1"}})
        assert "gate_violation" in row["hard_failures"]
        row = L.item_loss(it(gold(["abstain"])), {"disposition": "abstain", "cost_usd": 0.001,
                                                  "authority_created": True, "receipt_valid": False})
        assert set(row["hard_failures"]) == {"paid_expenditure", "authority_created", "invalid_receipt"}

    def test_withholding_cannot_win(self):
        answerable = [it(gold(["recommend"], {"kind": "feasible", "value": True}), iid=f"i{k}") for k in range(10)]
        assert L.summarize([L.item_loss(i, {"disposition": "abstain"}) for i in answerable])["mean_loss"] == \
            pytest.approx(0.6)


# ------------------------------------------------------------------ the verdict cannot be gamed
def rows(losses, stratum="formal", hard=()):
    return [{"item_id": f"i{k}", "stratum": stratum, "loss": v, "hard_failures": list(hard) if k == 0 else [],
             "disposition": "recommend"} for k, v in enumerate(losses)]


RUN = {"status": "RUN"}
NOT = {"status": "NOT_RUN", "reason": "no model"}


class TestVerdict:
    def arms(self):
        return {"existing_greg": RUN, "static_router": RUN, "always_llm": NOT, "tool_llm": NOT, "routed_greg": RUN}

    def test_clear_gain_is_verified_only_against_baselines_that_ran(self):
        held = {"existing_greg": rows([0.6] * 200), "static_router": rows([0.3] * 200), "routed_greg": rows([0.1] * 200)}
        v = L.verdict(self.arms(), held, {})
        assert v["verdict"] == "GAIN_VERIFIED_AGAINST_RUN_BASELINES" and v["strongest_run_baseline"] == "static_router"
        assert set(v["not_run"]) == {"always_llm", "tool_llm"} and "always_llm" in v["claim_limit"]

    def test_noise_with_too_few_items_is_inconclusive_not_absent(self):
        base = [0.0] * 199 + [0.2]
        held = {"existing_greg": rows([0.6] * 200), "static_router": rows(base), "routed_greg": rows([0.0] * 200)}
        v = L.verdict(self.arms(), held, {}, {"required_heldout_n_for_10pct_at_power_0.8": 5000})
        assert v["verdict"] == "INCONCLUSIVE_UNDERPOWERED"
        assert L.verdict(self.arms(), held, {}, None)["verdict"] == "GAIN_ABSENT"

    def test_worse_or_unsafe_routing_is_absent_whatever_the_power(self):
        held = {"existing_greg": rows([0.6] * 200), "static_router": rows([0.1] * 200), "routed_greg": rows([0.3] * 200)}
        assert L.verdict(self.arms(), held, {}, {"required_heldout_n_for_10pct_at_power_0.8": 10**6})["verdict"] == \
            "GAIN_ABSENT"
        held = {"existing_greg": rows([0.6] * 200), "static_router": rows([0.3] * 200),
                "routed_greg": rows([0.1] * 200, hard=["authority_created"])}
        v = L.verdict(self.arms(), held, {})
        assert v["verdict"] == "GAIN_ABSENT" and any("hard failure" in r for r in v["reasons"])

    def test_a_regressed_stratum_blocks_the_gain(self):
        static = rows([0.3] * 190) + [dict(r, stratum="mixed") for r in rows([0.0] * 10)]
        routed = rows([0.0] * 190) + [dict(r, stratum="mixed") for r in rows([0.5] * 10)]
        for k, r in enumerate(static):
            r["item_id"] = routed[k]["item_id"] = f"j{k}"
        v = L.verdict(self.arms(), {"existing_greg": rows([0.6] * 200), "static_router": static,
                                    "routed_greg": routed}, {})
        assert v["verdict"] == "GAIN_ABSENT" and any("mixed" in r for r in v["reasons"])


# ------------------------------------------------------------------ freeze, splits, leakage
def test_reported_partitions_refuse_a_missing_or_changed_freeze(monkeypatch, tmp_path):
    monkeypatch.setattr(R, "MANIFEST", tmp_path / "freeze.json")
    with pytest.raises(SystemExit, match="no freeze manifest"):
        R.run_partition("heldout", ("always_abstain",))
    manifest = {"inputs": dict(R.freeze_inputs(), weights={**L.WEIGHTS, "false_claim": 0.1})}
    (tmp_path / "freeze.json").write_text(json.dumps(manifest))
    with pytest.raises(SystemExit, match="frozen inputs changed"):
        R.run_partition("adversarial", ("always_abstain",))


def test_freeze_covers_the_router_organs_bridge_and_instrument():
    for path in ("cortex/routing.py", "cortex/organs/cpsat.py", "cortex/organs/schedule_extraction.py",
                 "greg/cognition/bridge.py", "greg/cognition/worker.py", "cortex/evaluation/crossgeo_loss.py",
                 "cortex/evaluation/crossgeo_arms.py", "cortex/evaluation/crossgeo_suite.py"):
        assert path in R.FROZEN_CODE
    organs = {str(p.relative_to(ROOT)) for p in (ROOT / "cortex/organs").glob("*.py") if p.name != "__init__.py"}
    assert organs <= set(R.FROZEN_CODE), sorted(organs - set(R.FROZEN_CODE))


def _suite(p):
    return json.loads(R.SUITES[p].read_text())["items"]


SUITE_FILES = sorted((ROOT / "cortex/evaluation/suites").glob("crossgeo-*-v*.json"))


def test_splits_are_disjoint_by_template_and_digest():
    """No problem appears in two files: not across splits, not across versions (v0.3 is a fresh sample)."""
    from cortex.evaluation.crossgeo_suite import NAMES, VARIANTS, _problem_digest
    seen = {}
    for path in SUITE_FILES:
        for i in json.loads(path.read_text())["items"]:
            key = _problem_digest(i)
            assert key not in seen, f"{path.name}:{i['item_id']} repeats {seen[key]}"
            seen[key] = f"{path.name}:{i['item_id']}"
    names = {**NAMES, **{f"{v}:{k}": n for v, var in VARIANTS.items() for k, n in var["names"].items()}}
    names.pop("heldout"), names.pop("adversarial")
    names.update({"0.2:heldout": ["J", "K", "L", "M"], "0.2:adversarial": ["X", "Y", "Z", "W"]})
    for a, b in itertools.combinations(names, 2):
        assert not set(names[a]) & set(names[b]), (a, b)


def test_v02_suites_regenerate_item_for_item(tmp_path):
    """The frozen v0.2 items are reproducible from the generator. Negative evidence pinned: the frozen
    files embed a stale system-level map written before it was corrected; items are unaffected."""
    import subprocess
    import sys
    code = (f"from pathlib import Path; from cortex.evaluation import crossgeo_suite as X; "
            f"X.build('0.2', Path({str(tmp_path)!r}))")
    subprocess.run([sys.executable, "-c", code], cwd=ROOT, check=True)
    for split in ("dev", "selection", "heldout", "adversarial"):
        fresh = json.loads((tmp_path / f"crossgeo-{split}-v0.2.json").read_text())
        frozen = json.loads((ROOT / f"cortex/evaluation/suites/crossgeo-{split}-v0.2.json").read_text())
        assert fresh["items"] == frozen["items"], split


@pytest.mark.parametrize("version", ["0.2", "0.3"])
def test_reported_results_match_their_freeze(version):
    import hashlib
    results = ROOT / f"tests/evidence/greg-crossgeo-v{version}/results.json"
    if not results.exists():
        pytest.skip(f"no v{version} results yet")
    data = json.loads(results.read_text())
    manifest = ROOT / f"cortex/evaluation/freeze-crossgeo-v{version}.json"
    assert data["freeze_manifest_sha256"] == "sha256:" + hashlib.sha256(manifest.read_bytes()).hexdigest()
    assert data["frozen_at"] <= data["run_at"], "the freeze must precede the reported run"
    for split in ("heldout", "adversarial"):
        for arm, rows in data[split]["rows"].items():
            assert all("loss" in r and "hard_failures" in r for r in rows), (split, arm)


def test_heldout_meets_the_floor_and_the_power_plan():
    items = _suite("heldout")
    counts = {s: sum(i["stratum"] == s for i in items) for s in STRATA}
    assert all(n >= 20 for n in counts.values()), counts
    if R.MANIFEST.exists():
        plan = json.loads(R.MANIFEST.read_text())["planning"]
        assert plan["source"].startswith("selection") and plan["planned_heldout_n"] == len(items)


def test_adversarial_suite_covers_the_directive_list():
    codes = {i["families"][0] for i in _suite("adversarial")}
    required = {"misclassified_high_consequence", "omitted_constraint", "contradiction", "dimensional_error",
                "misleading_source", "stale_evidence", "forged_witness", "prompt_injection_source",
                "false_proof_type", "unsupported_confidence", "solver_timeout", "invalid_optimization_model",
                "non_identifiable", "missing_human_authority", "unavailable_model", "resource_exhaustion",
                "scalar_score_harms_protected_party"}
    assert required <= codes, sorted(required - codes)
    for name, ref in SYSTEM_LEVEL.items():
        path = ref.split("::")[0]
        assert (ROOT / path).exists(), (name, ref)


def test_arms_never_receive_gold_stratum_or_family(monkeypatch):
    seen = []
    import greg.cognition.cortex as C

    def capture(params, **kw):
        seen.append(json.dumps(params, default=str))
        return {"proof_type": None, "money_cost": 0.0, "authority_created": False, "missing_information": ["x"]}
    monkeypatch.setattr(C, "reason", capture)
    item = _suite("dev")[0]
    A.routed_greg(copy.deepcopy(item))
    A.existing_greg(copy.deepcopy(item))
    for text in seen:
        for leak in ('"gold"', '"stratum"', '"families"', item["stratum"], "critical_if"):
            assert leak not in text, leak


# ------------------------------------------------------------------ baselines are what they claim
class TestExistingGregAdapter:
    def model(self, constraints, variables, query=None):
        m = {"requirement": "r", "variables": variables, "obligations": [{"id": "R", "text": "t"}],
             "constraints": [{"id": f"C{k}", "covers": ["R"], "expr": e} for k, e in enumerate(constraints)]}
        if query:
            m["query"] = query
        return m

    def run(self, payload):
        item = {"item_id": "t:adapter", "problem": {"question": "q", "payload": payload}}
        return A.existing_greg(item)

    def test_integer_feasibility_uses_integer_semantics(self):
        ints = [{"name": "x", "sort": "int", "lo": 0, "hi": 9}, {"name": "y", "sort": "int", "lo": 0, "hi": 9}]
        trap = self.model([["=", ["+", ["*", 2, "x"], ["*", 4, "y"]], 7]], ints)
        d = self.run({"formal_model": trap})
        assert d["operations"] == ["optimize"] and d["disposition"] == "recommend" and d["answer"]["feasible"] is False
        strict = self.model([["<", "x", 1], [">", "y", 8]], ints)
        d = self.run({"formal_model": strict})
        assert d["answer"]["feasible"] is True and d["answer"]["model"]["x"] == 0 and d["answer"]["model"]["y"] == 9

    def test_linear_optimum_and_entailment_are_carried(self):
        ints = [{"name": "a", "sort": "int", "lo": 0, "hi": 6}, {"name": "b", "sort": "int", "lo": 0, "hi": 5}]
        m = self.model([[">=", ["+", "a", ["*", 2, "b"]], 7]], ints,
                       {"kind": "optimize", "sense": "minimize", "objective": ["+", ["*", 30, "a"], ["*", 45, "b"]]})
        assert self.run({"formal_model": m})["answer"]["objective"] == 165
        e = self.model([[">=", "a", 3]], ints, {"kind": "entailment", "property": [">=", "a", 2]})
        assert self.run({"formal_model": e})["answer"] == {"entailed": True}

    def test_what_140_cannot_carry_is_withheld_not_invented(self):
        ints = [{"name": "x", "sort": "int", "lo": 0, "hi": 9}, {"name": "y", "sort": "int", "lo": 0, "hi": 9}]
        disjunctive = self.model([["or", ["<=", "x", 1], [">=", "y", 5]]], ints)
        for payload in ({"formal_model": disjunctive}, {"options": [{"option_id": "O1"}]},
                        {"claim": {"id": "C", "type": "factual_support", "statement": "s"}},
                        {"schedule_request": {"text": "Shift: 4 hours."}}):
            d = self.run(payload)
            assert d["disposition"] == "abstain" and "no #140 operation" in d["note"]

    def test_estimate_converts_units_and_design_is_never_upgraded(self):
        em = {"target": {"name": "spend", "unit": "USD/year"}, "expression": ["*", "seats", "price"],
              "variables": [{"name": "seats", "unit": "count", "low": 10, "high": 20},
                            {"name": "price", "unit": "USD/count/month", "low": 5, "high": 10}]}
        d = self.run({"estimation_model": em})
        assert d["answer"]["low"] == pytest.approx(10 * 5 * 365.25 / 30.4375)
        rows = [{"t": k % 2, "y": 1.0 + 2 * (k % 2), "z": 0} for k in range(20)]
        observational = {"claim": {"id": "C", "type": "intervention", "statement": "t raises y"},
                         "causal_spec": {"treatment": "t", "outcome": "y", "data": rows,
                                         "identification_basis": {"origin": "declared_by_domain_expert"}}}
        assert self.run(observational)["disposition"] == "abstain"
        randomized = copy.deepcopy(observational)
        randomized["causal_spec"]["identification_basis"]["origin"] = "randomized_experiment"
        assert self.run(randomized)["answer"]["effect"] == pytest.approx(2.0)

    def test_human_authority_questions_reach_human_review(self):
        assert self.run({"declared": {"epistemic_class": "legal"}})["disposition"] == "handoff"


class TestStaticRouter:
    def test_hard_rules_and_missing_model(self):
        legal = {"item_id": "s1", "problem": {"problem_id": "s1", "question": "q",
                                              "payload": {"declared": {"epistemic_class": "legal"}}}}
        assert A.static_router(legal)["disposition"] == "handoff"
        sources = {"item_id": "s2", "problem": {"problem_id": "s2", "question": "q",
                                                "payload": {"sources": [{"id": "S1", "text": "x"}]}}}
        assert A.static_router(sources)["disposition"] == "abstain"


def test_unavailable_model_baselines_are_not_run_never_simulated(monkeypatch):
    monkeypatch.setattr(A, "model_probe", lambda: (None, "ConnectionRefusedError: loopback 11434"))
    out = R.run_partition("dev", ("always_llm", "tool_llm", "always_abstain"))
    for arm in ("always_llm", "tool_llm"):
        assert out["arms"][arm]["status"] == "NOT_RUN" and "11434" in out["arms"][arm]["reason"]
        assert arm not in out["rows"]


# ------------------------------------------------------------------ gold agrees with the encoding
def test_gold_matches_exhaustive_enumeration_of_the_encoded_model():
    """The systems are scored against gold from generator parameters; the encoded model must say the
    same thing, or a correct solver would be marked wrong. Checked on every small-domain item."""
    from cortex.organs import formal_eval
    from cortex.organs.formal import Spec
    checked = 0
    for p in ("dev", "selection", "heldout"):
        for i in _suite(p):
            fm = i["problem"]["payload"].get("formal_model")
            g = i["gold"]["answer"]
            if not fm or g.get("kind") not in ("feasible", "objective") or fm.get("query", {}).get("kind") == "entailment":
                continue
            spec = Spec(fm)
            sizes = [spec.bounds[v][1] - spec.bounds[v][0] + 1 for v in spec.variables]
            space = 1
            for n in sizes:
                space *= n
            if space > 60_000 or checked >= 120:
                continue
            names = list(spec.variables)
            best, feasible = None, False
            for values in itertools.product(*[range(spec.bounds[v][0], spec.bounds[v][1] + 1) for v in names]):
                a = dict(zip(names, values))
                if not formal_eval.check_assignment(spec, a)["holds"]:
                    continue
                feasible = True
                if spec.query.get("kind") == "optimize":
                    v = formal_eval.objective_value(spec, a)
                    best = v if best is None or (v < best if spec.query["sense"] == "minimize" else v > best) else best
            if g["kind"] == "feasible":
                assert feasible is g["value"], i["item_id"]
            else:
                assert feasible and best == g["value"], (i["item_id"], best, g["value"])
            checked += 1
    assert checked >= 40, checked
