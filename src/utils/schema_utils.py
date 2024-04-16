#%%
"""
Utility functions for LinkML schemas.
"""
from typing import Dict
from dataclasses import asdict

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
    
def get_range_of_slot(cls: str, slot: str, schema: SchemaView) -> str:
    """Get the range (if any) of the slot in the specified class.

    Args:
        cls (str): The class that the slot belongs to.
        slot (str): The slot to get the range for.
        schema (SchemaView): The Schema to retrieve the slot info from.

    Returns:
        str: The range of the slot in the class. If the slot does not exist or no range is
            specified then None is returned.
    """
    defn = get_slot_definition(cls, slot, schema)
    
    if defn is not None:
        defn = defn.get("range", None)
        if defn is not None:
            defn = str(defn)
    
    return defn

def get_enum_name_for_slot(cls: str, slot: str, schema: SchemaView) -> str:
    """Get the enumeration name (if any) that is the range for the specified slot in the specified
    class.

    Args:
        cls (str): The class that the slot belongs to.
        slot (str): The slot to get the enumeration name for.
        schema (SchemaView): The Schema to retrieve the enumeration from.

    Returns:
        str: The name of the enumeration that is the range of slot. If slot does
            not have an enumeration for a range then None is returned.
    """
    rng = get_range_of_slot(cls, slot, schema)
    
    # See if rng is a name for an enumeration
    enum_definition = schema.get_enum(rng)
    if enum_definition is not None:
        return rng
    
    # rng is not an enumeration
    return None

