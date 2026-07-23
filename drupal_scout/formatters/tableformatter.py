from typing import Any

from rich import box
from rich.console import Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from drupal_scout.module import Module

from .formatter import Formatter


class TableFormatter(Formatter):
    """
    Formats the output as a beautiful Rich table and optional Deep Scan Details panel.
    """

    def format(self, modules: list[Module]) -> Any:
        """
        Format the output as a rich Table (or Group with Table and Deep Scan Details Panel).
        :param modules:     the list of modules
        :return:            Table or Group renderable
        """
        table = Table(
            show_header=True,
            header_style="bold magenta",
            box=box.ROUNDED,
            padding=(0, 1),
        )
        table.show_edge = True
        table.show_lines = True

        table.add_column("Name", style="cyan", no_wrap=True)
        table.add_column("Version", style="green")
        table.add_column("Suitable entries", style="white")

        has_deep_scan = any(m.deep_scan is not None for m in modules)
        # All modules in a single scan share the same mode
        mode = (
            next((m.deep_scan.mode for m in modules if m.deep_scan is not None), "all")
            if has_deep_scan
            else "all"
        )

        if has_deep_scan:
            if mode in ("all", "git"):
                table.add_column("Git index", style="white")
                table.add_column("Git history", style="white")
            if mode in ("all", "patches"):
                table.add_column("Patches", style="white")

        for module in modules:
            entries_text = Text()

            if len(module.suitable_entries) > 0:
                for i, entry in enumerate(module.suitable_entries):
                    if i > 0:
                        entries_text.append("\n")
                    entries_text.append(f"v{entry['version']} ", style="white")
                    entries_text.append(f"[{entry['requirement']}]", style="grey70")
            elif module.failed:
                entries_text.append("Failed to fetch module data", style="red")
            elif module.active is not True:
                entries_text.append("Module possibly not active", style="yellow")
            else:
                entries_text.append("No suitable entries found", style="italic grey50")

            row: list[Any] = [
                module.name,
                module.version or "[dim]N/A[/dim]",
                entries_text,
            ]

            if has_deep_scan:
                if module.deep_scan is not None:
                    idx_val = (
                        module.deep_scan.index_status.value
                        if hasattr(module.deep_scan.index_status, "value")
                        else str(module.deep_scan.index_status)
                    )
                    hist_val = (
                        module.deep_scan.history_status.value
                        if hasattr(module.deep_scan.history_status, "value")
                        else str(module.deep_scan.history_status)
                    )
                    patch_cnt = len(module.deep_scan.patches)
                    patch_val = (
                        f"{patch_cnt} patch"
                        if patch_cnt == 1
                        else (f"{patch_cnt} patches" if patch_cnt > 1 else "none")
                    )

                    if mode in ("all", "git"):
                        row.append(idx_val)
                        row.append(hist_val)
                    if mode in ("all", "patches"):
                        row.append(patch_val)
                else:
                    if mode in ("all", "git"):
                        row.append("[dim]N/A[/dim]")
                        row.append("[dim]N/A[/dim]")
                    if mode in ("all", "patches"):
                        row.append("[dim]N/A[/dim]")

            table.add_row(*row)

        if has_deep_scan:
            detail_texts = []
            clean_count = 0
            for module in modules:
                if module.deep_scan is not None:
                    audit = module.deep_scan
                    has_git_findings = audit.index_status.value in (
                        "found",
                        "unavailable",
                        "incomplete",
                    ) or audit.history_status.value in (
                        "found",
                        "unavailable",
                        "incomplete",
                    )
                    has_patch_findings = len(audit.patches) > 0

                    if mode == "git":
                        has_findings = has_git_findings
                    elif mode == "patches":
                        has_findings = has_patch_findings
                    else:
                        has_findings = has_git_findings or has_patch_findings

                    if not has_findings and len(modules) > 3:
                        clean_count += 1
                        continue

                    lines = [
                        f"[bold cyan]{module.name}[/bold cyan] ([dim]{audit.module_path or 'unknown path'}[/dim]):"
                    ]

                    if mode in ("all", "git"):
                        idx_status = (
                            audit.index_status.value
                            if hasattr(audit.index_status, "value")
                            else str(audit.index_status)
                        )
                        lines.append(
                            f"  • [bold]Index:[/bold] {idx_status} ({audit.tracked_files_count} tracked files)"
                        )
                        if audit.index_reason:
                            lines.append(
                                f"    [yellow]Reason: {audit.index_reason}[/yellow]"
                            )

                        hist_status = (
                            audit.history_status.value
                            if hasattr(audit.history_status, "value")
                            else str(audit.history_status)
                        )
                        if audit.recent_commits:
                            lines.append(
                                f"  • [bold]Recent Commits ({len(audit.recent_commits)}):[/bold]"
                            )
                            for c in audit.recent_commits:
                                lines.append(
                                    f"    - [yellow]{c['hash']}[/yellow] {c['subject']}"
                                )
                        else:
                            lines.append(f"  • [bold]History:[/bold] {hist_status}")
                            if audit.history_reason:
                                lines.append(
                                    f"    [yellow]Reason: {audit.history_reason}[/yellow]"
                                )

                    if mode in ("all", "patches") and audit.patches:
                        lines.append(
                            f"  • [bold]Applied Composer Patches ({len(audit.patches)}):[/bold]"
                        )
                        for p in audit.patches:
                            lines.append(
                                f"    - [green]{p['description']}[/green] ([dim]{p['source']}[/dim])"
                            )

                    detail_texts.append("\n".join(lines))

            if clean_count > 0:
                detail_texts.append(
                    f"[dim]✔ {clean_count} module(s) clear with no uncommitted files, commits, or patches.[/dim]"
                )

            if detail_texts:
                audit_panel = Panel(
                    "\n\n".join(detail_texts),
                    title="Deep Scan Details",
                    border_style="cyan",
                    box=box.ROUNDED,
                )
                return Group(table, audit_panel)

        return table
