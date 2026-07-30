from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.schemas.curve_models import CurveModelDetailResponse, CurveModelListResponse
from app.services.curve_models import (
    get_curve_model_by_version,
    get_latest_curve_model,
    list_curve_models,
)


router = APIRouter(prefix="/participants", tags=["curve-models"])


@router.get("/{participant_id}/curve-models", response_model=CurveModelListResponse)
def list_curve_models_endpoint(
    participant_id: int,
    session: Session = Depends(get_db),
) -> CurveModelListResponse:
    return CurveModelListResponse.model_validate(list_curve_models(session, participant_id))


@router.get("/{participant_id}/curve-models/latest", response_model=CurveModelDetailResponse)
def get_latest_curve_model_endpoint(
    participant_id: int,
    session: Session = Depends(get_db),
) -> CurveModelDetailResponse:
    return CurveModelDetailResponse.model_validate(get_latest_curve_model(session, participant_id))


@router.get("/{participant_id}/curve-models/{version}", response_model=CurveModelDetailResponse)
def get_curve_model_by_version_endpoint(
    participant_id: int,
    version: int,
    session: Session = Depends(get_db),
) -> CurveModelDetailResponse:
    return CurveModelDetailResponse.model_validate(get_curve_model_by_version(session, participant_id, version))
