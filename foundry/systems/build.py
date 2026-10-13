"""#53 Owned, reproducible build of UNIIMENTE's critical source.

Builds a bundle of the owned critical packages (constitution compiler, contracts,
proof and provenance, the event spine, the gate, GREG and the Foundry including
its registry, discovery and promotion tooling) the way reproducible-builds.org
prescribes: sorted entries, fixed mtime (SOURCE_DATE_EPOCH), zeroed owners and
modes, gzip header without a timestamp, bytecode caches excluded. A toolchain
manifest pins the interpreter version and the exact versions of the third-party
packages the build and its tests depend on.

``build`` in two separate processes must produce byte-identical bundles;
``verify`` rebuilds and compares; ``smoke`` unpacks the bundle into an empty
directory and runs the Foundry status command from the unpacked copy, so the
bundle is shown to be self-sufficient for its owned layer.
"""
from __future__ import annotations

import gzip
import hashlib
import io
import json
import subprocess
import sys
import tarfile
from importlib import metadata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE_DATE_EPOCH = 1_788_000_000          # fixed; the build never reads the clock
DATA_DIRS = ("contracts", "organs", "constitution")   # non-package inputs the code loads at runtime


def owned(root: Path = ROOT) -> list[str]:
    """Every top-level Python package in the repository (the import closure) plus its data directories."""
    packages = sorted(p.name for p in root.iterdir() if p.is_dir() and (p / "__init__.py").exists()
                      and p.name not in ("tests",))
    return packages + [d for d in DATA_DIRS if (root / d).exists() and d not in packages]
PINNED = ("PyYAML", "jsonschema", "cryptography", "pytest")
EXCLUDE_PARTS = {"__pycache__", ".pytest_cache"}
EXCLUDE_SUFFIX = {".pyc", ".pyo"}


class BuildError(RuntimeError):
    pass


def toolchain() -> dict:
    versions = {}
    for name in PINNED:
        try:
            versions[name] = metadata.version(name)
        except metadata.PackageNotFoundError:
            versions[name] = None
    return {"python": ".".join(map(str, sys.version_info[:3])), "packages": versions,
            "source_date_epoch": SOURCE_DATE_EPOCH}


def _files(root: Path) -> list[Path]:
    out = []
    for top in owned(root):
        base = root / top
        if not base.exists():
            continue
        for p in base.rglob("*"):
            if p.is_file() and not (EXCLUDE_PARTS & set(p.parts)) and p.suffix not in EXCLUDE_SUFFIX \
                    and "evidence" not in p.relative_to(root).parts[1:2]:
                out.append(p)
    return sorted(out, key=lambda p: p.relative_to(root).as_posix())


def build(out_dir: Path, *, root: Path = ROOT) -> dict:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest = {"toolchain": toolchain(), "files": {}}
    raw = io.BytesIO()
    with tarfile.open(fileobj=raw, mode="w", format=tarfile.PAX_FORMAT) as tar:
        for p in _files(root):
            rel = p.relative_to(root).as_posix()
            data = p.read_bytes()
            manifest["files"][rel] = hashlib.sha256(data).hexdigest()
            info = tarfile.TarInfo(rel)
            info.size, info.mtime, info.mode = len(data), SOURCE_DATE_EPOCH, 0o644
            info.uid = info.gid = 0
            info.uname = info.gname = ""
            tar.addfile(info, io.BytesIO(data))
        body = json.dumps(manifest, sort_keys=True, indent=1).encode()
        info = tarfile.TarInfo("BUILD-MANIFEST.json")
        info.size, info.mtime, info.mode, info.uid, info.gid = len(body), SOURCE_DATE_EPOCH, 0o644, 0, 0
        tar.addfile(info, io.BytesIO(body))
    bundle = out_dir / "uniimente-owned.tar.gz"
    with open(bundle, "wb") as fh, gzip.GzipFile(filename="", mode="wb", fileobj=fh, mtime=0, compresslevel=9) as gz:
        gz.write(raw.getvalue())
    digest = hashlib.sha256(bundle.read_bytes()).hexdigest()
    return {"bundle": bundle.name, "sha256": digest, "files": len(manifest["files"]),
            "toolchain": manifest["toolchain"]}


def build_in_subprocess(out_dir: Path, *, root: Path = ROOT) -> dict:
    code = ("import json,sys; from pathlib import Path; from foundry.systems.build import build; "
            "print(json.dumps(build(Path(sys.argv[1]), root=Path(sys.argv[2]))))")
    proc = subprocess.run([sys.executable, "-s", "-c", code, str(out_dir), str(root)], cwd=ROOT,
                          capture_output=True, text=True, timeout=300)
    if proc.returncode != 0:
        raise BuildError(proc.stderr[-400:])
    return json.loads(proc.stdout)


def verify(bundle: Path, *, root: Path = ROOT, scratch: Path) -> dict:
    rebuilt = build_in_subprocess(Path(scratch), root=root)
    have = hashlib.sha256(Path(bundle).read_bytes()).hexdigest()
    return {"reproduced": rebuilt["sha256"] == have, "expected": have, "rebuilt": rebuilt["sha256"]}


def smoke(bundle: Path, target: Path) -> dict:
    target = Path(target)
    if target.exists() and any(target.iterdir()):
        raise BuildError("smoke target must be empty")
    target.mkdir(parents=True, exist_ok=True)
    with tarfile.open(bundle, "r:gz") as tar:
        tar.extractall(target, filter="data")
    proc = subprocess.run([sys.executable, "-s", "-c",
                           "from foundry.systems import SYSTEMS; import foundry.completion as c; "
                           "print(bool(SYSTEMS), len(c.contract()))"],
                          cwd=target, capture_output=True, text=True, timeout=120,
                          env={"PYTHONPATH": str(target), "PATH": "/usr/bin:/bin", "PYTHONDONTWRITEBYTECODE": "1"})
    return {"ran_from_bundle": proc.returncode == 0,
            "output": proc.stdout.strip() or proc.stderr[-300:].replace(str(target), "<bundle>")}


QUERY_OPS = {"toolchain": lambda a, r: toolchain()}
APPLY_OPS = {"build": lambda a, r: build(r),
             "verify": lambda a, r: verify(Path(r) / "uniimente-owned.tar.gz", scratch=Path(r) / "rebuild")}


def exercise(root) -> dict:
    root = Path(root)
    a = build_in_subprocess(root / "a")
    b = build_in_subprocess(root / "b")
    check = verify(root / "a" / "uniimente-owned.tar.gz", scratch=root / "c")
    ran = smoke(root / "a" / "uniimente-owned.tar.gz", root / "unpacked")
    # a single changed byte in owned source changes the bundle hash
    src = root / "mutated-src"
    for top in ("foundry",):
        import shutil
        shutil.copytree(ROOT / top, src / top, ignore=shutil.ignore_patterns("__pycache__"))
    (src / "foundry" / "systems" / "cas.py").write_text((src / "foundry" / "systems" / "cas.py").read_text() + "#\n")
    base = build(root / "d", root=_only(root / "only-foundry", "foundry"))
    mutated = build(root / "e", root=src)
    return {"identical_across_processes": a["sha256"] == b["sha256"], "files": a["files"] > 100,
            "verify": check["reproduced"], "smoke": ran,
            "one_byte_changes_hash": base["sha256"] != mutated["sha256"],
            "toolchain_pins": sorted(a["toolchain"]["packages"])}


def _only(dst: Path, top: str) -> Path:
    import shutil
    shutil.copytree(ROOT / top, dst / top, ignore=shutil.ignore_patterns("__pycache__"))
    return dst
