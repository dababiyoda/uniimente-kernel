"""Uncleared third-party data stays out of every release (review of #179, M19)."""
import importlib.util
import json
import subprocess
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("check_release_exclusions", ROOT / "scripts/check_release_exclusions.py")
C = importlib.util.module_from_spec(spec)
spec.loader.exec_module(C)
LIST = json.loads((ROOT / "docs/collaboration/RELEASE-EXCLUSIONS.json").read_text())


def test_every_listed_path_is_tracked_frozen_evidence_and_every_source_is_uncleared():
    tracked = set(subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True).stdout.split())
    assert {e["path"] for e in LIST["paths"]} <= tracked
    assert {e["source"] for e in LIST["paths"]} == set(LIST["sources"])
    assert all(s["status"].startswith("uncleared") for s in LIST["sources"].values())


def test_no_unlisted_tracked_file_carries_a_marker_of_listed_data():
    """A new suite, result or log built from an uncleared source must join the list."""
    listed = {e["path"] for e in LIST["paths"]}
    ignore = ("docs/collaboration/", "docs/evidence/greg-mind-evidence-index.json", "tests/")
    found = set()
    for markers in LIST["markers"].values():
        for marker in markers:
            out = subprocess.run(["git", "grep", "-lF", marker, "--", "*.json", "*.log", "*.jsonl"], cwd=ROOT,
                                 capture_output=True, text=True).stdout.split()
            found |= {p for p in out if not p.startswith(ignore)}
    assert found - listed == set(), sorted(found - listed)


def test_the_package_ships_none_and_an_archive_that_carries_one_is_blocked(tmp_path):
    assert C.check(C.packaged()) == [] and C.main([]) == 0
    path = LIST["paths"][0]["path"]
    archive = tmp_path / "release.tar"
    with tarfile.open(archive, "w") as t:
        t.add(ROOT / path, arcname=f"release/{path}")
    assert any(f.startswith(f"release/{path}: ") for f in C.scan_archive(archive))
    assert C.main(["--archive", str(archive)]) == 1


def test_every_listed_file_carries_its_current_digest():
    import hashlib
    for entry in LIST["paths"]:
        assert entry["sha256"] == "sha256:" + hashlib.sha256((ROOT / entry["path"]).read_bytes()).hexdigest(), entry


def _excluded():
    entry = next(e for e in LIST["paths"] if e["path"].endswith(".json") and not e["path"].endswith(".json.gz"))
    return entry["path"], (ROOT / entry["path"]).read_bytes()


def _tar(path, members, mode="w"):
    with tarfile.open(path, mode) as t:
        for name, data in members:
            import io
            info = tarfile.TarInfo(name)
            info.size = len(data)
            t.addfile(info, io.BytesIO(data))


def test_renamed_nested_deep_and_wheel_copies_are_blocked(tmp_path):
    """Round-2 review of #179 (N3): exact-path matching let a renamed member, a nested .tar.gz, a two-level prefix and
    a wheel through. Digest, path-suffix and marker rules now apply at every depth."""
    import zipfile
    path, data = _excluded()
    renamed = tmp_path / "renamed.tar"
    _tar(renamed, [("release/notes/benign-name.bin", data)])
    inner = tmp_path / "inner.tar.gz"
    _tar(inner, [(path, data)], mode="w:gz")
    nested = tmp_path / "nested.tar"
    _tar(nested, [("bundle/inner.tar.gz", inner.read_bytes())])
    deep = tmp_path / "deep.tar"
    _tar(deep, [(f"a/b/{path}", data)])
    wheel = tmp_path / "pkg-0.1-py3-none-any.whl"
    with zipfile.ZipFile(wheel, "w") as z:
        z.writestr(f"pkg/data/{Path(path).name}", data)
    for archive in (renamed, nested, deep, wheel):
        assert C.scan_archive(archive), archive.name
        assert C.main(["--archive", str(archive)]) == 1, archive.name


def test_a_reformatted_copy_is_blocked_by_its_data_markers(tmp_path):
    """A re-serialised extract has a new digest and a new name; the listed data markers still catch it."""
    import zipfile
    path, data = _excluded()
    reformatted = json.dumps(json.loads(data), indent=4).encode()
    archive = tmp_path / "r.zip"
    with zipfile.ZipFile(archive, "w") as z:
        z.writestr("x/y/results.json", reformatted)
    assert any("data markers" in f for f in C.scan_archive(archive))


def test_a_clean_archive_passes(tmp_path):
    archive = tmp_path / "clean.tar.gz"
    _tar(archive, [("pkg/module.py", b"print('ok')\n"), ("pkg/data.json", b'{"a": 1}')], mode="w:gz")
    assert C.scan_archive(archive) == [] and C.main(["--archive", str(archive)]) == 0


def test_recompressed_and_minified_copies_are_blocked(tmp_path):
    """Round-3 review of #179 (finding 3): an xz- or bz2-compressed listed file and minified JSON under a .dat
    extension passed. Members are decompressed (gzip, xz, bz2) and JSON is compared in canonical form."""
    import bz2
    import lzma
    path, data = _excluded()
    gz = next(e["path"] for e in LIST["paths"] if e["path"].endswith(".json.gz"))
    raw = (ROOT / gz).read_bytes()
    import gzip
    extract = gzip.decompress(raw)
    members = [("a/data.xz", lzma.compress(data)), ("b/data.bz2", bz2.compress(data)),
               ("c/extract.bin.xz", lzma.compress(extract)),
               ("d/blob.dat", json.dumps(json.loads(data), separators=(",", ":")).encode())]
    for name, content in members:
        archive = tmp_path / (name.replace("/", "_") + ".tar")
        _tar(archive, [(name, content)])
        assert C.scan_archive(archive), name
        assert C.main(["--archive", str(archive)]) == 1, name


def test_the_check_states_what_it_cannot_catch():
    assert "Out of scope" in (ROOT / "scripts/check_release_exclusions.py").read_text()


def test_lzma_alone_zlib_base64_and_utf16_copies_are_blocked(tmp_path):
    """Round-4 review of #179 (finding C): these four encodings of a listed file passed."""
    import base64
    import lzma
    import zlib
    path, data = _excluded()
    encodings = {"alone.lzma": lzma.compress(data, format=lzma.FORMAT_ALONE), "z.zlib": zlib.compress(data),
                 "b64.txt": base64.b64encode(data), "u16.txt": data.decode("utf-8").encode("utf-16")}
    for name, content in encodings.items():
        archive = tmp_path / f"{name}.tar"
        _tar(archive, [(f"x/{name}", content)])
        assert C.scan_archive(archive), name


def test_python_source_alone_never_blocks_a_release(tmp_path):
    """Round-4 review of #179 (finding D): the marker scan flagged ordinary source naming the suites, so a tag
    archive without any listed data file was still blocked. Python source is exempt from the marker rule."""
    tracked = subprocess.run(["git", "ls-files", "*.py"], cwd=ROOT, capture_output=True, text=True).stdout.split()
    archive = tmp_path / "source.tar"
    with tarfile.open(archive, "w") as t:
        for rel in tracked:
            t.add(ROOT / rel, arcname=f"release/{rel}")
    assert C.scan_archive(archive) == []



def test_an_edited_data_copy_named_like_python_source_is_blocked(tmp_path):
    """Round-5 review of #179 (N1): the ``.py`` exemption let an edited copy of listed data through, and parsing
    as Python is no test, because JSON parses as Python. Only tracked source, byte for byte, is exempt."""
    data = json.loads((ROOT / "cortex/evaluation/composition_lift/suite-v4.json").read_text())
    data["extra"] = 1
    edited = json.dumps(data).encode()
    for name in ("x.py", "x.txt", "x.json"):
        _tar(tmp_path / f"{name}.tar", [(name, edited)])
        assert C.scan_archive(tmp_path / f"{name}.tar"), name
    source = "cortex/evaluation/composition_lift/run_v2.py"
    _tar(tmp_path / "src.tar", [(source, (ROOT / source).read_bytes())])
    assert C.scan_archive(tmp_path / "src.tar") == []


def test_a_release_of_every_unlisted_tracked_file_passes(tmp_path):
    """Round-5 review of #179 (N2): the exclusion list carries the markers it scans for, so a data-free tag archive
    was still blocked. The list itself, byte for byte, is exempt from the marker rule."""
    listed = {e["path"] for e in LIST["paths"]}
    tracked = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT, capture_output=True).stdout.decode().split("\0")
    members = [(p, (ROOT / p).read_bytes()) for p in tracked if p and p not in listed and (ROOT / p).is_file()]
    _tar(tmp_path / "tag.tar", members)
    assert C.scan_archive(tmp_path / "tag.tar") == []
    edited = (ROOT / "docs/collaboration/RELEASE-EXCLUSIONS.json").read_bytes() + b" "
    _tar(tmp_path / "list.tar", [("RELEASE-EXCLUSIONS.json", edited)])
    assert C.scan_archive(tmp_path / "list.tar")                         # only the exact list is exempt
