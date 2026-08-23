"""The application half of a web server. The transport half is absent.

Approved as Option A in FOUNDER-RULING-2026-08-22, ruling 5 (DEC-OM-004):

> Build pure typed request parsing, routing and response rendering. No listener,
> socket, bind, public port, outbound connection, HTTP client, external contact
> or hidden network primitive.
>
> Do not game the ladder. If this only earns SKETCHED, call it SKETCHED. Its
> value is that it creates a clean application boundary and raises legitimately
> earned headroom — not that we can claim to possess a real web server.

## What a web server actually is, and which half this is

Two separable halves:

1. **Transport.** Bind a port, listen, accept connections, read and write
   sockets. Every consequential thing a web server does to the outside world.
2. **Application.** Given request bytes, produce response bytes: parse, route,
   handle, render.

The second half is a pure function. It has no idea a network exists, and giving
it one is a deliberate, visible act — a socket does not appear by refactoring.

**This package is the second half only, and it will not become the first.** The
transport half is not "not yet written"; it is founder-gated. The standing
constraints forbid a public network surface, and that is not a temporary
scheduling fact.

## What this therefore does NOT mean

It does not mean UNIIMENTE has a web server. It cannot serve a request, cannot
be reached, and cannot reach anything. Nothing here has processed a byte that
came from outside this process. Recorded in `blueprint/registry.py` under #31
in those words.

## The kill criterion

Any network primitive appearing in this package is a **stop-the-line failure**,
not a code-review finding. `tests/unit/test_application_inertness.py` enforces
it structurally over the AST of every module here, and additionally runs the
whole request/response path in a child process under an audit hook with the
parent asserting zero network events. See `KILL_CRITERION` below.

That guard is not decoration. The failure mode it exists for is ordinary: a
later contributor adds a `serve()` helper "for local testing", it works, and the
institution acquires a listener nobody decided to build.
"""
from __future__ import annotations

from application.request import Request, RequestParseError, parse_request
from application.response import Response, render_response
from application.router import ApplicationRouter, Route, RouteNotFound

#: The stop-the-line condition, stated where the code lives rather than only in
#: a test. If any of these appears in `application/`, the build fails and the
#: package is treated as compromised until a founder decision says otherwise —
#: it is not fixed by deleting the line and moving on, because its presence
#: means the boundary was not being maintained.
KILL_CRITERION = (
    "STOP THE LINE. Trigger: any of a socket, a bind, a listen, an accept, an "
    "outbound connection, an HTTP client, a DNS lookup, a subprocess, or any "
    "import of socket / socketserver / http.server / urllib / requests / httpx "
    "/ asyncio, appearing anywhere in application/. "
    "Consequence: the build fails and this package is treated as compromised "
    "until a founder decision says otherwise. It is NOT remedied by deleting "
    "the offending line and continuing — the line's presence means the boundary "
    "was not being maintained, and whether a transport half exists at all is a "
    "founder decision, not a contributor's. "
    "Enforced structurally over every module's AST by "
    "tests/unit/test_application_inertness.py, and independently by running the "
    "full request path under sys.addaudithook with the parent process asserting."
)

#: Stated as data so the blueprint and the tests read the same sentence.
TRANSPORT_HALF_STATUS = (
    "ABSENT AND FOUNDER-GATED. No listener, socket, bind, port, outbound "
    "connection or HTTP client exists in this institution. This package cannot "
    "serve a request and has never processed a byte originating outside its own "
    "process. Building the transport half requires a separate explicit founder "
    "authorization; it is not scheduled work."
)

__all__ = [
    "ApplicationRouter",
    "KILL_CRITERION",
    "Request",
    "RequestParseError",
    "Response",
    "Route",
    "RouteNotFound",
    "TRANSPORT_HALF_STATUS",
    "parse_request",
    "render_response",
]
