"""#2 Restricted DSLs: narrow languages for pricing, budgets and capital rules.

A rule is a small expression language parsed with Python's ``ast`` and
evaluated by a whitelist interpreter: numbers, declared variables, + - * /,
comparisons, and/or/not, ``min``/``max``/``round`` and ``if-else``. Anything
else (attribute access, calls to other names, imports, lambdas, comprehensions,
subscripts) is rejected at parse time with the offending construct named, so
an agent can describe one narrow operation but cannot run code.

Each language declares its variables and an output contract; a budget rule
that could exceed its ceiling or a price rule that yields a negative number is
refused when it runs.
"""
from __future__ import annotations

import ast
import math

MAX_SOURCE_BYTES = 8192
MAX_NODES = 128
MAX_DEPTH = 24
MAX_MAGNITUDE = 1e100

FUNCS = {"min": min, "max": max, "round": round}
_BIN = {ast.Add: lambda a, b: a + b, ast.Sub: lambda a, b: a - b, ast.Mult: lambda a, b: a * b,
        ast.Div: lambda a, b: a / b}
_CMP = {ast.Lt: lambda a, b: a < b, ast.LtE: lambda a, b: a <= b, ast.Gt: lambda a, b: a > b,
        ast.GtE: lambda a, b: a >= b, ast.Eq: lambda a, b: a == b, ast.NotEq: lambda a, b: a != b}
LANGUAGES = {
    "pricing": {"variables": {"base_price", "units", "customer_tier", "cost_per_unit"}, "min": 0, "max": None},
    "budget": {"variables": {"remaining", "requested", "reserve"}, "min": 0, "max": "remaining"},
    "capital": {"variables": {"surplus", "obligations", "reserve_pct"}, "min": 0, "max": "surplus"},
}


class RuleError(ValueError):
    """Out-of-grammar construct, undeclared variable, or output outside its contract."""


def parse(language: str, source: str) -> ast.Expression:
    if language not in LANGUAGES:
        raise RuleError(f"unknown language {language!r}")
    if not isinstance(source, str) or len(source.encode()) > MAX_SOURCE_BYTES:
        raise RuleError("source exceeds the restricted language ceiling")
    try:
        tree = ast.parse(source, mode="eval")
    except (SyntaxError, RecursionError, ValueError) as exc:
        raise RuleError(f"invalid restricted expression: {exc}") from None
    nodes = list(ast.walk(tree))
    if len(nodes) > MAX_NODES:
        raise RuleError("expression operation ceiling exceeded")
    def depth(node, n=0):
        if n > MAX_DEPTH:
            raise RuleError("expression nesting ceiling exceeded")
        for child in ast.iter_child_nodes(node):
            depth(child, n + 1)
    depth(tree)
    allowed_vars = LANGUAGES[language]["variables"]
    for node in ast.walk(tree):
        if isinstance(node, (ast.Expression, ast.Load, ast.And, ast.Or, ast.Not, ast.USub, ast.UAdd)):
            continue
        if type(node) in _BIN or type(node) in _CMP:  # whitelisted operator tokens
            continue
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float, bool)) and not isinstance(node.value, complex):
            continue
        if isinstance(node, ast.Name):
            if node.id not in allowed_vars and node.id not in FUNCS:
                raise RuleError(f"undeclared name {node.id!r} (col {node.col_offset})")
            continue
        if isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name) or node.func.id not in FUNCS or node.keywords:
                raise RuleError(f"only {sorted(FUNCS)} may be called (col {node.col_offset})")
            continue
        if isinstance(node, (ast.BinOp,)) and type(node.op) in _BIN:
            continue
        if isinstance(node, ast.Compare) and all(type(o) in _CMP for o in node.ops):
            continue
        if isinstance(node, (ast.BoolOp, ast.UnaryOp, ast.IfExp)):
            continue
        raise RuleError(f"{type(node).__name__} is not part of the {language} language (col {getattr(node, 'col_offset', '?')})")
    return tree


def _eval(node, env):
    if isinstance(node, ast.Expression):
        return _eval(node.body, env)
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.Name):
        if node.id not in env:
            raise RuleError(f"missing input {node.id!r}")
        return env[node.id]
    if isinstance(node, ast.BinOp):
        return _BIN[type(node.op)](_eval(node.left, env), _eval(node.right, env))
    if isinstance(node, ast.UnaryOp):
        v = _eval(node.operand, env)
        return -v if isinstance(node.op, ast.USub) else (+v if isinstance(node.op, ast.UAdd) else not v)
    if isinstance(node, ast.BoolOp):
        values = [_eval(v, env) for v in node.values]
        return all(values) if isinstance(node.op, ast.And) else any(values)
    if isinstance(node, ast.Compare):
        left = _eval(node.left, env)
        for op, comparator in zip(node.ops, node.comparators):
            right = _eval(comparator, env)
            if not _CMP[type(op)](left, right):
                return False
            left = right
        return True
    if isinstance(node, ast.IfExp):
        return _eval(node.body, env) if _eval(node.test, env) else _eval(node.orelse, env)
    if isinstance(node, ast.Call):
        return FUNCS[node.func.id](*[_eval(a, env) for a in node.args])
    raise RuleError(f"cannot evaluate {type(node).__name__}")


def run(language: str, source: str, inputs: dict):
    tree = parse(language, source)
    env = {k: v for k, v in inputs.items() if k in LANGUAGES[language]["variables"]}
    if any(type(v) not in (int, float) or not math.isfinite(v) or abs(v) > MAX_MAGNITUDE for v in env.values()):
        raise RuleError("inputs must be finite bounded numbers")
    try:
        value = _eval(tree, env)
    except (ArithmeticError, TypeError, ValueError) as exc:
        raise RuleError(f"numeric evaluation refused: {type(exc).__name__}") from None
    spec = LANGUAGES[language]
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise RuleError(f"{language} rules must produce a number")
    if not math.isfinite(value) or abs(value) > MAX_MAGNITUDE:
        raise RuleError("result exceeds finite numeric limits")
    if spec["min"] is not None and value < spec["min"]:
        raise RuleError(f"{language} result {value} is below {spec['min']}")
    ceiling = inputs.get(spec["max"]) if isinstance(spec["max"], str) else spec["max"]
    if ceiling is not None and value > ceiling:
        raise RuleError(f"{language} result {value} exceeds {spec['max']}={ceiling}")
    return value


QUERY_OPS = {"run": lambda a, r: {"value": run(a["language"], a["source"], a.get("inputs", {}))},
             "check": lambda a, r: (parse(a["language"], a["source"]), {"valid": True})[1]}
APPLY_OPS: dict = {}


def exercise(root) -> dict:
    price = run("pricing", "max(base_price * units * (0.8 if customer_tier == 2 else 1), cost_per_unit * units * 1.2)",
                {"base_price": 49, "units": 10, "customer_tier": 2, "cost_per_unit": 30})
    budget = run("budget", "min(requested, remaining - reserve)", {"remaining": 1000, "requested": 1500, "reserve": 200})
    refused = {}
    for label, lang, src, inputs in (
            ("import", "pricing", "__import__('os').system('id')", {}),
            ("attribute", "pricing", "base_price.real", {"base_price": 1}),
            ("undeclared", "budget", "requested + bonus", {"requested": 1}),
            ("lambda", "pricing", "(lambda: 1)()", {}),
            ("over_ceiling", "budget", "requested * 2", {"requested": 600, "remaining": 1000, "reserve": 0}),
            ("negative_price", "pricing", "base_price - 100", {"base_price": 10})):
        try:
            run(lang, src, inputs)
            refused[label] = False
        except RuleError:
            refused[label] = True
    return {"price": price, "budget": budget, "refused": refused}
