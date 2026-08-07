# Reference

Complete descriptions of file formats and command-line tools. Look things up
here; these pages describe the machinery and do not explain how to use it.

## Input formats

| Document | Describes |
| --- | --- |
| [Mapping Configuration Files](mapping-config-files.md) | Every column of the `maps`, `wide`, and `enums` tabs in the Excel mapping workbooks |
| [CLI Configuration Files](cli-config-files.md) | The YAML `--config` file format for `make_mappers_cli.py`, path resolution, and slot format operations |

## Tools

| Document | Describes |
| --- | --- |
| [Mapper Validator](mapper-validator.md) | `mapper_validator.py` — enumeration completeness and consistency checks, and the CSV reports it writes |
| [Slot Derivations Checker](slot-derivations-checker.md) | `slot_derivations_checker.py` — the `multi_to_single` and `free_text_to_enum` structural checks |
| [ODM v1 to vx (legacy)](make-v1-to-vx.md) | `make_v1_to_vx.py` — the older data-dictionary-driven generator, superseded by `make_mappers_cli.py` |

The generator's own options are documented in its help text and in
[README.md](../../README.md#general-cli):

```console
python odm_map_maker/make_mappers_cli.py --help
```
