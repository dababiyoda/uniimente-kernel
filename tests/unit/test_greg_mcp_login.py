"""What a stored OAuth login may and may not do inside an approved ``mcp.act``.

An expired login renews only at the token endpoint recorded when the founder logged in, and only when that host is
the server's own or is named in the approved hosts. A login that cannot renew is refused before anything starts, and
the shown record never carries a token.
"""
from __future__ import annotations

from dataclasses import replace
import json
import time
from types import SimpleNamespace

import pytest

from greg import mcp_login, mcp_tools
from greg.capabilities import BUILTINS, CapabilityError, InvocationContext, SecretBroker
from tests.unit.test_greg_mcp_act import no_namespaces


def login(*, endpoint="https://service.test/token", expires_in=3600.0, refresh=True):
    tokens = {"access_token": "at-SECRET", "token_type": "Bearer", **({"refresh_token": "rt-SECRET"} if refresh else {})}
    return {"kind": mcp_login.KIND, "server": "https://service.test/mcp", "tokens": tokens, "scope": "notes",
            "expires_at": time.time() + expires_in, "client": {"client_id": "greg-client"}, "token_endpoint": endpoint}


@pytest.fixture
def ctx(tmp_path, monkeypatch):
    secrets = SecretBroker(tmp_path / "secrets.json")
    no_namespaces(monkeypatch)                  # passing every check ends at the namespace probe; nothing starts
    return InvocationContext(workspace=tmp_path / "ws", read_roots=(tmp_path,), secrets=secrets,
                             manifest=BUILTINS["mcp.act"][0], target="mcp:notes", mission_id="m:notes",
                             egress=SimpleNamespace(journal=None, connect=None, proxy=None))


CALL = {"server": "notes", "url": "https://service.test/mcp", "tool": "add_note", "arguments": {"text": "x"},
        "bearer": "mcp:notes"}


@pytest.mark.parametrize("stored, change, why", [
    (login(expires_in=-30, endpoint="https://auth.other.test/token"), {}, "renews at auth.other.test"),
    (login(expires_in=-30, refresh=False), {}, "cannot renew"),
    (login(endpoint="https://auth.other.test/token"), {"hosts": ["service.test", "elsewhere.test"]},
     "its login renews at auth.other.test"),
    (login(), {"hosts": ["service.test", "auth.other.test"]}, "exactly its own host"),
])
def test_a_login_that_cannot_renew_where_it_was_approved_is_refused_before_anything_starts(ctx, stored, change, why):
    ctx.secrets.put("mcp:notes", json.dumps(stored))
    with pytest.raises(CapabilityError, match=why):
        mcp_tools.act({**CALL, **change}, ctx)


@pytest.mark.parametrize("stored, change", [
    (login(), {}),                                                         # valid: used as it is
    (login(expires_in=-30), {}),                                           # renews at the server's own host
    (login(expires_in=-30, endpoint="https://auth.other.test/token"),
     {"hosts": ["service.test", "auth.other.test"]}),                     # renews where the approval names
])
def test_a_login_used_or_renewed_where_it_was_approved_passes_every_check(ctx, stored, change):
    ctx.secrets.put("mcp:notes", json.dumps(stored))
    with pytest.raises(CapabilityError, match="bubblewrap namespace"):   # only the host could stop it now
        mcp_tools.act({**CALL, **change}, ctx)


def test_what_is_shown_of_a_login_never_carries_a_token():
    shown = mcp_login.public(login(endpoint="https://auth.other.test/token"))
    assert shown["renews_at"] == "auth.other.test" and "SECRET" not in json.dumps(shown)


def test_a_renewal_rotates_what_the_service_sent_and_keeps_the_rest(tmp_path):
    broker = SecretBroker(tmp_path / "s.json")
    old = login(expires_in=-30)
    mcp_login.store_renewal(broker, "mcp:notes", old, {"access_token": "at-NEW", "expires_in": 600,
                                                       "refresh_token": None})
    kept = mcp_login.record(broker, "mcp:notes")
    assert kept["tokens"]["access_token"] == "at-NEW" and kept["tokens"]["refresh_token"] == "rt-SECRET"
    assert not mcp_login.expired(kept) and kept["token_endpoint"] == old["token_endpoint"]


def test_a_plain_token_is_not_a_login(tmp_path):
    broker = SecretBroker(tmp_path / "s.json")
    broker.put("mcp:plain", "just-a-token")
    assert mcp_login.record(broker, "mcp:plain") is None and mcp_login.record(broker, "mcp:missing") is None


@pytest.mark.parametrize("name, url, why", [("Notes Server", "https://service.test/mcp", "lowercase name"),
                                            ("notes", "http://service.test/mcp", "url must be https")])
def test_a_login_names_a_handle_and_an_https_server_before_anything_is_contacted(tmp_path, name, url, why):
    import asyncio
    with pytest.raises(CapabilityError, match=why):
        asyncio.run(mcp_login.login(name, url, SecretBroker(tmp_path / "s.json"),
                                    open_url=lambda link: pytest.fail("a link was opened")))


def test_the_founder_sees_one_line_when_a_login_is_refused(tmp_path):
    import subprocess
    import sys
    from pathlib import Path
    from greg.body import init_body
    init_body(tmp_path / "body", read_roots=[str(tmp_path)])
    out = subprocess.run([sys.executable, "-m", "greg", "--home", str(tmp_path / "body"), "mcp", "login", "notes",
                          "http://service.test/mcp"], capture_output=True, text=True, timeout=60,
                         cwd=Path(__file__).resolve().parents[2])
    assert out.returncode == 2 and out.stderr.startswith("greg: not logged in: url must be https")
    assert "Traceback" not in out.stderr and not (tmp_path / "body" / "secrets.json").exists()
