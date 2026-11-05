"""Every surface that offers an answer must keep showing the authority an ask requests, what approving covers, and
what silence does, and must offer only answers the body applies (directive part 2 §9).

Each named test must pass unmutated in the copy first (a skipped or failing test is INVALID, never a catch), and a
mutant is caught only when its named test fails. A mutant is one or more exact replacements in one file.
"""
from pathlib import Path
import os, shutil, subprocess, sys, tempfile

ROOT = Path(__file__).resolve().parents[2]
FILE = "tests/unit/test_greg_ask_terms_surfaces.py"
PAGES = FILE + "::test_console_and_mission_control_show_the_authority_requested_and_what_silence_does"
ESCAPE = FILE + "::test_the_console_escapes_the_scope_and_the_consequence"
REAL = FILE + "::test_a_real_approval_shows_the_exact_scope_approving_covers"
FORMAT = FILE + "::test_both_surfaces_print_values_alike"
PHONE = FILE + "::test_the_phone_shows_the_same_terms_and_sends_only_answers_the_body_applies"
PHONE_REAL = FILE + "::test_the_phone_shows_what_a_real_approval_covers"
COMP = FILE + "::test_a_compensation_approval_names_the_compensation_not_the_action_it_undoes"
PHONE_COMP = FILE + "::test_the_phone_names_the_compensation_too"
TYPED = FILE + "::test_a_typed_blocker_says_what_approving_covers_and_what_silence_does"
TYPED_COMP = FILE + "::test_a_compensation_approval_is_never_typed_as_the_action_it_undoes"
LEGACY = COMP + "[legacy]"
PHONE_LEGACY = PHONE_COMP + "[legacy]"
TYPED_LEGACY = TYPED_COMP + "[legacy]"
NEAR = FILE + "::test_only_a_compensation_record_reads_as_one_on_both_surfaces"
NOT_APPROVAL = FILE + "::test_a_decision_blocker_that_is_not_an_approval_never_says_what_approving_covers"

CONSOLE, CORE, APP, BLOCKERS = "greg/console.py", "greg/phone/core.js", "greg/phone/app.js", "greg/blockers.py"
TERMS = '    for (const line of askTerms(r)) card.append(el("p", line));'
SKIP = "    if (r.answerable === false) { box.append(card); continue; }"
MALFORMED_JS = ('if ("malformed" in requested) lines.push("This scope is malformed: " '
                '+ shownValue(requested.malformed));\n')
AUTHORITY_JS = ('if (rest.length) lines.push("Authority requested: " + rest.map(([k, v]) => `${k}: ${shownValue(v)}`)'
                '.join("; "));\n')
MUTANTS = [
    # console and Mission Control (one rendering part)
    ("console drops what silence does", CONSOLE,
     [('if r.get("consequence_of_no_response"):\n        parts.append("<br><b>If you do not answer:',
       'if False:\n        parts.append("<br><b>If you do not answer:')], PAGES),
    ("console shows only the reach keys again", CONSOLE,
     [('if k not in reach and k != "malformed"}', "if k in reach}")], PAGES),
    ("console repeats the reach keys", CONSOLE, [('if k not in reach and k != "malformed"}', 'if k != "malformed"}')],
     PAGES),
    ("console puts the malformed marker after the reach list (as before)", CONSOLE,
     [('    if "malformed" in requested:', '    if False:'),
      ('if k not in reach and k != "malformed"}', "if k not in reach}")], PAGES),
    ("console drops the paid clause of what approving covers", CONSOLE,
     [("if isinstance(cost, (int, float)) and not isinstance(cost, bool) and cost > 0:", "if False:")], PAGES),
    ("console drops the action an approval was asked for", CONSOLE,
     [('return COVERS + "; ".join(parts) + "." + asked_for(r)', 'return COVERS + "; ".join(parts) + "."')], REAL),
    ("console asks for action w on a compensation", CONSOLE,
     [('if is_compensation(r)\n', 'if False\n')], COMP),
    ("console names every approval a compensation", CONSOLE,
     [('if is_compensation(r)\n', 'if True\n')], REAL),
    ("console reads no compensation from an ask recorded before the marker", CONSOLE,
     [('    if "compensation" in r or r.get("kind") != "APPROVAL" or not r.get("action_id"):\n        return False\n',
       '    return False\n')], LEGACY),
    ("console's unmarked fallback ignores the original receipt", CONSOLE,
     [('and isinstance(evidence, dict) and "original_receipt" in evidence)', ')')], NEAR),
    ("console's unmarked fallback matches any action's compensation", CONSOLE,
     [('.startswith(f"compensation of {r[\'action_id\']}:")', '.startswith("compensation of ")')], NEAR),
    ("console's fallback overrides a marker that says no", CONSOLE,
     [('if "compensation" in r or r.get("kind")', 'if r.get("kind")')], NEAR),
    ("console's fallback reads any kind", CONSOLE,
     [('if "compensation" in r or r.get("kind") != "APPROVAL" or', 'if "compensation" in r or')], NEAR),
    ("console drops the params an approval covers", CONSOLE,
     [('if isinstance(p, dict) and isinstance(p.get("json"), str):', "if False:")], REAL),
    ("console drops the mission an approval covers", CONSOLE,
     [("""([f"mission {r['mission_id']}"] if r.get("mission_id") else [])""", "[]")], REAL),
    ("console shows cut params as whole", CONSOLE, [('whole = p.get("length") == len(p["json"])', "whole = True")],
     REAL),
    ("console stops escaping the consequence", CONSOLE,
     [('_e(r["consequence_of_no_response"])', 'r["consequence_of_no_response"]')], ESCAPE),
    ("console stops escaping the authority requested", CONSOLE,
     [('+ _e("; ".join(f"{k}: {_shown(v)}" for k, v in rest.items())))',
       '+ str("; ".join(f"{k}: {_shown(v)}" for k, v in rest.items())))')], ESCAPE),
    ("console stops escaping what approving covers", CONSOLE,
     [("+ _e(approval_covers(r)[len(COVERS):]))", "+ approval_covers(r)[len(COVERS):])")], ESCAPE),
    ("console prints numbers as Python does", CONSOLE, [("        return _number(v)", "        return str(v)")],
     FORMAT),
    ("console prints null as Python does", CONSOLE, [('        return "null"', '        return "None"')], FORMAT),
    ("console prints dicts as Python does", CONSOLE,
     [('return "{" + ", ".join(f"{k}: {_shown(v[k])}" for k in sorted(v, key=str)) + "}"', "return str(v)")], FORMAT),
    # the data behind them: the engine records the bound params, the projection carries them
    ("an APPROVAL records no params", "greg/missions.py",
     [('                message["bound_params"] = params_view(params)', "                pass")], REAL),
    ("the loop's APPROVAL records no params", "greg/missions.py",
     [('if float(s.get("cost_usd", 0.0)) > 0 else None, params=bound_params)',
       'if float(s.get("cost_usd", 0.0)) > 0 else None, params=None)')], REAL),
    ("the params view keeps the whole text", "greg/missions.py",
     [('"json": text[:PARAMS_SHOWN]', '"json": text')], REAL),
    ("the params view hashes another form", "greg/missions.py",
     [('"sha256": sha256_json(params)}', '"sha256": sha256_json({"params": params})}')], REAL),
    ("the projection drops the action id", "greg/asks.py",
     [('"mission_id", "action_id", "resource"', '"mission_id", "resource"')], REAL),
    ("the projection drops the bound params", "greg/asks.py",
     [('"authority_requested", "bound_params",', '"authority_requested",')], REAL),
    ("an ask records no compensation marker", "greg/missions.py",
     [('                message["compensation"] = True', "                pass")], COMP),
    ("the superseded mission's compensation ask is not marked", "greg/missions.py",
     [('compensation=True)\n            return "WAITING"\n        outcome = self.office.act(',
       'compensation=False)\n            return "WAITING"\n        outcome = self.office.act(')], COMP),
    ("the Gate-refused compensation ask is not marked", "greg/missions.py",
     [('compensation=True)\n            return "WAITING"\n        self.journal.record("mission.compensated"',
       'compensation=False)\n            return "WAITING"\n        self.journal.record("mission.compensated"')], COMP),
    ("the projection drops the compensation marker", "greg/asks.py",
     [('"compensation", "evidence",', '"evidence",')], COMP),
    # the typed blockers (greg/blockers.py): the morning report, Mission Control's Goals page, greg blockers
    ("a typed decision blocker drops what approving covers", BLOCKERS,
     [("+ _scope(request) + _covers(request),", "+ _scope(request),")], TYPED),
    ("a typed decision blocker drops what silence does", BLOCKERS,
     [('if request.get("consequence_of_no_response") else "")}', 'if False else "")}')], TYPED),
    ("a typed blocker names a compensation as the action it undoes", BLOCKERS,
     [('if kind == "APPROVAL" and is_compensation(request) else', "if False else")], TYPED_COMP),
    ("a typed blocker names every approval a compensation", BLOCKERS,
     [('if kind == "APPROVAL" and is_compensation(request) else', "if True else")], TYPED),
    ("a typed blocker reads only the marker, not an ask recorded before it", BLOCKERS,
     [('if kind == "APPROVAL" and is_compensation(request) else',
       'if kind == "APPROVAL" and request.get("compensation") is True else')], TYPED_LEGACY),
    ("a non-APPROVAL decision blocker says what approving covers", BLOCKERS,
     [('    if request.get("kind") != "APPROVAL":\n        return ""\n', "")], NOT_APPROVAL),
    ("the typed blockers list a closed mission's blocker", BLOCKERS,
     [("if m.blocker is None or m.status in TERMINAL or", "if m.blocker is None or")], TYPED_COMP),
    # the phone
    ("phone drops what silence does", CORE,
     [("if (r.consequence_of_no_response) lines.push", "if (false) lines.push")], PHONE),
    ("phone drops the authority requested", CORE,
     [('if (rest.length) lines.push("Authority requested: "', 'if (false) lines.push("Authority requested: "')], PHONE),
    ("phone puts the malformed marker after the authority line", CORE,
     [("  " + MALFORMED_JS + "  " + AUTHORITY_JS, "  " + AUTHORITY_JS + "  " + MALFORMED_JS)], PHONE),
    ("phone answers a RECONCILIATION with approve", CORE,
     [('if (r.kind === "RECONCILIATION")', 'if (r.kind === "NEVER")')], PHONE),
    ("phone's It happened sends reconcile_not_executed", CORE,
     [('[["It happened", "reconcile_executed"], ["It did not happen", "reconcile_not_executed"]]',
       '[["It happened", "reconcile_not_executed"], ["It did not happen", "reconcile_executed"]]')], PHONE),
    ("phone's Reject sends approve", CORE,
     [('[["Approve", "approve"], ["Reject", "reject"]]', '[["Approve", "reject"], ["Reject", "approve"]]')], PHONE),
    ("askAnswers offers answers on an ask no DECISION closes", CORE,
     [("  if (r.answerable === false) return [];\n", "")], PHONE),
    ("phone page never renders the terms", APP, [(TERMS, "")], PHONE),
    ("phone page renders the terms only after the unanswerable skip", APP,
     [(TERMS, "    //"), (SKIP, SKIP + "\n" + TERMS)], PHONE),
    ("phone page sends approve whatever the button", APP,
     [("{ request_id: r.request_id, answer, reason: reason.value }",
       '{ request_id: r.request_id, answer: "approve", reason: reason.value }')], PHONE),
    ("phone drops what approving covers", CORE,
     [('if (r.kind === "APPROVAL") lines.push(approvalCovers(r));', "")], PHONE_REAL),
    ("phone drops the params an approval covers", CORE,
     [('if (p !== null && typeof p === "object" && typeof p.json === "string") {', "if (false) {")], PHONE_REAL),
    ("phone drops the action an approval was asked for", CORE,
     [('parts.join("; ") + "." + asked;', 'parts.join("; ") + ".";')], PHONE_REAL),
    ("phone asks for action w on a compensation", CORE,
     [("isCompensation(r) ?", "false ?")], PHONE_COMP),
    ("phone names every approval a compensation", CORE,
     [("isCompensation(r) ?", "true ?")], PHONE_REAL),
    ("phone reads no compensation from an ask recorded before the marker", CORE,
     [('  if ("compensation" in r || r.kind !== "APPROVAL" || !r.action_id) return false;\n', "  return false;\n")],
     PHONE_LEGACY),
    ("phone's unmarked fallback ignores the original receipt", CORE,
     [('    && evidence !== null && typeof evidence === "object" && "original_receipt" in evidence;',
       "    ;")], NEAR),
    ("phone's unmarked fallback matches any action's compensation", CORE,
     [(".startsWith(`compensation of ${r.action_id}:`)", '.startsWith("compensation of ")')], NEAR),
    ("phone's fallback reads any kind", CORE,
     [('if ("compensation" in r || r.kind !== "APPROVAL" ||', 'if ("compensation" in r ||')], NEAR),
    ("phone shows cut params as whole", CORE, [("whole = p.length === shownLength", "whole = true")], PHONE_REAL),
    ("phone prints dicts as JSON", CORE,
     [('if (typeof v === "object") return "{" + Object.keys(v).sort(byCodePoint)',
       'if (typeof v === "object") return JSON.stringify(v); if (0) return "{" + Object.keys(v).sort(byCodePoint)')],
     FORMAT),
    ("phone sorts keys by UTF-16 unit", CORE, [(".sort(byCodePoint)", ".sort()")], FORMAT),
    ("phone joins lists with String()", CORE, [("return v.map(shownValue).join", "return v.join")], FORMAT),
]


def run(repo: Path, node: str):
    return subprocess.run([sys.executable, "-m", "pytest", "-q", "-x", "-rfEs", "-p", "no:cacheprovider", node],
                          cwd=repo, env={**os.environ, "PYTHONPATH": str(repo), "PYTHONDONTWRITEBYTECODE": "1"},
                          capture_output=True, text=True, timeout=300)


def main():
    bad = 0
    with tempfile.TemporaryDirectory(prefix="greg-ask-terms-mutants-") as temp:
        repo = Path(temp) / "repo"
        shutil.copytree(ROOT, repo, ignore=shutil.ignore_patterns(".git", "__pycache__", ".pytest_cache"))
        valid = {}
        for node in dict.fromkeys(m[3] for m in MUTANTS):
            clean = run(repo, node)
            summary = clean.stdout.strip().splitlines()[-1] if clean.stdout.strip() else ""
            valid[node] = clean.returncode == 0 and " passed" in summary and "skipped" not in summary
        for name, relative, replacements, node in MUTANTS:
            path = repo / relative
            original = path.read_text()
            mutated_text = original
            stale = False
            for old, new in replacements:
                if mutated_text.count(old) != 1:
                    stale = True
                    break
                mutated_text = mutated_text.replace(old, new)
            if stale:
                print("STALE", name); bad += 1; continue
            if not valid[node]:
                print("INVALID", name, "(its test does not pass unmutated)"); bad += 1; continue
            path.write_text(mutated_text)
            try:
                mutated = run(repo, node)
            finally:
                path.write_text(original)
            caught = (mutated.returncode == 1 and f"FAILED {node.split('::')[0]}::" in mutated.stdout
                      and "ERROR collecting" not in mutated.stdout)
            print("CAUGHT" if caught else "SURVIVED", name)
            bad += not caught
    print(f"{len(MUTANTS) - bad}/{len(MUTANTS)} caught")
    return int(bool(bad))


if __name__ == "__main__":
    raise SystemExit(main())
