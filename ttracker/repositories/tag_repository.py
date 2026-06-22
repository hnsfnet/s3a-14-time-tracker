import sqlite3
from typing import List

from ..database import get_connection


class TagRepository:
    """标签 CRUD + 项目标签关联"""

    def _get_or_create(self, name: str) -> int:
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

    def add_to_project(self, project_id: int, tag_name: str) -> bool:
        tag_id = self._get_or_create(tag_name)
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

    def remove_from_project(self, project_id: int, tag_name: str) -> bool:
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

    def get_for_project(self, project_id: int) -> List[str]:
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

    def get_all(self) -> List[str]:
        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT name FROM tags ORDER BY name")
            return [row["name"] for row in cur.fetchall()]
        finally:
            conn.close()
