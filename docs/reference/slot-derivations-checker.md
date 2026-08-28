# Slot Derivations Checker

[odm_map_maker/validate_mappers/slot_derivations_checker.py](../../odm_map_maker/validate_mappers/slot_derivations_checker.py)
inspects generated mapper YAML files for structural problems in slot
derivations — mappings that are syntactically valid but likely to produce bad
data.

It complements [mapper_validator.py](mapper-validator.md), which checks
enumeration *values*. This script checks the *shape* of a mapping: whether the
source and target slots are compatible in cardinality and type. Run both after
generating mappers.

## Running a check

```console
python odm_map_maker/validate_mappers/slot_derivations_checker.py \
    --checker <checker-name> \
    --mapper-dir <mappers-dir> \
    --source-schema <source-schema.yaml> \
    --target-schema <target-schema.yaml>
```

One check runs per invocation. To run both, invoke the script twice:

```console
# ODM v1 → ODM v3
python odm_map_maker/validate_mappers/slot_derivations_checker.py \
    --checker multi_to_single \
    --mapper-dir gen/odm-v1-to-v3/mappers \
    --source-schema odm_map_maker/data/odm_v1/linkml/odm_v1.yaml \
    --target-schema odm_map_maker/data/odm_v3/linkml/odm_v3.yaml

python odm_map_maker/validate_mappers/slot_derivations_checker.py \
    --checker free_text_to_enum \
    --mapper-dir gen/odm-v1-to-v3/mappers \
    --source-schema odm_map_maker/data/odm_v1/linkml/odm_v1.yaml \
    --target-schema odm_map_maker/data/odm_v3/linkml/odm_v3.yaml
```

## CLI options

**--checker** (Required)  
Which check to run: `multi_to_single` or `free_text_to_enum`. See below.

**--mapper-dir** (Required)  
Directory containing the mapper YAML files. Every `.yaml` file in the directory
is checked. A warning is logged if the directory contains none.

**--source-schema** (Required)  
LinkML schema for the source dataset the mappers read from.

**--target-schema** (Required)  
LinkML schema for the target dataset the mappers write to.

## The checks

### `multi_to_single`

Flags slot derivations where a **multi-valued source slot** feeds a
**single-valued target slot**. The target can then receive a list where only one
value is allowed, which silently corrupts the output.

Reported as:

```text
Found mapping from multi-valued source to single-valued target
(from populated_from block): <sourceClass>.<sourceSlot> -> <targetClass>.<targetSlot>
```

When the derivation uses `expr`, the message says `from expr block` and lists
every source slot the expression references, in brackets.

Fixing one of these usually means choosing between:

- collapsing single-element lists to a scalar (`["Myval"]` → `"Myval"`), which
  is safe; or
- splitting the row into several rows, one per value — which duplicates the
  primary key, so it generally has to happen *before* ID generation in the
  downstream mapper rather than after.

### `free_text_to_enum`

Flags slot derivations where a **free-text source slot** feeds an
**enumeration target slot**. Arbitrary text will rarely match a permissible
value, so the target ends up holding invalid values.

Reported as:

```text
Mapping from free-text to enum: <sourceClass>.<sourceSlot> to <targetClass>.<targetSlot>
```

When the derivation uses `expr`, the expression source is shown in place of the
slot name and the expression itself is appended to the message.

The usual fix is to route the free text to a target slot that accepts free text
— a `notes` field, for example — or to add an explicit enumeration mapping so
that known input strings are translated to valid target values.

A range is treated as free text when it is not an enumeration in the schema. If
a source slot has several ranges, the check reports it when *any* range is
free text while *no* target range is.

## How derivations are analysed

For each mapper file, every slot derivation of every class derivation is
examined. Two cases are handled:

- **`populated_from`** — the named source slot is looked up in the source schema
  and its ranges compared against the target slot's ranges.
- **`expr`** — there is no single named source slot, so the expression is
  scanned for namespaced variable references (`src.some_slot`, plus any
  namespace listed in `ENUM_MAPPED_EXPR_GLOBALS`). Every referenced slot is
  treated as a source of the target slot, and the check applies if any of them
  trips it.

The `Container` tree-root class derivation and any target slot beginning with
`_extra_` are skipped, since neither exists in the target schema.

## Output

Findings are logged to the console — errors and warnings, grouped by file, after
all files have been processed. Nothing is written to disk, and there is no
summary count; **no output means no findings**.

As with [mapper_validator.py](mapper-validator.md), a finding is not
automatically a defect. The downstream
[PHES-ODM-Mapper](https://github.com/Big-Life-Lab/PHES-ODM-Mapper) resolves some
of these cases itself. Review each one against how the mapping is intended to be
consumed.

## Troubleshooting

**`ValueError: No such slot <name> as an attribute of <class> ancestors or as a
slot definition in the schema`**

The checker resolves every target slot against the target class and raises if
the class has no such slot. Two causes:

- the `--target-schema` passed here is not the one the mappers were generated
  against (an ODM v2 schema against v3 mappers, say); or
- a workbook row genuinely maps to a slot that the target class does not have —
  note that a name existing *somewhere* in the schema is not enough, it has to
  be a slot of that specific class.

Confirm the schema first. If it is correct, the offending workbook row needs its
`targetSlot` corrected, or the `_extra_` prefix if the value is meant to be
carried through for downstream processing rather than written to the schema.

Unlike [mapper_validator.py](mapper-validator.md), which collects problems and
reports them all, this script stops at the first unresolvable slot, so fix them
one at a time.
