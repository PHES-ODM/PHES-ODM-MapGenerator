# Find out why a workbook row was ignored

You edited a row, regenerated, and nothing changed in the output. Three
mechanisms drop rows silently — check them in this order.

## 1. Look at the extracted CSV first

Every run writes each Excel sheet verbatim to `<output-dir>/configs/` as
`maps0.csv`, `wide0.csv`, `enums0.csv`, and so on, **before** any filtering.

```console
grep -n 'my_source_column' ../gen/nwss-reporting-to-v3/configs/maps0.csv
```

- **Not there** → the tool did not read the sheet you edited. Check that the
  sheet name appears in `excel-maps-sheets` / `excel-wide-sheets` /
  `excel-enums-sheets` in the config file, and that you saved the workbook.
- **There** → the row was read and then filtered out. Continue below.

## 2. Selectors

If the row's `selectors` cell does not match the `--selectors` passed on the
command line, the row is dropped. A row tagged `odm>=3.0` disappears from a run
invoked with `--selectors odm=2`, and vice versa.

Check the row's `selectors` cell against the `selectors:` list in your config
file, plus anything you passed on the command line — command-line values replace
the config file's list entirely, they do not merge.

Syntax reference: [selectors](../reference/mapping-config-files.md#selectors).

## 3. The `Complete` column

If a sheet has a `Complete` column, **only rows where it equals `1` OR `TRUE`
are processed.** A new row added to such a sheet is ignored until you set it.

Reference: [Complete](../reference/mapping-config-files.md#complete).

## 4. Empty rows

Completely blank rows are always skipped, and a row whose key cells are blank
may be treated as blank even if some other cell is filled in. Whitespace is
stripped before this test, so a cell holding only spaces counts as empty.

## Still nothing?

If the row survives all four, it is being read but is not producing what you
expect. Look at the generated mapper directly:

```console
grep -rn 'targetSlotName' ../gen/nwss-reporting-to-v3/mappers/
```

If the target slot is present but its `populated_from` is missing or wrong, the
problem is in `targetValue` — the `{{sourceSlot}}` template must contain the
source slot's real name. If the slot name in the mapper does not look like what
you typed, slot format operations rewrote it; see
[Normalize slot names](normalize-slot-names.md).
