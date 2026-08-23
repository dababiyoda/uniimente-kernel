"""Bytes in, typed request out. A pure function with no idea a network exists.

`parse_request` takes `bytes` and returns a `Request`. It never reads from
anything: no socket, no file, no stream. Where those bytes came from is the
caller's problem, and in this institution there is currently no caller that
obtains them from outside the process — see `application.TRANSPORT_HALF_STATUS`.

## Parsing is refusal-first

Every malformed input is refused with a reason rather than repaired. A parser
that guesses is a parser that disagrees with the sender about what was said,
which is where request smuggling lives. Concretely:

- no request line, no method, no target -> refused;
- a header without a colon -> refused, not skipped;
- duplicate `Content-Length`, or one that disagrees with the body -> refused;
- `Transfer-Encoding` present at all -> refused, because supporting chunked
  framing correctly is exactly the kind of thing that looks done and is not.

The size ceilings exist for the same reason. They are not tuned for a workload —
there is no workload — they are there so that an unbounded input cannot be
turned into unbounded memory by a future caller.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping

#: Refusal ceilings. Deliberately small: nothing here serves real traffic, and a
#: generous limit would be a claim about capacity this package cannot make.
MAX_REQUEST_BYTES = 64 * 1024
MAX_HEADER_COUNT = 64
MAX_TARGET_BYTES = 2048

#: Methods this parser accepts. A closed set, because an application boundary
#: that forwards unknown verbs is a proxy, and this is not one.
METHODS = ("GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS")

_CRLF = b"\r\n"


class RequestParseError(ValueError):
    """The bytes are not a request this parser will accept. Never repaired."""


@dataclass(frozen=True)
class Request:
    """One parsed request. Immutable, and carries no connection.

    There is deliberately no `client_address`, no `socket`, no `stream` and no
    `respond()`. A request object that knew how to reply would be holding the
    transport half in a field.
    """

    method: str
    #: Path with the query string removed. Never URL-decoded here: decoding is a
    #: policy decision (which encodings, what to do with `%2F`) and a parser that
    #: quietly decodes hands the router a different string than arrived.
    path: str
    query: str
    version: str
    headers: Mapping[str, str]
    body: bytes = b""
    #: Path segments captured by the matched route, filled in by the router.
    params: Mapping[str, str] = field(default_factory=dict)

    def header(self, name: str, default: str = "") -> str:
        """Case-insensitive lookup, because HTTP header names are."""
        return self.headers.get(name.lower(), default)

    def with_params(self, params: Mapping[str, str]) -> "Request":
        """A copy carrying route parameters. The original is untouched."""
        return Request(method=self.method, path=self.path, query=self.query,
                       version=self.version, headers=self.headers,
                       body=self.body, params=dict(params))


def _split_target(target: str) -> tuple[str, str]:
    path, _, query = target.partition("?")
    return path, query


def parse_request(raw: bytes) -> Request:
    """Parse request bytes. Raises `RequestParseError` on anything doubtful.

    Pure: no I/O of any kind. Given the same bytes it returns the same request,
    which is what makes the whole path testable without a network.
    """
    if not isinstance(raw, (bytes, bytearray)):
        raise RequestParseError("request must be bytes; this parser reads no streams")
    if not raw:
        raise RequestParseError("empty request")
    if len(raw) > MAX_REQUEST_BYTES:
        raise RequestParseError(
            f"request is {len(raw)} bytes, over the {MAX_REQUEST_BYTES} ceiling")

    head, separator, body = bytes(raw).partition(_CRLF + _CRLF)
    if not separator:
        raise RequestParseError("no header/body separator (CRLF CRLF)")

    lines = head.split(_CRLF)
    request_line = lines[0]
    parts = request_line.split(b" ")
    if len(parts) != 3:
        raise RequestParseError(
            f"malformed request line {request_line[:80]!r}; expected "
            "'METHOD target HTTP/x.y'")

    try:
        method, target, version = (p.decode("ascii") for p in parts)
    except UnicodeDecodeError as exc:
        raise RequestParseError(f"request line is not ASCII: {exc}") from exc

    if method not in METHODS:
        raise RequestParseError(
            f"method {method!r} is not accepted; this is an application "
            f"boundary, not a proxy. Accepted: {list(METHODS)}")
    if not target.startswith("/"):
        raise RequestParseError(
            f"target {target!r} must be origin-form and start with '/'. "
            "Absolute-form targets belong to proxies.")
    if len(target.encode()) > MAX_TARGET_BYTES:
        raise RequestParseError("target exceeds the length ceiling")
    if not version.startswith("HTTP/"):
        raise RequestParseError(f"unrecognised version {version!r}")

    headers: dict[str, str] = {}
    for line in lines[1:]:
        if not line:
            continue
        if len(headers) >= MAX_HEADER_COUNT:
            raise RequestParseError(
                f"more than {MAX_HEADER_COUNT} headers")
        name, colon, value = line.partition(b":")
        if not colon:
            # Refused rather than skipped: a header the sender meant and the
            # parser dropped is a disagreement about what the request said.
            raise RequestParseError(f"header line without a colon: {line[:60]!r}")
        try:
            key = name.decode("ascii").strip().lower()
            val = value.decode("ascii").strip()
        except UnicodeDecodeError as exc:
            raise RequestParseError(f"header is not ASCII: {exc}") from exc
        if not key:
            raise RequestParseError("header with an empty name")
        if key in headers:
            # Refused rather than merged or last-wins. Header duplication is the
            # ambiguity that request smuggling is built out of.
            raise RequestParseError(f"duplicate header {key!r}")
        headers[key] = val

    if "transfer-encoding" in headers:
        raise RequestParseError(
            "Transfer-Encoding is not supported. Chunked framing is refused "
            "rather than half-implemented: getting it subtly wrong is how "
            "request smuggling happens, and nothing here needs it.")

    if "content-length" in headers:
        try:
            declared = int(headers["content-length"])
        except ValueError as exc:
            raise RequestParseError(
                f"Content-Length {headers['content-length']!r} is not an integer"
            ) from exc
        if declared < 0:
            raise RequestParseError("negative Content-Length")
        if declared != len(body):
            raise RequestParseError(
                f"Content-Length declares {declared} bytes; body is "
                f"{len(body)}. Refused rather than truncated or padded.")
    elif body:
        raise RequestParseError(
            "body present with no Content-Length; the framing is ambiguous")

    path, query = _split_target(target)
    return Request(method=method, path=path, query=query, version=version,
                   headers=headers, body=bytes(body))
