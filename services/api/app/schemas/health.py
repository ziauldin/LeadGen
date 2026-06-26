from pydantic import BaseModel


class DependencyStatus(BaseModel):
    name: str
    status: str
    detail: str | None = None


class HealthReadyResponse(BaseModel):
    status: str
    environment: str
    dependencies: list[DependencyStatus]
