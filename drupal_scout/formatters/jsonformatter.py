import json

from drupal_scout.module import Module

from .formatter import Formatter


class JSONFormatter(Formatter):
    """
    Formats the output as JSON.
    """

    def format(self, modules: list[Module]) -> str:
        """
        Format the output as JSON.
        :param modules:     the list of modules
        :type modules:      list
        :return:            the formatted output
        :rtype:             str
        """
        output: list[dict] = []
        for module in modules:
            mod_dict: dict = {
                "name": module.name,
                "version": module.version,
                "suitable_entries": [],
                "failed": module.failed,
            }
            if module.deep_scan is not None:
                mod_dict["deep_scan"] = {
                    "mode": module.deep_scan.mode,
                    "module_path": module.deep_scan.module_path,
                    "index_status": module.deep_scan.index_status.value
                    if hasattr(module.deep_scan.index_status, "value")
                    else str(module.deep_scan.index_status),
                    "history_status": module.deep_scan.history_status.value
                    if hasattr(module.deep_scan.history_status, "value")
                    else str(module.deep_scan.history_status),
                    "index_reason": module.deep_scan.index_reason,
                    "history_reason": module.deep_scan.history_reason,
                    "tracked_files_count": module.deep_scan.tracked_files_count,
                    "recent_commits": module.deep_scan.recent_commits,
                    "patches": module.deep_scan.patches,
                }

            output.append(mod_dict)

            # omit modules that are not active or failed
            if module.active is False or module.failed:
                continue

            for entry in module.suitable_entries:
                output[-1]["suitable_entries"].append(
                    {"version": entry["version"], "requirement": entry["requirement"]}
                )
        return json.dumps(output, indent=4)
