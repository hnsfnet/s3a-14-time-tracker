import sys
import re
from typing import List

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich import box

from .. import db
from ..timer import format_duration_short, format_money

console = Console()


class ProjectCommand:

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

    @staticmethod
    def _parse_tag_list(tag_str: str) -> List[str]:
        tags = re.split(r'[,，\s]+', tag_str.strip())
        return [t.strip() for t in tags if t.strip()]

    @staticmethod
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
                hours_pct = ProjectCommand.budget_percent(total_hours, p.budget_hours)
                hours_bar = ProjectCommand.budget_progress_bar(total_hours, p.budget_hours, 10)
                hours_cell = Text()
                hours_cell.append(hours_bar)
                hours_cell.append(f" {hours_pct}", style="dim")
            else:
                hours_cell = Text("-", style="dim")

            if p.budget_cost:
                cost_pct = ProjectCommand.budget_percent(total_cost, p.budget_cost)
                cost_bar = ProjectCommand.budget_progress_bar(total_cost, p.budget_cost, 10)
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

    def handle_add(self, name, client, rate, desc):
        existing = db.get_project_by_name(name)
        if existing:
            console.print(f"[red]错误: 项目 '{name}' 已存在[/red]")
            sys.exit(1)

        pid = db.add_project(name, desc, client, rate)
        console.print(f"[green]✓ 项目添加成功[/green]")
        ProjectCommand._print_project_table([db.get_project_by_id(pid)])

    def handle_list(self):
        projects = db.get_all_projects()
        if not projects:
            console.print("[yellow]暂无项目，使用 'tt project add' 添加[/yellow]")
            return
        ProjectCommand._print_project_table(projects)

    def handle_delete(self, project_id):
        import click
        project = db.get_project_by_id(project_id)
        if not project:
            console.print(f"[red]错误: 项目 ID {project_id} 不存在[/red]")
            sys.exit(1)

        if click.confirm(f"确定删除项目 '{project.name}'？相关工时记录、标签、预算都会被移除。"):
            if db.delete_project(project_id):
                console.print(f"[green]✓ 项目 '{project.name}' 已删除[/green]")
            else:
                console.print(f"[red]删除失败[/red]")

    def handle_update(self, project_id, name, client, rate, desc):
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
            ProjectCommand._print_project_table([db.get_project_by_id(project_id)])
        else:
            console.print(f"[red]更新失败[/red]")

    def handle_tag(self, project_id, add_tags, remove_tags):
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

        add_list = ProjectCommand._parse_tag_list(add_tags) if add_tags else []
        remove_list = ProjectCommand._parse_tag_list(remove_tags) if remove_tags else []

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
        ProjectCommand._print_project_table([db.get_project_by_id(project_id)])

    def handle_budget(self, project_id, hours, cost):
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
                f"{project.budget_hours:.0f}h ({ProjectCommand.budget_percent(total_hours, project.budget_hours)})"
                if project.budget_hours else "未设置",
            )
            content.add_row(
                "费用预算:",
                f"¥{total_cost:.2f} / ¥{project.budget_cost:.2f} ({ProjectCommand.budget_percent(total_cost, project.budget_cost)})"
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
        ProjectCommand._print_project_table([db.get_project_by_id(project_id)])
