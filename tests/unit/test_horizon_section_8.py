"""Directive 2026-10-28 section 8: a distant capability keeps how it could become feasible and how it could fail.

"For distant capabilities preserve: intended effect; dependency chain; nearest achievable precursor; enabling
interfaces; evidence required; conditions that would make it feasible; conditions that would falsify it." Every
horizon on greg/path.json whose feasibility is not CURRENTLY_BUILDABLE carries ``enabling_interfaces``,
``feasible_when`` and ``falsified_by``. Each is recorded where the path, an intent record, the directive or the
repository already says it (``recorded_as`` a path field, or a ``value`` copied verbatim with its ``source``), or
it is ``{"unrecorded": "<reason>"}``: the gap is named, never filled with invented text, and ``greg path`` reports
it. The build frontier (#236) and the founder's path are untouched.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path
import re

import pytest

from greg import path

ROOT = Path(__file__).resolve().parents[2]
DIRECTIVE = ROOT / "docs/intent/sources/OPUS-MAXIMUS-MASTER-BUILD-DIRECTIVE-2026-10-28-source.md"


def raw() -> dict:
    return json.loads((ROOT / "greg/path.json").read_text())


def distant(data: dict) -> list[dict]:
    return [h for h in data["horizons"] if h["feasibility"] != "CURRENTLY_BUILDABLE"]


def whole(value: str, text: str) -> bool:
    """``value`` is a whole unit of ``text``: a line, a bullet item or a quoted string, not a cut fragment of one."""
    return re.search(r'(?:^|(?<=[\n"])|(?<=\* ))' + re.escape(value) + r'(?=["\n;.]|$)', text) is not None


def entries(field_value) -> list[dict]:
    return field_value if isinstance(field_value, list) else [field_value]


def test_the_three_fields_are_section_8s_own_words():
    lines = DIRECTIVE.read_text(encoding="utf-8").splitlines()
    start = lines.index("8. AMBITION IS NOT A REJECTION CRITERION")
    section = lines[start:lines.index("9. DO NOT LITERALIZE BIOLOGY", start)]
    items = [line[2:].rstrip(";.") for line in section if line.startswith("* ")]
    for words in ("enabling interfaces", "conditions that would make it feasible", "conditions that would falsify it"):
        assert words in items, words
    assert path.SECTION_8_FIELDS == ("enabling_interfaces", "feasible_when", "falsified_by")


def test_every_horizon_not_currently_buildable_carries_section_8():
    data = path.load()
    horizons = distant(data)
    assert len(horizons) >= 31
    for horizon in horizons:
        for field in path.SECTION_8_FIELDS:
            assert field in horizon, (horizon["id"], field)
            assert path.section_8_problem(data, horizon, field) is None, (horizon["id"], field)


def test_every_copied_value_is_verbatim_in_its_source():
    """A ``value`` must be found, item by item, in the text it cites; nothing is paraphrased into the path."""
    data = path.load()
    checked = 0
    for horizon in data["horizons"]:
        for field in path.SECTION_8_FIELDS:
            for entry in entries(horizon.get(field, [])):
                if "value" not in entry:
                    continue
                values = entry["value"] if isinstance(entry["value"], list) else [entry["value"]]
                sources = entry["source"] if isinstance(entry["source"], list) else [entry["source"]]
                texts = []
                for source in sources:
                    if source.startswith(path.PATH_SOURCE):
                        texts.append(path.resolve_text(data, horizon, source[len(path.PATH_SOURCE):]))
                    else:
                        file = ROOT / source.partition("#")[0]
                        assert file.is_file(), (horizon["id"], field, source)
                        texts.append(file.read_text(encoding="utf-8"))
                for value in values:
                    if all(s.startswith(path.PATH_SOURCE) for s in sources):
                        found = any(value in text for text in texts if text)      # an interface named in a field
                    else:                                       # a whole line, bullet item or quoted string, uncut
                        found = any(whole(value, text) for text in texts)
                    assert found, (horizon["id"], field, value)
                    checked += 1
    assert checked > 0


def test_the_section_8_gap_is_reported_on_greg_path():
    data = path.load()
    where = path.position(None, data)
    report = where["horizons"]["section_8_unrecorded"]
    for field in path.SECTION_8_FIELDS:
        expected = sorted(h["id"] for h in data["horizons"]
                          if isinstance(h.get(field), dict) and set(h[field]) == {"unrecorded"})
        assert report[field] == expected, field
    assert report["falsified_by"], "a horizon with no recorded falsifier must be visible"


def _first_distant(data: dict) -> dict:
    return distant(data)[0]


@pytest.mark.parametrize("field", ["enabling_interfaces", "feasible_when", "falsified_by"])
def test_a_distant_horizon_missing_a_section_8_field_fails_validate(field):
    data = raw()
    path.validate(copy.deepcopy(data))
    horizon = _first_distant(data)
    horizon.pop(field)
    with pytest.raises(path.PathError, match=f"{field} missing"):
        path.validate(data)


@pytest.mark.parametrize("value, needle", [
    pytest.param({"unrecorded": ""}, "unrecorded needs a reason", id="unrecorded without a reason"),
    pytest.param({"unrecorded": "x", "value": "y"}, "one of", id="two forms at once"),
    pytest.param({}, "one of", id="empty object"),
    pytest.param("", "one of", id="empty text"),
    pytest.param([], "one of", id="empty list"),
    pytest.param({"recorded_as": "nowhere"}, "names no field", id="pointer to nothing"),
    pytest.param({"recorded_as": "falsified_by"}, "names no field", id="pointer to a section 8 field"),
    pytest.param({"recorded_as": "id"}, "names no field", id="pointer to unrelated text"),
    pytest.param({"recorded_as": "workstreams/cognition_cortex/nodes/P99/falsification"}, "does not resolve",
                 id="pointer to no node"),
    pytest.param({"recorded_as": "frontier_backcasts/none/nearest_falsifiable_experiment"}, "does not resolve",
                 id="pointer to no backcast"),
    pytest.param({"value": "", "source": "docs/x.md"}, "value", id="empty value"),
    pytest.param({"value": "x", "source": ""}, "source", id="no source"),
    pytest.param({"value": "a condition nobody wrote", "source": "greg/path.json#prerequisite"},
                 "not in its source", id="a value its path source does not contain"),
    pytest.param([{"unrecorded": "x"}, {"recorded_as": "prerequisite"}], "unrecorded stands alone",
                 id="unrecorded inside a list"),
])
def test_validate_refuses_an_invented_or_empty_section_8_entry(value, needle):
    data = raw()
    _first_distant(data)["falsified_by"] = value
    with pytest.raises(path.PathError, match=needle):
        path.validate(data)


def test_a_currently_buildable_horizon_needs_none_but_a_present_field_is_checked():
    data = raw()
    buildable = next(h for h in data["horizons"] if h["feasibility"] == "CURRENTLY_BUILDABLE")
    assert not set(path.SECTION_8_FIELDS) & set(buildable)
    path.validate(data)
    buildable["falsified_by"] = {"unrecorded": ""}
    with pytest.raises(path.PathError, match="unrecorded needs a reason"):
        path.validate(data)


def test_feasibility_and_frontier_are_read_where_the_path_already_records_them():
    """``feasible_when`` points at the horizon's own prerequisite; the frontier backcasts' falsifiable experiments
    are the falsifier of the horizon they belong to, never copied."""
    data = path.load()
    for horizon in distant(data):
        assert horizon["feasible_when"] == {"recorded_as": "prerequisite"}, horizon["id"]
    for backcast in data["frontier_backcasts"]:
        horizon = next(h for h in data["horizons"] if h["id"] == backcast["horizon"])
        refs = [e.get("recorded_as") for e in entries(horizon["falsified_by"])]
        assert f"frontier_backcasts/{backcast['id']}/nearest_falsifiable_experiment" in refs, backcast["id"]
