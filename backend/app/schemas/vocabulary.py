from datetime import datetime

from pydantic import ConfigDict, Field

from app.schemas.base import APIModel


class VocabularyItemResponse(APIModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    korean: str
    english_answer: str
    is_active: bool
    created_at: datetime


class VocabularyListResponse(APIModel):
    items: list[VocabularyItemResponse]
    limit: int = Field(ge=1, le=100)
    offset: int = Field(ge=0)
    total: int
