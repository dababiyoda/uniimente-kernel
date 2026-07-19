"""Isolated experiment worker for the fast loop.

Runs inside a scrubbed subprocess spawned by IsolatedRunner. Reads the
request file named in argv[1] ({"module", "function", "kwargs"}), imports
the target, calls it, and prints exactly one JSON result line to stdout:
{"ok": true, "outcome": {...}} or {"ok": false, "error": "..."}. The
runner parses only the final non-empty stdout line; everything else is
an invalid outcome. Exceptions in the target are reported, never
swallowed, and never re-raised past the JSON line.
"""

import importlib
import json
import sys
import traceback


def main() -> int:
    request_path = sys.argv[1]
    with open(request_path, "r", encoding="utf-8") as handle:
        request = json.load(handle)
    try:
        module = importlib.import_module(request["module"])
        target = getattr(module, request["function"])
        outcome = target(**request.get("kwargs", {}))
    except Exception as exc:  # noqa: BLE001 - reported as data, by design
        print(json.dumps({
            "ok": False,
            "error": f"{type(exc).__name__}: {exc}",
            "traceback_tail": traceback.format_exc()[-2000:],
        }))
        return 0
    print(json.dumps({"ok": True, "outcome": outcome}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
