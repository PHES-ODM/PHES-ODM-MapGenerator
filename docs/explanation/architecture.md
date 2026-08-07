# Architecture

How the code is organized and what happens when you run
`make_mappers_cli.py`. Read [Concepts and vocabulary](concepts.md) first for the
terms used below.

## Repository layout

```text
PHES-ODM-MapGenerator/
├── odm_map_maker/
│   ├── make_mappers_cli.py       # Entry point: CLI, config loading, sheet extraction
│   ├── make_mappers.py           # MakeMappers — the generation engine
│   ├── validate.py               # Validate a data file against a LinkML schema
│   ├── make_v1_to_vx.py          # Legacy generator driven by the ODM data dictionary
│   ├── configs/                  # Ready-to-use CLI config files (one per mapping)
│   ├── data/                     # LinkML schemas + Excel mapping workbooks
│   │   ├── mapping_config_files/ # The human-edited Excel workbooks
│   │   ├── nwss_reporting/       # Each source/target format has <name>/linkml/<name>.yaml
│   │   ├── nwss_public_concentration/
│   │   ├── nwss_public_metric/
│   │   ├── odm_v1/               # …plus odm_v1/custom_wide/ for the legacy generator
│   │   ├── odm_v2/
│   │   ├── odm_v3/
│   │   └── pha4ge/
│   ├── validate_mappers/
│   │   ├── mapper_validator.py         # Enumeration completeness/consistency checks
│   │   └── slot_derivations_checker.py # Structural slot-derivation checks
│   ├── yaml_to_xlsx_mapper/
│   │   └── yaml_to_xlsx_mapper.py      # Reverse: mapper YAML → Excel workbook
│   ├── odm_vx/                   # Helpers used only by the legacy make_v1_to_vx.py
│   └── utils/                    # Shared helpers (see table below)
├── tests/                        # pytest suite
└── docs/                         # This documentation
```

There are no `__init__.py` files; `odm_map_maker` is an implicit namespace
package. Scripts are runnable either directly (`python odm_map_maker/...`) or,
after `pip install -e .`, via the `odm-map-maker` console entry point, which
maps to `make_mappers_cli:app`.

## The generation pipeline

Running `make_mappers_cli.py` moves through five stages.

### 1. Resolve arguments — `make_mappers_cli.py`

`--config` is an eager Typer option handled by `_config_callback`. It loads the
YAML file and injects its values into Click's `default_map`, so command-line
arguments naturally take precedence. Keys listed in `_PATH_KEYS` (schemas,
workbook, output directory, and the CSV/TSV file lists) are resolved relative to
the **config file's directory**, which is why config files can live anywhere in
the tree and still use short relative paths.

### 2. Clear and populate the output directory

Three subdirectories under `--output-dir` are cleared of existing `.csv`,
`.tsv`, and `.yaml` files by `clear_dirs`: `configs/`, `mappers/`, and
`mapped_data/`. The last is not written by this repository — it is cleaned for
the benefit of the downstream
[PHES-ODM-Mapper](https://github.com/Big-Life-Lab/PHES-ODM-Mapper).

Each requested Excel sheet is then extracted verbatim to `configs/` by
`extract_sheets`, named positionally: `maps0.csv`, `maps1.csv`, `wide0.csv`,
`enums0.csv`, and so on, in the order given by `--excel-maps-sheets`,
`--excel-wide-sheets`, and `--excel-enums-sheets`. Any standalone CSV/TSV files
passed via `--maps-files`, `--wide-files`, or `--enums-files` are copied into the
same directory. From this point on the pipeline only sees CSV files — the Excel
format is not a dependency of the engine.

Extraction uses `CONFIG_READ_KWARGS`, which forces `sourceValue` and
`targetValue` to be read as strings and treats only the empty string as NA. That
matters: without it, pandas would turn enum values such as `NA`, `None`, or
`nan` into missing data.

### 3. Load and filter the configuration — `MakeMappers.prepare_*_df`

`prepare_maps_df`, `prepare_wide_df`, and `prepare_enums_df` each read one CSV
and apply the same sequence of transformations:

1. strip whitespace and drop fully empty rows;
2. `drop_incomplete_rows` — if the sheet has a `Complete` column, keep only rows
   where it equals `1`;
3. `SelectorFilter.apply` against the `--selectors` given on the command line,
   which also removes the `selectors` column
   (see [selectors](../reference/mapping-config-files.md#selectors));
4. normalize the column set — unrecognized columns are dropped, missing known
   columns are added as empty;
5. `cleanup_slot_name` on the source and target slot columns, applying the
   configured format operations — except names carrying the `_extra_` prefix,
   which `format_slot_name` passes through untouched.

Column names are the constants on `MappingColumns` in
[utils/mapper_utils.py](../../odm_map_maker/utils/mapper_utils.py). That class is
the single source of truth linking workbook headers to the code.

### 4. Build derivations — `MakeMappers.make_mappers`

```text
maps CSVs  ──►  extract_class_derivations()  ──►  class derivations
           └─►  extract_enum_derivations()   ─┐
enums CSVs ────► extract_enum_derivations()  ─┴►  enum derivations
wide CSVs  ──►  make_wide_derivations()      ──►  one class derivation per wide group
```

- **`extract_class_derivations`** produces
  `derivations[source_class][target_class]` — a LinkML Map class derivation with
  one slot derivation per workbook row. A row becomes `populated_from` when
  `targetValue` is `{{sourceSlot}}`, or `expr` when `targetExpr` is set. The
  `customData` and `slotDerivationSettings` columns are merged into the slot
  derivation dictionary afterwards, so they can override anything.
- **`extract_enum_derivations`** produces the same two-level structure for
  enumeration mappings, from both the `maps` and `enums` sheets. Where an
  enumeration name is not given explicitly, it is looked up from the class and
  slot via `get_enum_names_for_slot`.
- **`make_wide_derivations`** groups each wide sheet by
  (`sourceClass`, `sourceSlot`, `targetClass`, `wideGroup`) and calls
  `expand_wide_derivations` to turn each group into its own class derivation.
  Rows whose `sourceSlot` *and* `wideGroup` are both blank are first given a
  synthetic unique `wideGroup` so each becomes its own output row — this is what
  lets a workbook author write several blank-source wide rows and get several
  output rows rather than one merged one.
- **`select_required_enum_derivations`** attaches to each class derivation only
  the enum derivations its slots actually need, so mappers stay small. For slot
  derivations that use `expr` rather than `populated_from`, the referenced source
  slots are recovered by parsing the expression's AST
  (`get_used_slots` / `get_source_slots_from_slot_derivation`) against the
  namespaces in `ENUM_MAPPED_EXPR_GLOBALS`.

### 5. Write one mapper per result

Each result becomes a standalone LinkML Map specification containing exactly one
real class derivation, plus the mandatory `Container` tree-root derivation
(`TREE_ROOT_CLASS_NAME`), plus its enum derivations. Files are named:

```text
mapper-{zero-padded index}-{sourceClass}-{targetClass}.yaml
```

with characters outside `[A-Za-z0-9 .,_]` replaced by underscores. Wide mappers
carry their bracket decoration in the target-class portion of the name, for
example `mapper-0000000003-nwss-measures_000,0000_collection_water_temp_.yaml`.

**One class derivation per file is deliberate.** LinkML Map produces at most one
output row per input row, so a wide-to-long mapping cannot be expressed in a
single specification. Splitting into many mappers and concatenating their
outputs downstream is how this repository works around that limitation — see
[Wide Columns Example](wide-columns.md).

## Module reference

### Core

| Module | Responsibility |
| --- | --- |
| [make_mappers_cli.py](../../odm_map_maker/make_mappers_cli.py) | Typer CLI, YAML config loading with relative-path resolution, sheet extraction, output directory management. |
| [make_mappers.py](../../odm_map_maker/make_mappers.py) | `MakeMappers` — loading, filtering, derivation building, wide expansion, mapper serialization. |

### Utilities — `odm_map_maker/utils/`

| Module | Responsibility |
| --- | --- |
| [mapper_utils.py](../../odm_map_maker/utils/mapper_utils.py) | `MappingColumns` (workbook column names), wide `_value`/`_expr` column handling, `expand_wide_derivations`, `format_slot_name`, expression AST parsing, `CONFIG_READ_KWARGS`. |
| [schema_utils.py](../../odm_map_maker/utils/schema_utils.py) | LinkML `SchemaView` queries: slot ranges, enum names for a slot, permissible values, class lookup, ontology-ID handling. |
| [selector_filter.py](../../odm_map_maker/utils/selector_filter.py) | `SelectorFilter` — include/exclude flags and versioned module selectors. |
| [general_utils.py](../../odm_map_maker/utils/general_utils.py) | File I/O and DataFrame helpers: `extract_sheets`, `clear_dirs`, `read_data_frame`, `expand_multi_rows`, plus the `TREE_ROOT_CLASS_NAME` and `EMPTY_CONFIG_VALUE` constants. |
| [logger.py](../../odm_map_maker/utils/logger.py) | `get_logger` and Rich-aware log formatting. |

### Tools

| Module | Responsibility |
| --- | --- |
| [validate_mappers/mapper_validator.py](../../odm_map_maker/validate_mappers/mapper_validator.py) | Enumeration completeness and consistency checks over a directory of mappers. See [Mapper Validator](../reference/mapper-validator.md). |
| [validate_mappers/slot_derivations_checker.py](../../odm_map_maker/validate_mappers/slot_derivations_checker.py) | Pluggable structural checks over slot derivations. See [Slot Derivations Checker](../reference/slot-derivations-checker.md). |
| [validate.py](../../odm_map_maker/validate.py) | Validate a CSV/TSV data file against a LinkML schema. See [Data Validator](../reference/data-validator.md). |
| [yaml_to_xlsx_mapper/yaml_to_xlsx_mapper.py](../../odm_map_maker/yaml_to_xlsx_mapper/yaml_to_xlsx_mapper.py) | Reverse-engineer mappers into a bootstrap workbook. See [YAML to XLSX Mapper](../reference/yaml-to-xlsx-mapper.md). |

### Legacy — `make_v1_to_vx.py` and `odm_vx/`

An earlier generator that read v1-to-vx mapping information embedded in the ODM
data dictionary (`version1Table`, `version1Variable`, … columns) rather than
from a separate workbook. It is retained for reference and reproducibility; new
work should use `make_mappers_cli.py`. See
[Generating ODM v1 to ODM vx](../reference/make-v1-to-vx.md).

## Cross-cutting conventions

**`_extra_` slots.** Target slots prefixed `_extra_` do not exist in the target
schema. They carry information needed by downstream processing (the
PHES-ODM-Mapper ID generator, for example) and are stripped from the final
output. Throughout the codebase they are exempt from slot-name formatting and
from schema lookups. See
[Extra Columns](../reference/mapping-config-files.md#extra-columns).

**`<empty>`.** `EMPTY_CONFIG_VALUE` is the literal string a workbook author
writes to mean "explicitly set this to blank", as distinct from leaving the cell
empty, which means "leave whatever an earlier sheet set".

**Ontology IDs.** Some schemas suffix enum values with an ontology ID, e.g.
`raw wastewater [GENEPIO:0001246]`. The `--source-match-ontology-id-regex` and
`--target-match-ontology-id-regex` options let the generator match workbook
values that omit the suffix against schema values that include it, and add the
ID back automatically (`add_ontoid_to_enum_value` / `remove_ontology_id`). Only
the PHA4GE config currently sets one.

**Everything flows through `SchemaView`.** Both schemas are loaded once in
`MakeMappers.__init__` and queried through
[schema_utils.py](../../odm_map_maker/utils/schema_utils.py). Add new schema
queries there rather than calling `SchemaView` directly from the engine.

## Tests

The suite in [tests/](../../tests/) covers the utility layer — `general_utils`,
`mapper_utils`, `schema_utils`, `selector_filter`, `logger` — plus
`mapper_validator`. `MakeMappers` itself has no direct unit tests; changes to
the engine are best verified by regenerating a known mapping and diffing the
output. See [Contributing](../../CONTRIBUTING.md).
