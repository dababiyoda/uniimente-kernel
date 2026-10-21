"""How text reads to a person: the code points that hide, and the folding used to compare what is read.

One definition, two readers, so they cannot drift: the GREG data plane (greg/dataplane.py, and through it the
outbound ask screen greg/asks.py) matches instruction-shaped text on what a reader sees, and the autonomy
authority (autonomy/levels.py) refuses an authorizer that names UNIIMENTE or the subject. This module only
reads text; like every identity module it carries no authority.

``INVISIBLE`` is derived from Unicode properties when the module loads (``unicodedata``), not hand-listed:

* every format character (General_Category Cf), except the Prepended_Concatenation_Mark characters, which
  draw a visible sign (U+0600-0605, U+06DD, U+070F, U+0890-0891, U+08E2, U+110BD, U+110CD);
* every control character (Cc: C0, DEL and C1 U+0080-009F), except tab, line feed and carriage return;
* Other_Default_Ignorable_Code_Point and Variation_Selector from PropList.txt, which ``unicodedata`` does
  not expose (their ranges are stable and listed below): the combining grapheme joiner U+034F, the Hangul
  fillers U+115F, U+1160, U+3164 and U+FFA0, the Khmer inherent vowels U+17B4-17B5, U+2065, U+FFF0-FFF8,
  the tag block U+E0000-E0FFF, and the variation selectors U+180B-180D, U+180F, U+FE00-FE0F and
  U+E0100-E01EF.

That is Default_Ignorable_Code_Point (DerivedCoreProperties.txt: Other_Default_Ignorable_Code_Point + Cf +
Variation_Selector, less White_Space, the prepended concatenation marks, and the interlinear-annotation and
Egyptian-hieroglyph format controls, which are kept here because they draw nothing either), plus the controls.

Bypass review of e9a3062 (#13): its hand-picked list missed tag characters ("ASCII smuggling"), variation
selectors, CGJ, U+061C, U+180E, U+206A-206F, U+1D173-1D17A, C1 controls and the Hangul fillers.
"""
from __future__ import annotations

import unicodedata

_PREPENDED_CONCATENATION_MARKS = frozenset((*range(0x0600, 0x0606), 0x06DD, 0x070F, 0x0890, 0x0891, 0x08E2,
                                            0x110BD, 0x110CD))
_KEPT_CONTROLS = frozenset((0x09, 0x0A, 0x0D))
_OTHER_DEFAULT_IGNORABLE = ((0x034F, 0x034F), (0x115F, 0x1160), (0x17B4, 0x17B5), (0x2065, 0x2065),
                            (0x3164, 0x3164), (0xFFA0, 0xFFA0), (0xFFF0, 0xFFF8), (0xE0000, 0xE0000),
                            (0xE0002, 0xE001F), (0xE0080, 0xE00FF), (0xE01F0, 0xE0FFF))
_VARIATION_SELECTOR = ((0x180B, 0x180D), (0x180F, 0x180F), (0xFE00, 0xFE0F), (0xE0100, 0xE01EF))

VARIATION_SELECTORS = frozenset(cp for low, high in _VARIATION_SELECTOR for cp in range(low, high + 1))
TAG_CHARACTERS = frozenset(range(0xE0000, 0xE0080))


def _derive() -> frozenset:
    found = set()
    for cp in range(0x110000):
        category = unicodedata.category(chr(cp))
        if (category == "Cf" and cp not in _PREPENDED_CONCATENATION_MARKS) or \
                (category == "Cc" and cp not in _KEPT_CONTROLS):
            found.add(cp)
    for low, high in _OTHER_DEFAULT_IGNORABLE:
        found.update(range(low, high + 1))
    return frozenset(found | VARIATION_SELECTORS)


INVISIBLE = _derive()
_DROP = dict.fromkeys(INVISIBLE)

# Letters a reader takes for an ASCII letter: Cyrillic, Greek, Armenian, and Latin small capitals and IPA
# letters (a subset of UTS #39 confusables.txt, one code point to one letter). NFKC already folds the
# fullwidth, mathematical, circled and compatibility forms. Digits are not folded.
_LOOKALIKES = {
    # Cyrillic
    "А": "A", "В": "B", "С": "C", "Е": "E", "Н": "H", "І": "I", "Ӏ": "I", "Ј": "J", "К": "K", "М": "M",
    "О": "O", "Р": "P", "Ѕ": "S", "Т": "T", "Х": "X", "У": "Y", "Ү": "Y", "Ԛ": "Q", "Ԝ": "W",
    "а": "a", "с": "c", "ԁ": "d", "е": "e", "г": "r", "һ": "h", "і": "i", "ј": "j", "ӏ": "l", "о": "o",
    "р": "p", "ԛ": "q", "ѕ": "s", "у": "y", "ԝ": "w", "х": "x",
    # Greek
    "Α": "A", "Β": "B", "Ε": "E", "Ζ": "Z", "Η": "H", "Ι": "I", "Κ": "K", "Μ": "M", "Ν": "N", "Ο": "O",
    "Ρ": "P", "Τ": "T", "Υ": "Y", "Χ": "X",
    "α": "a", "ϲ": "c", "ι": "i", "ϳ": "j", "κ": "k", "ν": "v", "ο": "o", "ρ": "p", "υ": "u", "χ": "x",
    # Armenian
    "Օ": "O", "Ս": "U", "ց": "g", "հ": "h", "ո": "n", "օ": "o", "զ": "q", "ս": "u",
    # Latin small capitals and IPA letters
    "ᴀ": "a", "ʙ": "b", "ᴄ": "c", "ᴅ": "d", "ᴇ": "e", "ɢ": "g", "ʜ": "h", "ɪ": "i", "ᴊ": "j", "ᴋ": "k",
    "ʟ": "l", "ᴍ": "m", "ɴ": "n", "ᴏ": "o", "ᴘ": "p", "ʀ": "r", "ꜱ": "s", "ᴛ": "t", "ᴜ": "u", "ᴠ": "v",
    "ᴡ": "w", "ʏ": "y", "ᴢ": "z", "ı": "i", "ȷ": "j", "ɑ": "a", "ɡ": "g", "ɩ": "i",
}
LOOKALIKES = str.maketrans(_LOOKALIKES)


def drop_invisible(text: str) -> str:
    return text.translate(_DROP)


def fold(text: str) -> str:
    """What a reader takes ``text`` to say, for comparison only, never for storage.

    Invisible code points removed, NFKC, look-alike letters mapped to the ASCII letter they imitate,
    case-folded, NFKC again (a fold can expose a new composition), the dotted capital I's fold
    rejoined, and invisible code points removed once more. Spacing and punctuation are kept.
    """
    text = unicodedata.normalize("NFKC", drop_invisible(text)).translate(LOOKALIKES)
    text = unicodedata.normalize("NFKC", text.casefold()).replace("i̇", "i")
    return drop_invisible(text)
