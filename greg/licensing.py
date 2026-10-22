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
    "Free For Home Use": NOT_OPEN, "Free for non-commercial use": NOT_OPEN,
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


def _worst(classes) -> str:
    return max(classes, key=ORDER.index) if classes else UNKNOWN


def _best(classes) -> str:
    return min(classes, key=ORDER.index) if classes else UNKNOWN


def _evaluate(canonical: str, terms: list) -> str:
    """SPDX semantics on a canonical expression: OR takes the best choice, AND the worst, WITH binds tightest."""
    tokens = re.findall(r"\(|\)|[^\s()]+", canonical)
    position = 0

    def atom():
        nonlocal position
        token = tokens[position]
        position += 1
        if token == "(":
            value = disjunction()
            position += 1                                          # ")": the expression is already canonical
            return value
        cls = SPDX_CLASS.get(token.rstrip("+").lower(), UNKNOWN)       # "X+" (or later) keeps X's class
        if position < len(tokens) and tokens[position] == "WITH":
            exception = tokens[position + 1]
            position += 2
            if cls == STRONG_COPYLEFT and exception.lower() in LINKING_EXCEPTIONS:
                cls = WEAK_COPYLEFT
            token = f"{token} WITH {exception}"
        terms.append({"id": token, "class": cls})
        return cls

    def conjunction():
        nonlocal position
        values = [atom()]
        while position < len(tokens) and tokens[position] == "AND":
            position += 1
            values.append(atom())
        return _worst(values)

    def disjunction():
        nonlocal position
        values = [conjunction()]
        while position < len(tokens) and tokens[position] == "OR":
            position += 1
            values.append(conjunction())
        return _best(values)

    return disjunction()


# Phrases that mark a license as not open source wherever they appear in a declared license field, including
# beside an open-source expression or classifier (a "rider"). "All rights reserved" and "proprietary" are not
# listed: ordinary BSD and MIT notices contain them.
RESTRICTIVE = ("non-commercial", "noncommercial", "non commercial", "commons clause", "server side public license",
               "business source license", "elastic license", "polyform", "not for commercial", "evaluation only")
# The phrases are searched only in a short declaration. A full license text (scipy's bundles the GPL of its
# compiled runtime, which says "noncommercially") is not interpreted: a rider inside one is not detected.
SHORT_LINES, SHORT_CHARS = 5, 600


def _text_terms(text: str) -> tuple[str | None, dict | None]:
    """What a legacy ``License`` field adds: (class, term), or (None, None) when it carries no classification."""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if len(lines) <= SHORT_LINES and len(text) <= SHORT_CHARS:
        lowered = text.lower()
        flagged = next((phrase for phrase in RESTRICTIVE if phrase in lowered), None)
        if flagged:
            return NOT_OPEN, {"id": f"License field mentions '{flagged}'", "class": NOT_OPEN}
    if len(lines) != 1:
        return None, None                    # a full license text: no short declaration to classify
    line = lines[0]
    try:                                     # a legacy field that already holds an SPDX expression
        terms: list = []
        cls = _evaluate(str(canonicalize_license_expression(line)), terms)
        if cls != UNKNOWN:
            return cls, {"id": line[:120], "class": cls}
    except InvalidLicenseExpression:
        pass
    cls = TEXT.get(line.lower().rstrip("."), UNKNOWN)
    return cls, {"id": line[:120], "class": cls}


def declared(dist) -> dict:
    """The license one installed distribution declares, classified.

    An SPDX ``License-Expression`` (PEP 639) or trove classifiers are the primary declaration. The legacy
    ``License`` field is always read as well: a restrictive phrase anywhere in it, or a one-line declaration that
    classifies stricter, makes the whole declaration that strict (conflicting declarations take the worst). A
    multi-line field alone is a license text GREG does not interpret: unclassified."""
    meta = dist.metadata
    name = meta["Name"]
    if canonicalize_license_expression is None:
        return {"distribution": name, "basis": "packaging.licenses unavailable on this body", "expression": "UNREAD",
                "class": UNKNOWN, "terms": []}
    text = meta.get("License") or ""
    text_class, text_term = _text_terms(text) if text.strip() else (None, None)
    expression = (meta.get("License-Expression") or "").strip()
    trove = [c.split("::", 1)[1].strip() for c in meta.get_all("Classifier") or () if c.startswith("License ::")]
    if expression:
        try:
            canonical = str(canonicalize_license_expression(expression))
        except InvalidLicenseExpression as exc:
            return {"distribution": name, "basis": "License-Expression (PEP 639), unparseable", "expression": expression,
                    "class": UNKNOWN, "terms": [], "note": str(exc)[:160]}
        terms: list = []
        cls, basis, shown = _evaluate(canonical, terms), "License-Expression (PEP 639), parsed by packaging.licenses", \
            canonical
    elif trove:
        if len(trove) > 1:               # the bare "OSI Approved" parent beside a specific classifier adds nothing
            trove = [t for t in trove if t != "OSI Approved"]
        terms = [{"id": t, "class": TROVE.get(t, UNKNOWN)} for t in trove]
        # several classifiers do not say whether they are alternatives or all apply: assume all apply
        cls, basis, shown = _worst([t["class"] for t in terms]), "trove classifiers (family; version may be unstated)", \
            " AND ".join(trove)
    elif text_term is not None:
        return {"distribution": name, "basis": "License field, exact short-name match" if text_class != UNKNOWN
                else "License field, not a recognised short name", "expression": text_term["id"], "class": text_class,
                "terms": [text_term]}
    elif text.strip():
        return {"distribution": name, "basis": "License field holds a full license text GREG does not interpret",
                "expression": text.strip().splitlines()[0][:120], "class": UNKNOWN, "terms": []}
    else:
        return {"distribution": name, "basis": "nothing declared", "expression": "UNDECLARED", "class": UNKNOWN,
                "terms": []}
    # beside a primary declaration, an unrecognised short name is informational; a recognised stricter one counts
    if text_term is not None and text_class != UNKNOWN and ORDER.index(text_class) > ORDER.index(cls):
        terms = terms + [text_term]
        cls, basis = text_class, basis + "; the License field declares something stricter"
    return {"distribution": name, "basis": basis, "expression": shown, "class": cls, "terms": terms}


def assess(dist, dependencies=()) -> dict:
    """Assessment of a package and the dependencies that run in its interpreter (all apply together)."""
    parts = [declared(dist)] + [declared(d) for d in dependencies if d is not None]
    worst = _worst([p["class"] for p in parts])
    cleared = ORDER.index(worst) <= ORDER.index(CLEARED_UP_TO)
    verdict = ("CLEARED" if worst == PERMISSIVE else "CLEARED_WITH_OBLIGATIONS") if cleared else "FOUNDER_REVIEW"
    blocking = [p for p in parts if ORDER.index(p["class"]) > ORDER.index(CLEARED_UP_TO)]
    reason = ("; ".join(f"{p['distribution']}: {p['expression']} ({p['class'].replace('_', ' ')}, {p['basis']})"
                        for p in blocking) if blocking else "every declared license is cleared for GREG's use")
    return {"verdict": verdict, "class": worst, "auto_attach": cleared, "reason": reason[:400],
            "obligations": sorted({OBLIGATIONS[p["class"]] for p in parts}), "parts": parts,
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


def _name_class(name: str) -> str:
    """One DEP-5 short name: Debian's spelling first, then the SPDX identifier ('AGPL-3.0+' as AGPL-3.0)."""
    key = re.split(r"\s+with\s+", name, flags=re.I)[0].strip().lower()
    return DEBIAN.get(key) or SPDX_CLASS.get(key) or SPDX_CLASS.get(key.rstrip("+")) or UNKNOWN


def _debian_class(expression: str) -> str:
    """A DEP-5 License short-name expression: 'or' takes the best alternative, 'and' the worst, and ', and' binds
    loosest ('GPL-1+ or Artistic, and BSD-3-clause' is (GPL-1+ or Artistic) and BSD-3-clause). 'with ... exception'
    keeps the base license's class (Debian names many exceptions; GREG does not downgrade on an unknown one)."""
    groups = []
    for group in re.split(r",\s*and\s+", expression.strip(), flags=re.I):
        best = []
        for alternative in re.split(r"\s+or\s+", group.strip(), flags=re.I):
            parts = [p.strip() for p in re.split(r"\s+and\s+|,\s*", alternative, flags=re.I) if p.strip()]
            best.append(_worst([_name_class(p) for p in parts]))
        groups.append(_best(best))
    return _worst(groups)


def _held_terms(terms) -> list:
    """Terms that hold a binary: a known network-copyleft or not-open license, whatever else is unclassified."""
    return [t for t in terms if t["class"] in (NETWORK_COPYLEFT, NOT_OPEN)]


def dep5(text: str) -> dict | None:
    """Every License declared by a Files paragraph (or the header) of a DEP-5 file; None if it is not DEP-5."""
    paragraphs = [p for p in re.split(r"\n\s*\n", text) if p.strip()]
    if not paragraphs or not paragraphs[0].lstrip().lower().startswith("format:"):
        return None
    terms = []
    for index, paragraph in enumerate(paragraphs):
        fields = {line.split(":", 1)[0].strip().lower(): line.split(":", 1)[1].strip()
                  for line in paragraph.splitlines() if line and not line[0].isspace() and ":" in line}
        if "license" in fields and (index == 0 or "files" in fields):
            terms.append({"id": fields["license"][:120], "class": _debian_class(fields["license"])})
    if not terms:
        return None
    return {"expression": " AND ".join(dict.fromkeys(t["id"] for t in terms)), "terms": terms,
            "class": _worst([t["class"] for t in terms])}


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
        parsed = dep5((Path("/usr/share/doc") / package / "copyright").read_text(errors="replace"))
    except OSError:
        parsed = None
    part = ({"distribution": f"{package} (dpkg)", "basis": "Debian DEP-5 copyright file", **parsed} if parsed else
            {"distribution": f"{package} (dpkg)", "basis": "copyright file missing or not DEP-5",
             "expression": "UNREAD", "class": UNKNOWN, "terms": []})
    worst = part["class"]
    held = _held_terms(part["terms"])
    cleared = ORDER.index(worst) <= ORDER.index(CLEARED_UP_TO)
    verdict = ("FOUNDER_REVIEW" if held else ("CLEARED" if worst == PERMISSIVE else "CLEARED_WITH_OBLIGATIONS")
               if cleared else "UNCLASSIFIED_PRIOR_BEHAVIOUR")
    reason = ("; ".join(f"{t['id']} ({t['class'].replace('_', ' ')})" for t in held) if held else
              "every declared license is cleared for GREG's use" if cleared else
              f"{part['distribution']}: some declared license is not classified by GREG; attach behaviour is as "
              "before licenses were read")
    return {"verdict": verdict, "class": worst, "held": bool(held), "auto_attach": not held, "reason": reason[:400],
            "obligations": sorted({OBLIGATIONS[t["class"]] for t in part["terms"]} or {OBLIGATIONS[worst]}),
            "parts": [part], "policy": "binary: held on any known network-copyleft or not-open term",
            "parser": "dpkg-query + DEP-5 (GREG reader)", "limits": LIMITS}


def attach_check(manifest) -> tuple[bool, str]:
    """Whether an acquired capability's license permits attach without the founder's own command.

    A Python package must carry a cleared assessment (fail closed). A system binary is held only when its OS
    package declares a license that is known and not cleared; an undeterminable one (no dpkg, no DEP-5 file)
    or unclassified one keeps the behaviour it had before licenses were read (system packages routinely list
    documentation licenses GREG does not classify), and its card says so. Other providers are GREG code."""
    provenance = manifest.provenance
    if manifest.provider.startswith("installed:python:"):
        return auto_attach_allowed(provenance)
    if manifest.provider.startswith("installed:"):
        assessment = provenance.get("license_assessment")
        if isinstance(assessment, dict) and (assessment.get("held") or assessment.get("class") in (NETWORK_COPYLEFT, NOT_OPEN)
                                             or any(_held_terms(p.get("terms") or [])
                                                    for p in assessment.get("parts") or [])):
            return False, assessment.get("reason", "")
    return True, ""
