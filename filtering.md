# Filtering

Once data has been mapped we may want to filter the resulting data to remove rows that have missing data or for other reasons. When mapping from a wide-format database such as NWSS to a long-format database such as ODM v2 the resulting mapping often has missing data. For example, in NWSS to ODM v2 in the `measures` table, rows with a value of `<ignore>` in the `measure` slot should be removed, as is rows with a blank `value`.

An example filter configuration file can be found at [data/mapping_config_files/nwss_to_odm_v2_filter.csv](data/mapping_config_files/nwss_to_odm_v2_filter.csv).

In this document, a `class` is the name of a table, which is synonymous with a DataFrame, and a `slot` is a column within that DataFrame.

## Filters Summary

The following is an example filters configuration. It will drop all rows in the `measures` table where the value in the `measure` or `unit` column is `<ignore>`, or any row that has a `value` of blank or `-1`. It will also perform similar filtering to the `protocolSteps` table.

|inputFilter|outputFilter|class         |slot       |operation     |value         |
|:----------|:-----------|:-------------|:----------|:-------------|:-------------|
|0          |0           |measures      |measure    |exclude_equals|\<ignore\>    |
|0          |0           |measures      |unit       |exclude_equals|\<ignore\>    |
|0          |0           |measures      |value      |exclude_equals|["", -1]      |
|0          |            |measures      |           |apply_filter  |measures      |
|1          |1           |protocolSteps |measure    |exclude_equals|\<ignore\>    |
|1          |1           |protocolSteps |method     |exclude_equals|\<ignore\>    |
|1          |1           |protocolSteps |value      |exclude_equals|              |
|1          |            |protocolSteps |           |apply_filter  |protocolSteps |

Filtering is performed using boolean filters that are given names and that are applied to various classes (ie. DataFrames). The names given to the filters in the example configuration table above are referenced in the `inputFilter` and `outputFilter` columns. The names can be any user-defined string. The first time a filter is created it consists of all `True` values, meaning it will select all rows in the DataFrame. It will iteratively be modified with each row in the configuration, and when complete it can be applied to a class (ie. a DataFrame).

Each row in the configuration table uses the filter in `inputFilter` as the filter to use. Once the operation is performed on that filter, it is saved as the named filter in `outputFilter` (overwriting any existing filter with the same name). The operation also uses the specified `class` and `slot` to calculate the new filter, along with which `operation` to perform along with a `value` specific to that operation. For example, the first row will exclude any rows in the `measures` class where the slot `measure` is equal to `<ignore>`. This exclusion will result in a new filter which is combined with filter `0` and then saved as filter `0` (specified by `outputFilter`).

Note that most operations will not alter the actual DataFrame for the class, but will instead modify the filter used for that class. Once we've performed all the operations we want for creating the filter, we can apply it to the DataFrame using the `apply_filter` operation. For example, in the fourth row in the example configuration table, we use filter `0` (which has been calculated using three `exclude_equals` operations), apply that filter to the measures class (specified in the `class` column), and then save the new filtered class back to the measures class (specified in the `value` column). If we wanted to keep the `measures` DataFrame unchanged, we could save the filtered DataFrame by changing the name in `value` to something like `measures2`.

The value found in the `value` column of the configuration is parsed as YAML (note that JSON strings are supported by YAML). This allows multiple values to be specified using an array such as `["", -1]` as found in the third row of the example, or more complex values such as dictionaries. Some operations expect the `value` to be in a certain format.

## Filter Operations

### apply_filter

|inputFilter|outputFilter|class         |slot       |operation     |value         |
|:----------|:-----------|:-------------|:----------|:-------------|:-------------|
|0          |            |measures      |           |apply_filter  |measures      |

Apply the filter in `inputFilter` to the DataFrame in `class`, and save the filtered DataFrame to the name in `value`. If a class with the name already exists then it is overwritten.

### copy_filter

|inputFilter|outputFilter|class         |slot       |operation     |value         |
|:----------|:-----------|:-------------|:----------|:-------------|:-------------|
|0          |1           |              |           |copy_filter   |              |

Copy the filter in `inputFilter` and name the copy `outputFilter`. Once copied it can be used in any subsequent row of the configuration.

### copy_class

|inputFilter|outputFilter|class         |slot       |operation     |value         |
|:----------|:-----------|:-------------|:----------|:-------------|:-------------|
|           |            |measures      |           |copy_class    |measures2     |

Copy the class/DataFrame in `class` and save it as the name in `value`. If a class with the same name already exists then it is overwritten. No filter is applied to the DataFrame when copying. To apply an existing filter, the `apply_filter` operation must be performed (either before or after copying the class). After copying the DataFrame it can be used in any subsequent row of the configuration.

### delete_class

|inputFilter|outputFilter|class         |slot       |operation     |value         |
|:----------|:-----------|:-------------|:----------|:-------------|:-------------|
|           |            |measures      |           |delete_class  |              |

Delete the class (DataFrame) specified by `class`.

### drop_duplicates

|inputFilter|outputFilter|class         |slot        |operation            |value         |
|:----------|:-----------|:-------------|:-----------|:--------------------|:-------------|
|0          |0           |measures      |measureRepID|drop_duplicates_keep |keep_first    |

Modify the filter specified by `inputFilter` to drop rows in class `class` where the value in column `slot` is a duplicate. If `value` is `keep_first` then keep the first duplicate when dropping a set of duplicates. If `value` is `keep_last` then keep the last duplicate when dropping a set of duplicates. The resulting filter is saved in `outputFilter`.

### delete_filter

|inputFilter|outputFilter|class         |slot       |operation     |value         |
|:----------|:-----------|:-------------|:----------|:-------------|:-------------|
|0          |            |              |           |delete_filter |              |

Delete the filter specified by `inputFilter`.

### exclude_equals

|inputFilter|outputFilter|class         |slot       |operation     |value         |
|:----------|:-----------|:-------------|:----------|:-------------|:-------------|
|0          |0           |measures      |measure    |exclude_equals|\<ignore\>    |

Modify the filter specified by `inputFilter` to exclude any row that has a value found in the `value` column of the configuration. Multiple values to match can be specified using arrays, such as `["", -1]` (which will exclude rows where the slot is blank or -1). The resulting filter will be saved with the name in `outputFilter`.

### include_equals

|inputFilter|outputFilter|class         |slot       |operation     |value         |
|:----------|:-----------|:-------------|:----------|:-------------|:-------------|
|0          |0           |measures      |measure    |include_equals|-1            |

Modify the filter specified by `inputFilter` to include any row that has a value found in the `value` column of the configuration. Multiple values to match can be specified using arrays, such as `["", -1]` (which will include rows where the slot is blank or -1). The resulting filter will be saved with the name in `outputFilter`.

### invert_filter

|inputFilter|outputFilter|class         |slot       |operation     |value         |
|:----------|:-----------|:-------------|:----------|:-------------|:-------------|
|0          |0           |measures      |           |invert_filter |              |

Invert/negate the specified filter. This will replace all True values in the filter to False, and all False values in the filter to True. The inverted filter will be saved with the name in `outputFilter`. The `class` is optional: If the filter named `inputFilter` already exists it then `class` is not required, if it does not exist then `class` is required, since we need the class's DataFrame to create the new `inputFilter` with the correct number of rows. For best practices the `class` value should be specified.