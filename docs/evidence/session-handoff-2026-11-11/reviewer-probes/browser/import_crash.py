"""playwright_builds() parses the build number with str.isdigit() then int(). isdigit() is True for characters
int() refuses (superscripts). The listing is read at import (BUILTINS -> installed_chrome()). glob.glob is replaced
before the import so the listing contains one such directory name; nothing on disk is touched."""
import glob, json, os, sys
sys.path.insert(0, os.getcwd())
real = glob.glob
ODD = "/opt/pw-browsers/chromium_headless_shell-1243²/chrome-headless-shell-linux64/chrome-headless-shell"
def listing(pattern, *a, **k):
    found = real(pattern, *a, **k)
    return found + [ODD] if "chromium_headless_shell-*" in pattern else found
glob.glob = listing
try:
    import greg.capabilities as c
    print(json.dumps({"import": "ok", "candidates": c.chrome_candidates()[:2]}))
except Exception as exc:
    print(json.dumps({"import greg.capabilities": f"{type(exc).__name__}: {exc}"}))
