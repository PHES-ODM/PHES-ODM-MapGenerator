# Data Validator

[odm_map_maker/validate.py](../../odm_map_maker/validate.py) validates a CSV or TSV
**data file** against a LinkML schema.

This is different from the other validators in this repository. The
[Mapper Validator](mapper-validator.md) and
[Slot Derivations Checker](slot-derivations-checker.md) inspect *mapper
specifications*; this script inspects *data*. Use it to answer questions like
"does this NWSS extract actually conform to the NWSS schema?" or "did the
downstream mapper produce valid ODM v3 output?"

## Running the validator

```console
python odm_map_maker/validate.py \
    --schema <schema.yaml> \
    --source-class <class-name> \
    --data-source <data-file.csv>
```

For example, to check an ODM v3 `samples` table:

```console
python odm_map_maker/validate.py \
    --schema odm_map_maker/data/odm_v3/linkml/odm_v3.yaml \
    --source-class samples \
    --data-source ../gen/mapped_data/samples.csv
```

## CLI options

**--schema** (Required)  
Path to the LinkML schema the data is expected to conform to.

**--source-class** (Required)  
The class in the schema that the data file represents. One data file holds rows
of exactly one class — for ODM, this is the table name (`samples`, `measures`,
`sites`, …).

**--data-source** (Required)  
The data file to validate. The delimiter is chosen from the file extension:
`.csv` is comma-separated; `.tsv` and `.txt` are tab-separated. Any other
extension raises an error.

**--max-errors** (Optional, default: `0`)  
Stop after reporting this many issues. `0` reports every issue found.

**--strict / --no-strict** (Optional, default: `--no-strict`)  
With `--strict`, validation raises on the first error instead of collecting all
of them.

## Output and exit code

Every issue is printed to standard output as:

```text
[ERROR] [<data-file>/<row-index>] <message>
```

If nothing is found, the script logs `No issues found`. The exit code is `1` if
any issue of severity `ERROR` was reported, and `0` otherwise, so the script can
be used directly in a shell pipeline or CI job.

## How values are typed

CSV and TSV files carry no type information — every cell arrives as a string. If
the raw strings were handed to the validator as-is, every numeric slot would
fail. The loader therefore consults the schema before validating and casts each
cell according to the range of its slot:

- range is `string` or an enumeration → the value stays a string;
- otherwise → the value is parsed as an integer or float where possible, and
  left unchanged where not.

Empty cells are dropped from the row rather than being validated as empty
strings, and completely empty rows are skipped.

## Validation strictness

The validator runs the LinkML
`JsonschemaValidationPlugin` with `closed=True`. "Closed" means **columns not
declared in the schema for that class are reported as errors**, not ignored. A
data file that carries extra bookkeeping columns will therefore produce one
error per extra column. This is intentional — it catches typos in column
names — but it does mean the script is not suitable for validating files that
deliberately carry `_extra_` columns or other out-of-schema annotations.
