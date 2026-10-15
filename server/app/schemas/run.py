from datetime import datetime
from typing import Any, List, Optional

from pydantic import BaseModel

from app.models.run import RecommendationStatus, RunStatus


class RunCreate(BaseModel):
    database: str


class RunStep(BaseModel):
    id: int
    node: str
    message: str
    payload: Optional[Any] = None
    created_at: datetime

    class Config:
        from_attributes = True


class Recommendation(BaseModel):
    id: int
    queryid: str
    original_sql: str
    fix_type: str
    fix_sql: str
    explanation: Optional[str] = None
    baseline_ms: Optional[float] = None
    new_ms: Optional[float] = None
    status: RecommendationStatus
    created_at: datetime

    class Config:
        from_attributes = True


class Run(BaseModel):
    id: int
    database: str
    status: RunStatus
    error: Optional[str] = None
    created_at: datetime
    finished_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class RunDetail(Run):
    steps: List[RunStep] = []
    recommendations: List[Recommendation] = []
