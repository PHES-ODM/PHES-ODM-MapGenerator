# Contributing

Thanks for working on the PHES-ODM Map Generator. This document covers the
development setup, the checks that must pass, and the conventions the codebase
follows.

New to the project? Work through
[Generate your first mappers](docs/tutorials/generate-your-first-mappers.md),
then read [Concepts and vocabulary](docs/explanation/concepts.md) and
[Architecture](docs/explanation/architecture.md) before changing code.

## Development setup

Python 3.10 or newer is required.

```console
git clone git@github.com:PHES-ODM/PHES-ODM-MapGenerator.git
cd PHES-ODM-MapGenerator
python3 -m venv .env
source .env/bin/activate          # Windows: .env\Scripts\activate

pip install -r requirements-dev.txt
pip install -e . --no-deps
```

`requirements-dev.txt` includes `requirements.txt` plus pytest, pytest-cov, and
ruff. The editable install makes the `odm_map_maker` package importable from
anywhere and provides the `odm-map-maker` console script.

## Checks

Both checks run in GitHub Actions on every push and pull request to `main`, and
both must pass.

### Tests

```console
pytest tests/            # add -v for per-test output
```

With coverage:

```console
pytest tests/ --cov=odm_map_maker --cov-report=term-missing
```

### Lint and format

```console
ruff check               # add --fix to apply safe fixes
ruff format --diff       # add --check for pass/fail only, or drop --diff to write
```

CI runs `ruff check --output-format=github` and `ruff format --diff`, so
formatting differences fail the build. Run `ruff format` before committing.

## Do I need to change code?

Often not. Most changes to *what* gets mapped belong in data, not code:

| Change | Where |
| --- | --- |
| A column or value maps incorrectly | The Excel workbook in `odm_map_maker/data/mapping_config_files/` |
| Different sheets, selectors, or paths for a run | The YAML file in `odm_map_maker/configs/` |
| A new source dataset | A new LinkML schema, workbook, and config file — no engine changes |
| Slot names differ in case or punctuation | `--source-slot-format-operations` / `--target-slot-format-operations` |

Reach for the engine only when the workbook cannot express the mapping.

## Conventions

**Type hints and docstrings.** Public functions carry full type hints and a
Google-style docstring with `Args:` and `Returns:` sections. Match the
surrounding style; see
[utils/general_utils.py](odm_map_maker/utils/general_utils.py) for the house
pattern.

**Modern typing syntax.** The codebase targets 3.10+ and uses `str | Path`
rather than `Union[str, Path]`, and `list[str]` rather than `List[str]`. Some
older docstrings still spell out `Union[...]` in prose; new code should not.

**Column names are constants.** Workbook column names live on `MappingColumns`
in [utils/mapper_utils.py](odm_map_maker/utils/mapper_utils.py). Never write a
column name as a bare string literal — add or use the constant.

**Schema access goes through `schema_utils`.** Add new `SchemaView` queries to
[utils/schema_utils.py](odm_map_maker/utils/schema_utils.py) rather than
calling `SchemaView` from the engine, so behaviour such as ontology-ID handling
stays consistent.

**Logging, not printing.** Use `get_logger(__name__)` from
[utils/logger.py](odm_map_maker/utils/logger.py) rather than `print`.

**CLI scripts use Typer.** Each script defines an `app = typer.Typer(...)`, puts
its help text in module-level `*_HELP` constants, and annotates options with
`Annotated[T, typer.Option(...)]`. Copy the structure from
[make_mappers_cli.py](odm_map_maker/make_mappers_cli.py).

## Testing changes to the engine

The test suite covers the utility layer and `mapper_validator`. `MakeMappers`
has no direct unit tests, so verify engine changes by regenerating a known
mapping and diffing the result:

```console
# Before your change
python odm_map_maker/make_mappers_cli.py \
    --config odm_map_maker/configs/nwss_to_odm.yaml \
    --output-dir /tmp/mappers-before

# After your change
python odm_map_maker/make_mappers_cli.py \
    --config odm_map_maker/configs/nwss_to_odm.yaml \
    --output-dir /tmp/mappers-after

diff -r /tmp/mappers-before/mappers /tmp/mappers-after/mappers
```

An empty diff means the change is behaviour-preserving. Repeat for the
`odm_v1_to_odm` and `pha4ge_to_odm` configs — each exercises different code
paths (PHA4GE is the only one using ontology-ID matching and
`remove_chars` slot formatting; `odm_v1_to_odm` uses many `maps` sheets and one
`wide` sheet).

Then re-run [mapper_validator.py](docs/reference/mapper-validator.md) and
[slot_derivations_checker.py](docs/reference/slot-derivations-checker.md) against the new
output and compare the reports.

Adding tests for engine behaviour you touch is welcome.

## Documentation

Documentation lives in [docs/](docs/) and is indexed by
[docs/index.md](docs/index.md). It is built with
[MkDocs](https://www.mkdocs.org/) and published to GitHub Pages by
[.github/workflows/docs.yaml](.github/workflows/docs.yaml) on every push to
`main`.

Preview the site locally:

```console
pip install -r requirements-dev.txt
mkdocs serve                       # http://127.0.0.1:8000
mkdocs build --strict              # what CI runs
```

### The four sections

Documentation follows the [Divio/Diátaxis](https://diataxis.fr/) framework. A
new page belongs in exactly one of these — if it seems to fit two, it is
probably two pages.

| Section | Purpose | A page there… |
| --- | --- | --- |
| `docs/tutorials/` | Teach a beginner by doing | is followed start to finish, works on throwaway data, and never offers alternatives or caveats mid-step |
| `docs/how-to/` | Solve one stated problem | assumes competence, starts from a goal ("Fix an incorrect mapping"), and links out rather than explaining |
| `docs/explanation/` | Give background and rationale | discusses why, may cover trade-offs and history, and contains no instructions to follow |
| `docs/reference/` | Describe the machinery | is exhaustive and dry, is structured like the thing it describes, and does not teach |

The most common mistake is putting how-to material in a reference page. If you
catch yourself writing "first…, then…" in `docs/reference/`, it belongs in
`docs/how-to/`.

When you add a page, also add it to the section's `index.md` table and to the
`nav` section of [mkdocs.yml](mkdocs.yml).

### Keep docs in the same change as the code

| If you change | Also update |
| --- | --- |
| A CLI option | The script's `*_HELP` constant, the option list in [README.md](README.md), and the relevant page under `docs/reference/` |
| A workbook column | [docs/reference/mapping-config-files.md](docs/reference/mapping-config-files.md) |
| The generation pipeline | [docs/explanation/architecture.md](docs/explanation/architecture.md) |
| A new config file in `configs/` | [README.md](README.md) and [docs/reference/cli-config-files.md](docs/reference/cli-config-files.md) |
| A step a newcomer would trip over | [docs/tutorials/generate-your-first-mappers.md](docs/tutorials/generate-your-first-mappers.md) |
| A recurring support question | A new page in [docs/how-to/](docs/how-to/) |

## Pull requests

- Branch from `main`.
- Keep `pytest tests/`, `ruff check`, and `ruff format --check` green.
- Describe what changed in the generated mapper output, if anything — that is
  the part reviewers cannot see from the diff.
