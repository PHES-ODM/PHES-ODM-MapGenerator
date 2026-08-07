# PHES-ODM Map Generator documentation

The PHES-ODM Map Generator turns human-editable Excel mapping workbooks into
[LinkML Map](https://github.com/linkml/linkml-map) YAML specifications that
describe how to convert data from one wastewater-surveillance format (ODM v1,
NWSS, PHA4GE) into another (ODM v2 or v3).

## The four kinds of documentation

This documentation follows the [Diátaxis](https://diataxis.fr/) (Divio)
framework. Each section answers a different kind of question, so pick the one
that matches what you need right now.

| Section | Answers | Read when |
| --- | --- | --- |
| **[Tutorials](tutorials/index.md)** | "Teach me the basics" | You are new and want to learn by doing |
| **[How-to guides](how-to/index.md)** | "How do I do X?" | You have a specific task in front of you |
| **[Explanation](explanation/index.md)** | "Why is it like this?" | You want to understand the design |
| **[Reference](reference/index.md)** | "What does this option do?" | You need exact details about a format or tool |

Tutorials and how-to guides are *practical* — they get something done.
Reference and explanation are *theoretical* — they inform. Tutorials and
explanation serve *study*; how-to guides and reference serve *work*.

## Start here

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
