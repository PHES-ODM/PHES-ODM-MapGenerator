#%%
"""
Creates the LinkML mapper specification (YAML) files for mapping from ODM v1 to ODM v2.

See make_v1_to_v2.py for usage information.

@TODO:
- There is no mapping from ODM v1 Reporter.contactName to v2. Should we try to populate contacts.firstName
and contacts.lastName from it?
- Reporter table is empty, is this alright?
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

import argparse
import pandas as pd
from pathlib import Path
import yaml
import os
from typing import Tuple, Union, Dict, List, Optional

from linkml_runtime import SchemaView

from utils.general_utils import read_data_frame, get_logger
from utils.mapper_utils import select_required_enum_derivations, expand_wide_derivations
from odm_v2.v2_utils import v2_get_header_rows, v2_class_names
from odm_v2.v2_mapping import V2MappingColumns, V2MappingVariableLocations

V2_PART_ID_COL = "partID"
V2_ENUM_NAME_COL = "v2EnumName"

logger = get_logger(__name__)

def make_enum_derivations(df: pd.DataFrame, source_enum_name: str) -> Dict[str, Dict]:
    """Create the LinkML mapper enum_derivation dictionary for converting the source enumeration
    source_enum_name to the proper ODM v2 enumeration(s).
    
    This function will raise an Exception if the source enumeration maps onto more than two v2 enumerations.
    This is because the LinkML mapper does not allow this, since it has no way of knowing which
    v2 enumeration to map to.

    Args:
        df (pd.DataFrame): The ODM v2 data dictionary parts list, after being prepared by prepare_parts.py.
        source_enum_name (str): The source enumeration name to create the enum_derivation for.

    Returns:
        Dict[str, Dict]: A dictionary where the keys are the target enumeration names and the values are
            the enum derivations for that target. The target name is not a real v2 enumeration name, it
            is a made-up name consisting of both the source enumeration name and the v2 enumeration name. This
            dictionary can be used as the value for the enum_derivations key in a mapper spec file.
            The format is:
                {
                    v2_enum_name : {
                        name : v2_enum_name,
                        mirror_source : False
                        populated_from : source_enum_name,
                        permissible_value_derivations : {
                            ...
                        }
                    },
                    ...
                }
    """
    logger.info(f"Making enum derivation for {source_enum_name}")
    
    # Extract all the parts where the source enumeration name is source_enum_name
    df = df[df[V2MappingColumns.SOURCE_ENUM_NAME].astype(str).str.lower() == source_enum_name.lower()]

    # Get the enumeration name in ODM v2 that source_enum_name maps to. There should always
    # only be one v2 enumeration for each source enumeration
    v2_enum_names = df[V2_ENUM_NAME_COL].unique()
    if len(v2_enum_names) != 1:
        raise RuntimeError(f"Source enumeration {source_enum_name} maps onto more than one v2 enumeration: {v2_enum_names}. This is not allowed by the LinkML mapper!")
    
    # For each of the rows, get the v2 enum name (in V2_ENUM_NAME_COL), source enum value (in Columns.SOURCE_CATEGORY)
    # and the v2 enum value (in V2_PART_ID_COL) that the source enum value maps to. Add it to the permissible
    # value derivations. The permissible value derivation name we add to has a made-up name equal to
    # {source_enum_name}_{v2_enum_name}.
    permissible_value_derivations = {}
    for _, row in df.iterrows():
        v2_enum_name = row[V2_ENUM_NAME_COL]
        v2_target_enum_name = f"{source_enum_name}_{v2_enum_name}"
    
        source_part_id = row[V2MappingColumns.SOURCE_CATEGORY]
        v2_part_id = row[V2_PART_ID_COL]
        
        if v2_target_enum_name not in permissible_value_derivations:
            permissible_value_derivations[v2_target_enum_name] = {}
        
        if v2_part_id in permissible_value_derivations[v2_target_enum_name].keys():
            # There is already an enum value mapping to v2_part_id. We can't specify more than
            # one source enum value in the "populated_from" field, but we can in 
            # the "sources" field. So we add the "sources" field and start adding extra populated_from
            # values there.
            sub_dict = permissible_value_derivations[v2_target_enum_name][v2_part_id]
            if "sources" not in sub_dict:
                sub_dict["sources"] = [sub_dict["populated_from"]]
            sub_dict["sources"].append(source_part_id)
        else:
            # Add the mapping from source_part_id to v2_part_id
            permissible_value_derivations[v2_target_enum_name][v2_part_id] = {
                "name" : v2_part_id,
                "populated_from" : source_part_id,
            }
    
    # Make the full enum derivation that the LinkML mapper recognizes.
    enum_derivations = {
        v2_target_enum_name : {
            "name" : v2_target_enum_name,
            "mirror_source" : False,
            "populated_from" : source_enum_name,
            "permissible_value_derivations" : permissible_values,
        }
        for v2_target_enum_name, permissible_values in permissible_value_derivations.items()
    }
    
    return enum_derivations

def make_class_derivations(df: pd.DataFrame, source_table_name: str, max_mapping_only: bool, custom_wide_dfs: Optional[List[pd.DataFrame]]=None) -> List[Dict]:
    """Make a LinkML mapper class_derivation dictionary for converting the source class source_table_name
    to the proper ODM v2 class.

    Args:
        df (pd.DataFrame): The ODM v2 data dictionary parts list, after being prepared by prepare_parts.py.
        source_table_name (str): The source class name to create the class_derivation for.
        max_mapping_only (bool): If True then we only make derivations to v2 tables that would result
            in copying over the most columns from the source table. If multiple mappings have the
            same maximum number of copied columns, then we make derivations for all of them. If False then we
            create derivations to all v2 tables. (Some of these derivations might be useless, for example if 
            we only copy over a single column).
        custom_wide_dfs (Optional[List[pd.DataFrame]]): Optional list of DataFrames containing information
            for mapping wide-like source columns to long target rows.

    Returns:
        List[Dict]: A list of dictionaries that contain the new class derivations, of the following form:
            {
                "source_class" : source_class_name,
                "target_class" : wide_target_class_name,
                "class_derivation" : {
                    "name" : wide_target_class_name,
                    "populated_from" : source_class_name,
                    "slot_derivations" : { ... }
                }
            }
    """
    # Extract all rows for the table source_table_name
    df = df[df[V2MappingColumns.SOURCE_TABLE].astype(str).str.lower() == source_table_name.lower()]
    
    # Extract all rows where a source variable is specified (for the table source_table_name)
    variables_df = df[df[V2MappingColumns.SOURCE_LOCATION].astype(str).str.lower() == V2MappingVariableLocations.VARIABLES.lower()]
    
    # Obtain all rows for each of the mappings from source_table_name to each of the v2 tables.
    # The keys of mapping_rows are the target v2 table names, and the values are all rows in the DataFrame
    # that contain information about the mappings from source_table_name to the v2 table.
    mapping_rows = { class_name : v2_get_header_rows(variables_df, class_name) for class_name in v2_class_names }
    
    if max_mapping_only:
        # Most of these mappings are useless (eg. if there's only one variable/header row to map,
        # such as "siteID"). To get the most useful one, we pick the mapping where we have the most variables 
        # to map (ie. where mappings_df has to most rows).
        max_rows = max(*[ len(mappings_df.index) for mappings_df in mapping_rows.values() ])
        mapping_rows = { k : v for k, v in mapping_rows.items() if len(v.index) == max_rows}

    # Using each of the v2 target tables and the DataFrame rows that define the mapping from
    # source_table_name to the v2 table, create all of the slot derivations for each mapping.
    results = []
    for target_class_name, mappings_df in mapping_rows.items():        
        # If the mapping only had 1 or fewer maps then return nothing
        if len(mappings_df.index) <= 1:
            continue
        
        slot_derivations = {}
        for _, row in mappings_df.iterrows():
            v2_variable = row[V2_PART_ID_COL]
            source_variable = row[V2MappingColumns.SOURCE_VARIABLE]
            if v2_variable in slot_derivations.keys():
                logger.warning(f"{v2_variable} already found in slot derivations from source table {source_table_name} onto v2 table {target_class_name} (source var={source_variable}, v2 var={v2_variable})")
            cur_derivation = {
                "name" : v2_variable,
                "populated_from" : source_variable,
            }
            slot_derivations[v2_variable] = cur_derivation
            
        has_expanded_wide = False
        if custom_wide_dfs is not None:
            # Custom wide to long mappings are available, so try to create a separate
            # mapping for each wide-to-long column from the source table to target table.
            custom_wide_results = expand_wide_derivations(source_class_name=source_table_name, target_class_name=target_class_name, slot_derivations=slot_derivations, custom_wide_dfs=custom_wide_dfs)
            if len(custom_wide_results) > 0:
                has_expanded_wide = True
                results.extend(custom_wide_results)
    
        if not has_expanded_wide:
            class_derivation = {
                "name" : target_class_name,
                "populated_from" : source_table_name,
                "slot_derivations" : slot_derivations,
            }
            results.append({
                "source_class" : source_table_name,
                "target_class" : target_class_name,
                "class_derivation" : class_derivation                
            })
    
    return results

def make_mappers(mapper_dir: Union[str, Path], prepared_parts_file: Union[str, Path], source_schema_file: Union[str, Path], max_mapping_only: Optional[bool]=True, custom_wide_dir: Optional[Union[List[Union[str, Path]], Union[str, Path]]]=None) -> List[Dict]:
    """Make the LinkML mapper specifications for mapping from all source tables to all ODM v2 tables
    where a mapping between the tables exists. A separate specification is created for each source table to
    v2 table mapping.

    Args:
        mapper_dir (Union[str, Path]): The directory to save the mapper specifications to (they are
            all YAML files).
        prepared_parts_file (Union[str, Path]): The ODM v2 data dictionary parts list, after being prepared
            by odm_v2.prepare_parts.prepare_parts.
        source_schema_file (Union[str, Path]): The LinkML schema for the source of the mapping.
        max_mapping_only (Optional[bool]): If True then for each source table we only make derivations to a
            single v2 table. That v2 table is chosen by selecting the v2 table that would result in copying over
            the most columns from the source table. If False then we create derivations to all v2 tables. (Some of
            these derivations might be useless, for example if we only copy over a single column). Defaults to True.
        custom_wide_dir (Optional[Union[List[Union[str, Path]], Union[str, Path]]]): Directory or list of directories
            that contain CSV files for custom mapping details for mapping wide-like source columns to long
            ODM v2. Defaults to None.

    Returns:
        List[Dict]: A list of dictionaries, where each dictionary contains the source type (source class),
            target type (ODM v2 class), and the path to the mapper spec file for mapping from
            the source type to target type.
    """
    logger.info("Running...")

    schema = SchemaView(source_schema_file)
    
    if isinstance(custom_wide_dir, (str, Path)):
        custom_wide_dir = [custom_wide_dir]
    
    custom_wide_dfs = None
    if custom_wide_dir is not None:
        custom_wide_files = [[os.path.join(d, f) for f in os.listdir(d)] for d in custom_wide_dir]
        custom_wide_files = [f for cf in custom_wide_files for f in cf]
        custom_wide_files = [f for f in custom_wide_files if os.path.splitext(f)[1].lower() in [".csv", ".tsv", ".txt"]]
        custom_wide_files = sorted(custom_wide_files, key=lambda x: os.path.basename(x))
        custom_wide_dfs = [read_data_frame(f, keep_default_na=False, na_values=[""]) for f in custom_wide_files]
    
    # Create the output directory where we save the mapper configurations
    if mapper_dir:
        os.makedirs(mapper_dir, exist_ok=True)
    
    # Read the parts and sets files
    logger.info("Reading dictionary...")
    df = read_data_frame(prepared_parts_file, keep_default_na=False, na_values=[""])
    
    # Make enum derivations using the parts files
    logger.info("Making enum derivations...")
    # Get all known source enumeration names from the parts list
    all_source_enums = sorted(df.loc[~pd.isna(df[V2MappingColumns.SOURCE_ENUM_NAME]), V2MappingColumns.SOURCE_ENUM_NAME].unique())
    enum_derivations = {}
    # Create the derivations for each source enumeration to map to a v2 enumeration
    for source_enum_name in all_source_enums:
        cur_derivations = make_enum_derivations(df, source_enum_name)
        existing_names = set(enum_derivations.keys())
        new_names = set(cur_derivations.keys())

        # Check if any of the v2 enum names (ie the keys of the derivations) already exists
        # These are made-up names and so this test should always pass
        names_intersection = list(existing_names.intersection(new_names))
        if len(names_intersection) != 0:
            raise RuntimeError(f"v2 enum names {names_intersection} already exists in the enum derivations when creating the derivation for {source_enum_name}")

        enum_derivations.update(cur_derivations)
        
    logger.info("Making class derivations...")
    # Get all known source table names from the parts list
    all_source_tables = sorted(df.loc[~pd.isna(df[V2MappingColumns.SOURCE_TABLE]), V2MappingColumns.SOURCE_TABLE].unique())
    
    class_derivations: Dict[str, List[Dict]] = {}

    # Create a class derivation for all source tables to a v2 table.
    for source_table_name in all_source_tables:
        for cur_results in make_class_derivations(df, source_table_name, max_mapping_only=max_mapping_only, custom_wide_dfs=custom_wide_dfs):
            cur_source_name = cur_results["source_class"]
            cur_target_name = cur_results["target_class"]
            cur_dict = cur_results["class_derivation"]
            if cur_target_name is None:
                continue
            logger.info(f"Adding class derivation from {cur_source_name} to {cur_target_name}")
            if cur_target_name not in class_derivations.keys():
                class_derivations[cur_target_name] = []
            class_derivations[cur_target_name].append(cur_dict)

    res = save_all_mappers(class_derivations, enum_derivations=enum_derivations, schema=schema, output_dir=mapper_dir)
    
    logger.info(f"Finished!")
    return res

def save_all_mappers(class_derivations: Dict, enum_derivations: Dict, schema: SchemaView, output_dir: Union[str,  Path]) -> List[Dict]:
    """ For each class derivation, create a separate mapper specification file (yaml file).
    These specs each map from a single source table to a single v2 table.
    
    A top-level Container class derivation will also be added to each YAML file. The slot
    derivations will have keys for the target class with populated_from fields from the source class.

    Args:
        class_derivations (Dict): Dictionary of all class derivations. A separate YAML file will be created
            for each individual class derivation. The keys are the target class names and the values are
            the class derivation for the target class. class_derivations is of the form:
                {
                    target_class_1 : {
                        name: target_class_1,
                        populated_from: source_class,
                        slot_derivations: { ... }
                    },
                    target_class_2 : { ... },
                    ...
                }                    
        enum_derivations (Dict): All possible enum derivations. For each class derivation we will only select
            the enum derivations that are required by the class derivation.
        schema (SchemaView): The schema of the source database for all the class derivations.
        output_dir (Union[str,  Path]): Directory to save all mapper YAML files to.

    Returns:
        List[Dict]: List of dictionaries with info for all saved mapper files. Dictionaries contain
            the source class, target class, and saved file location:
                [
                    {
                        "source_class" : source_class,
                        "target_class" : target_class,
                        "mapper_file" : "path/to/mapper.yaml"
                    },
                    ...
                ]
    """
    results = []
    for target_class, cur_derivations in class_derivations.items():
        for cur_derivation in cur_derivations:
            source_class = cur_derivation["populated_from"]
            
            # Get all the enumeration derivations required by the current class derivation (ie. any enum present in
            # a "populated_from" field of a slot derivation)
            cur_enum_derivations = select_required_enum_derivations(cur_derivation, enum_derivations, schema=schema)
            
            # Create the mapper spec for the mapping from source_class to target_class (v2).
            mapper_spec = {
                "class_derivations" : {
                    target_class : cur_derivation,
                    "Container" : {
                        "name" : "Container",
                        "slot_derivations" : {
                            target_class: {
                                "populated_from" : source_class,
                            }
                        }
                    }
                },
                "enum_derivations" : cur_enum_derivations,
            }
            
            # Save mapper specification to disk
            mapper_file = os.path.join(output_dir, f"mapper-{source_class}-{target_class}.yaml")
            logger.info(f"Saving mapper spec for {source_class} to {target_class}: {mapper_file}")
            with open(mapper_file, "w") as f:
                yaml.dump(mapper_spec, f, indent=2, sort_keys=False)
                
            results.append({
                "source_class" : source_class,
                "target_class" : target_class,
                "mapper_file" : mapper_file,
            })
            
    return results

if __name__ == "__main__":
    if "get_ipython" in globals():
        class opts:
            prepared_parts_file = "../../gen/odm_v1_to_v2/dictionary/parts_prepared.csv"
            data_output_dir = "../../gen/odm_v1_to_v2/mapped_data"
            mapper_dir = "../../gen/odm_v1_to_v2/mappers"
            source_schema = "../../data/odm_v1/linkml/odm_v1.yaml"
            max_mapping_only = True
            custom_wide_dir = "../../gen/odm_v1/custom_wide"
    else:
        args = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
        args.add_argument("--prepared_parts_file", type=str, help="The prepared parts file (prepared by prepare_parts.py) from the ODM v2 data dictionary. Can be a CSV or TSV file", required=True)
        args.add_argument("--mapper_dir", type=str, help="Location to save all mapper config files to", required=True)
        args.add_argument("--data_output_dir", type=str, help="Location to save all mapped data to", required=True)
        args.add_argument("--source_schema", type=str, help="Location of the source LinkML schema", required=True)
        args.add_argument("--custom_wide_dir", help="Directory of CSV files containing custom mappings for wide to long mappings", required=False)
        args.add_argument("--max_mapping_only", help="For each source table, map to only one v2 target table, which is the table that has the most columns to map. If not set then make mapper specs for all source tables to all v2 tables", action="store_true", required=True)
        opts = args.parse_args()
    
    
    make_mappers(mapper_dir=opts.mapper_dir, prepared_parts_file=opts.prepared_parts_file, source_schema_file=opts.source_schema, max_mapping_only=opts.max_mapping_only, custom_wide_dir=opts.custom_wide_dir)
