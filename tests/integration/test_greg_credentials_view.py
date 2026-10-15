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
        "expires_at": time.time() + 3600}))
    _, page = http(port, "/mc/authority")
    table = page.split("Credentials GREG holds", 1)[1].split("</table>", 1)[0]
    assert "<code>mcp:plain-token</code>" in table and "token or key" in table
    assert "<code>mcp:notes</code>" in table and "OAuth login" in table and "https://service.test/mcp" in table
    assert "auth.test" in table and "greg secret remove mcp:notes</code> and remove GREG's access" in table
    for value in ("PLAIN-VALUE-0a1b", "ACCESS-VALUE-2c3d", "REFRESH-VALUE-4e5f", "CLIENT-SECRET-6a7b"):
        assert value not in page                                    # names only, on every view of this page
