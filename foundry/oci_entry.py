"""Bounded JSON entrypoint for the existing restricted rule capability image."""
from __future__ import annotations

import importlib.util
import json
import math
from pathlib import Path
import sys


def evaluate(request, dsl_path=None):
    if not isinstance(request, dict) or set(request) != {"language", "source", "inputs"}:
        raise ValueError("exact language/source/inputs request required")
    if not isinstance(request["source"], str) or len(request["source"].encode()) > 4096:
        raise ValueError("rule source exceeds bounds")
    inputs = request["inputs"]
    if not isinstance(inputs, dict) or len(inputs) > 16 or any(
            not isinstance(k, str) or type(v) not in (int, float) or
            not math.isfinite(v) or abs(v) > 1e12 for k, v in inputs.items()):
        raise ValueError("finite bounded numeric inputs required")
    path = dsl_path or Path(__file__).with_name("dsl.py")
    spec = importlib.util.spec_from_file_location("owned_restricted_dsl", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if request["language"] not in module.LANGUAGES or set(inputs) - module.LANGUAGES[request["language"]]["variables"]:
        raise ValueError("unknown language or inputs")
    result = module.run(request["language"], request["source"], inputs)
    if not math.isfinite(result):
        raise ValueError("non-finite result refused")
    return {"value": result}


def main():
    try:
        raw = sys.stdin.buffer.read(16385)
        if len(raw) > 16384:
            raise ValueError("request exceeds bounds")
        out = evaluate(json.loads(raw))
    except (ValueError, TypeError, KeyError, ZeroDivisionError, OverflowError, RecursionError) as exc:
        out = {"error": str(exc)[:200]}
    print(json.dumps(out, sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()
