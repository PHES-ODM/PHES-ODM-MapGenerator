# <img src="docs/img/ODM-logo.png" align="right" alt="" width="180"/> PHES-ODM LinkML Map Generator

<!-- badges: start -->
[![lint.yaml](https://github.com/PHES-ODM/PHES-ODM-MapGenerator/actions/workflows/lint.yaml/badge.svg)](https://github.com/PHES-ODM/PHES-ODM-MapGenerator/actions/workflows/lint.yaml)
[![pytest.yaml](https://github.com/PHES-ODM/PHES-ODM-MapGenerator/actions/workflows/pytest.yaml/badge.svg)](https://github.com/PHES-ODM/PHES-ODM-MapGenerator/actions/workflows/pytest.yaml)
[![docs.yaml](https://github.com/PHES-ODM/PHES-ODM-MapGenerator/actions/workflows/docs.yaml/badge.svg)](https://github.com/PHES-ODM/PHES-ODM-MapGenerator/actions/workflows/docs.yaml)
<!-- badges: end -->

The PHES-ODM Map Generator generates
[LinkML Mapper](https://github.com/linkml/linkml-map) specifications for
mapping between various data formats, such as ODM v1 to ODM v2/v3, NWSS to
ODM, and PHA4GE to ODM.

This tool is one half of a two-repository workflow:

1. **This repository (MapGenerator)** — defines *how* to map (slot-by-slot,
   enum-by-enum) and generates [LinkML Map](https://github.com/linkml/linkml-map)
   YAML specification files.
2. **[PHES-ODM-Mapper](https://github.com/Big-Life-Lab/PHES-ODM-Mapper)** — reads
   those specification files and performs the actual data transformations (cleaning
   data and generating IDs).

**New here?** Work through
[Generate your first mappers](docs/tutorials/generate-your-first-mappers.md) — a
walkthrough from a clean clone to validated mapper files.

## Quick start

```console
git clone git@github.com:PHES-ODM/PHES-ODM-MapGenerator.git
cd PHES-ODM-MapGenerator
python3 -m venv .env && source .env/bin/activate
pip3 install -r requirements.txt
pip3 install -e . --no-deps

# Generate the NWSS → ODM v3 mappers
python odm_map_maker/make_mappers_cli.py \
    --config odm_map_maker/configs/nwss_to_odm.yaml \
    --output-dir ../gen/nwss-reporting-to-v3

# Check them
python odm_map_maker/validate_mappers/mapper_validator.py \
    --mappers-dir ../gen/nwss-reporting-to-v3/mappers \
    --source-schema odm_map_maker/data/nwss_reporting/linkml/nwss_reporting.yaml \
    --target-schema odm_map_maker/data/odm_v3/linkml/odm_v3.yaml \
    --output-dir ../gen/validate/nwss-reporting-to-v3 \
    --tag nwss-reporting-to-v3
```

## Documentation

Full documentation is published at
<https://phes-odm.github.io/PHES-ODM-MapGenerator/> and lives in
[docs/](docs/), indexed by [docs/index.md](docs/index.md).

It is organized on the [Divio/Diátaxis](https://diataxis.fr/) framework — four
sections, each answering a different kind of question:

| Section | Answers | Start at |
| --- | --- | --- |
| **Tutorials** | "Teach me the basics" | [Generate your first mappers](docs/tutorials/generate-your-first-mappers.md) |
| **How-to guides** | "How do I do X?" | [How-to index](docs/how-to/index.md) |
| **Explanation** | "Why is it like this?" | [Concepts and vocabulary](docs/explanation/concepts.md) |
| **Reference** | "What does this option do?" | [Reference index](docs/reference/index.md) |

The pages you are most likely to want:

| Document | Contents |
| --- | --- |
| [Concepts and Vocabulary](docs/explanation/concepts.md) | The problem, the design split, and every term used elsewhere |
| [Architecture](docs/explanation/architecture.md) | Code layout, generation pipeline, module responsibilities |
| [Mapping Configuration Files](docs/reference/mapping-config-files.md) | Every column of the `maps`, `wide`, and `enums` Excel tabs |
| [CLI Configuration Files](docs/reference/cli-config-files.md) | The `--config` YAML file format |
| [Wide Columns](docs/explanation/wide-columns.md) | Why one input row sometimes becomes several output rows |
| [Mapper Validator](docs/reference/mapper-validator.md) | Checking enumeration mappings in generated mappers |
| [Slot Derivations Checker](docs/reference/slot-derivations-checker.md) | Checking slot derivations for structural problems |
| [ODM v1 to vx (legacy)](docs/reference/make-v1-to-vx.md) | The older data-dictionary-driven generator |
| [Contributing](CONTRIBUTING.md) | Dev setup, tests, linting, conventions |

## Installation

To clone the repository and create a new virtual environment, run the following on the command-line:

```console
git clone git@github.com:PHES-ODM/PHES-ODM-MapGenerator.git
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

Install Python library requirements and the package itself:

```console
pip3 install -r requirements.txt
pip3 install -e . --no-deps
```

The editable install makes the `odm_map_maker` package importable from any
working directory, and provides an `odm-map-maker` console script equivalent to
`python odm_map_maker/make_mappers_cli.py`.

Python 3.10 or newer is required.

## Running the Tests

The test suite uses [pytest](https://docs.pytest.org/). Install the development
requirements (which include pytest, pytest-cov, and ruff alongside the runtime
dependencies):

```console
pip3 install -r requirements-dev.txt
pip3 install -e . --no-deps
```

Then run all tests from the repository root:

```console
pytest tests/          # add -v for per-test output
```

See [Contributing](CONTRIBUTING.md) for linting, coverage, and conventions.

## Project Structure

```text
PHES-ODM-MapGenerator/
├── odm_map_maker/                   # Main package
│   ├── make_mappers_cli.py          # Primary entry point — generate mapper YAML files
│   ├── make_mappers.py              # Core mapping logic (MakeMappers class)
│   ├── make_v1_to_vx.py             # Legacy: generate mappers from v1 using the data
│   │                                #   dictionary (see docs/reference/make-v1-to-vx.md)
│   ├── configs/                     # Ready-to-use CLI configuration files
│   │   ├── nwss_to_odm.yaml
│   │   ├── odm_v1_to_odm.yaml
│   │   └── pha4ge_to_odm.yaml
│   ├── data/                        # Source data: LinkML schemas and mapping config files
│   │   ├── mapping_config_files/    # Excel mapping configuration workbooks
│   │   ├── nwss_reporting/          # NWSS reporting LinkML schema
│   │   ├── nwss_public_concentration/
│   │   ├── nwss_public_metric/
│   │   ├── odm_v1/                  # ODM v1 LinkML schema
│   │   ├── odm_v2/                  # ODM v2 LinkML schema
│   │   ├── odm_v3/                  # ODM v3 LinkML schema
│   │   └── pha4ge/                  # PHA4GE LinkML schema
│   ├── validate_mappers/            # Validate generated mapper files
│   │   ├── mapper_validator.py      # Validate mapper YAML files against schemas
│   │   └── slot_derivations_checker.py  # Check for potential slot mapping problems
│   ├── odm_vx/                      # Internal helpers used by make_v1_to_vx.py (legacy)
│   └── utils/                       # Internal utilities
│       ├── general_utils.py         # File I/O and DataFrame helpers
│       ├── logger.py                # Logging setup
│       ├── mapper_utils.py          # Mapper building helpers (MappingColumns,
│       │                            #   format_slot_name, expand_wide_derivations, etc.)
│       ├── schema_utils.py          # LinkML schema helpers
│       └── selector_filter.py       # Row filtering by selector strings
├── tests/                           # pytest test suite
├── CONTRIBUTING.md                  # Dev setup, tests, linting, conventions
├── mkdocs.yml                       # Documentation site configuration
└── docs/                            # Documentation (see docs/index.md)
    ├── index.md                     # Documentation home and index
    ├── getting_started.md           # Guide: onboarding and end-to-end walkthrough
    ├── architecture.md              # Guide: code layout and generation pipeline
    ├── wide_columns_example.md      # Example: wide-to-long mapping
    ├── mapping_config_files.md      # Reference: Excel mapping file column definitions
    ├── make_mappers_cli_config.md   # Reference: YAML CLI config file format
    ├── mapper_validator.md          # Reference: mapper_validator.py script
    ├── slot_derivations_checker.md  # Reference: slot_derivations_checker.py script
    └── make_v1_to_vx.md             # Reference: legacy make_v1_to_vx.py script
```

### Where to look when making changes

Most changes to *what* gets mapped are data changes, not code changes — see
[Do I need to change code?](CONTRIBUTING.md#do-i-need-to-change-code).

| What you want to change | Where to look |
| --- | --- |
| Configuration files for generating the LinkML-Map mapping schemas | `odm_map_maker/data/mapping_config_files/*.xlsx` |
| Add support for a new source dataset | Create a new Excel mapping file in `data/mapping_config_files/` and a config file in `configs/`; add a section in this README and a LinkML schema in `data/` |
| Core mapper generation logic | `odm_map_maker/make_mappers.py` |
| CLI behaviour | `odm_map_maker/make_mappers_cli.py` |
| Configuration files provided to `odm_map_maker/make_mappers_cli.py` | `odm_map_maker/configs/*.yaml` |
| Mapper validation logic | `odm_map_maker/validate_mappers/mapper_validator.py` |
| Source or target LinkML schema | `odm_map_maker/data/<source>/linkml/<source>.yaml` |
| Documentation | `docs/`, plus the `nav` section of `mkdocs.yml` |

## Overview

The main entry point for generating mapping specifications is
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
[Mapping Config Files](docs/reference/mapping-config-files.md) for instructions on how to
modify or create your own mapping files.

## General CLI

The script [odm_map_maker/make_mappers_cli.py](odm_map_maker/make_mappers_cli.py)
accepts the following command-line options. All options can also be specified in
a YAML config file passed via `--config` — see
[CLI Configuration Files](docs/reference/cli-config-files.md) for details.

**--config** (Optional)  
Path to a YAML configuration file. Keys are CLI option names (with hyphens or
underscores). Values serve as defaults and are overridden by any arguments
supplied on the command line. Paths in the config file are resolved relative to
the config file's location. See [CLI Configuration Files](docs/reference/cli-config-files.md).

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
configuration file before looking them up in the source schema. Useful when the
config file uses a different casing or punctuation convention than the schema.
See [Slot Format Operations](#slot-format-operations) for available values.

**--target-slot-format-operations** (Optional)  
Formatting operations applied to all target slot names found in the
configuration file before looking them up in the target schema.
See [Slot Format Operations](#slot-format-operations) for available values.

**--source-match-ontology-id-regex** (Optional)  
Regular expression that matches ontology IDs in source schema enum values. When
set, ontology IDs found in the source schema are automatically added to enum
values that lack one in the mapping configuration.

**--target-match-ontology-id-regex** (Optional)  
Regular expression that matches ontology IDs in target schema enum values.

## Slot Format Operations

The `--source-slot-format-operations` and `--target-slot-format-operations`
options (and their YAML config equivalents) apply a pipeline of string
transformations to slot names read from the mapping configuration before looking
them up in the LinkML schema. Use them to normalize slot names that differ in
casing or punctuation between the config file and the schema.

Available operations:

| Operation | Effect |
| --- | --- |
| `lowercase` | Convert to lower case |
| `uppercase` | Convert to upper case |
| `alpha_numeric_underscore` | Replace every non-alphanumeric character with `_` |
| `single_underscores` | Collapse consecutive underscores into one (`__` → `_`) |
| `trim_trailing_underscores` | Remove trailing underscores |
| `trim_whitespace` | Remove leading and trailing whitespace |
| `remove_special` | Remove all non-alphanumeric, non-space characters |
| `{ remove_chars: "xyz" }` | Remove each listed character from the name (e.g. removes `x`, `y`, and `z`) |

Operations are applied in the order listed. Specify them as a YAML list in a
config file:

```yaml
source-slot-format-operations:
  - lowercase
  - "{ remove_chars: '-'}"
  - alpha_numeric_underscore
  - single_underscores
  - trim_trailing_underscores
```

Or repeat the flag on the command line:

```console
python odm_map_maker/make_mappers_cli.py \
    --source-slot-format-operations alpha_numeric_underscore \
    --source-slot-format-operations single_underscores \
    --source-slot-format-operations trim_trailing_underscores \
    ...
```

Slot names that begin with the `_extra_` prefix (special extra slots — see
[Mapping Config Files](docs/reference/mapping-config-files.md#extra-columns)) are never
transformed.

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
[Mapper Validator](docs/reference/mapper-validator.md) for full documentation and
examples for each mapping type.

## Utility Scripts

### slot_derivations_checker.py

[odm_map_maker/validate_mappers/slot_derivations_checker.py](odm_map_maker/validate_mappers/slot_derivations_checker.py)
inspects generated mapper YAML files for structural problems in slot derivations
that would not be caught by `mapper_validator.py`. It supports two checks:

- **multi_to_single** — flags source slots that are multi-valued being mapped
  to single-valued target slots (which can silently truncate data).
- **free_text_to_enum** — flags free-text source slots mapped to enumeration
  target slots (which can produce invalid enum values).

```console
python odm_map_maker/validate_mappers/slot_derivations_checker.py \
    --checker multi_to_single \
    --mapper-dir <mappers-dir> \
    --source-schema <source-schema.yaml> \
    --target-schema <target-schema.yaml>
```

See [Slot Derivations Checker](docs/reference/slot-derivations-checker.md) for full
documentation.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup, the test and lint
commands that CI enforces, and coding conventions.

## Mapping Data

Once all mapping specification YAML files are created, data can be mapped from
source to target datasets. To perform these mappings, as well as other
operations such as cleaning data and generating IDs, see the
[PHES-ODM-Mapper](https://github.com/Big-Life-Lab/PHES-ODM-Mapper) repository.
