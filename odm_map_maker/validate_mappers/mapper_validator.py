from typing import Union, List, Tuple, Annotated, Dict, Optional
from pathlib import Path
import os
import yaml
import pandas as pd
import typer

from linkml_runtime import SchemaView

from odm_map_maker.utils.logger import get_logger
from odm_map_maker.utils.mapper_utils import get_source_slots_from_slot_derivation
from odm_map_maker.utils.schema_utils import (
    get_class,
    get_enum_names_for_slot,
    get_permissible_values_from_enum_names,
)

logger = get_logger(__name__)

app = typer.Typer(
    pretty_exceptions_show_locals=False,
    rich_markup_mode="rich",
)


MAIN_HELP = """Validate mappers, testing to ensure all required enum derivations exist, that all permissible
values for the enum derivations exist, and that no unrecognized permissible values in the derivations exist."""

MAPPERS_DIR_HELP = """Directory containing all the LinkML-Map schemas to validate. All yaml files are tested."""

SOURCE_SCHEMA_HELP = """Path to the source LinkML schema that the mappers are for."""

TARGET_SCHEMA_HELP = """Path to the target LinkML schema that the mappers are for."""

OUTPUT_DIR_HELP = """Directory to save all validation results to."""

TAG_HELP = """If specified, then precede all the output file names with this
string, followed by a dash."""

SIMPLIFY_HELP = """If set then simplify the output by dropping duplicate rows."""


# Column names for the output DataFrames that contain the errors in the mappers
class EnumsColumns:
    SOURCE_CLASS = "sourceClass"
    SOURCE_SLOT = "sourceSlot"
    SOURCE_ENUM_NAME = "sourceEnumName"
    SOURCE_ENUM_VALUE = "sourceEnumValue"
    TARGET_CLASS = "targetClass"
    TARGET_SLOT = "targetSlot"
    TARGET_ENUM_NAME = "targetEnumName"
    TARGET_ENUM_VALUE = "targetEnumValue"
    MAPPER_FILE_COUNT = "numMappers"
    MAPPER_FILE = "mapper"


# Keys for the dictionaries containing information about enum mappings for function get_source_enum_to_target_enum_info
class SourceToTargetEnumInfoKeys:
    PERMISSIBLE_VALUES = "permissible_values"
    SOURCE_SLOTS = "source_slots"
    SOURCE_CLASSES = "source_classes"
    TARGET_ENUM_NAMES = "target_enum_names"


class ValidateMappers(object):
    def __init__(
        self,
        source_schema: Union[str, Path, SchemaView],
        target_schema: Union[str, Path, SchemaView],
    ):
        if not isinstance(source_schema, SchemaView):
            source_schema = SchemaView(source_schema)
        self.source_schema = source_schema

        if not isinstance(target_schema, SchemaView):
            target_schema = SchemaView(target_schema)
        self.target_schema = target_schema

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
                source_slots = get_source_slots_from_slot_derivation(
                    slot_derivation, recognized_globals=["emap"]
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

    def get_source_enum_to_target_enum_info(
        self, mapper: Dict, source_enum: str
    ) -> Dict[str, Dict[str, Dict[str, List[str]]]]:
        """From the specified LinkML-Map schema, get all slot mappings that map from the source enumeration to any slot
        in the target class, and collect the information about those mappings. The information includes a list of all
        enum values that the target slot can take on, all the source slots/classes that we map from, and all the
        enumeration names that the target slot has in its range.

        Args:
            mapper (Dict): The mapper to get the info from.
            source_enum (str): The source enumeration name to get the info for.

        Returns:
            Dict[str, Dict[str, Dict[str, List[str]]]]: A dictionary of the form:
                    info[target_class][target_slot][SourceToTargetEnumInfoKeys.*] = [values...]
                They values include the target permissible values, the target enumeration names of the
                target slot, and the source slots/classes.
        """
        info = {}

        # Go through the class derivations for all target classes
        for target_class, class_derivation in mapper["class_derivations"].items():
            if "populated_from" not in class_derivation:
                continue

            # Get the target class and source class names
            target_class = get_class(
                target_class, self.target_schema, ignore_case=False
            )
            source_class = class_derivation["populated_from"]

            # For the current derivation, go through all the slot derivations, determine which of those derivations
            # map from source_enum and get the info for them.
            for slot_derivation in class_derivation["slot_derivations"].values():
                # Get the target slot and the enums that are part of the target slot's range
                target_slot = slot_derivation["name"]
                target_enums = get_enum_names_for_slot(
                    target_class, target_slot, self.target_schema
                )
                # if not target_enums:
                #     continue

                # Get all the source slots that are part of the slot derivation
                source_slot_names = get_source_slots_from_slot_derivation(
                    slot_derivation, recognized_globals=["emap"]
                )

                # For all the source slots, if the slot has source_enum as part of its range then get the
                # info for the slot derivation
                for source_slot_name in source_slot_names:
                    # Get the enum name ranges for the source slot, if one of them is equal to source_enum then
                    # we get the info for the current slot derivation.
                    enum_names = get_enum_names_for_slot(
                        source_class, source_slot_name, self.source_schema
                    )
                    if not enum_names or source_enum not in enum_names:
                        continue

                    # For all the enumerations that are in the target slot's range, get all the permissible
                    # values of these enumerations and combine them into one list.
                    cur_permissible_values = get_permissible_values_from_enum_names(
                        target_enums, self.target_schema
                    )

                    # Add the info
                    if target_class not in info:
                        info[target_class] = {}
                    if target_slot not in info[target_class]:
                        info[target_class][target_slot] = {
                            SourceToTargetEnumInfoKeys.PERMISSIBLE_VALUES: [],
                            SourceToTargetEnumInfoKeys.SOURCE_SLOTS: [],
                            SourceToTargetEnumInfoKeys.SOURCE_CLASSES: [],
                            SourceToTargetEnumInfoKeys.TARGET_ENUM_NAMES: [],
                        }
                    info[target_class][target_slot][
                        SourceToTargetEnumInfoKeys.PERMISSIBLE_VALUES
                    ].extend(cur_permissible_values)
                    info[target_class][target_slot][
                        SourceToTargetEnumInfoKeys.SOURCE_SLOTS
                    ].append(source_slot_name)
                    info[target_class][target_slot][
                        SourceToTargetEnumInfoKeys.SOURCE_CLASSES
                    ].append(source_class)
                    info[target_class][target_slot][
                        SourceToTargetEnumInfoKeys.TARGET_ENUM_NAMES
                    ].extend(target_enums)
        return info

    def replace_blanks(self, values: List[str]) -> List[str]:
        return [v if v else "<blank>" for v in values]

    def validate_mapper(
        self, mapper: dict, mapper_file: Union[str, Path]
    ) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        """Run the validator on the specified LinkML-Map schema.

        We will check for unrecognized source or target enum values, incomplete permissible value derivations (ie.
        some source enum values are missing a mapping), and for empty permissible value derivations.

        Args:
            mapper (dict): The LinkML-Map schema to validate.
            mapper_file (Union[str, Path]): The LinkML-Map schema file that the mapper is for. This is for informational
                purposes, we add the mapper_file to a column in the resulting DataFrames so the user knows which files are
                affected by the errors.

        Returns:
            Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]: Tuple of five DataFrames containing
                reports of the results of the validation:
                    missing_source_enums_df: The source enum values that do not have a mapping (ie. they are missing from
                        a permissible_value_derivations block in the mapper)
                    unrecognized_source_enums_df: The source enum values found in a permissible_value_derivations that
                        are not valid enum values in the source schema.
                    unrecognized_target_enums_df: The target enum values found in a permissible_value_derivations that
                        are not valid enum values in the target schema.
                    empty_permissible_value_derivations_df: The permissible_value_derivations that are empty.
                    unrecognized_constant_values_df: The constant values, found within "expr" slots for a slot derivation,
                        that are invalid enumeration values for the target slot.
        """
        unrecognized_source_enum_values_df = pd.DataFrame()
        missing_source_enum_values_df = pd.DataFrame()
        empty_permissible_value_derivations_df = pd.DataFrame()
        unrecognized_target_enum_values_df = pd.DataFrame()
        unrecognized_constant_values_df = pd.DataFrame()

        # Go through all slot derivations and validate them
        for target_class, class_derivation in mapper["class_derivations"].items():
            target_class = get_class(
                target_class, self.target_schema, ignore_case=False
            )
            source_class = class_derivation.get("populated_from", None)
            if not source_class:
                continue
            for target_slot, slot_derivation in class_derivation[
                "slot_derivations"
            ].items():
                # Get the constant string value that the expr is for
                expr: Optional[str] = slot_derivation.get("expr", None)
                if not expr:
                    continue
                expr = expr.strip()
                if not (expr.startswith("'") and expr.endswith("'")) and not (
                    expr.startswith('"') and expr.endswith('"')
                ):
                    continue
                try:
                    target_value = yaml.safe_load(expr)
                except Exception:
                    continue

                # See if the target_value is a permissible value for the target slot
                target_enum_names = get_enum_names_for_slot(
                    target_class, target_slot, self.target_schema
                )
                if not target_enum_names:
                    continue
                permissible_values = get_permissible_values_from_enum_names(
                    target_enum_names, self.target_schema
                )
                if target_value in permissible_values:
                    continue

                # target_value is an invalid value for the target slot
                df = pd.DataFrame(
                    {
                        EnumsColumns.SOURCE_CLASS: [source_class],
                        EnumsColumns.TARGET_CLASS: [target_class],
                        EnumsColumns.TARGET_SLOT: [target_slot],
                        EnumsColumns.TARGET_ENUM_NAME: [", ".join(target_enum_names)],
                        EnumsColumns.TARGET_ENUM_VALUE: self.replace_blanks(
                            [target_value]
                        ),
                        EnumsColumns.MAPPER_FILE: [str(mapper_file)],
                    }
                )
                unrecognized_constant_values_df = pd.concat(
                    [unrecognized_constant_values_df, df], ignore_index=True
                )

        # Go through all enum derivations and validate them
        for enum_derivation_name, enum_derivation in mapper["enum_derivations"].items():
            source_enum_name = enum_derivation["populated_from"]
            allowable_source_enum_values = get_permissible_values_from_enum_names(
                [source_enum_name], self.source_schema
            )

            info = self.get_source_enum_to_target_enum_info(mapper, source_enum_name)
            if not info:
                # Format of info: info[target_class][target_slot][SourceToTargetEnumInfoKeys.*] = List[str]
                info = {
                    "": {
                        "": {
                            SourceToTargetEnumInfoKeys.SOURCE_SLOTS: [],
                            SourceToTargetEnumInfoKeys.SOURCE_CLASSES: [],
                            SourceToTargetEnumInfoKeys.TARGET_ENUM_NAMES: [],
                            SourceToTargetEnumInfoKeys.PERMISSIBLE_VALUES: [],
                        }
                    }
                }

            for target_class, target_slots_permissible_values in info.items():
                for (
                    target_slot,
                    target_permissible_values_info,
                ) in target_slots_permissible_values.items():
                    source_slots = target_permissible_values_info[
                        SourceToTargetEnumInfoKeys.SOURCE_SLOTS
                    ]
                    source_classes = target_permissible_values_info[
                        SourceToTargetEnumInfoKeys.SOURCE_CLASSES
                    ]
                    target_enum_names = target_permissible_values_info[
                        SourceToTargetEnumInfoKeys.TARGET_ENUM_NAMES
                    ]
                    permissible_values = target_permissible_values_info[
                        SourceToTargetEnumInfoKeys.PERMISSIBLE_VALUES
                    ]
                    global_df = pd.DataFrame(
                        {
                            EnumsColumns.SOURCE_CLASS: [", ".join(source_classes)],
                            EnumsColumns.SOURCE_SLOT: [", ".join(source_slots)],
                            EnumsColumns.SOURCE_ENUM_NAME: [source_enum_name],
                            EnumsColumns.TARGET_CLASS: [target_class],
                            EnumsColumns.TARGET_SLOT: [target_slot],
                            EnumsColumns.MAPPER_FILE: [str(mapper_file)],
                        }
                    )

                    def add_global_df(df: pd.DataFrame) -> pd.DataFrame:
                        new_global_df = pd.concat(
                            [global_df] * max(1, len(df)), ignore_index=True
                        )
                        return pd.concat([df, new_global_df], axis=1, join="inner")

                    if "permissible_value_derivations" in enum_derivation:
                        # Go through all permissible value derivations of the current enum derivation and collect
                        # all the source enum values (sources) that are being mapped as well as all target enum
                        # values (targets_to_sources)
                        sources = []
                        targets_to_sources = []
                        for (
                            target_enum_value,
                            permissible_value_derivation,
                        ) in enum_derivation["permissible_value_derivations"].items():
                            if "populated_from" in permissible_value_derivation:
                                cur_sources = [
                                    permissible_value_derivation["populated_from"]
                                ]
                            elif "sources" in permissible_value_derivation:
                                cur_sources = permissible_value_derivation["sources"]
                            sources += cur_sources
                            targets_to_sources.append((target_enum_value, cur_sources))

                        # Get the unrecognized source enum values, and the source enum values that have no mapping
                        unrecognized_source_enum_values = [
                            s for s in sources if s not in allowable_source_enum_values
                        ]
                        targets_of_unrecognized_source_enum_values = [
                            t[0]
                            for t in targets_to_sources
                            if set(t[1]).intersection(unrecognized_source_enum_values)
                        ]
                        missing_source_enum_values = [
                            v for v in allowable_source_enum_values if v not in sources
                        ]

                        # Add the unrecognized source enum values to the report DataFrame
                        if len(unrecognized_source_enum_values) > 0:
                            df = pd.DataFrame(
                                {
                                    EnumsColumns.SOURCE_ENUM_VALUE: self.replace_blanks(
                                        unrecognized_source_enum_values
                                    ),
                                    EnumsColumns.TARGET_ENUM_VALUE: self.replace_blanks(
                                        targets_of_unrecognized_source_enum_values
                                    ),
                                }
                            )
                            df = add_global_df(df)
                            unrecognized_source_enum_values_df = pd.concat(
                                [unrecognized_source_enum_values_df, df],
                                ignore_index=True,
                            )
                        # Add the missing source enum values that do not have a derivation to the report DataFrame
                        if len(missing_source_enum_values) > 0:
                            df = pd.DataFrame(
                                {
                                    EnumsColumns.SOURCE_ENUM_VALUE: self.replace_blanks(
                                        missing_source_enum_values
                                    ),
                                }
                            )
                            df = add_global_df(df)
                            missing_source_enum_values_df = pd.concat(
                                [missing_source_enum_values_df, df], ignore_index=True
                            )

                        # Get the unrecognized target enum values and add them to the report DataFrame
                        # info is in the format. If permissible_values is empty then it means the
                        # target slot does not have an enum range (eg. it has a string range), and so
                        # all target values are allowed
                        if target_slot and permissible_values:
                            unrecognized_target_enum_values = [
                                v[0]
                                for v in targets_to_sources
                                if v[0] not in permissible_values
                            ]
                            sources_of_unrecognized_target_enum_values = [
                                v[1]
                                for v in targets_to_sources
                                if v[0] not in permissible_values
                            ]
                            sources_of_unrecognized_target_enum_values = [
                                v
                                for v_top in sources_of_unrecognized_target_enum_values
                                for v in v_top
                            ]

                            # Add the unrecognized target enum values to the report DataFrame
                            if unrecognized_target_enum_values:
                                df = pd.DataFrame(
                                    {
                                        EnumsColumns.SOURCE_ENUM_VALUE: [
                                            ", ".join(
                                                self.replace_blanks(
                                                    sources_of_unrecognized_target_enum_values
                                                )
                                            )
                                        ],
                                        EnumsColumns.TARGET_ENUM_NAME: [
                                            ", ".join(target_enum_names)
                                        ],
                                        EnumsColumns.TARGET_ENUM_VALUE: [
                                            ", ".join(
                                                self.replace_blanks(
                                                    unrecognized_target_enum_values
                                                )
                                            )
                                        ],
                                    }
                                )
                                df = add_global_df(df)
                                unrecognized_target_enum_values_df = pd.concat(
                                    [unrecognized_target_enum_values_df, df],
                                    ignore_index=True,
                                )
                    else:
                        df = global_df.copy()
                        empty_permissible_value_derivations_df = pd.concat(
                            [empty_permissible_value_derivations_df, df],
                            ignore_index=True,
                        )
            # elif not enum_derivation.get("mirror_source", False):
            #     logger.error(
            #         f"Enum derivation has no permissible value derivations and mirror_source is False: {source_enum_name}"
            #     )

        return (
            missing_source_enum_values_df,
            unrecognized_source_enum_values_df,
            unrecognized_target_enum_values_df,
            empty_permissible_value_derivations_df,
            unrecognized_constant_values_df,
        )

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

    def simplify_enum_df(
        self, df: pd.DataFrame, sort_by: List[str] = [EnumsColumns.SOURCE_ENUM_NAME]
    ) -> pd.DataFrame:
        """For a DataFrame that reports problems with enum derivations, that has the columns defined in EnumColumns,
        simplify the DataFrame by merging rows that are duplicates other than the EnumsColumns.MAPPER_FILE column. Within
        the grouped rows the values under EnumsColumns.MAPPER_FILE are combined (separated by a semi-colon). This makes
        it easier for the user to read the DataFrames.

        Args:
            df (pd.DataFrame): The DataFrame to simplify.
            sort_by (List[str]): The columns to sort the final data by. (Defaults to [EnumsColumns.SOURCE_ENUM_NAME])

        Returns:
            pd.DataFrame: The simplified DataFrame. The original is left unchanged.
        """
        df = df.copy()

        if len(df) == 0:
            return df

        group_by = [
            getattr(EnumsColumns, c) for c in dir(EnumsColumns) if not c.startswith("_")
        ]
        group_by = [
            c for c in group_by if c in df.columns and c != EnumsColumns.MAPPER_FILE
        ]

        # Go through all the groups and merge the rows within each group. We also add a column that contains
        # the size of each group, and add a column that lists all mapper files that the rows in the group
        # apply to.
        for group_name, group_df in df.groupby(group_by):
            files = "; ".join(group_df[EnumsColumns.MAPPER_FILE])
            df.loc[group_df.index, EnumsColumns.MAPPER_FILE_COUNT] = len(group_df.index)
            df.loc[group_df.index, EnumsColumns.MAPPER_FILE] = files

        # Drop all duplicate rows and sort by group_by
        df = df.dropna(
            subset=group_by,
            how="all",
            ignore_index=True,
        )
        df = df.drop_duplicates(group_by)
        df = df.sort_values(group_by).reset_index(drop=True)

        # Sort by sort_by
        sort_by = [c for c in sort_by if c in df.columns]
        if sort_by:
            # Organize/sort the final DataFrame by the enum name
            dfs = [d for _, d in df.groupby(sort_by)]
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
        output_tag: Optional[str],
        simplify: bool,
    ):
        """Do a full validation of all LinkML-Map schemas in the mapper directory, and output the results
        to the specified output directory.

        Args:
            mappers_dir (Union[str, Path]): Directory containing all LinkML-Map schemas to validate. All files
                with a yaml extension are validated.
            output_dir (Union[str, Path]): Directory to save the results to.
            output_tag (Optional[str]): If not empty, then precede all the output file names with
                this string, followed by a dash.
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
        files = sorted(files)

        unrecognized_source_enums_dfs = []
        unrecognized_target_enums_dfs = []
        missing_source_enums_dfs = []
        empty_permissible_value_derivations_dfs = []
        unrecognized_constant_values_dfs = []
        for file in files:
            logger.info(f"Validating file {file}")
            with open(mappers_dir / file, "r") as f:
                mapper = yaml.safe_load(f)

            self.test_enum_derivations_exist(mapper)

            # Test if enum derivations are complete and for unrecognized enum values
            (
                cur_missing_source_enums_df,
                cur_unrecognized_source_enums_df,
                cur_unrecognized_target_enums_df,
                cur_empty_permissible_value_derivations_df,
                cur_unrecognized_constant_values_df,
            ) = self.validate_mapper(mapper, file)
            missing_source_enums_dfs.append(cur_missing_source_enums_df)
            unrecognized_source_enums_dfs.append(cur_unrecognized_source_enums_df)
            unrecognized_target_enums_dfs.append(cur_unrecognized_target_enums_df)
            empty_permissible_value_derivations_dfs.append(
                cur_empty_permissible_value_derivations_df
            )
            unrecognized_constant_values_dfs.append(cur_unrecognized_constant_values_df)

        # Combine and simplify the missing_source_enums_dfs, unrecognized_source_enums_dfs, and unrecognized_target_enums_dfs DataFrames
        missing_source_enums_df = self.concat_data_frames(
            missing_source_enums_dfs, insert_blank_rows=True
        )
        unrecognized_source_enums_df = self.concat_data_frames(
            unrecognized_source_enums_dfs, insert_blank_rows=True
        )
        unrecognized_target_enums_df = self.concat_data_frames(
            unrecognized_target_enums_dfs, insert_blank_rows=True
        )
        empty_permissible_value_derivations_df = self.concat_data_frames(
            empty_permissible_value_derivations_dfs, insert_blank_rows=True
        )
        unrecognized_constant_values_df = self.concat_data_frames(
            unrecognized_constant_values_dfs, insert_blank_rows=True
        )

        if simplify:
            missing_source_enums_df = self.simplify_enum_df(missing_source_enums_df)
            unrecognized_source_enums_df = self.simplify_enum_df(
                unrecognized_source_enums_df
            )
            unrecognized_target_enums_df = self.simplify_enum_df(
                unrecognized_target_enums_df, sort_by=[EnumsColumns.TARGET_ENUM_VALUE]
            )
            empty_permissible_value_derivations_df = self.simplify_enum_df(
                empty_permissible_value_derivations_df
            )
            unrecognized_constant_values_df = self.simplify_enum_df(
                unrecognized_constant_values_df
            )

        #  Order the columns
        missing_source_enums_df = self.order_columns(missing_source_enums_df)
        unrecognized_source_enums_df = self.order_columns(unrecognized_source_enums_df)
        unrecognized_target_enums_df = self.order_columns(unrecognized_target_enums_df)
        empty_permissible_value_derivations_df = self.order_columns(
            empty_permissible_value_derivations_df
        )
        unrecognized_constant_values_df = self.order_columns(
            unrecognized_constant_values_df
        )

        if output_dir:
            output_tag = f"{output_tag}-" if output_tag else ""
            if len(missing_source_enums_df):
                output_file = (
                    Path(output_dir) / f"{output_tag}missing_source_enum_values.csv"
                )
                logger.info(
                    f"Saving missing source enum value mappings to {output_file}"
                )
                missing_source_enums_df.to_csv(output_file, index=False)
            if len(unrecognized_source_enums_df):
                output_file = (
                    Path(output_dir)
                    / f"{output_tag}unrecognized_source_enum_values.csv"
                )
                logger.info(
                    f"Saving unrecognized source enum value mappings to {output_file}"
                )
                unrecognized_source_enums_df.to_csv(output_file, index=False)
            if len(unrecognized_target_enums_df):
                output_file = (
                    Path(output_dir)
                    / f"{output_tag}unrecognized_target_enum_values.csv"
                )
                logger.info(
                    f"Saving unrecognized target enum value mappings to {output_file}"
                )
                unrecognized_target_enums_df.to_csv(output_file, index=False)
            if len(empty_permissible_value_derivations_df):
                output_file = (
                    Path(output_dir)
                    / f"{output_tag}empty_permissible_value_derivations.csv"
                )
                logger.info(
                    f"Saving enums with no permissible value derivations to {output_file}"
                )
                empty_permissible_value_derivations_df.to_csv(output_file, index=False)
            if len(unrecognized_constant_values_df):
                output_file = (
                    Path(output_dir) / f"{output_tag}unrecognized_constant_values.csv"
                )
                logger.info(f"Saving unrecognized constant values to {output_file}")
                unrecognized_constant_values_df.to_csv(output_file, index=False)


@app.command(help=MAIN_HELP)
def main(
    mappers_dir: Annotated[
        Path, typer.Option(show_default=False, help=MAPPERS_DIR_HELP)
    ],
    source_schema: Annotated[
        Path, typer.Option(show_default=False, help=SOURCE_SCHEMA_HELP)
    ],
    target_schema: Annotated[
        Path, typer.Option(show_default=False, help=TARGET_SCHEMA_HELP)
    ],
    output_dir: Annotated[Path, typer.Option(show_default=False, help=OUTPUT_DIR_HELP)],
    tag: Annotated[str, typer.Option(show_default=False, help=TAG_HELP)] = None,
    simplify: Annotated[bool, typer.Option(help=SIMPLIFY_HELP)] = True,
):
    val = ValidateMappers(source_schema, target_schema)
    val.validate(mappers_dir, output_dir, output_tag=tag, simplify=simplify)


if __name__ == "__main__":
    app()
