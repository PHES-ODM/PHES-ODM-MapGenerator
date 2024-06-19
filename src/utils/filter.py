#%%
"""
Filter DataFrames (or data on disk) using configuration files.

## Usage

```python
# Filter .csv, .tsv, and .txt (tab-separated) files found in data_dir and save
# to output_data_dir. The input file names become the class names (as found in the
# filtering config file)
filtered_data = run_filter(filter_config_file="filter_config_file.csv", 
           data_dir="data/input", 
           output_data_dir="data/output")
           
# Filter DataFrames.
data = {
    "measures" : measure_df,
    "qualityReports" : qualityReports_df,
}
filtered_data = run_filter(filter_config_file="filter_config_file.csv", 
           data=data)
```
"""
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from typing import Union, Dict, List, Optional
import pandas as pd
import argparse
from pathlib import Path
import os
from datetime import datetime

from utils.general_utils import read_data_frame, save_data_frame, get_logger
from utils.filter_funcs import call_filter_func

logger = get_logger(__name__)

class FilterConfigColumns:
    INPUT_FILTER = "inputFilter"
    OUTPUT_FILTER = "outputFilter"
    CLASS = "class"
    SLOT = "slot"
    OPERATION = "operation"
    VALUE = "value"

def load_data(data_dir: Union[Path, str], recognized_classes: Optional[List[str]] = None) -> Dict[str, pd.DataFrame]:
    """Load all data from the specified directory. The file names are treated as the class names (excluding extension).

    Args:
        data_dir (Union[Path, str]): The directory to load all data files from.
        recognized_classes (Optional[List[str]], optional): If specified, then only load data files for
            classes in this list. The class for a data file is the file name (excluding the extension).

    Returns:
        Dict[str, pd.DataFrame]: Dictionary where the keys are the class names and the values are
            the loaded DataFrames.
    """
    data = {}
    for file in os.listdir(data_dir):
        if os.path.splitext(file)[1] not in [".csv", ".tsv", ".txt"]:
            continue
        file_class = os.path.splitext(file)[0]
        
        if recognized_classes and file_class not in recognized_classes:
            continue
        
        logger.info(f"Loading data from {file} (class='{file_class}')")

        # Load the data and append to any existing data for the class
        df = read_data_frame(os.path.join(data_dir, file), keep_default_na=False, na_values=[""])
        if file_class not in data:
            data[file_class] = df
        else:
            data[file_class] = pd.concat([data[file_class], df], ignore_index=True).reset_index(drop=True)
    return data

def save_data(data: Dict[str, pd.DataFrame], output_data_dir: Union[Path, str]):
    """Save all the data as CSV files to the output directory.

    Args:
        data (Dict[str, pd.DataFrame]): Data to save. The keys are the class names (which become the
            file names) and the values are the DataFrames to save.
        output_data_dir (Union[Path, str]): The directory to save all data to, as CSV files.
    """
    output_data_dir = Path(output_data_dir)
    if not output_data_dir.exists():
        output_data_dir.mkdir()
    for cur_class, cur_data in data.items():
        output_file = output_data_dir / f"{cur_class}.csv"
        logger.info(f"Saving data to {output_file}")
        save_data_frame(cur_data, output_file, index=False)    

def run_filter(filter_config_file: Union[Path, str], *, data: Dict[str, pd.DataFrame] = None, data_dir: Union[Path, str] = None, output_data_dir: Union[Path, str] = None) -> Dict[str, pd.DataFrame]:
    """Run the filters specified in the configuration file on all the data, and optionally save the data to disk.

    Args:
        filter_config_file (Union[Path, str]): The configuration file specying how filtering should be
            performed.
        data (Dict[str, pd.DataFrame], optional): The data to filter. The keys are the class names and the values are the
            DataFrames to filter. This dictionary is left unchanged, the returned dictionary is the filtered data.
            If None then data_dir must be specified. Defaults to None.
        data_dir (Union[Path, str], optional): If data is None, then load all data to filter from this directory, where the file
            names are the class names. If None then data must be set. Defaults to None.
        output_data_dir (Union[Path, str], optional): If specified then the directory to save all data after filtering has been
            performed. Defaults to None.
            
    Returns:
        Dict[str, pd.DataFrame]: The filtered data, where they keys are the classes and the values are the
            filtered DataFrames.
    """
    tic = datetime.now()
    
    config_df = read_data_frame(filter_config_file, keep_default_na=False)
    config_df = config_df.astype(str)
    if data is None:
        data = load_data(data_dir, recognized_classes=list(config_df[FilterConfigColumns.CLASS].unique()))
    else:
        data = data.copy()
    
    filters = {}
    # Go through each row and perform the filtering
    for _, config_row in config_df.iterrows():
        input_filter = str(config_row[FilterConfigColumns.INPUT_FILTER])
        output_filter = str(config_row[FilterConfigColumns.OUTPUT_FILTER])
        cls = config_row[FilterConfigColumns.CLASS]
        slot = config_row[FilterConfigColumns.SLOT]
        op = config_row[FilterConfigColumns.OPERATION]
        value = config_row[FilterConfigColumns.VALUE]
        
        if cls and cls not in data:
            logger.info(f"Not running filter on class '{cls}', data for class does not exist")
            continue
        
        logger.info(f"Running input filter '{input_filter}', output filter '{output_filter}' with operation '{op}' on class '{cls}', slot '{slot}', and value '{value}'")
        
        # Perform the filtering operation
        call_filter_func(op, input_name=input_filter, output_name=output_filter, filters=filters, data=data, cls=cls, slot=slot, value=value)

    if output_data_dir:
        save_data(data, output_data_dir)
        
    logger.info(f"Filtered in {datetime.now() - tic}")
    return data

if __name__ == "__main__":
    if "get_ipython" in globals():
        class opts:
            data_dir = "../../gen/nwss_reporting_to_v2/mapped_data"
            filter_config_file = "../../data/mapping_config_files/nwss_to_odm_v2_filter.csv"
            output_data_dir = "../../gen/nwss_reporting_to_v2/filtered_mapped_data"
    else:
        args = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
        args.add_argument("--data_dir", type=str, help="Location of the CSV or TSV data files to filter. The file names must be class names in the schema.", required=True)
        args.add_argument("--filter_config_file", type=str, help="Location of the CSV or TSV filtering configuration file.", required=True)
        args.add_argument("--output_data_dir", type=str, help="Location to save the filtered data to.", required=True)
        opts = args.parse_args()
    
    run_filter(filter_config_file=opts.filter_config_file, data_dir=opts.data_dir, output_data_dir=opts.output_data_dir)
