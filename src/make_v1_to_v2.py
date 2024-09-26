# %%
"""
Makes mapper configs for mapping from ODM v1 to ODM v2.

This script uses the ODM v2 data dictionary, which has the mapping from v1 to v2 embedded in it. In
the future, all mapping information will be removed from the ODM v2 data dictionary and stored in
separate configuration files. Having separate configuration files is the preferred method for configuring
the mappings. See make_mappers.py, and see make_mappers_cli.py for an example.
"""

from pathlib import Path
from typing import Union
import argparse

from odm_v2.make_v2_mappers_from_parts import make_mappers
from odm_v2.prepare_parts import prepare_parts
from odm_v2.v2_mapping import V2MappingColumns
from utils.general_utils import clear_dirs, extract_sheets, get_logger

logger = get_logger(__name__)

map_columns = {
    "version1Table": V2MappingColumns.SOURCE_TABLE,
    "version1Location": V2MappingColumns.SOURCE_LOCATION,
    "version1Variable": V2MappingColumns.SOURCE_VARIABLE,
    "version1Category": V2MappingColumns.SOURCE_CATEGORY,
}


def make_v1_to_v2(
    config: Union[str, Path],
    output_dir: Union[str, Path],
    v2_data_dictionary: Union[str, Path],
    source_schema: Union[str, Path],
    target_schema: Union[str, Path],
    wide_dir: Union[str, Path],
    max_mapping_only: bool,
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
        source_schema_file=source_schema,
        max_mapping_only=max_mapping_only,
        custom_wide_dir=wide_dir,
    )


if __name__ == "__main__":
    if "get_ipython" in globals():

        class opts:
            config = "../data/odm_v1/odm_v1_to_v2_config.yaml"
            source_schema = "../data/odm_v1/linkml/odm_v1.yaml"
            target_schema = "../data/odm_v2/linkml/odm_v2.yaml"
            wide_dir = "../data/odm_v1/custom_wide"
            output_dir = "../gen/odm_v1_to_v2"
            v2_data_dictionary = "../data/odm_v2/v2 ODM dictionary.xlsx"
            max_mapping_only = False
    else:
        args = argparse.ArgumentParser(
            formatter_class=argparse.ArgumentDefaultsHelpFormatter
        )
        args.add_argument(
            "--config",
            type=str,
            help="Location of the configuration file for mapping ODM v1 to ODM v2",
            required=True,
        )
        args.add_argument(
            "--source_schema",
            type=str,
            help="Location of the source (ODM v1) LinkML schema",
            required=True,
        )
        args.add_argument(
            "--target_schema",
            type=str,
            help="Location of the target (ODM v2) LinkML schema",
            required=True,
        )
        args.add_argument(
            "--wide_dir",
            type=str,
            help="Directory containing all wide-column mapping configurations.",
            required=False,
        )
        args.add_argument(
            "--output_dir",
            type=str,
            help="The directory to save the results to, including the final LinkML mapper config files. Various sub-directories are created with the different outputs.",
            required=True,
        )
        args.add_argument(
            "--v2_data_dictionary",
            type=str,
            help="Location of the ODM v2 data dictionary (Excel file).",
            required=True,
        )
        args.add_argument(
            "--max_mapping_only",
            action="store_true",
            help="If set, then for each source class, only create the mapper spec where the mapping will result in copying the maximum number of source slots to target slots. If more than one mapping has an equal number of copies, then all of the corresponding mapper specs are created. If not set then mappings from each source class to ALL target classes are created (even if only one or a few columns are copied).",
        )

        opts = args.parse_args()

    make_v1_to_v2(
        config=opts.config,
        output_dir=opts.output_dir,
        v2_data_dictionary=opts.v2_data_dictionary,
        source_schema=opts.source_schema,
        target_schema=opts.target_schema,
        wide_dir=opts.wide_dir,
        max_mapping_only=opts.max_mapping_only,
    )
