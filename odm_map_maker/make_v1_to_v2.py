# %%
"""
Makes mapper configs for mapping from ODM v1 to ODM v2.

This script uses the ODM v2 data dictionary, which has the mapping from v1 to v2 embedded in it. In
the future, all mapping information will be removed from the ODM v2 data dictionary and stored in
separate configuration files. Having separate configuration files is the preferred method for configuring
the mappings. See make_mappers.py, and see make_mappers_cli.py for an example.
"""

from pathlib import Path
from typing import Annotated
import typer

from odm_map_maker.odm_v2.make_v2_mappers_from_parts import make_mappers
from odm_map_maker.odm_v2.prepare_parts import prepare_parts
from odm_map_maker.odm_v2.v2_mapping import V2MappingColumns
from odm_map_maker.utils.general_utils import clear_dirs, extract_sheets, get_logger

logger = get_logger(__name__)

app = typer.Typer(
    pretty_exceptions_show_locals=False,
    rich_markup_mode="rich",
)

map_columns = {
    "version1Table": V2MappingColumns.SOURCE_TABLE,
    "version1Location": V2MappingColumns.SOURCE_LOCATION,
    "version1Variable": V2MappingColumns.SOURCE_VARIABLE,
    "version1Category": V2MappingColumns.SOURCE_CATEGORY,
}

MAIN_HELP = """Make the LinkML mapper configuration (YAML) files required for
mapping from ODM v1 to ODM v2."""

CONFIG_HELP = """Location of the config file for mapping from ODM v1 to v2.
              Includes information on which source tables should map to which
              target tables and other config details."""

OUTPUT_DIR_HELP = """Directory to save all the output to. Various
                  subdirectories will be created for the different outputs. The
                  final mapper config files will be in the "mappers"
                  sub-directory."""

V2_DATA_DICTIONARY_HELP = """Path to the ODM v2 Excel data dictionary. Must
                          contain a sheet called "parts" which contains all the
                          ODM v2 metadata and ODM v1 mapping data."""

SOURCE_SCHEMA_HELP = """The path to the source (ODM v1) LinkML schema."""

TARGET_SCHEMA_HELP = """The path to the target (ODM v2) LinkML schema."""

WIDE_DIR_HELP = """Directory that contains all wide-column information. All CSV
                files in this directory are used."""

MAX_MAPPING_ONLY_HELP = """If True then for each source (ODM v1) table, only
                        create the mapping config files that map to the ODM v2
                        table where the maximum number of columns are copied
                        over from ODM v1. This helps eliminate useless mappings
                        (eg. ones where a single column such as an identifier
                        is copied over)."""


@app.command(help=MAIN_HELP)
def main(
    config: Annotated[Path, typer.Option(show_default=False, help=CONFIG_HELP)],
    output_dir: Annotated[Path, typer.Option(show_default=False, help=OUTPUT_DIR_HELP)],
    v2_data_dictionary: Annotated[
        Path, typer.Option(show_default=False, help=V2_DATA_DICTIONARY_HELP)
    ],
    source_schema: Annotated[
        Path, typer.Option(show_default=False, help=SOURCE_SCHEMA_HELP)
    ],
    target_schema: Annotated[
        Path, typer.Option(show_default=False, help=TARGET_SCHEMA_HELP)
    ],
    wide_dir: Annotated[Path, typer.Option(help=WIDE_DIR_HELP)] = None,
    max_mapping_only: Annotated[bool, typer.Option(help=MAX_MAPPING_ONLY_HELP)] = False,
):
    """Make the LinkML mapper configuration (YAML) files required for mapping from ODM v1 to ODM v2.

    This currently creates the YAML files based on data in the ODM v2 data dictionary, using special columns
    (such as version1Table and version1Location) in the parts list that specify the corresponding ODM v1
    variables/tables/enums corresponding to the different rows in the parts list. We plan on changing this
    to specifying the mappings (and wide-column configurations) in a separate Excel file, as is done for
    NWSS to ODM v2 (see make_mappers_cli.py).

    Args:
        config (Union[str, Path]): Location of the config file for mapping from ODM v1 to v2. Includes
            information on which source tables should map to which target tables and other config details.
        output_dir (Union[str, Path]): Directory to save all the output to. Various subdirectories will
            be created for the different outputs. The final mapper config files will be in the
            "mappers" sub-directory.
        v2_data_dictionary (Union[str, Path]): Path to the ODM v2 Excel data dictionary. Must contain
            a sheet called "parts" which contains all the ODM v2 metadata and ODM v1 mapping data.
        source_schema (Union[str, Path]): The path to the source (ODM v1) LinkML schema.
        target_schema (Union[str, Path]): The path to the target (ODM v2) LinkML schema.
        wide_dir (Union[str, Path]): Directory that contains all wide-column information. All CSV
            files in this directory are used.
        max_mapping_only (bool): If True then for each source (ODM v1) table, only create the
            mapping config files that map to the ODM v2 table where the maximum number of columns
            are copied over from ODM v1. This helps eliminate useless mappings (eg. ones where
            a single column such as an identifier is copied over).
    """
    # Some paths, best to use the defaults
    output_dir = Path(output_dir)
    configs_dir = output_dir / "configs"
    mapper_dir = output_dir / "mappers"
    prepared_parts_file = configs_dir / "parts_prepared.csv"

    # Clean up directories (ie. delete old csv, tsv, and yaml files)
    clear_dirs([configs_dir, mapper_dir])

    # Extract the required sheets from the ODM v2 data dictionary
    extract_sheets(
        v2_data_dictionary,
        ["parts"],
        configs_dir,
        output_names=["parts"],
        na_values={"parts": {"partID": ""}},
    )

    # Prepare the parts file from the ODM v2 data dictionary, for mapping from the source format
    prepare_parts(
        configs_dir / "parts.csv",
        output_file=prepared_parts_file,
        map_columns=map_columns,
    )

    # Make all mapper configurations. Each config maps from one source table to one v2 table.
    make_mappers(
        config=config,
        mapper_dir=mapper_dir,
        prepared_parts_file=prepared_parts_file,
        source_schema=source_schema,
        target_schema=target_schema,
        max_mapping_only=max_mapping_only,
        custom_wide_dir=wide_dir,
    )


if __name__ == "__main__":
    if "get_ipython" in globals():
        opts = {
            "config": "data/odm_v1/odm_v1_to_v2_config.yaml",
            "source_schema": "data/odm_v1/linkml/odm_v1.yaml",
            "target_schema": "data/odm_v2/linkml/odm_v2.yaml",
            "wide_dir": "data/odm_v1/custom_wide",
            "output_dir": "../gen/odm_v1_to_v2",
            "v2_data_dictionary": "data/odm_v2/v2 ODM dictionary.xlsx",
            "max_mapping_only": False,
        }

        main(**opts)
    else:
        app()
