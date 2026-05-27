# %%
"""
Creates the LinkML mapper config files for mapping from one database format (eg. NWSS) to
another (eg. ODM v2). This is configured with CSV files (usually extracted from Excel files) that
specify both the mappings between source and target classes, wide-to-long columns, and enumeration
mappings.
"""

import pandas as pd
from pathlib import Path
from typing import Union, List, Dict, Optional, Any
import os
import yaml
import json
import re

from linkml_runtime import SchemaView
from linkml_runtime.linkml_model.meta import SchemaDefinition
from linkml_runtime.utils.schema_as_dict import schema_as_dict

from odm_map_maker.utils.logger import get_logger
from odm_map_maker.utils.selector_filter import SelectorFilter
from odm_map_maker.utils.general_utils import (
    read_data_frame,
    strip_whitespace,
    order_columns,
    EMPTY_CONFIG_VALUE,
    TREE_ROOT_CLASS_NAME,
)
from odm_map_maker.utils.schema_utils import (
    get_enum_names_for_slot,
    get_enum_name_with_permissible_value,
    add_ontoid_to_enum_value,
)
from odm_map_maker.utils.mapper_utils import (
    select_required_enum_derivations,
    expand_wide_derivations,
    get_variable_reference,
    MappingColumns,
    is_wide_target_value_slot,
    is_wide_target_expr_slot,
    any_wide_slot_name,
    get_blank_class_derivation,
    cleanup_slot_name,
    CONFIG_READ_KWARGS,
)

logger = get_logger(__name__)


class MakeMappers(object):
    def __init__(
        self,
        maps_files: Union[Union[str, Path], List[Union[str, Path]]],
        wide_files: Union[Union[str, Path], List[Union[str, Path]]],
        enums_files: Union[Union[str, Path], List[Union[str, Path]]],
        mapper_dir: Union[str, Path],
        source_schema: Union[str, Path],
        target_schema: Union[str, Path],
        selectors: Optional[List[str]],
        source_slot_format_operations: Optional[Union[str, List[str]]],
        target_slot_format_operations: Optional[Union[str, List[str]]],
        source_match_ontology_id_regex: Optional[str],
        target_match_ontology_id_regex: Optional[str],
    ):
        """Construct map maker for generating LinkML mapping files.

        Args:
            maps_files (Union[Union[str, Path], List[Union[str, Path]]]): The mapping config files.
            wide_files (Union[Union[str, Path], List[Union[str, Path]]]): The wide column config files. Set to None or []
                if there are no wide files.
            enums_files (Union[Union[str, Path], List[Union[str, Path]]]): The enumerations config files. Set to None or []
                if there are no enum files.
            mapper_dir (Union[str, Path]): Directory to save all the mapping config files to.
            source_schema (Union[str, Path]): Path to the source schema of the mapping.
            target_schema (Union[str, Path]): Path to the target schema of the mapping.
            selectors (Optional[List[str]], optional): Selectors to specify which rows to include or exclude
                in the mapping configuration files (if the "selectors" column is not blank for that row).
                Defaults to None.
            source_slot_format_operations (Optional[Union[str, List[str]]], optional): Formatting options to apply to
                all slot names, found in the configuration file, for the source schema.
            target_slot_format_operations (Optional[Union[str, List[str]]], optional): Formatting options to apply to
                all slot names, found in the configuration file, for the target schema.
            source_match_ontology_id_regex (Optional[str], optional): If set, then a regular expression string that matches ontology
                IDs in enum values in the source schema. This is used to allow automatically adding ontology IDs, as found in the source
                schema, onto enum values that do not have an ontology ID in the mapping configuration.
            target_match_ontology_id_regex (Optional[str], optional): If set, then a regular expression string that matches ontology
                IDs in enum values in the target schema. This is used to allow automatically adding ontology IDs, as found in the target
                schema, onto enum values that do not have an ontology ID in the mapping configuration.
        """
        self.mapper_dir = mapper_dir
        self.selector_filter = SelectorFilter(
            selectors=selectors, selector_column=MappingColumns.SELECTORS
        )
        self.source_slot_format_operations = source_slot_format_operations
        self.target_slot_format_operations = target_slot_format_operations
        self.source_match_ontology_id_regex = source_match_ontology_id_regex
        self.target_match_ontology_id_regex = target_match_ontology_id_regex

        self.maps_files = maps_files
        self.wide_files = wide_files
        self.enums_files = enums_files
        if isinstance(self.maps_files, (str, Path)):
            self.maps_files = [self.maps_files]
        if isinstance(self.wide_files, (str, Path)):
            self.wide_files = [self.wide_files]
        if isinstance(self.enums_files, (str, Path)):
            self.enums_files = [self.enums_files]

        # Load all schemas
        self.source_schema = SchemaView(source_schema)
        self.target_schema = SchemaView(target_schema)

    def make_mappers(self):
        if self.mapper_dir:
            os.makedirs(self.mapper_dir, exist_ok=True)

        # Load and prepare the maps files
        maps_dfs = [self.prepare_maps_df(f) for f in self.maps_files]
        maps_dfs = [df for df in maps_dfs if df is not None]
        maps_df = (
            pd.concat(maps_dfs).reset_index(drop=True) if maps_dfs else pd.DataFrame()
        )

        # Load and prepare the wide-columns files
        wide_dfs = []
        if self.wide_files is not None and len(self.wide_files) > 0:
            wide_dfs = [self.prepare_wide_df(f) for f in self.wide_files if f]

        # Load and prepare the enums mapping files
        enums_df = None
        if self.enums_files is not None and len(self.enums_files) > 0:
            enums_df = [self.prepare_enums_df(f) for f in self.enums_files]
            enums_df = pd.concat([df for df in enums_df if df is not None])

        groupby_columns = [
            MappingColumns.SOURCE_CLASS,
            MappingColumns.SOURCE_SLOT,
            MappingColumns.TARGET_CLASS,
            MappingColumns.WIDE_GROUP,
        ]

        # Any row where both sourceSlot and wideGroup are empty should be split into it's own wide group. To do this we create
        # a new wideGroup name for each row that this occurs in. This makes it so that in the config file users can specify multiple
        # wide rows with blank sourceSlots, which is a bit more intuitive. Normally, rows where the sourceSlot (and a few other columns)
        # are equal are treated as an individual group that specifies the output of a *single* wide row, but here, by adding a unique group
        # name, we get multiple output wide rows, one for each empty sourceSlot (rather than a single wide row, resulting from grouping
        # the empty sourceSlots together). We check that wideGroup is empty, since if wideGroup is explicitly specified by the user then
        # that means they want the rows to be grouped together.
        def isna(x: Any) -> bool:
            return pd.isna(x) or x == ""

        for wide_df in wide_dfs:
            if len(wide_df) == 0:
                continue
            # New group names are prefixed by new_group_name_prefix. It ensures that a unique/unused group name
            # is created for the new group names
            max_wide_group_length = (
                wide_df[MappingColumns.WIDE_GROUP].map(lambda x: len(x)).max()
            )
            new_group_name_prefix = "_" * max_wide_group_length
            new_group_rows = wide_df[MappingColumns.SOURCE_SLOT].map(isna) & wide_df[
                MappingColumns.WIDE_GROUP
            ].map(isna)
            if new_group_rows.sum() == 0:
                continue
            wide_df.loc[new_group_rows, MappingColumns.WIDE_GROUP] = [
                f"{new_group_name_prefix}_{i + 1}" for i in range(new_group_rows.sum())
            ]

        # Extract all enum and class derivations from the maps file and enums files.
        # (maps|enums)_enum_derivations is in the format (maps|enums)_enum_derivations[source_class][target_class] = {enum_derivations}
        # all_class_derivations is in the format all_class_derivations[source_class][target_class] = {class_derivations}
        maps_enum_derivations = self.extract_enum_derivations(maps_df)
        enums_enum_derivations = self.extract_enum_derivations(enums_df)
        all_class_derivations = self.extract_class_derivations(maps_df)

        # Go through all wide mapping data, and create the wide class derivations (one class derivation per wide group)
        results = []
        for wide_df in wide_dfs:
            for idx, (_, group_df) in enumerate(
                wide_df.groupby(groupby_columns, sort=False)
            ):
                source_class_name = group_df[MappingColumns.SOURCE_CLASS].iloc[0]
                target_class_name = group_df[MappingColumns.TARGET_CLASS].iloc[0]
                class_derivation = all_class_derivations.get(source_class_name, {}).get(
                    target_class_name, None
                )
                if not class_derivation:
                    class_derivation = get_blank_class_derivation(
                        source_class_name, target_class_name
                    )

                custom_wide_results = self.make_wide_derivations(
                    class_derivation=class_derivation,
                    custom_wide_df=group_df,
                    class_enum_derivations=[
                        enums_enum_derivations,
                        maps_enum_derivations,
                    ],
                )
                if len(custom_wide_results) > 0:
                    results.extend(custom_wide_results)

        # Add all the class derivations that were not expanded to wide derivations
        for (
            source_class_name,
            source_class_derivations,
        ) in all_class_derivations.items():
            for (
                target_class_name,
                target_class_derivation,
            ) in source_class_derivations.items():
                wide_results = [
                    r
                    for r in results
                    if r["undecorated_target_class"] == target_class_name
                    and r["source_class"] == source_class_name
                ]
                if len(wide_results) == 0:
                    enum_derivations = select_required_enum_derivations(
                        source_class_name,
                        target_class_name,
                        target_class_derivation,
                        [enums_enum_derivations, maps_enum_derivations],
                        schema=self.source_schema,
                    )
                    results.append(
                        {
                            "source_class": source_class_name,
                            "target_class": target_class_name,
                            "undecorated_target_class": target_class_name,
                            "class_derivation": target_class_derivation,
                            "enum_derivations": enum_derivations,
                        }
                    )

        # Go through all the results and create a mapping spec file for each
        for idx, cur_results in enumerate(results):
            target_class = cur_results["target_class"]
            class_derivation = cur_results["class_derivation"]
            source_class = cur_results["source_class"]
            enum_derivations = cur_results["enum_derivations"]
            # Create the mapping spec for the mapping from source_class to target_class
            mapper_spec = {
                "class_derivations": {
                    target_class: class_derivation,
                    TREE_ROOT_CLASS_NAME: {
                        "name": TREE_ROOT_CLASS_NAME,
                        "slot_derivations": {
                            target_class: {
                                "populated_from": source_class,
                            }
                        },
                    },
                },
                "enum_derivations": enum_derivations,
            }

            # Save mapper specification to disk
            re_match = r"[^A-Za-z0-9 .,\_]"
            source_class_tag = re.sub(re_match, "_", source_class)
            target_class_tag = re.sub(re_match, "_", target_class)
            mapper_file = os.path.join(
                self.mapper_dir,
                f"mapper-{idx:010n}-{source_class_tag}-{target_class_tag}.yaml",
            )
            logger.info(
                f"Saving mapper spec for '{source_class}' to '{target_class}': {mapper_file}"
            )
            with open(mapper_file, "w") as f:
                yaml.dump(mapper_spec, f, indent=2, sort_keys=False)

    def extract_class_derivations(
        self, maps_df: pd.DataFrame
    ) -> Dict[str, Dict[str, Dict]]:
        """Extract all class derivations in a DataFrame (typically from the mapping config file).

        Args:
            maps_df (pd.DataFrame): The mapping DataFrame loaded from the mapping specification file.

        Raises:
            ValueError: An error occurred due to problems with the mapping data.

        Returns:
            Dict[str, Dict[str, Dict]]: A dictionary with a separate key for each source class. Within each source class
                is a key for each target class that acts as the class derivation. Example:
                    {
                        "nwss_reporting": {
                            "sites": {
                                "name": "sites",
                                "populated_from": "nwss_reporting",
                                "slot_derivations": {
                                    ...
                                }
                            },
                            "other_target_class": { ... },
                            ...
                        }
                        "other_source_class" : { ... },
                        ...
                    }
        """
        if maps_df is None:
            return {}

        # This dictionary has a separate key for each source class. Within each source class there is a key for each target class
        # that forms the actual class derivation
        all_class_derivations: Dict[str, Dict[str, Dict]] = {}
        for _, row in maps_df.iterrows():
            # Get all the data from the row
            source_class = row[MappingColumns.SOURCE_CLASS]
            source_slot = row[MappingColumns.SOURCE_SLOT]
            target_class = row[MappingColumns.TARGET_CLASS]
            target_slot = row[MappingColumns.TARGET_SLOT]
            custom_data = row[MappingColumns.CUSTOM_DATA]
            target_expr = row[MappingColumns.TARGET_EXPR]
            slot_derivation_settings = row[MappingColumns.SLOT_DERIVATION_SETTINGS]
            if pd.isna(slot_derivation_settings):
                slot_derivation_settings = None
            if slot_derivation_settings:
                slot_derivation_settings = yaml.safe_load(slot_derivation_settings)

            if pd.isna(custom_data):
                custom_data = None
            if pd.isna(target_expr):
                target_expr = None

            # Make sure the row's source class exists in the source schema
            if source_class not in self.source_schema.all_classes():
                logger.error(
                    f"Found source class '{source_class}' in mapping data but class does not exist in source schema, ignoring row"
                )
                continue

            # Get the dictionary for the source_class. Within this dictionary are keys from each target class.
            if source_class not in all_class_derivations:
                all_class_derivations[source_class] = {}
            source_class_derivations = all_class_derivations[source_class]

            # Get the derivation targeting the target_class
            if target_class not in source_class_derivations:
                source_class_derivations[target_class] = get_blank_class_derivation(
                    source_class, target_class
                )
            slot_derivations = source_class_derivations[target_class][
                "slot_derivations"
            ]

            if custom_data or target_expr:
                new_dict = {
                    "name": target_slot,
                }
                if slot_derivation_settings:
                    new_dict.update(slot_derivation_settings)
                if target_expr:
                    new_dict["expr"] = target_expr
                if target_slot in slot_derivations:
                    # The slot derivation for target_slot already exists (ie. it was added in a previous row of maps_df). Here we make sure
                    # that the slot derivation for target_slot will be left unchanged.
                    if slot_derivations[target_slot] != new_dict:
                        raise ValueError(
                            f"Target slot '{target_slot}' in target class '{target_class}' from source class '{source_class}' already exists in slot_derivations but has different custom fields (expected '{new_dict}' but found '{slot_derivations[target_slot]}')"
                        )
                slot_derivations[target_slot] = new_dict
            else:
                # Add the slot derivation for target_slot (populating from source_slot)
                if source_slot not in self.source_schema.class_slots(source_class):
                    raise ValueError(
                        f"Found source slot '{source_slot}' (in source class '{source_class}') in mapping data that does not exist in the source schema, for row:\n{row}"
                    )
                if target_slot in slot_derivations:
                    if "populated_from" not in slot_derivations[target_slot]:
                        raise ValueError(
                            f"Target slot '{target_slot}' in target class '{target_class}' from source class '{source_class}' already exists in slot_derivations but has different populated_from fields (expected source slot '{source_slot}' but found Empty)"
                        )
                    if slot_derivations[target_slot]["populated_from"] != source_slot:
                        raise ValueError(
                            f"Target slot '{target_slot}' in target class '{target_class}' from source class '{source_class}' already exists in slot_derivations but has different populated_from fields (expected source slot '{source_slot}' but found '{slot_derivations[target_slot]['populated_from']}')"
                        )
                if target_slot not in slot_derivations:
                    slot_derivations[target_slot] = {}
                slot_derivations[target_slot].update(
                    {
                        "name": target_slot,
                        "populated_from": source_slot,
                    }
                )
                if slot_derivation_settings:
                    slot_derivations[target_slot].update(slot_derivation_settings)

        return all_class_derivations

    def extract_enum_derivations(
        self, maps_df: pd.DataFrame
    ) -> Dict[str, Dict[str, Dict[str, Dict[str, Dict]]]]:
        """Extract all enum derivations found within the mapping DataFrame.

        Args:
            maps_df (pd.DataFrame): The mapping DataFrame that contains the information for mapping from the
                source to target schemas. This can be either a maps tab, an enums tab, or a wide tab (which have been
                prepared with prepare_maps_df, prepare_enums_df, and prepare_wide_df).

        Raises:
            ValueError: An error occurred due to problems with the mapping data.

        Returns:
            Dict[str, Dict[str, Dict[str, Dict[str, Dict]]]]: A nested dictionary in the form
                return_value[source_class][target_class][source_slot][target_slot] = { enum_derivations }.
                Entries keyed by "" apply to all source/target classes or slots respectively.
                Example:
                        {
                            "nwss": {
                                "protocolSteps": {
                                    "vs_pcr_type": {
                                        "methods[protocolSteps_method]": {
                                            "name": "methods[protocolSteps_method]",
                                            "mirror_source": false,
                                            "populated_from": "vs_pcr_type",
                                            "permissible_value_derivations": { ... }
                                        }
                                    }
                                }
                            },
                            "other_source_class": { ... }
                        }
        """
        if maps_df is None:
            return {}

        # all_enum_derivations[source_class][target_class] are all enum derivations for the source
        # class to the target class.
        # all_enum_derivations[""][""] are all enum derivations where the source class and target class
        # are not specified (ie. applies to all source/target class pairs).
        # Enum derivations where source_class and target_class are specified take precedence over enum
        # derivations where source_class and target_class are "".
        all_enum_derivations: Dict[str, Dict[str, Dict]] = {}
        for _, row in maps_df.iterrows():
            # Get all the row's data
            source_class = row.get(MappingColumns.SOURCE_CLASS, "")
            source_slot = row.get(MappingColumns.SOURCE_SLOT, "")
            source_enum_name = row.get(MappingColumns.SOURCE_ENUM, "")
            source_enum_value = row[MappingColumns.SOURCE_VALUE]
            target_class = row.get(MappingColumns.TARGET_CLASS, "")
            target_slot = row.get(MappingColumns.TARGET_SLOT, "")
            target_enum_name = row.get(MappingColumns.TARGET_ENUM, "")
            target_enum_value = row[MappingColumns.TARGET_VALUE]
            enum_derivation_settings = row.get(
                MappingColumns.ENUM_DERIVATION_SETTINGS, {}
            )
            if pd.isna(enum_derivation_settings):
                enum_derivation_settings = None
            if enum_derivation_settings:
                enum_derivation_settings = yaml.safe_load(enum_derivation_settings)

            variable_match = get_variable_reference(
                target_enum_value,
                format_operations=self.source_slot_format_operations,
            )

            # If variable_match had a match (in the form {{variable_match}}, then it means we copy a source slot to the target slot,
            # so we don't need an enum derivation.
            if variable_match is not None:
                continue

            # Convert NA values to ""
            if pd.isna(source_enum_value):
                source_enum_value = ""
            if pd.isna(target_enum_value):
                target_enum_value = ""

            # If both the source enum value and target enum value are empty then this row is not an enumeration, so continue to next loop
            if source_enum_value == "" and target_enum_value == "":
                continue

            # Replace EMPTY_CONFIG_VALUE with ""
            if source_enum_value == EMPTY_CONFIG_VALUE:
                source_enum_value = ""
            if target_enum_value == EMPTY_CONFIG_VALUE:
                target_enum_value = ""

            # Get source enumeration name (if empty) based on the source class and slot
            if not source_enum_name:
                # Get the source enum name based on the range of the slot (there might be multiple enums for the range)
                source_enum_names = get_enum_names_for_slot(
                    source_class, source_slot, self.source_schema
                )
                if not source_enum_names:
                    raise ValueError(
                        f"Slot is not an enumeration for source class '{source_class}' and source slot '{source_slot}' (source_enum_value='{source_enum_value}', target_class='{target_class}', target_slot='{target_slot}', target_enum_value='{target_enum_value}')"
                    )
                # Find the first source enumeration that contains source_enum_value, use it as the source enum
                source_enum_name = get_enum_name_with_permissible_value(
                    source_enum_names,
                    source_enum_value,
                    self.source_schema,
                    match_ontology_id=self.source_match_ontology_id_regex,
                )
                if not source_enum_name:
                    source_enum_name = source_enum_names[0]
                    logger.error(
                        f"No source enumeration found for {source_class=}, {source_slot=} from slot range(s) {source_enum_names=} that has a permissible {source_enum_value=} ({target_class=}, {target_slot=}). Using source enumeration name '{source_enum_name}'"
                    )

            # Get the target enumeration name based on the target class and slot
            if target_class and target_slot:
                target_enum_names = get_enum_names_for_slot(
                    target_class, target_slot, self.target_schema
                )
                if target_enum_names:
                    target_enum_name = get_enum_name_with_permissible_value(
                        target_enum_names,
                        target_enum_value,
                        self.target_schema,
                        match_ontology_id=self.target_match_ontology_id_regex,
                    )
                    if not target_enum_name:
                        target_enum_name = target_enum_names[0]
                        logger.error(
                            f"No target enumeration found for {target_class=}, {target_slot=} from slot range(s) {target_enum_names=} that has a permissible value {target_enum_value=} ({source_class=}, {source_slot=}). Using target enumeration name '{target_enum_name}' (candidate enumerations: {target_enum_names})"
                        )
                else:
                    # If there is no target enum name (eg. we're mapping from a source slot that is an enum to a target slot that is not an
                    # enum), then we create a unique target enum name to use. Target enum names can be anything, they are just placeholders
                    # (but source enum names must be correct).
                    target_enum_name = f"{target_slot}_from_{source_enum_name}"
            # If no target enum name is given create a fake name
            if not target_enum_name:
                target_enum_name = (
                    f"{self.target_schema.schema.name}_enum_from_{source_enum_name}"
                )
            if not target_enum_name:
                raise ValueError(
                    f"At least one of target enumeration or target class/target slot must be specified for enumeration mapping from source class '{source_class}', source slot '{source_slot}', source enum '{source_enum_name}'"
                )

            # Add an ontology ID to the enum values if the schema has ontology IDs appended to the
            # enum values
            source_enum_value = add_ontoid_to_enum_value(
                self.source_schema,
                source_enum_name,
                source_enum_value,
                match_ontology_id=self.source_match_ontology_id_regex,
            )
            target_enum_value = add_ontoid_to_enum_value(
                self.target_schema,
                target_enum_name,
                target_enum_value,
                match_ontology_id=self.target_match_ontology_id_regex,
            )

            # Get the enum derivations dictionary for the current source_class and target_class and source_enum_name
            if source_class not in all_enum_derivations:
                all_enum_derivations[source_class] = {}
            source_enum_derivations = all_enum_derivations[source_class]
            if target_class not in source_enum_derivations:
                source_enum_derivations[target_class] = {}
            target_enum_derivations = source_enum_derivations[target_class]
            if source_slot not in target_enum_derivations:
                target_enum_derivations[source_slot] = {}
            source_slot_enum_derivations = target_enum_derivations[source_slot]
            if target_slot not in source_slot_enum_derivations:
                source_slot_enum_derivations[target_slot] = {}
            cur_enum_derivations = source_slot_enum_derivations[target_slot]

            # Add the current enum derivation if missing, we'll add the permissible value derivations later
            if target_enum_name not in cur_enum_derivations:
                cur_enum_derivations[target_enum_name] = {
                    "name": target_enum_name,
                    "mirror_source": False,
                    "populated_from": source_enum_name,
                    "permissible_value_derivations": {},
                }
            # Get the enum derivation for the target enum
            enum_derivation = cur_enum_derivations[target_enum_name]
            if enum_derivation["populated_from"] != source_enum_name:
                raise ValueError(
                    f"Enum derivation for {source_class=}, {target_class=}, {target_slot=}, {target_enum_name=} already exists but does not have a matching populated_from field (expected '{source_enum_name}' but found '{enum_derivation['populated_from']}')"
                )

            # Add the derivation settings from the config file (eg. { mirror_source: True })
            if enum_derivation_settings:
                enum_derivation.update(enum_derivation_settings)

            # Add the permissible value derivation. Derivation is from source_enum_value to target_enum_value
            # If there is already a permissible value derivation for target_enum_value, then we add the
            # source_enum_value to the permissible value derivation's "sources" field. If there isn't yet a
            # derivation then we add it to the "populated_from" field. The "sources" array field allows for
            # having multiple populated_from values.
            permissible_value_derivations = enum_derivation[
                "permissible_value_derivations"
            ]
            if target_enum_value in permissible_value_derivations:
                # The target_enum_value already has a derivation.
                # If source_enum_value is equal to the "populated_from" field, then we do nothing
                # Otherwise we move "populated_from" to "sources", and also add source_enum_value to "sources"
                sub_dict = permissible_value_derivations[target_enum_value]
                if (
                    "sources" not in sub_dict
                    and sub_dict["populated_from"] != source_enum_value
                ):
                    sub_dict["sources"] = [sub_dict["populated_from"]]
                    del sub_dict["populated_from"]
                if (
                    "sources" in sub_dict
                    and source_enum_value not in sub_dict["sources"]
                ):
                    sub_dict["sources"].append(source_enum_value)
            else:
                permissible_value_derivations[target_enum_value] = {
                    "name": target_enum_value,
                    "populated_from": source_enum_value,
                }

        return all_enum_derivations

    def prepare_maps_df(self, maps_file: Union[str, Path]) -> pd.DataFrame:
        """Load and prepare the mapping specification file from disk. This DataFrame specifies all
        the mappings other than the wide column mappings (wide columns data is prepared by
        prepare_wide_df).

        Args:
            maps_file (Union[str, Path]): The mapping file to load.

        Returns:
            pd.DataFrame: The loaded and processed mapping data. It will contain the columns found in
                MappingColumns.
        """
        if not maps_file:
            return None

        maps_df = read_data_frame(maps_file, **CONFIG_READ_KWARGS)
        maps_df = strip_whitespace(maps_df)

        # Drop empty rows
        maps_df = maps_df.dropna(axis=0, how="all")

        maps_df = self.drop_incomplete_rows(maps_df)

        # Only use the rows based on the values in the selectors column
        maps_df = self.selector_filter.apply(maps_df, remove_selectors_column=True)

        keep_columns = [
            MappingColumns.SOURCE_CLASS,
            MappingColumns.SOURCE_SLOT,
            MappingColumns.SOURCE_VALUE,
            MappingColumns.TARGET_CLASS,
            MappingColumns.TARGET_SLOT,
            MappingColumns.TARGET_VALUE,
            MappingColumns.TARGET_EXPR,
            MappingColumns.CUSTOM_DATA,
            MappingColumns.ENUM_DERIVATION_SETTINGS,
            MappingColumns.SLOT_DERIVATION_SETTINGS,
        ]
        # Select columns in keep_columns that exist in maps_df
        maps_df = maps_df[[c for c in keep_columns if c in maps_df.columns]]
        # Set columns in keep_columns that do not exist in maps_df to None
        maps_df[[c for c in keep_columns if c not in maps_df.columns]] = None
        # Sort the columns
        maps_df = maps_df[keep_columns]

        # Cleanup source/target slots (eg. replace whitespace with underscores, etc)
        maps_df[MappingColumns.SOURCE_SLOT] = cleanup_slot_name(
            maps_df[MappingColumns.SOURCE_SLOT],
            cleanup_options=self.source_slot_format_operations,
        )
        maps_df[MappingColumns.TARGET_SLOT] = cleanup_slot_name(
            maps_df[MappingColumns.TARGET_SLOT],
            cleanup_options=self.target_slot_format_operations,
        )

        return maps_df.copy()

    def prepare_wide_df(self, wide_file: Union[str, Path]) -> pd.DataFrame:
        """Load and prepare the wide column configuration file from disk. This DataFrame specifies
        all the columns that act as wide columns in the source schema, along with details for how
        to map the wide columns to the target schema. It may also include some additional enum
        mappings required by the wide columns that are not found in the maps sheet.

        Args:
            wide_file (Union[str, Path]): The path to the wide column configuration data.

        Returns:
            pd.DataFrame: The DataFrame with the wide column information. It will contain the columns
                found in MappingColumns, including the wide-specific columns specifying values used
                when pivoting.
        """
        if not wide_file:
            return None

        wide_df = read_data_frame(wide_file, **CONFIG_READ_KWARGS)
        wide_df = strip_whitespace(wide_df)

        # Drop empty rows
        wide_df = wide_df.dropna(axis=0, how="all")

        wide_df = self.drop_incomplete_rows(wide_df)

        # Only use the rows based on the values in the selectors column
        wide_df = self.selector_filter.apply(wide_df, remove_selectors_column=True)

        # Convert SOURCE_SLOT to strings
        wide_df[MappingColumns.SOURCE_SLOT] = wide_df[MappingColumns.SOURCE_SLOT].map(
            lambda x: "" if pd.isna(x) else str(x)
        )

        if MappingColumns.WIDE_OTHER_SLOTS not in wide_df.columns:
            wide_df[MappingColumns.WIDE_OTHER_SLOTS] = None

        # Get rid of NAs in the GROUP column. The pd.groupby function skips NA values, but doesn't
        # skip empty "" values.
        if MappingColumns.WIDE_GROUP in wide_df:
            wide_df[MappingColumns.WIDE_GROUP] = wide_df[MappingColumns.WIDE_GROUP].map(
                lambda x: "" if pd.isna(x) else str(x)
            )
        else:
            wide_df[MappingColumns.WIDE_GROUP] = ""

        # Make sure all required columns are present
        required_columns = [
            MappingColumns.SOURCE_CLASS,
            MappingColumns.SOURCE_SLOT,
            MappingColumns.SOURCE_VALUE,
            MappingColumns.TARGET_CLASS,
            MappingColumns.TARGET_VALUE,
            MappingColumns.ENUM_DERIVATION_SETTINGS,
            MappingColumns.SLOT_DERIVATION_SETTINGS,
        ]
        missing_columns = [c for c in required_columns if c not in wide_df.columns]
        wide_df[missing_columns] = ""

        # Order the columns into a nice order. This isn't necessary but makes it easier to view when debugging.
        wide_df = order_columns(wide_df, required_columns)

        # Cleanup source/target slot names
        if MappingColumns.SOURCE_SLOT in wide_df.columns:
            wide_df[MappingColumns.SOURCE_SLOT] = cleanup_slot_name(
                wide_df[MappingColumns.SOURCE_SLOT],
                cleanup_options=self.source_slot_format_operations,
            )
        if MappingColumns.TARGET_SLOT in wide_df.columns:
            wide_df[MappingColumns.TARGET_SLOT] = cleanup_slot_name(
                wide_df[MappingColumns.TARGET_SLOT],
                cleanup_options=self.target_slot_format_operations,
            )

        return wide_df.copy()

    def drop_incomplete_rows(self, df: pd.DataFrame) -> pd.DataFrame:
        """Drop all rows in the DataFrame where the "Complete" column is not True.

        Args:
            df (pd.DataFrame): The DataFrame to drop incomplete rows from. A copy is made
                and the original DataFrame is left unchanged.

        Returns:
            pd.DataFrame: The DataFrame with incomplete rows removed.
        """
        if "Complete" in df.columns:
            return (
                df[df["Complete"] == 1]
                .drop("Complete", axis="columns")
                .reset_index(drop=True)
            )

        return df.copy()

    def prepare_enums_df(self, enums_file: Union[str, Path]) -> pd.DataFrame:
        """Load and prepare the enums configuration file from disk. This DataFrame specifies enumeration
        mappings from source to target enums (note that enums can also be specified in the maps sheet, via
        prepare_maps_df).

        Args:
            enums_file (Union[str, Path]): The path to the enumeration configuration file.

        Returns:
            pd.DataFrame: The DataFrame with the enums mappings from enums_file.
        """
        if not enums_file:
            return None

        enums_df = read_data_frame(enums_file, **CONFIG_READ_KWARGS)
        enums_df = strip_whitespace(enums_df)

        # Drop empty rows
        enums_df = enums_df.dropna(axis=0, how="all")

        enums_df = self.drop_incomplete_rows(enums_df)

        # Only use the rows based on the values in the selectors column
        enums_df = self.selector_filter.apply(enums_df, remove_selectors_column=True)

        # Keep only relevant columns, and make sure the columns exist
        keep_columns = [
            MappingColumns.SOURCE_CLASS,
            MappingColumns.SOURCE_SLOT,
            MappingColumns.SOURCE_ENUM,
            MappingColumns.SOURCE_VALUE,
            MappingColumns.TARGET_CLASS,
            MappingColumns.TARGET_SLOT,
            MappingColumns.TARGET_ENUM,
            MappingColumns.TARGET_VALUE,
            MappingColumns.ENUM_DERIVATION_SETTINGS,
            MappingColumns.SLOT_DERIVATION_SETTINGS,
        ]
        enums_df[[c for c in keep_columns if c not in enums_df.columns]] = ""
        enums_df = enums_df[keep_columns]

        # Convert entire DataFrame to strings
        enums_df = enums_df.map(lambda x: "" if pd.isna(x) else str(x))

        # Cleanup slot names (eg. replace whitespace with underscores)
        enums_df[MappingColumns.SOURCE_SLOT] = cleanup_slot_name(
            enums_df[MappingColumns.SOURCE_SLOT],
            cleanup_options=self.source_slot_format_operations,
        )
        enums_df[MappingColumns.TARGET_SLOT] = cleanup_slot_name(
            enums_df[MappingColumns.TARGET_SLOT],
            cleanup_options=self.target_slot_format_operations,
        )

        return enums_df.copy()

    def make_wide_derivations(
        self,
        class_derivation: Dict,
        custom_wide_df: pd.DataFrame,
        class_enum_derivations: List[Dict[str, Dict[str, Dict]]],
    ) -> List[Dict]:
        """Based on the provided class derivation, make a separate class derivation for each wide column specified
        in custom_wide_df. We will also select all the enum derivations required by the new wide derivations from
        class_enum_derivations.

        Args:
            class_derivation (Dict): The class derivation that acts as the template for all wide derivations.
            custom_wide_df (pd.DataFrame): The DataFrame containing the wide column information.
            class_enum_derivations (List[Dict[str, Dict[str, Dict]]]): All known enum derivations. For each element in
                the list, the first key is the source class name, second key is the target class name, all sub-values
                are the actual enum derivations. An enum_derivation later in the list takes precedence of an
                enum_derivation earlier in the list (ie. if there are multiple derivations with the same
                populated_from field).
                enum_derivation[""][""] are all enum derivations with no source and target class name specified
                (eg from the enums tab), these apply to all source and target classes.
                For a given enum_derivation item, if a source enum exists at both class_enum_derivations[source_class][target_class]
                and at class_enum_derivations[""][""] then the former one takes precedence.
                For any enumeration in the resulting class derivations that is not found in class_enum_derivations we will create a
                new enum derivation where we simply copy values from the source  enum to the target enum.

        Returns:
            List[Dict]: A list of dictionaries containing all the new derivations. The dictionary has the
                following keys: "source_class", "target_class", "class_derivation", and "enum_derivations".
                "class_derivation" contains the actual class derivation recognized by the Mapper,
                and "enum_derivations" has all the enum derivations required by the class derivation. Example:
                    [
                        {
                            "source_class": "nwss",
                            "target_class": "protocolSteps[000,0002=extraction_method]",
                            "undecorated_target_class": "protocolSteps",
                            "class_derivation": {
                                "name": "protocolSteps[000,0002=extraction_method]",
                                "populated_from": "nwss",
                                "slot_derivations": {
                                    "reflink": {
                                        "name": "reflink",
                                        "populated_from": "lod_ref"
                                    },
                                    ...
                                },
                            "enum_derivations": {
                                "vs_yne[ext_blank]": {
                                    "name": "vs_yne[ext_blank]",
                                    "mirror_source": false,
                                    "populated_from": "vs_yne[ext_blank]",
                                    "permissible_values": { ... },
                                },
                                ...
                            }
                        },
                        ...
                    ]

        """
        source_class_name = class_derivation["populated_from"]
        target_class_name = class_derivation["name"]

        results = []
        # for idx, (_, group_df) in enumerate(custom_wide_df.groupby([MappingColumns.SOURCE_CLASS, MappingColumns.SOURCE_SLOT, MappingColumns.TARGET_CLASS, MappingColumns.WIDE_GROUP])):
        # Get source class and target class
        source_class = custom_wide_df[MappingColumns.SOURCE_CLASS].iloc[0]
        target_class = custom_wide_df[MappingColumns.TARGET_CLASS].iloc[0]

        # Extract enum derivations from the group. It is in the form group_enum_derivations[source_class][target_class] = { derivations }.
        group_enum_derivations = self.extract_enum_derivations(custom_wide_df)

        # Extract the wide-to-long data. We only use the first row of the group, since the others are identical other than
        # for the enum derivations.
        custom_wide_df = custom_wide_df.iloc[[0]].copy()

        # Set the columns in the OTHER_SLOTS field. It is a JSON dictionary of column:value pairs
        other_slots = custom_wide_df[MappingColumns.WIDE_OTHER_SLOTS].iloc[0]
        if other_slots and isinstance(other_slots, str):
            other_slots = json.loads(other_slots)
            custom_wide_df[list(other_slots.keys())] = list(other_slots.values())

        # Keep source class, target class, and all columns that are wide target slots or wide expr slots
        keep_columns = [
            MappingColumns.SOURCE_CLASS,
            MappingColumns.TARGET_CLASS,
            MappingColumns.ENUM_DERIVATION_SETTINGS,
            MappingColumns.SLOT_DERIVATION_SETTINGS,
        ]
        keep_columns = keep_columns + [
            c
            for c in custom_wide_df.columns
            if c not in keep_columns
            and (is_wide_target_value_slot(c) or is_wide_target_expr_slot(c))
        ]
        custom_wide_df = custom_wide_df[keep_columns]

        # Pivot the group to long format, keeping id_columns constant for all rows.
        # The pivoted table has a TARGET_VALUE column specifying either the constant value to set or the source slot to copy from (eg. {{slotName}})
        # as well as an TARGET_EXPR column specifying LinkML expression code to execute for calculating the value of the target slot.
        # We create the pivoted tables form TARGET_VALUEs and TARGET_EXPRs separated, then concatenate them together
        id_columns = [
            MappingColumns.SOURCE_CLASS,
            MappingColumns.TARGET_CLASS,
            MappingColumns.ENUM_DERIVATION_SETTINGS,
            MappingColumns.SLOT_DERIVATION_SETTINGS,
        ]
        wide_target_columns = [
            c for c in custom_wide_df.columns if is_wide_target_value_slot(c)
        ]
        wide_target_df = custom_wide_df.melt(
            id_vars=id_columns,
            value_vars=wide_target_columns,
            var_name=MappingColumns.TARGET_SLOT,
            value_name=MappingColumns.TARGET_VALUE,
            ignore_index=False,
        )
        # Drop the _value rows that have an empty value
        wide_target_df = wide_target_df[
            ~pd.isna(wide_target_df[MappingColumns.TARGET_VALUE])
            | (wide_target_df[MappingColumns.TARGET_VALUE] == "")
        ]
        # Replace <empty> with blank string
        wide_target_df[MappingColumns.TARGET_VALUE] = wide_target_df[
            MappingColumns.TARGET_VALUE
        ].map(lambda x: "" if x == EMPTY_CONFIG_VALUE else x)

        wide_expr_columns = [
            c for c in custom_wide_df.columns if is_wide_target_expr_slot(c)
        ]
        wide_expr_df = custom_wide_df.melt(
            id_vars=id_columns,
            value_vars=wide_expr_columns,
            var_name=MappingColumns.TARGET_SLOT,
            value_name=MappingColumns.TARGET_EXPR,
            ignore_index=False,
        )

        # Drop _expr rows that have an empty expression
        wide_expr_df = wide_expr_df[
            ~pd.isna(wide_expr_df[MappingColumns.TARGET_EXPR])
            | (wide_expr_df[MappingColumns.TARGET_EXPR] == "")
        ]

        # Combine wide_target_df and wide_expr_df, sort by index
        custom_wide_df = pd.concat([wide_target_df, wide_expr_df]).sort_index(
            kind="stable"
        )

        # Get the wide target slot names by trimming of the suffixes (eg. remove _target or _expr)
        custom_wide_df[MappingColumns.TARGET_SLOT] = custom_wide_df[
            MappingColumns.TARGET_SLOT
        ].map(any_wide_slot_name)

        # ROW_NUMBER is all the same, since group_df provides all the information for outputing a single row (we do one output
        # row at a time)
        custom_wide_df[MappingColumns.WIDE_ROW_NUMBER] = 0

        # Create the derivations for pivoting the single column defined by custom_wide_df
        cur_results = expand_wide_derivations(
            source_class_name=source_class_name,
            target_class_name=target_class_name,
            slot_derivations=class_derivation["slot_derivations"],
            custom_wide_dfs=custom_wide_df,
            source_schema=self.source_schema,
            target_schema=self.target_schema,
            source_slot_format_operations=self.source_slot_format_operations,
            target_slot_format_operations=self.target_slot_format_operations,
        )

        # Add the enum derivations for each of the expanded class derivations
        cur_enum_derivations = list(class_enum_derivations)
        cur_enum_derivations.append(group_enum_derivations)
        for results_dict in cur_results:
            results_enum_derivations = select_required_enum_derivations(
                source_class,
                target_class,
                results_dict["class_derivation"],
                cur_enum_derivations,
                schema=self.source_schema,
            )
            results_dict["enum_derivations"] = results_enum_derivations
        results.extend(cur_results)

        return results

    def merge_enum_derivations(self, enum_derivations: List[Dict]) -> Dict:
        """Merge a list of enum derivations into a single enum derivations dictionary, where the keys are the target
        enum name and the values are the derivations.
        Each populated_from field in the merged derivations is unique. If more than one enum derivation exists
        with the same populated_from field in the enum_derivations parameter, then the one later in the list takes
        precedence and overwrites any previous ones.

        Args:
            derivations (List[Dict]): List of all enum derivations. These are in the form:
                {
                    "target_enum_name" : {
                        "name" : target_enum_name,
                        "populated_from" : source_enum_name,
                        "permissible_value_derivations" : { ... }
                    },
                    "other_target_enum_name" : { ... },
                    ...
                }

        Returns:
            Dict: Dictionary of merged enum derivations.
        """
        results = {}
        for cur_derivations in enum_derivations:
            for k, v in cur_derivations.items():
                # Get all the derivations in results that have the same populated_from field.
                populated_from = v["populated_from"]
                key_matches = [
                    k
                    for k, v in results.items()
                    if v["populated_from"] == populated_from
                ]
                if len(key_matches) > 1:
                    raise RuntimeError(
                        f"Found {len(key_matches)} existing enum derivations for populated_from value='{populated_from}'"
                    )
                elif len(key_matches) == 1:
                    # A derivation for v["populated_from"] already exists in results, so delete it
                    # del(results[key_matches[0]])
                    raise ValueError(
                        f"Enum derivation with populated_from='{populated_from}' already exists, can only have one enum derivation per populated_from"
                    )
                # Add the current derivation
                results[k] = v

        return results

    def get_class_enum_derivations(
        self, source_class: str, target_class: str, class_enum_derivations: List[Dict]
    ) -> Dict:
        """Retrieve all enum derivations that involve mapping from the source_class to target_class from
        class_enum_derivations, and merge them by calling merge_enum_derivations. This can be run on the value
        returned by extract_enum_derivations, which is a dictionary with a top-level key being the source class
        and the second-level key being the target class. The dictionaries nested within the second-level key
        are the actual enum derivations (that apply to the source to target class mappings). That is,
        all enum derivations at class_enum_derivations[i][source_class][target_class] are the ones we're
        interested in, and the anum derivations at class_enum_derivations[i][""][""] also apply to all source
        to target class derivations.

        Args:
            source_class (str): The source class.
            target_class (str): The target class.
            class_enum_derivations (List[Dict]): List of all class enum derivations, where each item
                is a dict and where item[source_class][target_class] = { enum_derivations } where the
                enum_derivations are specific to mapping from a source class slot to a target class
                slot. Also, item[""][""] are also enum derivations that apply to ANY source class to
                ANY target class (so these are also returned).

        Returns:
            Dict: Dictionary of merged enum derivations involving slots from the source_class to target_class.
        """
        group = []
        for cur_derivations in class_enum_derivations:
            # Get the derivations in cur_derivations[""][""]
            d = cur_derivations.get("", {}).get("", {})
            if len(d) > 0:
                group.append(d)
            # Get the derivations in cur_derivations[source_class][""]
            if source_class:
                d = cur_derivations.get(source_class, {}).get("", {})
                if len(d) > 0:
                    group.append(d)
            # Get the derivations in cur_derivations[""][target_class]
            if target_class:
                d = cur_derivations.get("", {}).get(target_class, {})
                if len(d) > 0:
                    group.append(d)
            # Get the derivations in cur_derivations[source_class][target_class]
            if source_class and target_class:
                d = cur_derivations.get(source_class, {}).get(target_class, {})
                if len(d) > 0:
                    group.append(d)
        # Merge the list of derivations into a single derivation
        return self.merge_enum_derivations(group)

    def save_schema_definition(
        self, schema: SchemaDefinition, output_file: Union[str, Path]
    ):
        """Save the schema to disk as a LinkML YAML schema file.

        Args:
            schema (SchemaDefinition): The SchemaDefinition to save to disk.
            output_file (Union[str, Path]): The YAML file to save to.
        """
        schema_dict = schema_as_dict(schema)

        if os.path.dirname(output_file):
            os.makedirs(os.path.dirname(output_file), exist_ok=True)
        with open(output_file, "w") as f:
            f.write(yaml.dump(schema_dict, sort_keys=False))
        logger.info(f"LinkML schema saved to '{output_file}'")
