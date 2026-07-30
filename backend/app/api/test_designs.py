from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.schemas.test_designs import (
    LearningAttemptRequest,
    LearningAttemptResponse,
    LearningMaterialsResponse,
    LearningProgressResponse,
    NextLearningCheckResponse,
    TestDesignCreateRequest,
    TestDesignResponse,
)
from app.services.learning import (
    get_learning_materials,
    get_learning_progress,
    get_next_learning_check,
    initialize_learning,
    submit_learning_attempt,
)
from app.services.test_designs import (
    create_test_design,
    get_test_design,
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
    design = initialize_learning(session, test_design_id)
    return TestDesignResponse.model_validate(to_test_design_response_data(design))


@router.get("/{test_design_id}/learning-materials", response_model=LearningMaterialsResponse)
def get_learning_materials_endpoint(
    test_design_id: int,
    session: Session = Depends(get_db),
) -> LearningMaterialsResponse:
    return LearningMaterialsResponse.model_validate(get_learning_materials(session, test_design_id))


@router.get("/{test_design_id}/learning-checks/next", response_model=NextLearningCheckResponse)
def get_next_learning_check_endpoint(
    test_design_id: int,
    session: Session = Depends(get_db),
) -> NextLearningCheckResponse:
    return NextLearningCheckResponse.model_validate(get_next_learning_check(session, test_design_id))


@router.post("/{test_design_id}/learning-attempts", response_model=LearningAttemptResponse)
def submit_learning_attempt_endpoint(
    test_design_id: int,
    request: LearningAttemptRequest,
    session: Session = Depends(get_db),
) -> LearningAttemptResponse:
    return LearningAttemptResponse.model_validate(
        submit_learning_attempt(
            session,
            test_design_id=test_design_id,
            test_design_item_id=request.test_design_item_id,
            user_answer=request.user_answer,
            response_time_ms=request.response_time_ms,
        )
    )


@router.get("/{test_design_id}/learning-progress", response_model=LearningProgressResponse)
def get_learning_progress_endpoint(
    test_design_id: int,
    session: Session = Depends(get_db),
) -> LearningProgressResponse:
    return LearningProgressResponse.model_validate(get_learning_progress(session, test_design_id))
