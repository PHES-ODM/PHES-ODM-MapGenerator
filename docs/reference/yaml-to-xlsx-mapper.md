# YAML to XLSX Mapper

[odm_map_maker/yaml_to_xlsx_mapper/yaml_to_xlsx_mapper.py](../../odm_map_maker/yaml_to_xlsx_mapper/yaml_to_xlsx_mapper.py)
reverse-engineers a directory of
[LinkML Map](https://github.com/linkml/linkml-map) YAML files into a
human-editable Excel mapping configuration workbook. It is the complement of
[make_mappers_cli.py](../../README.md): where that script turns an Excel workbook
into YAML mappers, this script turns YAML mappers back into an Excel workbook.

The typical use case is **bootstrapping**: you already have a set of working
mapper YAML files (perhaps generated for an earlier ODM version or another
source), and you want to produce a starting-point Excel workbook that can then
be edited and fed back into `make_mappers_cli.py`.

## Workflow context

```text
Excel mapping config  ──►  make_mappers_cli.py  ──►  LinkML Map YAML files
                                                            │
                                ┌───────────────────────────┘
                                │
                                ▼
                     yaml_to_xlsx_mapper.py  ──►  mapping_config.xlsx  (bootstrap)
```

## CLI options

**--source-dir** (Required)  
Directory containing the LinkML Map YAML files to read. Every `.yaml` file in
the directory is processed.

**--source-schema** (Required)  
Path to the LinkML schema for the *source* dataset (e.g.
`odm_map_maker/data/nwss_reporting/linkml/nwss_reporting.yaml`). Used to look
up the range of source slots when deciding where to place enum derivations.

**--target-schema** (Required)  
Path to the LinkML schema for the *target* dataset (e.g.
`odm_map_maker/data/odm_v2/linkml/odm_v2.yaml`). Reserved for future use;
currently loaded but not queried during conversion.

**--output-dir** (Required)  
Directory where the output workbook `mapping_config.xlsx` is written. Created
automatically if it does not exist.

## Running the tool

```console
python odm_map_maker/yaml_to_xlsx_mapper/yaml_to_xlsx_mapper.py \
    --source-dir <mappers-dir> \
    --source-schema <source-schema.yaml> \
    --target-schema <target-schema.yaml> \
    --output-dir <output-dir>
```

### NWSS reporting → ODM v2

```console
python odm_map_maker/yaml_to_xlsx_mapper/yaml_to_xlsx_mapper.py \
    --source-dir ../gen/nwss-reporting-to-v2/mappers \
    --source-schema odm_map_maker/data/nwss_reporting/linkml/nwss_reporting.yaml \
    --target-schema odm_map_maker/data/odm_v2/linkml/odm_v2.yaml \
    --output-dir ../gen/nwss-reporting-to-v2/bootstrap
```

### ODM v1 → ODM v3

```console
python odm_map_maker/yaml_to_xlsx_mapper/yaml_to_xlsx_mapper.py \
    --source-dir ../gen/odm-v1-to-v3/mappers \
    --source-schema odm_map_maker/data/odm_v1/linkml/odm_v1.yaml \
    --target-schema odm_map_maker/data/odm_v3/linkml/odm_v3.yaml \
    --output-dir ../gen/odm-v1-to-v3/bootstrap
```

### PHA4GE → ODM v3

```console
python odm_map_maker/yaml_to_xlsx_mapper/yaml_to_xlsx_mapper.py \
    --source-dir ../gen/pha4ge-to-v3/mappers \
    --source-schema odm_map_maker/data/pha4ge/linkml/pha4ge.yaml \
    --target-schema odm_map_maker/data/odm_v3/linkml/odm_v3.yaml \
    --output-dir ../gen/pha4ge-to-v3/bootstrap
```

## Output

The tool writes a single file: `mapping_config.xlsx`. The workbook contains one
or more of the following sheet types:

| Sheet name | Content |
|---|---|
| `{TargetClass}` | Standard (long) slot-to-slot mappings for that target class |
| `wide_{TargetClass}` | Wide-format mappings for that target class |
| `enums` | Enum value mappings that are shared across more than one source slot |

### Standard mapping sheets

Each standard sheet is named after the target class (e.g. `measures`,
`samples`). It contains one row per source-to-target slot mapping, with the
following columns:

| Column | Description |
|---|---|
| `sourceClass` | Name of the source LinkML class |
| `sourceSlot` | Name of the source slot being mapped from |
| `sourceValue` | Enum value of the source slot (populated for enum rows only) |
| `targetClass` | Name of the target LinkML class |
| `targetSlot` | Name of the target slot being mapped to |
| `targetValue` | Template value — usually `{{sourceSlot}}` for direct copies |
| `targetExpr` | LinkML-Map expression used when there is no direct source slot |
| `customData` | Reserved; always empty in bootstrapped output |

When multiple source classes map to the same target class, the groups appear in
the same sheet, separated by a single blank row, sorted alphabetically by source
class name.

When a source slot's range is an enumeration, the single slot row is replaced
by one row per enum value mapping, with `sourceValue` and `targetValue`
populated for each pair.

### Wide mapping sheets

Wide sheets are named `wide_{TargetClass}` (e.g. `wide_measures`). Each row
represents one *instance* of the target class that is built from several source
slots. Instead of one row per slot, columns are added dynamically:

- **`{targetSlot}_value`** — the template value for `targetSlot`
  (e.g. `{{sourceSlot}}` for a direct copy, or a literal string for a constant)
- **`{targetSlot}_expr`** — a LinkML-Map expression for `targetSlot`
  (used when the value is computed rather than copied directly)

Wide sheets also include `sourceClass`, `sourceSlot`, `sourceValue`,
`targetClass`, and `targetValue` columns.

### Enums sheet

When the same enum derivation is referenced by more than one source slot within
the same YAML file, the enum value mappings are written to a global `enums`
sheet instead of being inlined into the slot row. The sheet has the same columns
as a standard mapping sheet.

## What the tool reads from the YAML files

The tool processes the `class_derivations` and `enum_derivations` sections of
each LinkML Map YAML file.

### `class_derivations`

Each entry maps a target class to a source class via `populated_from`, and lists
slot-by-slot derivations:

```yaml
class_derivations:
  samples:
    populated_from: nwss
    slot_derivations:
      sampleID:
        populated_from: sample_id
      collectionDate:
        populated_from: sample_collect_date
      collectionDateEnd:
        populated_from: sample_collect_dateEnd
      notes:
        expr: "''"
```

This produces rows in a `samples` sheet:

| sourceClass | sourceSlot | sourceValue | targetClass | targetSlot | targetValue | targetExpr | customData |
|---|---|---|---|---|---|---|---|
| nwss | sample_id | | samples | sampleID | `{{sample_id}}` | | |
| nwss | sample_collect_date | | samples | collectionDate | `{{sample_collect_date}}` | | |
| nwss | sample_collect_dateEnd | | samples | collectionDateEnd | `{{sample_collect_dateEnd}}` | | |
| nwss | | | samples | notes | | `''` | |

### `enum_derivations`

Each entry maps source enum values to target enum values:

```yaml
enum_derivations:
  vs_collection_water_type:
    populated_from: vs_collection_water_type
    permissible_value_derivations:
      wW:
        populated_from: raw_wastewater
      pSl:
        populated_from: primary_sludge
      rWW:
        sources:
          - raw_wastewater
          - settled_solids
```

When a source slot's range is `vs_collection_water_type` and only one slot
uses that enum, the rows are inserted inline, replacing the plain slot row:

| sourceClass | sourceSlot | sourceValue | targetClass | targetSlot | targetValue | targetExpr | customData |
|---|---|---|---|---|---|---|---|
| nwss | collection_water_type | raw_wastewater | samples | collection | | | |
| nwss | collection_water_type | primary_sludge | samples | collection | | | |
| nwss | collection_water_type | raw_wastewater | samples | collection | | | |
| nwss | collection_water_type | settled_solids | samples | collection | | | |

If two or more source slots share the same enum, the rows go to the global
`enums` sheet instead.

### Wide-format YAML files

A YAML file is treated as a wide mapping when its `class_derivations` key
contains bracket notation — `TargetClass[...]` — matching the convention used
by `make_mappers_cli.py`:

```yaml
class_derivations:
  measures[000,0000=collection_water_temp]:
    populated_from: nwss
    slot_derivations:
      datasetID:
        populated_from: lab_id
      compartment:
        expr: '"wat"'
      measure:
        expr: '''temp'''
      value:
        populated_from: collection_water_temp
      unit:
        expr: '''cel'''
```

The tool strips the `[...]` suffix to determine the target class (`measures`),
and pivots the derivations into a single wide row in the `wide_measures` sheet:

| sourceClass | sourceSlot | sourceValue | targetClass | targetValue | datasetID_value | compartment_value | measure_value | value_value | unit_value |
|---|---|---|---|---|---|---|---|---|---|
| nwss | collection_water_temp | | measures | | `{{lab_id}}` | wat | temp | `{{collection_water_temp}}` | cel |

Slots with a `populated_from` produce `{targetSlot}_value` set to
`{{sourceSlot}}`. Slots with a quoted constant `expr` (e.g. `'cel'`) produce
`{targetSlot}_value` set to the unquoted string (`cel`). Slots with a
non-quoted expression produce `{targetSlot}_expr`.

## Notes on the bootstrapped output

- **Rows are sorted** alphabetically by target slot name within each
  source-class group.
- **Groups** (different source classes mapping to the same target class) are
  separated by a single blank row.
- **`customData`** is always empty in bootstrapped output. Add selectors or
  other metadata by hand after bootstrapping.
- The output is a **starting point**, not a finished mapping configuration.
  Review every sheet before using it as input to `make_mappers_cli.py`.
