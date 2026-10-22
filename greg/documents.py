"""Frozen acceptance oracle for ``document.text``: PDFs GREG writes itself, with known words.

Capability Genesis acquires PDF text extraction from installed software (``pdftotext`` from poppler-utils
today; the ``pypdf`` and ``pypdfium2`` packages are recorded fallbacks). The oracle below is written before any
candidate is searched and shares no code with any of them: a minimal PDF 1.4 writer (one standard Type 1 font,
uncompressed content streams, an exact cross-reference table) and seeded word lists. A candidate qualifies only
if the words it extracts, whitespace-normalized, equal the words written, on every case.

This proves extraction on PDFs of this shape: text drawn in a standard font, in reading order. Scanned images
(which need OCR), embedded or subset fonts without a usable encoding, right-to-left scripts and multi-column
layouts are not covered by the oracle and are not claimed.
"""
from __future__ import annotations

import random
import zlib

WORDS = ("lease", "renewal", "term", "twelve", "months", "invoice", "total", "due", "net", "thirty", "party",
         "shall", "notice", "delivery", "proof", "settlement", "egregore", "a(b)c", "back\\slash", "50%", "x")


def _escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def write_pdf(pages: list[list[str]], *, compress: bool = False) -> bytes:
    """A valid PDF whose page i draws the lines pages[i], top to bottom, in Helvetica (Flate-compressed
    content streams when ``compress``, as most real PDFs are)."""
    objects: list[bytes] = []
    kids = []
    font_id = 3 + 2 * len(pages)
    for index, lines in enumerate(pages):
        page_id, content_id = 3 + 2 * index, 4 + 2 * index
        kids.append(f"{page_id} 0 R")
        ops = ["BT", "/F1 12 Tf", "16 TL", "72 720 Td"]
        for line in lines:
            ops += [f"({_escape(line)}) Tj", "T*"]
        ops.append("ET")
        stream = "\n".join(ops).encode("latin-1")
        flate = b" /Filter /FlateDecode" if compress else b""
        stream = zlib.compress(stream) if compress else stream
        objects.append(f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 {font_id} "
                       f"0 R >> >> /Contents {content_id} 0 R >>".encode())
        objects.append(b"<< /Length " + str(len(stream)).encode() + flate + b" >>\nstream\n" + stream + b"\nendstream")
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>")
    head = [b"<< /Type /Catalog /Pages 2 0 R >>",
            f"<< /Type /Pages /Kids [{' '.join(kids)}] /Count {len(pages)} >>".encode()]
    body = head + objects
    out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = []
    for number, obj in enumerate(body, start=1):
        offsets.append(len(out))
        out += f"{number} 0 obj\n".encode() + obj + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(body) + 1}\n0000000000 65535 f \n".encode()
    out += b"".join(f"{offset:010d} 00000 n \n".encode() for offset in offsets)
    out += f"trailer\n<< /Size {len(body) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    return bytes(out)


def oracle_document_text(seed: int) -> list[dict]:
    """Six PDFs, alternately plain and compressed: one line, several lines, several pages, an empty page,
    punctuation, a long page."""
    rng = random.Random(seed)

    def line(n):
        return " ".join(rng.choice(WORDS) for _ in range(n))
    shapes = [[[line(5)]],
              [[line(rng.randint(3, 9)) for _ in range(rng.randint(2, 6))]],
              [[line(4) for _ in range(3)] for _ in range(rng.randint(2, 4))],
              [[], [line(6)]],
              [["Total due: 50% net thirty (renewal) back\\slash."]],
              [[line(10) for _ in range(30)]]]
    cases = []
    for index, pages in enumerate(shapes):
        expected = " ".join(word for page in pages for text in page for word in text.split())
        cases.append({"name": f"case{index}.pdf", "data": write_pdf(pages, compress=bool(index % 2)),
                      "expected": expected})
    return cases
