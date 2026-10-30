"""Every surface that offers an answer must keep showing the exact scope and what silence does (directive part 2 §9).

Each named test must pass unmutated in the copy first (a skipped or failing test is INVALID, never a catch), and a
mutant is caught only when its named test fails.
"""
from pathlib import Path
import os, shutil, subprocess, sys, tempfile

ROOT = Path(__file__).resolve().parents[2]
FILE = "tests/unit/test_greg_ask_terms_surfaces.py"
PAGES = FILE + "::test_console_and_mission_control_show_the_exact_scope_and_what_silence_does"
ACTION = FILE + "::test_the_console_names_the_action_when_the_projection_carries_it"
ESCAPE = FILE + "::test_the_console_escapes_the_scope_and_the_consequence"
PHONE = FILE + "::test_the_phone_shows_the_same_terms_and_sends_only_answers_the_body_applies"
MUTANTS = [
    ("console drops what silence does", "greg/console.py",
     'if r.get("consequence_of_no_response"):\n        parts.append("<br><b>If you do not answer:',
     'if False:\n        parts.append("<br><b>If you do not answer:', PAGES),
    ("console shows only the reach keys again", "greg/console.py",
     ".items() if k not in reach}", ".items() if k in reach}", PAGES),
    ("console repeats the reach keys", "greg/console.py", ".items() if k not in reach}", ".items()}", PAGES),
    ("console drops the action", "greg/console.py",
     '**({"action": r["action_id"]} if r.get("action_id") else {}),', "", ACTION),
    ("console stops escaping the consequence", "greg/console.py",
     '_e(r["consequence_of_no_response"])', 'r["consequence_of_no_response"]', ESCAPE),
    ("console stops escaping the scope", "greg/console.py",
     '"<br><b>Exact scope of this ask:</b> " + _e(', '"<br><b>Exact scope of this ask:</b> " + str(', ESCAPE),
    ("phone drops what silence does", "greg/phone/core.js",
     "if (r.consequence_of_no_response) lines.push", "if (false) lines.push", PHONE),
    ("phone scope omits authority_requested", "greg/phone/core.js",
     "...(r.authority_requested || {}) });", "});", PHONE),
    ("phone answers a RECONCILIATION with approve", "greg/phone/core.js",
     'if (r.kind === "RECONCILIATION")', 'if (r.kind === "NEVER")', PHONE),
    ("phone page never renders the terms", "greg/phone/app.js",
     'for (const line of askTerms(r)) card.append(el("p", line));', "", PHONE),
    ("phone page sends approve whatever the button", "greg/phone/app.js",
     "{ request_id: r.request_id, answer, reason: reason.value }",
     '{ request_id: r.request_id, answer: "approve", reason: reason.value }', PHONE),
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
        for node in dict.fromkeys(m[4] for m in MUTANTS):
            clean = run(repo, node)
            summary = clean.stdout.strip().splitlines()[-1] if clean.stdout.strip() else ""
            valid[node] = clean.returncode == 0 and " passed" in summary and "skipped" not in summary
        for name, relative, old, new, node in MUTANTS:
            path = repo / relative
            original = path.read_text()
            if original.count(old) != 1:
                print("STALE", name); bad += 1; continue
            if not valid[node]:
                print("INVALID", name, "(its test does not pass unmutated)"); bad += 1; continue
            path.write_text(original.replace(old, new))
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
