"""
For auto IDs. Auto IDs can be specified in mapping config files by using slot names in the form id:idName, where idName is any
string. If these slot names are found then they are automatically added to the LinkML schema (as string slots). When doing
actual mapping of data, we will generate these IDs according to a configuration file, and add the generated IDs to the loaded
source data as new columns before running the LinkML mapper. This allows mapper schemas to access these IDs.
"""

from typing import Any, Union
import pandas as pd
import json
from pathlib import Path
import re

from linkml_runtime import SchemaView
from linkml_runtime.linkml_model.meta import SlotDefinition

from utils.general_utils import get_logger, read_data_frame
from utils.mapper_utils import get_variable_reference, MappingColumns, is_wide_target_value_slot

logger = get_logger(__name__)

class IDConfigColumns:
    # Name of the ID (eg. id:idName, where idName is any string)
    id = "id"
    # How to generate the ID. If in the format {{slotName}} then the ID receives the value found "slotName" of the source
    # class. Otherwise if not empty then the ID receives the constant value. If empty then a random identifier is generated.
    value = "value"
    
class IDType:
    # The type of ID to generate.
    # Copy the value from another slot in the source class.
    variable = "variable"
    # Set the value to a constant value
    constant = "constant"
    # Create a unique random ID
    random = "random"

def is_auto_id(name: Any) -> bool:
    """Determine if the specified variable name represents an auto ID.


    Args:
        name (Any): The variable name to test.

    Returns:
        bool: True if name is an auto ID, False otherwise. An auto id is of the form
            id:idName, where idName can be any string.
    """
    if not isinstance(name, str):
        return False
    return name.startswith("id:")

def add_id_to_schema(schema: SchemaView, cls: str, id_slot_name: str):
    """Add the specified slot (in the specified class) to the specified LinkML schema. The slot is added to the top-most
    "slots" of the schema, as well as in the "slots" and "slot_usage" fields of the class definition.

    Args:
        schema (SchemaView): The schema to modify to include the slot.
        cls (str): The class that the new slot belongs to.
        id_slot_name (str): The name of the slot to add.
    """
    logger.info(f"Adding auto ID '{id_slot_name}' to class '{cls}'")
    # Make sure the id_slot_name exists in the top-most schema slots
    if id_slot_name not in schema.all_slots():
        defn = SlotDefinition(id_slot_name, from_schema=schema.schema.id)
        schema.add_slot(defn)
    
    # Make sure id_slot_name exists in both slots and slot_usage of the class definition
    class_defn = schema.get_class(cls)
    if id_slot_name not in class_defn.slots:
        defn = SlotDefinition(id_slot_name, range="string", description=f"Auto generated ID for class '{cls}' and slot '{id_slot_name}'")
        class_defn.slots.append(id_slot_name)
        class_defn.slot_usage[id_slot_name] = defn
    
def add_auto_ids_to_schema(schema: SchemaView, df: pd.DataFrame):
    """Using the specified mapping DataFrame (from a mapping config file "maps" or "wide" sheet), create all the
    auto ids found and add them to the schema (in the appropriate classes).

    Args:
        schema (SchemaView): The LinkML schema to add the IDs to.
        df (pd.DataFrame): The DataFrame representing either a "maps" or "wide" sheet of a mapping config file.
            We will look in various columns (eg. sourceSlot, targetValue, wideOtherSlots, *_value columns) and find
            any auto IDs (eg. id:organizationID).
    """
    # Look for IDs in sourceSlot, targetValue, wideOtherSlots, *_target
    for _, row in df.iterrows():
        source_class = row.get(MappingColumns.SOURCE_CLASS, None)
        source_slot = row.get(MappingColumns.SOURCE_SLOT, None)
        wide_other_slots = row.get(MappingColumns.WIDE_OTHER_SLOTS, None)
        target_value = row.get(MappingColumns.TARGET_VALUE, None)
        
        # Check for an ID in sourceSlot
        if source_class and source_slot and is_auto_id(source_slot):
            add_id_to_schema(schema, source_class, source_slot)
            
        # Check for an ID in targetValue
        if source_class and source_slot and is_auto_id(target_value):
            add_id_to_schema(schema, source_class, target_value)
        
        # Check for an ID in wideOtherSlots (a dictionary where the value might be in the form {{id:idSlot}})
        if source_class and source_slot and wide_other_slots and isinstance(wide_other_slots, str):
            wide_other_slots = json.loads(wide_other_slots)
            for value in wide_other_slots.values():
                value = get_variable_reference(value)
                if value and is_auto_id(value):
                    add_id_to_schema(schema, source_class, value)
                    
        # Check all _value columns
        wide_target_value_slots = [s for s in df.columns if is_wide_target_value_slot(s)]
        if len(wide_target_value_slots) > 0:
            for s in wide_target_value_slots:
                value = row.get(s)
                value = get_variable_reference(value)
                if value and is_auto_id(value):
                    add_id_to_schema(schema, source_class, value)

def gen_auto_ids(id_config_file: Union[str, Path], schema: SchemaView, cls: str, df: pd.DataFrame):
    """Using the DataFrame that represents the specified class (cls), add any auto ID columns to the DataFrame that are
    found in the LinkML schema for the specified class. Any slot in the class that is of the form id:idName, where idName is
    any string, will be treated as an auto ID. The values that we set the IDs to depends on how they are configured in 
    id_config_file. These can include constant strings, random IDs, etc.

    Args:
        id_config_file (Union[str, Path]): The auto ID config CSV file. This should include the columns in IDConfigColumns.
        schema (SchemaView): The LinkML schema.
        cls (str): The class that the DataFrame represents.
        df (pd.DataFrame): The DataFrame to add the auto IDs to. This is modified in-place, with the new columns in the form
            id:idName.
    """
    if id_config_file:
        id_config_df = read_data_frame(id_config_file)
    else:
        id_config_df = None
    
    # Get all slots in the class that are given an auto ID name (eg. id:idName)
    class_defn = schema.get_class(cls)
    id_slots = [s for s in class_defn.slots if is_auto_id(s)]
    
    # Go through all auto ID slots and add the generated IDs to the DataFrame.
    if len(id_slots) > 0:
        for id_slot in id_slots:
            value = None
            id_type = IDType.random # Default ID type
            if id_config_df is not None:
                # Get the configuration for the ID slot.
                config_row = id_config_df[id_config_df[IDConfigColumns.id].map(lambda x: re.fullmatch(x, id_slot) is not None)]
                if len(config_row.index) > 1:
                    raise ValueError(f"Found multiple rows for ID '{id_slot}' in ID config file")
                if len(config_row.index) == 1:
                    config_row = config_row.iloc[0]
                    value = config_row[IDConfigColumns.value]
                    variable = get_variable_reference(value)
                    if not value or pd.isna(value):
                        id_type = IDType.random
                    elif variable:
                        id_type = IDType.variable
                    else:
                        id_type = IDType.constant

            # Generate the IDs (add them to the DataFrame)
            if id_type == IDType.random:
                df[id_slot] = [f"{id_slot.replace(':', '_')}_{i}" for i in range(len(df.index))]
            elif id_type == IDType.variable:
                df[id_slot] = df[variable]
            elif id_type == IDType.constant:
                df[id_slot] = value
            else:
                raise RuntimeError(f"Unrecognized ID type for ID '{id_slot}' with config value '{value}'")
