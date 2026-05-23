import ast
import pytest

from odm_map_maker.utils.mapper_utils import (
    format_slot_name,
    is_wide_target_value_slot,
    is_wide_target_expr_slot,
    any_wide_slot_name,
    wide_slot_name,
    get_used_slots,
    parse_used_slots,
)


# ---------------------------------------------------------------------------
# format_slot_name
# ---------------------------------------------------------------------------

def test_format_lowercase():
    assert format_slot_name("Hello_World", ["lowercase"]) == "hello_world"

def test_format_uppercase():
    assert format_slot_name("hello", ["uppercase"]) == "HELLO"

def test_format_alpha_numeric_underscore():
    assert format_slot_name("hello world!", ["alpha_numeric_underscore"]) == "hello_world_"

def test_format_single_underscores():
    assert format_slot_name("hello__world___foo", ["single_underscores"]) == "hello_world_foo"

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
        ["trim_whitespace", "lowercase", "alpha_numeric_underscore", "single_underscores", "trim_trailing_underscores"],
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
    code = "target = emap.collection_device"
    slots = get_used_slots(code, recognized_globals=["emap"])
    assert slots == ["collection_device"]

def test_get_used_slots_multiple():
    code = "x = emap.slot_a + emap.slot_b"
    slots = get_used_slots(code, recognized_globals=["emap"])
    assert slots == ["slot_a", "slot_b"]

def test_get_used_slots_ignores_other_namespaces():
    code = "x = src.slot_a + emap.slot_b"
    slots = get_used_slots(code, recognized_globals=["emap"])
    assert slots == ["slot_b"]

def test_get_used_slots_deduplicates():
    code = "x = emap.slot_a + emap.slot_a"
    slots = get_used_slots(code, recognized_globals=["emap"])
    assert slots == ["slot_a"]

def test_parse_used_slots_no_shared_mutable_default():
    # Calling parse_used_slots twice with no explicit path argument should
    # not accumulate results between calls.
    tree1 = ast.parse("emap.slot_a").body[0].value
    tree2 = ast.parse("emap.slot_b").body[0].value
    result1 = parse_used_slots(tree1)
    result2 = parse_used_slots(tree2)
    assert result1 == ["emap", "slot_a"]
    assert result2 == ["emap", "slot_b"]
