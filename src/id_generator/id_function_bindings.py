from typing import Any

class FunctionBindings:
    """All functions/properties accessible from ID code using the global fn object (eg. fn.makeid("a", "b", "c")).
    """
    def __init__(self, generator):
        self.generator = generator
    
    @property
    def rownum(self) -> str:
        return "{:04d}".format(self.generator.current_row_index)
    
    def makeid(self, *args) -> str:
        """Create an ID out of the list of values.
        
        Args:
            *args: The list of values to convert to an ID. We will convert them to strings and concatenate
                them. The leading character is lower case, and the first character of each item in the list
                becomes uppercase.

        Returns:
            str: The ID generated from the list of values.
        """
        firstcap = False
        if not args:
            return None
        args = [str(v).replace(" ", "") for v in args]
        args = [v for v in args if len(v)]
        # Make first character of each element uppercase. The first element has a first character that is
        # lowercase unless firstcap is True (in which case we uppercase it)
        args = ["%s%s" % (v[0].upper() if (idx or firstcap) else v[0].lower(), v[1:]) for idx, v in enumerate(args)]
        v = "".join(args)
        return v
        
    def date(self, d):
        # @TODO: Implement
        return d

    def countrows(self, class_name: str, slot: str, equals: Any) -> int:
        """Count number of rows in class class_name where the value in the slot is equal to any value in equals.

        Args:
            class_name (str): The class to count the rows in.
            slot (str): The slot in the class where we match to the equals parameter.
            equals (Any): The value(s) to match. If a list or tuple then we match any of the values in the list. If not a list
                then we only match the single value.

        Returns:
            int: The number of rows in the class where the value in the slot matches equals.
        """
        rows = self.generator.get_rows_equal(class_name, slot, equals)
        return len(rows) if rows is not None else 0