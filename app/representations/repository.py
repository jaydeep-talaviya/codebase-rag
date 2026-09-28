from sqlmodel import Field,SQLModel
from datetime import datetime

class RepositoryRepresentation(SQLModel):
    id: int = Field(default=None, primary_key=True)
    name: str = Field(default=None, validation_alias="name")
    url: str = Field(default=None, validation_alias="url")
    status: str = Field(default=None, validation_alias="status")
    created_at: datetime | None = Field(default=None, validation_alias="created_at")
    # When this repository was last indexed, previewed, or searched. The expiry
    # below is derived from it, so the UI never has to know the TTL itself.
    last_accessed_at: datetime | None = Field(
        default=None, validation_alias="last_accessed_at"
    )
    # When the sweeper becomes free to delete this repository, or None when
    # cleanup is disabled and nothing is ever going to be reclaimed. Computed
    # server-side so the client does not duplicate the TTL arithmetic, and so
    # the countdown cannot drift from the backend's clock.
    expires_at: datetime | None = Field(default=None, validation_alias="expires_at")
    # How much of the repository is actually searchable. A repository can be
    # `completed` while holding nothing, so the count is what a caller should
    # use to decide whether it is worth opening.
    chunk_count: int = Field(default=0, validation_alias="chunk_count")


class AskRequest(SQLModel):
    """Body for asking a question.

    A request body rather than query parameters, because asking costs money,
    refreshes the repository's idle timer, and runs the embedder — none of
    which a `GET` should be allowed to trigger. See `repository_api`.
    """

    question: str
    # Omit to search every repository. Only an explicit id counts as use, so a
    # cross-repository question does not wake every stored repository.
    repository_id: int | None = None
