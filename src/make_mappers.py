#%%
"""
Creates the LinkML mapper config files for mapping from one database format (eg. NWSS) to
another (eg. ODM v2). This is configured with CSV files (usually extracted from Excel files) that
specify both the mappings between source and target classes, wide-to-long columns, and enumeration
mappings.
"""

import argparse
import pandas as pd
from pathlib import Path
from typing import Union, List, Dict, Optional
import os
import yaml
import json

from linkml_runtime import SchemaView

from utils.general_utils import read_data_frame, strip_whitespace, get_logger, order_columns, extend_down, expand_multi_rows, rename_items, EMPTY_PERMISSIBLE_VALUE
from utils.schema_utils import get_enum_name_for_slot
from utils.mapper_utils import select_required_enum_derivations, expand_wide_derivations, get_variable_reference, WideSpecColumns

logger = get_logger(__name__)

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
    EXPR_VALUE = "exprValue"
    CUSTOM_DATA = "customData"
    
    # These columns should only be present in the enums tabs of the mapping files
    SOURCE_ENUM = "sourceEnum"
    TARGET_ENUM = "targetEnum"

def extract_class_derivations(maps_df: pd.DataFrame, source_schema: SchemaView) -> Dict[str, Dict[str, Dict]]:
    """Extract all class derivations from DataFraome from the the mapping file.

    Args:
        maps_df (pd.DataFrame): The mapping DataFrame loaded from the mapping specification file.
        source_schema (SchemaView): The schema that acts as the source for all the mappings (eg. schema
            for NWSS or ODM v1)

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
        expr_value = row[MappingColumns.EXPR_VALUE]
        
        if pd.isna(custom_data):
            custom_data = None
        if pd.isna(expr_value):
            expr_value = None
        
        # Make sure the row's source class exists in the source schema
        if source_class not in source_schema.all_classes():
            logger.error(f"Found source class {source_class} in mapping data but class does not exist in source schema, ignoring row")
            continue
        
        # Get the dictionary for the source_class. Within this dictionary are keys from each target class.
        if source_class not in all_class_derivations:
            all_class_derivations[source_class] = {}
        source_class_derivations = all_class_derivations[source_class]
        
        # Get the derivation targeting the target_class
        if target_class not in source_class_derivations:
            source_class_derivations[target_class] = {
                "name" : target_class,
                "populated_from" : source_class,
                "slot_derivations" : {},
            }
        slot_derivations = source_class_derivations[target_class]["slot_derivations"]
        
        if custom_data or expr_value:
            new_dict = {
                "name" : target_slot,
            }
            # The MappingColumns.CUSTOM_DATA field is set for the current row. This is a dictionary that we merge to the target_slot derivation.
            if custom_data:
                new_dict.update(json.loads(custom_data))
            if expr_value:
                new_dict["expr"] = expr_value
            if target_slot in slot_derivations:
                # The slot derivation for target_slot already exists (ie. it was added in a previous row of maps_df). Here we make sure
                # that the slot derivation for target_slot will be left unchanged.
                if slot_derivations[target_slot] != new_dict:
                    raise ValueError(f"Target slot {target_slot} for source class {source_class} and target class {target_class} already exists in slot_derivations but has different custom fields (expected {new_dict} but found {slot_derivations[target_slot]})")
            slot_derivations[target_slot] = new_dict
        else:
            # Add the slot derivation for target_slot (populating from source_slot)
            if source_slot not in source_schema.class_slots(source_class):
                logger.error(f"Found source slot {source_slot} (in class {source_class}) in mapping data that does not exist in the source schema, ignoring row")
                continue
            if target_slot in slot_derivations:
                if "populated_from" not in slot_derivations[target_slot]:
                    raise ValueError(f"Target slot {target_slot} for source class {source_class} and target class {target_class} already exists in slot_derivations but has different populated_from fields (expected {source_slot} but found Empty)")
                if slot_derivations[target_slot]["populated_from"] != source_slot:
                    raise ValueError(f"Target slot {target_slot} for source class {source_class} and target class {target_class} already exists in slot_derivations but has different populated_from fields (expected {source_slot} but found {slot_derivations[target_slot]['populated_from']})")
            slot_derivations[target_slot] = {
                "name" : target_slot,
                "populated_from" : source_slot
            }
    
    return all_class_derivations

def get_copy_to_slot(df: pd.Series) -> Optional[str]:
    """Get the first found column whose value in the Series is a reference to a source column. ie. a string in the
    form "{{sourceSlot}}". This means that we copy the sourceSlot to a target slot.

    Args:
        df (pd.Series): The series to get a column name where df's value is a copy from a source slot.

    Returns:
        Optional[str]: If a copy value is found then the column in df that the value is found in. If none
            is found then None is returned.
    """
    recognized_columns = [v for k, v in MappingColumns.__dict__.items() if not k.startswith("_")]
    for column in [c for c in df.index if c not in recognized_columns]:
        if get_variable_reference(df[column]) is not None:
            return column
    
    return None

def extract_enum_derivations(maps_df: pd.DataFrame, source_schema: SchemaView, target_schema: SchemaView) -> Dict[str, Dict[str, Dict]]:
    """Extract all enum derivations found within the mapping DataFrame.

    Args:
        maps_df (pd.DataFrame): The mapping DataFrame that contains the information for mapping from the
            source to target schemas. This can be either a maps tab, an enums tab, or a wide tab (which have been
            prepared with prepare_maps_df, prepare_enums_df, and prepare_wide_df).
        source_schema (SchemaView): The source schema for the mapping.
        target_schema (SchemaView): The target schema for the mapping.

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
    # all_enum_derivations[source_class][target_class] are all enum derivations for the source
    # class to the target class. 
    # all_enum_derivations[""][""] are all enum derivations where the source class and target class
    # are not specified (ie. applies to all source/target class pairs).
    # Enum derivations where source_class and target_class are specified take precedence over enum
    # derivations where source_class and target_class are "".
    all_enum_derivations: Dict[str, Dict[str, Dict]] = {}
    for _, row in maps_df.iterrows():
        # Get all the row's data
        source_class = row[MappingColumns.SOURCE_CLASS]
        source_slot = row[MappingColumns.SOURCE_SLOT]
        source_enum_value = row[MappingColumns.SOURCE_VALUE]
        target_class = row[MappingColumns.TARGET_CLASS]
        target_slot = row.get(MappingColumns.TARGET_SLOT, None)
        if not target_slot:
            target_slot = get_copy_to_slot(row)
        target_enum_value = row[MappingColumns.TARGET_VALUE]
        
        variable_match = get_variable_reference(target_enum_value)
        
        # If variable_match had a match (in the form {{variable_match}}, then it means we copy a source slot to the target slot,
        # so we don't need an enum derivation.
        if variable_match is not None:
            continue
        
        # @TODO: Remove this: We should load the NWSS Mapping config file without converting NA to NaNs
        if pd.isna(target_enum_value):
            target_enum_value = ""
            
        # @TODO: Remove this
        if target_enum_value == "see notes":
            target_enum_value = ""
        
        # If both the source enum value and target enum value are empty then this row is not an enumeration, so continue to next loop
        if (pd.isna(source_enum_value) or source_enum_value == "") and (pd.isna(target_enum_value) or target_enum_value == ""):
            continue
        
        if source_enum_value == EMPTY_PERMISSIBLE_VALUE:
            source_enum_value = ""

        # Get source enumeration name, either from the SOURCE_ENUM column or based on the source class and slot
        if MappingColumns.SOURCE_ENUM in row.index:
            # Source enum is available in the row, so use it
            source_enum_name = row[MappingColumns.SOURCE_ENUM]
        else:
            # Get the source enum name based on the range of the slot
            source_enum_name = get_enum_name_for_slot(source_class, source_slot, source_schema)
        # Get the target enumeration name, either from the TARGET_ENUM column or based on the target class and slot
        if MappingColumns.TARGET_ENUM in row.index:
            # Target enum name is available in the row, so use it
            target_enum_name = row[MappingColumns.TARGET_ENUM]
            # If no target enum name is given create a fake name
            if not target_enum_name:
                target_enum_name = f"{target_schema.schema.name}_enum_from_{source_enum_name}"
        else:
            target_enum_name = get_enum_name_for_slot(target_class, target_slot, target_schema)
            # If there is no target enum name (eg. we're mapping from a source slot that is an enum to a target slot that is not an
            # enum), then we create a unique target enum name to use. Target enum names can be anything, they are just placeholders 
            # (but source enum names must be correct).
            if not target_enum_name:
                target_enum_name = f"{target_slot}_from_{source_enum_name}"

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
                "name" : target_enum_name,
                "mirror_source" : False,
                "populated_from" : source_enum_name,
                "permissible_value_derivations" : {},
            }
        # Get the enum derivation for the target enum
        enum_derivation = cur_enum_derivations[target_enum_name]
        if enum_derivation["populated_from"] != source_enum_name:
            # raise ValueError(f"Enum derivation for target {target_enum_name} already exists but does not have a matching populated_from field (expected {source_enum_name} but found {enum_derivation['populated_from']})")
            raise ValueError(f"Enum derivation for source class='{source_class}', target class='{target_class}', target name='{target_enum_name}' already exists but does not have a matching populated_from field (expected '{source_enum_name}' but found '{enum_derivation['populated_from']}')")
        
        # Add the permissible value derivation. Derivation is from source_enum_value to target_enum_value
        # If there is already a permissible value derivation for target_enum_value, then we add the
        # source_enum_value to the permissible value derivation's "sources" field. If there isn't yet a
        # derivation then we add it to the "populated_from" field. The "sources" array field allows for
        # having multiple populated_from values.
        permissible_value_derivations = enum_derivation["permissible_value_derivations"]
        if target_enum_value in permissible_value_derivations:
            sub_dict = permissible_value_derivations[target_enum_value]
            if "sources" not in sub_dict:
                sub_dict["sources"] = [sub_dict["populated_from"]]
            sub_dict["sources"].append(source_enum_value)
        else:
            permissible_value_derivations[target_enum_value] = {
                "name" : target_enum_value,
                "populated_from": source_enum_value,
            }

    return all_enum_derivations

def prepare_maps_df(maps_file: Union[str, Path]) -> pd.DataFrame:
    """Load and prepare the mapping specification file from disk. This DataFrame specifies all
    the mappings other than the wide column mappings (wide columns data is prepared by
    prepare_wide_df).

    Args:
        maps_file (Union[str, Path]): The mapping file to load.

    Returns:
        pd.DataFrame: The loaded and processed mapping data. It will contain the columns found in
            MappingColumns.
    """
    if not maps_file:
        return None
    
    maps_df = read_data_frame(maps_file, keep_default_na=False, na_values=[""])
    maps_df = strip_whitespace(maps_df)

    # Drop empty rows
    maps_df = maps_df.dropna(axis=0, how="all")

    # Extend values downward to fill in missing data
    maps_df = extend_down(maps_df, columns=[MappingColumns.SOURCE_CLASS, MappingColumns.SOURCE_SLOT, MappingColumns.TARGET_CLASS, MappingColumns.TARGET_SLOT])
    
    # @TODO: Remove this once the maps_file is finalized
    if "Complete" in maps_df.columns:
        maps_df = maps_df[maps_df["Complete"] == 1].drop("Complete", axis="columns").reset_index(drop=True)

    maps_df = expand_multi_rows(maps_df, [MappingColumns.TARGET_CLASS, MappingColumns.TARGET_SLOT])
    
    keep_columns = [MappingColumns.SOURCE_CLASS, MappingColumns.SOURCE_SLOT, MappingColumns.SOURCE_VALUE, MappingColumns.TARGET_CLASS, MappingColumns.TARGET_SLOT, MappingColumns.TARGET_VALUE, MappingColumns.EXPR_VALUE, MappingColumns.CUSTOM_DATA]
    maps_df = maps_df[keep_columns]
    
    return maps_df.copy()

def prepare_wide_df(wide_file: Union[str, Path]) -> pd.DataFrame:
    """Load and prepare the wide column configuration file from disk. This DataFrame specifies
    all the columns that act as wide columns in the source schema, along with details for how
    to map the wide columns to the target schema. It may also include some additional enum
    mappings required by the wide columns that are not found in the maps sheet.

    Args:
        wide_file (Union[str, Path]): The path to the wide column configuration data.

    Returns:
        pd.DataFrame: The DataFrame with the wide column information. It will contain the columns
            found in MappingColumns as well as additional columns from WideSpecColumns specifying values used
            when pivoting.
    """
    if not wide_file:
        return None
    
    wide_df = read_data_frame(wide_file, keep_default_na=False, na_values=[""])
    wide_df = strip_whitespace(wide_df)

    # Drop empty rows
    wide_df = wide_df.dropna(axis=0, how="all")

    # Rename the existing columns
    wide_df.columns = rename_items(wide_df.columns, {
        WideSpecColumns.SOURCE_CLASS: MappingColumns.SOURCE_CLASS,
        WideSpecColumns.TARGET_CLASS: MappingColumns.TARGET_CLASS,
        WideSpecColumns.SOURCE_SLOT: MappingColumns.SOURCE_SLOT,
        # CustomWideColumns.TARGET_SLOT: MappingColumns.TARGET_SLOT,
        WideSpecColumns.SOURCE_VALUE: MappingColumns.SOURCE_VALUE,
        WideSpecColumns.TARGET_VALUE: MappingColumns.TARGET_VALUE,
    })
    
    # Extend values downward to fill in missing data
    wide_df = extend_down(wide_df, columns=[MappingColumns.SOURCE_CLASS, MappingColumns.SOURCE_SLOT, MappingColumns.TARGET_CLASS])

    # @TODO: Remove this once the wide_file is finalized    
    if "Complete" in wide_df.columns:
        wide_df = wide_df[wide_df["Complete"] == 1].drop("Complete", axis="columns").reset_index(drop=True)
    
    if WideSpecColumns.OTHER_SLOTS not in wide_df.columns:
        wide_df[WideSpecColumns.OTHER_SLOTS] = None
    
    # Get rid of NAs in the GROUP column. The pd.groupby function skips NA values, but doesn't
    # skip empty "" values.
    if WideSpecColumns.GROUP in wide_df:
        wide_df[WideSpecColumns.GROUP] = wide_df[WideSpecColumns.GROUP].map(lambda x: "" if pd.isna(x) else str(x))
        wide_df.loc[pd.isna(wide_df[WideSpecColumns.GROUP]), WideSpecColumns.GROUP] = ""
    else:
        wide_df[WideSpecColumns.GROUP] = ""

    # Order the columns into a nice order. This isn't necessary but makes it easier to view when debugging.
    wide_df = order_columns(wide_df, [MappingColumns.SOURCE_CLASS, MappingColumns.SOURCE_SLOT, MappingColumns.TARGET_CLASS])
    
    return wide_df.copy()

def prepare_enums_df(enums_file: Union[str, Path]) -> pd.DataFrame:
    """Load and prepare the enums configuration file from disk. This DataFrame specifies enumeration
    mappings from source to target enums (note that enums can also be specified in the maps sheet, via
    prepare_maps_df).

    Args:
        enums_file (Union[str, Path]): The path to the enumeration configuration file.

    Returns:
        pd.DataFrame: The DataFrame with the enums mappings from enums_file.
    """
    if not enums_file:
        return None
    
    enums_df = read_data_frame(enums_file, keep_default_na=False, na_values=[""])
    enums_df = strip_whitespace(enums_df)

    # Drop empty rows
    enums_df = enums_df.dropna(axis=0, how="all")
    
    # Extend values downward to fill in missing data
    enums_df = extend_down(enums_df, columns=[MappingColumns.SOURCE_ENUM, MappingColumns.TARGET_ENUM])

    # @TODO: Remove this once the wide_file is finalized    
    if "Complete" in enums_df.columns:
        enums_df = enums_df[enums_df["Complete"] == 1].drop("Complete", axis="columns").reset_index(drop=True)
    
    # Keep only relevant columns, and make sure the columns exist
    keep_columns = [MappingColumns.SOURCE_SLOT, MappingColumns.SOURCE_ENUM, MappingColumns.SOURCE_VALUE, MappingColumns.TARGET_ENUM, MappingColumns.TARGET_VALUE]
    enums_df[[c for c in keep_columns if c not in enums_df.columns]] = ""
    enums_df = enums_df[keep_columns]
    
    # Make other columns empty
    enums_df[MappingColumns.SOURCE_CLASS] = ""
    enums_df[MappingColumns.TARGET_CLASS] = ""
    
    for column in enums_df.columns:
        enums_df.loc[pd.isna(enums_df[column]), column] = ""

    return enums_df.copy()

def make_wide_derivations(class_derivation: Dict, custom_wide_dfs: List[pd.DataFrame], class_enum_derivations: List[Dict[str, Dict[str, Dict]]], source_schema: SchemaView, target_schema: SchemaView) -> List[Dict]:
    """Based on the provided class derivation, make a separate class derivation for each wide column specified
    in custom_wide_dfs. We will also select all the enum derivations required by the new wide derivations from
    class_enum_derivations.

    Args:
        class_derivation (Dict): The class derivation that acts as the template for all wide derivations.
        custom_wide_dfs (List[pd.DataFrame]): The DataFrame containing the wide column information.
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

    Returns:
        List[Dict]: A list of dictionaries containing all the new derivations. The dictionary has the 
            following keys: "source_class", "target_class", "class_derivation", and "enum_derivations".
            "class_derivation" contains the actual class derivation recognized by the Mapper,
            and "enum_derivations" has all the enum derivations required by the class derivation. Example:
                [
                    {
                        "source_class": "nwss",
                        "target_class": "protocolSteps[000,0002=]",
                        "class_derivation": {
                            "name": "protocolSteps[000,0002=]",
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
        
    filt = (custom_wide_dfs[MappingColumns.SOURCE_CLASS] == source_class_name) & (custom_wide_dfs[MappingColumns.TARGET_CLASS] == target_class_name)
    custom_wide_dfs = custom_wide_dfs[filt].copy()

    results = []
    for idx, (_, group_df) in enumerate(custom_wide_dfs.groupby([MappingColumns.SOURCE_CLASS, MappingColumns.SOURCE_SLOT, MappingColumns.TARGET_CLASS, WideSpecColumns.GROUP])):
        # Get source class and target class
        source_class = group_df[MappingColumns.SOURCE_CLASS].iloc[0]
        target_class = group_df[MappingColumns.TARGET_CLASS].iloc[0]

        # Extract enum derivations from the group. It is in the form group_enum_derivations[source_class][target_class] = { derivations }.
        group_enum_derivations = extract_enum_derivations(group_df, source_schema=source_schema, target_schema=target_schema)
        
        # Extract the wide-to-long data. We only use the first row of the group, since the others are identical other than
        # for the enum derivations.
        group_df = group_df.iloc[[0]].copy()
                
        # Set the columns in the OTHER_SLOTS field. It is a JSON dictionary of column:value pairs
        other_slots = group_df[WideSpecColumns.OTHER_SLOTS].iloc[0]
        if other_slots and isinstance(other_slots, str):
            other_slots = json.loads(other_slots)
            group_df[list(other_slots.keys())] = list(other_slots.values())
        
        group_df = group_df.drop([MappingColumns.SOURCE_SLOT, MappingColumns.SOURCE_VALUE, MappingColumns.TARGET_VALUE, WideSpecColumns.NOTES, WideSpecColumns.OTHER_SLOTS, WideSpecColumns.GROUP], axis=1).copy()
        group_df.columns = rename_items(group_df.columns, {
            MappingColumns.SOURCE_CLASS: WideSpecColumns.SOURCE_CLASS,
            # MappingColumns.SOURCE_SLOT: CustomWideColumns.SOURCE_SLOT,
            MappingColumns.TARGET_CLASS: WideSpecColumns.TARGET_CLASS,
        })
                
        # Pivot the group to long format, keeping id_columns constant for all rows. This is the format that expand_wide_derivations
        # expects (ie. each row in the pivoted table represents the value to place in one column in the output)
        id_columns = [WideSpecColumns.SOURCE_CLASS, WideSpecColumns.TARGET_CLASS]
        group_df = group_df.melt(id_vars = id_columns, var_name = WideSpecColumns.TARGET_SLOT, value_name = WideSpecColumns.TARGET_VALUE)

        # ROW_NUMBER is all the same, since group_df provides all the information for outputing a single row (we do one output
        # row at a time)
        group_df[WideSpecColumns.ROW_NUMBER] = idx
        
        # Clean up group_df by only selecting the WideSpecColumns columns
        group_df = group_df[[WideSpecColumns.SOURCE_CLASS, WideSpecColumns.TARGET_CLASS, WideSpecColumns.ROW_NUMBER, WideSpecColumns.TARGET_SLOT, WideSpecColumns.TARGET_VALUE]]
        
        # Create the derivations for pivoting the single column defined by group_df
        cur_results = expand_wide_derivations(source_class_name=source_class_name, target_class_name=target_class_name, slot_derivations=class_derivation["slot_derivations"], custom_wide_dfs=group_df)
        
        # Add the enum derivations for each of the expanded class derivations
        cur_enum_derivations = list(class_enum_derivations)
        cur_enum_derivations.append(group_enum_derivations)
        cur_enum_derivations = get_class_enum_derivations(source_class, target_class, cur_enum_derivations)
        for results_dict in cur_results:
            results_enum_derivations = select_required_enum_derivations(results_dict["class_derivation"], cur_enum_derivations, schema=source_schema)
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
            key_matches = [k for k, v in results.items() if v["populated_from"] == populated_from]
            if len(key_matches) > 1:
                raise RuntimeError(f"Found {len(key_matches)} existing enum derivations for populated_from value='{populated_from}'")
            elif len(key_matches) == 1:
                # A derivation for v["populated_from"] already exists in results, so delete it
                del(results[key_matches[0]])
            # Add the current derivation
            results[k] = v
            
    return results

def get_class_enum_derivations(source_class: str, target_class: str, class_enum_derivations: List[Dict]) -> Dict:
    """Retrieve all enum derivations that involve mapping from the source_class to target_class from
    class_enum_derivations, and merge them with merge_enum_derivations. This can be run on the value
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
        # First get the derivations in cur_derivations[""][""]
        if source_class or target_class:
            d = cur_derivations.get("", {}).get("", {})
            if len(d) > 0:
                group.append(d)
        # Second get the derivations in cur_derivations[source_class][target_class]
        d = cur_derivations.get(source_class, {}).get(target_class, {})
        if len(d) > 0:
            group.append(d)
    # Merge the list of derivations into a single derivation
    return merge_enum_derivations(group)

def make_mappers(maps_files: Union[Union[str, Path], List[Union[str, Path]]], wide_files: Union[Union[str, Path], List[Union[str, Path]]], enums_files: Union[Union[str, Path], List[Union[str, Path]]], mapper_dir: Union[str, Path], source_schema: Union[str, Path], target_schema: Union[str, Path]):
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
    target_schema = SchemaView(target_schema)

    # Load and prepare the maps files
    maps_df = [prepare_maps_df(f) for f in maps_files]
    maps_df = pd.concat([df for df in maps_df if df is not None]).reset_index(drop=True)
    # Load and prepare the wide-columns files
    wide_dfs = []
    if wide_files is not None and len(wide_files) > 0:
        wide_dfs = [prepare_wide_df(f) for f in wide_files if f]
    # Load and prepare the enums mapping files
    enums_df = None
    if enums_files is not None and len(enums_files) > 0:
        enums_df = [prepare_enums_df(f) for f in enums_files]
        enums_df = pd.concat([df for df in enums_df if df is not None])

    # Extract all enum and class derivations from the maps file and enums files. 
    # (maps|enums)_enum_derivations is in the format (maps|enums)_enum_derivations[source_class][target_class] = {enum_derivations}
    # all_class_derivations is in the format all_class_derivations[source_class][target_class] = {class_derivations}
    maps_enum_derivations = extract_enum_derivations(maps_df, source_schema=source_schema, target_schema=target_schema)
    enums_enum_derivations = extract_enum_derivations(enums_df, source_schema=source_schema, target_schema=target_schema)
    all_class_derivations = extract_class_derivations(maps_df, source_schema=source_schema)
    
    # Go through all the class derivations. Each class derivation is a mapping from a single source class
    # to a single target class. For the class derivation, we make a new modified copy of the class derivation
    # for each wide column (if there are any). We also select only the required enum derivations for each
    # mapping.
    results = []
    for source_class_name, source_class_derivations in all_class_derivations.items():
        for target_class_name, target_class_derivation in source_class_derivations.items():
            has_expanded_wide = False
            for wide_df in wide_dfs:
                # Try to make wide derivations. For each wide column in the source class, there will
                # be a new class derivation for that column. make_wide_derivations will also return
                # all the required enum derivations in results["enum_derivations"].
                custom_wide_results = make_wide_derivations(class_derivation=target_class_derivation, custom_wide_dfs=wide_df, class_enum_derivations=[enums_enum_derivations, maps_enum_derivations], source_schema=source_schema, target_schema=target_schema)
                if len(custom_wide_results) > 0:
                    has_expanded_wide = True
                    results.extend(custom_wide_results)

            if not has_expanded_wide:
                # There were no wide derivations for the source to target class.
                cur_enum_derivations = get_class_enum_derivations(source_class_name, target_class_name, [enums_enum_derivations, maps_enum_derivations])
                enum_derivations = select_required_enum_derivations(target_class_derivation, cur_enum_derivations, schema=source_schema)
                results.append({
                    "source_class" : source_class_name,
                    "target_class" : target_class_name,
                    "class_derivation" : target_class_derivation,
                    "enum_derivations" : enum_derivations
                })

    # Go through all the results and create a mapping spec file for each
    for cur_results in results:
        target_class = cur_results["target_class"]
        class_derivation = cur_results["class_derivation"]
        source_class = cur_results["source_class"]
        enum_derivations = cur_results["enum_derivations"]
        # Create the mapping spec for the mapping from source_class to target_class
        mapper_spec = {
            "class_derivations" : {
                target_class : class_derivation,
                "Container" : {
                    "name" : "Container",
                    "slot_derivations" : {
                        target_class: {
                            "populated_from" : source_class,
                            # @TODO: Remove "range" : "string": This is only included to remove warnings
                            # of unknown target range of target_class
                            "range" : "string",
                        }
                    }
                }
            },
            "enum_derivations" : enum_derivations,
        }
        
        # Save mapper specification to disk
        mapper_file = os.path.join(mapper_dir, f"mapper-{source_class}-{target_class}.yaml")
        logger.info(f"Saving mapper spec for {source_class} to {target_class}: {mapper_file}")
        with open(mapper_file, "w") as f:
            yaml.dump(mapper_spec, f, indent=2, sort_keys=False)

if __name__ == "__main__":
    if "get_ipython" in globals():
        dictionary_type = "reporting"
        class opts:
            maps_files = [f"../gen/nwss_{dictionary_type}_to_v2/dictionary/maps0.csv"]
            wide_files = [f"../gen/nwss_{dictionary_type}_to_v2/dictionary/wide0.csv"]
            enums_files = [f"../gen/nwss_{dictionary_type}_to_v2/dictionary/enums0.csv"]
            mapper_dir = f"../gen/nwss_{dictionary_type}_to_v2/mappers"
            source_schema = f"../data/nwss_{dictionary_type}/linkml/nwss_{dictionary_type}.yaml"
            target_schema = "../data/odm_v2/linkml/odm_v2.yaml"
    else:
        args = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
        args.add_argument("--maps_files", type=str, nargs="+", help="The configuration file(s) specifying how to map slots from the source dataset to the target dataset. Can be a CSV or TSV file", required=True)
        args.add_argument("--wide_files", type=str, nargs="+", help="The configuration file(s) specifying any wide columns in the mapping. Can be CSV or TSV files", required=False)
        args.add_argument("--enums_files", type=str, nargs="+", help="The configuration file(s) specifying any enumerations in the mapping. Can be CSV or TSV files", required=False)
        args.add_argument("--mapper_dir", type=str, help="Location to save all mapping config files to", required=True)
        args.add_argument("--source_schema", type=str, help="Location of the source LinkML schema", required=True)
        args.add_argument("--target_schema", type=str, help="Location of the target LinkML schema", required=True)
        opts = args.parse_args()
    
    logger.info("Running...")

    # @TODO Remove extract_sheets, this is done in make_mappers_cli.py
    # Extract the required sheets from the NWSS to ODM 2 mapping file
    from utils.general_utils import extract_sheets
    mapping_config_file = "../data/mapping_config_files/NWSS-to-ODM-dictionary.xlsx"
    dictionary_dir = f"../gen/nwss_{dictionary_type}_to_v2/dictionary/"
    extract_sheets(mapping_config_file, ["maps", "wide", "enums"], dictionary_dir, output_names=["maps0", "wide0", "enums0"], na_values={}, default_na_values=[""])

    make_mappers(maps_files=opts.maps_files, wide_files=opts.wide_files, enums_files=opts.enums_files, mapper_dir=opts.mapper_dir, source_schema=opts.source_schema, target_schema=opts.target_schema)

    logger.info("Finished!")
    