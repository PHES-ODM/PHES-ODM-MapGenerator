import ast

import pandas as pd

from odm_map_maker.utils.mapper_utils import (
    any_wide_slot_name,
    cleanup_slot_name,
    format_slot_name,
    get_blank_class_derivation,
    get_source_slots_from_slot_derivation,
    get_used_slots,
    get_variable_reference,
    is_wide_target_expr_slot,
    is_wide_target_value_slot,
    parse_used_slots,
    wide_slot_name,
    wide_target_expr_slot_name,
)

# ---------------------------------------------------------------------------
# format_slot_name
# ---------------------------------------------------------------------------


def test_format_lowercase():
    assert format_slot_name("Hello_World", ["lowercase"]) == "hello_world"


def test_format_uppercase():
    assert format_slot_name("hello", ["uppercase"]) == "HELLO"


def test_format_alpha_numeric_underscore():
    assert (
        format_slot_name("hello world!", ["alpha_numeric_underscore"]) == "hello_world_"
    )


def test_format_single_underscores():
    assert (
        format_slot_name("hello__world___foo", ["single_underscores"])
        == "hello_world_foo"
    )


def test_format_trim_trailing_underscores():
    assert format_slot_name("hello__", ["trim_trailing_underscores"]) == "hello"


def test_format_trim_whitespace():
    assert format_slot_name("  hello  ", ["trim_whitespace"]) == "hello"


def test_format_remove_chars():
    assert format_slot_name("hello (world)", [{"remove_chars": "()"}]) == "hello world"


def test_format_remove_special():
    assert format_slot_name("hello-world!", ["remove_special"]) == "helloworld"


def test_format_chained_operations():
    result = format_slot_name(
        "  Hello World!  ",
        [
            "trim_whitespace",
            "lowercase",
            "alpha_numeric_underscore",
            "single_underscores",
            "trim_trailing_underscores",
        ],
    )
    assert result == "hello_world"


def test_format_non_string_unchanged():
    assert format_slot_name(None, ["lowercase"]) is None
    assert format_slot_name(42, ["lowercase"]) == 42


def test_format_extra_column_prefix_unchanged():
    val = "_extra_someColumn"
    assert format_slot_name(val, ["lowercase"]) == val


# ---------------------------------------------------------------------------
# Wide slot name helpers
# ---------------------------------------------------------------------------


def test_is_wide_target_value_slot():
    assert is_wide_target_value_slot("sampleID_value") is True
    assert is_wide_target_value_slot("sampleID_expr") is False
    assert is_wide_target_value_slot("sampleID") is False
    assert is_wide_target_value_slot(None) is False


def test_is_wide_target_expr_slot():
    assert is_wide_target_expr_slot("measure_expr") is True
    assert is_wide_target_expr_slot("measure_value") is False
    assert is_wide_target_expr_slot(42) is False


def test_wide_slot_name_value():
    assert wide_slot_name("sampleID_value", "_value") == "sampleID"
    assert wide_slot_name("sampleID_expr", "_value") is None


def test_any_wide_slot_name():
    assert any_wide_slot_name("sampleID_value") == "sampleID"
    assert any_wide_slot_name("measure_expr") == "measure"
    assert any_wide_slot_name("sampleID") is None


# ---------------------------------------------------------------------------
# get_used_slots / parse_used_slots
# ---------------------------------------------------------------------------


def test_get_used_slots_simple():
    code = "target = myGlobal.collection_device"
    slots = get_used_slots(code, recognized_globals=["myGlobal"])
    assert slots == ["collection_device"]


def test_get_used_slots_multiple():
    code = "x = myGlobal.slot_a + myGlobal.slot_b"
    slots = get_used_slots(code, recognized_globals=["myGlobal"])
    assert slots == ["slot_a", "slot_b"]


def test_get_used_slots_ignores_other_namespaces():
    code = "x = src.slot_a + myGlobal.slot_b"
    slots = get_used_slots(code, recognized_globals=["myGlobal"])
    assert slots == ["slot_b"]


def test_get_used_slots_deduplicates():
    code = "x = myGlobal.slot_a + myGlobal.slot_a"
    slots = get_used_slots(code, recognized_globals=["myGlobal"])
    assert slots == ["slot_a"]


def test_parse_used_slots_no_shared_mutable_default():
    # Calling parse_used_slots twice with no explicit path argument should
    # not accumulate results between calls.
    tree1 = ast.parse("myGlobal.slot_a").body[0].value
    tree2 = ast.parse("myGlobal.slot_b").body[0].value
    result1 = parse_used_slots(tree1)
    result2 = parse_used_slots(tree2)
    assert result1 == ["myGlobal", "slot_a"]
    assert result2 == ["myGlobal", "slot_b"]


# ---------------------------------------------------------------------------
# wide_target_expr_slot_name
# ---------------------------------------------------------------------------


def test_wide_target_expr_slot_name_with_suffix():
    assert wide_target_expr_slot_name("measure_expr") == "measure"


def test_wide_target_expr_slot_name_without_suffix():
    assert wide_target_expr_slot_name("measure_value") is None


def test_wide_target_expr_slot_name_no_suffix():
    assert wide_target_expr_slot_name("measure") is None


# ---------------------------------------------------------------------------
# get_variable_reference
# ---------------------------------------------------------------------------


def test_get_variable_reference_valid():
    result = get_variable_reference("{{sampleID}}", format_operations=None)
    assert result == "sampleID"


def test_get_variable_reference_non_string():
    assert get_variable_reference(42, format_operations=None) is None


def test_get_variable_reference_no_braces():
    assert get_variable_reference("sampleID", format_operations=None) is None


def test_get_variable_reference_partial_braces():
    assert get_variable_reference("{sampleID}", format_operations=None) is None


def test_get_variable_reference_with_format_operations():
    result = get_variable_reference("{{Sample ID}}", format_operations=["lowercase"])
    assert result == "sample id"


# ---------------------------------------------------------------------------
# get_source_slots_from_slot_derivation
# ---------------------------------------------------------------------------


def test_get_source_slots_populated_from():
    derivation = {"name": "targetSlot", "populated_from": "sourceSlot"}
    result = get_source_slots_from_slot_derivation(derivation, recognized_globals=[])
    assert result == ["sourceSlot"]


def test_get_source_slots_from_expr():
    derivation = {"name": "targetSlot", "expr": "target = myGlobal.sourceSlot"}
    result = get_source_slots_from_slot_derivation(
        derivation, recognized_globals=["myGlobal"]
    )
    assert result == ["sourceSlot"]


def test_get_source_slots_from_expr_multiple():
    derivation = {
        "name": "targetSlot",
        "expr": "target = myGlobal.slotA + myGlobal.slotB",
    }
    result = get_source_slots_from_slot_derivation(
        derivation, recognized_globals=["myGlobal"]
    )
    assert result == ["slotA", "slotB"]


# ---------------------------------------------------------------------------
# get_blank_class_derivation
# ---------------------------------------------------------------------------


def test_get_blank_class_derivation_structure():
    result = get_blank_class_derivation("SourceClass", "TargetClass")
    assert result["name"] == "TargetClass"
    assert result["populated_from"] == "SourceClass"
    assert result["slot_derivations"] == {}


def test_get_blank_class_derivation_returns_new_dict_each_time():
    d1 = get_blank_class_derivation("A", "B")
    d2 = get_blank_class_derivation("A", "B")
    d1["slot_derivations"]["x"] = 1
    assert d2["slot_derivations"] == {}


# ---------------------------------------------------------------------------
# cleanup_slot_name
# ---------------------------------------------------------------------------


def test_cleanup_slot_name_no_options():
    assert cleanup_slot_name("Hello World", cleanup_options=None) == "Hello World"


def test_cleanup_slot_name_string():
    result = cleanup_slot_name("Hello World!", cleanup_options=["lowercase"])
    assert result == "hello world!"


def test_cleanup_slot_name_dataframe():
    df = pd.DataFrame({"col": ["Hello", "WORLD"]})
    result = cleanup_slot_name(df, cleanup_options=["lowercase"])
    assert result["col"].tolist() == ["hello", "world"]


def test_cleanup_slot_name_series():
    s = pd.Series(["Hello", "WORLD"])
    result = cleanup_slot_name(s, cleanup_options=["lowercase"])
    assert result.tolist() == ["hello", "world"]


# ---------------------------------------------------------------------------
# parse_used_slots — chained attribute (covers the recursive ast.Attribute branch)
# ---------------------------------------------------------------------------


def test_parse_used_slots_chained_attribute():
    # "a.b.c" produces a nested ast.Attribute (c on (b on a))
    tree = ast.parse("a.b.c").body[0].value
    result = parse_used_slots(tree)
    assert result == ["a", "b", "c"]


def test_get_used_slots_chained_attribute():
    # Only first-level namespace check applies, deeper chains should still work
    code = "x = myGlobal.ns.slot"
    # myGlobal.ns is an Attribute; slot is an Attribute on that — only "ns" is a direct attribute of myGlobal
    slots = get_used_slots(code, recognized_globals=["myGlobal"])
    # "ns" is the direct attribute of myGlobal here
    assert "ns" in slots
