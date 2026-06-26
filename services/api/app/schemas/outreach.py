from pydantic import BaseModel


class OutreachReadiness(BaseModel):
    ready: bool
    issues: list[str]
