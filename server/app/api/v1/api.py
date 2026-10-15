from fastapi import APIRouter

from app.api.v1.endpoints import databases, health, runs

api_router = APIRouter()
api_router.include_router(health.router, prefix="/health", tags=["health"])
api_router.include_router(databases.router, prefix="/databases", tags=["databases"])
api_router.include_router(runs.router, prefix="/runs", tags=["runs"])
