"""Typed response in, bytes out. Rendering, not sending.

`render_response` returns `bytes`. It does not write them anywhere, and there is
no `send`, `flush`, `write` or `close` in this module — those are the transport
half's vocabulary, and their absence is the boundary.

A `Response` object with a `send()` method would be a socket wearing a
dataclass.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping

_CRLF = b"\r\n"

#: The subset of status codes this boundary emits. Closed on purpose: a handler
#: returning an arbitrary integer would let the application invent semantics the
#: institution has not decided on.
STATUS_TEXT: Mapping[int, str] = {
    200: "OK",
    201: "Created",
    204: "No Content",
    400: "Bad Request",
    403: "Forbidden",
    404: "Not Found",
    405: "Method Not Allowed",
    413: "Payload Too Large",
    415: "Unsupported Media Type",
    422: "Unprocessable Content",
    500: "Internal Server Error",
    501: "Not Implemented",
}


class ResponseError(ValueError):
    """The response cannot be rendered. Fails closed rather than guessing."""


@dataclass(frozen=True)
class Response:
    """One response, not yet bytes and never sent."""

    status: int = 200
    headers: Mapping[str, str] = field(default_factory=dict)
    body: bytes = b""

    def __post_init__(self) -> None:
        if self.status not in STATUS_TEXT:
            raise ResponseError(
                f"status {self.status} is not in this boundary's closed set "
                f"{sorted(STATUS_TEXT)}")
        if not isinstance(self.body, (bytes, bytearray)):
            raise ResponseError(
                "body must be bytes; encoding is the handler's decision, not "
                "something to guess at render time")


def render_response(response: Response) -> bytes:
    """Serialise to wire bytes. Returns them; sends nothing.

    `Content-Length` is computed from the actual body rather than trusted from
    the headers — a mismatch here is the response-side twin of the request
    smuggling this parser refuses, and computing it makes the class of bug
    unreachable instead of merely tested for.

    204 carries no body and no Content-Length, per the one framing rule that is
    genuinely load-bearing rather than cosmetic.
    """
    if response.status == 204 and response.body:
        raise ResponseError("204 No Content must not carry a body")

    headers = {k.lower(): v for k, v in response.headers.items()}
    headers.pop("content-length", None)
    headers.pop("transfer-encoding", None)   # never emitted; see request.py

    lines = [f"HTTP/1.1 {response.status} {STATUS_TEXT[response.status]}".encode()]
    if response.status != 204:
        headers["content-length"] = str(len(response.body))
    for key in sorted(headers):
        lines.append(f"{key}: {headers[key]}".encode())

    return _CRLF.join(lines) + _CRLF + _CRLF + response.body
