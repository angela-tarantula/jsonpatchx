from __future__ import annotations

from pydantic import BaseModel, Field


class User(BaseModel):
    id: int
    name: str
    tags: list[str] = Field(default_factory=list)
    trial: bool = False
    quota: int = 0
