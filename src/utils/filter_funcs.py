"""
All filtering functions/operations.

Filtering involves creating boolean filters for the various different DataFrames (that represent the classes in our
dataset). Once the filters are created, we can apply them to the DataFrames and then use the filtered data.

Within the filtering functions, the `filters` dictionary contains the boolean filters, which are initialized to all True.
The keys of this dictionary are filter names (which are typically not class names). We build up the filters and when we're
done we apply these filters to the DataFrames in the `data` parameter, by specifying a filter name (in the `filters` 
dictionary) and a class to apply the filter to (a DataFrame in `data`).

Filtering functions can take the following arguments:

- filters (Dict[str, pd.Series]): All filters. Keys are the filter names and values are the boolean filters.
- data (Dict[str, pd.DataFrame]): The data. Keys are the classes and values are the DataFrames.
- input_name (str): The input filter name. We use this as the initial filter.
- output_name (str): The output filter name to save the filter as.
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

def set_named_filter(filt: pd.Series, name: str, filters: Dict[str, pd.Series]):
    """Set the current filter for the specified filter name. The filter is a boolean series
    that specifies which rows are selected in the table.

    Args:
        filt (pd.Series): The filter.
        name (int): The name to save the filter as.
        filters (Dict[str, pd.Series]): The dictionary containing all filters (values) for all names (keys).
            The value for the name gets modified with filt.
    """
    filters[name] = filt
    
def get_named_filter(name: str, filters: Dict[str, pd.Series], data: Dict[str, pd.DataFrame], cls: str) -> pd.Series:
    """Get the filter with the specified name. If the filter does not yet exist then we create the filter with all
    True values for the data of class cls (ie. the filter will have the same number of rows as the data
    for cls).

    Args:
        name (str): The name of the filter to get.
        filters (Dict[str, pd.Series]): All the named filters. We retrieve the filter form this,
            or if the name does not yet exist we create the filter and modify the dictionary to contain
            the new filter (ie. filters[name] = new_filt).
        data (Dict[str, pd.DataFrame]): The data that the filters reference. The keys are the class names and
            the values are the DataFrames.
        cls (str): The class that the filter is for. This corresponds to the keys in data. Note that
            data and cls are only used when the filter for the gorup does not yet exist, and so has to be
            created.

    Returns:
        pd.Series: The current filter with the specified name. If the filter did not yet exist then a new
            filter with all True values is created for the class in the data.
    """
    if name not in filters:
        filters[name] = pd.Series([True] * len(data[cls].index))
    filt = filters[name]
    return filt

def do_drop_duplicates(filters: Dict[str, pd.Series], data: Dict[str, pd.DataFrame], input_name: str, output_name: str, cls: str, slot: str, keep_first: bool, **kwargs):
    filt = get_named_filter(input_name, filters, data, cls)

    df = data[cls]
    filt = filt & ~df[slot].duplicated(keep="first" if keep_first else "last")

    set_named_filter(filt, output_name, filters)
    
def do_drop_duplicates_keep_first(filters: Dict[str, pd.Series], data: Dict[str, pd.DataFrame], input_name: str, output_name: str, cls: str, slot: str, value: Any, **kwargs):
    do_drop_duplicates(filters=filters, data=data, input_name=input_name, output_name=output_name, cls=cls, slot=slot, keep_first=True, **kwargs)

def do_drop_duplicates_keep_last(filters: Dict[str, pd.Series], data: Dict[str, pd.DataFrame], input_name: str, output_name: str, cls: str, slot: str, value: Any, **kwargs):
    do_drop_duplicates(filters=filters, data=data, input_name=input_name, output_name=output_name, cls=cls, slot=slot, keep_first=False, **kwargs)

def do_exclude_equals(filters: Dict[str, pd.Series], data: Dict[str, pd.DataFrame], input_name: str, output_name: str, cls: str, slot: str, value: Any, **kwargs):
    """Exclude operation. Exclude any row where the slot is equal to the value.

    Args:
        filters (Dict[str, pd.Series]): All filters. Keys are the names and values are the boolean filters.
        data (Dict[str, pd.DataFrame]): The data. Keys are the classes and values are the DataFrames.
        input_name (str): The input name. We use this as the initial filter.
        output_name (str): The output name. After ANDing with the input filter we save the resulting filter to this name.
        cls (str): The class to create the new filter based on.
        slot (str): The slot. Any row where this slot is equal to value will be excluded.
        value (Any): The value. Any row where the slot is equal to this value will be excluded.
    """
    filt = get_named_filter(input_name, filters, data, cls)
    
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
    
    set_named_filter(filt, output_name, filters)
    
def do_delete_filter(filters: Dict[str, pd.Series], input_name: str, **kwargs):
    """Delete the filter named input_name. After deleting, the filter will no longer exist
    but can be reacreated by a subsequent row that references the filter by the same name.

    Args:
        filters (Dict[str, pd.Series]): All filters. Keys are the names and values are the boolean filters.
        input_name (str): Name of the filter to delete.
    """
    if input_name in filters:
        del(filters[input_name])

def do_apply_filter(filters: Dict[str, pd.Series], data: Dict[str, pd.DataFrame], input_name: str, cls: str, value: Any, **kwargs):
    """Apply the filter from the input name to the DataFrame for class cls, and save the resulting DataFrame to the class
    specified in value.

    Args:
        filters (Dict[str, pd.Series]): All filters. Keys are the names and values are the boolean filters.
        data (Dict[str, pd.DataFrame]): The data. Keys are the classes and values are the DataFrames.
        input_name (str): The filter to apply to the input DataFrame.
        cls (str): The class to apply the filter to (in data)
        value (Any): The class to save the filtered DataFrame to (in data).
    """
    # Save the data by applying the current name's filter to the data for class cls
    filt = get_named_filter(input_name, filters, data, cls)
    init_num_rows = len(data[cls])
    data[value] = data[cls][filt]
    num_rows = len(data[value])
    logger.info(f"Saved data from filter {input_name} to class {cls}, number of rows changed from {init_num_rows} to {num_rows} (Change: {num_rows - init_num_rows})")

def do_delete_class(data: Dict[str, pd.DataFrame], cls: str, **kwargs):
    """Delete the class (DataFrame) named cls.

    Args:
        data (Dict[str, pd.DataFrame]): The data. Keys are the classes and values are the DataFrames.
        cls (str): The class to delete from the data.
    """
    if cls in data:
        del(data[cls])

# Map specifying which function to call for each operation.
FILTER_FUNCS = {
    "drop_duplicates_keep_first": do_drop_duplicates_keep_first,
    "drop_duplicates_keep_last": do_drop_duplicates_keep_last,
    "exclude_equals": do_exclude_equals,
    "apply_filter": do_apply_filter,
    "delete_filter": do_delete_filter,
    "delete_class": do_delete_class,
}
