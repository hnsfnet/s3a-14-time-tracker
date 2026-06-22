from typing import Optional, Tuple

from ..database import get_connection


class BudgetRepository:
    """项目预算 CRUD"""

    def set_hours(self, project_id: int, hours_limit: Optional[float]) -> bool:
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

    def set_cost(self, project_id: int, cost_limit: Optional[float]) -> bool:
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

    def get(self, project_id: int) -> Tuple[Optional[float], Optional[float]]:
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
