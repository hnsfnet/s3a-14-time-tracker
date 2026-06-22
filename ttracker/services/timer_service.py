from datetime import datetime, timedelta
from typing import Optional, Tuple

from ..models import Project
from ..repositories import ProjectRepository, TimeEntryRepository
from ..timer import parse_duration


class TimerService:

    def __init__(self) -> None:
        self._time_entry_repo = TimeEntryRepository()
        self._project_repo = ProjectRepository()

    def start_timer(self, project_name: str) -> Tuple[bool, str, Optional[Project], Optional[Tuple[int, int]]]:
        project = self._project_repo.get_by_name(project_name)
        if not project:
            return False, f"项目 '{project_name}' 不存在", None, None

        now = datetime.now()
        stopped_info = None

        active = self._time_entry_repo.get_active()
        if active:
            if active.project_id == project.id:
                return False, f"项目 '{project_name}' 已经在计时中", project, None

            old_start = active.start_time
            duration = int((now - old_start).total_seconds())
            self._time_entry_repo.stop_active(active.id, now, duration)
            stopped_info = (active.id, duration)

        self._time_entry_repo.start_active(project.id, now)
        return True, f"开始计时项目 '{project_name}'", project, stopped_info

    def stop_timer(self, note: str = "") -> Tuple[bool, str, Optional[Project], Optional[int]]:
        active = self._time_entry_repo.get_active()
        if not active:
            return False, "当前没有正在进行的计时", None, None

        now = datetime.now()
        duration = int((now - active.start_time).total_seconds())
        self._time_entry_repo.stop_active(active.id, now, duration, note)

        project = self._project_repo.get_by_id(active.project_id)
        return True, "计时已停止", project, duration

    def get_timer_status(self) -> Tuple[bool, str, Optional[Project], Optional[int], Optional[datetime]]:
        active = self._time_entry_repo.get_active()
        if not active:
            return False, "当前没有正在进行的计时", None, None, None

        now = datetime.now()
        duration = int((now - active.start_time).total_seconds())
        project = self._project_repo.get_by_id(active.project_id)
        return True, "计时中", project, duration, active.start_time

    def manual_log(self, project_name: str, duration_str: str, note: str = "",
                   start_time: Optional[datetime] = None) -> Tuple[bool, str, Optional[Project], Optional[int]]:
        project = self._project_repo.get_by_name(project_name)
        if not project:
            return False, f"项目 '{project_name}' 不存在", None, None

        try:
            duration = parse_duration(duration_str)
        except ValueError as e:
            return False, str(e), None, None

        now = start_time or datetime.now()
        end_time = now
        start = now - timedelta(seconds=duration)

        self._time_entry_repo.add(project.id, start, end_time, duration, note)
        return True, "已补录时长", project, duration
