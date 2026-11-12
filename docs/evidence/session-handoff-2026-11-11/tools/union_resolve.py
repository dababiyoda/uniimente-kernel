"""Resolve a conflicted file by keeping both sides' lines, in order (ours then theirs). Only for files where every
side adds independent lines at the same place (the CI step list, the ledger's top). usage: union_resolve.py FILE..."""
import sys
for path in sys.argv[1:]:
    out, n = [], 0
    for line in open(path, encoding="utf-8"):
        if line.startswith(("<<<<<<< ", "=======", ">>>>>>> ")) and (line.startswith("=======") and line.strip() == "=======" or not line.startswith("=======")):
            n += 1
            continue
        if line.startswith("||||||| "):
            raise SystemExit(f"{path}: diff3 conflict style is not handled")
        out.append(line)
    open(path, "w", encoding="utf-8").write("".join(out))
    print(f"{path}: {n // 3} conflict(s) resolved by keeping both sides")
