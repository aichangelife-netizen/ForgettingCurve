from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.schemas.test_designs import TestDesignCreateRequest, TestDesignResponse
from app.services.test_designs import (
    create_test_design,
    get_test_design,
    start_learning,
    to_test_design_response_data,
)


router = APIRouter(prefix="/test-designs", tags=["test-designs"])


@router.post("", response_model=TestDesignResponse, status_code=201)
def create_test_design_endpoint(
    request: TestDesignCreateRequest,
    session: Session = Depends(get_db),
) -> TestDesignResponse:
    design = create_test_design(
        session,
        participant_id=request.participant_id,
        items_per_group=request.items_per_group,
        intervals_seconds=request.intervals_seconds,
        random_seed=request.random_seed,
    )
    return TestDesignResponse.model_validate(to_test_design_response_data(design))


@router.get("/{test_design_id}", response_model=TestDesignResponse)
def get_test_design_endpoint(test_design_id: int, session: Session = Depends(get_db)) -> TestDesignResponse:
    design = get_test_design(session, test_design_id)
    return TestDesignResponse.model_validate(to_test_design_response_data(design))


@router.post("/{test_design_id}/start-learning", response_model=TestDesignResponse)
def start_learning_endpoint(test_design_id: int, session: Session = Depends(get_db)) -> TestDesignResponse:
    design = start_learning(session, test_design_id)
    return TestDesignResponse.model_validate(to_test_design_response_data(design))
