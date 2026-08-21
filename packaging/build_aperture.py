#!/usr/bin/env python3
"""Build the two Reality Aperture distributions and inspect what actually ships.

PACKAGE GEOMETRY: two distributions, not one.

  uniimente-aperture-client   contracts, certificate parsing and verification,
                              revocation verification, receipts, local veto,
                              request construction, the canonical manifest
  uniimente-aperture-issuer   the canonical issuer, the signing provider, the
                              revocation authority

Rejected geometries and why:

  ONE PACKAGE WITH INTERNAL BOUNDARIES - rejected. Internal boundaries are
  conventions. The issuer bytes would sit in DALEOBANKS' site-packages, one
  import away, enforced only by a check someone can delete.

  ONE CORE WITH AUTHORITY AS AN OPTIONAL EXTRA - rejected, and this is the
  subtle one. Extras add DEPENDENCIES, not modules. `pip install pkg` and
  `pip install pkg[issuer]` install the SAME files; the extra only pulls extra
  third-party deps. The issuer module would ship to every organ regardless.
  An extra cannot express "these bytes are not for you".

  SCHEMAS PLUS REPOSITORY-LOCAL IMPLEMENTATIONS - rejected. Every organ
  reimplementing verification is every organ having its own subtly different
  idea of what a valid certificate is. That is a second government arriving by
  divergence rather than by design.

Two distributions cost one extra version to keep in step. In exchange, an organ
that installs verification support CANNOT import a signer, because the bytes are
not on its disk. Authority leakage is prevented by the package boundary rather
than by a runtime check that can be bypassed.
"""
from __future__ import annotations

import hashlib
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import zipfile

# Deterministic builds. Without this the wheel's zip member timestamps are the
# wall-clock time of the build, so two builds of identical source produce
# different bytes. That was measured, not assumed: a fresh-clone rebuild
# differed from the working-tree build in 13 member timestamps and in ZERO
# content hashes.
#
# SOURCE_DATE_EPOCH is the reproducible-builds convention; setuptools honours
# it. Pinned to the UNIIMENTE constitutional epoch rather than "now" so the
# value does not drift.
SOURCE_DATE_EPOCH = "1750000000"
os.environ.setdefault("SOURCE_DATE_EPOCH", SOURCE_DATE_EPOCH)
os.environ.setdefault("PYTHONHASHSEED", "0")

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "dist"
VERSION = "0.1.0"

CLIENT_MODULES = ["__init__.py", "certificate.py", "verification.py",
                  "effector.py", "revocation.py", "legacy.py", "manifest.py",
                  "dispositions.py"]
ISSUER_MODULES = ["__init__.py", "signing.py", "issuer.py",
                  "revocation_authority.py"]

# Nothing matching these may appear in ANY built artifact.
FORBIDDEN_IN_ARTIFACTS = [
    "consequence_gate", "commit_witness", "uniimente_kernel/gate",
    "conftest", "test_", "_test", ".env", "id_ed25519", "private_key",
    "X_BEARER_TOKEN", "linkedin_client", "x_client",
]

CLIENT_PYPROJECT = f'''[build-system]
requires = ["setuptools>=68", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "uniimente-aperture-client"
version = "{VERSION}"
description = "Reality Aperture client: verify authorization certificates, check revocation, refuse locally. Cannot sign."
requires-python = ">=3.11"
dependencies = ["cryptography>=41.0", "pyyaml>=6.0"]
license = {{text = "Proprietary"}}

[project.urls]
Source = "https://github.com/dababiyoda/uniimente-kernel"

[tool.setuptools]
packages = ["aperture"]
include-package-data = true

[tool.setuptools.package-data]
aperture = ["canonical-authority.yaml"]
'''

ISSUER_PYPROJECT = f'''[build-system]
requires = ["setuptools>=68", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "uniimente-aperture-issuer"
version = "{VERSION}"
description = "Reality Aperture issuer: the single canonical authority. Installs the private signing path. NOT for organs."
requires-python = ">=3.11"
dependencies = ["cryptography>=41.0", "pyyaml>=6.0",
                "uniimente-aperture-client=={VERSION}"]
license = {{text = "Proprietary"}}

[tool.setuptools]
packages = ["aperture_issuer"]
'''


def stage(name: str, pkg: str, modules: list[str], pyproject: str,
          tmp: pathlib.Path) -> pathlib.Path:
    d = tmp / name
    (d / pkg).mkdir(parents=True)
    for m in modules:
        shutil.copy2(ROOT / pkg / m, d / pkg / m)
    # The canonical manifest travels WITH the client so a verifier always knows
    # which protocol it is speaking, even installed far from this repository.
    if pkg == "aperture":
        shutil.copy2(ROOT / "authority" / "canonical-authority.yaml",
                     d / pkg / "canonical-authority.yaml")
    (d / "pyproject.toml").write_text(pyproject)
    return d


def build(d: pathlib.Path) -> pathlib.Path:
    subprocess.run([sys.executable, "-m", "build", "--wheel", "--outdir",
                    str(OUT), str(d)], check=True, capture_output=True)
    wheels = sorted(OUT.glob("*.whl"), key=lambda p: p.stat().st_mtime)
    return wheels[-1]


def content_hash(wheel: pathlib.Path) -> str:
    """Identity of what the wheel CONTAINS, independent of archive metadata.

    Two wheels with the same version MUST have the same content_hash. The
    archive sha256 can legitimately differ across build environments; the
    content hash cannot. This is the stronger equivalence test: it refuses a
    same-version-different-contents substitution even where byte-level
    reproducibility is unavailable.
    """
    with zipfile.ZipFile(wheel) as z:
        members = sorted(
            (i.filename, hashlib.sha256(z.read(i.filename)).hexdigest())
            for i in z.infolist())
    return hashlib.sha256(
        json.dumps(members, sort_keys=True).encode()).hexdigest()


def inspect(wheel: pathlib.Path) -> dict:
    with zipfile.ZipFile(wheel) as z:
        names = sorted(z.namelist())
    violations = [n for n in names
                  for f in FORBIDDEN_IN_ARTIFACTS if f in n]
    return {
        "wheel": wheel.name,
        "sha256": hashlib.sha256(wheel.read_bytes()).hexdigest(),
        "content_hash": content_hash(wheel),
        "size_bytes": wheel.stat().st_size,
        "contents": names,
        "forbidden_content_found": sorted(set(violations)),
    }


def main() -> int:
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir()
    report = {"version": VERSION, "geometry": "two distributions",
              "source_date_epoch": os.environ["SOURCE_DATE_EPOCH"],
              "artifacts": {}}
    with tempfile.TemporaryDirectory() as t:
        tmp = pathlib.Path(t)
        c = stage("client", "aperture", CLIENT_MODULES, CLIENT_PYPROJECT, tmp)
        i = stage("issuer", "aperture_issuer", ISSUER_MODULES, ISSUER_PYPROJECT, tmp)
        report["artifacts"]["client"] = inspect(build(c))
        report["artifacts"]["issuer"] = inspect(build(i))

    cl = report["artifacts"]["client"]["contents"]
    report["assertions"] = {
        "client_excludes_issuer": not any("aperture_issuer" in n for n in cl),
        "client_excludes_signing_provider": not any("signing.py" in n for n in cl),
        "client_excludes_issuer_module": not any(
            n.endswith("aperture/issuer.py") for n in cl),
        "client_excludes_revocation_authority": not any(
            "revocation_authority" in n for n in cl),
        "client_ships_the_canonical_manifest": any(
            "canonical-authority.yaml" in n for n in cl),
        "no_forbidden_content_in_client":
            not report["artifacts"]["client"]["forbidden_content_found"],
        "no_forbidden_content_in_issuer":
            not report["artifacts"]["issuer"]["forbidden_content_found"],
    }
    report["all_assertions_pass"] = all(report["assertions"].values())

    (OUT / "PACKAGE_CONTENTS.txt").write_text(
        "\n".join(f"=== {k} ({v['wheel']}) sha256={v['sha256']}\n" +
                  "\n".join("  " + n for n in v["contents"])
                  for k, v in report["artifacts"].items()) + "\n")
    (OUT / "package_report.json").write_text(json.dumps(report, indent=2) + "\n")

    for k, v in report["assertions"].items():
        print(f"  {'ok  ' if v else 'FAIL'} {k}")
    print(f"\nclient: {report['artifacts']['client']['wheel']}")
    print(f"issuer: {report['artifacts']['issuer']['wheel']}")
    return 0 if report["all_assertions_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
