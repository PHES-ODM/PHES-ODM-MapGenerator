# %%
""" """

import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

import argparse
import re
from pathlib import Path
from typing import Union, List, Tuple, Dict
import yaml
import pandas as pd

from linkml_runtime import SchemaView

from utils.general_utils import get_class_name_from_file_name, TREE_ROOT_CLASS_NAME
from utils.mapper_utils import MappingColumns, get_logger, get_variable_reference

logger = get_logger(__name__)


class DataKeys:
    CLASS_DERIVATIONS = "class_derivations"
    ENUM_DERIVATIONS = "enum_derivations"
    GLOBAL_ENUM_DERIVATIONS = "enums"
    WIDE_DERIVATIONS = "wide_derivations"

    DATA_FRAME = "df"

    UNNAMED_INPUT_FILE = "unnamed_input_file"


def unquoted_string(s: str) -> bool:
    noquote_s = s
    if noquote_s and noquote_s.startswith("'"):
        noquote_s = re.sub(r"^'([^']*)'$", r"\1", noquote_s)
    elif noquote_s and noquote_s.startswith('"'):
        noquote_s = re.sub(r'^"([^"]*)"$', r"\1", noquote_s)
    if not pd.isna(noquote_s) and noquote_s != s:
        return noquote_s
    return None


class YAMLtoXLSXMapper(object):
    def __init__(
        self,
        source_dir: Union[str, Path],
        source_schema: Union[str, Path],
        target_schema: Union[str, Path],
        output_dir: Union[str, Path],
    ):
        self.source_schema = SchemaView(source_schema)
        self.target_schema = SchemaView(target_schema)
        self.source_dir = Path(source_dir)
        self.output_dir = Path(output_dir)

        self.data = {}

    def drop_topbottom_blank_rows(self, df: pd.DataFrame) -> pd.DataFrame:
        """Remove blank rows from top and bottom of DataFrame."""
        for top in [True, False]:
            if len(df.index) == 0:
                break
            if top:
                idx = df.index[0]
            else:
                idx = df.index[-1]
            if len([c for c in df.columns if not pd.isna(df.loc[idx, c])]) == 0:
                df = df.drop(idx, axis=0)
        return df.reset_index(drop=True)

    def get_input_file_data(
        self, input_data: Union[str, Path, Dict]
    ) -> Tuple[Dict, Dict, Dict]:
        if not isinstance(input_data, dict):
            if input_data not in self.data:
                self.data[input_data] = {}
            input_file_data = self.data[input_data]
        else:
            input_file_data = input_data
        if DataKeys.CLASS_DERIVATIONS not in input_file_data:
            input_file_data[DataKeys.CLASS_DERIVATIONS] = {}
        class_derivations_data = input_file_data[DataKeys.CLASS_DERIVATIONS]
        if DataKeys.ENUM_DERIVATIONS not in input_file_data:
            input_file_data[DataKeys.ENUM_DERIVATIONS] = {}
        enum_derivations_data = input_file_data[DataKeys.ENUM_DERIVATIONS]
        if DataKeys.WIDE_DERIVATIONS not in input_file_data:
            input_file_data[DataKeys.WIDE_DERIVATIONS] = {}
        wide_derivations_data = input_file_data[DataKeys.WIDE_DERIVATIONS]

        return (
            input_file_data,
            class_derivations_data,
            enum_derivations_data,
            wide_derivations_data,
        )

    def get_all_dfs(self, input_file_data_key: str, wide: bool) -> Dict:
        # Key is the input_file value is Dict where key is target class, values are DataFrames.
        all_class_df = {}
        # Key is the input file, value is Dict where key is target enum, values are Dict of form Dict[source_enum][DataKeys.DATA_FRAME]
        all_enums = {}
        for input_file, input_file_data in self.data.items():
            enum_derivations_data = input_file_data[DataKeys.ENUM_DERIVATIONS]
            for target_class, target_class_derivations in input_file_data[
                input_file_data_key
            ].items():
                is_wide = get_class_name_from_file_name(target_class) != target_class
                if is_wide != wide:
                    continue
                for (
                    source_class,
                    source_class_derivations,
                ) in target_class_derivations.items():
                    for (
                        target_enum_name,
                        target_enum_data,
                    ) in enum_derivations_data.items():
                        if target_enum_name not in all_enums:
                            all_enums[target_enum_name] = {}
                        cur_all_enums = all_enums[target_enum_name]
                        existing_target_enums = set(
                            target_enum_data.keys()
                        ).intersection(set(cur_all_enums.keys()))
                        existing_target_enums = list(existing_target_enums)
                        if len(existing_target_enums) > 0:
                            raise ValueError(
                                f"Enum derivations already exists for {source_class=}, {target_class=}, {target_enum_name=} for source enums: {existing_target_enums}"
                            )
                        cur_all_enums.update(target_enum_data)

                    class_df = source_class_derivations[DataKeys.DATA_FRAME]

                    # Concatenate the DataFrame to the DataFrame for target_class
                    cleaned_target_class = get_class_name_from_file_name(target_class)
                    if cleaned_target_class not in all_class_df:
                        all_class_df[cleaned_target_class] = []
                    cur = all_class_df[cleaned_target_class]

                    cur.append(class_df)

        # Sort alphabetically by target class (which is the dictionary key)
        all_class_df = dict(sorted(all_class_df.items()))
        # Sort the DataFrames for each target class by the source class
        all_class_df = {
            k: sorted(v, key=lambda x: x.loc[0, MappingColumns.SOURCE_CLASS])
            for k, v in all_class_df.items()
        }
        # Combine the DataFrames for each target class into a single DataFrame
        all_class_df = {
            k: self.concat_with_blank_rows(v, insert_row_separators=not wide)
            for k, v in all_class_df.items()
        }
        return all_class_df, all_enums

    def insert_enum_derivations(
        self, df: pd.DataFrame, input_file_data: Dict
    ) -> pd.DataFrame:
        # Insert enum derivations into the class derivations
        # for input_file, input_file_data in self.data.items():
        #     enum_derivations_data = input_file_data[DataKeys.ENUM_DERIVATIONS]
        #     class_derivations_data = input_file_data[DataKeys.CLASS_DERIVATIONS]

        df = df.copy()
        enum_derivations_data = input_file_data[DataKeys.ENUM_DERIVATIONS]

        # Add enum derivations to all the slot derivations that require enum mappings, or if an enum derivation must be assigned to
        # multiple slot derivations, create a separate global "enums" tab
        for target_enum, target_enum_derivations in enum_derivations_data.items():
            for source_enum, source_enum_derivations in target_enum_derivations.items():
                cur_enum_df = source_enum_derivations[DataKeys.DATA_FRAME]
                if len(cur_enum_df.index) == 0:
                    continue

                # Go through all source class/slot combinations. If the class/slot has a range equal to source_enum,
                # then it requires the enum derivations.
                groupby = df.groupby(
                    [MappingColumns.SOURCE_CLASS, MappingColumns.SOURCE_SLOT]
                )
                for _, group_df in groupby:
                    enum_source_class = group_df[MappingColumns.SOURCE_CLASS].iloc[0]
                    enum_source_slot = group_df[MappingColumns.SOURCE_SLOT].iloc[0]
                    enum_target_class = group_df[MappingColumns.TARGET_CLASS].iloc[0]
                    enum_target_slot = group_df[MappingColumns.TARGET_SLOT].iloc[0]

                    class_defn = self.source_schema.get_class(enum_source_class)
                    slot_defn = class_defn.slot_usage.get(enum_source_slot)
                    if slot_defn is None:
                        raise ValueError(
                            f"Slot {enum_source_slot=} does not exist in class {enum_source_class=}"
                        )
                    if slot_defn.range != source_enum:
                        continue

                    has_multi = len(group_df.index) > 1
                    if has_multi:
                        # There are multiple slots that use this enum mapping, so add the mapping to the global enums DataFrame
                        if DataKeys.GLOBAL_ENUM_DERIVATIONS not in input_file_data:
                            input_file_data[DataKeys.GLOBAL_ENUM_DERIVATIONS] = (
                                pd.DataFrame()
                            )
                        enums_df = input_file_data[DataKeys.GLOBAL_ENUM_DERIVATIONS]
                        enums_df = self.concat_with_blank_rows([enums_df, cur_enum_df])
                        input_file_data[DataKeys.GLOBAL_ENUM_DERIVATIONS] = enums_df
                    else:
                        # Add enum mappings to the class derivation's DataFrame
                        cur_enum_df = cur_enum_df.copy()
                        cur_enum_df[MappingColumns.SOURCE_CLASS] = enum_source_class
                        cur_enum_df[MappingColumns.SOURCE_SLOT] = enum_source_slot
                        cur_enum_df[MappingColumns.TARGET_CLASS] = enum_target_class
                        cur_enum_df[MappingColumns.TARGET_SLOT] = enum_target_slot
                        cur_enum_df = cur_enum_df[
                            [
                                c
                                for c in cur_enum_df.columns
                                if c not in [MappingColumns.SOURCE_ENUM]
                            ]
                        ]

                        existing_rows = df[
                            (df[MappingColumns.SOURCE_CLASS] == enum_source_class)
                            & (df[MappingColumns.SOURCE_SLOT] == enum_source_slot)
                            & (df[MappingColumns.TARGET_CLASS] == enum_target_class)
                            & (df[MappingColumns.TARGET_SLOT] == enum_target_slot)
                        ]

                        if len(existing_rows.index) != 1:
                            raise ValueError(
                                f"Only one matching row should be found, instead {len(existing_rows.index)} found: {enum_source_class=}, {enum_source_slot=}, {enum_target_class=}, {enum_target_slot=}"
                            )

                        target_index = existing_rows.index[0]

                        # Remove the row at target_index, and replace it with cur_enum_df
                        pre_df = df.iloc[0:target_index]
                        post_df = df.iloc[target_index + 1 :]
                        # Drop blank rows at end of pre_df and start of post_df
                        df = self.concat_with_blank_rows([pre_df, cur_enum_df, post_df])

                        # Order the columns
                        column_order = [
                            getattr(MappingColumns, c)
                            for c in vars(MappingColumns)
                            if not c.startswith("_")
                        ]
                        column_order = column_order + [
                            c for c in df.columns if c not in column_order
                        ]
                        df = df[[c for c in column_order if c in df.columns]]

        return df

    def convert(self):
        if self.output_dir:
            os.makedirs(self.output_dir, exist_ok=True)

        input_files = [
            self.source_dir / f
            for f in os.listdir(self.source_dir)
            if os.path.splitext(f)[1] == ".yaml"
        ]

        # Loop through all input files
        for input_file in input_files:
            logger.info(f"Processing mapper file {input_file}")
            with open(input_file, "r") as f:
                current_yaml = yaml.safe_load(f)

            (
                input_file_data,
                class_derivations_data,
                enum_derivations_data,
                wide_derivations_data,
            ) = self.get_input_file_data(input_file)

            # Load class derivations in input YAML file
            for target_class, class_derivation in current_yaml.get(
                "class_derivations", {}
            ).items():
                if target_class == TREE_ROOT_CLASS_NAME:
                    continue

                # Prepare the current data
                source_class = class_derivation["populated_from"]
                if target_class not in class_derivations_data:
                    class_derivations_data[target_class] = {}
                target_class_data = class_derivations_data[target_class]
                if source_class not in target_class_data:
                    target_class_data[source_class] = {}
                cur_data = target_class_data[source_class]

                logger.info(f"Creating mapping from {source_class} to {target_class}")

                df = pd.DataFrame()

                # Add all the rows from the slot_derivations
                for target_slot, slot_derivation in class_derivation.get(
                    "slot_derivations", {}
                ).items():
                    populated_from = slot_derivation.get("populated_from", None)
                    expr = slot_derivation.get("expr", None)
                    if expr in ["''", '""']:
                        expr = None

                    row = pd.DataFrame(
                        {
                            MappingColumns.SOURCE_CLASS: source_class,
                            MappingColumns.SOURCE_SLOT: populated_from,
                            MappingColumns.SOURCE_VALUE: None,
                            MappingColumns.TARGET_CLASS: target_class,
                            MappingColumns.TARGET_SLOT: target_slot,
                            MappingColumns.TARGET_VALUE: "{{%s}}" % populated_from
                            if populated_from
                            else None,
                            MappingColumns.TARGET_EXPR: expr,
                            MappingColumns.CUSTOM_DATA: None,
                        },
                        index=[len(df.index)],
                    )
                    df = pd.concat([df, row])

                # Sort by target slot
                df = df.sort_values(MappingColumns.TARGET_SLOT).reset_index(drop=True)
                cur_data[DataKeys.DATA_FRAME] = df

            # For any wide mappings, pivot the data to include the {slot_name}_value and {slot_name}_expr columns.
            # We know a file is for a wide mapping when the file name is of the form 'target_class[extra_text].csv
            for target_class, target_class_derivations in input_file_data[
                DataKeys.CLASS_DERIVATIONS
            ].items():
                for (
                    source_class,
                    source_class_derivations,
                ) in target_class_derivations.items():
                    if get_class_name_from_file_name(target_class) != target_class:
                        # Convert to wide
                        # cleaned_target_class = get_class_name_from_file_name(cleaned_target_class)
                        class_df = source_class_derivations[DataKeys.DATA_FRAME]
                        class_df = self.convert_to_wide(class_df)

                        if target_class not in wide_derivations_data:
                            wide_derivations_data[target_class] = {}
                        target_class_wide_derivations = wide_derivations_data[
                            target_class
                        ]
                        if source_class not in target_class_wide_derivations:
                            target_class_wide_derivations[source_class] = {}
                        source_class_wide_derivations = target_class_wide_derivations[
                            source_class
                        ]
                        if DataKeys.DATA_FRAME not in source_class_wide_derivations:
                            source_class_wide_derivations[DataKeys.DATA_FRAME] = (
                                pd.DataFrame()
                            )
                        wide_df = source_class_wide_derivations[DataKeys.DATA_FRAME]
                        wide_df = pd.concat([wide_df, class_df]).reset_index(drop=True)
                        source_class_wide_derivations[DataKeys.DATA_FRAME] = wide_df

            # Load enum derivations
            for target_enum, enum_derivation in current_yaml.get(
                "enum_derivations", {}
            ).items():
                source_enum = enum_derivation["populated_from"]

                df = pd.DataFrame()

                # Add all permissible value derivations
                for (
                    target_enum_value,
                    permissible_value_derivation,
                ) in enum_derivation.get("permissible_value_derivations", {}).items():
                    source_enum_value = permissible_value_derivation.get(
                        "populated_from", None
                    )
                    sources = permissible_value_derivation.get("sources", None)
                    source_enum_values = []
                    if source_enum_value is not None:
                        source_enum_values.append(source_enum_value)
                    if sources is not None:
                        source_enum_values.extend(sources)
                    # Remove duplicate sources
                    source_enum_values = list(dict.fromkeys(source_enum_values))
                    for val in source_enum_values:
                        row = pd.DataFrame(
                            {
                                MappingColumns.SOURCE_ENUM: source_enum,
                                MappingColumns.SOURCE_VALUE: val,
                                MappingColumns.TARGET_VALUE: target_enum_value,
                            },
                            index=[len(df.index)],
                        )
                        df = pd.concat([df, row])

                if target_enum not in enum_derivations_data:
                    enum_derivations_data[target_enum] = {}
                target_enum_data = enum_derivations_data[target_enum]
                target_enum_data[source_enum] = {}
                source_enum_data = target_enum_data[source_enum]
                source_enum_data[DataKeys.DATA_FRAME] = df

        # # For all wide mapping DataFrames, split off the _value and _expr columns where all
        # # values are constant
        # for input_file, input_file_data in self.data.items():
        #     enum_derivations_data = input_file_data[DataKeys.ENUM_DERIVATIONS]
        #     wide_derivations_data = input_file_data[DataKeys.WIDE_DERIVATIONS]
        #     for target_class, target_class_wide_derivations in wide_derivations_data.items():
        #         for source_class, source_class_wide_derivations in target_class_wide_derivations.items():
        #             # source_class = wide_df.loc[0, MappingColumns.SOURCE_CLASS]
        #             wide_df = source_class_wide_derivations[DataKeys.DATA_FRAME]
        #             wide_df, map_df = self.separate_wide_df(wide_df)
        #             source_class_wide_derivations[DataKeys.DATA_FRAME] = wide_df

        #             # if map_df is not None and len(map_df.index) > 0:
        #             #     if DataKeys.UNNAMED_INPUT_FILE not in self.data:
        #             #         self.data[DataKeys.UNNAMED_INPUT_FILE] = {}
        #             #     input_file_data = self.data[DataKeys.UNNAMED_INPUT_FILE]

        #             #     if DataKeys.CLASS_DERIVATIONS not in input_file_data:
        #             #         input_file_data[DataKeys.CLASS_DERIVATIONS] = {}
        #             #     class_derivations_data = input_file_data[DataKeys.CLASS_DERIVATIONS]

        #             #     if DataKeys.ENUM_DERIVATIONS not in input_file_data:
        #             #         input_file_data[DataKeys.ENUM_DERIVATIONS] = {}
        #             #     enum_derivations_data = input_file_data[DataKeys.ENUM_DERIVATIONS]

        #             #     if target_class not in class_derivations_data:
        #             #         class_derivations_data[target_class] = {}
        #             #     target_class_data = class_derivations_data[target_class]
        #             #     if source_class not in target_class_data:
        #             #         target_class_data[source_class] = {}
        #             #     cur_data = target_class_data[source_class]

        #             #     if DataKeys.DATA_FRAME not in cur_data:
        #             #         cur_data[DataKeys.DATA_FRAME] = pd.DataFrame()
        #             #     df = cur_data[DataKeys.DATA_FRAME]
        #             #     df = pd.concat([df, map_df]).sort_values([MappingColumns.TARGET_CLASS, MappingColumns.TARGET_SLOT])
        #             #     df = df.reset_index(drop=True)
        #             #     cur_data[DataKeys.DATA_FRAME] = df

        # Insert enum derivations
        for input_file, input_file_data in self.data.items():
            for input_file_data_key in [
                DataKeys.CLASS_DERIVATIONS,
                DataKeys.WIDE_DERIVATIONS,
            ]:
                for target_class, target_class_derivations in input_file_data[
                    input_file_data_key
                ].items():
                    for (
                        source_class,
                        source_class_derivations,
                    ) in target_class_derivations.items():
                        # Add enumerations
                        class_df = source_class_derivations[DataKeys.DATA_FRAME]
                        class_df = self.insert_enum_derivations(
                            class_df, input_file_data
                        )
                        source_class_derivations[DataKeys.DATA_FRAME] = class_df

        writer = pd.ExcelWriter(os.path.join(self.output_dir, "mapping_config.xlsx"))

        # Save all class derivations (that aren't wide derivations)
        all_class_dfs, all_enums = self.get_all_dfs(
            DataKeys.CLASS_DERIVATIONS, wide=False
        )
        for target_class, df in all_class_dfs.items():
            df.to_excel(writer, sheet_name=target_class, index=False)

        # Save all wide derivations
        all_class_dfs, all_enums = self.get_all_dfs(
            DataKeys.WIDE_DERIVATIONS, wide=True
        )
        for target_class, df in all_class_dfs.items():
            df.to_excel(writer, sheet_name=f"wide_{target_class}", index=False)

        # Save all enums
        all_enums_df = pd.DataFrame()
        for input_file, input_file_data in self.data.items():
            # Save the enums
            cur_df = input_file_data.get(DataKeys.GLOBAL_ENUM_DERIVATIONS)
            if cur_df is not None:
                all_enums_df = self.concat_with_blank_rows([all_enums_df, cur_df])
        if len(all_enums_df.index):
            all_enums_df.to_excel(writer, sheet_name="enums", index=False)

        writer.close()

        logger.info("Finished!")

    def concat_with_blank_rows(
        self, dfs: List[pd.DataFrame], insert_row_separators: bool = True
    ) -> pd.DataFrame:
        """Concatenate all DataFrames, adding a single blank row between them. We will also trim
        off leading and trailing blank rows in each of the individual DataFrames before concatenating.
        """
        new_dfs = []
        for df in dfs:
            df = self.drop_topbottom_blank_rows(df)
            if len(df.index) == 0:
                continue
            if insert_row_separators and len(new_dfs) > 0:
                new_dfs.append(
                    pd.DataFrame({c: None for c in new_dfs[0].columns}, index=[0])
                )
            new_dfs.append(df)
        return pd.concat(new_dfs).reset_index(drop=True)

    def convert_to_wide(self, df: pd.DataFrame) -> pd.DataFrame:
        # If sourceSlot is not None: Create column {targetSlot}_value, with value equal to {{sourceSlot}}
        # If sourceSlot is None and targetExpr is of the form 'str' or "str": Create {targetSlot}_value == str
        # If sourceSlot is None:     Create column {targetSlot}_expr, with value equal to targetExpr
        source_class = df.loc[0, MappingColumns.SOURCE_CLASS]
        target_class = get_class_name_from_file_name(
            df.loc[0, MappingColumns.TARGET_CLASS]
        )
        wide_df = pd.DataFrame(
            {
                MappingColumns.SOURCE_CLASS: source_class,
                MappingColumns.SOURCE_SLOT: None,
                MappingColumns.SOURCE_VALUE: None,
                MappingColumns.TARGET_CLASS: target_class,
                MappingColumns.TARGET_VALUE: None,
            },
            index=[0],
        )

        use_source_slot = None
        df = df.dropna(how="all")
        for _, row in df.iterrows():
            target_expr = row[MappingColumns.TARGET_EXPR]
            source_slot = row[MappingColumns.SOURCE_SLOT]
            target_slot = row[MappingColumns.TARGET_SLOT]

            if not pd.isna(source_slot):
                wide_df[f"{target_slot}_value"] = "{{%s}}" % source_slot
                use_source_slot = source_slot
            else:
                if target_expr in ["'NA'", '"NA"']:
                    target_expr = "''"
                noquote_expr = unquoted_string(target_expr)
                if isinstance(noquote_expr, str):
                    wide_df[f"{target_slot}_value"] = noquote_expr
                elif target_expr is not None:
                    wide_df[f"{target_slot}_expr"] = target_expr

        if "value_value" in wide_df.columns:
            use_source_slot = wide_df.loc[0, "value_value"].strip("{}")

        wide_df[MappingColumns.SOURCE_SLOT] = use_source_slot

        return wide_df

    def separate_wide_df(
        self, wide_df: pd.DataFrame
    ) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """_summary_

        Args:
            wide_df (pd.DataFrame): _description_

        Returns:
            Tuple[pd.DataFrame, pd.DataFrame]: _description_
        """
        # For _value or _expr slots where all values are constant:
        # For {target_slot}_value: If in format {{source_slot}}, then assign source_slot to sourceSlot column
        #                          Otherwise add quotes and assign to targetExpr column
        # For {target_slot}_expr: Assign to targetExpr column
        value_columns = [c for c in wide_df.columns if c.endswith("_value")]
        value_columns = [(c, c.split("_value")[0]) for c in value_columns]
        expr_columns = [c for c in wide_df.columns if c.endswith("_expr")]
        expr_columns = [(c, c.split("_expr")[0]) for c in expr_columns]

        map_df = pd.DataFrame()

        source_class = wide_df.loc[0, MappingColumns.SOURCE_CLASS]
        target_class = wide_df.loc[0, MappingColumns.TARGET_CLASS]
        for col, target_slot in value_columns + expr_columns:
            values = set(wide_df[col])
            print(col, values)
            if len(values) != 1:
                continue

            value = list(values)[0]
            source_slot = get_variable_reference(
                value, schema=None, format_operations=None
            )
            if col.endswith("_value") and source_slot:
                row = pd.DataFrame(
                    {
                        MappingColumns.SOURCE_CLASS: source_class,
                        MappingColumns.SOURCE_SLOT: source_slot,
                        MappingColumns.TARGET_CLASS: target_class,
                        MappingColumns.TARGET_SLOT: target_slot,
                        MappingColumns.TARGET_VALUE: "{{%s}}" % source_slot,
                    },
                    index=[0],
                )
                map_df = pd.concat([map_df, row]).reset_index(drop=True)
            elif col.endswith("_value"):
                row = pd.DataFrame(
                    {
                        MappingColumns.SOURCE_CLASS: source_class,
                        MappingColumns.SOURCE_SLOT: None,
                        MappingColumns.TARGET_CLASS: target_class,
                        MappingColumns.TARGET_SLOT: target_slot,
                        MappingColumns.TARGET_EXPR: f"'{value}'",
                    },
                    index=[0],
                )
            elif col.endswith("_expr"):
                row = pd.DataFrame(
                    {
                        MappingColumns.SOURCE_CLASS: source_class,
                        MappingColumns.SOURCE_SLOT: None,
                        MappingColumns.TARGET_CLASS: target_class,
                        MappingColumns.TARGET_SLOT: target_slot,
                        MappingColumns.TARGET_EXPR: value,
                    },
                    index=[0],
                )

            # Add the new row to map_df
            map_df = pd.concat([map_df, row])
            # Drop the column from wide_df
            wide_df = wide_df.drop(col, axis=1)

        if len(map_df.index) > 0:
            map_df = map_df.sort_values(
                [MappingColumns.TARGET_CLASS, MappingColumns.TARGET_SLOT]
            )
            map_df = map_df.reset_index(drop=True)

        return wide_df, map_df if len(map_df.index) > 0 else None


if __name__ == "__main__":
    if "get_ipython" in globals():

        class opts:
            # ODM v1 to v2
            source_dir = "../../gen/odm_v1_to_v2/mappers"
            source_schema = "../data/odm_v1/linkml/odm_v1.yaml"
            target_schema = "../data/odm_v2/linkml/odm_v2.yaml"
            output_dir = "../../gen/odm_v1_to_v2/xlsx_mappers_from_yaml"

            # NWSS to ODM v2
            # source_dir = "../../gen/nwss_reporting_to_v2/mappers"
            # source_schema = "../../gen/nwss_reporting_to_v2/linkml_for_mapping/nwss_reporting.yaml"
            # target_schema = "../data/odm_v2/linkml/odm_v2.yaml"
            # output_dir = "../../gen/nwss_reporting_to_v2/xlsx_mappers_from_yaml"
    else:
        args = argparse.ArgumentParser(
            formatter_class=argparse.ArgumentDefaultsHelpFormatter
        )
        args.add_argument(
            "--source_dir",
            type=str,
            help="Directory where all YAML LinkML-Map mappers are located, to convert to CSV format.",
            required=True,
        )
        args.add_argument(
            "--source_schema",
            type=str,
            help="LinkML schema for the source dataset.",
            required=True,
        )
        args.add_argument(
            "--target_schema",
            type=str,
            help="LinkML schema for the target dataset.",
            required=True,
        )
        args.add_argument(
            "--output_dir",
            type=str,
            help="Directory to save the CSV mappers to.",
            required=True,
        )
        opts = args.parse_args()

    mapper = YAMLtoXLSXMapper(
        opts.source_dir, opts.source_schema, opts.target_schema, opts.output_dir
    )
    mapper.convert()
