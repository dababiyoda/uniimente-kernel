"""The Foundry's 55-system completion contract, enforced.

``foundry/completion.yaml`` holds one obligation per numbered system. This
module makes the states binding:

* every id 1..55 must be present (nothing is removed by omission);
* OUTSTANDING and PARTIAL rows must carry acceptance criteria and a gap;
* PARTIAL kernel paths must exist;
* COMPLETE requires existing implementation and test paths, a system registered
  in ``foundry.systems`` with at least one GREG-reachable op, stated limitations
  and recovery behavior, and an evidence record whose result hash is re-derived
  now by RE-RUNNING the system's exercise. A claim that does not reproduce fails.

    python -m foundry.completion --status          # N/55 and every open obligation
    python -m foundry.completion --audit           # exit 1 on any unsupported claim
    python -m foundry.completion --run 36          # run one system's exercise
    python -m foundry.completion --run 35 media    # run a registered co-implementation's exercise
    python -m foundry.completion --record 36       # (re)write its evidence record
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "foundry" / "completion.yaml"
STATES = ("COMPLETE", "PARTIAL", "OUTSTANDING")


# Status distinctions of the 2026-10-13 full-machine completion contract; a row's
# COMPLETE is bounded local contract evidence and names its tier when merged rows
# could otherwise be read as more than that.
EVIDENCE_TIERS = ("INTENDED", "DESIGNED", "IMPLEMENTED", "INTEGRATED", "UNIT_VERIFIED", "SANDBOX_VERIFIED",
                  "BODY_VERIFIED", "FOUNDER_ACCEPTED", "AUTHORIZED_LIVE", "EXTERNALLY_VERIFIED",
                  "COMMERCIAL_OUTCOME_VERIFIED", "BLOCKED_WITH_REASON")


def _co_implementation_problems(sid: int, row: dict, label: str, rerun: bool = True) -> list[str]:
    """Every registered co-implementation is declared in its row and vice versa.

    A co-implementation keeps its own state and gap; it cannot claim COMPLETE,
    because the row's evidence record is re-derived from the primary only. A
    co-implementation that names its own evidence record must reproduce it.
    """
    from foundry.systems import CO_IMPLEMENTATIONS
    problems: list[str] = []
    declared = [c.get("module") for c in row.get("co_implementations", []) or []]
    registered = list(CO_IMPLEMENTATIONS.get(sid, ()))
    if sorted(declared) != sorted(registered):
        problems.append(f"{label}: co_implementations {declared} differ from the registry {registered}")
    for record in row.get("co_implementations", []) or []:
        name = f"{label} co-implementation {record.get('module')!r}"
        if not record.get("lineage"):
            problems.append(f"{name}: lineage is required")
        state = record.get("state")
        if state not in ("PARTIAL", "OUTSTANDING"):
            problems.append(f"{name}: state {state!r} must be PARTIAL or OUTSTANDING (evidence is the primary's)")
        elif not record.get("gap"):
            problems.append(f"{name}: an open obligation must name its gap")
        for path in list(record.get("implementation", [])) + list(record.get("existing", [])) + list(record.get("tests", [])):
            if ":" not in path and not (ROOT / path).exists():
                problems.append(f"{name}: path {path!r} not found")
        if record.get("evidence"):
            evidence_path = ROOT / str(record["evidence"])
            if not evidence_path.is_file():
                problems.append(f"{name}: evidence record {record['evidence']!r} not found")
            elif rerun and record.get("module") in registered and not _reproduces(evidence_path, run(sid, record["module"])):
                problems.append(f"{name}: evidence does not reproduce (re-run differs from the record)")
    return problems


def contract(path: Path = CONTRACT) -> dict[int, dict]:
    return {int(k): v for k, v in (yaml.safe_load(path.read_text()) or {}).items()}


def _hash(result) -> str:
    return "sha256:" + hashlib.sha256(json.dumps(result, sort_keys=True, default=str).encode()).hexdigest()


def run(system_id: int, implementation: str | None = None) -> dict:
    """Run the primary's exercise, or a registered co-implementation's when named."""
    import importlib
    from foundry.systems import implementations, module
    if implementation is None:
        system = module(system_id)
    elif implementation in implementations(system_id):
        system = importlib.import_module(f"foundry.systems.{implementation}")
    else:
        raise KeyError(f"{implementation!r} is not registered for Foundry system {system_id}")
    with tempfile.TemporaryDirectory(prefix=f"foundry-{system_id:02d}-") as scratch:
        result = system.exercise(Path(scratch))
    return {"system": system_id, "result": result, "result_sha256": _hash(result)}


def _reproduces(record_path: Path, fresh: dict) -> bool:
    claimed = json.loads(record_path.read_text())
    as_recorded = json.loads(json.dumps(fresh["result"], sort_keys=True, default=str))  # tuples -> lists
    return fresh["result_sha256"] == claimed.get("result_sha256") and as_recorded == claimed.get("result")


def record(system_id: int) -> Path:
    from foundry.arsenal import technology
    outcome = run(system_id)
    path = ROOT / "foundry" / "evidence" / f"system-{system_id:02d}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"system": system_id, "name": technology(system_id).name,
                                "command": f"python -m foundry.completion --run {system_id}",
                                "result": outcome["result"], "result_sha256": outcome["result_sha256"],
                                "note": "re-derived by `python -m foundry.completion --audit` on every CI run"},
                               indent=1, sort_keys=True, default=str) + "\n")
    return path


def audit(rows: dict[int, dict] | None = None, *, rerun: bool = True) -> list[str]:
    rows = contract() if rows is None else rows
    problems: list[str] = []
    missing = sorted(set(range(1, 56)) - set(rows))
    extra = sorted(set(rows) - set(range(1, 56)))
    if missing or extra:
        problems.append(f"contract must hold exactly systems 1..55 (missing {missing}, extra {extra})")
    for sid in sorted(set(rows) & set(range(1, 56))):
        row, label = rows[sid], f"system {sid}"
        state = row.get("state")
        if state not in STATES:
            problems.append(f"{label}: unknown state {state!r}")
            continue
        if not row.get("acceptance"):
            problems.append(f"{label}: acceptance criteria are required at every state")
        if state in ("PARTIAL", "OUTSTANDING") and not row.get("gap"):
            problems.append(f"{label}: an open obligation must name its gap")
        if state == "PARTIAL":
            for path in row.get("existing", []):
                if ":" not in path and not (ROOT / path).exists():
                    problems.append(f"{label}: existing path {path!r} not found")
        tier = row.get("evidence_tier")
        if tier is not None and tier not in EVIDENCE_TIERS:
            problems.append(f"{label}: evidence_tier {tier!r} is not in the directive vocabulary")
        problems.extend(_co_implementation_problems(sid, row, label, rerun))
        if state != "COMPLETE":
            continue
        for key in ("implementation", "tests", "interface", "evidence", "limitations", "recovery"):
            if not row.get(key):
                problems.append(f"{label}: COMPLETE requires {key}")
        for path in list(row.get("implementation", [])) + list(row.get("tests", [])):
            if not (ROOT / path).exists():
                problems.append(f"{label}: path {path!r} not found")
        try:
            from foundry.systems import module
            system = module(sid)
            if not (getattr(system, "QUERY_OPS", None) or getattr(system, "APPLY_OPS", None)):
                problems.append(f"{label}: no GREG-reachable op (foundry.query/foundry.apply)")
        except KeyError:
            problems.append(f"{label}: COMPLETE but not registered in foundry.systems")
            continue
        evidence_path = ROOT / str(row.get("evidence", ""))
        if not evidence_path.is_file():
            problems.append(f"{label}: evidence record {row.get('evidence')!r} not found")
            continue
        if rerun and not _reproduces(evidence_path, run(sid)):
            problems.append(f"{label}: evidence does not reproduce (re-run differs from the record)")
    return problems


def status(rows: dict[int, dict] | None = None) -> dict:
    from foundry.arsenal import technology
    rows = contract() if rows is None else rows
    by_state = {s: sorted(i for i, r in rows.items() if r.get("state") == s) for s in STATES}
    return {"complete": f"{len(by_state['COMPLETE'])}/55", "by_state": by_state,
            "open_obligations": [{"system": i, "name": technology(i).name, "state": rows[i]["state"],
                                  "gap": rows[i].get("gap", ""), "acceptance": rows[i]["acceptance"]}
                                 for i in sorted(rows) if rows[i].get("state") != "COMPLETE"]}


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] == "--status":
        s = status()
        print(json.dumps({"complete": s["complete"], "by_state": s["by_state"]}, indent=1))
        return 0
    if argv[0] == "--audit":
        problems = audit()
        for problem in problems:
            print("FAIL", problem)
        print(f"{'FAIL' if problems else 'PASS'}: {status()['complete']} complete; {len(problems)} problem(s)")
        return 1 if problems else 0
    if argv[0] in ("--run", "--record") and len(argv) == 2:
        sid = int(argv[1])
        print(json.dumps(run(sid), indent=1, default=str) if argv[0] == "--run" else str(record(sid)))
        return 0
    if argv[0] == "--run" and len(argv) == 3:              # a registered co-implementation's exercise
        print(json.dumps(run(int(argv[1]), argv[2]), indent=1, default=str))
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
