import prettytable

from .formatter import Formatter
from drupal_scout.module import Module
from textwrap import fill


class TableFormatter(Formatter):
    """
    Formats the output as a table.
    """

    def format(self, modules: [Module]) -> str:
        """
        Format the output as a table.
        :param modules:     the list of modules
        :type modules:      list
        :return:            the formatted output
        :rtype:             str
        """
        header = ['Name', 'Version', 'Suitable entries']
        table = prettytable.PrettyTable(field_names=header, align='l', hrules=prettytable.ALL)
        table.preserve_internal_border = True
        items = []
        for module in modules:
            suitable_entries = []
            if len(module.suitable_entries) > 1:
                for entry in module.suitable_entries:
                    suitable_entries.append(f"{entry['version']} [{entry['requirement']}]")
            else:
                suitable_entries.append(f"No suitable entries found")
            table.add_row([
                module.name,
                module.version,
                fill('\n'.join(suitable_entries), 80, break_long_words=False, replace_whitespace=False)
            ])
            items.clear()
        return table.get_string()
