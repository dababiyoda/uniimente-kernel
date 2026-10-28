"""greg/chromebook/install.sh: one command to a designated Body 1, idempotent, honest refusals.

Exercised in a Linux container without systemd, so --no-service and --allow-other-linux
are used; the ChromeOS path, the systemd user service and Alfonso's passphrase-protected
key are NOT exercised here. A generated encrypted fixture key exercises only the
read-only CLI. This proves the composition of existing greg commands, not a Chromebook install.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

from greg.body import Body
from greg.founder import FounderAuthError, generate_founder_key, key_id, load_founder_key, sign_command

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "greg/chromebook/install.sh"
pytestmark = pytest.mark.skipif(shutil.which("bash") is None or shutil.which("git") is None,
                                reason="needs bash and git")


def run(args, tmp: Path, **kw):
    env = {**os.environ, "HOME": str(tmp / "home"), "PATH": f"{tmp / 'bin'}:{os.environ['PATH']}"}
    env.pop("GREG_FOUNDER_PASSPHRASE", None)
    (tmp / "home").mkdir(exist_ok=True)
    return subprocess.run(["bash", str(SCRIPT), *args], capture_output=True, text=True, env=env, timeout=300, **kw)


def dev_args(tmp: Path):
    return ["--allow-other-linux", "--no-service", "--skip-deps", "--no-passphrase", "--python", sys.executable,
            "--home", str(tmp / "body"), "--key", str(tmp / "founder.pem"), "--bin-dir", str(tmp / "bin"),
            "--read-root", str(tmp / "src"), "--deliver-root", str(tmp / "GREG")]


def greg(tmp: Path, *args):
    out = subprocess.run([str(tmp / "bin/greg"), *args], capture_output=True, text=True, timeout=120,
                         env={**os.environ, "HOME": str(tmp / "home")})
    assert out.returncode == 0, out.stderr[-2000:]
    return out.stdout


def test_one_command_reaches_a_designated_body_and_a_rerun_changes_nothing(tmp_path):
    first = run(dev_args(tmp_path), tmp_path)
    assert first.returncode == 0, first.stdout[-3000:] + first.stderr[-3000:]
    assert "WARNING: not ChromeOS Linux" in first.stdout and "unprotected" in first.stdout
    head = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    assert f"Installing code {head} " in first.stdout                         # the commit an acceptance will name
    assert (tmp_path / "founder.pem").exists() and len((tmp_path / "founder.pem.pub").read_text().strip()) == 64
    assert list((tmp_path / "body/inbox").glob("*body_designate*.json"))          # queued, not self-accepted

    greg(tmp_path, "run", "--tick-seconds", "0.05", "--max-ticks", "2")          # the body accepts it
    status = json.loads(greg(tmp_path, "status"))
    assert len(status["security"]["founder_keys_enrolled"]) == 1
    assert [d["purpose"] for d in status["designation"]] == ["first_founder_body"]
    assert status["developmental_position"]["active"] == "N1"

    key_before = (tmp_path / "founder.pem").read_bytes()
    second = run(dev_args(tmp_path), tmp_path)
    assert second.returncode == 0, second.stdout[-3000:] + second.stderr[-3000:]
    assert "already designated" in second.stdout and "already enrolled" in second.stdout
    assert (tmp_path / "founder.pem").read_bytes() == key_before                  # never regenerates a key
    assert not list((tmp_path / "body/inbox").glob("*body_designate*.json"))      # no second designation
    path = json.loads(greg(tmp_path, "path"))
    assert path["active"]["id"] == "N1" and path["active"]["measurement"]["met"] is False


def test_it_refuses_to_pretend_another_linux_is_the_chromebook(tmp_path):
    args = [a for a in dev_args(tmp_path) if a != "--allow-other-linux"]
    if Path("/dev/.cros_milestone").exists() or Path("/opt/google/cros-containers").exists():
        pytest.skip("running inside ChromeOS Linux")
    out = run(args, tmp_path)
    assert out.returncode == 10 and "Settings > About ChromeOS > Developers" in out.stderr
    assert not (tmp_path / "body").exists() and not (tmp_path / "founder.pem").exists()


def test_it_stops_with_the_fix_when_no_python_311_exists(tmp_path):
    fake_bin = tmp_path / "fakebin"
    fake_bin.mkdir()
    old = fake_bin / "python3"
    old.write_text("#!/bin/sh\nexit 1\n")                                         # every version check fails
    old.chmod(0o755)
    for name in ("bash", "git", "uname", "dirname", "cat", "mkdir", "chmod"):
        found = shutil.which(name)
        if found:
            (fake_bin / name).symlink_to(found)
    env = {"HOME": str(tmp_path), "PATH": str(fake_bin)}
    out = subprocess.run([str(fake_bin / "bash"), str(SCRIPT), "--allow-other-linux", "--no-service"],
                         capture_output=True, text=True, env=env, timeout=60)
    assert out.returncode == 11 and "sudo apt install -y python3 python3-venv git" in out.stderr


def test_engines_are_best_effort_and_can_be_skipped(tmp_path):
    usage = run(["--help"], tmp_path)
    assert "--no-engines" in usage.stdout
    text = SCRIPT.read_text()
    assert "--only-binary=:all:" in text and "Body 1 continues" in text     # never compiles; never blocks Body 1
    done = run(dev_args(tmp_path) + ["--no-engines"], tmp_path)
    assert done.returncode == 0, done.stdout[-3000:] + done.stderr[-3000:]
    assert "Reasoning engines present:" in done.stdout


def _engine_specs():
    """Every requirement line the engine step must install, following -r includes, in file order."""
    def specs(path):
        for raw in path.read_text().splitlines():
            line = raw.split("#", 1)[0].strip()
            if line.startswith("-r "):
                yield from specs(path.parent / line[3:].strip())
            elif line:
                yield line
    return list(specs(ROOT / "requirements-cognition.txt"))


def test_an_engine_without_a_wheel_for_this_machine_costs_only_that_engine(tmp_path):
    """The pinned Z3's only Linux ARM64 wheel needs glibc 2.38; Debian 12, ChromeOS Linux's base, has 2.36, so pip
    finds nothing to install there (PyPI files, checked 2026-10-28). One pip call for every engine then failed as
    a whole and an ARM Chromebook got no engine at all. Here pip is a stand-in that has no wheel for z3-solver."""
    venv, log = tmp_path / "venv", tmp_path / "pip.log"
    (venv / "bin").mkdir(parents=True)
    fake = venv / "bin/python"
    fake.write_text(f"""#!/bin/sh
if [ "$1" = "-m" ] && [ "$2" = "pip" ]; then
  echo "$*" >> {log}
  case "$*" in
    *z3-solver*|*requirements-cognition.txt*|*requirements-cortex.txt*)
      echo "ERROR: No matching distribution found for z3-solver==5.1.0.0" >&2; exit 1 ;;
  esac
  exit 0
fi
exec {sys.executable} "$@"
""")
    fake.chmod(0o755)
    args = [a for a in dev_args(tmp_path) if a != "--skip-deps"] + ["--venv", str(venv)]
    out = run(args, tmp_path)
    assert out.returncode == 0, out.stdout[-3000:] + out.stderr[-3000:]          # Body 1 is still created
    calls = [line for line in log.read_text().splitlines() if "--only-binary=:all:" in line]
    specs = _engine_specs()
    assert len(calls) == len(specs) and [c.rsplit(" ", 1)[-1] for c in calls] == specs   # one call per engine
    assert all(" -c " in c for c in calls)                                       # each under the same pins
    assert "not installed: z3-solver==5.1.0.0 (ERROR: No matching distribution found" in out.stdout
    assert "WARNING: 1 reasoning engine requirement(s) did not install: z3-solver==5.1.0.0. Every other engine did." \
        in out.stdout


def test_the_doctor_says_why_an_engine_has_no_wheel_on_this_machine(monkeypatch):
    from greg import doctor, mechanisms
    real = mechanisms.installed
    monkeypatch.setattr(mechanisms, "installed", lambda name: None if name == "z3-solver" else real(name))
    monkeypatch.setattr(doctor.platform, "machine", lambda: "aarch64")
    monkeypatch.setattr(doctor.platform, "libc_ver", lambda: ("glibc", "2.36"))
    report = doctor.engines()
    z3 = next(r for r in report["engines"] if r["distribution"] == "z3-solver")
    assert "z3-solver" in report["missing"] and report["platform"] == {"machine": "aarch64", "glibc": "2.36"}
    assert "needs glibc 2.38, this system has 2.36" in z3["why_missing"]
    monkeypatch.setattr(doctor.platform, "machine", lambda: "x86_64")      # x86-64 has a wheel: no such claim
    assert "why_missing" not in next(r for r in doctor.engines()["engines"] if r["distribution"] == "z3-solver")


# -- #138 (b8a0ccd): the actual signer must be the companion's key and the body's enrolled key ----------

def test_existing_private_key_recovers_missing_public_companion(tmp_path):
    public = generate_founder_key(tmp_path / "founder.pem", None)
    before = (tmp_path / "founder.pem").read_bytes()
    result = run(dev_args(tmp_path), tmp_path)
    assert result.returncode == 0, result.stderr
    assert (tmp_path / "founder.pem").read_bytes() == before
    assert (tmp_path / "founder.pem.pub").read_text().strip() == public
    greg(tmp_path, "run", "--tick-seconds", "0.05", "--max-ticks", "1")
    state = json.loads(greg(tmp_path, "status"))
    assert state["security"]["founder_keys_enrolled"] == [key_id(public)]
    assert len(state["designation"]) == 1


def test_wrong_public_companion_refuses_before_enrollment_or_designation(tmp_path):
    generate_founder_key(tmp_path / "founder.pem", None)
    other_public = generate_founder_key(tmp_path / "other.pem", None)
    companion = tmp_path / "founder.pem.pub"
    companion.write_text(other_public + "\n")
    before = (tmp_path / "founder.pem").read_bytes()
    result = run(dev_args(tmp_path), tmp_path)
    assert result.returncode == 14 and "does not match" in result.stderr
    assert companion.read_text().strip() == other_public
    assert (tmp_path / "founder.pem").read_bytes() == before
    assert not list((tmp_path / "body/inbox").glob("*.json"))
    assert not (tmp_path / "home/.config/systemd/user/greg-body.service").exists()
    with Body(tmp_path / "body") as body:
        assert not body.enrolled_keys()
        assert not body.journal.replay("body.designated")


def test_other_private_key_cannot_replace_existing_enrollment(tmp_path):
    assert run(dev_args(tmp_path), tmp_path).returncode == 0
    greg(tmp_path, "run", "--tick-seconds", "0.05", "--max-ticks", "1")
    before = (tmp_path / "body/ledger.jsonl").read_bytes()
    other = tmp_path / "other.pem"
    generate_founder_key(other, None)
    args = dev_args(tmp_path)
    args[args.index("--key") + 1] = str(other)
    result = run(args, tmp_path)
    assert result.returncode == 14 and "not this body's currently enrolled" in result.stderr
    assert (tmp_path / "body/ledger.jsonl").read_bytes() == before
    assert not list((tmp_path / "body/inbox").glob("*.json"))


def test_installer_accepts_only_the_current_key_after_signed_rotation(tmp_path):
    assert run(dev_args(tmp_path), tmp_path).returncode == 0
    greg(tmp_path, "run", "--tick-seconds", "0.05", "--max-ticks", "1")
    old = load_founder_key(tmp_path / "founder.pem", None)
    new_file = tmp_path / "rotated.pem"
    new_public = generate_founder_key(new_file, None)
    with Body(tmp_path / "body") as body:
        body.apply(sign_command(old, "ROTATE_FOUNDER_KEY", {"new_public_key": new_public},
                                body_id=body.config["body_id"]))
    state = json.loads(greg(tmp_path, "status"))
    assert state["security"]["founder_keys_enrolled"] == [key_id(new_public)]
    args = dev_args(tmp_path)
    args[args.index("--key") + 1] = str(new_file)
    result = run(args, tmp_path)
    assert result.returncode == 0, result.stderr
    assert "already enrolled" in result.stdout and "already designated" in result.stdout
    assert (tmp_path / "rotated.pem.pub").read_text().strip() == new_public
    assert not list((tmp_path / "body/inbox").glob("*.json"))
    rejected = run(dev_args(tmp_path), tmp_path)
    assert rejected.returncode == 14 and "not this body's currently enrolled" in rejected.stderr


def test_founder_public_unlocks_encrypted_key_without_opening_a_body(tmp_path, monkeypatch, capsys):
    from greg.cli import main
    key = tmp_path / "encrypted.pem"
    public = generate_founder_key(key, b"fixture-passphrase")
    before = key.read_bytes()
    monkeypatch.delenv("GREG_FOUNDER_PASSPHRASE", raising=False)
    monkeypatch.setattr("greg.cli.getpass.getpass", lambda prompt: "fixture-passphrase")
    missing_body = tmp_path / "not-a-body"
    assert main(["--home", str(missing_body), "founder", "public", "--key", str(key)]) == 0
    assert capsys.readouterr().out.strip() == public
    assert not missing_body.exists() and key.read_bytes() == before
    key.chmod(0o644)
    with pytest.raises(FounderAuthError, match="readable by others"):
        main(["--home", str(missing_body), "founder", "public", "--key", str(key)])


def test_a_rerun_offers_the_founder_tier_to_a_body_designated_without_it(tmp_path):
    """A body designated before FOUNDER_TIER existed stayed silently unattested (review of 2026-10-14).
    The re-run now sees it in ``greg status`` and queues the attestation with the protected key."""
    args = [a for a in dev_args(tmp_path) if a != "--no-passphrase"]
    env = {**os.environ, "HOME": str(tmp_path / "home"), "PATH": f"{tmp_path / 'bin'}:{os.environ['PATH']}",
           "GREG_FOUNDER_PASSPHRASE": "a test passphrase, not Alfonso's"}
    (tmp_path / "home").mkdir(exist_ok=True)
    first = subprocess.run(["bash", str(SCRIPT), *args], capture_output=True, text=True, env=env, timeout=300)
    assert first.returncode == 0, first.stdout[-3000:] + first.stderr[-3000:]
    for queued in (tmp_path / "body/inbox").glob("*founder_tier*.json"):
        queued.unlink()                                  # as if designated before the attestation existed
    greg(tmp_path, "run", "--tick-seconds", "0.05", "--max-ticks", "2")
    assert json.loads(greg(tmp_path, "status"))["founder_tier"]["enrolled_key_attested"] is False
    second = subprocess.run(["bash", str(SCRIPT), *args], capture_output=True, text=True, env=env, timeout=300)
    assert second.returncode == 0, second.stdout[-3000:] + second.stderr[-3000:]
    assert "already designated" in second.stdout and "Founder-tier attestation queued" in second.stdout
    assert list((tmp_path / "body/inbox").glob("*founder_tier*.json"))
    greg(tmp_path, "run", "--tick-seconds", "0.05", "--max-ticks", "2")
    assert json.loads(greg(tmp_path, "status"))["founder_tier"]["enrolled_key_attested"] is True
    third = subprocess.run(["bash", str(SCRIPT), *args], capture_output=True, text=True, env=env, timeout=300)
    assert "has claimed the founder tier" in third.stdout and not list((tmp_path / "body/inbox").glob("*.json"))


# Every runbook or script that tells the founder to install the kernel by clone or checkout. A surface found by
# install_surfaces() must be listed here or in NOT_FOUNDER_INSTALL with the reason it installs no body.
FOUNDER_INSTALL_SURFACES = (
    "greg/CHROMEBOOK_FIRST_MISSION.md",
    "greg/chromebook/install.sh",
    "greg/FIRST_MISSION.md",                            # the Mac runbook
    "docs/opus-maximus/MISSION_CONTROL_OPERATIONS.md",  # the founder's operator card, section 1 "Install"
)
NOT_FOUNDER_INSTALL = {
    "docs/OPEN_SOURCE_RESEARCH_LINE.md": "an offline research preview beside the organ clones; it installs no body",
}


def install_commands(rel: str):
    """Commands a founder would copy: fenced blocks of a runbook, the whole of a script. Inline mentions (a rollback
    row, a checkout GREG is to read) are not install steps."""
    import re
    text = (ROOT / rel).read_text()
    if not rel.endswith(".md"):
        return [text]
    return [m.group(2) for m in re.finditer(r"^(```|~~~)[^\n]*\n(.*?)^\1[ \t]*$", text, re.M | re.S)]


def named_branches(block: str):
    """The branch each kernel clone installs: its -b/--branch, else the next checkout/switch, else None (the default
    branch). A checkout/switch with no clone in the block names its branch too."""
    import re
    named, clone_waiting = [], False
    for line in block.splitlines():
        clone = re.search(r"git clone\b(.*)", line)
        if clone and "uniimente-kernel" in clone.group(1):
            if clone_waiting:
                named.append(None)
            b = re.search(r"(?:-b|--branch)[ =](\S+)", clone.group(1))
            if b:
                named.append(b.group(1))
            clone_waiting = not b
            continue
        b = re.search(r"git (?:checkout|switch)(?: -c| -b)? ([^\s`;&|]+)", line)
        if b:
            named.append(b.group(1))
            clone_waiting = False
    return named + ([None] if clone_waiting else [])


def install_surfaces():
    import re
    tracked = subprocess.run(["git", "ls-files", "*.md", "*.sh"], cwd=ROOT, capture_output=True, text=True,
                             check=True).stdout.split()
    return {rel for rel in tracked if not rel.startswith(("tests/", "docs/evidence/")) and (ROOT / rel).is_file()
            and any(re.search(r"git clone\b[^\n]*uniimente-kernel|git (?:checkout|switch) ", b)
                    for b in install_commands(rel))}


def test_every_founder_install_surface_names_the_one_review_branch():
    """The runbooks and the installer once told Alfonso to clone branches the candidate had long left behind. Each
    founder-facing clone/checkout names the branch in greg/chromebook/REVIEW_BRANCH, and nothing else."""
    import re
    branch = (ROOT / "greg/chromebook/REVIEW_BRANCH").read_text().strip()
    assert re.fullmatch(r"[A-Za-z0-9._/-]+", branch)
    named = {rel: [b for block in install_commands(rel) for b in named_branches(block)]
             for rel in FOUNDER_INSTALL_SURFACES}
    assert all(named.values()), {rel: b for rel, b in named.items() if not b}
    stale = {rel: b for rel, b in named.items() if any(x != branch for x in b)}
    assert not stale, f"founder install surfaces that do not install {branch}: {stale}"


def test_no_founder_install_surface_escapes_the_review_branch_guard():
    """A new runbook that clones or checks out the kernel joins FOUNDER_INSTALL_SURFACES, or says why it is not one."""
    found = install_surfaces()
    assert set(FOUNDER_INSTALL_SURFACES) <= found, set(FOUNDER_INSTALL_SURFACES) - found
    assert found - set(FOUNDER_INSTALL_SURFACES) - set(NOT_FOUNDER_INSTALL) == set()


@pytest.mark.parametrize("block, expected", [
    ("git clone -b good https://github.com/dababiyoda/uniimente-kernel\n", ["good"]),
    ("git clone https://github.com/dababiyoda/uniimente-kernel && cd uniimente-kernel\ngit checkout good\n", ["good"]),
    ("git clone https://github.com/dababiyoda/uniimente-kernel && cd uniimente-kernel\n", [None]),
    ("git clone https://github.com/dababiyoda/uniimente-kernel\ngit clone -b good https://github.com/"
     "dababiyoda/uniimente-kernel\n", [None, "good"]),
    ("cd ~/src/uniimente-kernel\ngit switch stale   # comment\n", ["stale"]),
    ("git clone https://github.com/dababiyoda/DALEOBANKS\n", []),
])
def test_named_branches_reads_what_a_founder_would_install(block, expected):
    assert named_branches(block) == expected
