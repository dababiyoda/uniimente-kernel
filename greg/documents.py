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

What a person sees is not only text and images (#201 review DOC-1, DOC-12). Words painted by a tiling pattern,
glyphs drawn as vector outlines, a Type 3 font's drawings and a sticky note are visible and absent from the text
layer, or present only as the codes a font names. So a page is vouched for only when every ink pixel of its render
(``pdftoppm``, pinned like ``pdfimages``) lies in the box of a word the text layer holds (``pdftotext -tsv``) or on
a thin straight rule, no Type 3 font is used (``pdffonts``), and no reader reported the document damaged. The
residual is GREG's: the comparison of ink with word boxes below. Its cost, stated: a page with a logo, a signature,
a dashed or thick bar, a vector drawing, a dark background or any other non-text ink is never vouched for, so a
phrase's absence there stays unknown (the reader asks rather than proves). Ink lighter than ``INK_LEVEL`` is not
seen; a font whose glyphs are drawn as other characters than its encoding names (a lying ToUnicode) is read as the
characters it names, which only OCR could catch, and GREG has none.

A phrase is matched as a reader would read it (DOC-5, DOC-6, DOC-7, DOC-12): both sides in Unicode compatibility
form (NFKC; ligatures, full-width and compatibility characters), with typographic quotes and dashes folded and soft
hyphens and zero-width characters removed. It is **found** only as a whole: no letter, digit or joining mark
directly before it, and after it only closing punctuation and then a space or the end ("renewal term" is not
found in "nonrenewal term", nor "$1,000" in "$1,000,000"). It is **absent** only when even a loose reading misses
it: case ignored, with every space and hyphen removed (letter-spaced headings, line-end hyphens, words run
together, a phrase inside a longer word). Between the two the answer is undecided (``found`` None, with the reason),
so neither a check for the phrase nor one for its absence passes.
"""
from __future__ import annotations

import random
import re
import unicodedata
import zlib

WORDS = ("lease", "renewal", "term", "twelve", "months", "invoice", "total", "due", "net", "thirty", "party",
         "shall", "notice", "delivery", "proof", "settlement", "egregore", "a(b)c", "back\\slash", "50%", "x")


def _escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


# An 8x8 grey image: what a scanner leaves on a page, pixels and no text layer.
SCAN = bytes((x * 31 + y * 17) % 256 for y in range(8) for x in range(8))


class Stamped(str):
    """A scanned page with a line of real text stamped on it (a Bates number, a fax header)."""


class Drawn(list):
    """A text page that also carries ink its text layer does not hold as words (#201 review DOC-1, DOC-12):
    ``kind`` is ``pattern`` (words painted by a tiling pattern), ``outline`` (a letter drawn as a vector path),
    ``type3`` (a word drawn in a Type 3 font, whose glyphs are pictures) or ``note`` (a sticky-note annotation)."""

    def __init__(self, kind: str, lines: list):
        super().__init__(lines)
        self.kind = kind


DRAWN = ("pattern", "outline", "type3", "note")
HIDDEN = "automatic renewal"      # what the drawn ink says; it is never in the text layer as these words


def _drawn_ops(kind: str) -> list:
    if kind == "pattern":
        return ["/Pattern cs /P1 scn", "72 560 300 40 re f"]
    if kind == "outline":                      # a ring, like the letter O, drawn with curves: no word and no rule
        ring = []
        for r in (14, 9):
            k = 0.5523 * r
            ring += [f"{100 + r} 580 m", f"{100 + r} {580 + k:.2f} {100 + k:.2f} {580 + r} 100 {580 + r} c",
                     f"{100 - k:.2f} {580 + r} {100 - r} {580 + k:.2f} {100 - r} 580 c",
                     f"{100 - r} {580 - k:.2f} {100 - k:.2f} {580 - r} 100 {580 - r} c",
                     f"{100 + k:.2f} {580 - r} {100 + r} {580 - k:.2f} {100 + r} 580 c"]
        return ring + ["f*"]
    if kind == "type3":
        return ["BT", "/T3 24 Tf", "72 560 Td", "(x) Tj", "ET"]
    return []                                  # note: the annotation is on the page, not in its content


def write_pdf(pages: list, *, compress: bool = False) -> bytes:
    """A valid PDF whose page i draws the lines pages[i], top to bottom, in Helvetica (Flate-compressed
    content streams when ``compress``, as most real PDFs are). A page given as ``SCAN`` is an image only; a page
    given as ``Stamped(text)`` is the image with that text drawn small on top."""
    objects: list[bytes] = []
    kids = []
    font_id, image_id = 3 + 2 * len(pages), 4 + 2 * len(pages)
    drawn = any(isinstance(page, Drawn) for page in pages)
    pattern_id, type3_id, glyph_id, note_id = (5 + 2 * len(pages) + k for k in range(4))
    for index, lines in enumerate(pages):
        kind = lines.kind if isinstance(lines, Drawn) else None       # each page names only what it draws with
        extra = f" /Pattern << /P1 {pattern_id} 0 R >>" if kind == "pattern" else ""
        fonts = f"/F1 {font_id} 0 R" + (f" /T3 {type3_id} 0 R" if kind == "type3" else "")
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
            if kind:
                ops += _drawn_ops(kind)
        stream = "\n".join(ops).encode("latin-1")
        flate = b" /Filter /FlateDecode" if compress else b""
        stream = zlib.compress(stream) if compress else stream
        note = f" /Annots [{note_id} 0 R]" if kind == "note" else ""
        objects.append(f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << {fonts} "
                       f">> /XObject << /Im1 {image_id} 0 R >>{extra} >> /Contents {content_id} 0 R{note} >>".encode())
        objects.append(b"<< /Length " + str(len(stream)).encode() + flate + b" >>\nstream\n" + stream + b"\nendstream")
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>")
    objects.append(b"<< /Type /XObject /Subtype /Image /Width 8 /Height 8 /ColorSpace /DeviceGray "
                   b"/BitsPerComponent 8 /Length 64 >>\nstream\n" + SCAN + b"\nendstream")
    if drawn:
        cell = f"BT /F1 12 Tf 0 5 Td ({HIDDEN}) Tj ET".encode()
        objects.append(f"<< /Type /Pattern /PatternType 1 /PaintType 1 /TilingType 1 /BBox [0 0 300 40] /XStep 300 "
                       f"/YStep 40 /Matrix [1 0 0 1 72 560] /Resources << /Font << /F1 {font_id} 0 R >> >> "
                       f"/Length {len(cell)} >>".encode() + b"\nstream\n" + cell + b"\nendstream")
        objects.append(f"<< /Type /Font /Subtype /Type3 /FontBBox [0 0 750 750] /FontMatrix [0.001 0 0 0.001 0 0] "
                       f"/CharProcs << /x {glyph_id} 0 R >> /Encoding << /Type /Encoding /Differences [120 /x] >> "
                       f"/FirstChar 120 /LastChar 120 /Widths [750] /Resources << >> >>".encode())
        glyph = b"750 0 0 0 700 700 d1 50 0 m 350 700 l 650 0 l 500 0 l 350 400 l 200 0 l f"   # an A, not an x
        objects.append(b"<< /Length " + str(len(glyph)).encode() + b" >>\nstream\n" + glyph + b"\nendstream")
        objects.append(f"<< /Type /Annot /Subtype /Text /Rect [72 520 92 540] /Contents ({HIDDEN}) "
                       f"/Open true >>".encode())
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
    """Twelve PDFs, alternately plain and compressed: one line, several lines, several pages, an empty page,
    punctuation, a long page, a scanned page between two text pages, a scanned page with a stamp on it, and one
    text page each with ink its text layer does not hold as words (a pattern, a vector outline, a Type 3 font, a
    sticky note; #201 review DOC-1, DOC-12). A reader qualifies only if it also reports every case with a page it
    could not fully read as incomplete."""
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
    shapes += [[Drawn(kind, [line(5)])] for kind in DRAWN]
    cases = []
    for index, pages in enumerate(shapes):
        texts = [[str(page)] if isinstance(page, Stamped) else ([] if page is SCAN else
                 list(page) + (["x"] if isinstance(page, Drawn) and page.kind == "type3" else [])) for page in pages]
        expected = " ".join(word for page in texts for text in page for word in text.split())
        complete = all(page is not SCAN and not isinstance(page, (Stamped, Drawn)) and any(text.split() for text in page)
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


def type3_fonts(listing: str) -> list[str]:
    """Type 3 fonts ``pdffonts`` lists: each glyph is a drawing, so its text is only the code the font names.
    Columns are read from the widths of the dashed rule under the header (a font name may contain spaces)."""
    lines = listing.splitlines()
    rule = next((i for i, row in enumerate(lines) if row.startswith("---")), None)
    if rule is None:
        return []
    spans, start = [], 0
    for group in lines[rule].split(" "):
        spans.append((start, start + len(group)))
        start += len(group) + 1
    if len(spans) < 2:
        return []
    name, kind = spans[0], spans[1]
    return [row[name[0]:name[1]].strip() or "[none]" for row in lines[rule + 1:]
            if row[kind[0]:kind[1]].strip() == "Type 3"][:20]


def reader_errors(stderr: dict | None) -> list[str]:
    """Lines in which a pinned reader reported the document damaged ("Syntax Error", "Internal Error"): what was
    extracted may be only part of what the file holds, though every reader exited 0 (#201 directive VIII)."""
    found = []
    for name, text in sorted((stderr or {}).items()):
        found += [f"{name}: {row.strip()[:160]}" for row in (text or "").splitlines() if "Error" in row]
    return found[:5]


# What poppler's tools document for their exit status (the EXIT CODES section of each tool's manual page). The
# reader runs with -q, so this is often the only cause it gives; the refusal carries it to the mission record.
POPPLER_EXIT = {1: "the file could not be opened as a PDF: missing, unreadable, empty, damaged beyond repair, not a "
                   "PDF, or encrypted with a password GREG does not have",
                2: "the output could not be written", 3: "the PDF's permissions forbid this",
                99: "another error (for example a page range the document does not have)"}


# -- ink the text layer does not explain (#201 review DOC-1, DOC-12) ------------------------------------------------
INK_SCALE = 512           # pdftoppm -scale-to: each page fits a 512 x 512 pixel box (at most 256 KiB in grey)
INK_LEVEL = 200           # a pixel darker than this (0 black .. 255 white) is ink
RULE_PX = 24              # a straight run of ink at least this long (about 37 pt on a letter page) ...
THIN_PX = 2               # ... with no ink THIN_PX pixels to either side along most of it is a rule, not a glyph
PAD_PX = 2                # a word's box is widened by this much for glyphs that overhang it (accents, italics)
INK_MAX_PAGES = 300       # pages checked per document; past them no page is vouched for
_DARK = bytes(1 if level < INK_LEVEL else 0 for level in range(256))
_P5 = re.compile(rb"P5\s+(\d+)\s+(\d+)\s+255\s")
_RUN = re.compile(b"\x01{%d,}" % RULE_PX)


def pgm_pages(data: bytes) -> list[tuple]:
    """The pages of a ``pdftoppm -gray`` stream: binary 8-bit PGM images one after another, (width, height, pixels)."""
    pages, at = [], 0
    while at < len(data):
        head = _P5.match(data, at)
        if head is None:
            raise ValueError(f"not an 8-bit binary PGM at byte {at}")
        width, height = int(head[1]), int(head[2])
        pixels = data[head.end():head.end() + width * height]
        if not width or not height or len(pixels) != width * height:
            raise ValueError("truncated PGM")
        pages.append((width, height, pixels))
        at = head.end() + width * height
    return pages


def tsv_pages(text: str) -> dict:
    """Word boxes per page from ``pdftotext -tsv``: {page: {"size": (width, height), "boxes": [(x, y, w, h)]}}."""
    pages = {}
    for row in text.splitlines()[1:]:
        cells = row.split("\t")
        if len(cells) < 12 or not cells[0].isdigit() or not cells[1].isdigit():
            continue
        try:
            box = tuple(float(v) for v in cells[6:10])
        except ValueError:
            continue
        page = pages.setdefault(int(cells[1]), {"size": None, "boxes": []})
        if cells[0] == "1":
            page["size"] = box[2:]
        elif cells[0] == "5":
            page["boxes"].append(box)
    return pages


def unexplained_ink(image: tuple, page: dict | None) -> int:
    """Ink pixels of one rendered page that neither a word of its text layer nor a thin straight rule explains.

    Rules (table borders, underlines, signature lines) are found first, on the whole page: a run of at least
    ``RULE_PX`` ink pixels along a row or column with no ink ``THIN_PX`` pixels to either side along most of it.
    Then every word box, widened by ``PAD_PX``, is cleared. What is left is ink a reader sees and the text layer
    does not hold: words in a pattern, outlined glyphs, a drawing, a sticky note, a dashed or thick bar."""
    width, height, pixels = image
    ink = bytearray(pixels.translate(_DARK))
    if not ink.count(1):
        return 0
    rules = []
    for y in range(height):
        for run in _RUN.finditer(bytes(ink[y * width:(y + 1) * width])):
            s, e = run.start(), run.end()
            above = ink[(y - THIN_PX) * width + s:(y - THIN_PX) * width + e].count(1) if y >= THIN_PX else 0
            below = ink[(y + THIN_PX) * width + s:(y + THIN_PX) * width + e].count(1) if y + THIN_PX < height else 0
            if 4 * above <= e - s and 4 * below <= e - s:
                rules.append((y * width + s, y * width + e, 1))
    columns = [bytes(ink[x::width]) for x in range(width)]
    for x in range(width):
        for run in _RUN.finditer(columns[x]):
            s, e = run.start(), run.end()
            left = columns[x - THIN_PX][s:e].count(1) if x >= THIN_PX else 0
            right = columns[x + THIN_PX][s:e].count(1) if x + THIN_PX < width else 0
            if 4 * left <= e - s and 4 * right <= e - s:
                rules.append((s * width + x, e * width + x, width))
    for start, stop, step in rules:
        ink[start:stop:step] = bytes(len(range(start, stop, step)))
    if page and page.get("size") and page.get("boxes"):
        pw, ph = page["size"]
        if (width > height) != (pw > ph):        # a page turned a quarter: boxes come as displayed
            pw, ph = ph, pw
        sx, sy = width / pw, height / ph
        for x, y, w, h in page["boxes"]:
            x0, x1 = max(0, int(x * sx) - PAD_PX), min(width, int((x + w) * sx) + PAD_PX + 1)
            if x1 <= x0:
                continue
            for row in range(max(0, int(y * sy) - PAD_PX), min(height, int((y + h) * sy) + PAD_PX + 1)):
                ink[row * width + x0:row * width + x1] = bytes(x1 - x0)
    return ink.count(1)


def ink_check(pages: int, tools) -> dict:
    """Render every page and compare its ink with its words (module docstring). ``tools`` runs the pinned readers
    on the same file: ``tools.boxes(first, last)`` (``pdftotext -tsv``) and ``tools.render(first, last)``
    (``pdftoppm -gray``), each returning (output or None, why it is missing, stderr); ``tools.pages_per_run`` keeps
    each run under the output ceiling. The last run asks for one page past the end: a document with more pages
    than the text extraction read is not vouched for. Stops at the first range with unexplained ink (the
    extraction is incomplete either way)."""
    out = {"ink_check": f"pdftoppm -gray -scale-to {INK_SCALE} against pdftotext -tsv word boxes",
           "pages_with_unexplained_ink": None, "ink_errors": []}
    if tools is None:
        return {**out, "ink_check": "unavailable on this body"}
    if pages > INK_MAX_PAGES:
        return {**out, "ink_check": f"not run: {pages} pages, more than the {INK_MAX_PAGES} checked"}
    flagged, step = [], max(1, int(tools.pages_per_run))
    for first in range(1, pages + 1, step):
        last = min(pages, first + step - 1)
        boxes, why, err1 = tools.boxes(first, last)
        if boxes is None:
            return {**out, "ink_check": f"not completed: word boxes for pages {first}-{last}: {why}"}
        images, why, err2 = tools.render(first, last + 1 if last == pages else last)
        if images is None:
            return {**out, "ink_check": f"not completed: render of pages {first}-{last}: {why}"}
        out["ink_errors"] += reader_errors({"pdftotext -tsv": err1, "pdftoppm": err2})
        try:
            rendered, laid = pgm_pages(images), tsv_pages(boxes)
        except ValueError as exc:
            return {**out, "ink_check": f"not completed: pages {first}-{last}: {exc}"}
        if len(rendered) > last - first + 1:
            return {**out, "ink_check": f"not completed: the document has more than the {pages} pages the text "
                                        "extraction read"}
        if len(rendered) < last - first + 1:
            return {**out, "ink_check": f"not completed: pages {first}-{last} rendered {len(rendered)} images"}
        flagged += [first + i for i, image in enumerate(rendered) if unexplained_ink(image, laid.get(first + i))]
        if flagged:
            return {**out, "pages_with_unexplained_ink": flagged[:100],
                    "ink_check": out["ink_check"] + f"; stopped after page {last}"}
    return {**out, "pages_with_unexplained_ink": []}


def coverage(raw: str, images: str | None = None, *, fonts: str | None = None, errors: list | None = None,
             tools=None) -> dict:
    """Which pages the extraction fully holds. pdftotext ends every page with a form feed. A page is fully read
    only when it yields text, carries no image, uses no Type 3 font, no reader reported the document damaged and
    its rendered ink lies in its words' boxes or on rules (``ink_check``). With no image listing, no font listing
    or no render, no page can be vouched for; the render runs only when everything else already vouches."""
    pages = raw.split("\f")
    if pages and not pages[-1].strip():
        pages = pages[:-1]
    empty = [number for number, page in enumerate(pages, start=1) if not page.split()]
    imaged = sorted(image_pages(images)) if images is not None else None
    type3 = type3_fonts(fonts) if fonts is not None else None
    errors = list(errors or [])
    out = {"pages": len(pages), "pages_without_text": empty[:100],
           "pages_with_images": imaged[:100] if imaged is not None else None,
           "image_check": "pdfimages -list" if images is not None else "unavailable on this body",
           "type3_fonts": type3, "font_check": "pdffonts" if fonts is not None else "unavailable on this body",
           "reader_errors": errors, "pages_with_unexplained_ink": None, "ink_check": "not run"}
    if pages and not empty and imaged == [] and type3 == [] and not errors:
        ink = ink_check(len(pages), tools)
        out.update({k: ink[k] for k in ("pages_with_unexplained_ink", "ink_check")})
        out["reader_errors"] = (errors + ink["ink_errors"])[:5]
    else:
        out["ink_check"] = "not run: the extraction is already incomplete"
    out["complete"] = bool(pages) and not empty and imaged == [] and type3 == [] and not out["reader_errors"] \
        and out["pages_with_unexplained_ink"] == []
    return out


# -- matching a phrase as a reader reads it (#201 review DOC-5, DOC-6, DOC-7, DOC-12) ---------------------------------
PHRASE_RULES = "document.phrase/1"
NORMALIZATION = ("NFKC; typographic quotes and dashes folded to ' \" -; soft hyphens and zero-width characters "
                 "removed; whitespace collapsed")
_FOLD = str.maketrans({**{c: "'" for c in "‘’‚‛′ʼ"},
                       **{c: '"' for c in "“”„‟″"},
                       **{c: "-" for c in "‐‑‒–—―−﹘﹣－"},
                       **{c: None for c in "­​‌‍⁠﻿"}})
_OPEN = "\"'([{"                 # may stand directly before a phrase
_CLOSE = ".,;:!?\"')]}"          # may stand directly after it, before a space or the end


def normalize(text: str) -> str:
    """Text as a phrase is matched: Unicode compatibility form, quotes and dashes folded, invisible marks dropped."""
    return " ".join(unicodedata.normalize("NFKC", text).translate(_FOLD).split())


def _loose(text: str) -> str:
    return re.sub(r"[\s\-]+", "", normalize(text).casefold())


def _strict(needle: str, prefix: bool) -> re.Pattern:
    """The needle as a whole: nothing word-like directly before it (only a space, the start or an opening mark),
    after it only closing punctuation and then a space, or the end of a whole text. In a kept prefix the end is not
    an edge: the next character was cut off, and "renewal term" at the end could be "renewal terms"."""
    end = r"\s" if prefix else r"(?:\s|$)"
    return re.compile(r"(?:(?<=^)|(?<=[\s" + re.escape(_OPEN) + r"]))" + re.escape(needle)
                      + r"(?=[" + re.escape(_CLOSE) + r"]*" + end + ")")


def phrase_state(text: str, phrase: str, *, prefix: bool = False, ignore_case: bool = False) -> tuple:
    """(state, occurrences, why) for one phrase over one text: state True when the phrase occurs as a whole,
    False when even a loose reading misses it, None (undecided) when only a loose reading finds it or when the
    text is a kept prefix that does not hold it. ``occurrences`` counts the whole occurrences."""
    needle, haystack = normalize(phrase), normalize(text)
    if ignore_case:
        needle, haystack = needle.casefold(), haystack.casefold()
    count = sum(1 for _ in _strict(needle, prefix).finditer(haystack)) if needle else 0
    if count:
        return True, count, f"{needle!r:.80} occurs {count} time(s) as a whole"
    if prefix:
        return None, 0, f"{needle!r:.80} is not in the kept prefix as a whole; the rest was not retained"
    if needle and _loose(needle) and _loose(needle) in _loose(text):
        return None, 0, (f"{needle!r:.80} occurs only with its case, spacing, hyphens or word edges changed "
                         "(letter-spaced, hyphenated or inside a longer word): neither present nor absent")
    return False, 0, f"{needle!r:.80} does not occur, even ignoring case, spaces and hyphens"


def find_phrase(text: str, params: dict, raw: str | None = None, extras: dict | None = None) -> dict:
    """Evaluate ``params['phrase']`` over the whole extraction, not over a receipt's bounded prefix.

    A receipt keeps only a prefix of long text (``authority.bounded``), and a predicate on that prefix can miss a
    phrase past it ('contains' false) or miss a forbidden one ('not_contains' true). The reader therefore answers
    the question on every word it extracted; the receipt records the answer and the text's digest and length.

    Absence is claimed only over a complete extraction (``coverage``) and only when even a loose reading misses
    the phrase (``phrase_state``). A page that could hold the phrase where the text layer does not (pixels, a
    pattern, an outline, a note) leaves ``found`` None (unknown): a check for the phrase fails, and so does a check
    for its absence. A phrase found is found however much more could have been read, so it is listed in
    ``decided``: the engine may treat that field as settled even when the extraction is incomplete. The output
    declares in ``text_match`` that its ``text`` field is matched by the same rules, so the judge reads a
    'contains' or 'not_contains' check on it as this function would (DOC-7)."""
    import hashlib
    extras = extras or {}
    phrase = params.get("phrase")
    seen = coverage(raw if raw is not None else text, extras.get("pdfimages"), fonts=extras.get("pdffonts"),
                    errors=reader_errors(extras.get("stderr")), tools=extras.get("pages"))
    out = {"words": len(text.split()), "text_sha256": hashlib.sha256(text.encode()).hexdigest(), **seen,
           "text_match": {"text": PHRASE_RULES}, "normalization": NORMALIZATION}
    if isinstance(phrase, str) and phrase.split():
        needle = " ".join(phrase.split())
        state, count, why = phrase_state(text, needle, ignore_case=params.get("ignore_case") is True)
        if state is False and not seen["complete"]:
            state, why = None, f"{why}, but the extraction is incomplete: a page may hold it where the text does not"
        out.update({"phrase": needle, "found": state, "occurrences": count})
        if state is None:
            out["undecided"] = why
        if count:
            out["decided"] = ["found"]
    return out
