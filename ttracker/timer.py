import re
from datetime import datetime, timedelta
from typing import Optional, Tuple

from . import db


def parse_duration(duration_str: str) -> int:
    """
    解析时长字符串为秒数。支持格式：
    - 2h  -> 2小时
    - 30m -> 30分钟
    - 1h30m -> 1小时30分钟
    - 45s -> 45秒
    - 1.5h -> 1.5小时
    - 90m -> 90分钟
    """
    if duration_str is None:
        raise ValueError("时长不能为空")
    duration_str = duration_str.strip().lower()
    if not duration_str:
        raise ValueError("时长不能为空")

    total_seconds = 0
    pattern = r'(\d+(?:\.\d+)?)\s*([hms])'
    matches = re.findall(pattern, duration_str)

    if not matches:
        raise ValueError(
            f"无法解析时长: '{duration_str}'。\n"
            f"支持的格式示例：\n"
            f"  2h        -> 2小时\n"
            f"  45m       -> 45分钟\n"
            f"  1h30m     -> 1小时30分钟\n"
            f"  1.5h      -> 1.5小时 (90分钟)\n"
            f"  90m       -> 90分钟"
        )

    matched_chars = 0
    for value, unit in matches:
        matched_chars += len(value) + len(unit)
        value = float(value)
        if unit == 'h':
            total_seconds += int(value * 3600)
        elif unit == 'm':
            total_seconds += int(value * 60)
        elif unit == 's':
            total_seconds += int(value)

    if total_seconds <= 0:
        raise ValueError("时长必须大于 0")

    return total_seconds


def format_duration(seconds: int) -> str:
    """将秒数格式化为易读字符串"""
    if seconds < 0:
        seconds = 0
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60

    parts = []
    if hours > 0:
        parts.append(f"{hours}小时")
    if minutes > 0:
        parts.append(f"{minutes}分钟")
    if secs > 0 and hours == 0:
        parts.append(f"{secs}秒")

    return "".join(parts) if parts else "0秒"


def format_duration_short(seconds: int) -> str:
    """将秒数格式化为短格式字符串，如 2h30m"""
    if seconds < 0:
        seconds = 0
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60

    if hours > 0 and minutes > 0:
        return f"{hours}h{minutes}m"
    elif hours > 0:
        return f"{hours}h"
    else:
        return f"{minutes}m"


def format_money(amount: float) -> str:
    """格式化金额"""
    return f"¥{amount:.2f}"


def start_timer(project_name: str) -> Tuple[bool, str, Optional[object], Optional[Tuple[int, int]]]:
    """
    开始计时。如果已有正在进行的计时，先自动停止。
    返回: (是否成功, 消息, 新项目对象, (被停止的记录ID, 时长秒数) 或 None)
    """
    project = db.get_project_by_name(project_name)
    if not project:
        return False, f"项目 '{project_name}' 不存在", None, None

    now = datetime.now()
    stopped_info = None

    active = db.get_active_entry()
    if active:
        if active.project_id == project.id:
            return False, f"项目 '{project_name}' 已经在计时中", project, None

        old_start = active.start_time
        duration = int((now - old_start).total_seconds())
        db.stop_active_entry(active.id, now, duration)
        stopped_info = (active.id, duration)

    db.start_active_entry(project.id, now)
    return True, f"开始计时项目 '{project_name}'", project, stopped_info


def stop_timer(note: str = "") -> Tuple[bool, str, Optional[object], Optional[int]]:
    """
    停止计时。
    返回: (是否成功, 消息, 项目对象, 时长秒数)
    """
    active = db.get_active_entry()
    if not active:
        return False, "当前没有正在进行的计时", None, None

    now = datetime.now()
    duration = int((now - active.start_time).total_seconds())
    db.stop_active_entry(active.id, now, duration, note)

    project = db.get_project_by_id(active.project_id)
    return True, "计时已停止", project, duration


def get_timer_status() -> Tuple[bool, str, Optional[object], Optional[int], Optional[datetime]]:
    """
    获取当前计时状态。
    返回: (是否正在计时, 消息, 项目对象, 已计时秒数, 开始时间)
    """
    active = db.get_active_entry()
    if not active:
        return False, "当前没有正在进行的计时", None, None, None

    now = datetime.now()
    duration = int((now - active.start_time).total_seconds())
    project = db.get_project_by_id(active.project_id)
    return True, "计时中", project, duration, active.start_time


def manual_log(project_name: str, duration_str: str, note: str = "",
               start_time: Optional[datetime] = None) -> Tuple[bool, str, Optional[object], Optional[int]]:
    """
    手动补录时长。
    返回: (是否成功, 消息, 项目对象, 时长秒数)
    """
    project = db.get_project_by_name(project_name)
    if not project:
        return False, f"项目 '{project_name}' 不存在", None, None

    try:
        duration = parse_duration(duration_str)
    except ValueError as e:
        return False, str(e), None, None

    now = start_time or datetime.now()
    end_time = now
    start = now - timedelta(seconds=duration)

    db.add_time_entry(project.id, start, end_time, duration, note)
    return True, "已补录时长", project, duration


def merge_overlapping_intervals(entries) -> int:
    """
    合并一组时间段，去除重叠/包含的部分，返回实际覆盖的总秒数。
    entries: 任意包含 start_time 和 end_time 属性的对象列表
    """
    if not entries:
        return 0
    intervals = []
    for e in entries:
        if e.end_time and e.start_time:
            intervals.append((e.start_time, e.end_time))
    if not intervals:
        return 0

    intervals.sort(key=lambda x: x[0])
    merged = [intervals[0]]
    for start, end in intervals[1:]:
        last_start, last_end = merged[-1]
        if start <= last_end:
            new_end = last_end if last_end > end else end
            merged[-1] = (last_start, new_end)
        else:
            merged.append((start, end))

    total = 0
    for start, end in merged:
        total += int((end - start).total_seconds())
    return total if total > 0 else 0
