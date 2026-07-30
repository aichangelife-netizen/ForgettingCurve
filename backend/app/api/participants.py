from typing import Any

from fastapi import APIRouter, Body, Depends
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.schemas.participants import ParticipantResponse, ParticipantRetentionHistoryResponse
from app.schemas.test_designs import TestDesignResponse
from app.services.participants import create_participant, get_participant
from app.services.exceptions import ValidationServiceError
from app.services.retention_summary import get_participant_retention_history
from app.services.test_designs import get_current_test_design, to_test_design_response_data


router = APIRouter(prefix="/participants", tags=["participants"])


@router.post("", response_model=ParticipantResponse, status_code=201)
def create_participant_endpoint(
    request_body: dict[str, Any] | None = Body(default=None),
    session: Session = Depends(get_db),
) -> ParticipantResponse:
    if request_body not in (None, {}):
        raise ValidationServiceError(
            "participant_request_body_not_allowed",
            "Participant creation does not accept identifying fields.",
        )
    return create_participant(session)


@router.get("/{participant_id}", response_model=ParticipantResponse)
def get_participant_endpoint(participant_id: int, session: Session = Depends(get_db)) -> ParticipantResponse:
    return get_participant(session, participant_id)


@router.get("/{participant_id}/test-designs/current", response_model=TestDesignResponse)
def get_current_test_design_endpoint(
    participant_id: int,
    session: Session = Depends(get_db),
) -> TestDesignResponse:
    design = get_current_test_design(session, participant_id)
    return TestDesignResponse.model_validate(to_test_design_response_data(design))


@router.get("/{participant_id}/retention-history", response_model=ParticipantRetentionHistoryResponse)
def get_participant_retention_history_endpoint(
    participant_id: int,
    session: Session = Depends(get_db),
) -> ParticipantRetentionHistoryResponse:
    return ParticipantRetentionHistoryResponse.model_validate(
        get_participant_retention_history(session, participant_id)
    )
