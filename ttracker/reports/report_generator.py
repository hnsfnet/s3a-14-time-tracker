from datetime import datetime, timedelta
from typing import List, Optional, Tuple, Dict, Any
from collections import defaultdict

from .. import db
from ..models import Project, TimeEntry
from ..timer import merge_overlapping_intervals


class ReportGenerator:

    def get_date_range(self, period: str, value: Optional[str] = None) -> Tuple[datetime, datetime, str]:
        now = datetime.now()

        if period == "today" or period == "daily":
            start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            end = start + timedelta(days=1)
            desc = f"{start.strftime('%Y年%m月%d日')} 今日"
        elif period == "week":
            start = now - timedelta(days=now.weekday())
            start = start.replace(hour=0, minute=0, second=0, microsecond=0)
            end = start + timedelta(days=7)
            desc = f"{start.strftime('%Y年%m月%d日')} 起 本周"
        elif period == "weekly":
            start = now - timedelta(days=now.weekday())
            start = start.replace(hour=0, minute=0, second=0, microsecond=0)
            end = start + timedelta(days=7)
            desc = f"{start.strftime('%Y年%m月%d日')} 起 本周"
        elif period == "month":
            if value:
                try:
                    year, month = map(int, value.split("-"))
                    start = datetime(year, month, 1)
                except (ValueError, AttributeError):
                    raise ValueError(f"月份格式错误: {value}，请使用 YYYY-MM 格式")
            else:
                start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            if start.month == 12:
                end = datetime(start.year + 1, 1, 1)
            else:
                end = datetime(start.year, start.month + 1, 1)
            desc = f"{start.strftime('%Y年%m月')} 月度"
        elif period == "all":
            start = datetime(2000, 1, 1)
            end = datetime(2099, 12, 31)
            desc = "全部记录"
        else:
            raise ValueError(f"未知的周期: {period}")

        return start, end, desc

    def generate_log_entries_data(self, period: str = "today", month: Optional[str] = None,
                                   project_name: Optional[str] = None,
                                   tag_name: Optional[str] = None) -> Dict[str, Any]:
        error = None
        try:
            start, end, desc = self.get_date_range(period, month)
        except ValueError as e:
            error = str(e)
            return {"error": error}

        entries: List[TimeEntry] = []
        if project_name:
            project = db.get_project_by_name(project_name)
            if not project:
                return {"error": f"项目 '{project_name}' 不存在"}
            entries = db.get_time_entries(project_id=project.id, tag_name=tag_name)
            desc = f"项目 '{project_name}' 全部记录"
        elif tag_name and period == "all":
            entries = db.get_time_entries(tag_name=tag_name)
            desc = f"标签 '{tag_name}' 全部记录"
        else:
            entries = db.get_time_entries(start, end, tag_name=tag_name)
            if tag_name:
                desc += f" (标签: {tag_name})"

        if not entries:
            return {"empty": True, "desc": desc}

        total_duration = merge_overlapping_intervals(entries)
        total_cost = 0.0
        unique_projects = set()

        for entry in entries:
            project = db.get_project_by_id(entry.project_id)
            if project and project.id not in unique_projects:
                unique_projects.add(project.id)

        for pid in unique_projects:
            project = db.get_project_by_id(pid)
            if not project:
                continue
            p_entries = [e for e in entries if e.project_id == pid]
            p_duration = merge_overlapping_intervals(p_entries)
            total_cost += (p_duration / 3600.0) * project.rate

        entry_rows = []
        for entry in entries:
            start_str = entry.start_time.strftime("%Y-%m-%d %H:%M")
            end_str = entry.end_time.strftime("%H:%M") if entry.end_time else "-"
            project_display = entry.project_name or f"#{entry.project_id}"
            entry_rows.append({
                "start_str": start_str,
                "end_str": end_str,
                "duration": entry.duration,
                "project_display": project_display,
                "note": entry.note or "-",
            })

        return {
            "empty": False,
            "desc": desc,
            "entries": entries,
            "entry_rows": entry_rows,
            "total_duration": total_duration,
            "total_cost": total_cost,
        }

    def generate_report_data(self, period: str = "week", month: Optional[str] = None,
                             tag_name: Optional[str] = None) -> Dict[str, Any]:
        error = None
        try:
            start, end, desc = self.get_date_range(period, month)
        except ValueError as e:
            error = str(e)
            return {"error": error}

        results = db.get_entries_by_project(start, end, tag_name)

        if not results:
            return {"empty": True, "desc": desc}

        if tag_name:
            desc += f" (标签: {tag_name})"

        project_rows = []
        total_duration = 0
        total_cost = 0.0
        max_duration = 0

        for project, duration, cost in results:
            hours = duration / 3600.0

            h_pct = None
            h_bar_ratio = None
            if project.budget_hours:
                h_pct = (hours / project.budget_hours) * 100
                h_bar_ratio = min(hours / project.budget_hours, 1.0)

            c_pct = None
            c_bar_ratio = None
            if project.budget_cost:
                c_pct = (cost / project.budget_cost) * 100
                c_bar_ratio = min(cost / project.budget_cost, 1.0)

            project_rows.append({
                "project": project,
                "duration": duration,
                "cost": cost,
                "hours": hours,
                "h_pct": h_pct,
                "h_bar_ratio": h_bar_ratio,
                "c_pct": c_pct,
                "c_bar_ratio": c_bar_ratio,
            })
            total_duration += duration
            total_cost += cost
            if duration > max_duration:
                max_duration = duration

        bar_rows = []
        MAX_BAR_WIDTH = 40
        for project, duration, cost in results:
            if max_duration > 0:
                ratio = duration / max_duration
            else:
                ratio = 0
            filled = int(MAX_BAR_WIDTH * ratio)
            bar_rows.append({
                "project_name": project.name,
                "duration": duration,
                "filled": filled,
                "max_bar_width": MAX_BAR_WIDTH,
            })

        return {
            "empty": False,
            "desc": desc,
            "project_rows": project_rows,
            "total_duration": total_duration,
            "total_cost": total_cost,
            "max_duration": max_duration,
            "bar_rows": bar_rows,
            "project_count": len(results),
        }

    def generate_daily_data(self) -> Dict[str, Any]:
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        tomorrow = today + timedelta(days=1)
        date_str = today.strftime("%Y年%m月%d日 %A")

        entries = db.get_time_entries(today, tomorrow)
        if not entries:
            return {"empty": True, "date_str": date_str}

        by_project: Dict[str, List[TimeEntry]] = defaultdict(list)
        for entry in entries:
            name = entry.project_name or f"#{entry.project_id}"
            by_project[name].append(entry)

        project_sections = []
        total_duration = 0
        total_cost = 0.0

        for proj_name, items in sorted(by_project.items(),
                                       key=lambda x: sum(e.duration for e in x[1]), reverse=True):
            proj_total = merge_overlapping_intervals(items)
            project = db.get_project_by_name(proj_name)
            proj_cost = (proj_total / 3600.0) * (project.rate if project else 0)

            rows = []
            for e in sorted(items, key=lambda x: x.start_time):
                time_range = e.start_time.strftime("%H:%M") + "-" + (e.end_time.strftime("%H:%M") if e.end_time else "")
                rows.append({
                    "time_range": time_range,
                    "duration": e.duration,
                    "note": e.note or "(无备注)",
                })

            project_sections.append({
                "proj_name": proj_name,
                "proj_total": proj_total,
                "proj_cost": proj_cost,
                "client": project.client if project else None,
                "rows": rows,
            })
            total_duration += proj_total
            total_cost += proj_cost

        return {
            "empty": False,
            "date_str": date_str,
            "project_sections": project_sections,
            "project_count": len(by_project),
            "total_duration": total_duration,
            "total_cost": total_cost,
        }

    def generate_weekly_data(self) -> Dict[str, Any]:
        now = datetime.now()
        week_start = now - timedelta(days=now.weekday())
        week_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)
        week_end = week_start + timedelta(days=7)
        week_start_str = week_start.strftime("%Y年%m月%d日")

        entries = db.get_time_entries(week_start, week_end)
        if not entries:
            return {"empty": True, "week_start_str": week_start_str}

        by_day: Dict[str, Dict[str, List[TimeEntry]]] = defaultdict(lambda: defaultdict(list))
        for entry in entries:
            day_key = entry.start_time.strftime("%Y-%m-%d %A")
            name = entry.project_name or f"#{entry.project_id}"
            by_day[day_key][name].append(entry)

        day_sections = []
        week_total_duration = 0
        week_total_cost = 0.0

        for day_key in sorted(by_day.keys()):
            projects = by_day[day_key]
            day_entries_all = []
            for items in projects.values():
                day_entries_all.extend(items)
            day_total = merge_overlapping_intervals(day_entries_all)
            week_total_duration += day_total

            day_cost = 0.0
            proj_rows = []
            for proj_name, items in sorted(projects.items(),
                                           key=lambda x: sum(e.duration for e in x[1]), reverse=True):
                proj_total = merge_overlapping_intervals(items)
                notes = [e.note for e in items if e.note]
                notes_str = "; ".join(notes) if notes else "(无备注)"
                project = db.get_project_by_name(proj_name)
                proj_cost = (proj_total / 3600.0) * (project.rate if project else 0)
                day_cost += proj_cost

                proj_rows.append({
                    "proj_name": proj_name,
                    "duration": proj_total,
                    "notes_str": notes_str[:60] + "..." if len(notes_str) > 60 else notes_str,
                })

            week_total_cost += day_cost
            day_sections.append({
                "day_key": day_key,
                "day_total": day_total,
                "day_cost": day_cost,
                "proj_rows": proj_rows,
            })

        return {
            "empty": False,
            "week_start_str": week_start_str,
            "day_sections": day_sections,
            "work_days": len(by_day),
            "week_total_duration": week_total_duration,
            "week_total_cost": week_total_cost,
        }

    def generate_csv_data(self, period: str = "all", month: Optional[str] = None,
                          project_name: Optional[str] = None,
                          tag_name: Optional[str] = None) -> Dict[str, Any]:
        error = None
        try:
            start, end, desc = self.get_date_range(period, month)
        except ValueError as e:
            error = str(e)
            return {"error": error}

        if project_name:
            project = db.get_project_by_name(project_name)
            if not project:
                return {"error": f"项目 '{project_name}' 不存在"}
            entries = db.get_time_entries(project_id=project.id, tag_name=tag_name)
        else:
            entries = db.get_time_entries(start, end, tag_name=tag_name)

        if not entries:
            return {"empty": True}

        total_duration = merge_overlapping_intervals(entries)
        unique_projects_in_csv = set(e.project_id for e in entries)
        total_cost = 0.0
        for pid in unique_projects_in_csv:
            project = db.get_project_by_id(pid)
            if not project:
                continue
            p_entries = [e for e in entries if e.project_id == pid]
            p_dur = merge_overlapping_intervals(p_entries)
            total_cost += (p_dur / 3600.0) * project.rate

        csv_rows = []
        for entry in entries:
            project = db.get_project_by_id(entry.project_id)
            project_name_out = project.name if project else ""
            client = project.client if project else ""
            rate = project.rate if project else 0.0
            tags = ",".join(project.tags) if project else ""
            duration_hours = entry.duration / 3600.0
            cost = duration_hours * rate

            csv_rows.append({
                "start_time": entry.start_time.strftime("%Y-%m-%d %H:%M:%S"),
                "end_time": entry.end_time.strftime("%Y-%m-%d %H:%M:%S") if entry.end_time else "",
                "duration_seconds": entry.duration,
                "duration_hours": round(duration_hours, 4),
                "project_id": entry.project_id,
                "project_name": project_name_out,
                "client": client,
                "rate": rate,
                "cost": round(cost, 2),
                "note": entry.note or "",
                "tags": tags,
            })

        return {
            "empty": False,
            "csv_rows": csv_rows,
            "total_duration": total_duration,
            "total_cost": round(total_cost, 2),
        }

    def generate_markdown_data(self, period: str = "week", month: Optional[str] = None,
                               project_name: Optional[str] = None,
                               tag_name: Optional[str] = None) -> Dict[str, Any]:
        error = None
        try:
            start, end, desc = self.get_date_range(period, month)
        except ValueError as e:
            error = str(e)
            return {"error": error}

        if project_name:
            project = db.get_project_by_name(project_name)
            if not project:
                return {"error": f"项目 '{project_name}' 不存在"}
            entries = db.get_time_entries(project_id=project.id, tag_name=tag_name)
        else:
            entries = db.get_time_entries(start, end, tag_name=tag_name)

        if not entries:
            return {"empty": True}

        if tag_name:
            desc += f" (标签: {tag_name})"

        by_project: Dict[str, List[TimeEntry]] = defaultdict(list)
        for entry in entries:
            name = entry.project_name or f"#{entry.project_id}"
            by_project[name].append(entry)

        project_sections = []
        total_duration = 0
        total_cost = 0.0

        for proj_name, items in sorted(by_project.items(),
                                       key=lambda x: sum(e.duration for e in x[1]), reverse=True):
            proj_total = merge_overlapping_intervals(items)
            project = db.get_project_by_name(proj_name)
            proj_cost = (proj_total / 3600.0) * (project.rate if project else 0)
            total_duration += proj_total
            total_cost += proj_cost

            entry_rows = []
            for e in sorted(items, key=lambda x: x.start_time):
                start_s = e.start_time.strftime("%Y-%m-%d %H:%M")
                end_s = e.end_time.strftime("%H:%M") if e.end_time else "-"
                entry_rows.append({
                    "start_s": start_s,
                    "end_s": end_s,
                    "duration": e.duration,
                    "note": e.note or "",
                })

            project_sections.append({
                "proj_name": proj_name,
                "client": project.client if project else None,
                "rate": project.rate if project else 0,
                "tags": project.tags if project else [],
                "proj_total": proj_total,
                "proj_cost": proj_cost,
                "entry_rows": entry_rows,
            })

        return {
            "empty": False,
            "desc": desc,
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "project_sections": project_sections,
            "project_count": len(by_project),
            "total_duration": total_duration,
            "total_cost": total_cost,
        }
