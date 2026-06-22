import csv
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional, Tuple, Dict
from collections import defaultdict

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
    now = datetime.now()

    if period == "today" or period == "daily":
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=1)
        desc = f"{start.strftime('%Y年%m月%d日')} 今日"
    elif period == "week":
        start = now - timedelta(days=now.weekday())
        start = start.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=7)
        desc = f"{start.strftime('%Y年%m月%d日')} 起 本周"
    elif period == "weekly":
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


def _budget_bar(used: float, limit: float, width: int = 20) -> Text:
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


def _budget_pct(used: float, limit: float) -> str:
    if limit <= 0:
        return "-"
    return f"{(used / limit) * 100:.1f}%"


def print_log_entries(period: str = "today", month: Optional[str] = None,
                      project_name: Optional[str] = None,
                      tag_name: Optional[str] = None) -> None:
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
        entries = db.get_time_entries(project_id=project.id, tag_name=tag_name)
        desc = f"项目 '{project_name}' 全部记录"
    elif tag_name and period == "all":
        entries = db.get_time_entries(tag_name=tag_name)
        desc = f"标签 '{tag_name}' 全部记录"
    else:
        entries = db.get_time_entries(start, end, tag_name=tag_name)
        if tag_name:
            desc += f" (标签: {tag_name})"

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


def print_report(period: str = "week", month: Optional[str] = None,
                 tag_name: Optional[str] = None) -> None:
    try:
        start, end, desc = get_date_range(period, month)
    except ValueError as e:
        console.print(f"[red]错误: {e}[/red]")
        return

    results = db.get_entries_by_project(start, end, tag_name)

    if not results:
        console.print(f"[yellow]{desc}暂无数据[/yellow]")
        return

    if tag_name:
        desc += f" (标签: {tag_name})"

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
    table.add_column("工时预算", style="green")
    table.add_column("费用预算", style="yellow")

    total_duration = 0
    total_cost = 0.0
    max_duration = 0

    for project, duration, cost in results:
        hours = duration / 3600.0

        if project.budget_hours:
            hpct = _budget_pct(hours, project.budget_hours)
            hbar = _budget_bar(hours, project.budget_hours, 10)
            hcell = Text()
            hcell.append(hbar)
            hcell.append(f" {hpct}", style="dim")
        else:
            hcell = Text("-", style="dim")

        if project.budget_cost:
            cpct = _budget_pct(cost, project.budget_cost)
            cbar = _budget_bar(cost, project.budget_cost, 10)
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
        "",
        "",
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


# ─── 日报 ────────────────────────────────────────────────────────

def print_daily_report() -> None:
    """生成日报：按项目列出每个任务的时长和备注"""
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    tomorrow = today + timedelta(days=1)
    date_str = today.strftime("%Y年%m月%d日 %A")

    entries = db.get_time_entries(today, tomorrow)
    if not entries:
        console.print(f"[yellow]{date_str} 今日暂无记录[/yellow]")
        return

    by_project: Dict[str, List[TimeEntry]] = defaultdict(list)
    for entry in entries:
        name = entry.project_name or f"#{entry.project_id}"
        by_project[name].append(entry)

    console.print()
    console.print(f"[bold blue]📅 日报 - {date_str}[/bold blue]")
    console.print()

    total_duration = 0
    total_cost = 0.0

    for proj_name, items in sorted(by_project.items(),
                                   key=lambda x: sum(e.duration for e in x[1]), reverse=True):
        proj_total = sum(e.duration for e in items)
        project = db.get_project_by_name(proj_name)
        proj_cost = (proj_total / 3600.0) * (project.rate if project else 0)

        panel_title = f"[magenta]{proj_name}[/magenta] - [green]{format_duration(proj_total)}[/green]"
        if project and project.client:
            panel_title += f"  [cyan]({project.client})[/cyan]"

        tbl = Table(box=box.SIMPLE, show_header=False)
        tbl.add_column(style="cyan", width=12)
        tbl.add_column(style="green", width=10, justify="right")
        tbl.add_column()

        for e in sorted(items, key=lambda x: x.start_time):
            tbl.add_row(
                e.start_time.strftime("%H:%M") + "-" + (e.end_time.strftime("%H:%M") if e.end_time else ""),
                format_duration_short(e.duration),
                e.note or "(无备注)",
            )

        console.print(Panel(tbl, title=panel_title, border_style="blue"))
        total_duration += proj_total
        total_cost += proj_cost

    summary = Table(box=None, show_header=False, padding=(0, 2))
    summary.add_column("项目", style="bold", justify="right", width=15)
    summary.add_column("值", style="bold")
    summary.add_row("项目数:", f"[cyan]{len(by_project)}[/cyan] 个")
    summary.add_row("总工时:", f"[green]{format_duration(total_duration)}[/green]")
    summary.add_row("总费用:", f"[bold yellow]{format_money(total_cost)}[/bold yellow]")

    console.print(Panel(summary, title="💼 今日汇总", border_style="green"))
    console.print()


# ─── 周报 ────────────────────────────────────────────────────────

def print_weekly_report() -> None:
    """生成周报：按天分组，每天下面列出项目及时长"""
    now = datetime.now()
    week_start = now - timedelta(days=now.weekday())
    week_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)
    week_end = week_start + timedelta(days=7)

    entries = db.get_time_entries(week_start, week_end)
    if not entries:
        console.print(f"[yellow]本周暂无记录[/yellow]")
        return

    by_day: Dict[str, Dict[str, List[TimeEntry]]] = defaultdict(lambda: defaultdict(list))
    for entry in entries:
        day_key = entry.start_time.strftime("%Y-%m-%d %A")
        name = entry.project_name or f"#{entry.project_id}"
        by_day[day_key][name].append(entry)

    console.print()
    console.print(f"[bold blue]📆 周报 - {week_start.strftime('%Y年%m月%d日')} 起[/bold blue]")
    console.print()

    week_total_duration = 0
    week_total_cost = 0.0

    for day_key in sorted(by_day.keys()):
        projects = by_day[day_key]
        day_total = sum(sum(e.duration for e in items) for items in projects.values())
        week_total_duration += day_total

        day_title = f"[cyan]{day_key}[/cyan] - [green]{format_duration(day_total)}[/green]"
        day_panel = Table(box=box.SIMPLE, show_header=False)
        day_panel.add_column(style="magenta", width=20)
        day_panel.add_column(style="green", width=10, justify="right")
        day_panel.add_column()

        day_cost = 0.0
        for proj_name, items in sorted(projects.items(),
                                       key=lambda x: sum(e.duration for e in x[1]), reverse=True):
            proj_total = sum(e.duration for e in items)
            notes = [e.note for e in items if e.note]
            notes_str = "; ".join(notes) if notes else "(无备注)"
            project = db.get_project_by_name(proj_name)
            proj_cost = (proj_total / 3600.0) * (project.rate if project else 0)
            day_cost += proj_cost

            day_panel.add_row(
                proj_name,
                format_duration_short(proj_total),
                notes_str[:60] + "..." if len(notes_str) > 60 else notes_str,
            )

        week_total_cost += day_cost
        console.print(Panel(day_panel, title=day_title, border_style="blue"))

    summary = Table(box=None, show_header=False, padding=(0, 2))
    summary.add_column("项目", style="bold", justify="right", width=15)
    summary.add_column("值", style="bold")
    summary.add_row("工作天数:", f"[cyan]{len(by_day)}[/cyan] 天")
    summary.add_row("总工时:", f"[green]{format_duration(week_total_duration)}[/green]")
    summary.add_row("总费用:", f"[bold yellow]{format_money(week_total_cost)}[/bold yellow]")

    console.print(Panel(summary, title="💼 本周汇总", border_style="green"))
    console.print()


# ─── CSV 导出 ─────────────────────────────────────────────────────

def export_csv(period: str = "all", month: Optional[str] = None,
               project_name: Optional[str] = None, output_path: Optional[str] = None,
               tag_name: Optional[str] = None) -> Optional[str]:
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
        entries = db.get_time_entries(project_id=project.id, tag_name=tag_name)
    else:
        entries = db.get_time_entries(start, end, tag_name=tag_name)

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
                "项目ID", "项目名称", "客户名称", "小时费率", "费用", "备注", "标签"
            ])

            total_duration = 0
            total_cost = 0.0

            for entry in entries:
                project = db.get_project_by_id(entry.project_id)
                project_name_out = project.name if project else ""
                client = project.client if project else ""
                rate = project.rate if project else 0.0
                tags = ",".join(project.tags) if project else ""
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
                    tags,
                ])
                total_duration += entry.duration
                total_cost += cost

            writer.writerow([])
            writer.writerow(["", "", "合计", round(total_duration / 3600.0, 4),
                             "", "", "", "", round(total_cost, 2), "", ""])

        return output_path

    except OSError as e:
        console.print(f"[red]导出文件失败: {e}[/red]")
        return None


# ─── Markdown 导出 ───────────────────────────────────────────────

def export_markdown(period: str = "week", month: Optional[str] = None,
                    project_name: Optional[str] = None,
                    tag_name: Optional[str] = None,
                    output_path: Optional[str] = None) -> Optional[str]:
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
        entries = db.get_time_entries(project_id=project.id, tag_name=tag_name)
    else:
        entries = db.get_time_entries(start, end, tag_name=tag_name)

    if not entries:
        console.print(f"[yellow]没有可导出的记录[/yellow]")
        return None

    if tag_name:
        desc += f" (标签: {tag_name})"

    lines = []
    lines.append(f"# 📊 工时报表 - {desc}")
    lines.append("")
    lines.append(f"_生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}_")
    lines.append("")

    by_project: Dict[str, List[TimeEntry]] = defaultdict(list)
    for entry in entries:
        name = entry.project_name or f"#{entry.project_id}"
        by_project[name].append(entry)

    total_duration = 0
    total_cost = 0.0

    for proj_name, items in sorted(by_project.items(),
                                   key=lambda x: sum(e.duration for e in x[1]), reverse=True):
        proj_total = sum(e.duration for e in items)
        project = db.get_project_by_name(proj_name)
        proj_cost = (proj_total / 3600.0) * (project.rate if project else 0)
        total_duration += proj_total
        total_cost += proj_cost

        lines.append(f"## 📁 {proj_name}")
        if project and project.client:
            lines.append(f"**客户:** {project.client}  ")
            lines.append(f"**费率:** ¥{project.rate:.2f}/小时  ")
        if project and project.tags:
            lines.append(f"**标签:** {', '.join(project.tags)}  ")
        lines.append(f"**总时长:** {format_duration(proj_total)}  ")
        lines.append(f"**费用:** ¥{proj_cost:.2f}  ")
        lines.append("")
        lines.append("| 开始时间 | 结束时间 | 时长 | 备注 |")
        lines.append("| --- | --- | ---: | --- |")

        for e in sorted(items, key=lambda x: x.start_time):
            start_s = e.start_time.strftime("%Y-%m-%d %H:%M")
            end_s = e.end_time.strftime("%H:%M") if e.end_time else "-"
            lines.append(f"| {start_s} | {end_s} | {format_duration_short(e.duration)} | {e.note or ''} |")

        lines.append("")

    lines.append("## 💼 汇总")
    lines.append("")
    lines.append(f"| 项目 | 值 |")
    lines.append("| --- | ---: |")
    lines.append(f"| 项目数量 | {len(by_project)} 个 |")
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
        console.print(f"[red]导出文件失败: {e}[/red]")
        return None
