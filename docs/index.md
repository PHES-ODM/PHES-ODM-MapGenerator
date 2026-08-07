# PHES-ODM Map Generator documentation

The PHES-ODM Map Generator turns human-editable Excel mapping workbooks into
[LinkML Map](https://github.com/linkml/linkml-map) YAML specifications that
describe how to convert data from one wastewater-surveillance format (ODM v1,
NWSS, PHA4GE) into another (ODM v2 or v3).

## Where to start

This documentation follows the [Diátaxis](https://diataxis.fr/) (Divio)
framework, which splits writing into four kinds. Each answers a different
question, so pick the one that matches what you are doing right now.

<div class="grid cards" markdown>

- :material-school: **[Tutorials](tutorials/index.md)**

    ---

    *Learning-oriented.* Start here if the project is new to you. Follow along
    from an empty checkout to a set of mapper YAML files you can open and read.

    [Generate your first mappers →](tutorials/generate-your-first-mappers.md)

- :material-wrench: **[How-to guides](how-to/index.md)**

    ---

    *Goal-oriented.* Recipes for a specific job you already know you need to
    do: correct a wrong mapping, map a wide column, target ODM v2, add a new
    source dataset.

    [Browse the guides →](how-to/index.md)

- :material-lightbulb: **[Explanation](explanation/index.md)**

    ---

    *Understanding-oriented.* Background and design reasoning: the vocabulary
    used throughout, how the generator is put together, and why wide columns
    need special handling.

    [Read the background →](explanation/index.md)

- :material-book-open-variant: **[Reference](reference/index.md)**

    ---

    *Information-oriented.* Dry descriptions of what exists: every column of
    the mapping workbooks, the CLI configuration files, and the checking tools.

    [Look something up →](reference/index.md)

</div>

Tutorials and how-to guides are *practical* — they get something done.
Reference and explanation are *theoretical* — they inform. Tutorials and
explanation serve *study*; how-to guides and reference serve *work*.

## Pick a page

| If you are… | Read |
| --- | --- |
| New to the project | [Generate your first mappers](tutorials/generate-your-first-mappers.md) |
| Editing or creating a mapping | [Fix an incorrect mapping](how-to/fix-a-mapping.md), then [Mapping Configuration Files](reference/mapping-config-files.md) |
| Running the generator | [CLI Configuration Files](reference/cli-config-files.md) |
| Changing the code | [Architecture](explanation/architecture.md) and [Contributing](../CONTRIBUTING.md) |
| Lost in the jargon | [Concepts and vocabulary](explanation/concepts.md#vocabulary) |

## Related repositories

- **[PHES-ODM-Mapper](https://github.com/Big-Life-Lab/PHES-ODM-Mapper)** —
  consumes the mapper YAML files produced here and performs the actual data
  transformation, cleaning, and ID generation.
- **[PHES-ODM](https://github.com/PHES-ODM/PHES-ODM)** — the Open Data Model
  itself.
- **[linkml-map](https://github.com/linkml/linkml-map)** — the upstream
  transformation framework whose specification format this repository
  generates.
