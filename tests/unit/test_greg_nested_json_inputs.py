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
    assert rejected[0]["reason"].startswith("RecursionError")
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


def test_the_readers_of_model_and_mcp_answers_name_recursion_error_as_malformed():
    """greg/models.py (Ollama) and greg/mcp_tools.py read an answer GREG does not control; both catch RecursionError
    with the JSON errors, so a nested answer is a bad output or a refusal, never an unknown outcome."""
    import inspect
    from greg import mcp_tools, models
    assert "except (UnicodeError, ValueError, RecursionError)" in inspect.getsource(models.OllamaRoute._request)
    assert "except (ValueError, IndexError, RecursionError)" in inspect.getsource(mcp_tools)


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
