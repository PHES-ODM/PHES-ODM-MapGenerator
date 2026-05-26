import textwrap
import pytest
import pandas as pd

from odm_map_maker.validate_mappers.mapper_validator import (
    ValidateMappers,
    EnumsColumns,
)


# ---------------------------------------------------------------------------
# Minimal schemas and mapper fixture
# ---------------------------------------------------------------------------

MINIMAL_SOURCE_SCHEMA = textwrap.dedent("""
    id: https://example.org/source
    name: source_schema
    prefixes:
      linkml: https://w3id.org/linkml/
    imports:
      - linkml:types
    classes:
      Container:
        tree_root: true
      Sample:
        attributes:
          sampleID:
            range: string
          collectionDevice:
            range: CollectionDeviceEnum
    enums:
      CollectionDeviceEnum:
        permissible_values:
          swab: {}
          filter: {}
""")

MINIMAL_TARGET_SCHEMA = textwrap.dedent("""
    id: https://example.org/target
    name: target_schema
    prefixes:
      linkml: https://w3id.org/linkml/
    imports:
      - linkml:types
    classes:
      Container:
        tree_root: true
      MappedSample:
        attributes:
          id:
            range: string
          device:
            range: DeviceEnum
    enums:
      DeviceEnum:
        permissible_values:
          swab: {}
          filter: {}
""")


@pytest.fixture
def validator():
    return ValidateMappers(MINIMAL_SOURCE_SCHEMA, MINIMAL_TARGET_SCHEMA)


# ---------------------------------------------------------------------------
# enum_derivation_exists
# ---------------------------------------------------------------------------


def test_enum_derivation_exists_true(validator):
    mapper = {
        "enum_derivations": {
            "DeviceEnum": {
                "name": "DeviceEnum",
                "populated_from": "CollectionDeviceEnum",
            }
        }
    }
    assert validator.enum_derivation_exists("CollectionDeviceEnum", mapper) is True


def test_enum_derivation_exists_no_key(validator):
    mapper = {}
    assert validator.enum_derivation_exists("CollectionDeviceEnum", mapper) is False


def test_enum_derivation_exists_wrong_enum(validator):
    mapper = {
        "enum_derivations": {"Other": {"name": "Other", "populated_from": "OtherEnum"}}
    }
    assert validator.enum_derivation_exists("CollectionDeviceEnum", mapper) is False


# ---------------------------------------------------------------------------
# replace_blanks
# ---------------------------------------------------------------------------


def test_replace_blanks_empty_string(validator):
    result = validator.replace_blanks(["", "value", ""])
    assert result == ["<blank>", "value", "<blank>"]


def test_replace_blanks_all_non_empty(validator):
    result = validator.replace_blanks(["a", "b"])
    assert result == ["a", "b"]


def test_replace_blanks_empty_list(validator):
    assert validator.replace_blanks([]) == []


# ---------------------------------------------------------------------------
# concat_data_frames
# ---------------------------------------------------------------------------


def test_concat_data_frames_empty_list(validator):
    result = validator.concat_data_frames([])
    assert isinstance(result, pd.DataFrame)
    assert len(result) == 0


def test_concat_data_frames_drops_empty_dfs(validator):
    df1 = pd.DataFrame({"a": [1, 2]})
    df2 = pd.DataFrame()
    result = validator.concat_data_frames([df1, df2])
    assert len(result) == 2


def test_concat_data_frames_single(validator):
    df = pd.DataFrame({"a": [1]})
    result = validator.concat_data_frames([df])
    assert len(result) == 1


def test_concat_data_frames_multiple(validator):
    df1 = pd.DataFrame({"a": [1]})
    df2 = pd.DataFrame({"a": [2]})
    result = validator.concat_data_frames([df1, df2])
    assert list(result["a"]) == [1, 2]


def test_concat_data_frames_with_blank_rows(validator):
    df1 = pd.DataFrame({"a": [1]})
    df2 = pd.DataFrame({"a": [2]})
    result = validator.concat_data_frames([df1, df2], insert_blank_rows=True)
    assert len(result) == 3
    assert pd.isna(result.iloc[1]["a"])


# ---------------------------------------------------------------------------
# order_columns
# ---------------------------------------------------------------------------


def test_order_columns_orders_known_columns(validator):
    df = pd.DataFrame(
        {
            EnumsColumns.TARGET_SLOT: ["ts"],
            EnumsColumns.SOURCE_CLASS: ["sc"],
            EnumsColumns.SOURCE_SLOT: ["ss"],
        }
    )
    result = validator.order_columns(df)
    cols = list(result.columns)
    assert cols.index(EnumsColumns.SOURCE_CLASS) < cols.index(EnumsColumns.SOURCE_SLOT)
    assert cols.index(EnumsColumns.SOURCE_SLOT) < cols.index(EnumsColumns.TARGET_SLOT)


def test_order_columns_extra_columns_at_end(validator):
    df = pd.DataFrame(
        {
            "extra_col": [1],
            EnumsColumns.SOURCE_CLASS: ["sc"],
        }
    )
    result = validator.order_columns(df)
    cols = list(result.columns)
    assert cols[-1] == "extra_col"


def test_order_columns_returns_copy(validator):
    df = pd.DataFrame({EnumsColumns.SOURCE_CLASS: ["x"]})
    result = validator.order_columns(df)
    result[EnumsColumns.SOURCE_CLASS] = ["y"]
    assert df[EnumsColumns.SOURCE_CLASS].tolist() == ["x"]


# ---------------------------------------------------------------------------
# simplify_enum_df
# ---------------------------------------------------------------------------


def test_simplify_enum_df_empty(validator):
    df = pd.DataFrame()
    result = validator.simplify_enum_df(df)
    assert len(result) == 0


def test_simplify_enum_df_deduplicates_mapper_file(validator):
    df = pd.DataFrame(
        {
            EnumsColumns.SOURCE_ENUM_NAME: ["MyEnum", "MyEnum"],
            EnumsColumns.SOURCE_ENUM_VALUE: ["val1", "val1"],
            EnumsColumns.MAPPER_FILE: ["file_a.yaml", "file_b.yaml"],
        }
    )
    result = validator.simplify_enum_df(df, sort_by=[])
    # Two rows with same enum+value should be merged into one
    assert len(result) == 1
    assert "file_a.yaml" in result.iloc[0][EnumsColumns.MAPPER_FILE]
    assert "file_b.yaml" in result.iloc[0][EnumsColumns.MAPPER_FILE]
    assert result.iloc[0][EnumsColumns.MAPPER_FILE_COUNT] == 2


def test_simplify_enum_df_keeps_distinct_rows(validator):
    df = pd.DataFrame(
        {
            EnumsColumns.SOURCE_ENUM_NAME: ["EnumA", "EnumB"],
            EnumsColumns.SOURCE_ENUM_VALUE: ["val1", "val2"],
            EnumsColumns.MAPPER_FILE: ["file1.yaml", "file2.yaml"],
        }
    )
    result = validator.simplify_enum_df(df, sort_by=[])
    assert len(result) == 2
