from datetime import datetime

from pydantic import BaseModel


class CurveMetadataResponse(BaseModel):
    id: int
    participant_id: int
    trigger_test_design_id: int
    version: int
    display_name: str
    model_name: str
    fit_method: str
    T_seconds: float
    c: float
    log_likelihood: float | None
    sample_count: int
    complete_time_point_count: int
    converged: bool
    data_cutoff_at: datetime
    fitted_at: datetime


class ObservedPointResponse(BaseModel):
    test_design_id: int
    test_design_group_id: int
    group_index: int
    target_interval_seconds: int
    mean_actual_retention_seconds: float
    minimum_actual_retention_seconds: int
    maximum_actual_retention_seconds: int
    correct_count: int
    total_count: int
    observed_accuracy: float


class PredictedPointResponse(BaseModel):
    time_seconds: float
    predicted_retention: float


class CurveModelDetailResponse(BaseModel):
    curve: CurveMetadataResponse
    observed_points: list[ObservedPointResponse]
    predicted_points: list[PredictedPointResponse]
    warnings: list[str]


class CurveModelCreateResponse(CurveModelDetailResponse):
    created: bool


class CurveModelListResponse(BaseModel):
    participant_id: int
    curves: list[CurveMetadataResponse]


class CurveEligibilityResponse(BaseModel):
    test_design_id: int
    participant_id: int
    design_status: str
    eligible: bool
    complete_time_point_count: int
    sample_count: int
    correct_count: int
    incorrect_count: int
    has_existing_curve: bool
    next_version: int
    reasons: list[str]
