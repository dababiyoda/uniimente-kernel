"""Before (HEAD) and after (working tree) on this host's real declarations."""
import glob, importlib.util, importlib.metadata as md, os, sys, json
sys.path.insert(0, os.getcwd())
from greg import licensing as new
spec = importlib.util.spec_from_file_location("licensing_old", sys.argv[1]); old = importlib.util.module_from_spec(spec); spec.loader.exec_module(old)
out = {"distributions": [], "dep5": [], "binaries": []}
seen = set()
for d in md.distributions():
    name = d.metadata["Name"]
    if not name or name.lower() in seen: continue
    seen.add(name.lower())
    a, b = old.assess(d), new.assess(d)
    if (a["verdict"], a["class"]) != (b["verdict"], b["class"]):
        out["distributions"].append([name, a["verdict"], a["class"], b["verdict"], b["class"]])
n_dist = len(seen)
files = sorted(glob.glob("/usr/share/doc/*/copyright"))
n_dep5 = 0
for f in files:
    t = open(f, errors="replace").read()
    a, b = old.dep5(t), new.dep5(t)
    if b is not None: n_dep5 += 1
    ka = (a["class"], a["held"]) if a else None; kb = (b["class"], b["held"]) if b else None
    if ka != kb: out["dep5"].append([f, ka, kb])
bins = sorted(glob.glob("/usr/bin/*"))[:2000]
for bpath in bins:
    if not os.path.isfile(bpath): continue
    a, b = old.system_binary(bpath), new.system_binary(bpath)
    ka = (a["verdict"], a.get("held")) if a else None; kb = (b["verdict"], b.get("held")) if b else None
    if ka != kb: out["binaries"].append([bpath, ka, kb])
print(json.dumps({"distributions": n_dist, "copyright_files": len(files), "dep5_parsed": n_dep5, "binaries": len(bins),
                  "changes": {k: len(v) for k, v in out.items()}}, indent=1))
print(json.dumps(out, indent=1)[:4000])
json.dump(out, open(sys.argv[2], "w"), indent=1)
