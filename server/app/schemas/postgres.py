from typing import Dict, Optional

from pydantic import BaseModel


class ServerHealth(BaseModel):
    ok: bool
    version: Optional[str] = None
    error: Optional[str] = None


class Health(BaseModel):
    app_db: ServerHealth
    target: ServerHealth
    throwaway: ServerHealth


class Database(BaseModel):
    name: str
    size_bytes: int
    extensions: Dict[str, str] = {}


class SlowQuery(BaseModel):
    queryid: str
    query: str
    calls: int
    total_time_ms: float
    mean_time_ms: float
    rows: int
    shared_blks_hit: int
    shared_blks_read: int
