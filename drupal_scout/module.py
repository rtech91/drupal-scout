class Module:
    """
    Represents a Drupal module.
    """

    active: bool = True
    failed: bool = False

    def __init__(self, name: str):
        """
        Initialize the module.
        :param name:    the name of the module
        :type  name:    str
        """
        self.name = name
        self.version: str | None = None
        self.transitive_entries: list = []
        self.suitable_entries: list = []
