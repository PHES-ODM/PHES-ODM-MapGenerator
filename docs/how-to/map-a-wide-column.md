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

One row is one output row as long as each row names a different `sourceSlot`.
Rows that name the same one are combined (provided `sourceClass`,
`targetClass`, `targetSlot`, and `wideGroup` are the same); see [step
4](#4-pivot-the-same-column-more-than-once).

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

### What makes an output row

Rows of a wide tab are grouped by `sourceClass` + `sourceSlot` + `targetClass` +
`wideGroup`, and **each group** — not each row — becomes one output row and one
mapper file. So two rows that agree on `sourceClass`, `sourceSlot`, and
`targetClass`, both with `wideGroup` blank, are one group and produce a single
output row, with the `_value` columns read from the first row of the group only.

That default is what enumeration mappings rely on. The rows below are one group,
mapping the source values of `influent_equilibrated` onto ODM values and
producing one `measures` row:

| sourceClass | sourceSlot | sourceValue | targetClass | targetValue | specimen_value | measure_value | value_value |
| --- | --- | --- | --- | --- | --- | --- | --- |
| nwss | influent_equilibrated | yes | measures | true | sit | influEqui | `{{influent_equilibrated}}` |
| nwss | influent_equilibrated | no | measures | false | | | |
| nwss | influent_equilibrated | `<empty>` | measures | nr | | | |

### Splitting a column into two output rows

To get two output rows out of one source column, put the rows in different
groups by giving them different `wideGroup` values. Here one
storage-temperature column produces two `measures` rows, one per protocol stage
the temperature applies to:

| wideGroup | sourceClass | sourceSlot | targetClass | specimen_value | measure_value | unit_value | value_value |
| --- | --- | --- | --- | --- | --- | --- | --- |
| preConc | nwss | collection_storage_temp | measures | sa | preConcTemp | cel | `{{collection_storage_temp}}` |
| preExtract | nwss | collection_storage_temp | measures | sa | preExtractTemp | cel | `{{collection_storage_temp}}` |

The `wideGroup` names are arbitrary labels; they only have to differ. Delete
them and you are back to one output row.

A group can still span several rows, so the two features combine: repeat the
same `wideGroup` on every row of an enumeration mapping, and each distinct
`wideGroup` gets its own enumeration mapping for the same source column.

### Why the bundled workbooks have no wideGroup column

The workbooks in
[mapping_config_files/](../../odm_map_maker/data/mapping_config_files/) do not
define a `wideGroup` column at all, because none of them needs to pivot one
column twice. When the column is absent it is treated as blank on every row,
and therefore equal on every row, and since a wide tab holds one `sourceClass`
and `targetClass` throughout, groups are determined by `sourceSlot` alone — and
each source column is listed once per tab. Where those tabs do repeat a source
column across several rows, it is an enumeration mapping that is meant to
collapse into one output row, or a pair of rows separated by `selectors` (see
below). Either way, a tab's row count is an upper bound on the number of
mappers it produces, not the number itself.

Two consequences are worth knowing about:

- **Rows with a blank `sourceSlot`** would otherwise all land in one group. Each
  such row is instead given its own generated `wideGroup`, so it becomes its own
  output row. Tabs that pivot no source column at all — pha4ge's
  `protocolRelationships_wide`, for example — depend on this.
- **`selectors` is not part of the group key**, but selector filtering happens
  first, so rows that differ only by `selectors` never meet. `wide_measures`
  lists `rec_eff_percent` under both `odm<3` and `odm>=3`, and exactly one
  survives any given run. If you ever need two such variants in the same run,
  they will silently merge into one output row unless you also give them
  different `wideGroup` values.

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
