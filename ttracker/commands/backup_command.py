import sys

import click
from rich.console import Console
from pathlib import Path

from ..backup import export_backup, import_backup

console = Console()


class BackupCommand:

    def handle_backup(self, output_path):
        result = export_backup(output_path)
        if result:
            console.print(f"[green]✓ 备份成功:[/green] [cyan]{result}[/cyan]")
        else:
            console.print(f"[red]✗ 备份失败[/red]")
            sys.exit(1)

    def handle_restore(self, backup_file, yes):
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

        result = import_backup(backup_file)
        if result:
            console.print(f"[green]✓ 恢复成功: 已导入 {result['projects']} 个项目, "
                          f"{result['time_entries']} 条记录[/green]")
        else:
            console.print(f"[red]✗ 恢复失败[/red]")
            sys.exit(1)
