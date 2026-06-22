"""CLI 集成测试 - 使用 click.testing.CliRunner 测试完整命令行流程"""
import json
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from click.testing import CliRunner

from ttracker import db
from ttracker.cli import cli


@pytest.fixture
def runner():
    """创建 CliRunner 实例"""
    return CliRunner()


@pytest.fixture
def setup_sample_data(isolated_db, project_repo, time_entry_repo, tag_repo):
    """预置测试数据: 2个项目 + 标签 + 工时记录"""
    p1_id = project_repo.add("官网改版", "客户官网全面改版", "某某科技", 300.0)
    p2_id = project_repo.add("小程序开发", "微信小程序从零到一", "星辰工作室", 280.0)

    tag_repo.add_to_project(p1_id, "前端")
    tag_repo.add_to_project(p1_id, "React")
    tag_repo.add_to_project(p2_id, "后端")
    tag_repo.add_to_project(p2_id, "Node.js")

    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    time_entry_repo.add(
        p1_id,
        today + timedelta(hours=9),
        today + timedelta(hours=10),
        3600,
        "首页设计"
    )
    time_entry_repo.add(
        p2_id,
        today + timedelta(hours=14),
        today + timedelta(hours=15, minutes=30),
        5400,
        "API开发"
    )

    return {
        "p1_id": p1_id,
        "p2_id": p2_id,
        "p1_name": "官网改版",
        "p2_name": "小程序开发",
    }


# =====================================================================
# 1. 项目管理命令测试: tt project add/list/delete/update/tag/budget
# =====================================================================

class TestProjectCommands:

    @pytest.mark.cli
    def test_project_add_success(self, runner, isolated_db):
        """测试添加新项目成功"""
        db.init_db()
        result = runner.invoke(cli, ["project", "add", "测试项目",
                                     "--client", "测试客户",
                                     "--rate", "200",
                                     "--desc", "测试描述"])
        assert result.exit_code == 0
        assert "项目添加成功" in result.output
        assert "测试项目" in result.output
        assert "测试客户" in result.output

    @pytest.mark.cli
    def test_project_add_duplicate_name_error(self, runner, setup_sample_data):
        """测试添加重复项目名称报错"""
        db.init_db()
        result = runner.invoke(cli, ["project", "add", "官网改版"])
        assert result.exit_code != 0
        assert "错误:" in result.output
        assert "已存在" in result.output

    @pytest.mark.cli
    def test_project_list_with_projects(self, runner, setup_sample_data):
        """测试列出项目成功"""
        db.init_db()
        result = runner.invoke(cli, ["project", "list"])
        assert result.exit_code == 0
        assert "项目列表" in result.output
        assert "官网改" in result.output
        assert "小程序" in result.output
        assert "某某科技" in result.output
        assert "星辰工" in result.output

    @pytest.mark.cli
    def test_project_list_empty(self, runner, isolated_db):
        """测试无项目时列出项目"""
        db.init_db()
        result = runner.invoke(cli, ["project", "list"])
        assert result.exit_code == 0
        assert "暂无项目" in result.output

    @pytest.mark.cli
    def test_project_delete_success(self, runner, setup_sample_data):
        """测试删除项目成功"""
        db.init_db()
        p1_id = setup_sample_data["p1_id"]
        result = runner.invoke(cli, ["project", "delete", str(p1_id)], input="y\n")
        assert result.exit_code == 0
        assert "已删除" in result.output
        assert "官网改版" in result.output

    @pytest.mark.cli
    def test_project_delete_cancel(self, runner, setup_sample_data):
        """测试取消删除项目"""
        db.init_db()
        p1_id = setup_sample_data["p1_id"]
        result = runner.invoke(cli, ["project", "delete", str(p1_id)], input="n\n")
        assert result.exit_code == 0
        assert "已删除" not in result.output

    @pytest.mark.cli
    def test_project_delete_not_exist_error(self, runner, isolated_db):
        """测试删除不存在的项目报错"""
        db.init_db()
        result = runner.invoke(cli, ["project", "delete", "999"])
        assert result.exit_code != 0
        assert "错误:" in result.output
        assert "不存在" in result.output

    @pytest.mark.cli
    def test_project_update_success(self, runner, setup_sample_data):
        """测试更新项目信息成功"""
        db.init_db()
        p1_id = setup_sample_data["p1_id"]
        result = runner.invoke(cli, ["project", "update", str(p1_id),
                                     "--name", "官网V2",
                                     "--rate", "350"])
        assert result.exit_code == 0
        assert "项目信息已更新" in result.output
        assert "官网V2" in result.output

    @pytest.mark.cli
    def test_project_update_not_exist_error(self, runner, isolated_db):
        """测试更新不存在的项目报错"""
        db.init_db()
        result = runner.invoke(cli, ["project", "update", "999", "--name", "新名称"])
        assert result.exit_code != 0
        assert "错误:" in result.output
        assert "不存在" in result.output

    @pytest.mark.cli
    def test_project_update_no_fields_warning(self, runner, setup_sample_data):
        """测试未指定更新字段时的提示"""
        db.init_db()
        p1_id = setup_sample_data["p1_id"]
        result = runner.invoke(cli, ["project", "update", str(p1_id)])
        assert result.exit_code == 0
        assert "没有指定任何更新字段" in result.output

    @pytest.mark.cli
    def test_project_tag_add_success(self, runner, setup_sample_data):
        """测试添加项目标签成功"""
        db.init_db()
        p1_id = setup_sample_data["p1_id"]
        result = runner.invoke(cli, ["project", "tag", str(p1_id),
                                     "--add", "UI,设计"])
        assert result.exit_code == 0
        assert "已添加标签" in result.output
        assert "UI" in result.output
        assert "设计" in result.output

    @pytest.mark.cli
    def test_project_tag_remove_success(self, runner, setup_sample_data):
        """测试移除项目标签成功"""
        db.init_db()
        p1_id = setup_sample_data["p1_id"]
        result = runner.invoke(cli, ["project", "tag", str(p1_id),
                                     "--remove", "React"])
        assert result.exit_code == 0
        assert "已移除标签" in result.output
        assert "React" in result.output

    @pytest.mark.cli
    def test_project_tag_remove_not_exist_warning(self, runner, setup_sample_data):
        """测试移除不存在的标签警告"""
        db.init_db()
        p1_id = setup_sample_data["p1_id"]
        result = runner.invoke(cli, ["project", "tag", str(p1_id),
                                     "--remove", "不存在的标签"])
        assert result.exit_code == 0
        assert "⚠" in result.output
        assert "不存在" in result.output

    @pytest.mark.cli
    def test_project_tag_not_exist_error(self, runner, isolated_db):
        """测试给不存在的项目打标签报错"""
        db.init_db()
        result = runner.invoke(cli, ["project", "tag", "999", "--add", "测试"])
        assert result.exit_code != 0
        assert "错误:" in result.output
        assert "不存在" in result.output

    @pytest.mark.cli
    def test_project_tag_view(self, runner, setup_sample_data):
        """测试查看项目标签"""
        db.init_db()
        p1_id = setup_sample_data["p1_id"]
        result = runner.invoke(cli, ["project", "tag", str(p1_id)])
        assert result.exit_code == 0
        assert "标签" in result.output
        assert "前端" in result.output
        assert "React" in result.output

    @pytest.mark.cli
    def test_project_budget_set_hours_success(self, runner, setup_sample_data):
        """测试设置工时预算成功"""
        db.init_db()
        p1_id = setup_sample_data["p1_id"]
        result = runner.invoke(cli, ["project", "budget", str(p1_id),
                                     "--hours", "40"])
        assert result.exit_code == 0
        assert "已设置工时预算" in result.output
        assert "40" in result.output

    @pytest.mark.cli
    def test_project_budget_set_cost_success(self, runner, setup_sample_data):
        """测试设置费用预算成功"""
        db.init_db()
        p1_id = setup_sample_data["p1_id"]
        result = runner.invoke(cli, ["project", "budget", str(p1_id),
                                     "--cost", "12000"])
        assert result.exit_code == 0
        assert "已设置费用预算" in result.output
        assert "12000" in result.output

    @pytest.mark.cli
    def test_project_budget_clear(self, runner, setup_sample_data):
        """测试清除预算"""
        db.init_db()
        p1_id = setup_sample_data["p1_id"]
        runner.invoke(cli, ["project", "budget", str(p1_id), "--hours", "40"])
        result = runner.invoke(cli, ["project", "budget", str(p1_id),
                                     "--hours", "0"])
        assert result.exit_code == 0
        assert "已清除工时预算" in result.output

    @pytest.mark.cli
    def test_project_budget_view(self, runner, setup_sample_data):
        """测试查看预算概览"""
        db.init_db()
        p1_id = setup_sample_data["p1_id"]
        runner.invoke(cli, ["project", "budget", str(p1_id),
                            "--hours", "40", "--cost", "12000"])
        result = runner.invoke(cli, ["project", "budget", str(p1_id)])
        assert result.exit_code == 0
        assert "预算概览" in result.output
        assert "工时预算" in result.output
        assert "费用预算" in result.output

    @pytest.mark.cli
    def test_project_budget_not_exist_error(self, runner, isolated_db):
        """测试给不存在的项目设置预算报错"""
        db.init_db()
        result = runner.invoke(cli, ["project", "budget", "999", "--hours", "40"])
        assert result.exit_code != 0
        assert "错误:" in result.output
        assert "不存在" in result.output


# =====================================================================
# 2. 计时命令测试: tt start/stop/status
# =====================================================================

class TestTimerCommands:

    @pytest.mark.cli
    def test_start_stop_status_full_flow(self, runner, setup_sample_data):
        """测试完整计时流程: 启动→状态→停止"""
        db.init_db()
        p1_name = setup_sample_data["p1_name"]

        result = runner.invoke(cli, ["start", p1_name])
        assert result.exit_code == 0
        assert "▶" in result.output
        assert p1_name in result.output

        result = runner.invoke(cli, ["status"])
        assert result.exit_code == 0
        assert "计时进行中" in result.output
        assert p1_name in result.output
        assert "已计时" in result.output

        result = runner.invoke(cli, ["stop", "-n", "完成首页设计"])
        assert result.exit_code == 0
        assert "⏹" in result.output
        assert p1_name in result.output
        assert "完成首页设计" in result.output

        result = runner.invoke(cli, ["status"])
        assert result.exit_code == 0
        assert "⏸" in result.output

    @pytest.mark.cli
    def test_stop_without_start(self, runner, isolated_db):
        """测试未启动就停止"""
        db.init_db()
        result = runner.invoke(cli, ["stop"])
        assert result.exit_code == 0
        assert "ℹ" in result.output

    @pytest.mark.cli
    def test_start_not_exist_project(self, runner, isolated_db):
        """测试启动不存在的项目"""
        db.init_db()
        result = runner.invoke(cli, ["start", "不存在的项目"])
        assert result.exit_code != 0
        assert "✗" in result.output

    @pytest.mark.cli
    def test_start_same_project_twice(self, runner, setup_sample_data):
        """测试连续start同一项目"""
        db.init_db()
        p1_name = setup_sample_data["p1_name"]

        result1 = runner.invoke(cli, ["start", p1_name])
        assert result1.exit_code == 0

        result2 = runner.invoke(cli, ["start", p1_name])
        assert result2.exit_code != 0
        assert "✗" in result2.output
        assert "已经在计时中" in result2.output

    @pytest.mark.cli
    def test_start_different_project_auto_stop(self, runner, setup_sample_data):
        """测试启动不同项目时自动停止上次计时"""
        db.init_db()
        p1_name = setup_sample_data["p1_name"]
        p2_name = setup_sample_data["p2_name"]

        runner.invoke(cli, ["start", p1_name])
        result = runner.invoke(cli, ["start", p2_name])
        assert result.exit_code == 0
        assert "⏹" in result.output
        assert "已自动停止上次计时" in result.output
        assert p2_name in result.output

    @pytest.mark.cli
    def test_status_without_active_timer(self, runner, isolated_db):
        """测试无活动计时时的状态"""
        db.init_db()
        result = runner.invoke(cli, ["status"])
        assert result.exit_code == 0
        assert "⏸" in result.output


# =====================================================================
# 3. 日志命令测试: tt log
# =====================================================================

class TestLogCommands:

    @pytest.mark.cli
    def test_log_view_today(self, runner, setup_sample_data):
        """测试查看今天的日志"""
        db.init_db()
        result = runner.invoke(cli, ["log"])
        assert result.exit_code == 0
        assert "官网改版" in result.output
        assert "小程序开发" in result.output

    @pytest.mark.cli
    def test_log_view_week(self, runner, setup_sample_data):
        """测试查看本周的日志"""
        db.init_db()
        result = runner.invoke(cli, ["log", "--week"])
        assert result.exit_code == 0
        assert "官网改版" in result.output

    @pytest.mark.cli
    def test_log_view_month(self, runner, setup_sample_data):
        """测试查看本月的日志"""
        db.init_db()
        month_str = datetime.now().strftime("%Y-%m")
        result = runner.invoke(cli, ["log", "--month", month_str])
        assert result.exit_code == 0
        assert "官网改版" in result.output

    @pytest.mark.cli
    def test_log_manual_log_2h(self, runner, setup_sample_data):
        """测试手动补录 2h"""
        db.init_db()
        p1_name = setup_sample_data["p1_name"]
        result = runner.invoke(cli, ["log", "2h", "修复登录bug",
                                     "--project", p1_name])
        assert result.exit_code == 0
        assert "✓" in result.output
        assert "2小时" in result.output
        assert "修复登录bug" in result.output

    @pytest.mark.cli
    def test_log_manual_log_2h30m(self, runner, setup_sample_data):
        """测试手动补录 2h30m"""
        db.init_db()
        p1_name = setup_sample_data["p1_name"]
        result = runner.invoke(cli, ["log", "2h30m", "写接口文档",
                                     "--project", p1_name])
        assert result.exit_code == 0
        assert "✓" in result.output
        assert "2小时30分钟" in result.output

    @pytest.mark.cli
    def test_log_manual_log_1_5h(self, runner, setup_sample_data):
        """测试手动补录 1.5h"""
        db.init_db()
        p1_name = setup_sample_data["p1_name"]
        result = runner.invoke(cli, ["log", "1.5h", "代码review",
                                     "--project", p1_name])
        assert result.exit_code == 0
        assert "✓" in result.output
        assert "1小时30分钟" in result.output

    @pytest.mark.cli
    def test_log_manual_log_45m(self, runner, setup_sample_data):
        """测试手动补录 45m"""
        db.init_db()
        p1_name = setup_sample_data["p1_name"]
        result = runner.invoke(cli, ["log", "45m", "小bug修复",
                                     "--project", p1_name])
        assert result.exit_code == 0
        assert "✓" in result.output
        assert "45分钟" in result.output

    @pytest.mark.cli
    def test_log_manual_log_invalid_format_error(self, runner, setup_sample_data):
        """测试无效时长格式给出明确错误"""
        db.init_db()
        p1_name = setup_sample_data["p1_name"]
        result = runner.invoke(cli, ["log", "abc", "测试",
                                     "--project", p1_name])
        assert result.exit_code != 0
        assert "✗" in result.output
        assert "无法解析时长" in result.output

    @pytest.mark.cli
    def test_log_manual_log_no_project_no_active_error(self, runner, isolated_db):
        """测试无活动计时且未指定项目时报错"""
        db.init_db()
        result = runner.invoke(cli, ["log", "2h", "测试"])
        assert result.exit_code != 0
        assert "✗" in result.output
        assert "当前没有正在计时的项目" in result.output

    @pytest.mark.cli
    def test_log_manual_log_with_active_timer(self, runner, setup_sample_data):
        """测试有活动计时时补录不需要指定项目"""
        db.init_db()
        p1_name = setup_sample_data["p1_name"]
        runner.invoke(cli, ["start", p1_name])
        result = runner.invoke(cli, ["log", "1h", "测试补录"])
        assert result.exit_code == 0
        assert "✓" in result.output

    @pytest.mark.cli
    def test_log_filter_by_project(self, runner, setup_sample_data):
        """测试按项目筛选日志"""
        db.init_db()
        result = runner.invoke(cli, ["log", "--project", "官网改版"])
        assert result.exit_code == 0
        assert "官网改版" in result.output
        assert "小程序开发" not in result.output

    @pytest.mark.cli
    def test_log_filter_by_tag(self, runner, setup_sample_data):
        """测试按标签筛选日志"""
        db.init_db()
        result = runner.invoke(cli, ["log", "--tag", "前端"])
        assert result.exit_code == 0
        assert "官网改版" in result.output
        assert "小程序开发" not in result.output

    @pytest.mark.cli
    def test_log_filter_by_not_exist_tag(self, runner, setup_sample_data):
        """测试按不存在的标签筛选"""
        db.init_db()
        result = runner.invoke(cli, ["log", "--tag", "不存在的标签"])
        assert result.exit_code == 0


# =====================================================================
# 4. 报表命令测试: tt report
# =====================================================================

class TestReportCommands:

    @pytest.mark.cli
    def test_report_week(self, runner, setup_sample_data):
        """测试生成周报表"""
        db.init_db()
        result = runner.invoke(cli, ["report", "--week"])
        assert result.exit_code == 0

    @pytest.mark.cli
    def test_report_month(self, runner, setup_sample_data):
        """测试生成月报表"""
        db.init_db()
        result = runner.invoke(cli, ["report", "--month"])
        assert result.exit_code == 0

    @pytest.mark.cli
    def test_report_daily(self, runner, setup_sample_data):
        """测试生成日报"""
        db.init_db()
        result = runner.invoke(cli, ["report", "--daily"])
        assert result.exit_code == 0

    @pytest.mark.cli
    def test_report_weekly_grouped(self, runner, setup_sample_data):
        """测试生成周报(按天分组)"""
        db.init_db()
        result = runner.invoke(cli, ["report", "--weekly"])
        assert result.exit_code == 0

    @pytest.mark.cli
    def test_report_filter_by_tag(self, runner, setup_sample_data):
        """测试按标签筛选报表"""
        db.init_db()
        result = runner.invoke(cli, ["report", "--week", "--tag", "前端"])
        assert result.exit_code == 0

    @pytest.mark.cli
    def test_report_export_csv(self, runner, setup_sample_data):
        """测试导出 CSV"""
        db.init_db()
        with runner.isolated_filesystem():
            result = runner.invoke(cli, ["report", "--week",
                                         "--export", "csv",
                                         "--output", "report.csv"])
            assert result.exit_code == 0
            assert "CSV 导出成功" in result.output
            assert Path("report.csv").exists()
            content = Path("report.csv").read_text(encoding="utf-8")
            assert "官网改版" in content

    @pytest.mark.cli
    def test_report_export_csv_default_output(self, runner, setup_sample_data):
        """测试导出 CSV 不指定输出路径"""
        db.init_db()
        with runner.isolated_filesystem():
            result = runner.invoke(cli, ["report", "--week",
                                         "--export", "csv"])
            assert result.exit_code == 0
            assert "CSV 导出成功" in result.output

    @pytest.mark.cli
    def test_report_export_markdown(self, runner, setup_sample_data):
        """测试导出 Markdown"""
        db.init_db()
        with runner.isolated_filesystem():
            result = runner.invoke(cli, ["report", "--week",
                                         "--export", "markdown",
                                         "--output", "report.md"])
            assert result.exit_code == 0
            assert "Markdown 导出成功" in result.output
            assert Path("report.md").exists()
            content = Path("report.md").read_text(encoding="utf-8")
            assert "#" in content

    @pytest.mark.cli
    def test_report_export_md_alias(self, runner, setup_sample_data):
        """测试使用 md 别名导出 Markdown"""
        db.init_db()
        with runner.isolated_filesystem():
            result = runner.invoke(cli, ["report", "--week",
                                         "--export", "md",
                                         "--output", "report.md"])
            assert result.exit_code == 0
            assert "Markdown 导出成功" in result.output

    @pytest.mark.cli
    def test_report_filter_by_project(self, runner, setup_sample_data):
        """测试按项目筛选导出"""
        db.init_db()
        with runner.isolated_filesystem():
            result = runner.invoke(cli, ["report", "--all",
                                         "--export", "csv",
                                         "--project", "官网改版",
                                         "--output", "p1.csv"])
            assert result.exit_code == 0
            assert Path("p1.csv").exists()


# =====================================================================
# 5. 备份恢复命令测试: tt backup/restore
# =====================================================================

class TestBackupRestoreCommands:

    @pytest.mark.cli
    def test_backup_success(self, runner, setup_sample_data):
        """测试备份成功"""
        db.init_db()
        with runner.isolated_filesystem():
            result = runner.invoke(cli, ["backup", "-o", "backup.json"])
            assert result.exit_code == 0
            assert "备份成功" in result.output
            assert Path("backup.json").exists()

            with open("backup.json", "r", encoding="utf-8") as f:
                data = json.load(f)
            assert len(data["projects"]) == 2
            assert len(data["time_entries"]) == 2

    @pytest.mark.cli
    def test_backup_default_filename(self, runner, setup_sample_data):
        """测试备份使用默认文件名"""
        db.init_db()
        with runner.isolated_filesystem():
            result = runner.invoke(cli, ["backup"])
            assert result.exit_code == 0
            assert "备份成功" in result.output

            files = list(Path.cwd().glob("ttracker_backup_*.json"))
            assert len(files) == 1

    @pytest.mark.cli
    def test_restore_success_roundtrip(self, runner, setup_sample_data):
        """测试备份后再恢复验证数据一致"""
        db.init_db()
        p1_name = setup_sample_data["p1_name"]
        p2_name = setup_sample_data["p2_name"]

        with runner.isolated_filesystem():
            runner.invoke(cli, ["start", p1_name])
            runner.invoke(cli, ["stop", "-n", "测试数据"])

            backup_result = runner.invoke(cli, ["backup", "-o", "backup.json"])
            assert backup_result.exit_code == 0

            projects = db.get_all_projects()
            for p in projects:
                runner.invoke(cli, ["project", "delete", str(p.id)], input="y\n")

            list_result = runner.invoke(cli, ["project", "list"])
            assert "暂无项目" in list_result.output

            restore_result = runner.invoke(
                cli, ["restore", "backup.json", "--yes"]
            )
            assert restore_result.exit_code == 0
            assert "恢复成功" in restore_result.output

            list_result = runner.invoke(cli, ["project", "list"])
            assert list_result.exit_code == 0
            assert "官网改" in list_result.output
            assert "小程序" in list_result.output

            restored_p1 = db.get_project_by_name(p1_name)
            restored_p2 = db.get_project_by_name(p2_name)
            assert restored_p1 is not None
            assert restored_p2 is not None

            log_result = runner.invoke(cli, ["log"])
            assert log_result.exit_code == 0

    @pytest.mark.cli
    def test_restore_file_not_exist_error(self, runner, isolated_db):
        """测试恢复不存在的文件报错"""
        db.init_db()
        with runner.isolated_filesystem():
            result = runner.invoke(cli, ["restore", "not_exist.json", "--yes"])
            assert result.exit_code != 0
            assert "✗" in result.output
            assert "不存在" in result.output

    @pytest.mark.cli
    def test_restore_corrupted_json_error(self, runner, isolated_db):
        """测试恢复损坏的 JSON 文件报错"""
        db.init_db()
        with runner.isolated_filesystem():
            Path("corrupted.json").write_text("{invalid json", encoding="utf-8")
            result = runner.invoke(cli, ["restore", "corrupted.json", "--yes"])
            assert result.exit_code != 0
            assert "✗" in result.output
            assert "恢复失败" in result.output

    @pytest.mark.cli
    def test_restore_confirmation_yes(self, runner, setup_sample_data):
        """测试恢复确认输入 yes"""
        db.init_db()
        with runner.isolated_filesystem():
            runner.invoke(cli, ["backup", "-o", "backup.json"])

            result = runner.invoke(
                cli, ["restore", "backup.json"], input="y\n"
            )
            assert result.exit_code == 0
            assert "恢复成功" in result.output

    @pytest.mark.cli
    def test_restore_confirmation_cancel(self, runner, setup_sample_data):
        """测试恢复确认输入 no 取消"""
        db.init_db()
        with runner.isolated_filesystem():
            runner.invoke(cli, ["backup", "-o", "backup.json"])

            result = runner.invoke(
                cli, ["restore", "backup.json"], input="n\n"
            )
            assert result.exit_code == 0
            assert "已取消恢复" in result.output
            assert "恢复成功" not in result.output


# =====================================================================
# 6. 异常场景测试
# =====================================================================

class TestExceptionScenarios:

    @pytest.mark.cli
    def test_log_chinese_duration_error(self, runner, setup_sample_data):
        """测试中文单位'2小时'补录明确报错"""
        db.init_db()
        p1_name = setup_sample_data["p1_name"]
        result = runner.invoke(cli, ["log", "2小时", "测试中文时长",
                                     "--project", p1_name])
        assert result.exit_code != 0
        assert "✗" in result.output
        assert "无法解析时长" in result.output

    @pytest.mark.cli
    def test_delete_not_exist_project_error(self, runner, isolated_db):
        """测试删除不存在项目报错"""
        db.init_db()
        result = runner.invoke(cli, ["project", "delete", "999"])
        assert result.exit_code != 0
        assert "错误:" in result.output
        assert "不存在" in result.output

    @pytest.mark.cli
    def test_budget_not_exist_project_error(self, runner, isolated_db):
        """测试设置预算给不存在项目报错"""
        db.init_db()
        result = runner.invoke(cli, ["project", "budget", "999", "--hours", "40"])
        assert result.exit_code != 0
        assert "错误:" in result.output
        assert "不存在" in result.output

    @pytest.mark.cli
    def test_update_not_exist_project_error(self, runner, isolated_db):
        """测试更新不存在项目报错"""
        db.init_db()
        result = runner.invoke(cli, ["project", "update", "999", "--name", "新名称"])
        assert result.exit_code != 0
        assert "错误:" in result.output
        assert "不存在" in result.output

    @pytest.mark.cli
    def test_tag_not_exist_project_error(self, runner, isolated_db):
        """测试给不存在项目打标签报错"""
        db.init_db()
        result = runner.invoke(cli, ["project", "tag", "999", "--add", "测试"])
        assert result.exit_code != 0
        assert "错误:" in result.output
        assert "不存在" in result.output

    @pytest.mark.cli
    def test_start_not_exist_project_error(self, runner, isolated_db):
        """测试启动不存在项目报错"""
        db.init_db()
        result = runner.invoke(cli, ["start", "不存在的项目"])
        assert result.exit_code != 0
        assert "✗" in result.output

    @pytest.mark.cli
    def test_log_manual_not_exist_project_error(self, runner, isolated_db):
        """测试补录时指定不存在的项目"""
        db.init_db()
        result = runner.invoke(cli, ["log", "2h", "测试",
                                     "--project", "不存在的项目"])
        assert result.exit_code != 0
        assert "✗" in result.output
        assert "不存在" in result.output

    @pytest.mark.cli
    def test_log_invalid_duration_format_explicit_error(self, runner, setup_sample_data):
        """测试无效格式给出明确错误而不是静默切查看模式"""
        db.init_db()
        p1_name = setup_sample_data["p1_name"]
        result = runner.invoke(cli, ["log", "invalid", "测试",
                                     "--project", p1_name])
        assert result.exit_code != 0
        assert "✗" in result.output
        assert "无法解析时长" in result.output
        assert "支持的格式示例" in result.output

    @pytest.mark.cli
    def test_backup_restore_with_tags_and_budget(self, runner, setup_sample_data):
        """测试备份恢复时标签和预算也被正确恢复"""
        db.init_db()
        p1_id = setup_sample_data["p1_id"]
        p1_name = setup_sample_data["p1_name"]

        runner.invoke(cli, ["project", "budget", str(p1_id),
                            "--hours", "100", "--cost", "30000"])

        with runner.isolated_filesystem():
            runner.invoke(cli, ["backup", "-o", "backup.json"])

            projects = db.get_all_projects()
            for p in projects:
                runner.invoke(cli, ["project", "delete", str(p.id)], input="y\n")

            runner.invoke(cli, ["restore", "backup.json", "--yes"])

            result = runner.invoke(cli, ["project", "list"])
            assert "前端" in result.output
            assert "React" in result.output

            restored_project = db.get_project_by_name(p1_name)
            assert restored_project is not None
            budget_result = runner.invoke(
                cli, ["project", "budget", str(restored_project.id)]
            )
            assert "预算概览" in budget_result.output
