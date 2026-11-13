"""``brief.intake``: git reads nothing outside the read roots, and the kernel enforces it (re-check of c6e79087).

The round-3 re-check found twelve ways (E1-E12) in which the pin, which re-implemented in Python how git parses its
files and resolves paths, differed from git, and two false refusals the round introduced. Every git and tar process of
the rehearsal now runs in the worker envelope's Landlock backend (``intake._guard``): it reads only the read roots and
the host runtime and writes only the mission's scratch. The pin stays as the pre-check that says why a repository is
refused; it refuses wherever git and it could read a file two ways, and no longer refuses what git never reads.

Each test names the finding it covers and fails on c6e79087. A test that needs the kernel's confinement skips on a host
without Landlock, and fails there when GREG_REQUIRE_LANDLOCK=1 (CI). The pre-check tests come first: they start no git,
so the mutation gate (``scripts/ci/check_intake_mutants.py``) catches their mutants quickly. A test that could block on
a FIFO runs under a time guard, so a regression fails it instead of hanging the suite.
"""
from __future__ import annotations

import contextlib
import os
from pathlib import Path
import shutil
import subprocess
import sys
import threading

import pytest

from greg import intake, intake_rehearsal, workers
from greg.capabilities import BUILTINS, CapabilityError, InvocationContext
from tests.intake_fixtures import Script, branch, build_repo, git, landlock

SECRET = "tests/test_secret.py"


# -- building layouts ------------------------------------------------------------------------------------------------

def tiny(path: Path) -> Path:
    """A repository with one commit: enough for the pre-check, which starts no git."""
    path.mkdir(parents=True)
    git(path, "init", "-q")
    (path / "f").write_text("x\n")
    git(path, "add", ".")
    git(path, "commit", "-qm", "x")
    return path


def outside_store(tmp_path: Path) -> Path:
    return tiny(tmp_path / "outside" / "repo") / ".git" / "objects"


def world(tmp_path: Path) -> tuple[Path, dict]:
    """The fixture repository outside the read roots, with a commit only it holds (``secret``)."""
    outer = tmp_path / "outside" / "repo"
    shas = build_repo(outer)
    shas["secret"] = branch(outer, "secret", {SECRET: "def test_s():\n    assert True\n"})
    git(outer, "checkout", "-q", "base")
    (tmp_path / "roots").mkdir(exist_ok=True)
    return outer, shas


def pack(repo: Path) -> None:
    git(repo, "-c", "gc.auto=0", "repack", "-adq")
    git(repo, "prune-packed")


def deep(base: Path, length: int) -> Path:
    """A real directory under ``base`` whose path is exactly ``length`` characters long."""
    at = base
    at.mkdir(parents=True, exist_ok=True)
    while len(str(at)) + 1 + 250 + 1 + 10 <= length:
        at = at / ("d" * 250)
        os.mkdir(at)
    at = at / ("e" * (length - len(str(at)) - 1))
    os.mkdir(at)
    assert len(str(at)) == length
    return at


def link_in(directory: Path, target: Path, name: str) -> None:
    """A link named ``name`` in ``directory``, made relative to it: the full path may be longer than a path can be."""
    fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.symlink(target, name, dir_fd=fd)
    finally:
        os.close(fd)


def stale_atime(path: Path) -> float:
    """An atime older than the mtime, which the next read moves (relatime): a changed atime proves a read."""
    info = path.stat()
    os.utime(path, (info.st_mtime - 3600, info.st_mtime))
    return path.stat().st_atime


# -- running the pre-check and the capability -------------------------------------------------------------------------

def pinned(tmp_path: Path, where: Path) -> dict:
    return intake._pinned(where, (tmp_path / "roots",))


def context(tmp_path: Path, tag: str = "ctx", *, setting: str = "supervised") -> InvocationContext:
    return InvocationContext(workspace=tmp_path / tag / "workspace", read_roots=(tmp_path / "roots",), secrets=None,
                             manifest=BUILTINS["brief.intake"][0], deliver_root=tmp_path / tag / "out",
                             worker_confinement=setting, stop_check=None)


def recommend(tmp_path, where, shas, names, monkeypatch, tag="ctx", *, setting="supervised") -> dict:
    monkeypatch.setattr(workers, "run_tests", Script())
    params = {"repository": str(where), "base": shas["base"], "units": [{"name": n, "sha": shas[n]} for n in names]}
    return intake.intake_recommendation(params, context(tmp_path, tag, setting=setting))


def refused(tmp_path, where, shas, names, monkeypatch, tag="ctx", **kw) -> CapabilityError:
    with pytest.raises(CapabilityError) as caught:
        recommend(tmp_path, where, shas, names, monkeypatch, tag, **kw)
    briefs = tmp_path / tag / "out" / "briefs"
    assert not briefs.is_dir() or not list(briefs.iterdir())            # nothing was delivered
    return caught.value


def within(seconds: float, call):
    """``call()``'s result (or its exception), or a failure if it has not returned in ``seconds``: c6e79087 blocked for
    ever on a FIFO with no writer."""
    box: dict = {}

    def target():
        try:
            box["value"] = call()
        except BaseException as exc:                    # noqa: BLE001 - handed back to the test
            box["error"] = exc
    thread = threading.Thread(target=target, daemon=True)
    thread.start()
    thread.join(seconds)
    if thread.is_alive():
        pytest.fail(f"still running after {seconds}s: blocked")
    if "error" in box:
        raise box["error"]
    return box["value"]


@pytest.fixture
def fifos():
    """FIFOs a test makes; at its end each is opened for writing once, so a reader still blocked on it gets EOF."""
    made: list[Path] = []
    yield made
    for fifo in made:
        try:
            os.close(os.open(fifo, os.O_WRONLY | os.O_NONBLOCK))
        except OSError:
            pass                                        # no reader is blocked on it


def fifo(made: list, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    os.mkfifo(path)
    made.append(path)
    return path


# -- E1, E11: an alternates listing is read as git reads it, or refused --------------------------------------------

LISTINGS = {        # the listing's bytes, and the directory inside the store that git follows for them
    "a leading space": (b" sub\n", b" sub"),
    "a comment after a space": (b" #c\n", b" #c"),
    "a vertical tab": (b"a\x0bb\n", b"a\x0bb"),
    "bytes that are not UTF-8": (b"s\xff\n", b"s\xff"),
    "a carriage return": (b"s\r\n", b"s\r"),
    "a NUL byte": (b"a\x00b\n", b"a"),
}


@pytest.mark.parametrize("why", LISTINGS)
def test_e1_an_alternates_line_that_git_and_the_check_could_read_two_ways_is_refused(why, tmp_path):
    """E1, E11. git reads a listing whole, splits it on LF only and trims nothing; the pin stripped, split on any line
    break and replaced undecodable bytes, so it followed another path (or none) while git followed the directory the
    line names, whose own listing named a store outside the read roots: the secret commit was delivered. A NUL
    crashed the pin with ValueError. Each is refused now, by the rule that reads it."""
    store = outside_store(tmp_path)
    objects = tiny(tmp_path / "roots" / "repo") / ".git" / "objects"
    listing, name = LISTINGS[why]
    sub = os.path.join(os.fsencode(objects), name)
    os.makedirs(os.path.join(sub, b"info"))
    with open(os.path.join(sub, b"info", b"alternates"), "wb") as out:
        out.write(os.fsencode(store) + b"\n")
    (objects / "info" / "alternates").write_bytes(listing)
    with pytest.raises(CapabilityError, match="alternates listing"):
        pinned(tmp_path, tmp_path / "roots" / "repo")


def test_e1_a_listing_is_read_whole_never_cut_and_one_over_the_limit_is_refused(tmp_path):
    """E1. The pin read the first 65536 characters of a listing: a long comment hid the line after it, which named a
    store outside the read roots, and git read all of it."""
    store = outside_store(tmp_path)
    repo = tiny(tmp_path / "roots" / "repo")
    listing = repo / ".git" / "objects" / "info" / "alternates"
    listing.write_bytes(b"#" + b"x" * 70000 + b"\n" + os.fsencode(store) + b"\n")
    with pytest.raises(CapabilityError, match="alternate object store is outside the read roots"):
        pinned(tmp_path, repo)
    listing.write_bytes(b"#" + b"x" * (intake.MAX_LISTING_BYTES + 1) + b"\n")
    with pytest.raises(CapabilityError, match="longer than"):
        pinned(tmp_path, repo)


def test_a_store_whose_path_holds_a_space_inside_it_and_a_comment_are_read_as_git_reads_them(tmp_path):
    """The other side of E1: a space inside a path, a comment line and an empty line are what git reads them as."""
    roots = tmp_path / "roots"
    repo = tiny(roots / "repo")
    git(roots, "init", "-q", "--bare", "my store.git")
    (repo / ".git" / "objects" / "info" / "alternates").write_text(f"# shared\n\n{roots / 'my store.git' / 'objects'}\n")
    checked: dict = {}
    intake._pinned(repo, (roots,), checked)
    assert str((roots / "my store.git" / "objects").resolve()) in checked["stores"]


def test_a_git_directory_linked_from_elsewhere_inside_the_roots_is_followed(tmp_path):
    """The other side of the ``.git`` link refusal: ``repo/.git`` linked to a git directory elsewhere in the read roots
    is the one git reads, and is checked like any other."""
    roots = tmp_path / "roots"
    real = tiny(roots / "real")
    (roots / "repo").mkdir()
    os.symlink(real / ".git", roots / "repo" / ".git")
    checked: dict = {}
    intake._pinned(roots / "repo", (roots,), checked)
    assert checked["gitdir"] == str((real / ".git").resolve())


# -- E2, E11: commondir is read as git reads it, or refused --------------------------------------------------------

def worktree_git_directory(tmp_path: Path, content: bytes, name: bytes) -> Path:
    """A worktree whose git directory is in the read roots, with ``commondir`` holding ``content`` and the common
    directory git reads (the real directory ``name`` inside it) listing a store outside the read roots."""
    store = outside_store(tmp_path)
    gitdir = tmp_path / "roots" / "wtgit"
    gitdir.mkdir(parents=True)
    common = os.path.join(os.fsencode(gitdir), name)
    git(tmp_path / "roots", "init", "-q", "--bare", os.fsdecode(common))
    with open(os.path.join(common, b"objects", b"info", b"alternates"), "wb") as out:
        out.write(os.fsencode(store) + b"\n")
    (gitdir / "HEAD").write_text("0" * 40 + "\n")
    (gitdir / "commondir").write_bytes(content)
    tree = tmp_path / "roots" / "tree"
    tree.mkdir()
    (tree / ".git").write_text(f"gitdir: {gitdir}\n")
    return tree


@pytest.mark.parametrize("content,name", [(b" c\n", b" c"), (b"c \n", b"c "), (b"c\xff\n", b"c\xff"),
                                          (b"c\x00x\n", b"c")], ids=["leading space", "trailing space", "not UTF-8",
                                                                     "NUL"])
def test_e2_a_commondir_that_git_and_the_check_could_read_two_ways_is_refused(content, name, tmp_path):
    """E2, E11. git trims only trailing LFs and CRs from commondir; the pin stripped spaces too, followed a directory
    that did not exist, and git read the one the file names, whose store was outside the read roots. Bytes that are
    not UTF-8 crashed the rehearsal (UnicodeDecodeError), a NUL the pin (ValueError)."""
    tree = worktree_git_directory(tmp_path, content, name)
    with pytest.raises(CapabilityError, match="its commondir"):
        pinned(tmp_path, tree)


def test_a_commondir_ending_in_cr_lf_names_the_directory_git_reads(tmp_path):
    """The other side of E2: git trims every trailing CR and LF, and so does the pre-check."""
    roots = tmp_path / "roots"
    gitdir = roots / "wtgit"
    gitdir.mkdir(parents=True)
    git(roots, "init", "-q", "--bare", str(gitdir / "c"))
    (gitdir / "HEAD").write_text("0" * 40 + "\n")
    (gitdir / "commondir").write_bytes(b"c\r\n")
    (roots / "tree").mkdir()
    (roots / "tree" / ".git").write_text(f"gitdir: {gitdir}\n")
    checked: dict = {}
    intake._pinned(roots / "tree", (roots,), checked)
    assert checked["common"] == str((gitdir / "c").resolve())


# -- E3: a FIFO git would read is refused before any git runs -------------------------------------------------------

@pytest.mark.parametrize("where", ["objects/info/alternates", "commondir", "info/attributes", "config"])
def test_e3_a_fifo_git_would_read_is_refused_before_any_git_runs(where, tmp_path, fifos):
    """E3. The pin took a FIFO for no file (``is_file()`` is False); git read it, from whoever wrote it (a writer
    outside the read roots named the outside store there), or blocked on it for ever with no writer."""
    if where == "commondir":
        gitdir = tmp_path / "roots" / "wtgit"
        (gitdir / "objects").mkdir(parents=True)
        (gitdir / "HEAD").write_text("0" * 40 + "\n")
        fifo(fifos, gitdir / "commondir")
        repo = tmp_path / "roots" / "tree"
        repo.mkdir()
        (repo / ".git").write_text(f"gitdir: {gitdir}\n")
    else:
        repo = tiny(tmp_path / "roots" / "repo")
        (repo / ".git" / where).unlink(missing_ok=True)
        fifo(fifos, repo / ".git" / where)
    with pytest.raises(CapabilityError, match="FIFO"):
        pinned(tmp_path, repo)


# -- E4: a store or common directory inside a skipped hooks directory is listed by itself -------------------------

WATCHED: list[str] = []
OPENED: list[str] = []


def _audit(event, args):
    if event == "open" and WATCHED and args and isinstance(args[0], (str, bytes)):
        real = os.path.realpath(os.fsdecode(args[0]))
        if any(real == root or real.startswith(root + "/") for root in WATCHED):
            OPENED.append(real)


sys.addaudithook(_audit)


@contextlib.contextmanager
def watching(directory: Path):
    """Every file this process opens under ``directory`` while the block runs (an audit hook: GREG's own reads)."""
    WATCHED[:], OPENED[:] = [os.path.realpath(directory)], []
    try:
        yield OPENED
    finally:
        WATCHED[:] = []


def test_e4_a_store_or_common_directory_named_inside_hooks_is_listed_by_itself(tmp_path):
    """E4. The walk skipped ``.git/hooks`` and then counted everything under the listed git directory as listed: an
    alternate store ``../hooks/st`` whose packs link outside, or whose listing is a link to one outside (GREG's own
    process read it), and a worktree whose commondir is ``hooks/c.git`` were never looked at."""
    outer = tiny(tmp_path / "outside" / "repo")
    pack(outer)
    roots = tmp_path / "roots"
    repo = tiny(roots / "repo")
    store = repo / ".git" / "hooks" / "st"
    (store / "pack").mkdir(parents=True)
    for packed in (outer / ".git" / "objects" / "pack").iterdir():
        os.symlink(packed, store / "pack" / packed.name)
    (repo / ".git" / "objects" / "info" / "alternates").write_text("../hooks/st\n")
    with pytest.raises(CapabilityError, match="outside the read roots"):
        pinned(tmp_path, repo)
    shutil.rmtree(store / "pack")                     # a listing that is a link to one outside: never opened here
    (store / "info").mkdir()
    (tmp_path / "outside" / "alternates").write_text(f"{outer / '.git' / 'objects'}\n")
    os.symlink(tmp_path / "outside" / "alternates", store / "info" / "alternates")
    with watching(tmp_path / "outside") as opened:
        with pytest.raises(CapabilityError, match="outside the read roots"):
            pinned(tmp_path, repo)
    assert opened == []
    gitdir = roots / "wtgit"                          # a worktree whose repository is under its own hooks
    (gitdir / "hooks").mkdir(parents=True)
    git(roots, "init", "-q", "--bare", str(gitdir / "hooks" / "c.git"))
    for packed in (outer / ".git" / "objects" / "pack").iterdir():
        os.symlink(packed, gitdir / "hooks" / "c.git" / "objects" / "pack" / packed.name)
    (gitdir / "HEAD").write_text("0" * 40 + "\n")
    (gitdir / "commondir").write_text("hooks/c.git\n")
    (roots / "tree").mkdir()
    (roots / "tree" / ".git").write_text(f"gitdir: {gitdir}\n")
    with pytest.raises(CapabilityError, match="outside the read roots"):
        pinned(tmp_path, roots / "tree")


def test_a_listing_turned_outside_after_its_check_is_never_read_here(tmp_path, monkeypatch):
    """E4, E5: GREG's own process read a listing outside the read roots. A file read whole is opened only after its
    check, and where the opened file really is, is checked again before a byte is read: a directory link swapped in
    between (here: the check is made to hand back a path through one) is refused, not read."""
    roots = tmp_path / "roots"
    repo = tiny(roots / "repo")
    (tmp_path / "outside").mkdir()
    (tmp_path / "outside" / "alternates").write_text(f"{outside_store(tmp_path)}\n")
    os.symlink(tmp_path / "outside", roots / "hop")
    listing = str(repo / ".git" / "objects" / "info" / "alternates")
    real = intake._Pin.regular

    def swapped(self, path, what):
        found = real(self, path, what)
        return str(roots / "hop" / "alternates") if path == listing else found
    (repo / ".git" / "objects" / "info" / "alternates").write_text("")
    monkeypatch.setattr(intake._Pin, "regular", swapped)
    with pytest.raises(CapabilityError, match="an alternates listing is outside the read roots"):
        pinned(tmp_path, repo)


# -- the two false refusals of round 3, and one this round must not add ---------------------------------------------

def test_the_hooks_of_every_git_directory_are_skipped_and_a_dangling_hooks_link_refuses_nothing(tmp_path):
    """Re-check of c6e79087, false refusal 1. Hooks were skipped only at the top of the git directory, so a
    submodule's git directory whose hooks link outside the read roots (an ``init.templateDir`` of linked hooks) was
    refused, in ``.git/modules`` and in a worktree's ``modules``: git never reads a hook here. So was a ``.git/hooks``
    left dangling by a removed hook manager."""
    outside = tmp_path / "outside" / "templates"
    outside.mkdir(parents=True)
    (outside / "pre-commit").write_text("#!/bin/sh\n")
    repo = tiny(tmp_path / "roots" / "repo")
    for sub in (".git/modules/vendor/lib", ".git/worktrees/wt/modules/vendor/lib"):
        git(tmp_path / "roots", "init", "-q", "--bare", str(repo / sub))
        os.symlink(outside / "pre-commit", repo / sub / "hooks" / "pre-commit")
    shutil.rmtree(repo / ".git" / "hooks")
    os.symlink(tmp_path / "outside" / "removed-hook-manager", repo / ".git" / "hooks")
    pinned(tmp_path, repo)


def test_a_loop_of_links_git_never_resolves_refuses_nothing(tmp_path):
    """Not a refusal this round may add: a loop of links (``la -> lb -> la``) and a directory link to itself in the
    store. The kernel resolves a loop to nothing, so git reads nothing through it; c6e79087 delivered this, and a
    strict resolve that refused every error refused it ('Too many levels of symbolic links')."""
    repo = tiny(tmp_path / "roots" / "repo")
    objects = repo / ".git" / "objects"
    os.symlink(objects / "lb", objects / "la")
    os.symlink(objects / "la", objects / "lb")
    (objects / "dl").mkdir()
    os.symlink(objects / "dl", objects / "dl" / "self")
    checked: dict = {}
    intake._pinned(repo, (tmp_path / "roots",), checked)
    assert checked["stores"] == [str(objects.resolve())]


def test_real_directories_git_never_reads_are_not_counted_toward_the_cap(tmp_path, monkeypatch):
    """Re-check of c6e79087, false refusal 2. The cap counted real directories, so a git-annex or git-lfs store with
    more than 65536 directories was refused: real directories cannot loop. (Here the cap is 50 and there are 60.)"""
    monkeypatch.setattr(intake, "MAX_LISTED_DIRECTORIES", 50)
    repo = tiny(tmp_path / "roots" / "repo")
    for index in range(60):
        (repo / ".git" / "annex" / "objects" / f"k{index}").mkdir(parents=True)
    pinned(tmp_path, repo)


def test_e9_every_visit_through_a_link_counts_toward_the_cap_a_revisit_too(tmp_path, monkeypatch):
    """E9. A revisit through a link was listed and deduplicated afterwards, and never counted: N links to one
    directory of N files cost N squared and the cap never refused (38 s at N = 10000)."""
    monkeypatch.setattr(intake, "MAX_LISTED_DIRECTORIES", 100)
    repo = tiny(tmp_path / "roots" / "repo")
    big = repo / ".git" / "objects" / "big"
    big.mkdir()
    for index in range(10):
        (big / f"f{index}").touch()
    (repo / ".git" / "objects" / "links").mkdir()
    for index in range(150):
        os.symlink(big, repo / ".git" / "objects" / "links" / f"l{index}")
    with pytest.raises(CapabilityError, match="more than 100 directory links"):
        pinned(tmp_path, repo)


# -- E5: a path this process cannot resolve as the kernel does is refused --------------------------------------------

@pytest.mark.parametrize("what", ["pack", "info"])
def test_e5_a_path_this_process_cannot_resolve_as_the_kernel_does_is_refused(what, tmp_path):
    """E5. ``Path.resolve()`` ignores an error part-way: where the resolved path passes PATH_MAX, a link was taken for
    a plain file inside the read roots. ``objects/pack`` linked to a 4060-character directory whose packs link outside,
    or ``objects/info`` linked to one whose alternates is a link to a listing outside (GREG's process read it)."""
    outer = tiny(tmp_path / "outside" / "repo")
    repo = tiny(tmp_path / "roots" / "repo")
    if what == "pack":
        pack(outer)
        far = deep(tmp_path / "roots" / "deep", 4060)
        for packed in (outer / ".git" / "objects" / "pack").iterdir():
            link_in(far, packed, packed.name)
    else:                       # the listing names a store inside the roots: only the listing itself is outside
        shutil.copytree(outer / ".git" / "objects", tmp_path / "roots" / "store")
        (tmp_path / "outside" / "alternates").write_text(f"{tmp_path / 'roots' / 'store'}\n")
        far = deep(tmp_path / "roots" / "deep", 4088)
        link_in(far, tmp_path / "outside" / "alternates", "alternates")
    shutil.rmtree(repo / ".git" / "objects" / what)
    os.symlink(far, repo / ".git" / "objects" / what)
    with watching(tmp_path / "outside") as opened:
        with pytest.raises(CapabilityError, match="cannot be resolved here|cannot be listed"):
            pinned(tmp_path, repo)
    assert opened == []


# -- E10: a name too long to look up is a refusal naming the path, never a transient fault -------------------------

def test_e10_a_name_too_long_to_look_up_is_a_refusal_never_a_transient_fault(tmp_path, monkeypatch):
    """E10. ``Path.is_symlink()`` re-raised ENAMETOOLONG out of the walk, and the capability turned the OSError into a
    *transient* refusal, which invites a retry of a request that can never succeed."""
    _, shas = world(tmp_path)
    repo = tmp_path / "roots" / "repo"
    shutil.copytree(tmp_path / "outside" / "repo", repo, symlinks=True)
    far = deep(repo / ".git" / "objects" / "zz", 4060)
    fd = os.open(far, os.O_RDONLY | os.O_DIRECTORY)            # a directory whose full path is longer than a lookup takes
    try:
        os.mkdir("x" * 60, dir_fd=fd)
    finally:
        os.close(fd)
    exc = refused(tmp_path, repo, shas, ["label"], monkeypatch)
    assert getattr(exc, "failure_class", None) != "transient", exc
    assert "too long" in str(exc).lower(), exc


# -- the guard: what every git and tar process of the rehearsal may do ---------------------------------------------

PROBE = """
import os, socket, sys
def attempt(call):
    try:
        call()
        return "allowed"
    except OSError as exc:
        return "denied" if exc.errno in (1, 13) else f"error {exc.errno}"
inside, outside, scratch = sys.argv[1:4]
print(attempt(lambda: open(inside).read()), attempt(lambda: open(outside).read()),
      attempt(lambda: open(os.path.join(scratch, "w"), "w").write("x")),
      attempt(lambda: open(inside + ".w", "w").write("x")), attempt(lambda: socket.socket().close()))
"""


def test_the_guard_reads_the_roots_writes_only_scratch_and_opens_no_socket(tmp_path):
    """The kernel's part: under the guard a process reads inside the read roots and not outside them, writes only in
    the mission's scratch, and cannot open a socket. c6e79087 had no guard: git read and wrote with GREG's reach."""
    landlock()
    (tmp_path / "roots").mkdir()
    (tmp_path / "outside").mkdir()
    inside, outside = tmp_path / "roots" / "f", tmp_path / "outside" / "f"
    inside.write_text("in")
    outside.write_text("out")
    scratch = tmp_path / "ctx" / "workspace" / "intake-scratch"
    scratch.mkdir(parents=True)
    guard, said = intake._guard(tmp_path / "roots", scratch, context(tmp_path))
    assert guard.confined and said.startswith("Landlock ABI ") and "network denied" in said
    probe = tmp_path / "probe.py"
    probe.write_text(PROBE)
    shutil.copy(probe, scratch / "probe.py")           # the interpreter reads its script: put it where it may
    out = subprocess.run([sys.executable, "-I", str(scratch / "probe.py"), str(inside), str(outside), str(scratch)],
                         capture_output=True, text=True, preexec_fn=guard.preexec, cwd=scratch)
    assert out.stdout.split() == ["allowed", "denied", "allowed", "denied", "denied"], out.stderr[-600:]


def test_without_landlock_required_refuses_and_supervised_runs_git_unconfined_and_says_so(tmp_path, monkeypatch):
    """The posture is the body's worker confinement, as for the heads' tests: on a host without Landlock, ``required``
    refuses before anything reads the repository; ``supervised`` runs git unconfined and the recommendation says so
    (c6e79087 ran git unconfined on every host and said nothing)."""
    from greg import worker_isolation
    _, shas = world(tmp_path)
    repo = tmp_path / "roots" / "repo"
    shutil.copytree(tmp_path / "outside" / "repo", repo, symlinks=True)

    def unavailable():
        raise worker_isolation.WorkerIsolationError("Landlock ABI >= 3 unavailable: (test)")
    monkeypatch.setattr(worker_isolation, "_landlock_abi", unavailable)
    exc = refused(tmp_path, repo, shas, ["label"], monkeypatch, "required", setting="required")
    assert "cannot be confined on this host" in str(exc) and "'required'" in str(exc)
    assert not (tmp_path / "required" / "workspace" / "intake-scratch" / "objects").exists()   # no git ran
    out = recommend(tmp_path, repo, shas, ["label"], monkeypatch, "supervised")
    assert out["recommendations"] == {"label": "ready to take"}
    said = out["inputs"]["confinement"]["git"]
    assert said.startswith("supervised: NOT confined by the kernel (Landlock ABI >= 3 unavailable: (test))")
    assert said in Path(out["path"]).read_text()


def test_a_confinement_that_cannot_be_installed_refuses_and_nothing_runs_unconfined(tmp_path, monkeypatch):
    """Where the kernel refuses to install the ruleset for one git process (a seccomp or Landlock call failing in the
    child), that process never runs, and the request is refused, naming the repository, never as a fault to retry."""
    landlock()
    from greg import worker_isolation
    _, shas = world(tmp_path)
    repo = tmp_path / "roots" / "repo"
    shutil.copytree(tmp_path / "outside" / "repo", repo, symlinks=True)

    def failing(read, write):
        raise OSError(1, "Landlock restrict_self failed")
    monkeypatch.setattr(worker_isolation, "_install_landlock", failing)
    exc = refused(tmp_path, repo, shas, ["label"], monkeypatch)
    assert "could not be started inside the rehearsal's confinement" in str(exc) and str(repo) in str(exc), exc
    assert getattr(exc, "failure_class", None) != "transient"


def test_e11_a_name_that_is_not_utf8_never_crashes_the_rehearsal_whatever_core_quotepath_says(tmp_path, monkeypatch):
    """E11, the same class: the rehearsal reads the file names git prints as git's default listing, quoted where a
    byte is unusual. A repository that set ``core.quotePath=false`` made a head's test file whose name is not UTF-8
    crash it (UnicodeDecodeError). The rehearsal's own configuration sets it back; the file is reported as not run."""
    roots = tmp_path / "roots"
    shas = build_repo(roots / "repo")
    repo = roots / "repo"
    git(repo, "checkout", "-q", "-b", "odd", shas["base"])
    with open(os.path.join(os.fsencode(repo), b"tests", b"test_\xff.py"), "w") as out:
        out.write("def test_x():\n    assert True\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "odd")
    shas["odd"] = git(repo, "rev-parse", "HEAD")
    git(repo, "checkout", "-q", "base")
    git(repo, "config", "core.quotePath", "false")
    out = recommend(tmp_path, repo, shas, ["odd"], monkeypatch)
    assert out["inputs"]["skipped_tests"]["odd"] == [{"file": "tests/test_�.py",
                                                      "why": "git quotes this file name, so the rehearsal does not "
                                                             "run it"}]


def test_a_confined_recommendation_says_how_git_ran_and_what_a_hard_link_still_reads(tmp_path, monkeypatch):
    """E12 (hard links): a file hard-linked into the repository from outside the read roots is inside them by every
    path git uses, so the kernel lets git read it, as ``git clone --local`` relies on. That limit is said in every
    recommendation, beside how its git ran."""
    landlock()
    _, shas = world(tmp_path)
    repo = tmp_path / "roots" / "repo"
    shutil.copytree(tmp_path / "outside" / "repo", repo, symlinks=True)
    out = recommend(tmp_path, repo, shas, ["label"], monkeypatch)
    text = Path(out["path"]).read_text()
    assert out["inputs"]["confinement"]["git"].startswith("Landlock ABI ")
    assert "- the rehearsal's git and tar ran under: Landlock ABI " in text
    assert "a file the repository hard-links from outside the read roots is read like its own" in text


# -- the kernel refuses what a pre-check misses ------------------------------------------------------------------------

def permissive(repo, roots, checked=None):
    """A pre-check that checks nothing: what the kernel alone must refuse."""
    gitdir = str((Path(repo) / ".git").resolve())
    if checked is not None:
        checked.update(gitdir=gitdir, common=gitdir, stores=[str(Path(gitdir, "objects"))])
    return {"GIT_DIR": gitdir, "GIT_CEILING_DIRECTORIES": str(Path(repo).parent)}


@pytest.mark.parametrize("how", ["linked pack files", "linked loose object directories", "a linked info/attributes"])
def test_the_kernel_refuses_what_the_pre_check_missed(how, tmp_path, monkeypatch):
    """The guarantee is the kernel's, not the pre-check's (the re-check's recommendation): with a pre-check that checks
    nothing, git is still refused every file outside the read roots, and the request is refused, naming the
    repository, never delivered from what git could not read. On c6e79087 the same pre-check let git read the outside
    objects and the secret commit was recommended. A refused ``info/attributes`` is a refusal, not silence: git warns
    and goes on without it."""
    landlock()
    outer, shas = world(tmp_path)
    repo = tmp_path / "roots" / "repo"
    if how == "a linked info/attributes":
        shutil.copytree(outer, repo, symlinks=True)
        (tmp_path / "outside" / "attrs").write_text("tests/** export-ignore\n")
        (repo / ".git" / "info").mkdir(exist_ok=True)
        os.symlink(tmp_path / "outside" / "attrs", repo / ".git" / "info" / "attributes")
        names = ["label"]
    else:
        repo.mkdir(parents=True)
        git(repo, "init", "-q")
        objects = repo / ".git" / "objects"
        if how == "linked pack files":
            pack(outer)
            for packed in (outer / ".git" / "objects" / "pack").iterdir():
                os.symlink(packed, objects / "pack" / packed.name)
        else:
            for sub in (outer / ".git" / "objects").iterdir():
                if len(sub.name) == 2:
                    os.symlink(sub, objects / sub.name)
        names = ["secret"]
    monkeypatch.setattr(intake, "_pinned", permissive)
    exc = refused(tmp_path, repo, shas, names, monkeypatch)
    assert str(repo) in str(exc) and getattr(exc, "failure_class", None) != "transient", exc


def test_git_s_own_word_on_what_it_reads_must_match_what_was_checked(tmp_path, monkeypatch):
    """E1, E2 as a class: whatever makes the pre-check read a listing differently from git, git itself says which
    stores it reads (``count-objects -v``) and which repository (``rev-parse``), and a store the pre-check did not
    follow is refused by name. Here the pre-check is made to read no alternates at all."""
    landlock()
    roots = tmp_path / "roots"
    shas = build_repo(roots / "packed")
    git(roots, "clone", "-q", "--shared", str(roots / "packed"), str(roots / "shared"))
    monkeypatch.setattr(intake, "_alternates", lambda data, where: [])
    exc = refused(tmp_path, roots / "shared", shas, ["label"], monkeypatch)
    assert "git reads an object store this check did not follow" in str(exc)
    assert str((roots / "packed" / ".git" / "objects").resolve()) in str(exc)


def test_a_repository_whose_path_holds_a_colon_is_read(tmp_path, monkeypatch):
    """git splits ``GIT_ALTERNATE_OBJECT_DIRECTORIES`` at ':': the repository's own store, listed there for the
    scratch objects, was cut in two, and every revision read as missing. It is quoted now."""
    shas = build_repo(tmp_path / "roots" / "a:b" / "repo")
    out = recommend(tmp_path, tmp_path / "roots" / "a:b" / "repo", shas, ["label"], monkeypatch)
    assert out["recommendations"] == {"label": "ready to take"}


# -- E6, E7: no work-tree attributes, no system attributes -----------------------------------------------------------

def two_heads_one_file(roots: Path) -> tuple[Path, dict]:
    """Heads ``one`` and ``two`` change ``sub/data.txt`` in separate hunks: they merge cleanly unless an attribute
    says ``-merge``."""
    repo = roots / "repo"
    repo.mkdir(parents=True)
    git(repo, "init", "-q", "-b", "trunk")
    (repo / "sub").mkdir()
    (repo / "sub" / "data.txt").write_text("".join(f"line {i}\n" for i in range(40)))
    git(repo, "add", ".")
    git(repo, "commit", "-qm", "base")
    git(repo, "checkout", "-q", "-b", "base")
    shas = {"base": git(repo, "rev-parse", "HEAD")}
    lines = (repo / "sub" / "data.txt").read_text().splitlines(True)
    shas["one"] = branch(repo, "one", {"sub/data.txt": "".join(["ONE\n"] + lines[1:]),
                                       "tests/test_one.py": "def test_one():\n    assert True\n"})
    shas["two"] = branch(repo, "two", {"sub/data.txt": "".join(lines[:-1] + ["TWO\n"]),
                                       "tests/test_two.py": "def test_two():\n    assert True\n"})
    git(repo, "checkout", "-q", "base")
    return repo, shas


def test_e6_merge_tree_reads_no_attributes_from_the_repositorys_checkout(tmp_path, monkeypatch):
    """E6. ``merge-tree`` read ``.gitattributes`` in the repository's checkout, through a directory link a head can
    commit: ``sub`` linked to a directory outside saying ``* -merge`` turned a clean merge into a conflict, and the
    outside file was read. The rehearsal's git runs in an empty working tree now."""
    repo, shas = two_heads_one_file(tmp_path / "roots")
    attrs = tmp_path / "outside" / "attrdir"
    attrs.mkdir(parents=True)
    (attrs / ".gitattributes").write_text("* -merge\n")
    shutil.rmtree(repo / "sub")
    os.symlink(attrs, repo / "sub")
    before = stale_atime(attrs / ".gitattributes")
    out = recommend(tmp_path, repo, shas, ["one", "two"], monkeypatch)
    assert out["recommendations"] == {"one": "ready to take", "two": "ready to take"}
    assert (attrs / ".gitattributes").stat().st_atime == before


def test_e6_a_configured_working_tree_is_never_where_git_reads_attributes(tmp_path, monkeypatch):
    """E6, the configured form: ``core.worktree`` naming a directory above the rehearsal's scratch made git move there
    and read ``sub/.gitattributes`` from it (outside the read roots). The rehearsal's working tree is its own empty
    directory (``GIT_WORK_TREE``), so the repository's ``core.worktree`` is never read, and no longer refused."""
    repo, shas = two_heads_one_file(tmp_path / "roots")
    above = tmp_path / "ctx"                       # the mission's workspace is tmp_path/ctx/workspace
    (above / "sub").mkdir(parents=True)
    (above / "sub" / ".gitattributes").write_text("* -merge\n")
    git(repo, "config", "core.worktree", str(above))
    before = stale_atime(above / "sub" / ".gitattributes")
    out = recommend(tmp_path, repo, shas, ["one", "two"], monkeypatch)
    assert out["recommendations"] == {"one": "ready to take", "two": "ready to take"}
    assert (above / "sub" / ".gitattributes").stat().st_atime == before


def test_e7_the_rehearsals_git_reads_no_system_attributes(tmp_path):
    """E7. ``GIT_CONFIG_NOSYSTEM`` does not cover ``/etc/gitattributes``: host configuration (an ``export-ignore``
    there emptied the exported trees). git itself says it reads none now."""
    repo = tiny(tmp_path / "roots" / "repo")
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    env = intake._git_environment(repo, scratch, (tmp_path / "roots",))
    said = subprocess.run(["git", "var", "GIT_ATTR_SYSTEM"], cwd=repo, env=env, capture_output=True)
    assert said.stdout == b"", said.stdout


# -- E12: a link turned outside after the check is refused by the kernel --------------------------------------------

def test_e12_a_link_turned_outside_after_the_check_is_refused_by_the_kernel(tmp_path, monkeypatch):
    """E12. Pack links that pass through a link outside the read roots point inside when the pre-check looks and are
    turned to the outside packs just after (here: when the scratch objects are set up, after the check and before git
    reads an object). Nothing done before git runs can close that; the kernel does, since it confines every read git
    makes. The chain itself, inside -> outside link -> inside, is read (its last hop is inside)."""
    landlock()
    outer, shas = world(tmp_path)
    pack(outer)
    repo = tmp_path / "roots" / "repo"
    repo.mkdir(parents=True)
    git(repo, "init", "-q")
    decoy = tmp_path / "roots" / "decoy"
    decoy.mkdir()
    hops = []
    for packed in (outer / ".git" / "objects" / "pack").iterdir():
        (decoy / packed.name).write_bytes(b"")
        hop = tmp_path / "outside" / f"hop-{packed.name}"
        os.symlink(decoy / packed.name, hop)
        os.symlink(hop, repo / ".git" / "objects" / "pack" / packed.name)
        hops.append((hop, packed))
    real = intake_rehearsal.scratch_objects

    def turn(*args, **kw):
        for hop, packed in hops:
            hop.unlink()
            os.symlink(packed, hop)
        return real(*args, **kw)
    monkeypatch.setattr(intake_rehearsal, "scratch_objects", turn)
    exc = refused(tmp_path, repo, shas, ["secret"], monkeypatch)
    assert "outside the read roots" in str(exc), exc


# -- E3, E8: what blocks is refused within a time limit; an include is never read ---------------------------------

def test_e3_a_git_that_blocks_is_refused_at_its_time_limit(tmp_path, monkeypatch, fifos):
    """E3. ``rehearsal.git`` had no time limit: a FIFO git read with no writer hung the request for ever. Every git
    and tar process has one now. (Here the pre-check is made to miss the FIFO, and the limit is 3 s.)"""
    _, shas = world(tmp_path)
    repo = tmp_path / "roots" / "repo"
    shutil.copytree(tmp_path / "outside" / "repo", repo, symlinks=True)
    (repo / ".git" / "info").mkdir(exist_ok=True)
    fifo(fifos, repo / ".git" / "info" / "attributes")
    monkeypatch.setattr(intake, "GIT_TIMEOUT", 3)
    monkeypatch.setattr(intake._Pin, "special", lambda self, path, mode, what: None)
    exc = within(30, lambda: refused(tmp_path, repo, shas, ["label"], monkeypatch))
    assert "did not finish within 3s" in str(exc) and str(repo) in str(exc), exc


def test_e3_a_file_the_configuration_names_must_be_a_regular_file(tmp_path, monkeypatch, fifos):
    """E3. ``core.attributesFile`` naming a FIFO inside the read roots: the pin checked only where it was, and git
    blocked on it for ever. Refused before git opens it."""
    _, shas = world(tmp_path)
    repo = tmp_path / "roots" / "repo"
    shutil.copytree(tmp_path / "outside" / "repo", repo, symlinks=True)
    git(repo, "config", "core.attributesFile", str(fifo(fifos, tmp_path / "roots" / "attrs")))
    monkeypatch.setattr(intake, "GIT_TIMEOUT", 3)          # were it opened, the refusal would be the time limit's
    exc = within(60, lambda: refused(tmp_path, repo, shas, ["label"], monkeypatch))
    assert "core.attributesFile" in str(exc) and "not a regular file" in str(exc), exc


def test_e8_an_include_is_never_read_and_one_that_blocks_never_hangs(tmp_path, monkeypatch, fifos):
    """E8. The first ``git config`` call read an include before the include check refused it, and an include that was
    a FIFO hung the request. Confined, git is refused the file: it is never read, and the request is refused at once."""
    landlock()
    _, shas = world(tmp_path)
    repo = tmp_path / "roots" / "repo"
    shutil.copytree(tmp_path / "outside" / "repo", repo, symlinks=True)
    included = tmp_path / "outside" / "included"
    included.write_text("[core]\n\tbare = false\n")
    git(repo, "config", "include.path", str(included))
    before = stale_atime(included)
    exc = refused(tmp_path, repo, shas, ["label"], monkeypatch)
    assert "include" in str(exc) and included.stat().st_atime == before, exc
    git(repo, "config", "include.path", str(fifo(fifos, tmp_path / "outside" / "included-fifo")))
    within(60, lambda: refused(tmp_path, repo, shas, ["label"], monkeypatch, "fifo"))
