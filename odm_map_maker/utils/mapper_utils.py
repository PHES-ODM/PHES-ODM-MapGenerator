"""
Utility functions for LinkML Mapper
"""

from typing import Dict, List, Union, Any, Optional
import pandas as pd
import re
import yaml
import ast

from linkml_runtime import SchemaView

from odm_map_maker.utils.logger import get_logger
from odm_map_maker.utils.schema_utils import get_enum_names_for_slot

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

    # Additional fields to set for an enum or slot derivation (eg. { mirror_source: True })
    ENUM_DERIVATION_SETTINGS = "enumDerivationSettings"
    SLOT_DERIVATION_SETTINGS = "slotDerivationSettings"

    # Can be present in any tab (enums, wide, or maps)
    SELECTORS = "selectors"

    # These columns should only be present in the enums tabs of the mapping files
    SOURCE_ENUM = "sourceEnum"
    TARGET_ENUM = "targetEnum"

    # These columns should only be present in the wide tabs of the mapping files
    WIDE_GROUP = "wideGroup"
    WIDE_ROW_NUMBER = "wideRowNumber"
    WIDE_OTHER_SLOTS = "wideOtherSlots"


EXTRA_COLUMN_PREFIX = "_extra_"
EXTRA_COLUMN_SUFFIX = ""

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
    """Get the slot that the wide column name refers to. This removes any recognized wide slot name suffix
    from the specified column name. This includes _value and _expr suffixes. If no recognized suffix is present then None
    is returned.

    For example, "sampleID_value" will return "sampleID", and "measure_expr" will return "measure.

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


def get_variable_reference(
    v: Any, schema: SchemaView, format_operations: Optional[Union[str, List[str]]]
) -> Optional[str]:
    """Get the variable name that the value references. If the value is in the form {{variableName}} then the string
    "variableName" will be returned.

    Args:
        v (Any): The value to get the variable reference from.
        schema (SchemaView): The schema that the variable/slot belongs to.
        format_operations: (Optional[Union[str, List[str]]]): Operations to apply to the variable to format it. See
            cleanup_slot_name.

    Returns:
        Optional[str]: The variable that v refers to, or None if it does not refer to a variable.
    """
    if not isinstance(v, str):
        return None
    match = re.search(VARIABLE_REGEX, v)
    if match is None:
        return None

    return cleanup_slot_name(match[1], schema=schema, cleanup_options=format_operations)


def get_used_slots(expr: str, recognized_globals: List[str] = ["emap"]) -> List[str]:
    """Get all the slots referenced in the Python code specified in expr. Slots are any
    attributes taken on the global variables in recognized_globals. For example, if
    recognized_globals is ["enum"], then any attribute of enum is returned. If
    expr has "enum.collection_device" somewhere in the code, then the returned
    list will have the value "collection_device" in it.

    Args:
        expr (str): The code to get the referenced slots from.
        recognized_globals (List[str], optional): The recognized global variables that
            we want to get the slots of that are referened in the code. If recognized_globals
            has "enum", then if "enum.slot_name" is found in expr then "slot_name" will be
            part of the returned list. Defaults to ["emap"].

    Returns:
        List[str]: List of slots referenced in the code specified by expr.
    """
    used_slots = []
    s = ast.parse(expr)
    for i in ast.walk(s):
        if isinstance(i, ast.Attribute):
            slots = parse_used_slots(i)
            if len(slots) >= 2:
                if slots[0] in recognized_globals:
                    used_slots += [slots[1]]
    return list(dict.fromkeys(used_slots))


def parse_used_slots(node: ast.Attribute, path: List[str] = []) -> List[str]:
    """Recursively parse the slots in the attribute node. The returned path will be an array
    of names/variables that are used to make up the whole attribute. For example, for the attribute
    "enum.collection_device", the returned path will be ["enum", "collection_device"].

    Args:
        i (ast.Attribute): The attribute node to recursively parse.
        path (List[str], optional): The current path of the attribute that gets passed in recursively.
            Defaults to [].

    Returns:
        List[str]: The slots associated with the attribute.
    """
    attr = node.attr
    v = node.value
    if isinstance(v, ast.Attribute):
        path = [attr] + path
        path = parse_used_slots(v, path)
    elif isinstance(v, ast.Name):
        path = [v.id, attr] + path
    return path


def select_required_enum_derivations(
    source_class: str,
    target_class: str,
    class_derivation: Dict,
    enum_derivations: List[Dict],
    schema: SchemaView,
    mirror_missing_enum_derivations: bool = False,
) -> Dict:
    """Select all the enumeration derivations required by the specified class derivation.
    @TODO: Update this: The parameters and parameter types have changed

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
    enum_derivations = [
        e[source_class] for e in enum_derivations if source_class in e
    ] + [e[""] for e in enum_derivations if "" in e]
    enum_derivations = [
        e[target_class] for e in enum_derivations if target_class in e
    ] + [e[""] for e in enum_derivations if "" in e]
    class_name = class_derivation["populated_from"]
    selected_derivations = {}

    class_definition = schema.get_class(class_name)
    if class_definition is None:
        raise ValueError(f"Class {class_name} does not exist!")

    # Go through all slot derivations and get the populated_from field. If the populated_from field
    # is an enumeration in the source schema, then we keep its enum derivation.
    for slot_derivation in class_derivation["slot_derivations"].values():
        if "populated_from" not in slot_derivation and "expr" not in slot_derivation:
            continue

        # Get the source and target slot names for the current slot derivation
        if expr := slot_derivation.get("expr", None):
            # The slot derivation uses an expr. We look for all slot names that are preceded by "emap." in the
            # expr code. These will give us the slot names that are used and that need to be transformed as
            # an enumeration
            source_slot_names = get_used_slots(expr, recognized_globals=["emap"])
        else:
            source_slot_names = [slot_derivation["populated_from"]]
        target_slot_name = slot_derivation["name"]

        for source_slot_name in source_slot_names:
            # Get the enum name for the source slot
            enum_names = get_enum_names_for_slot(class_name, source_slot_name, schema)
            if enum_names is None:
                continue

            cur_enum_derivations = [
                e[source_slot_name] for e in enum_derivations if source_slot_name in e
            ] + [e[""] for e in enum_derivations if "" in e]
            cur_enum_derivations = [
                e[target_slot_name]
                for e in cur_enum_derivations
                if target_slot_name in e
            ] + [e[""] for e in cur_enum_derivations if "" in e]

            for enum_name in enum_names:
                # Try to get the enum derivation for the enum name. If an enum derivation exists then we keep it.
                derivations = []
                for d in cur_enum_derivations:
                    derivations += [
                        k for k, v in d.items() if v["populated_from"] == enum_name
                    ]
                if len(derivations) > 1:
                    raise RuntimeError(
                        f"Found multiple target enum derivations {derivations} populating from the same source enum {enum_name} (from source slot {source_slot_name}). This is not allowed by LinkML Mapper!"
                    )
                # if mirror_missing_enum_derivations and len(derivations) == 0:
                if len(derivations) == 0:
                    # No enum derivation found, but caller is requesting to create a mirror enum derivation in this case.
                    logger.warning(
                        f"No enum derivation found for {enum_name} in select_required_enum_derivations, creating a mirrored enum derivation"
                    )
                    mirrored_tag = (
                        "mirrored"
                        if mirror_missing_enum_derivations
                        else "not_mirrored"
                    )
                    target_enum_name = f"{enum_name}[={mirrored_tag}=]"
                    selected_derivations[target_enum_name] = {
                        "name": target_enum_name,
                        "mirror_source": mirror_missing_enum_derivations,
                        "populated_from": enum_name,
                    }
                else:
                    for derivation_name in derivations:
                        matching_derivations = [
                            e for e in cur_enum_derivations if derivation_name in e
                        ]
                        selected_derivations[derivation_name] = matching_derivations[0][
                            derivation_name
                        ]

    return selected_derivations


def expand_wide_derivations(
    source_class_name: str,
    target_class_name: str,
    slot_derivations: Dict,
    custom_wide_dfs: Union[List[pd.DataFrame], pd.DataFrame],
    source_schema: SchemaView,
    target_schema: SchemaView,
    source_slot_format_operations: Optional[Union[str, List[str]]],
    target_slot_format_operations: Optional[Union[str, List[str]]],
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
        source_schema (SchemaView): The source schema of the mapping.
        target_schema (SchemaView): The target schema of the mapping.
        source_slot_format_operations (Optional[Union[str, List[str]]], optional): Formatting options to apply to
            all slot names, found in the configuration file, for the source schema.
        target_slot_format_operations (Optional[Union[str, List[str]]], optional): Formatting options to apply to
            all slot names, found in the configuration file, for the target schema.

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
                slot_derivation_settings = row.get(
                    MappingColumns.SLOT_DERIVATION_SETTINGS, None
                )
                if pd.isna(slot_derivation_settings):
                    slot_derivation_settings = None
                if slot_derivation_settings:
                    slot_derivation_settings = yaml.safe_load(slot_derivation_settings)

                # We always need a target slot specified
                if not target_slot or pd.isna(target_slot):
                    raise ValueError(
                        f"{MappingColumns.TARGET_SLOT} is empty in row {row_number} for wide mapping"
                    )

                source_slot_variable = get_variable_reference(
                    target_value,
                    schema=source_schema,
                    format_operations=source_slot_format_operations,
                )
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
                        "populated_from": source_slot_variable,  # cleanup_slot_name(source_slot_variable),
                    }
                else:
                    # The value is a constant, so we populate with the constant using expr
                    if pd.isna(target_value):
                        target_value = ""
                    cur_slot_derivations[target_slot] = {
                        "name": target_slot,
                        "expr": f"'{target_value}'",
                    }
                if slot_derivation_settings:
                    cur_slot_derivations[target_slot].update(slot_derivation_settings)

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


def format_slot_name(val: str, format_options: Union[str, List[str]]) -> str:
    """Format the specified slot using the specified formatting options.

    Args:
        val (str): The slot name to format. If not a string then it is left unchanged.
        format_options (Union[str, List[str]]): The formatting operation, or list of formatting operations, to perform.
            Formating operations that can be performed are:
                    "lowercase": Make lowercase.
                    "uppercase": Make uppercase.
                    "alpha_numeric_underscore": Replace non alpha-numeric values with underscores.
                    "single_underscores": Replace double (or more) underscores (eg. __, ___) with single underscores
                    "trim_whitespace": Remove leading and trailing whitespace.
                    "trim_trailing_underscores": Remove trailing underscores.
                    "remove_chars": Remove all the specified characters. This should be specified as either a JSON/YAML
                        string or as a dictionary of the form { "remove_chars": "abc" } where "abc" contains all the
                        characters to remove (ie. "a", "b", and "c" will be removed).
                    "remove_special": Remove all special characters (characters other than alpha-numeric and spaces).
            Multiple operations can be specified, and the operations are performed in the same order as specified
            in the list.

    Returns:
        str: The formatted slot name (val), after all formatting operations are performed.
    """
    if not isinstance(val, str):
        return val

    if val.startswith(EXTRA_COLUMN_PREFIX) and val.endswith(EXTRA_COLUMN_SUFFIX):
        return val

    for options in format_options:
        if isinstance(options, str):
            options = yaml.safe_load(options)
            if isinstance(options, str):
                options = {options: True}
        for option, param in options.items():
            if option == "lowercase":
                val = val.lower()
            if option == "uppercase":
                val = val.upper()
            if option == "alpha_numeric_underscore":
                val = re.sub("[^A-Za-z0-9]", "_", val)
            if option == "single_underscores":
                val = re.sub("__+", "_", val)
            if option == "trim_trailing_underscores":
                val = val.rstrip("_")
            if option == "trim_whitespace":
                val = re.sub(r"^\s*", "", val)
                val = re.sub(r"\s*$", "", val)
            if option == "remove_chars":
                for ch in param:
                    val = val.replace(ch, "")
            if option == "remove_special":
                val = re.sub(r"[^A-Za-z0-9\s]", "", val)

    return val


def cleanup_slot_name(
    data: Union[str, pd.DataFrame, pd.Series],
    schema: SchemaView,
    cleanup_options: Optional[Union[str, List[str]]],
) -> Union[str, pd.DataFrame]:
    """Cleanup a slot name so that it can be used as a variable name, by replacing whitespace
    and other non-alphanumeric characters with an underscore.

    Args:
        data (Union[str, pd.DataFrame, pd.Series]): The data to cleanup. If a DataFrame or Series then cleanup all
            cells, if a string then cleanup the string.
        schema (SchemaView): The schema that the slot belongs to.
        cleanup_options (Optional[Union[str, List[str]]], optional): The cleanup options to perform.

    Returns:
        Union[str, pd.DataFrame]: The cleaned data.
    """
    if not cleanup_options:
        return data

    if isinstance(data, (pd.DataFrame, pd.Series)):
        return data.map(lambda x: format_slot_name(x, format_options=cleanup_options))

    return format_slot_name(data, format_options=cleanup_options)
