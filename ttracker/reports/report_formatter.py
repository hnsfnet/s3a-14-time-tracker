import csv
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box
from rich.text import Text

from ..timer import format_duration, format_duration_short, format_money


class ReportFormatter:

    def __init__(self):
        self.console = Console()

    def _budget_bar(self, used: float, limit: float, width: int = 20) -> Text:
        if limit <= 0:
            return Text("-", style="dim")
        ratio = used / limit
        filled = int(width * min(ratio, 1.0))
        bar = "█" * filled + "░" * (width - filled)
        if ratio >= 1.0:
            color = "red"
        elif ratio >= 0.8:
            color = "yellow"
        else:
            color = "green"
        return Text(bar, style=color)

    def _budget_pct(self, used: float, limit: float) -> str:
        if limit <= 0:
            return "-"
        return f"{(used / limit) * 100:.1f}%"

    def print_log_entries(self, data: Dict[str, Any]) -> None:
        if "error" in data:
            self.console.print(f"[red]错误: {data['error']}[/red]")
            return

        if data.get("empty"):
            self.console.print(f"[yellow]{data['desc']}暂无记录[/yellow]")
            return

        desc = data["desc"]
        entry_rows = data["entry_rows"]
        total_duration = data["total_duration"]
        total_cost = data["total_cost"]

        table = Table(title=f"📋 {desc} - 工时记录", box=box.ROUNDED, show_lines=False)
        table.add_column("开始时间", style="cyan", no_wrap=True)
        table.add_column("结束时间", style="cyan", no_wrap=True)
        table.add_column("时长", style="green", justify="right")
        table.add_column("项目", style="magenta")
        table.add_column("备注", style="white")

        for row in entry_rows:
            table.add_row(
                row["start_str"],
                row["end_str"],
                format_duration(row["duration"]),
                row["project_display"],
                row["note"],
            )

        self.console.print(table)

        summary = Table(box=None, show_header=False, padding=(0, 2))
        summary.add_column("项目", style="bold", justify="right")
        summary.add_column("值", style="bold")
        summary.add_row("总时长:", f"[green]{format_duration(total_duration)}[/green]")
        summary.add_row("总费用:", f"[bold yellow]{format_money(total_cost)}[/bold yellow]")

        self.console.print(Panel(summary, title="📊 汇总", border_style="blue"))

    def print_report(self, data: Dict[str, Any]) -> None:
        if "error" in data:
            self.console.print(f"[red]错误: {data['error']}[/red]")
            return

        if data.get("empty"):
            self.console.print(f"[yellow]{data['desc']}暂无数据[/yellow]")
            return

        desc = data["desc"]
        project_rows = data["project_rows"]
        total_duration = data["total_duration"]
        total_cost = data["total_cost"]
        bar_rows = data["bar_rows"]
        project_count = data["project_count"]

        self.console.print()
        self.console.print(f"[bold blue]{'=' * 50}[/bold blue]")
        self.console.print(f"[bold blue]  📈 {desc}项目报表[/bold blue]")
        self.console.print(f"[bold blue]{'=' * 50}[/bold blue]")
        self.console.print()

        table = Table(title="按项目汇总", box=box.ROUNDED)
        table.add_column("项目名称", style="magenta", no_wrap=True)
        table.add_column("客户", style="cyan")
        table.add_column("费率", style="yellow", justify="right")
        table.add_column("时长", style="green", justify="right")
        table.add_column("费用", style="bold yellow", justify="right")
        table.add_column("工时预算", style="green")
        table.add_column("费用预算", style="yellow")

        for pr in project_rows:
            project = pr["project"]
            duration = pr["duration"]
            cost = pr["cost"]
            hours = pr["hours"]

            if pr["h_pct"] is not None:
                hpct = f"{pr['h_pct']:.1f}%"
                hbar = self._budget_bar(hours, project.budget_hours, 10)
                hcell = Text()
                hcell.append(hbar)
                hcell.append(f" {hpct}", style="dim")
            else:
                hcell = Text("-", style="dim")

            if pr["c_pct"] is not None:
                cpct = f"{pr['c_pct']:.1f}%"
                cbar = self._budget_bar(cost, project.budget_cost, 10)
                ccell = Text()
                ccell.append(cbar)
                ccell.append(f" {cpct}", style="dim")
            else:
                ccell = Text("-", style="dim")

            table.add_row(
                project.name,
                project.client or "-",
                format_money(project.rate) + "/小时",
                format_duration_short(duration),
                format_money(cost),
                hcell,
                ccell,
            )

        table.add_row(
            "[bold]合计[/bold]",
            "",
            "",
            f"[bold green]{format_duration_short(total_duration)}[/bold green]",
            f"[bold]{format_money(total_cost)}[/bold]",
            "",
            "",
            end_section=True,
        )

        self.console.print(table)
        self.console.print()

        self.console.print("[bold blue]📊 时长分布图[/bold blue]")
        self.console.print()

        bar_table = Table(box=None, show_header=False, padding=(0, 1))
        bar_table.add_column("项目", width=20)
        bar_table.add_column("分布", width=50)
        bar_table.add_column("时长", justify="right", width=10)

        for br in bar_rows:
            filled = br["filled"]
            max_width = br["max_bar_width"]
            bar_str = "█" * filled + "░" * (max_width - filled)
            bar_text = Text(bar_str, style="green")
            bar_table.add_row(
                f"[magenta]{br['project_name']}[/magenta]",
                bar_text,
                f"[green]{format_duration_short(br['duration'])}[/green]",
            )

        self.console.print(bar_table)
        self.console.print()

        summary = Table(box=None, show_header=False, padding=(0, 2))
        summary.add_column("项目", style="bold", justify="right", width=15)
        summary.add_column("值", style="bold")
        summary.add_row("项目数量:", f"[cyan]{project_count}[/cyan] 个")
        summary.add_row("总工时:", f"[green]{format_duration(total_duration)}[/green]")
        summary.add_row("总费用:", f"[bold yellow]{format_money(total_cost)}[/bold yellow]")

        self.console.print(Panel(summary, title="💼 最终汇总", border_style="green"))
        self.console.print()

    def print_daily_report(self, data: Dict[str, Any]) -> None:
        if data.get("empty"):
            self.console.print(f"[yellow]{data['date_str']} 今日暂无记录[/yellow]")
            return

        date_str = data["date_str"]
        project_sections = data["project_sections"]
        project_count = data["project_count"]
        total_duration = data["total_duration"]
        total_cost = data["total_cost"]

        self.console.print()
        self.console.print(f"[bold blue]📅 日报 - {date_str}[/bold blue]")
        self.console.print()

        for ps in project_sections:
            proj_name = ps["proj_name"]
            proj_total = ps["proj_total"]
            client = ps["client"]
            rows = ps["rows"]

            panel_title = f"[magenta]{proj_name}[/magenta] - [green]{format_duration(proj_total)}[/green]"
            if client:
                panel_title += f"  [cyan]({client})[/cyan]"

            tbl = Table(box=box.SIMPLE, show_header=False)
            tbl.add_column(style="cyan", width=12)
            tbl.add_column(style="green", width=10, justify="right")
            tbl.add_column()

            for row in rows:
                tbl.add_row(
                    row["time_range"],
                    format_duration_short(row["duration"]),
                    row["note"],
                )

            self.console.print(Panel(tbl, title=panel_title, border_style="blue"))

        summary = Table(box=None, show_header=False, padding=(0, 2))
        summary.add_column("项目", style="bold", justify="right", width=15)
        summary.add_column("值", style="bold")
        summary.add_row("项目数:", f"[cyan]{project_count}[/cyan] 个")
        summary.add_row("总工时:", f"[green]{format_duration(total_duration)}[/green]")
        summary.add_row("总费用:", f"[bold yellow]{format_money(total_cost)}[/bold yellow]")

        self.console.print(Panel(summary, title="💼 今日汇总", border_style="green"))
        self.console.print()

    def print_weekly_report(self, data: Dict[str, Any]) -> None:
        if data.get("empty"):
            self.console.print(f"[yellow]本周暂无记录[/yellow]")
            return

        week_start_str = data["week_start_str"]
        day_sections = data["day_sections"]
        work_days = data["work_days"]
        week_total_duration = data["week_total_duration"]
        week_total_cost = data["week_total_cost"]

        self.console.print()
        self.console.print(f"[bold blue]📆 周报 - {week_start_str} 起[/bold blue]")
        self.console.print()

        for ds in day_sections:
            day_key = ds["day_key"]
            day_total = ds["day_total"]
            proj_rows = ds["proj_rows"]

            day_title = f"[cyan]{day_key}[/cyan] - [green]{format_duration(day_total)}[/green]"
            day_panel = Table(box=box.SIMPLE, show_header=False)
            day_panel.add_column(style="magenta", width=20)
            day_panel.add_column(style="green", width=10, justify="right")
            day_panel.add_column()

            for pr in proj_rows:
                day_panel.add_row(
                    pr["proj_name"],
                    format_duration_short(pr["duration"]),
                    pr["notes_str"],
                )

            self.console.print(Panel(day_panel, title=day_title, border_style="blue"))

        summary = Table(box=None, show_header=False, padding=(0, 2))
        summary.add_column("项目", style="bold", justify="right", width=15)
        summary.add_column("值", style="bold")
        summary.add_row("工作天数:", f"[cyan]{work_days}[/cyan] 天")
        summary.add_row("总工时:", f"[green]{format_duration(week_total_duration)}[/green]")
        summary.add_row("总费用:", f"[bold yellow]{format_money(week_total_cost)}[/bold yellow]")

        self.console.print(Panel(summary, title="💼 本周汇总", border_style="green"))
        self.console.print()

    def export_csv(self, data: Dict[str, Any], output_path: Optional[str] = None) -> Optional[str]:
        if "error" in data:
            self.console.print(f"[red]错误: {data['error']}[/red]")
            return None

        if data.get("empty"):
            self.console.print(f"[yellow]没有可导出的记录[/yellow]")
            return None

        if not output_path:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"ttracker_report_{timestamp}.csv"
            output_path = str(Path.cwd() / filename)

        try:
            with open(output_path, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.writer(f)
                writer.writerow([
                    "开始时间", "结束时间", "时长(秒)", "时长(小时)",
                    "项目ID", "项目名称", "客户名称", "小时费率", "费用", "备注", "标签"
                ])

                for row in data["csv_rows"]:
                    writer.writerow([
                        row["start_time"],
                        row["end_time"],
                        row["duration_seconds"],
                        row["duration_hours"],
                        row["project_id"],
                        row["project_name"],
                        row["client"],
                        row["rate"],
                        row["cost"],
                        row["note"],
                        row["tags"],
                    ])

                writer.writerow([])
                writer.writerow(["", "", "去重合计", round(data["total_duration"] / 3600.0, 4),
                                 "", "", "", "", data["total_cost"], "", ""])

            return output_path

        except OSError as e:
            self.console.print(f"[red]导出文件失败: {e}[/red]")
            return None

    def export_markdown(self, data: Dict[str, Any], output_path: Optional[str] = None) -> Optional[str]:
        if "error" in data:
            self.console.print(f"[red]错误: {data['error']}[/red]")
            return None

        if data.get("empty"):
            self.console.print(f"[yellow]没有可导出的记录[/yellow]")
            return None

        desc = data["desc"]
        generated_at = data["generated_at"]
        project_sections = data["project_sections"]
        project_count = data["project_count"]
        total_duration = data["total_duration"]
        total_cost = data["total_cost"]

        lines = []
        lines.append(f"# 📊 工时报表 - {desc}")
        lines.append("")
        lines.append(f"_生成时间: {generated_at}_")
        lines.append("")

        for ps in project_sections:
            proj_name = ps["proj_name"]
            client = ps["client"]
            rate = ps["rate"]
            tags = ps["tags"]
            proj_total = ps["proj_total"]
            proj_cost = ps["proj_cost"]
            entry_rows = ps["entry_rows"]

            lines.append(f"## 📁 {proj_name}")
            if client:
                lines.append(f"**客户:** {client}  ")
                lines.append(f"**费率:** ¥{rate:.2f}/小时  ")
            if tags:
                lines.append(f"**标签:** {', '.join(tags)}  ")
            lines.append(f"**总时长:** {format_duration(proj_total)}  ")
            lines.append(f"**费用:** ¥{proj_cost:.2f}  ")
            lines.append("")
            lines.append("| 开始时间 | 结束时间 | 时长 | 备注 |")
            lines.append("| --- | --- | ---: | --- |")

            for er in entry_rows:
                lines.append(f"| {er['start_s']} | {er['end_s']} | {format_duration_short(er['duration'])} | {er['note']} |")

            lines.append("")

        lines.append("## 💼 汇总")
        lines.append("")
        lines.append(f"| 项目 | 值 |")
        lines.append("| --- | ---: |")
        lines.append(f"| 项目数量 | {project_count} 个 |")
        lines.append(f"| 总工时 | {format_duration(total_duration)} |")
        lines.append(f"| 总费用 | ¥{total_cost:.2f} |")
        lines.append("")

        if not output_path:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"ttracker_report_{timestamp}.md"
            output_path = str(Path.cwd() / filename)

        try:
            with open(output_path, "w", encoding="utf-8") as f:
                f.write("\n".join(lines))
            return output_path
        except OSError as e:
            self.console.print(f"[red]导出文件失败: {e}[/red]")
            return None
