"""
IMPORTANT:
The following enumerations in v1 (according to the v1 enums.csv) are not found in the parts list:
SiteMeasureFractionAnalyzedDefault

What to do with inactive rows? eg. caRepDate is depreciated.
"""

from typing import Annotated, Any

import pandas as pd
import typer

from odm_map_maker.odm_vx.vx_mapping import VxMappingColumns, VxMappingVariableLocations
from odm_map_maker.utils.general_utils import (
    expand_multi_rows,
    save_data_frame,
)
from odm_map_maker.utils.logger import get_logger

VX_ENUM_NAME_COL = "vxEnumName"

NA_TAG = "NA"
AND_TAG = "&"

MAP_COLUMNS = {
    "version1Table": VxMappingColumns.SOURCE_TABLE,
    "version1Location": VxMappingColumns.SOURCE_LOCATION,
    "version1Variable": VxMappingColumns.SOURCE_VARIABLE,
    "version1Category": VxMappingColumns.SOURCE_CATEGORY,
}

logger = get_logger(__name__)

app = typer.Typer(
    pretty_exceptions_show_locals=False,
    rich_markup_mode="rich",
)

MAIN_HELP = """Prepare the ODM vx (eg. v2, v3) parts file by doing some basic
cleaning and reorganizing. We will only keep rows corresponding to a mapping
from a source class to ODM vx. We also expand rows that contain
data for multiple rows."""

PARTS_FILE_HELP = """Input CSV ODM vx parts file to prepare for v1 to vx
                  mapping."""

OUTPUT_FILE_HELP = """CSV file to save the prepared file to."""


def prepare_parts(
    parts_file: str,
    output_file: str,
    map_columns: dict[str, str] | None = None,
):
    """Prepare the ODM vx parts file by doing some basic cleaning and reorganizing. We will only
    keep rows corresponding to a mapping from a source class to ODM vx. We also expand rows that
    contain data for multiple rows.

    Args:
        parts_file (str): The original ODM vx parts file.
        output_file (str): File to save the prepared parts file to.
        map_columns (Optional[Dict[str, str]], optional): Rename columns in the parts list, changing
            columns with names matching a key in map_columns to the corresponding values in map_columns.
            The target names should be the values in VxMappingColumns, which are the columns used to
            specify the actual mappings to be performed. For example:
                map_columns = {
                    "version1Table" : VxMappingColumns.SOURCE_TABLE,
                    "version1Location" : VxMappingColumns.SOURCE_LOCATION,
                    "version1Variable" : VxMappingColumns.SOURCE_VARIABLE,
                    "version1Category" : VxMappingColumns.SOURCE_CATEGORY,
                }
            Defaults to None.
    """
    df = pd.read_csv(parts_file, keep_default_na=False, na_values=[""])

    # Map columns if necessary
    if map_columns is not None:
        columns = list(df.columns)
        for source_col, target_col in map_columns.items():
            columns[columns.index(source_col)] = target_col
        df.columns = columns

    # Only keep rows where the status is "active"
    # df = vx_keep_active_rows(df)

    # Only keep rows that have a Columns.SOURCE_TABLE specified
    df = df[
        ~pd.isna(df[VxMappingColumns.SOURCE_TABLE])
        & ~(df[VxMappingColumns.SOURCE_TABLE].astype(str).str.lower() == NA_TAG.lower())
    ]

    # Expand any row that contains data for multiple tables or variables. Multiple values are specified by
    # separating the values by a semicolon. (eg. "WWMeasure;SiteMeasure"). In the case of "WWMeasure;SiteMeasure"
    # we will split that row into two columns, one where the v1 table name is WWMeasure and the other
    # where the v1 table name is SiteMeasure.
    df = expand_multi_rows(
        df,
        columns=[
            VxMappingColumns.SOURCE_TABLE,
            VxMappingColumns.SOURCE_LOCATION,
            VxMappingColumns.SOURCE_VARIABLE,
            VxMappingColumns.SOURCE_CATEGORY,
        ],
    )

    # For any value that has AND_TAG in it, select the first item (eg. for "conf & report" we will select "conf")
    df = select_and_values(
        df,
        columns=[
            VxMappingColumns.SOURCE_TABLE,
            VxMappingColumns.SOURCE_LOCATION,
            VxMappingColumns.SOURCE_VARIABLE,
            VxMappingColumns.SOURCE_CATEGORY,
        ],
    )

    # Create the v1 enumeration names from Columns.SOURCE_TABLE and Columns.SOURCE_VARIABLE
    df = add_v1_enumeration_names(df)

    # Add the vx enumeration names
    df[VX_ENUM_NAME_COL] = df["partType"]

    save_data_frame(df, output_file, index=False)


def select_and_values(df: pd.DataFrame, columns: list[str] | str) -> pd.DataFrame:
    """In the specified columns of the DataFrame df, select the first item whenever an
    AND_TAG is found in it, after stripping off spaces and brackets. If no AND_TAG is found
    then we leave the value unchanged.

    For example, "(A & B)" and "A&B" and "A" would all result in "A".

    Args:
        df (pd.DataFrame): The DataFrame to select the AND values in. A copy of this is made
            with the original left unchanged.
        columns (Union[List[str], str]): The columns to select the AND values in.

    Returns:
        pd.DataFrame: A copy of df with the first item in any AND values selected.
    """
    if isinstance(columns, str):
        columns = [columns]

    def _select_element(val: Any) -> Any:
        if not isinstance(val, str) or AND_TAG not in val:
            return val
        val = val.strip("() ")
        val = val.split(AND_TAG)[0]
        return val.strip("() ")

    df = df.copy()
    df[columns] = df[columns].map(_select_element)
    return df


def add_v1_enumeration_names(df: pd.DataFrame) -> pd.DataFrame:
    """Add the v1 enumeration names (if any) corresponding to each row of the parts list.

    Args:
        df (pd.DataFrame): The parts list of ODM vx.

    Returns:
        pd.DataFrame: The parts list (df) with the v1 enumeration names added. A copy of df is
            made and the original is left unchanged.
    """

    def _make_enumeration_name(row: pd.Series) -> str:
        # If the row has a location of VariableLocations.VARIABLE_CATEGORIES, then it is a member of an enumeration. The
        # name of the enumeration consists of the concatenation of Columns.SOURCE_TABLE and Columns.SOURCE_VARIABLE (with
        # the first letter of Columns.SOURCE_VARIABLE capitalized)
        if (
            str(row[VxMappingColumns.SOURCE_LOCATION]).lower()
            == VxMappingVariableLocations.VARIABLE_CATEGORIES.lower()
        ):
            table = row[VxMappingColumns.SOURCE_TABLE]
            variable = row[VxMappingColumns.SOURCE_VARIABLE]
            return f"{table}{variable[0].upper()}{variable[1:]}"
        return None

    df = df.copy()
    df[VxMappingColumns.SOURCE_ENUM_NAME] = df[
        [
            VxMappingColumns.SOURCE_LOCATION,
            VxMappingColumns.SOURCE_TABLE,
            VxMappingColumns.SOURCE_VARIABLE,
        ]
    ].apply(_make_enumeration_name, axis=1)
    return df


@app.command(help=MAIN_HELP)
def main(
    parts_file: Annotated[str, typer.Option(show_default=False, help=PARTS_FILE_HELP)],
    output_file: Annotated[
        str, typer.Option(show_default=False, help=OUTPUT_FILE_HELP)
    ],
):
    logger.info("Making enumeration derivations...")
    prepare_parts(parts_file, output_file, map_columns=MAP_COLUMNS)
    logger.info("Finished!")


if __name__ == "__main__":
    app()
