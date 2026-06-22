from rich.console import Console

from .. import report

console = Console()


class ReportCommand:

    def handle_report(self, period, month_val, tag_name, export_format, output_path, project_name):
        if not period:
            period = "week"

        if export_format in ("markdown", "md"):
            result = report.export_markdown(period, month_val, project_name, tag_name, output_path)
            if result:
                console.print(f"[green]✓ Markdown 导出成功:[/green] [cyan]{result}[/cyan]")
            return

        if export_format == "csv":
            result = report.export_csv(period, month_val, project_name, output_path, tag_name)
            if result:
                console.print(f"[green]✓ CSV 导出成功:[/green] [cyan]{result}[/cyan]")
            return

        if period == "daily":
            report.print_daily_report()
        elif period == "weekly":
            report.print_weekly_report()
        else:
            report.print_report(period, month_val, tag_name)
