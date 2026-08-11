"""P4 gate — freeze the evaluator before any candidate exists.

Closure condition 3 requires candidates to be generated *after* the evaluator is
frozen, and condition 4 requires they cannot inspect or influence decisive
evaluation. Neither is checkable while the evaluator is just a directory that
might change.

So: hash every evaluator file, record the digests, and make drift loud. This is
the same self-sealing mechanism as ``runtime/contract.py`` applied one layer out
— an amendment stays possible and stops being silent.

What this does NOT do is prove isolation. That is
``runtime/evaluator/isolation.py``, which is already proven with three-way
discrimination. Freezing answers a different question: not "can a candidate
reach the evaluator" but "is the evaluator the same one it was when the
candidates were made".
"""
from __future__ import annotations

import hashlib
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))

#: Files whose content defines the evaluation. Held-out cases are excluded on
#: purpose: their *existence* is asserted, their content is never read here, and
#: hashing them would put their digest in a file candidates can see.
FROZEN_MEMBERS = ("isolation.py", "chamber.sh", "hostile_probe.sh", "freeze.py")

#: Recorded digests. Empty until frozen; ``verify()`` reports NOT_FROZEN rather
#: than passing vacuously, because an empty expectation matches nothing and
#: would otherwise read as agreement.
FROZEN_DIGESTS: dict[str, str] = {
    "chamber.sh": "e314bb46e1e0461a40d1450e1b4af42c0c64cd3fddbc9ada4a3065a1bab349bb",
    "hostile_probe.sh": "48f474d3dead67ed367183d315aaa8d515792595de601a3eb2fb45a5534edd35",
    "isolation.py": "c799d550fccbb0d7e0b7591a5f70f9c64337449f14ebf56d1a4a6d5ce124da5c",
}


def digest_file(path: str) -> str:
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def current_digests() -> dict[str, str]:
    """Hash every frozen member that exists, skipping this module's own record."""
    out = {}
    for name in FROZEN_MEMBERS:
        if name == "freeze.py":
            continue                    # self-reference: the record is not the subject
        path = os.path.join(HERE, name)
        if os.path.exists(path):
            out[name] = digest_file(path)
    return out


def evaluator_digest() -> str:
    """One digest over the whole evaluator, order-independent."""
    canonical = json.dumps(current_digests(), sort_keys=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def verify() -> tuple[str, dict]:
    """Compare recorded digests with reality.

    Returns ``(status, detail)`` where status is ``FROZEN_AND_UNCHANGED``,
    ``NOT_FROZEN`` or ``DRIFTED``. Three outcomes rather than a boolean, because
    "never frozen" and "frozen and matching" must never collapse into the same
    answer.
    """
    current = current_digests()
    if not FROZEN_DIGESTS:
        return "NOT_FROZEN", {"current": current, "recorded": {}}
    missing = [n for n in current if n not in FROZEN_DIGESTS]
    drifted = {n: {"recorded": FROZEN_DIGESTS[n], "current": current[n]}
               for n in current if n in FROZEN_DIGESTS and FROZEN_DIGESTS[n] != current[n]}
    absent = [n for n in FROZEN_DIGESTS if n not in current]
    if missing or drifted or absent:
        return "DRIFTED", {"unrecorded": missing, "drifted": drifted, "absent": absent}
    return "FROZEN_AND_UNCHANGED", {"digest": evaluator_digest(), "members": current}


if __name__ == "__main__":       # pragma: no cover - manual invocation
    import sys

    status, detail = verify()
    print(json.dumps({"status": status, "evaluator_digest": evaluator_digest(),
                      "detail": detail}, indent=2, sort_keys=True))
    sys.exit(0 if status == "FROZEN_AND_UNCHANGED" else 1)
