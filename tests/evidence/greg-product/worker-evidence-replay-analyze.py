import json, sys
from collections import defaultdict
def verdicts(rec):
    out = {}
    for pol, rows in rec["policies"].items():
        k = sum(r["killed"] for r in rows); n = len(rows)
        ratio_ok = n == 0 or (k >= 1 and k / n >= 0.5)
        lines = defaultdict(list)
        for r in rows: lines[(r["file"], r["mutant"].split(":")[0])].append(r["killed"])
        cov = sum(any(v) for v in lines.values())
        line_ok = not lines or (cov >= 1 and cov / len(lines) >= 0.5)
        out[pol] = {"n": n, "k": k, "ratio": ratio_ok, "lines": len(lines), "cov": cov, "perline": line_ok}
    return out
for path in sys.argv[1:]:
    print("==", path)
    tot = defaultdict(lambda: [0, 0]); errs = 0; disc_fail = 0; judged = 0
    for line in open(path):
        rec = json.loads(line)
        if "error" in rec: errs += 1; print(" ", rec["sha"], "ERR", rec["error"][:90]); continue
        judged += 1
        d = rec.get("base_rc") in (1, 2, -1)
        if not d: disc_fail += 1
        v = verdicts(rec)
        cells = []
        for pol in ("all", "expressions", "none"):
            for sc in ("ratio", "perline"):
                tot[(pol, sc)][0] += v[pol][sc]; tot[(pol, sc)][1] += 1
            cells.append(f"{pol[:3]} {v[pol]['k']}/{v[pol]['n']} L{v[pol]['cov']}/{v[pol]['lines']} {'A' if v[pol]['ratio'] else 'R'}{'A' if v[pol]['perline'] else 'R'}")
        print(f"  {rec['sha'][:8]} disc={'Y' if d else 'N('+str(rec.get('base_rc'))+')'} {rec['seconds']:>6}s | " + " | ".join(cells))
    print(f"  judged {judged}, errors {errs}, discrimination not established {disc_fail}")
    for key, (a, n) in sorted(tot.items()): print(f"  {key[0]:12s} {key[1]:8s} accepted {a}/{n}")
