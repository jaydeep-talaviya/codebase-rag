from sqlmodel import Field,SQLModel

class RepositoryRepresentation(SQLModel):
    id: int = Field(default=None, primary_key=True)
    name: str = Field(default=None, validation_alias="name")
    url: str = Field(default=None, validation_alias="url")
    status: str = Field(default=None, validation_alias="status")