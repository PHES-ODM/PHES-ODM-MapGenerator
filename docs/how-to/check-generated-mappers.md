# Check generated mappers

Run both checking tools after every generation run. They look for different
classes of problem and neither subsumes the other.

Pass the **same two source and target schemas** you generated the mappers with.
Checking v2 mappers against the v3 schema produces a wall of meaningless
errors.

## Check enumeration mappings

`mapper_validator.py` ensures all enumerations have a mapping, that all source
and target enumeration values actually exist in the LinkML schemas, and that
all constants are valid permissible values.

```console
python odm_map_maker/validate_mappers/mapper_validator.py \
    --mappers-dir gen/nwss-reporting-to-v3/mappers \
    --source-schema odm_map_maker/data/nwss_reporting/linkml/nwss_reporting.yaml \
    --target-schema odm_map_maker/data/odm_v3/linkml/odm_v3.yaml \
    --output-dir gen/validate/nwss-reporting-to-v3 \
    --tag nwss-reporting-to-v3
```

Results are written as CSV files under `--output-dir`. `--tag` is prefixed to
the file names, so several runs can share one output directory.

Full option list and output-file descriptions:
[Mapper Validator](../reference/mapper-validator.md).

## Check slot derivation structure

`slot_derivations_checker.py` finds mappings that are syntactically valid but
likely to produce bad data. **One check runs per invocation**, so run it twice
to perform the two types of checks (`multi_to_single` and `free_text_to_enum`):

```console
python odm_map_maker/validate_mappers/slot_derivations_checker.py \
    --checker multi_to_single \
    --mapper-dir gen/nwss-reporting-to-v3/mappers \
    --source-schema odm_map_maker/data/nwss_reporting/linkml/nwss_reporting.yaml \
    --target-schema odm_map_maker/data/odm_v3/linkml/odm_v3.yaml

python odm_map_maker/validate_mappers/slot_derivations_checker.py \
    --checker free_text_to_enum \
    --mapper-dir gen/nwss-reporting-to-v3/mappers \
    --source-schema odm_map_maker/data/nwss_reporting/linkml/nwss_reporting.yaml \
    --target-schema odm_map_maker/data/odm_v3/linkml/odm_v3.yaml
```

This tool logs to the console and writes nothing to disk. **No output means no
findings.**

Full description of each check:
[Slot Derivations Checker](../reference/slot-derivations-checker.md).

## Interpret the results

A finding is not automatically a defect — the downstream
[PHES-ODM-Mapper](https://github.com/Big-Life-Lab/PHES-ODM-Mapper) resolves some
of these cases itself, and some gaps are deliberate. See
[why validator findings are advisory](../explanation/concepts.md#why-validator-findings-are-advisory).

One failure is always real, though: if the slot derivations checker aborts with

```text
ValueError: No such slot <name> as an attribute of <class> ancestors …
```

then either you passed the wrong `--target-schema`, or a workbook row maps to a
slot the target class does not have. The checker stops at the first such slot,
so fix them one at a time. See
[Slot Derivations Checker — Troubleshooting](../reference/slot-derivations-checker.md#troubleshooting).
