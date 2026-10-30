"""Governed computer use: a real, isolated browser session driven step by step for a mission.

``browser.session`` extends the read-only ``browser.render`` route to multi-step work:
open -> navigate -> type/select/click/press/scroll -> inspect changed state -> extract
-> screenshot -> download, with evidence for every step. Structured (DOM) control comes
first; ``mouse`` steps (visual coordinates) exist for pages where selectors are not enough.

Mechanism: Playwright (Apache-2.0, maintained by Microsoft) driving the installed Chromium.
Each session gets a fresh, disposable profile; nothing persists between sessions.

Bounds enforced here, inside the authority office's single-action grant:

* **Network**: only the origins (host and port) the signed params name may be contacted: the
  start URL, absolute ``goto`` URLs on the signed hosts, and ``also_hosts`` (``host`` means
  port 443, ``host:port`` that port). Every other request and every other WebSocket is
  aborted and counted; a WebSocket is routed too, since ``context.route`` alone never sees
  one (measured 2026-10-14: a page's WebSocket reached an unlisted host, and a page on a
  loopback target reached the body's other loopback ports). The page is untrusted data,
  never instructions.
* **Confined egress (#26)**: on a body that confines egress, Chromium runs in a bubblewrap
  network namespace whose only way out is the body relay's door, allowlisted for exactly
  those origins; every connection, WebSockets included, is decided and journaled there,
  so the in-browser allowlist is no longer the only wall. Without namespaces nothing is
  launched.
* **Consequence**: a step marked ``consequential`` (submit an order, post, send, pay,
  accept terms, log in) is never executed by this capability. The session stops there
  with ``AUTHORITY_BOUNDARY`` and the evidence so far; doing it needs its own approved
  action (``consequence_class`` external_contact or above) through the Gate.
* **Credentials**: ``secret`` fills resolve only declared handles through the secret
  broker; an unprovisioned credential stops the session truthfully, it is never guessed.
* **Challenges**: CAPTCHA / bot challenges are detected and never solved. With
  ``on_challenge: skip`` the session records it and resumes at the next ``goto``.
* **Budget**: step count, per-step timeout and total wall time are capped.

Every step records the URL, title, a screenshot (PNG in the mission workspace) and their
SHA-256, plus a digest of the visible text, so the trace can be re-read later.
"""
from __future__ import annotations

import contextlib
import glob
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time
import urllib.parse

from greg.capabilities import CapabilityError, InvocationContext, _inside

OPS = ("goto", "fill", "type", "press", "click", "select", "check", "scroll", "wait_for", "expect_text",
       "extract", "extract_all", "screenshot", "download", "mouse")
MAX_STEPS = 40
STEP_TIMEOUT_MS = 20_000
SESSION_SECONDS = 300
CHALLENGE_MARKERS = ("client challenge", "captcha", "verify you are human", "are you a robot",
                     "unusual traffic", "attention required")
TRUST_BUNDLE_ENV = "GREG_BROWSER_TRUST_BUNDLE"
DEFAULT_PORTS = {"https": 443, "wss": 443, "http": 80, "ws": 80}
LOOPBACK = ("127.0.0.1", "localhost", "::1")


class BoundaryStop(Exception):
    def __init__(self, kind: str, why: str):
        super().__init__(why)
        self.kind, self.why = kind, why


def chromium() -> str:
    # Playwright's browser directory: chrome-linux/ in older builds, chrome-linux64/ in newer ones (chromium-1243,
    # Chrome for Testing 153, which Playwright 1.63 pins). Measured 2026-10-30: the older pattern alone found no
    # browser here, so the whole computer-use suite skipped even with Playwright installed.
    candidates = sorted(glob.glob("/opt/pw-browsers/chromium-*/chrome-linux*/chrome"))
    for path in candidates[::-1] + ["/usr/bin/chromium", "/usr/bin/chromium-browser", "/usr/bin/google-chrome"]:
        if os.access(path, os.X_OK):
            return path
    raise CapabilityError("no Chromium installed on this body")


def _trust_profile(home: Path) -> int:
    """Import an operator-configured CA bundle into this session's NSS store.

    Needed where the body's network uses TLS interception with a locally trusted CA.
    Verification stays ON; this only gives the disposable profile the same trust anchors
    the operating system already has. Returns the number of anchors imported.
    """
    bundle = os.environ.get(TRUST_BUNDLE_ENV)
    if not bundle or not Path(bundle).is_file():
        return 0
    certutil = "/usr/bin/certutil"
    if not os.access(certutil, os.X_OK):
        raise CapabilityError(f"{TRUST_BUNDLE_ENV} is set but certutil (libnss3-tools) is not installed")
    db = home / ".pki" / "nssdb"
    db.mkdir(parents=True)
    subprocess.run([certutil, "-N", "-d", f"sql:{db}", "--empty-password"], check=True, capture_output=True)
    pems = re.findall(r"-----BEGIN CERTIFICATE-----.+?-----END CERTIFICATE-----", Path(bundle).read_text(), re.S)
    for index, pem in enumerate(pems):
        subprocess.run([certutil, "-A", "-d", f"sql:{db}", "-n", f"anchor-{index}", "-t", "C,,"],
                       input=pem.encode(), check=True, capture_output=True)
    return len(pems)


def _origin(url: str) -> tuple[str, int] | None:
    """(host, port) a request or WebSocket would reach; None for anything that is not http(s)/ws(s)."""
    try:
        parts = urllib.parse.urlsplit(url)
        port = parts.port or DEFAULT_PORTS.get(parts.scheme)
    except ValueError:
        return None
    return ((parts.hostname or "").lower(), port) if port and parts.hostname else None


def _validate(params: dict) -> tuple[str, list[dict], set[str], set[tuple[str, int]]]:
    url = str(params.get("url", ""))
    parts = urllib.parse.urlsplit(url)
    host = parts.hostname or ""
    loopback = host in LOOPBACK
    if parts.scheme != "https" and not (parts.scheme == "http" and loopback):
        raise CapabilityError("browser.session starts on an https page (http only on loopback)")
    steps = params.get("steps")
    if not isinstance(steps, list) or not 1 <= len(steps) <= MAX_STEPS:
        raise CapabilityError(f"steps must be a list of 1..{MAX_STEPS} actions")
    for index, step in enumerate(steps):
        if not isinstance(step, dict) or step.get("op") not in OPS:
            raise CapabilityError(f"step {index}: op must be one of {OPS}")
    origins = {_origin(url)}
    for entry in params.get("also_hosts", []):
        name, _, port = str(entry).lower().rpartition(":") if ":" in str(entry) else (str(entry).lower(), "", "443")
        if not name or not port.isdigit() or not 0 < int(port) < 65536:
            raise CapabilityError(f"also_hosts entry {entry!r} is a host or host:port")
        origins.add((name, int(port)))
    hosts = {h for h, _ in origins}
    for step in steps:                      # an absolute goto on a signed host names its own port
        target = _origin(str(step.get("url", ""))) if step["op"] == "goto" and "://" in str(step.get("url", "")) else None
        if target and target[0] in hosts:
            origins.add(target)
    return url, steps, hosts, origins


def session(params: dict, ctx: InvocationContext) -> dict:
    """``browser.session``: run the signed step list in a disposable real browser and return the trace."""
    from playwright.sync_api import Error as PlaywrightError, sync_playwright

    url, steps, hosts, origins = _validate(params)
    confined = ctx.egress is not None
    if confined:
        from greg.worker_isolation import WorkerIsolationError, _backend
        try:
            _backend(require_bubblewrap=True)
        except WorkerIsolationError as exc:
            raise CapabilityError(f"confined egress needs bubblewrap network namespaces here: {exc}") from None
    name = re.sub(r"[^a-z0-9_.-]", "-", str(params.get("session", "session")).lower())[:60] or "session"
    trace_dir = _inside(ctx.workspace / "browser" / name, (ctx.workspace,))
    trace_dir.mkdir(parents=True, exist_ok=True)
    on_challenge = params.get("on_challenge", "stop")
    trace, extracted, blocked, blocked_sockets = [], {}, {}, {}
    status, boundary = "COMPLETED", None
    deadline = time.monotonic() + min(int(params.get("max_seconds", SESSION_SECONDS)), SESSION_SECONDS)
    # Chromium cannot sandbox itself as root on Linux, nor nest its own user namespace inside GREG's; reported below.
    sandboxed = not (sys.platform.startswith("linux") and os.geteuid() == 0) and not confined

    def allow(route):
        if _origin(route.request.url) in origins:
            return route.continue_()
        target = (urllib.parse.urlsplit(route.request.url).hostname or "").lower()
        blocked[target] = blocked.get(target, 0) + 1
        return route.abort()

    def allow_socket(ws):
        # Not connecting is the refusal: an unconnected routed WebSocket is answered inside the browser and never
        # opens a connection. (A synchronous close() here never returns: this handler runs on Playwright's loop.)
        if _origin(ws.url) in origins:
            ws.connect_to_server()
            return
        target = (urllib.parse.urlsplit(ws.url).hostname or "").lower()
        blocked_sockets[target] = blocked_sockets.get(target, 0) + 1

    with tempfile.TemporaryDirectory(prefix="greg-browser-session-") as home:
        home = Path(home)
        anchors = _trust_profile(home)
        binary = chromium()
        with contextlib.ExitStack() as stack:      # closes Playwright first, then the door (journals every stream)
            door = stack.enter_context(_door(ctx.egress, home, origins)) if confined else None
            launch = {"executable_path": binary, "args": [] if sandboxed else ["--no-sandbox"]}
            if door is not None:
                # The door is the namespace's own loopback and nothing else exists there to resolve or reach.
                launch = {"executable_path": _behind_door(home, binary, door),
                          "args": ["--no-sandbox", "--proxy-server={door}", "--proxy-bypass-list=<-loopback>",
                                   "--host-resolver-rules=MAP * ~NOTFOUND, EXCLUDE 127.0.0.1"]}
            pw = stack.enter_context(sync_playwright())
            browser = pw.chromium.launch(chromium_sandbox=sandboxed, downloads_path=str(home / "downloads"),
                                         env={"HOME": str(home), "PATH": "/usr/bin:/bin", "LANG": "C.UTF-8"},
                                         **launch)
            context = browser.new_context(accept_downloads=True, user_agent=params.get("user_agent"),
                                          viewport={"width": 1280, "height": 900})
            context.route("**/*", allow)
            context.route_web_socket(re.compile(".*"), allow_socket)
            page = context.new_page()
            page.set_default_timeout(STEP_TIMEOUT_MS)
            skipping = False
            try:
                page.goto(url, wait_until="domcontentloaded")
                trace.append(_evidence(page, trace_dir, 0, {"op": "open", "url": url}, "ok"))
                if _challenged(page):
                    if on_challenge != "skip":
                        raise BoundaryStop("CHALLENGE", "the site presented a bot challenge; GREG never solves "
                                                        "CAPTCHAs or challenges")
                    skipping = True
                    trace[-1]["result"] = "challenge_recorded"
                for index, step in enumerate(steps, start=1):
                    if time.monotonic() > deadline:
                        raise BoundaryStop("BUDGET", "session wall-time budget exhausted")
                    op = step["op"]
                    if skipping and op != "goto":
                        trace.append({"step": index, "op": op, "result": "skipped_after_challenge"})
                        continue
                    skipping = False
                    if step.get("consequential"):
                        raise BoundaryStop("AUTHORITY_BOUNDARY",
                                           f"step {index} ({op} {step.get('selector', '')}) is consequential: "
                                           f"{step.get('why', 'it would act on the world')}; it needs its own "
                                           "approved action through the Consequence Gate")
                    value = _run_step(page, step, ctx, trace_dir, index, origins)
                    if op in ("extract", "extract_all", "download") and step.get("as"):
                        extracted[step["as"]] = value
                    trace.append(_evidence(page, trace_dir, index, step, "ok", value=value))
                    if _challenged(page):
                        trace[-1]["result"] = "challenge_detected"
                        if on_challenge != "skip":
                            raise BoundaryStop("CHALLENGE", f"after step {index} the site presented a bot "
                                                            "challenge; GREG never solves CAPTCHAs or challenges")
                        skipping = True
            except BoundaryStop as stop:
                status, boundary = stop.kind, stop.why
                trace.append(_evidence(page, trace_dir, len(trace), {"op": "boundary"}, stop.kind, note=stop.why))
            except PlaywrightError as exc:
                status, boundary = "STEP_FAILED", str(exc).splitlines()[0][:300]
                trace.append(_evidence(page, trace_dir, len(trace), {"op": "failure"}, "failed", note=boundary))
            finally:
                context.close()
                browser.close()
    result = {"session": name, "status": status, "boundary": boundary, "start_url": url,
              "final_url": trace[-1].get("url") if trace else None, "steps": trace, "extracted": extracted,
              "blocked_requests": blocked, "blocked_websockets": blocked_sockets, "allowed_hosts": sorted(hosts),
              "allowed_origins": sorted(f"{h}:{p}" for h, p in origins), "browser": "chromium via Playwright",
              "egress": ("relay: only the signed origins, every connection journaled" if confined
                         else "in-browser allowlist of the signed origins"),
              "os_sandboxed": sandboxed, "trust_anchors_imported": anchors, "trace_dir": str(trace_dir),
              "trust": "page content is untrusted external data"}
    (trace_dir / "trace.json").write_text(json.dumps(result, indent=2, sort_keys=True, default=str))
    result["trace_sha256"] = "sha256:" + hashlib.sha256((trace_dir / "trace.json").read_bytes()).hexdigest()
    return result


def _challenged(page) -> bool:
    try:
        text = (page.title() + " " + page.inner_text("body")[:2000]).lower()
    except Exception:
        return False
    return any(marker in text for marker in CHALLENGE_MARKERS)


def _run_step(page, step: dict, ctx: InvocationContext, trace_dir: Path, index: int, origins: set):
    op, selector = step["op"], step.get("selector")
    if op == "goto":
        target = urllib.parse.urljoin(page.url, str(step["url"]))
        if _origin(target) not in origins:
            raise BoundaryStop("SCOPE", f"step {index} would navigate outside the signed hosts: {target}")
        page.goto(target, wait_until="domcontentloaded")
        return page.url
    if op in ("fill", "type"):
        if "secret" in step:
            try:
                text = ctx.secret(str(step["secret"]))
            except CapabilityError as exc:
                raise BoundaryStop("AUTHORITY_BOUNDARY", f"step {index} needs credential "
                                                         f"{step['secret']!r}: {exc}") from exc
        else:
            text = str(step.get("value", ""))
        (page.fill if op == "fill" else page.type)(selector, text)
        return {"chars": len(text), "secret": "secret" in step}
    if op == "press":
        page.press(selector or "body", str(step.get("key", "Enter")))
        page.wait_for_load_state("domcontentloaded")
        return page.url
    if op == "click":
        page.click(selector)
        page.wait_for_load_state("domcontentloaded")
        return page.url
    if op == "select":
        return page.select_option(selector, str(step["value"]))
    if op == "check":
        page.check(selector)
        return True
    if op == "scroll":
        page.mouse.wheel(0, int(step.get("dy", 800)))
        return int(step.get("dy", 800))
    if op == "wait_for":
        page.wait_for_selector(selector)
        return True
    if op == "expect_text":
        text = page.inner_text(selector or "body")
        if str(step["value"]) not in text:
            raise BoundaryStop("EXPECTATION_FAILED", f"step {index}: expected text {step['value']!r} not present")
        return True
    if op == "extract":
        return page.inner_text(selector).strip()[:4000]
    if op == "extract_all":
        limit = min(int(step.get("limit", 50)), 200)
        return [t.strip()[:500] for t in page.locator(selector).all_inner_texts()[:limit]]
    if op == "screenshot":
        return None  # every step already records one
    if op == "download":
        with page.expect_download() as info:
            page.click(selector)
        download = info.value
        path = trace_dir / re.sub(r"[^A-Za-z0-9_.-]", "_", download.suggested_filename)[:120]
        download.save_as(path)
        data = path.read_bytes()
        return {"path": str(path), "bytes": len(data), "sha256": "sha256:" + hashlib.sha256(data).hexdigest()}
    if op == "mouse":  # visual route: explicit coordinates when selectors are not enough
        page.mouse.click(float(step["x"]), float(step["y"]))
        page.wait_for_load_state("domcontentloaded")
        return {"x": step["x"], "y": step["y"]}
    raise CapabilityError(f"unsupported op {op}")


def _door(relay, home: Path, origins: set):
    """A door to a per-session relay that shares the body relay's journal and mandated proxy and allows exactly the
    signed origins; it listens in the session's private directory because Playwright's driver starts Chromium."""
    from foundry.systems.relay_door import Door
    from foundry.systems.segmentation import Relay
    scoped = Relay({"browser.session": {"allow": sorted([h, p] for h, p in origins),
                                        "external": any(h not in LOOPBACK for h, _ in origins)}},
                   relay.journal, connect=relay.connect, proxy=relay.proxy)
    return Door(scoped, "browser.session", path=home / "door.sock")


def _behind_door(home: Path, binary: str, door) -> str:
    """The executable Playwright launches: Chromium in a bubblewrap network namespace (no privilege), the door in front.
    Playwright's pipe (descriptors 3 and 4) is all of the launcher's that reaches Chromium."""
    import shlex
    from foundry.systems.relay_door import door_argv, namespace_argv
    # Playwright's per-launch profile lives in the scratch roots, private to the namespace.
    from foundry.systems.relay_door import SCRATCH_ROOTS
    namespace = namespace_argv(writable=[home], readonly=[str(Path(binary).resolve().parent)], chdir=home,
                               tmp_roots=(*SCRATCH_ROOTS, tempfile.gettempdir()))
    command = namespace + door_argv(sys.executable, door.control, [binary], keep_fds=(3, 4))
    launcher = home / "chromium-behind-door"
    launcher.write_text("#!/bin/sh\nexec " + " ".join(shlex.quote(a) for a in command) + ' "$@"\n')
    launcher.chmod(0o700)
    return str(launcher)


def _evidence(page, trace_dir: Path, index: int, step: dict, result: str, *, value=None, note: str = "") -> dict:
    record = {"step": index, "op": step.get("op"), "selector": step.get("selector"), "result": result,
              "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    try:
        record["url"], record["title"] = page.url, page.title()[:200]
        text = page.inner_text("body")
        record["text_sha256"] = "sha256:" + hashlib.sha256(text.encode()).hexdigest()
        shot = trace_dir / f"step-{index:02d}.png"
        page.screenshot(path=str(shot))
        record["screenshot"] = {"path": str(shot), "sha256": "sha256:" + hashlib.sha256(shot.read_bytes()).hexdigest()}
    except Exception as exc:                     # the evidence gap itself is evidence
        record["evidence_error"] = str(exc).splitlines()[0][:200]
    if value is not None:
        record["value"] = value if not isinstance(value, str) else value[:1000]
    if note:
        record["note"] = note[:400]
    return record


def session_status(params: dict, ctx: InvocationContext) -> dict:
    """``browser.trace`` (read-only sensor): re-read a retained session trace and re-hash its screenshots."""
    name = re.sub(r"[^a-z0-9_.-]", "-", str(params.get("session", "session")).lower())[:60] or "session"
    trace_file = _inside(ctx.workspace / "browser" / name / "trace.json", (ctx.workspace,))
    if not trace_file.is_file():
        return {"session": name, "present": False}
    trace = json.loads(trace_file.read_text())
    intact = all(Path(s["screenshot"]["path"]).is_file() and "sha256:" + hashlib.sha256(
        Path(s["screenshot"]["path"]).read_bytes()).hexdigest() == s["screenshot"]["sha256"]
        for s in trace["steps"] if s.get("screenshot"))
    return {"session": name, "present": True, "status": trace["status"], "boundary": trace.get("boundary"),
            "steps": len(trace["steps"]), "screenshots_intact": intact, "extracted": trace.get("extracted", {}),
            "extracted_keys": sorted(trace.get("extracted", {})), "final_url": trace.get("final_url"),
            "blocked_requests": trace.get("blocked_requests", {})}
