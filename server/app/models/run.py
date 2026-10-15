import enum

from sqlalchemy import JSON, Column, DateTime, Enum, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import relationship

from app.core.database import Base


class RunStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class RecommendationStatus(str, enum.Enum):
    PROPOSED = "proposed"
    APPROVED = "approved"
    REJECTED = "rejected"
    APPLIED = "applied"


class Run(Base):
    """One agent run over a target database."""

    __tablename__ = "runs"

    id = Column(Integer, primary_key=True, index=True)
    database = Column(String, nullable=False)
    status = Column(Enum(RunStatus), nullable=False, default=RunStatus.PENDING)
    error = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    finished_at = Column(DateTime(timezone=True))

    steps = relationship("RunStep", back_populates="run", cascade="all, delete-orphan", order_by="RunStep.id")
    recommendations = relationship("Recommendation", back_populates="run", cascade="all, delete-orphan")


class RunStep(Base):
    """One agent action (inspect_plan, diagnose, ...), streamed to the UI and kept for the audit log."""

    __tablename__ = "run_steps"

    id = Column(Integer, primary_key=True, index=True)
    run_id = Column(Integer, ForeignKey("runs.id", ondelete="CASCADE"), nullable=False, index=True)
    node = Column(String, nullable=False)
    message = Column(Text, nullable=False)
    payload = Column(JSON)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    run = relationship("Run", back_populates="steps")


class Recommendation(Base):
    """A verified fix for one slow query, waiting for human approval."""

    __tablename__ = "recommendations"

    id = Column(Integer, primary_key=True, index=True)
    run_id = Column(Integer, ForeignKey("runs.id", ondelete="CASCADE"), nullable=False, index=True)
    queryid = Column(String, nullable=False)
    original_sql = Column(Text, nullable=False)
    fix_type = Column(String, nullable=False)  # index | rewrite | analyze
    fix_sql = Column(Text, nullable=False)
    explanation = Column(Text)
    baseline_ms = Column(Float)
    new_ms = Column(Float)
    status = Column(Enum(RecommendationStatus), nullable=False, default=RecommendationStatus.PROPOSED)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    run = relationship("Run", back_populates="recommendations")
