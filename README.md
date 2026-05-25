# <img src="img/ODM-logo.png" align="right" alt="" width="180"/> PHES-ODM LinkML Map Generator

The PHES-ODM Map Generator generates
[LinkML Mapper](https://github.com/linkml/linkml-map) specifications for
mapping between various data formats, such as ODM v1 to ODM v2/v3, NWSS to
ODM, and PHA4GE to ODM.

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

Or on Windows:

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

For more verbose output:

```console
pytest tests/ -v
```

## Overview

The main entrypoint for generating mapping specifications is
[odm_map_maker/make_mappers_cli.py](odm_map_maker/make_mappers_cli.py). It
reads a [Mapping File](#mapping-files) (an Excel workbook describing how source
slots map to target slots) together with LinkML schemas for both the source and
target datasets, and produces [LinkML Map](https://github.com/linkml/linkml-map)
YAML specifications that can be used to transform data.

The following source-to-target mappings are currently supported:

- **ODM v1 → ODM v2/v3** — using [odm_map_maker/configs/odm_v1_to_odm.yaml](odm_map_maker/configs/odm_v1_to_odm.yaml)
- **NWSS → ODM v2/v3** — using [odm_map_maker/configs/nwss_to_odm.yaml](odm_map_maker/configs/nwss_to_odm.yaml)
- **PHA4GE → ODM v2/v3** — using [odm_map_maker/configs/pha4ge_to_odm.yaml](odm_map_maker/configs/pha4ge_to_odm.yaml)

Each config file defaults to mapping to ODM v3. Pass `--target-schema`,
`--output-dir`, and `--selectors` on the command line to target ODM v2 instead
(see the per-mapping sections below for examples).

## Mapping Files

Mapping files are Excel workbooks that contain all required information for
mapping from a source dataset to a target dataset. They specify basic slot
mappings, enumeration mappings, and wide-to-long column mappings. See
[Mapping Config Files](mapping_config_files.md) for instructions on how to
modify or create your own mapping files.

## General CLI

The script [odm_map_maker/make_mappers_cli.py](odm_map_maker/make_mappers_cli.py)
accepts the following command-line options. All options can also be specified in
a YAML config file passed via `--config` — see
[CLI Configuration Files](make_mappers_cli_config.md) for details.

**--config** (Optional)  
Path to a YAML configuration file. Keys are CLI option names (with hyphens or
underscores). Values serve as defaults and are overridden by any arguments
supplied on the command line. Paths in the config file are resolved relative to
the config file's location. See [CLI Configuration Files](make_mappers_cli_config.md).

**--source-schema** (Required)  
Full path to the source dataset LinkML schema.

**--target-schema** (Required)  
Full path to the target dataset LinkML schema.

**--output-dir** (Required)  
Directory to save all generated output to. Two sub-directories are created:

- *configs*: Extracted maps, wide, and enums configuration files.
- *mappers*: Generated [LinkML Map](https://github.com/linkml/linkml-map) YAML
  schemas — the main artifacts produced by the script.

**--mapping-excel-file** (Optional)  
The Excel mapping configuration file. Can contain any number of maps, wide, and
enums sheets named via `--excel-maps-sheets`, `--excel-wide-sheets`, and
`--excel-enums-sheets`. Additional CSV/TSV files can be specified with
`--maps-files`, `--wide-files`, and `--enums-files`. At least one maps sheet or
file must be provided.

**--excel-maps-sheets** (Optional)  
One or more sheet names in the Excel file that contain maps configurations.
Repeat the flag for each sheet name.

**--excel-wide-sheets** (Optional)  
One or more sheet names in the Excel file that contain wide-column configurations.
Repeat the flag for each sheet name.

**--excel-enums-sheets** (Optional)  
One or more sheet names in the Excel file that contain enumeration configurations.
Repeat the flag for each sheet name.

**--maps-files** (Optional)  
One or more paths to CSV or TSV maps configuration files. Repeat the flag for
each file.

**--wide-files** (Optional)  
One or more paths to CSV or TSV wide-column configuration files. Repeat the flag
for each file.

**--enums-files** (Optional)  
One or more paths to CSV or TSV enumeration configuration files. Repeat the flag
for each file.

**--selectors** (Optional)  
Flags or module-version strings used to include or exclude rows in the mapping
configuration files. A flag is a plain string (letters, numbers, underscores),
optionally negated with `!`. A module version has the form `module=version`
(e.g. `odm=3`). Multiple selectors can be combined in a single comma-separated
string (e.g. `amr,!deprecated,odm=3`).

**--source-slot-format-operations** (Optional)  
Formatting operations applied to all source slot names found in the
configuration file. Repeat the flag for each operation.

**--target-slot-format-operations** (Optional)  
Formatting operations applied to all target slot names found in the
configuration file. Repeat the flag for each operation.

**--source-match-ontology-id-regex** (Optional)  
Regular expression that matches ontology IDs in source schema enum values. When
set, ontology IDs found in the source schema are automatically added to enum
values that lack one in the mapping configuration.

**--target-match-ontology-id-regex** (Optional)  
Regular expression that matches ontology IDs in target schema enum values.

## ODM v1 to ODM

Generates LinkML mapping specifications for mapping from ODM v1 to ODM v3
(default) or v2. The config file is at
[odm_map_maker/configs/odm_v1_to_odm.yaml](odm_map_maker/configs/odm_v1_to_odm.yaml)
and the mapping configuration Excel file is at
[odm_map_maker/data/mapping_config_files/odm_v1_to_v2_mapping.xlsx](odm_map_maker/data/mapping_config_files/odm_v1_to_v2_mapping.xlsx).

```console
# Map ODM v1 to ODM v3 (default)
python odm_map_maker/make_mappers_cli.py \
    --config odm_map_maker/configs/odm_v1_to_odm.yaml

# Map ODM v1 to ODM v2
python odm_map_maker/make_mappers_cli.py \
    --config odm_map_maker/configs/odm_v1_to_odm.yaml \
    --target-schema odm_map_maker/data/odm_v2/linkml/odm_v2.yaml \
    --output-dir ../gen/odm-v1-to-v2 \
    --selectors odm=2
```

## NWSS to ODM

Generates LinkML mapping specifications for mapping from NWSS data to ODM v3
(default) or v2. The config file defaults to the NWSS reporting dictionary type;
override `--source-schema` on the command line to use a different type
(`public_concentration`, `public_metric`). The config file is at
[odm_map_maker/configs/nwss_to_odm.yaml](odm_map_maker/configs/nwss_to_odm.yaml)
and the mapping configuration Excel file is at
[odm_map_maker/data/mapping_config_files/nwss_to_odm_v2_mapping.xlsx](odm_map_maker/data/mapping_config_files/nwss_to_odm_v2_mapping.xlsx).

```console
# Map NWSS reporting to ODM v3 (default)
python odm_map_maker/make_mappers_cli.py \
    --config odm_map_maker/configs/nwss_to_odm.yaml

# Map NWSS reporting to ODM v2
python odm_map_maker/make_mappers_cli.py \
    --config odm_map_maker/configs/nwss_to_odm.yaml \
    --target-schema odm_map_maker/data/odm_v2/linkml/odm_v2.yaml \
    --output-dir ../gen/nwss-reporting-to-v2 \
    --selectors odm=2

# Map a different NWSS dictionary type to ODM v3
# Replace <type> with public_concentration or public_metric
python odm_map_maker/make_mappers_cli.py \
    --config odm_map_maker/configs/nwss_to_odm.yaml \
    --source-schema odm_map_maker/data/nwss_<type>/linkml/nwss_<type>.yaml \
    --output-dir ../gen/nwss-<type>-to-v3
```

## PHA4GE to ODM

Generates LinkML mapping specifications for mapping from PHA4GE wastewater data
to ODM v3 (default) or v2. The config file is at
[odm_map_maker/configs/pha4ge_to_odm.yaml](odm_map_maker/configs/pha4ge_to_odm.yaml)
and the mapping configuration Excel file is at
[odm_map_maker/data/mapping_config_files/pha4ge_to_odm_v2_mapping.xlsx](odm_map_maker/data/mapping_config_files/pha4ge_to_odm_v2_mapping.xlsx).

```console
# Map PHA4GE to ODM v3 (default)
python odm_map_maker/make_mappers_cli.py \
    --config odm_map_maker/configs/pha4ge_to_odm.yaml

# Map PHA4GE to ODM v2
python odm_map_maker/make_mappers_cli.py \
    --config odm_map_maker/configs/pha4ge_to_odm.yaml \
    --target-schema odm_map_maker/data/odm_v2/linkml/odm_v2.yaml \
    --output-dir ../gen/pha4ge-to-v2 \
    --selectors odm=2
```

## Validating Mappers

After generating mappers with `make_mappers_cli.py`, use
[odm_map_maker/validate_mappers/mapper_validator.py](odm_map_maker/validate_mappers/mapper_validator.py)
to check that all enumeration mappings are complete and consistent. See
[Mapper Validator](mapper_validator.md) for full documentation and examples for
each mapping type.

## Mapping Data

Once all mapping specification YAML files are created, data can be mapped from
source to target datasets. To perform these mappings, as well as other
operations such as cleaning data and generating IDs, see the
[PHES-ODM-Mapper](https://github.com/Big-Life-Lab/PHES-ODM-Mapper) repository.
