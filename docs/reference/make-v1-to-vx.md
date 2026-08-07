# Generating ODM v1 to ODM vx Mapper Specifications

The script [odm_map_maker/make_v1_to_vx.py](../../odm_map_maker/make_v1_to_vx.py)
generates all the LinkML Mapping specification files needed to map data from
ODM v1 to a target ODM version (v2, v3, etc., referred to as "vx"). Each
specification file covers a single v1-to-vx table pair. For v1 tables that
have "wide" columns requiring a wide-to-long transformation, additional
specification files are generated. The v1 table `AssayMethod` is one such
table.

> **Note:** This script reads mapping information that is embedded directly in the
> ODM vx data dictionary. The preferred approach going forward is to define mappings
> in a separate configuration file instead; see
> [odm_map_maker/make_mappers_cli.py](../../odm_map_maker/make_mappers_cli.py)
> and its config files under
> [odm_map_maker/configs/](../../odm_map_maker/configs/).

## Running the Script

```bash
python odm_map_maker/make_v1_to_vx.py \
    --config <config-file> \
    --output-dir <output-dir> \
    --vx-data-dictionary <vx-data-dictionary> \
    --source-schema <source-schema> \
    --target-schema <target-schema> \
    [--wide-dir <wide-dir>] \
    [--max-mapping-only]
```

## Arguments

| Argument | Required | Description |
| --- | --- | --- |
| `--config` | Yes | Config file specifying which source tables map to which target tables and other details. |
| `--output-dir` | Yes | Directory to write all output to. Subdirectories are created automatically; the final mapper YAML files are written to the `mappers/` subdirectory. |
| `--vx-data-dictionary` | Yes | Path to the ODM vx Excel data dictionary. Must contain a sheet named `parts` that holds the ODM vx metadata along with the ODM v1 mapping columns (e.g. `version1Table`, `version1Variable`). |
| `--source-schema` | Yes | Path to the source (ODM v1) LinkML schema. |
| `--target-schema` | Yes | Path to the target (ODM vx) LinkML schema. |
| `--wide-dir` | No | Directory containing CSV files that describe wide-column configurations. All CSV files in this directory are used. |
| `--max-mapping-only` | No | If set, only the mapper specification with the most columns copied from each v1 table is kept. This filters out low-value mappings where only a single identifier column is transferred. |

## Processing Steps

### Step 1 — Clean Output Directories

Old CSV, TSV, and YAML files are deleted from the output directories before anything
is written. This ensures no stale artifacts from previous runs are left behind.

### Step 2 — Extract the Parts Sheet

The ODM vx data dictionary is an Excel workbook. The `parts` sheet is
extracted and saved as a CSV file for use in subsequent steps.

### Step 3 — Prepare the Parts Data

The raw parts CSV requires several preprocessing steps before it can drive mapper
generation:

1. Rows that do not define any mapping from v1 (i.e. those missing values in the
   `version1Table`, `version1Location`, `version1Variable`, and `version1Category`
   columns) are removed.
2. Rows that contain multiple v1 table or variable names separated by semicolons
   (e.g. `WWMeasure;SiteMeasure`) are split into separate rows so that every row
   describes exactly one mapping.
3. Values that use an ampersand to combine two alternatives (e.g. `conf & report`)
   are resolved to the first alternative.
4. V1 enumeration names are derived from the `version1Table` and `version1Variable`
   columns and added as a new column.

### Step 4 — Generate Mapper Specifications

Using the prepared parts data, a separate LinkML Mapping specification (YAML) file
is created for each v1-to-vx table pair. The resulting files can be used directly
with the `linkml-tr` command-line tool or through the LinkML-Map Python API.
