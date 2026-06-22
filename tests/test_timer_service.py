"""TimerService 业务逻辑层测试"""
from datetime import datetime, timedelta

import pytest

from ttracker.models import TimeEntry
from ttracker.timer import parse_duration


# ── 1. 计时流程测试 ─────────────────────────────────────────────────


@pytest.mark.service
class TestTimerFlow:
    """计时流程测试"""

    def test_start_timer_success(self, timer_service, sample_projects):
        """start_timer 成功启动项目计时"""
        p1 = sample_projects["p1"]
        success, msg, project, stopped_info = timer_service.start_timer(p1.name)

        assert success is True
        assert "开始计时项目" in msg
        assert project is not None
        assert project.id == p1.id
        assert stopped_info is None

    def test_start_timer_project_not_exist(self, timer_service):
        """start_timer 项目不存在时返回失败"""
        success, msg, project, stopped_info = timer_service.start_timer("不存在的项目")

        assert success is False
        assert "不存在" in msg
        assert project is None
        assert stopped_info is None

    def test_start_timer_auto_stop_previous(self, timer_service, sample_projects):
        """start_timer 已有其他项目计时时自动停止上一个并返回 stopped_info"""
        p1 = sample_projects["p1"]
        p2 = sample_projects["p2"]

        success1, _, _, _ = timer_service.start_timer(p1.name)
        assert success1 is True

        success2, msg, project, stopped_info = timer_service.start_timer(p2.name)

        assert success2 is True
        assert "开始计时项目" in msg
        assert project is not None
        assert project.id == p2.id
        assert stopped_info is not None
        assert isinstance(stopped_info, tuple)
        assert len(stopped_info) == 2
        entry_id, duration = stopped_info
        assert entry_id > 0
        assert duration >= 0

    def test_start_timer_same_project_twice(self, timer_service, sample_projects):
        """start_timer 同一项目多次调用返回友好提示"""
        p1 = sample_projects["p1"]

        success1, _, _, _ = timer_service.start_timer(p1.name)
        assert success1 is True

        success2, msg, project, stopped_info = timer_service.start_timer(p1.name)

        assert success2 is False
        assert "已经在计时中" in msg
        assert project is not None
        assert project.id == p1.id
        assert stopped_info is None

    def test_stop_timer_success(self, timer_service, sample_projects):
        """stop_timer 成功停止计时"""
        p1 = sample_projects["p1"]
        timer_service.start_timer(p1.name)

        success, msg, project, duration = timer_service.stop_timer("测试备注")

        assert success is True
        assert "计时已停止" in msg
        assert project is not None
        assert project.id == p1.id
        assert duration is not None
        assert duration >= 0

    def test_stop_timer_not_running(self, timer_service):
        """stop_timer 未计时时返回失败"""
        success, msg, project, duration = timer_service.stop_timer()

        assert success is False
        assert "没有正在进行的计时" in msg
        assert project is None
        assert duration is None

    def test_get_timer_status_running(self, timer_service, sample_projects):
        """get_timer_status 计时中时返回正确状态"""
        p1 = sample_projects["p1"]
        timer_service.start_timer(p1.name)

        success, msg, project, elapsed, start_time = timer_service.get_timer_status()

        assert success is True
        assert "计时中" in msg
        assert project is not None
        assert project.id == p1.id
        assert elapsed is not None
        assert elapsed >= 0
        assert start_time is not None
        assert isinstance(start_time, datetime)

    def test_get_timer_status_not_running(self, timer_service):
        """get_timer_status 未计时时返回正确状态"""
        success, msg, project, elapsed, start_time = timer_service.get_timer_status()

        assert success is False
        assert "没有正在进行的计时" in msg
        assert project is None
        assert elapsed is None
        assert start_time is None


# ── 2. 跨天/跨月计算测试 ────────────────────────────────────────────


@pytest.mark.service
class TestCrossDayCalculation:
    """跨天/跨月计算测试"""

    def test_cross_day_duration_via_stop_active(self, timer_service, sample_projects, time_entry_repo):
        """模拟 23:30 开始 → 次日 01:00 停止 = 1.5 小时 = 5400 秒"""
        p1 = sample_projects["p1"]

        start_time = datetime(2024, 1, 15, 23, 30, 0)
        end_time = datetime(2024, 1, 16, 1, 0, 0)

        entry_id = time_entry_repo.start_active(p1.id, start_time)

        expected_duration = int((end_time - start_time).total_seconds())
        assert expected_duration == 5400

        result = time_entry_repo.stop_active(entry_id, end_time, expected_duration)
        assert result is True

        total_seconds, _ = timer_service._project_repo.get_total_usage(p1.id)
        assert total_seconds == 5400

    def test_cross_month_duration_via_stop_active(self, timer_service, sample_projects, time_entry_repo):
        """模拟 1 月 31 日 23:00 → 2 月 1 日 01:00 = 2 小时 = 7200 秒"""
        p1 = sample_projects["p1"]

        start_time = datetime(2024, 1, 31, 23, 0, 0)
        end_time = datetime(2024, 2, 1, 1, 0, 0)

        entry_id = time_entry_repo.start_active(p1.id, start_time)

        expected_duration = int((end_time - start_time).total_seconds())
        assert expected_duration == 7200

        result = time_entry_repo.stop_active(entry_id, end_time, expected_duration)
        assert result is True

        total_seconds, _ = timer_service._project_repo.get_total_usage(p1.id)
        assert total_seconds == 7200

    def test_time_entry_from_row_cross_day_validation(self):
        """测试 TimeEntry.from_row 自校验逻辑处理跨天 duration"""
        start = datetime(2024, 1, 15, 23, 30, 0)
        end = datetime(2024, 1, 16, 1, 0, 0)

        row = (
            1,
            100,
            start.isoformat(),
            end.isoformat(),
            0,
            "跨天测试",
            "测试项目",
        )

        entry = TimeEntry.from_row(row)
        assert entry.duration == 5400

    def test_time_entry_from_row_cross_month_validation(self):
        """测试 TimeEntry.from_row 自校验逻辑处理跨月 duration"""
        start = datetime(2024, 1, 31, 23, 0, 0)
        end = datetime(2024, 2, 1, 1, 0, 0)

        row = (
            1,
            100,
            start.isoformat(),
            end.isoformat(),
            0,
            "跨月测试",
            "测试项目",
        )

        entry = TimeEntry.from_row(row)
        assert entry.duration == 7200

    def test_time_entry_from_row_wrong_duration_corrected(self):
        """测试 TimeEntry.from_row 自动修正错误的 duration"""
        start = datetime(2024, 1, 15, 10, 0, 0)
        end = datetime(2024, 1, 15, 11, 0, 0)

        row = (
            1,
            100,
            start.isoformat(),
            end.isoformat(),
            99999,
            "错误 duration",
            "测试项目",
        )

        entry = TimeEntry.from_row(row)
        assert entry.duration == 3600

    def test_time_entry_from_row_negative_duration_corrected(self):
        """测试 TimeEntry.from_row 自动修正负的 duration"""
        start = datetime(2024, 1, 15, 10, 0, 0)
        end = datetime(2024, 1, 15, 11, 0, 0)

        row = (
            1,
            100,
            start.isoformat(),
            end.isoformat(),
            -100,
            "负 duration",
            "测试项目",
        )

        entry = TimeEntry.from_row(row)
        assert entry.duration == 3600


# ── 3. parse_duration 测试 ─────────────────────────────────────────


@pytest.mark.service
class TestParseDuration:
    """parse_duration 工具函数测试"""

    def test_parse_hours_only(self):
        """测试 '2h' = 7200 秒"""
        assert parse_duration("2h") == 7200

    def test_parse_minutes_only(self):
        """测试 '45m' = 2700 秒"""
        assert parse_duration("45m") == 2700

    def test_parse_hours_and_minutes(self):
        """测试 '1h30m' = 5400 秒"""
        assert parse_duration("1h30m") == 5400

    def test_parse_decimal_hours(self):
        """测试 '1.5h' = 5400 秒"""
        assert parse_duration("1.5h") == 5400

    def test_parse_minutes_only_large(self):
        """测试 '90m' = 5400 秒"""
        assert parse_duration("90m") == 5400

    def test_parse_hours_and_minutes_large(self):
        """测试 '2h30m' = 9000 秒"""
        assert parse_duration("2h30m") == 9000

    def test_parse_seconds_only(self):
        """测试 '30s' = 30 秒"""
        assert parse_duration("30s") == 30

    def test_parse_with_spaces(self):
        """测试带空格的格式"""
        assert parse_duration(" 1h 30m ") == 5400

    def test_parse_uppercase(self):
        """测试大写格式"""
        assert parse_duration("1H30M") == 5400

    def test_parse_invalid_abc(self):
        """测试 'abc' 抛 ValueError 且错误信息含示例"""
        with pytest.raises(ValueError) as excinfo:
            parse_duration("abc")
        assert "无法解析时长" in str(excinfo.value)
        assert "2h" in str(excinfo.value)
        assert "1h30m" in str(excinfo.value)

    def test_parse_invalid_empty(self):
        """测试 '' 抛 ValueError"""
        with pytest.raises(ValueError) as excinfo:
            parse_duration("")
        assert "不能为空" in str(excinfo.value)

    def test_parse_invalid_numeric_only(self):
        """测试 '2' 抛 ValueError 且错误信息含示例"""
        with pytest.raises(ValueError) as excinfo:
            parse_duration("2")
        assert "无法解析时长" in str(excinfo.value)
        assert "2h" in str(excinfo.value)

    def test_parse_invalid_chinese_units(self):
        """测试 '2小时' 抛 ValueError 且错误信息含示例"""
        with pytest.raises(ValueError) as excinfo:
            parse_duration("2小时")
        assert "无法解析时长" in str(excinfo.value)
        assert "2h" in str(excinfo.value)

    def test_parse_none_raises_error(self):
        """测试 None 抛 ValueError"""
        with pytest.raises(ValueError):
            parse_duration(None)

    def test_parse_zero_duration_raises(self):
        """测试 0 时长抛 ValueError"""
        with pytest.raises(ValueError) as excinfo:
            parse_duration("0h")
        assert "大于 0" in str(excinfo.value)




# ── 4. 预算使用率计算测试 ─────────────────────────────────────────


@pytest.mark.service
class TestBudgetUsage:
    """预算使用率计算测试"""

    def test_budget_80_percent_yellow(self, sample_projects, project_repo, budget_repo, time_entry_repo):
        """设置预算 40h，加一条 32h 记录 → 80% 使用率"""
        p1 = sample_projects["p1"]

        budget_repo.set_hours(p1.id, 40.0)

        start = datetime(2024, 1, 15, 9, 0, 0)
        duration_32h = 32 * 3600
        end = start + timedelta(seconds=duration_32h)
        time_entry_repo.add(p1.id, start, end, duration_32h, "32小时记录")

        total_seconds, total_cost = project_repo.get_total_usage(p1.id)
        assert total_seconds == duration_32h

        p1_updated = project_repo.get_by_id(p1.id)
        assert p1_updated.budget_hours == 40.0

        usage_percent = (total_seconds / 3600.0) / 40.0 * 100
        assert abs(usage_percent - 80.0) < 0.01

    def test_budget_100_percent(self, sample_projects, project_repo, budget_repo, time_entry_repo):
        """设置预算 40h，加一条 40h 记录 → 100% 使用率"""
        p1 = sample_projects["p1"]

        budget_repo.set_hours(p1.id, 40.0)

        start = datetime(2024, 1, 15, 9, 0, 0)
        duration_40h = 40 * 3600
        end = start + timedelta(seconds=duration_40h)
        time_entry_repo.add(p1.id, start, end, duration_40h, "40小时记录")

        total_seconds, total_cost = project_repo.get_total_usage(p1.id)
        assert total_seconds == duration_40h

        usage_percent = (total_seconds / 3600.0) / 40.0 * 100
        assert abs(usage_percent - 100.0) < 0.01

    def test_budget_105_percent_red(self, sample_projects, project_repo, budget_repo, time_entry_repo):
        """设置预算 40h，加一条 42h 记录 → 105% 使用率"""
        p1 = sample_projects["p1"]

        budget_repo.set_hours(p1.id, 40.0)

        start = datetime(2024, 1, 15, 9, 0, 0)
        duration_42h = 42 * 3600
        end = start + timedelta(seconds=duration_42h)
        time_entry_repo.add(p1.id, start, end, duration_42h, "42小时记录")

        total_seconds, total_cost = project_repo.get_total_usage(p1.id)
        assert total_seconds == duration_42h

        usage_percent = (total_seconds / 3600.0) / 40.0 * 100
        assert abs(usage_percent - 105.0) < 0.01

    def test_budget_cost_calculation(self, sample_projects, project_repo, budget_repo, time_entry_repo):
        """测试预算成本计算，p1 rate=300元/小时，32小时 = 9600元"""
        p1 = sample_projects["p1"]

        budget_repo.set_cost(p1.id, 15000.0)

        start = datetime(2024, 1, 15, 9, 0, 0)
        duration_32h = 32 * 3600
        end = start + timedelta(seconds=duration_32h)
        time_entry_repo.add(p1.id, start, end, duration_32h, "成本测试")

        total_seconds, total_cost = project_repo.get_total_usage(p1.id)
        assert total_seconds == duration_32h
        assert abs(total_cost - 9600.0) < 0.01

        p1_updated = project_repo.get_by_id(p1.id)
        assert p1_updated.budget_cost == 15000.0

    def test_budget_no_budget_set(self, sample_projects, project_repo, time_entry_repo):
        """未设置预算时返回 None"""
        p1 = sample_projects["p1"]

        start = datetime(2024, 1, 15, 9, 0, 0)
        duration_8h = 8 * 3600
        end = start + timedelta(seconds=duration_8h)
        time_entry_repo.add(p1.id, start, end, duration_8h, "无预算测试")

        total_seconds, total_cost = project_repo.get_total_usage(p1.id)
        assert total_seconds == duration_8h

        p1_updated = project_repo.get_by_id(p1.id)
        assert p1_updated.budget_hours is None
        assert p1_updated.budget_cost is None


# ── 5. manual_log 测试 ─────────────────────────────────────────────


@pytest.mark.service
class TestManualLog:
    """manual_log 手动补录测试"""

    def test_manual_log_success(self, timer_service, sample_projects):
        """manual_log 正确时长补录成功"""
        p1 = sample_projects["p1"]

        success, msg, project, duration = timer_service.manual_log(
            p1.name, "2h", "手动补录测试"
        )

        assert success is True
        assert "已补录时长" in msg
        assert project is not None
        assert project.id == p1.id
        assert duration == 7200

    def test_manual_log_project_not_exist(self, timer_service):
        """manual_log 项目不存在时返回失败"""
        success, msg, project, duration = timer_service.manual_log(
            "不存在的项目", "2h"
        )

        assert success is False
        assert "不存在" in msg
        assert project is None
        assert duration is None

    def test_manual_log_invalid_format(self, timer_service, sample_projects):
        """manual_log 格式错误时返回失败"""
        p1 = sample_projects["p1"]

        success, msg, project, duration = timer_service.manual_log(
            p1.name, "abc"
        )

        assert success is False
        assert "无法解析时长" in msg
        assert project is None
        assert duration is None

    def test_manual_log_with_start_time(self, timer_service, sample_projects, time_entry_repo):
        """手动指定 start_time 补录（注意：start_time 在代码中实际用作结束时间）"""
        p1 = sample_projects["p1"]

        end_time = datetime(2024, 1, 15, 14, 0, 0)
        expected_start = end_time - timedelta(hours=3)

        success, msg, project, duration = timer_service.manual_log(
            p1.name, "3h", "指定开始时间补录", start_time=end_time
        )

        assert success is True
        assert duration == 10800

        entries = time_entry_repo.list_entries(project_id=p1.id)
        assert len(entries) == 1
        assert entries[0].start_time == expected_start
        assert entries[0].end_time == end_time

    def test_manual_log_various_formats(self, timer_service, sample_projects):
        """测试各种时长格式的 manual_log"""
        p1 = sample_projects["p1"]

        test_cases = [
            ("1h", 3600),
            ("30m", 1800),
            ("1h30m", 5400),
            ("1.5h", 5400),
            ("60s", 60),
        ]

        for duration_str, expected_seconds in test_cases:
            success, msg, project, duration = timer_service.manual_log(
                p1.name, duration_str, f"测试 {duration_str}"
            )
            assert success is True, f"format {duration_str} should succeed"
            assert duration == expected_seconds, f"format {duration_str} should return {expected_seconds}"



    def test_manual_log_zero_duration_raises(self, timer_service, sample_projects):
        """测试 0 时长手动补录失败"""
        p1 = sample_projects["p1"]

        success, msg, project, duration = timer_service.manual_log(
            p1.name, "0h"
        )

        assert success is False
        assert project is None
        assert duration is None

    def test_manual_log_with_note(self, timer_service, sample_projects, time_entry_repo):
        """测试 manual_log 备注正确保存"""
        p1 = sample_projects["p1"]
        test_note = "这是一条测试备注"

        success, msg, project, duration = timer_service.manual_log(
            p1.name, "1h", test_note
        )

        assert success is True

        entries = time_entry_repo.list_entries(project_id=p1.id)
        assert len(entries) == 1
        assert entries[0].note == test_note
