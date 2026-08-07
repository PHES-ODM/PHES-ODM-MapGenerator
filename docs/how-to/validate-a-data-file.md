# Validate a data file against a schema

Use this to answer "does this CSV actually conform to the schema?" — either for
an incoming source extract or for output the downstream mapper produced.

This is not the same as [checking mappers](check-generated-mappers.md), which
inspects specifications rather than data.

```console
python odm_map_maker/validate.py \
    --schema odm_map_maker/data/odm_v3/linkml/odm_v3.yaml \
    --source-class samples \
    --data-source ../gen/mapped_data/samples.csv
```

One data file holds rows of exactly one class, so `--source-class` is the table
name. The delimiter comes from the file extension: `.csv` is comma-separated,
`.tsv` and `.txt` are tab-separated.

## Read the result

Issues print as:

```text
[ERROR] [<data-file>/<row-index>] <message>
```

The exit code is `1` if any `ERROR`-severity issue was reported and `0`
otherwise, so this drops straight into a shell pipeline or CI job:

```console
python odm_map_maker/validate.py --schema … --source-class samples --data-source … \
    || echo "validation failed"
```

## Handle a flood of "additional property" errors

Validation runs closed: **columns not declared in the schema for that class are
reported as errors.** That is deliberate — it catches misspelled column names —
but it means the script is unsuitable for files that deliberately carry
`_extra_` columns or other out-of-schema annotations. Strip those columns before
validating, or accept that each one produces an error per row.

## Stop early

```console
--max-errors 20     # report at most 20 issues; 0 (the default) reports all
--strict            # raise on the first error instead of collecting them
```

Full option list: [Data Validator](../reference/data-validator.md).
