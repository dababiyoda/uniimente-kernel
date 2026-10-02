"""Shared protocol for organs that recruit founder-attached formed functions.

Capability Genesis (PR #143) forms functions such as ``graph.shortest_path`` and
``lp.optimize`` from installed open-source packages: a frozen oracle qualifies the
package, the founder attaches it, and every later call re-pins the package digest and
accepts the engine's output only when GREG's own certificate (sharing no code with the
engine) proves it. The organs in ``graphsearch.py`` and ``continuous.py`` bring those
functions behind the cortex's one entry (``cognition.solve`` with a cortex payload).

Layering: the cortex never imports ``greg`` and never sees the GREG registry. The body
(``greg/cognition/bridge.py``) resolves which formed functions are attached and usable,
serializes their Mechanism Cards into the worker request, and the worker
(``greg/cognition/worker.py``) builds the callables this module's organs invoke.

Callable protocol
-----------------
``formed`` maps function name (``"graph.shortest_path"``, ...) to
``(callable | None, why_if_none)``. The callable takes ``(params, cpu_seconds)`` and
returns ``{"answer": <certified answer>, "solver_calls": int}``. The answer carries a
``"_mechanism"`` transport field (capability id, distribution, version, license,
package digest, runner, request digest/shape) which the organ moves into the proof and
never into the answer. The callable raises :class:`FormedFunctionError` with:

* ``kind="invalid"``      — the request is outside the function's competence envelope
                            (its ``normalize_*`` refused it) -> MALFORMED_INPUT
* ``kind="unavailable"``  — package missing/changed since qualification, or the engine
                            failed to run -> DEPENDENCY_UNAVAILABLE (a genesis trigger,
                            never a claim)
* ``kind="timeout"``      — the bounded runner did not finish -> TIMEOUT
* ``kind="certificate"``  — the engine answered but GREG's certificate disproved it
                            -> INCONCLUSIVE with the claim withheld
"""
from __future__ import annotations

import time

from ..contracts import Expenditure, OrganResult

KINDS = ("invalid", "unavailable", "timeout", "certificate")

# FormedFunctionError.kind -> cortex state. "certificate" is INCONCLUSIVE, never a
# failure of the request: the engine's claim is withheld, nothing is asserted.
STATE_OF = {"invalid": "MALFORMED_INPUT", "unavailable": "DEPENDENCY_UNAVAILABLE",
            "timeout": "TIMEOUT", "certificate": "INCONCLUSIVE"}


class FormedFunctionError(Exception):
    """A formed function could not produce a certified answer; ``kind`` says why."""

    def __init__(self, kind: str, why: str):
        if kind not in KINDS:
            raise ValueError(f"unknown formed-function failure kind {kind!r}")
        super().__init__(why)
        self.kind, self.why = kind, why


def fail(organ_id: str, version: str, state: str, why: str, started: float, *,
         function: str | None = None, calls: int = 0) -> OrganResult:
    """A truthful no-claim result for one formed-function organ."""
    proof = {"proof_class": "optimization", "scope": "valid_given_encoding", "failure": why,
             "unverified_premises": [], "original_requirement": ""}
    if function is not None:
        proof["function"] = function
    return OrganResult(organ_id=organ_id, organ_version=version, state=state, answer=None,
                       proof=proof, uncertainty="no result",
                       expenditure=Expenditure(seconds=time.perf_counter() - started, solver_calls=calls),
                       dependencies=(f"formed:{function}",) if function else (),
                       origin="solver", notes=(why,))


def formed_failure(organ_id: str, version: str, exc: FormedFunctionError, started: float, *,
                   function: str, dependencies: tuple = ()) -> OrganResult:
    """Map a FormedFunctionError to a state; a certificate failure withholds the claim."""
    state = STATE_OF[exc.kind]
    why = exc.why
    if exc.kind == "certificate":
        why = f"the engine's answer failed GREG's certificate; nothing is claimed: {exc.why}"
    elif exc.kind == "unavailable":
        why = f"{exc.why}"
    proof = {"proof_class": "optimization", "scope": "valid_given_encoding", "failure": why,
             "failure_kind": exc.kind, "function": function,
             "unverified_premises": [], "original_requirement": ""}
    return OrganResult(organ_id=organ_id, organ_version=version, state=state, answer=None,
                       proof=proof, uncertainty="no result",
                       expenditure=Expenditure(seconds=time.perf_counter() - started),
                       dependencies=dependencies or (f"formed:{function}",),
                       origin="solver", notes=(why,))


def proof_for(function: str, answer: dict, mechanism: dict, falsification: str,
              shape: dict) -> dict:
    """The typed proof artifact for a certified formed-function answer.

    Carries the Mechanism Card identity (capability id, engine, digest) so the receipt
    traces exactly which qualified package produced the answer, and GREG's certificate
    so the claim is checkable without the engine. The normalized request is digested,
    not embedded: the 64 KiB request bound keeps answers small, but request bodies are
    reproducible from the digest-pinned package and are not receipt material.
    """
    return {
        "proof_class": "optimization",
        "scope": "valid_given_encoding",
        "function": function,
        "formed_capability": mechanism["capability_id"],
        "engine": {"distribution": mechanism["distribution"], "version": mechanism["version"],
                   "license": mechanism["license"], "runner": mechanism["runner"]},
        "package_digest": mechanism["package_digest"],
        "normalized_request_sha256": mechanism["request_sha256"],
        "shape": shape,
        "certificate": answer.get("certificate"),
        "certificate_authority": "GREG-owned exact check sharing no code with the engine",
        "falsification": falsification,
        "unverified_premises": [],
        "original_requirement": "",
        "requirement_encoding": "the payload is already structured; the function's own normalize step "
                                "enforces its competence envelope before the engine sees any input",
    }
