"""#11 Portable components: DSL rules compiled to WebAssembly and run under a capability-limited host.

A pricing/budget/capital rule (#2) is compiled to a WebAssembly module (WAT ->
wasm) that exports one function taking the language's variables as f64 and
imports nothing. The module ships with a manifest (exports, imports, source hash,
wasm hash). The host is wasmtime (Bytecode Alliance, adopted, not rebuilt):

  - the linker defines only the imports the manifest declares AND the host policy
    allows; a module that imports anything else fails to instantiate;
  - WASI, when declared, gets an empty context: no preopened directories, no
    environment, no arguments, no inherited stdio;
  - every call runs on a fuel budget, so a runaway module traps instead of hanging.

The compiled module is checked against the Python interpreter on seeded inputs
(differential test) and the language's output contract is enforced on the result.
Limitation: this uses core WebAssembly modules with a declared manifest, not the
Component Model's WIT interfaces.
"""
from __future__ import annotations

import ast
import hashlib
import json
import math
import random
from pathlib import Path

from foundry.systems import dsl

HOST_ALLOWED_IMPORTS = {("wasi_snapshot_preview1", "*")}
FUEL = 50_000


class WasmError(RuntimeError):
    pass


def _expr(node, variables: list[str]) -> str:
    if isinstance(node, ast.Expression):
        return _expr(node.body, variables)
    if isinstance(node, ast.Constant):
        return f"(f64.const {float(node.value)!r})"
    if isinstance(node, ast.Name):
        return f"(local.get ${node.id})"
    if isinstance(node, ast.BinOp):
        op = {ast.Add: "add", ast.Sub: "sub", ast.Mult: "mul", ast.Div: "div"}[type(node.op)]
        return f"(f64.{op} {_expr(node.left, variables)} {_expr(node.right, variables)})"
    if isinstance(node, ast.UnaryOp):
        v = _expr(node.operand, variables)
        if isinstance(node.op, ast.USub):
            return f"(f64.neg {v})"
        if isinstance(node.op, ast.UAdd):
            return v
        return f"(f64.convert_i32_u (f64.eq {v} (f64.const 0)))"
    if isinstance(node, ast.BoolOp):
        parts = [f"(f64.ne {_expr(v, variables)} (f64.const 0))" for v in node.values]
        joined = parts[0]
        for p in parts[1:]:
            joined = f"(i32.{'and' if isinstance(node.op, ast.And) else 'or'} {joined} {p})"
        return f"(f64.convert_i32_u {joined})"
    if isinstance(node, ast.Compare):
        ops = {ast.Lt: "lt", ast.LtE: "le", ast.Gt: "gt", ast.GtE: "ge", ast.Eq: "eq", ast.NotEq: "ne"}
        terms, left = [], node.left
        for op, right in zip(node.ops, node.comparators):
            terms.append(f"(f64.{ops[type(op)]} {_expr(left, variables)} {_expr(right, variables)})")
            left = right
        joined = terms[0]
        for t in terms[1:]:
            joined = f"(i32.and {joined} {t})"
        return f"(f64.convert_i32_u {joined})"
    if isinstance(node, ast.IfExp):
        return (f"(if (result f64) (f64.ne {_expr(node.test, variables)} (f64.const 0)) "
                f"(then {_expr(node.body, variables)}) (else {_expr(node.orelse, variables)}))")
    if isinstance(node, ast.Call):
        name, args = node.func.id, [_expr(a, variables) for a in node.args]
        if name == "round":
            if len(args) != 1:
                raise WasmError("round(x, ndigits) is not supported in wasm; use round(x)")
            return f"(f64.nearest {args[0]})"
        if not args:
            raise WasmError(f"{name}() needs arguments")
        out = args[0]
        for a in args[1:]:
            out = f"(f64.{name} {out} {a})"
        return out
    raise WasmError(f"cannot compile {type(node).__name__}")


def compile_rule(language: str, source: str) -> dict:
    tree = dsl.parse(language, source)          # the DSL owner validates first
    variables = sorted(dsl.LANGUAGES[language]["variables"])
    params = " ".join(f"(param ${v} f64)" for v in variables)
    wat = f'(module (func (export "rule") {params} (result f64) {_expr(tree, variables)}))'
    import wasmtime
    wasm = wasmtime.wat2wasm(wat)
    manifest = {"language": language, "exports": {"rule": {"params": variables, "result": "f64"}}, "imports": [],
                "source_sha256": hashlib.sha256(source.encode()).hexdigest(),
                "wasm_sha256": hashlib.sha256(bytes(wasm)).hexdigest()}
    return {"wat": wat, "wasm": bytes(wasm), "manifest": manifest}


def _allowed(module_name: str, name: str) -> bool:
    return (module_name, name) in HOST_ALLOWED_IMPORTS or (module_name, "*") in HOST_ALLOWED_IMPORTS


def instantiate(wasm: bytes, manifest: dict):
    import wasmtime
    config = wasmtime.Config()
    config.consume_fuel = True
    # Independent appraisers fork after earlier native use. A compiler pool
    # inherited without its threads can otherwise retain unreleasable locks.
    config.parallel_compilation = False
    engine = wasmtime.Engine(config)
    module = wasmtime.Module(engine, wasm)
    if hashlib.sha256(wasm).hexdigest() != manifest["wasm_sha256"]:
        raise WasmError("module bytes do not match the manifest hash")
    declared = {(i["module"], i["name"]) for i in manifest["imports"]}
    for imp in module.imports:
        key = (imp.module, imp.name)
        if key not in declared:
            raise WasmError(f"module imports {imp.module}.{imp.name}, which its manifest does not declare")
        if not _allowed(*key):
            raise WasmError(f"host policy does not allow import {imp.module}.{imp.name}")
    store = wasmtime.Store(engine)
    store.set_fuel(FUEL)
    linker = wasmtime.Linker(engine)
    if any(m == "wasi_snapshot_preview1" for m, _ in declared):
        store.set_wasi(wasmtime.WasiConfig())      # empty: no preopens, env, args or stdio
        linker.define_wasi()
    instance = linker.instantiate(store, module)
    return store, instance


def run(wasm: bytes, manifest: dict, inputs: dict) -> float:
    import wasmtime
    store, instance = instantiate(wasm, manifest)
    fn = instance.exports(store)["rule"]
    params = manifest["exports"]["rule"]["params"]
    try:
        value = fn(store, *[float(inputs.get(p, 0.0)) for p in params])
    except wasmtime.Trap as exc:
        raise WasmError(f"trap: {str(exc).splitlines()[0]}") from None
    except wasmtime.WasmtimeError as exc:
        raise WasmError(f"host error: {str(exc).splitlines()[0]}") from None
    if not math.isfinite(value):
        raise WasmError("non-finite result (e.g. division by zero)")
    spec = dsl.LANGUAGES[manifest["language"]]
    if spec["min"] is not None and value < spec["min"]:
        raise WasmError(f"result {value} below {spec['min']}")
    ceiling = inputs.get(spec["max"]) if isinstance(spec["max"], str) else spec["max"]
    if ceiling is not None and value > ceiling:
        raise WasmError(f"result {value} exceeds {spec['max']}={ceiling}")
    return value


def differential(language: str, source: str, *, cases: int = 200, seed: int = 11) -> dict:
    comp = compile_rule(language, source)
    rng = random.Random(seed)
    variables = sorted(dsl.LANGUAGES[language]["variables"])
    agree = disagree = both_refused = 0
    first = None
    for _ in range(cases):
        inputs = {v: rng.choice([0, 1, 2, 3, rng.randint(1, 50), round(rng.uniform(0, 500), 2)]) for v in variables}
        try:
            py = dsl.run(language, source, inputs)
        except (dsl.RuleError, ZeroDivisionError):
            py = None
        try:
            wa = run(comp["wasm"], comp["manifest"], inputs)
        except WasmError:
            wa = None
        if py is None and wa is None:
            both_refused += 1
        elif py is not None and wa is not None and math.isclose(float(py), wa, rel_tol=1e-12, abs_tol=1e-9):
            agree += 1
        else:
            disagree += 1
            first = first or {"inputs": inputs, "python": py, "wasm": wa}
    return {"agree": agree, "both_refused": both_refused, "disagree": disagree, "first_disagreement": first}


def _store(args, root):
    comp = compile_rule(args["language"], args["source"])
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    name = comp["manifest"]["wasm_sha256"][:16]
    (root / f"{name}.wasm").write_bytes(comp["wasm"])
    (root / f"{name}.json").write_text(json.dumps(comp["manifest"], sort_keys=True, indent=1))
    return {"component": name, "manifest": comp["manifest"]}


def _run_stored(args, root):
    root = Path(root)
    return {"value": run((root / f"{args['component']}.wasm").read_bytes(),
                         json.loads((root / f"{args['component']}.json").read_text()), args["inputs"])}


QUERY_OPS = {"run": _run_stored,
             "differential": lambda a, r: differential(a["language"], a["source"], cases=int(a.get("cases", 200)))}
APPLY_OPS = {"compile": _store}


def exercise(root) -> dict:
    import wasmtime
    src = "max(base_price * units * (1 - 0.05 * customer_tier), cost_per_unit * units * 1.2) if units > 0 else 0"
    stored = _store({"language": "pricing", "source": src}, root)
    value = _run_stored({"component": stored["component"], "inputs": {"base_price": 100, "units": 3,
                                                                       "customer_tier": 2, "cost_per_unit": 50}}, root)
    diff = differential("pricing", src)
    budget = differential("budget", "min(requested, remaining - reserve) if remaining > reserve else 0")
    refusals = {}
    def refused(label, fn):
        try:
            fn()
            refusals[label] = None
        except WasmError as exc:
            refusals[label] = str(exc)
    sneaky = wasmtime.wat2wasm('(module (import "wasi_snapshot_preview1" "fd_write" '
                               '(func (param i32 i32 i32 i32) (result i32))) (func (export "rule") (result f64) (f64.const 1)))')
    manifest = {"language": "pricing", "exports": {"rule": {"params": [], "result": "f64"}}, "imports": [],
                "wasm_sha256": hashlib.sha256(bytes(sneaky)).hexdigest()}
    refused("undeclared_wasi_import", lambda: run(bytes(sneaky), manifest, {}))
    net = wasmtime.wat2wasm('(module (import "net" "connect" (func (param i32) (result i32))) '
                            '(func (export "rule") (result f64) (f64.const 1)))')
    refused("declared_but_host_forbids", lambda: run(bytes(net), {**manifest, "imports": [{"module": "net", "name": "connect"}],
                                                                   "wasm_sha256": hashlib.sha256(bytes(net)).hexdigest()}, {}))
    loop = wasmtime.wat2wasm('(module (func (export "rule") (result f64) (loop $l (br $l)) (f64.const 0)))')
    refused("runaway_loop_out_of_fuel", lambda: run(bytes(loop), {**manifest, "wasm_sha256": hashlib.sha256(bytes(loop)).hexdigest()}, {}))
    refused("tampered_bytes", lambda: run(bytes(loop), manifest, {}))
    declared_wasi = {**manifest, "imports": [{"module": "wasi_snapshot_preview1", "name": "fd_write"}]}
    wasi_ok = run(bytes(sneaky), declared_wasi, {})   # declared + allowed: links against an empty WASI context
    return {"component": stored["manifest"]["exports"], "value": value, "pricing_differential": diff,
            "budget_differential": budget, "refusals": refusals, "declared_wasi_instantiates": wasi_ok == 1.0}
