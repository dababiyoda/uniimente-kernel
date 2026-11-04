"""Run model_license_tree over every license text installed on this body; compare with each package's own declaration."""
import collections, glob, json, os, sys, importlib.metadata as md
sys.path.insert(0, os.getcwd())
from greg import licensing as L
rows = []
site = "/home/user/venv311/lib/python3.11/site-packages/"
for f in sorted(glob.glob(site + "*.dist-info/**/*", recursive=True)):
    if not os.path.isfile(f) or "LICEN" not in os.path.basename(f).upper() and "COPYING" not in os.path.basename(f).upper():
        continue
    dist = f[len(site):].split(".dist-info")[0].rsplit("-", 1)[0]
    try:
        meta = md.distribution(dist).metadata
        declared = meta.get("License-Expression") or "; ".join(c.split("::")[-1].strip() for c in meta.get_all("Classifier") or [] if c.startswith("License ::")) or (meta.get("License") or "")[:40]
    except Exception:
        declared = "?"
    tree = L.model_license_tree(open(f, errors="replace").read())
    cls = L._held_eval(tree)[0]
    rows.append({"file": f[len(site):], "declared": declared, "class": cls, "terms": [a["atom"][:60] for a in L._atoms(tree)]})
for f in sorted(glob.glob("/usr/share/common-licenses/*")):
    if os.path.isfile(f):
        tree = L.model_license_tree(open(f, errors="replace").read())
        rows.append({"file": f, "declared": os.path.basename(f), "class": L._held_eval(tree)[0], "terms": [a["atom"][:60] for a in L._atoms(tree)]})
count = collections.Counter(r["class"] for r in rows)
cleared = [r for r in rows if r["class"] == "permissive"]
print(json.dumps({"texts": len(rows), "by_class": count, "cleared": len(cleared),
                  "cleared_as": collections.Counter(r["terms"][0] for r in cleared)}, indent=1))
print("cleared texts whose package declares something other than plain Apache-2.0 or MIT:")
for r in cleared:
    d = r["declared"]
    if not any(k in d for k in ("Apache", "MIT")) or any(k in d for k in (" OR ", " AND ", ";")):
        print("  ", r["file"][:70], "| declared:", d[:60], "| read as:", r["terms"])
print("held, with a restrictive reading:")
for r in rows:
    if r["class"] == "not_open_source":
        print("  ", r["file"][:70], r["terms"])
json.dump(rows, open(sys.argv[1], "w"), indent=1)
