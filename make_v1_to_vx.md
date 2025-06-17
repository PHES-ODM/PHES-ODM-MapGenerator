# Generating the ODM v1 to ODM vx Mapper Specifications

The script [map_maker/make_v1_to_vx.py](map_maker/make_v1_to_vx.py) creates all the LinkML Mapping specifications for mapping from ODM v1 to ODM vx tables (eg. vx is "v2", "v3", etc). Each specification file is for a single v1 table to a single vx table, along with some additional specifications for cases where a v1 table has columns that should be treated as "wide" columns (ie. we do a wide-to-long mappings). The v1 table `AssayMethod` has wide columns.

The steps this script performs are detailed below.

## utils.general_utils.clear_dirs

The output directories are first cleaned by removing any old CSV, TSV, and YAML files. This is to ensure no artefacts are left over from previous runs.

## utils.general_utils.extract_sheets

The original data dictionary is an Excel file. The function `extract_sheets` extracts the required Excel sheets from the data dictionary as CSV files and saves them to disk. Only the "parts" sheet is extracted.

## prepare_parts.prepare_parts

The extracted parts sheet requires a bit of extra processing before being used. The first step is to remove any rows that do not specify mappings from v1 to vx (the mappings are defined in the columns "version1Table", "version1Location", "version1Variable", and "version1Category"). For rows that correspond to mappings from v1 enumerations to vx enumerations, we add the v1 enumeration name (which is constructed from the version1Table and version1Variable columns). We also find any row the describes more than one mapping, and split those rows up so that all rows only describe a single mapping. For example, the version1Table might contain multiple v1 table names separated by semicolons (eg. "WWMeasure;SiteMeasure") which the ODM vx variable for that row maps to. This script also performs some other processing not described here. See the code for details.

## make_vx_mappers_from_parts.make_mappers

Using the prepared parts sheet from the previous step, this function will create all Mapper specification files. For each pair of v1 table and vx table, a separate specification file is created. These specification files can be used from the command line (using the `linkml-tr` command) or from Python code using the LinkML and LinkML Mapper APIs. For an example mapping in Python using the LinkML-Map API, see [map_maker/map_data.py](map_maker/map_data.py)