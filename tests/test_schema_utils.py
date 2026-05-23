import pytest

from odm_map_maker.utils.schema_utils import (
    get_ranges_of_slot_defn,
    remove_ontology_id,
    remove_ignored_text_from_class_name,
)


# ---------------------------------------------------------------------------
# get_ranges_of_slot_defn  (regression test for the NameError fix)
# ---------------------------------------------------------------------------

def test_get_ranges_no_range_no_any_of():
    # Previously raised NameError; should now return []
    result = get_ranges_of_slot_defn({"name": "someSlot"})
    assert result == []

def test_get_ranges_with_range():
    result = get_ranges_of_slot_defn({"range": "string"})
    assert result == ["string"]

def test_get_ranges_with_any_of():
    slot = {"any_of": [{"range": "TypeA"}, {"range": "TypeB"}]}
    result = get_ranges_of_slot_defn(slot)
    assert set(result) == {"TypeA", "TypeB"}

def test_get_ranges_any_of_overrides_range():
    # When any_of is present and non-empty it replaces the range entry
    slot = {"range": "Fallback", "any_of": [{"range": "TypeA"}]}
    result = get_ranges_of_slot_defn(slot)
    assert result == ["TypeA"]

def test_get_ranges_list_of_dicts():
    slots = [{"range": "TypeA"}, {"range": "TypeB"}, {"name": "noRange"}]
    result = get_ranges_of_slot_defn(slots)
    assert result == ["TypeA", "TypeB"]

def test_get_ranges_deduplicates():
    slots = [{"range": "string"}, {"range": "string"}]
    result = get_ranges_of_slot_defn(slots)
    assert result == ["string"]


# ---------------------------------------------------------------------------
# remove_ontology_id
# ---------------------------------------------------------------------------

def test_remove_ontology_id_removes_bracketed_id():
    val = "degree Celsius (C) [UO:0000027]"
    result = remove_ontology_id(val, match_ontology_id=r"\s*\[.*?\]")
    assert result == "degree Celsius (C)"

def test_remove_ontology_id_no_match_unchanged():
    val = "degree Celsius (C)"
    result = remove_ontology_id(val, match_ontology_id=r"\s*\[.*?\]")
    assert result == "degree Celsius (C)"

def test_remove_ontology_id_none_pattern_unchanged():
    val = "some value [ID:123]"
    assert remove_ontology_id(val, match_ontology_id=None) == val
    assert remove_ontology_id(val, match_ontology_id="") == val


# ---------------------------------------------------------------------------
# remove_ignored_text_from_class_name
# ---------------------------------------------------------------------------

def test_remove_ignored_text_square_bracket():
    assert remove_ignored_text_from_class_name("protocolSteps[001=method]") == "protocolSteps"

def test_remove_ignored_text_round_bracket():
    assert remove_ignored_text_from_class_name("WWMeasure (2024-11-30)") == "WWMeasure "

def test_remove_ignored_text_no_bracket():
    assert remove_ignored_text_from_class_name("sites") == "sites"
