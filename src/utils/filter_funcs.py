"""
All filtering functions/operations.

Filtering involves creating boolean filters for the various different DataFrames (that represent the classes in our
dataset). Once the filters are created, we can apply them to the DataFrames and then use the filtered data.

Within the filtering functions, the `filters` dictionary contains the boolean filters, which are initialized to all True.
The keys of this dictionary are group names (which are typically not class names). We build up the filters associated with 
the groups, and when we're done we apply these filters to the DataFrames in the `data` parameter, by specifying a filter 
group (in `filters`) and a class to apply the filter to (a DataFrame in `data`).

Filtering functions can take the following arguments:

- filters (Dict[str, pd.Series]): All filters. Keys are the groups and values are the boolean filters.
- data (Dict[str, pd.DataFrame]): The data. Keys are the classes and values are the DataFrames.
- input_group (str): The input group. We use this as the initial filter.
- output_group (str): The output group. We save the modified filter, if any, to this group.
- cls (str): The class we are applying the filter to.
- slot (str): The slot (in the class) we are performing the operation on.
- value (Any): The value, whose meaning depends on which operation we're performing.
"""

from typing import Dict, Any
import pandas as pd

from utils.general_utils import get_logger

logger = get_logger(__name__)

def call_filter_func(op: str, **kwargs):
    """Call the filtering function corresponding to the specified operation.

    Args:
        op (str): The operation to call. eg. "exclude_equals". This operation receives
            the keyword arguments in kwargs.
    """
    FILTER_FUNCS[op](**kwargs)

def set_filter_for_group(filt: pd.Series, group: str, filters: Dict[str, pd.Series]):
    """Set the current filter for the specified group. The current filter is a boolean series
    that specifies which rows are currently selected in the group. The group can correspond
    to any of the DataFrames in the data being processed.

    Args:
        filt (pd.Series): The filter.
        group (int): The group that the filter belongs to.
        filters (Dict[str, pd.Series]): The dictionary containing all filters (values) for all groups (keys).
            The value for the group gets modified with filt.
    """
    filters[group] = filt
    
def get_filter_for_group(group: str, filters: Dict[str, pd.Series], data: Dict[str, pd.DataFrame], cls: str) -> pd.Series:
    """Get the filter for the specified group. If the filter does not yet exist then we create the filter with all
    True values for the data of class cls (ie. the filter will have the same number of rows as the data
    for cls).

    Args:
        group (str): The group to get the filter of.
        filters (Dict[str, pd.Series]): The filters for all the groups. We retrieve the filter form this,
            or if the group does not yet exist we create the filter and modify the dictionary to contain
            the new filter (ie. filters[group] = new_filt).
        data (Dict[str, pd.DataFrame]): The data that the filters reference. The keys are the class names and
            the values are the DataFrames.
        cls (str): The class that the filter is for. This corresponds to the keys in data. Note that
            data and cls are only used when the filter for the gorup does not yet exist, and so has to be
            created.

    Returns:
        pd.Series: The current filter for the specified group. If the filter did not yet exist then a new
            filter with all True values is created for the class in the data.
    """
    if group not in filters:
        filters[group] = pd.Series([True] * len(data[cls].index))
    filt = filters[group]
    return filt

def do_exclude_equals(filters: Dict[str, pd.Series], data: Dict[str, pd.DataFrame], input_group: str, output_group: str, cls: str, slot: str, value: Any, **kwargs):
    """Exclude operation. Exclude any row where the slot is equal to the value.

    Args:
        filters (Dict[str, pd.Series]): All filters. Keys are the groups and values are the boolean filters.
        data (Dict[str, pd.DataFrame]): The data. Keys are the classes and values are the DataFrames.
        input_group (str): The input group. We use this as the initial filter.
        output_group (str): The output group. After ANDing the input group we set the output group with the new filter.
        cls (str): The class to create the new filter based on.
        slot (str): The slot. Any row where this slot is equal to value will be excluded.
        value (Any): The value. Any row where the slot is equal to this value will be excluded.
    """
    filt = get_filter_for_group(input_group, filters, data, cls)
    
    # Create the new filter
    df = data[cls]
    if pd.isna(value) or value == "":
        cur_filt = pd.isna(df[slot]) | (df[slot] == value)
    else:
        cur_filt = df[slot] == value
        
    # Apply the filter
    init_num_rows = filt.sum()
    exclude_rows = cur_filt.sum()
    filt = filt & ~cur_filt
    num_rows = filt.sum()
    logger.info(f"Excluded rows, number of rows changed from {init_num_rows} to {num_rows} (Change: {num_rows - init_num_rows}). Filter matched {exclude_rows} row(s)")
    
    set_filter_for_group(filt, output_group, filters)
    
def do_save(filters: Dict[str, pd.Series], data: Dict[str, pd.DataFrame], input_group: str, cls: str, value: Any, **kwargs):
    """Apply the filter from the input group to the DataFrame for class cls, and save the resulting DataFrame to the class
    specified in value.

    Args:
        filters (Dict[str, pd.Series]): All filters. Keys are the groups and values are the boolean filters.
        data (Dict[str, pd.DataFrame]): The data. Keys are the classes and values are the DataFrames.
        input_group (str): The filter to apply to the input DataFrame.
        cls (str): The class to apply the filter to (in data)
        value (Any): The class to save the filtered DataFrame to (in data).
    """
    # Save the data by applying the current group's filter to the data for class cls
    filt = get_filter_for_group(input_group, filters, data, cls)
    init_num_rows = len(data[cls])
    data[value] = data[cls][filt]
    num_rows = len(data[value])
    logger.info(f"Saved data from group {input_group} to class {cls}, number of rows changed from {init_num_rows} to {num_rows} (Change: {num_rows - init_num_rows})")

# Map specifying which function to call for each operation.
FILTER_FUNCS = {
    "exclude_equals": do_exclude_equals,
    "save": do_save,
}
