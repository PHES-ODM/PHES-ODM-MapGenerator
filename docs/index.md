# PHES-ODM Map Generator documentation

The PHES-ODM Map Generator turns human-editable Excel mapping workbooks into
[LinkML Map](https://github.com/linkml/linkml-map) YAML specifications that
describe, in part, how to convert data from one wastewater-surveillance format
(ODM v1, NWSS, PHA4GE) into another (ODM v2 or v3). These YAML files are only
part of the process for mapping between formats; data must first be
preprocessed, mapped, and then postprocessed for the full mapping to be
complete. The outputs of the PHES-ODM Map Generator are used by the [PHES-ODM
Mapper](https://github.com/PHES-ODM/PHES-ODM-Mapper), which also implements all
other necessary steps for mapping.

## Generate the mappers

After [installing](../README.md#install), each config file already holds every
option needed, so no other arguments are required:

```console
# ODM v1 → ODM v3
python odm_map_maker/make_mappers_cli.py \
    --config odm_map_maker/configs/odm_v1_to_odm.yaml

# NWSS reporting → ODM v3
python odm_map_maker/make_mappers_cli.py \
    --config odm_map_maker/configs/nwss_to_odm.yaml

# PHA4GE → ODM v3
python odm_map_maker/make_mappers_cli.py \
    --config odm_map_maker/configs/pha4ge_to_odm.yaml
```

Output goes to `gen/odm-v1-to-v3`, `gen/nwss-reporting-to-v3`, and
`gen/pha4ge-to-v3`. The LinkML Map YAML files land in `mappers/`; the tables
extracted from the workbook land in `configs/`.

Then check the result — see
[Check generated mappers](how-to/check-generated-mappers.md).

To target ODM v2 instead, see
[Generate mappers for ODM v2](how-to/target-odm-v2.md). For a different NWSS
dictionary type, or for the meaning of any option, see
[CLI Configuration Files](reference/cli-config-files.md).

## Where to start

| If you are… | Read |
| --- | --- |
| New to the project | [Generate your first mappers](tutorials/generate-your-first-mappers.md) |
| Editing or creating a mapping | [Fix an incorrect mapping](how-to/fix-a-mapping.md), then [Mapping Configuration Files](reference/mapping-config-files.md) |
| Running the generator | [CLI Configuration Files](reference/cli-config-files.md) |
| Checking generated output | [Check generated mappers](how-to/check-generated-mappers.md) |
| Changing the code | [Architecture](explanation/architecture.md) and [Contributing](../CONTRIBUTING.md) |
| Lost in the jargon | [Concepts and vocabulary](explanation/concepts.md#vocabulary) |

Otherwise, browse by kind: [tutorials](tutorials/index.md) teach,
[how-to guides](how-to/index.md) solve a specific task,
[explanation](explanation/index.md) gives background, and
[reference](reference/index.md) describes the file formats and tools.

## Related repositories

- **[PHES-ODM-Mapper](https://github.com/Big-Life-Lab/PHES-ODM-Mapper)** —
  consumes the mapper YAML files produced here and performs the actual data
  transformation, cleaning, and ID generation.
- **[PHES-ODM](https://github.com/PHES-ODM/PHES-ODM)** — the Open Data Model
  itself.
- **[linkml-map](https://github.com/linkml/linkml-map)** — the upstream
  transformation framework whose specification format this repository
  generates.
