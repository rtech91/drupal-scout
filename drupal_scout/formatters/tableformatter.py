from rich.table import Table
from rich.text import Text
from rich import box
from .formatter import Formatter
from drupal_scout.module import Module

class TableFormatter(Formatter):
    """
    Formats the output as a beautiful Rich table.
    """

    def format(self, modules: list[Module]) -> Table:
        """
        Format the output as a rich Table.
        :param modules:     the list of modules
        :return:            the rich Table object
        """
        table = Table(show_header=True, header_style="bold magenta", box=box.ROUNDED, padding=(0, 1))
        # Adding a border between rows for clarity
        table.show_edge = True
        table.show_lines = True
        
        table.add_column("Name", style="cyan", no_wrap=True)
        table.add_column("Version", style="green")
        table.add_column("Suitable entries", style="white")

        for module in modules:
            entries_text = Text()
            
            if len(module.suitable_entries) > 0:
                for i, entry in enumerate(module.suitable_entries):
                    if i > 0:
                        entries_text.append("\n")
                    # Using Rich style instead of ANSI codes
                    entries_text.append(f"v{entry['version']} ", style="white")
                    entries_text.append(f"[{entry['requirement']}]", style="grey70")
            elif module.failed:
                entries_text.append("Failed to fetch module data", style="red")
            elif module.active is not True:
                entries_text.append("Module possibly not active", style="yellow")
            else:
                entries_text.append("No suitable entries found", style="italic grey50")
            
            table.add_row(
                module.name,
                module.version or "[dim]N/A[/dim]",
                entries_text
            )
            
        return table
