from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.database import utc_now
from app.db.enums import CurveFitMethod, CurveModelName, TestAssignmentStatus, TestDesignGroupStatus, TestDesignStatus, VocabularyAttemptType
from app.db.models import CurveModel, Participant, TestAssignment, TestDesign, TestDesignGroup, VocabularyAttempt
from app.services.curve_fitting import fit_exponential_power_curve, predicted_points
from app.services.exceptions import ConflictError, NotFoundError, ValidationServiceError


@dataclass(frozen=True)
class Observation:
    test_design_id: int
    test_design_group_id: int
    group_index: int
    target_interval_seconds: int
    is_correct: bool
    actual_retention_seconds: int
    attempted_at: datetime


def curve_display_name(version: int) -> str:
    return f"Personal Curve V{version}"


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _get_design(session: Session, test_design_id: int) -> TestDesign:
    design = session.get(TestDesign, test_design_id)
    if design is None:
        raise NotFoundError("test_design_not_found", "Test design was not found.")
    return design


def _get_participant(session: Session, participant_id: int) -> Participant:
    participant = session.get(Participant, participant_id)
    if participant is None:
        raise NotFoundError("participant_not_found", "Participant was not found.")
    return participant


def _completed_designs_through_trigger(session: Session, trigger_design: TestDesign) -> list[TestDesign]:
    all_completed = list(
        session.scalars(
            select(TestDesign)
            .where(TestDesign.participant_id == trigger_design.participant_id)
            .where(TestDesign.status == TestDesignStatus.COMPLETED)
            .order_by(TestDesign.completed_at, TestDesign.id)
        )
    )
    included: list[TestDesign] = []
    for design in all_completed:
        included.append(design)
        if design.id == trigger_design.id:
            return included
    return []


def _later_curve_exists(session: Session, trigger_design: TestDesign) -> bool:
    later_design_ids = [
        design.id
        for design in session.scalars(
            select(TestDesign)
            .where(TestDesign.participant_id == trigger_design.participant_id)
            .where(TestDesign.status == TestDesignStatus.COMPLETED)
            .where(
                (TestDesign.completed_at > trigger_design.completed_at)
                | ((TestDesign.completed_at == trigger_design.completed_at) & (TestDesign.id > trigger_design.id))
            )
        )
    ]
    if not later_design_ids:
        return False
    return (
        session.scalar(
            select(func.count()).select_from(CurveModel).where(CurveModel.trigger_test_design_id.in_(later_design_ids))
        )
        or 0
    ) > 0


def _next_version(session: Session, participant_id: int) -> int:
    current_max = session.scalar(select(func.max(CurveModel.version)).where(CurveModel.participant_id == participant_id))
    return int(current_max or 0) + 1


def eligible_observations_for_trigger(session: Session, trigger_design: TestDesign) -> list[Observation]:
    included_designs = _completed_designs_through_trigger(session, trigger_design)
    if not included_designs:
        return []
    included_ids = [design.id for design in included_designs]
    rows = session.execute(
        select(
            TestDesign.id,
            TestDesignGroup.id,
            TestDesignGroup.group_index,
            TestDesignGroup.interval_seconds,
            VocabularyAttempt.is_correct,
            VocabularyAttempt.actual_retention_seconds,
            VocabularyAttempt.attempted_at,
        )
        .join(TestAssignment, TestAssignment.test_design_id == TestDesign.id)
        .join(TestDesignGroup, TestDesignGroup.id == TestAssignment.test_design_group_id)
        .join(VocabularyAttempt, VocabularyAttempt.test_assignment_id == TestAssignment.id)
        .where(TestDesign.id.in_(included_ids))
        .where(TestDesign.participant_id == trigger_design.participant_id)
        .where(TestDesign.status == TestDesignStatus.COMPLETED)
        .where(TestDesignGroup.status == TestDesignGroupStatus.COMPLETED)
        .where(TestAssignment.status == TestAssignmentStatus.COMPLETED)
        .where(VocabularyAttempt.attempt_type == VocabularyAttemptType.DELAYED_RECALL)
        .where(VocabularyAttempt.is_valid_for_fitting.is_(True))
        .where(VocabularyAttempt.actual_retention_seconds.is_not(None))
        .where(VocabularyAttempt.actual_retention_seconds > 0)
    ).all()
    return [
        Observation(
            test_design_id=row[0],
            test_design_group_id=row[1],
            group_index=row[2],
            target_interval_seconds=row[3],
            is_correct=bool(row[4]),
            actual_retention_seconds=int(row[5]),
            attempted_at=row[6],
        )
        for row in rows
    ]


def complete_time_point_count_for_trigger(session: Session, trigger_design: TestDesign) -> int:
    included_designs = _completed_designs_through_trigger(session, trigger_design)
    if not included_designs:
        return 0
    return session.scalar(
        select(func.count())
        .select_from(TestDesignGroup)
        .where(TestDesignGroup.test_design_id.in_([design.id for design in included_designs]))
        .where(TestDesignGroup.status == TestDesignGroupStatus.COMPLETED)
    ) or 0


def curve_eligibility(session: Session, test_design_id: int) -> dict:
    design = _get_design(session, test_design_id)
    reasons: list[str] = []
    if design.status != TestDesignStatus.COMPLETED:
        reasons.append("design_not_completed")
    elif _later_curve_exists(session, design):
        reasons.append("out_of_order_trigger")

    observations = eligible_observations_for_trigger(session, design) if design.status == TestDesignStatus.COMPLETED else []
    complete_time_point_count = complete_time_point_count_for_trigger(session, design) if design.status == TestDesignStatus.COMPLETED else 0
    sample_count = len(observations)
    correct_count = sum(1 for observation in observations if observation.is_correct)
    incorrect_count = sample_count - correct_count
    if design.status == TestDesignStatus.COMPLETED:
        if complete_time_point_count < 5:
            reasons.append("fewer_than_five_complete_time_points")
        if sample_count == 0:
            reasons.append("no_valid_delayed_results")
        if sample_count and correct_count == sample_count:
            reasons.append("all_results_correct")
        if sample_count and incorrect_count == sample_count:
            reasons.append("all_results_incorrect")
        if len({observation.actual_retention_seconds for observation in observations}) < 2:
            reasons.append("insufficient_distinct_times")
    has_existing_curve = session.scalar(select(CurveModel.id).where(CurveModel.trigger_test_design_id == test_design_id)) is not None
    return {
        "test_design_id": design.id,
        "participant_id": design.participant_id,
        "design_status": design.status.value,
        "eligible": not reasons,
        "complete_time_point_count": complete_time_point_count,
        "sample_count": sample_count,
        "correct_count": correct_count,
        "incorrect_count": incorrect_count,
        "has_existing_curve": has_existing_curve,
        "next_version": _next_version(session, design.participant_id),
        "reasons": reasons,
    }


def _raise_for_ineligible(eligibility: dict) -> None:
    if eligibility["eligible"]:
        return
    if "design_not_completed" in eligibility["reasons"]:
        raise ConflictError("design_not_completed", "Trigger design must be completed.")
    if "out_of_order_trigger" in eligibility["reasons"]:
        raise ConflictError("out_of_order_trigger", "Older trigger design cannot be fitted after a newer curve version.")
    raise ValidationServiceError("curve_not_eligible", ", ".join(eligibility["reasons"]))


def observed_points_from_observations(observations: list[Observation]) -> list[dict]:
    grouped: dict[tuple[int, int], list[Observation]] = {}
    for observation in observations:
        grouped.setdefault((observation.test_design_id, observation.test_design_group_id), []).append(observation)
    points = []
    for group_observations in grouped.values():
        retention_values = [observation.actual_retention_seconds for observation in group_observations]
        correct_count = sum(1 for observation in group_observations if observation.is_correct)
        total_count = len(group_observations)
        first = group_observations[0]
        points.append(
            {
                "test_design_id": first.test_design_id,
                "test_design_group_id": first.test_design_group_id,
                "group_index": first.group_index,
                "target_interval_seconds": first.target_interval_seconds,
                "mean_actual_retention_seconds": sum(retention_values) / total_count,
                "minimum_actual_retention_seconds": min(retention_values),
                "maximum_actual_retention_seconds": max(retention_values),
                "correct_count": correct_count,
                "total_count": total_count,
                "observed_accuracy": correct_count / total_count,
            }
        )
    return sorted(points, key=lambda point: (point["mean_actual_retention_seconds"], point["test_design_id"], point["group_index"]))


def curve_metadata(curve: CurveModel) -> dict:
    return {
        "id": curve.id,
        "participant_id": curve.participant_id,
        "trigger_test_design_id": curve.trigger_test_design_id,
        "version": curve.version,
        "display_name": curve_display_name(curve.version),
        "model_name": getattr(curve.model_name, "value", curve.model_name),
        "fit_method": getattr(curve.fit_method, "value", curve.fit_method),
        "T_seconds": curve.T,
        "c": curve.c,
        "log_likelihood": curve.log_likelihood,
        "sample_count": curve.sample_count,
        "complete_time_point_count": curve.complete_time_point_count,
        "converged": curve.converged,
        "data_cutoff_at": _as_utc(curve.data_cutoff_at),
        "fitted_at": _as_utc(curve.fitted_at),
    }


def _curve_payload(session: Session, curve: CurveModel, warnings: list[str] | None = None) -> dict:
    trigger_design = _get_design(session, curve.trigger_test_design_id)
    observations = eligible_observations_for_trigger(session, trigger_design)
    retention_values = [observation.actual_retention_seconds for observation in observations]
    return {
        "curve": curve_metadata(curve),
        "observed_points": observed_points_from_observations(observations),
        "predicted_points": predicted_points(min(retention_values), max(retention_values), curve.T, curve.c),
        "warnings": warnings or [],
    }


def create_curve_model(session: Session, test_design_id: int) -> dict:
    existing = session.scalar(select(CurveModel).where(CurveModel.trigger_test_design_id == test_design_id))
    if existing is not None:
        return {"created": False, **_curve_payload(session, existing)}

    design = _get_design(session, test_design_id)
    eligibility = curve_eligibility(session, test_design_id)
    _raise_for_ineligible(eligibility)
    observations = eligible_observations_for_trigger(session, design)
    times = [observation.actual_retention_seconds for observation in observations]
    outcomes = [1 if observation.is_correct else 0 for observation in observations]
    fit = fit_exponential_power_curve(times, outcomes)
    next_version = _next_version(session, design.participant_id)
    participant_id = design.participant_id
    trigger_design_id = design.id
    data_cutoff_at = max(observation.attempted_at for observation in observations)
    complete_time_point_count = complete_time_point_count_for_trigger(session, design)
    session.rollback()
    try:
        with session.begin():
            reloaded_design = _get_design(session, test_design_id)
            if reloaded_design.status != TestDesignStatus.COMPLETED:
                raise ConflictError("design_not_completed", "Trigger design must be completed.")
            if session.scalar(select(CurveModel.id).where(CurveModel.trigger_test_design_id == test_design_id)) is not None:
                raise ConflictError("duplicate_trigger_model", "Curve model already exists for this trigger design.")
            if _next_version(session, participant_id) != next_version:
                raise ConflictError("out_of_order_trigger", "Curve version changed before insert.")
            curve = CurveModel(
                participant_id=participant_id,
                trigger_test_design_id=trigger_design_id,
                version=next_version,
                model_name=CurveModelName.EXPONENTIAL_POWER,
                fit_method=CurveFitMethod.BERNOULLI_MLE,
                T=fit.T,
                c=fit.c,
                log_likelihood=fit.log_likelihood,
                sample_count=fit.sample_count,
                complete_time_point_count=complete_time_point_count,
                converged=True,
                data_cutoff_at=data_cutoff_at,
                fitted_at=utc_now(),
            )
            session.add(curve)
            session.flush()
    except IntegrityError as exc:
        raise ConflictError("database_integrity_conflict", "Curve model could not be created.") from exc
    return {"created": True, **_curve_payload(session, curve, fit.warnings)}


def list_curve_models(session: Session, participant_id: int) -> dict:
    _get_participant(session, participant_id)
    curves = list(
        session.scalars(select(CurveModel).where(CurveModel.participant_id == participant_id).order_by(CurveModel.version))
    )
    return {"participant_id": participant_id, "curves": [curve_metadata(curve) for curve in curves]}


def get_curve_model_by_version(session: Session, participant_id: int, version: int) -> dict:
    _get_participant(session, participant_id)
    curve = session.scalar(
        select(CurveModel).where(CurveModel.participant_id == participant_id).where(CurveModel.version == version)
    )
    if curve is None:
        raise NotFoundError("curve_version_not_found", "Requested curve version was not found.")
    return _curve_payload(session, curve)


def get_latest_curve_model(session: Session, participant_id: int) -> dict:
    _get_participant(session, participant_id)
    curve = session.scalar(
        select(CurveModel).where(CurveModel.participant_id == participant_id).order_by(CurveModel.version.desc()).limit(1)
    )
    if curve is None:
        raise NotFoundError("curve_model_not_found", "No official curve model exists for this participant.")
    return _curve_payload(session, curve)
