#%%
from pathlib import Path
from typing import Union, List
import argparse

from make_mappers import make_mappers
from map_data import map
from utils.clean_data import clean_data_directory
from utils.general_utils import clear_dirs, extract_sheets, get_logger

logger = get_logger(__name__)

def make_mappers_cli(output_dir: Union[str, Path], mapping_config_file: Union[str, Path], maps_sheets: Union[List[str], str], wide_sheets: Union[List[str], str], enums_sheets: Union[List[str], str], source_schema: Union[str, Path], target_schema: Union[str, Path]):
    """Make the LinkML Mapper spec (YAML) files required for mapping from any source data set to
    any taret dataset, as specified in the mapping_config_file.

    Args:
        output_dir (Union[str, Path]): Directory to save all outputs to, including the final mapper files.
            Various sub-directories will be created, with the mappers in the "mappers" subdirectory.
        mapping_config_file (Union[str, Path]): The mapping configuration Excel file that specifies how to map from
            the source dataset (eg. NWSS) to the target dataset (eg. ODM v2).
        maps_sheets (Union[List[str], str]): Name of the map tab(s)/sheet(s) in the mapping_config_file Excel file.
            (eg. "maps")
        wide_sheets (Union[List[str], str]): Name of the wide tab(s)/sheet(s) in the mapping_config_file Excel file.
            (eg. "wide")
        enums_sheets (Union[List[str], str]): Name of the enums tab(s)/sheet(s) in the mapping_config_file Excel file.
            (eg. "enums")
        source_schema (Union[str, Path]): The source dataset schema LinkML YAML file.
        target_schema (Union[str, Path]): The target dataset schema LinkML YAML file.
    """
    output_dir = Path(output_dir)
    
    if isinstance(wide_sheets, str):
        wide_sheets = [wide_sheets]
    if isinstance(maps_sheets, str):
        maps_sheets = [maps_sheets]

    dictionary_dir = output_dir / "dictionary"
    mapper_dir = output_dir / "mappers"
    mapped_dir = output_dir / "mapped_data"
    
    # Clean up directories (ie. delete old csv, tsv, and yaml files)
    clear_dirs([dictionary_dir, mapper_dir, mapped_dir])

    # Extract the required sheets from the mapping config file
    output_maps_names = [f"maps{i}" for i in range(len(maps_sheets))]
    maps_files = [dictionary_dir / f"{f}.csv" for f in output_maps_names]
    output_wide_names = [f"wide{i}" for i in range(len(wide_sheets))]
    wide_files = [dictionary_dir / f"{f}.csv" for f in output_wide_names]
    output_enums_names = [f"enums{i}" for i in range(len(enums_sheets))]
    enums_files = [dictionary_dir / f"{f}.csv" for f in output_enums_names]
    extract_sheets(mapping_config_file, [*maps_sheets, *wide_sheets, *enums_sheets], dictionary_dir, output_names=[*output_maps_names, *output_wide_names, *output_enums_names], na_values={}, default_na_values=[""])

    # Create the mapper specs
    make_mappers(maps_files=maps_files, wide_files=wide_files, enums_files=enums_files, mapper_dir=mapper_dir, source_schema=source_schema, target_schema=target_schema)

    logger.info("Finished!")

if __name__ == "__main__":
    if "get_ipython" in globals():
        dictionary_type = "reporting"
        class opts:
            source_schema = f"../data/nwss_{dictionary_type}/linkml/nwss_{dictionary_type}.yaml"
            target_schema = f"../data/odm_v2/linkml/odm_v2.yaml"
            mapping_config_file = "../data/mapping_config_files/NWSS-to-ODM-dictionary.xlsx"
            maps_sheets = ["maps"]
            wide_sheets = ["wide"]
            enums_sheets = ["enums"]
            output_dir = Path(f"../gen/nwss_{dictionary_type}_to_v2")
            input_data_dir = "../../../PHES-ODM-Data/nwss/private_renamed/"
            input_max_rows = 10
    else:
        args = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
        args.add_argument("--source_schema", type=str, help="Location of the source dataset LinkML schema", required=True)
        args.add_argument("--target_schema", type=str, help="Location of the target dataset LinkML schema", required=True)
        args.add_argument("--mapping_config_file", type=str, help="The Excel mapping file that specifies how mapping is performed and how wide columns are treated.", required=True)
        args.add_argument("--maps_sheets", type=str, nargs="+", help="The sheet(s) in the mapping Excel file that contain the mapping configuration.", required=True)
        args.add_argument("--wide_sheets", type=str, nargs="+", help="The sheet(s) in the mapping Excel file that contain the wide-column configuration.", required=False)
        args.add_argument("--enums_sheets", type=str, nargs="+", help="The sheet(s) in the mapping Excel file that contain the enums configuration.", required=False)
        args.add_argument("--output_dir", type=str, help="Directory to save all output to, including where the mapper config files are saved. Various sub-directories are created for the different outputs.", required=True)
        args.add_argument("--input_data_dir", type=str, help="Directory containing all the input data to map using the generated mapper config files. If empty then no mapping is performed.", required=False)
        args.add_argument("--input_max_rows", type=int, help="If input_data_dir is set, then the number of rows to map from each input data file. If 0 then map all rows.", default=0, required=False)
        opts = args.parse_args()
    
    make_mappers_cli(output_dir=opts.output_dir, 
                    mapping_config_file=opts.mapping_config_file, 
                    maps_sheets=opts.maps_sheets,
                    wide_sheets=opts.wide_sheets,
                    enums_sheets=opts.enums_sheets,
                    source_schema=opts.source_schema, 
                    target_schema=opts.target_schema)

    if opts.input_data_dir:
        # @TODO: Remove this, it is for testing. After generating the mapping specs we run the below code to test the specs by mapping data
        logger.info(f"Running data mappings...")
        output_dir = Path(opts.output_dir)
        mapper_dir = output_dir / "mappers"
        mapped_dir = output_dir / "mapped_data"

        # Prepare data
        cleaned_data_dir = output_dir / "cleaned_data"
        max_processes = 1
        # clear_dirs([cleaned_data_dir, mapped_dir])
        # files = clean_data_directory(opts.input_data_dir, cleaned_data_dir, schema=opts.source_schema, max_rows=opts.input_max_rows)

        # Map the data
        map(source_schema_file=opts.source_schema, target_schema_file=opts.target_schema, mapper_dir=mapper_dir, data_dir=cleaned_data_dir, data_output_dir=mapped_dir, max_processes=max_processes)
