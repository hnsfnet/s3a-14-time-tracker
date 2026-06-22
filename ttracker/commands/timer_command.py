import sys

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text

from .. import db
from .. import timer
from ..timer import format_duration, format_duration_short, format_money

console = Console()


class TimerCommand:

    @staticmethod
    def budget_progress_bar(used: float, limit: float, width: int = 20) -> Text:
        if limit <= 0:
            return Text("-" * width, style="dim")
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

    @staticmethod
    def budget_percent(used: float, limit: float) -> str:
        if limit <= 0:
            return "-"
        pct = (used / limit) * 100
        return f"{pct:.1f}%"

    def handle_start(self, project_name):
        success, msg, project, stopped = timer.start_timer(project_name)

        if stopped:
            stopped_id, duration = stopped
            console.print(f"[yellow]⏹  已自动停止上次计时: {format_duration(duration)}[/yellow]")

        if success:
            rate_str = format_money(project.rate) + "/h" if project.rate > 0 else "未设置费率"
            client_str = f" (客户: {project.client})" if project.client else ""
            tag_str = f" [{', '.join(project.tags)}]" if project.tags else ""
            console.print(f"[green]▶  {msg}[/green]")
            console.print(f"  [cyan]项目:[/cyan] {project.name}{client_str}{tag_str}")
            console.print(f"  [cyan]费率:[/cyan] {rate_str}")

            total_sec, total_cost = db.get_project_total_usage(project.id)
            total_hours = total_sec / 3600.0
            if project.budget_hours:
                pct = TimerCommand.budget_percent(total_hours, project.budget_hours)
                bar = TimerCommand.budget_progress_bar(total_hours, project.budget_hours)
                console.print(f"  [cyan]工时进度:[/cyan] {bar} {format_duration_short(total_sec)}/{project.budget_hours:.0f}h ({pct})")
        else:
            console.print(f"[red]✗ {msg}[/red]")
            sys.exit(1)

    def handle_stop(self, note):
        success, msg, project, duration = timer.stop_timer(note)

        if success:
            hours = duration / 3600.0
            cost = hours * (project.rate if project else 0)

            console.print(f"[yellow]⏹  {msg}[/yellow]")
            if project:
                console.print(f"  [cyan]项目:[/cyan] {project.name}")
            console.print(f"  [cyan]时长:[/cyan] [green]{format_duration(duration)}[/green] ({hours:.2f} 小时)")
            if project and project.rate > 0:
                console.print(f"  [cyan]费用:[/cyan] [bold yellow]{format_money(cost)}[/bold yellow]")
            if note:
                console.print(f"  [cyan]备注:[/cyan] {note}")

            if project:
                total_sec, total_cost = db.get_project_total_usage(project.id)
                total_hours = total_sec / 3600.0
                if project.budget_hours:
                    pct = TimerCommand.budget_percent(total_hours, project.budget_hours)
                    bar = TimerCommand.budget_progress_bar(total_hours, project.budget_hours)
                    warn = ""
                    if total_hours >= project.budget_hours:
                        warn = " [red]⚠ 已超出预算![/red]"
                    elif total_hours >= project.budget_hours * 0.8:
                        warn = " [yellow]⚠ 接近预算[/yellow]"
                    console.print(f"  [cyan]累计进度:[/cyan] {bar} {format_duration_short(total_sec)}/{project.budget_hours:.0f}h ({pct}){warn}")
        else:
            console.print(f"[yellow]ℹ  {msg}[/yellow]")

    def handle_status(self):
        is_active, msg, project, duration, start_time = timer.get_timer_status()

        if is_active:
            rate_str = format_money(project.rate) + "/h" if project and project.rate > 0 else "未设置费率"
            current_cost = (duration / 3600.0) * (project.rate if project else 0)

            content = Table(box=None, show_header=False, padding=(0, 1))
            content.add_column(style="bold cyan", width=12)
            content.add_column()
            content.add_row("项目:", f"[magenta]{project.name if project else '未知'}[/magenta]")
            if project and project.client:
                content.add_row("客户:", project.client)
            if project and project.tags:
                content.add_row("标签:", ", ".join(project.tags))
            content.add_row("开始:", f"[cyan]{start_time.strftime('%Y-%m-%d %H:%M:%S')}[/cyan]")
            content.add_row("已计时:", f"[bold green]{format_duration(duration)}[/bold green]")
            if project and project.rate > 0:
                content.add_row("当前费用:", f"[bold yellow]{format_money(current_cost)}[/bold yellow]")
            content.add_row("费率:", rate_str)

            if project:
                total_sec, total_cost = db.get_project_total_usage(project.id)
                total_hours = total_sec / 3600.0

                if project.budget_hours:
                    pct = TimerCommand.budget_percent(total_hours, project.budget_hours)
                    bar = TimerCommand.budget_progress_bar(total_hours, project.budget_hours)
                    content.add_row(
                        "工时预算:",
                        f"{bar} {format_duration_short(total_sec)} / {project.budget_hours:.0f}h ({pct})",
                    )
                else:
                    content.add_row("工时预算:", "未设置")

                if project.budget_cost:
                    pct = TimerCommand.budget_percent(total_cost, project.budget_cost)
                    bar = TimerCommand.budget_progress_bar(total_cost, project.budget_cost)
                    content.add_row(
                        "费用预算:",
                        f"{bar} ¥{total_cost:.0f} / ¥{project.budget_cost:.0f} ({pct})",
                    )
                else:
                    content.add_row("费用预算:", "未设置")

            console.print(Panel(content, title="▶ 计时进行中", border_style="green"))
        else:
            console.print(f"[yellow]⏸  {msg}[/yellow]")
