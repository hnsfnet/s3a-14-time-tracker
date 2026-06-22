from typing import List, Optional

from ..database import get_connection, _attach_tags_and_budget
from ..models import Project
from ..timer import merge_overlapping_intervals


class ProjectRepository:
    """项目 CRUD + 级联删除 + 预算使用统计"""

    def add(self, name: str, description: str, client: str, rate: float) -> int:
        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO projects (name, description, client, rate) VALUES (?, ?, ?, ?)",
                (name, description, client, rate),
            )
            conn.commit()
            return cur.lastrowid
        finally:
            conn.close()

    def update(self, project_id: int, name: Optional[str] = None,
               description: Optional[str] = None, client: Optional[str] = None,
               rate: Optional[float] = None) -> bool:
        conn = get_connection()
        try:
            cur = conn.cursor()
            fields, values = [], []
            if name is not None:
                fields.append("name = ?")
                values.append(name)
            if description is not None:
                fields.append("description = ?")
                values.append(description)
            if client is not None:
                fields.append("client = ?")
                values.append(client)
            if rate is not None:
                fields.append("rate = ?")
                values.append(rate)
            if not fields:
                return False
            values.append(project_id)
            cur.execute(f"UPDATE projects SET {', '.join(fields)} WHERE id = ?", values)
            conn.commit()
            return cur.rowcount > 0
        finally:
            conn.close()

    def delete(self, project_id: int) -> bool:
        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.execute("DELETE FROM time_entries WHERE project_id = ?", (project_id,))
            cur.execute("DELETE FROM project_tags WHERE project_id = ?", (project_id,))
            cur.execute("DELETE FROM budgets WHERE project_id = ?", (project_id,))
            cur.execute("DELETE FROM projects WHERE id = ?", (project_id,))
            conn.commit()
            return cur.rowcount > 0
        finally:
            conn.close()

    def get_all(self) -> List[Project]:
        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT id, name, description, client, rate FROM projects ORDER BY id")
            rows = cur.fetchall()
            projects = [Project.from_row(row) for row in rows]
            for p in projects:
                _attach_tags_and_budget(p, conn)
            return projects
        finally:
            conn.close()

    def get_by_id(self, project_id: int) -> Optional[Project]:
        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT id, name, description, client, rate FROM projects WHERE id = ?",
                        (project_id,))
            row = cur.fetchone()
            if not row:
                return None
            project = Project.from_row(row)
            _attach_tags_and_budget(project, conn)
            return project
        finally:
            conn.close()

    def get_by_name(self, name: str) -> Optional[Project]:
        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT id, name, description, client, rate FROM projects WHERE name = ?",
                        (name,))
            row = cur.fetchone()
            if not row:
                return None
            project = Project.from_row(row)
            _attach_tags_and_budget(project, conn)
            return project
        finally:
            conn.close()

    def get_total_usage(self, project_id: int) -> tuple:
        from ..models import TimeEntry
        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT id, project_id, start_time, end_time, duration, note, NULL "
                "FROM time_entries WHERE project_id = ? AND end_time IS NOT NULL",
                (project_id,),
            )
            rows = cur.fetchall()
            entries = [TimeEntry.from_row(r) for r in rows]
            total_seconds = merge_overlapping_intervals(entries)
            project = self.get_by_id(project_id)
            rate = project.rate if project else 0.0
            total_cost = (total_seconds / 3600.0) * rate
            return total_seconds, total_cost
        finally:
            conn.close()
