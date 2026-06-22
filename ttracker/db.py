"""db.py - 向后兼容层，内部委托给 Repository。重构完成后可删除此文件。"""
from typing import List, Optional, Tuple
from datetime import datetime

from .database import get_connection, init_db, get_db_path  # noqa: F401
from .models import Project, TimeEntry
from .repositories import (
    ProjectRepository,
    TimeEntryRepository,
    TagRepository,
    BudgetRepository,
)

_project_repo = ProjectRepository()
_time_entry_repo = TimeEntryRepository()
_tag_repo = TagRepository()
_budget_repo = BudgetRepository()


# ── 项目 ─────────────────────────────────────────────────────────

def add_project(name: str, description: str, client: str, rate: float) -> int:
    return _project_repo.add(name, description, client, rate)


def update_project(project_id: int, name: Optional[str] = None,
                   description: Optional[str] = None, client: Optional[str] = None,
                   rate: Optional[float] = None) -> bool:
    return _project_repo.update(project_id, name, description, client, rate)


def delete_project(project_id: int) -> bool:
    return _project_repo.delete(project_id)


def get_all_projects() -> List[Project]:
    return _project_repo.get_all()


def get_project_by_id(project_id: int) -> Optional[Project]:
    return _project_repo.get_by_id(project_id)


def get_project_by_name(name: str) -> Optional[Project]:
    return _project_repo.get_by_name(name)


# ── 工时记录 ──────────────────────────────────────────────────────

def add_time_entry(project_id: int, start_time: datetime, end_time: datetime,
                   duration: int, note: str = "") -> int:
    return _time_entry_repo.add(project_id, start_time, end_time, duration, note)


def start_active_entry(project_id: int, start_time: datetime) -> int:
    return _time_entry_repo.start_active(project_id, start_time)


def stop_active_entry(entry_id: int, end_time: datetime, duration: int,
                      note: str = "") -> bool:
    return _time_entry_repo.stop_active(entry_id, end_time, duration, note)


def get_active_entry() -> Optional[TimeEntry]:
    return _time_entry_repo.get_active()


def stop_all_active_entries(end_time: datetime) -> List[Tuple[int, int]]:
    return _time_entry_repo.stop_all_active(end_time)


def get_time_entries(start_date: Optional[datetime] = None,
                     end_date: Optional[datetime] = None,
                     project_id: Optional[int] = None,
                     project_name: Optional[str] = None,
                     tag_name: Optional[str] = None) -> List[TimeEntry]:
    return _time_entry_repo.list_entries(start_date, end_date, project_id, project_name, tag_name)


def get_entries_by_project(start_date: Optional[datetime] = None,
                           end_date: Optional[datetime] = None,
                           tag_name: Optional[str] = None) -> List[Tuple[Project, int, float]]:
    return _time_entry_repo.group_by_project(start_date, end_date, tag_name)


# ── 标签 ──────────────────────────────────────────────────────────

def get_or_create_tag(name: str) -> int:
    return _tag_repo._get_or_create(name)


def add_tag_to_project(project_id: int, tag_name: str) -> bool:
    return _tag_repo.add_to_project(project_id, tag_name)


def remove_tag_from_project(project_id: int, tag_name: str) -> bool:
    return _tag_repo.remove_from_project(project_id, tag_name)


def get_project_tags(project_id: int) -> List[str]:
    return _tag_repo.get_for_project(project_id)


def get_all_tags() -> List[str]:
    return _tag_repo.get_all()


# ── 预算 ──────────────────────────────────────────────────────────

def set_budget_hours(project_id: int, hours_limit: Optional[float]) -> bool:
    return _budget_repo.set_hours(project_id, hours_limit)


def set_budget_cost(project_id: int, cost_limit: Optional[float]) -> bool:
    return _budget_repo.set_cost(project_id, cost_limit)


def get_project_budget(project_id: int) -> Tuple[Optional[float], Optional[float]]:
    return _budget_repo.get(project_id)


def get_project_total_usage(project_id: int) -> Tuple[int, float]:
    return _project_repo.get_total_usage(project_id)
