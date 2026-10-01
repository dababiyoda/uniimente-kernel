"""#3 Version control for institutional objects (policies, genomes, charters, capital rules).

Built on #36: every version is an immutable CAS record naming its content, its
parent version, a required reason and evidence references. ``refs/<name>`` points
at the head and moves only by compare-and-swap on the expected parent, so two
writers cannot silently overwrite each other. Rollback never rewrites history: it
commits the old content as a new version that names what it restores.
"""
from __future__ import annotations

import difflib
import fcntl
import json
import os
from pathlib import Path

from foundry.systems import cas


class VersionError(RuntimeError):
    """Refused: stale parent, missing reason, unknown version or broken chain."""


def _canonical(value) -> bytes:
    return json.dumps(value, sort_keys=True, indent=1, ensure_ascii=False).encode("utf-8")


def _ref(root: Path, name: str) -> Path:
    if not name or "/" in name or name.startswith("."):
        raise VersionError(f"invalid object name {name!r}")
    return Path(root) / "refs" / name


def head(root: Path, name: str) -> str | None:
    ref = _ref(root, name)
    return ref.read_text().strip() if ref.is_file() else None


def commit(root: Path, name: str, content, *, reason: str, evidence: list | tuple = (),
           expected_parent: str | None = "__head__") -> dict:
    if not str(reason).strip():
        raise VersionError("a version requires a reason")
    lock_path = Path(root) / "refs" / ".lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with open(lock_path, "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)  # compare-and-swap is atomic across processes
        return _commit_locked(root, name, content, reason, evidence, expected_parent)


def _commit_locked(root, name, content, reason, evidence, expected_parent) -> dict:
    current = head(root, name)
    if expected_parent != "__head__" and expected_parent != current:
        raise VersionError(f"stale parent: {name} moved to {current}, not {expected_parent}")
    parent = json.loads(cas.get(root, current)) if current else None
    record = {"name": name, "n": (parent["n"] + 1) if parent else 1, "parent": current,
              "content": cas.put(root, _canonical(content)), "reason": reason, "evidence": list(evidence)}
    address = cas.put(root, _canonical(record))
    ref = _ref(root, name)
    ref.parent.mkdir(parents=True, exist_ok=True)
    temporary = ref.with_name(f".{name}.{os.getpid()}.tmp")
    temporary.write_text(address)
    os.replace(temporary, ref)
    return dict(record, address=address)


def history(root: Path, name: str) -> list[dict]:
    out, address = [], head(root, name)
    while address:
        record = json.loads(cas.get(root, address))  # re-hashed: a tampered record is refused
        if record["name"] != name:
            raise VersionError(f"broken chain at {address}")
        out.append(dict(record, address=address))
        address = record["parent"]
    if out and [r["n"] for r in out] != list(range(len(out), 0, -1)):
        raise VersionError(f"non-contiguous history for {name}")
    return out


def content(root: Path, name: str, n: int | None = None):
    versions = history(root, name)
    if not versions:
        raise VersionError(f"no versions of {name}")
    chosen = versions[0] if n is None else next((v for v in versions if v["n"] == n), None)
    if chosen is None:
        raise VersionError(f"{name} has no version {n}")
    return json.loads(cas.get(root, chosen["content"]))


def diff(root: Path, name: str, a: int, b: int) -> str:
    left = _canonical(content(root, name, a)).decode().splitlines()
    right = _canonical(content(root, name, b)).decode().splitlines()
    return "\n".join(difflib.unified_diff(left, right, f"{name}@{a}", f"{name}@{b}", lineterm=""))


def rollback(root: Path, name: str, to: int, *, reason: str) -> dict:
    return commit(root, name, content(root, name, to), reason=f"rollback to v{to}: {reason}",
                  evidence=[f"restores:{name}@{to}"])


# -- Foundry interface ------------------------------------------------------------------

QUERY_OPS = {
    "history": lambda a, r: {"versions": [{k: v[k] for k in ("n", "reason", "evidence", "address")}
                                          for v in history(r, a["name"])]},
    "content": lambda a, r: {"content": content(r, a["name"], a.get("n"))},
    "diff": lambda a, r: {"diff": diff(r, a["name"], int(a["a"]), int(a["b"]))},
}
APPLY_OPS = {
    "commit": lambda a, r: {k: v for k, v in commit(r, a["name"], a["content"], reason=a.get("reason", ""),
                                                    evidence=a.get("evidence", ()),
                                                    expected_parent=a.get("expected_parent", "__head__")).items()
                            if k in ("n", "address", "parent")},
    "rollback": lambda a, r: {k: v for k, v in rollback(r, a["name"], int(a["to"]), reason=a.get("reason", "")).items()
                              if k in ("n", "address", "parent")},
}


def exercise(root: Path) -> dict:
    v1 = commit(root, "capital-policy", {"reserve_pct": 20, "max_single_bet_usd": 0}, reason="initial policy",
                evidence=["intent:SR-INTENT-3"])
    v2 = commit(root, "capital-policy", {"reserve_pct": 30, "max_single_bet_usd": 0}, reason="raise reserve",
                evidence=["critique:reserve-too-thin"], expected_parent=v1["address"])
    try:
        commit(root, "capital-policy", {"reserve_pct": 5}, reason="stale writer", expected_parent=v1["address"])
        stale_refused = False
    except VersionError:
        stale_refused = True
    try:
        commit(root, "capital-policy", {"reserve_pct": 5}, reason="  ")
        reasonless_refused = False
    except VersionError:
        reasonless_refused = True
    v3 = rollback(root, "capital-policy", 1, reason="reserve change hurt liquidity")
    versions = history(root, "capital-policy")
    return {"versions": [v["n"] for v in versions], "head_content": content(root, "capital-policy"),
            "rollback_is_new_version": v3["n"] == 3 and v3["parent"] == v2["address"],
            "v2_still_retrievable": content(root, "capital-policy", 2)["reserve_pct"] == 30,
            "stale_writer_refused": stale_refused, "reasonless_refused": reasonless_refused,
            "diff_1_2": diff(root, "capital-policy", 1, 2)}
