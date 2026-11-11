"""Reviewer's mutants of the branch's new code that the builder's gate does not list. Run against a scratch copy
of the adv-br worktree with the builder's own test file. A survivor is a behaviour no stand-in test holds."""
import sys
from pathlib import Path
ROOT = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(ROOT / "scripts" / "ci"))
from mutation_harness import run  # noqa: E402

TESTS = "tests/unit/test_greg_browser_binary.py"
C = "greg/capabilities.py"
MUTANTS = [
    (C, "R1 a directory is not an installed browser (is_file dropped)",
     "    return bool(path) and Path(path).is_file() and os.access(path, os.X_OK)",
     "    return bool(path) and os.access(path, os.X_OK)"),
    (C, "R2 a file that is not executable is not an installed browser (X_OK dropped)",
     "    return bool(path) and Path(path).is_file() and os.access(path, os.X_OK)",
     "    return bool(path) and Path(path).is_file()"),
    (C, "R3 a replaced binary of the same size is judged again (size alone as identity)",
     "    key = (binary, made.st_size, made.st_mtime_ns)", "    key = (binary, made.st_size)"),
    (C, "R4 a replaced binary with the same mtime is judged again (mtime alone as identity)",
     "    key = (binary, made.st_size, made.st_mtime_ns)", "    key = (binary, made.st_mtime_ns)"),
    (C, "R5 a candidate that vanished before it was judged is a reason, not an exception",
     '        return f"cannot be read ({exc.strerror})"', "        raise"),
    (C, "R6 the check runs in its own fresh directory, not the caller's",
     "timeout=RENDER_SECONDS, cwd=profile,", "timeout=RENDER_SECONDS,"),
    (C, "R7 as root on Linux the browser is told it cannot sandbox itself",
     '    return not (sys.platform.startswith("linux") and os.geteuid() == 0)', "    return True"),
    (C, "R8 a render (not the check) that never returns ends at RENDER_SECONDS",
     "timeout=RENDER_SECONDS, env=env, cwd=profile)", "timeout=RENDER_SECONDS * 10000, env=env, cwd=profile)"),
    (C, "R9 a render that ran out of time is a CapabilityError naming the limit",
     '            raise CapabilityError(f"browser did not finish rendering within {RENDER_SECONDS} seconds") from exc',
     "            raise"),
    (C, "R10 the manifest names the first installed candidate",
     "                                binaries=(installed_chrome(),), target_from=\"url\",",
     "                                binaries=(CHROME_CANDIDATES[0],), target_from=\"url\","),
    (C, "R11 a build directory with no number sorts after every numbered build",
     "        return int(number) if number.isdigit() else -1", "        return int(number) if number.isdigit() else 10 ** 9"),
    (C, "R12 the headless run keeps background networking off (flag content)",
     '"--disable-extensions", "--disable-background-networking", "--disable-sync",',
     '"--disable-extensions", "--enable-logging", "--disable-sync",'),
    (C, "R13 a failure is remembered with the time it was judged (retry clock)",
     "    _render_judged[key] = (time.monotonic(), why)", "    _render_judged[key] = (time.monotonic() + 10 ** 9, why)"),
]
if __name__ == "__main__":
    raise SystemExit(run(MUTANTS, TESTS, prefix="adv-br-extra-mutants-", root=ROOT))
