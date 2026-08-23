"""`python -m shell [pipeline]` — the institutional operator surface.

Exit code is the worst outcome across stages: 0 clean, 1 something unresolved,
2 a reporter failed. That makes the shell usable from CI without parsing prose,
and it means an unresolved institutional question is visible as a signal rather
than only as text a human might skim past.

This command reports. It grants nothing and activates nothing.
"""
from __future__ import annotations

import sys

from shell.pipeline import Outcome, PipelineReport, report
from shell.pipelines import DEFAULT_PIPELINE, PIPELINES

RULE = "=" * 78
THIN = "-" * 78

_MARK = {Outcome.OK: "ok  ", Outcome.UNRESOLVED: "open", Outcome.FAILED: "FAIL"}


def render(result_report: PipelineReport) -> str:
    lines = [
        RULE,
        f"UNIIMENTE INSTITUTIONAL SHELL — pipeline '{result_report.pipeline}'",
        result_report.purpose,
        RULE,
    ]
    for result in result_report.results:
        lines.append("")
        lines.append(f"[{_MARK[result.outcome]}] {result.name} — {result.headline}")
        for line in result.detail:
            lines.append(f"       {line}" if line else "")
    counts = result_report.counts()
    lines += [
        "",
        THIN,
        "  ".join(f"{k} {v}" for k, v in counts.items() if v),
        THIN,
        "This report describes institutional state. It grants nothing and "
        "activates nothing.",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv

    if argv and argv[0] in ("-h", "--help"):
        print(f"usage: python -m shell [{'|'.join(PIPELINES)}]")
        for pipeline in PIPELINES.values():
            print(f"  {pipeline.name:<10} {pipeline.purpose}")
        return 0

    if argv and argv[0] == "--list":
        for pipeline in PIPELINES.values():
            stages = ", ".join(s.name for s in pipeline.stages)
            print(f"{pipeline.name:<10} {pipeline.purpose}\n           stages: {stages}")
        return 0

    name = argv[0] if argv else DEFAULT_PIPELINE
    pipeline = PIPELINES.get(name)
    if pipeline is None:
        print(f"unknown pipeline {name!r}; known: {', '.join(PIPELINES)}",
              file=sys.stderr)
        return 2

    result_report = report(pipeline)
    print(render(result_report))
    return result_report.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
