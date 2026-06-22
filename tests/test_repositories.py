"""数据库层完整测试 - 覆盖所有 Repository 方法"""
import sqlite3
from datetime import datetime, timedelta

import pytest

from ttracker.database import get_connection


# ── ProjectRepository 测试 ────────────────────────────────────────────


@pytest.mark.repo
def test_project_add_success(project_repo):
    pid = project_repo.add("测试项目", "项目描述", "客户A", 200.0)
    assert pid > 0
    p = project_repo.get_by_id(pid)
    assert p is not None
    assert p.name == "测试项目"
    assert p.description == "项目描述"
    assert p.client == "客户A"
    assert p.rate == 200.0


@pytest.mark.repo
def test_project_add_duplicate_name_fails(project_repo):
    project_repo.add("测试项目", "描述1", "客户A", 200.0)
    with pytest.raises(sqlite3.IntegrityError):
        project_repo.add("测试项目", "描述2", "客户B", 300.0)


@pytest.mark.repo
def test_project_update_success(project_repo, sample_projects):
    p1 = sample_projects["p1"]
    result = project_repo.update(p1.id, name="新名称", client="新客户")
    assert result is True
    updated = project_repo.get_by_id(p1.id)
    assert updated.name == "新名称"
    assert updated.client == "新客户"
    assert updated.description == p1.description
    assert updated.rate == p1.rate


@pytest.mark.repo
def test_project_update_nonexistent_returns_false(project_repo):
    result = project_repo.update(99999, name="不存在")
    assert result is False


@pytest.mark.repo
def test_project_update_no_fields_returns_false(project_repo, sample_projects):
    p1 = sample_projects["p1"]
    result = project_repo.update(p1.id)
    assert result is False


@pytest.mark.repo
def test_project_delete_cascades_all_related(
    project_repo, time_entry_repo, tag_repo, budget_repo, sample_projects, sample_time_entries
):
    p1 = sample_projects["p1"]
    p2 = sample_projects["p2"]

    tag_repo.add_to_project(p1.id, "测试标签")
    tag_repo.add_to_project(p1.id, "另一个标签")
    budget_repo.set_hours(p1.id, 100.0)
    budget_repo.set_cost(p1.id, 5000.0)

    assert time_entry_repo.list_entries(project_id=p1.id)
    assert tag_repo.get_for_project(p1.id)
    assert budget_repo.get(p1.id) != (None, None)

    result = project_repo.delete(p1.id)
    assert result is True

    assert project_repo.get_by_id(p1.id) is None
    assert time_entry_repo.list_entries(project_id=p1.id) == []
    assert tag_repo.get_for_project(p1.id) == []
    assert budget_repo.get(p1.id) == (None, None)

    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM time_entries WHERE project_id = ?", (p1.id,))
        assert cur.fetchone()[0] == 0
        cur.execute("SELECT COUNT(*) FROM project_tags WHERE project_id = ?", (p1.id,))
        assert cur.fetchone()[0] == 0
        cur.execute("SELECT COUNT(*) FROM budgets WHERE project_id = ?", (p1.id,))
        assert cur.fetchone()[0] == 0
    finally:
        conn.close()

    assert project_repo.get_by_id(p2.id) is not None


@pytest.mark.repo
def test_project_delete_nonexistent_returns_false(project_repo):
    result = project_repo.delete(99999)
    assert result is False


@pytest.mark.repo
def test_project_get_all(project_repo, sample_projects):
    projects = project_repo.get_all()
    assert len(projects) == 2
    assert projects[0].name == "官网改版"
    assert projects[1].name == "小程序开发"


@pytest.mark.repo
def test_project_get_all_empty(project_repo):
    projects = project_repo.get_all()
    assert projects == []


@pytest.mark.repo
def test_project_get_by_id_exists(project_repo, sample_projects):
    p1 = sample_projects["p1"]
    result = project_repo.get_by_id(p1.id)
    assert result is not None
    assert result.id == p1.id
    assert result.name == p1.name


@pytest.mark.repo
def test_project_get_by_id_not_exists(project_repo):
    result = project_repo.get_by_id(99999)
    assert result is None


@pytest.mark.repo
def test_project_get_by_name_exists(project_repo, sample_projects):
    result = project_repo.get_by_name("官网改版")
    assert result is not None
    assert result.name == "官网改版"


@pytest.mark.repo
def test_project_get_by_name_not_exists(project_repo):
    result = project_repo.get_by_name("不存在的项目")
    assert result is None


@pytest.mark.repo
def test_project_get_total_usage_empty_project(project_repo):
    pid = project_repo.add("空项目", "", "", 100.0)
    seconds, cost = project_repo.get_total_usage(pid)
    assert seconds == 0
    assert cost == 0.0


@pytest.mark.repo
def test_project_get_total_usage_with_entries(project_repo, sample_projects, sample_time_entries):
    p1 = sample_projects["p1"]
    seconds, cost = project_repo.get_total_usage(p1.id)
    assert seconds == 5400
    expected_cost = (5400 / 3600.0) * 300.0
    assert abs(cost - expected_cost) < 0.01


@pytest.mark.repo
def test_project_get_total_usage_nonexistent_project(project_repo):
    seconds, cost = project_repo.get_total_usage(99999)
    assert seconds == 0
    assert cost == 0.0


# ── TimeEntryRepository 测试 ─────────────────────────────────────────


@pytest.mark.repo
def test_time_entry_add_success(time_entry_repo, sample_projects):
    p1 = sample_projects["p1"]
    now = datetime.now()
    start = now.replace(hour=9, minute=0, second=0, microsecond=0)
    end = now.replace(hour=10, minute=0, second=0, microsecond=0)
    eid = time_entry_repo.add(p1.id, start, end, 3600, "测试任务")
    assert eid > 0
    entries = time_entry_repo.list_entries(project_id=p1.id)
    assert len(entries) == 1
    assert entries[0].duration == 3600
    assert entries[0].note == "测试任务"


@pytest.mark.repo
def test_time_entry_start_stop_active_flow(time_entry_repo, project_repo):
    pid = project_repo.add("计时器项目", "", "", 150.0)
    start = datetime.now().replace(hour=9, minute=0, second=0, microsecond=0)

    assert time_entry_repo.get_active() is None

    eid = time_entry_repo.start_active(pid, start)
    assert eid > 0

    active = time_entry_repo.get_active()
    assert active is not None
    assert active.id == eid
    assert active.project_id == pid
    assert active.end_time is None

    end = start + timedelta(hours=1)
    result = time_entry_repo.stop_active(eid, end, 3600, "完成任务")
    assert result is True

    assert time_entry_repo.get_active() is None

    entries = time_entry_repo.list_entries(project_id=pid)
    assert len(entries) == 1
    assert entries[0].duration == 3600
    assert entries[0].note == "完成任务"


@pytest.mark.repo
def test_time_entry_stop_active_nonexistent_returns_false(time_entry_repo):
    end = datetime.now()
    result = time_entry_repo.stop_active(99999, end, 3600, "")
    assert result is False


@pytest.mark.repo
def test_time_entry_stop_all_active(time_entry_repo, project_repo):
    p1 = project_repo.add("项目1", "", "", 100.0)
    p2 = project_repo.add("项目2", "", "", 200.0)
    now = datetime.now().replace(hour=8, minute=0, second=0, microsecond=0)

    e1 = time_entry_repo.start_active(p1, now)
    e2 = time_entry_repo.start_active(p2, now + timedelta(hours=1))

    end_time = now + timedelta(hours=2)
    stopped = time_entry_repo.stop_all_active(end_time)

    assert len(stopped) == 2
    stopped_ids = {s[0] for s in stopped}
    assert e1 in stopped_ids
    assert e2 in stopped_ids

    durations = {s[0]: s[1] for s in stopped}
    assert durations[e1] == 7200
    assert durations[e2] == 3600

    assert time_entry_repo.get_active() is None


@pytest.mark.repo
def test_time_entry_stop_all_active_empty(time_entry_repo):
    end = datetime.now()
    result = time_entry_repo.stop_all_active(end)
    assert result == []


@pytest.mark.repo
def test_time_entry_list_entries_today(time_entry_repo, sample_time_entries):
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    tomorrow = today + timedelta(days=1)
    entries = time_entry_repo.list_entries(start_date=today, end_date=tomorrow)
    assert len(entries) == 4


@pytest.mark.repo
def test_time_entry_list_entries_yesterday(time_entry_repo, sample_projects):
    p1 = sample_projects["p1"]
    yesterday = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=1)
    start = yesterday + timedelta(hours=9)
    end = yesterday + timedelta(hours=10)
    time_entry_repo.add(p1.id, start, end, 3600, "昨天的任务")

    day_start = yesterday
    day_end = yesterday + timedelta(days=1)
    entries = time_entry_repo.list_entries(start_date=day_start, end_date=day_end)
    assert len(entries) == 1
    assert entries[0].note == "昨天的任务"


@pytest.mark.repo
def test_time_entry_list_entries_last_week(time_entry_repo, sample_projects):
    p1 = sample_projects["p1"]
    last_week = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=7)
    start = last_week + timedelta(hours=9)
    end = last_week + timedelta(hours=10)
    time_entry_repo.add(p1.id, start, end, 3600, "上周任务")

    week_start = last_week - timedelta(days=last_week.weekday())
    week_end = week_start + timedelta(days=7)
    entries = time_entry_repo.list_entries(start_date=week_start, end_date=week_end)
    assert len(entries) == 1
    assert entries[0].note == "上周任务"


@pytest.mark.repo
def test_time_entry_list_entries_specific_month(time_entry_repo, sample_projects):
    p1 = sample_projects["p1"]
    now = datetime.now()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if month_start.month == 12:
        next_month = month_start.replace(year=month_start.year + 1, month=1)
    else:
        next_month = month_start.replace(month=month_start.month + 1)

    start = month_start + timedelta(days=5, hours=9)
    end = month_start + timedelta(days=5, hours=10)
    time_entry_repo.add(p1.id, start, end, 3600, "当月任务")

    entries = time_entry_repo.list_entries(start_date=month_start, end_date=next_month)
    assert len(entries) >= 1


@pytest.mark.repo
def test_time_entry_list_entries_by_project_name(time_entry_repo, sample_time_entries):
    entries = time_entry_repo.list_entries(project_name="官网改版")
    assert len(entries) == 2
    for e in entries:
        assert e.project_name == "官网改版"


@pytest.mark.repo
def test_time_entry_list_entries_by_project_id(time_entry_repo, sample_projects, sample_time_entries):
    p2 = sample_projects["p2"]
    entries = time_entry_repo.list_entries(project_id=p2.id)
    assert len(entries) == 2
    for e in entries:
        assert e.project_id == p2.id


@pytest.mark.repo
def test_time_entry_list_entries_by_tag(time_entry_repo, sample_project_with_tags):
    p1 = sample_project_with_tags["p1"]
    p2 = sample_project_with_tags["p2"]
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

    start = today + timedelta(hours=9)
    end = today + timedelta(hours=10)
    time_entry_repo.add(p1.id, start, end, 3600, "前端任务")
    time_entry_repo.add(p2.id, start, end, 3600, "后端任务")

    entries = time_entry_repo.list_entries(tag_name="前端")
    assert len(entries) == 1
    assert entries[0].project_id == p1.id

    entries = time_entry_repo.list_entries(tag_name="后端")
    assert len(entries) == 1
    assert entries[0].project_id == p2.id


@pytest.mark.repo
def test_time_entry_list_entries_no_filters(time_entry_repo, sample_time_entries):
    entries = time_entry_repo.list_entries()
    assert len(entries) == 4


@pytest.mark.repo
def test_time_entry_group_by_project_overlapping_intervals(
    time_entry_repo, project_repo
):
    pid = project_repo.add("重叠测试项目", "", "", 300.0)
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

    s1 = today + timedelta(hours=9)
    e1 = today + timedelta(hours=10)
    time_entry_repo.add(pid, s1, e1, 3600, "任务1")

    s2 = today + timedelta(hours=9, minutes=30)
    e2 = today + timedelta(hours=10, minutes=30)
    time_entry_repo.add(pid, s2, e2, 3600, "任务2")

    results = time_entry_repo.group_by_project()
    assert len(results) == 1
    project, duration, cost = results[0]
    assert project.id == pid
    assert duration == 5400
    expected_cost = (5400 / 3600.0) * 300.0
    assert abs(cost - expected_cost) < 0.01


@pytest.mark.repo
def test_time_entry_group_by_project_with_date_range(
    time_entry_repo, sample_projects, sample_time_entries
):
    p1 = sample_projects["p1"]
    p2 = sample_projects["p2"]
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    tomorrow = today + timedelta(days=1)

    results = time_entry_repo.group_by_project(start_date=today, end_date=tomorrow)
    assert len(results) == 2

    result_map = {r[0].id: r for r in results}
    _, p1_duration, _ = result_map[p1.id]
    _, p2_duration, _ = result_map[p2.id]

    assert p1_duration == 5400
    assert p2_duration == 7200


@pytest.mark.repo
def test_time_entry_group_by_project_with_tag(
    time_entry_repo, sample_project_with_tags
):
    p1 = sample_project_with_tags["p1"]
    p2 = sample_project_with_tags["p2"]
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

    start = today + timedelta(hours=9)
    end = today + timedelta(hours=10)
    time_entry_repo.add(p1.id, start, end, 3600, "前端任务")
    time_entry_repo.add(p2.id, start, end, 3600, "后端任务")

    results = time_entry_repo.group_by_project(tag_name="React")
    assert len(results) == 1
    assert results[0][0].id == p1.id


@pytest.mark.repo
def test_time_entry_group_by_project_empty(time_entry_repo):
    results = time_entry_repo.group_by_project()
    assert results == []


@pytest.mark.repo
def test_time_entry_group_by_project_sorted_by_duration_desc(
    time_entry_repo, project_repo
):
    p1_id = project_repo.add("项目A", "", "", 100.0)
    p2_id = project_repo.add("项目B", "", "", 200.0)
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

    s1 = today + timedelta(hours=9)
    e1 = today + timedelta(hours=10)
    time_entry_repo.add(p1_id, s1, e1, 3600, "短任务")

    s2 = today + timedelta(hours=11)
    e2 = today + timedelta(hours=13)
    time_entry_repo.add(p2_id, s2, e2, 7200, "长任务")

    results = time_entry_repo.group_by_project()
    assert len(results) == 2
    assert results[0][0].id == p2_id
    assert results[0][1] == 7200
    assert results[1][0].id == p1_id
    assert results[1][1] == 3600


# ── TagRepository 测试 ───────────────────────────────────────────────


@pytest.mark.repo
def test_tag_add_to_project_success(tag_repo, sample_projects):
    p1 = sample_projects["p1"]
    result = tag_repo.add_to_project(p1.id, "新标签")
    assert result is True
    tags = tag_repo.get_for_project(p1.id)
    assert "新标签" in tags


@pytest.mark.repo
def test_tag_add_to_project_duplicate_returns_false(tag_repo, sample_projects):
    p1 = sample_projects["p1"]
    assert tag_repo.add_to_project(p1.id, "重复标签") is True
    assert tag_repo.add_to_project(p1.id, "重复标签") is False
    tags = tag_repo.get_for_project(p1.id)
    assert tags.count("重复标签") == 1


@pytest.mark.repo
def test_tag_remove_from_project_exists(tag_repo, sample_project_with_tags):
    p1 = sample_project_with_tags["p1"]
    assert "React" in tag_repo.get_for_project(p1.id)
    result = tag_repo.remove_from_project(p1.id, "React")
    assert result is True
    assert "React" not in tag_repo.get_for_project(p1.id)


@pytest.mark.repo
def test_tag_remove_from_project_not_exists(tag_repo, sample_projects):
    p1 = sample_projects["p1"]
    result = tag_repo.remove_from_project(p1.id, "不存在的标签")
    assert result is False


@pytest.mark.repo
def test_tag_remove_from_project_tag_not_in_system(tag_repo, sample_projects):
    p1 = sample_projects["p1"]
    result = tag_repo.remove_from_project(p1.id, "从未存在过的标签")
    assert result is False


@pytest.mark.repo
def test_tag_get_for_project(tag_repo, sample_project_with_tags):
    p1 = sample_project_with_tags["p1"]
    tags = tag_repo.get_for_project(p1.id)
    assert tags == ["React", "前端", "设计"]


@pytest.mark.repo
def test_tag_get_for_project_empty(tag_repo, sample_projects):
    p1 = sample_projects["p1"]
    tags = tag_repo.get_for_project(p1.id)
    assert tags == []


@pytest.mark.repo
def test_tag_get_all(tag_repo, sample_project_with_tags):
    all_tags = tag_repo.get_all()
    assert sorted(all_tags) == ["Node.js", "React", "前端", "后端", "设计"]
    assert len(all_tags) == 5


@pytest.mark.repo
def test_tag_get_all_empty(tag_repo):
    all_tags = tag_repo.get_all()
    assert all_tags == []


# ── BudgetRepository 测试 ────────────────────────────────────────────


@pytest.mark.repo
def test_budget_set_hours_create_new(budget_repo, sample_projects):
    p1 = sample_projects["p1"]
    result = budget_repo.set_hours(p1.id, 100.0)
    assert result is True
    hours, cost = budget_repo.get(p1.id)
    assert hours == 100.0
    assert cost is None


@pytest.mark.repo
def test_budget_set_hours_update_existing(budget_repo, sample_projects):
    p1 = sample_projects["p1"]
    budget_repo.set_hours(p1.id, 100.0)
    result = budget_repo.set_hours(p1.id, 200.0)
    assert result is True
    hours, _ = budget_repo.get(p1.id)
    assert hours == 200.0


@pytest.mark.repo
def test_budget_set_cost_create_new(budget_repo, sample_projects):
    p1 = sample_projects["p1"]
    result = budget_repo.set_cost(p1.id, 5000.0)
    assert result is True
    hours, cost = budget_repo.get(p1.id)
    assert hours is None
    assert cost == 5000.0


@pytest.mark.repo
def test_budget_set_cost_update_existing(budget_repo, sample_projects):
    p1 = sample_projects["p1"]
    budget_repo.set_cost(p1.id, 5000.0)
    result = budget_repo.set_cost(p1.id, 10000.0)
    assert result is True
    _, cost = budget_repo.get(p1.id)
    assert cost == 10000.0


@pytest.mark.repo
def test_budget_set_both_hours_and_cost(budget_repo, sample_projects):
    p1 = sample_projects["p1"]
    budget_repo.set_hours(p1.id, 100.0)
    budget_repo.set_cost(p1.id, 5000.0)
    hours, cost = budget_repo.get(p1.id)
    assert hours == 100.0
    assert cost == 5000.0


@pytest.mark.repo
def test_budget_get_with_budget(budget_repo, sample_projects):
    p1 = sample_projects["p1"]
    budget_repo.set_hours(p1.id, 80.0)
    budget_repo.set_cost(p1.id, 24000.0)
    hours, cost = budget_repo.get(p1.id)
    assert hours == 80.0
    assert cost == 24000.0


@pytest.mark.repo
def test_budget_get_without_budget(budget_repo, sample_projects):
    p1 = sample_projects["p1"]
    hours, cost = budget_repo.get(p1.id)
    assert hours is None
    assert cost is None


@pytest.mark.repo
def test_budget_get_nonexistent_project(budget_repo):
    hours, cost = budget_repo.get(99999)
    assert hours is None
    assert cost is None


@pytest.mark.repo
def test_budget_set_null_values(budget_repo, sample_projects):
    p1 = sample_projects["p1"]
    budget_repo.set_hours(p1.id, 100.0)
    budget_repo.set_cost(p1.id, 5000.0)
    budget_repo.set_hours(p1.id, None)
    budget_repo.set_cost(p1.id, None)
    hours, cost = budget_repo.get(p1.id)
    assert hours is None
    assert cost is None
