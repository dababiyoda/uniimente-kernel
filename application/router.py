"""Path routing: request in, handler out. It chooses; it does not connect.

The same discipline as `routing/decision_router.py`, in a different domain: this
router matches a path to a registered handler and calls it. It has no transport,
no client, and no way to reach anything that is not already in this process.

## Routes are registered explicitly and matched exactly

No decorators that register on import, no filesystem scanning, no dynamic
import. A route exists because a caller registered it, so the set of reachable
handlers is exactly the set someone wrote down. FBO's constraint against
arbitrary dynamic imports applies here as much as it does to the module loader,
and the reason is the same: an application boundary that discovers its own
endpoints has a surface nobody enumerated.

Path parameters use `{name}` segments, matched segment-wise. There is no regex
compilation of caller-supplied patterns — a router that compiles arbitrary
patterns supplied at registration time has an exponential-backtracking denial of
service waiting in it.

## Errors become responses, never exceptions escaping the boundary

`dispatch` converts a handler exception into a 500 with no detail. Leaking an
exception message through an application boundary is how internal paths, module
names and occasionally secrets end up in a response body. The detail belongs in
whatever the caller uses for logging, which is deliberately not this module's
business.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from application.request import Request
from application.response import Response

Handler = Callable[[Request], Response]


class RouteNotFound(LookupError):
    """No route matched. Raised by `match`; `dispatch` renders it as a 404."""


class RouteConflict(ValueError):
    """Two routes claim the same method and pattern. Refused at registration."""


@dataclass(frozen=True)
class Route:
    """One registered path pattern and the handler that serves it."""

    method: str
    pattern: str
    handler: Handler

    @property
    def segments(self) -> tuple[str, ...]:
        return tuple(s for s in self.pattern.strip("/").split("/") if s != "")


def _match_segments(pattern: tuple[str, ...], actual: tuple[str, ...]
                    ) -> dict[str, str] | None:
    """Segment-wise match. Returns captured params, or None for no match."""
    if len(pattern) != len(actual):
        return None
    params: dict[str, str] = {}
    for expected, got in zip(pattern, actual):
        if expected.startswith("{") and expected.endswith("}"):
            name = expected[1:-1]
            if not name:
                return None
            params[name] = got
        elif expected != got:
            return None
    return params


class ApplicationRouter:
    """Matches requests to handlers. Owns no connection and opens none."""

    def __init__(self) -> None:
        self._routes: list[Route] = []

    def add(self, method: str, pattern: str, handler: Handler) -> Route:
        """Register one route. Conflicts are refused, not last-wins.

        Last-wins registration means a later import can silently take over an
        existing endpoint, which is a change of behaviour with no diff at the
        call site.
        """
        method = method.upper()
        if not pattern.startswith("/"):
            raise RouteConflict(f"pattern {pattern!r} must start with '/'")
        route = Route(method=method, pattern=pattern, handler=handler)
        for existing in self._routes:
            if existing.method == method and existing.segments == route.segments:
                raise RouteConflict(
                    f"{method} {pattern!r} conflicts with the registered "
                    f"{existing.pattern!r}")
        self._routes.append(route)
        return route

    def routes(self) -> tuple[Route, ...]:
        """Every reachable endpoint. Enumerable by construction."""
        return tuple(self._routes)

    def match(self, request: Request) -> tuple[Route, dict[str, str]]:
        """Find the route for this request.

        Raises `RouteNotFound` when nothing matches the path, and a distinct
        405-shaped `RouteNotFound` when the path exists under another method —
        the two are different facts and a caller that conflates them tells a
        client the wrong thing.
        """
        actual = tuple(s for s in request.path.strip("/").split("/") if s != "")
        path_exists = False
        for route in self._routes:
            params = _match_segments(route.segments, actual)
            if params is None:
                continue
            path_exists = True
            if route.method == request.method:
                return route, params
        if path_exists:
            raise RouteNotFound(f"405:{request.path}")
        raise RouteNotFound(f"404:{request.path}")

    def dispatch(self, request: Request) -> Response:
        """Route and invoke. Always returns a Response; never raises outward."""
        try:
            route, params = self.match(request)
        except RouteNotFound as exc:
            status = 405 if str(exc).startswith("405:") else 404
            return Response(status=status, headers={"content-type": "text/plain"},
                            body=b"")
        try:
            response = route.handler(request.with_params(params))
        except Exception:
            # Deliberately no detail. An exception message crossing an
            # application boundary is how internal paths and occasionally
            # secrets reach a response body.
            return Response(status=500,
                            headers={"content-type": "text/plain"}, body=b"")
        if not isinstance(response, Response):
            raise TypeError(
                f"handler for {route.pattern!r} returned "
                f"{type(response).__name__}, not a Response")
        return response


def handle(raw: bytes, router: ApplicationRouter) -> bytes:
    """The whole application half, end to end: bytes in, bytes out.

    This is the complete boundary. A transport half, if one were ever
    authorised, would be the code that obtains `raw` and disposes of the return
    value — and it would be an entirely separate module, because nothing here
    would need to change to accommodate it.

    That is the point of the split: the seam is a function signature, so adding
    a network is an addition somebody has to make and review, not an emergent
    property of this package.
    """
    from application.request import RequestParseError, parse_request

    try:
        request = parse_request(raw)
    except RequestParseError:
        return _render(Response(status=400,
                                headers={"content-type": "text/plain"}, body=b""))
    return _render(router.dispatch(request))


def _render(response: Response) -> bytes:
    from application.response import render_response

    return render_response(response)
