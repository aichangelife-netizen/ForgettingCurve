from datetime import timedelta
import math

import numpy as np
import pytest
import sqlalchemy as sa

from app.db.database import utc_now
from app.db.enums import (
    CurveFitMethod,
    CurveModelName,
    TestAssignmentStatus as AssignmentStatus,
    TestDesignGroupStatus as GroupStatus,
    TestDesignStatus as DesignStatus,
    VocabularyAttemptType,
)
from app.db.models import (
    CurveModel as Model,
    Participant,
    TestAssignment as Assignment,
    TestDesign as Design,
    TestDesignGroup as DesignGroup,
    TestDesignItem as DesignItem,
    VocabularyAttempt,
    VocabularyItem,
)
from app.services.curve_fitting import (
    fit_exponential_power_curve,
    log_likelihood,
    predicted_points,
)
from app.services.curve_models import curve_eligibility, eligible_observations_for_trigger
from app.services.exceptions import ValidationServiceError


def create_participant(db_session, code: str = "P-STAGE700") -> Participant:
    participant = Participant(participant_code=code, created_at=utc_now())
    db_session.add(participant)
    db_session.commit()
    db_session.refresh(participant)
    return participant


def create_completed_design(
    db_session,
    participant: Participant,
    *,
    intervals: list[int] | None = None,
    items_per_group: int = 4,
    start_index: int = 1,
    status: DesignStatus = DesignStatus.COMPLETED,
    invalid_first_attempt: bool = False,
    include_learning_attempt: bool = False,
) -> Design:
    intervals = intervals or [60, 300, 1200, 3600, 14400]
    created_at = utc_now()
    design = Design(
        participant_id=participant.id,
        items_per_group=items_per_group,
        group_count=len(intervals),
        random_seed=123,
        status=status,
        created_at=created_at,
        learning_started_at=created_at,
        activation_review_started_at=created_at,
        activated_at=created_at,
        completed_at=created_at if status == DesignStatus.COMPLETED else None,
    )
    db_session.add(design)
    db_session.flush()
    assignment_order = 1
    item_index = start_index
    for group_index, interval in enumerate(intervals, start=1):
        group = DesignGroup(
            test_design_id=design.id,
            group_index=group_index,
            interval_seconds=interval,
            status=GroupStatus.COMPLETED if status == DesignStatus.COMPLETED else GroupStatus.PENDING,
            completed_at=created_at if status == DesignStatus.COMPLETED else None,
        )
        db_session.add(group)
        db_session.flush()
        for offset in range(items_per_group):
            vocabulary = VocabularyItem(
                korean=f"곡선{participant.id}-{design.id}-{item_index}",
                english_answer=f"word{item_index}",
                is_active=True,
                created_at=created_at,
            )
            db_session.add(vocabulary)
            db_session.flush()
            item = DesignItem(
                test_design_id=design.id,
                vocabulary_item_id=vocabulary.id,
                attempt_count=2,
                correct_count=2,
                consecutive_correct_count=2,
                is_mastered=True,
                mastered_at=created_at,
                created_at=created_at,
                updated_at=created_at,
            )
            db_session.add(item)
            db_session.flush()
            actual_seconds = interval + offset + group_index
            anchor_at = created_at
            attempted_at = created_at.replace(microsecond=0) + timedelta(seconds=actual_seconds)
            assignment = Assignment(
                test_design_id=design.id,
                test_design_item_id=item.id,
                test_design_group_id=group.id,
                assignment_order=assignment_order,
                anchor_at=anchor_at,
                scheduled_at=anchor_at,
                status=AssignmentStatus.COMPLETED if status == DesignStatus.COMPLETED else AssignmentStatus.PENDING,
                created_at=created_at,
                completed_at=attempted_at if status == DesignStatus.COMPLETED else None,
            )
            db_session.add(assignment)
            db_session.flush()
            is_correct = (assignment_order % 3) != 0
            db_session.add(
                VocabularyAttempt(
                    test_design_item_id=item.id,
                    test_assignment_id=assignment.id,
                    attempt_type=VocabularyAttemptType.DELAYED_RECALL,
                    user_answer="answer",
                    normalized_answer="answer",
                    is_correct=is_correct,
                    response_time_ms=1000,
                    attempted_at=attempted_at,
                    actual_retention_seconds=actual_seconds,
                    is_valid_for_fitting=not (invalid_first_attempt and assignment_order == 1),
                    exclusion_reason="invalid" if invalid_first_attempt and assignment_order == 1 else None,
                )
            )
            if include_learning_attempt and assignment_order == 1:
                db_session.add(
                    VocabularyAttempt(
                        test_design_item_id=item.id,
                        test_assignment_id=None,
                        attempt_type=VocabularyAttemptType.LEARNING_CHECK,
                        user_answer="answer",
                        normalized_answer="answer",
                        is_correct=True,
                        response_time_ms=1000,
                        attempted_at=created_at,
                        actual_retention_seconds=None,
                        is_valid_for_fitting=False,
                    )
                )
            assignment_order += 1
            item_index += 1
    db_session.commit()
    db_session.refresh(design)
    return design


def test_data_selection_filters_observations(db_session) -> None:
    participant = create_participant(db_session)
    trigger = create_completed_design(db_session, participant, invalid_first_attempt=True, include_learning_attempt=True)
    active_design = create_completed_design(db_session, participant, start_index=100, status=DesignStatus.ACTIVE)
    other_participant = create_participant(db_session, "P-STAGE701")
    create_completed_design(db_session, other_participant, start_index=200)

    observations = eligible_observations_for_trigger(db_session, trigger)

    assert len(observations) == 19
    assert all(observation.test_design_id == trigger.id for observation in observations)
    assert active_design.id not in {observation.test_design_id for observation in observations}
    assert all(observation.actual_retention_seconds > 0 for observation in observations)


def test_later_than_trigger_design_data_excluded(db_session) -> None:
    participant = create_participant(db_session)
    first = create_completed_design(db_session, participant)
    second = create_completed_design(db_session, participant, start_index=100)
    first.completed_at = utc_now()
    second.completed_at = first.completed_at.replace(microsecond=0) + timedelta(seconds=60)
    db_session.commit()

    observations = eligible_observations_for_trigger(db_session, first)

    assert {observation.test_design_id for observation in observations} == {first.id}


def test_curve_eligibility_reasons(db_session) -> None:
    participant = create_participant(db_session)
    incomplete = create_completed_design(db_session, participant, intervals=[60], status=DesignStatus.ACTIVE)
    too_few = create_completed_design(db_session, participant, intervals=[60, 120, 180, 240], start_index=100)

    incomplete_result = curve_eligibility(db_session, incomplete.id)
    too_few_result = curve_eligibility(db_session, too_few.id)

    assert incomplete_result["eligible"] is False
    assert "design_not_completed" in incomplete_result["reasons"]
    assert too_few_result["eligible"] is False
    assert "fewer_than_five_complete_time_points" in too_few_result["reasons"]


def test_curve_eligibility_accepts_five_points_and_rejects_identical_outcomes(db_session) -> None:
    participant = create_participant(db_session)
    eligible_design = create_completed_design(db_session, participant)
    all_correct_participant = create_participant(db_session, "P-STAGE702")
    all_correct_design = create_completed_design(db_session, all_correct_participant, start_index=100)
    db_session.execute(
        sa.update(VocabularyAttempt)
        .where(VocabularyAttempt.test_design_item_id.in_(
            sa.select(DesignItem.id).where(DesignItem.test_design_id == all_correct_design.id)
        ))
        .values(is_correct=True)
    )
    db_session.commit()

    assert curve_eligibility(db_session, eligible_design.id)["eligible"] is True
    assert "all_results_correct" in curve_eligibility(db_session, all_correct_design.id)["reasons"]


def test_likelihood_stability_and_input_validation() -> None:
    times = np.asarray([1.0, 10.0, 1000.0], dtype=np.float64)
    outcomes = np.asarray([1.0, 0.0, 0.0], dtype=np.float64)

    assert math.isfinite(log_likelihood(times, outcomes, T=1e9, c=1.0))
    assert math.isfinite(log_likelihood(times, outcomes, T=1.0, c=5.0))
    with pytest.raises(ValidationServiceError):
        fit_exponential_power_curve([1.0, math.inf, 3.0], [1, 0, 1])
    with pytest.raises(ValidationServiceError):
        fit_exponential_power_curve([1.0, 1.0, 1.0], [1, 0, 1])


def test_synthetic_fit_recovers_parameters_and_predictions() -> None:
    true_T = 5000.0
    true_c = 0.8
    times = np.geomspace(60.0, 50000.0, 240)
    probabilities = np.exp(-((times / true_T) ** true_c))
    rng = np.random.default_rng(123)
    outcomes = rng.binomial(1, probabilities)

    result = fit_exponential_power_curve(list(times), [1 if outcome else 0 for outcome in outcomes])
    points = predicted_points(float(np.min(times)), float(np.max(times)), result.T, result.c)

    assert result.T == pytest.approx(true_T, rel=0.7)
    assert result.c == pytest.approx(true_c, rel=0.7)
    assert result.log_likelihood < 0
    assert len(points) == 100
    assert points[0]["time_seconds"] == pytest.approx(float(np.min(times)))
    assert points[-1]["time_seconds"] == pytest.approx(float(np.max(times)))
    assert all(0 <= point["predicted_retention"] <= 1 for point in points)


def test_create_curve_model_persists_version_one_and_is_idempotent(api_client, db_session) -> None:
    participant = create_participant(db_session)
    design = create_completed_design(db_session, participant)

    response = api_client.post(f"/api/test-designs/{design.id}/curve-model")
    second_response = api_client.post(f"/api/test-designs/{design.id}/curve-model")

    assert response.status_code == 200
    body = response.json()
    assert body["created"] is True
    assert body["curve"]["version"] == 1
    assert body["curve"]["display_name"] == "Personal Curve V1"
    assert body["curve"]["model_name"] == CurveModelName.EXPONENTIAL_POWER.value
    assert body["curve"]["fit_method"] == CurveFitMethod.BERNOULLI_MLE.value
    assert body["curve"]["T_seconds"] > 0
    assert body["curve"]["c"] > 0
    assert body["curve"]["log_likelihood"] < 0
    assert body["curve"]["data_cutoff_at"] is not None
    assert len(body["observed_points"]) == 5
    assert len(body["predicted_points"]) == 100
    assert second_response.json()["created"] is False
    assert db_session.scalar(sa.select(sa.func.count()).select_from(Model)) == 1


def test_next_completed_design_creates_version_two_and_old_version_remains(api_client, db_session) -> None:
    participant = create_participant(db_session)
    first = create_completed_design(db_session, participant)
    first_response = api_client.post(f"/api/test-designs/{first.id}/curve-model")
    first_curve = first_response.json()["curve"]
    second = create_completed_design(db_session, participant, start_index=100)

    second_response = api_client.post(f"/api/test-designs/{second.id}/curve-model")
    old_version_response = api_client.get(f"/api/participants/{participant.id}/curve-models/1")

    assert second_response.status_code == 200
    assert second_response.json()["curve"]["version"] == 2
    assert second_response.json()["curve"]["sample_count"] == 40
    assert old_version_response.json()["curve"] == first_curve


def test_out_of_order_older_trigger_rejected(api_client, db_session) -> None:
    participant = create_participant(db_session)
    first = create_completed_design(db_session, participant)
    second = create_completed_design(db_session, participant, start_index=100)
    api_client.post(f"/api/test-designs/{second.id}/curve-model")

    response = api_client.post(f"/api/test-designs/{first.id}/curve-model")

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "out_of_order_trigger"


def test_observed_points_keep_duplicate_target_groups_separate(api_client, db_session) -> None:
    participant = create_participant(db_session)
    first_design = create_completed_design(db_session, participant, intervals=[60, 300, 1200, 3600, 14400])
    design = create_completed_design(db_session, participant, intervals=[60, 600, 1800, 7200, 28800], start_index=100)

    response = api_client.post(f"/api/test-designs/{design.id}/curve-model")

    points = response.json()["observed_points"]
    assert len(points) == 10
    assert [point["target_interval_seconds"] for point in points].count(60) == 2
    assert points == sorted(points, key=lambda point: (point["mean_actual_retention_seconds"], point["test_design_id"], point["group_index"]))
    assert all(point["total_count"] == 4 for point in points)


def test_reading_apis_and_privacy(api_client, db_session) -> None:
    participant = create_participant(db_session)
    design = create_completed_design(db_session, participant)
    create_response = api_client.post(f"/api/test-designs/{design.id}/curve-model")

    list_response = api_client.get(f"/api/participants/{participant.id}/curve-models")
    latest_response = api_client.get(f"/api/participants/{participant.id}/curve-models/latest")
    version_response = api_client.get(f"/api/participants/{participant.id}/curve-models/1")
    missing_version_response = api_client.get(f"/api/participants/{participant.id}/curve-models/99")
    missing_participant_response = api_client.get("/api/participants/999/curve-models")

    assert list_response.status_code == 200
    assert [curve["version"] for curve in list_response.json()["curves"]] == [1]
    assert latest_response.json()["curve"] == create_response.json()["curve"]
    assert version_response.json()["curve"] == create_response.json()["curve"]
    assert missing_version_response.status_code == 404
    assert missing_participant_response.status_code == 404
    assert "user_answer" not in latest_response.text
    assert "english_answer" not in latest_response.text


def test_no_model_returns_not_found(api_client, db_session) -> None:
    participant = create_participant(db_session)

    response = api_client.get(f"/api/participants/{participant.id}/curve-models/latest")

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "curve_model_not_found"


def test_eligibility_endpoint_is_read_only(api_client, db_session) -> None:
    participant = create_participant(db_session)
    design = create_completed_design(db_session, participant)

    response = api_client.get(f"/api/test-designs/{design.id}/curve-eligibility")

    assert response.status_code == 200
    assert response.json()["eligible"] is True
    assert db_session.scalar(sa.select(sa.func.count()).select_from(Model)) == 0


def test_curve_is_not_created_on_fitting_failure(api_client, db_session) -> None:
    participant = create_participant(db_session)
    design = create_completed_design(db_session, participant)
    db_session.execute(
        sa.update(VocabularyAttempt)
        .where(VocabularyAttempt.test_assignment_id.is_not(None))
        .values(actual_retention_seconds=100)
    )
    db_session.commit()

    response = api_client.post(f"/api/test-designs/{design.id}/curve-model")

    assert response.status_code == 422
    assert db_session.scalar(sa.select(sa.func.count()).select_from(Model)) == 0
