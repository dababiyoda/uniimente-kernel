"""Each decision of browser.render's browser choice must fail a behavioural test when removed.

    python scripts/ci/check_browser_choice_mutants.py

The decisions are those of the smallest repair measured against #293's render check
(docs/evidence/greg-browser-binary/2026-11-12-smallest): the order (headless shells first, both full-build layouts),
the manifest naming no binary, GREG_CHROMIUM refused by name, no installed browser and an unstartable one refused.
A mutant counts as caught only when tests/unit/test_greg_browser_choice.py reports a FAILED test (an import or
collection error does not count). The tests run stand-in executables, so the gate needs no browser and no network.
A scratch copy is mutated; the live source never is. Exit 1 on any survivor or stale anchor.
"""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mutation_harness import run  # noqa: E402

TESTS = "tests/unit/test_greg_browser_choice.py"
C = "greg/capabilities.py"

ORDER = "    return [candidate for candidate in (*shells, *HEADLESS_SHELL_CANDIDATES, *CHROME_CANDIDATES, *full)"
INSTALLED = "            if Path(candidate).is_file() and os.access(candidate, os.X_OK)]"
A_CHOICE = "        if not (os.path.isabs(chosen) and Path(chosen).is_file() and os.access(chosen, os.X_OK)):"
NONE_FOUND = "    if not found:       # a refusal, not a path that does not exist (whose FileNotFoundError the Gate cannot type)\n        raise CapabilityError(NO_BROWSER)\n    return found[0]"
REFUSED_CHOICE = (A_CHOICE + """
            raise CapabilityError(f"GREG_CHROMIUM is set to {chosen!r}, which is not the absolute path of an "
                                  "executable file; GREG runs the browser that variable names or none (unset it "
                                  "to let GREG choose among the installed browsers)")
        return [chosen]
""")
NOT_STARTED = "                except OSError as exc:      # installed, and the system cannot start it (or it is gone): a refusal"

MUTANTS = [
    # which installed browsers, in which order
    (C, "the headless shells are tried before an installed Chrome and the full builds", ORDER,
     "    return [candidate for candidate in (*CHROME_CANDIDATES, *full, *shells, *HEADLESS_SHELL_CANDIDATES)"),
    (C, "the system headless shell is tried before an installed Chrome", ORDER,
     "    return [candidate for candidate in (*shells, *CHROME_CANDIDATES, *HEADLESS_SHELL_CANDIDATES, *full)"),
    (C, "a full build is found under either spelling of its OS directory",
     '    full = sorted(glob.glob(f"{PLAYWRIGHT_BROWSERS}/chromium-*/chrome-linux*/chrome"))',
     '    full = sorted(glob.glob(f"{PLAYWRIGHT_BROWSERS}/chromium-*/chrome-linux/chrome"))'),
    (C, "the headless shell is found where Playwright installs it",
     '    shells = sorted(glob.glob(f"{PLAYWRIGHT_BROWSERS}/chromium_headless_shell-*/chrome-headless-shell-*/"',
     '    shells = sorted(glob.glob(f"{PLAYWRIGHT_BROWSERS}/chromium-*/chrome-headless-shell-*/"'),
    (C, "a directory is not an installed browser", INSTALLED,
     "            if os.access(candidate, os.X_OK)]"),
    (C, "a file that is not executable is not an installed browser", INSTALLED,
     "            if Path(candidate).is_file()]"),
    # the founder's choice
    (C, "the founder's chosen browser is the one used", "        return [chosen]\n",
     "        ignored = [chosen]\n"),
    (C, "a choice that names no executable file is refused, not passed over for another browser", REFUSED_CHOICE,
     "        if os.path.isabs(chosen) and Path(chosen).is_file() and os.access(chosen, os.X_OK):\n"
     "            return [chosen]\n"),
    (C, "a choice that is not an absolute path is refused", A_CHOICE,
     "        if not (Path(chosen).is_file() and os.access(chosen, os.X_OK)):"),
    (C, "a refused choice makes the capability unavailable with that reason",
     "    except CapabilityError as exc:      # GREG_CHROMIUM names no browser\n        return False, str(exc)",
     '    except CapabilityError as exc:      # GREG_CHROMIUM names no browser\n        return True, "available"'),
    # no browser, or one that cannot start
    (C, "no installed browser is a refusal from the adapter", NONE_FOUND,
     "    return found[0] if found else CHROME_CANDIDATES[0]"),
    (C, "no installed browser is unavailable at the office's precheck",
     '        return (True, "available") if chrome_candidates() else (False, NO_BROWSER)',
     '        return True, "available"'),
    (C, "an installed browser the system cannot start is a refusal, not an unknown outcome", NOT_STARTED,
     "                except ValueError as exc:"),
    # the manifest and the office
    (C, "the office asks what is installed when it asks whether browser.render is available",
     '        return asked_now() if asked_now is not None else (True, "available")',
     '        return True, "available"'),
    (C, "the manifest names no binary, so the separate appraiser derives the body's digest",
     '                                target_from="url",\n                                provenance={"source": "uniimente-kernel/greg/capabilities.py",\n'
     '                                            "mechanism_from": "installed Chrome/Chromium --headless --dump-dom"}),',
     '                                binaries=tuple(chrome_candidates()[:1]), target_from="url",\n'
     '                                provenance={"source": "uniimente-kernel/greg/capabilities.py",\n'
     '                                            "mechanism_from": "installed Chrome/Chromium --headless --dump-dom"}),'),
]

if __name__ == "__main__":
    sys.exit(run(MUTANTS, TESTS, "greg-browser-choice-mutants-"))
