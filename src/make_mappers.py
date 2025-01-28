# %%
"""
Creates the LinkML mapper config files for mapping from one database format (eg. NWSS) to
another (eg. ODM v2). This is configured with CSV files (usually extracted from Excel files) that
specify both the mappings between source and target classes, wide-to-long columns, and enumeration
mappings.
"""

import argparse
import pandas as pd
from pathlib import Path
from typing import Union, List, Dict, Optional, Any
import os
import yaml
import json
import re

from linkml_runtime import SchemaView
from linkml_runtime.linkml_model.meta import SchemaDefinition
from linkml_runtime.utils.schema_as_dict import schema_as_dict

from utils.general_utils import (
    read_data_frame,
    strip_whitespace,
    get_logger,
    order_columns,
    EMPTY_PERMISSIBLE_VALUE,
    TREE_ROOT_CLASS_NAME,
)
from utils.schema_utils import (
    get_enum_names_for_slot,
    get_enum_name_with_permissible_value,
    remove_ontology_id,
)
from utils.mapper_utils import (
    select_required_enum_derivations,
    expand_wide_derivations,
    get_variable_reference,
    MappingColumns,
    is_wide_target_value_slot,
    is_wide_target_expr_slot,
    any_wide_slot_name,
    get_blank_class_derivation,
    cleanup_slot_name,
    CONFIG_READ_KWARGS,
)
from utils.auto_id import add_auto_ids_to_schema

logger = get_logger(__name__)


def extract_class_derivations(
    maps_df: pd.DataFrame,
    source_schema: SchemaView,
    source_slot_format_operations: Optional[Union[str, List[str]]],
    target_slot_format_operations: Optional[Union[str, List[str]]],
) -> Dict[str, Dict[str, Dict]]:
    """Extract all class derivations from DataFraome from the the mapping file.

    Args:
        maps_df (pd.DataFrame): The mapping DataFrame loaded from the mapping specification file.
        source_schema (SchemaView): The schema that acts as the source for all the mappings (eg. schema
            for NWSS or ODM v1)
        source_slot_format_operations (Optional[Union[str, List[str]]], optional): Formatting options to apply to
            all slot names, found in the configuration file, for the source schema.
        target_slot_format_operations (Optional[Union[str, List[str]]], optional): Formatting options to apply to
            all slot names, found in the configuration file, for the target schema.

    Raises:
        ValueError: An error occurred due to problems with the mapping data.

    Returns:
        Dict[str, Dict[str, Dict]]: A dictionary with a separate key for each source class. Within each source class
            is a key for each target class that acts as the class derivation. Example:
                {
                    "nwss_reporting": {
                        "sites": {
                            "name": "sites",
                            "populated_from": "nwss_reporting",
                            "slot_derivations": {
                                ...
                            }
                        },
                        "other_target_class": { ... },
                        ...
                    }
                    "other_source_class" : { ... },
                    ...
                }
    """
    if maps_df is None:
        return {}

    # This dictionary has a separate key for each source class. Within each source class there is a key for each target class
    # that forms the actual class derivation
    all_class_derivations: Dict[str, Dict[str, Dict]] = {}
    for _, row in maps_df.iterrows():
        # Get all the data from the row
        source_class = row[MappingColumns.SOURCE_CLASS]
        source_slot = row[MappingColumns.SOURCE_SLOT]
        target_class = row[MappingColumns.TARGET_CLASS]
        target_slot = row[MappingColumns.TARGET_SLOT]
        custom_data = row[MappingColumns.CUSTOM_DATA]
        target_expr = row[MappingColumns.TARGET_EXPR]

        if pd.isna(custom_data):
            custom_data = None
        if pd.isna(target_expr):
            target_expr = None

        # Make sure the row's source class exists in the source schema
        if source_class not in source_schema.all_classes():
            logger.error(
                f"Found source class '{source_class}' in mapping data but class does not exist in source schema, ignoring row"
            )
            continue

        # Get the dictionary for the source_class. Within this dictionary are keys from each target class.
        if source_class not in all_class_derivations:
            all_class_derivations[source_class] = {}
        source_class_derivations = all_class_derivations[source_class]

        # Get the derivation targeting the target_class
        if target_class not in source_class_derivations:
            source_class_derivations[target_class] = get_blank_class_derivation(
                source_class, target_class
            )
        slot_derivations = source_class_derivations[target_class]["slot_derivations"]

        if custom_data or target_expr:
            new_dict = {
                "name": target_slot,
            }
            # The MappingColumns.CUSTOM_DATA field is set for the current row. This is a dictionary that we merge to the target_slot derivation.
            if custom_data:
                new_dict.update(json.loads(custom_data))
            if target_expr:
                new_dict["expr"] = target_expr
            if target_slot in slot_derivations:
                # The slot derivation for target_slot already exists (ie. it was added in a previous row of maps_df). Here we make sure
                # that the slot derivation for target_slot will be left unchanged.
                if slot_derivations[target_slot] != new_dict:
                    raise ValueError(
                        f"Target slot '{target_slot}' in target class '{target_class}' from source class '{source_class}' already exists in slot_derivations but has different custom fields (expected '{new_dict}' but found '{slot_derivations[target_slot]}')"
                    )
            slot_derivations[target_slot] = new_dict
        else:
            # Add the slot derivation for target_slot (populating from source_slot)
            if source_slot not in source_schema.class_slots(source_class):
                raise ValueError(
                    f"Found source slot '{source_slot}' (in source class '{source_class}') in mapping data that does not exist in the source schema, for row:\n{row}"
                )
            if target_slot in slot_derivations:
                if "populated_from" not in slot_derivations[target_slot]:
                    raise ValueError(
                        f"Target slot '{target_slot}' in target class '{target_class}' from source class '{source_class}' already exists in slot_derivations but has different populated_from fields (expected source slot '{source_slot}' but found Empty)"
                    )
                if slot_derivations[target_slot]["populated_from"] != source_slot:
                    raise ValueError(
                        f"Target slot '{target_slot}' in target class '{target_class}' from source class '{source_class}' already exists in slot_derivations but has different populated_from fields (expected source slot '{source_slot}' but found '{slot_derivations[target_slot]['populated_from']}')"
                    )
            slot_derivations[target_slot] = {
                "name": target_slot,
                "populated_from": source_slot,  # cleanup_slot_name(source_slot),
            }

    return all_class_derivations


def add_ontoid_to_enum_value(
    schema: SchemaView, enum_name: str, enum_value: str
) -> str:
    """Add an ontology ID to an enum value, if an ontology ID is present for that enum value
    in the schema. For example, an enum value of "degree Celsius (C)" might be changed to
    "degree Celsius (C) [UO:0000027]".

    Args:
        schema (SchemaView): The schema the enum value belongs to.
        enum_name (str): The enumeration name that the enum value belongs to.
        enum_value (str): The enum value to an ontology ID to, if the ontology ID is present
            in the schema.

    Returns:
        str: The enumeration value, possibly with an ontology ID added to it.
    """
    if not enum_name:
        return enum_value
    enum_defn = schema.get_enum(enum_name)
    if not enum_defn:
        return enum_value
    for permissible_value in enum_defn.permissible_values.keys():
        if remove_ontology_id(str(permissible_value)) == enum_value:
            return permissible_value
    return enum_value


def extract_enum_derivations(
    maps_df: pd.DataFrame,
    source_schema: SchemaView,
    target_schema: SchemaView,
    source_slot_format_operations: Optional[Union[str, List[str]]],
    target_slot_format_operations: Optional[Union[str, List[str]]],
) -> Dict[str, Dict[str, Dict]]:
    """Extract all enum derivations found within the mapping DataFrame.

    Args:
        maps_df (pd.DataFrame): The mapping DataFrame that contains the information for mapping from the
            source to target schemas. This can be either a maps tab, an enums tab, or a wide tab (which have been
            prepared with prepare_maps_df, prepare_enums_df, and prepare_wide_df).
        source_schema (SchemaView): The source schema for the mapping.
        target_schema (SchemaView): The target schema for the mapping.
        source_slot_format_operations (Optional[Union[str, List[str]]], optional): Formatting options to apply to
            all slot names, found in the configuration file, for the source schema.
        target_slot_format_operations (Optional[Union[str, List[str]]], optional): Formatting options to apply to
            all slot names, found in the configuration file, for the target schema.

    Raises:
        ValueError: _description_

    Returns:
        Dict[str, Dict[str, Dict]]: A dictionary where in the form
            return_value[source_class_name][target_class_name] = { all_derivations }. The items
            at return_value[""][""] have no source class and target class name specified.
            Example:
                    {
                        "nwss" : {
                            "protocolSteps" : {
                                "methods[protocolSteps_method]": {
                                    "name": "methods[protocolSteps_method]",
                                    "mirror_source": false,
                                    "populated_from": "vs_pcr_type",
                                    "permissible_value_derivations": { ... }
                                },
                                "other_target_enum": {
                                    "name": "other_target_enum",
                                    "mirror_source": false,
                                    "populated_from": "source_set",
                                    "permissible_value_derivations": { ... }
                                },
                                ...
                            }
                        },
                        "other_source_class" : { ... }
                    }
    """
    if maps_df is None:
        return {}

    # all_enum_derivations[source_class][target_class] are all enum derivations for the source
    # class to the target class.
    # all_enum_derivations[""][""] are all enum derivations where the source class and target class
    # are not specified (ie. applies to all source/target class pairs).
    # Enum derivations where source_class and target_class are specified take precedence over enum
    # derivations where source_class and target_class are "".
    all_enum_derivations: Dict[str, Dict[str, Dict]] = {}
    for _, row in maps_df.iterrows():
        # Get all the row's data
        source_class = row.get(MappingColumns.SOURCE_CLASS, "")
        source_slot = row.get(MappingColumns.SOURCE_SLOT, "")
        source_enum_name = row.get(MappingColumns.SOURCE_ENUM, "")
        source_enum_value = row[MappingColumns.SOURCE_VALUE]
        target_class = row.get(MappingColumns.TARGET_CLASS, "")
        target_slot = row.get(MappingColumns.TARGET_SLOT, "")
        target_enum_name = row.get(MappingColumns.TARGET_ENUM, "")
        target_enum_value = row[MappingColumns.TARGET_VALUE]

        variable_match = get_variable_reference(
            target_enum_value,
            source_schema,
            format_operations=source_slot_format_operations,
        )

        # If variable_match had a match (in the form {{variable_match}}, then it means we copy a source slot to the target slot,
        # so we don't need an enum derivation.
        if variable_match is not None:
            continue

        # Convert NA values to ""
        if pd.isna(source_enum_value):
            source_enum_value = ""
        if pd.isna(target_enum_value):
            target_enum_value = ""

        # If both the source enum value and target enum value are empty then this row is not an enumeration, so continue to next loop
        if source_enum_value == "" and target_enum_value == "":
            continue

        # Replace EMPTY_PERMISSIBLE_VALUE with ""
        if source_enum_value == EMPTY_PERMISSIBLE_VALUE:
            source_enum_value = ""
        if target_enum_value == EMPTY_PERMISSIBLE_VALUE:
            target_enum_value = ""

        # Get source enumeration name (if empty) based on the source class and slot
        # orig_source_enum_value = source_enum_value
        if not source_enum_name:
            # Get the source enum name based on the range of the slot (there might be multiple enums for the range)
            source_enum_names = get_enum_names_for_slot(
                source_class, source_slot, source_schema
            )
            if not source_enum_names:
                raise ValueError(
                    f"Slot is not an enumeration for source class '{source_class}' and source slot '{source_slot}' (source_enum_value='{source_enum_value}', target_class='{target_class}', target_slot='{target_slot}', target_enum_value='{target_enum_value}')"
                )
            # Find the first source enumeration that contains source_enum_value, use it as the source enum
            source_enum_name = get_enum_name_with_permissible_value(
                source_enum_names,
                source_enum_value,
                source_schema,
                with_ontology_id=True,
            )
            if not source_enum_name:
                source_enum_name = source_enum_names[0]
                logger.error(
                    f"No source enumeration found for {source_class=}, {source_slot=} from slot range(s) {source_enum_names=} that has a permissible {source_enum_value=} ({target_class=}, {target_slot=}). Using source enumeration name '{source_enum_name}'"
                )
                # raise ValueError(
                #     f"No source enumeration found for {source_class=}, {source_slot=} from slot range(s) {source_enum_names=} that has a permissible {source_enum_value=} ({target_class=}, {target_slot=})"
                # )
            # if source_enum_name:
            #     print("!!!!REMOVE!") # For removing ontology identifier
            #     source_enum_defn = source_schema.get_enum(source_enum_name)
            #     if source_enum_value in source_enum_defn.permissible_values:
            #         source_enum_value_defn = source_enum_defn.permissible_values[source_enum_value]
            #         if "old_name" in source_enum_value_defn:
            #             orig_source_enum_value = source_enum_value_defn["old_name"]
            #     else:
            #         logger.error(f"Source enum value '{source_enum_value}' not found in source enum '{source_enum_name}'")
        # print("!!!!REMOVE!") # For removing ontology identifier
        # source_enum_value = orig_source_enum_value

        # Get the target enumeration name based on the target class and slot
        if target_class and target_slot:
            target_enum_names = get_enum_names_for_slot(
                target_class, target_slot, target_schema
            )
            if target_enum_names:
                target_enum_name = get_enum_name_with_permissible_value(
                    target_enum_names,
                    target_enum_value,
                    target_schema,
                    with_ontology_id=True,
                )
                if not target_enum_name:
                    target_enum_name = target_enum_names[0]
                    logger.error(
                        f"No target enumeration found for {target_class=}, {target_slot=} from slot range(s) {target_enum_names=} that has a permissible value {target_enum_value=} ({source_class=}, {source_slot=}). Using target enumeration name '{target_enum_name}'"
                    )
                    # raise ValueError(
                    #     f"No target enumeration found for {target_class=}, {target_slot=} from slot range(s) {target_enum_names=} that has a permissible value {target_enum_value=} ({source_class=}, {source_slot=})"
                    # )
            else:
                # If there is no target enum name (eg. we're mapping from a source slot that is an enum to a target slot that is not an
                # enum), then we create a unique target enum name to use. Target enum names can be anything, they are just placeholders
                # (but source enum names must be correct).
                target_enum_name = f"{target_slot}_from_{source_enum_name}"
        # If no target enum name is given create a fake name
        if not target_enum_name:
            target_enum_name = (
                f"{target_schema.schema.name}_enum_from_{source_enum_name}"
            )
        if not target_enum_name:
            raise ValueError(
                f"At least one of target enumeration or target class/target slot must be specified for enumeration mapping from source class '{source_class}', source slot '{source_slot}', source enum '{source_enum_name}'"
            )

        # Add an ontology ID to the enum values if the schema has ontology IDs appended to the
        # enum values
        source_enum_value = add_ontoid_to_enum_value(
            source_schema, source_enum_name, source_enum_value
        )
        target_enum_value = add_ontoid_to_enum_value(
            target_schema, target_enum_name, target_enum_value
        )

        # Get the enum derivations dictionary for the current source_class and target_class
        if source_class not in all_enum_derivations:
            all_enum_derivations[source_class] = {}
        source_enum_derivations = all_enum_derivations[source_class]
        if target_class not in source_enum_derivations:
            source_enum_derivations[target_class] = {}
        cur_enum_derivations = source_enum_derivations[target_class]

        # Add the current enum derivation if missing, we'll add the permissible value derivations later
        if target_enum_name not in cur_enum_derivations:
            cur_enum_derivations[target_enum_name] = {
                "name": target_enum_name,
                "mirror_source": False,
                "populated_from": source_enum_name,
                "permissible_value_derivations": {},
            }
        # Get the enum derivation for the target enum
        enum_derivation = cur_enum_derivations[target_enum_name]
        if enum_derivation["populated_from"] != source_enum_name:
            raise ValueError(
                f"Enum derivation for {source_class=}, {target_class=}, {target_slot=}, {target_enum_name=} already exists but does not have a matching populated_from field (expected '{source_enum_name}' but found '{enum_derivation['populated_from']}')"
            )

        # Add the permissible value derivation. Derivation is from source_enum_value to target_enum_value
        # If there is already a permissible value derivation for target_enum_value, then we add the
        # source_enum_value to the permissible value derivation's "sources" field. If there isn't yet a
        # derivation then we add it to the "populated_from" field. The "sources" array field allows for
        # having multiple populated_from values.
        permissible_value_derivations = enum_derivation["permissible_value_derivations"]
        if target_enum_value in permissible_value_derivations:
            # The target_enum_value already has a derivation.
            # If source_enum_value is equal to the "populated_from" field, then we do nothing
            # Otherwise we move "populated_from" to "sources", and also add source_enum_value to "sources"
            sub_dict = permissible_value_derivations[target_enum_value]
            if (
                "sources" not in sub_dict
                and sub_dict["populated_from"] != source_enum_value
            ):
                sub_dict["sources"] = [sub_dict["populated_from"]]
                del sub_dict["populated_from"]
            if "sources" in sub_dict and source_enum_value not in sub_dict["sources"]:
                sub_dict["sources"].append(source_enum_value)
        else:
            permissible_value_derivations[target_enum_value] = {
                "name": target_enum_value,
                "populated_from": source_enum_value,
            }

    return all_enum_derivations


def apply_selectors_to_df(
    df: pd.DataFrame, selectors: Optional[List[str]]
) -> pd.DataFrame:
    """Apply selectors to the DataFrame, dropping rows where the selectors do not match properly.

    For a given value of selectors in the data, we separate the negated selectors from the
    non-negated selectors. The following two conditions must pass:

    1. For negated selectors: None of these selectors must have been specified from
    in the `selectors` parameter (ie. we perform an AND operation for all negated
    selectors). If there are no negated selectors then this rule always passes.
    2. For non-negated selectors: Any of these selectors must have been specified
    in the `selectors` parameter (ie. we perform an OR operation for all non-negated
    selectors). If there are no non-negated selectors then this rule always
    passes.

    Following the above rules, if the data has a row that is blank in the `selectors` column,
    then that row is always retained.

    Args:
        df (pd.DataFrame): The DataFrame to drop rows from based on the selectors parameter. A copy of this
            DataFrame is made and the original is left unchanged.
        selectors (Optional[List[str]]): The selectors specifying which rows to retain or drop.

    Returns:
        pd.DataFrame: The DataFrame with rows dropped according to the rules described above.
    """
    if len(df) == 0:
        return df.copy()
    df = df.copy()
    if MappingColumns.SELECTORS not in df.columns:
        df[MappingColumns.SELECTORS] = None
    if pd.isna(selectors):
        selectors = []
    exclude_selectors = [s.lstrip("!").strip() for s in selectors if s.startswith("!")]
    selectors = [s.strip() for s in selectors if not s.startswith("!")]

    # Expand the selectors (in the DataFrame) from a comma-separated string to a list of strings
    def _expand_selectors(v: Any) -> List[str]:
        if pd.isna(v):
            return []
        v = str(v)
        v = v.split(",")
        v = [x.strip() for x in v]
        return v

    df[MappingColumns.SELECTORS] = df[MappingColumns.SELECTORS].map(_expand_selectors)

    # Do the matching of selectors
    def _should_keep_row(df_selectors: List[str]) -> bool:
        # If the data has no selectors, then always include the row
        if len(df_selectors) == 0:
            return True
        # If any exclude_selector is found, then do not include the row
        if len([v for v in df_selectors if v in exclude_selectors]) > 0:
            return False
        # If any selector is not found, then do not include the row
        if len([v for v in df_selectors if v not in selectors]) > 0:
            return False
        # No exclude_selector was found, and all selectors were found
        return True

    df = df[df[MappingColumns.SELECTORS].map(_should_keep_row)]
    df = df[[c for c in df.columns if c != MappingColumns.SELECTORS]]
    return df.reset_index(drop=True).copy()


def prepare_maps_df(
    maps_file: Union[str, Path],
    source_schema: SchemaView,
    target_schema: SchemaView,
    selectors: Optional[List[str]],
    source_slot_format_operations: Optional[Union[str, List[str]]],
    target_slot_format_operations: Optional[Union[str, List[str]]],
) -> pd.DataFrame:
    """Load and prepare the mapping specification file from disk. This DataFrame specifies all
    the mappings other than the wide column mappings (wide columns data is prepared by
    prepare_wide_df).

    Args:
        maps_file (Union[str, Path]): The mapping file to load.

    Returns:
        pd.DataFrame: The loaded and processed mapping data. It will contain the columns found in
            MappingColumns.
        source_schema (SchemaView): The source schema for the mapping.
        target_schema (SchemaView): The target schema for the mapping.
        selectors (Optional[List[str]], optional): For rows in the mapping config file that have a value in the "selectors" column, only use the
            row if any of these selectors is found. The "selectors" column has a comma-separated list of selector values. A selector
            value in the data can also be preceded by an exclamation mark, meaning only select the row if the
            selector value is NOT specified. For details see apply_selectors_to_df.
        source_slot_format_operations (Optional[Union[str, List[str]]], optional): Formatting options to apply to
            all slot names, found in the configuration file, for the source schema.
        target_slot_format_operations (Optional[Union[str, List[str]]], optional): Formatting options to apply to
            all slot names, found in the configuration file, for the target schema.
    """
    if not maps_file:
        return None

    maps_df = read_data_frame(maps_file, **CONFIG_READ_KWARGS)
    maps_df = strip_whitespace(maps_df)

    # Drop empty rows
    maps_df = maps_df.dropna(axis=0, how="all")

    # @TODO: Remove this once the maps_file is finalized
    maps_df = drop_incomplete_rows(maps_df)

    # Only use the rows based on the values in the selectors column
    maps_df = apply_selectors_to_df(maps_df, selectors=selectors)

    keep_columns = [
        MappingColumns.SOURCE_CLASS,
        MappingColumns.SOURCE_SLOT,
        MappingColumns.SOURCE_VALUE,
        MappingColumns.TARGET_CLASS,
        MappingColumns.TARGET_SLOT,
        MappingColumns.TARGET_VALUE,
        MappingColumns.TARGET_EXPR,
        MappingColumns.CUSTOM_DATA,
    ]
    # Select columns in keep_columns that exist in maps_df
    maps_df = maps_df[[c for c in keep_columns if c in maps_df.columns]]
    # Set columns in keep_columns that do not exist in maps_df to None
    maps_df[[c for c in keep_columns if c not in maps_df.columns]] = None
    # Sort the columns
    maps_df = maps_df[keep_columns]

    # Cleanup source/target slots (eg. replace whitespace with underscores, etc)
    maps_df[MappingColumns.SOURCE_SLOT] = cleanup_slot_name(
        maps_df[MappingColumns.SOURCE_SLOT],
        schema=source_schema,
        cleanup_options=source_slot_format_operations,
    )
    maps_df[MappingColumns.TARGET_SLOT] = cleanup_slot_name(
        maps_df[MappingColumns.TARGET_SLOT],
        schema=target_schema,
        cleanup_options=target_slot_format_operations,
    )
    # ws_columns = [
    #     MappingColumns.SOURCE_SLOT,
    #     MappingColumns.TARGET_SLOT,
    # ]
    # maps_df[ws_columns] = cleanup_slot_name(maps_df[ws_columns])

    return maps_df.copy()


def prepare_wide_df(
    wide_file: Union[str, Path],
    source_schema: SchemaView,
    target_schema: SchemaView,
    selectors: Optional[List[str]],
    source_slot_format_operations: Optional[Union[str, List[str]]],
    target_slot_format_operations: Optional[Union[str, List[str]]],
) -> pd.DataFrame:
    """Load and prepare the wide column configuration file from disk. This DataFrame specifies
    all the columns that act as wide columns in the source schema, along with details for how
    to map the wide columns to the target schema. It may also include some additional enum
    mappings required by the wide columns that are not found in the maps sheet.

    Args:
        wide_file (Union[str, Path]): The path to the wide column configuration data.

    Returns:
        pd.DataFrame: The DataFrame with the wide column information. It will contain the columns
            found in MappingColumns, including the wide-specific columns specifying values used
            when pivoting.
        source_schema (SchemaView): The source schema for the mapping.
        target_schema (SchemaView): The target schema for the mapping.
        selectors (Optional[List[str]], optional): For rows in the mapping config file that have a value in the "selectors" column, only use the
            row if any of these selectors is found. The "selectors" column has a comma-separated list of selector values. A selector
            value in the data can also be preceded by an exclamation mark, meaning only select the row if the
            selector value is NOT specified. For details see apply_selectors_to_df.
        source_slot_format_operations (Optional[Union[str, List[str]]], optional): Formatting options to apply to
            all slot names, found in the configuration file, for the source schema.
        target_slot_format_operations (Optional[Union[str, List[str]]], optional): Formatting options to apply to
            all slot names, found in the configuration file, for the target schema.
    """
    if not wide_file:
        return None

    wide_df = read_data_frame(wide_file, **CONFIG_READ_KWARGS)
    wide_df = strip_whitespace(wide_df)

    # Drop empty rows
    wide_df = wide_df.dropna(axis=0, how="all")

    # @TODO: Remove this once the wide_file is finalized
    wide_df = drop_incomplete_rows(wide_df)

    # Only use the rows based on the values in the selectors column
    wide_df = apply_selectors_to_df(wide_df, selectors=selectors)

    # Convert SOURCE_SLOT to strings
    wide_df[MappingColumns.SOURCE_SLOT] = wide_df[MappingColumns.SOURCE_SLOT].map(
        lambda x: "" if pd.isna(x) else str(x)
    )

    if MappingColumns.WIDE_OTHER_SLOTS not in wide_df.columns:
        wide_df[MappingColumns.WIDE_OTHER_SLOTS] = None

    # Get rid of NAs in the GROUP column. The pd.groupby function skips NA values, but doesn't
    # skip empty "" values.
    if MappingColumns.WIDE_GROUP in wide_df:
        wide_df[MappingColumns.WIDE_GROUP] = wide_df[MappingColumns.WIDE_GROUP].map(
            lambda x: "" if pd.isna(x) else str(x)
        )
        wide_df.loc[
            pd.isna(wide_df[MappingColumns.WIDE_GROUP]), MappingColumns.WIDE_GROUP
        ] = ""
    else:
        wide_df[MappingColumns.WIDE_GROUP] = ""

    # Make sure all required columns are present
    required_columns = [
        MappingColumns.SOURCE_CLASS,
        MappingColumns.SOURCE_SLOT,
        MappingColumns.SOURCE_VALUE,
        MappingColumns.TARGET_CLASS,
        MappingColumns.TARGET_VALUE,
    ]
    missing_columns = [c for c in required_columns if c not in wide_df.columns]
    wide_df[missing_columns] = ""

    # Order the columns into a nice order. This isn't necessary but makes it easier to view when debugging.
    wide_df = order_columns(wide_df, required_columns)

    # Cleanup source/target slot names
    # ws_columns = [
    #     MappingColumns.SOURCE_SLOT,
    #     MappingColumns.TARGET_SLOT,
    # ]
    # ws_columns = [c for c in ws_columns if c in wide_df.columns]
    if MappingColumns.SOURCE_SLOT in wide_df.columns:
        wide_df[MappingColumns.SOURCE_SLOT] = cleanup_slot_name(
            wide_df[MappingColumns.SOURCE_SLOT],
            schema=source_schema,
            cleanup_options=source_slot_format_operations,
        )
    if MappingColumns.TARGET_SLOT in wide_df.columns:
        wide_df[MappingColumns.TARGET_SLOT] = cleanup_slot_name(
            wide_df[MappingColumns.TARGET_SLOT],
            schema=target_schema,
            cleanup_options=target_slot_format_operations,
        )

    return wide_df.copy()


def drop_incomplete_rows(df: pd.DataFrame) -> pd.DataFrame:
    """Drop all rows in the DataFrame where the "Complete" column is not True.

    Args:
        df (pd.DataFrame): The DataFrame to drop incomplete rows from. A copy is made
            and the original DataFrame is left unchanged.

    Returns:
        pd.DataFrame: The DataFrame with incomplete rows removed.
    """
    if "Complete" in df.columns:
        return (
            df[df["Complete"] == 1]
            .drop("Complete", axis="columns")
            .reset_index(drop=True)
        )

    return df.copy()


def prepare_enums_df(
    enums_file: Union[str, Path],
    source_schema: SchemaView,
    target_schema: SchemaView,
    selectors: Optional[List[str]],
    source_slot_format_operations: Optional[Union[str, List[str]]],
    target_slot_format_operations: Optional[Union[str, List[str]]],
) -> pd.DataFrame:
    """Load and prepare the enums configuration file from disk. This DataFrame specifies enumeration
    mappings from source to target enums (note that enums can also be specified in the maps sheet, via
    prepare_maps_df).

    Args:
        enums_file (Union[str, Path]): The path to the enumeration configuration file.
        source_schema (SchemaView): The source schema for the mapping.
        target_schema (SchemaView): The target schema for the mapping.
        selectors (Optional[List[str]], optional): For rows in the mapping config file that have a value in the "selectors" column, only use the
            row if any of these selectors is found. The "selectors" column has a comma-separated list of selector values. A selector
            value in the data can also be preceded by an exclamation mark, meaning only select the row if the
            selector value is NOT specified. For details see apply_selectors_to_df.
        source_slot_format_operations (Optional[Union[str, List[str]]], optional): Formatting options to apply to
            all slot names, found in the configuration file, for the source schema.
        target_slot_format_operations (Optional[Union[str, List[str]]], optional): Formatting options to apply to
            all slot names, found in the configuration file, for the target schema.

    Returns:
        pd.DataFrame: The DataFrame with the enums mappings from enums_file.
    """
    if not enums_file:
        return None

    enums_df = read_data_frame(enums_file, **CONFIG_READ_KWARGS)
    enums_df = strip_whitespace(enums_df)

    # Drop empty rows
    enums_df = enums_df.dropna(axis=0, how="all")

    # @TODO: Remove this once the wide_file is finalized
    enums_df = drop_incomplete_rows(enums_df)

    # Only use the rows based on the values in the selectors column
    enums_df = apply_selectors_to_df(enums_df, selectors=selectors)

    # Keep only relevant columns, and make sure the columns exist
    keep_columns = [
        MappingColumns.SOURCE_CLASS,
        MappingColumns.SOURCE_SLOT,
        MappingColumns.SOURCE_ENUM,
        MappingColumns.SOURCE_VALUE,
        MappingColumns.TARGET_CLASS,
        MappingColumns.TARGET_SLOT,
        MappingColumns.TARGET_ENUM,
        MappingColumns.TARGET_VALUE,
    ]
    enums_df[[c for c in keep_columns if c not in enums_df.columns]] = ""
    enums_df = enums_df[keep_columns]

    # Convert entire DataFrame to strings
    enums_df = enums_df.map(lambda x: "" if pd.isna(x) else str(x))

    # Cleanup slot names (eg. replace whitespace with underscores)
    enums_df[MappingColumns.SOURCE_SLOT] = cleanup_slot_name(
        enums_df[MappingColumns.SOURCE_SLOT],
        schema=source_schema,
        cleanup_options=source_slot_format_operations,
    )
    enums_df[MappingColumns.TARGET_SLOT] = cleanup_slot_name(
        enums_df[MappingColumns.TARGET_SLOT],
        schema=target_schema,
        cleanup_options=target_slot_format_operations,
    )

    return enums_df.copy()


def make_wide_derivations(
    class_derivation: Dict,
    custom_wide_df: pd.DataFrame,
    class_enum_derivations: List[Dict[str, Dict[str, Dict]]],
    source_schema: SchemaView,
    target_schema: SchemaView,
    source_slot_format_operations: Optional[Union[str, List[str]]],
    target_slot_format_operations: Optional[Union[str, List[str]]],
) -> List[Dict]:
    """Based on the provided class derivation, make a separate class derivation for each wide column specified
    in custom_wide_df. We will also select all the enum derivations required by the new wide derivations from
    class_enum_derivations.

    Args:
        class_derivation (Dict): The class derivation that acts as the template for all wide derivations.
        custom_wide_df (pd.DataFrame): The DataFrame containing the wide column information.
        class_enum_derivations (List[Dict[str, Dict[str, Dict]]]): All known enum derivations. For each element in
            the list, the first key is the source class name, second key is the target class name, all sub-values
            are the actual enum derivations. An enum_derivation later in the list takes precedence of an
            enum_derivation earlier in the list (ie. if there are multiple derivations with the same
            populated_from field).
            enum_derivation[""][""] are all enum derivations with no source and target class name specified
            (eg from the enums tab), these apply to all source and target classes.
            For a given enum_derivation item, if a source enum exists at both class_enum_derivations[source_class][target_class]
            and at class_enum_derivations[""][""] then the former one takes precedence.
            For any enumeration in the resulting class derivations that is not found in class_enum_derivations we will create a
            new enum derivation where we simply copy values from the source  enum to the target enum.
        source_schema (SchemaView): The source schema for the class_derivation.
        target_schema (SchemaView): The target schema for the class_derivation.
        source_slot_format_operations (Optional[Union[str, List[str]]], optional): Formatting options to apply to
            all slot names, found in the configuration file, for the source schema.
        target_slot_format_operations (Optional[Union[str, List[str]]], optional): Formatting options to apply to
            all slot names, found in the configuration file, for the target schema.

    Returns:
        List[Dict]: A list of dictionaries containing all the new derivations. The dictionary has the
            following keys: "source_class", "target_class", "class_derivation", and "enum_derivations".
            "class_derivation" contains the actual class derivation recognized by the Mapper,
            and "enum_derivations" has all the enum derivations required by the class derivation. Example:
                [
                    {
                        "source_class": "nwss",
                        "target_class": "protocolSteps[000,0002=extraction_method]",
                        "undecorated_target_class": "protocolSteps",
                        "class_derivation": {
                            "name": "protocolSteps[000,0002=extraction_method]",
                            "populated_from": "nwss",
                            "slot_derivations": {
                                "reflink": {
                                    "name": "reflink",
                                    "populated_from": "lod_ref"
                                },
                                ...
                            },
                        "enum_derivations": {
                            "vs_yne[ext_blank]": {
                                "name": "vs_yne[ext_blank]",
                                "mirror_source": false,
                                "populated_from": "vs_yne[ext_blank]",
                                "permissible_values": { ... },
                            },
                            ...
                        }
                    },
                    ...
                ]

    """
    source_class_name = class_derivation["populated_from"]
    target_class_name = class_derivation["name"]

    # filt = (custom_wide_df[MappingColumns.SOURCE_CLASS] == source_class_name) & (custom_wide_df[MappingColumns.TARGET_CLASS] == target_class_name)
    # custom_wide_df = custom_wide_df[filt].copy()

    results = []
    # for idx, (_, group_df) in enumerate(custom_wide_df.groupby([MappingColumns.SOURCE_CLASS, MappingColumns.SOURCE_SLOT, MappingColumns.TARGET_CLASS, MappingColumns.WIDE_GROUP])):
    # Get source class and target class
    source_class = custom_wide_df[MappingColumns.SOURCE_CLASS].iloc[0]
    target_class = custom_wide_df[MappingColumns.TARGET_CLASS].iloc[0]

    # Extract enum derivations from the group. It is in the form group_enum_derivations[source_class][target_class] = { derivations }.
    group_enum_derivations = extract_enum_derivations(
        custom_wide_df,
        source_schema=source_schema,
        target_schema=target_schema,
        source_slot_format_operations=source_slot_format_operations,
        target_slot_format_operations=target_slot_format_operations,
    )

    # Extract the wide-to-long data. We only use the first row of the group, since the others are identical other than
    # for the enum derivations.
    custom_wide_df = custom_wide_df.iloc[[0]].copy()

    # Set the columns in the OTHER_SLOTS field. It is a JSON dictionary of column:value pairs
    other_slots = custom_wide_df[MappingColumns.WIDE_OTHER_SLOTS].iloc[0]
    if other_slots and isinstance(other_slots, str):
        other_slots = json.loads(other_slots)
        custom_wide_df[list(other_slots.keys())] = list(other_slots.values())

    # Keep source class, target class, and all columns that are wide target slots or wide expr slots
    keep_columns = [MappingColumns.SOURCE_CLASS, MappingColumns.TARGET_CLASS]
    keep_columns = keep_columns + [
        c
        for c in custom_wide_df.columns
        if c not in keep_columns
        and (is_wide_target_value_slot(c) or is_wide_target_expr_slot(c))
    ]
    custom_wide_df = custom_wide_df[keep_columns]

    # Pivot the group to long format, keeping id_columns constant for all rows.
    # The pivoted table has a TARGET_VALUE column specifying either the constant value to set or the source slot to copy from (eg. {{slotName}})
    # as well as an TARGET_EXPR column specifying LinkML expression code to execute for calculating the value of the target slot.
    # We create the pivoted tables form TARGET_VALUEs and TARGET_EXPRs separated, then concatenate them together
    id_columns = [MappingColumns.SOURCE_CLASS, MappingColumns.TARGET_CLASS]
    wide_target_columns = [
        c for c in custom_wide_df.columns if is_wide_target_value_slot(c)
    ]
    wide_target_df = custom_wide_df.melt(
        id_vars=id_columns,
        value_vars=wide_target_columns,
        var_name=MappingColumns.TARGET_SLOT,
        value_name=MappingColumns.TARGET_VALUE,
        ignore_index=False,
    )
    wide_expr_columns = [
        c for c in custom_wide_df.columns if is_wide_target_expr_slot(c)
    ]
    wide_expr_df = custom_wide_df.melt(
        id_vars=id_columns,
        value_vars=wide_expr_columns,
        var_name=MappingColumns.TARGET_SLOT,
        value_name=MappingColumns.TARGET_EXPR,
        ignore_index=False,
    )

    # Drop expr rows that have an empty expression
    wide_expr_df = wide_expr_df[
        ~pd.isna(wide_expr_df[MappingColumns.TARGET_EXPR])
        | (wide_expr_df[MappingColumns.TARGET_EXPR] == "")
    ]

    # Combine wide_target_df and wide_expr_df, sort by index
    custom_wide_df = pd.concat([wide_target_df, wide_expr_df]).sort_index(kind="stable")

    # Get the wide target slot names by trimming of the suffixes (eg. remove _target or _expr)
    custom_wide_df[MappingColumns.TARGET_SLOT] = custom_wide_df[
        MappingColumns.TARGET_SLOT
    ].map(any_wide_slot_name)

    # ROW_NUMBER is all the same, since group_df provides all the information for outputing a single row (we do one output
    # row at a time)
    custom_wide_df[MappingColumns.WIDE_ROW_NUMBER] = 0

    # Create the derivations for pivoting the single column defined by custom_wide_df
    cur_results = expand_wide_derivations(
        source_class_name=source_class_name,
        target_class_name=target_class_name,
        slot_derivations=class_derivation["slot_derivations"],
        custom_wide_dfs=custom_wide_df,
        source_schema=source_schema,
        target_schema=target_schema,
        source_slot_format_operations=source_slot_format_operations,
        target_slot_format_operations=target_slot_format_operations,
    )

    # Add the enum derivations for each of the expanded class derivations
    cur_enum_derivations = list(class_enum_derivations)
    cur_enum_derivations.append(group_enum_derivations)
    cur_enum_derivations = get_class_enum_derivations(
        source_class, target_class, cur_enum_derivations
    )
    for results_dict in cur_results:
        results_enum_derivations = select_required_enum_derivations(
            results_dict["class_derivation"], cur_enum_derivations, schema=source_schema
        )
        results_dict["enum_derivations"] = results_enum_derivations
    results.extend(cur_results)

    return results


def merge_enum_derivations(enum_derivations: List[Dict]) -> Dict:
    """Merge a list of enum derivations into a single enum derivations dictionary, where the keys are the target
    enum name and the values are the derivations.
    Each populated_from field in the merged derivations is unique. If more than one enum derivation exists
    with the same populated_from field in the enum_derivations parameter, then the one later in the list takes
    precedence and overwrites any previous ones.

    Args:
        derivations (List[Dict]): List of all enum derivations. These are in the form:
            {
                "target_enum_name" : {
                    "name" : target_enum_name,
                    "populated_from" : source_enum_name,
                    "permissible_value_derivations" : { ... }
                },
                "other_target_enum_name" : { ... },
                ...
            }

    Returns:
        Dict: Dictionary of merged enum derivations.
    """
    results = {}
    for cur_derivations in enum_derivations:
        for k, v in cur_derivations.items():
            # Get all the derivations in results that have the same populated_from field.
            populated_from = v["populated_from"]
            key_matches = [
                k for k, v in results.items() if v["populated_from"] == populated_from
            ]
            if len(key_matches) > 1:
                raise RuntimeError(
                    f"Found {len(key_matches)} existing enum derivations for populated_from value='{populated_from}'"
                )
            elif len(key_matches) == 1:
                # A derivation for v["populated_from"] already exists in results, so delete it
                # del(results[key_matches[0]])
                raise ValueError(
                    f"Enum derivation with populated_from='{populated_from}' already exists, can only have one enum derivation per populated_from"
                )
            # Add the current derivation
            results[k] = v

    return results


def get_class_enum_derivations(
    source_class: str, target_class: str, class_enum_derivations: List[Dict]
) -> Dict:
    """Retrieve all enum derivations that involve mapping from the source_class to target_class from
    class_enum_derivations, and merge them by calling merge_enum_derivations. This can be run on the value
    returned by extract_enum_derivations, which is a dictionary with a top-level key being the source class
    and the second-level key being the target class. The dictionaries nested within the second-level key
    are the actual enum derivations (that apply to the source to target class mappings). That is,
    all enum derivations at class_enum_derivations[i][source_class][target_class] are the ones we're
    interested in, and the anum derivations at class_enum_derivations[i][""][""] also apply to all source
    to target class derivations.

    Args:
        source_class (str): The source class.
        target_class (str): The target class.
        class_enum_derivations (List[Dict]): List of all class enum derivations, where each item
            is a dict and where item[source_class][target_class] = { enum_derivations } where the
            enum_derivations are specific to mapping from a source class slot to a target class
            slot. Also, item[""][""] are also enum derivations that apply to ANY source class to
            ANY target class (so these are also returned).

    Returns:
        Dict: Dictionary of merged enum derivations involving slots from the source_class to target_class.
    """
    group = []
    for cur_derivations in class_enum_derivations:
        # Get the derivations in cur_derivations[""][""]
        d = cur_derivations.get("", {}).get("", {})
        if len(d) > 0:
            group.append(d)
        # Get the derivations in cur_derivations[source_class][""]
        if source_class:
            d = cur_derivations.get(source_class, {}).get("", {})
            if len(d) > 0:
                group.append(d)
        # Get the derivations in cur_derivations[""][target_class]
        if target_class:
            d = cur_derivations.get("", {}).get(target_class, {})
            if len(d) > 0:
                group.append(d)
        # Get the derivations in cur_derivations[source_class][target_class]
        if source_class and target_class:
            d = cur_derivations.get(source_class, {}).get(target_class, {})
            if len(d) > 0:
                group.append(d)
    # Merge the list of derivations into a single derivation
    return merge_enum_derivations(group)


def save_schema_definition(schema: SchemaDefinition, output_file: Union[str, Path]):
    """Save the schema to disk as a LinkML YAML schema file.

    Args:
        schema (SchemaDefinition): The SchemaDefinition to save to disk.
        output_file (Union[str, Path]): The YAML file to save to.
    """
    schema_dict = schema_as_dict(schema)

    if os.path.dirname(output_file):
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
    with open(output_file, "w") as f:
        f.write(yaml.dump(schema_dict, sort_keys=False))
    logger.info(f"LinkML schema saved to '{output_file}'")


def make_mappers(
    maps_files: Union[Union[str, Path], List[Union[str, Path]]],
    wide_files: Union[Union[str, Path], List[Union[str, Path]]],
    enums_files: Union[Union[str, Path], List[Union[str, Path]]],
    mapper_dir: Union[str, Path],
    source_schema: Union[str, Path],
    target_schema: Union[str, Path],
    source_schema_for_mapping: Union[str, Path],
    selectors: Optional[List[str]],
    source_slot_format_operations: Optional[Union[str, List[str]]],
    target_slot_format_operations: Optional[Union[str, List[str]]],
):
    """Make all mapper configuration files using the specified mapping, wide column, and enums config files.

    Args:
        maps_files (Union[Union[str, Path], List[Union[str, Path]]]): The mapping config files.
        wide_files (Union[Union[str, Path], List[Union[str, Path]]]): The wide column config files. Set to None or []
            if there are no wide files.
        enums_files (Union[Union[str, Path], List[Union[str, Path]]]): The enumerations config files. Set to None or []
            if there are no enum files.
        mapper_dir (Union[str, Path]): Directory to save all the mapping config files to.
        source_schema (Union[str, Path]): Path to the source schema of the mapping.
        target_schema (Union[str, Path]): Path to the target schema of the mapping.
        source_schema_for_mapping (Union[str, Path]): Path to save the modified source_schema to. This LinkML schema contains additional
            slots that are meant to contain generated IDs when doing the actual mapping, for linking between tables.
        selectors (Optional[List[str]], optional): For rows in the mapping config file that have a value in the "selectors" column, only use the
            row if any of these selectors is found. The "selectors" column has a comma-separated list of selector values. A selector
            value in the data can also be preceded by an exclamation mark, meaning only select the row if the
            selector value is NOT specified.
        source_slot_format_operations (Optional[Union[str, List[str]]], optional): Formatting options to apply to
            all slot names, found in the configuration file, for the source schema.
        target_slot_format_operations (Optional[Union[str, List[str]]], optional): Formatting options to apply to
            all slot names, found in the configuration file, for the target schema.
    """
    if mapper_dir:
        os.makedirs(mapper_dir, exist_ok=True)

    if isinstance(maps_files, (str, Path)):
        maps_files = [maps_files]
    if isinstance(wide_files, (str, Path)):
        wide_files = [wide_files]
    if isinstance(enums_files, (str, Path)):
        enums_files = [enums_files]

    # Load all schemas
    source_schema = SchemaView(source_schema)
    # remove_enum_ontology_ids(source_schema)
    target_schema = SchemaView(target_schema)

    # Load and prepare the maps files
    maps_df = [
        prepare_maps_df(
            f,
            source_schema=source_schema,
            target_schema=target_schema,
            selectors=selectors,
            source_slot_format_operations=source_slot_format_operations,
            target_slot_format_operations=target_slot_format_operations,
        )
        for f in maps_files
    ]
    maps_df = pd.concat([df for df in maps_df if df is not None]).reset_index(drop=True)
    # Load and prepare the wide-columns files
    wide_dfs = []
    if wide_files is not None and len(wide_files) > 0:
        wide_dfs = [
            prepare_wide_df(
                f,
                source_schema=source_schema,
                target_schema=target_schema,
                selectors=selectors,
                source_slot_format_operations=source_slot_format_operations,
                target_slot_format_operations=target_slot_format_operations,
            )
            for f in wide_files
            if f
        ]
    # Load and prepare the enums mapping files
    enums_df = None
    if enums_files is not None and len(enums_files) > 0:
        enums_df = [
            prepare_enums_df(
                f,
                source_schema=source_schema,
                target_schema=target_schema,
                selectors=selectors,
                source_slot_format_operations=source_slot_format_operations,
                target_slot_format_operations=target_slot_format_operations,
            )
            for f in enums_files
        ]
        enums_df = pd.concat([df for df in enums_df if df is not None])

    # Add all auto IDs (eg. id:sampleID) to the LinkML schema
    add_auto_ids_to_schema(source_schema, maps_df)
    for wide_df in wide_dfs:
        add_auto_ids_to_schema(source_schema, wide_df)
    logger.info(
        f"Saving modified source schema for mapping to {source_schema_for_mapping}"
    )
    save_schema_definition(source_schema.schema, source_schema_for_mapping)

    # Extract all enum and class derivations from the maps file and enums files.
    # (maps|enums)_enum_derivations is in the format (maps|enums)_enum_derivations[source_class][target_class] = {enum_derivations}
    # all_class_derivations is in the format all_class_derivations[source_class][target_class] = {class_derivations}
    maps_enum_derivations = extract_enum_derivations(
        maps_df,
        source_schema=source_schema,
        target_schema=target_schema,
        source_slot_format_operations=source_slot_format_operations,
        target_slot_format_operations=target_slot_format_operations,
    )
    enums_enum_derivations = extract_enum_derivations(
        enums_df,
        source_schema=source_schema,
        target_schema=target_schema,
        source_slot_format_operations=source_slot_format_operations,
        target_slot_format_operations=target_slot_format_operations,
    )
    all_class_derivations = extract_class_derivations(
        maps_df,
        source_schema=source_schema,
        source_slot_format_operations=source_slot_format_operations,
        target_slot_format_operations=target_slot_format_operations,
    )

    # Go through all wide mapping data, and create the wide class derivations (one class derivation per wide group)
    results = []
    for wide_df in wide_dfs:
        for idx, (_, group_df) in enumerate(
            wide_df.groupby(
                [
                    MappingColumns.SOURCE_CLASS,
                    MappingColumns.SOURCE_SLOT,
                    MappingColumns.TARGET_CLASS,
                    MappingColumns.WIDE_GROUP,
                ],
                sort=False,
            )
        ):
            source_class_name = group_df[MappingColumns.SOURCE_CLASS].iloc[0]
            target_class_name = group_df[MappingColumns.TARGET_CLASS].iloc[0]
            class_derivation = all_class_derivations.get(source_class_name, {}).get(
                target_class_name, None
            )
            if not class_derivation:
                class_derivation = get_blank_class_derivation(
                    source_class_name, target_class_name
                )

            custom_wide_results = make_wide_derivations(
                class_derivation=class_derivation,
                custom_wide_df=group_df,
                class_enum_derivations=[enums_enum_derivations, maps_enum_derivations],
                source_schema=source_schema,
                target_schema=target_schema,
                source_slot_format_operations=source_slot_format_operations,
                target_slot_format_operations=target_slot_format_operations,
            )
            if len(custom_wide_results) > 0:
                results.extend(custom_wide_results)

    # Add all the class derivations that were not expanded to wide derivations
    for source_class_name, source_class_derivations in all_class_derivations.items():
        for (
            target_class_name,
            target_class_derivation,
        ) in source_class_derivations.items():
            wide_results = [
                r
                for r in results
                if r["undecorated_target_class"] == target_class_name
                and r["source_class"] == source_class_name
            ]
            if len(wide_results) == 0:
                cur_enum_derivations = get_class_enum_derivations(
                    source_class_name,
                    target_class_name,
                    [enums_enum_derivations, maps_enum_derivations],
                )
                enum_derivations = select_required_enum_derivations(
                    target_class_derivation, cur_enum_derivations, schema=source_schema
                )
                results.append(
                    {
                        "source_class": source_class_name,
                        "target_class": target_class_name,
                        "undecorated_target_class": target_class_name,
                        "class_derivation": target_class_derivation,
                        "enum_derivations": enum_derivations,
                    }
                )

    # Go through all the results and create a mapping spec file for each
    for idx, cur_results in enumerate(results):
        target_class = cur_results["target_class"]
        class_derivation = cur_results["class_derivation"]
        source_class = cur_results["source_class"]
        enum_derivations = cur_results["enum_derivations"]
        # Create the mapping spec for the mapping from source_class to target_class
        mapper_spec = {
            "class_derivations": {
                target_class: class_derivation,
                TREE_ROOT_CLASS_NAME: {
                    "name": TREE_ROOT_CLASS_NAME,
                    "slot_derivations": {
                        target_class: {
                            "populated_from": source_class,
                            # @TODO: Remove "range" : "string": This is only included to remove warnings
                            # of unknown target range of target_class. Also, having a range of string
                            # seems to force enum mappings where the source enum has no mapping to
                            # the string "None", rather than the NULL value None.
                            # "range": "string",
                        }
                    },
                },
            },
            "enum_derivations": enum_derivations,
        }

        # Save mapper specification to disk
        re_match = r"[^A-Za-z0-9 .,\_]"
        source_class_tag = re.sub(re_match, "_", source_class)
        target_class_tag = re.sub(re_match, "_", target_class)
        mapper_file = os.path.join(
            mapper_dir, f"mapper-{idx:010n}-{source_class_tag}-{target_class_tag}.yaml"
        )
        logger.info(
            f"Saving mapper spec for '{source_class}' to '{target_class}': {mapper_file}"
        )
        with open(mapper_file, "w") as f:
            yaml.dump(mapper_spec, f, indent=2, sort_keys=False)


# def remove_enum_ontology_ids(schema: SchemaView):
#     print("!!!!REMOVE!")
#     for enum_name in schema.all_enums():
#         enum_defn = schema.get_enum(enum_name)
#         permissible_values = enum_defn.permissible_values
#         for key in list(permissible_values.keys()):
#             key_cleaned = re.sub(r" \[([A-Za-z0-9]+)\:([A-Za-z0-9]+)\]$", "", key)
#             if key_cleaned != key:
#                 permissible_values[key]["old_name"] = key
#                 permissible_values[key_cleaned] = permissible_values[key]
#                 del permissible_values[key]


if __name__ == "__main__":
    if "get_ipython" in globals():
        dictionary_type = "reporting"

        class opts:
            maps_files = ["../gen/odm_v1_to_v2/configs/maps0.csv"]
            wide_files = []
            enums_files = []
            mapper_dir = "../gen/odm_v1_to_v2/mappers"
            source_schema = "../data/odm_v1/linkml/odm_v1.yaml"
            target_schema = "../data/odm_v2/linkml/odm_v2.yaml"
            selectors = []
            source_schema_for_mapping = (
                "../gen/odm_v1_to_v2/linkml_for_mapping/odm_v1.yaml"
            )

            # maps_files = [f"../gen/nwss_{dictionary_type}_to_v2/configs/maps0.csv"]
            # wide_files = [
            #     f"../gen/nwss_{dictionary_type}_to_v2/configs/wide0.csv",
            #     f"../gen/nwss_{dictionary_type}_to_v2/configs/wide1.csv",
            #     f"../gen/nwss_{dictionary_type}_to_v2/configs/wide2.csv",
            # ]
            # enums_files = [f"../gen/nwss_{dictionary_type}_to_v2/configs/enums0.csv"]
            # mapper_dir = f"../gen/nwss_{dictionary_type}_to_v2/mappers"
            # source_schema = (
            #     f"../data/nwss_{dictionary_type}/linkml/nwss_{dictionary_type}.yaml"
            # )
            # target_schema = "../data/odm_v2/linkml/odm_v2.yaml"
            # source_schema_for_mapping = f"../gen/nwss_{dictionary_type}_to_v2/linkml_for_mapping/nwss_{dictionary_type}.yaml"

            source_slot_format_operations = [
                "alpha_numeric_underscore",
                "single_underscores",
                "trim_underscores",
            ]
            target_slot_format_operations = [
                "alpha_numeric_underscore",
                "single_underscores",
                "trim_underscores",
            ]

            # For PHA4GE
            # source_slot_format_operations = [ "lowercase", '{ remove_chars: "-"}', "alpha_numeric_underscore", "single_underscores", "trim_underscores" ]
    else:
        args = argparse.ArgumentParser(
            formatter_class=argparse.ArgumentDefaultsHelpFormatter
        )
        args.add_argument(
            "--maps_files",
            type=str,
            nargs="+",
            help="The configuration file(s) specifying how to map slots from the source dataset to the target dataset. Can be a CSV or TSV file",
            required=True,
        )
        args.add_argument(
            "--wide_files",
            type=str,
            nargs="+",
            help="The configuration file(s) specifying any wide columns in the mapping. Can be CSV or TSV files",
            required=False,
        )
        args.add_argument(
            "--enums_files",
            type=str,
            nargs="+",
            help="The configuration file(s) specifying any enumerations in the mapping. Can be CSV or TSV files",
            required=False,
        )
        args.add_argument(
            "--mapper_dir",
            type=str,
            help="Location to save all mapping config files to",
            required=True,
        )
        args.add_argument(
            "--source_schema",
            type=str,
            help="Location of the source LinkML schema",
            required=True,
        )
        args.add_argument(
            "--target_schema",
            type=str,
            help="Location of the target LinkML schema",
            required=True,
        )
        args.add_argument(
            "--selectors",
            type=str,
            nargs="+",
            help="Selectors, to select rows in the mapping config file that has any of these values in the selectors column. If the value in the selectors column is empty then that row is always included.",
            required=False,
        )
        args.add_argument(
            "--source_schema_for_mapping",
            type=str,
            help="Location to save the modified source_schema that should be used for mapping. This schema will include additional slots where IDs get generated, for linking between tables in the output, as well as possibly other changes. The resulting schema might be the same as the original.",
            required=True,
        )
        args.add_argument(
            "--source_slot_format_operations",
            type=str,
            nargs="+",
            help="Formatting operations to apply to all configured slots from the source schema.",
            required=False,
        )
        args.add_argument(
            "--target_slot_format_operations",
            type=str,
            nargs="+",
            help="Formatting operations to apply to all configured slots from the target schema.",
            required=False,
        )
        opts = args.parse_args()

    logger.info("Running...")

    # @TODO Remove extract_sheets, this is done in make_mappers_cli.py
    # Extract the required sheets from the NWSS to ODM 2 mapping file
    # from utils.general_utils import extract_sheets

    # mapping_config_file = "../data/mapping_config_files/nwss_to_odm_v2_mapping.xlsx"
    # configs_dir = f"../gen/nwss_{dictionary_type}_to_v2/configs/"
    # extract_sheets(
    #     mapping_config_file,
    #     ["maps", "wide", "enums"],
    #     configs_dir,
    #     output_names=["maps0", "wide0", "enums0"],
    #     na_values={},
    #     default_na_values=[""],
    # )

    make_mappers(
        maps_files=opts.maps_files,
        wide_files=opts.wide_files,
        enums_files=opts.enums_files,
        mapper_dir=opts.mapper_dir,
        source_schema=opts.source_schema,
        target_schema=opts.target_schema,
        selectors=opts.selectors,
        source_schema_for_mapping=opts.source_schema_for_mapping,
        source_slot_format_operations=opts.source_slot_format_operations,
        target_slot_format_operations=opts.target_slot_format_operations,
    )

    logger.info("Finished!")
