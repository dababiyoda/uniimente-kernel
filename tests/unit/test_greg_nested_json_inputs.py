"""A JSON document nested too deep for ``json.loads`` is malformed input, never an exception out of the body.

``json.loads`` raises ``RecursionError`` (not ``ValueError``) on a document nested past the interpreter's recursion
limit, and every read below caught only ``ValueError``. The independent re-check of 8f72ceff (N3) found the one this
unit introduced: a 30 KB inbox file of nested brackets made the revocation pre-read raise, so a paused body could no
longer apply the founder's BODY_RESUME (it stayed paused) and every greg serve route answered 500. The same class
was present in four other reads of input GREG does not control: the inbox file a running body applies, the signed
commands' digests the morning report reads, a file in the data plane's intake (untrusted by design), and a command
posted to greg serve. Each now treats such a document as malformed, as it treats any other text that is not JSON.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json

from greg import remote
from greg.body import Body, inbox_digests, Layout, send_signed
from greg.founder import sign_command, sign_read
from tests.greg_fixtures import make_body

NESTED = "[" * 15000 + "]" * 15000          # 30 KB: under every size limit, deeper than json.loads can recurse
# json.loads reads this one without error; the value then raises RecursionError wherever it is hashed or printed
DEEP_OBJECT = '{"a":' * 15000 + "1" + "}" * 15000


def test_a_paused_body_sets_the_nested_file_aside_and_applies_the_founders_resume(tmp_path):
    home, key, body_id, _ = make_body(tmp_path)
    with Body(home) as body:
        body.apply(sign_command(key, "BODY_PAUSE", {}, body_id=body_id))
    (home / "inbox" / "0000-nested.json").write_text(NESTED)
    send_signed(home, key, "BODY_RESUME", {})
    with Body(home) as body:
        body.tick()
        assert not body.paused()
    assert not list((home / "inbox").glob("*.json"))


def test_a_running_body_refuses_the_nested_file_and_keeps_ticking(tmp_path):
    home, key, body_id, _ = make_body(tmp_path)
    (home / "inbox" / "0000-nested.json").write_text(NESTED)
    with Body(home) as body:
        body.tick()
        rejected = [e.payload for e in body.journal.replay("command.rejected")]
        body.tick()
    assert [r["file"] for r in rejected] == ["0000-nested.json"]
    assert "nested too deeply" in rejected[0]["reason"]
    assert not list((home / "inbox").glob("*.json"))


def test_greg_serve_keeps_answering_the_founder_with_a_nested_file_waiting(tmp_path):
    home, key, body_id, _ = make_body(tmp_path)
    with Body(home) as body:
        body.tick()
    (home / "inbox" / "0000-nested.json").write_text(NESTED)
    for route in ("/api/status", "/api/decisions", "/api/commands"):
        now = datetime.now(timezone.utc)
        answer = remote.handle(home, "GET", route, sign_read(key, body_id=body_id, method="GET", path=route, now=now),
                               b"", now=now)
        assert answer[0] == 200, (route, answer)
    stop = json.dumps(sign_command(key, "BODY_STOP", {}, body_id=body_id)).encode()
    assert remote.handle(home, "POST", "/api/command", {}, stop)[0] == 202
    assert inbox_digests(Layout(home)) != set()          # the founder's command is read; the nested file is not


def test_a_nested_command_posted_to_greg_serve_is_refused_as_not_json(tmp_path):
    home, key, body_id, _ = make_body(tmp_path)
    try:
        remote.handle(home, "POST", "/api/command", {}, NESTED.encode())
    except remote.RemoteError as exc:
        assert (exc.status, str(exc)) == (400, "command must be JSON")
    else:
        raise AssertionError("a nested body was accepted")


def test_a_nested_intake_file_is_refused_as_not_json_and_the_body_keeps_ticking(tmp_path):
    home, key, body_id, _ = make_body(tmp_path)
    layout = Layout(home)
    layout.intake.mkdir(parents=True, exist_ok=True)
    (layout.intake / "deep.json").write_text(NESTED)
    with Body(home) as body:
        body.tick()
        refused = [e.payload for e in body.journal.replay("external.intake_refused")]
    assert [(r["file"], r["why"]) for r in refused] == [("deep.json", "not JSON")]
    assert not (layout.intake / "deep.json").exists()


# ---------------------------------------------- re-check of 48d66f5f, F2: the same class in four more readers
def test_a_worker_report_nested_too_deep_is_no_claim():
    from greg import workers
    assert workers._parse_claim(f"{workers.REPORT_MARK} {NESTED}") is None


def test_an_organ_signal_nested_too_deep_is_refused_as_not_json(tmp_path):
    import pytest
    from greg import organ_exchange
    from greg.capabilities import CapabilityError
    path = tmp_path / "signal.json"
    path.write_text(NESTED)
    with pytest.raises(CapabilityError, match="not JSON"):
        organ_exchange._signal(path)


def test_a_nested_ollama_answer_is_bad_output(tmp_path):
    """greg/models.py reads Ollama's answer over loopback; a nested one is BAD_OUTPUT, never an unknown outcome.
    Served by a real local HTTP server (re-check of bdfca22d, L3: the source-text check this replaces passed for any
    function that merely named the exception)."""
    import http.server
    import threading
    import pytest
    from greg import models

    class Deep(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            body = DEEP_OBJECT.encode()
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Deep)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        with pytest.raises(models.RouteError, match="invalid JSON") as raised:
            models.OllamaRoute("m", port=server.server_address[1])._request("GET", "/api/tags")
        assert raised.value.kind == models.BAD_OUTPUT
    finally:
        server.shutdown()


def test_a_nested_claude_code_report_is_no_report():
    from types import SimpleNamespace
    from greg import models
    assert models.cli_report(SimpleNamespace(stdout=NESTED)) is None
    assert models.cli_report(SimpleNamespace(stdout=DEEP_OBJECT)) is None


def test_the_mcp_client_answer_is_read_by_the_untrusted_reader():
    """greg/mcp_tools.py's remote call reads the client's last line; a nested one is the client failing."""
    import inspect
    from greg import mcp_tools
    source = inspect.getsource(mcp_tools._remote_act)
    assert "untrusted_json.loads(done.stdout" in source and "json.loads(done.stdout" not in source.replace(
        "untrusted_json.loads(done.stdout", "")


# ---------------------------------------------- re-check of 48d66f5f, F3: an inbox entry that is not a regular file
def test_a_fifo_in_the_inbox_never_holds_the_tick(tmp_path):
    """A FIFO named *.json with no writer held a plain read forever: the tick never ended and the BODY_STOP or
    BODY_RESUME behind it was never read. It now raises at once, as a directory named *.json always did: a running
    body exits on it for the crash-loop breaker to count, and a paused body sets it aside and reads on."""
    import os
    import threading
    home, key, body_id, _ = make_body(tmp_path)
    with Body(home) as body:
        body.apply(sign_command(key, "BODY_PAUSE", {}, body_id=body_id))
    os.mkfifo(home / "inbox" / "0000-fifo.json")
    send_signed(home, key, "BODY_RESUME", {})
    done = {}

    def run():
        with Body(home) as body:
            body.tick()
            done["paused"] = body.paused()
    worker = threading.Thread(target=run, daemon=True)
    worker.start()
    worker.join(30)
    assert not worker.is_alive(), "the tick waited on the FIFO"
    assert done == {"paused": False}
    assert (home / "inbox" / "faulted" / "0000-fifo.json").exists()


# ---------------------------------------------- re-check of bdfca22d
def test_the_untrusted_reader_refuses_both_shapes_and_reads_ordinary_json():
    import pytest
    from greg import untrusted_json
    for doc in (NESTED, DEEP_OBJECT, NESTED.encode(), "[" * 201 + "]" * 201):
        with pytest.raises(untrusted_json.TooDeep):
            untrusted_json.loads(doc)
    assert untrusted_json.loads("[" * 200 + "]" * 200) is not None
    assert untrusted_json.loads('{"a": [1, {"b": null}]}') == {"a": [1, {"b": None}]}
    assert issubclass(untrusted_json.TooDeep, json.JSONDecodeError)


def test_a_deep_object_in_the_inbox_is_refused_and_the_body_keeps_ticking(tmp_path):
    """Both shapes are refused: one json.loads cannot read, and one it reads but deeper than MAX_DEPTH."""
    from greg.untrusted_json import MAX_DEPTH
    home, key, body_id, _ = make_body(tmp_path)
    (home / "inbox" / "0000-deep.json").write_text(DEEP_OBJECT)
    (home / "inbox" / "0001-deep.json").write_text('{"a":' * (MAX_DEPTH + 1) + "1" + "}" * (MAX_DEPTH + 1))
    with Body(home) as body:
        body.tick()
        rejected = [e.payload for e in body.journal.replay("command.rejected")]
        body.tick()
    assert [r["file"] for r in rejected] == ["0000-deep.json", "0001-deep.json"]
    assert all(r["reason"].startswith("TooDeep") for r in rejected)


def test_a_built_candidate_printing_a_nested_document_is_unreadable_output(tmp_path):
    """M3: a model-built candidate passes screen() and prints a nested array at import; execute and verify raised
    RecursionError, outside the gate's containment, and the kept candidate repeated it on restart."""
    import pytest
    from greg import builders
    from greg.capabilities import CapabilityError
    for document in ('"[" * 15000 + "]" * 15000', '\'{"a":\' * 15000 + "1" + "}" * 15000'):
        source = f"print({document}, end='')\ndef run(text):\n    return text\n"
        assert builders.screen(source) == []
        path = tmp_path / "candidate.py"
        path.write_text(source)
        with pytest.raises(CapabilityError, match="unreadable output"):
            builders.execute(path, ["a"])
        ok, report = builders.verify(path, [{"input_text": "a", "expected": "a"}])
        assert not ok and "unreadable output" in report["failures"][0]["error"]


def test_a_nested_claims_file_is_a_finding_not_an_exception():
    from greg.cognition import restatement
    for document in (NESTED, DEEP_OBJECT):
        claims, findings = restatement.read_claims(document, ["a"])
        assert claims == [] and findings and "not JSON" in findings[0]


def test_a_nested_model_draft_is_refused_at_once():
    """M3: the draft request failed with RecursionError after the paid model call; and refusing the outer object
    only to retry from every inner brace rescanned the reply once per brace."""
    import time
    import pytest
    from greg import planner
    from greg.missions import MissionError
    started = time.monotonic()
    with pytest.raises(MissionError, match="too deeply"):
        planner._first_json_object("draft: " + DEEP_OBJECT)
    assert time.monotonic() - started < 5
    assert planner._first_json_object('noise {"plan": [1]} tail') == {"plan": [1]}


def _blocks(fn, seconds=10):
    import threading
    worker = threading.Thread(target=fn, daemon=True)
    worker.start()
    worker.join(seconds)
    return worker.is_alive()


def test_a_refused_inbox_file_is_recorded_from_the_bytes_already_read(tmp_path, monkeypatch):
    """M1: a refused file was opened again with a blocking read; an inbox writer who renamed a FIFO over its name
    in between held the tick, and the BODY_STOP behind it was never read."""
    import os
    import sys
    import greg.body as body_module
    home, key, body_id, _ = make_body(tmp_path)
    inbox = home / "inbox"
    (inbox / "0000-bad.json").write_text("not json")
    real = body_module._parse_inbox
    swapped = []

    def racing(raw):
        try:
            return real(raw)
        except ValueError:
            # refused while the body applies it (not during the revocation pre-scan, which reads every file first):
            # the inbox writer renames a FIFO over it now
            if raw == b"not json" and not swapped and sys._getframe(1).f_code.co_name == "_ingest_one":
                os.mkfifo(inbox / ".swap")
                os.rename(inbox / ".swap", inbox / "0000-bad.json")
                swapped.append(raw)
            raise
    monkeypatch.setattr(body_module, "_parse_inbox", racing)
    outcome = {}

    def tick():
        with Body(home) as body:
            try:     # a later pass of the same tick meets the FIFO and exits on it, for the crash-loop breaker
                body.tick()
            except OSError:
                pass
            outcome["rejected"] = [e.payload for e in body.journal.replay("command.rejected")]
    assert not _blocks(tick), "the tick waited on the FIFO renamed over a refused file"
    assert swapped and [r["file"] for r in outcome["rejected"]] == ["0000-bad.json"]
    from greg.body import sha256_json
    assert outcome["rejected"][0]["sha256"] == sha256_json(b"not json".hex())


def test_status_and_the_morning_report_never_wait_on_a_fifo(tmp_path):
    """M2: inbox_digests read with a blocking read_text; greg status, greg morning, Mission Control and greg serve's
    /api/status and /api/decisions each hung for good on a FIFO in the inbox."""
    import os
    from greg.body import morning_projection, status
    home, key, body_id, _ = make_body(tmp_path)
    with Body(home) as body:
        body.tick()
    send_signed(home, key, "BODY_STOP", {})
    os.mkfifo(home / "inbox" / "0000-fifo.json")
    assert not _blocks(lambda: inbox_digests(Layout(home)))
    assert len(inbox_digests(Layout(home))) == 1          # the founder's command still counts; the FIFO does not
    assert not _blocks(lambda: status(home))
    assert not _blocks(lambda: morning_projection(home))
    for route in ("/api/status", "/api/decisions"):
        now = datetime.now(timezone.utc)
        answer = {}

        def call(route=route, now=now):
            answer[route] = remote.handle(home, "GET", route,
                                          sign_read(key, body_id=body_id, method="GET", path=route, now=now), b"",
                                          now=now)
        assert not _blocks(call), route
        assert answer[route][0] == 200, (route, answer[route])


def test_an_oversized_or_linked_inbox_entry_is_never_read(tmp_path):
    """L2: a link to a huge or sparse file was read whole on the tick. One reader now refuses links and anything over
    INBOX_FILE_BYTES before reading it."""
    import errno
    import os
    import pytest
    from greg.body import INBOX_FILE_BYTES, _read_inbox_file
    big = tmp_path / "big.json"
    with open(big, "wb") as handle:
        handle.truncate(INBOX_FILE_BYTES + 1)             # sparse: no disk, but read whole it is 4 MiB of zeros
    with pytest.raises(OSError) as raised:
        _read_inbox_file(big)
    assert raised.value.errno == errno.EFBIG
    small = tmp_path / "small.json"
    small.write_text("{}")
    link = tmp_path / "link.json"
    os.symlink(small, link)
    with pytest.raises(OSError) as raised:
        _read_inbox_file(link)
    assert raised.value.errno == errno.ELOOP
    assert _read_inbox_file(small) == b"{}"


# A depth json.loads itself reads without error, past the untrusted reader's MAX_DEPTH: each reader refuses it, so a
# reader that went back to plain json.loads is caught even where its except clause still names RecursionError.
DEPTH_300 = "[" * 300 + "]" * 300


def test_every_reader_refuses_a_document_deeper_than_the_bound(tmp_path):
    import pytest
    from greg import organ_exchange, workers
    from greg.capabilities import CapabilityError
    assert json.loads(DEPTH_300)                           # plain json.loads reads it
    assert workers._parse_claim(f"{workers.REPORT_MARK} {DEPTH_300}") is None
    deep_claim = '{"changed":' * 300 + "[]" + "}" * 300        # an object, so only the depth bound refuses it
    assert workers._parse_claim(f"{workers.REPORT_MARK} {deep_claim}") is None
    signal = tmp_path / "signal.json"
    signal.write_text(DEPTH_300)
    with pytest.raises(CapabilityError, match="not JSON"):
        organ_exchange._signal(signal)
    (tmp_path / "b").mkdir()
    home, key, body_id, _ = make_body(tmp_path / "b")
    try:
        remote.handle(home, "POST", "/api/command", {}, DEPTH_300.encode())
    except remote.RemoteError as exc:
        assert (exc.status, str(exc)) == (400, "command must be JSON")
    else:
        raise AssertionError("a document past the bound was accepted as a command")
    layout = Layout(home)
    layout.intake.mkdir(parents=True, exist_ok=True)
    (layout.intake / "deep.json").write_text(DEPTH_300)
    with Body(home) as body:
        body.tick()
        refused = [e.payload for e in body.journal.replay("external.intake_refused")]
    assert [(r["file"], r["why"]) for r in refused] == [("deep.json", "not JSON")]
