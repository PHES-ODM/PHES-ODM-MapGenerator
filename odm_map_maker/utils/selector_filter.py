"""
# SelectorFilter Class

This class is used for filtering rows in a DataFrame based on selectors.
Selectors can either be a flag (eg. "amr"), or a versioned module (eg.
"odm>=3.0"). For multiple selectors, separate them by a comma (eg.
"amr,odm>=3.0").

A versioned module can be included in a row to make sure we drop any rows that
are for an incompatible version (eg. if we want to use a different row for ODM
v2 vs ODM v3), whereas a flag selector is used to only include or exclude rows
based on the presence or absence of that flag. Exclude selectors are preceded
by an exclamation mark (eg. "!deprecated").

When constructing a SelectorFilter, a set of selectors is specified that we
call "constructor selectors", and these constructor selectors are used by
comparing them to the selectors specified in the `selectors` column of the
DataFrame.

The `selectors` column can have three types of selectors:

1. *Include flags*: These are flags that do not start with "!" and do not have
   a version specifier (eg. "amr", "b", etc).
2. *Exclude flags*: These are flags that start with "!" and do not have a
   version specifier (eg. "!deprecated", "!d", etc).
3. *Versioned modules*: These are module selectors that have a module name and
   a version specifier (eg. "odm>=3.0", "odm<3.0", etc).

A row in a mapping configuration file is always retained if the `selector`
column for that row is blank.

If the `selector` column is not blank, then a row is removed/retained according
to the following rules (using the example table below):

| row_num | selectors          |
|---------|--------------------|
|    0    | amr                |
|    1    | !deprecated        |
|    2    | a                  |
|    3    | a, b               |
|    4    | !d                 |
|    5    | odm>=3.0           |
|    6    | odm<3.0            |
|    7    | odm>=3.0, odm<=3.1 |

1. If a row has include flags then at least one of them must be in the
   constructor include flags. For example, if the constructor includes the
   flags "b,c", then row_num=0 and row_num=2 are dropped, while all other rows
   are retained. If the constructor has no include flags, then row_num=0,
   row_num=2, and row_num=3 are all dropped, while all other rows are retained.
2. If an exclude flag is specified to the constructor (eg. "!amr") and the row
   has that flag (eg. "amr"), then the row is dropped. For example, if "!amr"
   is provided to the constructor then row_num=0 is dropped.
3. If a row has an exclude flag (eg. "!deprecated") and the constructor
   includes that flag (eg. "deprecated"), then the row is dropped. For example,
   if the flag "deprecated" is provided to the constructor then row_num=1 is
   removed (also, row_num=0, 2, and 3 are also dropped, according to rule 1
   above).
4. A module version number can be specified to the constructor, in the format
   "module=version" (eg. odm=3). If a row has one or more module version
   selectors (eg. "odm>=3.0"), then the row is retained only if the constructor
   version agrees with all the row versions. If the row has a module version
   but no version is specified to the constructor for that module, then the row
   is dropped. For example, if "odm=3" is specified to the constructor, then
   row_num=5 and row_num=7 are retained but row_num=6 is removed (all other
   rows are retained). As another example, if "odm=3.2" is specified to the
   constructor, then row_num=5 is retained but row_num=6 and row_num=7 are
   removed (all other rows are retained). If now version for "odm" is specified
   in the constructor, then all of row_num=5, 6, and 7 are dropped. The
   allowable version specifiers in the `selectors` column are: ==, !=, >=, <=,
   >, <, ~= (see [Version Specifiers in the Python Packaging
   guide](https://packaging.python.org/en/latest/specifications/version-specifiers/#id5)).

## Usage

```python
from odm_map_maker.utils.selector_filter import SelectorFilter

sf = SelectorFilter(selectors=["!deprecated", "odm=3.0.0"],
selector_column="selectors") filtered_df = sf.apply(df,
remove_selectors_column=False)
```
"""

from typing import List, Any, Tuple, Dict, Union
import pandas as pd
from packaging.specifiers import SpecifierSet
from packaging.version import parse as parse_version
import re


class SelectorTypes:
    """These are keys into the a SelectorFilter's self.selectors_dict dictionary, that specifies the global selectors
    to apply to all of a DataFrame's rows.
    """

    INCLUDE = "include"
    EXCLUDE = "exclude"
    MODULE_VERSION = "module_version"


class SelectorFilter:
    def __init__(self, selectors: Union[str, List, Tuple], selector_column: str):
        self.selectors_dict = self._gather_selectors(
            selectors, equals_version_only=True
        )
        self.selector_column = selector_column

    def _parse_selector(self, s: str, equals_version_only: bool) -> Any:
        """Parse the single specified selector value and return the selector type (from SelectorTypes) and the
        root selector value.

        Args:
            s (str): The string to parse as a selector.
            equals_version_only (bool): If True, then if the selector is for a module and version (eg. odm>=3.0) then
                only allow "=" as the version specifier. If False, then allow other version specifiers (eg. odm>=3.0). An
                exception is raised if equals_version_only is True and a non-equals version specifier is used.
                Version specifiers allowed if equals_version_only=False are: ==, !=, <, <=, >, >=, ~= (See PEP 440 for
                more details).

        Raises:
            ValueError: If equals_version_only is True but a non-equals version specifier is used (eg. odm>=3.0), then an
                exception is raised.

        Returns:
            Any: The selector type (from SelectorTypes) and the root selector value. The selector value is either
                a string (for SelectorKeys.INCLUDE/SelectorKeys.EXCLUDE selector types) or a tuple of the form
                (module, version) for SelectorKeys.MODULE_VERSION selector type. For SelectorKeys.EXCLUDE types,
                the string will not have the leading "!" (eg. If the passed in s="!amr", then (SelectorTypes.EXCLUDE, "amr")
                is returned).
        """
        if not s or not s.strip():
            return None, None
        s = s.strip()
        if equals_version_only:
            if "=" in s:
                # Only one equals sign is allowed if equals_version_only=True
                if s.count("=") != 1:
                    raise ValueError(f"Version selector must have one equal sign: {s}")
                # Get the module and version (ie. s is of the form "module=version")
                s = s.split("=")
                module = s[0].strip()
                version = s[1].strip()
                return SelectorTypes.MODULE_VERSION, (module, version)
        else:
            # Split off the module and version specifier. The version specifier includes both
            # the operator and the version number (eg. ">=3.0.0").
            res = re.match(r"([A-Za-z0-9_]+)\s*([<>=!~]+)(\s*)([\d\.]+)", s)
            if res is not None and len(res.groups()) == 4:
                module = res.groups()[0]
                version = "%s%s" % (res.groups()[1], res.groups()[3])
                return SelectorTypes.MODULE_VERSION, (module, version)

        # EXCLUDE selectors are preceded by "!"
        if s.startswith("!"):
            s = s.lstrip("!").strip()
            return SelectorTypes.EXCLUDE, s

        return SelectorTypes.INCLUDE, s

    def _gather_selectors(self, selectors: Any, equals_version_only: bool) -> Dict:
        """From the specified selectors (which can be a string, list or tuple), gather the selectors
        into a dictionary where the keys are the selector types (from SelectorTypes) and the values
        are lists of the selector values.

        The selector value can be a flag string (for SelectorKeys.INCLUDE/SelectorKeys.EXCLUDE selector types, for
        example "amr" or "!amr"), or a tuple of the form (module, version) for SelectorKeys.MODULE_VERSION selector types.
        The version string can be a version specifier (eg. ">=3.0.0"). If equals_version_only is True then only exact
        version matches are allowed (eg. "=3.0.0").

        For example, if selectors = "amr,!deprecated,odm>=3.0.0" then the returned dictionary will be:

            {
                SelectorKeys.INCLUDE: ["amr"],
                SelectorKeys.EXCLUDE: ["deprecated"],
                SelectorKeys.MODULE_VERSION: [("odm", ">=3.0.0")]
            }

        Args:
            selectors (Any): Either a list of strings, with each string being a different selector, or a single comma-separated
                string of multiple selectors.
            equals_version_only (bool): If True, then for selectors that specify a module and a version (eg. "odm=3"), then
                only allow "=" as the version specifier. If False, then allow other version specifiers (eg. "odm>=3"). An
                exception is raised if equals_version_only is True and a non-equals version specifier is used.

        Returns:
            Dict: A dictionary where the keys are the selector types (from SelectorTypes) and the values are lists of the
                selector values.
        """
        if not isinstance(selectors, (list, tuple)):
            # If selectors is empty then return empty dict
            if pd.isna(selectors) or not selectors:
                return {}
            # Split comma-separated string into list
            if not isinstance(selectors, str):
                selectors = str(selectors)
            selectors = selectors.split(",")

        # Expand all selectors that have a comma in it (ie. "amr,deprecated" becomes two seperate selectors
        # named "amr" and "deprecated")
        new_selectors = []
        for s in selectors:
            new_selectors.extend(s.split(","))
        selectors = new_selectors

        # Go through each selector and parse it and add it to selectors_dict
        selectors_dict = {}
        for s in selectors:
            # Get the selector type (from SelectorTypes) and the selector value
            # The selector value is either a string (for SelectorKeys.INCLUDE/SelectorKeys.EXCLUDE selector types)
            # or a tuple of the form (module, version) for SelectorKeys.MODULE_VERSION selector type. The version
            # string can be a version specifier (eg. ">=3.0.0"). If equals_version_only is True then only exact
            # version matches are allowed (eg. "=3.0.0").
            selector_type, selector_value = self._parse_selector(
                s, equals_version_only=equals_version_only
            )
            if selector_type:
                if selector_type not in selectors_dict:
                    selectors_dict[selector_type] = []
                selectors_dict[selector_type].append(selector_value)

        return selectors_dict

    def _seletors_pass(self, selectors: Dict, row_selectors: Dict) -> bool:
        """Determine if the row (with the specified row_selectors) passes the selector test based on the
        given selectors. If a row passes the test then it is included in the output, if it isn't then it
        is filtered out.

        Args:
            selectors (Dict): The selectors used to test against the row selectors. This is usually the
                selectors provided to the SelectorFilter instance constructor.
            row_selectors (Dict): The selectors associated with the row being tested.

        Returns:
            bool: True if the row passes the selector test and should therefore be included in the
                final filtered DataFrame, False otherwise.
        """
        exclude_selectors = selectors.get(SelectorTypes.EXCLUDE, [])
        include_selectors = selectors.get(SelectorTypes.INCLUDE, [])
        row_exclude_selectors = row_selectors.get(SelectorTypes.EXCLUDE, [])
        row_include_selectors = row_selectors.get(SelectorTypes.INCLUDE, [])

        # If an exclude_selector is found in the row then fail
        if len([s for s in exclude_selectors if s in row_include_selectors]) > 0:
            return False

        # If a row_exclude_selector is found in include_selectors then fail
        if len([s for s in row_exclude_selectors if s in include_selectors]) > 0:
            return False

        # If the row has row_include_selectors, then at least one of them must be in include_selectors
        if (
            row_include_selectors
            and len([s for s in include_selectors if s in row_include_selectors]) == 0
        ):
            return False

        # Check module version selectors
        module_version_selectors = selectors.get(SelectorTypes.MODULE_VERSION, [])
        row_module_version_selectors = row_selectors.get(
            SelectorTypes.MODULE_VERSION, []
        )
        for row_mod, row_ver in row_module_version_selectors:
            # Check to see if the module is in the constructor selectors, if it is
            # not then fail
            matching_mudule_selectors = [
                m for m in module_version_selectors if m[0] == row_mod
            ]
            if not matching_mudule_selectors:
                return False
            else:
                # Make sure the row module version passes all the versions
                # specified in matching_module_selectors
                for _, ver in matching_mudule_selectors:
                    spec_set = SpecifierSet(row_ver)
                    if parse_version(ver) not in spec_set:
                        return False
        return True

    def apply(
        self, df: pd.DataFrame, remove_selectors_column: bool = False
    ) -> pd.DataFrame:
        """Apply selectors to the DataFrame, dropping rows where the selectors do not match properly.

        A row in a mapping configuration file is always retained if the `selector`
        column for that row is blank.

        If the `selector` column is not blank, then a row is removed/retained according
        to the following rules (using the example table below):

        | row_num | selectors          |
        |---------|--------------------|
        |    0    | amr                |
        |    1    | !deprecated        |
        |    2    | a                  |
        |    3    | a, b               |
        |    4    | !d                 |
        |    5    | odm>=3.0           |
        |    6    | odm<3.0            |
        |    7    | odm>=3.0, odm<=3.1 |

        1. If a row has include flags then at least one of them must be in the
        constructor include flags. For example, if the constructor includes the
        flags "b,c", then row_num=0 and row_num=2 are dropped, while all other rows
        are retained. If the constructor has no include flags, then row_num=0,
        row_num=2, and row_num=3 are all dropped, while all other rows are retained.
        2. If an exclude flag is specified to the constructor (eg. "!amr") and the row
        has that flag (eg. "amr"), then the row is dropped. For example, if "!amr"
        is provided to the constructor then row_num=0 is dropped.
        3. If a row has an exclude flag (eg. "!deprecated") and the constructor
        includes that flag (eg. "deprecated"), then the row is dropped. For example,
        if the flag "deprecated" is provided to the constructor then row_num=1 is
        removed (also, row_num=0, 2, and 3 are also dropped, according to rule 1
        above).
        4. A module version number can be specified to the constructor, in the format
        "module=version" (eg. odm=3). If a row has one or more module version
        selectors (eg. "odm>=3.0"), then the row is retained only if the constructor
        version agrees with all the row versions. If the row has a module version
        but no version is specified to the constructor for that module, then the row
        is dropped. For example, if "odm=3" is specified to the constructor, then
        row_num=5 and row_num=7 are retained but row_num=6 is removed (all other
        rows are retained). As another example, if "odm=3.2" is specified to the
        constructor, then row_num=5 is retained but row_num=6 and row_num=7 are
        removed (all other rows are retained). If now version for "odm" is specified
        in the constructor, then all of row_num=5, 6, and 7 are dropped. The
        allowable version specifiers in the `selectors` column are: ==, !=, >=, <=,
        >, <, ~= (see [Version Specifiers in the Python Packaging
        guide](https://packaging.python.org/en/latest/specifications/version-specifiers/#id5)).

        Args:
            df (pd.DataFrame): The DataFrame to drop rows from based on the selectors parameter. A copy of this
                DataFrame is made and the original is left unchanged.
            selectors (Optional[List[str]]): The selectors specifying which rows to retain or drop.
            remove_selectors_column (bool): If True then remove the selectors column from the returned DataFrame.
                Defaults to False.

        Returns:
            pd.DataFrame: The DataFrame with rows dropped according to the rules described above.
        """
        df = df.copy()
        if len(df) > 0:
            # Make sure the selector column exists
            if self.selector_column not in df.columns:
                df[self.selector_column] = None

            # Gather the selectors for each row (ie. parse the selectors column)
            df[self.selector_column] = df[self.selector_column].map(
                lambda x: self._gather_selectors(x, equals_version_only=False)
            )
            # Only keep the rows where the selectors pass the test
            df = df[
                df[self.selector_column].map(
                    lambda x: self._seletors_pass(self.selectors_dict, x)
                )
            ]

        # Remove the selector column if required
        if remove_selectors_column:
            df = df[[c for c in df.columns if c != self.selector_column]]

        return df.reset_index(drop=True).copy()

    def apply_single(self, test_selectors: Any) -> bool:
        """Test if the given test_selectors pass the selector test.

        Args:
            test_selectors (Any): The selectors to test the object's selectors against. This can be a
                string (comma-separated selectors), or a list/tuple of selectors.

        Returns:
            bool: True if the test_selectors passes the selector test, False otherwise. A return value of
                is equivalent to saying that a row containing the test_selectors should be included
                when filtering.
        """
        df = pd.DataFrame({self.selector_column: [test_selectors]})
        filtered_df = self.apply(df, remove_selectors_column=True)
        return len(filtered_df) > 0
