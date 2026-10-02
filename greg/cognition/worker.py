"""Fixed local numeric worker. Invoked by the existing network-isolated process adapter."""
from __future__ import annotations

import json
import math
from pathlib import Path
import resource
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from greg.cognition.contracts import CognitionError, canonical  # noqa: E402
from greg.cognition.solvers import SOLVERS  # noqa: E402


def main():
    family, request_json = sys.argv[1:]
    request = json.loads(request_json)
    seconds = max(1, math.ceil(request["geometry"]["latency_limit"]))
    resource.setrlimit(resource.RLIMIT_CPU, (seconds, seconds + 1))
    if sys.platform != "darwin":
        resource.setrlimit(resource.RLIMIT_AS, (2 * 1024**3, 2 * 1024**3))
    try:
        if family == "verify":
            from greg.cognition.verification import verify
            answer = verify(request["family"], request["data"], request["answer"], request["proof_class"])
            answer["execution_contract"] = "separate network-denied process, scrubbed environment, bounded CPU/RAM"
        else:
            answer = SOLVERS[family](request["data"], request["geometry"])
        text = canonical(answer)
        if len(text.encode()) > 256 * 1024:
            raise CognitionError("solver output exceeds 256 KiB")
        print(text)
    except (CognitionError, ValueError, TypeError, KeyError, ZeroDivisionError, SyntaxError) as exc:
        print(canonical({"error": "MODEL_INVALID", "detail": str(exc)[:300]}))
    except ImportError as exc:
        print(canonical({"error": "DEPENDENCY_UNAVAILABLE", "detail": str(exc)[:300]}))


if __name__ == "__main__":
    main()
