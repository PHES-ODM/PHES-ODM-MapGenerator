# CLI Configuration Files for make_mappers_cli.py

`make_mappers_cli.py` supports a `--config` option that loads arguments from a
YAML file. This lets you run the CLI with a single argument instead of repeating
a long list of flags, and makes it easy to store reusable argument sets in
version control.

## Basic usage

```console
python odm_map_maker/make_mappers_cli.py --config odm_map_maker/configs/odm_v1_to_odm.yaml
```

Any argument that can be passed on the command line can also be specified in the
config file. Arguments supplied on the command line **always override** the
values in the config file, so you can use the config file as a set of defaults
while still customising individual options at run time.

## File format

Config files are YAML. Keys are the long CLI option names, written with either
hyphens or underscores:

```yaml
source-schema: ../data/nwss_reporting/linkml/nwss_reporting.yaml
target-schema: ../data/odm_v3/linkml/odm_v3.yaml
output-dir: ../../../gen/nwss-reporting-to-v3
```

Options that accept multiple values (such as `--excel-maps-sheets`) are written
as YAML lists:

```yaml
excel-maps-sheets:
  - maps

excel-wide-sheets:
  - wide_measures
  - wide_protocolRelationships

selectors:
  - odm=3
```

When a list option is provided on the command line, the **entire** list from
the config file is replaced; the two lists are not merged.

## Path resolution

**Paths in the config file are resolved relative to the config file's
location.** This means you can place a config file anywhere in the project tree
and use relative paths without worrying about the working directory from which
the CLI is invoked.

For example, a config file at `odm_map_maker/configs/nwss_to_odm.yaml` would
use paths like:

```yaml
source-schema: ../data/nwss_reporting/linkml/nwss_reporting.yaml
output-dir: ../../../gen/nwss-reporting-to-v3
```

The path `../data/nwss_reporting/linkml/nwss_reporting.yaml` resolves from
`odm_map_maker/configs/` to `odm_map_maker/data/nwss_reporting/linkml/nwss_reporting.yaml`.
The path `../../../gen/nwss-reporting-to-v3` resolves up three levels (past
`configs/`, past `odm_map_maker/`, past the project root) to place output in
the sibling `gen/` directory.

Path options affected by this rule: `--source-schema`, `--target-schema`,
`--mapping-excel-file`, `--output-dir`, `--maps-files`, `--wide-files`,
`--enums-files`.

**Paths supplied directly on the command line are not affected** — they remain
relative to the working directory as usual.

## Provided config files

Ready-to-use config files are in `odm_map_maker/configs/`. Each file defaults
to mapping to ODM v3; pass `--target-schema`, `--output-dir`, and `--selectors`
on the command line to map to v2 instead.

### ODM v1 to ODM (`odm_v1_to_odm.yaml`)

Maps ODM v1 tables to ODM v3 (default) or v2.

```console
# Map to ODM v3 (default)
python odm_map_maker/make_mappers_cli.py \
    --config odm_map_maker/configs/odm_v1_to_odm.yaml

# Map to ODM v2
python odm_map_maker/make_mappers_cli.py \
    --config odm_map_maker/configs/odm_v1_to_odm.yaml \
    --target-schema odm_map_maker/data/odm_v2/linkml/odm_v2.yaml \
    --output-dir ../gen/odm-v1-to-v2 \
    --selectors odm=2
```

### NWSS to ODM (`nwss_to_odm.yaml`)

Maps NWSS reporting data to ODM v3 (default) or v2. To use a different NWSS
dictionary type (`public_concentration`, `public_metric`), override
`--source-schema` on the command line.

```console
# Map NWSS reporting to ODM v3 (default)
python odm_map_maker/make_mappers_cli.py \
    --config odm_map_maker/configs/nwss_to_odm.yaml

# Map NWSS reporting to ODM v2
python odm_map_maker/make_mappers_cli.py \
    --config odm_map_maker/configs/nwss_to_odm.yaml \
    --target-schema odm_map_maker/data/odm_v2/linkml/odm_v2.yaml \
    --output-dir ../gen/nwss-reporting-to-v2 \
    --selectors odm=2

# Map a different NWSS dictionary type to ODM v3
python odm_map_maker/make_mappers_cli.py \
    --config odm_map_maker/configs/nwss_to_odm.yaml \
    --source-schema odm_map_maker/data/nwss_public_concentration/linkml/nwss_public_concentration.yaml \
    --output-dir ../gen/nwss-public_concentration-to-v3
```

### PHA4GE to ODM (`pha4ge_to_odm.yaml`)

Maps PHA4GE wastewater data to ODM v3 (default) or v2.

```console
# Map PHA4GE to ODM v3 (default)
python odm_map_maker/make_mappers_cli.py \
    --config odm_map_maker/configs/pha4ge_to_odm.yaml

# Map PHA4GE to ODM v2
python odm_map_maker/make_mappers_cli.py \
    --config odm_map_maker/configs/pha4ge_to_odm.yaml \
    --target-schema odm_map_maker/data/odm_v2/linkml/odm_v2.yaml \
    --output-dir ../gen/pha4ge-to-v2 \
    --selectors odm=2
```

## Writing your own config file

Copy one of the provided files and adjust the values. The supported keys mirror
the CLI options exactly:

| Key | CLI option | Type |
| --- | --- | --- |
| `source-schema` | `--source-schema` | path |
| `target-schema` | `--target-schema` | path |
| `mapping-excel-file` | `--mapping-excel-file` | path |
| `output-dir` | `--output-dir` | path |
| `maps-files` | `--maps-files` | list of paths |
| `wide-files` | `--wide-files` | list of paths |
| `enums-files` | `--enums-files` | list of paths |
| `excel-maps-sheets` | `--excel-maps-sheets` | list of strings |
| `excel-wide-sheets` | `--excel-wide-sheets` | list of strings |
| `excel-enums-sheets` | `--excel-enums-sheets` | list of strings |
| `selectors` | `--selectors` | list of strings |
| `source-slot-format-operations` | `--source-slot-format-operations` | list of strings |
| `target-slot-format-operations` | `--target-slot-format-operations` | list of strings |
| `source-match-ontology-id-regex` | `--source-match-ontology-id-regex` | string |
| `target-match-ontology-id-regex` | `--target-match-ontology-id-regex` | string |

Run `python odm_map_maker/make_mappers_cli.py --help` for descriptions of each
option.

## Slot format operations

The `source-slot-format-operations` and `target-slot-format-operations` keys
accept a YAML list of string transformation operations. These are applied in
order to every slot name read from the mapping configuration file, allowing you
to normalize names that differ in casing or punctuation from the LinkML schema.

Available operations:

| Operation | Effect |
| --- | --- |
| `lowercase` | Convert to lower case |
| `uppercase` | Convert to upper case |
| `alpha_numeric_underscore` | Replace every non-alphanumeric character with `_` |
| `single_underscores` | Collapse consecutive underscores into one (`__` → `_`) |
| `trim_trailing_underscores` | Remove trailing underscores |
| `trim_whitespace` | Remove leading and trailing whitespace |
| `remove_special` | Remove all non-alphanumeric, non-space characters |
| `{ remove_chars: "xyz" }` | Remove each listed character (removes `x`, `y`, `z`) |

The `remove_chars` operation is specified as a YAML mapping rather than a plain
string. Wrap it in quotes so that it is parsed correctly:

```yaml
source-slot-format-operations:
  - lowercase
  - "{ remove_chars: '-'}"
  - alpha_numeric_underscore
  - single_underscores
  - trim_trailing_underscores
```

Slot names that begin with the `_extra_` prefix (special extra slots — see
[Mapping Config Files](mapping-config-files.md#extra-columns)) are never
transformed by these operations.
