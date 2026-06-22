import os
import sqlite3
from pathlib import Path
from typing import List, Optional, Tuple, Dict
from datetime import datetime, timedelta

from .models import Project, TimeEntry, Tag, Budget


def get_db_path() -> Path:
    home = Path.home()
    db_dir = home / ".ttracker"
    db_dir.mkdir(parents=True, exist_ok=True)
    return db_dir / "data.db"


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(str(get_db_path()))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                description TEXT,
                client TEXT,
                rate REAL NOT NULL DEFAULT 0
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS time_entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                start_time TEXT NOT NULL,
                end_time TEXT,
                duration INTEGER NOT NULL DEFAULT 0,
                note TEXT,
                FOREIGN KEY (project_id) REFERENCES projects (id) ON DELETE CASCADE
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS tags (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS project_tags (
                project_id INTEGER NOT NULL,
                tag_id INTEGER NOT NULL,
                PRIMARY KEY (project_id, tag_id),
                FOREIGN KEY (project_id) REFERENCES projects (id) ON DELETE CASCADE,
                FOREIGN KEY (tag_id) REFERENCES tags (id) ON DELETE CASCADE
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS budgets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL UNIQUE,
                hours_limit REAL,
                cost_limit REAL,
                FOREIGN KEY (project_id) REFERENCES projects (id) ON DELETE CASCADE
            )
            """
        )
        conn.commit()
    finally:
        conn.close()


def add_project(name: str, description: str, client: str, rate: float) -> int:
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


def update_project(project_id: int, name: Optional[str] = None,
                   description: Optional[str] = None, client: Optional[str] = None,
                   rate: Optional[float] = None) -> bool:
    conn = get_connection()
    try:
        cur = conn.cursor()
        fields = []
        values = []
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


def delete_project(project_id: int) -> bool:
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


def _attach_tags_and_budget(project: Project, conn: sqlite3.Connection) -> Project:
    cur = conn.cursor()
    cur.execute(
        """
        SELECT t.name FROM tags t
        INNER JOIN project_tags pt ON t.id = pt.tag_id
        WHERE pt.project_id = ?
        ORDER BY t.name
        """,
        (project.id,),
    )
    project.tags = [row["name"] for row in cur.fetchall()]

    cur.execute("SELECT hours_limit, cost_limit FROM budgets WHERE project_id = ?",
                (project.id,))
    row = cur.fetchone()
    if row:
        project.budget_hours = row["hours_limit"]
        project.budget_cost = row["cost_limit"]
    return project


def get_all_projects() -> List[Project]:
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


def get_project_by_id(project_id: int) -> Optional[Project]:
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


def get_project_by_name(name: str) -> Optional[Project]:
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


def add_time_entry(project_id: int, start_time: datetime, end_time: datetime,
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


def start_active_entry(project_id: int, start_time: datetime) -> int:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO time_entries (project_id, start_time, duration, note) VALUES (?, ?, 0, '')",
            (project_id, start_time.isoformat()),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def stop_active_entry(entry_id: int, end_time: datetime, duration: int, note: str = "") -> bool:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "UPDATE time_entries SET end_time = ?, duration = ?, note = ? WHERE id = ?",
            (end_time.isoformat(), duration, note, entry_id),
        )
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def get_active_entry() -> Optional[TimeEntry]:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT te.id, te.project_id, te.start_time, te.end_time, te.duration, te.note, p.name
            FROM time_entries te
            LEFT JOIN projects p ON te.project_id = p.id
            WHERE te.end_time IS NULL
            ORDER BY te.id DESC LIMIT 1
            """
        )
        row = cur.fetchone()
        return TimeEntry.from_row(row) if row else None
    finally:
        conn.close()


def stop_all_active_entries(end_time: datetime) -> List[Tuple[int, int]]:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, start_time FROM time_entries WHERE end_time IS NULL"
        )
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
        conn.commit()
        return stopped
    finally:
        conn.close()


def get_time_entries(start_date: Optional[datetime] = None,
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


def get_entries_by_project(start_date: Optional[datetime] = None,
                           end_date: Optional[datetime] = None,
                           tag_name: Optional[str] = None) -> List[Tuple[Project, int, float]]:
    from .timer import merge_overlapping_intervals
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
            from .models import TimeEntry
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


# ─── 标签相关 ────────────────────────────────────────────────────

def get_or_create_tag(name: str) -> int:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT id FROM tags WHERE name = ?", (name,))
        row = cur.fetchone()
        if row:
            return row["id"]
        cur.execute("INSERT INTO tags (name) VALUES (?)", (name,))
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def add_tag_to_project(project_id: int, tag_name: str) -> bool:
    tag_id = get_or_create_tag(tag_name)
    conn = get_connection()
    try:
        cur = conn.cursor()
        try:
            cur.execute(
                "INSERT INTO project_tags (project_id, tag_id) VALUES (?, ?)",
                (project_id, tag_id),
            )
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False
    finally:
        conn.close()


def remove_tag_from_project(project_id: int, tag_name: str) -> bool:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT id FROM tags WHERE name = ?", (tag_name,))
        row = cur.fetchone()
        if not row:
            return False
        cur.execute(
            "DELETE FROM project_tags WHERE project_id = ? AND tag_id = ?",
            (project_id, row["id"]),
        )
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def get_project_tags(project_id: int) -> List[str]:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT t.name FROM tags t
            INNER JOIN project_tags pt ON t.id = pt.tag_id
            WHERE pt.project_id = ?
            ORDER BY t.name
            """,
            (project_id,),
        )
        return [row["name"] for row in cur.fetchall()]
    finally:
        conn.close()


def get_all_tags() -> List[str]:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT name FROM tags ORDER BY name")
        return [row["name"] for row in cur.fetchall()]
    finally:
        conn.close()


# ─── 预算相关 ────────────────────────────────────────────────────

def set_budget_hours(project_id: int, hours_limit: Optional[float]) -> bool:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT id FROM budgets WHERE project_id = ?", (project_id,))
        row = cur.fetchone()
        if row:
            cur.execute(
                "UPDATE budgets SET hours_limit = ? WHERE project_id = ?",
                (hours_limit, project_id),
            )
        else:
            cur.execute(
                "INSERT INTO budgets (project_id, hours_limit, cost_limit) VALUES (?, ?, NULL)",
                (project_id, hours_limit),
            )
        conn.commit()
        return True
    finally:
        conn.close()


def set_budget_cost(project_id: int, cost_limit: Optional[float]) -> bool:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT id FROM budgets WHERE project_id = ?", (project_id,))
        row = cur.fetchone()
        if row:
            cur.execute(
                "UPDATE budgets SET cost_limit = ? WHERE project_id = ?",
                (cost_limit, project_id),
            )
        else:
            cur.execute(
                "INSERT INTO budgets (project_id, hours_limit, cost_limit) VALUES (?, NULL, ?)",
                (project_id, cost_limit),
            )
        conn.commit()
        return True
    finally:
        conn.close()


def get_project_budget(project_id: int) -> Tuple[Optional[float], Optional[float]]:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT hours_limit, cost_limit FROM budgets WHERE project_id = ?",
                    (project_id,))
        row = cur.fetchone()
        if row:
            return row["hours_limit"], row["cost_limit"]
        return None, None
    finally:
        conn.close()


def get_project_total_usage(project_id: int) -> Tuple[int, float]:
    from .timer import merge_overlapping_intervals
    from .models import TimeEntry
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
        project = get_project_by_id(project_id)
        rate = project.rate if project else 0.0
        total_cost = (total_seconds / 3600.0) * rate
        return total_seconds, total_cost
    finally:
        conn.close()
