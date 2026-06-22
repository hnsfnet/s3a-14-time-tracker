import sys
import re
from typing import Optional

from rich.console import Console

from .. import db
from .. import timer
from .. import report
from ..timer import format_duration, format_money

console = Console()


class LogCommand:

    def _do_manual_log(self, duration_str: str, note: str, target_project: Optional[str] = None):
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

    def handle_log(self, args, period, month_val, project_name, tag_name):
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

            if project_name and len(args) >= 1:
                duration_str = first_arg
                note = " ".join(args[1:]) if len(args) > 1 else ""
                self._do_manual_log(duration_str, note, project_name)
                return

            if strongly_looks_like_manual_log:
                duration_str = first_arg
                note = " ".join(args[1:]) if len(args) > 1 else ""
                self._do_manual_log(duration_str, note, project_name)
                return
            else:
                try:
                    timer.parse_duration(first_arg)
                    duration_str = first_arg
                    note = " ".join(args[1:]) if len(args) > 1 else ""
                    self._do_manual_log(duration_str, note, project_name)
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
