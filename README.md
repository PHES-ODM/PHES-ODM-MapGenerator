# <img src="img/ODM-logo.png" align="right" alt="" width="180"/> PHES-ODM LinkML Map Generator

The PHES-ODM Map Generator generates [LinkML Mapper](https://github.com/linkml/linkml-map) specifications for mapping between various data formats, such as ODM v1 to ODM v2, ODM v2 Wide to Long, NWSS to ODM, etc.

## Installation

To clone the repository and create a new virtual environment, run the following on the command-line:

```console
git clone git@github.com:Big-Life-Lab/PHES-ODM-MapGenerator.git
cd PHES-ODM-MapGenerator
python3 -m venv .env
```

Activate the virtual environment on Linux/macOS:

```console
source .env/bin/activate
```

Or if you're running Windows:

```console
.env\Scripts\activate
```

Install Python library requirements:

```console
pip3 install -r requirements.txt
```

## Running the Tests

The test suite uses [pytest](https://docs.pytest.org/). Install it alongside the project dependencies if it is not already present:

```console
pip3 install pytest
```

Then run all tests from the repository root:

```console
pytest tests/
```

For more verbose output showing each test name:

```console
pytest tests/ -v
```

## Getting Familiar

Currently both ODM v1 to ODM v2 and NWSS to ODM v2 are partially supported (ie. they are not yet complete). ODM v1 to ODM v2 involves parsing the ODM v2 data dictionary, whereas NWSS to ODM v2 uses a separate mapping configuration file (located at [map_maker/data/mapping_config_files/nwss_to_odm_v2_mapping.xlsx](map_maker/data/mapping_config_files/nwss_to_odm_v2_mapping.xlsx)). Mapping from ODM v1 to ODM v2 will be switched over to use a mapping configuration file in the near future. Therefore, if you're trying to get familiar with this repo and its code it is best to ignore ODM v1 to ODM v2 (including [map_maker/make_v1_to_vx.py](map_maker/make_v1_to_vx.py) and all code in [map_maker/odm_v2](map_maker/odm_v2)) and look at NWSS to ODM v2 instead. The main entrypoint for NWSS to ODM v2 is [map_maker/make_mappers_cli.py](map_maker/make_mappers_cli.py).

## ODM v1 to ODM v2

Generating the LinkML mapping specification files for mapping between ODM v1 and v2 involves parsing the ODM v2 Data Dictionary to extract all information pertaining to mapping between slots and enumerations. Generating the ODM v1 to ODM v2 LinkML mapping specification files is the only mapping between datasets that does not use [Mapping Files](#mapping-files) and the [General CLI](#general-cli). In the future, ODM v1 to ODM v2 will be switched over to use [Mapping Files](#mapping-files). The script [map_maker/make_v1_to_vx.py](map_maker/make_v1_to_vx.py) will generate all mapping spec (YAML) files to map from ODM v1 to ODM v2. To run the script, execute:

```console
cd map_maker
python3 make_v1_to_vx.py \
    --config data/odm_v1/odm_v1_to_v2_config.yaml \
    --source-schema data/odm_v1/linkml/odm_v1.yaml \
    --target-schema data/odm_v2/linkml/odm_v2.yaml \
    --wide-dir data/odm_v1/custom_wide \
    --output-dir ../gen/odm_v1_to_v2 \
    --v2-data-dictionary "data/odm_v2/v2 ODM dictionary.xlsx"
```

A separate mapper specification (YAML) file is created for each mapping from a single v1 table to a single v2 table. These are saved at the location specified by `output-dir` on the command-line (`../gen/odm_v1_to_v2`).

For more details on the steps performed by this script, see [make_v1_to_vx.md](make_v1_to_vx.md).

## Mapping Files

Mapping files are Excel files that contain all required information for mapping from a source dataset (eg. NWSS) to a target dataset (eg. ODM v2). Mapping files can specify basic mappings, such as one-to-one copying, combining multiple fields into a single date/time/time-zone, as well as more complex mappings such as wide-to-long column mappings. See the [Mapping Config Files](mapping_config_files.md) section for instructions on how to modify or create your own mapping files.

## General CLI

In order to generate the LinkML mapping specification files to map from a source dataset to a target dataset, the following are required:

1. The source LinkML schema
2. The target LinkML schema
3. Mapping configuration files (with at least one maps datasheet, and optionally any number of wide or enums datasheets)

The script for the CLI is at [map_maker/make_mappers_cli.py](map_maker/make_mappers_cli.py). Command-line parameters are listed below (see [NWSS to ODM v2](#nwss-to-odm-v2) for an example):

**--source-schema** (Required)  
Required full path to the source dataset LinkML schema.

**--target-schema** (Required)  
Required full path to the target dataset LinkML schema.

**--output-dir** (Required)  
The directory to save all generated output to. Various sub-directories will be created:

- *configs*: Contains all the maps, wide, and enums configuration files, extracted from *mapping-excel-file*, and copied from *maps-files*, *wide-files*, and *enums-files*. These specify all the mappings to perform from the source to target datasets, including basic mappings, enumeration mappings, wide-to-long mappings, etc.
- *mappers*: Contains all generated [LinkML Map](https://github.com/linkml/linkml-map) schemas to perform the mappings from the source to target datasets. These are the main artifacts generated by the script.

**--mapping-excel-file** (Optional)  
The Excel mapping configuration file. This can include multiple maps, wide, and enums configuration sheets, with the sheets specified by the *excel-maps-sheets*, *excel-wide-sheets*, and the *excel-enums-sheets* command-line options. Additional configuration sheets that are available in CSV or TSV format can also be specified with the *maps-files*, *wide-files*, and *enums-files* options. At least one *maps* sheet or file must be specified.

**--excel-maps-sheets** (Optional)  
If *mapping-excel-file* is specified, then this option is one or more strings specifying the names of the sheets in the Excel file that are mapping configuration sheets. Any number of maps sheets can be specified, and each specified sheet must be preceded by a *--excel-maps-sheets* flag. These will be used in addition to all maps files specified with *maps-files*.

**--excel-wide-sheets** (Optional)  
If *mapping-excel-file* is specified, then this option is one or more strings specifying the names of the sheets in the Excel file that are wide configuration sheets. Any number of wide sheets can be specified, and each specified sheet must be preceded by a *--excel-wide-sheets* flag. These will be used in addition to all wide files specified with *wide-files*.

**--excel-enums-sheets** (Optional)  
If *mapping-excel-file* is specified, then this option is one or more strings specifying the names of the sheets in the Excel file that are enum configuration sheets. Any number of enum sheets can be specified, and each specified sheet must be preceded by a *--exce-enums-sheets* flag. These will be used in addition to all enums files specified with *enums-files*.

**--maps-files** (Optional)  
One or more full paths to any maps configuration files to use, in CSV or TSV format. Each specified file must be preceded by a *--maps-files* flag. These will be used in addition to all the maps sheets specified by *mapping-excel-file* and *excel-maps-sheets*.

**--wide-files** (Optional)  
One or more full paths to any wide configuration files to use, in CSV or TSV format. Each specified file must be preceded by a *--wide-files* flag. These will be used in addition to all the wide sheets specified by *mapping-excel-file* and *excel-wide-sheets*.

**--enums-files** (Optional)  
One or more full paths to any enums configuration files to use, in CSV or TSV format. Each specified file must be preceded by a *--enums-files* flag. These will be used in addition to all the enums sheets specified by *mapping-excel-file* and *excel-enums-sheets*.

## NWSS to ODM v2

Mapping NWSS to ODM follows the instructions found in the section [General CLI](#general-cli). NWSS has multiple allowable data formats. Until the NWSS mapping spec is complete, you should stick to mapping from the default NWSS reporting data format (other formats include NWSS public metric, NWSS public concentration, and several NWSS restricted formats).

To generate the NWSS reporting to ODM v2 mapper specs, execute:

```console
cd map_maker
python3 make_mappers_cli.py \
    --source-schema "data/nwss_reporting/linkml/nwss_reporting.yaml" \
    --target-schema "data/odm_v2/linkml/odm_v2.yaml" \
    --mapping-excel-file "data/mapping_config_files/nwss_to_odm_v2_mapping.xlsx" \
    --excel-maps-sheets maps \
    --excel-wide-sheets wide_measures \
    --excel-wide-sheets wide_protocolRelationships \
    --excel-wide-sheets wide_protocolSteps \
    --excel-wide-sheets wide_qualityReports \
    --excel-enums-sheets enums \
    --output-dir "../gen/nwss_reporting_to_v2"
```

## Mapping Data

Once all the mapping spec (YAML) files are created, data can be mapped from source to target datasets. To perform these mappings, as well as other operations such as cleaning the data and generating IDs, see the [PHES-ODM-Mapper](https://github.com/Big-Life-Lab/PHES-ODM-Mapper) repo.