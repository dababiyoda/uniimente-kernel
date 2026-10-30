import json, sys, collections
from licensedcode.models import load_licenses
from license_expression import Licensing, LicenseSymbol, AND, OR, LicenseWithExceptionSymbol
db = load_licenses()
NETWORK = {"agpl", "osl", "eupl", "rpl", "sspl"}
def kcls(key):
    lic = db.get(key)
    cat = (lic.category if lic else "Unstated License") or "Unstated License"
    if any(key.startswith(p) for p in NETWORK): return "network_copyleft", cat
    return {"Permissive": "permissive", "Public Domain": "permissive", "Copyleft Limited": "weak_copyleft",
            "Copyleft": "strong_copyleft", "Commercial": "not_open", "Proprietary Free": "not_open",
            "Source-available": "not_open", "Free Restricted": "not_open"}.get(cat, "unclassified"), cat
ORDER = ["permissive", "weak_copyleft", "strong_copyleft", "network_copyleft", "not_open", "unclassified"]
L = Licensing()
def ev(node, cats):
    if isinstance(node, LicenseWithExceptionSymbol):
        c, k = kcls(node.license_symbol.key); cats[k] += 1; return c
    if isinstance(node, LicenseSymbol):
        c, k = kcls(node.key); cats[k] += 1; return c
    vals = [ev(a, cats) for a in node.args]
    return max(vals, key=ORDER.index) if isinstance(node, AND) else min(vals, key=ORDER.index)
scan = json.load(open(sys.argv[1])); out = {}
cats = collections.Counter()
for f in scan["files"]:
    if f["type"] != "file": continue
    expr = f.get("detected_license_expression")
    out[f["path"].rsplit("/", 1)[-1]] = {"expression": (expr or "")[:300], "class": ev(L.parse(expr), cats) if expr else "unclassified"}
print(json.dumps({"by_package": out, "categories_seen": cats}, indent=1))
