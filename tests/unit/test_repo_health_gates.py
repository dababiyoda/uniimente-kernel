"""Gate liveness and the environment doctor (scripts/repo_review.py, scripts/dev_env_check.py).

Gate liveness: every literal mutation anchor still occurs in its target file, and
every mutation gate is run by some workflow (shrink-only KEPT list). A stale anchor
otherwise surfaces only when the gate runs late in Canonical CI job 1.

Environment doctor: names the machine-side causes of test failure before tests run
(register P-8 and P-14).
"""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


review = _load("repo_review")
doctor = _load("dev_env_check")


# ------------------------------------------------------------------ gate liveness

def test_no_mutation_anchor_is_stale():
    gates = review.gate_liveness(ROOT)
    assert sum(r["anchors_checked"] for r in gates.values()) > 100   # the check is not vacuous
    stale = {g: r["stale"] for g, r in gates.items() if r["stale"]}
    assert not stale, stale


def test_unwired_gates_match_the_shrink_only_list():
    gates = review.gate_liveness(ROOT)
    unwired = {g for g, r in gates.items() if not r["wired"]}
    assert review.ratchet(unwired, review.KEPT_UNWIRED_GATES) == {"new": [], "gone": []}


def _mini(tmp_path, target_text, gate_text, workflow_text=""):
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "mod.py").write_text(target_text)
    (tmp_path / "scripts" / "ci").mkdir(parents=True)
    (tmp_path / "scripts" / "ci" / "check_demo_mutants.py").write_text(gate_text)
    (tmp_path / ".github" / "workflows").mkdir(parents=True)
    (tmp_path / ".github" / "workflows" / "ci.yml").write_text(workflow_text)
    return tmp_path


GATE = 'MUTANTS = [("drop check", "pkg/mod.py", "if ok:", "if True:", "tests/x.py::t")]\n'


def test_live_anchor_passes(tmp_path):
    root = _mini(tmp_path, "if ok:\n    pass\n", GATE, "run: python scripts/ci/check_demo_mutants.py")
    row = review.gate_liveness(root)["check_demo_mutants.py"]
    assert row == {"anchors_checked": 1, "stale": [], "multi_site": [], "wired": True}


def test_moved_code_makes_the_anchor_stale(tmp_path):
    root = _mini(tmp_path, "if is_ok():\n    pass\n", GATE, "check_demo_mutants.py")
    assert review.gate_liveness(root)["check_demo_mutants.py"]["stale"] == [
        {"target": "pkg/mod.py", "anchor": "if ok:"}]


def test_anchor_at_two_sites_is_advisory_not_stale(tmp_path):
    root = _mini(tmp_path, "if ok:\n    a()\nif ok:\n    b()\n", GATE, "check_demo_mutants.py")
    row = review.gate_liveness(root)["check_demo_mutants.py"]
    assert row["stale"] == [] and row["multi_site"][0]["sites"] == 2


def test_a_gate_no_workflow_runs_is_unwired(tmp_path):
    root = _mini(tmp_path, "if ok:\n", GATE, "")
    assert review.gate_liveness(root)["check_demo_mutants.py"]["wired"] is False


def test_a_list_of_test_paths_is_not_read_as_an_anchor(tmp_path):
    gate = 'TESTS = ["pkg/mod.py", "tests/unit/test_other.py"]\n'
    root = _mini(tmp_path, "x = 1\n", gate, "check_demo_mutants.py")
    assert review.gate_liveness(root)["check_demo_mutants.py"]["anchors_checked"] == 0


def test_text_a_mutant_appends_or_creates_is_not_read_as_an_anchor(tmp_path):
    """("append", path, text) and ("create", path, text) add new text; it is not expected in the file. The
    canonical-owner guard gate (#253) uses both, and every one read as stale on the joined tree."""
    gate = ('MUTANTS = [("dup", [("append", "pkg/mod.py", "\\n\\ndef _probe():\\n    pass\\n")], "t"),\n'
            '           ("new", [("create", "pkg/mod.py", "def f():\\n    return 1\\n")], "t"),\n'
            '           ("swap", [("replace", "pkg/mod.py", "if ok:", "if True:")], "t")]\n')
    root = _mini(tmp_path, "if ok:\n    pass\n", gate, "check_demo_mutants.py")
    row = review.gate_liveness(root)["check_demo_mutants.py"]
    assert row["stale"] == [] and row["anchors_checked"] == 1        # only the replace anchor is checked


# ---------------------------------------------------------------- environment doctor

def test_doctor_report_shape_and_read_only():
    report = doctor.build_report()
    assert report["schema"] == "uniimente.dev_env_check/1"
    assert set(report["requirements"]) == set(doctor.REQUIREMENT_FILES)
    for name in doctor.REQUIREMENT_FILES:
        assert (ROOT / name).is_file(), name   # every file it reads exists


def test_requirements_follow_includes(tmp_path):
    (tmp_path / "base.txt").write_text("alpha>=1\n# comment\n")
    (tmp_path / "top.txt").write_text("-r base.txt\nbeta==2  # pinned\n")
    assert doctor._requirements(tmp_path / "top.txt") == ["alpha>=1", "beta==2"]


def test_missing_and_wrong_version_packages_are_reported():
    assert doctor._check_requirement("uniimente-no-such-package==1.0")["ok"] is False
    assert doctor._check_requirement("pytest>=1")["ok"] is True
    assert doctor._check_requirement("pytest<1")["ok"] is False


MOUNTS = "proc /proc proc rw 0 0\n/dev/sda1 / ext4 rw 0 0\ntmpfs /tmp tmpfs rw 0 0\n"


def test_tmpfs_tempdir_is_detected_as_volatile():
    assert doctor._fs_type("/tmp/x", MOUNTS) == "tmpfs"
    assert doctor._fs_type("/home/runner/work", MOUNTS) == "ext4"
    assert "tmpfs" in doctor.VOLATILE_FS


def test_renamed_copies_of_one_body_are_reported_once(tmp_path):
    def body(var: str) -> str:
        return ("    total = 0\n" + "".join(f"    total += {var} * {i}\n" for i in range(10))
                + "    return total\n")
    (tmp_path / "a.py").write_text("def score(x):\n" + body("x"))
    (tmp_path / "b.py").write_text("def weigh(y):\n" + body("y"))
    (tmp_path / "c.py").write_text("def short(z):\n    return z\n")
    groups = review.duplicate_functions(tmp_path)
    assert [sorted(x["path"] for x in g) for g in groups] == [["a.py", "b.py"]]
