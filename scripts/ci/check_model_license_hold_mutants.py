"""Mutants for the license hold that must not crash the body.

    python scripts/ci/check_model_license_hold_mutants.py

Each mutant removes one safeguard. The route tests must fail. The working tree
is restored after every mutant. Exit status 1 if any mutant survives or the
pattern is no longer unique.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TESTS = ["tests/unit/test_greg_model_license_route.py"]
MUTANTS = [
    ("a license change still raises out of the body",
     "greg/model_license_hold.py",
     "        if not _is_license_refusal(exc):\n            raise\n        stored = _stored_selection(journal)",
     "        if True:\n            raise\n        stored = _stored_selection(journal)"),
    ("a hold keeps the ollama route",
     "greg/model_license_hold.py",
     'kept = [name for name in order if name != "ollama"] if isinstance(order, list) else []',
     "kept = [name for name in order if True] if isinstance(order, list) else []"),
    ("admit runs before validate",
     "greg/model_license_hold.py",
     "    validated = models.validate_route_selection(body)\n    return validated, admit_after_validate(validated)",
     "    admitted = admit_after_validate(body)\n    validated = models.validate_route_selection(body)\n    return validated, admitted"),
    ("replay does not call admit after validate",
     "greg/model_license_hold.py",
     "        return gate_model_config(selection if isinstance(selection, dict) else {})\n    return admit_after_validate(selection)",
     "        return gate_model_config(selection if isinstance(selection, dict) else {})\n    return selection"),
    ("cognition calls a held model",
     "greg/cognition/cortex.py",
     "    model_config = gate_model_config(model_config)\n"
     "    hold = model_config.get(\"model_license_hold\") if isinstance(model_config, dict) else None\n"
     "    if isinstance(hold, dict):\n"
     "        raise CognitionError(\"license: \" + str(hold.get(\"reason\") or \"model license does not permit this use\")[:300])\n",
     "    model_config = model_config\n"),
    ("a hold is not recorded",
     "greg/body.py",
     "        if isinstance(hold, dict):\n            payload = {\"model\": hold.get(\"model\"), \"verdict\": hold.get(\"verdict\"),",
     "        if False and isinstance(hold, dict):\n            payload = {\"model\": hold.get(\"model\"), \"verdict\": hold.get(\"verdict\"),"),
    ("the signed selection stores admit's extra fields",
     "greg/body.py",
     '{"selection": selection, "command_digest": digest}',
     '{"selection": admitted, "command_digest": digest}'),
]


def main() -> int:
    bad = 0
    for name, rel, old, new in MUTANTS:
        path = ROOT / rel
        source = path.read_text(encoding="utf-8")
        if source.count(old) != 1:
            print(f"STALE     {name}: pattern not found exactly once in {rel}")
            bad += 1
            continue
        path.write_text(source.replace(old, new), encoding="utf-8")
        try:
            run = subprocess.run(
                [sys.executable, "-m", "pytest", "-q", "-x", "-p", "no:cacheprovider", *TESTS],
                cwd=ROOT, capture_output=True, text=True)
        finally:
            path.write_text(source, encoding="utf-8")
        caught = run.returncode != 0
        tail = (run.stdout.strip().splitlines() or ["(no output)"])[-1]
        if not caught:
            bad += 1
        print(f"{'CAUGHT ' if caught else 'SURVIVED'} {name}: {tail}")
    print(f"{len(MUTANTS)} mutants, {bad} survived or stale")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
