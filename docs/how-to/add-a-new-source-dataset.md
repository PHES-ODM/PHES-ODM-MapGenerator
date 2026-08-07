# Add support for a new source dataset

To map a format the repository does not yet handle, you need a LinkML schema for
it, a mapping workbook, and a CLI config file. No engine code changes are
required.

## 1. Add the source LinkML schema

Place it at `odm_map_maker/data/<source>/linkml/<source>.yaml`, matching the
layout of the existing formats (`nwss_reporting/`, `pha4ge/`, `odm_v1/`).

The schema must describe the source data as classes (tables) with slots
(columns), and declare enumerations for any coded column, since enumeration
mapping is looked up through the schema.

## 2. Create the mapping workbook

Add a workbook to `odm_map_maker/data/mapping_config_files/` with `maps`,
`wide`, and `enums` tabs as needed.

To avoid starting from a blank sheet, bootstrap it from an existing set of
mappers — see [Bootstrap a workbook from existing mappers](bootstrap-a-workbook.md).

Column reference:
[Mapping Configuration Files](../reference/mapping-config-files.md).

## 3. Create a CLI config file

Copy an existing file from `odm_map_maker/configs/` and adjust the schema paths
and sheet names:

```yaml
source-schema: ../data/<source>/linkml/<source>.yaml
target-schema: ../data/odm_v3/linkml/odm_v3.yaml
mapping-excel-file: ../data/mapping_config_files/<source>_to_odm_mapping.xlsx
output-dir: ../../../gen/<source>-to-v3

selectors:
  - odm=3

excel-maps-sheets:
  - maps
excel-wide-sheets:
  - wide_measures
excel-enums-sheets:
  - enums
```

**Paths are resolved relative to the config file's own directory**, not the
working directory. Full format:
[CLI Configuration Files](../reference/cli-config-files.md).

If the workbook's slot names differ from the schema's in casing or punctuation,
add format operations rather than editing the workbook — see
[Normalize slot names](normalize-slot-names.md).

## 4. Generate and check

```console
python odm_map_maker/make_mappers_cli.py \
    --config odm_map_maker/configs/<source>_to_odm.yaml
```

Then run both checking tools with your new source schema — see
[Check generated mappers](check-generated-mappers.md). Expect findings on a
first pass; work through them against the workbook.

## 5. Document it

- Add a section to [README.md](../../README.md).
- List the new config file in
  [CLI Configuration Files](../reference/cli-config-files.md#provided-config-files).
- Add validator invocations for it to
  [Mapper Validator](../reference/mapper-validator.md).
