"""Reviewed bounded child recipes, never caller-supplied Python source.

In GREG these inherit the parent's network filter, resource ceilings, process
group and fixed workspace scope. Owned packaging reads only published source
inventory paths; arbitrary providers and code execution remain refused.
"""
import json
import os
from pathlib import Path
import resource
import sys


def main():
    mode = sys.argv[1:]
    if mode not in (["dsl-verify"], ["build-owned"]):
        raise ValueError("unreviewed child recipe")
    resource.setrlimit(resource.RLIMIT_CPU, (12, 12))
    resource.setrlimit(resource.RLIMIT_AS, (2 * 1024**3, 2 * 1024**3))
    ceiling = 8 * 1048576 if mode == ["build-owned"] else 0
    resource.setrlimit(resource.RLIMIT_FSIZE, (ceiling, ceiling))
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    raw = sys.stdin.buffer.read(131073)
    if len(raw) > 131072:
        raise ValueError("reviewed child job exceeds 128 KiB")
    job = json.loads(raw)
    scope = os.environ.get("GREG_FOUNDRY_STORE")
    if mode == ["dsl-verify"]:
        if set(job) != {"language", "source", "cases"} or not isinstance(job["cases"], list) or len(job["cases"]) > 4096:
            raise ValueError("invalid bounded DSL verification job")
        from foundry.systems import dsl
        if scope:
            from greg.foundry_worker import guard
            guard(Path(scope))
        result = [dsl.run(job["language"], job["source"], case) for case in job["cases"]]
    else:
        if not scope or set(job) != {"out"} or not isinstance(job["out"], str):
            raise ValueError("owned packaging requires its parent-installed scope")
        root, out = Path(scope).resolve(), Path(job["out"]).resolve()
        if out == root or root not in out.parents:
            raise ValueError("owned packaging output outside its scope")
        from foundry.systems.build import build
        from greg.foundry_worker import guard, source_files
        guard(root, source_files())
        result = build(out)
    print(json.dumps(result, allow_nan=False))


if __name__ == "__main__":
    main()
