#%%
"""
Map data in a directory using all the mapper specification (YAML) files found in another directory.

## Usage

Mapping data requires:

1) A source schema (eg. NWSS)
2) A target schema (eg. ODM v2)
3) Generated mapping specification (YAML) files
4) Input data

If the input data is large, performance can be improved by increasing the number of processes,
by changing the `max_processes` parameter in the call to `map`. For small datasets multi-processing
might not have any improvement (and may in fact be slower).

### Python

```python
from utils.general_utils import clear_dirs
from map_data import map

clear_dirs(["../gen/nwss_reporting_to_v2/mapped_data"])
map(
    source_schema_file="../data/nwss_reporting/linkml/nwss_reporting.yaml", 
    target_schema_file="../data/odm_v2/linkml/odm_v2.yaml", 
    mapper_dir="../gen/nwss_reporting_to_v2/mappers", 
    data_dir="path/to/input/data", 
    data_output_dir="../gen/nwss_reporting_to_v2/mapped_data", 
    max_processes=1
    )
    
### Command-Line

To map data from the command-line, execute the following for NWSS reporting to ODM v2 (replacing values
where appropriate):

```console
cd src
python3 map_data.py --source_schema "../data/nwss_reporting/linkml/nwss_reporting.yaml" \
    --target_schema "../data/odm_v2/linkml/odm_v2.yaml" \
    --mapper_dir "../gen/nwss_reporting_to_v2/mappers" \
    --data_dir "path/to/input/data" \
    --output_dir "../gen/nwss_reporting_to_v2/mapped_data" \
    --max_processes 1
```
"""

from pathlib import Path
from typing import Union, Optional, List, Dict, Any
import os
import math
import yaml
import pandas as pd
import logging
import argparse
from datetime import datetime
from multiprocessing import Queue, Pool, cpu_count

from linkml_map.session import Session
# from linkml_transformer.session import Session
from linkml_runtime import SchemaView
from linkml_runtime.linkml_model import SlotDefinition

from utils.general_utils import save_data_frame, read_data_frame, get_logger, order_columns, choose_ignore_case_value, get_class_name_from_file_name, clear_dirs
from utils.auto_id import gen_auto_ids

logger = get_logger(__name__)

class TrackingColumns:
    ROW_NUMBER = "(___row_number___)"

# Change the logging level of the Transformer. For very large datasets we will get way too many WARNINGs in
# the output.
for logger_name in [ 
                    "linkml_map.transformer.object_transformer", 
                    "linkml_map.transformer.transformer" 
                    ]:
    trlogger = logging.getLogger(logger_name)
    trlogger.setLevel("ERROR")

def load_data(data_dir: Union[str, Path], schema: Union[str, SchemaView], id_config_file: Union[str, Path]) -> Dict[str, List[Dict]]:
    """Load all data files (CSV, TSV, and TXT files) from disk in a format compatible with the
    LinkML Mapper.

    Args:
        data_dir (Union[str, Path]): Directory where all data files are located. We load all CSV files
            as well as all TSV and TXT (tab-separated) files.
        schema (Union[str, SchemaView]): The schema that the data should conform to.
        id_config_file (Union[str, Path]): File containing the configuration for generating IDs. If
            empty then no ID generation is performed.

    Returns:
        Dict[str, List[Dict]]: Dictionary of all data. Keys are the class/table names and values are
            the rows. The class that each loaded file belongs to is determined by the file name, which
            should be in the format "class_name[extra_stuff].ext" where "extra_stuff" can be any
            additional text that is ignored.
    """
    # Read all the data from disk.
    logger.info(f"Reading all data from {data_dir}...")
    
    if isinstance(schema, str):
        schema = SchemaView(schema)
    
    data = {}    
    for file in os.listdir(data_dir):
        if os.path.splitext(file)[1].lower() in [".csv", ".tsv", ".txt"]:
            # Get the class name, which is the file name (without extension and ignoring case)
            class_name = get_class_name_from_file_name(file)
            class_name = choose_ignore_case_value(class_name, list(schema.all_classes().keys()))
            
            # Skip if the file name is not a recognized class
            if class_name not in schema.all_classes():
                continue
            
            logger.info(f"Reading data file {file}...")
            df = read_data_frame(os.path.join(data_dir, file), keep_default_na=False, na_values=None)
            if df is None or len(df.index) == 0:
                continue
            
            # Add auto-generated IDs
            gen_auto_ids(id_config_file, schema, class_name, df)
            
            # Make sure all columns exist (except for TrackingColumns.ROW_NUMBER, which we add later)
            class_definition = schema.induced_class(class_name)
            missing_slots = [s for s in class_definition.attributes if s not in df.columns and s != TrackingColumns.ROW_NUMBER]
            # @TODO: eval_utils.py (that evaluates "expr" values in mapper specs) raises an exception if any
            # variable it accesses is None. To avoid this we set missing slots to "" instead of None. (Do a PR with
            # changes to eval_utils.py to support None variables)
            df[missing_slots] = ""

            # Only keep recognized slots
            recognized_slots = [s for s in df.columns if s in class_definition.attributes]
            df = df[recognized_slots]
            
            # Add the row number. The mappers will copy this row number to the mapped target data,
            # allowing us to sort the target data to retain the initial ordering in the source data.
            if TrackingColumns.ROW_NUMBER in df.columns:
                raise ValueError(f"Loaded data already has row number column. The row number column named '{TrackingColumns.ROW_NUMBER}' must be removed before proceeding.")
            df[TrackingColumns.ROW_NUMBER] = df.index
            df[TrackingColumns.ROW_NUMBER] = df[TrackingColumns.ROW_NUMBER].map(lambda x: f"{file}-{x:010d}")
            
            # Reorient the data to a format recognized by the mapper (an array of rows, where
            # each row is a dictionary of the form {column_name:value, ...})
            cur_data = [{ c: v for c, v in r.items() } for _, r in df.iterrows() ]
            if class_name not in data:
                data[class_name] = []
            data[class_name].extend(cur_data)
            logger.info(f"Data file has {len(cur_data)} rows: {file}")
    
    return data

def add_row_number_derivation(spec: Dict):
    """Add a slot derivation for all class derivations in the mapper spec to copy over the row number
    (in the column TrackingColumns.ROW_NUMBER) to the output. The row number allows us to sort the output
    by input row number, to maintain a nice ordering.
    
    A row number slot should be called on the source and target schemas by calling add_row_number_slot.
    The TrackingColumns.ROW_NUMBER column should also be set when loading the source data from disk.

    Args:
        spec (Dict): The mapper spec to add a row number slot derivation to all classes.
    """
    for cls, class_derivation in spec["class_derivations"].items():
        class_derivation["slot_derivations"][TrackingColumns.ROW_NUMBER] = {
            "name" : TrackingColumns.ROW_NUMBER,
            "populated_from" : TrackingColumns.ROW_NUMBER,
        }

def add_row_number_slot(schema: SchemaView):
    """Add a row number slot (in the column TrackingColumns.ROW_NUMBER) to all classes in the schema.
    
    The row number slot contains the row number of the source data set (added after loading from disk).
    We copy this row number to the target data when mapping, then sort the target data by input
    row number to maintain a consistent ordering of the output. The mapper specs should also
    be modified with add_row_number_derivation to do the actual copying of row number.

    Args:
        schema (SchemaView): The schema to add a row number slot to (for all classes).
    """
    for cls, slot_definition in schema.schema.classes.items():
        slot_definition.slots.append(TrackingColumns.ROW_NUMBER)
        
    schema.schema.slots[TrackingColumns.ROW_NUMBER] = SlotDefinition(name=TrackingColumns.ROW_NUMBER, from_schema = schema.schema.id)

def run_mapper(data: Dict[str, List], session: Session, data_output_dir: Union[str, Path], mapper_file: Union[str, Path], target_schema: SchemaView, file_index: Optional[int] = None, unrestricted_eval: bool = False) -> Dict[str, List[Dict]]:
    """Run the mapper on the specified data using the specified mapper YAML file and save the
    results to disk.

    Args:
        data (Dict): The input data to map. The keys specify the table/class names and the values are the rows of
            the tables. The rows are dictionaries.
        session (Session): The linkml_map.session.Session object to use for running the mapper.
        data_output_dir (Union[str, Path]): Directory to save the output to. The outputs are CSV files
            with a name based on the mapper_file name.
        mapper_file (Union[str, Path]): The mapper config (YAML) file for the mapper to use.
        target_schema (SchemaView): The SchemaView of the target schema.
        file_index (Optional[int]): Optional file index to add to the output file name. It's just an extra number
            so that we can differentiate between different runs of the mapper when using the same
            mapper_file. It is required if we run the mapper more than once with the same
            mapper_file, as it ensures that the filename of the output is different for each run
            (assuming we properly use unique file_index values for each run).
        unrestricted_eval (Optional[bool]): If True then run expr code in slot derivations in unrestricted mode
            (ie. allow any Python code to execute).

    Returns:
        Dict[str, List[Dict]]: The mapped data, where the keys are the output class names and the
            values are the rows. The rows are dictionaries.
    """
    # Load the mapper spec
    with open(mapper_file, "r") as f:
        mapper_spec = yaml.safe_load(f)
        
    # Add a slot derivation to all class derivations to copy over the row number from the source table to target table.
    # This allows us to sort the output by the input row number to retain a nice ordering. (We delete the row
    # number column in the final output after sorting)
    add_row_number_derivation(mapper_spec)
    
    # Run the mapper to get the mapped data
    logger.info(f"Mapping data with mapper spec {mapper_file}")
    trans_tic = datetime.now()
    session.set_object_transformer(mapper_spec)
    session.object_transformer.unrestricted_eval = unrestricted_eval
    mapped_data = session.transform(data)
    logger.info(f"Mapped in {datetime.now() - trans_tic} (for mapper spec {mapper_file})")
    
    # Convert the data to a DataFrame, store in all_mapped_data, and save to disk
    all_mapped_data = {}
    for target_type, target_data in mapped_data.items():
        if target_data is None:
            continue
        
        # Remove any extra info from the target_type
        # eg "protocolSteps[inhibition]" becomes "protocolSteps"
        target_type = get_class_name_from_file_name(target_type, target_schema)

        df = pd.DataFrame(target_data)

        # Add any missing columns and order them according to the target schema
        if target_schema is not None:
            class_definition = target_schema.induced_class(target_type)
            all_slots = list(class_definition.attributes.keys())
            missing = [s for s in all_slots if s not in df.columns]
            if len(missing) > 0:
                df[missing] = None
            df = order_columns(df, all_slots)
        
        # Keep a copy of the mapped data
        if target_type not in all_mapped_data:
            all_mapped_data[target_type] = []
        all_mapped_data[target_type].append(df)

        # Save the mapped data to disk
        if data_output_dir is not None:
            file_index_tag = f"-{file_index:03d}" if file_index is not None else ""
            output_data_file = os.path.join(data_output_dir, f"%s-{target_type}{file_index_tag}.csv" % os.path.splitext(os.path.basename(mapper_file))[0])
            logger.info(f"Saving mapped data file for {target_type} ({len(df.index)} rows): {output_data_file}")
            keep_columns = [c for c in df.columns if c != TrackingColumns.ROW_NUMBER]
            save_data_frame(df[keep_columns], output_data_file, index=False)    
            
    return file_index, all_mapped_data

def _run_mapper_with_kwargs(kwargs: Dict) -> Dict[str, List[Dict]]:
    """Call run_mapper with the specified kwargs as named parameters.

    Args:
        kwargs (Dict): Dictionary of key-values to pass to run_mapper.

    Returns:
        Dict[str, List[Dict]]: The result of running run_mapper.
    """
    return run_mapper(**kwargs)

def make_data_splits(data: Dict[str, List], num_splits: int, min_split_size: int=100) -> List[Dict[str, List[Dict]]]:
    """Split the data into multiple smaller data splits, to make it easier to use for multiprocessing.
    Each split can be used by run_mapper.

    Args:
        data (Dict[str, List]): The data to split. The keys are the source table names and the values
            are the rows of the data.
        num_splits (int): The number of splits to create.
        min_split_size (int, optional): If all tables when split will result in splits less
            than this many rows then no splitting is performed and instead the list [data] is returned.
            Defaults to 100.

    Returns:
        List[Dict[str, List[Dict]]]: The data splits. Each element of the array is in the same format
            as the passed in data parameter, but will possibly have missing tables (due to the table
            being fully included in earlier tables in the split) and will have possibly have fewer
            rows per table (from making the splits).
    """
    data_splits = []
    max_len = max([len(d) for d in data.values()])
    rows_per_split = math.ceil(max_len / num_splits)
    if rows_per_split < min_split_size:
        return [data]
    split_num = 0
    while True:
        # Make the data splits for each table
        split_data = {
            c: d[split_num*rows_per_split:(split_num+1)*rows_per_split] for c, d in data.items()
        }
        # Remove any key where the table is empty
        split_data = {
            c: d for c, d in split_data.items() if len(d) > 0
        }
        # If all tables were empty then we're done
        if len(split_data.keys()) == 0:
            break
        
        data_splits.append(split_data)
        split_num += 1
    return data_splits

def map(source_schema_file: Union[str, Path], target_schema_file: Union[str, Path], mapper_dir: Union[str, Path], data_dir: Union[str, Path], data_output_dir: Optional[Union[str, Path]] = None, id_config_file: Union[str, Path] = None, max_processes: Optional[int] = 1) -> Dict[str, List[Dict]]:
    """Run the mapper using all mapper files found in the specified mapper directory and on all 
    data files found in the specified data directory. The results are returned and optionally saved to disk.
    
    The results will be saved to data_output_dir. The file names will match the mapper config file's name
    used to map the data (from mapper_dir), along with an extra number that differentiates the
    data splits used for multi-processing. The final outputs will also be merged into single tables and
    saved as the target table's name.

    Args:
        source_schema_file (Union[str, Path]): The LinkML schema for the source database.
        target_schema_file (Union[str, Path]): The LinkML schema for the target database.
        mapper_dir (Union[str, Path]): The directory containing all LinkML Mapper configuration (YAML)
            files. All config files will be used for mapping all the loaded data.
        data_dir (Union[str, Path]): The directory containing all the data from the source database to
            map. They can be CSV (comma-separated) or TSV/TXT (tab-separated) files. The file names
            should be of the form "class_name[extra_stuff].ext", where "class_name" is the source class name
            and "extra_stuff" is any extra string (which is ignored).
        data_output_dir (Optional[Union[str, Path]], optional): Directory to save the mapped output to. If None
            then the mapped data are not saved to disk, but are still returned. Defaults to None.
        id_config_file (Union[str, Path], optional): File containing the configuration for generating IDs. If
            empty then no ID generation is performed. Defaults to None
        max_processes (Optional[int], optional): Maximum number of processes to use for multi-processing.
            If 1 then no multi-processing will be performed. If None or 0 then the maximum number
            (as obtained by cpu_count()) will be used. Note that for mapping small tables multi-processing
            might be slower. Defaults to 1.

    Returns:
        Dict[str, List[Dict]]: The mapped data. Each key is the target class name and
            the values are the rows.
    """
    tic = datetime.now()

    logger.info(f"Beginning mapping at {tic}")

    if not max_processes or max_processes <= 0:
        max_processes = cpu_count()

    source_schema = SchemaView(source_schema_file)
    target_schema = SchemaView(target_schema_file) if target_schema_file else None
    
    # Add a row number slot to the source and target schemas. This is a temporary slot that contains the row number of
    # the initial input tables. It allows us to sort the outputs by the input row number. Once sorting is complete we
    # delete the row number column from the final output.
    # After loading the mapper spec we also add a slot derivation for all classes to copy the row number slot to
    # the output (see add_row_number_derivation)
    add_row_number_slot(source_schema)
    if target_schema:
        add_row_number_slot(target_schema)

    # Read all the data from disk.
    data = load_data(data_dir, source_schema, id_config_file=id_config_file)
    
    if len(data) == 0:
        logger.warning("No data loaded from disk. Be sure the file names match the source schema table names, that there are files in the directory, and that the files are not empty.")
        return {}
    
    logger.info(f"Data loaded for source tables: {list(data.keys())}")
    
    if max_processes == 1:
        split_data = [data]
    else:
        # @TODO: Remove min_split_size=1
        split_data = make_data_splits(data, num_splits=max_processes, min_split_size=1)
    
    # Set up the LinkML Mapper Session
    logger.info("Creating Session for mapping")
    t = datetime.now()
    session = Session()
    session.set_source_schema(source_schema)
    logger.info(f"Finished creating Session for mapping in {datetime.now() - t}")
        
    # Collect all mapper config (yaml) files
    mapper_files = [f for f in sorted(os.listdir(mapper_dir)) if os.path.splitext(f)[1].lower() in [".yaml"]]
    mapper_files = [os.path.join(mapper_dir, f) for f in mapper_files]
    
    # Sort by decreasing data size, to maximize overlap of multiprocessing
    # mappers = { f: yaml.safe_load(open(f, "r"))["class_derivations"] for f in mapper_files }
    # source_classes = { f: d[list(d.keys())[0]]["populated_from"] for f, d in mappers.items() }
    # source_class_sizes = { f: len(data.get(c, [])) for f, c in source_classes.items() }
    # mapper_files = sorted(mapper_files, key=lambda c: -source_class_sizes[c])
    
    # Create arguments to pass to _run_mapper for each mapper config file.
    map_args = []
    for split_num, split in enumerate(split_data):
        cur_args = [{
            "file_index": split_num+file_num*len(mapper_files),
            "data": split,
            "data_output_dir": data_output_dir,
            "session": session, 
            "mapper_file": mapper_file,
            "target_schema": target_schema,
            "unrestricted_eval": True,
        } for file_num, mapper_file in enumerate(mapper_files)]
        map_args.extend(cur_args)
    
    # Call _run_mapper, either using multiple processes or one at a time
    if max_processes == 1:
        logging.info(f"Running without multiprocessing")
        results = []
        for args in map_args:
            results.append(_run_mapper_with_kwargs(args))
    else:
        logging.info(f"Running with {max_processes} processes")
        pool = Pool(max_processes)
        results = pool.map(_run_mapper_with_kwargs, map_args)
        
    # Collect all the results in a single Dictionary. The keys are the target class and the
    # values are Lists of the resulting DataFrames.
    all_mapped_data = {}
    results = sorted(results, key=lambda x: x[0])
    for _, cur_mapped_data in results:
        for cls, mapped_data in cur_mapped_data.items():
            if cls not in all_mapped_data:
                all_mapped_data[cls] = []
            all_mapped_data[cls].extend(mapped_data)
        
    # Some target tables have multiple source tables (ie. multipled DataFrames for a target table). Combine
    # the multiples and save the combined DataFrames to disk.
    if data_output_dir is not None:
        logger.info("Combining and saving DataFrames...")
        for target_type, all_df in all_mapped_data.items():
            df = pd.concat(all_df, axis=0)
            # Retain the original order by sorting by ROW_NUMBER. ROW_NUMBER was added in code with the integer row number,
            # so that we can sort the output DataFrame by row number.
            # df[TrackingColumns.ROW_NUMBER] = df[TrackingColumns.ROW_NUMBER].astype(int)
            df = df.sort_values(TrackingColumns.ROW_NUMBER, axis=0, kind="stable").drop(TrackingColumns.ROW_NUMBER, axis=1)
            output_data_file = os.path.join(data_output_dir, f"{target_type}.csv")
            logger.info(f"Saving merged mapped data file for {target_type} ({len(all_df)} source frame(s), {len(df.index)} rows): {output_data_file}")
            save_data_frame(df, output_data_file, index=False)

    logger.info(f"Finished all mappings in {datetime.now() - tic}")
    
    return all_mapped_data

if __name__ == "__main__":
    if "get_ipython" in globals():
        class opts:
            # ODM v1 to v2
            # source_schema = "../data/odm_v1/linkml/odm_v1.yaml"
            # mapper_dir = "../gen/odm_v1_to_v2/mappers"
            # data_dir = "../gen/odm_v1_to_v2/cleaned_data"
            # output_dir = "../gen/odm_v1_to_v2/mapped_data"
            # target_schema = "../data/odm_v2/linkml/odm_v2.yaml"

            # NWSS to v2
            dictionary_type = "reporting"
            source_schema = f"../gen/nwss_{dictionary_type}_to_v2/linkml_for_mapping/nwss_{dictionary_type}.yaml"
            mapper_dir = f"../gen/nwss_{dictionary_type}_to_v2/mappers"
            data_dir = f"../gen/nwss_{dictionary_type}_to_v2/cleaned_data"
            output_dir = f"../gen/nwss_{dictionary_type}_to_v2/mapped_data"
            target_schema = "../data/odm_v2/linkml/odm_v2.yaml"
            id_config = f"../data/mapping_config_files/id_config.csv"

            max_processes = 1
    else:
        args = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
        args.add_argument("--source_schema", type=str, help="LinkML Schema file for the source", required=True)
        args.add_argument("--target_schema", type=str, help="Optional LinkML Schema file for the target. If specified then the mapped data will contain all columns specified in the target schema, even if all rows are blank. Columns will also be in the order specified in the schema", required=False)
        args.add_argument("--mapper_dir", type=str, help="Directory that contains all the mapper specifications. We will use all of the YAML files in this directory and run a separate mappings on the data for each YAML file", required=True)
        args.add_argument("--data_dir", type=str, help="Directory containing all of the (cleaned) input data to map. The file names (without extension) correspond to the table name. These files should have been cleaned by clean_v1_data.py", required=True)
        args.add_argument("--output_dir", type=str, help="Directory to save all the mapped data to", required=True)
        args.add_argument("--max_processes", type=int, help="Maximum number of processes to run at a time for mapping the data. If non-positive then the max available processes are used.", default=1, required=False)
        args.add_argument("--id_config", type=str, help="Configuration file for generating IDs", required=False)
        opts = args.parse_args()

    clear_dirs([opts.output_dir])
    map(source_schema_file=opts.source_schema, target_schema_file=opts.target_schema, mapper_dir=opts.mapper_dir, data_dir=opts.data_dir, data_output_dir=opts.output_dir, id_config_file=opts.id_config, max_processes=opts.max_processes)
