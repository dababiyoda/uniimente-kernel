"""System 11 through real Body, laboratory signatures, Gate and appraiser."""
import pytest

pytest.importorskip("wasmtime", reason="optional requirements-foundry.txt not installed")
from greg.body import Body
from tests.greg_fixtures import drop, make_body, signed
from tests.integration.test_greg_foundry_extraction import _spec, _output


def test_wasm_native_path_preserves_receipt_and_revocation_across_restart(tmp_path):
    home, key, body_id, _ = make_body(tmp_path)
    spec = _spec("m:wasm-rule", 11, "run", {"language": "pricing", "source": "base_price * units",
                                           "inputs": {"base_price": 12, "units": 3}}, "value", 36)
    with Body(home) as body:
        assert body.registry.state["foundry.query"] == "VERIFIED"
        body.apply(signed(key, body_id, "CAPABILITY_ATTACH", {"capability_id": "foundry.query"}))
        drop(home, signed(key, body_id, "MISSION", spec))
        body.boot()
        assert body.tick()["missions"][0]["state"] == "ACHIEVED"
        output = _output(body, body.journal.replay("mission.observed")[-1])
        assert output["result"]["engine"] == "wasmtime" and output["result"]["checked"]
        assert body.journal.replay("mission.appraised")[-1].payload["verdict"] == "VERIFIED"
        assert not body.journal.replay("cognition.settled"), "component agreement is not an empirical outcome"
        before = len(body.ledger.by_type("receipt"))
        body.apply(signed(key, body_id, "CAPABILITY_DETACH", {"capability_id": "foundry.query"}))
    with Body(home) as body:
        body.boot(); body.tick()
        assert body.registry.state["foundry.query"] == "DETACHED"
        assert len(body.ledger.by_type("receipt")) == before
        assert body.ledger.verify_chain()[0]


def test_wasm_reference_and_artifact_must_survive_separate_appraisal(tmp_path):
    home, key, body_id, _ = make_body(tmp_path)
    spec = _spec("m:wasm-forgery", 11, "run", {"language": "pricing", "source": "2+2", "inputs": {}}, "checked", True)
    with Body(home) as body:
        body.apply(signed(key, body_id, "CAPABILITY_ATTACH", {"capability_id": "foundry.query"}))
        adapter = body.registry.adapters["foundry.query"]
        def forged(params, ctx):
            out = adapter(params, ctx)
            out["result"]["value"] = 5
            out["result"]["reference_value"] = 5
            return out
        body.registry.adapters["foundry.query"] = forged
        drop(home, signed(key, body_id, "MISSION", spec))
        body.boot()
        assert body.tick()["missions"][0]["state"] == "ACHIEVED"
        appraisal = body.journal.replay("mission.appraised")[-1].payload
        assert appraisal["verdict"] == "REFUTED", appraisal
        assert not body.journal.replay("cognition.settled")
