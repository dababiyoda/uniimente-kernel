"""The memory of a judged binary: two renders at once, a symlink whose target changes, a wrapper whose real binary
changes, the same size and mtime, and growth. Stand-ins only."""
import json, os, shutil, stat, sys, tempfile, threading, time
from pathlib import Path
sys.path.insert(0, os.getcwd())
from greg import capabilities
capabilities.RENDER_SECONDS = 2
tmp = Path(tempfile.mkdtemp(prefix="adv-br-mem-"))
PAGE = "<html><p>greg-renders-42</p></html>"
def script(path, body):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"#!/bin/sh\necho run >> '{path}.runs'\n{body}\n"); path.chmod(0o755); return str(path)
def runs(p):
    q = Path(str(p) + ".runs"); return len(q.read_text().splitlines()) if q.exists() else 0
out = {}

# 1. two renders at once judge the same binary twice (no lock); and a hanging one costs each caller its own timeout
slow = script(tmp / "slow", f"sleep 1; echo '{PAGE}'")
res = []
ts = [threading.Thread(target=lambda: res.append(capabilities.cannot_render(slow))) for _ in range(2)]
t = time.monotonic(); [x.start() for x in ts]; [x.join() for x in ts]
out["two_renders_at_once"] = {"check_runs": runs(slow), "results": res, "seconds": round(time.monotonic() - t, 1)}

# 2. a symlinked binary whose target changes (different size): judged again?
a = script(tmp / "a" / "chrome", f"echo '{PAGE}'"); b = script(tmp / "b" / "chrome", "echo broken >&2; exit 3  # new build")
link = tmp / "link-chrome"; os.symlink(a, link)
first = capabilities.cannot_render(str(link)); os.unlink(link); os.symlink(b, link)
second = capabilities.cannot_render(str(link))
out["symlink_retargeted"] = {"first": first, "after_retarget": second, "rejudged": runs(b) == 1}

# 3. a wrapper script that execs the real binary (as /usr/bin/google-chrome and this container's headless shell do):
real = script(tmp / "opt" / "chrome.real", f"echo '{PAGE}'")
wrapper = tmp / "usr-bin-chrome"; wrapper.write_text(f"#!/bin/sh\nexec '{real}' \"$@\"\n"); wrapper.chmod(0o755)
first = capabilities.cannot_render(str(wrapper))
script(tmp / "opt" / "chrome.real", "sleep 30")                      # the real browser is upgraded to one that hangs
t = time.monotonic(); second = capabilities.cannot_render(str(wrapper)); took = round(time.monotonic() - t, 2)
out["wrapper_real_binary_replaced"] = {"first": first, "after_replacement": second, "seconds": took,
                                      "note": "None means the remembered success was returned without running it"}

# 4. a replacement with the same size and the same mtime (cp -p of another build, or a restore from backup)
x = script(tmp / "same" / "chrome", f"echo '{PAGE}'  # A")
st = os.stat(x); first = capabilities.cannot_render(x)
Path(x).write_text(Path(x).read_text().replace("echo '", "exit 9 #'").ljust(st.st_size)[:st.st_size]); os.utime(x, ns=(st.st_atime_ns, st.st_mtime_ns))
out["same_size_same_mtime"] = {"size_equal": os.stat(x).st_size == st.st_size, "first": first, "after": capabilities.cannot_render(x)}

# 5. growth: one entry per (path, size, mtime) ever judged; nothing is removed
before = len(capabilities._render_judged)
g = script(tmp / "grow" / "chrome", f"echo '{PAGE}'")
for i in range(20):
    Path(g).write_text(Path(g).read_text() + f"# build {i}\n"); capabilities.cannot_render(g)
out["growth"] = {"entries_added_by_20_reinstalls_of_one_path": len(capabilities._render_judged) - before}
print(json.dumps(out, indent=1))
