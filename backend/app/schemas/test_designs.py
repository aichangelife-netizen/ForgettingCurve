from datetime import datetime

from pydantic import BaseModel, ConfigDict


class TestDesignCreateRequest(BaseModel):
    participant_id: int
    items_per_group: int
    intervals_seconds: list[int]
    random_seed: int | None = None


class TestDesignGroupResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    group_index: int
    interval_seconds: int
    status: str
    completed_at: datetime | None = None


class TestDesignResponse(BaseModel):
    id: int
    participant_id: int
    items_per_group: int
    group_count: int
    required_item_count: int
    random_seed: int
    status: str
    groups: list[TestDesignGroupResponse]
    created_at: datetime
    learning_started_at: datetime | None = None
    activation_review_started_at: datetime | None = None
    activated_at: datetime | None = None
    completed_at: datetime | None = None
