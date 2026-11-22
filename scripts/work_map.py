#!/usr/bin/env python3
"""Work map: where the build stands, what is open to take, and who holds what.

Read-only. It writes only the files you name (no bytecode either), posts nothing, locks nothing and
grants nothing. It joins sources that already exist:

- ``greg/path.json`` (the route) and ``acceptance/directive-sections.json`` (the
  77-section directive: buildable units in dependency order, at the static ceiling);
- ``foundry/completion.yaml`` (the 55 obligations) and ``scripts/mind_status.py``;
- open pull requests and their version-2 receipts (read as declared, not re-validated here);
- work-board comments.

Sessions and holders come from two places only: a receipt's ``session_id``, and a comment that is itself a check-in
(the check-in marker alone on its first line, then the block's own ``Session:`` line first, after the block's heading
when it has one; see ``checkin_author``). Every other reading of a comment's
author (heading bylines, other labels, opening lines and the joins in ``JOINS``) is ``author_guess``, kept with its
``how`` for diagnosis and never used as authority, because on replay the parser named wrong authors and left more than
a quarter of a week's posts unresolved, the plan's stop condition for building the map from receipts only.

Threat model: these rules guard against ordinary changes by cooperating agents working in parallel: refactors, copies
made by mistake or convenience, handoffs, relays, templates filled in for someone else, receipts copied between PRs.
They are not a security boundary against a deliberate evader who writes exotic code or text to defeat them. A receipt
and a check-in are declared, not authenticated. A check-in that relays, or whose heading hands over, reassigns or
reviews, or that names another poster, names nobody; but a block filled in, pasted or copied with none of this wording
is read as the session its Session line names, whoever posts it. The residuals each rule leaves are stated where the
rule is, never claimed as covered.

Ask it before you edit::

    python scripts/work_map.py --github OWNER/REPO                       # the whole map
    python scripts/work_map.py --github OWNER/REPO --paths greg/missions.py
    python scripts/work_map.py --github OWNER/REPO --unit WU-11

``--prs-json`` and ``--comments-json`` replay saved API responses offline.
Without any of them it prints the position and the units, and says that pull requests
and comments were not read.

The JSON (``--json``) holds ``generated``, ``line``, ``authority`` ("none"), ``sources`` (counts, among them
``git_diffs`` and ``api_file_lists``, the PRs whose changed files came from local git and from the GitHub API, each
None when git did not answer or the files API was not asked; the flags ``prs_read``, ``comments_read`` and
``git_read``, and ``notes``/``note``: what was not read), ``position``, ``units``
(``state``; ``named_by``, the PRs headed for the line whose title or receipt names the unit or one of its asks;
``carried_by_line``; ``mentioned_by``; ``named_on_board``; ``claimed_on_board``), ``contended``, ``sessions`` (one
per receipt session or check-in session; ``how`` is ``receipt`` or ``check-in block``, ``checkin`` its latest check-in
comment) and ``claims`` (``session`` is the check-in's session or None, ``how`` is ``check-in block`` or
``unverified``; ``author_guess`` and ``author_guess_how`` are what the text suggests, for diagnosis only; a claim's
``state`` is its own, its session's is ``session_activity``; a release counts only from the claim's own exact author,
one by another exact author is ``release_stated_by_another_author`` and one by an author that is not exact
``release_by_unverified_author``), ``claims_without_pr``,
``older_claims_without_pr``, ``line_checks``, ``gaps`` (``None`` where its source was not read; what git could not
check is listed there, never counted as zero; in ``recent_posts_unresolved`` a post that opens with the check-in marker
but is not exact has its ``reason`` and ``names``, the one id its Session line names, never a session or a holder) and ``prs`` (one row per open pull request, read once however often
given: its receipt's fields as declared, ``files`` cut to the first ``FILES_LIMIT`` with ``files_cut`` counting the
rest, ``receipt_problems`` for fields of the wrong type, ``files_refused``, why the receipt check refuses its
coordination or its files (then its files are unknown, never an empty list), ``session_refused``, why the receipt
check refuses its ``session_id`` or its PR comes from a fork (then it names no session), ``session_unnamed``, why the
map names no session for a receipt the check accepts (``receipt_session``), ``receipt_head_stale``,
whether the receipt's ``head_sha`` is not the PR's head (it keeps its session: a push lands before its description
is updated), ``changed``, the files it changes
itself, and ``changed_via``, where they came from: ``diff`` for local git, ``api`` for the GitHub API (``--github``, a
PR into the line that this clone cannot diff), None when neither said; ``line_bound`` and ``carried``).

A snapshot, not a lock. A claim coordinates work; an expired one never permits
overwriting someone's files (``docs/collaboration/START_HERE.md``). A comment
whose author is not exact has no session; its guess is labelled and never used. Text from pull
requests and comments is printed as code, so it cannot format the map. It exits 0 whatever it reads, also when it
cannot build the map or write a file (it says so on stderr, so check the files you named, not the exit code); a
malformed command line is a usage error (exit 2).
"""
from __future__ import annotations

import sys

sys.dont_write_bytecode = True

import argparse  # noqa: E402
import bisect  # noqa: E402
import fnmatch  # noqa: E402
import json  # noqa: E402
import os  # noqa: E402
import posixpath  # noqa: E402
import re  # noqa: E402
import stat  # noqa: E402
import subprocess  # noqa: E402
import tempfile  # noqa: E402
from datetime import datetime, timezone  # noqa: E402
from pathlib import Path  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT))

import branch_catalog  # noqa: E402
import repo_review  # noqa: E402
from lineage_map import _stacked_on  # noqa: E402 - one stack walk
from repo_review import RECEIPT_MARKER as MARKER, _get, receipt_of  # noqa: E402,F401 - one reader, one client

LINE = branch_catalog.LINE
CHECKIN = "<!-- uniimente:checkin -->"

# The check-in a session posts on the work board before it edits. Printed by the map
# so the block has one source. Tolerantly parsed: older claims use other labels.
CHECKIN_BLOCK = """\
<!-- uniimente:checkin -->
## Check-in: <one-line outcome>
- Session: <actual session or task id> (<client>)
- Prompt: <what I was asked, one or two sentences; no secrets>
- Plan: <how, in 1-3 steps; what I will not do>
- Route: N3 | P5 | <unit id> | process   (greg/path.json)
- Guidance read: uniimente-kernel@<the commit at which you read the guide, e.g. your starting checkout>
- Repository / branch / base → head: <owner/repo> · <branch> · <base sha> → pending
- Files / interfaces: <paths in backticks>; read-only: <...>
- Depends on: <... or nothing>
- Overlap inspected and split: <claims and PRs you opened> (clear: nothing open changes the same lines | split proposed to <session>, ack: <link or waiting> | blocked)
- Acceptance evidence: <what will show it works; results go in the PR>
- Reviewer / integrator · Destination: <session or unassigned> · <branch> (PR: pending)
- Next action / blocker / handoff condition: <...>
- Recheck (UTC): <YYYY-MM-DDTHH:MM:SSZ>"""

# The engineering target the founder set on 2026-11-12 (INTENT-20261112-CONVERGENCE-USEFUL-PATH; verbatim source
# docs/intent/sources/CONVERGENCE-CLARIFICATION-2026-11-12-source.md). One dated line; a later founder
# direction replaces it here.
ENGINEERING_TARGET = ("a useful mission on one exact composed revision; then recovery under interruption and "
                      "changed evidence; then useful transfer to a materially different mission "
                      "(founder direction of 2026-11-12)")

HEADING_LIMIT = 2000         # characters of a comment's first line that are read (the longest real one is 1,142)
SENTENCE_LIMIT = 3000        # characters of one sentence of a files field that are read
SEGMENT_LIMIT = 8000         # characters of one labelled segment that are read (the longest real one is 2,013)
FILES_LIMIT = 500            # files of one receipt that are read (the longest real list is far shorter)


def _text(value) -> str:
    """``value`` when it is a string, else the empty string."""
    return value if isinstance(value, str) else ""


def _texts(value) -> list[str]:
    """The strings in ``value`` when it is a list, else none."""
    return [x for x in value if isinstance(x, str)] if isinstance(value, list) else []


def _reason(exc: BaseException, root: Path = ROOT) -> str:
    """An exception as its type and, when it names a file, that file relative to the repository (else its name):
    no local path and no text taken from the data. It never raises: the file is resolved with ``os.path.realpath``,
    which leaves a symbolic link loop as it is, where ``Path.resolve()`` raises RuntimeError before Python 3.13."""
    name, where = getattr(exc, "filename", None), ""
    if isinstance(name, (str, os.PathLike)) and "://" not in str(name):
        try:
            where = Path(os.path.realpath(name)).relative_to(os.path.realpath(root)).as_posix()
        except (ValueError, OSError, RuntimeError):
            try:
                where = Path(name).name
            except (TypeError, ValueError):
                where = ""
    code = getattr(exc, "code", None)
    return type(exc).__name__ + (f" {code}" if type(code) is int else "") + (f": {where}" if where else "")


# ------------------------------------------------------------------ identities

_IDS = [
    ("claude", re.compile(r"session_01[0-9A-Za-z]{22}(?![0-9A-Za-z])"), lambda m: m[0]),
    ("cursor", re.compile(r"(?<![\w-])(?:bc-[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}|bc-[0-9a-f]{8}(?![0-9a-f-]))"),
     lambda m: m[0][:11]),
    ("kimi", re.compile(r"(?<![\w/.-])kimi-[a-z0-9]+(?:-[a-z0-9]+)*-20\d{6}(?:-\d{2})?(?![\w.-])"),
     lambda m: m[0]),
    ("codex", re.compile(r"(?i:codex)\s+`?/root`?[,;]?\s+(?:workspace\s+)?(?:session\s+)?`?([0-9a-f]{12})`?"),
     lambda m: "codex:" + m[1]),
    ("codex", re.compile(r"(?i)codex[-/]root[-/]([0-9a-f]{12})"), lambda m: "codex:" + m[1]),
]
_TEAM = re.compile(r"\bUAT\b|\bHegemony\b|Provider-review session")
_AUTHOR_LABELS = {"implementer", "agent / claim", "agent", "identity", "session", "posted by", "from"}
_ADDRESSEE_LABELS = {"receiver", "next owner", "reviewer", "integration owner", "reviewer / integrator",
                     "reviewer / integrator · destination"}
_OPENING = re.compile(r"(?i)^[^\w>|]*(?:session|implementer|from|posted by)\b[\s`*:]*")   # never a quote or a table
# A heading names its author only as a signature, in one of four places:
#   "· `id`" or "· session `id`" closed by the end, "·" or "(", and not right after a party ("the integrator ·
#     `id`"): "## Claim: x · `id` · 2026", "... · `id` (2026-10-30)";
#   "(`id`)" or "(session `id`)" closed by ")" or ";" and attached to the heading itself, not to a number, a party,
#     a possessive or a phrase after a preposition: "**Resumed (`id`).**", "## Wave 3 (session `id`)";
#   the sender that opens the heading, "From ...", "Hand over from ..." or "Handing ... over from ...", with only
#     "the", "#196's", a role word or "session" before the id: "**From the #196 integrator, `id`**";
#   "Session `id`" opening the heading or one of its sentences, closed by the end, "·" or ".": "**x.** Session `id`.".
# Nothing else is a byline. "from `id`" after a noun or a verb ("#300 from", "handoff from", "picked up from",
# "forwarded from") names where work came from; a role ("integrator `id`", "Owner: `id`", "the integrator, `id`")
# names whoever holds it; an id that a verb or "'s" follows names who acted or whose work it is ("**Session `id`
# replied**"); and "#300 (`id`)", "the integrator (`id`)" or "status of WU-11 (`id`)" name whose that thing is. Each
# is as plausible from a poster naming someone else, so none is recovered. The author is the one id the signatures
# name; when they name several it is unresolved, never ranked. An id named as acting, as the receiver, as a role in
# a definite phrase, as taken over or split from, or after "for", "to", "cc" or "with" in its clause is listed as
# another party. A heading that opens with "@", "To" or "For ... (" names its addressee there.
# Checked by test_a_heading_names_its_poster_or_nobody_never_another_party: 148 headings posted by one session and
# naming others give that session or unresolved, never another id. Limit: a signature place is still read as the
# poster's when a poster puts another party there ("## Review · #300 · `id`", "## Seam review (`id`)", a relayed
# "## From `id`: ..."); those wordings are not in the probes. So a byline is only ever ``author_guess`` (see
# ``checkin_author`` for the one comment author the map uses).
_BYLINE = re.compile(r"(?i)(·|\(|\bsession|\bfrom|\bintegrator|\bowner)[\s`*_:,]*$")
_ROLES = ("integrator", "owner")
_FOR = re.compile(r"(?i)\b(?:for|to|cc|with)\b[^.:;·]*$")
_RECEIVER = re.compile(r"(?i)\b(?:receivers?|next\s+owners?)\b[^.;·]*$")
_DEFINITE = re.compile(r"(?i)\bthe\b[^.:;·()]{0,48}$")       # the text before a role word: "the #196 "
_TAKEN_FROM = re.compile(r"(?i)\b(?:(?:tak(?:e|es|en|ing)|took|pick(?:s|ed|ing)?|handed)\s+(?:\w+\s+){0,2}?"
                         r"(?:over|up)|inherit(?:s|ed|ing)?|split(?:s|ting)?(?:\s+off)?|fork(?:s|ed|ing)?)\s+from"
                         r"[\s`*_:,]*(?:session\b[\s`*_:,]*)?$")
_ACTS = re.compile(r"(?i)^[`*_]*(?:['’]s\b|[^\S\n]+(?:(?:has|had|have)\s+(?:not\s+|already\s+|now\s+|also\s+)?)?"
                   r"(?:asked|agreed|agrees|approved|approves|accepted|accepts|acknowledged|acknowledges|requested|"
                   r"confirmed|confirms|proposed|suggested|offered|assigned|answered|decided|said|wrote|replied)\b)")
_AFTER_DOT = re.compile(r"·[\s`*_]*(?:session\b[\s`*_]*)?$")                  # "· `", "· session `"
_AFTER_PAREN = re.compile(r"\([\s`*_]*(?:session\b[\s`*_]*)?$")               # "(`", "(session `"
_SEGMENT_ENDS = re.compile(r"^[`*_]*\s*(?:$|[·(])")                           # "· `id` ·", "· `id` (date)"
_SENTENCE_ENDS = re.compile(r"^[`*_]*(?:\s*$|\s*·|\.(?:[\s*_]|$))")    # "Session `id`.", "**Session `id`** ·"
_PAREN_ENDS = re.compile(r"^[`*_]*\s*[);]")
# What a "(" must not follow to be the heading's own: a number ("#300", a comment id), a party ("the integrator",
# "receiver", "session"), a possessive, or a phrase after a preposition in its clause ("status of WU-11").
_PARTY = re.compile(r"(?i)\b(?:integrators?|owners?|receivers?|reviewers?|sessions?)[\s`*_]*$")
_PAREN_OWNED = re.compile(r"(?i)(?:#\d+|\d{6,}|\b(?:integrators?|owners?|receivers?|reviewers?|sessions?)|['’]s)"
                          r"[\s`*_]*$|\b(?:of|on|about|for|to|with|by|from|in|into|at|before|after)\b"
                          r"(?:[^:;·.—–,()]|\.(?=\S))*$")                     # "genesis.py" ends no clause
_SENDER = re.compile(r"(?i)^[#*_\s]*(?:from|hand(?:ing)?\s+over\b[^`·;:()\n]{0,60}?\bfrom|"
                     r"handing\b[^`·;:()\n]{1,60}?\bover\s+from)\b"
                     r"[\s`*_:,]*(?:the\s+)?(?:#\d+(?:['’]s)?\s+)?(?:(?:integration\s+)?(?:integrator|owner)\b)?"
                     r"[\s`*_:,(]*(?:session\b)?[\s`*_:,]*$")
_SESSION_OPENS = re.compile(r"(?i)(?:^[#*_\s]*|\.[*_]*\s+[*_]*)session[\s`*_]*$")   # "**Session `", ".** Session `"
_ADDRESSED = re.compile(r"(?i)^[#*_\s]*(?:@|to\b|for\b[^(\n]{0,80}\()[\s`]*")
_FENCE = re.compile(r"^[ \t]*(`{3,}|~{3,})")
_INDENTED = re.compile(r"^(?: {4}|\t| {0,3}\t)")
_MD_LINES = re.compile(r"\r\n|\r|\n")                # the only line endings CommonMark (and so GitHub) knows


def _lines(text: str) -> list[str]:
    """The lines of a text where CommonMark ends them (LF, CR, CRLF): never at a form feed, a vertical tab or a
    Unicode line separator, which Python's ``splitlines`` also splits at."""
    return _MD_LINES.split(_text(text))


def _spans(text: str) -> list[tuple[int, int, str, str]]:
    """(start, end, canonical id, client) for every session identity in ``text``, in order."""
    found = []
    for client, pattern, key in _IDS:
        found += [(m.start(), m.end(), key(m), client) for m in pattern.finditer(_text(text))]
    return sorted(found)


def identities(text: str) -> list[tuple[int, str, str]]:
    """(position, canonical id, client) for every session identity in ``text``, in order."""
    return [(at, key, client) for at, _end, key, client in _spans(text)]


OPENS_WITH_ANOTHER = "receipt session_id names an id it does not open with"
NAMES_SEVERAL = "receipt session_id names more than one id"


def receipt_session(value: str | None) -> tuple[str | None, str, str | None]:
    """A receipt's ``session_id`` as (canonical id, client, why it names no session). The value names a session only
    as the check-in rule does: it opens (after code marks or emphasis) with an id in a known form and names exactly
    one, so "`B` → `A`", "B, handed over to A" or "B (now A)" names nobody (``NAMES_SEVERAL``), and so does a value
    that names a known id it does not open with: "unknown (handed over from B)", "Session: B" or "my parent B's
    worker" (``OPENS_WITH_ANOTHER``). A value that names no id in a known form ("uat-vulcan",
    "codex/root/collab-20261030") is the whole value verbatim, an opaque id."""
    value = _text(value).strip()
    if not value:
        return None, "unknown", None
    hits = _spans(value)
    if not hits:
        prefix = re.match(r"(?i)(codex|kimi|cursor|claude|uat)\b", value)
        return value, (prefix[1].lower() if prefix else "other"), None
    if value[:hits[0][0]].strip("`*_ \t"):
        return None, "unknown", OPENS_WITH_ANOTHER
    if len({h[2] for h in hits}) > 1:
        return None, "unknown", NAMES_SEVERAL
    return hits[0][2], hits[0][3], None


def canonical_identity(value: str | None) -> tuple[str | None, str]:
    """A receipt's ``session_id`` as (canonical id, client): ``receipt_session`` without its reason, (None, "unknown")
    when the value names no session."""
    return receipt_session(value)[:2]


# ------------------------------------------------------------------ board comments

_HTML = re.compile(r"\A\s*(?:<!--.*?-->\s*)+", re.S)
# A bold run with code in it ("**New `x.py`, read-only.**") is a sentence, not a label, and ends no segment.
_LABEL = re.compile(r"^(?P<indent>[ \t]*)(?:[-*][ \t]+)?"       # [ \t], not \s: a blank line is never rescanned
                    r"(?:\*\*(?P<bold>[A-Z][^*`\n]{0,70}?)[:.]?\*\*[ \t]*:?"
                    r"|(?P<plain>[A-Z][A-Za-z /()·>→-]{1,48}):(?=\s))", re.M)
# Kinds, tested in this order on the heading's lead (the text before its first ":", "(", "—" or "."). A lead that
# names no kind, or only an update ("Resumed ..."), is a claim or handoff when the rest of the heading announces one.
_KINDS = [
    ("claim+handoff", r"\bclaims?\b.*handoff|handoff.*\bclaims?\b"), ("handoff", r"handoff|released into"),
    ("release", r"\breleas|\bwithdr[ae]w"), ("claim", r"\bclaims?\b"), ("check-in", r"check-?in"),
    ("correction", r"correction"), ("acknowledgment", r"acknowledg"), ("intake", r"\bintake\b"),
    ("update", r"update|status|landed|resumed|pause|continuation|heads-up"),
]
_ANNOUNCES = ("claim+handoff", "handoff", "claim")
_CLAIM_ID = re.compile(r"(?i)\bclaims?[\s:]*(?:comment\s+)?`?\d{6,}`?|\b(?:no|not a|without)\s+claims?\b")
_RECHECK = re.compile(r"(?i)\br[^\w\n]{0,2}e-?check[^\n]{0,24}?"
                      r"(20[0-9]{2}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}(?::[0-9]{2})?Z)")
_RELEASE = re.compile(r"(?i)releases?\s+(the \w+ half of\s+)?claims?\s+`?(\d{10})"
                      r"|claim\s+`?(\d{10})`?\s+(?:is\s+|was\s+|now\s+)?released\b"
                      r"|\bclos(?:e|es|ing)\s+(?:the\s+|my\s+)?claims?\s+(?:in\s+|at\s+)?"
                      r"(?:\S*?issuecomment-|comment\s+)?`?(\d{10})(?!\d)")
_STOPPED = re.compile(r"(?i)delivery under claim `?(\d{10})`? is stopped")
_NEGATED = re.compile(r"(?i)\b(?:not|never|no|nothing)\b|n't\b")
# A negation reaches only its own clause: "Nothing is merged, so this releases claim N" releases it.
_CLAUSE = re.compile(r"(?i)[.;:,!?\n]|\b(?:so|and|but|then)\b")
_CLAIM_REF = re.compile(r"(?i)claim[s:]*\s*(?:comment\s+)?`?(\d{10})|issuecomment-(\d{10})|correction to `?(\d{10})")
# A comment speaks of its own claim only in the first person.
_OWN_CLAIM = re.compile(r"(?i)\bmy\s+\[?claims?[\s:]*(?:comment\s+)?`?(\d{10})|\bclaims?\s+`?(\d{10})`?\s+(?:is\s+)?"
                        r"released\s+into\b|\bcorrection\s+to\s+(?:my\s+)?(?:claim\s+)?(?:comment\s+)?`?(\d{10})")
_COMMENT_ID = re.compile(r"(?<![\d#/])\d{10}(?!\d)")
_UNDONE = re.compile(r"(?i)\b(?:blocked|pending|planned|proposed|requested|later)\b")    # "Release blocked: ..."
_DRAFT = re.compile(r"(?i)(?:draft(?:\s+(?:PR|child))?:?|handoff:?(?:\s+PR)?|released into(?:\s+draft)?(?:\s+PR)?)"
                    r"\**\s*\[?#(\d{1,9})(?!\d)")
_BRANCH = re.compile(r"(?i)\bbranch:?\**[^\S\n]*`([\w.-]+/[\w./-]+)`")
_PULL_LINK = re.compile(r"github\.com/([\w.-]+/[\w.-]+)/pull/(\d{1,9})\b")
_ROUTE = re.compile(r"greg/path\.json#(N(?:10|\d)|P(?:1[0-3]|\d)|process)\b")
_NODE = re.compile(r"\b(N(?:10|\d)|P(?:1[0-3]|\d))\b|\bprocess\b")
UNIT = re.compile(r"\b(?:WU|MU|MW)-[0-9A-Z]{1,2}\b|\b[SD]\d{1,2}-[A-Z]\b")
ASK = re.compile(r"\b[SD]\d{1,2}\.A\d{1,2}\b")
_UNIT_PHRASE = re.compile(r"(?i)\bunit\s+((?:WU|MU|MW)-[0-9A-Z]{1,2}|[SD]\d{1,2}-[A-Z])\b")
# A clause that excludes what follows it ("Not `x`", "read-only: `x`", "No edits to `x`"), and a predicate that
# excludes the paths just before it ("`x` is read-only", "`x` (read-only)").
_NEGATIVE = re.compile(r"(?i)^\W*(?:no|not|do\s+not|explicitly\s+not|out\s+of\s+scope|read-only|excluded|leave)\b|"
                       r"[,;:(]\s*not\s+(?=`)|read-only|\bexcluded\b|\bnot\s+touch(?:ed|ing)\b|\bno\s+edits?\s+to\b|"
                       r"\bdo\s+not\s+(?:edit|touch|change)\b|\bleave\b|\bout\s*\(|\breviews\b")
_PREDICATE = re.compile(r"(?i)\b(?:is|are|stays?|remains?|kept|left)\s+"
                        r"(?:read-only|untouched|excluded|out\s+of\s+scope)\b|\bare\s+not\s+touched\b|"
                        r"\b(?:is|are)\s+read\b,?\s*(?:and\s+|but\s+)?never\s+(?:edited|changed)\b")
_EXCLUDED_BEFORE = re.compile(r"(?i)[\s`]*\(?\s*(?:is|are|stays?|remains?|kept)?\s*(?:(?:read-only|excluded|untouched|"
                              r"not\s+touched|out\s+of\s+scope|hot|held\s+by)\b|=\s*#\d)")
# Emphasis markers, matched so that each can become spaces of its own length: "Do **not** edit" is "Do   not   edit".
_EMPHASIS = re.compile(r"\*+|(?<![\w`/.-])_+|_+(?![\w`/.-])")
# A list item that opens with a path and limits itself to it ("- `x.json` and its pin only") declares that path.
_ONLY_ITEM = re.compile(r"(?m)^[ \t]*(?:[-*+]|\d{1,3}[.)])[ \t]+`[^`\n]+`[^\n.;:`]{0,40}?(?<!-)\bonly\b")
_INLINE_FILES = re.compile(r"(?i)(?<=[^\s*-])[^\S\n]+\*{0,2}files?:\*{0,2}[^\S\n]")
_ALIASES = {
    "prompt": {"prompt", "founder request", "asked to", "request", "task / intended observable outcome", "task"},
    "plan": {"plan", "approach", "method"},
    "route": {"route", "gps node", "parent gps node"},
    "guidance": {"guidance read", "guidance revision"},
}
_SCOPE_LABELS = {"owned", "scope", "bounded scope", "remaining scope"}
CLAIM_KINDS = ("claim", "check-in", "claim+handoff")
# Authors taken from another comment or a pull request rather than stated in the comment itself. Like every reading
# of ``comment_author``, a join gives only ``author_guess``: it never makes a session, a claim's session or a release.
JOINS = ("claim reference", "shared marker", "pr receipt", "pr task_ref")
EXACT = "check-in block"     # the ``how`` of a comment author the map uses (``checkin_author``)
UNVERIFIED = "unverified"    # the ``how`` of every other comment


def heading_of(body: str) -> str:
    """The first non-empty line after any leading HTML comments, at most ``HEADING_LIMIT`` characters."""
    text = _HTML.sub("", _text(body))
    return next((line.strip() for line in _lines(text) if line.strip()), "")[:HEADING_LIMIT]


def comment_kind(heading: str) -> str:
    """What a comment is, from the lead of its heading; a claim id it cites ("claim 6794587797") is not a claim."""
    low = _CLAIM_ID.sub(" ", _text(heading)[:HEADING_LIMIT].lower())
    low = re.sub(r"\bclaims?\s+releas", "releas", low)
    lead = re.split(r"[:(—.]", low, maxsplit=1)[0]
    kind = next((k for k, pat in _KINDS if re.search(pat, lead)), None)
    if kind in (None, "update"):
        kind = next((k for k, pat in _KINDS if k in _ANNOUNCES and re.search(pat, low)), kind)
    return kind or "other"


def _norm(label: str) -> str:
    return re.split(r"[,(]", label.lower())[0].strip(" *:.")


def segments(body: str) -> list[tuple[str, str]]:
    """Every labelled segment of a comment, in order: (normalized label, its text up to the next label indented no
    deeper), so a label's nested list belongs to it."""
    body = _text(body)
    marks = [(m.start(), m.end(), _norm(m["bold"] or m["plain"]), len(m["indent"])) for m in _LABEL.finditer(body)]
    stops, open_ = [len(body)] * len(marks), []
    for i, (start, _end, _label, indent) in enumerate(marks):
        while open_ and marks[open_[-1]][3] >= indent:     # a label no deeper ends every open one at its depth or more
            stops[open_.pop()] = start
        open_.append(i)
    return [(label, body[end:min(stop, end + SEGMENT_LIMIT)].strip())
            for (_s, end, label, _d), stop in zip(marks, stops)]


def fields(body: str) -> dict[str, str]:
    """Labelled segments of a comment: ``{normalized label: text of its first segment}``."""
    out: dict[str, str] = {}
    for label, text in segments(body):
        out.setdefault(label, text)
    return out


def _field(found: dict[str, str], name: str) -> str:
    """The first segment whose label is an alias of ``name``. Labels match whole, never by prefix."""
    return next((found[a] for a in found if a in _ALIASES[name]), "")


def files_parts(body: str) -> list[tuple[str, bool]]:
    """The texts a comment declares its files in, each with whether a files or "Owned" label introduces it: every
    segment whose label has the word "files", every inline "File(s):" sentence, or else the owned/scope segments; and
    every list item that limits itself to a path ("- `x.json` and its pin only")."""
    segs = segments(body)
    named = [(t, True) for label, t in segs if re.search(r"\bfiles?\b", label)]
    for line in _lines(body):
        found = list(_INLINE_FILES.finditer(line))
        for i, m in enumerate(found):                    # from its sentence's start to the next inline label
            floor = max(found[i - 1].end() if i else 0, m.start() - SENTENCE_LIMIT)
            start = max(line.rfind(". ", floor, m.start()), line.rfind("; ", floor, m.start()))
            stop = min(found[i + 1].start() if i + 1 < len(found) else len(line), m.start() + SENTENCE_LIMIT)
            named.append((line[start + 2 if start >= 0 else floor:stop], True))
    only = [(m[0][:SENTENCE_LIMIT], False) for m in _ONLY_ITEM.finditer(_text(body))]
    return (named or [(t, label == "owned") for label, t in segs if label in _SCOPE_LABELS]) + only


def files_text(body: str) -> str:
    """The text a comment declares its files in (``files_parts``), as one text."""
    return "\n".join(t for t, _labelled in files_parts(body))


def _excluded(sentence: str) -> list[tuple[int, int]]:
    """Spans of a sentence whose backticked paths it excludes: after a negative phrase ("Not", "read-only:", "Leave",
    "Founder reviews"), and before a negative predicate ("... are read-only", "... are read, never edited"); inside
    parentheses either reaches only the parentheses. Emphasis does not hide a phrase ("Do **not** edit")."""
    plain = _EMPHASIS.sub(lambda m: " " * len(m[0]), sentence)

    def scope(at: int) -> tuple[int, int]:
        opened = sentence.rfind("(", 0, at)
        closed = sentence.find(")", opened) if opened >= 0 else -1
        inside = opened >= 0 and (closed < 0 or closed >= at)
        return (opened, closed if closed >= 0 else len(sentence)) if inside else (0, len(sentence))
    spans = []
    for m in _NEGATIVE.finditer(plain):
        spans.append((m.start(), scope(m.start())[1]))
    for m in _PREDICATE.finditer(plain):
        spans.append((scope(m.start())[0], m.start()))
    return spans


def declared_files(text: str, tracked: set[str], dirs: set[str], globs: bool = True) -> list[str]:
    """Backticked repository paths in a files/scope field, without the ones a negative phrase excludes. A directory
    holds its files only when written as a glob (``dir/**``), and a glob counts only where ``globs`` says a files label
    introduces the text; otherwise a directory is recorded as ``new file under <dir>``, which covers no existing
    file."""
    keep, seen = [], set()
    for sentence in re.split(r"\n|(?<=[.;])\s+", _text(text)):
        sentence = sentence[:SENTENCE_LIMIT]
        spans = _excluded(sentence)
        plain = _EMPHASIS.sub(lambda m: " " * len(m[0]), sentence)
        for m in re.finditer(r"`([^`\n]+)`", sentence):
            if _EXCLUDED_BEFORE.match(plain, m.end()) or any(a <= m.start() < b for a, b in spans):
                continue
            token = m[1].split("::")[0].strip()          # `greg/x.py::test_y` names the file greg/x.py
            if not re.fullmatch(r"[\w./*-]+", token):       # spaces, braces, colons: prose or a pattern, not a path
                continue
            bare = token.rstrip("/")
            if "*" in token:
                if not globs:
                    continue
                root = token.split("*")[0].rstrip("/")
                ok = root in dirs or root in tracked or root.rsplit("/", 1)[0] in dirs
            elif bare in dirs and bare not in tracked:
                token, ok = f"new file under {bare}", True
            else:
                ok = token in tracked or ("/" in token and "." in token.rsplit("/", 1)[-1]
                                          and token.split("/")[0] in dirs)
            if ok and token not in seen:
                keep.append(token)
                seen.add(token)
    return keep


def _addressed(heading: str) -> set[int]:
    """Positions of the ids a heading addresses: right after a leading "@", "To" or "For ... (" ."""
    m = _ADDRESSED.match(heading)
    return {at for at, _k, _c in identities(heading) if m and at <= m.end() + 1}


def _prose_at(lines: list[str]) -> list[int]:
    """The indices of the lines outside code: a fence closes only on a run of its own character at least as long as
    the one that opened it, with nothing after it, and a line indented four spaces after a blank line is an indented
    block."""
    out, fence, blank, block = [], None, True, False
    for i, line in enumerate(lines):
        f = _FENCE.match(line)
        if fence:
            if f and f[1][0] == fence[0] and len(f[1]) >= len(fence) and not line[f.end():].strip():
                fence = None
            continue
        if f:
            fence = f[1]
            continue
        block = bool(line.strip()) and bool(_INDENTED.match(line)) and (blank or block)
        blank = not line.strip()
        if not block:
            out.append(i)
    return out


def _prose(text: str) -> list[str]:
    """The lines of a text outside code (``_prose_at``), split where CommonMark ends lines."""
    lines = _lines(text)
    return [lines[i] for i in _prose_at(lines)]


def _signature(heading: str, at: int, end: int, key: str) -> bool:
    """Whether the id at ``at``-``end`` stands where only the poster's signature stands (see the rules above)."""
    before, after = heading[:at], heading[end:end + 16]
    if _SENDER.match(before):
        return True
    dot = _AFTER_DOT.search(before)
    if dot:                                              # "to the integrator · `id`" names the integrator
        return bool(_SEGMENT_ENDS.match(after)) and not _PARTY.search(before[max(0, dot.start() - 32):dot.start()])
    if _SESSION_OPENS.search(before):
        return bool(_SENTENCE_ENDS.match(after))
    paren = _AFTER_PAREN.search(before)
    if paren and key.startswith("session_") and _PAREN_ENDS.match(after):
        return not _PAREN_OWNED.search(heading[max(0, paren.start() - 200):paren.start()].rstrip("`*_ \t"))
    return False


def _heading_bylines(heading: str) -> tuple[tuple[str, str] | None, list[str]]:
    """The (id, client) a heading's signatures name as its author, or None, and the ids it names as other parties."""
    bylines, others = [], []
    for at, end, key, client in _spans(heading):
        window = max(0, at - 48)
        by = _BYLINE.search(heading[window:at])
        if not by or (by[1] == "(" and not key.startswith("session_")):
            continue
        word, before = by[1].lower(), heading[max(0, at - 64):at]
        role_at = window + by.start()
        sender = bool(_SENDER.match(heading[:at]))
        the = _DEFINITE.search(heading[max(0, role_at - 64):role_at]) if word in _ROLES and not sender else None
        if (_ACTS.match(heading[end:end + 64]) or _RECEIVER.search(before) or _TAKEN_FROM.search(before) or the
                or (word not in ("·", "from") and _FOR.search(before))):
            others.append(key)
        elif _signature(heading, at, end, key):
            bylines.append((key, client))
    if len(set(bylines)) != 1:                           # none, or several ids: unresolved, not guessed
        return None, others
    [(key, client)] = set(bylines)
    return (key, client), [k for k in others if k != key]


def comment_author(body: str) -> dict:
    """Who wrote a board comment: a labelled author line outside code fences, else the byline of a Markdown heading
    or bold title, else an opening "Session `id`" line. Never an addressee, never the first id in the body.

    Returns ``author`` (None when unresolved), ``client``, ``how``, the ``addressees`` it names and its ``team``.
    """
    body = _text(body)
    heading = heading_of(body)
    team = _TEAM.search(heading) or _TEAM.search(body)
    addressed = _addressed(heading)
    addressees = [k for at, k, _c in identities(heading) if at in addressed]
    author = None
    for line in _prose(_HTML.sub("", body)):
        m = _LABEL.match(line)
        if not m:
            continue
        label, hits = _norm(m["bold"] or m["plain"]), identities(line)
        if label in _ADDRESSEE_LABELS:
            addressees += [h[1] for h in hits]
        elif label in _AUTHOR_LABELS and hits and author is None:
            author = (hits[0][1], hits[0][2], "label")
    if author is None and heading.startswith(("#", "**")) and not _TEAM.search(heading):
        found, others = _heading_bylines(heading)
        addressees += others
        if found:
            author = (*found, "heading")
    if author is None:                                   # "Session `...`." as the comment's opening line
        rest = [ln for ln in _lines(_HTML.sub("", body)) if ln.strip()][1:2]
        opening = _OPENING.match(rest[0]) if rest and not _INDENTED.match(rest[0]) else None
        hits = identities(rest[0]) if opening else []
        if hits and hits[0][0] <= opening.end():
            author = (hits[0][1], hits[0][2], "opening line")
    lead = _HTML.match(body)
    return {"author": author[0] if author else None, "client": author[1] if author else "unknown",
            "how": author[2] if author else "unresolved", "addressees": sorted(set(addressees)),
            "team": team[0] if team else None,
            "marker": next(iter(re.findall(r"<!--\s*(UNIIMENTE-[A-Za-z0-9-]+)\s*-->", lead[0] if lead else "")), None)}


# The block's own Session line, in CHECKIN_BLOCK's format ("- Session: <id> (<client>)", the label also in bold).
_CHECKIN_SESSION = re.compile(r"^-[ \t]+(?:\*\*Session:\*\*|Session:)[ \t]+(?P<value>\S.*)$")
_LIST_ITEM = re.compile(r"^[ \t]*(?:[-*+]|\d{1,3}[.)])[ \t]")
_HEADING = re.compile(r"^#{1,6}(?:[ \t]|$)")       # an ATX heading at the margin, as CHECKIN_BLOCK's "## Check-in"
_BOLD_TITLE = re.compile(r"^\*\*(?:[^*\n]|\*(?!\*))+\*\*[ \t]*$")   # a line that is one bold run: "**Handoff**"
# A line at the margin that starts another block, so it is not a lazy continuation of the Session line's paragraph:
# what CommonMark lets interrupt a paragraph. An ATX heading ("#" to "######", then a space, a tab or the end), a
# thematic break, a fence, a block quote, a list item that is not empty (an ordered one only from 1), and an HTML
# block of types 1 to 6 (its tag in both CommonMark 0.29's and 0.31's lists). Anything else is read with the Session
# line, the safe direction: "#317", inline HTML ("<sub>"), a "|" row, an emphasis run, an item numbered "2.".
_HTML_BLOCK = ("address|article|aside|base|basefont|blockquote|body|caption|center|col|colgroup|dd|details|dialog|dir|"
               "div|dl|dt|fieldset|figcaption|figure|footer|form|frame|frameset|h[1-6]|head|header|hr|html|iframe|"
               "legend|li|link|main|menu|menuitem|nav|noframes|ol|optgroup|option|p|param|section|summary|table|"
               "tbody|td|tfoot|th|thead|title|tr|track|ul")
_BLOCK_START = re.compile(r"^(?:#{1,6}(?:[ \t]|$)|(?:\*[ \t]*){3,}$|(?:-[ \t]*){3,}$|(?:_[ \t]*){3,}$|`{3,}[^`]*$|~{3,}|>"
                          r"|[-*+][ \t]+\S|1[.)][ \t]+\S"
                          r"|(?i:<(?:script|pre|style|textarea)(?:[ \t>]|$)|<!--|<\?|<![a-z]|<!\[CDATA\[|"
                          rf"</?(?:{_HTML_BLOCK})(?:[ \t>]|/>|$)))")


def opens_with_checkin(body: str) -> bool:
    """Whether the check-in marker opens the comment: its first line that is not blank starts with it, at the margin
    (never inside a quote, a fence or an indented block, never later in the body)."""
    first = next((line for line in _lines(body) if line.strip(" \t")), "")
    return first.startswith(CHECKIN)


# What a check-in post says about who posts it (see ``checkin_verdict``).
_RELAYED = re.compile(r"(?i)(?<![a-z])relay(?:s|ed|ing)?(?![a-z])|\bon\s+(?:\S+\s+){0,3}?behalf\b|"
                      r"\bposts?\s+(?:this|it)\s+as\s+(?:yours|(?:your|its|their)\s+own)\b")
_HANDED = re.compile(r"(?i)\bhand\s*-?\s*(?:offs?|overs?)\b|\bhand(?:s|ed|ing)?\s+(?:\S+\s+){0,3}?over\b|\breassign|"
                     r"\b(?P<review>review(?:ed)?)\b|\b(?:for|to)\s+the\s+next\s+owner\b")
_ANSWERS = re.compile(r"(?i)\banswer(?:s|ed|ing)?\b[^.]*$")     # "#316 answers the integrator's review": its own reply
_POSTER_LABELS = {"posted by", "relayed by", "relay", "from", "on behalf of", "recording session", "implementer",
                  "agent", "agent / claim", "identity", "author", "sender"}
_ASK = re.compile(r"(?i)^#{1,6}[ \t]+(?:[\w-]+[ \t]+){0,2}?ask\b")      # "## Coordination ask:", "## Second ask,"
RELAYED = "relayed"
HANDED = "handoff, review or reassignment wording in its heading"
POSTER = "a label naming its poster names another id"
HEADING_NAMES = "its heading names another id"
MARKER_LINE = "text after the marker on its line"
NOT_FIRST = "Session line not first"
NO_ID = "Session value does not open with an id"
TWO_IDS = "Session value names more than one id"


def _session_value(lines: list[str], at: int) -> tuple[str | None, str | None, bool]:
    """(id, client, whether it names more than one id) for the Session line at ``at``: its value with the lines
    GitHub renders in the same paragraph (indented ones, and lazy ones up to a blank line or a line at the margin that
    CommonMark lets interrupt a paragraph, ``_BLOCK_START``). The id is the one that opens the value, else None."""
    first = _CHECKIN_SESSION.match(lines[at])["value"]
    value = [first]
    for line in lines[at + 1:]:
        if not line.strip(" \t") or _BLOCK_START.match(line):
            break
        value.append(line)
    hits = _spans("\n".join(value))
    if not hits or hits[0][0] >= len(first) or first[:hits[0][0]].strip("`*_ \t"):
        return None, None, len({h[2] for h in hits}) > 1
    return hits[0][2], hits[0][3], len({h[2] for h in hits}) > 1


def checkin_verdict(body: str) -> dict:
    """Whether a comment is itself a check-in: ``author`` and ``client`` when it is exact, else ``reason``, why not
    (None when the marker does not open it), and ``names``, the one id its block's Session line names (diagnosis only,
    never a session or a holder). See ``checkin_author`` for the rule."""
    out = {"author": None, "client": "unknown", "reason": None, "names": None}
    lines = _lines(body)
    filled = [i for i, line in enumerate(lines) if line.strip(" \t")]
    if not filled or not lines[filled[0]].startswith(CHECKIN):
        return out
    reasons = [MARKER_LINE] if lines[filled[0]].rstrip(" \t") != CHECKIN else []
    after, heading = filled[1:], ""
    if after and (_HEADING.match(lines[after[0]]) or (_BOLD_TITLE.match(lines[after[0]])
                                                     and not _spans(lines[after[0]]))):
        heading, after = lines[after[0]], after[1:]
    prose = _prose_at(lines)
    at = after[0] if after and _CHECKIN_SESSION.match(lines[after[0]]) else None
    if at is None:
        reasons.append(NOT_FIRST)
        at = next((i for i in prose if _CHECKIN_SESSION.match(lines[i])), None)   # for ``names`` only
    key, client, several = _session_value(lines, at) if at is not None else (None, None, False)
    if key is None and at is not None:
        reasons.append(NO_ID)
    if several:
        reasons.append(TWO_IDS)
    text = [lines[i] for i in prose]
    said = []
    if _RELAYED.search("\n".join(text)):
        said.append(RELAYED)
    if any(not (m["review"] and _ANSWERS.search(heading[:m.start()])) for m in _HANDED.finditer(heading)):
        said.append(HANDED)
    if key and any((m := _LABEL.match(line)) and _norm(m["bold"] or m["plain"]) in _POSTER_LABELS
                   and {k for _at, k, _c in identities(line)} - {key} for line in text):
        said.append(POSTER)
    if key and heading.startswith("#") and {k for _at, k, _c in identities(heading)} - {key}:
        byline = _heading_bylines(heading)[0]
        if not _ASK.match(heading) or (byline and byline[0] != key):
            said.append(HEADING_NAMES)
    reasons = said + reasons
    out["names"] = key if not several else None
    if reasons:
        out["reason"] = reasons[0]
    else:
        out.update(author=key, client=client)
    return out


def checkin_author(body: str) -> tuple[str, str] | None:
    """The (id, client) of a comment that is itself a check-in, else None (``checkin_verdict`` says why not).

    Where the block stands, as ``CHECKIN_BLOCK`` puts it: the marker alone on the comment's first line that is not
    blank (nothing else on that line), then the block's own ``Session:`` line as the first line that is not blank after
    it, or after the block's heading when that follows the marker. The heading is one ``#`` heading line, or a line
    that is one bold run and names no session id (so "**Relayed by `A`.**" is a lead line, not a heading). The value,
    the Session line with the lines GitHub renders in the same paragraph (indented ones, and lazy ones up to a blank
    line or a line at the margin that CommonMark lets interrupt a paragraph, ``_BLOCK_START``), opens with an id and
    names exactly one: "`B` → `A`" or "`B` (relayed by `A`)" names nobody. So only blank lines sit between the marker,
    the heading and the Session line: no lead paragraph, no second heading, nothing GitHub does not render as plain
    text (an HTML comment, ``<details>``, ``<pre>``, a fence).

    What the post says about who posts it: it names nobody when its text outside code relays ("relay", "relays",
    "relayed", "relaying", "on ... behalf", "post this as yours"); when its heading, or the bold line acting as its
    heading, hands over, reassigns or reviews ("handoff", "hand over", "reassign", "review", "reviewed", "for the next
    owner"; a "review" after "answers" in the same sentence is the post's own reply, as in live check-in 7068165767);
    when a labelled line that names a poster ("Posted by", "Relayed by", "Relay", "From", "On behalf of", "Recording
    session", "Implementer", "Agent", "Identity", "Author", "Sender") names another id; or when its heading names
    another id, except an ask ("## Coordination ask: ... still yours, `X`?", "## Second ask, `X`: ..."; live
    check-ins 6853648077 and 6858741219 ask another session in their headings) whose byline is no other id. So a
    relay, a handoff, a reassignment record, a review and a template filled in for someone else that say what they
    are name nobody, and so does a session's own handoff of its own claim: release your own claim under a heading
    such as "## Release: claim N". On the live board this keeps all 29 check-ins round 6 read as exact.

    Limit, inherent: a check-in is declared, not authenticated. A block filled in, pasted or copied with none of this
    wording is read as the session its Session line names, whoever posts it; this guards against ordinary posts by
    cooperating agents, not a deliberate evader.

    Lines end only where CommonMark ends them (LF, CR, CRLF), and a blank line holds only spaces and tabs: a form
    feed or a Unicode line separator after the marker leaves the text after it on the marker's line, which GitHub
    shows as literal text but not as a list item, so no Session line follows the marker."""
    verdict = checkin_verdict(body)
    return (verdict["author"], verdict["client"]) if verdict["author"] else None


def _statements(pattern: re.Pattern, body: str) -> list[tuple[re.Match, bool]]:
    """Each match of ``pattern`` with whether its clause negates it ("I do NOT release claim ...", "Nothing here
    releases claim ..."; not "Nothing is merged, so this releases claim ...")."""
    out = []
    for m in pattern.finditer(body):
        before = body[max(0, m.start() - 120):m.start()]
        before = before[max((x.end() for x in _CLAUSE.finditer(before)), default=0):]
        out.append((m, bool(_NEGATED.search(before))))
    return out


def withdrawn(kind: str, heading: str, own: list[str]) -> list[str]:
    """Claims a comment gives up by its kind: a release or withdrawal ("Withdrawn: my claim N", "Claim release (N)")
    gives up the claims it calls its own and those its heading cites; a handoff gives up the claims its heading cites
    ("Handoff: ..., draft #296 (claim: comment N)"). A heading whose lead negates or defers it ("Not withdrawn",
    "Release blocked") gives up nothing."""
    lead = re.split(r"[:(—.]", heading, maxsplit=1)[0]
    if kind not in ("release", "handoff") or _NEGATED.search(lead) or _UNDONE.search(lead):
        return []
    cited = [m[1] for m in _CLAIM_REF.finditer(heading) if m[1]]
    if kind == "handoff":
        return cited
    return own + cited + _COMMENT_ID.findall(heading)


def unit_refs(heading: str, body: str) -> list[str]:
    """Unit and ask ids a claim names: any in its heading, "unit <id>" and ask ids in its text."""
    return sorted(set(UNIT.findall(heading)) | set(ASK.findall(body)) | set(_UNIT_PHRASE.findall(body)))


def parse_comment(c: dict, tracked: set[str], dirs: set[str]) -> dict:
    body = "\n".join(_lines(c.get("body")))           # one line ending, so every reader splits where GitHub does
    found, heading = fields(body), heading_of(body)
    who, verdict = comment_author(body), checkin_verdict(body)
    exact = (verdict["author"], verdict["client"]) if verdict["author"] else None
    kind = comment_kind(heading)
    route = _field(found, "route")
    node = _ROUTE.search(body)
    in_label = (_NODE.search(route) or UNIT.search(route)) if route else None
    in_heading = (UNIT.search(heading) or ASK.search(heading)) if kind in CLAIM_KINDS else None
    recheck = _RECHECK.search(body)
    refs = [next(g for g in m.groups() if g) for m in _CLAIM_REF.finditer(body[:600])]
    own = [next(g for g in m.groups() if g) for m in _OWN_CLAIM.finditer(body[:600])]
    draft = _DRAFT.search(heading)
    released = _statements(_RELEASE, body)
    files: list[str] = []
    for text, labelled in files_parts(body):
        files += [f for f in declared_files(text, tracked, dirs, globs=labelled) if f not in files]
    return {
        "cid": c.get("id"), "at": _text(c.get("created_at")), "heading": heading[:160],
        "kind": kind, "author": exact[0] if exact else None, "client": exact[1] if exact else "unknown",
        "how": EXACT if exact else UNVERIFIED,
        "author_guess": who["author"], "author_guess_client": who["client"], "author_guess_how": who["how"],
        "addressees": who["addressees"], "team": who["team"],
        "prompt": _field(found, "prompt")[:400], "plan": _field(found, "plan")[:400],
        "route": node[1] if node else (in_label or in_heading or [None])[0],
        "guidance": _field(found, "guidance")[:160],
        "files": files,
        "recheck": recheck[1] if recheck else None,
        "releases": list(dict.fromkeys([m[2] or m[3] or m[4] for m, negated in released if not negated and not m[1]]
                                       + withdrawn(kind, heading, own))),
        "partial_releases": [m[2] for m, negated in released if not negated and m[1]],
        "stops": [m[1] for m, negated in _statements(_STOPPED, body) if not negated],
        "claim_refs": refs, "own_claim_refs": own, "draft_pr": int(draft[1]) if draft else None,
        "pr_refs": sorted({int(n) for n in _DRAFT.findall(body)}),
        "pr_links": sorted({(repo, int(n)) for repo, n in _PULL_LINK.findall(body)}),
        "branch_refs": sorted(set(_BRANCH.findall(body))),
        "unit_refs": unit_refs(heading, body), "heading_units": sorted(_ids(heading)),
        "heading_ids": sorted({k for _at, k, _c in identities(heading)}),
        "is_checkin": opens_with_checkin(body), "marker": who["marker"],
        "checkin_reason": verdict["reason"], "checkin_names": verdict["names"],
    }


def issue_comments(repo: str, issue: int, token: str | None) -> list[dict]:
    out, page = [], 1
    while True:
        batch = _get(f"https://api.github.com/repos/{repo}/issues/{issue}/comments?per_page=100&page={page}", token)
        if not isinstance(batch, list):
            raise ValueError("the comments API answered with something other than a list")
        out += batch
        if len(batch) < 100:
            return out
        page += 1


def pr_files(repo: str, number: int, token: str | None) -> list[str]:
    """The files a pull request changes against its base, from the GitHub API, every page; a renamed file counts under
    its old name too. Raises when an entry has no readable name, or when the list reaches the API's cap of 3,000 files
    and may be cut: a list that may be incomplete is not read, never taken as whole."""
    out, page = [], 1
    while True:
        batch = _get(f"https://api.github.com/repos/{repo}/pulls/{number}/files?per_page=100&page={page}", token)
        if not isinstance(batch, list):
            raise ValueError("the files API answered with something other than a list")
        for f in batch:
            if not (isinstance(f, dict) and isinstance(f.get("filename"), str)
                    and (f.get("previous_filename") is None or isinstance(f["previous_filename"], str))):
                raise ValueError("the files API answered with an entry that has no file name")
            out += [f["filename"]] + ([f["previous_filename"]] if f.get("previous_filename") else [])
        if len(batch) < 100:
            return out
        if page >= 30:
            raise ValueError("the files API stops at 3,000 files, so this list may be cut")
        page += 1


API_FILES = "_api_files"   # where main() leaves a pull request's changed files read from the API


def attach_api_files(repo: str, prs: list, token: str | None, line: str = LINE, workers: int = 8,
                     reader=None) -> tuple[int, list[int]]:
    """For each open pull request into the line, read its changed files from the API and leave them on the object
    under ``API_FILES``; ``_row`` uses them only when local git cannot diff the PR. A PR stacked on another branch is
    left alone: its file list against its own base would count files merged forward from the line as its own. Returns
    how many were read and the numbers that could not be."""
    from concurrent.futures import ThreadPoolExecutor
    reader = reader or (lambda n: pr_files(repo, n, token))
    todo = [p for p in prs or [] if isinstance(p, dict) and p.get("state") == "open" and type(p.get("number")) is int
            and isinstance(p.get("base"), dict) and p["base"].get("ref") == line]

    def one(p):
        try:
            p[API_FILES] = reader(p["number"])
            return None
        except Exception:  # noqa: BLE001 - a PR whose files cannot be read stays "without diff"
            return p["number"]
    with ThreadPoolExecutor(max_workers=workers) as pool:
        failed = sorted(n for n in pool.map(one, todo) if n is not None)
    return len(todo) - len(failed), failed


# ------------------------------------------------------------------ position

def _try(fn, root: Path = ROOT):
    try:
        return fn()
    except Exception as exc:  # noqa: BLE001 - a missing source is reported, never fatal
        return {"not_run": _reason(exc, root)}


def _route(root: Path) -> dict:
    from greg import path as gp
    data = gp.load(root / "greg" / "path.json")
    pos = gp.position(None, data)
    workstreams = data.get("subordinate_workstreams") or {}
    return {"destination": data["destination"], "boundary": data.get("completion_boundary", {}).get("product"),
            "acceptance_node": {"id": pos["active"]["id"], "title": pos["active"]["title"]} if pos.get("active") else None,
            "achieved": pos.get("achieved", []),
            "founder_use_gate": data.get("completion_boundary", {}).get("founder_use_gate"),
            "nodes": [n["id"] for n in data["nodes"]],
            "mind_nodes": [n["id"] for w in workstreams.values() if isinstance(w, dict) for n in w.get("nodes", [])]}


def _directive(root: Path) -> dict:
    from acceptance import directive
    here = root / "acceptance"
    doc = directive.load_map(here / directive.DIRECTIVE_MAP.name)
    rep = directive.directive_report(doc, directive.load(here / directive.MANIFEST.name),
                                     directive.load(here / directive.CONTRACT.name), None, root)
    units = {u["id"]: u for u in doc.get("units", [])}
    asks = {a["id"]: a for s in rep["sections"] for a in s["asks"]}
    paths = {a["id"]: a.get("owner_paths", []) for s in doc["sections"] for a in s["asks"]}
    open_units = {row["unit"] for row in rep["buildable_in_dependency_order"] if row["unit"]}
    rows = []
    for row in rep["buildable_in_dependency_order"]:
        unit = units.get(row["unit"] or "", {})
        waits = [d for d in unit.get("depends_on", []) if d in open_units]
        tiers = sorted({(f"{asks[a]['tier']} -> {asks[a]['required_tier']}" if asks[a]["tier"] != asks[a]["required_tier"]
                         else f"{asks[a]['tier']} ({asks[a].get('coverage', 'partial')})")
                        for a in row["asks"] if a in asks})
        rows.append({"unit": row["unit"], "title": unit.get("title", "asks with no gap-map unit"),
                     "asks": row["asks"], "prerequisite_only": bool(row.get("prerequisite_only")),
                     "waits_on": waits, "evidence": tiers,
                     "owner_paths": sorted({p for a in row["asks"] for p in paths.get(a, [])})})
    return {"ran_tests": rep["ran"], "summary": rep["summary"], "line": directive.summary_line(rep), "units": rows}


def _foundry(root: Path) -> dict:
    from foundry import completion
    s = completion.status(completion.contract(root / "foundry" / "completion.yaml"))
    return {"complete": s["complete"], "by_state": {k: len(v) for k, v in s["by_state"].items()}}


def _mind(root: Path) -> dict:
    out = subprocess.run([sys.executable, "-B", "scripts/mind_status.py"], cwd=root, capture_output=True, text=True,
                         timeout=120, env={**os.environ, "PYTHONPATH": str(root)})
    return json.loads(out.stdout)["counts"]


def _intents(root: Path, top: int = 4) -> list[dict]:
    """The newest founder intent records on this tree, by the 8-digit date in their file name."""
    rows = []
    for f in (root / "docs" / "intent").glob("INTENT-20*.json"):
        date = re.match(r"INTENT-(20\d\d)-?(\d\d)-?(\d\d)", f.name)
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError, RecursionError):
            continue
        if date and isinstance(d, dict) and _text(d.get("intent_id")):
            rows.append({"id": d["intent_id"], "title": (_text(d.get("title")) or _text(d.get("statement")))[:140],
                         "state": _text(d.get("state")), "date": "".join(date.groups())})
    rows.sort(key=lambda r: (r["date"], r["id"]), reverse=True)
    return rows[:top]


def route_drift(root: Path, route: dict) -> dict:
    """Node ids on ``greg/path.json`` that the current-route section of BACKCAST_GPS.md does not name.

    The section starts at a heading beginning "## Current full-machine route" and ends at the next level-2 heading.
    A range names the nodes between its ends only when both ends carry the same letter (N0–N10, P3–P4).
    """
    if "not_run" in route:
        return {"not_run": "route not read"}
    doc = root / "docs" / "BACKCAST_GPS.md"
    text = doc.read_text(encoding="utf-8") if doc.exists() else ""
    m = re.search(r"^## Current full-machine route[^\n]*\n(.*?)(?=^## |\Z)", text, re.S | re.M)
    if not m:
        return {"section": False, "missing": []}
    section = m[1]
    named = set(re.findall(r"\b[NP]\d{1,2}\b", section))
    for letter, lo, hi in re.findall(r"\b([NP])(\d{1,2})\s*[–-]\s*\1(\d{1,2})\b", section):
        named |= {f"{letter}{i}" for i in range(int(lo), int(hi) + 1)}
    wanted = route.get("nodes", []) + route.get("mind_nodes", [])
    return {"section": True, "missing": [n for n in wanted if n not in named]}


_REPEAT = {"": {"?": "?", "+": "+"}, "?": {"?": "?", "+": "*"}, "+": {"?": "*", "+": "+"}, "*": {"?": "*", "+": "*"}}


def _filter_pattern(pattern: str) -> list[tuple[re.Pattern, str]]:
    """A GitHub Actions filter pattern (the workflow syntax's filter pattern cheat sheet) as a list of (one-character
    test, repetition): ``*`` is any character but ``/`` repeated, ``**`` any character repeated; ``?`` makes the
    character before it optional and ``+`` repeats it; ``[...]`` is one letter or digit of a class; ``\\`` escapes;
    everything else is literal. A repetition applied to a repetition is folded into one (``*+`` is ``*``, ``a+?`` is
    ``a*``), so no quantifier is ever nested."""
    out: list[tuple[re.Pattern, str]] = []
    i = 0
    while i < len(pattern):
        ch = pattern[i]
        if pattern.startswith("**", i):
            out.append((re.compile("."), "*"))
            i += 1
        elif ch == "*":
            out.append((re.compile("[^/]"), "*"))
        elif ch in "?+" and out:
            out[-1] = (out[-1][0], _REPEAT[out[-1][1]][ch])
        elif ch == "[" and "]" in pattern[i + 2:]:
            end = pattern.index("]", i + 2)
            out.append((re.compile("[" + "".join(c if c.isalnum() or c == "-" else "\\" + c
                                                 for c in pattern[i + 1:end]) + "]"), ""))
            i = end
        elif ch == "\\" and i + 1 < len(pattern):
            out.append((re.compile(re.escape(pattern[i + 1])), ""))
            i += 1
        else:
            out.append((re.compile(re.escape(ch)), ""))
        i += 1
    return out


def _filter_matches(pattern: str, text: str) -> bool:
    """Whether a GitHub filter pattern matches the whole of ``text``. The pattern is run as a set of positions over
    ``text``, one character at a time, so the time grows with the length of the pattern times the length of the text,
    whatever the pattern: no backtracking, so no pattern can make the map hang."""
    steps = _filter_pattern(pattern)

    def closure(states: set[int]) -> set[int]:          # a "?" or "*" step may match nothing
        out, todo = set(), list(states)
        while todo:
            s = todo.pop()
            if s not in out:
                out.add(s)
                if s < len(steps) and steps[s][1] in ("?", "*"):
                    todo.append(s + 1)
        return out
    states = closure({0})
    for ch in text:
        moved = set()
        for s in states:
            if s < len(steps) and steps[s][0].fullmatch(ch):
                moved |= {s, s + 1} if steps[s][1] in ("+", "*") else {s + 1}
        states = closure(moved)
        if not states:
            return False
    return len(steps) in states


def _push_covers(on, line: str) -> tuple[str, list[str], bool]:
    """(filter kind, branch patterns, whether every push to ``line`` triggers) for a workflow's ``on`` value. A
    ``paths`` or ``paths-ignore`` filter makes a push trigger only when its files match, so it covers no line."""
    if isinstance(on, str):
        on = [on]
    if isinstance(on, list):
        return ("every branch", [], True) if "push" in on else ("no push trigger", [], False)
    if not isinstance(on, dict) or "push" not in on:
        return "no push trigger", [], False
    push = on["push"] if isinstance(on["push"], dict) else {}
    paths = " and paths" if "paths" in push or "paths-ignore" in push else ""
    for kind in ("branches", "branches-ignore"):
        if kind in push:
            patterns = [push[kind]] if isinstance(push[kind], str) else _texts(push[kind])
            hit = False
            for pattern in patterns:                     # GitHub: the last matching pattern wins; "!" negates
                if _filter_matches(pattern[1:] if pattern.startswith("!") else pattern, line):
                    hit = not pattern.startswith("!")
            matched = hit if kind == "branches" else not hit
            return kind + (paths if matched else ""), patterns, matched and not paths
    if "tags" in push or "tags-ignore" in push:
        return "tags only", [], False
    return "every branch" + paths, [], not paths


def line_checks(rows: list[dict], root: Path, line: str = LINE, prs_read: bool = True, unreadable=()) -> dict:
    """How pushes to the line get checked: by the push trigger of ``canonical-ci.yml``, or only through an open pull
    request from this repository whose head is the line. ``covered`` is None, never False, when the pull requests were
    not read or one of them could not be read (it may be the one). Without PyYAML the workflow is not read."""
    try:
        import yaml
    except ImportError:
        return {"not_run": "PyYAML not importable"}
    doc = yaml.safe_load((root / ".github" / "workflows" / "canonical-ci.yml").read_text(encoding="utf-8"))
    on = (doc.get("on", doc.get(True)) if isinstance(doc, dict) else None)    # YAML 1.1 reads a bare `on:` as True
    kind, patterns, pushed = _push_covers(on, line)
    carriers = sorted(r["pr"] for r in rows if r["head"] == line and r["same_repo"]) if prs_read else None
    covered = True if pushed or carriers else None if not prs_read or unreadable else False
    return {"push_filter": kind, "push_branches": patterns, "push_covers_line": pushed,
            "pull_requests_with_line_as_head": carriers, "covered": covered}


def position(root: Path = ROOT) -> dict:
    route = _try(lambda: _route(root), root)
    return {"route": route, "directive": _try(lambda: _directive(root), root),
            "foundry": _try(lambda: _foundry(root), root), "mind": _try(lambda: _mind(root), root),
            "latest_intents": _try(lambda: _intents(root), root),
            "route_drift": _try(lambda: route_drift(root, route), root)}


# ------------------------------------------------------------------ the join

# Times are read only in ASCII digits: on a str pattern \d matches any Unicode digit, and strptime and int() read
# them too, so a time in Arabic-Indic or full-width digits would sort after every real time.
_NOW = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]{1,6})?(?:Z|[+-][0-9]{2}:[0-9]{2})")
_TIME = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}")


def _when(stamp: str | None) -> datetime | None:
    """A ``YYYY-MM-DDTHH:MM:SS`` prefix in ASCII digits that is a real time, in UTC; None for anything else."""
    if not _TIME.fullmatch(_text(stamp)[:19]):
        return None
    try:
        return datetime.strptime(_text(stamp)[:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def parse_now(value: str | None) -> datetime | None:
    """``YYYY-MM-DDTHH:MM:SSZ`` or an ISO time with an offset, in UTC; None for anything else."""
    if not isinstance(value, str) or not _NOW.fullmatch(value.strip()):
        return None
    try:
        return datetime.fromisoformat(value.strip().replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None


def activity(last: str | None, now: datetime) -> str:
    seen = _when(last)
    if not seen:
        return "UNKNOWN"
    hours = (now - seen).total_seconds() / 3600
    return "ACTIVE" if hours < 48 else "QUIET" if hours < 168 else "DORMANT"


def changed_files(pr: dict, root: Path, against: str | None = None) -> list[str] | None:
    """Files the PR changes against its base (or ``against``), from local git, a renamed file under both names; None
    when the refs are not here or git is not."""
    try:
        r = subprocess.run(["git", "diff", "--no-renames", "--name-only",
                            f"origin/{against or pr['base']}...{pr['head_sha']}"],
                           cwd=root, capture_output=True, text=True, timeout=60, check=False)
    except (OSError, ValueError, subprocess.SubprocessError):
        return None
    return [f for f in r.stdout.splitlines() if f] if r.returncode == 0 else None


def _own_commit_files(pr: dict, root: Path, line: str = LINE) -> set[str] | None:
    """Files touched by the PR's own commits: non-merge commits of its head on neither its base nor the line (a renamed
    file under both names)."""
    try:
        r = subprocess.run(["git", "log", "--no-merges", "--no-renames", "--name-only", "--format=", pr["head_sha"],
                            f"^origin/{pr['base']}", f"^origin/{line}"], cwd=root, capture_output=True, text=True,
                           timeout=60, check=False)
    except (OSError, ValueError, subprocess.SubprocessError):
        return None
    return {f for f in r.stdout.splitlines() if f} if r.returncode == 0 else None


def own_files(pr: dict, root: Path, line: str = LINE) -> list[str] | None:
    """Files the PR itself changes: against its base, and for a PR not based directly on the line only those that
    also differ from the line and that one of its own commits touches (a commit on neither its base nor the line), so
    the line's files a stacked head merged in, and its parent's files, are not counted as the PR's. Several merge
    bases make a three-dot diff fall back to one of them; the commit test does not."""
    changed = changed_files(pr, root)
    if changed is None or pr["base"] == line:
        return changed
    on_line = changed_files(pr, root, against=line)
    both = None if on_line is None else [f for f in changed if f in set(on_line)]
    touched = _own_commit_files(pr, root, line) if both else set()
    return None if both is None or touched is None else [f for f in both if f in touched]


def _git_ok(*args: str, root: Path) -> bool | None:
    """Whether a git command exits 0; None when it could not answer (exit codes above 1, or no git)."""
    try:
        r = subprocess.run(["git", *args], cwd=root, capture_output=True, timeout=60, check=False)
    except (OSError, ValueError, subprocess.SubprocessError):
        return None
    return {0: True, 1: False}.get(r.returncode)


def on_line(base: str, root: Path, line: str = LINE) -> bool | None:
    """A branch whose tip is already in the line's history (a merged or closed parent's branch): work stacked on it
    is headed for the line. ``main`` and the line are never such a branch. None when git cannot say (the branch or the
    line is not in this clone)."""
    if base in (line, "main"):
        return False
    return _git_ok("merge-base", "--is-ancestor", f"origin/{base}", f"origin/{line}", root=root)


def carried(pr: dict, root: Path, line: str = LINE) -> bool | None:
    """Whether the PR holds no commit of its own off the line: every non-merge commit of its head is already on the
    line, by branch_catalog's rule (patch-equal copies count as present), or, for a PR stacked on another branch, every
    one is on that branch or on the line (its own work landed; what is left is its parent's). None when git cannot
    say."""
    try:
        unique = branch_catalog._git("rev-list", "--count", "--no-merges", "--cherry-pick", "--right-only",
                                     f"origin/{line}...{pr['head_sha']}", root=root).strip()
        if unique == "0" or pr.get("base") in (None, line):
            return unique == "0"
        own = branch_catalog._git("rev-list", "--count", "--no-merges", pr["head_sha"], f"^origin/{pr['base']}",
                                  f"^origin/{line}", root=root).strip()
    except (OSError, ValueError, subprocess.SubprocessError):
        return None
    return own == "0"


def _covers(declared: str, path: str) -> bool:
    """A declared file, directory prefix or glob covers ``path``, a path under it, or a directory that holds it; ``*``
    or ``**`` alone covers every path."""
    whole, declared, path = "*" in declared, declared.rstrip("/*"), path.rstrip("/")
    if not declared:
        return whole
    if "*" in declared:
        return fnmatch.fnmatchcase(path, declared)
    return declared == path or path.startswith(declared + "/") or declared.startswith(path + "/")


_SHA = re.compile(r"[0-9a-f]{40}")
_STAMP = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z")


def _stamp(value) -> str:
    """A GitHub timestamp (``YYYY-MM-DDTHH:MM:SSZ`` in ASCII digits, and a real date and time) as given; anything
    else is the empty string, which reads as unknown, sorts before every real time and shows as nothing. Only such a
    stamp is ever compared, so none can sort after every real time and win the newest copy of a PR or a session's
    last update."""
    return value if isinstance(value, str) and _STAMP.fullmatch(value) and _when(value) else ""


def _pull(p) -> dict | None:
    """The fields of one pull-request object the map reads, typed; None when one it needs is missing."""
    if not isinstance(p, dict):
        return None
    head, base = p.get("head"), p.get("base")
    if not (type(p.get("number")) is int and isinstance(head, dict) and isinstance(base, dict)
            and _text(head.get("ref")) and _text(base.get("ref")) and _SHA.fullmatch(_text(head.get("sha")))
            and all(p.get(k) is None or isinstance(p[k], str) for k in ("title", "body"))):
        return None

    def repo(side: dict) -> str | None:
        return _text(side["repo"].get("full_name")) or None if isinstance(side.get("repo"), dict) else None
    return {"number": p["number"], "state": _text(p.get("state")), "draft": p.get("draft") is True,
            "title": _text(p.get("title")), "body": _text(p.get("body")), "updated_at": _stamp(p.get("updated_at")),
            "head": head["ref"], "head_sha": head["sha"], "head_repo": repo(head),
            "base": base["ref"], "base_repo": repo(base),
            "api_files": [f for f in p[API_FILES] if isinstance(f, str)] if isinstance(p.get(API_FILES), list)
            else None}


def _ident(item, index: int, key: str):
    """How an unreadable item is cited: its number or id when it has one, else its position."""
    value = item.get(key) if isinstance(item, dict) else None
    return value if type(value) is int else f"item {index + 1}"


def _receipt_fields(r: dict | None) -> tuple[dict, list[str]]:
    """The receipt fields the map reads, each of the type the receipt check requires. A field of another type is
    read as absent and named in the returned problems, never coerced into a guess; a field that is missing is
    absent without a problem."""
    problems: list[str] = []
    r = r or {}
    coord = r.get("coordination", {})
    if not isinstance(coord, dict):
        coord, problems = {}, ["coordination"]

    def text(obj: dict, key: str, label: str) -> str | None:
        value = obj.get(key)
        if key in obj and not isinstance(value, str):
            problems.append(label)
        return value if isinstance(value, str) else None

    def strings(obj: dict, key: str, label: str) -> list[str]:
        value = obj.get(key)
        if key in obj and (not isinstance(value, list) or len(_texts(value)) != len(value)):
            problems.append(label)
        return _texts(value)
    overlap = coord.get("overlap")
    if "overlap" in coord and not isinstance(overlap, dict):
        problems.append("overlap")
    out = {"session_id": text(coord, "session_id", "session_id"), "task_ref": text(coord, "task_ref", "task_ref"),
           "recheck_at": text(coord, "recheck_at", "recheck_at"), "files": strings(coord, "files", "files"),
           "overlap": text(overlap, "status", "overlap.status") if isinstance(overlap, dict) else None,
           "scope": text(r, "scope", "scope") or "", "intent_refs": strings(r, "intent_refs", "intent_refs")}
    return out, problems


_COORDINATION = {"task_ref", "session_id", "files", "interfaces", "recheck_at", "overlap", "integration"}


def _files_refused(r: dict | None) -> str | None:
    """Why the receipt check (``.github/workflows/collaboration-receipt.yml``) refuses a receipt for the shape of its
    coordination or of its claimed files, in the check's words; None when those pass, or there is no receipt. The
    check's rules, copied because it runs without a checkout: ``coordination`` is present and has exactly the check's
    fields, and ``files`` is a list of at least one distinct non-blank text, each a repository-relative path or
    directory prefix. Such a receipt's files are not a whole list. Its other refusals (a stale head SHA, an interface,
    a recheck time, overlap or integration fields) say nothing about its files."""
    if not isinstance(r, dict):
        return None
    if "coordination" not in r:
        return "receipt: missing or unexpected fields"
    coordination = r["coordination"]
    if not (isinstance(coordination, dict) and set(coordination) == _COORDINATION):
        return "coordination: missing or unexpected fields"
    files = coordination["files"]
    if not (isinstance(files, list) and files and all(isinstance(f, str) and f.strip() for f in files)):
        return "claimed files: text array required"
    if len(files) != len({f.strip() for f in files}):
        return "claimed files: duplicate entries"
    for path in files:
        if not (path == path.strip() and not path.startswith("/") and not set("\\:<>") & set(path)
                and all(part not in ("", ".", "..") for part in path.rstrip("/").split("/"))):
            return "claimed files must be repository-relative paths or directory prefixes"
    return None


def _session_refused(value: str | None) -> str | None:
    """Why the receipt check refuses a receipt's ``session_id`` text, in the check's words; None when it does not (or
    the value is not text, which ``receipt_problems`` names). Copied from ``.github/workflows/collaboration-receipt.yml``
    for the reason ``_files_refused`` gives. Such a value names no session."""
    if not isinstance(value, str):
        return None
    if not value.strip():
        return "task reference and actual session identifier required"
    if value.strip().casefold() in ("unknown", "unassigned", "none", "pending"):
        return "actual session identifier required"
    if "<" in value or ">" in value:
        return "replace session identifier placeholders"
    return None


def _ids(text: str) -> set[str]:
    """Unit ids (``WU-11``, ``S42-A``) and ask ids (``S42.A1``) in a text."""
    return set(UNIT.findall(text)) | set(ASK.findall(text))


def _changed(pull: dict, root: Path, use_git: bool, line: str = LINE) -> dict:
    """A PR's changed files and where they came from: local git (``diff``), else, for a PR into the line, the GitHub
    API (``api``); None when neither could say."""
    local = own_files(pull, root, line) if use_git else None
    if local is not None:
        return {"changed": local, "changed_via": "diff"}
    if pull.get("api_files") is not None and pull["base"] == line:
        return {"changed": pull["api_files"], "changed_via": "api"}
    return {"changed": None, "changed_via": None}


def _row(pull: dict, root: Path, use_git: bool, line: str = LINE) -> dict:
    body = pull["body"]
    r = receipt_of(body)
    f, problems = _receipt_fields(r)
    same_repo = pull["head_repo"] is not None and pull["head_repo"] == pull["base_repo"]
    refused = _session_refused(f["session_id"])
    sid, client, unnamed = (None, "unknown", None) if refused else receipt_session(f["session_id"])
    if sid and not same_repo:                 # a receipt from another repository is no session's declaration here
        refused = "fork: " + ("the head repository is not the base repository" if pull["head_repo"] else
                              "the head repository is unknown, so it is not known to be the base repository")
        sid, client = None, "unknown"
    stated_head = r.get("head_sha") if r else None
    refs = " ".join(f["intent_refs"])
    node = _ROUTE.search(refs)
    named = _ids(pull["title"]) | _ids(f["scope"]) | _ids(refs)
    return {
        "pr": pull["number"], "title": pull["title"][:110], "base": pull["base"], "head": pull["head"],
        "head_sha": pull["head_sha"], "head_repo": pull["head_repo"], "base_repo": pull["base_repo"],
        "same_repo": same_repo,
        "draft": pull["draft"], "updated": pull["updated_at"], "receipt": r is not None,
        "older_receipt": r is None and receipt_of(body, version=1) is not None, "receipt_problems": problems,
        "files_refused": _files_refused(r),
        "session": sid, "client": client, "session_refused": refused, "session_unnamed": unnamed,
        "receipt_head_stale": stated_head != pull["head_sha"] if isinstance(stated_head, str) else None,
        "task_ref": f["task_ref"],
        "files": f["files"][:FILES_LIMIT], "files_cut": max(0, len(f["files"]) - FILES_LIMIT),
        **_changed(pull, root, use_git, line),
        "overlap": f["overlap"], "recheck": f["recheck_at"], "scope": f["scope"][:200],
        "names": sorted(named), "mentions": sorted(_ids(body) - named),
        "route": node[1] if node else None,
    }


def pr_rows(prs: list[dict], root: Path, use_git: bool = True, unreadable: list | None = None,
            line: str = LINE, duplicates: list | None = None) -> list[dict]:
    """One row per open pull request. ``names`` are the unit and ask ids in its title or receipt (scope and
    intent_refs); ``mentions`` are those only its body has; ``files`` are the receipt's first ``FILES_LIMIT`` files
    and ``files_cut`` counts the rest. An object the map cannot read is skipped and cited in ``unreadable``. A number
    seen twice (pages that shifted while they were fetched) is read once, from its newest ``updated_at``, and cited
    in ``duplicates``."""
    newest: dict[int, tuple[int, dict]] = {}
    for i, p in enumerate(prs or []):
        try:
            pull = _pull(p)
        except Exception:  # noqa: BLE001 - one unreadable pull request never stops the map
            pull = None
        if pull is None:
            if unreadable is not None:
                unreadable.append(_ident(p, i, "number"))
            continue
        if pull["number"] in newest:
            if duplicates is not None:
                duplicates.append(pull["number"])
            if pull["updated_at"] <= newest[pull["number"]][1]["updated_at"]:
                continue
        newest[pull["number"]] = (i, pull)
    rows = []
    for i, pull in newest.values():
        if pull["state"] != "open":
            continue
        try:
            rows.append(_row(pull, root, use_git, line))
        except Exception:  # noqa: BLE001 - one unreadable pull request never stops the map
            if unreadable is not None:
                unreadable.append(_ident(prs[i], i, "number"))
    return rows


def _integration(r: dict, line: str = LINE) -> bool:
    """The integration PR (its head is the line) or a composed ``candidate/`` head, from this repository."""
    return r["same_repo"] and (r["head"] == line or r["head"].startswith("candidate/"))


def line_bound(rows: list[dict], line: str = LINE, contained=None) -> list[dict]:
    """Open PRs whose work is headed for the line: based on it, stacked on a PR that is, or based on a branch no open PR
    has as its head that ``contained(base)`` says is already in the line's history (a merged or closed parent). The
    stack walk is lineage_map's: no depth limit, a cycle ends it, and a head opened twice reaches the line through
    either PR.

    A head branch is matched to another PR's base only when that PR comes from this repository: a fork's branch
    called ``main`` or the line's name stacks nothing. The integration PR and composed ``candidate/`` heads are left
    out: each carries everyone's files, so counting it would make every file look contended.
    """
    contained = contained or (lambda _base: False)
    heads = {r["head"] for r in rows if r["same_repo"]}

    def node(r: dict) -> dict:
        reached = r["base"] == line or (r["base"] not in heads and contained(r["base"]))
        return {"number": (r["head"], r["base"]), "base": line if reached else r["base"]}
    nodes = [node(r) for r in rows]
    waiting: dict[str, list[int]] = {}
    for i, r in enumerate(rows):
        if r["same_repo"]:
            waiting.setdefault(nodes[i]["base"], []).append(i)
    by_ref: dict[str, dict] = {}
    reached = [line]                                     # each ref once, from the line outwards: no depth is re-walked
    while reached:
        for i in waiting.pop(reached.pop(), []):
            if rows[i]["head"] not in by_ref:
                by_ref[rows[i]["head"]] = nodes[i]
                reached.append(rows[i]["head"])
    return [r for i, r in enumerate(rows) if not _integration(r, line) and _stacked_on(nodes[i], line, by_ref)]


def _holder(r: dict) -> str:
    """The holder a PR counts as: its session, else a label of its own, so two PRs that name no session never share
    one and their overlap still shows."""
    if r["session"]:
        return r["session"]
    why = ("no receipt" if not r["receipt"] else "refused session id" if r.get("session_refused")
           else r.get("session_unnamed") or "no session id")
    return f"({why}) #{r['pr']}"


_PR_NUMBER = re.compile(r"(?:#|/pull/)(\d+)(?!\d)")
_FIX_ROUND = re.compile(r"(?i)\bfix[- ]round\b")


def _fix_round_of(child: dict, parent: dict) -> bool:
    """A child PR whose title calls it a fix round ("Fix round: ...") and whose title or task_ref names the parent it
    is stacked on."""
    return bool(_FIX_ROUND.search(child["title"])) and str(parent["pr"]) in _PR_NUMBER.findall(
        f"{child['title']} {child['task_ref'] or ''}")


def _norm_path(path: str) -> str:
    """A declared path as a key: a directory without its trailing slash, a glob as written, the whole tree as ``**``."""
    bare = path.rstrip("/*")
    return ("**" if "*" in path else bare) if not bare else path if "*" in bare else bare


def _ends(glob: str) -> tuple[str, str]:
    """The literal start and end of a glob: two globs can share a path only where one start extends the other and
    one end extends the other."""
    first = min(i for i, ch in enumerate(glob) if ch in "*?[")
    last = max(i for i, ch in enumerate(glob) if ch in "*?]")
    return glob[:first], glob[last + 1:]


def _holders(bound: list[dict]) -> tuple[dict[int, str], dict[int, str]]:
    """For each PR, the holder it counts as (a fix-round child counts as the parent it is stacked on, through any
    depth) and the label it is shown under (its own declared session, marked when it is a fix round)."""
    heads = {r["head"]: r for r in bound if r["same_repo"]}
    key: dict[int, str] = {}
    label: dict[int, str] = {}
    for r in bound:
        path, cur, on_path = [], r, set()
        while cur["pr"] not in key:
            path.append(cur)
            on_path.add(cur["pr"])
            parent = heads.get(cur["base"])
            if parent is None or parent["pr"] in on_path or not _fix_round_of(cur, parent):
                key[cur["pr"]] = _holder(cur)
                break
            label[cur["pr"]] = f"{_holder(cur)} (fix round of #{parent['pr']})"
            cur = parent
        for p in path:
            key[p["pr"]] = key[cur["pr"]]
            label.setdefault(p["pr"], _holder(p))
    return key, label


def contended(rows: list[dict], line: str = LINE, contained=None) -> list[dict]:
    """Paths that line-bound PRs from two or more session ids declare or change, a declared directory or glob
    covering the paths under it (the rule ``who_touches`` uses); two globs share a row when their literal starts and
    ends allow a common path. A PR carried by the line holds nothing; one session's stack, and a fix-round child
    stacked on its parent, count once. ``holders`` shows each PR under its own declared session."""
    bound = [r for r in line_bound(rows, line, contained) if not r.get("carried")]
    key_of, label_of = _holders(bound)
    exact: dict[str, list] = {}
    under: dict[str, set[str]] = {}
    globs: dict[str, list] = {}
    for r in bound:
        who = key_of[r["pr"]]
        for f in set(r["files"]) | set(r["changed"] or []):
            key = _norm_path(f)
            if "*" in key:
                globs.setdefault(key, []).append((who, r["pr"]))
                continue
            exact.setdefault(key, []).append((who, r["pr"]))
            for i in range(1, key.count("/") + 1):
                under.setdefault("/".join(key.split("/")[:i]), set()).add(key)
    by_dir: dict[str, dict[tuple, list[str]]] = {}        # globs by the directory they start in, then by holder
    ends: dict[str, dict[str, set[tuple]]] = {}           # globs by their literal start, then their literal end
    for g, entries in globs.items():
        lead = g.split("*")[0]
        start, end = _ends(g)
        for e in entries:
            by_dir.setdefault(lead.rsplit("/", 1)[0] if "/" in lead else "", {}).setdefault(e, []).append(g)
            ends.setdefault(start, {}).setdefault(end, set()).add(e)
    matchers = {d: [(e, re.compile("|".join(fnmatch.translate(g) for g in gs))) for e, gs in held_by.items()]
                for d, held_by in by_dir.items()}
    starts = sorted(ends)

    def overlapping(start: str, end: str) -> list[tuple]:
        """Holders of globs whose literal start and end are compatible with these."""
        found = []
        near = {start[:i] for i in range(len(start) + 1)}       # starts this one extends, and starts extending it
        near |= set(starts[bisect.bisect_left(starts, start):bisect.bisect_left(starts, start + "\U0010ffff")])
        for s in near & ends.keys():
            for e, entries in ends[s].items():
                if e.endswith(end) or end.endswith(e):
                    found += entries
        return found
    compatible: dict[tuple[str, str], list[tuple]] = {}

    def held(key: str) -> dict[str, set[int]]:
        parts = key.split("/")
        ancestors = ["/".join(parts[:i]) for i in range(1, len(parts) + 1)]
        found = [e for a in ancestors for e in exact.get(a, [])]
        if "*" in key:                                  # a glob row: same or compatible globs, not every pattern run
            se = _ends(key)
            found += compatible[se] if se in compatible else compatible.setdefault(se, overlapping(*se))
        else:
            found += [e for k in under.get(key, ()) for e in exact[k]]
            found += [e for a in ["", *ancestors] for e, pattern in matchers.get(a, []) if pattern.match(key)]
        by: dict[str, set[int]] = {}
        for who, pr in found:
            by.setdefault(who, set()).add(pr)
        return by
    table = {k: by for k in [*exact, *globs] if len(by := held(k)) > 1}
    for k in [k for k in table if k in under]:          # a directory row adds nothing a file row under it shows
        if any(k2 in table and set(table[k]) <= set(table[k2]) for k2 in under[k]):
            del table[k]
    out = []
    for f, by in table.items():
        shown: dict[str, set[int]] = {}
        for n in {n for ns in by.values() for n in ns}:
            shown.setdefault(label_of[n], set()).add(n)
        out.append({"file": f, "sessions": len(by), "prs": sorted({n for ns in by.values() for n in ns}),
                    "holders": {s: sorted(ns) for s, ns in sorted(shown.items())}})
    return sorted(out, key=lambda x: (-x["sessions"], -len(x["prs"]), x["file"]))


def _worktree(where: Path) -> tuple[Path, Path] | None:
    """(top of the worktree, the repository's common git directory) that holds a directory; None when git cannot
    say. What git prints is resolved with ``os.path.realpath``, never ``Path.resolve()``, which raises RuntimeError on
    a symbolic link loop before Python 3.13."""
    try:
        r = subprocess.run(["git", "-C", str(where), "rev-parse", "--path-format=absolute", "--show-toplevel",
                            "--git-common-dir"], capture_output=True, text=True, timeout=30, check=False)
        found = r.stdout.splitlines()
        if r.returncode != 0 or len(found) != 2:
            return None
        return Path(os.path.realpath(found[0])), Path(os.path.realpath(found[1]))
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError):
        return None


def _place(path: str, root: Path = ROOT, worktrees: dict | None = None) -> tuple[str, str | None]:
    """(the path the map answers for, why it could not be placed or None). A path, relative to the root or absolute,
    is placed by the worktree that git says holds its nearest existing directory, also under the root, where a
    worktree can be nested (``.claude/worktrees/<name>``): in a worktree of this repository it is made relative to that
    worktree's top; in another repository or in none it is made absolute (``outside_path``). A symbolic link at its
    end is placed as the link, not as what it points to. When git cannot answer for the root, the root decides. When a
    directory on its way cannot be read, or git cannot say which worktree holds a path under the root, it is not
    placed: it is returned as asked with the reason, and nothing answers for it. ``worktrees`` caches what git said
    for each directory (the root and each nearest existing directory), so many paths cost git once per directory."""
    asked = posixpath.normpath(Path(path).as_posix())
    worktrees = {} if worktrees is None else worktrees

    def tree(where) -> tuple[Path, Path] | None:
        key = os.fspath(where)
        if key not in worktrees:
            worktrees[key] = _worktree(Path(key))
        return worktrees[key]

    try:
        lexical = os.path.normpath(os.path.join(root, path))
        near = lexical
        while True:                                      # the nearest existing directory, never past an error
            try:
                if stat.S_ISDIR(os.lstat(near).st_mode):
                    break
            except (FileNotFoundError, NotADirectoryError):
                pass
            if os.path.dirname(near) == near:
                raise FileNotFoundError(f"no existing directory holds {asked}")
            near = os.path.dirname(near)
        real, rest = os.path.realpath(near, strict=True), os.path.relpath(lexical, near)
        absolute = Path(real, rest).as_posix()
        here, there = tree(root), tree(real)
        if here is None:                                 # git answers for nothing here: the root decides
            top = os.path.realpath(root)
        elif there is not None and there[1] == here[1]:  # a worktree of this repository, nested or not
            top = str(there[0])
        elif there is None and os.path.relpath(real, os.path.realpath(root)).split(os.sep)[0] != os.pardir:
            return asked, "git could not say which worktree of this repository holds it"
        else:
            return absolute, None                        # another repository's worktree, or none
        placed = posixpath.normpath(Path(os.path.relpath(real, top), rest).as_posix())
    except (OSError, ValueError, RuntimeError) as exc:
        return asked, _reason(exc, root)
    return (absolute if outside_path(placed) else placed), None


def query_path(path: str, root: Path = ROOT) -> str:
    """A path as asked, made relative to the worktree of this repository that holds it (``_place``): ``./greg/x.py``,
    ``<root>/greg/x.py`` and ``greg/x.py`` in another worktree of this repository, nested under the root or not, are
    ``greg/x.py``. A path in no worktree of this repository stays absolute (``outside_path``); one that could not be
    placed is returned as asked."""
    return _place(path, root)[0]


def outside_path(path: str) -> bool:
    """A path ``query_path`` could not place in this repository: absolute, or above its root."""
    return posixpath.isabs(path) or path == ".." or path.startswith("../")


def _files_unknown(r: dict) -> bool:
    """A PR whose changed files were not read and whose receipt gives no whole readable file list: it has none, its
    list was cut, or the receipt check refuses its coordination or its files (``_files_refused``: no coordination,
    one without ``files``, an empty list, a list of the wrong type). An empty list is never read as touching
    nothing."""
    return r["changed"] is None and (not r["receipt"] or r["files_cut"] > 0 or bool(r["files_refused"]))


def who_touches(paths: list[str], rows: list[dict] | None, claims: list[dict] | None,
                tracked: set[str] | None = None, line: str = LINE, unread: list | None = None,
                root: Path = ROOT) -> list[dict]:
    """For each path: the open PRs and the claims that cover it, and ``unknown_prs``, the PRs for which nobody can say:
    those in ``unread`` (PRs that could not be read) and those whose files are known neither from a diff nor from a
    whole receipt (``_files_unknown``). ``prs``, ``unknown_prs`` or ``claims`` is None when its source was not read;
    ``tracked`` is None when the tracked files were not given. A path is placed in the worktree that holds it
    (``_place``). One in no worktree of this repository is marked ``outside_repository``; one that could not be placed
    has ``outside_repository`` None and ``not_placed``, the reason. For both, all four are None: nothing here answers
    for them, and the other paths are still answered. The integration PR is left out. A claim's ``session`` is exact or
    None; one whose author is not verified still answers for its files, with a ``note`` saying so (the risk is a wrong
    name, not a wrong file)."""
    dirs = {"/".join(f.split("/")[:i]) for f in tracked for i in range(1, f.count("/") + 1)} if tracked else set()
    bound = {r["pr"] for r in line_bound(rows or [], line)}
    hits, worktrees = [], {}
    for asked in paths:
        path, unplaced = _place(asked, root, worktrees)
        if unplaced or outside_path(path):
            hits.append({"path": path, "asked": asked, "outside_repository": None if unplaced else True,
                         **({"not_placed": unplaced} if unplaced else {}), "tracked": None, "prs": None,
                         "unknown_prs": None, "claims": None})
            continue
        prs = None if rows is None else [
            {"pr": r["pr"], "session": r["session"],
             **({"session_refused": r["session_refused"]} if r.get("session_refused") else {}),
             **({"session_unnamed": r["session_unnamed"]} if r.get("session_unnamed") else {}),
             **({"receipt_head_stale": True} if r.get("receipt_head_stale") else {}),
             "base": r["base"], "overlap": r["overlap"], "title": r["title"],
             "updated": r["updated"], "line_bound": r.get("line_bound", r["pr"] in bound),
             "carried_by_line": r.get("carried"),
             "via": [v for v, fs in (("receipt", r["files"]), (r.get("changed_via") or "diff", r["changed"] or []))
                     if any(_covers(f, path) for f in fs)], "unknown": _files_unknown(r)}
            for r in rows if not (r["same_repo"] and r["head"] == line)]
        hits.append({"path": path, **({"asked": asked} if asked != path else {}),
                     "tracked": (path in tracked or path in dirs) if tracked is not None else None,
                     "prs": None if prs is None else [{k: v for k, v in p.items() if k != "unknown"}
                                                      for p in prs if p["via"]],
                     "unknown_prs": None if prs is None else sorted(p["pr"] for p in prs if p["unknown"]
                                                                    and not p["via"]) + list(unread or []),
                     "claims": None if claims is None else [
                         {"comment": c["comment"], "session": c["session"], "how": c["how"], "at": c["at"],
                          "state": c["state"], "posted": c["posted"], "session_activity": c["session_activity"],
                          "cited_by_receipts": c["cited_by_receipts"], "names_prs": c["names_prs"],
                          **({} if c["session"] else
                             {"note": f"claimed by a comment whose author is not verified: comment {c['comment']}"})}
                         for c in claims if any(_covers(f, path) for f in c["files"])]})
    return hits


def _by_task_ref(rows: list[dict]) -> dict[str, dict]:
    """Comment ids that a receipt with a session id names exactly in its task reference (a whole digit run, never part
    of a longer number), each with the first such pull request."""
    out: dict[str, dict] = {}
    for r in rows:
        if r["task_ref"] and r["session"]:
            for run in re.findall(r"\d+", r["task_ref"]):
                out.setdefault(run, r)
    return out


def _comment(c) -> dict | None:
    """A board comment the map can read: an object with an integer id and a text body (or none)."""
    if not isinstance(c, dict) or type(c.get("id")) is not int:
        return None
    if not (c.get("body") is None or isinstance(c["body"], str)):
        return None
    return {"id": c["id"], "created_at": _stamp(c.get("created_at")), "body": _text(c.get("body"))}


def _tracked(root: Path) -> tuple[set[str], str | None]:
    """Tracked files, and a note when git did not answer (the files on disk then stand in for them)."""
    try:
        return set(branch_catalog._git("ls-files", root=root).splitlines()), None
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        note = f"git not read ({_reason(exc, root)}), files on disk stand in for tracked files"
        return set(repo_review.tracked_files(root)), note


def _said(o: dict) -> tuple[str | None, str]:
    """A comment's author as far as anything says: its exact author, else its guess."""
    return (o["author"], o["client"]) if o["author"] else (o["author_guess"], o["author_guess_client"])


def join_authors(parsed: list[dict], rows: list[dict]) -> None:
    """Give a comment that neither is a check-in nor suggests an author an ``author_guess`` from what it points to,
    labelled by how: its first-person claim ("my claim N", "claim N released into", "Correction to N"), a shared
    ``UNIIMENTE-`` marker, the receipt of the draft PR its heading hands off, or the receipt whose task_ref cites it.
    Review, intake, acknowledgment and team posts are never joined to a PR or a claim, and no join contradicts an id
    the comment's heading names. A join is a guess even when what it points to is exact."""
    by_id = {c["cid"]: c for c in parsed if _said(c)[0]}
    by_pr = {r["pr"]: r for r in rows}
    by_task = _by_task_ref(rows)
    marked: dict[str, dict] = {}
    for o in parsed:
        if o["marker"] and _said(o)[0]:
            marked.setdefault(o["marker"], o)
    for c in parsed:
        if _said(c)[0]:
            continue
        plain = not re.search(r"(?i)review|intake|acknowledg", c["heading"]) and not c["team"]
        ref = next((by_id[int(x)] for x in c["own_claim_refs"] if int(x) in by_id and int(x) != c["cid"]), None)
        pr = by_pr.get(c["draft_pr"]) if c["draft_pr"] else None
        twin = marked.get(c["marker"]) if c["marker"] else None
        task = by_task.get(str(c["cid"])) if c["kind"] in CLAIM_KINDS else None
        fits = set(c["heading_ids"]).__contains__ if c["heading_ids"] else (lambda _author: True)
        found = None
        if ref and plain and fits(_said(ref)[0]):
            found = (*_said(ref), "claim reference")
        elif twin and fits(_said(twin)[0]):
            found = (*_said(twin), "shared marker")
        elif pr and pr["session"] and plain and fits(pr["session"]):
            found = (pr["session"], pr["client"], "pr receipt")
        elif task and plain and fits(task["session"]):
            found = (task["session"], task["client"], "pr task_ref")
        if found:
            c.update(author_guess=found[0], author_guess_client=found[1], author_guess_how=found[2])


def sessions_of(rows: list[dict], parsed: list[dict], now: datetime) -> dict[str, dict]:
    """One row per session id that a receipt or a check-in block names (never a guess): its PRs, its check-in
    comments, and what they say it was asked, plans and works on."""
    sessions: dict[str, dict] = {}
    stated = {c["cid"]: c for c in parsed if c["author"]}

    def slot(key: str, client: str) -> dict:
        return sessions.setdefault(key, {"session": key, "client": client, "how": set(), "prs": [], "comments": 0,
                                         "last": "", "prompt": "", "plan": "", "route": None, "guidance": "",
                                         "overlap": set(), "checkin": None, "checkin_block": False, "task_refs": []})

    def seen(s: dict, at: str) -> None:
        s["last"] = max(s["last"], at)
    for r in rows:
        if r["session"]:
            s = slot(r["session"], r["client"])
            s["how"].add("receipt")
            s["prs"].append(r["pr"])
            seen(s, r["updated"])
            if r["overlap"]:
                s["overlap"].add(r["overlap"])
            s["route"] = s["route"] or r["route"]
            for run in re.findall(r"(?<!\d)\d{10}(?!\d)", r["task_ref"] or ""):
                cited = stated.get(int(run))
                if cited and cited["author"] != r["session"]:
                    s["task_refs"].append({"pr": r["pr"], "comment": int(run), "author": cited["author"]})
    for c in sorted(parsed, key=lambda x: x["at"]):
        if not c["author"]:
            continue
        s = slot(c["author"], c["client"])
        s["how"].add(c["how"])
        s["comments"] += 1
        seen(s, c["at"])
        s["prompt"] = c["prompt"] or s["prompt"]
        s["plan"] = c["plan"] or s["plan"]
        s["guidance"] = c["guidance"] or s["guidance"]
        s["route"] = c["route"] or s["route"]
        s["checkin_block"] = s["checkin_block"] or c["is_checkin"]
        s["checkin"] = c["cid"]
    for s in sessions.values():
        s["activity"] = activity(s["last"], now)
    return sessions


def _naming(rows: list[dict], line: str = LINE):
    """A function giving the open pull requests a comment names: by ``#N`` after draft/handoff wording, by a link to
    a pull request of these repositories, or by a branch an open PR from this repository has as its head. The
    integration PR and composed candidates are left out."""
    repos = {r["base_repo"] for r in rows if r["base_repo"]}
    skip = {r["pr"] for r in rows if _integration(r, line)}
    heads = {r["head"]: r["pr"] for r in rows if r["same_repo"] and r["head"] != line}

    def named(o: dict) -> set[int]:
        return ({*o["pr_refs"], *([o["draft_pr"]] if o["draft_pr"] else [])} | {n for repo, n in o["pr_links"]
                                                                              if repo in repos}
                | {heads[b] for b in o["branch_refs"] if b in heads}) - skip
    return named


def claims_of(parsed: list[dict], rows: list[dict], sessions: dict[str, dict], now: datetime,
              line: str = LINE) -> list[dict]:
    """Claim and check-in comments that declare files. ``session`` is the claim's exact author (a check-in block) or
    None; a claim whose author is not exact keeps its files, comment, state and time. A release or stop counts only
    when its comment's exact author is the claim's exact author and its clause does not negate it; "the X half of
    claim N" is a partial release. One by another exact author is ``release_stated_by_another_author``; one where
    either author is not exact is ``release_by_unverified_author``, and changes nothing. The state is the activity of
    the claim or of its exact author's newest check-in citing it; ``session_activity`` is the claiming session's.
    ``names_prs`` are the PRs the claim, or a handoff citing it, names."""
    said: dict[str, dict[str, list[dict]]] = {"releases": {}, "partial_releases": {}, "stops": {}}
    cites: dict[str, list[dict]] = {}
    for c in parsed:
        for key, index in said.items():
            for x in c[key]:
                index.setdefault(x, []).append(c)
        if c["kind"] in ("handoff", "claim+handoff", "release"):
            for x in c["claim_refs"]:
                cites.setdefault(x, []).append(c)
    by_pr = {r["pr"]: r for r in rows}
    receipts = {}
    for r in rows:
        for run in re.findall(r"(?<!\d)\d+(?!\d)", r["task_ref"] or ""):
            receipts.setdefault(run, []).append(r["pr"])
    named = _naming(rows, line)
    cited_by: dict[str, list[dict]] = {}
    for c in parsed:
        for x in set(c["claim_refs"]) | set(c["own_claim_refs"]):
            cited_by.setdefault(x, []).append(c)

    def counts(o: dict, who: str | None) -> bool:
        return bool(who) and o["author"] == who
    out = []
    for c in sorted(parsed, key=lambda x: x["at"]):
        if c["kind"] not in CLAIM_KINDS or not c["files"]:
            continue
        cid, who = str(c["cid"]), c["author"]
        mine = {k: [o for o in said[k].get(cid, []) if counts(o, who)] for k in said}
        unverified = sorted({o["cid"] for k in said for o in said[k].get(cid, [])
                             if o not in mine[k] and not (who and o["author"])})
        others = sorted({o["cid"] for k in said for o in said[k].get(cid, []) if o not in mine[k]} - set(unverified))
        fresh = max([c["at"]] + [o["at"] for o in cited_by.get(cid, []) if counts(o, who)])
        state = ("released" if mine["releases"] else "stopped" if mine["stops"] else activity(fresh, now).lower())
        prs = {n: str(c["cid"]) for n in named(c)}
        for o in cites.get(cid, []):
            for n in named(o):
                prs.setdefault(n, str(o["cid"]))
        cited = sorted(receipts.get(cid, []))
        names_prs = [{"pr": n, "state": "open" if n in by_pr else "closed", "named_in": int(src)}
                     for n, src in sorted(prs.items())]
        out.append({"comment": c["cid"], "session": who, "how": c["how"],
                    "author_guess": c["author_guess"], "author_guess_how": c["author_guess_how"],
                    "addressees": c["addressees"], "at": c["at"], "posted": activity(c["at"], now).lower(),
                    "files": c["files"], "recheck": c["recheck"], "state": state,
                    "session_activity": activity(sessions[who]["last"], now).lower() if who in sessions else None,
                    "released_by": [{"comment": o["cid"], "how": o["how"]} for o in mine["releases"] + mine["stops"]],
                    "partly_released_by": [o["cid"] for o in mine["partial_releases"]],
                    "release_stated_by_another_author": others, "release_by_unverified_author": unverified,
                    "cited_by_receipts": cited, "names_prs": names_prs,
                    "has_pr": bool(cited or names_prs), "units": c["unit_refs"], "heading": c["heading"]})
    return out


def board_naming(parsed: list[dict], rows: list[dict], bound: list[dict], line: str = LINE) -> list[dict]:
    """Claims and handoffs on the board, of any age, whose heading names unit or ask ids and that name an open pull
    request headed for the line and not carried by it: ``{"comment", "ids", "prs"}`` (heuristic)."""
    live = {r["pr"] for r in bound if not r.get("carried")}
    named = _naming(rows, line)
    out = []
    for c in parsed:
        if c["kind"] in ("handoff", *CLAIM_KINDS) and c["heading_units"] and (prs := sorted(named(c) & live)):
            out.append({"comment": c["cid"], "ids": c["heading_units"], "prs": prs})
    return out


def units_of(units: list[dict], rows: list[dict], bound: list[dict], claims: list[dict] | None,
             prs_read: bool, board: list[dict] | None = None) -> list[dict]:
    """Each buildable unit with the line-bound open PRs whose title or receipt names it or one of its asks, the PRs
    carried by the line that name it, the PRs that only mention it, the board claims and handoffs that name it and
    link such a PR, the recent board claims that name it, and the PRs touching its owner paths. Units keep the
    directive's dependency order."""
    ask_unit = {a: u["unit"] for u in units if u["unit"] for a in u["asks"]}

    def of(ids) -> set[str]:
        return {i if UNIT.fullmatch(i) else ask_unit.get(i) for i in ids} - {None}
    for u in units:
        uid = u["unit"]
        naming = [r for r in bound if uid and uid in of(r["names"])]
        live = [r for r in naming if not r.get("carried")]
        u["named_by"] = [{"pr": r["pr"], "session": r["session"], "base": r["base"]} for r in live]
        u["carried_by_line"] = sorted(r["pr"] for r in naming if r.get("carried"))
        u["mentioned_by"] = sorted(r["pr"] for r in rows if uid and r not in naming
                                   and uid in of(r["names"] + r["mentions"]))
        u["named_on_board"] = None if board is None else [
            {"pr": n, "comment": b["comment"]} for b in board if uid and uid in of(b["ids"]) for n in b["prs"]]
        u["claimed_on_board"] = None if claims is None else sorted(
            c["comment"] for c in claims if uid and c["state"] in ("active", "quiet")
            and c["posted"] in ("active", "quiet") and uid in of(c["units"]))
        u["also_touching_its_files"] = sorted({r["pr"] for r in bound if r not in naming and not r.get("carried")
                                               and u["owner_paths"] and any(_covers(f, p) for f in
                                                                            set(r["files"]) | set(r["changed"] or [])
                                                                            for p in u["owner_paths"])})
        u["state"] = ("unknown" if not prs_read else "named" if live else "named on the board"
                      if u["named_on_board"] else "claimed on the board"
                      if u["claimed_on_board"] else "prerequisite, no completion record" if u["prerequisite_only"]
                      else "waits" if u["waits_on"] else "unclaimed")
    return units


def _utcnow() -> datetime:
    """The current time, in UTC. One seam, so tests judge activity against a fixed clock."""
    return datetime.now(timezone.utc)


def build(prs: list[dict] | None, comments: list[dict] | None, *, root: Path = ROOT, line: str = LINE,
          now: datetime | None = None, use_git: bool = True, notes: list[str] | None = None,
          contained=None, carried_by=None, api_read: bool = False) -> dict:
    """The map. ``prs`` or ``comments`` None means that source was not read: what depends on it is None, not zero.
    ``api_read`` says the files API was asked for the PRs into the line (``attach_api_files``), as it is when a PR
    carries a file list from it; otherwise ``api_file_lists`` is None, not zero. ``contained(base)`` and
    ``carried_by(row)`` default to asking git; tests pass them in. Either may answer None (git could not say): such a
    base or PR is listed in the gaps, never counted as off the line or not carried."""
    now = now or _utcnow()
    notes = list(notes or [])
    tracked, git_note = _tracked(root)
    if git_note:
        notes.append(git_note)
    git = use_git and not git_note
    if git and _git_ok("rev-parse", "--verify", "--quiet", f"origin/{line}^{{commit}}", root=root) is not True:
        notes.append(f"origin/{line} is not in this clone (fetch origin): which pull requests are stacked on merged "
                     "parents or carried by the line was not checked")
    known: dict[str, bool | None] = {}

    def asked_git(base: str) -> bool | None:
        if base not in known:
            known[base] = on_line(base, root, line) if git or base in (line, "main") else None
        return known[base]
    given = contained or asked_git
    unchecked: set[str] = set()

    def checked(base: str) -> bool | None:
        """The given answer, with the bases it could not answer kept."""
        answer = given(base)
        if answer is None:
            unchecked.add(base)
        return answer
    carried_by = carried_by or ((lambda r: carried(r, root, line)) if git else (lambda r: None))
    dirs = {"/".join(f.split("/")[:i]) for f in tracked for i in range(1, f.count("/") + 1)}
    pos = position(root)
    prs_read, comments_read = prs is not None, comments is not None
    api_read = api_read or any(isinstance(p, dict) and isinstance(p.get(API_FILES), list) for p in prs or [])
    bad_prs: list = []
    twice_prs: list = []
    rows = pr_rows(prs or [], root, git, bad_prs, line, twice_prs)
    bound = line_bound(rows, line, checked)
    inside = {r["pr"] for r in bound}
    maybe = sorted(r["pr"] for r in line_bound(rows, line, lambda b: True if b in unchecked else checked(b))
                   if r["pr"] not in inside)
    for r in rows:
        r["line_bound"] = r["pr"] in inside
        r["carried"] = carried_by(r) if r["line_bound"] else None

    parsed, bad_comments, twice_comments, ids = [], [], [], set()
    for i, raw in enumerate(comments or []):
        try:
            c = _comment(raw)
            if c is None:
                raise ValueError("not a comment object")
            if c["id"] in ids:
                twice_comments.append(c["id"])
                continue
            ids.add(c["id"])
            parsed.append(parse_comment(c, tracked, dirs))
        except Exception:  # noqa: BLE001 - one unreadable comment never stops the map
            bad_comments.append(_ident(raw, i, "id"))
    join_authors(parsed, rows)
    sessions = sessions_of(rows, parsed, now)
    claims = claims_of(parsed, rows, sessions, now, line)
    units = units_of(pos["directive"].get("units", []) if isinstance(pos["directive"], dict) else [], rows, bound,
                     claims if comments_read else None, prs_read,
                     board_naming(parsed, rows, bound, line) if comments_read else None)

    live = [s for s in sessions.values() if s["activity"] in ("ACTIVE", "QUIET")]
    recent = [c for c in parsed if activity(c["at"], now) in ("ACTIVE", "QUIET")]
    older = [c for c in claims if c["posted"] not in ("active", "quiet") and c["state"] not in ("released", "stopped")
             and not c["cited_by_receipts"]]
    unchecked_prs = sorted(r["pr"] for r in bound if r["carried"] is None)
    both = prs_read and comments_read

    def if_prs(value):
        return value if prs_read else None

    def if_comments(value):
        return value if comments_read else None

    def if_both(value):
        return value if both else None
    return {
        "generated": now.strftime("%Y-%m-%dT%H:%M:%SZ"), "line": line, "authority": "none",
        "sources": {"open_prs": if_prs(len(rows)), "line_bound_prs": if_prs(len(bound)),
                    "board_comments": if_comments(len(parsed)),
                    "git_diffs": if_prs(sum(r["changed_via"] == "diff" for r in rows)) if git_note is None else None,
                    "api_file_lists": if_prs(sum(r["changed_via"] == "api" for r in rows)) if api_read else None,
                    "prs_read": prs_read, "comments_read": comments_read, "git_read": git_note is None,
                    "notes": notes, "note": "; ".join(notes) or None},
        "position": pos, "units": units, "contended": if_prs(contended(rows, line, checked)),
        "sessions": sorted(({**s, "how": sorted(s["how"]), "overlap": sorted(s["overlap"])}
                            for s in sessions.values()), key=lambda s: s["last"], reverse=True),
        "claims_without_pr": if_comments([c for c in claims if c["state"] in ("active", "quiet")
                                          and c["posted"] in ("active", "quiet") and not c["cited_by_receipts"]]),
        "older_claims_without_pr": if_comments({"count": len(older),
                                                "naming_a_pr": sum(bool(c["names_prs"]) for c in older),
                                                "by_live_sessions": sum(c["session_activity"] in ("active", "quiet")
                                                                        for c in older)}),
        "line_checks": _try(lambda: line_checks(rows, root, line, prs_read, bad_prs), root),
        "gaps": {
            "unreadable_prs": if_prs(bad_prs),
            "unreadable_comments": if_comments(bad_comments),
            "duplicate_prs": if_prs(sorted(set(twice_prs))),
            "duplicate_comments": if_comments(sorted(set(twice_comments))),
            "receipts_with_files_cut": if_prs(sorted(r["pr"] for r in rows if r["files_cut"])),
            "prs_on_bases_not_checked": if_prs(maybe),
            "open_prs_without_receipt": if_prs(sorted(r["pr"] for r in rows
                                                      if not r["receipt"] and not r["older_receipt"])),
            "open_prs_with_older_receipt": if_prs(sorted(r["pr"] for r in rows if r["older_receipt"])),
            "open_prs_without_receipt_into_line": if_prs(sorted(r["pr"] for r in rows
                                                                if not r["receipt"] and r["base"] == line)),
            "receipts_with_unreadable_fields": if_prs(sorted(r["pr"] for r in rows if r["receipt_problems"])),
            "receipts_refused_for_files": if_prs(sorted(r["pr"] for r in rows if r["files_refused"])),
            "receipts_with_refused_session": if_prs(sorted(r["pr"] for r in rows if r.get("session_refused"))),
            "receipts_naming_no_session": if_prs(sorted(r["pr"] for r in rows if r.get("session_unnamed"))),
            "receipts_with_stale_head": if_prs(sorted(r["pr"] for r in rows if r.get("receipt_head_stale"))),
            "line_bound_prs_without_diff": if_prs(sorted(r["pr"] for r in bound if r["changed"] is None)),
            "line_bound_prs_carried_by_line": if_prs(sorted(r["pr"] for r in bound if r["carried"])),
            "line_bound_prs_not_checked_against_line": if_prs(unchecked_prs),
            "claims_without_readable_files": if_comments(sorted(c["cid"] for c in parsed
                                                                if c["kind"] in CLAIM_KINDS and not c["files"])),
            "recent_posts_unresolved": if_comments([{"comment": c["cid"], "at": c["at"], "heading": c["heading"],
                                                     "team": c["team"], "author_guess": c["author_guess"],
                                                     "author_guess_how": c["author_guess_how"],
                                                     "opens_with_marker": c["is_checkin"],
                                                     "reason": c["checkin_reason"], "names": c["checkin_names"]}
                                                    for c in recent if not c["author"]]),
            "recent_posts": if_comments(len(recent)),
            "live_sessions": if_both(len(live)),
            "live_sessions_stating_prompt": if_both(sum(bool(s["prompt"]) for s in live)),
            "live_sessions_stating_plan": if_both(sum(bool(s["plan"]) for s in live)),
            "live_sessions_stating_route": if_both(sum(bool(s["route"]) for s in live)),
            "live_sessions_with_checkin_block": if_both(sum(s["checkin_block"] for s in live)),
        },
        "prs": rows, "claims": if_comments(claims),
    }


# ------------------------------------------------------------------ rendering

# Control characters and invisible format characters (bidirectional overrides, zero-width marks) become spaces.
_CONTROL = re.compile(r"[\x00-\x1f\x7f-\x9f\u00ad\u061c\u180e\u200b-\u200f\u2028-\u202e\u2060-\u206f"
                      r"\ufeff\ufff9-\ufffb]")


def _cell(text, limit: int = 150) -> str:
    """Text for one table cell: control characters as spaces, cut to ``limit`` with a marker, then backslash and
    pipe escaped."""
    text = _CONTROL.sub(" ", "" if text is None else str(text))
    if len(text) > limit:
        text = text[:limit - 1] + "…"
    return text.replace("\\", "\\\\").replace("|", "\\|")


def _untrusted(text, limit: int = 150) -> str:
    """Text from a pull request or a board comment: ``_cell`` with backticks as quotes, inside a code span, so nothing
    in it can start a heading, a table row, a link, a mention, an issue reference or HTML. Empty text stays empty."""
    text = _cell(("" if text is None else str(text)).replace("`", "'"), limit)
    return f"`{text}`" if text.strip() else ""


def _more(shown: int, total: int) -> str:
    """The marker for a list cut to ``shown`` of ``total`` items."""
    return f" +{total - shown}" if total > shown else ""


def _prs(numbers: list[int], top: int) -> str:
    return ", ".join("#%d" % n for n in numbers[:top]) + _more(min(top, len(numbers)), len(numbers))


def _not_read(m: dict) -> list[str]:
    """Every source that was not read, for the header."""
    pos, src = m["position"], m["sources"]
    note = src.get("note") or ""
    out = list(src.get("notes") or [])
    if not src["prs_read"] and "pull request" not in note:
        out.append("pull requests (no --github or --prs-json given)")
    if not src["comments_read"] and "comment" not in note:
        out.append("board comments (no --github or --comments-json given)")
    out += [f"{name} ({pos[key]['not_run']})" for key, name in (("route", "route"), ("directive", "directive"),
                                                               ("foundry", "Foundry obligations"), ("mind", "Mind"))
            if isinstance(pos.get(key), dict) and "not_run" in pos[key]]
    return out


def _who(c: dict) -> str:
    """A claim's session cell: its check-in's session, else "not verified" (a guess is never shown as a name)."""
    return _untrusted(c["session"]) if c["session"] else "not verified"


def _named_prs(c: dict) -> str:
    return ", ".join(f"#{p['pr']} ({p['state']})" for p in c["names_prs"][:4]) + _more(min(4, len(c["names_prs"])),
                                                                                       len(c["names_prs"]))


def markdown(m: dict) -> str:
    pos, g, src = m["position"], m["gaps"], m["sources"]
    route, dire = pos["route"], pos["directive"]
    maybe = g["prs_on_bases_not_checked"] or []
    diffs = (f"{src['git_diffs']} of them with their commits in this clone" if src["git_diffs"] is not None
             else "their commits not read from git")
    lists = (f", {src['api_file_lists']} with file lists read from the GitHub API" if src["api_file_lists"] is not None
             else "; their file lists not read from the GitHub API (only --github without --prs-json reads them)")
    read = [f"{src['open_prs']} open pull requests ({src['line_bound_prs']} based on the line directly, through open "
            f"PRs or through a branch already on it"
            + (f"; {len(maybe)} more may be stacked on bases git could not check here, {_prs(maybe, 12)}: fetch origin"
               if maybe else "") + "), " + diffs + lists
            if src["prs_read"] else "pull requests not read",
            f"{src['board_comments']} board comments" if src["comments_read"] else "board comments not read"]
    out = [
        "# Work map", "",
        f"Generated by `scripts/work_map.py` at {m['generated']} against {_untrusted(m['line'])}. A snapshot, not a "
        "lock, and no authority. Receipts are read as declared and not re-validated here. File lists come from "
        "`git diff origin/<base>...<head>` (for a PR not based on the line, only the files that also differ from the "
        "line and that one of its own commits touches) for the PRs whose commits are in this clone, from the GitHub "
        "API for the open PRs into the line that this clone cannot diff (with `--github`), and from the receipt "
        "otherwise. The board shares one GitHub login, so sessions and holders come only from receipts and from "
        "check-in blocks: a comment that opens with the check-in marker and whose block's own `Session:` line names "
        "an id. Anything else a comment seems to say about its author (a byline, another label, its opening line, a "
        "claim or PR it points to) is kept in the JSON as `author_guess` for diagnosis and never used, because on "
        "replay the parser named wrong authors and left over a quarter of a week's posts unresolved, the stop "
        "condition for building the map from receipts only. A claim whose author is not verified still holds its "
        "files. Text from "
        "pull requests and comments is shown as code. What could not be verified is counted under Gaps and listed in "
        "the JSON output. Regenerate it; do not hand-edit it.", "",
        f"Sources: {'; '.join(read)}.", "",
    ]
    missing = _not_read(m)
    if missing:
        out += ["**Not read:** " + "; ".join(_untrusted(x, 200) for x in missing) + ". What depends on them says "
                "*not read* below; nothing there is a zero.", ""]
    out += ["## 1. Position", ""]
    if "not_run" in route:
        out += [f"Route: not read ({_cell(route['not_run'])}).", "", "| | |", "|---|---|"]
    else:
        node = route["acceptance_node"] or {}
        out += [f"**Destination ({_cell(route['boundary'])}).** {_cell(route['destination'], 2000)}", "",
                "| | |", "|---|---|",
                f"| Attested as achieved in `greg/path.json` | {_cell(', '.join(route['achieved'])) or 'none'} |",
                f"| Acceptance node | `{_cell(node.get('id'))}`: {_cell(node.get('title'))}. Its exit needs "
                "founder-tier evidence; nothing here measures it |",
                f"| Does it block building? | No. {_cell(route['founder_use_gate'])} |"]
    out += [f"| Engineering target | {ENGINEERING_TARGET}. A declared target, not a measured result |"]
    if "not_run" in dire:
        out += [f"| Directive | not read ({_cell(dire['not_run'])}) |"]
    else:
        s = dire["summary"]
        out += [f"| Directive ({s['sections']} sections) | {_cell(dire['line'], 600)}; open asks only the founder can "
                f"close: {s['open_by_blocker'].get('FOUNDER_ONLY', 0)}; external: "
                f"{s['open_by_blocker'].get('EXTERNAL', 0)} |"]
    f, mind = pos["foundry"], pos["mind"]
    out += [f"| Foundry obligations | {_cell(f.get('complete', 'not read'))} complete (bounded local evidence) |",
            "| Mind mechanisms | " + (_cell(", ".join(f"{k} {v}" for k, v in mind.items())) if "not_run" not in mind
                                      else "not read") + " |"]
    intents = pos["latest_intents"]
    if isinstance(intents, list) and intents:
        out += ["", "Latest founder intent records on this tree (a newer one may be pending in an open PR):", ""]
        out += [f"- `{_cell(i['id'])}` ({_cell(i['state'])}): {_cell(i['title'])}" for i in intents]

    out += ["", "## 2. Next eligible work, in dependency order", ""]
    if "not_run" in dire:
        out += [f"Not read: the directive was not read ({_cell(dire['not_run'])}), so no unit is listed."]
    else:
        out += ["Units come from `acceptance/directive-sections.json`, in its dependency order. *Named* means an open "
                "pull request headed for the line has the unit id or one of its ask ids in its title or receipt "
                "(scope, intent_refs); the PR may be old, so check it. A PR whose commits are all on the line is "
                "listed as *carried* and names nothing. *Named on the board* means a claim or handoff of any age "
                "names the unit or one of its asks in its heading and links such a pull request (heuristic). *Claimed "
                "on the board* means a claim posted in the last 7 days names the unit or its asks (heuristic). "
                "*Unclaimed* means none of these: read the newest board comments before you take it."
                + ("" if src["prs_read"] else " Pull requests were not read, so every state is *unknown*.")
                + (f" Git could not check {len(g['line_bound_prs_not_checked_against_line'])} of the PRs headed for the "
                   "line against it (section 5), so a unit they name may already be carried."
                   if src["prs_read"] and g["line_bound_prs_not_checked_against_line"] else ""), "",
                "| Unit | What it builds | Closes | Evidence: now -> required | State | Open PRs naming it "
                "| Also touching its files |", "|---|---|---|---|---|---|---|"]
        for u in m["units"]:
            naming = ", ".join(f"#{o['pr']}" for o in u["named_by"])
            if u["carried_by_line"]:
                naming += ("; " if naming else "") + "carried: " + _prs(u["carried_by_line"], 6)
            state = u["state"] + (f" ({', '.join(map(str, u['claimed_on_board'][:3]))})"
                                  if u["state"] == "claimed on the board" else "")
            state += "".join(f" → #{b['pr']} (comment {b['comment']})" for b in u["named_on_board"][:3]
                             ) if u["state"] == "named on the board" else ""
            state += f" (waits on {', '.join(u['waits_on'])})" if u["waits_on"] else ""
            closes = ", ".join(u["asks"][:4]) + _more(min(4, len(u["asks"])), len(u["asks"]))
            out.append(f"| `{_cell(u['unit'] or '-')}` | {_cell(u['title'])} | {_cell(closes) or 'prerequisite'} | "
                       f"{_cell('; '.join(u['evidence']))} | {_cell(state)} | {naming} | "
                       f"{_prs(u['also_touching_its_files'], 6)} |")
        mentioned = sum(bool(u.get("mentioned_by")) for u in m["units"])
        if mentioned:
            out += ["", f"{mentioned} units are also mentioned by pull requests that do not name them (not headed for "
                    "the line, or named only in the body): `mentioned_by` in the JSON."]

    out += ["", "## 3. Before you edit: contended files", ""]
    if m["contended"] is None:
        out += ["Not read: pull requests were not read."]
    else:
        bare = g["line_bound_prs_without_diff"]
        out += ["Paths that two or more session ids declare in a receipt or change against their PR base (own changes "
                "only), among PRs headed for the line. A declared directory or glob covers the paths under it. A PR "
                "with no receipt counts as its own session id; a PR carried by the line holds nothing; a fix-round "
                "child counts with the parent it is stacked on. The integration PR and composed candidates are left "
                "out." + ("" if src["git_read"] else " Git was not read: declared files only"
                          + (", and file lists read from the GitHub API." if src["api_file_lists"] else ".")), "",
                f"{len(bare)} of {src['line_bound_prs']} PRs headed for the line have neither a local diff nor a file "
                "list from the GitHub API"
                + (f" ({_prs(bare, 30)}); their file lists rest on the receipt alone: fetch their heads." if bare
                   else "."), "",
                "| File | Session ids (a PR with no receipt counts as one) | Pull requests |", "|---|---:|---|"]
        out += [f"| {_untrusted(c['file'])} | {c['sessions']} | {_prs(c['prs'], 14)} |" for c in m["contended"][:40]]
        if len(m["contended"]) > 40:
            out.append(f"| ... | | {len(m['contended']) - 40} more: run with `--json` |")

    out += ["", "## 4. Active sessions", ""]
    if not (src["prs_read"] or src["comments_read"]):
        out += ["Not read: neither pull requests nor board comments were read."]
    else:
        if not (src["prs_read"] and src["comments_read"]):
            out += [("Board comments" if src["prs_read"] else "Pull requests") + " were not read: this table is "
                    "partial.", ""]
        out += ["| Session | Client | Resolved by | Last update seen (PR updated_at or check-in) | Asked to | "
                "Plan | Route | Open PRs | Overlap declared |", "|---|---|---|---|---|---|---|---|---|"]
        for s in m["sessions"]:
            if s["activity"] == "DORMANT":
                continue
            how = _cell(", ".join(s["how"])) + "".join(f"; #{t['pr']} task_ref cites comment {t['comment']} by "
                                                       f"{_untrusted(t['author'], 40)}" for t in s["task_refs"][:2])
            out.append(f"| {_untrusted(s['session'])} | {_cell(s['client'])} | {how} | "
                       f"{s['activity']} {_cell(s['last'][:16])} | "
                       f"{_untrusted(s['prompt'])} | {_untrusted(s['plan'])} | "
                       f"{_untrusted(s['route'] or '')} | {_prs(sorted(s['prs']), 12)} | "
                       f"{', '.join(_untrusted(o, 40) for o in s['overlap'])} |")
        dormant = sum(s["activity"] == "DORMANT" for s in m["sessions"])
        out += ["", f"{dormant} dormant sessions (no update seen for 7 days) are in the JSON output. Only receipts "
                "and check-in blocks name a session here."]

    out += ["", "## 5. Gaps: documented is not demonstrated", ""]
    if src["prs_read"]:
        out += [f"- Open pull requests without a receipt: {len(g['open_prs_without_receipt'])} "
                f"({len(g['open_prs_without_receipt_into_line'])} of them into the line); with an older (version-1) "
                f"receipt: {len(g['open_prs_with_older_receipt'])}; receipts with fields of the wrong type: "
                f"{len(g['receipts_with_unreadable_fields'])}; receipts the receipt check refuses for their "
                f"coordination or files: {len(g['receipts_refused_for_files'])}; receipts naming no session because "
                f"the receipt check refuses their session_id or they come from a fork: "
                f"{len(g['receipts_with_refused_session'])}; receipts the check accepts that name no session (their "
                f"session_id names more than one id or an id it does not open with): "
                f"{len(g['receipts_naming_no_session'])}; receipts written for another head than the PR's (normal "
                f"for minutes after a push): {len(g['receipts_with_stale_head'])}"
                + (f"; receipts listing more than {FILES_LIMIT} files, the rest not read: "
                   f"{_prs(g['receipts_with_files_cut'], 12)}" if g["receipts_with_files_cut"] else "") + ".",
                _carried_line(m),
                f"- Unreadable pull requests: {len(g['unreadable_prs'])}"
                + (f" ({_cell(', '.join(map(str, g['unreadable_prs'][:12])))}{_more(12, len(g['unreadable_prs']))})"
                   if g["unreadable_prs"] else "") + "."]
        if g["duplicate_prs"]:
            out += [f"- Pull requests given more than once, read once from the newest copy: "
                    f"{_prs(g['duplicate_prs'], 12)}."]
    else:
        out += ["- Pull requests and their receipts: not read."]
    if src["prs_read"] and src["comments_read"]:
        out += [f"- Sessions with an update seen in the last 7 days: {g['live_sessions']}. With a comment carrying a "
                f"Prompt/Request/Task label: {g['live_sessions_stating_prompt']}; a Plan/Approach/Method label: "
                f"{g['live_sessions_stating_plan']}; a route node or unit: {g['live_sessions_stating_route']}; "
                f"the check-in block: {g['live_sessions_with_checkin_block']}."]
    else:
        out += ["- Sessions active in the last 7 days: not read (it needs both pull requests and board comments)."]
    if src["comments_read"]:
        unread = g["claims_without_readable_files"]
        marked = sum(u["opens_with_marker"] for u in g["recent_posts_unresolved"])
        reasons: dict[str, int] = {}
        for u in g["recent_posts_unresolved"]:
            if u.get("reason"):
                reasons[u["reason"]] = reasons.get(u["reason"], 0) + 1
        out += [f"- Board posts in the last 7 days with no check-in block of their own (the marker alone on the first "
                f"line, then the block's own Session line first), so they name no verified author: "
                f"{len(g['recent_posts_unresolved'])} of {g['recent_posts']}; {marked} of them "
                f"open{'s' if marked == 1 else ''} with the check-in marker"
                + (" (" + "; ".join(f"{_cell(why)}: {n}" for why, n in sorted(reasons.items(), key=lambda x: -x[1]))
                   + "; `reason` and `names` in the JSON)" if reasons else "") + ".",
                f"- Claims whose file list could not be read: {len(unread)}"
                + (f" ({_cell(', '.join(map(str, unread[-12:])))}{_more(12, len(unread))})" if unread else "") + ".",
                f"- Unreadable board comments: {len(g['unreadable_comments'])}"
                + (f" ({_cell(', '.join(map(str, g['unreadable_comments'][:12])))}"
                   f"{_more(12, len(g['unreadable_comments']))})" if g["unreadable_comments"] else "") + "."]
        if g["duplicate_comments"]:
            out += [f"- Board comments given more than once, read once: {len(g['duplicate_comments'])}."]
    else:
        out += ["- Board posts: not read."]
    out += [_checks_line(m), ""]
    if not src["comments_read"]:
        out += ["Claims that no open pull request's receipt cites: not read (board comments were not read)."]
    else:
        shown = m["claims_without_pr"][-25:]
        out += ["Claims that no open pull request's receipt cites (posted in the last 7 days, not released"
                + (f"; the newest {len(shown)} of {len(m['claims_without_pr'])}" if len(m["claims_without_pr"]) > 25
                   else "") + "):", "",
                "| Comment | Session | Resolved by | Posted | Files declared | Recheck | State | Pull request named |",
                "|---|---|---|---|---|---|---|---|"]
        out += [f"| {c['comment']} | {_who(c)} | {_cell(c['how'])} | "
                f"{_cell(c['at'][:16])} | {', '.join(_untrusted(x, 80) for x in c['files'][:6])}"
                f"{_more(min(6, len(c['files'])), len(c['files']))} | {_cell(c['recheck'] or 'event-based')} | "
                f"{_cell(c['state'] + (' (part released)' if c['partly_released_by'] else ''))} | {_named_prs(c)} |"
                for c in shown]
        older = m["older_claims_without_pr"]
        out += ["", f"{older['count']} claims posted more than 7 days ago that no open pull request's receipt cites "
                f"and that were not released ({older['naming_a_pr']} of them name a pull request; "
                f"{older['by_live_sessions']} are by sessions with an update in the last 7 days) are in the JSON "
                "output. An old claim is still not permission to overwrite."]

    drift = pos["route_drift"]
    out += ["", "## 6. Route drift", ""]
    if not isinstance(drift, dict) or "not_run" in drift:
        out += ["Not read."]
    elif not drift.get("section"):
        out += ["This tree has no current-route section in `docs/BACKCAST_GPS.md` to compare with `greg/path.json`."]
    elif drift["missing"]:
        out += [f"`docs/BACKCAST_GPS.md` does not name these nodes of `greg/path.json`: "
                f"{_cell(', '.join(drift['missing']), 600)}."]
    else:
        out += ["None: the route table in `docs/BACKCAST_GPS.md` names every node of `greg/path.json`."]

    out += ["", "## The check-in", "",
            "Post this on the work board before any edit, commit or push, and again when you resume. When the pull "
            "request exists, give this comment's URL as its receipt's `coordination.task_ref`:", "",
            "```text", CHECKIN_BLOCK, "```", "",
            "The map names your session only when the marker is alone on the comment's first line and your own "
            "`Session:` line, naming one id, comes first after the heading. Post a check-in block only for your own "
            "session: a block that opens with the marker names the session on its Session line whoever posts it. To "
            "pass a block to another session, leave out the marker line. A post whose text relays, whose heading "
            "hands over, reassigns or reviews, or whose heading or poster label names another id names nobody, even "
            "your own: release your own claim under a heading such as `## Release: claim N`.", ""]
    return "\n".join(out)


def _carried_line(m: dict) -> str:
    """How many PRs headed for the line are carried by it, out of those git could check; never a zero for the rest."""
    g, head = m["gaps"], "- PRs headed for the line whose commits are all on it already (carried): "
    unknown, done = g["line_bound_prs_not_checked_against_line"], g["line_bound_prs_carried_by_line"]
    if not unknown:
        return head + f"{len(done)}."
    checked = m["sources"]["line_bound_prs"] - len(unknown)
    return (head + (f"{len(done)} of the {checked} git could check; " if checked else "")
            + f"not checked: {len(unknown)} ({_prs(unknown, 12)}), their commits are not in this clone or git was "
            "not read.")


def _checks_line(m: dict) -> str:
    c = m.get("line_checks") or {}
    if "not_run" in c:
        return "- Checks on pushes to the line: not read."
    if c["push_covers_line"]:
        return "- Checks on pushes to the line: Canonical CI runs on push to the line."
    push = ("`canonical-ci.yml` runs on push to it only when the pushed files match its paths filter"
            if "paths" in c["push_filter"] else "`canonical-ci.yml` does not run on push to it")
    if not m["sources"]["prs_read"]:
        return f"- Checks on pushes to the line: {push}; whether an open pull request runs them was not read."
    if c["covered"] is None:
        bad = m["gaps"]["unreadable_prs"] or []
        return (f"- Checks on pushes to the line: unknown. {len(bad)} open pull requests could not be read "
                f"({_cell(', '.join(map(str, bad[:12])))}{_more(12, len(bad))}), and one of them may have the line as "
                f"its head; {push}.")
    if not c["covered"]:
        return ("- Checks on pushes to the line: **none**. No open pull request from this repository has the line as "
                f"its head, and {push}.")
    prs = ", ".join("#%d" % n for n in c["pull_requests_with_line_as_head"])
    return (f"- Checks on pushes to the line: only through the pull-request runs of {prs} (its head is the line). "
            "If it closes, pushes to the line run no Canonical CI.")


# ------------------------------------------------------------------ input and output

def _load(paths: list[Path] | None, kind: str, key: str) -> tuple[list | None, list[str]]:
    """Saved API responses: the items of every file, or None with notes when a file is missing, broken or not a list.
    A file holding one object with ``key`` counts as that one item. Items that are not objects are passed on, and
    the map reports them as unreadable."""
    if not paths:
        return None, []
    out: list = []
    notes = []
    for p in paths:
        try:
            data = json.loads(Path(p).read_text(encoding="utf-8"), parse_constant=lambda _name: None)
        except (OSError, ValueError, RecursionError) as exc:
            notes.append(f"{kind} file {Path(p).name} not read ({_reason(exc)})")
            continue
        if isinstance(data, dict) and key in data:
            data = [data]
        if not isinstance(data, list):
            notes.append(f"{kind} file {Path(p).name} not read (not a list of {kind}s)")
            continue
        out += data
    return (None if notes else out), notes


def _descriptor(path: Path) -> int | None:
    """The descriptor of this process that ``path`` names, when it is or links to one (``/dev/stdout``, ``/dev/fd/1``,
    ``/proc/self/fd/1``, or a link to any of them); else None. Such a path resolves to whatever the descriptor has open,
    so it is written through the descriptor, never renamed over."""
    fds = re.compile(rf"/dev/fd|/proc/{os.getpid()}(?:/task/\d+)?/fd")
    p = Path(os.path.abspath(path))
    for _hop in range(40):
        if p.name.isdigit() and fds.fullmatch(os.path.realpath(p.parent)):
            return int(p.name)
        if not p.is_symlink():
            return None
        p = Path(os.path.normpath(p.parent / os.readlink(p)))
    return None


def _write(path: Path, text: str) -> str | None:
    """Write ``text`` in UTF-8 with unencodable characters escaped. A new or regular file, or the regular file a
    symbolic link points to, is written through a temporary file beside it and an atomic rename, so a failed write
    leaves it as it was and the link stays a link. A descriptor of this process (``/dev/stdout``, also when it is
    redirected to a file) is written through that descriptor, so a file opened for append keeps what it held and
    what is printed later follows; anything else (a pipe, a device) is written through as it is. Returns why it
    failed, or None."""
    path, tmp = Path(path), None
    asked = path.name
    try:
        fd = _descriptor(path)
        if fd is not None:
            for stream in (sys.stdout, sys.stderr):
                stream.flush()
            with open(os.dup(fd), "w", encoding="utf-8", errors="backslashreplace", newline="\n") as fh:
                fh.write(text)
            return None
        if path.is_symlink() or (path.exists() and not path.is_file()):
            target = Path(os.path.realpath(path))
            if not (target.is_file() and not target.is_symlink()):
                with open(path, "w", encoding="utf-8", errors="backslashreplace", newline="\n") as fh:
                    fh.write(text)
                return None
            path = target
        fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
        with os.fdopen(fd, "w", encoding="utf-8", errors="backslashreplace", newline="\n") as fh:
            fh.write(text)
        os.chmod(tmp, path.stat().st_mode & 0o777 if path.is_file() else 0o644)
        os.replace(tmp, path)
        return None
    except (OSError, ValueError, RuntimeError) as exc:
        if tmp:
            try:
                os.unlink(tmp)
            except OSError:
                pass
        return f"{asked} not written ({_reason(exc)})"


def _answer_sources(m: dict) -> dict:
    """What a ``--paths`` or ``--unit`` answer rests on: an empty list means nobody only when its source was read, and
    every pull request the map could not read whole is named here."""
    src, g = m["sources"], m["gaps"]
    unknown = sorted(r["pr"] for r in m["prs"] if _files_unknown(r))
    return {"pull_requests_read": src["prs_read"], "comments_read": src["comments_read"],
            "git_read": src["git_read"], "api_file_lists": src["api_file_lists"], "note": src["note"],
            "not_read": _not_read(m),
            "unreadable_prs": g["unreadable_prs"], "receipts_with_files_cut": g["receipts_with_files_cut"],
            "receipts_with_unreadable_fields": g["receipts_with_unreadable_fields"],
            "receipts_refused_for_files": g["receipts_refused_for_files"],
            "receipts_with_refused_session": g["receipts_with_refused_session"],
            "receipts_naming_no_session": g["receipts_naming_no_session"],
            "receipts_with_stale_head": g["receipts_with_stale_head"],
            "line_bound_prs_without_diff": g["line_bound_prs_without_diff"],
            "open_prs_without_diff": sorted(r["pr"] for r in m["prs"] if r["changed"] is None)
            if src["prs_read"] else None,
            "files_of_those": "declared in the receipt alone: their diffs were neither in local git nor read from "
                              "the API (a PR stacked on another branch is never read from the API)"
                              + (f"; {', '.join('#%d' % n for n in unknown)} have no receipt, a cut one or one the "
                                 "receipt check refuses for its coordination or its files, so a path lists them under "
                                 "unknown_prs" if unknown else "")}


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="backslashreplace")
        except (AttributeError, ValueError, OSError):
            pass
    ap = argparse.ArgumentParser(description=(__doc__ or "Work map.").strip().splitlines()[0])   # -OO drops __doc__
    ap.add_argument("--github", metavar="OWNER/REPO")
    ap.add_argument("--board", type=int, default=96)
    ap.add_argument("--prs-json", type=Path, action="append")
    ap.add_argument("--comments-json", type=Path, action="append")
    ap.add_argument("--line", default=LINE)
    ap.add_argument("--now", help="UTC time to judge activity against: YYYY-MM-DDTHH:MM:SSZ or ISO with an offset")
    ap.add_argument("--markdown", type=Path)
    ap.add_argument("--json", type=Path)
    ap.add_argument("--paths", nargs="*", metavar="FILE",
                    help="who touches these files? Repository-relative paths (a path in any worktree of this "
                         "repository, nested under this checkout or not, is made relative to that worktree); none "
                         "still gets an answer")
    ap.add_argument("--unit", help="is this unit taken?")
    a = ap.parse_args(argv)          # a malformed command line is a usage error: argparse exits 2
    try:
        prs, notes = _load(a.prs_json, "pull request", "number")
        comments, more = _load(a.comments_json, "comment", "id")
        notes += more
        token = os.environ.get("GITHUB_TOKEN")
        api_read = False
        if a.github and not a.prs_json:
            try:
                prs = branch_catalog.pull_requests(a.github, token)
            except Exception as exc:  # noqa: BLE001 - the map still prints what it can
                notes.append(f"GitHub pull requests not read ({_reason(exc)})")
            api_read = prs is not None                   # the files API is asked for every PR read here
            if prs:
                read, failed = attach_api_files(a.github, prs, token, a.line)
                if failed:
                    notes.append(f"changed files of {len(failed)} open pull requests into the line not read from the "
                                 f"API: {', '.join('#%d' % n for n in failed[:20])}{_more(min(20, len(failed)), len(failed))}")
        if a.github and not a.comments_json:
            try:
                comments = issue_comments(a.github, a.board, token)
            except Exception as exc:  # noqa: BLE001
                notes.append(f"GitHub comments not read ({_reason(exc)})")
        now = parse_now(a.now) if a.now else None
        if a.now and now is None:
            notes.append(f"--now {a.now[:40]!r} not understood (YYYY-MM-DDTHH:MM:SSZ or ISO with an offset); "
                         "the current time is used")
        m = build(prs, comments, line=a.line, now=now, notes=notes, api_read=api_read)
        outputs = [(a.json, lambda: json.dumps(m, indent=1, default=sorted, allow_nan=False) + "\n"),
                   (a.markdown, lambda: markdown(m) + "\n")]
        failed = [_write(path, render()) for path, render in outputs if path]
        if a.paths is not None:
            tracked, _ = _tracked(ROOT)
            print(json.dumps({"sources": _answer_sources(m), "paths": who_touches(
                a.paths, m["prs"] if m["sources"]["prs_read"] else None, m["claims"], tracked, a.line,
                m["gaps"]["unreadable_prs"]),
                "checkin": CHECKIN_BLOCK}, indent=1))
        elif a.unit:
            rows = [u for u in m["units"] if u["unit"] == a.unit]
            known = "not_run" not in m["position"]["directive"]
            answer = {"rows": rows} if rows else {"answer": "no such unit" if known else "units not read"}
            print(json.dumps({"sources": _answer_sources(m), "unit": a.unit, **answer, "checkin": CHECKIN_BLOCK},
                             indent=1))
        elif not (a.json or a.markdown):
            print(markdown(m))
        for line in [*m["sources"]["notes"], *failed]:
            if line:
                print(line, file=sys.stderr)
    except Exception as exc:  # noqa: BLE001 - never a gate: report and exit 0
        print(f"work map not built ({_reason(exc)})", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
