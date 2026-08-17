"""The institutional shell: one read-only operator surface over the kernel's
existing reporters.

Specified by `docs/INSTITUTIONAL_SHELL_SPEC.md`. Technology #14 in
`foundry/arsenal.py`.

    python -m shell            # status
    python -m shell frontier
    python -m shell evidence
    python -m shell handoff

The shell reports. It grants nothing, activates nothing, writes nothing and
listens on nothing. The arsenal declares #14's consequence class as
`internal_write`; this is a strict read-only subset of that technology and the
remainder stays recorded as an open gap rather than quietly dropped.
"""
from shell.pipeline import (
    Outcome,
    Pipeline,
    PipelineReport,
    ShellError,
    Stage,
    StageResult,
    report,
)
from shell.pipelines import DEFAULT_PIPELINE, PIPELINES

__all__ = [
    "DEFAULT_PIPELINE",
    "Outcome",
    "PIPELINES",
    "Pipeline",
    "PipelineReport",
    "ShellError",
    "Stage",
    "StageResult",
    "report",
]
