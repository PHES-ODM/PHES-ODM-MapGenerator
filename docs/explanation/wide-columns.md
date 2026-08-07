# Wide columns and the one-row-per-row limit

Why some mappings need several output rows per input row, why that forces the
generator to emit multiple mapper files, and what the result looks like.

To actually configure one, see
[Map a wide column](../how-to/map-a-wide-column.md); for every column of the
`wide` tab, see
[Mapping Configuration Files — Wide tabs](../reference/mapping-config-files.md#wide-tabs).

## The shape of the problem

There are often cases where we require a wide-to-long mapping. In wide-to-long
mappings, a single input row can result in multiple output rows. An example of
this, using NWSS to ODM v2 mapping, is shown below. The following table is a
shortened extract from an NWSS dataset:

| major_lab_method | test_result_date | capacity_mgd | collection_storage_temp | collection_storage_time |
| ---------------- | ---------------- | ------------ | ----------------------- | ----------------------- |
| 1                | 2024-06-01       | 2.3          | 4                       | 12:25:00                |

The columns `capacity_mgd`, `collection_storage_temp`, and
`collection_storage_time` are treated as wide columns. Because there are three
wide columns, the mapping of the above table will result in an output table with
three rows, one for each wide column. The actual mapping results in the
following `measures` table in ODM v2:

| protocolID | aDateEnd   | specimen | measure | unit  | aggregation | value    |
| ---------- | ---------- | -------- | ------- | ----- | ----------- | -------- |
| 1          | 2024-06-01 | si       | wwtpCap | mgd   | sin         | 2.3      |
| 1          | 2024-06-01 | sa       | sTemp   | cel   | sin         | 4        |
| 1          | 2024-06-01 | sa       | stoTim  | hours | sin         | 12:25:00 |

In the above example, `major_lab_method` gets mapped unchanged to all rows as
`protocolID` and `test_result_date` to `aDateEnd`. The first row is the
wide-to-long mapping (or pivoting/melting) of `capacity_mgd`, the second of
`collection_storage_temp`, and the third of `collection_storage_time`. The
values under the new columns `specimen`, `measure`, `unit`, and `aggregation`
are predefined constants in the mapping, whereas the value in the `value` column
is copied from each of the wide columns.

This shape is not an oddity of NWSS. It is what happens whenever a source format
stores measurements as *columns* and the target format stores them as *rows* —
which is exactly the difference between a reporting spreadsheet and the ODM
`measures` table.

## Why one mapper file per wide column

With the LinkML Mapper, we can only have one output row for each input row. This
makes it difficult to handle wide columns. In order to deal with this, we create
multiple Mapping specs, one for each wide column. Running each mapping on the
same table can then result in multiple output rows (one per Mapping spec) for a
single input row. We then concatenate the outputs into a single output table.

The concatenation is the downstream consumer's job — this repository's output is
the set of specs, not a merged table.

## How to recognize a wide mapper file

The generated Mapping YAML specs that handle the wide columns have file names
that contain which wide column the YAML file is for. For example, the Mapping
file that handles the `collection_storage_temp` wide column in NWSS (that gets
mapped to the measures table in ODM v2) might be named
`mapper-nwss-measures[000,0001=collection_storage_temp].yaml`.

The same bracket decoration appears in the class derivation name inside the
file, which is how a wide mapper can be told apart from an ordinary one by
reading the mapper alone.

## See also

- [Map a wide column](../how-to/map-a-wide-column.md) — the recipe.
- [Mapping Configuration Files — Wide tabs](../reference/mapping-config-files.md#wide-tabs)
  — every column of the `wide` tab.
- [nwss_to_odm_v2_mapping.xlsx](../../odm_map_maker/data/mapping_config_files/nwss_to_odm_v2_mapping.xlsx)
  — a worked example workbook.
