"""For each mutant that survived the builder's tests: does one of the reviewer's probes fail on it (so it is not
an equivalent mutant)? Probes are copied into a scratch copy of the branch; nothing in a worktree changes."""
import importlib.util, os, shutil, subprocess, sys, tempfile, re
from pathlib import Path
S = Path("/tmp/claude-0/-home-user/f78643ba-8a14-5107-b25c-e0462dfdc774/scratchpad")
spec = importlib.util.spec_from_file_location("em", S / "adv-negrc-probes/extra_mutants.py")
src = (S / "adv-negrc-probes/extra_mutants.py").read_text().replace("\nmain()\n", "\n")
ns = {"__name__": "em"}
sys.argv = ["x", str(S / "adv-negrc")]
exec(compile(src, "em", "exec"), ns)
MUT = {m[0].split()[0]: m for m in ns["MUTANTS"]}
P1, P2 = "tests/unit/test_adv_probe_negrc.py", "tests/unit/test_adv_probe_negrc2.py"
PAIRS = [("A1", P2 + "::test_q1_a_recovered_receipt_of_a_paid_action_books_its_signed_cost"),
         ("A3", P2 + "::test_q4_a_compensation_the_founder_declined_is_not_asked_about_again"),
         ("A4", P1 + "::test_p7_an_uncertain_compensations_lost_question_is_asked_after_the_restart"),
         ("A10", P1 + "::test_p7_an_uncertain_compensations_lost_question_is_asked_after_the_restart"),
         ("A6", P2 + "::test_q3_a_completed_non_worker_output_that_says_uncertain_is_still_done"),
         ("A13", P1 + "::test_p3_compensation_killed_inside_adapter_is_uncertain_asked_and_never_rerun"),
         ("A8", "tests/unit/test_greg_retained_receipt.py"), ]
with tempfile.TemporaryDirectory(prefix="adv-negrc-kill-") as temp:
    repo = Path(temp) / "repo"
    shutil.copytree(S / "adv-negrc", repo, ignore=shutil.ignore_patterns(".git", "__pycache__", ".pytest_cache"))
    for f in ("test_adv_probe_negrc.py", "test_adv_probe_negrc2.py"):
        shutil.copy(S / "adv-negrc-probes" / f, repo / "tests/unit" / f)
    env = {**os.environ, "PYTHONPATH": str(repo), "PYTHONDONTWRITEBYTECODE": "1"}
    def run(node):
        for top in ("greg", "tests"):
            for c in (repo / top).rglob("__pycache__"):
                shutil.rmtree(c, ignore_errors=True)
        r = subprocess.run([sys.executable, "-B", "-m", "pytest", "-q", "-p", "no:cacheprovider", "-rf", node],
                           cwd=repo, env=env, capture_output=True, text=True, timeout=900)
        return r.returncode, (r.stdout.strip().splitlines() or ["?"])[-1], re.findall(r"^E\s+(.*)", r.stdout, flags=re.M)[:2]
    for key, node in PAIRS:
        base = run(node)
        name, target, old, new = MUT[key]
        path = repo / target
        original = path.read_text()
        assert original.count(old) == 1, key
        path.write_text(original.replace(old, new))
        try:
            mutated = run(node)
        finally:
            path.write_text(original)
        print(f"{key}: unmutated -> {base[1]} | mutated -> {mutated[1]} {mutated[2]}", flush=True)
