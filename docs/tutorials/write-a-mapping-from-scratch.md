# Write a mapping from scratch

In [the first tutorial](generate-your-first-mappers.md) you ran a mapping
somebody else had written. Here you will write one yourself — four rows, mapping
NWSS to the ODM v3 `samples` table — and watch each row turn into a piece of the
generated mapper.

You will not need Excel. Real mappings live in Excel workbooks, but the
generator also accepts plain CSV, which is easier to type and easier to see.

Budget about 20 minutes. You need a working install from the first tutorial.

## Step 1 — Create the output directory

```console
mkdir -p ../gen/my-first-mapping/configs
```

The generator writes into `configs/` and `mappers/` under the output directory.
It creates `mappers/` for you, but when you supply your own CSV rather than an
Excel workbook it expects `configs/` to already exist — hence the `mkdir`.

## Step 2 — Write four mapping rows

Create `../gen/my-first-mapping/my_maps.csv` with exactly this content:

```csv
sourceClass,sourceSlot,sourceValue,targetClass,targetSlot,targetValue,targetExpr
nwss,site_id,,samples,siteID,{{site_id}},
nwss,sample_id,,samples,sampleID,{{sample_id}},
nwss,sample_collect_date,,samples,collDate,{{sample_collect_date}},
nwss,,,samples,notes,,"""my first mapping"""
```

Read it a row at a time:

- Rows 1–3 are **direct copies**. `sourceClass`/`sourceSlot` name where the
  value comes from, `targetClass`/`targetSlot` name where it goes, and
  `targetValue` is the template `{{sourceSlot}}` — the literal instruction "put
  the source slot's value here".
- Row 4 is a **computed value**. It has no `sourceSlot`, because nothing is read
  from the source. Instead `targetExpr` holds an expression — here the constant
  string `"my first mapping"`. The tripled quotes are CSV escaping: the cell's
  actual content is `"my first mapping"`, double quotes included, because the
  expression language needs them to know this is a string rather than a slot
  name.

These are the columns of a `maps` tab. There are more of them, all described in
[Mapping Configuration Files](../reference/mapping-config-files.md#maps-tabs).

## Step 3 — Generate the mapper

Point the generator at your CSV instead of a config file, naming both schemas
explicitly:

```console
python odm_map_maker/make_mappers_cli.py \
    --maps-files ../gen/my-first-mapping/my_maps.csv \
    --source-schema odm_map_maker/data/nwss_reporting/linkml/nwss_reporting.yaml \
    --target-schema odm_map_maker/data/odm_v3/linkml/odm_v3.yaml \
    --output-dir ../gen/my-first-mapping
```

The last line of the output tells you what was written:

```text
Saving mapper spec for 'nwss' to 'samples': …/mappers/mapper-0000000000-nwss-samples.yaml
Finished!
```

One source class mapped to one target class, so you got exactly one file.

## Step 4 — Compare your rows with the result

```console
cat ../gen/my-first-mapping/mappers/mapper-0000000000-nwss-samples.yaml
```

```yaml
class_derivations:
  samples:
    name: samples
    populated_from: nwss
    slot_derivations:
      siteID:
        name: siteID
        populated_from: site_id
      sampleID:
        name: sampleID
        populated_from: sample_id
      collDate:
        name: collDate
        populated_from: sample_collect_date
      notes:
        name: notes
        expr: '"my first mapping"'
  Container:
    name: Container
    slot_derivations:
      samples:
        populated_from: nwss
enum_derivations: {}
```

Line the two up:

| Your CSV | The mapper |
| --- | --- |
| `sourceClass` = `nwss`, `targetClass` = `samples` | one `class_derivations:` entry, keyed by the target class, with `populated_from: nwss` |
| each row's `targetSlot` | one entry under `slot_derivations:` |
| `targetValue` = `{{site_id}}` | `populated_from: site_id` |
| `targetExpr` = `"my first mapping"` | `expr: '"my first mapping"'` |
| *(nothing you wrote)* | the `Container` class derivation |
| *(no enum rows)* | `enum_derivations: {}` |

Every line of YAML traces back to something you wrote, except `Container` —
which LinkML Map requires as the tree root of every specification, and which the
generator therefore adds unconditionally.

## Step 5 — Break something on purpose

Add a fifth row naming a target slot that does not exist in `samples`:

```csv
nwss,zipcode,,samples,notASlot,{{zipcode}},
```

Re-run the command from step 3. The generator writes the mapper anyway — it does
not verify target slots against the schema. That is the job of the checking
tools you ran in the first tutorial:

```console
python odm_map_maker/validate_mappers/slot_derivations_checker.py \
    --checker multi_to_single \
    --mapper-dir ../gen/my-first-mapping/mappers \
    --source-schema odm_map_maker/data/nwss_reporting/linkml/nwss_reporting.yaml \
    --target-schema odm_map_maker/data/odm_v3/linkml/odm_v3.yaml
```

This raises `ValueError: No such slot notASlot …`, because the checker resolves
every target slot against the target class. **Generation succeeding does not
mean the mapping is correct.** Remove the bad row before moving on.

## What you did

You wrote a mapping by hand, generated a specification from it, traced every
generated line back to a row you wrote, and saw what the generator does not
check for you.

Real mappings differ from this one in scale, not in kind: hundreds of rows
across several Excel tabs, plus `wide` tabs for pivoted columns and `enums` tabs
for value translation.

## Next steps

- [Fix an incorrect mapping](../how-to/fix-a-mapping.md) — the same edit against
  a real workbook.
- [Mapping Configuration Files](../reference/mapping-config-files.md) — every
  column of every tab.
- [Concepts and vocabulary](../explanation/concepts.md) — why the authoring
  surface is a spreadsheet at all.
