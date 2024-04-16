#%%
"""
Utility functions for cleaning data.

fix_data_with_schema will make sure column names have the correct capitalization (ie. they match the slots in the schema).
It will also go through all columns that are enumerations and correct the capitalization of all values in the column.
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from pathlib import Path
import pandas as pd
import os
import argparse
from typing import Tuple, List, Union, Optional

from linkml_runtime import SchemaView

from utils.general_utils import read_data_frame, save_data_frame, get_logger, choose_ignore_case_value, get_class_name_from_file_name
from utils.schema_utils import get_range_of_slot

logger = get_logger(__name__)

def fix_data_with_schema(df: pd.DataFrame, class_name: str, schema: SchemaView) -> pd.DataFrame:
    """Using the specified schema, do some basic cleanup of the DataFrame so that it better matches
    the requirements of the schema. We will make sure the column names and enumeration values have the
    correct capitalization, and drop any columns that are not recognized by the schema.

    Args:
        df (pd.DataFrame): The DataFrame to clean up. The original is left unchanged (a copy is returned).
        class_name (str): The class name of the table.
        schema (SchemaView): The LinkML schema to use for making any corrections to the data.

    Returns:
        pd.DataFrame: A copy of the DataFrame, with the basic cleanup performed.
    """
    # if class_name not in schema.all_classes():
    #     logger.info(f"Not fixing data for class {class_name} since class is not recognized")
    #     return df
    
    # logger.info(f"Fixing data for class {class_name}")
    # df = df.copy()

    # class_definition = schema.induced_class(class_name)
    
    # # Fix up column names (Use correct capitalization)
    # df.columns = [choose_ignore_case_value(col, list(class_definition.attributes.keys())) for col in df.columns]
    
    # # Fix enumerations (Use correct capitalization), and only keep recognized slots
    # keep_columns = []
    # for slot_name in df.columns:
    #     if slot_name not in class_definition.attributes:
    #         continue
    #     keep_columns.append(slot_name)
    #     slot_range = get_range_of_slot(class_name, slot_name, schema)
        
    #     # Get enumeration for the slot range, if there is one, and fix up the capitalization of all slot values.
    #     enum = schema.all_enums().get(str(slot_range), None)
    #     if enum is not None:
    #         permissible_values = list(enum.permissible_values.keys())
    #         lowercase_permissible_values = [v.lower() for v in permissible_values]
    #         df[slot_name] = df[slot_name].apply(lambda x: choose_ignore_case_value(x, permissible_values, lowercase_permissible_values))
    
    # return df[keep_columns]
    return df

def fix_data_no_schema(df: pd.DataFrame) -> pd.DataFrame:
    """Do some general fixes to the DataFrame. This includes converting dates and datetimes to proper format
    (as recognized by LinkML), and converting booleans to "true"/"false" strings. These are all fixes
    that are independent of any LinkML schema.

    Args:
        df (pd.DataFrame): The DataFrame to fix.

    Returns:
        pd.DataFrame: The fixed DataFrame. The original is left unchanged, this is a copy.
    """
    # df = df.copy()
    # for col in df.columns:
    #     if df[col].dtype != object:
    #         continue
    #     try:
    #         # First try to parse a date without time, then convert back to a string
    #         # recognizable by linkml as a date
    #         df[col] = pd.to_datetime(df[col], format="%Y-%m-%d").dt.strftime("%Y-%m-%d")
    #     except Exception:
    #         try:
    #             # Try to prase a date with time in ISO8601 format, then convert back to a string
    #             # recognizable by linkml as a datetime
    #             df[col] = pd.to_datetime(df[col], format="ISO8601", utc=True).dt.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    #         except Exception:
    #             ...
    #     # @TODO: We don't need this! Only ODM v2 uses lowercase "true"/"false" strings, but we should
    #     # not have specialized code to fix this.
    #     # Convert bools (True/False) to strings ('true'/'false')
    #     for col in df.columns:
    #         if df[col].dtype == bool:
    #             df[col] = df[col].astype(str)
    #             df.loc[df[col] == "True", col] = "true"
    #             df.loc[df[col] == "False", col] = "false"
    
    return df
    
def clean_data_file(file: Union[str, Path], output_dir: Optional[Union[str, Path]], max_rows: Optional[int] = 0, schema: Optional[Union[str, Path, SchemaView]] = None) -> Tuple[str, pd.DataFrame]:
    """Clean the specified file and save to the specified output directory. The file should be a tsv, csv, or txt
    file (txt files are treated as tab-separated).

    Args:
        file (Union[str, Path]): The file to clean.
        output_dir (Optional[Union[str, Path]]): The directory to save the cleaned data file to. This should
            be different than the directory that the original file is located in to avoid overwriting the
            original.
        max_rows (Optional[int]): Maximum nuimber of rows to load and clean from the file. If 0 then clean
            all rows. Defaults to 0.
        schema (Optional[Union[str, Path, SchemaView]]): If specified the path to a schema file. We will 
            do some minor cleanup of the data to conform better to the schema (eg. fixing capitalization of
            columns and enumerations). If None then no cleanup is performed. Defaults to None.

    Returns:
        Tuple[str, pd.DataFrame]: A tuple of (new file name, data frame). The DataFrame
            is the contents of the file with any required processing performed (eg.
            putting dates and datetimes into the correct string format) 
    """
    if output_dir == os.path.dirname(file):
        raise ValueError(f"The output_dir and input file directory must be different. output_dir is '{output_dir}' and file is '{file}'")
    
    if isinstance(schema, (str, Path)):
        schema = SchemaView(schema)
    
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
    
    # Get the class name from the file name (correcting the case)
    class_name = get_class_name_from_file_name(file, schema)
    
    # Create the output file path
    # output_file = "%s.csv" % class_name
    output_file = "%s.csv" % os.path.splitext(os.path.basename(file))[0]
    output_file = Path(output_dir) / output_file
    logger.info(f"Fixing data from {file}")
    
    # Read the DataFrame from disk
    df = read_data_frame(file, nrows=max_rows if max_rows else None, keep_default_na=False, na_values=[""])

    # Fix the data
    df = fix_data_no_schema(df)
    if schema:
        df = fix_data_with_schema(df, class_name, schema=schema)
    
    # Save to disk
    logger.info(f"Saving fixed data to {output_file}")
    save_data_frame(df, output_file, index=False)
    
    return output_file, df

def clean_data_directory(directory: Union[str, Path], output_dir: Union[str, Path], max_rows: int = 0, schema: Optional[Union[str, Path, SchemaView]] = None) -> List[Tuple[str, pd.DataFrame]]:
    """Clean all TSV, TXT, and CSV data files in the specified directory and save the cleaned data
    to the specified output directory. Cleaning involves changing the format of dates, making sure columns
    are capitalized correctly, and making sure enumerations are capitalized correctly.

    Args:
        directory (Union[str, Path]): Clean all tsv, txt, and csv files in this directory. txt files
            are treated as tab-separated.
        output_dir (Union[str, Path]): Output directory to save the cleaned data files to. This should
            be different than the parameter directory to ensure that the original files are not overwritten.
        max_rows (int): Maximum number of rows to load and clean for each file. If 0 then clean all rows.
            Defaults to 0.
        schema (Optional[Union[str, Path, SchemaView]]): If specified the path to a schema file. We 
            will do some minor cleanup of the data to conform better to the schema (eg. fixing 
            capitalization of columns and enumerations). If None then no cleanup is performed. 
            Defaults to None.

    Returns:
        List[Tuple[str, pd.DataFrame]]: List of tuples of (file name, data frame), where the
            file names are the output files and the data frames are the DataFrames used to
            create the output file. The DataFrames are loaded from the input files with
            some additional cleaning.
    """
    dfs = []
    for f in os.listdir(directory):
        if os.path.splitext(f)[1].lower() in [ ".tsv", ".txt", ".csv" ]:
            output_file, df = clean_data_file(Path(directory) / f, schema=schema, output_dir=output_dir, max_rows=max_rows)
            dfs.append([output_file, df])
    return dfs

if __name__ == "__main__":
    if "get_ipython" in globals():
        class opts:
            # directory = Path("../../../../PHES-ODM-Data/odm_v1_data/wwMeasure")
            # directory = Path("../../../../PHES-ODM-Data/odm_v1_data/centreau_qc/updated")
            directory = Path("../../../../PHES-ODM-Data/nwss/private_renamed")
            file = ""
            output_dir = Path("../../../../PHES-ODM-Data/nwss/private_cleaned")
            max_rows = 1000
            # schema = Path("../../data/odm_v1/linkml/odm_v1.yaml")
            schema = Path("../../data/nwss_reporting/linkml/nwss_reporting.yaml")
    else:
        args = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
        args.add_argument("--directory", type=str, help="Clean all csv, txt, and tsv files in this directory. txt files are treated as tab-separated", required=False)
        args.add_argument("--file", type=str, help="Clean this file. Must be a csv, txt, or tsv file. txt files are treated as tab separated", required=False)
        args.add_argument("--output_dir", type=str, help="Save results to this directory", required=True)
        args.add_argument("--max_rows", type=int, help="Maximum number of rows to load and clean. If 0 then clean all rows. Default is 0.", default=0, required=False)
        args.add_argument("--schema", type=str, help="Schema file that the data conforms to. We will do some basic cleanup to the data based on this schema (eg. correcting capitalization of classes and enums). We assume the file name of the file being cleaned is the class name for the data. If no schema provided then only basic cleanup is performed", required=False)
        opts = args.parse_args()
        
    if opts.file:
        clean_data_file(opts.file, output_dir=opts.output_dir, max_rows=opts.max_rows, schema=opts.schema)
    if opts.directory:
        clean_data_directory(opts.directory, output_dir=opts.output_dir, max_rows=opts.max_rows, schema=opts.schema)

    logger.info("Finished!")
