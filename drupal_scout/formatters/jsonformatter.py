import json

from .formatter import Formatter
from drupal_scout.module import Module


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
                'name': module.name,
                'version': module.version,
                'suitable_entries': [],
                'failed': module.failed
            }
            if module.git_audit is not None:
                mod_dict['git_audit'] = {
                    'module_path': module.git_audit.module_path,
                    'index_status': module.git_audit.index_status.value if hasattr(module.git_audit.index_status, 'value') else str(module.git_audit.index_status),
                    'history_status': module.git_audit.history_status.value if hasattr(module.git_audit.history_status, 'value') else str(module.git_audit.history_status),
                    'index_reason': module.git_audit.index_reason,
                    'history_reason': module.git_audit.history_reason,
                    'tracked_files_count': module.git_audit.tracked_files_count,
                    'recent_commits': module.git_audit.recent_commits,
                    'patches': module.git_audit.patches,
                }


            output.append(mod_dict)

            # omit modules that are not active or failed
            if module.active is False or module.failed:
                continue

            for entry in module.suitable_entries:
                output[-1]['suitable_entries'].append({
                    'version': entry['version'],
                    'requirement': entry['requirement']
                })
        return json.dumps(output, indent=4)
