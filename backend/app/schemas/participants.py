from datetime import datetime

from pydantic import ConfigDict

from app.schemas.base import APIModel

from app.schemas.test_designs import RetentionSummaryGroupResponse


class ParticipantResponse(APIModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    participant_code: str
    created_at: datetime


class ParticipantRetentionDesignResponse(APIModel):
    test_design_id: int
    status: str
    created_at: datetime
    activated_at: datetime | None
    completed_at: datetime | None
    complete_time_point_count: int
    required_time_point_count_for_curve: int
    curve_available: bool
    groups: list[RetentionSummaryGroupResponse]


class ParticipantRetentionHistoryResponse(APIModel):
    participant_id: int
    designs: list[ParticipantRetentionDesignResponse]
