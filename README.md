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

## Install

Python 3.10 or newer is required.

```console
git clone git@github.com:PHES-ODM/PHES-ODM-MapGenerator.git
cd PHES-ODM-MapGenerator
python3 -m venv .env && source .env/bin/activate   # Windows: .env\Scripts\activate
pip3 install -r requirements.txt
pip3 install -e . --no-deps
```

The editable install makes the `odm_map_maker` package importable from any
working directory, and provides an `odm-map-maker` console script equivalent to
`python odm_map_maker/make_mappers_cli.py`.

## Generate the mappers

The three mappings the repository exists to produce. Each config file already
holds every option needed, so no other arguments are required:

```console
# ODM v1 → ODM v3
python odm_map_maker/make_mappers_cli.py \
    --config odm_map_maker/configs/odm_v1_to_odm.yaml

# NWSS reporting → ODM v3
python odm_map_maker/make_mappers_cli.py \
    --config odm_map_maker/configs/nwss_to_odm.yaml

# PHA4GE → ODM v3
python odm_map_maker/make_mappers_cli.py \
    --config odm_map_maker/configs/pha4ge_to_odm.yaml
```

Output goes to a `gen/` directory *beside* the repository, one sub-directory per
mapping — `../gen/odm-v1-to-v3`, `../gen/nwss-reporting-to-v3`, and
`../gen/pha4ge-to-v3`. Each contains `mappers/` (the LinkML Map YAML files, the
artifacts you want) and `configs/` (the extracted maps, wide, and enums tables,
useful for debugging). Every run clears CSV, TSV, and YAML files from the
directories it writes to. Pass `--output-dir` to write somewhere else.

## Check the generated mappers

Run the validator against the same schemas the mappers were generated from:

```console
# ODM v1 → ODM v3
python odm_map_maker/validate_mappers/mapper_validator.py \
    --mappers-dir ../gen/odm-v1-to-v3/mappers \
    --source-schema odm_map_maker/data/odm_v1/linkml/odm_v1.yaml \
    --target-schema odm_map_maker/data/odm_v3/linkml/odm_v3.yaml \
    --output-dir ../gen/validate/odm-v1-to-v3 \
    --tag odm-v1-to-v3 \
    --simplify

# NWSS reporting → ODM v3
python odm_map_maker/validate_mappers/mapper_validator.py \
    --mappers-dir ../gen/nwss-reporting-to-v3/mappers \
    --source-schema odm_map_maker/data/nwss_reporting/linkml/nwss_reporting.yaml \
    --target-schema odm_map_maker/data/odm_v3/linkml/odm_v3.yaml \
    --output-dir ../gen/validate/nwss-reporting-to-v3 \
    --tag nwss-reporting-to-v3 \
    --simplify

# PHA4GE → ODM v3
python odm_map_maker/validate_mappers/mapper_validator.py \
    --mappers-dir ../gen/pha4ge-to-v3/mappers \
    --source-schema odm_map_maker/data/pha4ge/linkml/pha4ge.yaml \
    --target-schema odm_map_maker/data/odm_v3/linkml/odm_v3.yaml \
    --output-dir ../gen/validate/pha4ge-to-v3 \
    --tag pha4ge-to-v3 \
    --simplify
```

Findings are advisory, not errors — see
[Check generated mappers](docs/how-to/check-generated-mappers.md), which also
covers `slot_derivations_checker.py`.

## Other targets

- **ODM v2 instead of v3** — override `--target-schema`, `--output-dir`, and
  `--selectors odm=2`. See
  [Generate mappers for ODM v2](docs/how-to/target-odm-v2.md); omitting
  `--selectors` silently drops the v2-specific rows.
- **A different NWSS dictionary type** (`public_concentration`,
  `public_metric`) — override `--source-schema` and `--output-dir`. See
  [NWSS to ODM](docs/reference/cli-config-files.md#nwss-to-odm).

## How it works

[odm_map_maker/make_mappers_cli.py](odm_map_maker/make_mappers_cli.py) reads a
**mapping file** — an Excel workbook in
[odm_map_maker/data/mapping_config_files/](odm_map_maker/data/mapping_config_files/)
describing how source slots, enumeration values, and wide columns map to the
target — together with LinkML schemas for the source and target datasets, and
writes [LinkML Map](https://github.com/linkml/linkml-map) YAML specifications.

Changing *what* gets mapped means editing the workbook, not the code. See
[Fix an incorrect mapping](docs/how-to/fix-a-mapping.md) to get started, and
[CLI Configuration Files](docs/reference/cli-config-files.md) for every
command-line option.

## Documentation

Full documentation is published at
<https://phes-odm.github.io/PHES-ODM-MapGenerator/> and lives in
[docs/](docs/), indexed by [docs/index.md](docs/index.md).

| Section | Answers |
| --- | --- |
| [Tutorials](docs/tutorials/index.md) | "Teach me the basics" |
| [How-to guides](docs/how-to/index.md) | "How do I do X?" |
| [Explanation](docs/explanation/index.md) | "Why is it like this?" |
| [Reference](docs/reference/index.md) | "What does this option do?" |

## Project structure

```text
PHES-ODM-MapGenerator/
├── odm_map_maker/                   # Main package
│   ├── make_mappers_cli.py          # Primary entry point — generate mapper YAML files
│   ├── make_mappers.py              # Core mapping logic (MakeMappers class)
│   ├── make_v1_to_vx.py             # Legacy: generate mappers from v1 using the data
│   │                                #   dictionary (see docs/reference/make-v1-to-vx.md)
│   ├── configs/                     # Ready-to-use CLI configuration files
│   ├── data/                        # Source data: LinkML schemas and mapping workbooks
│   │   ├── mapping_config_files/    # Excel mapping configuration workbooks
│   │   ├── nwss_reporting/          # One directory per dataset, each holding linkml/
│   │   ├── nwss_public_concentration/
│   │   ├── nwss_public_metric/
│   │   ├── odm_v1/
│   │   ├── odm_v2/
│   │   ├── odm_v3/
│   │   └── pha4ge/
│   ├── validate_mappers/            # Check generated mapper files
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
├── docs/                            # Documentation source (see docs/index.md)
├── mkdocs.yml                       # Documentation site configuration
└── CONTRIBUTING.md                  # Dev setup, tests, linting, conventions
```

Most changes to *what* gets mapped are data changes, not code changes — see
[Do I need to change code?](CONTRIBUTING.md#do-i-need-to-change-code).

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup, the test and lint
commands that CI enforces, and coding conventions.

## Mapping data

Once the mapping specification YAML files exist, data can be mapped from source
to target. To perform those mappings, as well as operations such as cleaning
data and generating IDs, see the
[PHES-ODM-Mapper](https://github.com/Big-Life-Lab/PHES-ODM-Mapper) repository.
