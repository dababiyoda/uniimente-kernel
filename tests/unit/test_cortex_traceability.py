"""Cortex seed — the build prompt, line by line, against executable evidence.

``docs/cortex/BUILD_PROMPT_TRACEABILITY.json`` maps every line of the verbatim
build prompt to a requirement with a status and evidence. These tests keep the
map honest: anchors must be verbatim, every line must be covered, every
evidence reference must resolve, and the claims the map relies on (layers,
contract fields, held-out coverage, freeze discipline, examples) are checked
directly rather than trusted.
"""
import hashlib
import json
import pathlib

import pytest

from cortex.contracts import CORTEX_VERSION, LAYERS
from cortex.evidence_refs import resolve
from cortex.genome import seed_registry
from cortex.schemas import validate

ROOT = pathlib.Path(__file__).resolve().parents[2]
MATRIX = json.loads((ROOT / "docs/cortex/BUILD_PROMPT_TRACEABILITY.json").read_text(encoding="utf-8"))
SOURCE = (ROOT / MATRIX["source"]).read_text(encoding="utf-8")
BODY = SOURCE.split("=== BEGIN VERBATIM TEXT ===\n", 1)[1].split("=== END VERBATIM TEXT ===", 1)[0]
REQS = MATRIX["requirements"]


def _schema(name):
    return json.loads((ROOT / "contracts" / f"{name}.schema.json").read_text(encoding="utf-8"))


# ------------------------------------------------------------------ the map itself
def test_matrix_shape():
    ids = [r["id"] for r in REQS]
    assert len(ids) == len(set(ids))
    assert {r["status"] for r in REQS} <= set(MATRIX["status_vocabulary"])
    assert {r["item"] for r in REQS} == set(range(0, 13)), "items 1-11 plus framing (0) and governing rule (12)"
    assert MATRIX["cortex_version"] == CORTEX_VERSION
    for r in REQS:
        assert r["evidence"], r["id"]
        if r["status"] in ("partial", "blocked_external", "met_reported_negative"):
            assert r["notes"], f"{r['id']}: a non-met status must say why"


def test_anchors_are_verbatim():
    for r in REQS:
        for anchor in r["anchors"]:
            assert anchor in BODY, f"{r['id']}: anchor not in the verbatim prompt: {anchor[:60]!r}"


def test_every_line_of_the_prompt_is_covered():
    anchors = sorted({a for r in REQS for a in r["anchors"]} | set(MATRIX["framing_anchors"]), key=len, reverse=True)
    uncovered = []
    for line in BODY.splitlines():
        rest = line
        for a in anchors:
            rest = rest.replace(a, "")
        if rest.strip(" \t*`-.:,;0123456789"):
            uncovered.append(line.strip())
    assert not uncovered, uncovered


@pytest.mark.parametrize("ref", sorted({ref for r in REQS for ref in r["evidence"]}))
def test_evidence_resolves(ref):
    resolve(ROOT, ref)


# ------------------------------------------------------------------ claims checked directly
def test_layers_match_the_prompt():
    prompt = ["Primitive / basal", "Distributed / collective", "Solver / macro-cognitive",
              "Developmental / morphogenetic", "Meta-intelligence / Polyintelligence Cortex"]
    assert all(p in BODY for p in prompt) and len(LAYERS) == len(prompt)
    for p, layer in zip(prompt, LAYERS):
        assert p.split(" / ")[0].lower().split("-")[0] in layer
    enum = _schema("cortex-intelligence-genome")["properties"]["profile"]["properties"]["layer"]["enum"]
    assert tuple(enum) == LAYERS


PROMPT_FIELDS = {
    "cortex-problem-geometry": {
        "epistemic class": ["epistemic_class"], "objective": ["objective"], "ambiguity": ["ambiguity"],
        "exactness": ["exactness"], "uncertainty": ["uncertainty"], "causal structure": ["causal_structure"],
        "constraints": ["constraints"], "sequential or static character": ["temporal_character"],
        "evidence quality": ["evidence_quality"], "resource limits": ["resource_limits"],
        "consequence vector": ["consequence_vector"], "reversibility": ["reversibility"],
        "unresolved fields": ["unresolved_fields"]},
    "cortex-intelligence-genome#profile": {
        "supported geometries": ["supported_geometries"], "input/output contracts": ["input_contract", "output_contract"],
        "proof classes": ["proof_classes"], "observations": ["observations"], "state": ["state"],
        "memory scope": ["memory_scope"], "update rules": ["update_rules"],
        "recruitment/inhibition behavior": ["recruitment", "inhibition"],
        "evidence requirements": ["evidence_requirements"], "costs": ["cost_usd_per_call"],
        "latency": ["latency_s_budget"], "cognitive light cone": ["cognitive_light_cone"],
        "existing authority reference": ["authority_ref"], "contraindications": ["contraindications"],
        "abstention conditions": ["abstention_conditions"], "failure modes": ["failure_modes"],
        "lineage": ["lineage"], "benchmark history": ["benchmark_history"]},
    "cortex-receipt": {
        "inputs and evidence references": ["inputs"], "versions": ["versions"], "geometry": ["geometry"],
        "eligibility results": ["eligibility"], "route rationale": ["route"], "alternatives": ["alternatives"],
        "assumptions": ["assumptions"], "output": ["output"], "uncertainty": ["uncertainty"],
        "proof artifact": ["proof_artifacts"], "verifier findings": ["verifier"],
        "shared dependencies": ["shared_dependencies"], "expenditure": ["expenditure"],
        "disposition": ["disposition"], "later outcome linkage": ["outcome_link"]},
    "cortex-routing-memory": {
        "verified outcome provenance": ["outcome_status", "outcome_provenance"], "geometry": ["geometry"],
        "attribution uncertainty": ["attribution"], "competence update": ["competence_update"],
        "policy version": ["policy_version"], "rollback reference": ["rollback_ref"],
        # item 10 linkage
        "problem": ["problem_id"], "selected methods": ["method", "method_version"],
        "recommendation": ["recommendation"], "authorization where applicable": ["authorization_ref"],
        "consequence": ["consequence_class"], "observed outcome": ["outcome_status"], "attribution": ["attribution"],
        "conditions": ["conditions"]},
}


@pytest.mark.parametrize("contract", sorted(PROMPT_FIELDS))
def test_contract_fields_cover_the_prompt(contract):
    name, _, sub = contract.partition("#")
    schema = _schema(name)
    node = schema["properties"][sub] if sub else schema
    for phrase, fields in PROMPT_FIELDS[contract].items():
        assert phrase.split("/")[0] in BODY, phrase
        for f in fields:
            assert f in node["required"], f"{contract}: prompt field {phrase!r} -> {f} not required"
    if name == "cortex-receipt":
        truth = schema["properties"]["truth"]["required"]
        assert {"formal_validity", "empirical_validity", "legitimate_authority"} <= set(truth)


def test_every_registered_genome_validates():
    registry = seed_registry()
    for key in registry.keys():
        validate(registry.get(key).to_dict(), "cortex-intelligence-genome")


def test_heldout_covers_categories_and_named_failures():
    items = json.loads((ROOT / "cortex/evaluation/suites/heldout-v0.1.json").read_text(encoding="utf-8"))["items"]
    categories = {i["category"] for i in items}
    assert {"mixed", "adversarial", "malformed", "unanswerable"} <= categories
    families = {f for i in items for f in i["families"]}
    named = {"stale_evidence", "contradictory_sources", "shared_misconception", "omitted_constraint", "solver_outage",
             "exhausted_budget", "delayed_outcome", "evaluator_gaming", "distribution_shift"}
    assert named <= families, named - families


def _sha(path: pathlib.Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.mark.parametrize("results", sorted((ROOT / "tests/evidence").glob("cortex-seed-v*/heldout-results.json")),
                         ids=lambda p: p.parent.name)
def test_reported_results_match_their_freeze(results):
    data = json.loads(results.read_text(encoding="utf-8"))
    version = data.get("cortex_version") or results.parent.name.removeprefix("cortex-seed-v")
    manifest = ROOT / "cortex/evaluation" / f"freeze-v{version}.json"
    assert manifest.exists() and data["freeze_manifest_sha256"] == _sha(manifest)
    assert data["frozen_at"] <= data["run_at"], "the freeze must precede the reported run"
    declared = json.loads(manifest.read_text(encoding="utf-8"))["inputs"]["arms"]["declared_baselines"]
    if any(data["arms"].get(b, {}).get("status") != "RUN" for b in declared):
        assert data["exit"]["promote"] is False and data["exit"]["verdict"] != "GAIN_VERIFIED"


def test_examples_validate_and_are_current():
    folder = ROOT / "docs/cortex/examples"
    index = json.loads((folder / "INDEX.json").read_text(encoding="utf-8"))["contracts"]
    assert set(index) == {p.name for p in folder.glob("*.json")} - {"INDEX.json"}
    for name, contract in index.items():
        payload = json.loads((folder / name).read_text(encoding="utf-8"))
        validate(payload, contract)
        if contract == "cortex-receipt":
            assert payload["versions"]["cortex"] == CORTEX_VERSION, f"{name}: regenerate with python -m cortex.examples"
