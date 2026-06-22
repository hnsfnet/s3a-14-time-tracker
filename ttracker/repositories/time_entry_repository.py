from typing import List, Optional, Tuple
from datetime import datetime

from ..database import get_connection, _attach_tags_and_budget
from ..models import Project, TimeEntry
from ..timer import merge_overlapping_intervals


class TimeEntryRepository:
    """工时记录 CRUD + 查询 + 按项目汇总"""

    def add(self, project_id: int, start_time: datetime, end_time: datetime,
            duration: int, note: str = "") -> int:
        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO time_entries (project_id, start_time, end_time, duration, note)
                VALUES (?, ?, ?, ?, ?)
                """,
                (project_id, start_time.isoformat(), end_time.isoformat(), duration, note),
            )
            conn.commit()
            return cur.lastrowid
        finally:
            conn.close()

    def start_active(self, project_id: int, start_time: datetime) -> int:
        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO time_entries (project_id, start_time, duration, note) VALUES (?, ?, 0, '')",
                (project_id, start_time.isoformat()),
            )
            conn.commit()
            entry_id = cur.lastrowid
            cur.execute("UPDATE timer_state SET is_active = 1, active_entry_id = ? WHERE id = 1",
                        (entry_id,))
            conn.commit()
            return entry_id
        finally:
            conn.close()

    def stop_active(self, entry_id: int, end_time: datetime, duration: int,
                    note: str = "") -> bool:
        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.execute(
                "UPDATE time_entries SET end_time = ?, duration = ?, note = ? WHERE id = ?",
                (end_time.isoformat(), duration, note, entry_id),
            )
            cur.execute("UPDATE timer_state SET is_active = 0, active_entry_id = NULL WHERE id = 1")
            conn.commit()
            return cur.rowcount > 0
        finally:
            conn.close()

    def get_active(self) -> Optional[TimeEntry]:
        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT active_entry_id, is_active FROM timer_state WHERE id = 1")
            state = cur.fetchone()
            if not state or not state["is_active"] or not state["active_entry_id"]:
                return None
            cur.execute(
                """
                SELECT te.id, te.project_id, te.start_time, te.end_time, te.duration, te.note, p.name
                FROM time_entries te
                LEFT JOIN projects p ON te.project_id = p.id
                WHERE te.id = ?
                """,
                (state["active_entry_id"],),
            )
            row = cur.fetchone()
            if not row or row["end_time"] is not None:
                cur.execute("UPDATE timer_state SET is_active = 0, active_entry_id = NULL WHERE id = 1")
                conn.commit()
                return None
            return TimeEntry.from_row(row)
        finally:
            conn.close()

    def stop_all_active(self, end_time: datetime) -> List[Tuple[int, int]]:
        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT id, start_time FROM time_entries WHERE end_time IS NULL")
            rows = cur.fetchall()
            stopped = []
            for row in rows:
                start = datetime.fromisoformat(row["start_time"])
                duration = int((end_time - start).total_seconds())
                cur.execute(
                    "UPDATE time_entries SET end_time = ?, duration = ? WHERE id = ?",
                    (end_time.isoformat(), duration, row["id"]),
                )
                stopped.append((row["id"], duration))
            cur.execute("UPDATE timer_state SET is_active = 0, active_entry_id = NULL WHERE id = 1")
            conn.commit()
            return stopped
        finally:
            conn.close()

    def list_entries(self, start_date: Optional[datetime] = None,
                     end_date: Optional[datetime] = None,
                     project_id: Optional[int] = None,
                     project_name: Optional[str] = None,
                     tag_name: Optional[str] = None) -> List[TimeEntry]:
        conn = get_connection()
        try:
            cur = conn.cursor()
            query = """
                SELECT te.id, te.project_id, te.start_time, te.end_time, te.duration, te.note, p.name
                FROM time_entries te
                LEFT JOIN projects p ON te.project_id = p.id
                WHERE te.end_time IS NOT NULL
            """
            params = []
            if start_date:
                query += " AND te.start_time >= ?"
                params.append(start_date.isoformat())
            if end_date:
                query += " AND te.start_time < ?"
                params.append(end_date.isoformat())
            if project_id:
                query += " AND te.project_id = ?"
                params.append(project_id)
            if project_name:
                query += " AND p.name = ?"
                params.append(project_name)
            if tag_name:
                query += """
                    AND te.project_id IN (
                        SELECT pt.project_id FROM project_tags pt
                        INNER JOIN tags t ON pt.tag_id = t.id
                        WHERE t.name = ?
                    )
                """
                params.append(tag_name)
            query += " ORDER BY te.start_time ASC"
            cur.execute(query, params)
            rows = cur.fetchall()
            return [TimeEntry.from_row(row) for row in rows]
        finally:
            conn.close()

    def group_by_project(self, start_date: Optional[datetime] = None,
                         end_date: Optional[datetime] = None,
                         tag_name: Optional[str] = None) -> List[Tuple[Project, int, float]]:
        conn = get_connection()
        try:
            cur = conn.cursor()
            query = """
                SELECT DISTINCT p.id, p.name, p.description, p.client, p.rate
                FROM projects p
                INNER JOIN time_entries te ON p.id = te.project_id
                WHERE te.end_time IS NOT NULL
            """
            params = []
            if start_date:
                query += " AND te.start_time >= ?"
                params.append(start_date.isoformat())
            if end_date:
                query += " AND te.start_time < ?"
                params.append(end_date.isoformat())
            if tag_name:
                query += """
                    AND p.id IN (
                        SELECT pt.project_id FROM project_tags pt
                        INNER JOIN tags t ON pt.tag_id = t.id
                        WHERE t.name = ?
                    )
                """
                params.append(tag_name)
            query += " ORDER BY p.id"
            cur.execute(query, params)
            rows = cur.fetchall()

            results = []
            for row in rows:
                pid = row[0]
                project = Project(pid, row[1], row[2] or "", row[3] or "", row[4] or 0.0)
                _attach_tags_and_budget(project, conn)

                eq = """
                    SELECT id, project_id, start_time, end_time, duration, note, NULL
                    FROM time_entries
                    WHERE project_id = ? AND end_time IS NOT NULL
                """
                eparams = [pid]
                if start_date:
                    eq += " AND start_time >= ?"
                    eparams.append(start_date.isoformat())
                if end_date:
                    eq += " AND start_time < ?"
                    eparams.append(end_date.isoformat())
                cur.execute(eq, eparams)
                erows = cur.fetchall()
                entries = [TimeEntry.from_row(r) for r in erows]
                merged_duration = merge_overlapping_intervals(entries)
                cost = (merged_duration / 3600.0) * project.rate
                results.append((project, merged_duration, cost))

            results.sort(key=lambda x: x[1], reverse=True)
            return results
        finally:
            conn.close()
