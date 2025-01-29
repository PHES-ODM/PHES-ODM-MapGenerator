# %%
from pathlib import Path
from typing import Union, List, Optional
import argparse
import os
import shutil

from make_mappers import MakeMappers
from utils.general_utils import clear_dirs, extract_sheets, get_logger
from utils.mapper_utils import CONFIG_READ_KWARGS

logger = get_logger(__name__)


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


def make_mappers_cli(
    output_dir: Union[str, Path],
    mapping_excel_file: Union[str, Path],
    excel_maps_sheets: Union[List[str], str],
    excel_wide_sheets: Union[List[str], str],
    excel_enums_sheets: Union[List[str], str],
    maps_files: Union[List[Union[str, Path]], Union[str, Path]],
    wide_files: Union[List[Union[str, Path]], Union[str, Path]],
    enums_files: Union[List[Union[str, Path]], Union[str, Path]],
    source_schema: Union[str, Path],
    target_schema: Union[str, Path],
    selectors: Optional[List[str]],
    source_slot_format_operations: Optional[Union[str, List[str]]],
    target_slot_format_operations: Optional[Union[str, List[str]]],
):
    """Make the LinkML Mapper spec (YAML) files required for mapping from any source data set to
    any taret dataset, as specified in the mapping_excel_file.

    Args:
        output_dir (Union[str, Path]): Directory to save all outputs to, including the final mapper files.
            Various sub-directories will be created, with the mappers in the "mappers" subdirectory.
        mapping_excel_file (Union[str, Path]): The mapping configuration Excel file that specifies how to map from
            the source dataset (eg. NWSS) to the target dataset (eg. ODM v2).
        excel_maps_sheets (Union[List[str], str]): Name of the map tab(s)/sheet(s) in the mapping_excel_file Excel file.
            (eg. "maps")
        excel_wide_sheets (Union[List[str], str]): Name of the wide tab(s)/sheet(s) in the mapping_excel_file Excel file.
            (eg. "wide")
        excel_enums_sheets (Union[List[str], str]): Name of the enums tab(s)/sheet(s) in the mapping_excel_file Excel file.
            (eg. "enums")
        maps_files (Union[List[Union[str, Path]], Union[str, Path]]): Path to CSV or TSV files that contain the maps configurations.
        wide_files (Union[List[Union[str, Path]], Union[str, Path]]): Path to CSV or TSV files that contain the wide configurations.
        enum_files (Union[List[Union[str, Path]], Union[str, Path]]): Path to CSV or TSV files that contain the enum configurations.
        source_schema (Union[str, Path]): The source dataset schema LinkML YAML file.
        target_schema (Union[str, Path]): The target dataset schema LinkML YAML file.
        selectors (Optional[List[str]], optional): For rows in the mapping config file that have a value in the "selectors" column, only use the
            row if any of these selectors is found. The "selectors" column has a comma-separated list of selector values. A selector
            value in the data can also be preceded by an exclamation mark, meaning only select the row if the
            selector value is NOT specified.
        source_slot_format_operations (Optional[Union[str, List[str]]], optional): Formatting options to apply to
            all slot names, found in the configuration file, for the source schema.
        target_slot_format_operations (Optional[Union[str, List[str]]], optional): Formatting options to apply to
            all slot names, found in the configuration file, for the target schema.
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
        class opts:
            # source_schema = f"../data/test/source.yaml"
            # target_schema = f"../data/test/target.yaml"
            # mapping_excel_file = f"../data/test/test-map.xlsx"
            # excel_maps_sheets = ["maps"]
            # excel_wide_sheets = []
            # excel_enums_sheets = ["enums"]
            # maps_files = []
            # wide_files = []
            # enums_files = []
            # output_dir = f"../data/test/output"
            # input_data_dir = f"../data/test/output/uncleaned_data"
            # input_max_rows = None
            # id_config_file = None
            # filter_config_file = None

            # source_schema = f"../data/lights/lights.yaml"
            # target_schema = f"../data/lights/lights_inventory.yaml"
            # mapping_excel_file = "../data/lights/lights-mapping.xlsx"
            # excel_maps_sheets = ["maps"]
            # excel_wide_sheets = None
            # excel_enums_sheets = ["enums"]
            # maps_files = []
            # wide_files = []
            # enums_files = []
            # output_dir = f"../data/lights/output"
            # input_data_dir = f"../data/lights/data"
            # input_max_rows = None
            # id_config_file = None
            # filter_config_file = None

            # ODM v1 to ODM v2
            # source_schema = "../data/odm_v1/linkml/odm_v1.yaml"
            # target_schema = "../data/odm_v2/linkml/odm_v2.yaml"
            # mapping_excel_file = "../gen/odm_v1_to_v2/xlsx_mappers_from_yaml/mapping_config.xlsx"
            # excel_maps_sheets = [
            #     "measures",
            #     "qualityReports",
            #     "polygons",
            #     "samples",
            #     "contacts",
            #     "instruments",
            #     "sites",
            #     "organizations",
            #     "protocols",
            # ]
            # excel_wide_sheets = ["wide_protocolSteps"]
            # excel_enums_sheets = ["enums"]
            # maps_files = []
            # wide_files = []
            # enums_files = []
            # output_dir = "../gen/odm_v1_to_v2"
            # input_data_dir = "../../../PHES-ODM-Data/odm_v1_data/centreau_qc/updated"
            # input_max_rows = 50  # 25
            # id_config_file = None
            # filter_config_file = None
            # source_slot_format_operations = ["alpha_numeric_underscore", "single_underscores", "trim_underscores"]
            # target_slot_format_operations = ["alpha_numeric_underscore", "single_underscores", "trim_underscores"]

            # NWSS to ODM v2
            # source_schema = f"../data/nwss_{dictionary_type}/linkml/nwss_{dictionary_type}.yaml"
            # target_schema = "../data/odm_v2/linkml/odm_v2.yaml"
            # mapping_excel_file = (
            #     "../data/mapping_config_files/nwss_to_odm_v2_mapping.xlsx"
            #     # "../gen/nwss_reporting_to_v2/xlsx_mappers_from_yaml/mapping_config.xlsx"
            # )
            # excel_maps_sheets = ["maps"]
            # # excel_maps_sheets = ["measureSets", "contacts", "samples", "addresses", "polygons", "datasets", "sites", "organizations", "protocols", "instruments"]
            # excel_wide_sheets = [
            #     "wide_measures",
            #     "wide_protocolRelationships",
            #     "wide_protocolSteps",
            #     "wide_qualityReports",
            # ]
            # excel_enums_sheets = ["enums"]
            # # excel_enums_sheets = []
            # maps_files = []
            # wide_files = []
            # enums_files = []
            # output_dir = Path(f"../gen/nwss_{dictionary_type}_to_v2")
            # source_slot_format_operations = ["alpha_numeric_underscore", "single_underscores", "trim_underscores"]
            # target_slot_format_operations = ["alpha_numeric_underscore", "single_underscores", "trim_underscores"]
            
            # PHA4GE to ODM v2
            # source_schema = "../data/pha4ge/linkml/pha4ge.yaml"
            source_schema = "../../../PHES-ODM-Data/PHA4GE/schema-WastewaterSARC-CoV-2.yaml"
            target_schema = "../data/odm_v2/linkml/odm_v2.yaml"
            mapping_excel_file = "../data/mapping_config_files/pha4ge_to_odm_v2_mapping.xlsx"
            excel_maps_sheets = [
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
            ]
            excel_wide_sheets = [
                "wide_samples",
                "wide_sampleRelationships",
                "wide_repositories",
                "wide_measures",
                "wide_datasets",
                "wide_contacts",

                # "wide_protocolSteps",
                # "wide_protocols",
            ]
            excel_enums_sheets = [
                "enums_samples",
                "enums_measures",
                "enums_addresses",
            ]
            # excel_enums_sheets = []
            maps_files = []
            wide_files = []
            enums_files = []
            selectors = []
            output_dir = Path("../gen/pha4ge_to_v2")
            source_slot_format_operations = [ "lowercase", '{ remove_chars: "-"}', "alpha_numeric_underscore", "single_underscores", "trim_underscores" ]
            target_slot_format_operations = ["alpha_numeric_underscore", "single_underscores", "trim_underscores"]
        # fmt: on
    else:
        args = argparse.ArgumentParser(
            formatter_class=argparse.ArgumentDefaultsHelpFormatter
        )
        args.add_argument(
            "--source_schema",
            type=str,
            help="Location of the source dataset LinkML schema",
            required=True,
        )
        args.add_argument(
            "--target_schema",
            type=str,
            help="Location of the target dataset LinkML schema",
            required=True,
        )
        args.add_argument(
            "--output_dir",
            type=str,
            help="Directory to save all output to, including where the mapper config files are saved. Various sub-directories are created for the different outputs.",
            required=True,
        )
        args.add_argument(
            "--mapping_excel_file",
            type=str,
            help="The Excel mapping file that contains the mapping, wide, and enums configuration sheets (see excel_maps_sheets, excel_wide_sheets, and excel_enums_sheets).",
            required=False,
        )
        args.add_argument(
            "--excel_maps_sheets",
            type=str,
            nargs="+",
            help="The sheet(s) in the mapping Excel file (mapping_excel_file) that contain the mapping configuration.",
            required=False,
        )
        args.add_argument(
            "--excel_wide_sheets",
            type=str,
            nargs="+",
            help="The sheet(s) in the mapping Excel file (mapping_excel_file) that contain the wide-column configuration.",
            required=False,
        )
        args.add_argument(
            "--excel_enums_sheets",
            type=str,
            nargs="+",
            help="The sheet(s) in the mapping Excel file (mapping_excel_file) that contain the enums configuration.",
            required=False,
        )
        args.add_argument(
            "--maps_files",
            type=str,
            nargs="+",
            help="The file(s) that contain the mapping configuration, in addition to what is already extracted from mapping_excel_file.",
            required=False,
        )
        args.add_argument(
            "--wide_files",
            type=str,
            nargs="+",
            help="The file(s) that contain the wide-column configuration, in addition to what is already extracted from mapping_excel_file.",
            required=False,
        )
        args.add_argument(
            "--enums_files",
            type=str,
            nargs="+",
            help="The file(s) that contain the enums configuration, in addition to what is already extracted from mapping_excel_file.",
            required=False,
        )
        args.add_argument(
            "--selectors",
            type=str,
            nargs="+",
            help="Selectors, to select rows in the mapping config file that has any of these values in the selectors column. If the value in the selectors column is empty then that row is always included.",
            required=False,
        )
        args.add_argument(
            "--source_slot_format_operations",
            type=str,
            nargs="+",
            help="Formatting operations to apply to all configured slots from the source schema.",
            required=False,
        )
        args.add_argument(
            "--target_slot_format_operations",
            type=str,
            nargs="+",
            help="Formatting operations to apply to all configured slots from the target schema.",
            required=False,
        )

        opts = args.parse_args()

    make_mappers_cli(
        output_dir=opts.output_dir,
        mapping_excel_file=opts.mapping_excel_file,
        excel_maps_sheets=opts.excel_maps_sheets,
        excel_wide_sheets=opts.excel_wide_sheets,
        excel_enums_sheets=opts.excel_enums_sheets,
        maps_files=opts.maps_files,
        wide_files=opts.wide_files,
        enums_files=opts.enums_files,
        source_schema=opts.source_schema,
        target_schema=opts.target_schema,
        selectors=opts.selectors,
        source_slot_format_operations=opts.source_slot_format_operations,
        target_slot_format_operations=opts.target_slot_format_operations,
    )
