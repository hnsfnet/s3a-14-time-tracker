import click

from . import db
from .commands import (
    ProjectCommand,
    TimerCommand,
    LogCommand,
    ReportCommand,
    BackupCommand,
)


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
    ProjectCommand().handle_add(name, client, rate, desc)


@project.command("list")
def project_list():
    """列出所有项目（含标签和预算进度）"""
    ProjectCommand().handle_list()


@project.command("delete")
@click.argument("project_id", type=int)
def project_delete(project_id):
    """删除指定 ID 的项目"""
    ProjectCommand().handle_delete(project_id)


@project.command("update")
@click.argument("project_id", type=int)
@click.option("--name", "-n", help="新名称")
@click.option("--client", "-c", help="新客户名称")
@click.option("--rate", "-r", type=float, help="新小时费率")
@click.option("--desc", "-d", help="新描述")
def project_update(project_id, name, client, rate, desc):
    """更新项目信息"""
    ProjectCommand().handle_update(project_id, name, client, rate, desc)


@project.command("tag")
@click.argument("project_id", type=int)
@click.option("--add", "-a", "add_tags", help="要添加的标签，多个用逗号分隔，如: 前端,React,设计")
@click.option("--remove", "-r", "remove_tags", help="要移除的标签，多个用逗号分隔")
def project_tag(project_id, add_tags, remove_tags):
    """管理项目标签。使用: tt project tag 3 --add 前端,React ; tt project tag 3 --remove React"""
    ProjectCommand().handle_tag(project_id, add_tags, remove_tags)


@project.command("budget")
@click.argument("project_id", type=int)
@click.option("--hours", type=float, help="总工时上限（小时），设 0 或留空清除")
@click.option("--cost", type=float, help="总费用上限（元），设 0 或留空清除")
def project_budget(project_id, hours, cost):
    """设置或清除项目预算。使用: tt project budget 3 --hours 40 --cost 12000"""
    ProjectCommand().handle_budget(project_id, hours, cost)


# ─── 计时命令 ────────────────────────────────────────────────────

@cli.command("start")
@click.argument("project_name")
def cmd_start(project_name):
    """开始为指定项目计时"""
    TimerCommand().handle_start(project_name)


@cli.command("stop")
@click.option("--note", "-n", default="", help="本次工作的备注")
def cmd_stop(note):
    """停止当前计时并记录"""
    TimerCommand().handle_stop(note)


@cli.command("status")
def cmd_status():
    """查看当前计时状态"""
    TimerCommand().handle_status()


# ─── 日志命令 ────────────────────────────────────────────────────

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
    LogCommand().handle_log(args, period, month_val, project_name, tag_name)


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
    ReportCommand().handle_report(period, month_val, tag_name, export_format, output_path, project_name)


# ─── 备份与恢复 ───────────────────────────────────────────────────

@cli.command("backup")
@click.option("--output", "-o", "output_path", help="备份文件路径")
def cmd_backup(output_path):
    """导出所有数据为 JSON 备份文件"""
    BackupCommand().handle_backup(output_path)


@cli.command("restore")
@click.argument("backup_file")
@click.option("--yes", "-y", is_flag=True, help="跳过确认提示")
def cmd_restore(backup_file, yes):
    """从 JSON 备份文件恢复数据（覆盖当前数据库）"""
    BackupCommand().handle_restore(backup_file, yes)


if __name__ == "__main__":
    cli()
