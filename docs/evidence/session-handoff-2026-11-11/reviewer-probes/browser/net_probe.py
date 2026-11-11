"""Run the real headless shell through cannot_render with a listener on the check's proxy address (127.0.0.1:9)
and a catch-all listener; report every accepted connection and its first bytes."""
import json, os, socket, sys, threading, time
sys.path.insert(0, os.getcwd())
from greg import capabilities

hits = []
def listen(port):
    s = socket.socket(); s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(("127.0.0.1", port)); s.listen(50)
    def loop():
        while True:
            try:
                c, addr = s.accept()
            except OSError:
                return
            c.settimeout(2)
            try:
                data = c.recv(400)
            except Exception as exc:
                data = repr(exc).encode()
            hits.append({"port": port, "from": addr, "first_bytes": data[:200].decode("latin1")})
            c.close()
    threading.Thread(target=loop, daemon=True).start()
    return s

s9 = listen(9)
os.environ["GREG_SECRET_FOR_PROBE"] = "must-not-reach-the-browser"
os.environ["HTTPS_PROXY"] = os.environ.get("HTTPS_PROXY", "http://127.0.0.1:1")
binary = sys.argv[1]
t = time.monotonic()
why = capabilities.cannot_render(binary)
print(json.dumps({"binary": binary, "cannot_render": why, "seconds": round(time.monotonic() - t, 2),
                  "connections_to_127.0.0.1:9": hits}, indent=1))
