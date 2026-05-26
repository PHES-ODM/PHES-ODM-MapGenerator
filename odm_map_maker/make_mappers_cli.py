from pathlib import Path
from typing import Union, List, Optional, Annotated
import os
import shutil
import yaml
import typer

from odm_map_maker.make_mappers import MakeMappers
from odm_map_maker.utils.general_utils import clear_dirs, extract_sheets, get_logger
from odm_map_maker.utils.mapper_utils import CONFIG_READ_KWARGS

logger = get_logger(__name__)

app = typer.Typer(
    pretty_exceptions_show_locals=False,
    rich_markup_mode="rich",
)

MAIN_HELP = """Create LinkML-Map mapping schemas from tabular mapping config files."""

OUTPUT_DIR_HELP = """Directory to save all outputs to, including the final
mapper files. Various sub-directories will be created, with
the mappers in the "mappers" subdirectory."""

MAPPING_EXCEL_FILE_HELP = """The mapping configuration Excel file that
specifies how to map from the source dataset (eg. NWSS) to the target dataset
(eg. ODM v2)."""


EXCEL_MAPS_SHEETS_HELP = """Name of the map tab(s)/sheet(s) in the
mapping_excel_file Excel file. (eg. "maps")"""

EXCEL_WIDE_SHEETS_HELP = """Name of the wide tab(s)/sheet(s) in the
mapping_excel_file Excel file. (eg. "wide")"""

EXCEL_ENUMS_SHEETS_HELP = """Name of the enums tab(s)/sheet(s) in the
mapping_excel_file Excel file. (eg. "enums")"""

MAPS_FILES_HELP = """Path to CSV or TSV files that contain the maps
configurations."""

WIDE_FILES_HELP = """Path to CSV or TSV files that contain the wide
configurations."""

ENUMS_FILES_HELP = """Path to CSV or TSV files that contain the enum
configurations."""

SOURCE_SCHEMA_HELP = """The source dataset schema LinkML YAML file."""

TARGET_SCHEMA_HELP = """The target dataset schema LinkML YAML file."""

SELECTORS_HELP = """A list of strings consisting of flags or module versions
used to include or exclude rows from the mapping configuration files. A flag is
a single string (consisting of letters, numbers, or underscores), which can be
preceded by an exclamation mark to negate the flag, whereas a module version is
of the form "module=version" where "module" is a string consisting of letters,
numbers, and underscores, and "version" is a version number (eg. 1.0.0, 3, 3.1,
etc). An example command-line argument could be: "amr,!deprecated,odm=2.0.0".
See the documentation for mapping config files more details."""

SOURCE_SLOT_FORMAT_OPERATIONS_HELP = """Formatting options to apply to all slot
names, found in the configuration file, for the source schema."""

TARGET_SLOT_FORMAT_OPERATIONS_HELP = """Formatting options to apply to all slot
names, found in the configuration file, for the target schema."""

SOURCE_MATCH_ONTOLOGY_ID_REGEX_HELP = """If set, then a regular expression
string that matches ontology IDs in enum values in the source schema. This is
used to allow automatically adding ontology IDs, as found in the source schema,
onto enum values that do not have an ontology ID in the mapping
configuration."""

TARGET_MATCH_ONTOLOGY_ID_REGEX_HELP = """If set, then a regular expression
string that matches ontology IDs in enum values in the target schema. This is
used to allow automatically adding ontology IDs, as found in the target schema,
onto enum values that do not have an ontology ID in the mapping
configuration."""

CONFIG_HELP = """Path to a YAML configuration file whose keys are CLI option
names (with hyphens or underscores). Values in this file serve as defaults
and are overridden by any arguments supplied on the command line. Path values
in the config file are resolved relative to the config file's location."""

# Option names whose values are file/directory paths and should be resolved
# relative to the config file's directory.
_PATH_KEYS = {
    "source_schema",
    "target_schema",
    "mapping_excel_file",
    "output_dir",
    "maps_files",
    "wide_files",
    "enums_files",
}


def _resolve_config_path(config_dir: Path, v: str) -> str:
    p = Path(v)
    return str(p if p.is_absolute() else (config_dir / p).resolve())


def _config_callback(
    ctx: typer.Context, param: typer.CallbackParam, value: Optional[Path]
):
    """Load a YAML config file and inject its values into Click's default_map.

    Path options are resolved relative to the config file's directory so that
    the config file can be placed anywhere in the project tree without requiring
    absolute paths.
    """
    if value is None:
        return value
    config_path = Path(value).resolve()
    config_dir = config_path.parent
    with open(config_path) as f:
        config = yaml.safe_load(f) or {}
    ctx.default_map = ctx.default_map or {}
    for key, val in config.items():
        normalized = key.replace("-", "_")
        if normalized in _PATH_KEYS and val is not None:
            if isinstance(val, list):
                val = [_resolve_config_path(config_dir, str(v)) for v in val]
            else:
                val = _resolve_config_path(config_dir, str(val))
        ctx.default_map[normalized] = val
    return value


def get_available_file_path(
    source_file: Union[str, Path], target_dir: Union[str, Path]
) -> Path:
    """Get a full path and filename in the target directory that is not currently being used by an
    existing file in the directory. The name of the file will be similar (but not necessarily identical)
    to the file name from the source_file. The returned path can be used to create a new file in the
    target directory without overwriting any existing files.

    Args:
        source_file (Union[str, Path]): The source file that the returned file name is based on. The
            returned file name will have a similar name and the same extension.
        target_dir (Union[str, Path]): The target directory where we want the returned file to be in.

    Returns:
        Path: The full path and filename. The caller can assume that creating the returned file will
            not overwrite any existing files.
    """
    target_name = Path(source_file).name
    target_dir: Path = Path(target_dir)

    stem, ext = os.path.splitext(target_name)
    counter = 1
    while (target_dir / target_name).exists():
        target_name = f"{stem}_{counter}{ext}"
        counter += 1

    return target_dir / target_name


@app.command(help=MAIN_HELP)
def main(
    output_dir: Annotated[Path, typer.Option(show_default=False, help=OUTPUT_DIR_HELP)],
    source_schema: Annotated[
        Path, typer.Option(show_default=False, help=SOURCE_SCHEMA_HELP)
    ],
    target_schema: Annotated[
        Path, typer.Option(show_default=False, help=SOURCE_SCHEMA_HELP)
    ],
    config: Annotated[
        Optional[Path],
        typer.Option(
            "--config",
            callback=_config_callback,
            is_eager=True,
            show_default=False,
            help=CONFIG_HELP,
        ),
    ] = None,
    mapping_excel_file: Annotated[
        Path, typer.Option(show_default=False, help=MAPPING_EXCEL_FILE_HELP)
    ] = None,
    excel_maps_sheets: Annotated[
        List[str], typer.Option(show_default=False, help=EXCEL_MAPS_SHEETS_HELP)
    ] = None,
    excel_wide_sheets: Annotated[
        List[str], typer.Option(show_default=False, help=EXCEL_WIDE_SHEETS_HELP)
    ] = None,
    excel_enums_sheets: Annotated[
        List[str], typer.Option(show_default=False, help=EXCEL_ENUMS_SHEETS_HELP)
    ] = None,
    maps_files: Annotated[
        List[Path], typer.Option(show_default=False, help=MAPS_FILES_HELP)
    ] = None,
    wide_files: Annotated[
        List[Path], typer.Option(show_default=False, help=WIDE_FILES_HELP)
    ] = None,
    enums_files: Annotated[
        List[Path], typer.Option(show_default=False, help=ENUMS_FILES_HELP)
    ] = None,
    selectors: Annotated[
        Optional[List[str]], typer.Option(show_default=False, help=SELECTORS_HELP)
    ] = None,
    source_slot_format_operations: Annotated[
        Optional[List[str]],
        typer.Option(show_default=False, help=SOURCE_SLOT_FORMAT_OPERATIONS_HELP),
    ] = None,
    target_slot_format_operations: Annotated[
        Optional[List[str]],
        typer.Option(show_default=False, help=TARGET_SLOT_FORMAT_OPERATIONS_HELP),
    ] = None,
    source_match_ontology_id_regex: Annotated[
        Optional[str],
        typer.Option(show_default=False, help=SOURCE_MATCH_ONTOLOGY_ID_REGEX_HELP),
    ] = None,
    target_match_ontology_id_regex: Annotated[
        Optional[str],
        typer.Option(show_default=False, help=TARGET_MATCH_ONTOLOGY_ID_REGEX_HELP),
    ] = None,
):
    """Make the LinkML Mapper spec (YAML) files required for mapping from any source data set to
    any taret dataset, as specified in the mapping_excel_file.

    Args:
        output_dir (Path): Directory to save all outputs to, including the final mapper files.
            Various sub-directories will be created, with the mappers in the "mappers" subdirectory.
        mapping_excel_file (Path): The mapping configuration Excel file that specifies how to map from
            the source dataset (eg. NWSS) to the target dataset (eg. ODM v2).
        excel_maps_sheets (List[str]): Name of the map tab(s)/sheet(s) in the mapping_excel_file Excel file.
            (eg. "maps")
        excel_wide_sheets (List[str]): Name of the wide tab(s)/sheet(s) in the mapping_excel_file Excel file.
            (eg. "wide")
        excel_enums_sheets (List[str]): Name of the enums tab(s)/sheet(s) in the mapping_excel_file Excel file.
            (eg. "enums")
        maps_files (List[Path]): Path to CSV or TSV files that contain the maps configurations.
        wide_files (List[Path]): Path to CSV or TSV files that contain the wide configurations.
        enum_files (List[Path]): Path to CSV or TSV files that contain the enum configurations.
        source_schema (Path): The source dataset schema LinkML YAML file.
        target_schema (Path): The target dataset schema LinkML YAML file.
        selectors (Optional[List[str]], optional): Selectors to specify which rows to include or exclude
            in the mapping configuration files (if the "selectors" column is not blank for that row).
            Defaults to None.
        source_slot_format_operations (Optional[List[str]], optional): Formatting options to apply to
            all slot names, found in the configuration file, for the source schema. Defaults to None.
        target_slot_format_operations (Optional[List[str]], optional): Formatting options to apply to
            all slot names, found in the configuration file, for the target schema. Defaults to None.
    """
    output_dir = Path(output_dir)

    if not excel_maps_sheets:
        excel_maps_sheets = []
    if not excel_wide_sheets:
        excel_wide_sheets = []
    if not excel_enums_sheets:
        excel_enums_sheets = []

    if not maps_files:
        maps_files = []
    if not wide_files:
        wide_files = []
    if not enums_files:
        enums_files = []

    if isinstance(excel_maps_sheets, str):
        excel_maps_sheets = [excel_maps_sheets]
    if isinstance(excel_wide_sheets, str):
        excel_wide_sheets = [excel_wide_sheets]
    if isinstance(excel_enums_sheets, str):
        excel_enums_sheets = [excel_enums_sheets]
    if isinstance(maps_files, (str, Path)):
        maps_files = [maps_files]
    if isinstance(wide_files, (str, Path)):
        wide_files = [wide_files]
    if isinstance(enums_files, (str, Path)):
        enums_files = [enums_files]

    configs_dir = output_dir / "configs"
    mapper_dir = output_dir / "mappers"
    mapped_dir = output_dir / "mapped_data"

    # Clean up directories (ie. delete old csv, tsv, and yaml files)
    clear_dirs([configs_dir, mapper_dir, mapped_dir])

    # Extract the required maps/wide/enums sheets from the mapping config/Excel file
    if mapping_excel_file:
        output_maps_names = [f"maps{i}" for i in range(len(excel_maps_sheets))]
        output_maps_files = [configs_dir / f"{f}.csv" for f in output_maps_names]
        output_wide_names = [f"wide{i}" for i in range(len(excel_wide_sheets))]
        output_wide_files = [configs_dir / f"{f}.csv" for f in output_wide_names]
        output_enums_names = [f"enums{i}" for i in range(len(excel_enums_sheets))]
        output_enums_files = [configs_dir / f"{f}.csv" for f in output_enums_names]
        extract_sheets(
            mapping_excel_file,
            [*excel_maps_sheets, *excel_wide_sheets, *excel_enums_sheets],
            configs_dir,
            output_names=[*output_maps_names, *output_wide_names, *output_enums_names],
            na_values={},
            default_na_values=[""],
            read_excel_kwargs=CONFIG_READ_KWARGS,
        )
    else:
        output_maps_files = []
        output_wide_files = []
        output_enums_files = []

    # Copy the maps/wide/enums files to the same location as the ones we extracted from the Excel file
    for source_files, output_files in [
        (maps_files, output_maps_files),
        (wide_files, output_wide_files),
        (enums_files, output_enums_files),
    ]:
        for source_file in source_files:
            new_file = get_available_file_path(source_file, configs_dir)
            shutil.copyfile(source_file, new_file)
            output_files.append(new_file)

    # Create the mapper specs
    maker = MakeMappers(
        maps_files=output_maps_files,
        wide_files=output_wide_files,
        enums_files=output_enums_files,
        mapper_dir=mapper_dir,
        source_schema=source_schema,
        target_schema=target_schema,
        selectors=selectors,
        source_slot_format_operations=source_slot_format_operations,
        target_slot_format_operations=target_slot_format_operations,
        source_match_ontology_id_regex=source_match_ontology_id_regex,
        target_match_ontology_id_regex=target_match_ontology_id_regex,
    )
    maker.make_mappers()

    logger.info("Finished!")


if __name__ == "__main__":
    app()
