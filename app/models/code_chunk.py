from sqlmodel import SQLModel, Field
from sqlalchemy import Column
from pgvector.sqlalchemy import Vector


class CodeChunk(SQLModel, table=True):
    __tablename__ = "code_chunks"

    id: int | None = Field(default=None, primary_key=True)

    # CASCADE matters: this column had no constraint, so deleting a repository
    # used to orphan every one of its chunks permanently. Nothing can now remove
    # a repository row without taking its chunks with it.
    repository_id: int = Field(
        index=True,
        foreign_key="repositories.id",
        ondelete="CASCADE",
    )

    file_path: str
    file_name: str
    language: str

    chunk_index: int
    content: str

    start_line: int
    end_line: int

    embedding: list[float] = Field(
        sa_column=Column(Vector(384))
    )