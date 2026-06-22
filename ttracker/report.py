from typing import Optional, Tuple
from datetime import datetime

from .reports.report_generator import ReportGenerator
from .reports.report_formatter import ReportFormatter

_generator = ReportGenerator()
_formatter = ReportFormatter()


def get_date_range(period: str, value: Optional[str] = None) -> Tuple[datetime, datetime, str]:
    return _generator.get_date_range(period, value)


def print_log_entries(period: str = "today", month: Optional[str] = None,
                      project_name: Optional[str] = None,
                      tag_name: Optional[str] = None) -> None:
    data = _generator.generate_log_entries_data(period, month, project_name, tag_name)
    _formatter.print_log_entries(data)


def print_report(period: str = "week", month: Optional[str] = None,
                 tag_name: Optional[str] = None) -> None:
    data = _generator.generate_report_data(period, month, tag_name)
    _formatter.print_report(data)


def print_daily_report() -> None:
    data = _generator.generate_daily_data()
    _formatter.print_daily_report(data)


def print_weekly_report() -> None:
    data = _generator.generate_weekly_data()
    _formatter.print_weekly_report(data)


def export_csv(period: str = "all", month: Optional[str] = None,
               project_name: Optional[str] = None, output_path: Optional[str] = None,
               tag_name: Optional[str] = None) -> Optional[str]:
    data = _generator.generate_csv_data(period, month, project_name, tag_name)
    return _formatter.export_csv(data, output_path)


def export_markdown(period: str = "week", month: Optional[str] = None,
                    project_name: Optional[str] = None,
                    tag_name: Optional[str] = None,
                    output_path: Optional[str] = None) -> Optional[str]:
    data = _generator.generate_markdown_data(period, month, project_name, tag_name)
    return _formatter.export_markdown(data, output_path)
