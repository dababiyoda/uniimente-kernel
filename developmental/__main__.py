"""Emit the canonical TARGET_FORM_001 report as JSON."""
from __future__ import annotations

import json
from dataclasses import asdict
from enum import Enum

from .cdpe import DevelopmentalProgramExecutor
from .contracts import DevelopmentalVerdict


def _default(value):
    if isinstance(value, Enum):
        return value.value
    raise TypeError(f"cannot serialize {type(value).__name__}")


def main() -> int:
    report = DevelopmentalProgramExecutor().run()
    print(json.dumps(asdict(report), indent=2, sort_keys=True, default=_default))
    return (
        0
        if report.verdict
        is DevelopmentalVerdict.MECHANICS_VALIDATED_NOT_PRODUCTION_AUTHORIZED
        else 1
    )


if __name__ == "__main__":
    raise SystemExit(main())
