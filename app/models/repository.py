from sqlmodel import Field, SQLModel
from enum import Enum
from datetime import datetime
import pytz

class RepositoryStatus(str, Enum):
    pending = "pending"
    processing = "processing"
    completed = "completed"
    failed = "failed"

class RepositoryBase(SQLModel):
    id: int = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(pytz.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(pytz.utc))

class Repository(RepositoryBase, table=True):
    __tablename__ = "repositories"

    id: int|None = Field(default=None, primary_key=True)
    name: str|None = Field(default=None)
    url: str|None = Field(default=None)
    status: RepositoryStatus|None = Field(default=None)
    # Drives idle expiry. Deliberately separate from `updated_at`, which tracks
    # indexing state and would make a half-finished run look "recently used".
    # Indexed because the sweeper filters on it.
    last_accessed_at: datetime = Field(
        default_factory=lambda: datetime.now(pytz.utc),
        index=True,
    )

