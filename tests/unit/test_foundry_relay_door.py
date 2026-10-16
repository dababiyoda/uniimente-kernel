"""#26 relay door: a program in a bubblewrap network namespace reaches allowlisted hosts only through the body relay."""
import http.server
import json
import shutil
import socket
import subprocess
import sys
import threading

import pytest

from foundry.systems.relay_door import Door, door_argv
from foundry.systems.segmentation import Journal, Relay


def _netns():
    bwrap = shutil.which("bwrap")
    if not bwrap or not sys.platform.startswith("linux"):
        return None
    probe = subprocess.run([bwrap, "--unshare-user", "--unshare-net", "--ro-bind", "/", "/", "--", "/usr/bin/true"],
                           capture_output=True, timeout=10)
    return bwrap if probe.returncode == 0 else None


BWRAP = _netns()
pytestmark = pytest.mark.skipif(BWRAP is None, reason="bubblewrap network namespaces unavailable on this host")


@pytest.fixture
def upstream():
    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            body = json.dumps({"path": self.path, "host": self.headers.get("Host")}).encode()
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *a):
            pass
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield server.server_address[1]
    server.shutdown()


def confined(door, program):
    argv = [BWRAP, "--unshare-user", "--unshare-pid", "--unshare-net", "--die-with-parent", "--ro-bind", "/", "/",
            "--proc", "/proc", "--dev", "/dev", "--", *door_argv(sys.executable, door.fd, program)]
    return subprocess.run(argv, pass_fds=[door.fd], capture_output=True, text=True, timeout=60)


CLIENT = r'''
import json, os, socket, sys, urllib.request
up = int(sys.argv[1])
out = {}
opener = urllib.request.build_opener(urllib.request.ProxyHandler({"http": os.environ["HTTP_PROXY"]}))
out["allowed"] = json.loads(opener.open("http://127.0.0.1:%d/hello" % up, timeout=10).read())
try:
    opener.open("http://127.0.0.1:%d/other-port" % (up + 1), timeout=10)
    out["denied"] = "REACHED"
except Exception as exc:
    out["denied"] = str(exc)[:120]
port = int(os.environ["HTTPS_PROXY"].rsplit(":", 1)[1])
s = socket.create_connection(("127.0.0.1", port))
s.sendall(b"CONNECT example.com:443 HTTP/1.1\r\nHost: example.com:443\r\n\r\n")
out["connect_undeclared"] = s.recv(200).split(b"\r\n")[0].decode()
for target in (("127.0.0.1", up), ("1.1.1.1", 443)):
    try:
        socket.create_connection(target, timeout=2)
        out["direct_" + target[0]] = "REACHED"
    except OSError as exc:
        out["direct_" + target[0]] = type(exc).__name__
out["argv_door"] = sys.argv[2]
print(json.dumps(out))
'''


def test_a_program_in_the_namespace_reaches_only_its_allowlist_and_every_decision_is_journaled(tmp_path, upstream):
    journal = Journal(tmp_path / "egress.jsonl")
    relay = Relay({"browser.render": {"allow": [["127.0.0.1", upstream]], "external": False}}, journal)
    with Door(relay, "browser.render") as door:
        run = confined(door, [sys.executable, "-c", CLIENT, str(upstream), "--proxy-server={door}"])
    assert run.returncode == 0, run.stderr[-800:]
    out = json.loads(run.stdout)
    assert out["allowed"] == {"path": "/hello", "host": f"127.0.0.1:{upstream}"}   # absolute-form became origin-form
    assert "403" in out["denied"] and out["connect_undeclared"].startswith("HTTP/1.1 403")
    assert out["direct_127.0.0.1"] == "ConnectionRefusedError"           # the body's loopback is not this loopback
    assert out["direct_1.1.1.1"] in ("OSError", "ConnectionRefusedError", "TimeoutError")
    assert out["argv_door"].startswith("--proxy-server=http://127.0.0.1:")
    entries = journal.read()
    denied = {(e["host"], e["port"]) for e in entries if e.get("verdict") == "DENIED"}
    assert denied == {("example.com", 443), ("127.0.0.1", upstream + 1)}
    allowed = [e for e in entries if e.get("verdict") == "ALLOWED"]
    assert len(allowed) == 1 and allowed[0]["bytes_received"] > 0
    assert journal.verify()["intact"]


def test_without_the_door_the_namespace_has_no_network_at_all(tmp_path, upstream):
    """The program ignoring its proxy settings is the program having no network: nothing to bypass."""
    relay = Relay({}, Journal(tmp_path / "egress.jsonl"))
    with Door(relay, "nobody") as door:
        run = confined(door, [sys.executable, "-c",
                              "import socket,sys\ntry:\n socket.create_connection(('127.0.0.1', %d), timeout=2)\n"
                              " print('REACHED')\nexcept OSError as e:\n print(type(e).__name__)" % upstream])
    assert run.stdout.strip() == "ConnectionRefusedError"


def test_the_door_refuses_a_program_argv_that_is_not_strings():
    with pytest.raises(ValueError):
        door_argv(sys.executable, 3, [])
    with pytest.raises(ValueError):
        door_argv(sys.executable, 3, ["ok", 5])


KEEPER = r'''
import json, os, sys
kept, stray = int(sys.argv[1]), int(sys.argv[2])
out = {"kept": os.read(kept, 64).decode()}
try:
    os.fstat(stray)
    out["other"] = "INHERITED"
except OSError:
    out["other"] = "closed"
print(json.dumps(out))
'''


def test_a_door_on_a_path_serves_a_program_another_launcher_started_and_keeps_only_its_descriptors(tmp_path, upstream):
    """Playwright's driver, not the body, starts Chromium: no body descriptor survives that way. The door then reaches
    the relay over a one-time Unix socket in a private directory, and the program keeps only the launcher's pipe."""
    import os
    private = tmp_path / "private"
    private.mkdir(mode=0o700)
    journal = Journal(tmp_path / "egress.jsonl")
    relay = Relay({"browser.session": {"allow": [["127.0.0.1", upstream]], "external": False}}, journal)
    read, write = os.pipe()
    stray_read, stray_write = os.pipe()              # stands for anything else of the launcher's: must not arrive
    os.write(write, b"from the launcher")
    os.close(write)
    with Door(relay, "browser.session", path=private / "door.sock") as door:
        assert door.control == f"unix:{private / 'door.sock'}"
        with pytest.raises(ValueError):
            door.fd
        argv = [BWRAP, "--unshare-user", "--unshare-pid", "--unshare-net", "--die-with-parent", "--ro-bind", "/", "/",
                "--proc", "/proc", "--dev", "/dev", "--bind", str(private), str(private), "--",
                *door_argv(sys.executable, door.control, [sys.executable, "-c", KEEPER, str(read), str(stray_read)],
                           keep_fds=[read])]
        run = subprocess.run(argv, pass_fds=[read, stray_read], capture_output=True, text=True, timeout=60)
    assert run.returncode == 0, run.stderr[-800:]
    out = json.loads(run.stdout)
    assert out == {"kept": "from the launcher", "other": "closed"}   # the launcher's other descriptors stay out
    assert not (private / "door.sock").exists()            # one connection, then the path is gone
    for fd in (read, stray_read, stray_write):
        os.close(fd)


def test_a_door_on_a_path_serves_one_program_and_lets_it_reach_only_its_allowlist(tmp_path, upstream):
    private = tmp_path / "private"
    private.mkdir(mode=0o700)
    journal = Journal(tmp_path / "egress.jsonl")
    relay = Relay({"browser.session": {"allow": [["127.0.0.1", upstream]], "external": False}}, journal)
    with Door(relay, "browser.session", path=private / "door.sock") as door:
        argv = [BWRAP, "--unshare-user", "--unshare-pid", "--unshare-net", "--die-with-parent", "--ro-bind", "/", "/",
                "--proc", "/proc", "--dev", "/dev", "--bind", str(private), str(private), "--",
                *door_argv(sys.executable, door.control, [sys.executable, "-c", CLIENT, str(upstream), "x"])]
        run = subprocess.run(argv, capture_output=True, text=True, timeout=60)
    assert run.returncode == 0, run.stderr[-800:]
    out = json.loads(run.stdout)
    assert out["allowed"]["path"] == "/hello" and "403" in out["denied"]
    assert {e["identity"] for e in journal.read()} == {"browser.session"} and journal.verify()["intact"]


def test_a_door_path_must_sit_in_a_directory_private_to_the_body(tmp_path):
    shared = tmp_path / "shared"
    shared.mkdir(mode=0o755)
    shared.chmod(0o755)
    with pytest.raises(ValueError):
        Door(Relay({}, Journal(tmp_path / "egress.jsonl")), "x", path=shared / "door.sock")


def test_a_door_refuses_kept_descriptors_that_are_standard_streams():
    with pytest.raises(ValueError):
        door_argv(sys.executable, 3, ["ok"], keep_fds=[2])
