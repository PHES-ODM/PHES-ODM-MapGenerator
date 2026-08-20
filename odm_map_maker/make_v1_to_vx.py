# %%
"""
Makes mapper configs for mapping from ODM v1 to ODM vx.

This script uses the ODM vx data dictionary (vx = v2, v3, etc), which has the mapping from v1 to vx embedded in it. In
the future, all mapping information will be removed from the ODM vx data dictionary and stored in
separate configuration files. Having separate configuration files is the preferred method for configuring
the mappings. See make_mappers.py, and see make_mappers_cli.py for an example.
"""

from pathlib import Path
from typing import Annotated

import typer

from odm_map_maker.odm_vx.make_vx_mappers_from_parts import make_mappers
from odm_map_maker.odm_vx.prepare_parts import prepare_parts
from odm_map_maker.odm_vx.vx_mapping import VxMappingColumns
from odm_map_maker.utils.general_utils import clear_dirs, extract_sheets
from odm_map_maker.utils.logger import get_logger

logger = get_logger(__name__)

app = typer.Typer(
    pretty_exceptions_show_locals=False,
    rich_markup_mode="rich",
)

map_columns = {
    "version1Table": VxMappingColumns.SOURCE_TABLE,
    "version1Location": VxMappingColumns.SOURCE_LOCATION,
    "version1Variable": VxMappingColumns.SOURCE_VARIABLE,
    "version1Category": VxMappingColumns.SOURCE_CATEGORY,
}

MAIN_HELP = """Make the LinkML mapper configuration (YAML) files required for
mapping from ODM v1 to ODM vx (eg. v2, v3)."""

CONFIG_HELP = """Location of the config file for mapping from ODM v1 to vx.
              Includes information on which source tables should map to which
              target tables and other config details."""

OUTPUT_DIR_HELP = """Directory to save all the output to. Various
                  subdirectories will be created for the different outputs. The
                  final mapper config files will be in the "mappers"
                  sub-directory."""

VX_DATA_DICTIONARY_HELP = """Path to the ODM vx (eg. v2, v3) Excel data dictionary.
                          Must contain a sheet called "parts" which contains all the
                          ODM vx metadata and ODM v1 mapping data."""

SOURCE_SCHEMA_HELP = """The path to the source (ODM v1) LinkML schema."""

TARGET_SCHEMA_HELP = """The path to the target (ODM vx) LinkML schema."""

WIDE_DIR_HELP = """Directory that contains all wide-column information. All CSV
                files in this directory are used."""


@app.command(help=MAIN_HELP)
def main(
    config: Annotated[Path, typer.Option(show_default=False, help=CONFIG_HELP)],
    output_dir: Annotated[Path, typer.Option(show_default=False, help=OUTPUT_DIR_HELP)],
    vx_data_dictionary: Annotated[
        Path, typer.Option(show_default=False, help=VX_DATA_DICTIONARY_HELP)
    ],
    source_schema: Annotated[
        Path, typer.Option(show_default=False, help=SOURCE_SCHEMA_HELP)
    ],
    target_schema: Annotated[
        Path, typer.Option(show_default=False, help=TARGET_SCHEMA_HELP)
    ],
    wide_dir: Annotated[Path | None, typer.Option(help=WIDE_DIR_HELP)] = None,
):
    """Make the LinkML mapper configuration (YAML) files required for mapping from ODM v1 to ODM vx.

    This currently creates the YAML files based on data in the ODM vx data dictionary, using special columns
    (such as version1Table and version1Location) in the parts list that specify the corresponding ODM v1
    variables/tables/enums corresponding to the different rows in the parts list. We plan on changing this
    to specifying the mappings (and wide-column configurations) in a separate Excel file, as is done for
    NWSS to ODM vx (see make_mappers_cli.py).

    Args:
        config (Union[str, Path]): Location of the config file for mapping from ODM v1 to vx. Includes
            information on which source tables should map to which target tables and other config details.
        output_dir (Union[str, Path]): Directory to save all the output to. Various subdirectories will
            be created for the different outputs. The final mapper config files will be in the
            "mappers" sub-directory.
        vx_data_dictionary (Union[str, Path]): Path to the ODM vx Excel data dictionary. Must contain
            a sheet called "parts" which contains all the ODM vx metadata and ODM v1 mapping data.
        source_schema (Union[str, Path]): The path to the source (ODM v1) LinkML schema.
        target_schema (Union[str, Path]): The path to the target (ODM vx) LinkML schema.
        wide_dir (Union[str, Path]): Directory that contains all wide-column information. All CSV
            files in this directory are used.
    """
    # Some paths, best to use the defaults
    output_dir = Path(output_dir)
    configs_dir = output_dir / "configs"
    mapper_dir = output_dir / "mappers"
    prepared_parts_file = configs_dir / "parts_prepared.csv"

    # Clean up directories (ie. delete old csv, tsv, and yaml files)
    clear_dirs([configs_dir, mapper_dir])

    # Extract the required sheets from the ODM vx data dictionary
    extract_sheets(
        vx_data_dictionary,
        ["parts"],
        configs_dir,
        output_names=["parts"],
        na_values={"parts": {"partID": ""}},
    )

    # Prepare the parts file from the ODM vx data dictionary, for mapping from the source format
    prepare_parts(
        configs_dir / "parts.csv",
        output_file=prepared_parts_file,
        map_columns=map_columns,
    )

    # Make all mapper configurations. Each config maps from one source table to one vx table.
    make_mappers(
        config=config,
        mapper_dir=mapper_dir,
        prepared_parts_file=prepared_parts_file,
        source_schema=source_schema,
        target_schema=target_schema,
        custom_wide_dir=wide_dir,
    )


if __name__ == "__main__":
    app()
