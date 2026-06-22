import sys
from typing import Optional

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box

from . import db
from . import timer
from . import report
from .timer import format_duration, format_duration_short, format_money


console = Console()


@click.group()
@click.version_option(version="0.1.0", prog_name="tt")
def cli():
    """命令行工时追踪工具 - 管理外包项目工时与结算"""
    db.init_db()


# ─── 项目管理命令组 ───────────────────────────────────────────────

@cli.group()
def project():
    """项目管理：增删改查项目"""
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
    """列出所有项目"""
    projects = db.get_all_projects()
    if not projects:
        console.print("[yellow]暂无项目，使用 'tt project add' 添加[/yellow]")
        return
    _print_project_table(projects)


def _print_project_table(projects):
    table = Table(title="📁 项目列表", box=box.ROUNDED)
    table.add_column("ID", style="cyan", justify="right", no_wrap=True)
    table.add_column("名称", style="magenta")
    table.add_column("客户", style="cyan")
    table.add_column("费率", style="yellow", justify="right")
    table.add_column("描述", style="white")

    for p in projects:
        table.add_row(
            str(p.id),
            p.name,
            p.client or "-",
            format_money(p.rate) + "/h",
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

    if click.confirm(f"确定删除项目 '{project.name}'？相关工时记录也会被移除。"):
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


# ─── 计时命令 ────────────────────────────────────────────────────

@cli.command("start")
@click.argument("project_name")
def cmd_start(project_name):
    """开始为指定项目计时"""
    success, msg, project, stopped = timer.start_timer(project_name)

    if stopped:
        stopped_id, duration = stopped
        active = db.get_active_entry()
        old_project = None
        if active:
            old_project = db.get_project_by_id(active.project_id)
        console.print(f"[yellow]⏹  已自动停止上次计时: {format_duration(duration)}[/yellow]")

    if success:
        rate_str = format_money(project.rate) + "/h" if project.rate > 0 else "未设置费率"
        client_str = f" (客户: {project.client})" if project.client else ""
        console.print(f"[green]▶  {msg}[/green]")
        console.print(f"  [cyan]项目:[/cyan] {project.name}{client_str}")
        console.print(f"  [cyan]费率:[/cyan] {rate_str}")
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
        content.add_column(style="bold cyan", width=10)
        content.add_column()
        content.add_row("项目:", f"[magenta]{project.name if project else '未知'}[/magenta]")
        if project and project.client:
            content.add_row("客户:", project.client)
        content.add_row("开始:", f"[cyan]{start_time.strftime('%Y-%m-%d %H:%M:%S')}[/cyan]")
        content.add_row("已计时:", f"[bold green]{format_duration(duration)}[/bold green]")
        if project and project.rate > 0:
            content.add_row("当前费用:", f"[bold yellow]{format_money(current_cost)}[/bold yellow]")
        content.add_row("费率:", rate_str)

        console.print(Panel(content, title="▶ 计时进行中", border_style="green"))
    else:
        console.print(f"[yellow]⏸  {msg}[/yellow]")


@cli.command("log")
@click.argument("args", nargs=-1)
@click.option("--week", "period", flag_value="week", help="查看本周记录")
@click.option("--month", "month_val", help="查看指定月份 (YYYY-MM)")
@click.option("--project", "project_name", help="查看/补录指定项目的记录")
def cmd_log(args, period, month_val, project_name):
    """查看工时记录或手动补录。
    \b
    查看记录:
      tt log                    # 今天
      tt log --week             # 本周
      tt log --month 2024-06    # 指定月
      tt log --project "官网改版"  # 指定项目
    \b
    手动补录 (当前计时项目):
      tt start "官网改版"
      tt log 2h "修复首页样式bug"
    \b
    手动补录 (指定项目):
      tt log 2h30m "写接口文档" --project "官网改版"
    """

    if len(args) >= 1 and not period and not month_val:
        try:
            timer.parse_duration(args[0])
            is_duration = True
        except ValueError:
            is_duration = False

        if is_duration:
            duration_str = args[0]
            note = " ".join(args[1:]) if len(args) > 1 else ""
            _do_manual_log(duration_str, note, project_name)
            return

    if month_val:
        report.print_log_entries("month", month_val, project_name)
    elif period:
        report.print_log_entries(period, None, project_name)
    elif project_name and not args:
        report.print_log_entries("all", None, project_name)
    else:
        report.print_log_entries("today", None, project_name)


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
@click.option("--week", "period", flag_value="week", help="生成周报表")
@click.option("--month", "period", flag_value="month", help="生成月报表 (默认当月)")
@click.option("--month-value", "month_val", help="指定月份 YYYY-MM")
@click.option("--all", "period", flag_value="all", help="生成全部报表")
@click.option("--export", "export_format", type=click.Choice(["csv"]), help="导出格式")
@click.option("--output", "-o", "output_path", help="导出文件路径")
@click.option("--project", "project_name", help="仅导出指定项目")
def cmd_report(period, month_val, export_format, output_path, project_name):
    """生成报表（周/月/全部），按项目汇总，支持导出 CSV"""

    if not period:
        period = "week"

    if export_format == "csv":
        result = report.export_csv(period, month_val, project_name, output_path)
        if result:
            console.print(f"[green]✓ CSV 导出成功:[/green] [cyan]{result}[/cyan]")
        return

    report.print_report(period, month_val)


if __name__ == "__main__":
    cli()
