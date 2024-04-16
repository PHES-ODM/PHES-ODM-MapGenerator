class V2MappingColumns:
    """Columns used internally to specify how a source class gets mapped to ODM v2. In the ODM v2
    parts list we will rename certain columns to these values. The original column names are
    the columns associated with one specific source dataset (eg. ODM v1). For example, the ODM v2 
    parts file has columns "version1Table", "version1Location", etc. that specify the ODM v1 tables
    and columns used in mapping from ODM v1 to v2. A full list of the columns for ODM v1 are:
        "version1Table" -> V2MappingColumns.SOURCE_TABLE
        "version1Location" -> V2MappingColumns.SOURCE_LOCATION
        "version1Variable" -> V2MappingColumns.SOURCE_VARIABLE
        "version1Category" -> V2MappingColumns.SOURCE_CATEGORY
    SOURCE_ENUM_NAME is added in code, to add the source enumeration name for each row.
    """
    SOURCE_TABLE: str = "_sourceTable"
    SOURCE_LOCATION: str = "_sourceLocation"
    SOURCE_VARIABLE: str = "_sourceVariable"
    SOURCE_CATEGORY: str = "_sourceCategory"
    SOURCE_ENUM_NAME: str = "_sourceEnumName"
    
class V2MappingVariableLocations:
    """Recognized values in the V2MappingColumns.SOURCE_VARIABLE column
    """
    # The row is for an enumeration value
    VARIABLE_CATEGORIES: str = "variableCategories"
    # The row is for a table
    TABLE: str = "Tables"
    # The row is for a column
    VARIABLES: str = "variables"
