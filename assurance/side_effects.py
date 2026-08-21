"""Side-effect inventory: does anything reach the world without crossing the gate?

`policy/consequence_gate.py` opens with a claim — *"The sole path to external
effects."* Nothing has ever measured it. Kimi's Final Plan names the same hole
from the other direction: the active gate is *"no proof that one action family is
non-bypassable end to end"*, and the active metric is *"Verified Mediated
Side-Effect Coverage, baseline unknown until inventory."*

This is that inventory. It walks every non-test module's AST, finds each call
that can affect something outside this process, and asks whether the module
holding it can reach the gate at all.

**What this proves, and what it cannot.** A static read cannot prove runtime
reachability. A module that imports the gate might still call a socket around
it, and a module that does not import the gate might only ever be invoked behind
one. So the classification here is deliberately weak on purpose:
`UNMEDIATED_BY_STATIC_READING` means *this site has no visible path to the gate
from its own module*, which is a candidate for review — never a proven bypass.
Naming it any more strongly would be inventing assurance, and an assurance
module that overstates itself is worse than none.

What it does prove is the negative direction, which is the useful one: a site
whose module never imports the gate cannot be *shown* to be mediated, and the
institution should not claim coverage it cannot show. Coverage is therefore
reported as a floor, not an estimate.

**Categories are not equal.** The arsenal already separates `internal_write`
from `external_contact`, and so does this. Writing a snapshot to disk is not
reaching the world. Opening a socket is. They are counted separately, because a
single blended number would let filesystem noise bury the four call sites that
actually matter.
"""
from __future__ import annotations

import ast
import os
from dataclasses import dataclass
from enum import Enum

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

#: The gate module. A site is only *showably* mediated if its module can see this.
GATE_MODULE = "policy.consequence_gate"

#: Directories excluded from the walk, with the reason each is excluded.
EXCLUDED = {
    ".git": "not source",
    "__pycache__": "generated",
    "tests": "test code exercises effects deliberately and is not institutional behaviour",
    "scripts": "developer tooling, not the institution acting",
}


class Family(Enum):
    """What a call site can reach. Narrower is more serious."""

    #: Off this machine entirely: sockets, HTTP, mail, DNS.
    NETWORK = "network_egress"
    #: Another process, which can then do anything at all.
    PROCESS = "process_spawn"
    #: This machine's disk. Consequential, but not external contact.
    FILESYSTEM = "filesystem_write"


class Mediation(Enum):
    SHOWABLY_MEDIATED = "showably_mediated"
    #: No visible path to the gate from this module. A review candidate.
    UNMEDIATED_BY_STATIC_READING = "unmediated_by_static_reading"
    #: The gate and its own machinery. Excluded from the ratio rather than
    #: counted as mediated, because the gate mediating itself proves nothing.
    IS_THE_MEDIATOR = "is_the_mediator"


#: Attribute calls that reach off-machine, by module root.
_NETWORK_ROOTS = {"socket", "requests", "urllib", "http", "smtplib", "ftplib",
                  "telnetlib", "asyncio", "aiohttp", "httpx", "websockets"}
_PROCESS_ROOTS = {"subprocess", "multiprocessing", "pty"}
#: os functions that spawn or reach out, as opposed to os.path arithmetic.
_OS_PROCESS = {"system", "popen", "execv", "execve", "execvp", "spawnv", "fork"}
_FS_WRITE_ROOTS = {"shutil"}
_OS_FS_WRITE = {"remove", "unlink", "rmdir", "makedirs", "mkdir", "rename",
                "replace", "truncate", "chmod", "chown"}
#: Modes that make `open()` a write.
_WRITE_MODES = ("w", "a", "x", "+")


@dataclass(frozen=True)
class Site:
    """One call that can affect something outside this process."""

    module: str
    line: int
    call: str
    family: Family
    mediation: Mediation

    @property
    def counts_toward_coverage(self) -> bool:
        return self.mediation is not Mediation.IS_THE_MEDIATOR


def _root_of(node: ast.AST) -> str:
    """The leftmost name of a dotted call: `a.b.c()` -> 'a'."""
    while isinstance(node, ast.Attribute):
        node = node.value
    return node.id if isinstance(node, ast.Name) else ""


def _rendered(node: ast.AST) -> str:
    try:
        return ast.unparse(node)
    except Exception:                        # pragma: no cover - very old ASTs
        return "<call>"


def _classify_call(node: ast.Call) -> Family | None:
    """Which family this call belongs to, or None if it touches nothing outside."""
    func = node.func

    if isinstance(func, ast.Name) and func.id == "open":
        mode = ""
        if len(node.args) > 1 and isinstance(node.args[1], ast.Constant):
            mode = str(node.args[1].value)
        for kw in node.keywords:
            if kw.arg == "mode" and isinstance(kw.value, ast.Constant):
                mode = str(kw.value.value)
        return Family.FILESYSTEM if any(m in mode for m in _WRITE_MODES) else None

    if isinstance(func, ast.Attribute):
        root, attr = _root_of(func), func.attr
        if root in _NETWORK_ROOTS:
            return Family.NETWORK
        if root in _PROCESS_ROOTS:
            return Family.PROCESS
        if root == "os":
            if attr in _OS_PROCESS:
                return Family.PROCESS
            if attr in _OS_FS_WRITE:
                return Family.FILESYSTEM
        if root in _FS_WRITE_ROOTS:
            return Family.FILESYSTEM
    return None


def _imported_capabilities(tree: ast.AST) -> list[tuple[str, Family, int]]:
    """Reaching capability acquired by import, not by dotted call.

    Closes the obvious evasion, and one this detector genuinely had: it matched
    `socket.socket()` but not `from socket import socket` followed by a bare
    `socket()`. Today nothing imports a network module, so the network total was
    accidentally correct rather than defended. An import is recorded as its own
    site because acquiring the capability is the reportable event — whether it is
    called on line 10 or line 400 does not change that the module can reach out.
    """
    found: list[tuple[str, Family, int]] = []
    for node in ast.walk(tree):
        roots: list[str] = []
        if isinstance(node, ast.ImportFrom) and node.module:
            roots = [node.module.split(".")[0]]
        elif isinstance(node, ast.Import):
            roots = [alias.name.split(".")[0] for alias in node.names]
        for root in roots:
            if root in _NETWORK_ROOTS:
                found.append((f"import {root}", Family.NETWORK, node.lineno))
            elif root in _PROCESS_ROOTS:
                found.append((f"import {root}", Family.PROCESS, node.lineno))
    return found


def _module_sees_gate(tree: ast.AST) -> bool:
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            if node.module.startswith("policy"):
                return True
        elif isinstance(node, ast.Import):
            if any(a.name.startswith("policy") for a in node.names):
                return True
    return False


def _source_files(root: str = ROOT) -> list[str]:
    out: list[str] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in EXCLUDED]
        for name in sorted(filenames):
            if name.endswith(".py"):
                out.append(os.path.join(dirpath, name))
    return sorted(out)


def inventory(root: str = ROOT) -> tuple[Site, ...]:
    """Every site in institutional code that can affect the world outside it."""
    sites: list[Site] = []
    for path in _source_files(root):
        rel = os.path.relpath(path, root)
        module = rel[:-3].replace(os.sep, ".")
        try:
            with open(path, encoding="utf-8") as fh:
                tree = ast.parse(fh.read(), filename=rel)
        except (OSError, SyntaxError):
            continue

        if module.startswith("policy."):
            mediation = Mediation.IS_THE_MEDIATOR
        elif _module_sees_gate(tree):
            mediation = Mediation.SHOWABLY_MEDIATED
        else:
            mediation = Mediation.UNMEDIATED_BY_STATIC_READING

        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            family = _classify_call(node)
            if family is None:
                continue
            sites.append(Site(module=module, line=node.lineno,
                              call=_rendered(node.func), family=family,
                              mediation=mediation))

        for label, family, line in _imported_capabilities(tree):
            sites.append(Site(module=module, line=line, call=label,
                              family=family, mediation=mediation))
    return tuple(sites)


def by_family(sites: tuple[Site, ...] | None = None) -> dict[Family, tuple[Site, ...]]:
    found = inventory() if sites is None else sites
    out: dict[Family, list[Site]] = {family: [] for family in Family}
    for site in found:
        out[site.family].append(site)
    return {family: tuple(rows) for family, rows in out.items()}


def coverage(family: Family, sites: tuple[Site, ...] | None = None) -> tuple[int, int]:
    """(showably mediated, total) for one family, excluding the mediator itself.

    Returned as a pair rather than a percentage so a caller cannot render 0/0 as
    100%. An empty family means the institution cannot do that thing at all,
    which is a different and much stronger statement than full coverage.
    """
    rows = [s for s in (inventory() if sites is None else sites)
            if s.family is family and s.counts_toward_coverage]
    mediated = [s for s in rows if s.mediation is Mediation.SHOWABLY_MEDIATED]
    return len(mediated), len(rows)


def render() -> str:
    sites = inventory()
    families = by_family(sites)
    lines = [f"side-effect sites in institutional code : {len(sites)}",
             "  (tests and scripts excluded; policy/ is the mediator and is not "
             "counted against itself)", ""]

    for family in Family:
        rows = families[family]
        mediated, total = coverage(family, sites)
        if total == 0:
            verdict = ("NO SITES — the institution cannot do this at all, which "
                       "is stronger than full coverage")
            lines.append(f"{family.value:<18} {len(rows):>3} site(s)   {verdict}")
            continue
        pct = 100 * mediated // total
        lines.append(f"{family.value:<18} {total:>3} site(s)   "
                     f"showably mediated: {mediated}/{total} ({pct}%)")
        unmediated = [s for s in rows
                      if s.mediation is Mediation.UNMEDIATED_BY_STATIC_READING]
        for site in unmediated[:12]:
            lines.append(f"      {site.module}:{site.line}  {site.call}")
        if len(unmediated) > 12:
            lines.append(f"      … and {len(unmediated) - 12} more")

    lines += ["",
              "COVERAGE IS A FLOOR, NOT AN ESTIMATE. A static read cannot prove "
              "runtime reachability, so `unmediated_by_static_reading` means the "
              "site has no visible path to the gate from its own module — a "
              "review candidate, never a proven bypass. Sites are reported so a "
              "human can close them, not so a number can be quoted."]
    return "\n".join(lines)


if __name__ == "__main__":  # pragma: no cover - operator entry point
    print(render())
