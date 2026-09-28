from sqlmodel import Field,SQLModel
from datetime import datetime

class RepositoryRepresentation(SQLModel):
    id: int = Field(default=None, primary_key=True)
    name: str = Field(default=None, validation_alias="name")
    url: str = Field(default=None, validation_alias="url")
    status: str = Field(default=None, validation_alias="status")
    created_at: datetime | None = Field(default=None, validation_alias="created_at")
    # How much of the repository is actually searchable. A repository can be
    # `completed` while holding nothing, so the count is what a caller should
    # use to decide whether it is worth opening.
    chunk_count: int = Field(default=0, validation_alias="chunk_count")
