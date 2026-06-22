import re
from datetime import datetime, timedelta
from typing import Optional, Tuple


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


def start_timer(project_name: str) -> Tuple[bool, str, Optional[object], Optional[Tuple[int, int]]]:
    from .services import TimerService
    return TimerService().start_timer(project_name)


def stop_timer(note: str = "") -> Tuple[bool, str, Optional[object], Optional[int]]:
    from .services import TimerService
    return TimerService().stop_timer(note)


def get_timer_status() -> Tuple[bool, str, Optional[object], Optional[int], Optional[datetime]]:
    from .services import TimerService
    return TimerService().get_timer_status()


def manual_log(project_name: str, duration_str: str, note: str = "",
               start_time: Optional[datetime] = None) -> Tuple[bool, str, Optional[object], Optional[int]]:
    from .services import TimerService
    return TimerService().manual_log(project_name, duration_str, note, start_time)
