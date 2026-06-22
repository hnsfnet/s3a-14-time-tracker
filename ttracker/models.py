from dataclasses import dataclass, field
from typing import Optional, List
from datetime import datetime


@dataclass
class Tag:
    id: Optional[int]
    name: str

    @classmethod
    def from_row(cls, row):
        return cls(
            id=row[0],
            name=row[1],
        )


@dataclass
class Budget:
    id: Optional[int]
    project_id: int
    budget_type: str  # 'hours' or 'cost'
    limit: float

    @classmethod
    def from_row(cls, row):
        return cls(
            id=row[0],
            project_id=row[1],
            budget_type=row[2],
            limit=row[3],
        )


@dataclass
class Project:
    id: Optional[int]
    name: str
    description: str
    client: str
    rate: float
    tags: List[str] = field(default_factory=list)
    budget_hours: Optional[float] = None
    budget_cost: Optional[float] = None

    @classmethod
    def from_row(cls, row):
        return cls(
            id=row[0],
            name=row[1],
            description=row[2] or "",
            client=row[3] or "",
            rate=row[4] or 0.0,
        )


@dataclass
class TimeEntry:
    id: Optional[int]
    project_id: int
    start_time: datetime
    end_time: Optional[datetime]
    duration: int
    note: str
    project_name: Optional[str] = None

    @classmethod
    def from_row(cls, row):
        end_time = datetime.fromisoformat(row[3]) if row[3] else None
        return cls(
            id=row[0],
            project_id=row[1],
            start_time=datetime.fromisoformat(row[2]),
            end_time=end_time,
            duration=row[4] or 0,
            note=row[5] or "",
            project_name=row[6] if len(row) > 6 else None,
        )
