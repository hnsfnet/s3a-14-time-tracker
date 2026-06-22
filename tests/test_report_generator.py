"""ReportGenerator 报表计算层测试"""
from datetime import datetime, timedelta

import pytest


@pytest.mark.report
class TestGetDateRange:
    """get_date_range 方法测试：所有 period 返回正确日期范围和描述"""

    def test_today_period(self, report_generator):
        start, end, desc = report_generator.get_date_range("today")
        now = datetime.now()
        assert start.hour == 0 and start.minute == 0 and start.second == 0
        assert end == start + timedelta(days=1)
        assert "今日" in desc
        assert start.strftime("%Y年%m月%d日") in desc

    def test_daily_period(self, report_generator):
        start, end, desc = report_generator.get_date_range("daily")
        now = datetime.now()
        assert start.hour == 0 and start.minute == 0 and start.second == 0
        assert end == start + timedelta(days=1)
        assert "今日" in desc

    def test_week_period(self, report_generator):
        start, end, desc = report_generator.get_date_range("week")
        assert start.weekday() == 0
        assert start.hour == 0 and start.minute == 0 and start.second == 0
        assert end == start + timedelta(days=7)
        assert "本周" in desc

    def test_weekly_period(self, report_generator):
        start, end, desc = report_generator.get_date_range("weekly")
        assert start.weekday() == 0
        assert end == start + timedelta(days=7)
        assert "本周" in desc

    def test_month_period_default(self, report_generator):
        start, end, desc = report_generator.get_date_range("month")
        now = datetime.now()
        assert start.day == 1
        assert start.hour == 0 and start.minute == 0 and start.second == 0
        if start.month == 12:
            assert end == datetime(start.year + 1, 1, 1)
        else:
            assert end == datetime(start.year, start.month + 1, 1)
        assert "月度" in desc
        assert start.strftime("%Y年%m月") in desc

    def test_month_period_with_value(self, report_generator):
        start, end, desc = report_generator.get_date_range("month", "2024-06")
        assert start == datetime(2024, 6, 1)
        assert end == datetime(2024, 7, 1)
        assert "2024年06月" in desc

    def test_month_period_december(self, report_generator):
        start, end, desc = report_generator.get_date_range("month", "2024-12")
        assert start == datetime(2024, 12, 1)
        assert end == datetime(2025, 1, 1)

    def test_all_period(self, report_generator):
        start, end, desc = report_generator.get_date_range("all")
        assert start == datetime(2000, 1, 1)
        assert end == datetime(2099, 12, 31)
        assert desc == "全部记录"

    def test_invalid_period(self, report_generator):
        with pytest.raises(ValueError, match="未知的周期"):
            report_generator.get_date_range("invalid")

    def test_invalid_month_format(self, report_generator):
        with pytest.raises(ValueError, match="月份格式错误"):
            report_generator.get_date_range("month", "abc")


@pytest.mark.report
class TestGenerateLogEntriesData:
    """generate_log_entries_data 方法测试"""

    def test_today_period_entries_count(self, report_generator, sample_time_entries):
        result = report_generator.generate_log_entries_data(period="today")
        assert not result["empty"]
        assert len(result["entries"]) == 4
        assert "total_duration" in result

    def test_week_period_entries_count(self, report_generator, sample_time_entries):
        result = report_generator.generate_log_entries_data(period="week")
        assert not result["empty"]
        assert len(result["entries"]) == 4

    def test_month_period_entries_count(self, report_generator, sample_time_entries):
        result = report_generator.generate_log_entries_data(period="month")
        assert not result["empty"]
        assert len(result["entries"]) == 4

    def test_all_period_entries_count(self, report_generator, sample_time_entries):
        result = report_generator.generate_log_entries_data(period="all")
        assert not result["empty"]
        assert len(result["entries"]) == 4

    def test_filter_by_project_name(self, report_generator, sample_time_entries, sample_projects):
        p1 = sample_projects["p1"]
        result = report_generator.generate_log_entries_data(period="all", project_name=p1.name)
        assert not result["empty"]
        assert len(result["entries"]) == 2
        for entry in result["entries"]:
            assert entry.project_id == p1.id

    def test_filter_by_project_name_not_found(self, report_generator):
        result = report_generator.generate_log_entries_data(period="all", project_name="不存在的项目")
        assert "error" in result
        assert "不存在" in result["error"]

    def test_filter_by_tag_name(self, report_generator, sample_project_with_tags, time_entry_repo):
        p1 = sample_project_with_tags["p1"]
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        s = today + timedelta(hours=9)
        e = today + timedelta(hours=10)
        time_entry_repo.add(p1.id, s, e, 3600, "带标签任务")

        result = report_generator.generate_log_entries_data(period="today", tag_name="前端")
        assert not result["empty"]
        assert len(result["entries"]) >= 1
        for entry in result["entries"]:
            assert entry.project_id == p1.id

    def test_total_duration_is_merged_not_sum(self, report_generator, sample_time_entries, sample_projects):
        """验证 total_duration 是合并重叠后的值，而非简单相加"""
        p1 = sample_projects["p1"]
        result = report_generator.generate_log_entries_data(period="today", project_name=p1.name)
        p1_entries = result["entries"]
        assert len(p1_entries) == 2

        raw_sum = sum(e.duration for e in p1_entries)
        assert raw_sum == 7200

        merged_duration = result["total_duration"]
        expected_merged = 5400
        assert merged_duration == expected_merged
        assert merged_duration < raw_sum


@pytest.mark.report
class TestGenerateReportData:
    """generate_report_data 方法测试：按项目汇总，重叠去重"""

    def test_aggregate_by_project(self, report_generator, sample_time_entries, sample_projects):
        result = report_generator.generate_report_data(period="week")
        assert not result["empty"]
        assert len(result["project_rows"]) == 2

        project_names = [row["project"].name for row in result["project_rows"]]
        assert sample_projects["p1"].name in project_names
        assert sample_projects["p2"].name in project_names

    def test_overlapping_intervals_deduplication(self, report_generator, sample_time_entries, sample_projects):
        """验证重叠时间段去重：09:00-10:00 和 09:30-10:30 合并后应为 90 分钟"""
        result = report_generator.generate_report_data(period="week")

        p1_row = None
        for row in result["project_rows"]:
            if row["project"].id == sample_projects["p1"].id:
                p1_row = row
                break

        assert p1_row is not None
        expected_duration = 5400
        assert p1_row["duration"] == expected_duration

    def test_filter_by_tag(self, report_generator, sample_project_with_tags, time_entry_repo):
        """按 tag 筛选只返回带该 tag 的项目"""
        p1 = sample_project_with_tags["p1"]
        p2 = sample_project_with_tags["p2"]
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

        s = today + timedelta(hours=9)
        e = today + timedelta(hours=10)
        time_entry_repo.add(p1.id, s, e, 3600, "p1任务")

        s = today + timedelta(hours=14)
        e = today + timedelta(hours=15)
        time_entry_repo.add(p2.id, s, e, 3600, "p2任务")

        result = report_generator.generate_report_data(period="week", tag_name="前端")
        assert not result["empty"]
        assert len(result["project_rows"]) == 1
        assert result["project_rows"][0]["project"].id == p1.id
        assert "标签: 前端" in result["desc"]

    def test_total_duration_and_cost(self, report_generator, sample_time_entries):
        result = report_generator.generate_report_data(period="week")
        assert not result["empty"]

        calc_total_duration = sum(row["duration"] for row in result["project_rows"])
        calc_total_cost = sum(row["cost"] for row in result["project_rows"])

        assert result["total_duration"] == calc_total_duration
        assert abs(result["total_cost"] - calc_total_cost) < 0.01

    def test_empty_result(self, report_generator):
        result = report_generator.generate_report_data(period="week")
        assert result["empty"]
        assert "desc" in result


@pytest.mark.report
class TestGenerateDailyData:
    """generate_daily_data 方法测试：按项目分组，验证合并去重"""

    def test_group_by_project(self, report_generator, sample_time_entries, sample_projects):
        result = report_generator.generate_daily_data()
        assert not result["empty"]
        assert len(result["project_sections"]) == 2

        proj_names = [section["proj_name"] for section in result["project_sections"]]
        assert sample_projects["p1"].name in proj_names
        assert sample_projects["p2"].name in proj_names

    def test_project_duration_is_merged(self, report_generator, sample_time_entries, sample_projects):
        """验证每个项目的 duration 是合并去重后的值"""
        result = report_generator.generate_daily_data()

        p1_section = None
        for section in result["project_sections"]:
            if section["proj_name"] == sample_projects["p1"].name:
                p1_section = section
                break

        assert p1_section is not None
        assert p1_section["proj_total"] == 5400

        p2_section = None
        for section in result["project_sections"]:
            if section["proj_name"] == sample_projects["p2"].name:
                p2_section = section
                break

        assert p2_section is not None
        assert p2_section["proj_total"] == 7200

    def test_total_duration_and_cost(self, report_generator, sample_time_entries):
        result = report_generator.generate_daily_data()
        assert not result["empty"]

        calc_total_duration = sum(section["proj_total"] for section in result["project_sections"])
        calc_total_cost = sum(section["proj_cost"] for section in result["project_sections"])

        assert result["total_duration"] == calc_total_duration
        assert abs(result["total_cost"] - calc_total_cost) < 0.01

    def test_empty_result(self, report_generator):
        result = report_generator.generate_daily_data()
        assert result["empty"]
        assert "date_str" in result


@pytest.mark.report
class TestGenerateWeeklyData:
    """generate_weekly_data 方法测试：按天分组，验证每天总时长"""

    def test_group_by_day(self, report_generator, time_entry_repo, project_repo):
        p1_id = project_repo.add("测试项目", "描述", "客户", 300.0)
        now = datetime.now()
        week_start = now - timedelta(days=now.weekday())
        week_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)

        day1 = week_start
        s = day1 + timedelta(hours=9)
        e = day1 + timedelta(hours=10)
        time_entry_repo.add(p1_id, s, e, 3600, "周一任务")

        day2 = week_start + timedelta(days=1)
        s = day2 + timedelta(hours=14)
        e = day2 + timedelta(hours=16)
        time_entry_repo.add(p1_id, s, e, 7200, "周二任务")

        result = report_generator.generate_weekly_data()
        assert not result["empty"]
        assert len(result["day_sections"]) == 2

    def test_daily_total_duration(self, report_generator, time_entry_repo, project_repo):
        """验证每天总时长正确"""
        p1_id = project_repo.add("测试项目", "描述", "客户", 300.0)
        now = datetime.now()
        week_start = now - timedelta(days=now.weekday())
        week_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)

        target_day = week_start
        s1 = target_day + timedelta(hours=9)
        e1 = target_day + timedelta(hours=10)
        time_entry_repo.add(p1_id, s1, e1, 3600, "任务1")

        s2 = target_day + timedelta(hours=9, minutes=30)
        e2 = target_day + timedelta(hours=10, minutes=30)
        time_entry_repo.add(p1_id, s2, e2, 3600, "任务2")

        s3 = target_day + timedelta(hours=14)
        e3 = target_day + timedelta(hours=15)
        time_entry_repo.add(p1_id, s3, e3, 3600, "任务3")

        result = report_generator.generate_weekly_data()
        assert not result["empty"]
        assert len(result["day_sections"]) == 1

        day_section = result["day_sections"][0]
        expected_day_total = 5400 + 3600
        assert day_section["day_total"] == expected_day_total

    def test_week_total_duration(self, report_generator, time_entry_repo, project_repo):
        p1_id = project_repo.add("测试项目", "描述", "客户", 300.0)
        now = datetime.now()
        week_start = now - timedelta(days=now.weekday())
        week_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)

        for i in range(3):
            day = week_start + timedelta(days=i)
            s = day + timedelta(hours=9)
            e = day + timedelta(hours=10)
            time_entry_repo.add(p1_id, s, e, 3600, f"周{i+1}任务")

        result = report_generator.generate_weekly_data()
        assert not result["empty"]
        assert result["work_days"] == 3
        assert result["week_total_duration"] == 3600 * 3

    def test_empty_result(self, report_generator):
        result = report_generator.generate_weekly_data()
        assert result["empty"]
        assert "week_start_str" in result


@pytest.mark.report
class TestOverlapMergeSpecial:
    """重叠合并专项测试"""

    def test_three_overlapping_entries(self, report_generator, project_repo, time_entry_repo):
        """
        插入3条重叠记录:
        - 09:00-10:00 (60分钟)
        - 09:30-10:30 (60分钟)
        - 11:00-11:30 (30分钟)
        验证 p1 总时长为 90分钟(09:00-10:30) + 30分钟 = 120分钟
        而非 60+60+30=150分钟
        """
        p1_id = project_repo.add("p1", "测试重叠", "客户", 300.0)
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

        s1 = today + timedelta(hours=9)
        e1 = today + timedelta(hours=10)
        time_entry_repo.add(p1_id, s1, e1, 3600, "条目1")

        s2 = today + timedelta(hours=9, minutes=30)
        e2 = today + timedelta(hours=10, minutes=30)
        time_entry_repo.add(p1_id, s2, e2, 3600, "条目2")

        s3 = today + timedelta(hours=11)
        e3 = today + timedelta(hours=11, minutes=30)
        time_entry_repo.add(p1_id, s3, e3, 1800, "条目3")

        result = report_generator.generate_log_entries_data(period="today")
        raw_sum = 3600 + 3600 + 1800
        assert raw_sum == 9000

        expected_merged = 5400 + 1800
        assert result["total_duration"] == expected_merged
        assert result["total_duration"] == 7200
        assert result["total_duration"] < raw_sum

    def test_report_data_overlap_merge(self, report_generator, project_repo, time_entry_repo):
        p1_id = project_repo.add("p1", "测试重叠", "客户", 300.0)
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

        s1 = today + timedelta(hours=9)
        e1 = today + timedelta(hours=10)
        time_entry_repo.add(p1_id, s1, e1, 3600, "条目1")

        s2 = today + timedelta(hours=9, minutes=30)
        e2 = today + timedelta(hours=10, minutes=30)
        time_entry_repo.add(p1_id, s2, e2, 3600, "条目2")

        s3 = today + timedelta(hours=11)
        e3 = today + timedelta(hours=11, minutes=30)
        time_entry_repo.add(p1_id, s3, e3, 1800, "条目3")

        result = report_generator.generate_report_data(period="today")
        assert len(result["project_rows"]) == 1
        assert result["project_rows"][0]["duration"] == 7200


@pytest.mark.report
class TestCostCalculation:
    """费用计算验证"""

    def test_cost_precision_to_cents(self, report_generator, project_repo, time_entry_repo):
        """300元/小时 × 1.5小时 = 450元，验证 total_cost 精确到分"""
        p1_id = project_repo.add("计费测试", "描述", "客户", 300.0)
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

        s = today + timedelta(hours=9)
        e = today + timedelta(hours=10, minutes=30)
        time_entry_repo.add(p1_id, s, e, 5400, "1.5小时任务")

        result = report_generator.generate_log_entries_data(period="today")
        assert result["total_duration"] == 5400

        expected_cost = 450.0
        assert abs(result["total_cost"] - expected_cost) < 0.01

        cost_str = f"{result['total_cost']:.2f}"
        assert cost_str == "450.00"

    def test_report_data_cost_calculation(self, report_generator, project_repo, time_entry_repo):
        p1_id = project_repo.add("计费测试", "描述", "客户", 300.0)
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

        s = today + timedelta(hours=9)
        e = today + timedelta(hours=10, minutes=30)
        time_entry_repo.add(p1_id, s, e, 5400, "1.5小时任务")

        result = report_generator.generate_report_data(period="today")
        assert len(result["project_rows"]) == 1
        assert abs(result["project_rows"][0]["cost"] - 450.0) < 0.01
        assert abs(result["total_cost"] - 450.0) < 0.01

    def test_daily_data_cost_calculation(self, report_generator, project_repo, time_entry_repo):
        p1_id = project_repo.add("计费测试", "描述", "客户", 300.0)
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

        s = today + timedelta(hours=9)
        e = today + timedelta(hours=10, minutes=30)
        time_entry_repo.add(p1_id, s, e, 5400, "1.5小时任务")

        result = report_generator.generate_daily_data()
        assert len(result["project_sections"]) == 1
        assert abs(result["project_sections"][0]["proj_cost"] - 450.0) < 0.01
        assert abs(result["total_cost"] - 450.0) < 0.01

    def test_multiple_projects_cost(self, report_generator, project_repo, time_entry_repo):
        p1_id = project_repo.add("p1", "描述", "客户1", 300.0)
        p2_id = project_repo.add("p2", "描述", "客户2", 200.0)
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

        s = today + timedelta(hours=9)
        e = today + timedelta(hours=10)
        time_entry_repo.add(p1_id, s, e, 3600, "p1 1小时")

        s = today + timedelta(hours=14)
        e = today + timedelta(hours=15, minutes=30)
        time_entry_repo.add(p2_id, s, e, 5400, "p2 1.5小时")

        result = report_generator.generate_log_entries_data(period="today")
        expected_total = 300.0 + 300.0
        assert abs(result["total_cost"] - expected_total) < 0.01

        cost_str = f"{result['total_cost']:.2f}"
        assert cost_str == "600.00"
