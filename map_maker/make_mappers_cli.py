# %%
from pathlib import Path
from typing import Union, List, Optional, Annotated
import os
import shutil
import typer

from make_mappers import MakeMappers
from utils.general_utils import clear_dirs, extract_sheets, get_logger
from utils.mapper_utils import CONFIG_READ_KWARGS

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
                          specifies how to map from the source dataset (eg.
                          NWSS) to the target dataset (eg. ODM v2)."""


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

SELECTORS_HELP = """For rows in the mapping config file that have a value in
                 the "selectors" column, only use the row if any of these
                 selectors is found. The "selectors" column has a
                 comma-separated list of selector values. A selector value in
                 the data can also be preceded by an exclamation mark, meaning
                 only select the row if the selector value is NOT specified."""

SOURCE_SLOT_FORMAT_OPERATIONS_HELP = """Formatting options to apply to all slot
                                     names, found in the configuration file,
                                     for the source schema."""

TARGET_SLOT_FORMAT_OPERATIONS_HELP = """Formatting options to apply to all slot
                                     names, found in the configuration file,
                                     for the target schema."""


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

    while (target_dir / target_name).exists():
        target_name = "%s_%s" % os.path.splitext(target_name)

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
        selectors (Optional[List[str]], optional): For rows in the mapping config file that have a value in the "selectors" column, only use the
            row if any of these selectors is found. The "selectors" column has a comma-separated list of selector values. A selector
            value in the data can also be preceded by an exclamation mark, meaning only select the row if the
            selector value is NOT specified. Defaults to None
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

    source_schema_for_mapping_dir = output_dir / "linkml_for_mapping"
    source_schema_for_mapping = source_schema_for_mapping_dir / os.path.basename(
        source_schema
    )

    # Clean up directories (ie. delete old csv, tsv, and yaml files)
    clear_dirs([configs_dir, mapper_dir, mapped_dir, source_schema_for_mapping_dir])

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

    if len(output_maps_files) == 0:
        logger.error("No maps configurations found")
    else:
        # Create the mapper specs
        maker = MakeMappers(
            maps_files=output_maps_files,
            wide_files=output_wide_files,
            enums_files=output_enums_files,
            mapper_dir=mapper_dir,
            source_schema=source_schema,
            target_schema=target_schema,
            source_schema_for_mapping=source_schema_for_mapping,
            selectors=selectors,
            source_slot_format_operations=source_slot_format_operations,
            target_slot_format_operations=target_slot_format_operations,
        )
        maker.make_mappers()

    logger.info("Finished!")


if __name__ == "__main__":
    if "get_ipython" in globals():
        dictionary_type = "reporting"

        # fmt: off
        opts = {
            # ODM v1 to ODM v2
            # "source_schema": "data/odm_v1/linkml/odm_v1.yaml",
            # "target_schema": "data/odm_v2/linkml/odm_v2.yaml",
            # "mapping_excel_file": "../gen/odm_v1_to_v2/xlsx_mappers_from_yaml/mapping_config.xlsx",
            # "excel_maps_sheets":
            #     "measures",
            #     "qualityReports",
            #     "polygons",
            #     "samples",
            #     "contacts",
            #     "instruments",
            #     "sites",
            #     "organizations",
            #     "protocols",
            # ],
            # "excel_wide_sheets": ["wide_protocolSteps"],
            # "excel_enums_sheets": ["enums"],
            # "maps_files": [],
            # "wide_files": [],
            # "enums_files": [],
            # "output_dir": "../gen/odm_v1_to_v2",
            # "selectors": [],
            # "input_max_rows": 50,  # 25,
            # "id_config_file": None,
            # "filter_config_file": None,
            # "source_slot_format_operations": ["alpha_numeric_underscore", "single_underscores", "trim_underscores"],
            # "target_slot_format_operations": ["alpha_numeric_underscore", "single_underscores", "trim_underscores"],

            # NWSS to ODM v2
            # "source_schema": f"data/nwss_{dictionary_type}/linkml/nwss_{dictionary_type}.yaml",
            # "target_schema": "data/odm_v2/linkml/odm_v2.yaml",
            # "mapping_excel_file": "data/mapping_config_files/nwss_to_odm_v2_mapping.xlsx",
            # # "mapping_excel_file": "../gen/nwss_reporting_to_v2/xlsx_mappers_from_yaml/mapping_config.xlsx",
            # "excel_maps_sheets": ["maps"],
            # # "excel_maps_sheets": ["measureSets", "contacts", "samples", "addresses", "polygons", "datasets", "sites", "organizations", "protocols", "instruments"],
            # "excel_wide_sheets": [
            #     "wide_measures",
            #     "wide_protocolRelationships",
            #     "wide_protocolSteps",
            #     "wide_qualityReports",
            # ],
            # "excel_enums_sheets": ["enums"],
            # "maps_files": [],
            # "wide_files": [],
            # "enums_files": [],
            # "output_dir": Path(f"../gen/nwss_{dictionary_type}_to_v2"),
            # "selectors": [],
            # "source_slot_format_operations": ["alpha_numeric_underscore", "single_underscores", "trim_underscores"],
            # "target_slot_format_operations": ["alpha_numeric_underscore", "single_underscores", "trim_underscores"],

            # PHA4GE to ODM v2
            "source_schema": "../../../PHES-ODM-Data/PHA4GE/schema-WastewaterSARC-CoV-2.yaml",
            "target_schema": "data/odm_v2/linkml/odm_v2.yaml",
            "mapping_excel_file": "data/mapping_config_files/pha4ge_to_odm_v2_mapping.xlsx",
            "excel_maps_sheets": [
                "maps_OTHER",
                "maps_sites",
                "maps_samples",
                "maps_repositories",
                "maps_polygons",
                "maps_measures",
                "maps_instruments",
                "maps_datasets",
                "maps_addresses",
                "maps_accessions",

                # "maps_qualityReports",
                # "maps_protocolSteps",
                # "maps_protocols",
            ],
            "excel_wide_sheets": [
                "wide_samples",
                "wide_sampleRelationships",
                "wide_repositories",
                "wide_measures",
                "wide_datasets",
                "wide_contacts",

                # "wide_protocolSteps",
                # "wide_protocols",
            ],
            "excel_enums_sheets": [
                "enums_samples",
                "enums_measures",
                "enums_addresses",
            ],
            # "excel_enums_sheets": [],
            "maps_files": [],
            "wide_files": [],
            "enums_files": [],
            "selectors": [],
            "output_dir": Path("../gen/pha4ge_to_v2"),
            "source_slot_format_operations": [ "lowercase", '{ remove_chars: "-"}', "alpha_numeric_underscore", "single_underscores", "trim_underscores" ],
            "target_slot_format_operations": ["alpha_numeric_underscore", "single_underscores", "trim_underscores"],
        }
        # fmt: on

        main(**opts)
    else:
        app()
