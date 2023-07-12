class Module:
    """
    Represents a Drupal module.
    """

    name: str = None
    version: str = None
    transitive_entries: list = None
    suitable_entries: list = None
    active: bool = True

    def __init__(self, name: str):
        """
        Initialize the module.
        :param name:    the name of the module
        :type  name:    str
        """
        self.name = name
        self.transitive_entries = []
        self.suitable_entries = []
