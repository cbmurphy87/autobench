class AutobenchException(Exception):

    """
    Base Autobench exception.
    """

    def __init__(self, message):
        super(AutobenchException, self).__init__(message)

    def __str__(self):
        return repr(self.message)


class MissingEntry(AutobenchException):
    def __init__(self, message):
        super(MissingEntry, self).__init__(message)
