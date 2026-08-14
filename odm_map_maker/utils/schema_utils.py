"""
Utility functions for LinkML schemas.
"""

import re
from dataclasses import asdict
from typing import Any

import numpy as np
from linkml_runtime import SchemaView
from linkml_runtime.linkml_model.meta import SlotDefinition

from odm_map_maker.utils.general_utils import choose_ignore_case_value


def all_classes_without_tree_root(schema: SchemaView) -> list[str]:
    """Get a list of all classes in the schema, excluding the tree root class that contains
    all the classes.

    Args:
        schema (SchemaView): The Schema to get the classes of.

    Returns:
        List[str]: List of all classes belonging to the schema, excluding the tree root class.
    """
    classes = [str(c) for c, defn in schema.all_classes().items() if not defn.tree_root]
    return classes


def get_slot_definition(
    cls: str, slot: str, schema: SchemaView, exception_on_error: bool = True
) -> dict:
    """Get the full definition for the slot. This includes fields that are attributes of the class.
    If a slot is modified with a slot_usage, then we also update the returned dictionary with the
    slot usage information.

    Args:
        cls (str): The class that contains the slot.
        slot (str): The slot name to get the definition for.
        schema (SchemaView): The Schema the class and slot belong to.
        exception_on_error (bool): If True then raise an exception if the slot does not exist. If False then
            return None if the slot does not exist.

    Returns:
        Dict: The dictionary with all information about the slot (eg. the name, range, pattern, etc).
            If the slot is not a member of the class then None is returned.
    """
    if exception_on_error:
        return asdict(schema.induced_slot(slot, cls))
    else:
        try:
            return asdict(schema.induced_slot(slot, cls))
        except ValueError:
            # SchemaView raises a ValueError when the class or slot does not exist
            return None


def get_ranges_of_slot(
    class_name: str,
    slot_name: str | list[str],
    schema: SchemaView,
    exception_on_error: bool = True,
) -> list[str]:
    """Get the range(s) (if any) of the slot(s) in the specified class.

    Args:
        cls (str): The class that the slot belongs to.
        slot (Union[str, List[str]]): The slot(s) to get the range(s) for.
        schema (SchemaView): The Schema to retrieve the slot info from.
        exception_on_error (bool): If True then raise an exception if the a slot does not exist. If False then
            an empty range is retrieved for slots that do not exist.

    Returns:
        List[str]: A list of range(s) for the specified slots, if at least one range exists. If
            no range is found (eg. the class or slot are invalid) then an empty list is returned.
    """
    if isinstance(slot_name, str):
        slot_name = [slot_name]
    ranges = []
    for cur_slot in slot_name:
        # slot_defn = schema.induced_slot(cur_slot, class_name)
        slot_defn = get_slot_definition(
            class_name, cur_slot, schema, exception_on_error=exception_on_error
        )
        if slot_defn:
            cur_ranges = get_ranges_of_slot_defn(slot_defn)
            if cur_ranges:
                ranges.extend(cur_ranges)

    # Remove duplicates (but retain order)
    ranges = list(dict.fromkeys(ranges))
    return ranges


def get_ranges_of_slot_defn(
    slot_defn: dict | SlotDefinition | list[SlotDefinition],
) -> list[str]:
    """Get the range(s) (if any) of the slot definition(s).

    Args:
        slot_defn (Union[Dict, SlotDefinition, List[SlotDefinition]]): The SlotDefinition(s) to get the ranges of.

    Returns:
        List[str]: A list of range(s) for the specified slot(s), if at least one range exists. If
            no range is found then an empty list is returned.
    """
    if isinstance(slot_defn, (SlotDefinition, dict)):
        slot_defn = [slot_defn]
    ranges = []
    for cur_defn in slot_defn:
        if not isinstance(cur_defn, dict):
            cur_defn = asdict(cur_defn)
        # Try getting the range
        cur_ranges = []
        range_defn = cur_defn.get("range", None)
        if range_defn is not None:
            # range_defn is of type linkml_runtime.linkml_model.meta.ElementName
            # We need to convert it to either type str or type List[str]
            cur_ranges = [str(range_defn)]

        # Try getting any_of. This overrides what we retrieved from "range".
        # For example, sometimes we might have "range: Any" and "any_of: ...",
        # which in LinkML means to use the "any_of" field, but having "range: Any"
        # is not required.
        any_of_defn = cur_defn.get("any_of", None)
        if any_of_defn is not None:
            any_of_ranges = []
            for cur_defn in any_of_defn:
                cur_range = cur_defn.get("range", None)
                if cur_range:
                    any_of_ranges.append(str(cur_range))
            if len(any_of_ranges):
                cur_ranges = any_of_ranges

        ranges.extend(cur_ranges)

    # Remove duplicates (but retain order)
    ranges = list(dict.fromkeys(ranges))
    return ranges


def get_enum_name_with_permissible_value(
    enum_names: list[str],
    permissible_value: Any,
    schema: SchemaView,
    match_ontology_id: str | None,
) -> str | None:
    """Get the first enumeration name that contains the specified permissible value.

    Args:
        enum_names (List[str]): List of enumeration names (in schema) to look for the permissible value in.
        permissible_value (Any): The permissible value to find.
        schema (SchemaView): The schema view that contains all the enumerations.
        match_ontology_id (Optional[str], optional): If set, then a regular expression string that matches ontology
            IDs for enum values in the schema. Any enum value in the schema will have its ontology ID removed when
            comparing it to permissible_value, so that the caller does not need to explicitly include it.

    Returns:
        Optional[str]: The first enumeration name found in enum_names that has permissible_value as a permissible value.
            None if none of the enumerations have the permissible value.
    """
    for enum_name in enum_names:
        enum = schema.all_enums().get(enum_name, None)
        if enum is not None:
            permissible_values = list(enum.permissible_values.keys())
            if permissible_value in permissible_values:
                return enum_name
            if match_ontology_id:
                permissible_values = [
                    remove_ontology_id(p, match_ontology_id=match_ontology_id)
                    for p in permissible_values
                ]
                if permissible_value in permissible_values:
                    return enum_name
    return None


def add_ontoid_to_enum_value(
    schema: SchemaView,
    enum_name: str,
    enum_value: str,
    match_ontology_id: str | None,
) -> str:
    """Add an ontology ID to an enum value, if an ontology ID is present for that enum value
    in the schema. For example, an enum value of "degree Celsius (C)" might be changed to
    "degree Celsius (C) [UO:0000027]".

    Args:
        schema (SchemaView): The schema the enum value belongs to.
        enum_name (str): The enumeration name that the enum value belongs to.
        enum_value (str): The enum value to an ontology ID to, if the ontology ID is present
            in the schema.
        match_ontology_id (Optional[str], optional): If set, then a regular expression string that matches ontology
            IDs for enum values in the schema. If a permissible value with its ontology ID removed matches
            enum_value, then that permissible value (with the ontology ID) will be returned. If
            match_ontology_id is None or empty ("") then enum_value is returned unchanged.

    Returns:
        str: The enumeration value, possibly with an ontology ID added to it.
    """
    if not match_ontology_id:
        return enum_value
    if not enum_name:
        return enum_value
    enum_defn = schema.get_enum(enum_name)
    if not enum_defn:
        return enum_value
    for permissible_value in enum_defn.permissible_values:
        if (
            remove_ontology_id(
                str(permissible_value), match_ontology_id=match_ontology_id
            )
            == enum_value
        ):
            return permissible_value
    return enum_value


def remove_ontology_id(val: str, match_ontology_id: str | None) -> str:
    """Remove an ontology ID from the end of a value. For example, "degree Celsius (C) [UO:0000027]" would
        become "degree Celsius (C)"

    Args:
        val (str): The value to remove the ontology ID from.
        match_ontology_id (Optional[str], optional): If set, then a regular expression string that matches ontology
            IDs for enum values in the schema. If a match is found in val, then it is removed. If
            match_ontology_id is None or empty ("") then val is returned unchanged.

    Returns:
        str: The value with the ontology ID removed. If there was no ontology ID it is returned unchanged.
    """
    if not match_ontology_id:
        return val
    val = re.sub(match_ontology_id, "", val.strip()).strip()
    return val


def get_enum_names_for_slot(cls: str, slot: str, schema: SchemaView) -> list[str]:
    """Get the enumeration names (if any) for the range of the specified slot in the specified class.

    Args:
        cls (str): The class that the slot belongs to.
        slot (str): The slot to get the enumeration name for.
        schema (SchemaView): The Schema to retrieve the enumeration from.

    Returns:
        List[str]: The names of the enumerations that is the range of slot. If slot does
            not have an enumeration for a range then the empty list [] is returned.
    """
    ranges = get_ranges_of_slot(cls, slot, schema, exception_on_error=False)

    enum_names = []
    for rng in ranges:
        # See if rng is a name for an enumeration
        enum_definition = schema.get_enum(rng)
        if enum_definition is not None:
            enum_names.append(rng)

    return enum_names


def get_permissible_values_from_enum_names(
    enum_names: list[str], schema: SchemaView, sort_values: bool = False
) -> list[str]:
    """Get all the permissible values for all the specified enumerations in the schema.

    Args:
        enum_names (List[str]): The enumeration to get the permissible values for.
        schema (SchemaView): The LinkML schema that the enumerations belong to.
        sort_values (bool): If True then sort all the values alphabetically (case insensitive) before returning
            them. If False then keep them in the order according to enum_names and the order they appear in the
            schema.

    Returns:
        List[str]: A list of all enumeration values of all the specified enumerations.
    """
    permissible_values = []

    # Get all the permissible values
    for cur_enum_name in enum_names:
        enum_defn = schema.get_enum(cur_enum_name)
        permissible_values.extend(list(enum_defn.permissible_values.keys()))

    # Remove duplicates and sort
    permissible_values = list(dict.fromkeys(permissible_values))
    if sort_values:
        permissible_values = sorted(permissible_values, key=lambda x: x.lower())

    return permissible_values


def remove_ignored_text_from_class_name(class_name: str) -> str:
    """Remove any text to ignore when trying to identify a class name within a string.

    This will remove all text after the first opening square or round bracket.

    Args:
        class_name (str): The class name string candidate to clean up.

    Returns:
        str: The string class_name with text we should ignore removed. After
            cleaning up the string we can search for a class name in the cleaned
            string.
    """
    return class_name.split("[")[0].split("(")[0]


def find_class(
    class_name: str, schema: SchemaView | None, ignore_case: bool
) -> str | None:
    """Figure out which class the class_name string should belong to, making the search
    fairly flexible. We will typically search for a recognized class name in the string,
    so for example "1 - WWMeasure (2024-11-30)" would map to the class "WWMeasure".
    For a stricter search, where the whole string (after cleaning) must match a recognized class,
    see get_class().

    For cleaning, any text after the first opening square or round bracket in class_name is
    ignored.

    The matching class is the longest class name in the schema that can be found
    in the string class_name (eg. If "WWMeasure" and "Measure" are both classes in
    the schema, then the string "1 - WWMeasure" will match to "WWMeasure", even
    though "Measure" is found in the string, because "WWMeasure" is longer).

    If schema is None, then the class_name is cleaned but we return the cleaned class_name
    without searching for class name strings within the class_name (since we need schema
    to know which classes are valid classes)

    Args:
        class_name (str): The string to search for the class name. Any text after the
            first opening square or round bracket in class_name is ignored.
        schema (Optional[SchemaView], optional): The schema containing all the recognized
            classes. Can be None.
        ignore_case (bool): If True then make the search case-insensitive, otherwise
            make it case-sensitive.

    Returns:
        Optional[str]: The class that the string should represent, or None if no
            class was found.
    """
    class_name = remove_ignored_text_from_class_name(class_name)

    if schema is None:
        return class_name

    all_classes = all_classes_without_tree_root(schema)

    all_classes_lower = [c.lower() for c in all_classes] if ignore_case else all_classes
    match_lower = class_name.lower() if ignore_case else class_name

    # Find all matches
    matches = [c for c in all_classes_lower if c in match_lower]
    if len(matches) == 0:
        return None
    # Match found, so get the longeset matching class name
    matched = matches[np.argmax([len(c) for c in matches])]

    # Correct capitalization of class
    return choose_ignore_case_value(matched, all_classes)


def get_class(
    class_name: str, schema: SchemaView | None, ignore_case: bool
) -> str | None:
    """Get the recognized class name based on the string class_name (optionally case-
    sensitive or case-insensitive), or None if the class name does not exist.

    Any text after the first opening square or round bracket in class_name is
    ignored.

    If schema is None, then we simply return the cleaned text as a class name,
    since we need schema to know which class names are valid.

    Args:
        class_name (str): The string to get the class name for. Any text after the
            first opening square or round bracket in class_name is ignored.
        schema (Optional[SchemaView], optional): The schema that contains all the
            recognized classes. If None then we simply return the cleaned class_name
            (since we need schema to know which class names are valid)
        ignore_case (bool): If True then make class_name case-insensitive, but return
            the class name with the correct capitaliztion. If False then only
            return the recognized class if class_name already has the correct
            capitalization.

    Returns:
        Optional[str]: The recognized class name, or None if class_name is not
            a recognized class name in the schema. If schema is None, then we
            clean class_name (remove text after the first opening round or
            square bracket) and return the value without checking if it is
            a valid class name.
    """
    class_name = remove_ignored_text_from_class_name(class_name)

    if schema is None:
        return class_name

    all_classes = all_classes_without_tree_root(schema)

    if ignore_case:
        # Case-insensitive
        return choose_ignore_case_value(
            class_name, all_classes, return_same_if_missing=False
        )
    else:
        # Case-sensitive, so only return exact match
        if class_name in all_classes:
            return class_name
        return None
