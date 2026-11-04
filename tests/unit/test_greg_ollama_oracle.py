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
digest names); the F3 cloud names broke it too, through the cloud-proxy check added here.
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
    assert len(NAMES) == len(set(NAMES)) >= 76
    provenance = FROZEN["provenance"]
    assert provenance["ollama"] == {
        "v040": "https://github.com/ollama/ollama/tree/0d0720e51fb2fd9aa58781c3d720c06d720c2e7b",
        "main": "https://github.com/ollama/ollama/tree/e9fde36d75fea66579d84099956ce1430792737a"}
    assert provenance["platform"].startswith("linux/"), "runs with no runner use Ollama's non-Apple runner order"
    assert scenarios.CLEARS <= set(NAMES) and len(scenarios.CLEARS) >= 15


@pytest.mark.parametrize("name", NAMES)
def test_greg_never_clears_what_ollama_would_serve_differently(name, tmp_path):
    frozen = FROZEN["scenarios"][name]
    (tmp_path / "models").mkdir()
    got = getattr(scenarios, name)(tmp_path / "models")
    assert (got[0], scenarios.fingerprint(tmp_path)) == (frozen["request"], frozen["fingerprint"]), \
        "the scenario writes other bytes than were frozen: re-run tests/fixtures/ollama_oracle/freeze.py"
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
    assert served or name not in scenarios.CLEARS, (name, "a positive control Ollama serves nothing for")
