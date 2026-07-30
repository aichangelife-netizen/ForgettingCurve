from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.schemas.test_designs import (
    ActivationProgressResponse,
    ActivationReviewCompletionResponse,
    ActivationReviewNextResponse,
    AssignmentInitializationResponse,
    AssignmentScheduleResponse,
    DelayedRecallProgressResponse,
    DelayedRecallSubmissionRequest,
    DelayedRecallSubmissionResponse,
    LearningAttemptRequest,
    LearningAttemptResponse,
    LearningMaterialsResponse,
    LearningProgressResponse,
    NextDelayedRecallResponse,
    NextLearningCheckResponse,
    RetentionSummaryResponse,
    TestDesignCreateRequest,
    TestDesignResponse,
)
from app.schemas.curve_models import CurveEligibilityResponse, CurveModelCreateResponse
from app.services.activation_review import (
    complete_activation_review_assignment,
    get_activation_progress,
    get_activation_review_next,
)
from app.services.assignment import get_assignment_schedule, initialize_assignments
from app.services.delayed_recall import (
    get_delayed_recall_progress,
    get_next_due_delayed_recall,
    submit_delayed_recall,
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
from app.services.retention_summary import get_retention_summary
from app.services.curve_models import create_curve_model, curve_eligibility


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


@router.post("/{test_design_id}/initialize-assignments", response_model=AssignmentInitializationResponse)
def initialize_assignments_endpoint(
    test_design_id: int,
    session: Session = Depends(get_db),
) -> AssignmentInitializationResponse:
    return AssignmentInitializationResponse.model_validate(initialize_assignments(session, test_design_id))


@router.get("/{test_design_id}/activation-review/next", response_model=ActivationReviewNextResponse)
def get_activation_review_next_endpoint(
    test_design_id: int,
    session: Session = Depends(get_db),
) -> ActivationReviewNextResponse:
    return ActivationReviewNextResponse.model_validate(get_activation_review_next(session, test_design_id))


@router.post(
    "/{test_design_id}/activation-review/{assignment_id}/complete",
    response_model=ActivationReviewCompletionResponse,
)
def complete_activation_review_assignment_endpoint(
    test_design_id: int,
    assignment_id: int,
    session: Session = Depends(get_db),
) -> ActivationReviewCompletionResponse:
    return ActivationReviewCompletionResponse.model_validate(
        complete_activation_review_assignment(
            session,
            test_design_id=test_design_id,
            assignment_id=assignment_id,
        )
    )


@router.get("/{test_design_id}/activation-review/progress", response_model=ActivationProgressResponse)
def get_activation_progress_endpoint(
    test_design_id: int,
    session: Session = Depends(get_db),
) -> ActivationProgressResponse:
    return ActivationProgressResponse.model_validate(get_activation_progress(session, test_design_id))


@router.get("/{test_design_id}/assignment-schedule", response_model=AssignmentScheduleResponse)
def get_assignment_schedule_endpoint(
    test_design_id: int,
    session: Session = Depends(get_db),
) -> AssignmentScheduleResponse:
    return AssignmentScheduleResponse.model_validate(get_assignment_schedule(session, test_design_id))


@router.get("/{test_design_id}/delayed-recalls/next", response_model=NextDelayedRecallResponse)
def get_next_due_delayed_recall_endpoint(
    test_design_id: int,
    session: Session = Depends(get_db),
) -> NextDelayedRecallResponse:
    return NextDelayedRecallResponse.model_validate(get_next_due_delayed_recall(session, test_design_id))


@router.post("/{test_design_id}/delayed-recalls/{assignment_id}", response_model=DelayedRecallSubmissionResponse)
def submit_delayed_recall_endpoint(
    test_design_id: int,
    assignment_id: int,
    request: DelayedRecallSubmissionRequest,
    session: Session = Depends(get_db),
) -> DelayedRecallSubmissionResponse:
    return DelayedRecallSubmissionResponse.model_validate(
        submit_delayed_recall(
            session,
            test_design_id=test_design_id,
            assignment_id=assignment_id,
            user_answer=request.user_answer,
            response_time_ms=request.response_time_ms,
        )
    )


@router.get("/{test_design_id}/delayed-recalls/progress", response_model=DelayedRecallProgressResponse)
def get_delayed_recall_progress_endpoint(
    test_design_id: int,
    session: Session = Depends(get_db),
) -> DelayedRecallProgressResponse:
    return DelayedRecallProgressResponse.model_validate(get_delayed_recall_progress(session, test_design_id))


@router.get("/{test_design_id}/retention-summary", response_model=RetentionSummaryResponse)
def get_retention_summary_endpoint(
    test_design_id: int,
    session: Session = Depends(get_db),
) -> RetentionSummaryResponse:
    return RetentionSummaryResponse.model_validate(get_retention_summary(session, test_design_id))


@router.get("/{test_design_id}/curve-eligibility", response_model=CurveEligibilityResponse)
def get_curve_eligibility_endpoint(
    test_design_id: int,
    session: Session = Depends(get_db),
) -> CurveEligibilityResponse:
    return CurveEligibilityResponse.model_validate(curve_eligibility(session, test_design_id))


@router.post("/{test_design_id}/curve-model", response_model=CurveModelCreateResponse)
def create_curve_model_endpoint(
    test_design_id: int,
    session: Session = Depends(get_db),
) -> CurveModelCreateResponse:
    return CurveModelCreateResponse.model_validate(create_curve_model(session, test_design_id))
