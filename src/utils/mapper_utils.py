"""
Utility functions for LinkML Mapper
"""

import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from typing import Dict, List, Union, Any, Optional
import pandas as pd
import re

from linkml_runtime import SchemaView

from utils.general_utils import get_logger
from utils.schema_utils import get_enum_names_for_slot

logger = get_logger(__name__)

# Regular expression for matching strings that refer to a source slot. Usually meaning to
# copy the value found in the source slot to a different target slot. This is in the form
# {{sourceSlotName}}.
VARIABLE_REGEX = r"^{{([^}]*)}}$"

# For wide tab, any column name that ends in WIDE_SPEC_VALUE_SUFFIX will be trimmed of the suffix
# and used as a column in the output row to set a value for (eg. to a constant or copying from
# an input slot such as {{slotName}}).
WIDE_SPEC_VALUE_SUFFIX = "_value"

# For wide tab, any column that ends in WIDE_SPEC_EXPR_SUFFIX will be trimmed of the suffix
# and used as an LinkML expr block (ie. code to execute to calcualte the column value)
WIDE_SPEC_EXPR_SUFFIX = "_expr"


class MappingColumns:
    """Columns used internally that specify the mappings. These are assigned to the columns in the
    Excel mapping configuration files.
    """

    SOURCE_CLASS = "sourceClass"
    SOURCE_SLOT = "sourceSlot"
    SOURCE_VALUE = "sourceValue"
    TARGET_CLASS = "targetClass"
    TARGET_SLOT = "targetSlot"
    TARGET_VALUE = "targetValue"
    TARGET_EXPR = "targetExpr"
    CUSTOM_DATA = "customData"

    # These columns should only be present in the enums tabs of the mapping files
    SOURCE_ENUM = "sourceEnum"
    TARGET_ENUM = "targetEnum"

    # These columns should only be present in the wide tabs of the mapping files
    WIDE_GROUP = "wideGroup"
    WIDE_ROW_NUMBER = "wideRowNumber"
    WIDE_OTHER_SLOTS = "wideOtherSlots"


# Additional arguments to pass to pd.read_csv, pd.read_excel, etc for reading in the mapping configuration files.
CONFIG_READ_KWARGS = {
    "dtype": {
        MappingColumns.SOURCE_VALUE: str,
        MappingColumns.TARGET_VALUE: str,
    },
    "keep_default_na": False,
    "na_values": [""],
    "default_na_values": [""],
}


def is_wide_slot(name: Any, suffix: str) -> bool:
    """Test if the column name refers to a special wide slot name, such as for a wide target value, wide expr value, etc.

    These are column names that end in a suffix, such as _value, _expr, etc.

    Args:
        name (Any): The column name to test.
        suffix (str): The suffix to test for, such as WIDE_SPEC_VALUE_SUFFIX and WIDE_SPEC_EXPR_SUFFIX.

    Returns:
        bool: True if name is a special wide slot name that ends in the specified suffix.
    """
    if not isinstance(name, str):
        return False
    return name.endswith(suffix)


def wide_slot_name(name: str, suffix: str) -> Optional[str]:
    """Get the name of the special wide slot with the suffix removed. If name does not end in the suffix then None is returned.

    eg. If name is "qualityRepID_value" and suffix is "_value", then "qualityRepID" is returned.

    Args:
        name (str): The column name to remove the suffix from.
        suffix (str): The suffix to remove.

    Returns:
        Optional[str]: The column name with the suffix removed, or None if column name does not end in the suffix.
    """
    if not is_wide_slot(name, suffix):
        return None
    return name[0 : -len(suffix)]


def any_wide_slot_name(name: str) -> Optional[str]:
    """Get the slot that the special wide column name refers to. This removes any recognized special wide slot name suffix
    from the specified column name. This includes _value and _expr suffixes. If no recognized suffix is present then None
    is returned.

    Args:
        name (str): The column name to remove the suffix from.

    Returns:
        Optional[str]: The column name with any recognized suffix removed, or None if name does not end
            in a recognized suffix.
    """
    check_suffixes = [
        WIDE_SPEC_VALUE_SUFFIX,
        WIDE_SPEC_EXPR_SUFFIX,
    ]
    for suffix in check_suffixes:
        if is_wide_slot(name, suffix):
            return wide_slot_name(name, suffix)
    return None


def is_wide_target_value_slot(name: Any) -> bool:
    """Test if the specified wide column name ends in the _value suffix.

    Args:
        name (Any): The column name to test.

    Returns:
        bool: True of the column name ends in the _value suffix, False otherwise.
    """
    return is_wide_slot(name, WIDE_SPEC_VALUE_SUFFIX)


def wide_target_value_slot_name(name: str) -> Optional[str]:
    """Remove the _value suffix from the specified special wide column name. Returns
    None if it does not end with the _value suffix.

    Args:
        name (str): The column name to remove the suffix from.

    Returns:
        Optional[str]: The column name with the _value suffix removed, or None if it does
            not end in the _value suffix.
    """
    return wide_slot_name(name, WIDE_SPEC_VALUE_SUFFIX)


def is_wide_target_expr_slot(name: Any) -> bool:
    """Test if the specified wide column name ends in the _expr suffix.

    Args:
        name (Any): The column name to test.

    Returns:
        bool: True of the column name ends in the _expr suffix, False otherwise.
    """
    return is_wide_slot(name, WIDE_SPEC_EXPR_SUFFIX)


def wide_target_expr_slot_name(name: str) -> Optional[str]:
    """Remove the _expr suffix from the specified special wide column name. Returns
    None if it does not end with the _expr suffix.

    Args:
        name (str): The column name to remove the suffix from.

    Returns:
        Optional[str]: The column name with the _expr suffix removed, or None if it does
            not end in the _expr suffix.
    """
    return wide_slot_name(name, WIDE_SPEC_EXPR_SUFFIX)


def get_variable_reference(v: Any) -> Optional[str]:
    """Get the variable name that the value references. If the value is in the form {{variableName}} then the string
    "variableName" will be returned.

    Args:
        v (Any): The value to get the variable reference from.

    Returns:
        Optional[str]: The variable that v refers to, or None if it does not refer to a variable.
    """
    if not isinstance(v, str):
        return None
    match = re.search(VARIABLE_REGEX, v)
    return None if match is None else match[1]


def select_required_enum_derivations(
    class_derivation: Dict,
    enum_derivations: Dict,
    schema: SchemaView,
    mirror_missing_enum_derivations: bool = True,
) -> Dict:
    """Select all the enumeration derivations required by the specified class derivation.

    To select the enum derivations we go through each slot derivation and get the derivation's populated_from field.
    The populated_from field is a slot in the source schema for the class, so we extract the slot's definition.
    If the slot definition has a range that's an enum, we keep the enum derivation for that range.

    Args:
        class_name (str): The class
        class_derivation (Dict): A single class derivation dictionary.
        enum_derivations (Dict): All available enum derivations. We will select only the required ones from this.
        schema (SchemaView): The source schema.
        mirror_missing_enum_derivations (bool): If True, then if a categorical variable is found in class_derivation
            that does not have an existing enum derivation, then we create a basic enum derivation where all values
            are mirrored (ie. the enum values are copied over unchanged).

    Returns:
        Dict: A dictionary that is the same as enum_derivations but where only the required enum derivations are included.
    """
    class_name = class_derivation["populated_from"]
    selected_derivations = {}

    class_definition = schema.get_class(class_name)
    if class_definition is None:
        raise ValueError(f"Class {class_name} does not exist!")

    # Go through all slot derivations and get the populated_from field. If the populated_from field
    # is an enumeration in the source schema, then we keep its enum derivation.
    for slot_derivation in class_derivation["slot_derivations"].values():
        if "populated_from" not in slot_derivation:
            continue
        source_slot_name = slot_derivation["populated_from"]

        # Get the enum name for the slot
        enum_names = get_enum_names_for_slot(class_name, source_slot_name, schema)
        if enum_names is None:
            continue

        for enum_name in enum_names:
            # Try to get the enum derivation for the enum name. If an enum derivation exists then we keep it.
            derivations = [
                k
                for k, v in enum_derivations.items()
                if v["populated_from"] == enum_name
            ]
            if len(derivations) > 1:
                raise RuntimeError(
                    f"Found multiple target enum derivations {derivations} populating from the same source enum {enum_name} (from source slot {source_slot_name}). This is not allowed by LinkML Mapper!"
                )
            if mirror_missing_enum_derivations and len(derivations) == 0:
                logger.warning(
                    f"No enum derivation found for {enum_name} in select_required_enum_derivations, creating a mirrored enum derivation"
                )
                target_enum_name = f"{enum_name}[=mirrored=]"
                selected_derivations[target_enum_name] = {
                    "name": target_enum_name,
                    "mirror_source": True,
                    "populated_from": enum_name,
                }
            else:
                for derivation_name in derivations:
                    selected_derivations[derivation_name] = enum_derivations[
                        derivation_name
                    ]

    return selected_derivations


def expand_wide_derivations(
    source_class_name: str,
    target_class_name: str,
    slot_derivations: Dict,
    custom_wide_dfs: Union[List[pd.DataFrame], pd.DataFrame],
) -> List[Dict]:
    """Using custom wide DataFrames and an already calculated slot_derivations, see if there are any
    custom wide-to-long columns for the current source class to target class slot_derivations. If there are,
    then create multiple new slot_derivations (for multiple mappers) based on the original slot_derivations, each new
    derivation includes a single wide-to-long column mapping.

    Later on, when we map the data, we run each wide-to-long mapping separately.
    This takes care of each wide-to-long column. We then concatenate the mapped data of
    each separate mapping.

    Args:
        source_class_name (str): The source class (table) name that the slot_derivations is for.
        target_class_name (str): The target class (table) name that the slot_derivations is for.
        slot_derivations (Dict): The slot_derivations before any wide-to-long derivations are added.
            We will make a copy of this and modify each copy for each wide-to-long column.
        custom_wide_dfs (Union[List[pd.DataFrame], pd.DataFrame]): The DataFrame(s) containing all the
            information required for wide-to-long mappings.

    Returns:
        Dict: A list of dictionaries of the following form:
            {
                "source_class" : source_class_name,
                "target_class" : wide_target_class_name,
                "undecorated_target_class" : target_class_name,
                "class_derivation" : new_class_derivation
            }
            The wide_target_class_name is the target_class_name with an additional modifier added in square brackets, that specify
            the column used for the wide-to-long mappings (eg. protocolSteps[extractionVolMl]),
            and new_class_derivation is a copy of slot_derivations with the wide-to-long derivations
            added. If there are no wide-to-long columns for the specified source to target
            classes, then an empty List is returned.
    """
    results = []

    if isinstance(custom_wide_dfs, pd.DataFrame):
        custom_wide_dfs = [custom_wide_dfs]

    # We have custom wide information. For wide information, we create multiple
    # mapper configs, one for each wide column.
    for custom_wide_number, custom_wide_df in enumerate(custom_wide_dfs):
        # Select all rows matching the source class and target class
        custom_wide_df = custom_wide_df[
            (custom_wide_df[MappingColumns.SOURCE_CLASS] == source_class_name)
            & (custom_wide_df[MappingColumns.TARGET_CLASS] == target_class_name)
        ]
        if len(custom_wide_df.index) == 0:
            continue

        # Sort by the ROW_NUMBER column. We use "stable" sort, this preserves the order
        # for already-sorted rows (eg. if all row numbers are 0, then sorting preserves
        # the existing order of the rows). This ensures that if a later row overwrites the
        # target slot of a previous row, that the later row actually does occur later in the
        # input configuration file. This makes more sense from a user-point of view.
        custom_wide_df = custom_wide_df.sort_values(
            MappingColumns.WIDE_ROW_NUMBER, kind="stable"
        )

        # Group by ROW_NUMBER and iterate. We make one class derivation per group.
        for group_number, rows_df in custom_wide_df.groupby(
            MappingColumns.WIDE_ROW_NUMBER
        ):
            # Make a copy of the full slot derivation we previously calculated. We'll
            # modify it with the current wide info
            cur_slot_derivations = slot_derivations.copy()

            # Each row in the rows group defines a target column and a target value to set in the
            # target class.
            # source_slots keeps a record of all the source slots we populated from (ie. copied over
            # to the target). It is for naming purposes only, we include all source slots used
            # in the mapper spec file name (see wide_target_class_name).
            source_slots = []
            for row_number, row in rows_df.iterrows():
                target_slot = row[MappingColumns.TARGET_SLOT]
                target_value = row[MappingColumns.TARGET_VALUE]
                target_expr = row[MappingColumns.TARGET_EXPR]

                # We always need a target slot specified
                if not target_slot or pd.isna(target_slot):
                    raise ValueError(
                        f"{MappingColumns.TARGET_SLOT} is empty in row {row_number} for wide mapping"
                    )

                source_slot_variable = get_variable_reference(target_value)
                if target_expr and isinstance(target_expr, str):
                    # A target expr (ie. custom code) is specified
                    cur_slot_derivations[target_slot] = {
                        "name": target_slot,
                        "expr": target_expr,
                    }
                elif source_slot_variable is not None:
                    # target_value is of the form {{sourceSlot}}, where sourceSlot is the name
                    # of a column in the source class. So we populate from sourceSlot to the
                    # target slot.
                    source_slots.append(source_slot_variable)
                    # The value is "<sourceSlot>", so we populate from source_column
                    cur_slot_derivations[target_slot] = {
                        "name": target_slot,
                        "populated_from": source_slot_variable,
                    }
                else:
                    # The value is a constant, so we populate with the constant using expr
                    if pd.isna(target_value):
                        target_value = ""
                    cur_slot_derivations[target_slot] = {
                        "name": target_slot,
                        "expr": f"'{target_value}'",
                    }

            # Create a new unique name for the target class. Target class names
            # can have the real target class followed by an optional modifier in
            # square brackets.
            source_slot_names = "-".join(sorted(source_slots))
            wide_target_class_name = f"{target_class_name}[{custom_wide_number:03n},{group_number:04n}={source_slot_names}]"
            class_derivation = {
                "name": wide_target_class_name,
                "populated_from": source_class_name,
                "slot_derivations": cur_slot_derivations,
            }
            results.append(
                {
                    "source_class": source_class_name,
                    "target_class": wide_target_class_name,
                    "undecorated_target_class": target_class_name,
                    "class_derivation": class_derivation,
                }
            )

    return results


def get_blank_class_derivation(source_class: str, target_class: str) -> Dict:
    """Create a new LinkML class derivation dictionary with an empty slots derivation.

    Args:
        source_class (str): The source class (for the "populated_from" field)
        target_class (str): The target class (for the "name" field)

    Returns:
        Dict: A blank class derivation populating target_class from source_class.
    """
    return {
        "name": target_class,
        "populated_from": source_class,
        "slot_derivations": {},
    }
