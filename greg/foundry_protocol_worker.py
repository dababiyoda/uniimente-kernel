"""One reviewed child recipe: recompute a restricted DSL, never Python source.

When invoked by Foundry, inherits its network filter and resource budget.
The scope is installed by the reviewed parent, never by the caller's DSL input.
"""
import json
import os
from pathlib import Path
import resource
import sys


def main():
    resource.setrlimit(resource.RLIMIT_CPU, (12, 12))
    resource.setrlimit(resource.RLIMIT_AS, (2 * 1024**3, 2 * 1024**3))
    resource.setrlimit(resource.RLIMIT_FSIZE, (0, 0))
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    if sys.argv[1:] != ["dsl-verify"]:
        raise ValueError("unreviewed child recipe")
    raw = sys.stdin.buffer.read(131073)
    if len(raw) > 131072:
        raise ValueError("DSL verification job exceeds 128 KiB")
    job = json.loads(raw)
    if set(job) != {"language", "source", "cases"} or not isinstance(job["cases"], list) or len(job["cases"]) > 4096:
        raise ValueError("invalid bounded DSL verification job")
    from foundry.systems import dsl
    scope = os.environ.get("GREG_FOUNDRY_STORE")
    if scope:
        from greg.foundry_worker import guard
        guard(Path(scope))
    print(json.dumps([dsl.run(job["language"], job["source"], case) for case in job["cases"]], allow_nan=False))


if __name__ == "__main__":
    main()
