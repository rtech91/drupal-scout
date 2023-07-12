# Specific formatter that will take the modules suitable entries, and replace with them the composer.json requirements.

import json
import os
from argparse import Namespace
from .formatter import Formatter
from packaging import version
from drupal_scout.module import Module


class SuggestFormatter(Formatter):
    """
    Formats the output as composer.json contents based on real composer.json contents.
    """

    def __init__(self, args: Namespace):
        self.directory = args.directory
        self.save_dump = args.save_dump

    def format(self, modules: [Module]) -> str:
        """
        Take the real composer.json contents, and module requirement versions with suitable entry versions.
        :param modules:   the list of modules
        :type modules:    list
        :return:          the formatted output
        :rtype:           str
        """
        output = []
        with open(os.path.join(self.directory, "composer.json"), "r") as f:
            composer_json = json.load(f)
            for module in modules:
                # module have more than one suitable entry, find the lowest version and replace the requirement version
                if len(module.suitable_entries) > 1 and module.active is True:
                    lowest_version = self.find_lowest_version(module.suitable_entries)
                    # find the module in the composer.json
                    for package in composer_json['require']:
                        if package == module.name:
                            # replace the version with the lowest version
                            composer_json['require'][package] = f"^{lowest_version}"
                # module have only one suitable entry, replace the requirement version with the suitable entry version
                elif len(module.suitable_entries) == 1:
                    for package in composer_json['require']:
                        if package == module.name:
                            composer_json['require'][package] = f"^{module.suitable_entries[0]['version']}"
                elif len(module.suitable_entries) == 0:
                    continue
        if self.save_dump:
            with open(os.path.join(self.directory, "composer.json"), "w") as f:
                json.dump(composer_json, f, indent=4)
        return json.dumps(composer_json, indent=4)

    def find_lowest_version(self, suitable_entries: [dict]) -> str:
        """
        Find the lowest version from the list of suitable entries.
        :param suitable_entries:   the list of suitable entries
        :type suitable_entries:    list
        :return:                   the lowest version
        :rtype:                    str
        """
        lowest_version = None
        for entry in suitable_entries:
            if lowest_version is None:
                lowest_version = entry['version']
            elif version.parse(lowest_version) > version.parse(entry['version']):
                lowest_version = entry['version']
        return lowest_version
