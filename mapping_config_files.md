# Mapping Configuration Files

Mapping configuration files are Excel files that contain all required
configuration information for mapping from a source dataset (eg. NWSS) to a
target dataset (eg. ODM v2). Each mapping file can have multiple tabs, one or
more that defines some basic mappings from source to target slots (typically
the tab is named `maps`), one or more separate tabs configuring how wide
columns are mapped (typically the tab is named `wide`), and one or more
separate tabs configuring mapping of enumerations (typically called `enums`).
While these tabs in mapping configuration files are usually named `maps`,
`wide`, and `enums`, they can be given any name, as long as the names are
provided when running the appropriate scripts.

This document describes the structure of these configuration files. To see an
example mapping configuration file see
[data/mapping_config_files/nwss_to_odm_v2_mapping.xlsx](data/mapping_config_files/nwss_to_odm_v2_mapping.xlsx)

## Maps tabs

The `maps` tab(s) specify the mappings other than wide-column mappings. It
provides details on how a slot from the source class is mapped onto a slot from
the target class. The simplest of which is to simply copy from one slot to
another. The `maps` tab is also where you can specify mappings of enumerations.
Any row that is completely empty is ignored. Multiple `maps` tabs are allowed,
their names must be specified when running the appropriate scripts. The `maps`
tab has the headings described below.

Any row that is completely empty is ignored.

### selectors

A comma-separated string of selector values. A selector is specified from the
command-line and tells us which rows to keep or drop from the input data.
Individual selectors in the data can be negated by preceding it with an
exclamation mark.

Below is an example table with a `selectors` column:

| Color   | selectors     |
|:--------|:--------------|
| Red     | amr           |
| Orange  | !agnostic,!amr,other      |
| Yellow  | amr           |
| Green   | amr           |
| Blue    | !agnostic,amr |
| Indigo  |               |
| Violet  |               |
| Cyan    | amr,agnostic  |
| Magenta |               |

For a given value of selectors, we separate the negated selectors from the
non-negated selectors. The following two conditions must pass:

1. For negated selectors: None of these selectors must have been specified from
   the command-line (ie. we perform an AND operation for all negated
   selectors). If there are no negated selectors then this rule always passes.
2. For non-negated selectors: Any of these selectors must have been specified
   from the command-line (ie. we perform an OR operation for all non-negated
   selectors). If there are no non-negated selectors then this rule always
   passes.

Following the above rules, if the `selectors` column is empty for a row, then
that row is always retained.

So for the row with `Color` equal to `Blue`, the selectors are "!agnostic,amr".
We keep the row if 1) "agnostic" was not specified form the command-line, and
2) "amr" was specified from the command-line.

For the row with `Color` equal to `Cyan`, the selectors are "amr,agnostic". We
keep the row if either (or both) "amr" or "agnostic" were specified from the
command-line.

For the row with `Color` equal to `Yellow`, the selectors are "amr". We keep
the row if "amr" was specified from the command-line.

For the row with `Color` equal to `Orange`, the selectors are
"!agnostic,!amr,other". We keep the row if neither "agnostic" or "amr" were
specified from the command-line, and "other" was specified from the
command-line.

### sourceClass

The class name from the source dataset.

### sourceSlot

The slot in the source dataset that we are copying from (ie. this becomes the
`populated_from` field in the mapping specification). If `targetExpr` or
`customData` are set then `sourceSlot` is ignored.

### sourceValue

If empty then we copy from the source slot to the target slot unchanged. In
this case `targetValue` must be set to '{{sourceSlot}}', where 'sourceSlot' is
replaced with the value found in the row's `sourceSlot` column.

If not empty, then the value represents a source enumeration value. This
enumeration value (if found in the sourceSlot) will be mapped to the value
found in the `targetValue` column.

### targetClass

The class in the target dataset that we are populating (from the `sourceClass`
and `sourceSlot`).

### targetSlot

The slot in the `targetClass` in the target dataset that we are populating
(from the `sourceClass` and `sourceSlot`).

### targetValue

The value to set in the `targetSlot` in the `targetClass`. If `sourceValue` is
empty then this should be set to `{{sourceSlot}}`, where 'sourceSlot' is
replaced with the value found in the row's `sourceSlot` column. If
`sourceValue` is set (and therefore represents a source enumeration value),
then `targetValue` equals the value we map the `sourceValue` to.

### targetExpr

An optional value, that if set is assigned to the `expr` slot of the slot
derivation. The `expr` slot allows custom code to calcualte a value, that is
then assigned to the `targetSlot`. The custom code can be in the LinkML
expression language or it can be Python code. For Python code the source class
can be referenced with the `src` object variable and the result should be saved
in the `target` variable. For example, the following will return the value of
the `sample_type` slot if it is set, or if not set the value of `source_type`,
or an empty string if neither are set:

```python
def a_or_b(a, b):
    if a:
        return a
    if b:
        return b
    return ""
target = a_or_b(src.sample_type, src.source_type)
```

If the value of `targetSlot` should be a constant, simply set `targetExpr` to
the constant in double quotes (if a string), or enter the value unchanged (if a
number or boolean).

If `targetExpr` is set, then `sourceValue` and `targetValue` should be left
empty.

### customData

An optional value, in the form of a JSON string. The dictionary in the slot
derivation for this row gets updated with the values in this column. For
example, the following value in `customData` will set the `expr` key in the
slot derivation for the `targetSlot`. The slot will be set to `False` if
`dashboard_ignore` or `analysis_ignore` in the source dataset are equal to
`yes`:

```json
{
    "expr" : "(str(dashboard_ignore) == 'yes') + (str(analysis_ignore) == 'yes') == 0"
}
```

## Wide tabs

The `wide` tab(s) specify how to pivot wide-columns. For details on what
pivoting wide columns means, see the [Wide Columns
Example](wide_columns_example.md) document.

There can be multiple `wide` tabs, which are specified on the command-line when
running the appropriate scripts. Any row that is completely empty is ignored.

Any row that is completely empty is ignored.

### selectors

The `selectors` column in the Wide tabs are used in the same way as specified
above in the maps tabs.

### wideGroup

This is an optional grouping column. In most cases this can be left blank.
However, there are cases where we might want to pivot the same wide-column
multiple times (ie. pivoting the same column to have multiple output rows,
rather than just one), or even perform different enumeration mappings on the
same wide-column. In such a case, we can set the `wideGroup` to values that
group the rows in the wide sheet together. All rows with the same value in
`wideGroup` (for a given `sourceClass`, `sourceSlot`, and `targetClass`
combination) will be considered a full wide-to-long specification for that slot
and will be considered separately from all other rows with a different
`wideGroup`.

### sourceClass

This is the class from the source dataset that contains the slot that is a
wide-column.

### sourceSlot

This is the slot from the source dataset and source class that is the
wide-column to pivot.

### sourceValue

If not empty, then the value represents a source enumeration value for the
`sourceSlot`, and we map this enumeration value to the value found in
`targetValue`. All rows with the same `sourceClass`, `sourceSlot`,
`targetClass`, and `wideGroup` are used for determining how the enumeration
values are mapped for the same source slot. Only the first row in the group is
used to determine the values to set in the output row (see [All other
columns](#all-other-wide-columns) below for how these values are set).

### targetClass

This is the class in the target dataset that we map the source slot to.

### targetValue

If not empty, then this is the target value that we map enumerations to. If the
source slot has the value found in `sourceValue`, then we map it to this value.

### notes

This is to add additional notes for the row. It is ignored.

### Target Value Columns (_value)

Any column in the `wide` tab that ends with the string `_value` specifies a
column in the target class that we want to set a value for. The actual column
name we set is determined by removing the `_value` suffix. For example, a
column named `measure_value` will result in a value in the output row being set
for the column `measure`. These values can be constant values or optionally a
string in the form `{{slotName}}` where `slotName` is the name of a slot in the
source class to copy the value from. Note that if `slotName` is an enumeration
then any enumeration mappings will also be performed when copying from
`slotName`.

For example, given the wide-column spec table below:

| sourceClass | sourceSlot         | sourceValue | targetClass | targetValue | unit_value  | measure_value | value_value            |
|-------------|--------------------|-------------|-------------|-------------|-------------|---------------|------------------------|
| nwss        | sewage_travel_time |             | measures    |             | hours       | sewTrTi       | {{sewage_travel_time}} |

Each output row will have columns `unit` and `measure` set to the constants
`hours` and `sewTrTi` (respectively), and the output column `value` will be
copied from the `sewage_travel_time` slot.

Note that all the columns in the example configuration above will apply to
every row specified in the configuration. However, it's possible that a target
column does not exist for a particular target class (eg. if we also had a row
where `targetClass` is equal to `samples` instead of `measures`). There are two
ways to deal with this. Either specify additional slots specific to a target
class in `wideOtherSlots`, or create multiple `wide` tabs in the mapping file,
with each tab having different target columns. One good approach to organizing
your `wide` tabs is to have a different `wide` tab for each `targetClass`.

All of these columns specified will take precedence over any values set/copied
in the `maps` tab, but not over any values set/copied in the `wideOtherSlots`
column for the current row.

### Target Expression Columns (_expr)

Any column in the `wide` tab that ends with the string `_expr` specifies a
column in the target class that we want to set the LinkML expression code for.
The actual column name we set is determined by removing the `_expr` suffix.

This works identically to `_value` columns, as described above. Any blank value
will be ignored.

### wideOtherSlots

This is a JSON string for a dictionary specifying additional columns and values
to set for the current row. These will generally be `_value` columns or `_expr`
columns (See [Target Value Columns (_value)](#target-value-columns-_value) and
[Target Expression Columns (_expr)](#target-expression-columns-_expr)) above).
For example, the following will set the "notes_value" column of the current row
to `{{pretreatment_specify}}`, resulting in the `notes` column being populated
from the `pretreatment_specify` column:

```json
{ 
    "notes_value" : "{{pretreatment_specify}}" 
}
```

Using this method, instead of adding the `notes_value` column to the entire
configuration spreadsheet, ensures that all other rows in the same `wide` tab
will not have to have a value set for these other slots. If `notes_value` was
added to the entire spreadsheet, then all rows will have a blank value set for
the `notes` output slot, which might not be the desired behavior.

Values in `wideOtherSlots` will take precedence over any values set/copied in
the `maps` tab or in [Target Value Columns
(_value)](#target-value-columns-_value) and [Target Expression Columns
(_expr)](#target-expression-columns-_expr)) in the `wide` tab for the current
row.

## Enums Tabs

The `enums` tab(s) allow specifying enumeration mappings. As with enumeration
mappings in the `maps` tab, any enumeration will go through any mapping
specified in the configuration file. If there is an enumeration that does not
have any data regarding its mapping in the configuration file then it is copied
unchanged.

Sometimes you may want to include all (or most) enums mappings in the `enums`
tab to organize the configuration sheets. Additionally, the `enums` sheet
(unlike the other sheets) allows you to specify a source or target enumeration
by the actual enumeration name found in the dataset's LinkML schema, which
might not be the same as a slot name. For example in NWSS, the slot
`pcr_gene_target` is an enumeration of type `vs_pcr_gene_target`.
Alternatively, you can stick to specifying the class and slot names rather than
enumeration names. In this case, the code will automatically extract the
enumeration name from the class and slot names.

Any row that is completely empty is ignored. Multiple `enums` tabs are allowed,
their names must be specified when running the appropriate scripts. The `enums`
tab has the headings described below.

### selectors

The `selectors` column in the Wide tabs are used in the same way as specified
above in the maps tabs.

### sourceClass

If specified, then this is the source class that the enumeration belongs to. It
is typically paired with `sourceSlot` to identify the slot that the enumeration
mapping is for. If not specified then `sourceEnum` should be used.

### sourceSlot

If specified, then this is the source slot (within the `sourceClass`) that the
enumeration mapping is for. If `sourceClass` and `sourceSlot` are not used the
`sourceEnum` should be used instead.

### sourceEnum

The name of the source enumeration to map. A `sourceEnum` can only map to a
single `targetEnum`, so be sure that `targetEnum` is the same for all rows of
the same `sourceEnum`.

If `sourceEnum` is not used, then `sourceClass` and `sourceSlot` should be used
instead.

### sourceValue

The enumeration value in the `sourceEnum` that we are mapping from.

### targetClass

If set, then the target class of the `targetSlot` we are mapping to. We will
extract the target enumeration name from the combination of `targetClass` and
`targetSlot`. Alternatively, these can be left blank and `targetEnum` can be
used instead, to specify the target enumeration explicitly.

If `targetEnum`, `targetClass`, and `targetSlot` are left blank them a fake
target enumeration name is created.

### targetSlot

If set, then the target slot within the `targetClass` we are mapping to. We
will extract the target enumeration name from the combination of `targetClass`
and `targetSlot`. Alternatively, these can be left blank and `targetEnum` can
be used instead, to specify the target enumeration explicitly.

If `targetEnum`, `targetClass`, and `targetSlot` are left blank them a fake
target enumeration name is created.

### targetEnum

If set, the name of the target enumeration to map to. It is only possible to
map a `sourceEnum` to a single `targetEnum`, so be sure that `targetEnum` is
the same for all rows of the same `sourceEnum`.

If `targetEnum`, `targetClass`, and `targetSlot` are left blank them a fake
target enumeration name is created.

### targetValue

The enumeration value that we map the `sourceValue` to.
