"""`python -m blueprint` — the institution's own state, computed from evidence.

Prints the awarded rung for all 55 Foundry technologies, the reality of each,
the unblocked build frontier ranked by leverage, what is blocked and by what,
and every named hardening gap with its owner.

Nothing here authorizes, schedules or activates anything.
"""
from __future__ import annotations

import argparse
import json
import sys

from blueprint.critical_path import compute
from blueprint.ladder import RUNG_ORDER, Reality
from blueprint.registry import Owner

RUNG_GLYPH = {
    "BLUEPRINT": "·",
    "SKETCHED": "○",
    "BUILT": "◔",
    "EXERCISED": "◑",
    "PROVEN": "◕",
    "HARDENED": "●",
}


def _rung_label(status) -> str:
    return status.awarded_rung.value if status.awarded_rung else "UNSUPPORTED"


def _print_ladder(report) -> None:
    print("=" * 78)
    print("OPUS MAXIMUS — 55-TECHNOLOGY HARDENING LADDER")
    print("=" * 78)
    print(f"{'':2} {'#':>3}  {'TECHNOLOGY':<42} {'RUNG':<10} {'REALITY':<15}")
    print("-" * 78)
    for tech_id in sorted(report.statuses):
        s = report.statuses[tech_id]
        label = _rung_label(s)
        glyph = RUNG_GLYPH.get(label, "?")
        flag = "!" if s.problems else " "
        name = s.name if len(s.name) <= 42 else s.name[:39] + "..."
        print(f"{glyph}{flag} {tech_id:>3}  {name:<42} {label:<10} {s.reality.value:<15}")


def _print_distribution(report) -> None:
    by_rung = report.by_rung()
    by_reality = report.by_reality()
    print()
    print("-" * 78)
    print("DISTRIBUTION")
    print("-" * 78)
    total = len(report.statuses)
    for rung in RUNG_ORDER:
        ids = by_rung.get(rung.value, ())
        bar = "█" * len(ids)
        print(f"  {rung.value:<11} {len(ids):>3}/{total}  {bar}")
    unsupported = by_rung.get("UNSUPPORTED", ())
    if unsupported:
        print(f"  {'UNSUPPORTED':<11} {len(unsupported):>3}/{total}  "
              f"{'█' * len(unsupported)}   <- claimed a rung the evidence refused")
    print()
    for reality in Reality:
        ids = by_reality.get(reality.value, ())
        print(f"  {reality.value:<16} {len(ids):>3}/{total}")


def _print_frontier(report, limit: int) -> None:
    print()
    print("-" * 78)
    print("BUILD FRONTIER — unblocked today, highest leverage first")
    print("-" * 78)
    frontier = report.frontier
    if not frontier:
        print("  nothing can advance: every technology is held down by a dependency")
        return
    for s in frontier[:limit]:
        target = s.target_rung.value if s.target_rung else "—"
        print(f"  #{s.technology_id:<3} {s.name:<40} "
              f"{_rung_label(s)} -> {target:<10} "
              f"leverage={s.leverage:<3} owner={s.owner.value}")
    if len(frontier) > limit:
        print(f"  ... and {len(frontier) - limit} more (use --all)")


def _print_blocked(report, limit: int) -> None:
    blocked = report.blocked
    print()
    print("-" * 78)
    print(f"BLOCKED — {len(blocked)} technologies cannot advance until a dependency does")
    print("-" * 78)
    for s in blocked[:limit]:
        holders = ", ".join(
            f"#{d} {report.statuses[d].name} ({_rung_label(report.statuses[d])})"
            for d in s.blocked_by
        )
        print(f"  #{s.technology_id:<3} {s.name:<34} ceiling={s.ceiling.value}")
        print(f"        held by: {holders}")
    if len(blocked) > limit:
        print(f"  ... and {len(blocked) - limit} more (use --all)")


def _print_ownership(report) -> None:
    print()
    print("-" * 78)
    print("GAP OWNERSHIP")
    print("-" * 78)
    for owner in Owner:
        owned = report.owned_by(owner)
        ids = ", ".join(f"#{s.technology_id}" for s in owned)
        print(f"  {owner.value:<9} {len(owned):>3} technologies: {ids}")


def _print_gaps(report) -> None:
    print()
    print("-" * 78)
    print("NAMED HARDENING GAPS")
    print("-" * 78)
    for tech_id in sorted(report.statuses):
        s = report.statuses[tech_id]
        if not s.gaps:
            continue
        print(f"  #{s.technology_id} {s.name}  [{s.owner.value}]")
        for gap in s.gaps:
            print(f"      - {gap}")


def _print_honesty(report) -> None:
    print()
    print("-" * 78)
    print("HONESTY CHECK")
    print("-" * 78)
    if not report.dishonest:
        print("  every claimed rung is supported by evidence that resolves.")
        return
    print(f"  {len(report.dishonest)} bindings claim more than the evidence supports:")
    for tech_id in report.dishonest:
        s = report.statuses[tech_id]
        for problem in s.problems:
            print(f"    #{tech_id} {s.name}: {problem}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m blueprint",
                                     description=__doc__.splitlines()[0])
    parser.add_argument("--json", action="store_true",
                        help="emit the full report as JSON")
    parser.add_argument("--all", action="store_true",
                        help="do not truncate the frontier or blocked lists")
    parser.add_argument("--gaps", action="store_true",
                        help="print every named hardening gap")
    args = parser.parse_args(argv)

    report = compute()
    limit = 10_000 if args.all else 12

    if args.json:
        payload = {
            "technologies": {
                str(t): {
                    "name": s.name,
                    "category": s.category,
                    "rung": _rung_label(s),
                    "ceiling": s.ceiling.value,
                    "reality": s.reality.value,
                    "owner": s.owner.value,
                    "leverage": s.leverage,
                    "can_advance": s.can_advance,
                    "blocked_by": list(s.blocked_by),
                    "gaps": list(s.gaps),
                    "problems": list(s.problems),
                }
                for t, s in sorted(report.statuses.items())
            },
            "frontier": [s.technology_id for s in report.frontier],
            "blocked": [s.technology_id for s in report.blocked],
            "by_rung": {k: list(v) for k, v in report.by_rung().items()},
            "by_reality": {k: list(v) for k, v in report.by_reality().items()},
            "dishonest": list(report.dishonest),
            "grants_issued": 0,
        }
        json.dump(payload, sys.stdout, indent=2)
        print()
        return 0

    _print_ladder(report)
    _print_distribution(report)
    _print_frontier(report, limit)
    _print_blocked(report, limit)
    _print_ownership(report)
    if args.gaps:
        _print_gaps(report)
    _print_honesty(report)
    print()
    print("This report recommends. It grants nothing and activates nothing.")
    return 1 if report.dishonest else 0


if __name__ == "__main__":
    raise SystemExit(main())
