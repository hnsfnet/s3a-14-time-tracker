"""数据库连接与初始化（原 db.py 的基础设施层抽离）"""
import sqlite3
from pathlib import Path
from typing import Callable, TypeVar, Any

from .models import Project, TimeEntry, Tag, Budget

T = TypeVar("T")


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


def with_connection(fn: Callable[[sqlite3.Connection], T]) -> T:
    """上下文管理器风格的连接辅助函数"""
    conn = get_connection()
    try:
        result = fn(conn)
        conn.commit()
        return result
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    """初始化所有表结构（含 timer_state 新表）"""
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
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS timer_state (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                is_active INTEGER NOT NULL DEFAULT 0,
                active_entry_id INTEGER,
                FOREIGN KEY (active_entry_id) REFERENCES time_entries (id) ON DELETE SET NULL
            )
            """
        )
        cur.execute("SELECT COUNT(*) FROM timer_state")
        if cur.fetchone()[0] == 0:
            cur.execute("INSERT INTO timer_state (id, is_active, active_entry_id) VALUES (1, 0, NULL)")
        conn.commit()
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
