"""Fixed local numeric worker. Invoked by the existing network-isolated process adapter."""
from __future__ import annotations

import json
import math
import os
from pathlib import Path
import resource
import sys
import time

# The verifier's certificate may spend what is left of its caller's budget: the request's ``deadline`` (wall-clock
# seconds, so it counts this process's start-up, which this process cannot time: 60-140 ms of fork, network filter and
# interpreter before this line on one core of a shared machine, 2026-10-15, and 200-400 ms with three other busy
# processes on the core), and never more than the latency limit timed from here. The reserve is for what follows the
# certificate's first budget test: importing Z3 when it passes, then returning the answer (its emit, this process's
# exit and the caller's parse took 40-50 ms there, and 120-155 ms with the core shared four ways). Those slow down with
# the machine, as this process's own imports below do, and took 0.7-0.9 times as long as them; so the reserve is twice
# those imports, and never under VERIFY_RESERVE_SECONDS. With the core shared three or four ways, a fixed 0.25 s timed
# out 7 of 16 verifications at a 1.3 s limit (a little budget passed the first test, then the Z3 import outlasted the
# reserve); this reserve timed out none, as did a worker that never runs the certificate.
STARTED = time.monotonic()
VERIFY_RESERVE_SECONDS = 0.25
MAX_STDIN_REQUEST = 4 * 1024 * 1024

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from greg.cognition.contracts import CognitionError, canonical  # noqa: E402
from greg.cognition.solvers import SOLVERS  # noqa: E402


def _result_channel():
    """The worker's one JSON result is the only thing its stdout may carry. Native code inside a solver or verifier
    (a HiGHS debug line, a BLAS warning, C stdio flushed at exit) writes to file descriptor 1 directly, below Python's
    ``sys.stdout``; one such line made the caller read 'Extra data' and abstain on a valid model. From here on
    descriptor 1 is stderr, for Python and native writes alike, and the result goes to a private duplicate of the
    original stdout that nothing else holds."""
    sys.stdout.flush()
    result = os.dup(1)
    os.dup2(2, 1)
    channel = os.fdopen(result, "w", encoding="utf-8")

    def emit(text):
        channel.write(text + "\n")
        channel.flush()
    return emit


def cortex_main(request, emit):
    """Run the Polyintelligence Cortex inside this bounded, network-isolated process.

    The body supplies which organs GREG's registry withholds (founder detach) and,
    only when the founder selected a local model, the loopback model to use. The
    receipt is emitted; the body re-validates it before anything is retained."""
    from cortex.genome import seed_registry
    from cortex.organs.schedule_extraction import ScheduleExtractionOrgan
    from cortex.organs.semantic import SemanticOrgan
    from cortex.routing import Cortex
    seconds = max(1, math.ceil(request["cpu_seconds"]))
    resource.setrlimit(resource.RLIMIT_CPU, (seconds, seconds + 1))
    if sys.platform != "darwin":
        resource.setrlimit(resource.RLIMIT_AS, (3 * 1024**3, 3 * 1024**3))
    registry = seed_registry()
    for key, why in request["withheld"].items():
        registry.withhold(key, why)
    model = request.get("semantic_model")
    if model:
        from egregore.local_model import LocalModelClient, LocalModelConfig
        client = LocalModelClient(LocalModelConfig(model=model["model"], timeout_seconds=model["timeout_seconds"],
                                                   max_tokens=model["max_tokens"]))
    else:
        client = _NoSelectedModel()
    memory = None
    if request.get("learned_memory"):
        # Signed learned mode: content-addressed records on stdin; any mismatch refuses the run.
        from greg.cognition.learned_routing import conditional, ledger_from_records
        memory = conditional(ledger_from_records(json.loads(sys.stdin.read(64 * 1024 * 1024))),
                             request["problem"].get("payload"))
    cortex = Cortex(registry, clock=lambda: request["created_at"], memory=memory)
    cortex.organs["cortex.semantic@0.1.0"] = SemanticOrgan(client)
    # The extractor reads free text only through a founder-selected model; otherwise the
    # controlled grammar alone, and out-of-grammar text abstains (DEPENDENCY_UNAVAILABLE).
    cortex.organs["cortex.extraction.schedule@0.1.0"] = ScheduleExtractionOrgan(client if model else None)
    receipt = cortex.run(request["problem"], records=request.get("records"),
                         **({"authority_as_of": request["authority_as_of"]} if request.get("authority_as_of") else {}))
    text = canonical(receipt)
    if len(text.encode()) > 512 * 1024:
        raise CognitionError("cortex receipt exceeds 512 KiB")
    emit(text)


class _NoSelectedModel:
    """GREG's founder-selected route names no local model: the semantic organ abstains."""
    def complete(self, system, user):
        raise OSError("no founder-selected local model (greg model set --route ollama --local-model <name> --key ...)")


def main():
    emit = _result_channel()
    if len(sys.argv) == 2:
        # numeric solve or verify: the request arrives on stdin, bounded (data up to 1 MiB plus an answer)
        family, request_json = sys.argv[1], sys.stdin.read(MAX_STDIN_REQUEST + 1)
        if len(request_json) > MAX_STDIN_REQUEST:
            emit(canonical({"error": "MODEL_INVALID", "detail": "request on stdin exceeds 4 MiB"}))
            return
    else:
        family, request_json = sys.argv[1:]
    request = json.loads(request_json)
    if family == "__cortex__":
        try:
            cortex_main(request, emit)
        except (CognitionError, ValueError, TypeError, KeyError) as exc:
            emit(canonical({"error": "MODEL_INVALID", "detail": str(exc)[:300]}))
        except ImportError as exc:
            emit(canonical({"error": "DEPENDENCY_UNAVAILABLE", "detail": str(exc)[:300]}))
        return
    seconds = max(1, math.ceil(request["geometry"]["latency_limit"]))
    resource.setrlimit(resource.RLIMIT_CPU, (seconds, seconds + 1))
    if sys.platform != "darwin":
        resource.setrlimit(resource.RLIMIT_AS, (2 * 1024**3, 2 * 1024**3))
    try:
        if family == "verify":
            from greg.cognition.verification import verify
            # the certificate gets what is left of the budget, less the reserve: an answer that verifies is never
            # lost to a check it cannot afford
            reserve = max(VERIFY_RESERVE_SECONDS, 2 * (time.monotonic() - STARTED))
            deadline = min(STARTED + request["geometry"]["latency_limit"],
                           time.monotonic() + request.get("deadline", math.inf) - time.time())
            answer = verify(request["family"], request["data"], request["answer"], request["proof_class"],
                            deadline=deadline - reserve)
            answer["execution_contract"] = "separate network-denied process, scrubbed environment, bounded CPU/RAM"
        else:
            answer = SOLVERS[family](request["data"], request["geometry"])
        text = canonical(answer)
        if len(text.encode()) > 256 * 1024:
            raise CognitionError("solver output exceeds 256 KiB")
        emit(text)
    except (CognitionError, ValueError, TypeError, KeyError, ZeroDivisionError, SyntaxError) as exc:
        emit(canonical({"error": "MODEL_INVALID", "detail": str(exc)[:300]}))
    except ImportError as exc:
        emit(canonical({"error": "DEPENDENCY_UNAVAILABLE", "detail": str(exc)[:300]}))


if __name__ == "__main__":
    main()
