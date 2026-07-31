"""
Utility functions for ODM LinkML Schema Generator, specific to ODM vx dictionary.
"""

from typing import Any

import pandas as pd

# In the ODM vx data dictionary, in the parts sheet, each table (eg. samples, sites, measures) has
# a column with the same name as the table. If a row has any of the following _vx_header_tags in that
# column, then the partID for that row is a column header in the ODM vx table.
_vx_header_tags = [
    "header",  # Regular header
    "fK",  # Foreign key
    "pK",  # Primary key
]

# Enumerations specified in the parts list (that are NOT in the sets list) are identified by rows that
# have "categorical" as the "dataType" and that have an empty "mmaSet" column. The names for
# the enumerations for these rows are created by adding an "s" to the end of the "partID". However, some
# enumeration names do not follow this pattern. The exceptions are listed below, with the "partID" as the
# key and the corresponding enumeration name as the value.
_vx_enum_name_exceptions = {
    "aggragationScale": "aggregationScales",  # TYPO! Should be aggregationScale / Only in parts table
    "class": "classes",  # Add "es" instead of "s"
    "dataTypes": "dataTypes",  # No change
    "measure": "measurements",  # Not sure?
    "missingnessSets": "missingnessSets",  # No change
    "partType": "partType",  # Not sure?
    "qualityFlag": "qualityIndicators",
    "specimenSets": "specimenSets",  # No change
}

# In the ODM data dictionary parts sheet, any column that ends with the string ODM_PARTS_COLUMN_CLASS_TAG begins
# with the name of an ODM class (eg. measuresOrder, protocolStepsOrder, etc). This is used by
# odm_get_available_class_names to extract all the known class names from the data dictionary.
ODM_PARTS_COLUMN_CLASS_TAG = "Order"


def odm_get_available_class_names(headers: pd.DataFrame | list[str]) -> list[str]:
    """Get a list of all ODM class/table names that are defined in a ODM parts sheet that contains
    the specified headers.

    Args:
        headers (Union[pd.DataFrame, List[str]]): Either a list of all headers in the ODM parts sheet, or the actual
            DataFrame for the parts sheet.

    Returns:
        List[str]: List of all class/table names that the parts sheet defines.
    """
    if isinstance(headers, pd.DataFrame):
        headers = headers.columns
    headers = [
        h[: -len(ODM_PARTS_COLUMN_CLASS_TAG)]
        for h in headers
        if h.endswith(ODM_PARTS_COLUMN_CLASS_TAG)
        and len(h) > len(ODM_PARTS_COLUMN_CLASS_TAG)
    ]
    return headers


def vx_get_header_rows(
    df: pd.DataFrame,
    tables: str | list[str],
    header_tags: str | list[str] | None = None,
) -> pd.DataFrame:
    """Retrieve all rows in the DataFrame that correspond to a column in any of the specified
    ODM vx tables.

    This corresponds to rows that are either a primary key, a foreign key, or a header in any
    of the tables. Note that to determine if a row is a column, the DataFrame df must
    have a column with the same name as the table.

    Args:
        df (pd.DataFrame): The DataFrame to retrieve the rows from.
        tables (Union[str, List[str]]): The table name(s) to retrieve the rows for. For each
            table name a column with that name must be present in df.
        header_tags (Optional[Union[str, List[str]]]): The header tags (ie. header types) to search for.
            This can be "fK" (for foreign key), "pK" (for primary key), and/or "header" (for a regular
            non-key header). These are case-insensitive. If None then all of these header types are
            retrieved. Defaults to None.

    Returns:
        pd.DataFrame: df filtered to only include the rows that specify a column in at least
            one of the tables. A copy of the DataFrame is made.
    """
    if header_tags is None:
        header_tags = _vx_header_tags
    if isinstance(header_tags, str):
        header_tags = [header_tags]
    if isinstance(tables, str):
        tables = [tables]
    lower_header_tags = [h.lower() for h in header_tags]
    lower_df = df[tables].map(lambda x: x.lower() if isinstance(x, str) else x)
    is_header = lower_df[tables].isin(lower_header_tags)
    is_header = is_header.sum(axis=1)
    return df[is_header > 0].copy()


def vx_keep_active_rows(
    df: pd.DataFrame,
    status_column: str = "status",
    keep_status: Any | list[Any] = "active",
) -> pd.DataFrame:
    """Keep only rows that have an "active" status. Status is specified in a single column in the
    DataFrame.

    Args:
        df (pd.DataFrame): The DataFrame to filter, retrieving only active rows.
        status_column (str, optional): The column name that contains each row's status. Defaults to "status".
        keep_status (Union[Any, List[Any]], optional): The string(s) that indicate an active status. Defaults to "active".

    Returns:
        pd.DataFrame: df filtered to only have active status rows. A copy of the DataFrame is made before
            returning.
    """
    if not isinstance(keep_status, (list, tuple)):
        keep_status = [keep_status]
    keep_filt = df[status_column].str.strip().isin(keep_status)
    df = df[keep_filt]
    return df.copy()


def vx_get_enum_name_from_part_id(part_id: str) -> str:
    """Get the enumeration name for the specified part ID.

    Args:
        part_id (str): The partID to get the enumeration name for. This is typically equal
            to the partID with a trailing "s", but there are some exceptions.

    Returns:
        str: The enumeration name (for the partID)
    """
    return _vx_enum_name_exceptions.get(part_id, f"{part_id}s")
