"""pytest fixtures - 每个测试用独立的临时 SQLite 数据库"""
import os
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Generator, Tuple, Dict, Any

import pytest

# ── 数据库隔离：每个测试用独立临时文件 ─────────────────────────────


@pytest.fixture(autouse=True)
def isolated_db(monkeypatch, tmp_path) -> Generator[Path, None, None]:
    """自动为每个测试创建独立的临时 SQLite 数据库。

    - monkeypatch 掉 ttracker.database.get_db_path 返回临时文件
    - 每个测试前自动建表
    - 测试结束自动清理
    """
    import importlib
    from ttracker import database

    db_file = tmp_path / "test_ttracker.db"

    def _patched_get_db_path() -> Path:
        return db_file

    monkeypatch.setattr(database, "get_db_path", _patched_get_db_path)

    database.init_db()

    # 确保重新导入 db 兼容层时也用新路径
    import sys
    for mod_name in list(sys.modules.keys()):
        if mod_name.startswith("ttracker.db") or mod_name == "ttracker.db":
            importlib.reload(sys.modules[mod_name])
        if mod_name.startswith("ttracker.repositories"):
            importlib.reload(sys.modules[mod_name])
        if mod_name.startswith("ttracker.services"):
            importlib.reload(sys.modules[mod_name])
        if mod_name.startswith("ttracker.reports"):
            importlib.reload(sys.modules[mod_name])

    yield db_file


# ── Repository fixtures ───────────────────────────────────────────


@pytest.fixture
def project_repo(isolated_db):
    from ttracker.repositories import ProjectRepository
    return ProjectRepository()


@pytest.fixture
def time_entry_repo(isolated_db):
    from ttracker.repositories import TimeEntryRepository
    return TimeEntryRepository()


@pytest.fixture
def tag_repo(isolated_db):
    from ttracker.repositories import TagRepository
    return TagRepository()


@pytest.fixture
def budget_repo(isolated_db):
    from ttracker.repositories import BudgetRepository
    return BudgetRepository()


@pytest.fixture
def timer_service(isolated_db):
    from ttracker.services import TimerService
    return TimerService()


@pytest.fixture
def report_generator(isolated_db):
    from ttracker.reports import ReportGenerator
    return ReportGenerator()


# ── 预置数据 helpers ──────────────────────────────────────────────


@pytest.fixture
def sample_projects(project_repo):
    """预置 2 个项目: p1(官网改版), p2(小程序开发)"""
    p1_id = project_repo.add("官网改版", "客户官网全面改版", "某某科技", 300.0)
    p2_id = project_repo.add("小程序开发", "微信小程序从零到一", "星辰工作室", 280.0)
    return {
        "p1": project_repo.get_by_id(p1_id),
        "p2": project_repo.get_by_id(p2_id),
    }


@pytest.fixture
def sample_project_with_tags(sample_projects, tag_repo):
    p1 = sample_projects["p1"]
    tag_repo.add_to_project(p1.id, "前端")
    tag_repo.add_to_project(p1.id, "React")
    tag_repo.add_to_project(p1.id, "设计")
    p2 = sample_projects["p2"]
    tag_repo.add_to_project(p2.id, "后端")
    tag_repo.add_to_project(p2.id, "Node.js")
    from ttracker.repositories import ProjectRepository
    return {
        "p1": ProjectRepository().get_by_id(p1.id),
        "p2": ProjectRepository().get_by_id(p2.id),
    }


@pytest.fixture
def sample_time_entries(sample_projects, time_entry_repo):
    """预置今天的 3 条不重叠记录 + 1 条重叠记录"""
    p1 = sample_projects["p1"]
    p2 = sample_projects["p2"]
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

    entries = []

    # p1: 09:00-10:00 = 3600s
    s = today + timedelta(hours=9)
    e = today + timedelta(hours=10)
    entries.append(time_entry_repo.add(p1.id, s, e, 3600, "任务A"))

    # p1: 09:30-10:30 = 3600s (与上一条重叠 30 分钟)
    s = today + timedelta(hours=9, minutes=30)
    e = today + timedelta(hours=10, minutes=30)
    entries.append(time_entry_repo.add(p1.id, s, e, 3600, "任务B"))

    # p2: 11:00-12:00 = 3600s
    s = today + timedelta(hours=11)
    e = today + timedelta(hours=12)
    entries.append(time_entry_repo.add(p2.id, s, e, 3600, "任务C"))

    # p2: 14:00-15:00 = 3600s
    s = today + timedelta(hours=14)
    e = today + timedelta(hours=15)
    entries.append(time_entry_repo.add(p2.id, s, e, 3600, "任务D"))

    return entries
