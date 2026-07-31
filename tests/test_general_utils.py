import os

import pandas as pd
import pytest

from odm_map_maker.utils.general_utils import (
    choose_ignore_case_value,
    clear_dirs,
    expand_multi_rows,
    get_class_name_from_file_name,
    order_columns,
    parse_df_values,
    parse_numeric,
    read_data_frame,
    rename_items,
    save_data_frame,
    select_func_kwargs,
    strip_whitespace,
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
    assert (
        get_class_name_from_file_name("protocolSteps[001=method].csv")
        == "protocolSteps"
    )


def test_get_class_name_from_file_name_path():
    assert get_class_name_from_file_name("/some/path/measures.tsv") == "measures"


# ---------------------------------------------------------------------------
# save_data_frame / read_data_frame (round-trip)
# ---------------------------------------------------------------------------


def test_save_and_read_tsv(tmp_path):
    df = pd.DataFrame({"a": [1, 2], "b": ["x", "y"]})
    path = tmp_path / "test.tsv"
    save_data_frame(df, str(path), index=False)
    result = read_data_frame(str(path))
    assert list(result.columns) == ["a", "b"]
    assert result["a"].tolist() == [1, 2]


def test_save_and_read_csv(tmp_path):
    df = pd.DataFrame({"a": [3], "b": ["z"]})
    path = tmp_path / "test.csv"
    save_data_frame(df, str(path), index=False)
    result = read_data_frame(str(path))
    assert result["b"].tolist() == ["z"]


def test_save_and_read_txt(tmp_path):
    df = pd.DataFrame({"col": ["hello"]})
    path = tmp_path / "test.txt"
    save_data_frame(df, str(path), index=False)
    result = read_data_frame(str(path))
    assert result["col"].tolist() == ["hello"]


def test_save_and_read_yaml(tmp_path):
    df = pd.DataFrame({"x": [10, 20], "y": ["a", "b"]})
    path = tmp_path / "test.yaml"
    save_data_frame(df, str(path))
    result = read_data_frame(str(path))
    assert result["x"].tolist() == [10, 20]


def test_save_data_frame_strips_whitespace(tmp_path):
    df = pd.DataFrame({"a": ["  hello  "]})
    path = tmp_path / "test.tsv"
    save_data_frame(df, str(path), strip=True, index=False)
    result = read_data_frame(str(path))
    assert result["a"].tolist() == ["hello"]


def test_save_data_frame_unsupported_extension(tmp_path):
    df = pd.DataFrame({"a": [1]})
    path = tmp_path / "test.xyz"
    with pytest.raises(ValueError):
        save_data_frame(df, str(path))


def test_save_data_frame_creates_dirs(tmp_path):
    df = pd.DataFrame({"a": [1]})
    nested = tmp_path / "sub" / "dir" / "test.tsv"
    save_data_frame(df, str(nested), index=False)
    assert nested.exists()


def test_read_data_frame_unsupported_extension(tmp_path):
    path = tmp_path / "test.xyz"
    path.write_text("data")
    with pytest.raises(ValueError):
        read_data_frame(str(path))


# ---------------------------------------------------------------------------
# clear_dirs
# ---------------------------------------------------------------------------


def test_clear_dirs_removes_matching_files(tmp_path):
    (tmp_path / "a.tsv").write_text("data")
    (tmp_path / "b.csv").write_text("data")
    (tmp_path / "keep.txt").write_text("data")
    clear_dirs(tmp_path, extensions=[".tsv", ".csv"])
    remaining = os.listdir(tmp_path)
    assert "keep.txt" in remaining
    assert "a.tsv" not in remaining
    assert "b.csv" not in remaining


def test_clear_dirs_nonexistent_dir_no_error(tmp_path):
    clear_dirs(tmp_path / "does_not_exist")


def test_clear_dirs_string_extension(tmp_path):
    (tmp_path / "file.tsv").write_text("data")
    clear_dirs(str(tmp_path), extensions=".tsv")
    assert "file.tsv" not in os.listdir(tmp_path)


def test_clear_dirs_single_path_as_string(tmp_path):
    (tmp_path / "x.yaml").write_text("data")
    clear_dirs(str(tmp_path), extensions=[".yaml"])
    assert "x.yaml" not in os.listdir(tmp_path)


# ---------------------------------------------------------------------------
# choose_ignore_case_value
# ---------------------------------------------------------------------------


def test_choose_ignore_case_value_matches_capitalization():
    result = choose_ignore_case_value("hello", ["Hello", "World"])
    assert result == "Hello"


def test_choose_ignore_case_value_exact_match():
    result = choose_ignore_case_value("Hello", ["Hello", "World"])
    assert result == "Hello"


def test_choose_ignore_case_value_not_found_returns_same():
    result = choose_ignore_case_value("missing", ["Hello", "World"])
    assert result == "missing"


def test_choose_ignore_case_value_not_found_returns_none():
    result = choose_ignore_case_value(
        "missing", ["Hello"], return_same_if_missing=False
    )
    assert result is None


def test_choose_ignore_case_value_non_string_passthrough():
    result = choose_ignore_case_value(42, ["Hello"])
    assert result == 42


def test_choose_ignore_case_value_precomputed_lowercase():
    allowable = ["Alpha", "Beta"]
    lower = [v.lower() for v in allowable]
    result = choose_ignore_case_value(
        "ALPHA", allowable, lowercase_allowable_values=lower
    )
    assert result == "Alpha"


# ---------------------------------------------------------------------------
# parse_df_values
# ---------------------------------------------------------------------------


def test_parse_df_values_inline():
    df = pd.DataFrame({"a": ["1", "2"], "b": ["3.14", "hello"]})
    result = parse_df_values(df, inline=True)
    assert result["a"].tolist() == [1, 2]
    assert result["b"][0] == pytest.approx(3.14)
    assert result["b"][1] == "hello"


def test_parse_df_values_not_inline_leaves_original_unchanged():
    df = pd.DataFrame({"a": ["10"]})
    result = parse_df_values(df, inline=False)
    assert result["a"].tolist() == [10]
    assert df["a"].tolist() == ["10"]


# ---------------------------------------------------------------------------
# select_func_kwargs
# ---------------------------------------------------------------------------


def test_select_func_kwargs_filters_valid_keys():
    def my_func(a, b, c=1):
        _ = (a, b, c)

    kwargs = {"a": 10, "b": 20, "d": 99}
    result = select_func_kwargs(my_func, kwargs)
    assert "a" in result
    assert "b" in result
    assert "d" not in result


def test_select_func_kwargs_empty_kwargs():
    def my_func(a, b):
        _ = (a, b)

    assert select_func_kwargs(my_func, {}) == {}


def test_select_func_kwargs_no_overlap():
    def my_func(x, y):
        _ = (x, y)

    result = select_func_kwargs(my_func, {"a": 1, "b": 2})
    assert result == {}
