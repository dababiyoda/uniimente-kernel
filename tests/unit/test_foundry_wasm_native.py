"""Real optional Wasmtime: arithmetic, import denial, fuel and artifact checks."""
from copy import deepcopy
import hashlib

import pytest

wasmtime = pytest.importorskip("wasmtime", reason="optional requirements-foundry.txt not installed")
from foundry.systems import wasm
from tests.unit.test_foundry_bridge_boundaries import invoke
from greg.capabilities import CapabilityError


def test_real_import_free_module_matches_distinct_native_interpreter(tmp_path):
    result = wasm.exercise(tmp_path)
    assert result["value"]["value"] == 270
    for family in ("pricing_differential", "budget_differential"):
        assert result[family]["cases"] == 32
        assert result[family]["disagree"] == 0
        assert result[family]["agree"] + result[family]["both_refused"] == 32
    assert all(result["refusals"].values()), result["refusals"]
    assert result["value"]["engine_version"] == "49.0.0"
    assert result["authority_created"] is False


@pytest.mark.parametrize("source,inputs,expected", [
    ("base_price * units", {"base_price": 12, "units": 3}, 36),
    ("round(base_price)", {"base_price": 2.5}, 2),
    ("round(base_price)", {"base_price": 3.5}, 4),
    ("min(base_price, units, cost_per_unit)", {"base_price": 8, "units": 3, "cost_per_unit": 4}, 3),
    ("1 if base_price > 2 and units > 0 else 0", {"base_price": 3, "units": 1}, 1),
    ("5 if not units else 9", {"units": 0}, 5),
])
def test_canonical_query_executes_real_wasm_and_reference(tmp_path, source, inputs, expected):
    out = invoke(tmp_path, 11, "run", {"language": "pricing", "source": source, "inputs": inputs})
    assert out["result"]["value"] == expected == out["result"]["reference_value"]
    assert out["result"]["manifest"]["imports"] == []
    assert out["result"]["checked"] and not out["authority_created"]
    assert not (tmp_path / "workspace").exists()


@pytest.mark.parametrize("args", [
    {"language": "pricing", "source": "__import__('os').getenv('HOME')", "inputs": {}},
    {"language": "pricing", "source": "base_price", "inputs": {}},
    {"language": "pricing", "source": "1e1000", "inputs": {}},
    {"language": "pricing", "source": "1/0", "inputs": {}},
    {"language": "pricing", "source": "-1", "inputs": {}},
    {"language": "pricing", "source": "1", "inputs": {}, "wasm": "caller bytes"},
])
def test_caller_code_binary_undefined_and_unsafe_numeric_inputs_refuse(tmp_path, args):
    with pytest.raises(CapabilityError):
        invoke(tmp_path, 11, "run", args)


def test_declared_host_import_remains_forbidden_even_with_correct_digest():
    data = bytes(wasmtime.wat2wasm('(module (import "host" "secret" (func)) '
                                 '(func (export "rule") (result f64) (f64.const 1)))'))
    manifest = {"language": "pricing", "exports": {"rule": {"params": [], "result": "f64"}},
                "imports": [{"module": "host", "name": "secret"}],
                "wasm_sha256": hashlib.sha256(data).hexdigest()}
    with pytest.raises(wasm.WasmError, match="host policy does not allow"):
        wasm.run(data, manifest, {})


def test_finite_module_tamper_is_not_a_checkable_artifact():
    compiled = wasm.compile_rule("pricing", "1")
    manifest = deepcopy(compiled["manifest"])
    manifest["wasm_sha256"] = "0" * 64
    with pytest.raises(wasm.WasmError, match="manifest hash"):
        wasm.run(compiled["wasm"], manifest, {})
