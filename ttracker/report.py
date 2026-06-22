import csv
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional, Tuple

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box
from rich.text import Text

from . import db
from .models import Project, TimeEntry
from .timer import format_duration, format_duration_short, format_money


console = Console()


def get_date_range(period: str, value: Optional[str] = None) -> Tuple[datetime, datetime, str]:
    """
    根据参数获取日期范围和描述。
    period: today, week, month, all
    value: 当 period=month 时为 YYYY-MM
    返回: (开始时间, 结束时间, 描述)
    """
    now = datetime.now()

    if period == "today":
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=1)
        desc = f"{start.strftime('%Y年%m月%d日')} 今日"
    elif period == "week":
        start = now - timedelta(days=now.weekday())
        start = start.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=7)
        desc = f"{start.strftime('%Y年%m月%d日')} 起 本周"
    elif period == "month":
        if value:
            try:
                year, month = map(int, value.split("-"))
                start = datetime(year, month, 1)
            except (ValueError, AttributeError):
                raise ValueError(f"月份格式错误: {value}，请使用 YYYY-MM 格式")
        else:
            start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        if start.month == 12:
            end = datetime(start.year + 1, 1, 1)
        else:
            end = datetime(start.year, start.month + 1, 1)
        desc = f"{start.strftime('%Y年%m月')} 月度"
    elif period == "all":
        start = datetime(2000, 1, 1)
        end = datetime(2099, 12, 31)
        desc = "全部记录"
    else:
        raise ValueError(f"未知的周期: {period}")

    return start, end, desc


def print_log_entries(period: str = "today", month: Optional[str] = None,
                      project_name: Optional[str] = None) -> None:
    """打印时间记录列表"""
    try:
        start, end, desc = get_date_range(period, month)
    except ValueError as e:
        console.print(f"[red]错误: {e}[/red]")
        return

    if project_name:
        project = db.get_project_by_name(project_name)
        if not project:
            console.print(f"[red]项目 '{project_name}' 不存在[/red]")
            return
        entries = db.get_time_entries(project_id=project.id)
        desc = f"项目 '{project_name}' 全部记录"
    else:
        entries = db.get_time_entries(start, end)

    if not entries:
        console.print(f"[yellow]{desc}暂无记录[/yellow]")
        return

    table = Table(title=f"📋 {desc} - 工时记录", box=box.ROUNDED, show_lines=False)
    table.add_column("开始时间", style="cyan", no_wrap=True)
    table.add_column("结束时间", style="cyan", no_wrap=True)
    table.add_column("时长", style="green", justify="right")
    table.add_column("项目", style="magenta")
    table.add_column("备注", style="white")

    total_duration = 0
    total_cost = 0.0

    for entry in entries:
        start_str = entry.start_time.strftime("%Y-%m-%d %H:%M")
        end_str = entry.end_time.strftime("%H:%M") if entry.end_time else "-"
        project_display = entry.project_name or f"#{entry.project_id}"

        project = db.get_project_by_id(entry.project_id)
        if project:
            cost = (entry.duration / 3600.0) * project.rate
            total_cost += cost

        table.add_row(
            start_str,
            end_str,
            format_duration(entry.duration),
            project_display,
            entry.note or "-",
        )
        total_duration += entry.duration

    console.print(table)

    summary = Table(box=None, show_header=False, padding=(0, 2))
    summary.add_column("项目", style="bold", justify="right")
    summary.add_column("值", style="bold")
    summary.add_row("总时长:", f"[green]{format_duration(total_duration)}[/green]")
    summary.add_row("总费用:", f"[bold yellow]{format_money(total_cost)}[/bold yellow]")

    console.print(Panel(summary, title="📊 汇总", border_style="blue"))


def print_report(period: str = "week", month: Optional[str] = None) -> None:
    """生成报表：按项目汇总时长和费用，表格 + 柱状图"""
    try:
        start, end, desc = get_date_range(period, month)
    except ValueError as e:
        console.print(f"[red]错误: {e}[/red]")
        return

    results = db.get_entries_by_project(start, end)

    if not results:
        console.print(f"[yellow]{desc}暂无数据[/yellow]")
        return

    console.print()
    console.print(f"[bold blue]{'=' * 50}[/bold blue]")
    console.print(f"[bold blue]  📈 {desc}项目报表[/bold blue]")
    console.print(f"[bold blue]{'=' * 50}[/bold blue]")
    console.print()

    table = Table(title="按项目汇总", box=box.ROUNDED)
    table.add_column("项目名称", style="magenta", no_wrap=True)
    table.add_column("客户", style="cyan")
    table.add_column("费率", style="yellow", justify="right")
    table.add_column("时长", style="green", justify="right")
    table.add_column("费用", style="bold yellow", justify="right")

    total_duration = 0
    total_cost = 0.0
    max_duration = 0

    for project, duration, cost in results:
        table.add_row(
            project.name,
            project.client or "-",
            format_money(project.rate) + "/小时",
            format_duration_short(duration),
            format_money(cost),
        )
        total_duration += duration
        total_cost += cost
        if duration > max_duration:
            max_duration = duration

    table.add_row(
        "[bold]合计[/bold]",
        "",
        "",
        f"[bold green]{format_duration_short(total_duration)}[/bold green]",
        f"[bold]{format_money(total_cost)}[/bold]",
        end_section=True,
    )

    console.print(table)
    console.print()

    console.print("[bold blue]📊 时长分布图[/bold blue]")
    console.print()

    bar_table = Table(box=None, show_header=False, padding=(0, 1))
    bar_table.add_column("项目", width=20)
    bar_table.add_column("分布", width=50)
    bar_table.add_column("时长", justify="right", width=10)

    MAX_BAR_WIDTH = 40
    for project, duration, cost in results:
        if max_duration > 0:
            ratio = duration / max_duration
        else:
            ratio = 0
        filled = int(MAX_BAR_WIDTH * ratio)
        bar_str = "█" * filled + "░" * (MAX_BAR_WIDTH - filled)
        bar_text = Text(bar_str, style="green")
        bar_table.add_row(
            f"[magenta]{project.name}[/magenta]",
            bar_text,
            f"[green]{format_duration_short(duration)}[/green]",
        )

    console.print(bar_table)
    console.print()

    summary = Table(box=None, show_header=False, padding=(0, 2))
    summary.add_column("项目", style="bold", justify="right", width=15)
    summary.add_column("值", style="bold")
    summary.add_row("项目数量:", f"[cyan]{len(results)}[/cyan] 个")
    summary.add_row("总工时:", f"[green]{format_duration(total_duration)}[/green]")
    summary.add_row("总费用:", f"[bold yellow]{format_money(total_cost)}[/bold yellow]")

    console.print(Panel(summary, title="💼 最终汇总", border_style="green"))
    console.print()


def export_csv(period: str = "all", month: Optional[str] = None,
               project_name: Optional[str] = None, output_path: Optional[str] = None) -> Optional[str]:
    """导出 CSV 报表"""
    try:
        start, end, desc = get_date_range(period, month)
    except ValueError as e:
        console.print(f"[red]错误: {e}[/red]")
        return None

    if project_name:
        project = db.get_project_by_name(project_name)
        if not project:
            console.print(f"[red]项目 '{project_name}' 不存在[/red]")
            return None
        entries = db.get_time_entries(project_id=project.id)
    else:
        entries = db.get_time_entries(start, end)

    if not entries:
        console.print(f"[yellow]没有可导出的记录[/yellow]")
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
                "项目ID", "项目名称", "客户名称", "小时费率", "费用", "备注"
            ])

            total_duration = 0
            total_cost = 0.0

            for entry in entries:
                project = db.get_project_by_id(entry.project_id)
                project_name_out = project.name if project else ""
                client = project.client if project else ""
                rate = project.rate if project else 0.0
                duration_hours = entry.duration / 3600.0
                cost = duration_hours * rate

                writer.writerow([
                    entry.start_time.strftime("%Y-%m-%d %H:%M:%S"),
                    entry.end_time.strftime("%Y-%m-%d %H:%M:%S") if entry.end_time else "",
                    entry.duration,
                    round(duration_hours, 4),
                    entry.project_id,
                    project_name_out,
                    client,
                    rate,
                    round(cost, 2),
                    entry.note or "",
                ])
                total_duration += entry.duration
                total_cost += cost

            writer.writerow([])
            writer.writerow(["", "", "合计", round(total_duration / 3600.0, 4),
                             "", "", "", "", round(total_cost, 2), ""])

        return output_path

    except OSError as e:
        console.print(f"[red]导出文件失败: {e}[/red]")
        return None
