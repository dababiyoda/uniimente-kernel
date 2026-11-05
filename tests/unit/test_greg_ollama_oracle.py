"""GREG's model-license gate against Ollama's own manifest code, frozen: no Go is needed to run this.

``tests/fixtures/ollama_oracle/answers.json`` holds, for each store ``scenarios.py`` writes, what Ollama v0.40.0
(0d0720e) and main (e9fde36d) serve for its request name with no runner and with each runner. The answers come from
Ollama's own manifest, types/model and internal/modelref packages, compiled by ``build_oracle.sh`` with the
independent reviewer's oracle program and run by ``freeze.py``; the provenance is in the file. Each store is built
again here and checked against the fingerprint frozen with it, so the frozen digests still name its files.

The rule: GREG never clears a model for which Ollama would serve something GREG did not assess. When GREG clears,
every manifest either Ollama version serves under any runner must be one GREG assessed (the plain manifest, or a
child of the list), carry license layers that are exactly the Apache text GREG cleared, no weight layer GREG did not
list, and no relay config; no run may go to ollama.com; and the child /api/tags reports in GREG's evidence must be
the one Ollama selects on this platform. The stores in ``scenarios.CLEARS`` must clear, so a reader that holds
everything does not pass. On 52f5703b, 15 of the reviewer's 54 scenarios broke this rule (12 JSON-key cases, 3
digest names); the F3 cloud names broke it too, through the cloud-proxy check added here. A clear is a break as well
when Ollama does not find the model under some run, or serves it under none (it would pull bytes GREG never read): on d1724006 the four quoted or
padded OLLAMA_MODELS spellings cleared the home store's Apache copy while Ollama served the named store's Llama
manifest (N1), a store without the model fell through to the home store (N2), and a manifest with a UTF-8 BOM or in
UTF-16, which Go's decoder rejects, cleared (N3); and a name under the host ollama.com cleared a local manifest that
main never finds under that host. On 49aaa812 a manifest Go's decoder rejects for a NaN or Infinity, or for a value
its field cannot hold (a layer size 1e2, 1.5, 2**63, "1" or true), cleared (F2); and with OLLAMA_MODELS unset GREG
read the system store /usr/share/ollama beside HOME's (F1), which a fixture cannot write: the stores here run with
OLLAMA_MODELS unset, and HOME set, unset (Ollama panics) or empty, as scenarios.HOME says.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from greg import licensing

ORACLE = Path(__file__).resolve().parents[1] / "fixtures" / "ollama_oracle"
_spec = importlib.util.spec_from_file_location("ollama_oracle_scenarios", ORACLE / "scenarios.py")
scenarios = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(scenarios)
FROZEN = json.loads((ORACLE / "answers.json").read_text(encoding="utf-8"))
# Every layer Ollama runs as weights (manifest/layer.go, v0.40.0 and main), kept here rather than read from GREG.
WEIGHTS = {"application/vnd.ollama.image.model", "application/vnd.ollama.image.projector",
           "application/vnd.ollama.image.adapter", "application/vnd.ollama.image.tensor",
           "application/vnd.ollama.image.draft"}
NAMES = [fn.__name__ for fn in scenarios.SCENARIOS]


def test_every_scenario_is_frozen_with_its_provenance():
    assert sorted(FROZEN["scenarios"]) == sorted(NAMES), "re-run tests/fixtures/ollama_oracle/freeze.py"
    assert len(NAMES) == len(set(NAMES)) >= 110
    assert {n: s["ollama_models"] for n, s in FROZEN["scenarios"].items() if s["ollama_models"] != "{models}"} == \
        {n: v for n, v in scenarios.ENV.items() if v != "{models}"}, "re-run tests/fixtures/ollama_oracle/freeze.py"
    assert {n: s["home"] for n, s in FROZEN["scenarios"].items() if "home" in s} == scenarios.HOME, \
        "re-run tests/fixtures/ollama_oracle/freeze.py"
    provenance = FROZEN["provenance"]
    assert provenance["ollama"] == {
        "v040": "https://github.com/ollama/ollama/tree/0d0720e51fb2fd9aa58781c3d720c06d720c2e7b",
        "main": "https://github.com/ollama/ollama/tree/e9fde36d75fea66579d84099956ce1430792737a"}
    assert provenance["platform"].startswith("linux/"), "runs with no runner use Ollama's non-Apple runner order"
    assert scenarios.CLEARS <= set(NAMES) and len(scenarios.CLEARS) >= 25


@pytest.mark.parametrize("name", NAMES)
def test_greg_never_clears_what_ollama_would_serve_differently(name, tmp_path, monkeypatch):
    frozen = FROZEN["scenarios"][name]
    (tmp_path / "models").mkdir()
    got = getattr(scenarios, name)(tmp_path / "models")
    assert (got[0], scenarios.fingerprint(tmp_path)) == (frozen["request"], frozen["fingerprint"]), \
        "the scenario writes other bytes than were frozen: re-run tests/fixtures/ollama_oracle/freeze.py"
    if name in scenarios.ENV:       # GREG finds the store as Ollama does, from the same environment
        for variable, value, stands_for in (("OLLAMA_MODELS", scenarios.ENV[name], ("{models}", tmp_path / "models")),
                                            ("HOME", scenarios.HOME.get(name, "{dir}"), ("{dir}", tmp_path))):
            if value is None:
                monkeypatch.delenv(variable, raising=False)
            else:
                monkeypatch.setenv(variable, value.replace(stands_for[0], str(stands_for[1])))
        a = licensing.ollama_model(frozen["request"])
    else:
        a = licensing.ollama_model(frozen["request"], tmp_path / "models")
    cleared = a is not None and not a["held"]
    if name in scenarios.CLEARS:
        assert cleared, (name, a and a["reason"])
    if not cleared:
        return
    subject = a["subject"]
    assessed = {subject["manifest_sha256"]} | {c["manifest_sha256"] for c in subject.get("children", ())}
    served = 0
    for run, index in frozen["runs"].items():
        answer = frozen["served"][index]
        if "error" in answer:
            assert not answer["error"].startswith("CLOUD PROXY"), (name, run, "Ollama runs this on ollama.com")
            assert answer["error"] != "file does not exist", (name, run, "Ollama does not have this model here and "
                                                              "would pull bytes GREG never read")
            continue
        served += 1
        licenses = [d for media, d in answer["layers"] if media == licensing.OLLAMA_LICENSE]
        weights = {d for media, d in answer["layers"] if media in WEIGHTS}
        assert answer["selected"] in assessed, (name, run, "Ollama serves a manifest GREG did not assess")
        assert licenses and set(licenses) == {scenarios.APACHE_DIGEST}, (name, run, licenses)
        assert weights <= set(subject["weights"]), (name, run, sorted(weights - set(subject["weights"])))
        assert answer["config"] not in frozen["relays"], (name, run, "Ollama serves a relay")
        if "api_tags_digest" in subject and run.endswith("/-"):
            assert subject["api_tags_digest"]["llamacpp>ggml>mlx"] == answer["selected"], (name, run)
        if "api_tags_digest" in subject and run.endswith("/mlx"):
            assert subject["api_tags_digest"]["mlx>llamacpp>ggml"] == answer["selected"], (name, run)
    assert served, (name, "GREG clears a model Ollama does not have here: a run would pull bytes GREG never read")
