"""Each safeguard of the directive completion contract must fail its unit tests when removed.

    python scripts/ci/check_directive_sections_mutants.py

Mutants are applied to acceptance/directive.py in a scratch copy of the repository, never to the working tree; the
copy runs without bytecode and its __pycache__ is purged before each mutant. A mutant is caught only when
tests/unit/test_directive_sections.py reports a FAILED test (an import or collection error does not count).
Exit status 1 if any mutant survives or no longer applies.
"""
from pathlib import Path
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
TARGET = "acceptance/directive.py"
TESTS = "tests/unit/test_directive_sections.py"
MUTANTS = [
    ("a missing section passes", 'if numbers.count(n) == 0:', 'if False:'),
    ("a duplicated section passes", 'elif numbers.count(n) > 1:', 'elif False:'),
    ("a section the directive lacks passes",
     'for n in sorted(set(numbers) - set(range(1, SECTIONS + 1))):', 'for n in []:'),
    ("a changed source digest passes",
     'if hashlib.sha256(body.encode("utf-8")).hexdigest() != doc["source"]["sha256"]:', 'if False:'),
    ("a heading that is not the source's passes",
     'if n in texts and section["heading"] != texts[n][0]:', 'if False:'),
    ("an excerpt that is not verbatim passes",
     'if n in texts and _norm(ask["excerpt"]) not in _norm(texts[n][1]):', 'if False:'),
    ("an unresolved cited node passes", 'problem = _node_problem(ref, root)', 'problem = None'),
    ("a node that collects nothing passes",
     'return [f"{node}: collects nothing" for node in nodes if not any(covers(node, c) for c in collected)]',
     'return []'),
    ("an unknown mission requirement passes",
     'if kind == "mission" and tuple(name.split(".", 1)) not in reqs:', 'if False:'),
    ("an unknown contract function passes", 'elif kind == "contract" and name not in functions:', 'elif False:'),
    ("own unit nodes may claim BODY_VERIFIED",
     'if ask.get("tests_tier") == "BODY_VERIFIED" and not out and not real_process_nodes(nodes, registry, root, cache):',
     'if False:'),
    ("a claimed tier is never compared", 'if ask["tier"] != got["tier"]:', 'if False:'),
    ("a tier above the evidence reads as merely stale", 'if _level(ask["tier"]) > _level(got["tier"]):', 'if False:'),
    ("coverage is not capped by what an ask cites",
     'coverage = min([ask["coverage"]] + caps, key=_COVERAGE_RANK.__getitem__)', 'coverage = ask["coverage"]'),
    ("a met ask need not be covered",
     'met = tier != BLOCKED and coverage == "covered" and rank(tier) >= rank(ask["required_tier"])',
     'met = tier != BLOCKED and rank(tier) >= rank(ask["required_tier"])'),
    ("a met ask need not reach its required tier",
     'met = tier != BLOCKED and coverage == "covered" and rank(tier) >= rank(ask["required_tier"])',
     'met = tier != BLOCKED and coverage == "covered"'),
    ("a failed run node still counts", 'tiers.append(SHORT_FLOOR if observed else ask.get("tests_tier", "UNIT_VERIFIED"))',
     'tiers.append(ask.get("tests_tier", "UNIT_VERIFIED"))'),
    ("one met ask makes a section DONE",
     'return "DONE" if asks and met == len(asks) else "OPEN" if met == 0 else "PARTIAL"',
     'return "DONE" if met else "OPEN"'),
    ("DONE with an open ask is not named",
     'if section["status"] == "DONE" and computed != "DONE":', 'if False:'),
    ("a recorded status may differ from the computed one", 'elif section["status"] != computed:', 'elif False:'),
    ("a met ask may name a blocker",
     'if blocker:\n            out.append(f"{where}: a met ask names a blocker', 'if False:\n            out.append(f"'),
    ("a founder or external tier may be blamed on building",
     'if ask["required_tier"] in BEYOND_TESTS and cls not in ("FOUNDER_ONLY", "EXTERNAL"):', 'if False:'),
    ("a unit on a non-buildable blocker passes", 'if "unit" in blocker and cls != "BUILDABLE_NOT_BUILT":', 'if False:'),
    ("an unknown unit passes", 'if blocker.get("unit") and blocker["unit"] not in units:', 'if False:'),
    ("a principle need not name its guards",
     'if guard != UNGUARDED and not (isinstance(guard, list) and guard):', 'if False:'),
    ("a unit dependency cycle passes", 'if _cyclic(units):', 'if False:'),
    ("an unknown unit dependency passes", 'if d not in units:', 'if False:'),
    ("the build verdict ignores buildable asks",
     'return blocker.get("class") == "BUILDABLE_NOT_BUILT" or (', 'return False and ('),
    ("the build verdict ignores missing sections",
     '"prompt_completely_built": not residual and len(sections) == SECTIONS,', '"prompt_completely_built": not residual,'),
]


def purge(tree: Path) -> None:
    for cache in tree.rglob("__pycache__"):
        shutil.rmtree(cache, ignore_errors=True)


def main() -> int:
    invalid = 0
    with tempfile.TemporaryDirectory(prefix="directive-sections-mutants-") as temp:
        repo = Path(temp) / "repo"
        shutil.copytree(ROOT, repo, ignore=shutil.ignore_patterns(".git", "__pycache__", ".pytest_cache"))
        path = repo / TARGET
        original = path.read_text()
        env = {**os.environ, "PYTHONPATH": str(repo), "PYTHONDONTWRITEBYTECODE": "1"}
        for name, old, new in MUTANTS:
            if original.count(old) != 1:
                print("STALE", name)
                invalid += 1
                continue
            path.write_text(original.replace(old, new))
            purge(repo)
            run = subprocess.run([sys.executable, "-B", "-m", "pytest", "-q", "-x", "-p", "no:cacheprovider", TESTS],
                                 cwd=repo, env=env, capture_output=True, text=True, timeout=600)
            caught = (run.returncode == 1 and f"FAILED {TESTS}::" in run.stdout and "ERROR collecting" not in run.stdout)
            print("CAUGHT" if caught else "SURVIVED_OR_INVALID", name)
            invalid += not caught
            path.write_text(original)
    return int(bool(invalid))


if __name__ == "__main__":
    raise SystemExit(main())
