import textwrap

import pytest
from linkml_runtime import SchemaView
from linkml_runtime.linkml_model.meta import SlotDefinition

from odm_map_maker.utils.schema_utils import (
    add_ontoid_to_enum_value,
    all_classes_without_tree_root,
    find_class,
    get_class,
    get_enum_name_with_permissible_value,
    get_enum_names_for_slot,
    get_permissible_values_from_enum_names,
    get_ranges_of_slot,
    get_ranges_of_slot_defn,
    get_slot_definition,
    remove_ignored_text_from_class_name,
    remove_ontology_id,
)

# ---------------------------------------------------------------------------
# Minimal schema fixture used for all schema-dependent tests
# ---------------------------------------------------------------------------

MINIMAL_SCHEMA_YAML = textwrap.dedent("""
    id: https://example.org/test
    name: test_schema
    prefixes:
      linkml: https://w3id.org/linkml/
    imports:
      - linkml:types

    classes:
      Container:
        tree_root: true
        attributes:
          samples:
            range: Sample
            multivalued: true
      Sample:
        attributes:
          sampleID:
            range: string
          collectionDevice:
            range: CollectionDeviceEnum
      Site:
        attributes:
          siteID:
            range: string

    enums:
      CollectionDeviceEnum:
        permissible_values:
          swab: {}
          filter: {}
      StatusEnum:
        permissible_values:
          active: {}
          inactive: {}
""")

# Schema where enum permissible values have embedded ontology IDs like "swab [CD:001]"
ONTOID_SCHEMA_YAML = textwrap.dedent("""
    id: https://example.org/ontoid
    name: ontoid_schema
    prefixes:
      linkml: https://w3id.org/linkml/
    imports:
      - linkml:types

    classes:
      Container:
        tree_root: true
      Sample:
        attributes:
          collectionDevice:
            range: DeviceEnum

    enums:
      DeviceEnum:
        permissible_values:
          "swab [CD:001]": {}
          "filter [CD:002]": {}
""")


@pytest.fixture
def schema():
    return SchemaView(MINIMAL_SCHEMA_YAML)


@pytest.fixture
def ontoid_schema():
    return SchemaView(ONTOID_SCHEMA_YAML)


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


def test_get_ranges_slot_definition_object():
    # Pass an actual SlotDefinition instance (not a dict) to exercise the asdict() branch
    slot_defn = SlotDefinition(name="mySlot", range="integer")
    result = get_ranges_of_slot_defn(slot_defn)
    assert result == ["integer"]


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
    assert (
        remove_ignored_text_from_class_name("protocolSteps[001=method]")
        == "protocolSteps"
    )


def test_remove_ignored_text_round_bracket():
    assert remove_ignored_text_from_class_name("WWMeasure (2024-11-30)") == "WWMeasure "


def test_remove_ignored_text_no_bracket():
    assert remove_ignored_text_from_class_name("sites") == "sites"


# ---------------------------------------------------------------------------
# all_classes_without_tree_root
# ---------------------------------------------------------------------------


def test_all_classes_without_tree_root_excludes_container(schema):
    classes = all_classes_without_tree_root(schema)
    assert "Container" not in classes
    assert "Sample" in classes
    assert "Site" in classes


def test_all_classes_without_tree_root_count(schema):
    classes = all_classes_without_tree_root(schema)
    assert len(classes) == 2


# ---------------------------------------------------------------------------
# get_slot_definition
# ---------------------------------------------------------------------------


def test_get_slot_definition_returns_dict(schema):
    defn = get_slot_definition("Sample", "sampleID", schema)
    assert isinstance(defn, dict)
    assert defn["name"] == "sampleID"


def test_get_slot_definition_no_exception_returns_none(schema):
    result = get_slot_definition(
        "Sample", "nonexistent", schema, exception_on_error=False
    )
    assert result is None


def test_get_slot_definition_raises_by_default(schema):
    with pytest.raises(ValueError):
        get_slot_definition("Sample", "nonexistent", schema, exception_on_error=True)


# ---------------------------------------------------------------------------
# get_ranges_of_slot
# ---------------------------------------------------------------------------


def test_get_ranges_of_slot_string_range(schema):
    ranges = get_ranges_of_slot("Sample", "sampleID", schema)
    assert "string" in ranges


def test_get_ranges_of_slot_enum_range(schema):
    ranges = get_ranges_of_slot("Sample", "collectionDevice", schema)
    assert "CollectionDeviceEnum" in ranges


def test_get_ranges_of_slot_list_input(schema):
    ranges = get_ranges_of_slot("Sample", ["sampleID", "collectionDevice"], schema)
    assert "string" in ranges
    assert "CollectionDeviceEnum" in ranges


def test_get_ranges_of_slot_invalid_no_exception(schema):
    ranges = get_ranges_of_slot("Sample", "badSlot", schema, exception_on_error=False)
    assert ranges == []


# ---------------------------------------------------------------------------
# get_enum_name_with_permissible_value
# ---------------------------------------------------------------------------


def test_get_enum_name_with_permissible_value_found(schema):
    result = get_enum_name_with_permissible_value(
        ["CollectionDeviceEnum", "StatusEnum"], "swab", schema, match_ontology_id=None
    )
    assert result == "CollectionDeviceEnum"


def test_get_enum_name_with_permissible_value_not_found(schema):
    result = get_enum_name_with_permissible_value(
        ["CollectionDeviceEnum"], "unknown", schema, match_ontology_id=None
    )
    assert result is None


def test_get_enum_name_with_permissible_value_ontology_id(ontoid_schema):
    # Value "swab" matches "swab [CD:001]" after stripping the ontology ID
    result = get_enum_name_with_permissible_value(
        ["DeviceEnum"], "swab", ontoid_schema, match_ontology_id=r"\s*\[.*?\]"
    )
    assert result == "DeviceEnum"


def test_get_enum_name_with_permissible_value_ontology_id_no_match(ontoid_schema):
    result = get_enum_name_with_permissible_value(
        ["DeviceEnum"], "unknown", ontoid_schema, match_ontology_id=r"\s*\[.*?\]"
    )
    assert result is None


# ---------------------------------------------------------------------------
# add_ontoid_to_enum_value
# ---------------------------------------------------------------------------


def test_add_ontoid_to_enum_value_no_pattern(schema):
    result = add_ontoid_to_enum_value(
        schema, "CollectionDeviceEnum", "swab", match_ontology_id=None
    )
    assert result == "swab"


def test_add_ontoid_to_enum_value_no_enum_name(schema):
    result = add_ontoid_to_enum_value(
        schema, "", "swab", match_ontology_id=r"\s*\[.*?\]"
    )
    assert result == "swab"


def test_add_ontoid_to_enum_value_nonexistent_enum(schema):
    result = add_ontoid_to_enum_value(
        schema, "FakeEnum", "swab", match_ontology_id=r"\s*\[.*?\]"
    )
    assert result == "swab"


def test_add_ontoid_to_enum_value_no_match(schema):
    result = add_ontoid_to_enum_value(
        schema, "CollectionDeviceEnum", "unknown", match_ontology_id=r"\s*\[.*?\]"
    )
    assert result == "unknown"


def test_add_ontoid_to_enum_value_match_returns_full_value(ontoid_schema):
    # "swab" should be expanded to "swab [CD:001]" because the schema has "swab [CD:001]"
    result = add_ontoid_to_enum_value(
        ontoid_schema, "DeviceEnum", "swab", match_ontology_id=r"\s*\[.*?\]"
    )
    assert result == "swab [CD:001]"


# ---------------------------------------------------------------------------
# get_enum_names_for_slot
# ---------------------------------------------------------------------------


def test_get_enum_names_for_slot_has_enum(schema):
    result = get_enum_names_for_slot("Sample", "collectionDevice", schema)
    assert result == ["CollectionDeviceEnum"]


def test_get_enum_names_for_slot_no_enum(schema):
    result = get_enum_names_for_slot("Sample", "sampleID", schema)
    assert result == []


# ---------------------------------------------------------------------------
# get_permissible_values_from_enum_names
# ---------------------------------------------------------------------------


def test_get_permissible_values_from_enum_names_basic(schema):
    values = get_permissible_values_from_enum_names(["CollectionDeviceEnum"], schema)
    assert set(values) == {"swab", "filter"}


def test_get_permissible_values_from_enum_names_sorted(schema):
    values = get_permissible_values_from_enum_names(
        ["CollectionDeviceEnum"], schema, sort_values=True
    )
    assert values == sorted(values, key=str.lower)


def test_get_permissible_values_from_enum_names_multiple_enums(schema):
    values = get_permissible_values_from_enum_names(
        ["CollectionDeviceEnum", "StatusEnum"], schema
    )
    assert "swab" in values
    assert "active" in values


# ---------------------------------------------------------------------------
# find_class
# ---------------------------------------------------------------------------


def test_find_class_exact_match(schema):
    assert find_class("Sample", schema, ignore_case=True) == "Sample"


def test_find_class_case_insensitive(schema):
    assert find_class("sample", schema, ignore_case=True) == "Sample"


def test_find_class_in_longer_string(schema):
    # "1 - Sample (2024)" → should find "Sample"
    result = find_class("1 - Sample", schema, ignore_case=True)
    assert result == "Sample"


def test_find_class_no_match(schema):
    assert find_class("Nonexistent", schema, ignore_case=True) is None


def test_find_class_no_schema():
    result = find_class("WWMeasure[001]", schema=None, ignore_case=True)
    assert result == "WWMeasure"


# ---------------------------------------------------------------------------
# get_class
# ---------------------------------------------------------------------------


def test_get_class_exact(schema):
    assert get_class("Sample", schema, ignore_case=False) == "Sample"


def test_get_class_case_insensitive(schema):
    assert get_class("sample", schema, ignore_case=True) == "Sample"


def test_get_class_case_sensitive_no_match(schema):
    assert get_class("sample", schema, ignore_case=False) is None


def test_get_class_strips_brackets(schema):
    assert get_class("Sample[001]", schema, ignore_case=False) == "Sample"


def test_get_class_no_schema():
    result = get_class("Sample[extra]", schema=None, ignore_case=True)
    assert result == "Sample"
