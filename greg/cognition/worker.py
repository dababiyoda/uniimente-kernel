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


def cortex_main(request):
    """Run the Polyintelligence Cortex inside this bounded, network-isolated process.

    The body supplies which organs GREG's registry withholds (founder detach) and,
    only when the founder selected a local model, the loopback model to use. The
    receipt is printed; the body re-validates it before anything is retained."""
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
        from greg.cognition.learned_routing import ledger_from_records
        memory = ledger_from_records(json.loads(sys.stdin.read(64 * 1024 * 1024)))
    cortex = Cortex(registry, clock=lambda: request["created_at"], memory=memory)
    cortex.organs["cortex.semantic@0.1.0"] = SemanticOrgan(client)
    # The extractor reads free text only through a founder-selected model; otherwise the
    # controlled grammar alone, and out-of-grammar text abstains (DEPENDENCY_UNAVAILABLE).
    cortex.organs["cortex.extraction.schedule@0.1.0"] = ScheduleExtractionOrgan(client if model else None)
    receipt = cortex.run(request["problem"], records=request.get("records"))
    text = canonical(receipt)
    if len(text.encode()) > 512 * 1024:
        raise CognitionError("cortex receipt exceeds 512 KiB")
    print(text)


class _NoSelectedModel:
    """GREG's founder-selected route names no local model: the semantic organ abstains."""
    def complete(self, system, user):
        raise OSError("no founder-selected local model (greg model set --route ollama --local-model <name> --key ...)")


def main():
    family, request_json = sys.argv[1:]
    request = json.loads(request_json)
    if family == "__cortex__":
        try:
            cortex_main(request)
        except (CognitionError, ValueError, TypeError, KeyError) as exc:
            print(canonical({"error": "MODEL_INVALID", "detail": str(exc)[:300]}))
        except ImportError as exc:
            print(canonical({"error": "DEPENDENCY_UNAVAILABLE", "detail": str(exc)[:300]}))
        return
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
