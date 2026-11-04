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


def cited(source: str) -> str:
    """The text a file source cites: the whole file, or the numbered section its ``#<n>-<heading>`` anchor names
    (the first ``<n>. HEADING`` line up to section n+1), whose heading must match the anchor."""
    name, _, anchor = source.partition("#")
    file = ROOT / name
    assert file.is_file(), source
    text = file.read_text(encoding="utf-8")
    section = re.fullmatch(r"(\d+)-([a-z0-9-]+)", anchor)
    if not section:
        return text
    number, slug = int(section.group(1)), section.group(2)
    lines = text.splitlines()
    start = next(i for i, line in enumerate(lines) if line.startswith(f"{number}. "))
    assert re.sub(r"[^a-z0-9]+", "-", lines[start][len(f"{number}. "):].lower()).strip("-") == slug, source
    end = next(i for i in range(start + 1, len(lines)) if lines[i].startswith(f"{number + 1}. "))
    return "\n".join(lines[start:end]) + "\n"


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
    """A ``value`` must be found, item by item, in the text it cites (for a directive anchor, the section it names);
    nothing is paraphrased into the path."""
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
                        texts.append(cited(source))
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
                 "not an uncut phrase or name of its source", id="a value its path source does not contain"),
    pytest.param([{"unrecorded": "x"}, {"recorded_as": "prerequisite"}], "unrecorded stands alone",
                 id="unrecorded inside a list"),
    pytest.param({"unrecorded": "\u200b"}, "unrecorded needs a reason", id="a zero-width reason"),
    pytest.param({"recorded_as": []}, "records nothing", id="an empty pointer list"),
    pytest.param([{"recorded_as": []}], "records nothing", id="an empty pointer list in a list"),
])
def test_validate_refuses_an_invented_or_empty_section_8_entry(value, needle):
    data = raw()
    _first_distant(data)["falsified_by"] = value
    with pytest.raises(path.PathError, match=needle):
        path.validate(data)


ROBOTICS_FALSIFIER = "frontier_backcasts/advanced_robotic_embodiment/nearest_falsifiable_experiment"


@pytest.mark.parametrize("field, value", [
    *[pytest.param(field, value, id=f"{field} {form}") for field in path.SECTION_8_FIELDS
      for form, value in (("object", {"recorded_as": []}), ("list", [{"recorded_as": []}]))],
    pytest.param("falsified_by", [{"recorded_as": ROBOTICS_FALSIFIER}, {"recorded_as": []}],
                 id="falsified_by beside a real pointer"),
])
def test_an_empty_pointer_list_records_nothing(field, value):
    """``{"recorded_as": []}`` names no text; accepting it would also drop the horizon from the gap report."""
    data = raw()
    next(h for h in data["horizons"] if h["id"] == "robotics")[field] = value
    with pytest.raises(path.PathError, match="records nothing"):
        path.validate(data)


@pytest.mark.parametrize("horizon_id, field, value, needle", [
    pytest.param("remote_interface_iphone", "falsified_by", {"recorded_as": ROBOTICS_FALSIFIER},
                 "belongs to horizon 'robotics'", id="another horizon's backcast falsifier"),
    pytest.param("voice", "falsified_by", [{"recorded_as": ROBOTICS_FALSIFIER}], "belongs to horizon 'robotics'",
                 id="another horizon's backcast falsifier in a list"),
    pytest.param("selective_web3_settlement", "falsified_by",
                 {"recorded_as": "workstreams/cognition_cortex/nodes/P3/falsification"}, "do not name",
                 id="a P-node the horizon never names"),
    pytest.param("voice", "feasible_when", {"recorded_as": "horizons/robotics/prerequisite"},
                 "not this horizon's field", id="another horizon's prerequisite"),
    pytest.param("remote_interface_iphone", "feasible_when",
                 {"recorded_as": "frontier_backcasts/advanced_robotic_embodiment/activation_condition"},
                 "belongs to horizon 'robotics'", id="another horizon's activation condition"),
    pytest.param("voice", "enabling_interfaces",
                 {"value": "a simulated actuator contract", "source": path.PATH_SOURCE + ROBOTICS_FALSIFIER},
                 "belongs to horizon 'robotics'", id="a value copied from another horizon's backcast"),
    pytest.param("remote_interface_iphone", "enabling_interfaces",
                 {"value": "a", "source": "greg/path.json#prerequisite"}, "uncut phrase or name",
                 id="a lone article of the field"),
    pytest.param("remote_interface_iphone", "enabling_interfaces",
                 {"value": "running", "source": "greg/path.json#prerequisite"}, "uncut phrase or name",
                 id="a lone common word of the field"),
    pytest.param("remote_interface_iphone", "enabling_interfaces",
                 {"value": "e", "source": "greg/path.json#prerequisite"}, "uncut phrase or name",
                 id="a letter cut from a word"),
    pytest.param("remote_interface_iphone", "enabling_interfaces",
                 {"value": "erified HTTPS pat", "source": "greg/path.json#prerequisite"}, "uncut phrase or name",
                 id="a phrase cut mid-word"),
    pytest.param("cognitive_ecology", "enabling_interfaces",
                 {"value": "cortex-receipt.schema.json",
                  "source": "greg/path.json#frontier_backcasts/substrate_adaptive_cognition/current_precursor"},
                 "uncut phrase or name", id="a name cut out of a path"),
    pytest.param("cognitive_ecology", "enabling_interfaces",
                 {"value": "greg/cognition/worker",
                  "source": "greg/path.json#frontier_backcasts/substrate_adaptive_cognition/current_precursor"},
                 "uncut phrase or name", id="a name cut at a dot"),
    pytest.param("voice", "enabling_interfaces",
                 {"value": "an invented interface", "source": ["greg/path.json#prerequisite", "docs/nowhere.md"]},
                 "at once", id="path and file sources mixed"),
])
def test_validate_refuses_text_that_belongs_elsewhere_or_is_cut(horizon_id, field, value, needle):
    """A section 8 entry is the horizon's own recorded text: its fields, its own frontier backcasts, a P-node its
    prerequisite or activation evidence names. Another horizon's text, or a fragment of a word, fills no gap."""
    data = raw()
    next(h for h in data["horizons"] if h["id"] == horizon_id)[field] = value
    with pytest.raises(path.PathError, match=needle):
        path.validate(data)


def test_every_pointer_and_path_value_on_the_path_is_the_horizons_own():
    """Every recorded pointer names the horizon's own text, so the present data passes the rule the refusals test."""
    data = path.load()
    nodes = 0
    for horizon in distant(data):
        for field in path.SECTION_8_FIELDS:
            for entry in entries(horizon[field]):
                refs = entries(entry.get("recorded_as", []))
                sources = entries(entry.get("source", []))
                refs += [s[len(path.PATH_SOURCE):] for s in sources if s.startswith(path.PATH_SOURCE)]
                for ref in refs:
                    parts = ref.split("/")
                    if parts[0] == "frontier_backcasts":
                        assert next(b for b in data["frontier_backcasts"] if b["id"] == parts[1])["horizon"] \
                            == horizon["id"], (horizon["id"], ref)
                    elif parts[0] == "workstreams":
                        named = f"{horizon.get('prerequisite', '')} {horizon['activation_evidence']}"
                        assert re.search(rf"\b{parts[3]}\b", named), (horizon["id"], ref)
                        nodes += 1
                    else:
                        assert len(parts) == 1, (horizon["id"], ref)
    assert nodes > 0


def test_a_file_sourced_value_is_checked_here_not_at_load():
    """greg.path reads no repository document at load (an install may ship without docs/), so a value cited from a
    file is checked by this module: the file must exist and the value must stand whole in the section it cites."""
    with pytest.raises(AssertionError):
        cited("docs/nowhere.md")
    section = cited("docs/intent/sources/OPUS-MAXIMUS-MASTER-BUILD-DIRECTIVE-2026-10-28-source.md"
                    "#44-business-objective-function")
    assert whole("Engagement that destroys trust is failure.", section)
    assert not whole("GREG never earns a dollar", section)


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
