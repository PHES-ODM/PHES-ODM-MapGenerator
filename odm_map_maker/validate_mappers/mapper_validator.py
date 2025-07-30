# %%
from typing import Union, List, Tuple, Annotated
from pathlib import Path
import os
import yaml
import pandas as pd
import typer

from linkml_runtime import SchemaView

from odm_map_maker.utils.logger import get_logger
from odm_map_maker.utils.mapper_utils import get_used_slots

logger = get_logger(__name__)

app = typer.Typer(
    pretty_exceptions_show_locals=False,
    rich_markup_mode="rich",
)


MAIN_HELP = """Validate mappers, testing to ensure all required enum derivations exist, that all permissible
values for the enum derivations exist, and that no unrecognized permissible values in the derivations exist."""

MAPPERS_DIR_HELP = """Directory containing all the LinkML-Map schemas to validate. All yaml files are tested."""

SOURCE_SCHEMA_HELP = """Path to the source LinkML schema that the mappers are for."""

OUTPUT_DIR_HELP = """Directory to save all validation results to."""

SIMPLIFY_HELP = """If set then simplify the output by dropping duplicate rows."""


class EnumsColumns:
    ENUM_NAME = "enumName"
    ENUM_VALUE = "enumValue"
    MAPPER_FILE_COUNT = "numMappers"
    MAPPER_FILE = "mapper"


class ValidateMappers(object):
    def __init__(self, source_schema: Union[str, Path, SchemaView]):
        self.source_schema = source_schema
        if not isinstance(self.source_schema, SchemaView):
            self.source_schema = SchemaView(self.source_schema)

    def test_enum_derivations_exist(self, mapper: dict):
        """Make sure that an enum derivation exists for all of the source slots used in the mapper (for the source
        slots that have enumeration(s) as a range).

        Args:
            mapper (dict): The mapper file to check.
        """
        for class_derivation in mapper["class_derivations"].values():
            if class_derivation.get("tree_root", False):
                continue
            # Go through all slot derivations
            for target_slot, slot_derivation in class_derivation[
                "slot_derivations"
            ].items():
                if "populated_from" in slot_derivation:
                    # For "populated_from" derivations, use the "populated_from" value as the slot name
                    source_slots = [slot_derivation["populated_from"]]
                elif "expr" in slot_derivation:
                    # For "expr" derivations, use all the slot names that are accessed through the
                    # "emap" global variable (eg. "emap.collection_device")
                    source_slots = get_used_slots(
                        slot_derivation["expr"], recognized_globals=["emap"]
                    )
                # Go through all the source slots, and make sure an enum derivation exists for all of
                # the slot's ranges that are enums.
                for source_slot in source_slots:
                    try:
                        slot_definition = self.source_schema.induced_slot(source_slot)
                    except Exception:
                        logger.error(
                            f"Source slot {source_slot} found in mapper does not exist"
                        )
                        continue
                    ranges = self.source_schema.slot_range_as_union(slot_definition)

                    # Make sure an enum derivation for all ranges exist
                    for rng in ranges:
                        if rng is None:
                            continue
                        if rng in self.source_schema.all_types():
                            continue
                        if not self.enum_derivation_exists(rng, mapper):
                            logger.error(
                                f"Enum derivation for {rng} does not exist ({source_slot=}, {target_slot=})"
                            )

    def enum_derivation_exists(self, enum_name: str, mapper: dict) -> bool:
        """Test to make sure an enum derivation exists for enum_name.

        Args:
            enum_name (str): The enum name to test.
            mapper (dict): The LinkML-Map schema to look for the enum derivation in.

        Returns:
            bool: True if an enum derivation for the enum_name exists in the mapper schema, False if it does
                not exist.
        """
        if "enum_derivations" not in mapper:
            return False

        matching_enums = [
            e
            for e in mapper["enum_derivations"].values()
            if e["populated_from"] == enum_name
        ]
        return len(matching_enums) > 0

    def get_all_enum_values(self, enum_name: str) -> List[str]:
        """Get all values that an enumeration can take on in the source schema.

        Args:
            enum_name (str): The enumeration name to get all permissible values for.

        Returns:
            List[str]: A list of all values that the enumeration can take on.
        """
        enum_defn = self.source_schema.get_enum(enum_name)
        return list(enum_defn["permissible_values"].keys())

    def test_enum_derivations_complete(
        self, mapper: dict, mapper_file: Union[str, Path]
    ) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        """Make sure all enumeration derivations are complete, and make sure there are no unrecognized enumeration source values
        in the derivations.

        Args:
            mapper (dict): The LinkML-Map schema to test. All enum derivations are tested.
            mapper_file (Union[str, Path]): The LinkML-Map schema file that the mapper is for. This is for informational purposes,
                we add the mapper_file to a column in the resulting DataFrames.

        Returns:
            Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]: Tuple of three DataFrames. The first is of missing enumeration
                values, the second is of unrecognized enumeration values, and the third is enumerations that have no
                permissible value derivations. The DataFrames have the columns in the data class EnumColumns.
        """
        unrecognized_df = pd.DataFrame()
        missing_df = pd.DataFrame()
        no_permissible_values_df = pd.DataFrame()

        # Go through all enum derivations
        for enum_derivation_name, enum_derivation in mapper["enum_derivations"].items():
            source_enum_name = enum_derivation["populated_from"]
            enum_values = self.get_all_enum_values(source_enum_name)

            if "permissible_value_derivations" in enum_derivation:
                # Go through all permissible value derivations of the current enum derivation and collect
                # all the source enum values that are being mapped
                sources = []
                for target_enum_value, permissible_value_derivation in enum_derivation[
                    "permissible_value_derivations"
                ].items():
                    if "populated_from" in permissible_value_derivation:
                        sources = sources + [
                            permissible_value_derivation["populated_from"]
                        ]
                    if "sources" in permissible_value_derivation:
                        sources = sources + list(
                            permissible_value_derivation["sources"]
                        )

                unrecognized_sources = [s for s in sources if s not in enum_values]
                missing_sources = [v for v in enum_values if v not in sources]

                if len(unrecognized_sources) > 0:
                    logger.error(
                        f"Unrecognized source enum mappings for enum {source_enum_name}: {unrecognized_sources}"
                    )
                    df = pd.DataFrame(
                        {
                            EnumsColumns.ENUM_NAME: [source_enum_name]
                            * len(unrecognized_sources),
                            EnumsColumns.ENUM_VALUE: unrecognized_sources,
                            EnumsColumns.MAPPER_FILE: [str(mapper_file)]
                            * len(unrecognized_sources),
                        }
                    )
                    unrecognized_df = pd.concat(
                        [unrecognized_df, df], ignore_index=True
                    )
                if len(missing_sources) > 0:
                    logger.error(
                        f"Missing source enum mappings for enum {source_enum_name}: {missing_sources}"
                    )
                    df = pd.DataFrame(
                        {
                            EnumsColumns.ENUM_NAME: [source_enum_name]
                            * len(missing_sources),
                            EnumsColumns.ENUM_VALUE: missing_sources,
                            EnumsColumns.MAPPER_FILE: [str(mapper_file)]
                            * len(missing_sources),
                        }
                    )
                    missing_df = pd.concat([missing_df, df], ignore_index=True)
            else:
                df = pd.DataFrame(
                    {
                        EnumsColumns.ENUM_NAME: [source_enum_name],
                        EnumsColumns.MAPPER_FILE: [str(mapper_file)],
                    }
                )
                no_permissible_values_df = pd.concat(
                    [no_permissible_values_df, df], ignore_index=True
                )
            # elif not enum_derivation.get("mirror_source", False):
            #     logger.error(
            #         f"Enum derivation has no permissible value derivations and mirror_source is False: {source_enum_name}"
            #     )

        return missing_df, unrecognized_df, no_permissible_values_df

    def concat_data_frames(
        self, dfs: List[pd.DataFrame], insert_blank_rows: bool = False
    ) -> pd.DataFrame:
        """Concatenate an array of DataFrames, and optionally put a blank row in between each non-empty
        DataFrame.

        Args:
            dfs (List[pd.DataFrame]): The list of DataFrames to concatenate.
            insert_blank_rows (bool, optional): If True, then a blank row is placed in between each non-empty
                DataFrame. If False then no blank row is inserted. Defaults to False.

        Returns:
            pd.DataFrame: The concatenated DataFrames.
        """
        # Drop empty DataFrames
        dfs = [df for df in dfs if len(df) > 0]

        if len(dfs) == 0:
            return pd.DataFrame()
        if len(dfs) == 1:
            return dfs[0]

        if insert_blank_rows:
            # Insert a blank row between each DataFrames in dfs
            blank_row = pd.DataFrame({dfs[0].columns[0]: [None]})
            for i in range(1, len(dfs))[::-1]:
                dfs.insert(i, blank_row)

        return pd.concat(dfs, ignore_index=True)

    def simplify_enum_df(self, df: pd.DataFrame) -> pd.DataFrame:
        """For a DataFrame that reports problems with enum derivations, that has the columns defined in EnumColumns,
        simplify the DataFrame by dropping duplicate rows (where ENUM_NAME and ENUM_VALUE columns are identical), and
        sort by ENUM_NAME and ENUM_VALUE. This makes it easier for the user to read the DataFrames.

        Args:
            df (pd.DataFrame): The DataFrame to simplify.

        Returns:
            pd.DataFrame: The simplified DataFrame. The original is left unchanged.
        """
        df = df.copy()

        if len(df) == 0:
            return df

        main_columns = []
        if EnumsColumns.ENUM_NAME in df.columns:
            main_columns.append(EnumsColumns.ENUM_NAME)
        if EnumsColumns.ENUM_VALUE in df.columns:
            main_columns.append(EnumsColumns.ENUM_VALUE)

        for group_name, group_df in df.groupby(main_columns):
            files = "; ".join(group_df[EnumsColumns.MAPPER_FILE])
            df.loc[group_df.index, EnumsColumns.MAPPER_FILE_COUNT] = len(group_df.index)
            df.loc[group_df.index, EnumsColumns.MAPPER_FILE] = files

        df = df.dropna(
            subset=main_columns,
            how="all",
            ignore_index=True,
        )
        df = df.drop_duplicates(main_columns)
        df = df.sort_values(main_columns).reset_index(drop=True)

        if EnumsColumns.ENUM_NAME in df.columns:
            dfs = [d for _, d in df.groupby([EnumsColumns.ENUM_NAME])]
            df = self.concat_data_frames(dfs, insert_blank_rows=True)
        return df

    def order_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """Order the columns of a DataFrame so that they are the same as the ordering in EnumsColumns.
        Additional columns not in EnumsColumns are placed at the end.

        Args:
            df (pd.DataFrame): The DataFrame to order the columns. A copy of this DataFrame is made
                with the original left unchanged.

        Returns:
            pd.DataFrame: The DataFrame with the columns ordered. The original df is left unchanged.
        """
        enums_columns = [
            getattr(EnumsColumns, c)
            for c in EnumsColumns.__dict__
            if not c.startswith("_")
        ]
        enums_columns = [c for c in enums_columns if c in df.columns]
        enums_columns = enums_columns + [
            c for c in df.columns if c not in enums_columns
        ]
        df = df[enums_columns]

        return df.copy()

    def validate(
        self,
        mappers_dir: Union[str, Path],
        output_dir: Union[str, Path],
        simplify: bool,
    ):
        """Do a full validation of all LinkML-Map schemas in the mapper directory, and output the results
        to the specified output directory.

        Args:
            mappers_dir (Union[str, Path]): Directory containing all LinkML-Map schemas to validate. All files
                with a yaml extension are validated.
            output_dir (Union[str, Path]): Directory to save the results to.
            simplify (bool): If True then simplify the resulting output by dropping duplicate rows.
        """
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)

        mappers_dir = Path(mappers_dir)
        files = [
            f
            for f in os.listdir(mappers_dir)
            if os.path.splitext(f)[1].lower() == ".yaml"
        ]
        unrecognized_dfs = []
        missing_dfs = []
        no_permissible_values_dfs = []
        for file in files:
            logger.info(f"Validating file {file}")
            with open(mappers_dir / file, "r") as f:
                mapper = yaml.safe_load(f)

            self.test_enum_derivations_exist(mapper)

            # Test if enum derivations are complete and for unrecognized enum values
            cur_missing_df, cur_unrecognized_df, cur_no_permissible_values_df = (
                self.test_enum_derivations_complete(mapper, file)
            )
            missing_dfs.append(cur_missing_df)
            unrecognized_dfs.append(cur_unrecognized_df)
            no_permissible_values_dfs.append(cur_no_permissible_values_df)

        # Combine and simplify the missing_dfs and unrecognized_dfs DataFrames
        missing_df = self.concat_data_frames(missing_dfs, insert_blank_rows=True)
        unrecognized_df = self.concat_data_frames(
            unrecognized_dfs, insert_blank_rows=True
        )
        no_permissible_values_df = self.concat_data_frames(
            no_permissible_values_dfs, insert_blank_rows=True
        )
        if simplify:
            missing_df = self.simplify_enum_df(missing_df)
            unrecognized_df = self.simplify_enum_df(unrecognized_df)
            no_permissible_values_df = self.simplify_enum_df(no_permissible_values_df)

        #  Order the columns
        missing_df = self.order_columns(missing_df)
        unrecognized_df = self.order_columns(unrecognized_df)
        no_permissible_values_df = self.order_columns(no_permissible_values_df)

        if output_dir:
            if len(missing_df):
                output_file = Path(output_dir) / "missing_enums.csv"
                logger.info(f"Saving missing enum value mappings to {output_file}")
                missing_df.to_csv(output_file, index=False)
            if len(unrecognized_df):
                output_file = Path(output_dir) / "unrecognized_enums.csv"
                logger.info(f"Saving unrecognized enum value mappings to {output_file}")
                unrecognized_df.to_csv(output_file, index=False)
            if len(no_permissible_values_df):
                output_file = Path(output_dir) / "no_permissible_values_enums.csv"
                logger.info(
                    f"Saving enums with no permissible value derivations to {output_file}"
                )
                no_permissible_values_df.to_csv(output_file, index=False)


@app.command(help=MAIN_HELP)
def main(
    mappers_dir: Annotated[
        Path, typer.Option(show_default=False, help=MAPPERS_DIR_HELP)
    ],
    source_schema: Annotated[
        Path, typer.Option(show_default=False, help=SOURCE_SCHEMA_HELP)
    ],
    output_dir: Annotated[Path, typer.Option(show_default=False, help=OUTPUT_DIR_HELP)],
    simplify: Annotated[bool, typer.Option(help=SIMPLIFY_HELP)] = True,
):
    val = ValidateMappers(source_schema)
    val.validate(mappers_dir, output_dir, simplify=simplify)


if __name__ == "__main__":
    if "get_ipython" in globals():
        opts = {
            # ODM v1
            # "mappers_dir": "../../gen/odm_v1_to_v2/mappers",
            # "source_schema": "../data/odm_v1/linkml/odm_v1.yaml",
            # "output_dir": "../../gen/validate/odm_v1",
            # NWSS
            # "mappers_dir": "../../gen/nwss_reporting_to_v2/mappers",
            # "source_schema": "../data/nwss_reporting/linkml/nwss_reporting.yaml",
            # "output_dir": "../../gen/validate/nwss_reporting",
            # PHA4GE
            "mappers_dir": "../../gen/pha4ge_to_v2/mappers",
            "source_schema": "../data/pha4ge/linkml/pha4ge.yaml",
            "output_dir": "../../gen/validate/pha4ge",
            "simplify": True,
        }
        main(**opts)
    else:
        app()
