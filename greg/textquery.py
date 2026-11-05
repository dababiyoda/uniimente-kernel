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

A PDF is not text, however plain its bytes: a page draws its words with text operators, so a phrase over two lines is
not in the bytes and an operator or font name is. ``Query`` refuses a source a PDF reader could read as a PDF
(``PdfEvidence``): one with a header where readers look for it, or with PDF structure anywhere, since poppler reads a
PDF whose header is missing, misspelled or lowercased. It decides nothing until it has read 1024 bytes or reached the
end.
"""
from __future__ import annotations

import codecs
import errno
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
PDF_HEAD = 1024      # readers look for the header this far in; junk may precede it (PDF Reference 1.7, appendix H,
                     # the note on section 3.4.1). poppler reads a PDF whatever precedes it, and with no header at all
PDF_CARRY = 1024     # bytes kept between pieces, so structure split over two is still seen: with no "startxref" or
                     # "endobj", pdftotext 24.02 reads a PDF with 200 spaces between an object's number and "obj",
                     # and not with 300
PDF = ("may be a PDF ({}): a PDF's text is drawn by page operators, not stored as text, so GREG does not search its "
       "bytes; read it with document.text")
_PDF_SPACE = rb"[\x00\t\n\x0b\f\r ]+"     # PDF whitespace, and vertical tab: never fewer than a reader allows
OBJECT_HEADER = re.compile(rb"(?<![0-9])[0-9]+" + _PDF_SPACE + rb"[0-9]+" + _PDF_SPACE   # "12 0 obj", ended by a
                           + rb"obj(?=[\x00\t\n\x0b\f\r ()<>\[\]{}/%])")                  # delimiter
PDF_KEYWORDS = (b"startxref", b"endobj")


class PdfEvidence:
    """What in a source's bytes says a PDF reader could read it as a PDF, streamed in bounded memory: a header
    ("%PDF-") within the first PDF_HEAD bytes, or PDF structure anywhere.

    The structure is what poppler needs, measured on pdftotext 24.02 with no header: it reads a PDF through
    "startxref" (still 2000 bytes from the end, not 100 KiB from it), through a linearized first object ended by
    "endobj", or, with neither, by finding objects as "N G obj" with only whitespace between the three. Comments
    between them it allows only on the first two routes. A PDF it reads therefore holds "startxref", "endobj" or such
    an object header. Each is looked for anywhere, which never refuses less than poppler reads, and refuses a text
    that quotes one (a program that writes PDFs). Another reader may read files poppler does not."""

    def __init__(self):
        self.read = 0
        self.header = None          # the byte "%PDF-" starts at, within the first PDF_HEAD bytes
        self.structure = None       # (what, the byte it starts at): the first PDF structure seen
        self.finished = False       # every byte was fed
        self._lead = b""            # the first PDF_HEAD bytes, while the header may still be in them
        self._carry = b""           # the last PDF_CARRY bytes, for structure split over two pieces

    def feed(self, data: bytes) -> None:
        start, self.read = self.read, self.read + len(data)
        if self.header is None and start < PDF_HEAD:
            self._lead = (self._lead + data)[:PDF_HEAD]
            at = self._lead.find(b"%PDF-")
            self.header = at if at != -1 else None
        if self.structure is None:
            window, base = self._carry + data, start - len(self._carry)
            seen = [(at, f'"{word.decode()}"') for word in PDF_KEYWORDS if (at := window.find(word)) != -1]
            if (match := OBJECT_HEADER.search(window)) is not None:
                shown = re.sub(_PDF_SPACE, b" ", match.group())[:40].decode()
                seen.append((match.start(), f'an object header "{shown}"'))
            if seen:
                at, what = min(seen)
                self.structure = (what, base + at)
            self._carry = window[-PDF_CARRY:]

    def finish(self) -> None:
        self.finished = True

    def reason(self) -> str | None:
        """What was seen, with where: None when nothing so far says a PDF reader could read this source."""
        seen = ([f'a PDF header ("%PDF-") at byte {self.header}'] if self.header is not None else []) + (
            [f"PDF structure ({self.structure[0]} at byte {self.structure[1]})"] if self.structure else [])
        return "; ".join(seen) or None


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
        self._pdf = PdfEvidence()   # whether a PDF reader could read the bytes as a PDF
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
        self._pdf.feed(data)
        if final:
            self._pdf.finish()
        if (seen := self._pdf.reason()) is not None:
            self.unreadable = PDF.format(seen)
            return
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
        if self.codec in ("utf-8", "utf-8-sig") and "\x00" in text:     # a UTF-8 mark before UTF-16 bytes too
            self.unreadable = "holds NUL bytes: UTF-16 or UTF-32 read as UTF-8, or not text"
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
        with the reason in ``stopped`` or ``unreadable``. A reading stopped before PDF_HEAD bytes found nothing yet: the
        bytes it read could be junk before a PDF's header."""
        complete = self.finished and not self.unreadable and stopped is None
        readable = self.unreadable is None and (self.finished or self.read >= PDF_HEAD)
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
    if not path.exists():    # absence is a measurement of the world; a directory or FIFO there is a failed read
        return {"path": str(path), "exists": False}
    deadline, stopped = time.monotonic() + seconds, None
    try:   # a FIFO swapped in never blocks; a link swapped in after the roots were checked is not followed
        fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW)
    except OSError as exc:
        if exc.errno == errno.ELOOP:
            raise CapabilityError(f"{path.name} became a link after its path was checked") from None
        raise
    info = os.fstat(fd)
    if not stat.S_ISREG(info.st_mode):                  # checked on the descriptor, before Python wraps it
        os.close(fd)
        raise CapabilityError(f"{path.name} is not a regular file")
    with open(fd, "rb") as stream:
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
