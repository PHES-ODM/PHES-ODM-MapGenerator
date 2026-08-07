# How-to guides

Task-oriented recipes. Each one assumes you already have the project installed
and know roughly what you are trying to achieve. If you do not, work through the
[tutorials](../tutorials/index.md) first.

## Editing mappings

| Guide | For when |
| --- | --- |
| [Fix an incorrect column or value mapping](fix-a-mapping.md) | A column lands in the wrong place, or a coded value comes through untranslated |
| [Map a wide column into its own output row](map-a-wide-column.md) | One source column has to become several output rows |
| [Normalize slot names that don't match the schema](normalize-slot-names.md) | Workbook column names differ from the schema in casing or punctuation |
| [Find out why a workbook row was ignored](find-out-why-a-row-was-ignored.md) | You edited a row and nothing changed |

## Running the generator

| Guide | For when |
| --- | --- |
| [Generate mappers for ODM v2 instead of v3](target-odm-v2.md) | The target is v2, not the default v3 |
| [Add support for a new source dataset](add-a-new-source-dataset.md) | Mapping a format the repository does not handle yet |
| [Bootstrap a workbook from existing mappers](bootstrap-a-workbook.md) | You have working mappers and want an editable workbook from them |

## Checking output

| Guide | For when |
| --- | --- |
| [Check generated mappers](check-generated-mappers.md) | After every generation run |
| [Validate a data file against a schema](validate-a-data-file.md) | Confirming that a CSV/TSV conforms to a LinkML schema |
