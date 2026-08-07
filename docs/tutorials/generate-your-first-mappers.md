# Generate your first mappers

In this tutorial you will install the project, generate a complete set of
NWSS → ODM v3 mapper files, look inside one of them, and run the two checking
tools over the result. You do not need to know anything about LinkML or the ODM
beforehand, and you will not edit any files.

Budget about 30 minutes.

By the end you will have:

- a working development environment;
- a directory of generated LinkML Map specifications;
- validation reports for those specifications.

## Before you start

You need **Python 3.10 or newer** and **git**. Check your Python version:

```console
python3 --version
```

If it prints 3.10 or higher, you are ready.

## Step 1 — Install the project

Clone the repository and create a virtual environment:

```console
git clone git@github.com:PHES-ODM/PHES-ODM-MapGenerator.git
cd PHES-ODM-MapGenerator
python3 -m venv .env
source .env/bin/activate          # Windows: .env\Scripts\activate
```

Install the dependencies and the package itself:

```console
pip install -r requirements.txt
pip install -e . --no-deps
```

The second command makes the `odm_map_maker` package importable from any working
directory.

Confirm the install by asking the generator for its help text:

```console
python odm_map_maker/make_mappers_cli.py --help
```

You should see a list of options beginning with `--config`. If instead you see a
`ModuleNotFoundError`, the virtual environment is probably not active — re-run
the `source` line above.

## Step 2 — Generate the NWSS mappers

Three ready-made configurations ship with the repository, each mapping one
source format to ODM v3 by default. You will use the NWSS one:

```console
python odm_map_maker/make_mappers_cli.py \
    --config odm_map_maker/configs/nwss_to_odm.yaml \
    --output-dir ../gen/nwss-reporting-to-v3
```

The `--config` file supplies the source schema, target schema, Excel workbook,
sheet names, selectors, and slot-name formatting rules. Anything you pass on the
command line overrides it — here you set `--output-dir` explicitly, though the
config file already has a default.

Output goes to `../gen/`, a sibling of the repository, so nothing you generate
ends up inside your clone.

> **Point `--output-dir` at a scratch location.** Both output subdirectories are
> **cleared of existing CSV, TSV, and YAML files** at the start of every run.

## Step 3 — Look at what you generated

```console
ls ../gen/nwss-reporting-to-v3
```

You will find two directories:

```text
../gen/nwss-reporting-to-v3/
├── configs/          # each Excel sheet, extracted verbatim to CSV
│   ├── maps0.csv
│   ├── wide0.csv … wide3.csv
│   └── enums0.csv
└── mappers/          # the actual output: one LinkML Map spec per mapping
    ├── mapper-0000000000-nwss-measures_000,0000__.yaml
    ├── …
    └── mapper-0000000068-nwss-sites.yaml
```

`configs/` is an intermediate artifact — it exists so you can see exactly what
the tool read out of the Excel workbook. `mappers/` is the deliverable.

Open the `sites` mapper, which is one of the simpler ones:

```console
cat ../gen/nwss-reporting-to-v3/mappers/mapper*-nwss-sites.yaml
```

Three things are worth finding in what it prints:

1. A `class_derivations:` block naming a **target class** (`sites`), with
   `populated_from:` naming the **source class** (`nwss`).
2. Inside it, `slot_derivations:` — one entry per target column. Most say
   `populated_from: <source column>`; a few say `expr:` and compute a value.
3. A second class derivation called `Container`. Every mapper has one; it is the
   LinkML Map tree root and is not something anyone configures.

If a mapper maps enumerated values, it also carries an `enum_derivations:`
block. [Concepts and vocabulary](../explanation/concepts.md#reading-a-generated-mapper)
walks through an annotated example in full.

## Step 4 — Check the mappers

Two tools inspect generated mappers. Run both.

The **mapper validator** finds enumeration problems — source values with no
mapping, mapped values that do not exist in either schema, empty derivations,
invalid constants:

```console
python odm_map_maker/validate_mappers/mapper_validator.py \
    --mappers-dir ../gen/nwss-reporting-to-v3/mappers \
    --source-schema odm_map_maker/data/nwss_reporting/linkml/nwss_reporting.yaml \
    --target-schema odm_map_maker/data/odm_v3/linkml/odm_v3.yaml \
    --output-dir ../gen/validate/nwss-reporting-to-v3 \
    --tag nwss-reporting-to-v3
```

Results are written as CSV files under `../gen/validate/nwss-reporting-to-v3`.
Open one and skim it.

The **slot derivations checker** finds structural problems the validator does
not look for, such as a multi-valued source slot being funnelled into a
single-valued target slot:

```console
python odm_map_maker/validate_mappers/slot_derivations_checker.py \
    --checker multi_to_single \
    --mapper-dir ../gen/nwss-reporting-to-v3/mappers \
    --source-schema odm_map_maker/data/nwss_reporting/linkml/nwss_reporting.yaml \
    --target-schema odm_map_maker/data/odm_v3/linkml/odm_v3.yaml
```

This one logs to the console and writes nothing; no output means no findings.

**Both tools will report something, and that is expected.** Reported issues are
not automatically bugs — see
[why validator findings are advisory](../explanation/concepts.md#why-validator-findings-are-advisory).
For now, note that the reports exist and move on.

## What you did

You installed the project, ran the generator against a shipped configuration,
inspected a generated LinkML Map specification, and produced validation reports
for the whole set. That is the entire job of this repository: everything else is
a variation on these four steps.

## Next steps

- [Write a mapping from scratch](write-a-mapping-from-scratch.md) — the second
  tutorial, where you author the rows yourself.
- [Concepts and vocabulary](../explanation/concepts.md) — the terms behind what
  you just ran.
- [How-to guides](../how-to/index.md) — recipes for real tasks.
