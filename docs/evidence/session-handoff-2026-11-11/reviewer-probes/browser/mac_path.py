import json, os, sys, tempfile
from pathlib import Path
sys.path.insert(0, os.getcwd())
from greg import capabilities
from greg.capabilities import BUILTINS, InvocationContext, browser_render
tmp = Path(tempfile.mkdtemp(prefix="adv-br-mac-"))
mac = tmp / "Applications" / "Google Chrome.app" / "Contents" / "MacOS" / "Google Chrome"
mac.parent.mkdir(parents=True)
mac.write_text("#!/bin/sh\nprintf '%s\\n' \"$#\" >> '" + str(tmp) + "/argc'\necho '<html><title>t</title><p>greg-renders-42</p><p>mac page</p></html>'\n"); mac.chmod(0o755)
capabilities.CHROME_CANDIDATES = (str(mac),); capabilities.HEADLESS_SHELL_CANDIDATES = (); capabilities.PLAYWRIGHT_BROWSERS = str(tmp / "none")
m = BUILTINS["browser.render"][0]
out = browser_render({"url": "http://127.0.0.1:9/x"}, InvocationContext(workspace=tmp, read_roots=(), secrets=None, manifest=m))
print(json.dumps({"chosen": capabilities.chrome_binary().replace(str(tmp), ""), "browser_field": out["browser"], "text": out["text"],
                  "arg_counts(check, render)": (tmp / "argc").read_text().split()}))
