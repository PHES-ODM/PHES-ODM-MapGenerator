# <img src="img/ODM-logo.png" align="right" alt="" width="180"/> PHES-ODM LinkML Map Generator

The PHES-ODM Map Generator generates [LinkML Mapper](https://github.com/linkml/linkml-map) specifications for mapping between various data formats, such as ODM v1 to ODM v2, ODM v2 Wide to Long, NWSS to ODM, etc.

## Installation

To clone the repository and create a new virtual environment, run the following on the command-line:

```console
git clone git@github.com:Big-Life-Lab/PHES-ODM-MapGenerator.git
cd PHES-ODM-MapGenerator
python3 -m venv .env
```

Activate the virtual environment on Unix/macOS:

```console
source .env/bin/activate
```

Or if you're running Windows:

```console
.env\Scripts\activate
```

Install Python library requirements:

```
pip3 install -r requirements.txt
```

## Important Notes

There are multiple changes that have been made to the [LinkML Map repo](https://github.com/linkml/linkml-map) that have not yet been merged. These changes include:

- The `constant` field in a slot derivation. Without this field the `expr` field has to be used to assign a constant value to a target slot (which is done a lot when pivoting wide-columns). Using `expr` is very slow since the mapper has to compile and execute code for each mapping. At the moment the PHES-ODM-MapGenerator code sticks to using `expr` so that it is compatible with the current LinkML mapper repo (see [src/utils/mapper_utils.py](src/utils/mapper_utils.py)).
- The `datetime` field in a slot derivation. This allows using different source slots for the date, time, and time zone, and combining them into a single target slot that is a full datetime. As with `constant`, this is not in the LinkML Map repo. The `datetime` field is specified in the mapping configuration file. The current version located at [data/mapping_config_files/NWSS-to-ODM-dictionary.xlsx](data/mapping_config_files/NWSS-to-ODM-dictionary.xlsx) has the `datetime` field removed (see `unused_customData` column in the `maps` tab) but will be re-added once the LinkML repo has been updated.

## Getting Familiar

Currently both ODM v1 to ODM v2 and NWSS to ODM v2 are partially supported (ie. they are not yet complete). ODM v1 to ODM v2 involves parsing the ODM v2 data dictionary, whereas NWSS to ODM v2 uses a separate mapping configuration file (located at [data/mapping_config_files/NWSS-to-ODM-dictionary.xlsx](data/mapping_config_files/NWSS-to-ODM-dictionary.xlsx)). Mapping from ODM v1 to ODM v2 will be switched over to use a mapping configuration file in the near future. Therefore, if you're trying to get familiar with this repo and its code it is best to ignore ODM v1 to ODM v2 (including [src/make_v1_to_v2.py](src/make_v1_to_v2.py) and all code in [src/odm_v2](src/odm_v2)) and look at NWSS to ODM v2 instead. The main entrypoint for NWSS to ODM v2 is [src/make_mappers_cli.py](src/make_mappers_cli.py).

## ODM v1 to ODM v2

Mapping between ODM v1 and v2 involves parsing the ODM v2 Data Dictionary to extract all information pertaining to mapping between slots and enumerations. The script [src/make_v1_to_v2.py](src/make_v1_to_v2.py) will generate all mapping spec (YAML) files to map from ODM v1 to ODM v2. To run the script, execute:

```console
cd src
python3 make_v1_to_v2.py --source_schema "../data/odm_v1/linkml/odm_v1.yaml" \
    --target_schema "../data/odm_v2/linkml/odm_v2.yaml" \
    --wide_dir "../data/odm_v1/custom_wide" \
    --output_dir "../gen/odm_v1_to_v2" \
    --v2_data_dictionary "../data/odm_v2/v2 ODM dictionary.xlsx" \
    --max_mapping_only
```

A separate mapper specification (YAML) file is created for each mapping from a single v1 table to a single v2 table. These are saved at the location specified by `output_dir` on the command-line (`../gen/odm_v1_to_v2`).

For more details on the steps performed by this script, see [make_v1_to_v2.md](make_v1_to_v2.md).

## NWSS to ODM v2

NWSS has multiple allowable data formats. Until the NWSS mapping spec is complete, you should stick to mapping from the default NWSS reporting data format (other formats include NWSS public metric, NWSS public concentration, and several NWSS restricted formats).

To generate the NWSS reporting to ODM v2 mapper specs, execute:

```console
cd src
python3 make_mappers_cli.py --source_schema "../data/nwss_reporting/linkml/nwss_reporting.yaml" \
    --target_schema "../data/odm_v2/linkml/odm_v2.yaml" \
    --mapping_config_file "../data/mapping_config_files/NWSS-to-ODM-dictionary.xlsx" \
    --maps_sheets "maps" \
    --wide_sheets "wide" \
    --enums_sheets "enums" \
    --output_dir "../gen/nwss_reporting_to_v2"
```

## Mapping Files

Mapping files are Excel files that contain all required information for mapping from a source dataset (eg. NWSS) to a target dataset (eg. ODM v2). Mapping files can specify basic mappings, such as one-to-one copying, combining multiple fields into a single date/time/time-zone, as well as more complex mappings such as wide-to-long column mappings. See the [Mapping Config Files](mapping_config_files.md) section for instructions on how to modify or create your own mapping files.

## Mapping Data

Once all the mapping spec (YAML) files are created, data can be mapped from source to target datasets. Data files are required and are not currently included in this repository. However, if you have example data you can follow the instructions in this section. The code for mapping will eventually move to a separate repository.

Using NWSS to ODM v2 as an example, run the following, replacing values as necessary:

```console
cd src
python3 map_data.py --source_schema "../data/nwss_reporting/linkml/nwss_reporting.yaml" \
    --target_schema "../data/odm_v2/linkml/odm_v2.yaml" \
    --mapper_dir "../gen/nwss_reporting_to_v2/mappers" \
    --data_dir "path/to/input/data/dir" \
    --output_dir "../gen/nwss_reporting_to_v2/mapped_data" \
    --max_processes 1
```

Using all generated mapping spec (YAML) files in the directory specified by `mapper_dir`, all data files in `data_dir` will be mapped from NWSS to ODM v2, with the results saved in `output_dir`. If the dataset is large, you can try increasing `max_processes` for performance improvements, but for small datasets larger values of `max_processes` may end up being slower.

The data files in `data_dir` should be named after the class or table that the data are for. After the table name, any additional information about the file can be appended in square brackets, which is ignored. For example, NWSS has a single class or table called "nwss", so a data file for NWSS might be called "nwss[my sample data].csv". For ODM v1, data for the "SiteMeasure" table might be called "SiteMeasure.csv" or "SiteMeasure[My Data].csv". CSV, TSV, and TXT files are supported. TSV and TXT files are treated as tab-separated.
