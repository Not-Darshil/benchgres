from typing import Any, List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import deps
from app.models.run import Run as RunModel
from app.schemas.run import Run, RunCreate, RunDetail

router = APIRouter()


@router.get("/", response_model=List[Run])
def read_runs(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(deps.get_db),
) -> Any:
    """
    Retrieve runs, newest first.
    """
    return db.query(RunModel).order_by(RunModel.id.desc()).offset(skip).limit(limit).all()


@router.post("/", response_model=Run)
def create_run(
    *,
    db: Session = Depends(deps.get_db),
    run_in: RunCreate,
) -> Any:
    """
    Create a new run. The agent that executes it is added in Phase 2.
    """
    run = RunModel(database=run_in.database)
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


@router.get("/{run_id}", response_model=RunDetail)
def read_run(
    run_id: int,
    db: Session = Depends(deps.get_db),
) -> Any:
    """
    Get a run with its steps and recommendations.
    """
    run = db.get(RunModel, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return run
