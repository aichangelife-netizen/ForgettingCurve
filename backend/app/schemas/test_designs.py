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


class LearningMaterialItemResponse(BaseModel):
    test_design_item_id: int
    vocabulary_item_id: int
    korean: str
    english_answer: str
    is_mastered: bool


class LearningMaterialsResponse(BaseModel):
    test_design_id: int
    required_item_count: int
    mastered_item_count: int
    remaining_item_count: int
    items: list[LearningMaterialItemResponse]


class NextLearningCheckResponse(BaseModel):
    test_design_item_id: int
    vocabulary_item_id: int
    korean: str
    attempt_count: int
    consecutive_correct_count: int


class LearningAttemptRequest(BaseModel):
    test_design_item_id: int
    user_answer: str
    response_time_ms: int | None = None


class LearningAttemptResponse(BaseModel):
    attempt_id: int
    test_design_item_id: int
    is_correct: bool
    canonical_answer: str
    attempt_count: int
    correct_count: int
    consecutive_correct_count: int
    is_mastered: bool
    mastered_at: datetime | None
    mastered_item_count: int
    required_item_count: int
    remaining_item_count: int
    design_status: str


class LearningProgressResponse(BaseModel):
    test_design_id: int
    status: str
    required_item_count: int
    pool_item_count: int
    mastered_item_count: int
    remaining_item_count: int
    total_attempt_count: int
    correct_attempt_count: int
    learning_started_at: datetime | None
