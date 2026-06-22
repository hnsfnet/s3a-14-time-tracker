import json
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any

from . import db
from .models import Project, TimeEntry


def export_backup(output_path: Optional[str] = None) -> Optional[str]:
    """导出所有数据为 JSON 备份文件"""
    projects = db.get_all_projects()
    all_entries = db.get_time_entries()

    if not output_path:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"ttracker_backup_{timestamp}.json"
        output_path = str(Path.cwd() / filename)

    data = {
        "version": "1.0",
        "exported_at": datetime.now().isoformat(),
        "projects": [],
        "time_entries": [],
    }

    for p in projects:
        data["projects"].append({
            "id": p.id,
            "name": p.name,
            "description": p.description,
            "client": p.client,
            "rate": p.rate,
            "tags": p.tags,
            "budget_hours": p.budget_hours,
            "budget_cost": p.budget_cost,
        })

    for entry in all_entries:
        data["time_entries"].append({
            "id": entry.id,
            "project_id": entry.project_id,
            "project_name": entry.project_name,
            "start_time": entry.start_time.isoformat() if entry.start_time else None,
            "end_time": entry.end_time.isoformat() if entry.end_time else None,
            "duration": entry.duration,
            "note": entry.note,
        })

    try:
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return output_path
    except OSError:
        return None


def import_backup(backup_path: str) -> Optional[Dict[str, int]]:
    """从 JSON 备份文件恢复数据。返回导入统计或 None。"""
    try:
        with open(backup_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return None

    projects_data = data.get("projects", [])
    entries_data = data.get("time_entries", [])

    if not projects_data and not entries_data:
        return {"projects": 0, "time_entries": 0}

    conn = db.get_connection()
    try:
        cur = conn.cursor()

        cur.execute("DELETE FROM time_entries")
        cur.execute("DELETE FROM project_tags")
        cur.execute("DELETE FROM tags")
        cur.execute("DELETE FROM budgets")
        cur.execute("DELETE FROM projects")

        project_id_map: Dict[int, int] = {}

        for p_data in projects_data:
            old_id = p_data.get("id", 0)
            cur.execute(
                "INSERT INTO projects (name, description, client, rate) VALUES (?, ?, ?, ?)",
                (p_data.get("name", f"项目_{old_id}"),
                 p_data.get("description", ""),
                 p_data.get("client", ""),
                 p_data.get("rate", 0.0)),
            )
            new_id = cur.lastrowid
            project_id_map[old_id] = new_id

            tags = p_data.get("tags", [])
            for tag_name in tags:
                cur.execute("SELECT id FROM tags WHERE name = ?", (tag_name,))
                row = cur.fetchone()
                if row:
                    tag_id = row["id"]
                else:
                    cur.execute("INSERT INTO tags (name) VALUES (?)", (tag_name,))
                    tag_id = cur.lastrowid
                cur.execute(
                    "INSERT OR IGNORE INTO project_tags (project_id, tag_id) VALUES (?, ?)",
                    (new_id, tag_id),
                )

            budget_hours = p_data.get("budget_hours")
            budget_cost = p_data.get("budget_cost")
            if budget_hours is not None or budget_cost is not None:
                cur.execute(
                    "INSERT INTO budgets (project_id, hours_limit, cost_limit) VALUES (?, ?, ?)",
                    (new_id, budget_hours, budget_cost),
                )

        entry_count = 0
        for e_data in entries_data:
            old_proj_id = e_data.get("project_id", 0)
            new_proj_id = project_id_map.get(old_proj_id)
            if new_proj_id is None:
                continue

            start_time = e_data.get("start_time")
            end_time = e_data.get("end_time")
            duration = e_data.get("duration", 0)
            note = e_data.get("note", "")

            if end_time:
                cur.execute(
                    """
                    INSERT INTO time_entries (project_id, start_time, end_time, duration, note)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (new_proj_id, start_time, end_time, duration, note),
                )
            else:
                cur.execute(
                    """
                    INSERT INTO time_entries (project_id, start_time, duration, note)
                    VALUES (?, ?, 0, ?)
                    """,
                    (new_proj_id, start_time, note),
                )
            entry_count += 1

        conn.commit()
        return {
            "projects": len(project_id_map),
            "time_entries": entry_count,
        }
    except Exception:
        conn.rollback()
        return None
    finally:
        conn.close()
