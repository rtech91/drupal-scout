from dataclasses import dataclass, field
from enum import Enum


class AuditStatus(str, Enum):
    FOUND = "found"
    CLEAR = "clear"
    UNAVAILABLE = "unavailable"
    INCOMPLETE = "incomplete"


@dataclass
class ModuleDeepScan:
    mode: str = "all"
    module_path: str | None = None
    index_status: AuditStatus = AuditStatus.UNAVAILABLE
    history_status: AuditStatus = AuditStatus.UNAVAILABLE
    index_reason: str | None = None
    history_reason: str | None = None
    tracked_files_count: int = 0
    recent_commits: list[dict[str, str]] = field(default_factory=list)
    patches: list[dict[str, str]] = field(default_factory=list)


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
        self.deep_scan: ModuleDeepScan | None = None
