from pydantic import BaseModel, Field


class TemplateRead(BaseModel):
    id: str
    name: str
    description: str = ""
    subject: str
    body: str
    is_system: bool
    is_archived: bool = False


class TemplateCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=500)
    subject: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1, max_length=10_000)


class TemplateUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=500)
    subject: str | None = Field(default=None, min_length=1, max_length=200)
    body: str | None = Field(default=None, min_length=1, max_length=10_000)
    is_archived: bool | None = None


class TemplateVariables(BaseModel):
    variables: list[str]
    required: list[str]
