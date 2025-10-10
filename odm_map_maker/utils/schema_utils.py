"""
Utility functions for LinkML schemas.
"""

from typing import Dict, List, Optional, Any, Union
from dataclasses import asdict
from linkml_runtime.linkml_model.meta import SlotDefinition
import re

from linkml_runtime import SchemaView


def get_slot_definition(
    cls: str, slot: str, schema: SchemaView, exception_on_error: bool = True
) -> Dict:
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

    class_definition = schema.induced_class(cls)
    if slot in class_definition.attributes:
        return asdict(class_definition.attributes[slot])
    return None


def get_ranges_of_slot(
    class_name: str,
    slot_name: Union[str, List[str]],
    schema: SchemaView,
    exception_on_error: bool = True,
) -> List[str]:
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
    slot_defn: Union[Dict, SlotDefinition, List[SlotDefinition]],
) -> List[str]:
    """Get the range(s) (if any) of the slot definition(s).

    Args:
        slot_defn (Union[Dict, SlotDefinition, List[SlotDefinition]]): The SlotDefinition(s) to get the ranges of.

    Returns:
        List[str]: A list of range(s) for the specified slot(s), if at least one range exists. If
            no range is found then an empty list is returned.
    """
    if isinstance(slot_defn, (SlotDefinition, Dict)):
        slot_defn = [slot_defn]
    ranges = []
    for cur_defn in slot_defn:
        if not isinstance(cur_defn, dict):
            cur_defn = asdict(cur_defn)
        # Try getting the range
        range_defn = cur_defn.get("range", None)
        if range_defn is not None:
            # range_defn is of type linkml_runtime.linkml_model.meta.ElementName
            # We need to convert it to either type str or type List[str]
            cur_ranges = [str(range_defn)]

        # Try getting any_of
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
    enum_names: List[str],
    permissible_value: Any,
    schema: SchemaView,
    with_ontology_id: bool = False,
) -> Optional[str]:
    """Get the first enumeration name that contains the specified permissible value.

    Args:
        enum_names (List[str]): List of enumeration names (in schema) to look for the permissible value in.
        permissible_value (Any): The permissible value to find.
        schema (SchemaView): The schema view that contains all the enumerations.
        with_ontology_id (bool): If True then we also allow the permissible_value to match the schema
            enum values that have an additional ontology ID appended to it (in square brackets). For example,
            if permissible_value is "degree Celsius (C)" then it will also match a permissible value
            in the schema of "degree Celsius (C) [UO:0000027]".

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
            if with_ontology_id:
                permissible_values = [remove_ontology_id(p) for p in permissible_values]
                if permissible_value in permissible_values:
                    return enum_name
    return None


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


def remove_ontology_id(val: str) -> str:
    """Remove an ontology ID from the end of a value. For example, "degree Celsius (C) [UO:0000027]" would
        become "degree Celsius (C)"

    Args:
        val (str): The value to remove the ontology ID from.

    Returns:
        str: The value with the ontology ID removed. If there was no ontology ID it is returned unchanged.
    """
    val = re.sub(r"\[[A-Za-z0-9_]+:[A-Za-z0-9_]+\]$", "", val.strip()).strip()
    return val


def get_enum_names_for_slot(
    cls: str, slot: str, schema: SchemaView
) -> Optional[List[str]]:
    """Get the enumeration names (if any) for the range of the specified slot in the specified class.

    Args:
        cls (str): The class that the slot belongs to.
        slot (str): The slot to get the enumeration name for.
        schema (SchemaView): The Schema to retrieve the enumeration from.

    Returns:
        List[str]: The names of the enumerations that is the range of slot. If slot does
            not have an enumeration for a range then None is returned.
    """
    ranges = get_ranges_of_slot(cls, slot, schema)
    if not ranges:
        return None

    enum_names = []
    for rng in ranges:
        # See if rng is a name for an enumeration
        enum_definition = schema.get_enum(rng)
        if enum_definition is not None:
            enum_names.append(rng)

    return enum_names if enum_names else None
