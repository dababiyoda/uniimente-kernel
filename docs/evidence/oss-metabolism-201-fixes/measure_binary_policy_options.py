"""Measure the four binary-license policy options of BINARY_LICENSE_POLICY.md on this body. Read-only: it runs
dpkg-query and apt-cache, reads /usr/share/doc/*/copyright and changes nothing. Prints JSON.

Usage: PYTHONPATH=. python docs/evidence/oss-metabolism-201-fixes/measure_binary_policy_options.py

Options (none is activated by this script; the active policy stays P0):
  O1 fail closed: a newly acquired binary attaches by itself only when its license verdict is CLEARED or
     CLEARED_WITH_OBLIGATIONS; unclassified, undeterminable and held binaries wait for the founder.
  O2 reviewed allowlist: O1, except (package, binary) pairs a person reviewed for GREG's use attach.
  O3 use context with authenticated approval: P4c (every term compatible with GREG's actual use) for automatic
     attach, plus D-LIC-1 (a founder-signed, digest-bound license_clearance) to lift a hold.
  O4 distributor-reviewed component: a known network-copyleft or not-open term holds (as P0); an unclassified
     binary attaches only when its package version comes from a signed distributor archive component whose
     policy admits only free software (Debian main, Ubuntu main or universe) and GREG's use is the local,
     unmodified, unredistributed one; anything else (non-free, contrib, restricted, multiverse, a third-party
     archive, a local .deb, no package manager) waits for the founder. The origin is the Release file's Origin
     field, which apt verified against the key configured for that source; a repository the founder adds could
     claim "Ubuntu" with its own key, so the evidence is only as good as the configured sources.
"""
import collections
import json
import os
import re
import shutil
import subprocess
import sys
from types import SimpleNamespace

from greg import genesis, licensing

CLEARED = {"CLEARED", "CLEARED_WITH_OBLIGATIONS"}
ALLOWLIST = {("coreutils", "sha256sum"), ("coreutils", "wc"), ("openssl", "openssl"),
             ("poppler-utils", "pdftotext"), ("poppler-utils", "pdfimages")}


def catalog() -> dict:
    """Every binary Genesis can acquire, with the function it serves and its companions."""
    out = {}
    for function, spec in genesis.CATALOG.items():
        for c in spec.get("candidates", ()):
            if hasattr(c, "binary_name"):
                out[c.binary_name] = function
                for name, _ in getattr(c, "companions", ()):
                    out[name] = f"{function} (companion)"
    return out


def package_of(path: str) -> str | None:
    if shutil.which("dpkg-query") is None:
        return None
    proc = subprocess.run(["dpkg-query", "-S", os.path.realpath(path)], capture_output=True, text=True,
                          env={"PATH": "/usr/bin:/bin", "LC_ALL": "C"})
    owners = {line.split(":", 1)[0].split(":")[0] for line in proc.stdout.splitlines() if line.strip()}
    return owners.pop() if proc.returncode == 0 and len(owners) == 1 else None


FREE = {"Debian": {"main"}, "Ubuntu": {"main", "universe"}}   # distributor archives whose policy admits free software only
_RELEASES: dict = {}
_ORIGINS: dict = {}


def releases() -> dict:
    """apt's package sources ("<url> <suite>/<component> <arch> Packages") mapped to their release origin and
    component, read from the Release files apt verified against its configured keys."""
    if not _RELEASES and shutil.which("apt-cache"):
        source = None
        for line in subprocess.run(["apt-cache", "policy"], capture_output=True, text=True,
                                   env={"PATH": "/usr/bin:/bin", "LC_ALL": "C"}).stdout.splitlines():
            m = re.match(r"\s*-?\d+\s+(\S+\s+\S+\s+\S+\s+Packages)$", line)
            if m:
                source = m.group(1)
            elif source and line.strip().startswith("release "):
                attrs = dict(kv.split("=", 1) for kv in line.strip()[8:].split(",") if "=" in kv)
                _RELEASES[source] = (attrs.get("o", "?"), attrs.get("c", "?"))
                source = None
    return _RELEASES


def origin(package: str) -> str:
    """'<origin>/<component>' for each archive serving the installed version; 'local' when none does (a .deb
    installed by hand, or a version no configured archive carries)."""
    if package in _ORIGINS:
        return _ORIGINS[package]
    if shutil.which("apt-cache") is None:
        return _ORIGINS.setdefault(package, "no apt")
    text = subprocess.run(["apt-cache", "policy", package], capture_output=True, text=True,
                          env={"PATH": "/usr/bin:/bin", "LC_ALL": "C"}).stdout
    found, installed, table = set(), False, False
    for line in text.splitlines():
        if line.strip() == "Version table:":
            table = True
        elif table and not line.startswith("        "):          # a version line: " *** 1.0 500" or "     0.9 500"
            installed = line.lstrip().startswith("***")
        elif table and installed:                                  # a source line of the installed version
            m = re.match(r"\s*-?\d+\s+(\S+\s+\S+\s+\S+\s+Packages)$", line)
            if m:
                found.add("/".join(releases().get(m.group(1), ("?", "?"))))
    return _ORIGINS.setdefault(package, " ".join(sorted(found)) or "local")


def distributor_free(component: str) -> bool:
    return any(c in FREE.get(o, ()) for o, _, c in (x.partition("/") for x in component.split()))


def manifest(assessment):
    return SimpleNamespace(capability_id="acquired.x.y", provider="installed:/usr/bin/x",
                           provenance={"license_assessment": assessment})


def row(name: str, path: str) -> dict:
    a = licensing.system_binary(path)
    package = package_of(path)
    comp = origin(package) if package else "no package"
    verdict = a["verdict"] if a else "UNDETERMINABLE"
    held_p0 = bool(a) and not licensing.attach_check(manifest(a), "P0")[0]
    o1 = verdict not in CLEARED
    o2 = o1 and (package, name) not in ALLOWLIST
    o3 = not licensing.attach_check(manifest(a), "P4c")[0]
    free = distributor_free(comp)
    o4 = held_p0 or (verdict not in CLEARED and not free)
    return {"binary": name, "package": package, "component": comp, "verdict": verdict, "held_P0": held_p0,
            "held_O1": o1, "held_O2": o2, "held_O3": o3, "held_O4": o4,
            "unclassified": (a or {}).get("uncertainty", [])[1:2]}


def main():
    cat = catalog()
    rows = []
    for name in sorted(os.listdir("/usr/bin")):
        path = os.path.join("/usr/bin", name)
        if os.path.isfile(path) and os.access(path, os.X_OK) and not os.path.islink(path):
            rows.append(row(name, path))
    for name in sorted(cat):                    # catalog binaries that live elsewhere on the search path
        if name not in {r["binary"] for r in rows} and genesis.installed_binary(name):
            rows.append(row(name, genesis.installed_binary(name)))
    tally = {k: sum(r[k] for r in rows) for k in ("held_P0", "held_O1", "held_O2", "held_O3", "held_O4")}
    catalog_rows = {r["binary"]: {k: r[k] for k in r if k != "binary"} for r in rows if r["binary"] in cat}
    no_dpkg = {name: {"held_O1": True, "held_O2": True, "held_O3": True, "held_O4": True, "held_P0": False}
               for name in cat}                # a body without dpkg (macOS): nothing is readable
    print(json.dumps({"body": {"os": open("/etc/os-release").read().split("\n")[0] if os.path.exists("/etc/os-release")
                               else sys.platform, "dpkg": shutil.which("dpkg-query") is not None},
                      "binaries": len(rows), "components": collections.Counter(r["component"] for r in rows),
                      "verdicts": collections.Counter(r["verdict"] for r in rows), "held": tally,
                      "catalog": {"functions": cat, "on_this_body": catalog_rows, "missing": sorted(set(cat) -
                                                                                                      set(catalog_rows))},
                      "catalog_without_dpkg": no_dpkg, "allowlist": sorted(ALLOWLIST),
                      "held_O4_binaries": [[r["binary"], r["package"], r["component"], r["verdict"]] for r in rows
                                           if r["held_O4"]]}, indent=1, default=str))


if __name__ == "__main__":
    main()
