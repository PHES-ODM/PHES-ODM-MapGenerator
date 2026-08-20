# Normalize slot names that don't match the schema

Workbook authors write column names the way they appear in a data dictionary;
schemas spell them differently — `Sample Collect Date` versus
`sample_collect_date`. Rather than editing hundreds of cells, tell the generator
how to normalize names before it looks them up.

## Apply format operations

Set `source-slot-format-operations` and `target-slot-format-operations` in the
config file. Operations run **in order**, on every slot name read from the
workbook:

```yaml
source-slot-format-operations:
  - lowercase
  - remove_chars: '-'
  - alpha_numeric_underscore
  - single_underscores
  - trim_trailing_underscores
```

The available operations are listed in
[CLI Configuration Files — Slot format operations](../reference/cli-config-files.md#slot-format-operations).

The shipped NWSS config uses a minimal set, which is a good starting point:

```yaml
source-slot-format-operations:
  - alpha_numeric_underscore
  - single_underscores
  - trim_trailing_underscores
```

## Confirm the result

Regenerate, then look at what the mapper actually contains:

```console
grep -n 'populated_from' ../gen/nwss-reporting-to-v3/mappers/mapper*-nwss-samples.yaml
```

Read the lines under `slot_derivations` — those are source slot names, and they
are post-normalization. `populated_from` also appears under `enum_derivations`
and `permissible_value_derivations`, holding source enumeration names and
source enumeration values. Slot format operations never touch those, so ignore
them here.

If a slot name still does not match the schema, add or reorder an operation —
order matters, since `alpha_numeric_underscore` turns punctuation into
underscores that `single_underscores` then collapses.

## What is never transformed

Slot names beginning with `_extra_` pass through untouched. They intentionally
do not exist in the target schema — see
[Extra Columns](../reference/mapping-config-files.md#extra-columns).

## When normalization is the wrong tool

Format operations apply uniformly. If a handful of names differ in ways no rule
captures — a genuine rename rather than a casing difference — fix those cells in
the workbook instead.
