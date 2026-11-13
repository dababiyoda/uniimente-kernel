"""Mission Control's Authority view lists every credential GREG holds, by name, with how to revoke it, and never a
value. An OAuth login also shows what the founder authorized: the server, where it may renew, and when it expires."""
from __future__ import annotations

import json
import time

from greg import mcp_login
from greg.capabilities import SecretBroker
from tests.integration.test_greg_mcp_founder_path import running  # noqa: F401 (fixture)
from tests.integration.test_greg_mission_control import http


def test_the_founder_sees_every_credential_greg_holds_and_how_to_revoke_it(running):
    home, data, console, port = running
    broker = SecretBroker(home / "secrets.json")
    broker.put("mcp:plain-token", "PLAIN-VALUE-0a1b")
    broker.put("mcp:notes", json.dumps({
        "kind": mcp_login.KIND, "server": "https://service.test/mcp", "token_endpoint": "https://auth.test/token",
        "tokens": {"access_token": "ACCESS-VALUE-2c3d", "refresh_token": "REFRESH-VALUE-4e5f"},
        "client": {"client_id": "greg-client", "client_secret": "CLIENT-SECRET-6a7b"}, "scope": "notes",
        "expires_at": time.time() + 3600, "listed_at": time.time(),
        "tools": [{"name": "add_note", "description": "Add a note to the shared notes.", "needs": ["text"],
                   "claims_read_only": None}]}))
    _, page = http(port, "/mc/authority")
    table = page.split("Credentials GREG holds", 1)[1].split("</table>", 1)[0]
    assert "<code>mcp:plain-token</code>" in table and "token or key" in table
    assert "<code>mcp:notes</code>" in table and "OAuth login" in table and "https://service.test/mcp" in table
    assert "auth.test" in table and "greg secret remove mcp:notes</code> and remove GREG's access" in table
    for value in ("PLAIN-VALUE-0a1b", "ACCESS-VALUE-2c3d", "REFRESH-VALUE-4e5f", "CLIENT-SECRET-6a7b"):
        assert value not in page                                    # names only, on every view of this page


def test_the_founder_sees_the_hosted_servers_greg_is_logged_in_to_without_contacting_them(running):
    home, data, console, port = running
    SecretBroker(home / "secrets.json").put("mcp:notes", json.dumps({
        "kind": mcp_login.KIND, "server": "https://service.test/mcp", "token_endpoint": "https://service.test/token",
        "tokens": {"access_token": "ACCESS-VALUE-8c9d"}, "client": {"client_id": "greg-client"},
        "expires_at": time.time() + 3600, "listed_at": time.time(),
        "tools": [{"name": "add_note", "description": "Add a note to the shared notes.", "needs": ["text"],
                   "claims_read_only": None}]}))
    _, command = http(port, "/mc/command")
    hosted = command.split("Hosted servers GREG holds a login or token for", 1)[1].split("</table>", 1)[0]
    assert "https://service.test/mcp" in hosted and "<code>add_note</code>" in hosted and "<code>mcp:notes</code>" in hosted
    assert "ACCESS-VALUE-8c9d" not in command


def test_a_registered_token_shows_as_a_hosted_server_with_its_tools(running):
    home, data, console, port = running
    SecretBroker(home / "secrets.json").put("mcp:issues", json.dumps({
        "kind": mcp_login.TOKEN_KIND, "server": "https://issues.test/mcp", "tokens": {"access_token": "PASTED-VALUE-1f2e"},
        "listed_at": time.time(), "tools": [{"name": "open_issue", "description": "Open an issue.", "needs": ["title"],
                                             "claims_read_only": False}]}))
    _, authority = http(port, "/mc/authority")
    table = authority.split("Credentials GREG holds", 1)[1].split("</table>", 1)[0]
    assert "registered token" in table and "https://issues.test/mcp" in table
    assert "greg secret remove mcp:issues</code> and revoke the token at the service" in table
    _, command = http(port, "/mc/command")
    hosted = command.split("Hosted servers GREG holds a login or token for", 1)[1].split("</table>", 1)[0]
    assert "https://issues.test/mcp" in hosted and "<code>open_issue</code>" in hosted and "registered token" in hosted
    assert "PASTED-VALUE-1f2e" not in authority + command
