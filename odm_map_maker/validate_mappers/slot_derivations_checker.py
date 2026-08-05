import os
import re
from abc import abstractmethod
from pathlib import Path
from typing import Annotated

import typer
import yaml
from linkml_map.datamodel.transformer_model import SlotDerivation
from linkml_runtime import SchemaView
from linkml_runtime.linkml_model.meta import SlotDefinition

from odm_map_maker.utils.general_utils import (
    TREE_ROOT_CLASS_NAME,
    get_class_name_from_file_name,
)
from odm_map_maker.utils.logger import get_logger, make_logger_bullet_list
from odm_map_maker.utils.mapper_utils import ENUM_MAPPED_EXPR_GLOBALS
from odm_map_maker.utils.schema_utils import get_ranges_of_slot, get_ranges_of_slot_defn

logger = get_logger(__name__)

# Allowable namespaces in LinkML-Map expr blocks. Names preceded by these (plus a dot) are variables
# eg. src.collection_device. These are used by SlotDerivationChecker.extract_vars to extract all
# slot/variable references in expr code. This is the source namespace ("src") plus all the globals
# whose source slots are enum mapped, so that adding a global to ENUM_MAPPED_EXPR_GLOBALS also makes
# it an allowable namespace here. dict.fromkeys removes any duplicates while preserving the order.
EXPR_NAME_SPACES = list(dict.fromkeys(["src"] + ENUM_MAPPED_EXPR_GLOBALS))

app = typer.Typer(
    pretty_exceptions_show_locals=False,
    rich_markup_mode="rich",
)

CHECKER_HELP_ITEMS = make_logger_bullet_list(
    [
        """[bold]multi_to_single[/bold]: Look for instances where a multi-valued slot
in the source dataset is mapped to a single-valued slot in the target dataset.
This can lead to problems, as the target slot might take on multiple values
when only a single value is allowed.""",
        """[bold]free_text_to_enum[/bold]: Look for instances where a free-text slot in
the source dataset is mapped to an enumeration slot in the target dataset. This
can lead to problems, as the free-text source can be any value, whereas the
enum target must match pre-defined values.""",
    ],
    bullet="- ",
    end="\n\n",
    indent=4,
)

MAIN_HELP = """Check for possible errors or important characteristics of slot derivations
in LinkML-Map schemas."""

CHECKER_HELP = f"""The type of check to run. Can be:
multi_to_single: Look for instances where a multi-valued slot in the source
dataset is mapped to a single-valued slot in the target dataset. This can lead
to problems, as the target slot might take on multiple values when only a
single value is allowed.

{CHECKER_HELP_ITEMS}
"""

MAPPER_DIR_HELP = """The directory containing the LinkML-Map YAML schemas. All YAML files are checked."""

SOURCE_SCHEMA_HELP = """The LinkML schema for the source dataset of the mappers."""

TARGET_SCHEMA_HELP = """The LinkML schema for the target dataset of the mappers."""


class SlotDerivationChecker:
    def __init__(
        self,
        mapper_dir: str | Path,
        source_schema: str | Path,
        target_schema: str | Path,
    ):
        self.mapper_dir = Path(mapper_dir)
        self.source_schema = SchemaView(source_schema)
        self.target_schema = SchemaView(target_schema)

    def check_all(self):
        self.errors = []
        self.warnings = []
        files = [
            self.mapper_dir / f
            for f in os.listdir(self.mapper_dir)
            if os.path.splitext(f)[1] == ".yaml"
        ]
        if not files:
            logger.warning(f"No mapper YAML files found in {self.mapper_dir}")
        for file in files:
            self.check_file(file)
        self.show_logs()

    def set_current_file(self, current_file: Path):
        self._current_file = current_file
        self.errors_added = False
        self.warnings_added = False

    def add_error(self, msg: str):
        if not self.errors_added:
            self.errors_added = True
            self.errors.append(f"Error(s) in {self._current_file!s}")
        self.errors.append(msg)

    def add_warning(self, msg: str):
        if not self.warnings_added:
            self.warnings_added = True
            self.warnings.append(f"Warnings(s) in {self._current_file!s}")
        self.warnings.append(msg)

    def extract_vars(self, expr: str) -> list[str]:
        vars = []
        for ns in EXPR_NAME_SPACES:
            pat = f"(?<![A-Za-z0-9_\\.]){ns}\\.([A-Za-z_]([A-Za-z0-9_]*))(?![A-Za-z0-9_\\.])"
            res = re.findall(pat, expr)
            if res:
                for match in res:
                    vars.append(match[0])
        return list(dict.fromkeys(vars))

    def check_file(self, file: str | Path):
        self.set_current_file(file)

        with open(file, "r") as f:
            mapper = yaml.safe_load(f)

        for target_class_name, class_derivation in mapper["class_derivations"].items():
            if target_class_name == TREE_ROOT_CLASS_NAME:
                continue

            source_class_name = get_class_name_from_file_name(
                class_derivation["populated_from"], self.source_schema
            )
            target_class_name = get_class_name_from_file_name(
                target_class_name, self.target_schema
            )
            for target_slot_name, slot_derivation in class_derivation[
                "slot_derivations"
            ].items():
                # _extra_ slots are ignored
                if target_slot_name.startswith("_extra_"):
                    # logger.info(f"Skipping slot {target_class_name}.{target_slot_name}")
                    continue

                # Get the source slot ranges
                source_slot_name = slot_derivation.get("populated_from", None)
                source_slot_defn = None
                source_ranges = []
                if source_slot_name:
                    # Found "populated_from" in the slot_derivation, so get the ranges of the source slot
                    source_slot_defn = self.source_schema.induced_slot(
                        source_slot_name, source_class_name
                    )
                    source_ranges = get_ranges_of_slot_defn(source_slot_defn)

                # Get the target ranges
                target_slot_defn = self.target_schema.induced_slot(
                    target_slot_name, target_class_name
                )
                target_ranges = get_ranges_of_slot_defn(target_slot_defn)

                self.check_derivation(
                    slot_derivation,
                    source_class_name,
                    target_class_name,
                    source_slot_name,
                    target_slot_name,
                    source_slot_defn,
                    target_slot_defn,
                    source_ranges,
                    target_ranges,
                )

    def show_logs(self):
        for log, log_func in (
            (self.warnings, logger.warning),
            (self.errors, logger.error),
        ):
            for msg in log:
                log_func(msg)

    @abstractmethod
    def check_derivation(
        self,
        slot_derivation: SlotDerivation,
        source_class_name: str,
        target_class_name: str,
        source_slot_name: str,
        target_slot_name: str,
        source_slot_defn: SlotDefinition,
        target_slot_defn: SlotDefinition,
        source_ranges: list[str],
        target_ranges: list[str],
    ): ...


class FreeTextToEnumChecker(SlotDerivationChecker):
    """Check for slot derivations where we map from free text to an enumeration. We typically do not want to have free text to
    an enumeration since the mapped free text will likely not take on a valid enumeration value. In this case we would want
    to map the free text onto a different slot that also accepts free text, such as a notes field.
    """

    def check_derivation(
        self,
        slot_derivation: SlotDerivation,
        source_class_name: str,
        target_class_name: str,
        source_slot_name: str,
        target_slot_name: str,
        source_slot_defn: SlotDefinition,
        target_slot_defn: SlotDefinition,
        source_ranges: list[str],
        target_ranges: list[str],
    ):
        extra_error_info = ""

        expr = None
        if not source_slot_name:
            # No "populated_from" in slot_derivation, extract the variables from the custom "expr" code
            expr = slot_derivation["expr"]
            extra_error_info = f":\n{expr}"
            source_slot_name = self.extract_vars(expr)
            source_ranges = get_ranges_of_slot(
                source_class_name, source_slot_name, self.source_schema
            )

        # Find all source and target ranges that are NOT enums. We assume that these ranges are free-text
        source_string_ranges = [
            r for r in source_ranges if self.range_is_not_enum(r, self.source_schema)
        ]
        target_string_ranges = [
            r for r in target_ranges if self.range_is_not_enum(r, self.target_schema)
        ]

        # If the source slot can be free text, but the target slot is not (ie. it is one or more enums) then
        # we report an error.
        if len(source_string_ranges) > 0 and len(target_string_ranges) == 0:
            self.add_error(
                f"Mapping from free-text to enum: {source_class_name}.{source_slot_name if source_slot_name else '<expr>'} to {target_class_name}.{target_slot_name}{extra_error_info}"
            )

    def range_is_not_enum(self, rng: str, schema: SchemaView) -> bool:
        enum_defn = schema.get_enum(rng)
        return enum_defn is None


class MultiToSingleSlotChecker(SlotDerivationChecker):
    """Check for slot derivations where a source slot that is multivalued is mapped to a target slot that is single-valued.

    If cases are found, it may be necessary to expand the target slot, either by splitting the row into multiple identical
    rows with each row having a different value from the array in the target slot, or simply converting arrays with size 1 into
    a non-array version (eg. convert ["Myval"] to "Myval").

    Splitting arrays of size greater than 1 into multiple rows might not be desirable, since it would then duplicate the primary
    key. We may want to expand these rows before ID generation, rather than afterward.
    """

    def check_derivation(
        self,
        slot_derivation: SlotDerivation,
        source_class_name: str,
        target_class_name: str,
        source_slot_name: str,
        target_slot_name: str,
        source_slot_defn: SlotDefinition,
        target_slot_defn: SlotDefinition,
        source_ranges: list[str],
        target_ranges: list[str],
    ):
        expr = None
        if not source_slot_name:
            # No "populated_from" in slot_derivation, extract the variables from the custom "expr" code
            expr = slot_derivation["expr"]
            source_slot_name = self.extract_vars(expr)

        if isinstance(source_slot_name, str):
            source_slot_name = [source_slot_name]
        if isinstance(target_slot_name, str):
            target_slot_name = [target_slot_name]

        def _is_multivalued(
            slots: list[str], class_name: str, schema: SchemaView
        ) -> bool:
            for slot in slots:
                slot_defn = schema.induced_slot(slot, class_name)
                if slot_defn.multivalued:
                    return True
            return False

        is_source_multivalued = _is_multivalued(
            source_slot_name, source_class_name, self.source_schema
        )
        is_target_multivalued = _is_multivalued(
            target_slot_name, target_class_name, self.target_schema
        )

        if is_source_multivalued and not is_target_multivalued:

            def _make_slots_str(slots: list[str]) -> str:
                if len(slots) == 1:
                    return slots[0]
                else:
                    return "[" + ", ".join(slots) + "]"

            self.add_error(
                f"Found mapping from multi-valued source to single-valued target (from {'expr' if expr else 'populated_from'} block): {source_class_name}.{_make_slots_str(source_slot_name)} -> {target_class_name}.{_make_slots_str(target_slot_name)}"
            )


CHECKER_CLASSES = {
    "free_text_to_enum": FreeTextToEnumChecker,
    "multi_to_single": MultiToSingleSlotChecker,
}


@app.command(help=MAIN_HELP)
def main(
    checker: Annotated[str, typer.Option(show_default=False, help=CHECKER_HELP)],
    mapper_dir: Annotated[Path, typer.Option(show_default=False, help=MAPPER_DIR_HELP)],
    source_schema: Annotated[
        Path, typer.Option(show_default=False, help=SOURCE_SCHEMA_HELP)
    ],
    target_schema: Annotated[
        Path, typer.Option(show_default=False, help=TARGET_SCHEMA_HELP)
    ],
):
    if checker not in CHECKER_CLASSES:
        raise ValueError(
            f"Specified checker '{checker}' does not exist. Acceptable values are: {', '.join(CHECKER_CLASSES)}"
        )
    checker = CHECKER_CLASSES[checker](mapper_dir, source_schema, target_schema)
    checker.check_all()


if __name__ == "__main__":
    app()
