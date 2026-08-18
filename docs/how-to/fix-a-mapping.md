# Fix an incorrect column or value mapping

A column lands in the wrong place, or an enumerated value comes through
untranslated. Almost always this is a workbook edit, not a code change.

## Fix a column mapping

1. Open the workbook for that mapping in
   `odm_map_maker/data/mapping_config_files/` — for example
   `nwss_to_odm_v2_mapping.xlsx`.
2. Go to the `maps` tab and find the row by searching the `sourceSlot` column
   for the source column name.
3. Correct `targetClass` and/or `targetSlot`. If the value should be copied
   straight across, `targetValue` must be `{{sourceSlot}}` with the actual
   source slot name inside the braces — a stale name there is a common cause of
   an empty output column.
4. Regenerate and re-check — see
   [Check generated mappers](check-generated-mappers.md).

Column-by-column meanings are in
[Mapping Configuration Files — Maps tabs](../reference/mapping-config-files.md#maps-tabs).

## Fix an enumerated value mapping

Where the fix goes depends on how many slots use the enumeration:

| Situation | Tab | What to write |
| --- | --- | --- |
| One slot uses this enumeration | `maps` | one row per value pair, with `sourceValue` and `targetValue` filled in and `targetSlot` naming the slot |
| Several slots share the enumeration, or you want to name it directly | `enums` | one row per value pair, identifying the enumeration by `sourceEnum`/`targetEnum` |

In both cases `sourceValue` is the value as it appears in the **incoming data**
and `targetValue` is the permissible value in the **target schema**. Both must
match their schema exactly, including case.

See
[Mapping Configuration Files — Enums tabs](../reference/mapping-config-files.md#enums-tabs).

## If the row you edited seems to be ignored

See [Find out why a row was ignored](find-out-why-a-row-was-ignored.md). Three
separate mechanisms drop rows silently.

## Verify the fix

Regenerate, then diff the mappers against the previous output:

```console
python odm_map_maker/make_mappers_cli.py \
    --config odm_map_maker/configs/nwss_to_odm.yaml \
    --output-dir ../gen/nwss-reporting-to-v3

diff -r ../gen/nwss-reporting-to-v3-before/mappers \
        ../gen/nwss-reporting-to-v3/mappers
```

The diff should show your change and nothing else.
