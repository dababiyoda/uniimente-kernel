"""Each safeguard of the directive completion contract must fail its unit tests when removed.

    python scripts/ci/check_directive_sections_mutants.py

Mutants are applied to acceptance/directive.py and acceptance/__main__.py in a scratch copy of the repository, never to
the working tree; the copy runs without bytecode and its __pycache__ is purged before each mutant. A mutant is caught
only when tests/unit/test_directive_sections.py reports a FAILED test (an import or collection error does not count).
Exit status 1 if any mutant survives or no longer applies.
"""
from pathlib import Path
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
DIRECTIVE = "acceptance/directive.py"
CLI = "acceptance/__main__.py"
TESTS = "tests/unit/test_directive_sections.py"
MUTANTS = [
    # the sections and the source
    (DIRECTIVE, "a missing section passes", 'if numbers.count(n) == 0:', 'if False:'),
    (DIRECTIVE, "a duplicated section passes", 'elif numbers.count(n) > 1:', 'elif False:'),
    (DIRECTIVE, "a section the directive lacks passes",
     'for n in sorted(set(numbers) - set(range(1, SECTIONS + 1))):', 'for n in []:'),
    (DIRECTIVE, "sections out of order pass", 'if numbers != sorted(numbers):', 'if False:'),
    (DIRECTIVE, "a changed source digest passes",
     'if hashlib.sha256(body.encode("utf-8")).hexdigest() != doc["source"]["sha256"]:', 'if False:'),
    (DIRECTIVE, "a source without 77 sections passes", 'if sorted(texts) != list(range(1, SECTIONS + 1)):', 'if False:'),
    (DIRECTIVE, "another source file may be read", 'if doc["source"]["directive"] != SOURCE:', 'if False:'),
    (DIRECTIVE, "a source without a fence raises",
     'return [f"source: {doc[\'source\'][\'directive\']} holds no four-backtick text fence"]', 'raise'),
    (DIRECTIVE, "a source without sections raises",
     'return {n: (heading, text) for n, heading, text in found[0]} if found else {}',
     'return {n: (heading, text) for n, heading, text in found[0]}'),
    (DIRECTIVE, "a heading that is not the source's passes",
     'if n in texts and section["heading"] != texts[n][0]:', 'if False:'),
    (DIRECTIVE, "an excerpt that is not verbatim passes",
     'if n in texts and _norm(ask["excerpt"]) not in _norm(texts[n][1]):', 'if False:'),
    (DIRECTIVE, "an ask id may name another section", 'if not ask["id"].startswith(f"S{n}."):', 'if False:'),
    (DIRECTIVE, "a missing owner path passes", 'if not (root / path).exists():', 'if False:'),
    # evidence
    (DIRECTIVE, "an unresolved cited node passes", 'problem = _node_problem(ref, root)', 'problem = None'),
    (DIRECTIVE, "a helper in a test file counts as a test",
     '_NODES[key] = f"{node}: {parts[-1]} is not a test pytest collects"', 'pass'),
    (DIRECTIVE, "a node that collects nothing passes",
     'return [f"{node}: collects nothing" for node in nodes if not any(covers(node, c) for c in collected)]',
     'return []'),
    (DIRECTIVE, "collection skips nodes inside a wholesale-cited file", 'return sorted(set(nodes))',
     'return sorted(n for n in set(nodes) if not any(o != n and covers(o, n) for o in nodes))'),
    (DIRECTIVE, "guard nodes are not collected", 'nodes += ask_nodes(ask) + _guards(ask)', 'nodes += ask_nodes(ask)'),
    (DIRECTIVE, "an unknown mission requirement passes",
     'if kind == "mission" and tuple(name.split(".", 1)) not in reqs:', 'if False:'),
    (DIRECTIVE, "an unknown contract function passes", 'elif kind == "contract" and name not in functions:',
     'elif False:'),
    (DIRECTIVE, "tests_tier without nodes passes", 'if "tests_tier" in ask and not nodes:', 'if False:'),
    (DIRECTIVE, "own unit nodes may claim BODY_VERIFIED",
     'if ask.get("tests_tier") == "BODY_VERIFIED" and not out and not real_process_nodes(nodes, registry, root, cache):',
     'if False:'),
    (DIRECTIVE, "an unresolved guard node passes", 'problem = _node_problem(node, root)', 'problem = None'),
    (DIRECTIVE, "a guard need not be the ask's evidence",
     'elif not any(e == node or covers(e, node) for e in nodes):', 'elif False:'),
    # tiers, coverage, met
    (DIRECTIVE, "a claimed tier is never compared", 'if ask["tier"] != got["tier"]:', 'if False:'),
    (DIRECTIVE, "a tier above the evidence reads as merely stale", 'if _level(ask["tier"]) > _level(got["tier"]):',
     'if False:'),
    (DIRECTIVE, "coverage is not capped by what an ask cites",
     'coverage = min([ask["coverage"]] + caps, key=_COVERAGE_RANK.__getitem__)', 'coverage = ask["coverage"]'),
    (DIRECTIVE, "a contract function's coverage is ignored", 'caps.append(f["coverage"])', 'pass'),
    (DIRECTIVE, "Mission L's trace does not cap the tier", 'tiers += [r["status"]] + [x["status"] for x in links]',
     'tiers += [r["status"]]'),
    (DIRECTIVE, "Mission L's trace does not cap the coverage", 'if not all(x["attained"] for x in links):',
     'if False:'),
    (DIRECTIVE, "a met ask need not be covered",
     'met = tier != BLOCKED and coverage == "covered" and rank(tier) >= rank(ask["required_tier"])',
     'met = tier != BLOCKED and rank(tier) >= rank(ask["required_tier"])'),
    (DIRECTIVE, "a met ask need not reach its required tier",
     'met = tier != BLOCKED and coverage == "covered" and rank(tier) >= rank(ask["required_tier"])',
     'met = tier != BLOCKED and coverage == "covered"'),
    (DIRECTIVE, "a failed run node still counts",
     'tiers.append(SHORT_FLOOR if observed else ask.get("tests_tier", "UNIT_VERIFIED"))',
     'tiers.append(ask.get("tests_tier", "UNIT_VERIFIED"))'),
    (DIRECTIVE, "a guard's run is never read",
     '"guard_observed": shortfalls(guards, outcomes) if outcomes is not None and guards else []',
     '"guard_observed": []'),
    (DIRECTIVE, "a guard that fell short still guards", 'or bool(row.get("guard_observed"))', ''),
    # sections and listed lines
    (DIRECTIVE, "one met ask makes a section DONE",
     'return "DONE" if asks and met == len(asks) and not unaccounted else "OPEN" if met == 0 else "PARTIAL"',
     'return "DONE" if met else "OPEN"'),
    (DIRECTIVE, "every listed line counts as answered",
     'done = [line for line in lines if line in named or any(_core(line) in e for e in excerpts)]', 'done = lines'),
    (DIRECTIVE, "a DONE claim ignores unanswered lines",
     'unaccounted = accounted_lines(section, texts[n][1])[1] if n in texts else []', 'unaccounted = []'),
    (DIRECTIVE, "an ask may name a line its section lacks", 'if n in texts and _norm(line) not in listed:',
     'if False:'),
    (DIRECTIVE, "not_asks may name a line its section lacks", 'if n in texts and line not in listed:', 'if False:'),
    (DIRECTIVE, "a line may be both answered and set aside",
     'elif line in named or any(_core(line) in e for e in excerpts):', 'elif False:'),
    (DIRECTIVE, "DONE with an open ask is not named", 'if section["status"] == "DONE" and computed != "DONE":',
     'if False:'),
    (DIRECTIVE, "a recorded status may differ from the computed one", 'elif section["status"] != computed:',
     'elif False:'),
    # blockers and records
    (DIRECTIVE, "a met ask may name a blocker",
     'if blocker:\n            out.append(f"{where}: a met ask names a blocker',
     'if False:\n            out.append(f"'),
    (DIRECTIVE, "a founder or external tier may be blamed on building",
     'if ask["required_tier"] in BEYOND_TESTS and cls not in ("FOUNDER_ONLY", "EXTERNAL"):', 'if False:'),
    (DIRECTIVE, "a founder or external blocker a test could reach needs no record",
     'elif ask["required_tier"] in TEST_TIERS:', 'elif False:'),
    (DIRECTIVE, "a blocker's record is never checked", 'problem = _record_problem(blocker["record"], cls, gaps, root)',
     'problem = None'),
    (DIRECTIVE, "any blocker may cite a record", 'elif "record" in blocker:', 'elif False:'),
    (DIRECTIVE, "an unknown gap holds a blocker", 'if gap is None:', 'if False:'),
    (DIRECTIVE, "a closed or buildable gap holds a blocker",
     'if gap["state"] != "OPEN" or gap["buildable_now"]:', 'if False:'),
    (DIRECTIVE, "a gap of another dependency holds a blocker",
     'if gap["dependency"] not in RECORD_DEPENDENCIES[cls]:', 'if False:'),
    (DIRECTIVE, "a record may name no file", 'if not file.is_file():', 'if False:'),
    (DIRECTIVE, "a record's words need not be in its file",
     'if _norm(words) not in _norm(file.read_text(encoding="utf-8", errors="replace")):', 'if False:'),
    (DIRECTIVE, "the map may hold its own record",
     'if path in (DIRECTIVE_MAP.relative_to(ROOT).as_posix(), PIN.relative_to(ROOT).as_posix()):', 'if False:'),
    (DIRECTIVE, "a unit on a non-buildable blocker passes", 'if "unit" in blocker and cls != "BUILDABLE_NOT_BUILT":',
     'if False:'),
    (DIRECTIVE, "an unknown unit passes", 'if blocker.get("unit") and blocker["unit"] not in units:', 'if False:'),
    (DIRECTIVE, "a principle need not name its guards",
     'if guard != UNGUARDED and not (isinstance(guard, list) and guard):', 'if False:'),
    # units
    (DIRECTIVE, "a unit id may be listed twice", 'if len(units) != len(doc.get("units", [])):', 'if False:'),
    (DIRECTIVE, "a unit dependency cycle passes", 'if _cyclic(units):', 'if False:'),
    (DIRECTIVE, "an unknown unit dependency passes", 'if d not in units:', 'if False:'),
    (DIRECTIVE, "a unit no open ask needs passes",
     'for u in sorted(set(units) - _prerequisites(named_units, units)):', 'for u in []:'),
    (DIRECTIVE, "a closed unit may still be named", 'if unit.get("closed_by") and u in named_units:', 'if False:'),
    (DIRECTIVE, "prerequisites without asks are dropped from the order",
     'needed = _prerequisites({u for u in by_unit if u}, units)', 'needed = set(by_unit)'),
    # the pin and retirement
    (DIRECTIVE, "a missing pin file passes",
     'return out + [f"pin: no {PIN.relative_to(ROOT)}: the set of asks is not pinned"]', 'return out'),
    (DIRECTIVE, "a malformed pin passes", 'out = _schema_problems(pin, "directive-asks.pin.schema.json")', 'out = []'),
    (DIRECTIVE, "a pinned ask may be deleted", 'for aid in pin["asks"]:\n        if aid not in ids:',
     'for aid in pin["asks"]:\n        if False:'),
    (DIRECTIVE, "an ask may go unpinned", 'if aid not in pin["asks"]:', 'if False:'),
    (DIRECTIVE, "an open ask may leave the build residual",
     'if pinned and cls not in (pinned, "BUILDABLE_NOT_BUILT"):', 'if False:'),
    (DIRECTIVE, "the ratchet forgets a base id", 'if aid not in head["asks"]:', 'if False:'),
    (DIRECTIVE, "the ratchet lets a pinned class move", 'elif head["asks"][aid] not in (cls, "BUILDABLE_NOT_BUILT"):',
     'elif False:'),
    (DIRECTIVE, "an unreadable git ref reads as no pin",
     'capture_output=True).returncode:\n        return None, f"pin: cannot read git ref {ref}"',
     'capture_output=True).returncode and False:\n        return None, f"pin: cannot read git ref {ref}"'),
    (DIRECTIVE, "a superseded ask is not carried by its successor",
     'if gone and gone.get("superseded_by") in live:', 'if False:'),
    (DIRECTIVE, "a withdrawn ask still counts", 'elif gone:', 'elif False:'),
    (DIRECTIVE, "a retirement may name both or neither route",
     'if ("superseded_by" in gone) == ("record" in gone):', 'if False:'),
    (DIRECTIVE, "a successor need not be live", 'if successor is None:\n            return [', 'if False:\n            return ['),
    (DIRECTIVE, "a successor may ask less", 'if rank(successor["required_tier"]) < rank(ask["required_tier"]):',
     'if False:'),
    (DIRECTIVE, "a withdrawal's record is never checked",
     'problem = _record_problem(gone["record"], None, gaps, root, intent_only=True)', 'problem = None'),
    # the verdicts
    (DIRECTIVE, "the build verdict ignores buildable asks",
     'return blocker.get("class") == "BUILDABLE_NOT_BUILT" or (', 'return False and ('),
    (DIRECTIVE, "a reopened ask with no blocker is not building's to close",
     'blocker.get("class") == "PRINCIPLE" and _unguarded(row)) or not blocker',
     'blocker.get("class") == "PRINCIPLE" and _unguarded(row))'),
    (DIRECTIVE, "the build verdict ignores unanswered lines",
     '"prompt_completely_built": not residual and not unread and whole,', '"prompt_completely_built": not residual and whole,'),
    (DIRECTIVE, "the build verdict ignores missing sections",
     '"prompt_completely_built": not residual and not unread and whole,', '"prompt_completely_built": not residual and not unread,'),
    (DIRECTIVE, "every section done ignores missing sections", '"every_section_done": whole and all(',
     '"every_section_done": all('),
    # the command line
    (CLI, "the CLI never collects", 'if args.cmd == "directive" and args.collect and not found:', 'if False:'),
    (CLI, "the CLI never ratchets", 'if args.cmd == "directive" and args.against and not found:', 'if False:'),
    (CLI, "the CLI ignores an unsound map",
     '        if found:\n            print("directive map is unsound:"', '        if False:\n            print("directive map is unsound:"'),
]


def purge(tree: Path) -> None:
    for cache in tree.rglob("__pycache__"):
        shutil.rmtree(cache, ignore_errors=True)


def main() -> int:
    invalid = 0
    with tempfile.TemporaryDirectory(prefix="directive-sections-mutants-") as temp:
        repo = Path(temp) / "repo"
        shutil.copytree(ROOT, repo, ignore=shutil.ignore_patterns(".git", "__pycache__", ".pytest_cache"))
        env = {**os.environ, "PYTHONPATH": str(repo), "PYTHONDONTWRITEBYTECODE": "1"}
        for target, name, old, new in MUTANTS:
            path = repo / target
            original = path.read_text()
            if original.count(old) != 1:
                print("STALE", name)
                invalid += 1
                continue
            path.write_text(original.replace(old, new))
            purge(repo)
            try:
                run = subprocess.run([sys.executable, "-B", "-m", "pytest", "-q", "-x", "-p", "no:cacheprovider", TESTS],
                                     cwd=repo, env=env, capture_output=True, text=True, timeout=900)
            finally:
                path.write_text(original)
            caught = (run.returncode == 1 and f"FAILED {TESTS}::" in run.stdout and "ERROR collecting" not in run.stdout)
            print("CAUGHT" if caught else "SURVIVED_OR_INVALID", name, flush=True)
            invalid += not caught
    print(f"{len(MUTANTS) - invalid}/{len(MUTANTS)} caught")
    return int(bool(invalid))


if __name__ == "__main__":
    raise SystemExit(main())
