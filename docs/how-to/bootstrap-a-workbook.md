# Bootstrap a workbook from existing mappers

If you already have working mapper YAML files — generated for an earlier ODM
version, or for a related source format — you can reverse them into an Excel
workbook and edit from there instead of starting from a blank sheet.

```console
python odm_map_maker/yaml_to_xlsx_mapper/yaml_to_xlsx_mapper.py \
    --source-dir ../gen/nwss-reporting-to-v2/mappers \
    --source-schema odm_map_maker/data/nwss_reporting/linkml/nwss_reporting.yaml \
    --target-schema odm_map_maker/data/odm_v2/linkml/odm_v2.yaml \
    --output-dir ../gen/nwss-reporting-to-v2/bootstrap
```

Every `.yaml` file in `--source-dir` is processed. The output is a single
`mapping_config.xlsx` in `--output-dir`.

## What you get

| Sheet | Content |
| --- | --- |
| `{TargetClass}` | Standard slot-to-slot mappings for that target class |
| `wide_{TargetClass}` | Wide-format mappings for that target class |
| `enums` | Enum value mappings shared by more than one source slot |

Enum mappings used by exactly one source slot are inlined into that slot's rows
instead of going to the `enums` sheet.

## Before you use it as input

The output is a **starting point, not a finished configuration**. Review every
sheet, and expect to do at least this much:

- **`customData` is always empty.** Add selectors and other metadata by hand.
- **Groups are separated by blank rows** — different source classes mapping to
  the same target class share a sheet. Keep or remove the separators as you
  reorganize.
- **Sheet names become the tab names you must list** in `excel-maps-sheets`,
  `excel-wide-sheets`, and `excel-enums-sheets` in your config file. The
  bootstrapped names (`measures`, `wide_measures`, …) are not the defaults the
  shipped configs use.

Then feed it back through the generator and check the round trip:

```console
python odm_map_maker/make_mappers_cli.py \
    --config odm_map_maker/configs/<your-config>.yaml
```

Full description of the output format:
[YAML to XLSX Mapper](../reference/yaml-to-xlsx-mapper.md).
