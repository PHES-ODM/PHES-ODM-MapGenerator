# %%
"""
Utility functions for LinkML schemas.
"""

from typing import Dict, List, Optional, Any
from dataclasses import asdict
import yaml

from linkml_runtime import SchemaView


def get_slot_definition(cls: str, slot: str, schema: SchemaView) -> Dict:
    """Get the full definition for the slot. This includes fields that are attributes of the class.
    If a slot is modified with a slot_usage, then we also update the returned dictionary with the
    slot usage information.

    Args:
        cls (str): The class that contains the slot.
        slot (str): The slot name to get the definition for.
        schema (SchemaView): The Schema the class and slot belong to.

    Returns:
        Dict: The dictionary with all information about the slot (eg. the name, range, pattern, etc).
            If the slot is not a member of the class then None is returned.
    """
    class_definition = schema.induced_class(cls)
    if slot in class_definition.attributes:
        return asdict(class_definition.attributes[slot])
    return None


def get_ranges_of_slot(cls: str, slot: str, schema: SchemaView) -> List[str]:
    """Get the range(s) (if any) of the slot in the specified class.

    Args:
        cls (str): The class that the slot belongs to.
        slot (str): The slot to get the range for.
        schema (SchemaView): The Schema to retrieve the slot info from.

    Returns:
        List[str]: A list of range(s) for the specified slot, if at least one range exists. If
            no range is found (eg. the class or slot are invalid) then None is returned.
    """
    defn = get_slot_definition(cls, slot, schema)

    if defn is not None:
        defn = defn.get("range", None)
        if defn is not None:
            # defn is of type linkml_runtime.linkml_model.meta.ElementName
            # We need to convert it to either type str or type List[str]
            defn = yaml.safe_load(str(defn))

    if isinstance(defn, str):
        defn = [defn]

    return defn


def get_enum_name_with_permissible_value(
    enum_names: List[str], permissible_value: Any, schema: SchemaView
) -> Optional[str]:
    """Get the first enumeration name that contains the specified permissible value.

    Args:
        enum_names (List[str]): List of enumeration names (in schema) to look for the permissible value in.
        permissible_value (Any): The permissible value to find.
        schema (SchemaView): The schema view that contains all the enumerations.

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
    return None


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
