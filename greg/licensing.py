"""License qualification for open-source supply: is this package legally usable as GREG uses it?

Directive of 2026-10-22, sections 5.3 and 6: a package that is technically qualified is not yet
legally qualified, and the two states are not interchangeable. Before this module, the Mechanism
Card carried the license string read from installed metadata and nothing read it again, so a
signed read-only ``auto_attach`` could attach a package whose license was undeclared,
non-commercial, source-available or network-copyleft.

Acquired, not built: SPDX expressions are parsed and canonicalized by ``packaging.licenses``
(PyPA; Apache-2.0 OR BSD-2-Clause), which carries the SPDX license list. GREG owns only the
residual: the obligation class of each identifier *as GREG uses the package* (an unmodified
local dependency run in a separate no-network interpreter, never redistributed by GREG), and
the rule that anything it cannot classify goes to the founder. The table fails closed: an
identifier missing from it costs one founder decision, never a silent attach.

This is not a legal review. It reads what the package declares about itself; a wrong
declaration is not detected, and the founder or counsel decides whatever is sent to review.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

try:                                   # packaging >= 24.2 (requirements-dev.txt); absent, every license fails closed
    from packaging.licenses import InvalidLicenseExpression, canonicalize_license_expression
except ImportError:                    # pragma: no cover - exercised by the fail-closed test
    canonicalize_license_expression = None

    class InvalidLicenseExpression(ValueError):
        pass

# Severity order. A class at or below CLEARED_UP_TO may be attached under a signed read-only scope.
PERMISSIVE, WEAK_COPYLEFT, STRONG_COPYLEFT, NETWORK_COPYLEFT, NOT_OPEN, UNKNOWN = (
    "permissive", "weak_copyleft", "strong_copyleft", "network_copyleft", "not_open_source", "unclassified")
ORDER = (PERMISSIVE, WEAK_COPYLEFT, STRONG_COPYLEFT, NETWORK_COPYLEFT, NOT_OPEN, UNKNOWN)
CLEARED_UP_TO = STRONG_COPYLEFT

OBLIGATIONS = {
    PERMISSIVE: "keep the copyright and license notice with any copy GREG ever redistributes",
    WEAK_COPYLEFT: "changes to the package's own files must be released under its license if redistributed; "
                   "using it unmodified as a separate process carries no further obligation",
    STRONG_COPYLEFT: "local, unmodified use in a separate process carries no obligation; redistributing GREG "
                     "together with this package, or linking it into GREG's own code, brings GREG under its terms",
    NETWORK_COPYLEFT: "offering a modified copy to users over a network obliges releasing its source; whether any "
                      "planned GREG service would do so is the founder's decision",
    NOT_OPEN: "not an open-source license: use may be restricted (non-commercial, field of use, competing "
              "service or time-limited terms)",
    UNKNOWN: "GREG cannot tell what the license permits",
}

_PERMISSIVE = ("0BSD", "AFL-3.0", "Apache-1.1", "Apache-2.0", "Artistic-2.0", "BlueOak-1.0.0", "BSD-1-Clause",
               "BSD-2-Clause", "BSD-3-Clause", "BSD-3-Clause-Clear", "BSD-4-Clause", "BSL-1.0", "CC-BY-4.0",
               "CC0-1.0", "curl", "HPND", "ISC", "MIT", "MIT-0", "MIT-CMU", "NCSA", "PostgreSQL", "PSF-2.0",
               "Python-2.0", "Python-2.0.1", "Unicode-3.0", "Unicode-DFS-2016", "Unlicense", "UPL-1.0", "W3C",
               "WTFPL", "X11", "Zlib", "ZPL-2.1")
_WEAK = ("CDDL-1.0", "CDDL-1.1", "EPL-1.0", "EPL-2.0", "LGPL-2.0-only", "LGPL-2.0-or-later",
         "LGPL-2.1-only", "LGPL-2.1-or-later", "LGPL-3.0-only", "LGPL-3.0-or-later", "MPL-1.1", "MPL-2.0",
         "MPL-2.0-no-copyleft-exception", "OFL-1.1", "CC-BY-SA-4.0", "LGPL-2.0", "LGPL-2.1", "LGPL-3.0")
_STRONG = ("GPL-2.0-only", "GPL-2.0-or-later", "GPL-3.0-only", "GPL-3.0-or-later", "GPL-2.0", "GPL-3.0")
# OSL-3.0 (external deployment) and EUPL (online access counts as distribution) reach network use
_NETWORK = ("AGPL-3.0-only", "AGPL-3.0-or-later", "AGPL-3.0", "EUPL-1.1", "EUPL-1.2", "OSL-3.0")
_NOT_OPEN = ("BUSL-1.1", "SSPL-1.0", "Elastic-2.0", "Commons-Clause", "PolyForm-Noncommercial-1.0.0",
             "PolyForm-Small-Business-1.0.0", "CC-BY-NC-4.0", "CC-BY-NC-SA-4.0", "CC-BY-NC-ND-4.0",
             "CC-BY-ND-4.0", "JSON")
SPDX_CLASS = {**{i.lower(): PERMISSIVE for i in _PERMISSIVE}, **{i.lower(): WEAK_COPYLEFT for i in _WEAK},
              **{i.lower(): STRONG_COPYLEFT for i in _STRONG}, **{i.lower(): NETWORK_COPYLEFT for i in _NETWORK},
              **{i.lower(): NOT_OPEN for i in _NOT_OPEN}}
# Exceptions that permit linking without the copyleft reaching the linking program.
LINKING_EXCEPTIONS = ("classpath-exception-2.0", "gcc-exception-3.1", "llvm-exception", "openvpn-openssl-exception")

# Trove classifiers (``License :: ...``) name a family, often without a version. A family is mapped only when
# every version in it has the same obligation class; the rest are unclassified.
TROVE = {
    "OSI Approved :: MIT License": PERMISSIVE, "OSI Approved :: MIT No Attribution License (MIT-0)": PERMISSIVE,
    "OSI Approved :: BSD License": PERMISSIVE, "OSI Approved :: Apache Software License": PERMISSIVE,
    "OSI Approved :: ISC License (ISCL)": PERMISSIVE, "OSI Approved :: Python Software Foundation License": PERMISSIVE,
    "OSI Approved :: zlib/libpng License": PERMISSIVE, "OSI Approved :: The Unlicense (Unlicense)": PERMISSIVE,
    "OSI Approved :: Boost Software License 1.0 (BSL-1.0)": PERMISSIVE,
    "OSI Approved :: Universal Permissive License (UPL)": PERMISSIVE, "OSI Approved :: Historical Permission Notice "
    "and Disclaimer (HPND)": PERMISSIVE, "CC0 1.0 Universal (CC0 1.0) Public Domain Dedication": PERMISSIVE,
    "Public Domain": PERMISSIVE,
    "OSI Approved :: Mozilla Public License 2.0 (MPL 2.0)": WEAK_COPYLEFT,
    "OSI Approved :: GNU Lesser General Public License v2 (LGPLv2)": WEAK_COPYLEFT,
    "OSI Approved :: GNU Lesser General Public License v2 or later (LGPLv2+)": WEAK_COPYLEFT,
    "OSI Approved :: GNU Lesser General Public License v3 (LGPLv3)": WEAK_COPYLEFT,
    "OSI Approved :: GNU Lesser General Public License v3 or later (LGPLv3+)": WEAK_COPYLEFT,
    "OSI Approved :: GNU Library or Lesser General Public License (LGPL)": WEAK_COPYLEFT,
    "OSI Approved :: Eclipse Public License 2.0 (EPL-2.0)": WEAK_COPYLEFT,
    "OSI Approved :: GNU General Public License (GPL)": STRONG_COPYLEFT,
    "OSI Approved :: GNU General Public License v2 (GPLv2)": STRONG_COPYLEFT,
    "OSI Approved :: GNU General Public License v2 or later (GPLv2+)": STRONG_COPYLEFT,
    "OSI Approved :: GNU General Public License v3 (GPLv3)": STRONG_COPYLEFT,
    "OSI Approved :: GNU General Public License v3 or later (GPLv3+)": STRONG_COPYLEFT,
    "OSI Approved :: GNU Affero General Public License v3": NETWORK_COPYLEFT,
    "OSI Approved :: GNU Affero General Public License v3 or later (AGPLv3+)": NETWORK_COPYLEFT,
    "Other/Proprietary License": NOT_OPEN, "Freeware": NOT_OPEN, "Free For Educational Use": NOT_OPEN,
    "Free For Home Use": NOT_OPEN, "Free for non-commercial use": NOT_OPEN, "Shareware": NOT_OPEN,
    "Free To Use But Restricted": NOT_OPEN, "Aladdin Free Public License (AFPL)": NOT_OPEN,
}
# A bare ``License`` field (legacy metadata) is matched only against these exact short names.
TEXT = {"mit": PERMISSIVE, "mit license": PERMISSIVE, "the mit license": PERMISSIVE, "bsd": PERMISSIVE,
        "bsd license": PERMISSIVE, "new bsd license": PERMISSIVE, "3-clause bsd license": PERMISSIVE,
        "bsd 3-clause license": PERMISSIVE, "bsd 2-clause license": PERMISSIVE, "modified bsd license": PERMISSIVE,
        "apache 2.0": PERMISSIVE, "apache-2": PERMISSIVE, "apache license 2.0": PERMISSIVE,
        "apache license, version 2.0": PERMISSIVE, "apache software license": PERMISSIVE, "isc": PERMISSIVE,
        "isc license": PERMISSIVE, "psf": PERMISSIVE, "psf license": PERMISSIVE, "public domain": PERMISSIVE,
        "mpl 2.0": WEAK_COPYLEFT, "lgpl": WEAK_COPYLEFT, "lgplv3": WEAK_COPYLEFT, "gpl": STRONG_COPYLEFT,
        "gplv2": STRONG_COPYLEFT, "gplv3": STRONG_COPYLEFT, "agpl": NETWORK_COPYLEFT, "agplv3": NETWORK_COPYLEFT,
        "expat (mit/x11)": PERMISSIVE, "expat": PERMISSIVE, "psfl": PERMISSIVE, "lgpl v3": WEAK_COPYLEFT,
        "gnu lgpl": WEAK_COPYLEFT, "gnu gpl": STRONG_COPYLEFT, "proprietary": NOT_OPEN, "commercial": NOT_OPEN, "non-commercial": NOT_OPEN}

LIMITS = ("read from the package's own installed metadata, not a legal review: a false declaration, or a rider "
          "inside a full license text, is not detected; "
          "classes describe GREG's use (unmodified, separate no-network process, not redistributed by GREG)")

HELD = (NETWORK_COPYLEFT, NOT_OPEN)
# What kind of permission a term is. Only NOT_OPEN is split: a source-available license (BUSL, SSPL, Elastic,
# Commons Clause, PolyForm) publishes the source under use limits GREG does not read; a restricted-use one
# (non-commercial, field of use, proprietary, non-free) limits who may use it, or for what.
OPEN_SOURCE, SOURCE_AVAILABLE, RESTRICTED_USE, UNCLASSIFIED = (
    "open_source", "source_available", "restricted_use", "unclassified")
_SOURCE_AVAILABLE = re.compile(r"busl|bsl-?1\.1|business-source|sspl|server-side-public|elastic|elv2|commons-?clause"
                               r"|polyform")
# Restrictive wording, matched on normalized text: a rider in a short declaration, or a license name GREG's tables do
# not list (every AGPL and CC NC/ND version, SSPL, BUSL, PolyForm). It only ever makes an unknown stricter; nothing
# here clears, and bare "BSL" (Boost in Debian) is not Business Source. "All rights reserved" and "proprietary" are
# not riders: ordinary BSD and MIT notices contain them. An inclusive phrase ("commercial and non-commercial use")
# is masked first, so it does not read as a non-commercial restriction. Model-weight licenses are named by family,
# any version: Llama 2 and later, Gemma, every OpenRAIL/RAIL variant, the Qwen research and Tongyi Qianwen license
# agreements, the DeepSeek and DeepFloyd licenses, Mistral's non-production and research licenses, and research-only
# terms. Each attaches conditions to the model and what is made with it (an acceptable-use policy, use restrictions
# passed to every downstream user, a user-count threshold, research-only use).
RIDERS = ((r"commons-?clause", NOT_OPEN),
          (r"server-side-public-license|(?<![a-z0-9])sspl(?:-?v?[0-9][0-9.]*)?(?![a-z])", NOT_OPEN),
          (r"business-source-license|(?<![a-z0-9])busl(?:-?v?[0-9][0-9.]*)?(?![a-z])|(?<![a-z0-9])bsl-?1\.1(?![0-9])",
           NOT_OPEN),
          (r"elastic-license|(?<![a-z0-9])elv2(?![a-z0-9])|(?<![a-z0-9])elastic-2\.0(?![0-9])", NOT_OPEN),
          (r"polyform", NOT_OPEN),
          (r"non-?commercial|not-for-commercial|evaluation-only|(?<![a-z])by-n[cd](?![a-z])", NOT_OPEN),
          (r"(?<![a-z0-9])llama-?[2-9](?:\.[0-9]+)?(?![0-9])", NOT_OPEN), (r"(?<![a-z0-9])gemma(?![a-z0-9])", NOT_OPEN),
          (r"(?<![a-z])(?:open-?)?rail(?:-m|-license|-[0-9.]+|\+\+)?(?![a-z])", NOT_OPEN),
          (r"tongyi-qianwen|(?<![a-z])qwen-(?:research(?:-license)?|license)", NOT_OPEN),
          (r"(?<![a-z])(?:deepseek|deepfloyd(?:-if)?)-license", NOT_OPEN),
          (r"non-?production-license|mistral-ai-research-license|research-(?:use-|purposes?-)?only", NOT_OPEN),
          (r"(?<![a-z])agpl|affero", NETWORK_COPYLEFT))
INCLUSIVE = (r"(?<![a-z])(?<!non-)commercial-?(?:and/or|and|or|&|/)-?non-?commercial"
             r"|non-?commercial-?(?:and/or|and|or|&|/)-?commercial")
# A sentence that restricts ("Commercial and non-commercial use require a separate license") keeps its phrase, so
# the rider still reads it; only a sentence that grants both is masked.
RESTRICTING = (r"requir|prohibit|forbid|not-permitted|not-allowed|not-be-used|may-not|must-not|cannot|must-obtain"
               r"|separate-licen|(?:without|written|prior|explicit|express|separate)-permission"
               r"|(?<!without-)(?<!no-)restrict|purchase|royalt|(?<![a-z])paid(?![a-z])|(?<![a-z])fees?(?![a-z])")


def _masked(text: str) -> str:
    """``text`` normalized, its inclusive commercial phrases masked in every sentence that does not restrict."""
    out = []
    for sentence in re.split(r"(?<=[.!?;])\s+|\n+", text):
        norm = _norm(sentence)
        out.append(norm if re.search(RESTRICTING, norm) else re.sub(INCLUSIVE, " ", norm))
    return " ".join(out)
# The phrases are searched only in a short declaration. A full license text (scipy's bundles the GPL of its
# compiled runtime, which says "noncommercially") is not interpreted: a rider inside one is not detected.
SHORT_LINES, SHORT_CHARS = 5, 600


def _worst(classes) -> str:
    return max(classes, key=ORDER.index) if classes else UNKNOWN


def _best(classes) -> str:
    return min(classes, key=ORDER.index) if classes else UNKNOWN


def _norm(text: str) -> str:
    return re.sub(r"[\s_]+", "-", text.strip().lower())


def _riders(text: str) -> list:
    """(matched wording, class) for each restrictive rider in ``text``."""
    norm = _masked(text)
    return [(m.group(0), cls) for pattern, cls in RIDERS for m in [re.search(pattern, norm)] if m]


def _category(cls: str, ident: str = "") -> str:
    if cls == UNKNOWN:
        return UNCLASSIFIED
    if cls != NOT_OPEN:
        return OPEN_SOURCE
    return SOURCE_AVAILABLE if _SOURCE_AVAILABLE.search(_norm(ident)) else RESTRICTED_USE


def _table_class(name: str, dialect: str) -> str:
    """One license name in GREG's tables: Debian's spelling first (DEP-5), then the SPDX identifier, then a
    GPL-family -only/-or-later variant. Anything else is unknown."""
    key = _norm(name)
    keys = [key, key.rstrip("+")]
    if re.match(r"^[al]?gpl-", key):
        keys += [re.sub(r"-only$", "", key), re.sub(r"-or-later$", "+", key), re.sub(r"-or-later$", "", key)]
    for k in keys:
        cls = (DEBIAN.get(k) if dialect == "dep5" else None) or SPDX_CLASS.get(k)
        if cls:
            return cls
    return UNKNOWN


def _lookup(name: str, dialect: str) -> str:
    """One license name: GREG's tables, then restrictive wording in the name (a family at any version)."""
    cls = _table_class(name, dialect)
    if cls != UNKNOWN:
        return cls
    held = [cls for _, cls in _riders(name)]
    return _worst(held) if held else UNKNOWN


def _atom(name: str, dialect: str) -> dict:
    """One license, with any "WITH"/"with" addition bound to it. An exception grants a permission, so it keeps the
    base class (a linking exception lowers strong copyleft to weak); an unknown base is never lowered. In DEP-5, an
    addition that is not an exception, or that names a restrictive license, is classified, and a restrictive
    addition is never hidden by an unknown base."""
    base, *rest = re.split(r"\s+with\s+", name.strip(), maxsplit=1, flags=re.I)
    cls = _lookup(base, dialect)
    unlisted = cls != UNKNOWN and _table_class(base, dialect) == UNKNOWN     # named like a family, terms unread
    if rest:
        addition = rest[0]
        extra = _lookup(addition, dialect) if dialect == "dep5" else UNKNOWN
        if dialect == "spdx" or ("exception" in addition.lower() and extra not in HELD):
            if cls == STRONG_COPYLEFT and _norm(addition) in LINKING_EXCEPTIONS:
                cls = WEAK_COPYLEFT
        else:
            restrictive = [c for c in (cls, extra) if c in HELD]
            unlisted = unlisted or UNKNOWN in (cls, extra) or _table_class(addition, dialect) == UNKNOWN
            cls = _worst(restrictive or [cls, extra])        # a restrictive addition is never hidden by an unknown
    atom = {"atom": name.strip()[:120], "class": cls, "category": _category(cls, name)}
    return {**atom, "unlisted": True} if unlisted and cls != UNKNOWN else atom


def _parse(expression: str, dialect: str) -> dict:
    """A license expression as a tree: {"atom", "class", "category"} | {"and": [...]} | {"or": [...]}.

    One grammar serves SPDX (canonicalized by packaging.licenses) and DEP-5 short names. Precedence, tightest
    first: WITH, AND, OR; in DEP-5 a comma before "and"/"or" binds loosest ("GPL-1+ or Artistic, and BSD-3-clause"
    is (GPL-1+ or Artistic) and BSD-3-clause), and a bare comma lists licenses that all apply. Parentheses group."""
    tokens = re.findall(r"\(|\)|,|[^\s(),]+", expression)
    position = depth = 0

    def peek():
        return tokens[position].lower() if position < len(tokens) else None

    def unit():
        nonlocal position, depth
        if peek() == "(":
            position += 1
            depth += 1
            if depth > MAX_NESTING:
                raise ValueError("parentheses nested too deeply")
            node = sequence()
            depth -= 1
            if peek() != ")":
                raise ValueError("unbalanced parenthesis")
            position += 1
            return node
        words = []
        while peek() not in (None, "(", ")", ",", "and", "or"):
            words.append(tokens[position])
            position += 1
        if not words:
            raise ValueError("a license name is missing")
        return _atom(" ".join(words), dialect)

    def joined(operator, operand):
        nonlocal position
        nodes = [operand()]
        while peek() == operator:
            position += 1
            nodes.append(operand())
        return nodes[0] if len(nodes) == 1 else {operator: nodes}

    def disjunction():
        return joined("or", lambda: joined("and", unit))

    def sequence():
        nonlocal position
        node = disjunction()
        while peek() == ",":
            position += 1
            operator = "and"                                 # a bare comma lists licenses that all apply
            if peek() in ("and", "or"):
                operator = peek()
                position += 1
            node = {operator: [node, disjunction()]}
        return node

    node = sequence()
    if position != len(tokens):
        raise ValueError("unexpected text after the expression")
    return node


MAX_NESTING, MAX_WORDS = 32, 256


def _tree(expression: str, dialect: str) -> dict:
    """``_parse``, failing closed: an unparseable expression is unknown, and every restrictive name in it still
    counts."""
    try:
        return _parse(expression, dialect)
    except ValueError:                        # malformed, or nested past MAX_NESTING
        words = [w for w in re.findall(r"[^\s(),]+", expression) if w.lower() not in ("and", "or", "with")]
        held = [a for a in (_atom(w, dialect) for w in words[:MAX_WORDS]) if a["class"] in HELD]
        held += [{"atom": f"mentions '{p}'", "class": c, "category": _category(c, p)} for p, c in _riders(expression)]
        return {"and": held + [{"atom": expression.strip()[:120] or "(empty)", "class": UNKNOWN,
                                "category": UNCLASSIFIED, "note": "not a parseable license expression"}]}


def _named_restrictions(text: str, label: str) -> list:
    """The licenses ``text`` names, word by word, that GREG's tables hold restrictive, for text no parser accepts
    ("EUPL-1.2 AND (MIT"). Restrictive wording finds AGPL, SSPL, BUSL and the like anywhere; EUPL, OSL and JSON are
    restrictive by the table alone, so without this they vanished with the parse. Exact names only: a word is never
    read as wording here ("non-commercial" in "commercial and non-commercial use" is not a restriction)."""
    words = [w for w in re.findall(r"[^\s(),]+", text) if w.lower() not in ("and", "or", "with")]
    return [{"atom": f"{label} mentions '{w[:80]}'", "class": c, "category": _category(c, w)}
            for w in words[:MAX_WORDS] for c in [_table_class(w, "spdx")] if c in HELD]


def _atoms(node: dict) -> list:
    return [node] if "atom" in node else [a for child in node.get("and") or node["or"] for a in _atoms(child)]


def _held_eval(node: dict) -> tuple[str, bool, list]:
    """(class, held, elected terms). AND applies every term: the worst class, held when any term is a known
    network-copyleft or not-open license, whatever else is unknown. OR elects one whole alternative: the best class
    (unknown ranks worst), and on a tie one with no known restriction. The elected terms are one alternative's."""
    if "atom" in node:
        return node["class"], node["class"] in HELD, [node]
    parts = [_held_eval(child) for child in node.get("and") or node["or"]]
    if "and" in node:
        return _worst([p[0] for p in parts]), any(p[1] for p in parts), [a for p in parts for a in p[2]]
    cls, _, elected = min(parts, key=lambda p: (ORDER.index(p[0]), p[1]))
    cleared = any(ORDER.index(p[0]) <= ORDER.index(CLEARED_UP_TO) for p in parts)
    return cls, not cleared and any(p[1] for p in parts), elected


def _part_tree(part: dict) -> dict:
    """The expression tree of one assessed part. Parts recorded before trees existed: their terms all apply."""
    if isinstance(part.get("tree"), dict):
        return part["tree"]
    terms = [t.get("tree") if isinstance(t.get("tree"), dict) else
             {"atom": str(t.get("id"))[:120], "class": t.get("class") or UNKNOWN,
              "category": t.get("category") or _category(t.get("class") or UNKNOWN, str(t.get("id")))}
             for t in part.get("terms") or []]
    if not terms:
        cls = part.get("class") or UNKNOWN
        return {"atom": str(part.get("expression") or "UNREAD")[:120], "class": cls, "category": _category(cls)}
    return terms[0] if len(terms) == 1 else {"and": terms}


def _text_declaration(text: str) -> dict | None:
    """What a legacy ``License`` field declares, or None when it carries no classification (a full license text).
    ``spdx`` says whether the field is a valid SPDX expression: one GREG cannot classify still counts, since a
    LicenseRef or an unlisted identifier names terms nobody has read."""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    one = lines[0] if len(lines) == 1 else None
    parsed = None
    if one is not None:
        try:
            parsed = _tree(str(canonicalize_license_expression(one)), "spdx")
        except InvalidLicenseExpression:
            parsed = None
        cls = _held_eval(parsed)[0] if parsed is not None else UNKNOWN
        if cls != UNKNOWN:
            return {"tree": parsed, "class": cls, "id": one[:120], "spdx": True}
    if len(lines) <= SHORT_LINES and len(text) <= SHORT_CHARS:
        atoms = [{"atom": f"License field mentions '{phrase}'", "class": cls, "category": _category(cls, phrase)}
                 for phrase, cls in _riders(text)]
        if one is not None and parsed is None:       # one line packaging rejects: the restrictive names in it count
            atoms += _named_restrictions(one, "License field")
        if atoms:
            tree = atoms[0] if len(atoms) == 1 else {"and": atoms}
            return {"tree": tree, "class": _held_eval(tree)[0], "id": atoms[0]["atom"], "spdx": False}
    if one is None:
        return None                          # a full license text: no short declaration to classify
    if parsed is not None:
        return {"tree": parsed, "class": UNKNOWN, "id": one[:120], "spdx": True}
    cls = TEXT.get(one.lower().rstrip("."), UNKNOWN)
    return {"tree": {"atom": one[:120], "class": cls, "category": _category(cls, one)}, "class": cls, "id": one[:120],
            "spdx": False}


def _part(name, basis, shown, tree, uncertainty=()) -> dict:
    cls, _, elected = _held_eval(tree)
    unknown = [a["atom"] for a in elected if a["class"] == UNKNOWN]
    unlisted = [a["atom"] for a in elected if a.get("unlisted")]
    notes = list(uncertainty) + ([f"not classified by GREG: {', '.join(unknown)[:200]}"] if unknown else []) + \
        ([f"named like a known family, not in GREG's tables: {', '.join(unlisted)[:200]}"] if unlisted else [])
    return {"distribution": name, "basis": basis, "expression": shown, "class": cls,
            "terms": [{"id": a["atom"], "class": a["class"], "category": a["category"]} for a in _atoms(tree)],
            "tree": tree, "restrictive": [a["atom"] for a in elected if a["class"] in HELD], "uncertainty": notes}


def declared(dist) -> dict:
    """The license one installed distribution declares, classified.

    An SPDX ``License-Expression`` (PEP 639) or trove classifiers are the primary declaration. The others are read
    beside it: a classifier, or a short legacy ``License`` field, that declares something stricter than the primary
    one (or any network-copyleft or not-open term) is added to it, and every term then applies; a License field
    that is a valid SPDX expression GREG cannot classify (a LicenseRef) counts as unknown. A disagreement that does
    not raise the class is recorded as uncertainty. A multi-line field alone is a license text GREG does not
    interpret: unclassified."""
    meta = dist.metadata
    name = meta["Name"]
    if canonicalize_license_expression is None:
        return {"distribution": name, "basis": "packaging.licenses unavailable on this body", "expression": "UNREAD",
                "class": UNKNOWN, "terms": [], "restrictive": [], "uncertainty": ["the SPDX parser is missing"]}
    text = meta.get("License") or ""
    text_decl = _text_declaration(text) if text.strip() else None
    expression = (meta.get("License-Expression") or "").strip()
    trove = [c.split("::", 1)[1].strip() for c in meta.get_all("Classifier") or () if c.startswith("License ::")]
    if len(trove) > 1:                   # the bare "OSI Approved" parent beside a specific classifier adds nothing
        trove = [t for t in trove if t != "OSI Approved"]
    trove_atoms = [{"atom": t, "class": TROVE.get(t, UNKNOWN), "category": _category(TROVE.get(t, UNKNOWN), t)}
                   for t in trove]
    notes, note = [], None
    if expression:
        try:
            canonical = str(canonicalize_license_expression(expression))
            tree, basis, shown = _tree(canonical, "spdx"), \
                "License-Expression (PEP 639), parsed by packaging.licenses", canonical
        except InvalidLicenseExpression as exc:      # unparseable: unknown, its restrictive wording still counts
            atoms = [{"atom": f"License-Expression mentions '{p}'", "class": c, "category": _category(c, p)}
                     for p, c in _riders(expression)] + _named_restrictions(expression, "License-Expression")
            tree = {"and": atoms + [{"atom": expression[:120], "class": UNKNOWN, "category": UNCLASSIFIED}]}
            basis, shown, note = "License-Expression (PEP 639), unparseable", expression, str(exc)[:160]
            notes.append("the License-Expression is not valid SPDX")
        cls = _held_eval(tree)[0]
        present = {a["class"] for a in _atoms(tree)}
        for atom in trove_atoms:         # a classifier naming a class no term of the expression has contradicts it
            if atom["class"] == UNKNOWN:
                if atom["atom"].startswith("OSI Approved"):
                    notes.append(f"classifier '{atom['atom']}' is not classified by GREG; the expression governs")
                else:                    # a non-OSI license GREG does not list: its terms are unknown and count
                    tree = {"and": [tree, atom]}
                    basis += "; a classifier GREG cannot classify"
                continue
            if atom["class"] in present and (atom["class"] not in HELD or atom["atom"].startswith("OSI Approved")):
                continue                 # it names an alternative: agreement. A non-OSI restriction names no license
                                         # of the expression, so it always counts
            if ORDER.index(atom["class"]) > ORDER.index(cls) or atom["class"] in HELD:
                tree = {"and": [tree, atom]}
                basis += "; a classifier declares something stricter"
            else:
                notes.append(f"declarations disagree: classifier '{atom['atom']}' is less strict than the expression; "
                             "the stricter declaration governs")
    elif trove:
        # several classifiers do not say whether they are alternatives or all apply: assume all apply
        tree = trove_atoms[0] if len(trove_atoms) == 1 else {"and": trove_atoms}
        basis, shown = "trove classifiers (family; version may be unstated)", " AND ".join(trove)
        if len({a["class"] for a in trove_atoms if a["class"] != UNKNOWN}) > 1:
            notes.append("classifiers of different classes: GREG assumes all of them apply")
    elif text_decl is not None:
        basis = ("License field, restrictive wording" if text_decl["id"].startswith("License field mentions")
                 else "License field, exact short-name match" if text_decl["class"] != UNKNOWN
                 else "License field, not a recognised short name")
        return _part(name, basis, text_decl["id"], text_decl["tree"])
    elif text.strip():
        return _part(name, "License field holds a full license text GREG does not interpret",
                     text.strip().splitlines()[0][:120],
                     {"atom": text.strip().splitlines()[0][:120], "class": UNKNOWN, "category": UNCLASSIFIED})
    else:
        return _part(name, "nothing declared", "UNDECLARED", {"atom": "UNDECLARED", "class": UNKNOWN,
                                                              "category": UNCLASSIFIED})
    # beside a primary declaration, an unrecognised free-text name is informational; a recognised stricter one, a
    # restrictive one, or an SPDX expression GREG cannot classify counts
    cls = _held_eval(tree)[0]
    if text_decl is not None:
        text_class = text_decl["class"]
        if (text_class != UNKNOWN and (ORDER.index(text_class) > ORDER.index(cls) or text_class in HELD)) or \
                (text_class == UNKNOWN and text_decl["spdx"]):
            tree = {"and": [tree, text_decl["tree"]]}
            basis += "; the License field declares something stricter" if text_class != UNKNOWN else \
                "; the License field is an SPDX expression GREG cannot classify"
        elif text_class != UNKNOWN and text_class != cls:
            notes.append(f"declarations disagree: the License field ('{text_decl['id']}') is less strict than the "
                         "primary declaration; the stricter declaration governs")
    part = _part(name, basis, shown, tree, notes)
    return {**part, "note": note} if note else part


def _elected(part: dict) -> list:
    return _held_eval(_part_tree(part))[2]


def assess(dist, dependencies=()) -> dict:
    """Assessment of a package and the dependencies that run in its interpreter (all apply together)."""
    parts = [declared(dist)] + [declared(d) for d in dependencies if d is not None]
    worst = _worst([p["class"] for p in parts])
    cleared = ORDER.index(worst) <= ORDER.index(CLEARED_UP_TO)
    verdict = ("CLEARED" if worst == PERMISSIVE else "CLEARED_WITH_OBLIGATIONS") if cleared else "FOUNDER_REVIEW"
    blocking = [p for p in parts if ORDER.index(p["class"]) > ORDER.index(CLEARED_UP_TO)]
    reason = ("; ".join(f"{p['distribution']}: {p['expression']} ({p['class'].replace('_', ' ')}, {p['basis']})"
                        + (f"; restrictive: {', '.join(p['restrictive'])}" if p.get("restrictive") else "")
                        for p in blocking) if blocking else "every declared license is cleared for GREG's use")
    elected = [a for p in parts for a in _elected(p)]
    return {"verdict": verdict, "class": worst, "auto_attach": cleared, "reason": reason[:400],
            "obligations": sorted({OBLIGATIONS[a["class"]] for a in elected}), "parts": parts,
            "restrictive": [r for p in parts for r in p.get("restrictive") or []],
            "categories": sorted({a["category"] for a in elected}),
            "uncertainty": [f"{p['distribution']}: {u}" for p in parts for u in p.get("uncertainty") or []],
            "policy": f"auto-attach under a signed read-only scope up to {CLEARED_UP_TO.replace('_', ' ')}; anything "
                      "stricter or unclassified waits for the founder's own attach",
            "parser": "packaging.licenses (PyPA)", "limits": LIMITS}


def auto_attach_allowed(provenance: dict) -> tuple[bool, str]:
    """Whether a package manifest's license permits attach without the founder's own command."""
    assessment = provenance.get("license_assessment")
    if not isinstance(assessment, dict):          # a card recorded before assessments: read what is installed now
        assessment = _reassess(provenance)
        if assessment is None:
            return False, "no license assessment on its Mechanism Card"
    return bool(assessment.get("auto_attach")), assessment.get("reason", "")


def _reassess(provenance: dict) -> dict | None:
    """Assess the distribution and common-mode dependencies a card names, as installed at this version."""
    import importlib.metadata
    name, version = provenance.get("distribution"), provenance.get("version")
    if not name:
        return None
    try:
        dist = importlib.metadata.distribution(name)
    except importlib.metadata.PackageNotFoundError:
        return None
    if dist.version != version:
        return None                               # not the package that was qualified
    deps = []
    for dep in provenance.get("common_mode") or ():
        try:
            deps.append(importlib.metadata.distribution(dep.get("distribution")))
        except (importlib.metadata.PackageNotFoundError, TypeError, ValueError):
            pass
    return assess(dist, deps)


# -- installed system binaries (Debian DEP-5 copyright files) ---------------------------------------------------
# A binary Genesis acquires (sha256sum, wc, pdftotext) belongs to an operating-system package. On Debian-family
# bodies (Debian, Ubuntu, ChromeOS Crostini) dpkg names that package and its machine-readable copyright file
# (https://www.debian.org/doc/packaging-manuals/copyright-format/1.0/) declares the licenses. Elsewhere (macOS,
# a hand-built binary) nothing is readable: the assessment is None and the caller keeps its prior behaviour.
DEBIAN = {"gpl-2": STRONG_COPYLEFT, "gpl-2+": STRONG_COPYLEFT, "gpl-3": STRONG_COPYLEFT, "gpl-3+": STRONG_COPYLEFT,
          "gpl": STRONG_COPYLEFT, "lgpl-2": WEAK_COPYLEFT, "lgpl-2+": WEAK_COPYLEFT, "lgpl-2.1": WEAK_COPYLEFT,
          "lgpl-2.1+": WEAK_COPYLEFT, "lgpl-3": WEAK_COPYLEFT, "lgpl-3+": WEAK_COPYLEFT, "mpl-2.0": WEAK_COPYLEFT,
          "agpl-3": NETWORK_COPYLEFT, "agpl-3+": NETWORK_COPYLEFT, "expat": PERMISSIVE, "mit": PERMISSIVE,
          "isc": PERMISSIVE, "zlib": PERMISSIVE, "apache-2.0": PERMISSIVE, "bsd-2-clause": PERMISSIVE,
          "bsd-3-clause": PERMISSIVE, "bsd-4-clause": PERMISSIVE, "bsd-4-clause-uc": PERMISSIVE,
          "public-domain": PERMISSIVE, "cc0-1.0": PERMISSIVE, "psf-2": PERMISSIVE, "x11": PERMISSIVE,
          "fsfap": PERMISSIVE, "fsful": PERMISSIVE, "fsfullr": PERMISSIVE, "gfdl-1.3+": WEAK_COPYLEFT,
          "non-free": NOT_OPEN, "proprietary": NOT_OPEN, "sspl-1": NOT_OPEN, "sspl-1.0": NOT_OPEN,
          "busl-1.1": NOT_OPEN, "elastic-2.0": NOT_OPEN, "cc-by-nc-4.0": NOT_OPEN, "cc-by-nc-sa-4.0": NOT_OPEN,
          "gfdl": WEAK_COPYLEFT, "gfdl-ni": WEAK_COPYLEFT, "gfdl-niv-1.3": WEAK_COPYLEFT, "gfdl-niv-1.3+": WEAK_COPYLEFT,
          "artistic": WEAK_COPYLEFT, "artistic-2.0": PERMISSIVE, "gpl-1": STRONG_COPYLEFT, "gpl-1+": STRONG_COPYLEFT, "gfdl-1.2+": WEAK_COPYLEFT, "gfdl-1.3": WEAK_COPYLEFT}
DPKG_TIMEOUT = 5
FILES_ASSUMPTION = ("each Files stanza is assumed to reach the binary: GREG cannot tell which source files it was "
                    "built from")


def _debian_class(expression: str) -> str:
    """A DEP-5 License short-name expression: 'or' takes the best alternative, 'and' the worst, and ', and' binds
    loosest ('GPL-1+ or Artistic, and BSD-3-clause' is (GPL-1+ or Artistic) and BSD-3-clause). 'with ... exception'
    keeps the base license's class (Debian names many exceptions; GREG does not downgrade on an unknown one); any
    other 'with' addition, or one naming a restrictive license, is classified and the stricter class applies."""
    return _held_eval(_tree(expression, "dep5"))[0]


def _held_terms(terms) -> list:
    """Terms that hold a binary: a known network-copyleft or not-open license that applies, whatever else in the
    same field or file is unclassified."""
    return [t for t in terms if t.get("held") or t["class"] in HELD]


def _dep5_stanzas(text: str) -> list:
    """The paragraphs of a DEP-5 file as {field: [values]}. A continuation line extends the field above it (a
    multi-line Files list; a License's text, which is not read). Field order inside a paragraph is not significant
    (deb822): a License line before its Files line belongs to it. A second Files line in one paragraph, or a Files
    line in the header paragraph, starts a new stanza; a repeated License line is kept, not overwritten."""
    stanzas, fields, last = [], {}, None
    for line in text.splitlines():
        if not line.strip():
            if fields:
                stanzas.append(fields)
            fields, last = {}, None
            continue
        if line.startswith("#"):
            continue
        if line[0].isspace():
            if last == "files":
                fields["files"][-1] += " " + line.strip()
            continue
        if ":" not in line:
            last = None
            continue
        key, value = line.split(":", 1)
        key = key.strip().lower()
        if key == "files" and ("files" in fields or "format" in fields):
            stanzas.append(fields)
            fields = {}
        fields.setdefault(key, []).append(value.strip())
        last = key
    if fields:
        stanzas.append(fields)
    return stanzas


def dep5(text: str) -> dict | None:
    """Every License declared by a Files stanza (or the header) of a DEP-5 file, with the files it covers; None if
    it is not DEP-5. A stand-alone License paragraph defines a license and applies to nothing by itself; a Files
    stanza with no License is unclassified, not skipped."""
    stanzas = _dep5_stanzas(text)
    if not stanzas or "format" not in stanzas[0]:
        return None
    terms = []
    for index, fields in enumerate(stanzas):
        applies = index == 0 or "files" in fields          # a stand-alone License paragraph only defines a license
        if not applies or (index == 0 and "license" not in fields):
            continue
        files = " ".join(fields["files"]).split() if "files" in fields else None
        for synopsis in fields.get("license") or [""]:
            tree = _tree(synopsis, "dep5") if synopsis else {"atom": "no License field", "class": UNKNOWN,
                                                             "category": UNCLASSIFIED}
            cls, held, elected = _held_eval(tree)
            restrictive = [a for a in elected if a["class"] in HELD]
            terms.append({"id": (synopsis or "no License field")[:120], "class": cls, "held": held,
                          "category": restrictive[0]["category"] if restrictive else _category(cls),
                          "restrictive": [a["atom"] for a in restrictive], "files": files,
                          "stanza": "header" if index == 0 else "files", "tree": tree})
    if not terms:
        return None
    header = [t["class"] for t in terms if t["stanza"] == "header"]
    stanzas = [t["class"] for t in terms if t["stanza"] == "files"]
    disagree = bool(header and stanzas and header[0] != _worst(stanzas))
    return {"expression": " AND ".join(dict.fromkeys(t["id"] for t in terms)), "terms": terms,
            "class": _worst([t["class"] for t in terms]), "held": any(t["held"] for t in terms),
            "uncertainty": ["the header's License summary and the Files stanzas declare different classes; every one "
                            "applies"] if disagree else []}


def binary_assessment(package: str, text: str | None) -> dict:
    """The P0 assessment of an OS package from its copyright file's text (None: missing or unreadable)."""
    parsed = dep5(text) if text is not None else None
    part = ({"distribution": f"{package} (dpkg)", "basis": "Debian DEP-5 copyright file", **parsed} if parsed else
            {"distribution": f"{package} (dpkg)", "basis": "copyright file missing or not DEP-5",
             "expression": "UNREAD", "class": UNKNOWN, "terms": []})
    worst = part["class"]
    held = _held_terms(part["terms"])
    cleared = ORDER.index(worst) <= ORDER.index(CLEARED_UP_TO)
    verdict = ("FOUNDER_REVIEW" if held else ("CLEARED" if worst == PERMISSIVE else "CLEARED_WITH_OBLIGATIONS")
               if cleared else "UNCLASSIFIED_PRIOR_BEHAVIOUR")
    reason = ("; ".join(f"{t['id']} ({t['class'].replace('_', ' ')}"
                        + (f"; restrictive: {', '.join(t['restrictive'])}" if t.get("restrictive") and
                           t["restrictive"] != [t["id"]] else "")
                        + (f"; files {' '.join(t['files'])[:80]}" if t.get("files") else "") + ")" for t in held)
              if held else "every declared license is cleared for GREG's use" if cleared else
              f"{part['distribution']}: some declared license is not classified by GREG; attach behaviour is as "
              "before licenses were read")
    elected = [a for t in part["terms"] for a in _held_eval(_part_tree({"terms": [t]}))[2]]
    unknown = sorted({a["atom"] for a in elected if a["class"] == UNKNOWN})
    return {"verdict": verdict, "class": worst, "held": bool(held), "auto_attach": not held, "reason": reason[:400],
            "obligations": sorted({OBLIGATIONS[a["class"]] for a in elected} or {OBLIGATIONS[worst]}),
            "categories": sorted({a["category"] for a in elected} or {_category(worst)}),
            "uncertainty": ([FILES_ASSUMPTION] + parsed["uncertainty"] if parsed else
                            ["no DEP-5 copyright file could be read"])
            + ([f"not classified by GREG: {', '.join(unknown)[:200]}"] if unknown else []),
            "parts": [part], "policy": "binary: held on any known network-copyleft or not-open term",
            "parser": "dpkg-query + DEP-5 (GREG reader)", "limits": LIMITS}


def system_binary(binary: str) -> dict | None:
    """The DEP-5 assessment of the OS package that owns ``binary``, or None when no package manager says."""
    import os
    import shutil
    import subprocess
    dpkg = shutil.which("dpkg-query")
    if dpkg is None:
        return None
    real = os.path.realpath(binary)
    try:
        proc = subprocess.run([dpkg, "-S", real], capture_output=True, text=True, timeout=DPKG_TIMEOUT,
                              env={"PATH": "/usr/bin:/bin", "LC_ALL": "C"})
    except (OSError, subprocess.TimeoutExpired):
        return None
    owners = [line.split(":", 1)[0].strip() for line in proc.stdout.splitlines()
              if line.rstrip().endswith(": " + real) or line.rstrip().endswith(":" + real)]
    if proc.returncode or len(set(owners)) != 1:
        return None
    package = owners[0].split(":")[0]                          # strip a multiarch qualifier
    if not re.fullmatch(r"[a-z0-9][a-z0-9.+-]+", package):
        return None
    try:
        text = (Path("/usr/share/doc") / package / "copyright").read_text(errors="replace")
    except OSError:
        text = None
    return binary_assessment(package, text)


# -- model weights (the license an installed Ollama model carries) ----------------------------------------------
# GREG's local models run through Ollama (greg/models.py OllamaRoute; docs/OPEN_SOURCE_STACK.md). A pulled model
# stores its license as layers of mediaType application/vnd.ollama.image.license in its manifest
# (<models>/manifests/<host>/<namespace>/<model>/<tag>), each a full license text in a content-addressed blob
# (<models>/blobs/sha256-<hex>). The software licenses above say nothing about the weights: Ollama is MIT whatever
# the model is. A license text is classified by what it is, not by its title: Apache-2.0 and MIT only when the
# terms match the standard text exactly, restrictive wording anywhere in it is held, and any other text is
# unclassified. Weights are never cleared by default; nothing here attaches or runs a model.

OLLAMA_LICENSE = "application/vnd.ollama.image.license"
OLLAMA_WEIGHTS = ("application/vnd.ollama.image.model", "application/vnd.ollama.image.projector",
                  "application/vnd.ollama.image.adapter")
OLLAMA_HOST, OLLAMA_NAMESPACE, OLLAMA_TAG = "registry.ollama.ai", "library", "latest"
MAX_MANIFEST_BYTES = MAX_MODEL_LICENSE_BYTES = 1 << 20
MODEL_LIMITS = ("read from the model's own license layers in the local Ollama store, not a legal review: Apache-2.0 "
                "and MIT are recognised only when their terms match the standard text; any other text, and any text "
                "beside those terms, is unclassified; the weights' embedded metadata (GGUF general.license) and the "
                "base model a derivative was made from are not read")
# The terms of Apache-2.0, sections 1-9, from "TERMS AND CONDITIONS FOR USE" through "END OF TERMS AND CONDITIONS",
# lowercased with whitespace and quotation marks normalized (``_flat``). Measured on Debian's
# /usr/share/common-licenses/Apache-2.0 and on 15 copies shipped by installed Python packages.
APACHE_2_TERMS_SHA256 = "bd01d1cbace1131cd60e3341a451ccd492ef00582e93b8a2b5a4caa1c919fe7a"
_APACHE_HEADER = r"(?:apache license,? version 2\.0,? january 2004 https?://www\.apache\.org/licenses/? ?)?"
_APACHE_NOTICE = (r"(copyright .{0,300}?) licensed under the apache license, version 2\.0 \(the \"license\"\); you may not "
                  r"use this file except in compliance with the license\. you may obtain a copy of the license at "
                  r"https?://www\.apache\.org/licenses/license-2\.0 unless required by applicable law or agreed to in "
                  r"writing, software distributed under the license is distributed on an \"as is\" basis, without "
                  r"warranties or conditions of any kind, either express or implied\. see the license for the "
                  r"specific language governing permissions and limitations under the license\.")
_APACHE_APPENDIX = (r"appendix: how to apply the apache license to your work\. to apply the apache license to your work, "
                    r"attach the following boilerplate notice, with the fields enclosed by brackets \"\[\]\" replaced "
                    r"with your own identifying information\. \(don't include the brackets!\) the text should be "
                    r"enclosed in the appropriate comment syntax for the file format\. we also recommend that a file or "
                    r"class name and description of purpose be included on the same \"printed page\" as the copyright "
                    r"notice for easier identification within third-party archives\. " + _APACHE_NOTICE)
_MIT_TERMS = ("permission is hereby granted, free of charge, to any person obtaining a copy of this software and "
              "associated documentation files (the \"software\"), to deal in the software without restriction, "
              "including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, "
              "and/or sell copies of the software, and to permit persons to whom the software is furnished to do so, "
              "subject to the following conditions: the above copyright notice and this permission notice shall be "
              "included in all copies or substantial portions of the software. the software is provided \"as is\", "
              "without warranty of any kind, express or implied, including but not limited to the warranties of "
              "merchantability, fitness for a particular purpose and noninfringement. in no event shall the authors "
              "or copyright holders be liable for any claim, damages or other liability, whether in an action of "
              "contract, tort or otherwise, arising from, out of or in connection with the software or the use or "
              "other dealings in the software.")
_MIT_TITLE = re.compile(r"(?:the )?mit license(?: \(mit\))?|all rights reserved\.?")
# A copyright notice and nothing else: "Copyright (c) <years> <holder>", where the holder is a name. Terms hide in
# this field when it is free text (the review of #230: "Copyright 2024 Acme. Licensee shall not use the model to
# train other models" was dropped as boilerplate and the weights CLEARED). After its address and URL are set aside,
# a holder may end in a full stop but not contain one, except after an initial or in a company suffix, and holds
# no normative word.
_COPYRIGHT = re.compile(r"(?:copyright|\(c\)|\u00a9)(?:\s*(?:\(c\)|\u00a9))*\s+(.{1,200}?)(?:\.?\s*all rights reserved)?\.?")
_HOLDER_ASIDE = re.compile(r"<[^<>\s]+>|\(?https?://[^\s)]+\)?|[^\s<>()]+@[^\s<>()]+\.\w+"
                           r"|\b(?:inc|ltd|co|corp|llc|l\.l\.c|gmbh|ag|s\.a|b\.v|e\.v|pty|plc|jr|sr|[a-z])\.")
_NORMATIVE = re.compile(r"\b(?:shall|must|may|might|can|cannot|will|not|no|nor|only|never|solely|exclusively|except|"
                        r"unless|without|subject|limit\w*|prohibit\w*|restrict\w*|licen[cs]\w*|permi\w*|use[ds]?|"
                        r"using|agree\w*|condition\w*|terms?|research|commercial\w*|production|users?|train\w*|"
                        r"deploy\w*|distribut\w*)\b")


def _flat(text: str) -> str:
    quotes = str.maketrans({"“": '"', "”": '"', "‘": "'", "’": "'"})
    return re.sub(r"\s+", " ", text.translate(quotes)).strip().lower()


def _text_riders(text: str) -> list:
    """(wording, class) of each not-open rider anywhere in a full license text. Only whole words count, so a GPL's
    "noncommercially" is not a non-commercial restriction; network copyleft is read from a declaration, not
    searched for in a text (the GPL-3.0 names the Affero GPL in section 13). GPL-1 and GPL-2 section 3c ("allowed
    only for noncommercial distribution") limits one way of offering source, not use, and is masked."""
    norm = re.sub(r"only-for-non-?commercial-distribution", " ", _masked(text))
    found = []
    for pattern, cls in RIDERS:
        if cls != NOT_OPEN:
            continue
        for m in re.finditer(pattern, norm):
            if m.end() == len(norm) or not norm[m.end()].isalpha():
                found.append((m.group(0), cls))
                break
    return found


def _copyright_only(line: str) -> bool:
    """Whether a flat line is a copyright notice and nothing more (``_COPYRIGHT``)."""
    m = _COPYRIGHT.fullmatch(line)
    if not m:
        return False
    holder = _HOLDER_ASIDE.sub(" ", m.group(1))
    return not re.search(r"[.;:!?]", holder) and not _NORMATIVE.search(holder)


def _standard_text(text: str) -> tuple[str | None, str]:
    """(SPDX id, other text) when ``text`` holds the standard Apache-2.0 or MIT terms, else (None, its flat form).
    Apache-2.0: the terms hash to the standard, and only its title header, its appendix or its boilerplate notice
    may stand beside them, the notice's copyright field a copyright notice only. MIT: the terms are the standard ones
    word for word, after only a title and copyright notices. Anything else beside the terms is returned, for the
    caller to leave unclassified."""
    flat = _flat(text)
    start = flat.find("terms and conditions for use, reproduction, and distribution")
    end = flat.find("end of terms and conditions")
    if 0 <= start < end:
        stop = end + len("end of terms and conditions")
        if hashlib.sha256(flat[start:stop].encode()).hexdigest() == APACHE_2_TERMS_SHA256:
            before = re.sub("^" + _APACHE_HEADER, "", flat[:start]).strip()
            after = flat[stop:].strip()
            notice = re.fullmatch(f"(?:{_APACHE_APPENDIX}|{_APACHE_NOTICE})", after) if after else None
            if notice and _copyright_only(next(g for g in notice.groups() if g)):
                after = ""
            return "Apache-2.0", " ".join(x for x in (before, after) if x)
    lines = text.splitlines()
    first = next((i for i, line in enumerate(lines) if _flat(line).startswith("permission is hereby granted")), None)
    if first is not None:
        rest = _flat("\n".join(lines[first:]))
        if rest.startswith(_MIT_TERMS):
            before = [line.strip() for line in lines[:first]
                      if _flat(line) and not _MIT_TITLE.fullmatch(_flat(line)) and not _copyright_only(_flat(line))]
            return "MIT", " ".join(before + [rest[len(_MIT_TERMS):].strip()]).strip()
    return None, flat


def model_license_tree(text: str) -> dict:
    """The expression tree of one full model-license text: the standard license it is, with anything else in it
    unclassified, and every restrictive rider in it applying (AND)."""
    known, extra = _standard_text(text)
    atoms = [{"atom": f"license text mentions '{p}'", "class": c, "category": _category(c, p)}
             for p, c in _text_riders(text)]
    if known:
        atoms.insert(0, {"atom": known, "class": SPDX_CLASS[known.lower()], "category": OPEN_SOURCE})
        if extra:
            atoms.append({"atom": f"{known} text with other terms beside it ('{extra[:60]}')", "class": UNKNOWN,
                          "category": UNCLASSIFIED})
    elif not atoms:
        first = next((line.strip() for line in text.splitlines() if line.strip()), "(empty)")
        atoms.append({"atom": f"license text '{first[:80]}'", "class": UNKNOWN, "category": UNCLASSIFIED})
    return atoms[0] if len(atoms) == 1 else {"and": atoms}


def _read_regular(path: Path, limit: int) -> bytes | None:
    """At most ``limit`` bytes of a regular file, checked on its descriptor; None when unreadable or larger."""
    import os
    import stat
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK | getattr(os, "O_NOFOLLOW", 0))
    except OSError:
        return None
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_size > limit:
            return None
        with open(fd, "rb", closefd=False) as stream:
            data = stream.read(limit + 1)
        return data if len(data) <= limit else None
    finally:
        os.close(fd)


def _ollama_parts(name: str) -> tuple[str, str, str, str] | None:
    """(host, namespace, model, tag) of an Ollama model name, completed as Ollama completes it; None when malformed."""
    path, tag = name.rsplit(":", 1) if ":" in name.rsplit("/", 1)[-1] else (name, OLLAMA_TAG)
    pieces = path.split("/")
    if len(pieces) == 1:
        host, namespace, model = OLLAMA_HOST, OLLAMA_NAMESPACE, pieces[0]
    elif len(pieces) == 2:
        host, namespace, model = OLLAMA_HOST, pieces[0], pieces[1]
    elif len(pieces) == 3:
        host, namespace, model = pieces
    else:
        return None
    word = r"[A-Za-z0-9][A-Za-z0-9._-]{0,79}"
    if not all(re.fullmatch(word, p) for p in (host, namespace, model)) or \
            not re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9._-]{0,127}", tag):    # no piece can be "." or ".."
        return None
    return host, namespace, model, tag


def _ollama_stores(models_dir) -> list:
    import os
    if models_dir is not None:
        return [Path(models_dir)]
    stores = [Path(os.environ["OLLAMA_MODELS"])] if os.environ.get("OLLAMA_MODELS") else []
    return stores + [Path.home() / ".ollama" / "models", Path("/usr/share/ollama/.ollama/models")]


def model_assessment(model: str, licenses: list, subject: dict, problem: str | None = None) -> dict:
    """The assessment of a model from its license texts (None: a license layer that could not be read, or did not
    match its digest). Weights are cleared only when every license is known and cleared; no license at all, an
    unreadable one, an unclassified one, or a ``problem`` reading the manifest, is held."""
    unread = {"atom": "UNREAD", "class": UNKNOWN, "category": UNCLASSIFIED}
    parts = []
    if problem:
        parts.append(_part(model, problem, "UNREAD", unread, [problem]))
    elif not licenses:
        parts.append(_part(model, "the model carries no license layer", "UNDECLARED",
                           {"atom": "UNDECLARED", "class": UNKNOWN, "category": UNCLASSIFIED},
                           ["the model declares no license"]))
    for index, text in enumerate([] if problem else licenses):
        label = f"{model} (license layer {index + 1})"
        if text is None:
            parts.append(_part(label, "license layer unreadable or not matching its digest", "UNREAD", unread,
                               ["a license layer could not be read, or its bytes do not match its digest"]))
        else:
            first = next((line.strip() for line in text.splitlines() if line.strip()), "(empty)")
            parts.append(_part(label, "Ollama license layer (full text)", first[:120], model_license_tree(text)))
    worst = _worst([p["class"] for p in parts])
    blocking = [p for p in parts if ORDER.index(p["class"]) > ORDER.index(CLEARED_UP_TO)]
    cleared = not blocking
    verdict = ("CLEARED" if worst == PERMISSIVE else "CLEARED_WITH_OBLIGATIONS") if cleared else "FOUNDER_REVIEW"
    elected = [a for p in parts for a in _elected(p)]
    return {"verdict": verdict, "class": worst, "held": not cleared, "auto_attach": cleared,
            "reason": ("; ".join(f"{p['distribution']}: {p['class'].replace('_', ' ')}"
                                 + (f"; restrictive: {', '.join(p['restrictive'])}" if p.get("restrictive") else "")
                                 + "".join(f"; {u}" for u in p.get("uncertainty") or []) for p in blocking)
                       if blocking else "every license the model carries is cleared for GREG's use")[:400],
            "obligations": sorted({OBLIGATIONS[a["class"]] for a in elected}),
            "categories": sorted({a["category"] for a in elected}),
            "restrictive": [r for p in parts for r in p.get("restrictive") or []],
            "uncertainty": [f"{p['distribution']}: {u}" for p in parts for u in p.get("uncertainty") or []],
            "parts": parts, "subject": subject,
            "policy": "model weights: held unless every license layer is a recognised cleared license",
            "parser": "Ollama manifest + license text (GREG reader)", "limits": MODEL_LIMITS}


def ollama_model(model: str, models_dir=None) -> dict | None:
    """The license assessment of an Ollama model installed on this body, read from its manifest and license blobs,
    bound to the manifest and weight digests. None when the name is malformed or no store holds the model."""
    parts = _ollama_parts(model)
    if parts is None:
        return None
    for store in _ollama_stores(models_dir):
        manifest_path = store / "manifests" / Path(*parts)
        raw = _read_regular(manifest_path, MAX_MANIFEST_BYTES)
        if raw is None:
            raw = _read_regular(store / "manifests" / Path(*(p.lower() for p in parts)), MAX_MANIFEST_BYTES)
        if raw is None:
            continue
        try:
            layers = json.loads(raw)["layers"]
            layers = [layer for layer in layers if isinstance(layer, dict)]
        except (ValueError, KeyError, TypeError):
            layers = None
        name = "/".join(parts[:3]) + ":" + parts[3]
        subject = {"model": name, "manifest_sha256": hashlib.sha256(raw).hexdigest(),
                   "weights": sorted(str(layer.get("digest")) for layer in layers or []
                                     if layer.get("mediaType") in OLLAMA_WEIGHTS)}
        if layers is None:
            return model_assessment(name, [], subject, "the model's manifest is not a readable Ollama manifest")
        texts = []
        for layer in layers:
            if layer.get("mediaType") != OLLAMA_LICENSE:
                continue
            digest = str(layer.get("digest") or "")
            data = (_read_regular(store / "blobs" / digest.replace(":", "-"), MAX_MODEL_LICENSE_BYTES)
                    if re.fullmatch(r"sha256:[0-9a-f]{64}", digest) else None)
            if data is None or "sha256:" + hashlib.sha256(data).hexdigest() != digest:
                texts.append(None)
                continue
            try:
                texts.append(data.decode("utf-8"))
            except UnicodeDecodeError:
                texts.append(None)
        return model_assessment(name, texts, subject)
    return None


# -- use-context qualification: drafts D-LIC-1 and P4c ------------------------------------------------------------
# A license permits or forbids a *use*, not a package. GREG's real use of an acquired capability is fixed by its
# route: an unmodified binary or interpreter run as a separate process with network isolation, never redistributed,
# under a read-only consequence scope. ``qualify_use`` judges each declared term against that use and binds the
# verdict to the exact assessed facts (content hash, version, parts) and to the use, so a change in either is a
# change of qualification. Both policies are drafts: the active values stay P0 until the founder adopts them in a
# reviewed commit (directive of 2026-10-23: "Do not activate the policy until I explicitly approve it").

ACTIVE_BINARY_POLICY = "P0"            # draft: "P4c"
ACTIVE_FOUNDER_ATTACH_POLICY = "P0"    # draft: "D-LIC-1"
COMPATIBLE, UNCERTAIN, INCOMPATIBLE = "compatible", "uncertain", "incompatible"
VERDICT_ORDER = (COMPATIBLE, UNCERTAIN, INCOMPATIBLE)
GREG_USE = {"interaction": "separate_process", "network": "none", "modified": False, "redistributed": False,
            "scope": "read_only"}


def _digest(value) -> str:
    return "sha256:" + hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                                 default=str).encode()).hexdigest()


NOT_OPEN_WHY = {
    SOURCE_AVAILABLE: "source-available: the license's own grant may cover this use (internal, non-production or "
                      "non-service use), but GREG does not read it; that grant, read against this use, or the rights "
                      "holder's permission must be evidenced",
    RESTRICTED_USE: "restricted use (non-commercial, field-of-use, proprietary or non-free terms): permission must be "
                    "evidenced, not assumed"}


def _term_verdict(cls: str, use: dict, category: str = RESTRICTED_USE) -> tuple[str, str]:
    """Whether one declared term permits ``use``. Obligations are not prohibitions: GPL and AGPL are compatible
    with the uses their conditions do not reach. Unknown is never compatible, whatever the use."""
    local = use.get("interaction") == "separate_process" and not use.get("redistributed")
    if cls == PERMISSIVE:
        return COMPATIBLE, "permissive"
    if cls in (WEAK_COPYLEFT, STRONG_COPYLEFT):
        return ((COMPATIBLE, "copyleft conditions apply to redistribution or linking, neither of which this use does")
                if local else (UNCERTAIN, "this use redistributes or links copyleft code"))
    if cls == NETWORK_COPYLEFT:
        return ((COMPATIBLE, "network-copyleft conditions apply to modified or network-offered copies; this use is "
                             "an unmodified, network-isolated local process")
                if local and use.get("network") == "none" and not use.get("modified")
                else (UNCERTAIN, "this use modifies or network-exposes network-copyleft code"))
    if cls == NOT_OPEN:
        return INCOMPATIBLE, "not an open-source license: " + NOT_OPEN_WHY.get(category, NOT_OPEN_WHY[RESTRICTED_USE])
    return UNCERTAIN, "license not classified: absence of network use or redistribution does not make it compatible"


def _use_eval(node: dict, use: dict) -> tuple[str, int, list]:
    """(verdict, class rank, elected (term, verdict, why)). AND applies every term: the worst verdict. OR is usable
    when one whole alternative is: the best verdict, and on a tie the alternative with the less strict class. The
    elected terms are one alternative's; terms are never mixed across alternatives."""
    if "atom" in node:
        verdict, why = _term_verdict(node["class"], use, node.get("category") or _category(node["class"], node["atom"]))
        if node.get("unlisted") and verdict == COMPATIBLE:
            verdict, why = UNCERTAIN, ("named like a known license family but not in GREG's tables: its own terms, "
                                       "or an addition to them, are unread")
        return verdict, ORDER.index(node["class"]), [(node, verdict, why)]
    parts = [_use_eval(child, use) for child in node.get("and") or node["or"]]
    if "and" in node:
        return (max((p[0] for p in parts), key=VERDICT_ORDER.index), max(p[1] for p in parts),
                [e for p in parts for e in p[2]])
    return min(parts, key=lambda p: (VERDICT_ORDER.index(p[0]), p[1], sum(e[0]["class"] in HELD for e in p[2]),
                                     sorted(str(e[0]["atom"]) for e in p[2])))


def qualify_use(assessments, use: dict, subject: dict) -> dict:
    """Use-specific verdict for every assessment a capability carries (its binary, then each companion): can this
    exact component, at this version, perform its function in ``use``?

    Every assessment, part and DEP-5 stanza applies (AND). Within an expression, AND applies every term and OR
    elects the one whole alternative that best permits ``use``; ``terms`` are the elected ones (their obligations
    are the ones accepted), ``not_elected`` the alternatives GREG does not rely on. ``uncertainty`` says what was
    not read. ``subject`` pins what was assessed (content hash, version, provider); the digest covers it, the
    assessed parts and nothing else, so it changes exactly when the facts change. A missing assessment is uncertain."""
    terms, not_elected, facts, uncertainty = [], [], [], []
    for assessment in assessments:
        if not isinstance(assessment, dict):
            terms.append({"id": "NO ASSESSMENT", "class": UNKNOWN, "verdict": UNCERTAIN,
                          "why": "no license assessment could be read for this binary"})
            facts.append(None)
            uncertainty.append("no license assessment could be read for one binary")
            continue
        parts = assessment.get("parts") or []
        facts.append([{k: p.get(k) for k in ("distribution", "expression", "class", "terms")} for p in parts])
        uncertainty += [u for u in assessment.get("uncertainty") or [] if u not in uncertainty]
        for part in parts or [{"expression": "UNREAD", "class": assessment.get("class") or UNKNOWN, "terms": []}]:
            tree = _part_tree(part)
            elected = _use_eval(tree, use)[2]
            chosen = {id(atom) for atom, _, _ in elected}
            for atom, verdict, why in elected:
                terms.append({"id": str(atom["atom"])[:120], "class": atom["class"],
                              "category": atom.get("category") or _category(atom["class"], atom["atom"]),
                              "verdict": verdict, "why": why, **({"unlisted": True} if atom.get("unlisted") else {})})
            not_elected += [{"id": str(a["atom"])[:120], "class": a["class"]} for a in _atoms(tree)
                            if id(a) not in chosen]
    worst = max((t["verdict"] for t in terms), key=VERDICT_ORDER.index, default=UNCERTAIN)
    blocking = [t for t in terms if t["verdict"] != COMPATIBLE]
    uncertainty += [f"{t['id']}: not classified by GREG" for t in terms
                    if t["class"] == UNKNOWN and f"{t['id']}: not classified by GREG" not in uncertainty]
    uncertainty += [f"{t['id']}: named like a known family, not in GREG's tables" for t in terms if t.get("unlisted")
                    and f"{t['id']}: named like a known family, not in GREG's tables" not in uncertainty]
    return {"verdict": worst, "use": dict(use), "use_digest": _digest(use),
            "assessment_digest": _digest({"subject": subject, "facts": facts}), "terms": terms,
            "not_elected": not_elected, "uncertainty": uncertainty, "limits": LIMITS,
            "obligations": sorted({OBLIGATIONS[t["class"]] for t in terms if t["class"] in OBLIGATIONS}),
            "reason": ("; ".join(f"{t['id']}: {t['why']}" for t in blocking) if blocking
                       else "every declared term permits this use")[:400]}


def _binary_assessments(provenance: dict) -> list:
    return [provenance.get("license_assessment")] + [
        c.get("license_assessment") for c in (provenance.get("companions") or {}).values() if isinstance(c, dict)]


def _binary_subject(provenance: dict) -> dict:
    return {"binary_sha256": provenance.get("binary_sha256"), "version": provenance.get("version"),
            "companions": {n: c.get("binary_sha256") for n, c in sorted((provenance.get("companions") or {}).items())
                           if isinstance(c, dict)}}


def capability_qualification(manifest, use: dict = GREG_USE) -> dict:
    """The use-specific qualification of an acquired capability as its card records it now."""
    provenance = manifest.provenance
    if manifest.provider.startswith("installed:python:"):
        return qualify_use([provenance.get("license_assessment")], use,
                           {"distribution": provenance.get("distribution"), "version": provenance.get("version")})
    return qualify_use(_binary_assessments(provenance), use, _binary_subject(provenance))


def _p0_binary_check(provenance: dict) -> tuple[bool, str]:
    for assessment in _binary_assessments(provenance):
        if isinstance(assessment, dict) and (assessment.get("held")
                                             or assessment.get("class") in (NETWORK_COPYLEFT, NOT_OPEN)
                                             or any(_held_terms(p.get("terms") or [])
                                                    for p in assessment.get("parts") or [])):
            return False, assessment.get("reason", "")
    return True, ""


def attach_check(manifest, policy: str | None = None) -> tuple[bool, str]:
    """Whether an acquired capability's license permits attach without the founder's own command.

    A Python package must carry a cleared assessment (fail closed). Under P0 (active) a system binary is held only
    when its OS package declares a license that is known and not cleared; an undeterminable one (no dpkg, no DEP-5
    file) or unclassified one keeps the behaviour it had before licenses were read. Under P4c (draft) every term of
    the binary and of each companion must be compatible with GREG's actual use; anything uncertain, incompatible
    or unassessed is held until a use-specific founder clearance. Other providers are GREG code."""
    policy = policy or ACTIVE_BINARY_POLICY
    provenance = manifest.provenance
    if manifest.provider.startswith("installed:python:"):
        return auto_attach_allowed(provenance)
    if not manifest.provider.startswith("installed:"):
        return True, ""
    if policy == "P0":
        return _p0_binary_check(provenance)
    if policy == "P4c":
        q = capability_qualification(manifest)
        if q["verdict"] != COMPATIBLE:
            return False, q["reason"] + "; a use-specific founder clearance (D-LIC-1) can lift this hold"
        return True, ""
    raise ValueError(f"unknown binary license policy {policy!r}")


def founder_attach_check(manifest, body: dict, policy: str | None = None,
                         binary_policy: str | None = None) -> tuple[bool, str, dict | None]:
    """Whether a founder CAPABILITY_ATTACH may proceed past the capability's license hold.

    P0 (active): the founder's attach is not license-checked (prior behaviour). D-LIC-1 (draft): a capability the
    license check holds is attached only with ``body["license_clearance"]`` naming the exact assessment digest
    (a stale one is refused), GREG's real use, a non-empty basis and every obligation accepted; an incompatible
    (not-open) term also needs ``permission`` evidence, since a signature does not override third-party rights.
    Returns (allowed, reason, clearance record to journal)."""
    policy = policy or ACTIVE_FOUNDER_ATTACH_POLICY
    if policy == "P0":
        return True, "", None
    if policy != "D-LIC-1":
        raise ValueError(f"unknown founder attach policy {policy!r}")
    licensed, why = attach_check(manifest, binary_policy)
    if licensed:
        return True, "", None
    clearance = body.get("license_clearance")
    if not isinstance(clearance, dict):
        return False, (f"license hold unresolved ({why}); a bare attach does not clear it: add a license_clearance "
                       "for this exact assessment and use"), None
    q = capability_qualification(manifest)
    if clearance.get("assessment_digest") != q["assessment_digest"]:
        return False, "license_clearance is for a different or earlier assessment; requalify and clear again", None
    if clearance.get("use") != q["use"]:
        return False, "license_clearance names a use other than this route's real use", None
    if not str(clearance.get("basis") or "").strip():
        return False, "license_clearance needs a basis: why these terms allow this use", None
    missing = sorted(set(q["obligations"]) - set(clearance.get("obligations_accepted") or ()))
    if missing:
        return False, f"license_clearance does not accept every obligation: {missing[0]}", None
    if any(t["verdict"] == INCOMPATIBLE for t in q["terms"]) and not str(clearance.get("permission") or "").strip():
        return False, ("a not-open term needs permission evidence (a grant or license from the rights holder); "
                       "a founder signature does not override third-party rights"), None
    return True, "license cleared by the founder for this use", {
        "assessment_digest": q["assessment_digest"], "use_digest": q["use_digest"], "verdict": q["verdict"],
        "basis": str(clearance["basis"])[:400], "permission": str(clearance.get("permission") or "")[:400] or None,
        "obligations_accepted": q["obligations"], "elected_terms": [t["id"] for t in q["terms"]]}


def requalify(manifest, live_assessments: list, use: dict = GREG_USE,
              policy: str | None = None) -> tuple[bool, str]:
    """Before each run under P4c: the license facts read now and the use about to happen must equal those the
    capability was qualified (or cleared) under. P0 does not requalify. A change is not judged here; it stops the
    run and sends the capability back through qualification."""
    if (policy or ACTIVE_BINARY_POLICY) != "P4c":
        return True, ""
    recorded = manifest.provenance.get("use_qualification")
    if not isinstance(recorded, dict):
        return False, "no use qualification recorded; requalification required"
    now = qualify_use(live_assessments, use, _binary_subject(manifest.provenance))
    if now["use_digest"] != recorded.get("use_digest"):
        return False, ("use context changed since qualification (network, modification, redistribution or scope); "
                       "requalification required")
    if now["assessment_digest"] != recorded.get("assessment_digest"):
        return False, "license facts changed since qualification; requalification required"
    return True, ""


def requalify_binary(manifest, binary: str, use: dict = GREG_USE, policy: str | None = None) -> tuple[bool, str]:
    """``requalify`` for an installed binary and its companions, reading their DEP-5 facts now (P4c only)."""
    if (policy or ACTIVE_BINARY_POLICY) != "P4c":
        return True, ""
    live = [system_binary(binary)] + [system_binary(c["binary"]) for _, c in
                                      sorted((manifest.provenance.get("companions") or {}).items())
                                      if isinstance(c, dict) and c.get("binary")]
    return requalify(manifest, live, use, policy="P4c")
