"""Governed computer use: a real, isolated browser session driven step by step for a mission.

``browser.session`` extends the read-only ``browser.render`` route to multi-step work:
open -> navigate -> type/select/click/press/scroll -> inspect changed state -> extract
-> screenshot -> download, with evidence for every step. Structured (DOM) control comes
first; ``mouse`` steps (visual coordinates) exist for pages where selectors are not enough.

Mechanism: Playwright (Apache-2.0, maintained by Microsoft) driving the installed Chromium.
Each session gets a fresh, disposable profile; nothing persists between sessions.

Bounds enforced here, inside the authority office's single-action grant:

* **Network**: only the founder-signed target host (``web:<host>``) and hosts the signed
  params name in ``also_hosts`` may be contacted; every other request is aborted and
  counted. The page is untrusted data, never instructions.
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


class BoundaryStop(Exception):
    def __init__(self, kind: str, why: str):
        super().__init__(why)
        self.kind, self.why = kind, why


def chromium() -> str:
    candidates = sorted(glob.glob("/opt/pw-browsers/chromium-*/chrome-linux/chrome"))
    for path in candidates[::-1] + ["/usr/bin/chromium", "/usr/bin/chromium-browser", "/usr/bin/google-chrome"]:
        if os.access(path, os.X_OK):
            return path
    raise CapabilityError("no Chromium installed on this body")


def computer_use_ready() -> dict:
    """Report, read-only, whether this body has what ``browser.session`` needs.

    Checks the Playwright package, a Chromium binary and certutil without importing
    Playwright's driver, launching a browser or running any subprocess.
    """
    import importlib.util
    try:
        playwright = importlib.util.find_spec("playwright") is not None
    except (ImportError, ValueError):
        playwright = False
    try:
        chromium_path = chromium()
    except CapabilityError:
        chromium_path = None
    certutil = os.access("/usr/bin/certutil", os.X_OK)
    return {"ready": playwright and chromium_path is not None and certutil,
            "playwright": playwright, "chromium": chromium_path, "certutil": certutil}


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


def _validate(params: dict) -> tuple[str, list[dict], set[str]]:
    url = str(params.get("url", ""))
    parts = urllib.parse.urlsplit(url)
    host = parts.hostname or ""
    loopback = host in ("127.0.0.1", "localhost", "::1")
    if parts.scheme != "https" and not (parts.scheme == "http" and loopback):
        raise CapabilityError("browser.session starts on an https page (http only on loopback)")
    steps = params.get("steps")
    if not isinstance(steps, list) or not 1 <= len(steps) <= MAX_STEPS:
        raise CapabilityError(f"steps must be a list of 1..{MAX_STEPS} actions")
    for index, step in enumerate(steps):
        if not isinstance(step, dict) or step.get("op") not in OPS:
            raise CapabilityError(f"step {index}: op must be one of {OPS}")
    hosts = {host} | {str(h).lower() for h in params.get("also_hosts", [])}
    return url, steps, hosts


def session(params: dict, ctx: InvocationContext) -> dict:
    """``browser.session``: run the signed step list in a disposable real browser and return the trace."""
    from playwright.sync_api import Error as PlaywrightError, sync_playwright

    url, steps, hosts = _validate(params)
    name = re.sub(r"[^a-z0-9_.-]", "-", str(params.get("session", "session")).lower())[:60] or "session"
    trace_dir = _inside(ctx.workspace / "browser" / name, (ctx.workspace,))
    trace_dir.mkdir(parents=True, exist_ok=True)
    on_challenge = params.get("on_challenge", "stop")
    trace, extracted, blocked = [], {}, {}
    status, boundary = "COMPLETED", None
    deadline = time.monotonic() + min(int(params.get("max_seconds", SESSION_SECONDS)), SESSION_SECONDS)
    sandboxed = not (sys.platform.startswith("linux") and os.geteuid() == 0)

    def allow(route):
        target = (urllib.parse.urlsplit(route.request.url).hostname or "").lower()
        if target in hosts:
            return route.continue_()
        blocked[target] = blocked.get(target, 0) + 1
        return route.abort()

    with tempfile.TemporaryDirectory(prefix="greg-browser-session-") as home:
        home = Path(home)
        anchors = _trust_profile(home)
        with sync_playwright() as pw:
            browser = pw.chromium.launch(executable_path=chromium(), chromium_sandbox=sandboxed,
                                         args=[] if sandboxed else ["--no-sandbox"],
                                         env={"HOME": str(home), "PATH": "/usr/bin:/bin", "LANG": "C.UTF-8"})
            context = browser.new_context(accept_downloads=True, user_agent=params.get("user_agent"),
                                          viewport={"width": 1280, "height": 900})
            context.route("**/*", allow)
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
                    value = _run_step(page, step, ctx, trace_dir, index, hosts)
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
              "blocked_requests": blocked, "allowed_hosts": sorted(hosts), "browser": "chromium via Playwright",
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


def _run_step(page, step: dict, ctx: InvocationContext, trace_dir: Path, index: int, hosts: set[str]):
    op, selector = step["op"], step.get("selector")
    if op == "goto":
        target = urllib.parse.urljoin(page.url, str(step["url"]))
        if (urllib.parse.urlsplit(target).hostname or "").lower() not in hosts:
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
