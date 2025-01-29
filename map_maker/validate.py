# %%

import typer
from collections import Counter
from typing import Any, Optional, Iterator, Union, Annotated
from pathlib import Path
from abc import ABC, abstractmethod
import csv
import sys
import os

from linkml.validator import Validator
from linkml.validator.loaders import Loader
from linkml.validator.plugins.jsonschema_validation_plugin import (
    JsonschemaValidationPlugin,
)
from linkml_runtime import SchemaView
from linkml.validator.report import Severity

from utils.general_utils import parse_numeric, get_logger
from utils.schema_utils import get_ranges_of_slot

logger = get_logger(__name__)

app = typer.Typer(
    pretty_exceptions_show_locals=False,
    rich_markup_mode="rich",
)

MAIN_HELP = """Run LinkML validator on some data."""

SCHEMA_HELP = """The schema the data belongs to."""

SOURCE_CLASS_HELP = """The class in the schema that the data is for."""

DATA_SOURCE_HELP = """The data file to validate."""

MAX_ERRORS_HELP = """The maximum number of errors to report before exiting. If
                  0 then show all errors without exiting."""


def _parse_value(value: Any, cls: str, slot: str, schema: SchemaView) -> Any:
    """Parse the value, as found in a table/class named cls, according to the format it should
    be in for the specified slot and schema.

    Args:
        value (Any): The value to parse.
        cls (str): The class (table) that the value belongs to.
        slot (str): The slot (column) in the table that the value belongs to.
        schema (SchemaView): The SchemaView of the table, which is where we retrieve the format
            that the value should be in for the given class and slot.

    Returns:
        Any: The parsed value. If the range of the slot is a string or enum then we cast the
            value to a string. Otherwise we try to cast to an integer or float. If we can't cast
            then the value is returned unchanged.
    """
    # Get the range and cast to string if range is "string" or an enum
    ranges = get_ranges_of_slot(cls, slot, schema)

    if ranges:
        for rng in ranges:
            # Test if rng is an enum or "string", if it is then return the value as a string
            if rng == "string" or rng in schema.all_enums():
                return str(value)

    # Try to cast to an integer or float
    return parse_numeric(value)


class LoaderWithSchema(Loader, ABC):
    """ """

    def __init__(
        self,
        source: Union[str, Path],
        source_schema: Union[str, Path],
        source_class: str,
        *,
        skip_empty_rows: bool = False,
        index_slot_name: Optional[str] = None,
    ) -> None:
        """Initializer for LoaderWithSchema. LoaderWithSchema is an abstract base class that loads a data file
        one row at a time and casts the columns to the appropriate type according to a schema and class.

        Derived classes should override the delimiter property, which specifies the delimeter used for the
        data source.

        Args:
            source (Union[str, Path]): The file to load the data from.
            source_schema (Union[str, Path]): The source schema the data is for.
            source_class (str): The class that the data is from.
            skip_empty_rows (bool, optional): If True then skip empty rows found in the data source. Defaults to False.
            index_slot_name (Optional[str], optional): If specified then all data are loaded at once as
                a list of dictionaries and assigned to a top-level dictionary with a key equal to
                index_slot_name and a value equal to the rows. Defaults to None.
        """
        super().__init__(source)
        self.skip_empty_rows = skip_empty_rows
        self.index_slot_name = index_slot_name
        self.schema = SchemaView(source_schema)
        self.source_class = source_class

    def _rows(self) -> Iterator[dict]:
        """Iterate over all rows one at a time. Values are parsed according to the type they should be in
        and empty rows are skipped if skip_empty_rows was True in the constructor.

        Yields:
            Iterator[dict]: A single row.
        """
        with open(self.source) as file:
            reader: csv.DictReader = csv.DictReader(
                file, delimiter=self.delimiter, skipinitialspace=True
            )
            for row in reader:
                if self.skip_empty_rows and not any(row.values()):
                    continue
                yield {
                    k: _parse_value(v, self.source_class, k, self.schema)
                    for k, v in row.items()
                    if k is not None and v != ""
                }

    def iter_instances(self) -> Iterator[dict]:
        """Iterate over all rows or return the full data all once as a single dictionary where the key
        is the index_slot_name (specified from the constructor) and the value is the list of all rows.

        Yields:
            Iterator[dict]: A dictionary, either a single row or all rows at once.
        """
        if self.index_slot_name is not None:
            yield {self.index_slot_name: list(self._rows())}
        else:
            yield from self._rows()

    @property
    @abstractmethod
    def delimiter(self): ...


class CsvLoaderWithSchema(LoaderWithSchema):
    @property
    def delimiter(self):
        return ","


class TsvLoaderWithSchema(LoaderWithSchema):
    @property
    def delimiter(self):
        return "\t"


def loader_from_file(
    data_source: Union[str, Path], *args, **kwargs
) -> LoaderWithSchema:
    """Construct the correct LoaderWithSchema-derived class according to the file extension of the
    data_source, and prepare the loader to load the data. The LoaderWithSchema-derived class will
    ensure that the correct delimiter is used (ie. comma-separated or tab-separated).

    For **kwargs source_schema and source_class are required, and skip_empty_rows is optional.

    Args:
        data_source (Union[str, Path]): The data file to load.

    Raises:
        ValueError: No LoaderWithSchema-derived class exists for the extension found in data_source.

    Returns:
        LoaderWithSchema: A LoaderWithSchema-derived object initialized with the data_source.
    """
    ext = os.path.splitext(data_source)[1].lower()
    if ext == ".csv":
        return CsvLoaderWithSchema(data_source, *args, **kwargs)
    elif ext in [".tsv", ".txt"]:
        return TsvLoaderWithSchema(data_source, *args, **kwargs)
    else:
        raise ValueError(f"No LoaderWithSchema for file {data_source}")


@app.command(help=MAIN_HELP)
def main(
    schema: Annotated[str, typer.Option(show_default=False, help=SCHEMA_HELP)],
    source_class: Annotated[
        str, typer.Option(show_default=False, help=SOURCE_CLASS_HELP)
    ],
    data_source: Annotated[
        str, typer.Option(show_default=False, help=DATA_SOURCE_HELP)
    ],
    max_errors: int = typer.Option(default=0),
):
    """Run LinkML validator on some data.

    Args:
        schema (str): The schema the data belongs to.
        source_class (str): The class in the schema that the data is for.
        data_source (str): The data file to validate.
        max_errors (int): The maximum number of errors to report before exiting. If 0 then show all
            errors without exiting. Defaults to 0.
    """
    strict = False

    plugins = [JsonschemaValidationPlugin(closed=True)]
    loader = loader_from_file(
        data_source,
        source_schema=schema,
        source_class=source_class,
        skip_empty_rows=True,
    )
    validator = Validator(schema, validation_plugins=plugins, strict=strict)

    severity_counter = Counter()
    for idx, result in enumerate(
        validator.iter_results_from_source(loader, source_class)
    ):
        severity_counter[result.severity] += 1
        print(
            f"[{result.severity.value}] [{loader.source}/{result.instance_index}] {result.message}"
        )
        if max_errors and idx + 1 >= max_errors:
            break

    if sum(severity_counter.values()) == 0:
        logger.info("No issues found")

    if "get_ipython" not in globals():
        # Exit with or without error
        exit_code = 1 if severity_counter[Severity.ERROR] > 0 else 0
        sys.exit(exit_code)

    print(severity_counter)


if __name__ == "__main__":
    if "get_ipython" in globals():
        opts = {
            # "schema": "data/nwss_restricted_analytics/linkml/nwss_restricted_analytics.yaml",
            "schema": "data/nwss_reporting/linkml/nwss_reporting.yaml",
            "source_class": "nwss",
            "data_source": "../../../PHES-ODM-Data/nwss/nwss_renamed/nwss[cdc-nwss-restricted-dataset-wastewater-20240730].csv",
            "max_errors": 500,
        }

        main(**opts)
    else:
        app()
