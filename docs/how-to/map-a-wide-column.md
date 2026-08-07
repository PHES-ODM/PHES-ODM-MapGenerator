# Map a wide column into its own output row

Use this when one source column has to become its own row in the target table —
typically a measurement column feeding the ODM `measures` table. For why this is
necessary at all, see [Wide columns](../explanation/wide-columns.md).

Wide columns go in a **`wide` tab**, not a `maps` tab.

## 1. Pick the right wide tab

A good convention is one `wide` tab per target class — `wide_measures`,
`wide_qualityReports`, and so on. The `_value` columns you add apply to every
row in the tab, and a target slot that exists on `measures` may not exist on
`samples`, so mixing target classes in one tab causes trouble.

Every tab you use must be listed under `excel-wide-sheets` in the config file.

## 2. Add one row per output row you want

The row identifies the source column to pivot and sets the target slots for the
row it produces:

| sourceClass | sourceSlot | targetClass | unit_value | measure_value | value_value |
| --- | --- | --- | --- | --- | --- |
| nwss | sewage_travel_time | measures | hours | sewTrTi | `{{sewage_travel_time}}` |

- **`sourceSlot`** — the source column to pivot.
- **`{targetSlot}_value`** columns — any column ending in `_value` sets the
  target slot named by the rest of the column name. The cell holds either a
  constant (`hours`) or `{{slotName}}` to copy from a source slot. A blank cell
  is ignored, so it will not clobber a value the `maps` tab set; to force a
  blank, write `<empty>`.
- **`{targetSlot}_expr`** columns — the same, but the cell holds LinkML
  expression code instead of a value.

Values here take precedence over anything the `maps` tab set for the same slot.

## 3. Handle slots that only one row needs

Do not add a `_value` column to the whole sheet for the sake of one row —
every other row would then set that target slot to blank. Put it in that row's
**`wideOtherSlots`** cell instead, as a JSON object:

```json
{ "notes_value": "{{pretreatment_specify}}" }
```

`wideOtherSlots` wins over both the `maps` tab and the sheet's `_value`/`_expr`
columns for that row.

## 4. Pivot the same column more than once

Give the rows different **`wideGroup`** values. Rows sharing a `wideGroup` — for
one `sourceClass`, `sourceSlot`, and `targetClass` — form a single wide-to-long
specification; a different `wideGroup` is a separate output row. This is also
how you apply different enumeration mappings to the same source column.

## 5. Regenerate and confirm

```console
python odm_map_maker/make_mappers_cli.py \
    --config odm_map_maker/configs/nwss_to_odm.yaml \
    --output-dir ../gen/nwss-reporting-to-v3

ls ../gen/nwss-reporting-to-v3/mappers/ | grep sewage_travel_time
```

Each wide row gets its own mapper file, with the source column named in the
bracketed part of the file name. If no file appears, see
[Find out why a row was ignored](find-out-why-a-row-was-ignored.md).

## Related

- [Mapping Configuration Files — Wide tabs](../reference/mapping-config-files.md#wide-tabs)
  — every column, in full.
- [Wide columns](../explanation/wide-columns.md) — why one mapper per wide
  column.
