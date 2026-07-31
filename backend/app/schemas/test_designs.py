from datetime import datetime

from pydantic import ConfigDict

from app.schemas.base import APIModel


class TestDesignCreateRequest(APIModel):
    participant_id: int
    items_per_group: int
    intervals_seconds: list[int]
    random_seed: int | None = None


class TestDesignGroupResponse(APIModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    group_index: int
    interval_seconds: int
    status: str
    completed_at: datetime | None = None


class TestDesignResponse(APIModel):
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


class LearningMaterialItemResponse(APIModel):
    test_design_item_id: int
    vocabulary_item_id: int
    korean: str
    english_answer: str
    is_mastered: bool


class LearningMaterialsResponse(APIModel):
    test_design_id: int
    required_item_count: int
    mastered_item_count: int
    remaining_item_count: int
    items: list[LearningMaterialItemResponse]


class NextLearningCheckResponse(APIModel):
    test_design_item_id: int
    vocabulary_item_id: int
    korean: str
    attempt_count: int
    consecutive_correct_count: int


class LearningAttemptRequest(APIModel):
    test_design_item_id: int
    user_answer: str
    response_time_ms: int | None = None


class LearningAttemptResponse(APIModel):
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


class LearningProgressResponse(APIModel):
    test_design_id: int
    status: str
    required_item_count: int
    pool_item_count: int
    mastered_item_count: int
    remaining_item_count: int
    total_attempt_count: int
    correct_attempt_count: int
    learning_started_at: datetime | None


class AssignmentInitializationGroupResponse(APIModel):
    test_design_group_id: int
    group_index: int
    interval_seconds: int
    assignment_count: int


class AssignmentInitializationResponse(APIModel):
    test_design_id: int
    status: str
    assignment_count: int
    group_count: int
    items_per_group: int
    random_seed: int
    groups: list[AssignmentInitializationGroupResponse]
    activation_review_started_at: datetime


class ActivationReviewNextResponse(APIModel):
    assignment_id: int
    assignment_order: int
    total_assignment_count: int
    completed_activation_count: int
    remaining_activation_count: int
    vocabulary_item_id: int
    korean: str
    english_answer: str
    group_index: int
    interval_seconds: int


class ActivationReviewCompletionResponse(APIModel):
    assignment_id: int
    anchor_at: datetime
    scheduled_at: datetime
    interval_seconds: int
    remaining_activation_count: int
    design_status: str
    activated_at: datetime | None


class ActivationProgressResponse(APIModel):
    test_design_id: int
    status: str
    total_assignment_count: int
    anchored_assignment_count: int
    remaining_activation_count: int
    activation_review_started_at: datetime | None
    activated_at: datetime | None


class AssignmentScheduleGroupResponse(APIModel):
    test_design_group_id: int
    group_index: int
    interval_seconds: int
    assignment_count: int
    awaiting_anchor_count: int
    pending_count: int
    completed_count: int
    earliest_scheduled_at: datetime | None
    latest_scheduled_at: datetime | None


class AssignmentScheduleResponse(APIModel):
    test_design_id: int
    status: str
    groups: list[AssignmentScheduleGroupResponse]


class DelayedRecallAssignmentResponse(APIModel):
    assignment_id: int
    test_design_item_id: int
    vocabulary_item_id: int
    korean: str
    group_index: int
    target_interval_seconds: int
    scheduled_at: datetime


class NextDelayedRecallResponse(APIModel):
    available: bool
    server_time: datetime
    due_count: int
    pending_count: int
    assignment: DelayedRecallAssignmentResponse | None
    next_scheduled_at: datetime | None = None


class DelayedRecallSubmissionRequest(APIModel):
    user_answer: str
    response_time_ms: int | None = None


class DelayedRecallSubmissionResponse(APIModel):
    attempt_id: int
    assignment_id: int
    attempted_at: datetime
    actual_retention_seconds: int
    target_interval_seconds: int
    lateness_seconds: int
    assignment_status: str
    group_index: int
    group_completed_count: int
    group_assignment_count: int
    group_status: str
    overall_completed_count: int
    overall_assignment_count: int
    design_status: str


class DelayedRecallProgressResponse(APIModel):
    test_design_id: int
    status: str
    total_assignment_count: int
    completed_assignment_count: int
    pending_assignment_count: int
    due_assignment_count: int
    completed_group_count: int
    total_group_count: int
    next_scheduled_at: datetime | None
    activated_at: datetime | None
    completed_at: datetime | None


class RetentionSummaryGroupResponse(APIModel):
    test_design_group_id: int
    group_index: int
    target_interval_seconds: int
    status: str
    assignment_count: int
    completed_count: int
    valid_result_count: int
    correct_count: int | None
    incorrect_count: int | None
    observed_accuracy: float | None
    mean_actual_retention_seconds: float | None
    minimum_actual_retention_seconds: int | None
    maximum_actual_retention_seconds: int | None


class RetentionSummaryResponse(APIModel):
    test_design_id: int
    status: str
    complete_time_point_count: int
    required_time_point_count_for_curve: int
    curve_available: bool
    groups: list[RetentionSummaryGroupResponse]
