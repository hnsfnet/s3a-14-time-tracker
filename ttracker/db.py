import os
import sqlite3
from pathlib import Path
from typing import List, Optional, Tuple
from datetime import datetime, timedelta

from .models import Project, TimeEntry


def get_db_path() -> Path:
    home = Path.home()
    db_dir = home / ".ttracker"
    db_dir.mkdir(parents=True, exist_ok=True)
    return db_dir / "data.db"


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(str(get_db_path()))
    conn.row_factory = sqlite3.Row
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
        cur.execute("DELETE FROM projects WHERE id = ?", (project_id,))
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def get_all_projects() -> List[Project]:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT id, name, description, client, rate FROM projects ORDER BY id")
        rows = cur.fetchall()
        return [Project.from_row(row) for row in rows]
    finally:
        conn.close()


def get_project_by_id(project_id: int) -> Optional[Project]:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT id, name, description, client, rate FROM projects WHERE id = ?",
                    (project_id,))
        row = cur.fetchone()
        return Project.from_row(row) if row else None
    finally:
        conn.close()


def get_project_by_name(name: str) -> Optional[Project]:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT id, name, description, client, rate FROM projects WHERE name = ?",
                    (name,))
        row = cur.fetchone()
        return Project.from_row(row) if row else None
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
                     project_name: Optional[str] = None) -> List[TimeEntry]:
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
        query += " ORDER BY te.start_time ASC"
        cur.execute(query, params)
        rows = cur.fetchall()
        return [TimeEntry.from_row(row) for row in rows]
    finally:
        conn.close()


def get_entries_by_project(start_date: Optional[datetime] = None,
                           end_date: Optional[datetime] = None) -> List[Tuple[Project, int, float]]:
    conn = get_connection()
    try:
        cur = conn.cursor()
        query = """
            SELECT p.id, p.name, p.description, p.client, p.rate,
                   SUM(te.duration) as total_duration
            FROM projects p
            LEFT JOIN time_entries te ON p.id = te.project_id
            WHERE te.end_time IS NOT NULL
        """
        params = []
        if start_date:
            query += " AND te.start_time >= ?"
            params.append(start_date.isoformat())
        if end_date:
            query += " AND te.start_time < ?"
            params.append(end_date.isoformat())
        query += " GROUP BY p.id, p.name, p.description, p.client, p.rate ORDER BY total_duration DESC"
        cur.execute(query, params)
        rows = cur.fetchall()
        results = []
        for row in rows:
            project = Project(row[0], row[1], row[2] or "", row[3] or "", row[4] or 0.0)
            duration = row[5] or 0
            cost = (duration / 3600.0) * project.rate
            results.append((project, duration, cost))
        return results
    finally:
        conn.close()
