# Import all models here so Alembic can detect them during autogenerate.
# This also ensures they are registered on Base.metadata.
from app.models.run import Recommendation, Run, RunStep  # noqa: F401
