import json

from .formatter import Formatter
from drupal_scout.module import Module


class JSONFormatter(Formatter):
    """
    Formats the output as JSON.
    """

    def format(self, modules: [Module]) -> str:
        """
        Format the output as JSON.
        :param modules:     the list of modules
        :type modules:      list
        :return:            the formatted output
        :rtype:             str
        """
        output = []
        for module in modules:
            output.append({
                'name': module.name,
                'version': module.version,
                'suitable_entries': []
            })
            for entry in module.suitable_entries:
                output[-1]['suitable_entries'].append({
                    'version': entry['version'],
                    'requirement': entry['requirement']
                })
        return json.dumps(output, indent=4)

