import sys
import re
from typing import Optional, List

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich import box

from . import db
from . import timer
from . import report
from .timer import format_duration, format_duration_short, format_money


console = Console()


def budget_progress_bar(used: float, limit: float, width: int = 20) -> Text:
    """生成带颜色的预算进度条"""
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


def budget_percent(used: float, limit: float) -> str:
    if limit <= 0:
        return "-"
    pct = (used / limit) * 100
    return f"{pct:.1f}%"


@click.group()
@click.version_option(version="0.2.0", prog_name="tt")
def cli():
    """命令行工时追踪工具 - 管理外包项目工时与结算"""
    db.init_db()


# ─── 项目管理命令组 ───────────────────────────────────────────────

@cli.group()
def project():
    """项目管理：增删改查、标签、预算"""
    pass


@project.command("add")
@click.argument("name")
@click.option("--client", "-c", default="", help="客户名称")
@click.option("--rate", "-r", type=float, default=0.0, help="小时费率")
@click.option("--desc", "-d", default="", help="项目描述")
def project_add(name, client, rate, desc):
    """添加新项目"""
    existing = db.get_project_by_name(name)
    if existing:
        console.print(f"[red]错误: 项目 '{name}' 已存在[/red]")
        sys.exit(1)

    pid = db.add_project(name, desc, client, rate)
    console.print(f"[green]✓ 项目添加成功[/green]")
    _print_project_table([db.get_project_by_id(pid)])


@project.command("list")
def project_list():
    """列出所有项目（含标签和预算进度）"""
    projects = db.get_all_projects()
    if not projects:
        console.print("[yellow]暂无项目，使用 'tt project add' 添加[/yellow]")
        return
    _print_project_table(projects)


def _print_project_table(projects):
    table = Table(title="项目列表", box=box.ROUNDED)
    table.add_column("ID", style="cyan", justify="right", no_wrap=True)
    table.add_column("名称", style="magenta")
    table.add_column("客户", style="cyan")
    table.add_column("费率", style="yellow", justify="right")
    table.add_column("标签", style="blue")
    table.add_column("工时预算", style="green")
    table.add_column("费用预算", style="yellow")
    table.add_column("描述", style="white")

    for p in projects:
        tag_str = ", ".join(p.tags) if p.tags else "-"

        total_sec, total_cost = db.get_project_total_usage(p.id)
        total_hours = total_sec / 3600.0

        if p.budget_hours:
            hours_pct = budget_percent(total_hours, p.budget_hours)
            hours_bar = budget_progress_bar(total_hours, p.budget_hours, 10)
            hours_cell = Text()
            hours_cell.append(hours_bar)
            hours_cell.append(f" {hours_pct}", style="dim")
        else:
            hours_cell = Text("-", style="dim")

        if p.budget_cost:
            cost_pct = budget_percent(total_cost, p.budget_cost)
            cost_bar = budget_progress_bar(total_cost, p.budget_cost, 10)
            cost_cell = Text()
            cost_cell.append(cost_bar)
            cost_cell.append(f" {cost_pct}", style="dim")
        else:
            cost_cell = Text("-", style="dim")

        table.add_row(
            str(p.id),
            p.name,
            p.client or "-",
            format_money(p.rate) + "/h",
            tag_str,
            hours_cell,
            cost_cell,
            p.description or "-",
        )

    console.print(table)


@project.command("delete")
@click.argument("project_id", type=int)
def project_delete(project_id):
    """删除指定 ID 的项目"""
    project = db.get_project_by_id(project_id)
    if not project:
        console.print(f"[red]错误: 项目 ID {project_id} 不存在[/red]")
        sys.exit(1)

    if click.confirm(f"确定删除项目 '{project.name}'？相关工时记录、标签、预算都会被移除。"):
        if db.delete_project(project_id):
            console.print(f"[green]✓ 项目 '{project.name}' 已删除[/green]")
        else:
            console.print(f"[red]删除失败[/red]")


@project.command("update")
@click.argument("project_id", type=int)
@click.option("--name", "-n", help="新名称")
@click.option("--client", "-c", help="新客户名称")
@click.option("--rate", "-r", type=float, help="新小时费率")
@click.option("--desc", "-d", help="新描述")
def project_update(project_id, name, client, rate, desc):
    """更新项目信息"""
    project = db.get_project_by_id(project_id)
    if not project:
        console.print(f"[red]错误: 项目 ID {project_id} 不存在[/red]")
        sys.exit(1)

    if all(x is None for x in [name, client, rate, desc]):
        console.print("[yellow]没有指定任何更新字段[/yellow]")
        return

    updated = db.update_project(
        project_id,
        name=name,
        description=desc,
        client=client,
        rate=rate,
    )

    if updated:
        console.print(f"[green]✓ 项目信息已更新[/green]")
        _print_project_table([db.get_project_by_id(project_id)])
    else:
        console.print(f"[red]更新失败[/red]")


@project.command("tag")
@click.argument("project_id", type=int)
@click.option("--add", "-a", "add_tags", help="要添加的标签，多个用逗号分隔，如: 前端,React,设计")
@click.option("--remove", "-r", "remove_tags", help="要移除的标签，多个用逗号分隔")
def project_tag(project_id, add_tags, remove_tags):
    """管理项目标签。使用: tt project tag 3 --add 前端,React ; tt project tag 3 --remove React"""
    project = db.get_project_by_id(project_id)
    if not project:
        console.print(f"[red]错误: 项目 ID {project_id} 不存在[/red]")
        sys.exit(1)

    if not add_tags and not remove_tags:
        tags = db.get_project_tags(project_id)
        if tags:
            console.print(f"[cyan]项目 '{project.name}' 的标签:[/cyan] " + ", ".join(tags))
        else:
            console.print(f"[yellow]项目 '{project.name}' 暂无标签[/yellow]")
        return

    add_list = _parse_tag_list(add_tags) if add_tags else []
    remove_list = _parse_tag_list(remove_tags) if remove_tags else []

    for tag in add_list:
        db.add_tag_to_project(project_id, tag)
        console.print(f"[green]✓ 已添加标签:[/green] {tag}")

    for tag in remove_list:
        ok = db.remove_tag_from_project(project_id, tag)
        if ok:
            console.print(f"[green]✓ 已移除标签:[/green] {tag}")
        else:
            console.print(f"[yellow]⚠  标签 '{tag}' 不存在或未绑定[/yellow]")

    console.print()
    _print_project_table([db.get_project_by_id(project_id)])


def _parse_tag_list(tag_str: str) -> List[str]:
    import re
    tags = re.split(r'[,，\s]+', tag_str.strip())
    return [t.strip() for t in tags if t.strip()]


@project.command("budget")
@click.argument("project_id", type=int)
@click.option("--hours", type=float, help="总工时上限（小时），设 0 或留空清除")
@click.option("--cost", type=float, help="总费用上限（元），设 0 或留空清除")
def project_budget(project_id, hours, cost):
    """设置或清除项目预算。使用: tt project budget 3 --hours 40 --cost 12000"""
    project = db.get_project_by_id(project_id)
    if not project:
        console.print(f"[red]错误: 项目 ID {project_id} 不存在[/red]")
        sys.exit(1)

    if hours is None and cost is None:
        total_sec, total_cost = db.get_project_total_usage(project_id)
        total_hours = total_sec / 3600.0

        content = Table(box=None, show_header=False, padding=(0, 1))
        content.add_column(style="bold cyan", width=12)
        content.add_column()

        content.add_row("项目:", f"[magenta]{project.name}[/magenta]")
        content.add_row(
            "工时预算:",
            f"{format_duration_short(total_sec)} / "
            f"{project.budget_hours:.0f}h ({budget_percent(total_hours, project.budget_hours)})"
            if project.budget_hours else "未设置",
        )
        content.add_row(
            "费用预算:",
            f"¥{total_cost:.2f} / ¥{project.budget_cost:.2f} ({budget_percent(total_cost, project.budget_cost)})"
            if project.budget_cost else "未设置",
        )
        console.print(Panel(content, title="💰 预算概览", border_style="yellow"))
        return

    if hours is not None:
        hours_val = hours if hours > 0 else None
        db.set_budget_hours(project_id, hours_val)
        if hours_val:
            console.print(f"[green]✓ 已设置工时预算:[/green] {hours_val} 小时")
        else:
            console.print(f"[yellow]⚠  已清除工时预算[/yellow]")

    if cost is not None:
        cost_val = cost if cost > 0 else None
        db.set_budget_cost(project_id, cost_val)
        if cost_val:
            console.print(f"[green]✓ 已设置费用预算:[/green] ¥{cost_val:.2f}")
        else:
            console.print(f"[yellow]⚠  已清除费用预算[/yellow]")

    console.print()
    _print_project_table([db.get_project_by_id(project_id)])


# ─── 计时命令 ────────────────────────────────────────────────────

@cli.command("start")
@click.argument("project_name")
def cmd_start(project_name):
    """开始为指定项目计时"""
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
            pct = budget_percent(total_hours, project.budget_hours)
            bar = budget_progress_bar(total_hours, project.budget_hours)
            console.print(f"  [cyan]工时进度:[/cyan] {bar} {format_duration_short(total_sec)}/{project.budget_hours:.0f}h ({pct})")
    else:
        console.print(f"[red]✗ {msg}[/red]")
        sys.exit(1)


@cli.command("stop")
@click.option("--note", "-n", default="", help="本次工作的备注")
def cmd_stop(note):
    """停止当前计时并记录"""
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
                pct = budget_percent(total_hours, project.budget_hours)
                bar = budget_progress_bar(total_hours, project.budget_hours)
                warn = ""
                if total_hours >= project.budget_hours:
                    warn = " [red]⚠ 已超出预算![/red]"
                elif total_hours >= project.budget_hours * 0.8:
                    warn = " [yellow]⚠ 接近预算[/yellow]"
                console.print(f"  [cyan]累计进度:[/cyan] {bar} {format_duration_short(total_sec)}/{project.budget_hours:.0f}h ({pct}){warn}")
    else:
        console.print(f"[yellow]ℹ  {msg}[/yellow]")


@cli.command("status")
def cmd_status():
    """查看当前计时状态"""
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
                pct = budget_percent(total_hours, project.budget_hours)
                bar = budget_progress_bar(total_hours, project.budget_hours)
                content.add_row(
                    "工时预算:",
                    f"{bar} {format_duration_short(total_sec)} / {project.budget_hours:.0f}h ({pct})",
                )
            else:
                content.add_row("工时预算:", "未设置")

            if project.budget_cost:
                pct = budget_percent(total_cost, project.budget_cost)
                bar = budget_progress_bar(total_cost, project.budget_cost)
                content.add_row(
                    "费用预算:",
                    f"{bar} ¥{total_cost:.0f} / ¥{project.budget_cost:.0f} ({pct})",
                )
            else:
                content.add_row("费用预算:", "未设置")

        console.print(Panel(content, title="▶ 计时进行中", border_style="green"))
    else:
        console.print(f"[yellow]⏸  {msg}[/yellow]")


@cli.command("log")
@click.argument("args", nargs=-1)
@click.option("--week", "period", flag_value="week", help="查看本周记录")
@click.option("--month", "month_val", help="查看指定月份 (YYYY-MM)")
@click.option("--project", "project_name", help="查看/补录指定项目的记录")
@click.option("--tag", "tag_name", help="按标签筛选记录")
def cmd_log(args, period, month_val, project_name, tag_name):
    """查看工时记录或手动补录。
    \b
    查看记录:
      tt log                    # 今天
      tt log --week             # 本周
      tt log --month 2024-06    # 指定月
      tt log --project "官网改版"  # 指定项目
      tt log --tag "前端"        # 按标签筛选
    \b
    手动补录 (当前计时项目):
      tt start "官网改版"
      tt log 2h "修复首页样式bug"
    \b
    手动补录 (指定项目):
      tt log 2h30m "写接口文档" --project "官网改版"
    """
    if len(args) >= 1 and not period and not month_val and not tag_name:
        first_arg = args[0]
        first_arg_stripped = first_arg.strip()
        starts_with_digit = bool(first_arg_stripped) and first_arg_stripped[0].isdigit()

        looks_like_duration = (
            starts_with_digit and
            (first_arg_stripped[-1].lower() in ('h', 'm', 's') or
             bool(re.search(r'\d+[hms]', first_arg_stripped.lower())))
        )

        strongly_looks_like_manual_log = looks_like_duration or (
            starts_with_digit and (project_name or len(args) >= 2)
        )

        if strongly_looks_like_manual_log:
            duration_str = first_arg
            note = " ".join(args[1:]) if len(args) > 1 else ""
            _do_manual_log(duration_str, note, project_name)
            return
        else:
            try:
                timer.parse_duration(first_arg)
                duration_str = first_arg
                note = " ".join(args[1:]) if len(args) > 1 else ""
                _do_manual_log(duration_str, note, project_name)
                return
            except ValueError:
                pass

    if month_val:
        report.print_log_entries("month", month_val, project_name, tag_name)
    elif period:
        report.print_log_entries(period, None, project_name, tag_name)
    elif project_name and not args:
        report.print_log_entries("all", None, project_name, tag_name)
    elif tag_name:
        report.print_log_entries("all", None, None, tag_name)
    else:
        report.print_log_entries("today", None, project_name, tag_name)


def _do_manual_log(duration_str: str, note: str, target_project: Optional[str] = None):
    resolved_project = None

    if target_project:
        resolved_project = db.get_project_by_name(target_project)
        if not resolved_project:
            console.print(f"[red]✗ 项目 '{target_project}' 不存在[/red]")
            sys.exit(1)
    else:
        is_active, _, project, _, _ = timer.get_timer_status()
        if is_active and project:
            resolved_project = project
        else:
            console.print("[red]✗ 当前没有正在计时的项目，请指定项目名[/red]")
            console.print("[yellow]用法: tt log 2h \"修bug\" --project \"官网改版\"[/yellow]")
            sys.exit(1)

    success, msg, _, duration = timer.manual_log(resolved_project.name, duration_str, note)
    if success:
        hours = duration / 3600.0
        cost = hours * resolved_project.rate
        console.print(f"[green]✓ {msg}[/green]")
        console.print(f"  [cyan]项目:[/cyan] {resolved_project.name}")
        console.print(f"  [cyan]时长:[/cyan] [green]{format_duration(duration)}[/green] ({hours:.2f} 小时)")
        if resolved_project.rate > 0:
            console.print(f"  [cyan]费用:[/cyan] [bold yellow]{format_money(cost)}[/bold yellow]")
        if note:
            console.print(f"  [cyan]备注:[/cyan] {note}")
    else:
        console.print(f"[red]✗ {msg}[/red]")
        sys.exit(1)


# ─── 报表命令 ────────────────────────────────────────────────────

@cli.command("report")
@click.option("--daily", "period", flag_value="daily", help="生成日报")
@click.option("--weekly", "period", flag_value="weekly", help="生成周报（按天分组）")
@click.option("--week", "period", flag_value="week", help="生成周汇总报表")
@click.option("--month", "period", flag_value="month", help="生成月报表 (默认当月)")
@click.option("--month-value", "month_val", help="指定月份 YYYY-MM")
@click.option("--all", "period", flag_value="all", help="生成全部报表")
@click.option("--tag", "tag_name", help="按标签筛选")
@click.option("--export", "export_format", type=click.Choice(["csv", "markdown", "md"]), help="导出格式")
@click.option("--output", "-o", "output_path", help="导出文件路径")
@click.option("--project", "project_name", help="仅导出指定项目")
def cmd_report(period, month_val, tag_name, export_format, output_path, project_name):
    """生成报表（日/周/月/全部），支持 CSV / Markdown 导出"""

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


# ─── 备份与恢复 ───────────────────────────────────────────────────

@cli.command("backup")
@click.option("--output", "-o", "output_path", help="备份文件路径")
def cmd_backup(output_path):
    """导出所有数据为 JSON 备份文件"""
    from .backup import export_backup
    result = export_backup(output_path)
    if result:
        console.print(f"[green]✓ 备份成功:[/green] [cyan]{result}[/cyan]")
    else:
        console.print(f"[red]✗ 备份失败[/red]")
        sys.exit(1)


@cli.command("restore")
@click.argument("backup_file")
@click.option("--yes", "-y", is_flag=True, help="跳过确认提示")
def cmd_restore(backup_file, yes):
    """从 JSON 备份文件恢复数据（覆盖当前数据库）"""
    from pathlib import Path
    if not Path(backup_file).exists():
        console.print(f"[red]✗ 备份文件不存在: {backup_file}[/red]")
        sys.exit(1)

    if not yes:
        if not click.confirm(
            "⚠  恢复将覆盖当前数据库的所有数据，确定继续吗？",
            default=False,
        ):
            console.print("[yellow]已取消恢复[/yellow]")
            return

    from .backup import import_backup
    result = import_backup(backup_file)
    if result:
        console.print(f"[green]✓ 恢复成功: 已导入 {result['projects']} 个项目, "
                      f"{result['time_entries']} 条记录[/green]")
    else:
        console.print(f"[red]✗ 恢复失败[/red]")
        sys.exit(1)


if __name__ == "__main__":
    cli()
