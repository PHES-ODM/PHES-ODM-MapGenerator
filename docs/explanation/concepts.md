# Concepts and vocabulary

What this project is for, and the words you need to read the rest of the
documentation. Nothing here is a set of instructions — if you want to run
something, start with the
[tutorial](../tutorials/generate-your-first-mappers.md).

## The problem

Wastewater surveillance data arrives in several different formats. A lab in the
United States reports to [NWSS](https://www.cdc.gov/nwss/reporting.html); a
genomics group might use the [PHA4GE](https://pha4ge.org/) wastewater
specification; older Canadian datasets use ODM v1. All of them need to end up in
the same place: the current [PHES-ODM](https://github.com/PHES-ODM/PHES-ODM)
(v2 or v3).

Converting between these formats is a per-column, per-value problem. NWSS calls
a column `sample_collect_date`; ODM v3 calls it `collectionDate`. NWSS records a
water type as `raw_wastewater`; ODM v3 records it as `rawWW`. Somebody has to
write all of that down.

## The split: experts describe, tooling generates

This repository is where it gets written down, and it splits the job in two:

- **Domain experts** describe the mapping in an **Excel workbook** — one row per
  column mapping, one row per enumeration value mapping. No code.
- **This tool** reads that workbook plus the LinkML schemas for both formats,
  and generates **LinkML Map YAML specifications** — machine-readable files that
  a transformation engine can execute.

That division is the central design decision of the project. The people who know
that `raw_wastewater` means `rawWW` are epidemiologists and lab scientists, not
Python programmers, so the authoring surface is a spreadsheet. Everything the
code does is downstream of that spreadsheet.

The actual data transformation happens in a separate repository,
[PHES-ODM-Mapper](https://github.com/Big-Life-Lab/PHES-ODM-Mapper), which reads
the YAML files this tool produces.

```text
   Excel mapping workbook                 LinkML schemas
   (odm_map_maker/data/                   (odm_map_maker/data/
    mapping_config_files/*.xlsx)           <format>/linkml/*.yaml)
            │                                      │
            └──────────────┬───────────────────────┘
                           ▼
              make_mappers_cli.py            ← this repository
                           │
                           ▼
              LinkML Map YAML mappers
                           │
            ┌──────────────┴───────────────┐
            ▼                              ▼
   mapper_validator.py            PHES-ODM-Mapper repo
   (check correctness)            (transform real data)
```

A consequence worth internalizing early: **most fixes are workbook edits, not
code changes.** If a column maps to the wrong place or an enumeration value is
missing, the defect is almost always a row in a spreadsheet.

## Vocabulary

You will hit these terms in the first five minutes. Learn them now and the rest
of the documentation reads easily.

| Term | Meaning |
| --- | --- |
| **LinkML** | A schema language for describing data models in YAML. Every data format handled here (ODM v1/v2/v3, NWSS, PHA4GE) has a LinkML schema in `odm_map_maker/data/`. |
| **Class** | A LinkML class ≈ a table. `samples`, `measures`, `sites` are ODM classes. |
| **Slot** | A LinkML slot ≈ a column. `sampleID` and `collectionDate` are slots of the `samples` class. |
| **Enumeration (enum)** | A slot whose value must come from a fixed list. ODM v3's `collection` slot is an enum with values like `rawWW` and `pSl`. |
| **Permissible value** | One allowed value of an enumeration. |
| **Source / target** | Source is the format you are converting *from* (e.g. NWSS); target is the format you are converting *to* (e.g. ODM v3). |
| **[LinkML Map](https://github.com/linkml/linkml-map)** | The upstream framework that executes transformations. Its input is a "transformation specification". |
| **Mapper** | One LinkML Map transformation specification YAML file. This tool generates many of them — roughly one per source-class-to-target-class pair. |
| **Class derivation** | The part of a mapper that says "build target class X from source class Y". |
| **Slot derivation** | The part of a class derivation that says how one target slot gets its value — copied from a source slot (`populated_from`) or computed by an expression (`expr`). |
| **Enum derivation** | The part of a mapper that maps source enum values onto target enum values. |
| **Mapping configuration file** | The Excel workbook that a human edits. Described in [Mapping Configuration Files](../reference/mapping-config-files.md). |
| **Wide column** | A source column that must be pivoted into multiple output rows. See [Wide columns](wide-columns.md). |
| **Selector** | A tag in the workbook that includes or excludes a row for a particular run, e.g. `odm=3` or `!deprecated`. |

## Reading a generated mapper

The three derivation types above are exactly what you see in a generated file.
Trimmed from the generated `nwss` → `samples` mapper:

```yaml
class_derivations:
  samples:                             # target class
    name: samples
    populated_from: nwss               # source class
    slot_derivations:
      siteID:                          # target slot…
        name: siteID
        populated_from: site_id        # …copied straight from this source slot
      sampleMatSet:
        name: sampleMatSet
        populated_from: sample_matrix  # copied, then run through an enum derivation
      reporterID:
        name: reporterID
        expr: '"nwss"'                 # computed — here, a constant
  Container:                           # LinkML Map tree root; not configurable
    name: Container
    slot_derivations:
      samples:
        populated_from: nwss
enum_derivations:
  sampleMatSet:
    name: sampleMatSet
    mirror_source: false
    populated_from: vs_sample_matrix   # source enumeration
    permissible_value_derivations:
      rawWW:                           # target value…
        name: rawWW
        populated_from: raw wastewater # …produced from this source value
      pSludge:
        name: pSludge
        populated_from: primary sludge
```

Two things surprise most people the first time:

- Every mapper contains a `Container` class derivation. That is a LinkML Map
  requirement — the tree root that holds all tables — and is not something you
  configure in the workbook.
- `permissible_value_derivations` are keyed by the **target** value, with
  `populated_from` naming the **source** value. That is the opposite reading
  order from the workbook, where `sourceValue` comes before `targetValue`.

## Why there are many mappers instead of one

LinkML Map produces at most one output row per input row. Some mappings need
several output rows per input row — see [Wide columns](wide-columns.md) — so the
generator emits one specification per class derivation and the downstream
consumer concatenates the results. This is why a single NWSS-to-ODM-v3 run
produces dozens of files rather than one.

## Why validator findings are advisory

Two tools inspect generated mappers, and neither one's output is a defect list.

- [Mapper Validator](../reference/mapper-validator.md) reports enumeration
  problems: source values with no mapping, mapped values that exist in neither
  schema, empty derivations.
- [Slot Derivations Checker](../reference/slot-derivations-checker.md) reports
  structural problems: a multi-valued source slot funnelled into a single-valued
  target slot, free text feeding an enumeration.

**Reported issues are not automatically bugs.** The downstream
[PHES-ODM-Mapper](https://github.com/Big-Life-Lab/PHES-ODM-Mapper) supplies
defaults for some unmapped values, and some gaps are deliberate — a source
format simply may not carry the information a target slot wants. Whoever owns
the mapping workbook decides, case by case, whether each report needs a fix.
Treat both tools as reviewers, not gatekeepers.

## Where to go next

- [Architecture](architecture.md) — how the code implements all of this.
- [Mapping Configuration Files](../reference/mapping-config-files.md) — the
  reference you will use most often.
- [Generate your first mappers](../tutorials/generate-your-first-mappers.md) —
  if you would rather see it run.
