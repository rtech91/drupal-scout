class ComposerV1Exception(Exception):
    """Exception raised for case when Composer v1 is used."""

    def __init__(self, message="The Drupal project uses Composer v1. Please upgrade to Composer v2."):
        self.message = message
        super().__init__(self.message)


class DirectoryNotFoundException(Exception):
    """Exception raised for case when the directory does not exist."""

    def __init__(self, message):
        self.message = message
        super().__init__(self.message)


class NoComposerJSONFileException(Exception):
    """Exception raised for case when the directory does not contain the composer.json file."""

    def __init__(self, message="The directory does not contain the composer.json file."):
        self.message = message
        super().__init__(self.message)


class ModuleNotFoundException(Exception):
    """Exception raised for case when the module is not found."""

    def __init__(self, message):
        self.message = message
        super().__init__(self.message)
