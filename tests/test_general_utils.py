import pytest
import pandas as pd

from odm_map_maker.utils.general_utils import (
    order_columns,
    strip_whitespace,
    rename_items,
    parse_numeric,
    expand_multi_rows,
    get_class_name_from_file_name,
)


# ---------------------------------------------------------------------------
# order_columns
# ---------------------------------------------------------------------------

def test_order_columns_basic():
    df = pd.DataFrame({"b": [1], "a": [2], "c": [3]})
    result = order_columns(df, ["a", "b"])
    assert list(result.columns) == ["a", "b", "c"]

def test_order_columns_extra_at_end():
    df = pd.DataFrame({"z": [1], "a": [2]})
    result = order_columns(df, ["a"])
    assert list(result.columns) == ["a", "z"]

def test_order_columns_does_not_mutate_original():
    df = pd.DataFrame({"b": [1], "a": [2]})
    _ = order_columns(df, ["a", "b"])
    assert list(df.columns) == ["b", "a"]


# ---------------------------------------------------------------------------
# strip_whitespace
# ---------------------------------------------------------------------------

def test_strip_whitespace_strings():
    df = pd.DataFrame({"x": ["  hello  ", " world"], "y": [1, 2]})
    result = strip_whitespace(df)
    assert result["x"].tolist() == ["hello", "world"]
    assert result["y"].tolist() == [1, 2]

def test_strip_whitespace_leaves_non_strings_alone():
    df = pd.DataFrame({"x": [None, 3.14, True]})
    result = strip_whitespace(df)
    assert result["x"].tolist() == [None, 3.14, True]


# ---------------------------------------------------------------------------
# rename_items
# ---------------------------------------------------------------------------

def test_rename_items_basic():
    assert rename_items(["a", "b", "c"], {"a": "x", "c": "z"}) == ["x", "b", "z"]

def test_rename_items_does_not_mutate_original():
    original = ["a", "b"]
    rename_items(original, {"a": "x"})
    assert original == ["a", "b"]

def test_rename_items_empty_renames():
    assert rename_items(["a", "b"], {}) == ["a", "b"]


# ---------------------------------------------------------------------------
# parse_numeric
# ---------------------------------------------------------------------------

def test_parse_numeric_int():
    assert parse_numeric("42") == 42
    assert isinstance(parse_numeric("42"), int)

def test_parse_numeric_float():
    assert parse_numeric("3.14") == pytest.approx(3.14)
    assert isinstance(parse_numeric("3.14"), float)

def test_parse_numeric_non_numeric_unchanged():
    assert parse_numeric("hello") == "hello"
    assert parse_numeric("1abc") == "1abc"

def test_parse_numeric_non_string_unchanged():
    assert parse_numeric(None) is None
    assert parse_numeric(42) == 42

def test_parse_numeric_negative():
    assert parse_numeric("-5") == -5


# ---------------------------------------------------------------------------
# expand_multi_rows
# ---------------------------------------------------------------------------

def test_expand_multi_rows_no_semicolons():
    df = pd.DataFrame({"a": ["x", "y"], "b": [1, 2]})
    result = expand_multi_rows(df, "a")
    assert len(result) == 2

def test_expand_multi_rows_basic():
    df = pd.DataFrame({"a": ["x;y;z"], "b": ["p;q"]})
    result = expand_multi_rows(df, ["a", "b"]).reset_index(drop=True)
    assert len(result) == 3
    assert result["a"].tolist() == ["x", "y", "z"]
    # "b" only has 2 values; last one is repeated for extra rows
    assert result["b"].tolist() == ["p", "q", "q"]

def test_expand_multi_rows_does_not_mutate_original():
    df = pd.DataFrame({"a": ["x;y"]})
    _ = expand_multi_rows(df, "a")
    assert df["a"].tolist() == ["x;y"]


# ---------------------------------------------------------------------------
# get_class_name_from_file_name
# ---------------------------------------------------------------------------

def test_get_class_name_from_file_name_simple():
    assert get_class_name_from_file_name("sites.csv") == "sites"

def test_get_class_name_from_file_name_with_brackets():
    assert get_class_name_from_file_name("protocolSteps[001=method].csv") == "protocolSteps"

def test_get_class_name_from_file_name_path():
    assert get_class_name_from_file_name("/some/path/measures.tsv") == "measures"
