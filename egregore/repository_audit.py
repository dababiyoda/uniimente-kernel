"""Fixed local read capability. No fetch, shell, hook, write or credentials.

Owner: Kernel fixed local mission capability. Inputs are host-approved paths and exact cached refs;
output retains the bytes used for appraisal. This is not a general Git executor.
"""
from __future__ import annotations

import ast
import hashlib
import os
from pathlib import Path
import re
import shutil
import subprocess
import tomllib

FILES = {"kernel": ("pyproject.toml",),
         "dale": ("pyproject.toml", "requirements.txt"),
         "wmi": ("pyproject.toml", "requirements.txt")}
INTEGRATION_FILES = {
    "kernel": FILES["kernel"] + ("egregore/runtime.py", "policy/consequence_gate.py"),
    "dale": FILES["dale"] + ("services/reflection.py", "services/generator.py"),
    "wmi": FILES["wmi"] + ("src/services/bridge_security.py",),
}


def source_files(profile=None):
    if profile is None:
        return FILES
    if profile != "integration-v1":
        raise ValueError("unsupported audit profile")
    return INTEGRATION_FILES


SHA = re.compile(r"^[0-9a-f]{40}$")
PIN = re.compile(r"https://github.com/dababiyoda/uniimente-kernel/archive/([0-9a-f]{40})\.tar\.gz")
MAX_BLOB = 65536


def validate_repositories(repositories):
    if not isinstance(repositories, list) or len(repositories) != 3:
        raise ValueError("exactly three approved repositories required")
    if {r.get("role") for r in repositories} != set(FILES):
        raise ValueError("kernel, dale and wmi each required")
    for r in repositories:
        if set(r) != {"role", "path", "commit"} or not SHA.fullmatch(r["commit"]):
            raise ValueError("invalid repository binding")
        p = Path(r["path"])
        if not p.is_absolute() or not p.is_dir() or p.resolve() != p:
            raise ValueError("approved absolute real repository path required")


def git_read(path, *args):
    git = shutil.which("git")
    if not git:
        raise RuntimeError("Git capability unavailable")
    env = {"PATH": os.defpath, "LANG": "C.UTF-8", "GIT_CONFIG_NOSYSTEM": "1",
           "GIT_CONFIG_GLOBAL": os.devnull, "GIT_TERMINAL_PROMPT": "0",
           "GIT_OPTIONAL_LOCKS": "0", "GIT_NO_LAZY_FETCH": "1"}
    result = subprocess.run([git, "--no-pager", "-C", path, *args], env=env,
                            capture_output=True, timeout=5, check=True)
    if len(result.stdout) > MAX_BLOB:
        raise ValueError("source exceeds audit bound")
    return result.stdout


def capture(repositories, profile=None):
    validate_repositories(repositories)
    sources = []
    for repo in sorted(repositories, key=lambda r: r["role"]):
        observed = git_read(repo["path"], "rev-parse", "refs/remotes/origin/main").decode().strip()
        if observed != repo["commit"]:
            raise ValueError("cached main changed; reconsider the original mission")
        for name in source_files(profile)[repo["role"]]:
            obj = repo["commit"] + ":" + name
            size = int(git_read(repo["path"], "cat-file", "-s", obj))
            if not 0 <= size <= MAX_BLOB:
                raise ValueError("source exceeds audit bound")
            raw = git_read(repo["path"], "cat-file", "blob", obj)
            if len(raw) != size:
                raise ValueError("source size changed")
            blob = hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
            sources.append({"role": repo["role"], "commit": observed, "file": name,
                            "blob": blob, "text": raw.decode("utf-8")})
    return sources


def derive(sources, expected_pin, expected_version, profile=None):
    """Semantic appraisal of retained bytes, not a worker's success flag."""
    source_files(profile)
    rows, compatible = [], True
    for source in sources:
        if source["file"] not in FILES[source["role"]]:
            continue
        text = source["text"]
        if source["role"] == "kernel":
            version = tomllib.loads(text)["project"]["version"]
            valid = version == expected_version
            row = {"version": version}
        else:
            values = (tomllib.loads(text)["project"]["dependencies"]
                      if source["file"] == "pyproject.toml" else text.splitlines())
            declarations = [v for v in values if v.strip().startswith("uniimente-kernel-boundaries")]
            pins = [PIN.findall(v) for v in declarations]
            valid = pins == [[expected_pin]]
            row = {"pins": pins}
        compatible = compatible and valid
        rows.append({"role": source["role"], "file": source["file"],
                     "commit": source["commit"], "blob": source["blob"],
                     "matches": valid, **row})
    report = {"compatible": compatible, "rows": rows, "source_scope": "cached local Git snapshots"}
    if profile:
        report["findings"] = integration_findings(sources, rows)
        report["coverage"] = [f"{s['role']}:{s['commit']}:{s['file']}" for s in sources]
        report["limits"] = "Bounded static source checks; not a complete integration diagnosis or fresh remote state."
    return report


def integration_findings(sources, rows):
    findings = []
    for row in rows:
        if not row["matches"]:
            findings.append({"id": "pin:" + row["role"] + ":" + row["file"], "kind": "dependency",
                "summary": "Dependency declaration differs from the approved boundary contract", "evidence": row,
                "next_action": "Compare the declared revision against the approved contract in an isolated consumer test."})
    for s in sources:
        evidence = {k: s[k] for k in ("role", "commit", "file", "blob")}
        if s["file"] == "egregore/runtime.py":
            for node in ast.walk(ast.parse(s["text"])):
                if isinstance(node, ast.FunctionDef) and node.name == "resume":
                    calls = {ast.unparse(n.func) for n in ast.walk(node) if isinstance(n, ast.Call)}
                    if "require_hash" in calls and "gate.run" not in calls:
                        findings.append({"id": "resume-authority", "kind": "authority",
                            "summary": "Standing cognition resume checks hash format without issuer verification in this method",
                            "evidence": evidence | {"line": node.lineno},
                            "next_action": "Trace trusted callers; require a pre-existing exact-scope Kernel grant before resume."})
        if s["file"] == "services/reflection.py" and "follower_delta" in s["text"]:
            findings.append({"id": "reflection-outcome-gap", "kind": "learning",
                "summary": "Reflection consumes engagement/follower signals; these alone do not establish participant benefit",
                "evidence": evidence,
                "next_action": "Compare a bounded correction on a held-out participant task before retaining a lesson."})
    return findings
