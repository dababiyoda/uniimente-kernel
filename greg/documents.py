"""Frozen acceptance oracle for ``document.text``: PDFs GREG writes itself, with known words.

Capability Genesis acquires PDF text extraction from installed software (``pdftotext`` from poppler-utils
today; the ``pypdf`` and ``pypdfium2`` packages are recorded fallbacks). The oracle below is written before any
candidate is searched and shares no code with any of them: a minimal PDF 1.4 writer (one standard Type 1 font,
uncompressed content streams, an exact cross-reference table) and seeded word lists. A candidate qualifies only
if the words it extracts, whitespace-normalized, equal the words written, on every case.

This proves extraction on PDFs of this shape: text drawn in a standard font, in reading order. Scanned images
(which need OCR), embedded or subset fonts without a usable encoding, right-to-left scripts and multi-column
layouts are not covered by the oracle and are not claimed. What the oracle does require is that a reader say so:
a page that yields no text (a scanned image, or a blank page; the reader cannot tell which), or that carries any
image at all (a scan with a Bates number or fax header stamped on it yields a few words and still hides its
content in pixels; ``pdfimages -list`` reports images per page), makes the extraction
``complete: false``, and a phrase it did not find there is unknown, never absent.
"""
from __future__ import annotations

import random
import zlib

WORDS = ("lease", "renewal", "term", "twelve", "months", "invoice", "total", "due", "net", "thirty", "party",
         "shall", "notice", "delivery", "proof", "settlement", "egregore", "a(b)c", "back\\slash", "50%", "x")


def _escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


# An 8x8 grey image: what a scanner leaves on a page, pixels and no text layer.
SCAN = bytes((x * 31 + y * 17) % 256 for y in range(8) for x in range(8))


class Stamped(str):
    """A scanned page with a line of real text stamped on it (a Bates number, a fax header)."""


def write_pdf(pages: list, *, compress: bool = False) -> bytes:
    """A valid PDF whose page i draws the lines pages[i], top to bottom, in Helvetica (Flate-compressed
    content streams when ``compress``, as most real PDFs are). A page given as ``SCAN`` is an image only; a page
    given as ``Stamped(text)`` is the image with that text drawn small on top."""
    objects: list[bytes] = []
    kids = []
    font_id, image_id = 3 + 2 * len(pages), 4 + 2 * len(pages)
    for index, lines in enumerate(pages):
        page_id, content_id = 3 + 2 * index, 4 + 2 * index
        kids.append(f"{page_id} 0 R")
        if lines is SCAN or isinstance(lines, Stamped):
            ops = ["q", "468 0 0 648 72 72 cm", "/Im1 Do", "Q"]
            if isinstance(lines, Stamped):
                ops += ["BT", "/F1 8 Tf", "72 40 Td", f"({_escape(str(lines))}) Tj", "ET"]
        else:
            ops = ["BT", "/F1 12 Tf", "16 TL", "72 720 Td"]
            for line in lines:
                ops += [f"({_escape(line)}) Tj", "T*"]
            ops.append("ET")
        stream = "\n".join(ops).encode("latin-1")
        flate = b" /Filter /FlateDecode" if compress else b""
        stream = zlib.compress(stream) if compress else stream
        objects.append(f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 {font_id} "
                       f"0 R >> /XObject << /Im1 {image_id} 0 R >> >> /Contents {content_id} 0 R >>".encode())
        objects.append(b"<< /Length " + str(len(stream)).encode() + flate + b" >>\nstream\n" + stream + b"\nendstream")
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>")
    objects.append(b"<< /Type /XObject /Subtype /Image /Width 8 /Height 8 /ColorSpace /DeviceGray "
                   b"/BitsPerComponent 8 /Length 64 >>\nstream\n" + SCAN + b"\nendstream")
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
    """Eight PDFs, alternately plain and compressed: one line, several lines, several pages, an empty page,
    punctuation, a long page, a scanned page between two text pages, and a scanned page with a stamp on it. A
    reader qualifies only if it also reports the three cases with a page it could not fully read as incomplete."""
    rng = random.Random(seed)

    def line(n):
        return " ".join(rng.choice(WORDS) for _ in range(n))
    shapes = [[[line(5)]],
              [[line(rng.randint(3, 9)) for _ in range(rng.randint(2, 6))]],
              [[line(4) for _ in range(3)] for _ in range(rng.randint(2, 4))],
              [[], [line(6)]],
              [["Total due: 50% net thirty (renewal) back\\slash."]],
              [[line(10) for _ in range(30)]],
              [[line(5)], SCAN, [line(5)]],
              [[line(5)], Stamped("BATES-000002"), [line(5)]]]
    cases = []
    for index, pages in enumerate(shapes):
        texts = [[str(page)] if isinstance(page, Stamped) else ([] if page is SCAN else page) for page in pages]
        expected = " ".join(word for page in texts for text in page for word in text.split())
        complete = all(page is not SCAN and not isinstance(page, Stamped) and any(text.split() for text in page)
                       for page in pages)
        cases.append({"name": f"case{index}.pdf", "data": write_pdf(pages, compress=bool(index % 2)),
                      "expected": expected, "complete": complete})
    return cases


def image_pages(listing: str) -> set[int]:
    """Pages ``pdfimages -list`` reports an image on: rows after the dashed rule start with the page number."""
    pages, rows = set(), False
    for row in listing.splitlines():
        if row.startswith("---"):
            rows = True
        elif rows and row.split() and row.split()[0].isdigit():
            pages.add(int(row.split()[0]))
    return pages


def coverage(raw: str, images: str | None = None) -> dict:
    """Which pages the extraction fully holds. pdftotext ends every page with a form feed. A page is fully read
    only when it yields text and carries no image; with no image listing, no page can be vouched for."""
    pages = raw.split("\f")
    if pages and not pages[-1].strip():
        pages = pages[:-1]
    empty = [number for number, page in enumerate(pages, start=1) if not page.split()]
    imaged = sorted(image_pages(images)) if images is not None else None
    return {"pages": len(pages), "pages_without_text": empty[:100],
            "pages_with_images": imaged[:100] if imaged is not None else None,
            "image_check": "pdfimages -list" if images is not None else "unavailable on this body",
            "complete": bool(pages) and not empty and imaged is not None and not imaged}


def find_phrase(text: str, params: dict, raw: str | None = None, extras: dict | None = None) -> dict:
    """Evaluate ``params['phrase']`` over the whole extraction, not over a receipt's bounded prefix.

    A receipt keeps only a prefix of long text (``authority.bounded``), and a predicate on that prefix can miss a
    phrase past it ('contains' false) or miss a forbidden one ('not_contains' true). The reader therefore answers
    the question on every word it extracted; the receipt records the answer and the text's digest and length.

    Absence is claimed only over a complete extraction. A page with no text layer may hold the phrase as pixels,
    so there ``found`` is None (unknown): a check for the phrase fails, and so does a check for its absence. A
    phrase found is found however much more could have been read, so it is listed in ``decided``: the engine
    may treat that field as settled even when the extraction is incomplete."""
    import hashlib
    phrase = params.get("phrase")
    seen = coverage(raw if raw is not None else text, (extras or {}).get("pdfimages"))
    out = {"words": len(text.split()), "text_sha256": hashlib.sha256(text.encode()).hexdigest(), **seen}
    if isinstance(phrase, str) and phrase.split():
        needle = " ".join(phrase.split())
        count = text.count(needle)
        out.update({"phrase": needle, "found": True if count else (False if seen["complete"] else None),
                    "occurrences": count})
        if count:
            out["decided"] = ["found"]
    return out
