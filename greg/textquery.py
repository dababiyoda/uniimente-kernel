"""A question about a source too large to keep, answered over all of it (directive of 2026-10-22, section VIII:
a bounded verified traversal that produces a compact authenticated result with coverage evidence).

``fs.read`` keeps at most 256 KiB, and a receipt keeps an output whole only up to 1 MiB of canonical JSON (#209), so a
check on a 40 MiB log could never be decided: GREG asked the founder. ``Query`` reads a source as a stream. It holds
one chunk, the end of the text whose normalized form is still open, and the last ``overlap`` characters it searched,
so its memory is bounded however large the source is. It answers every phrase over every character it read, in one
normalization form (``greg.textform``), and returns a result small enough for any receipt that states what it
covered: the bytes read and their digest, the encoding, and whether it reached the end. A phrase found is found however
much more there is; a phrase is absent only when every byte was read and faithfully decoded. Anything else is left
undecided, with the reason, through the incomplete-observation contract the judge reads (``complete``, ``decided``).
"""
from __future__ import annotations

import codecs
import hashlib
import os
from pathlib import Path
import re
import stat
import time

from greg.capabilities import BYTE_ORDER_MARKS, CapabilityError, InvocationContext, _inside
from greg.textform import canon, stable

CHUNK_BYTES = 64 * 1024
MAX_PHRASES = 16
MAX_PHRASE_CHARS = 1024
MAX_BYTES = 4 * 1024 ** 3          # the most one query reads; a larger source is answered as far as it goes
MAX_SECONDS = 60.0
MAX_OPEN_CHARS = 64 * 1024         # text whose normalized form is still open: a run of marks with no starter
WHITESPACE = ("exact", "collapse")
SPACES = re.compile(r"\s+")


class Query:
    """Answer ``phrases`` over bytes fed in any number of pieces, then ``finish``. ``whitespace="collapse"`` reads
    every run of whitespace, in the text and in the phrases, as one space (text extracted from PDFs breaks lines
    anywhere)."""

    def __init__(self, phrases, *, whitespace: str = "exact"):
        if whitespace not in WHITESPACE:
            raise ValueError(f"whitespace must be one of {WHITESPACE}")
        if not isinstance(phrases, list) or not 1 <= len(phrases) <= MAX_PHRASES or not all(
                isinstance(p, str) and p.strip() and len(p) <= MAX_PHRASE_CHARS for p in phrases):
            raise ValueError(f"phrases must be 1 to {MAX_PHRASES} nonblank strings of at most {MAX_PHRASE_CHARS} "
                             "characters")
        self.whitespace = whitespace
        self.phrases = [SPACES.sub(" ", canon(p)).strip() if whitespace == "collapse" else canon(p) for p in phrases]
        self.overlap = max(map(len, self.phrases)) - 1
        self.digest, self.read = hashlib.sha256(), 0
        self.codec, self.unreadable, self.finished = None, None, False
        self.first, self.count = [None] * len(self.phrases), [0] * len(self.phrases)
        self._head = b""           # the first bytes, until their byte-order mark (or its absence) can be told
        self._decoder = None
        self._open = ""            # decoded text whose NFC form a later character could still change
        self._tail = ""            # the last ``overlap`` characters searched, for a match across two pieces
        self._offset = 0           # characters searched before ``_tail``
        self._space = False        # collapse: the text searched so far ends in a space

    def feed(self, data: bytes, *, final: bool = False) -> None:
        if self.unreadable or self.finished:
            return
        self.digest.update(data)
        self.read += len(data)
        if self._decoder is None:
            self._head += data
            if len(self._head) < 4 and not final:
                return
            data, self._head = self._head, b""
            self.codec = next((name for mark, name in BYTE_ORDER_MARKS if data.startswith(mark)), "utf-8")
            self._decoder = codecs.getincrementaldecoder(self.codec)()
        try:
            text = self._decoder.decode(data, final=final)
        except UnicodeDecodeError as exc:
            at = self.read - len(data) + exc.start
            self.unreadable = f"not valid {self.codec.removesuffix('-sig')} near byte {at}"
            return
        if self.codec == "utf-8" and "\x00" in text:
            self.unreadable = "holds NUL bytes: UTF-16 or UTF-32 without a byte-order mark, or not text"
            return
        self._open += text
        ready = self._open if final else stable(self._open)
        self._open = self._open[len(ready):]
        if len(self._open) > MAX_OPEN_CHARS:
            self.unreadable = (f"a run of more than {MAX_OPEN_CHARS} characters with no normalization boundary "
                               "cannot be normalized in bounded memory")
            return
        self._search(canon(ready))
        self.finished = final

    def finish(self) -> None:
        self.feed(b"", final=True)

    def _search(self, text: str) -> None:
        if self.whitespace == "collapse":
            text = SPACES.sub(" ", text)
            if self._space and text.startswith(" "):
                text = text[1:]
            self._space = text.endswith(" ") if text else self._space
        if not text:
            return
        window = self._tail + text
        for i, phrase in enumerate(self.phrases):
            # only matches that end past the tail: those inside it were counted with the piece before
            at = window.find(phrase, max(0, len(self._tail) - len(phrase) + 1))
            while at != -1:
                self.first[i] = self._offset + at if self.first[i] is None else self.first[i]
                self.count[i] += 1
                at = window.find(phrase, at + 1)
        keep = window[max(0, len(window) - self.overlap):] if self.overlap else ""
        self._offset += len(window) - len(keep)
        self._tail = keep

    def result(self, stopped: str | None = None) -> dict:
        """The compact answer. ``complete`` only when every byte was read, decoded and searched; then ``found`` is
        True or False. Otherwise a phrase found is True and vouched for (``decided``), and every other answer is None,
        with the reason in ``stopped`` or ``unreadable``."""
        complete = self.finished and not self.unreadable and stopped is None
        readable = self.unreadable is None
        queries = [{"phrase": phrase, "found": True if count and readable else (False if complete else None),
                    "first_offset": first if readable else None, "occurrences": count if readable else None}
                   for phrase, first, count in zip(self.phrases, self.first, self.count)]
        out = {"bytes_read": self.read, "read_sha256": self.digest.hexdigest(), "encoding": self.codec,
               "normalization": "NFC", "whitespace": self.whitespace, "chunk_bytes": CHUNK_BYTES,
               "overlap_chars": self.overlap, "stopped": stopped, "complete": complete, "queries": queries}
        if self.unreadable:
            out["unreadable"] = self.unreadable
        if not complete:
            out["decided"] = sorted([k for k in out if k not in ("complete", "queries")]
                                    + [f"queries.{i}.{field}" for i, q in enumerate(queries)
                                       for field in ("phrase", "found", "first_offset") if field == "phrase"
                                       or q["found"] is True])
        return out


def fs_search(params, ctx: InvocationContext) -> dict:
    """``fs.search``: answer phrases over one whole file inside the permitted roots, streamed (``Query``). Reads at
    most ``max_bytes`` (at most MAX_BYTES) for at most ``max_seconds`` (at most MAX_SECONDS); past either, the answer
    is as far as it went, and says so."""
    path = _inside(Path(params["path"]), ctx.read_roots + (ctx.workspace,))
    try:
        query = Query(params["phrases"], whitespace=params.get("whitespace", "exact"))
        limit = int(params.get("max_bytes", MAX_BYTES))
        seconds = float(params.get("max_seconds", MAX_SECONDS))
    except (TypeError, ValueError) as exc:
        raise CapabilityError(f"fs.search: {exc}") from None
    if not 0 < limit <= MAX_BYTES or not 0 < seconds <= MAX_SECONDS:
        raise CapabilityError(f"fs.search reads at most {MAX_BYTES} bytes for at most {MAX_SECONDS:g} seconds")
    if not path.is_file():   # absence is a measurement of the world, not a sensor failure
        return {"path": str(path), "exists": False}
    deadline, stopped = time.monotonic() + seconds, None
    with open(os.open(path, os.O_RDONLY | os.O_NONBLOCK), "rb") as stream:     # a FIFO swapped in never blocks
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode):
            raise CapabilityError(f"{path.name} is not a regular file")
        while not query.unreadable:
            if query.read >= limit:
                stopped = None if not stream.read(1) else f"byte limit: read the first {limit} bytes"
                break
            if time.monotonic() > deadline:
                stopped = f"time limit: read {query.read} bytes in {seconds:g} seconds"
                break
            chunk = stream.read(min(CHUNK_BYTES, limit - query.read))
            if not chunk:
                break
            query.feed(chunk)
    if stopped is None:
        query.finish()
    return {"path": str(path), "exists": True, "size": info.st_size, **query.result(stopped)}
