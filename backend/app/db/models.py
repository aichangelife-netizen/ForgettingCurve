from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.constants import MASTERY_THRESHOLD
from app.db.base import Base
from app.db.database import utc_now
from app.db.enums import (
    CurveFitMethod,
    CurveModelName,
    NON_TERMINAL_TEST_DESIGN_STATUSES,
    TestAssignmentStatus,
    TestDesignGroupStatus,
    TestDesignStatus,
    VocabularyAttemptType,
)


def enum_values(enum_class: type) -> list[str]:
    return [member.value for member in enum_class]


class Participant(Base):
    __tablename__ = "participants"
    __table_args__ = (
        CheckConstraint("length(trim(participant_code)) > 0", name="participant_code_nonblank"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    participant_code: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)

    test_designs: Mapped[list[TestDesign]] = relationship(back_populates="participant")
    curve_models: Mapped[list[CurveModel]] = relationship(back_populates="participant")


class VocabularyItem(Base):
    __tablename__ = "vocabulary_items"
    __table_args__ = (
        CheckConstraint("length(trim(korean)) > 0", name="korean_nonblank"),
        CheckConstraint("length(trim(english_answer)) > 0", name="english_answer_nonblank"),
        Index("ix_vocabulary_items_is_active", "is_active"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    korean: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    english_answer: Mapped[str] = mapped_column(String, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)

    test_design_items: Mapped[list[TestDesignItem]] = relationship(back_populates="vocabulary_item")


class TestDesign(Base):
    __tablename__ = "test_designs"
    __table_args__ = (
        UniqueConstraint("id", "participant_id", name="uq_test_designs_id_participant_id"),
        CheckConstraint("items_per_group > 0", name="items_per_group_positive"),
        CheckConstraint("group_count > 0", name="group_count_positive"),
        Index("ix_test_designs_participant_id_status", "participant_id", "status"),
        Index("ix_test_designs_participant_id_created_at", "participant_id", "created_at"),
        Index(
            "uq_test_designs_one_non_terminal_per_participant",
            "participant_id",
            unique=True,
            sqlite_where=text(
                "status IN ('draft', 'learning', 'assigning', 'activation_review', 'active')"
            ),
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    participant_id: Mapped[int] = mapped_column(
        ForeignKey("participants.id", ondelete="RESTRICT"), nullable=False
    )
    items_per_group: Mapped[int] = mapped_column(Integer, nullable=False)
    group_count: Mapped[int] = mapped_column(Integer, nullable=False)
    random_seed: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[TestDesignStatus] = mapped_column(
        Enum(
            TestDesignStatus,
            values_callable=enum_values,
            native_enum=False,
            create_constraint=True,
            name="test_design_status",
        ),
        nullable=False,
        default=TestDesignStatus.DRAFT,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    learning_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    activation_review_started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    participant: Mapped[Participant] = relationship(back_populates="test_designs")
    groups: Mapped[list[TestDesignGroup]] = relationship(
        back_populates="test_design", cascade="all, delete-orphan"
    )
    items: Mapped[list[TestDesignItem]] = relationship(
        back_populates="test_design", cascade="all, delete-orphan"
    )
    assignments: Mapped[list[TestAssignment]] = relationship(
        back_populates="test_design", cascade="all, delete-orphan"
    )
    triggered_curve_model: Mapped[CurveModel | None] = relationship(
        back_populates="trigger_test_design",
        overlaps="curve_models",
    )

    @property
    def required_item_count(self) -> int:
        return self.items_per_group * self.group_count

    @property
    def is_terminal(self) -> bool:
        return self.status.value not in NON_TERMINAL_TEST_DESIGN_STATUSES


class TestDesignGroup(Base):
    __tablename__ = "test_design_groups"
    __table_args__ = (
        UniqueConstraint("test_design_id", "group_index", name="uq_test_design_groups_design_group_index"),
        UniqueConstraint(
            "test_design_id", "interval_seconds", name="uq_test_design_groups_design_interval_seconds"
        ),
        UniqueConstraint("id", "test_design_id", name="uq_test_design_groups_id_test_design_id"),
        CheckConstraint("group_index > 0", name="group_index_positive"),
        CheckConstraint("interval_seconds > 0", name="interval_seconds_positive"),
        Index("ix_test_design_groups_test_design_id_status", "test_design_id", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    test_design_id: Mapped[int] = mapped_column(
        ForeignKey("test_designs.id", ondelete="CASCADE"), nullable=False
    )
    group_index: Mapped[int] = mapped_column(Integer, nullable=False)
    interval_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[TestDesignGroupStatus] = mapped_column(
        Enum(
            TestDesignGroupStatus,
            values_callable=enum_values,
            native_enum=False,
            create_constraint=True,
            name="test_design_group_status",
        ),
        nullable=False,
        default=TestDesignGroupStatus.PENDING,
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    test_design: Mapped[TestDesign] = relationship(back_populates="groups")
    assignments: Mapped[list[TestAssignment]] = relationship(
        back_populates="test_design_group",
        overlaps="assignments",
    )


class TestDesignItem(Base):
    __tablename__ = "test_design_items"
    __table_args__ = (
        UniqueConstraint(
            "test_design_id", "vocabulary_item_id", name="uq_test_design_items_design_vocabulary_item"
        ),
        UniqueConstraint("id", "test_design_id", name="uq_test_design_items_id_test_design_id"),
        CheckConstraint("attempt_count >= 0", name="attempt_count_nonnegative"),
        CheckConstraint("correct_count >= 0", name="correct_count_nonnegative"),
        CheckConstraint(
            "consecutive_correct_count >= 0", name="consecutive_correct_count_nonnegative"
        ),
        CheckConstraint("correct_count <= attempt_count", name="correct_count_not_above_attempt_count"),
        CheckConstraint(
            "consecutive_correct_count <= correct_count",
            name="consecutive_correct_count_not_above_correct_count",
        ),
        CheckConstraint(
            "(is_mastered = 1 AND mastered_at IS NOT NULL "
            f"AND consecutive_correct_count >= {MASTERY_THRESHOLD}) "
            "OR (is_mastered = 0 AND mastered_at IS NULL "
            f"AND consecutive_correct_count < {MASTERY_THRESHOLD})",
            name="mastery_state_consistent",
        ),
        Index("ix_test_design_items_test_design_id_is_mastered", "test_design_id", "is_mastered"),
        Index("ix_test_design_items_vocabulary_item_id", "vocabulary_item_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    test_design_id: Mapped[int] = mapped_column(
        ForeignKey("test_designs.id", ondelete="CASCADE"), nullable=False
    )
    vocabulary_item_id: Mapped[int] = mapped_column(
        ForeignKey("vocabulary_items.id", ondelete="RESTRICT"), nullable=False
    )
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    correct_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    consecutive_correct_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_mastered: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    mastered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )

    test_design: Mapped[TestDesign] = relationship(back_populates="items")
    vocabulary_item: Mapped[VocabularyItem] = relationship(back_populates="test_design_items")
    assignment: Mapped[TestAssignment | None] = relationship(
        back_populates="test_design_item",
        overlaps="assignments,test_design",
    )
    attempts: Mapped[list[VocabularyAttempt]] = relationship(
        back_populates="test_design_item",
        overlaps="vocabulary_attempt",
    )


class TestAssignment(Base):
    __tablename__ = "test_assignments"
    __table_args__ = (
        ForeignKeyConstraint(
            ["test_design_item_id", "test_design_id"],
            ["test_design_items.id", "test_design_items.test_design_id"],
            ondelete="CASCADE",
            name="fk_test_assignments_item_same_design",
        ),
        ForeignKeyConstraint(
            ["test_design_group_id", "test_design_id"],
            ["test_design_groups.id", "test_design_groups.test_design_id"],
            ondelete="CASCADE",
            name="fk_test_assignments_group_same_design",
        ),
        UniqueConstraint(
            "test_design_id", "test_design_item_id", name="uq_test_assignments_design_item"
        ),
        UniqueConstraint(
            "test_design_group_id", "assignment_order", name="uq_test_assignments_group_order"
        ),
        UniqueConstraint("id", "test_design_item_id", name="uq_test_assignments_id_test_design_item_id"),
        CheckConstraint("assignment_order > 0", name="assignment_order_positive"),
        CheckConstraint(
            "(status = 'awaiting_anchor' AND anchor_at IS NULL "
            "AND scheduled_at IS NULL AND completed_at IS NULL) "
            "OR (status = 'pending' AND anchor_at IS NOT NULL "
            "AND scheduled_at IS NOT NULL AND completed_at IS NULL) "
            "OR (status = 'completed' AND anchor_at IS NOT NULL "
            "AND scheduled_at IS NOT NULL AND completed_at IS NOT NULL) "
            "OR status = 'cancelled'",
            name="status_timestamps_consistent",
        ),
        Index("ix_test_assignments_status_scheduled_at", "status", "scheduled_at"),
        Index(
            "ix_test_assignments_test_design_id_status_scheduled_at",
            "test_design_id",
            "status",
            "scheduled_at",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    test_design_id: Mapped[int] = mapped_column(
        ForeignKey("test_designs.id", ondelete="CASCADE"), nullable=False
    )
    test_design_item_id: Mapped[int] = mapped_column(Integer, nullable=False)
    test_design_group_id: Mapped[int] = mapped_column(Integer, nullable=False)
    assignment_order: Mapped[int] = mapped_column(Integer, nullable=False)
    anchor_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[TestAssignmentStatus] = mapped_column(
        Enum(
            TestAssignmentStatus,
            values_callable=enum_values,
            native_enum=False,
            create_constraint=True,
            name="test_assignment_status",
        ),
        nullable=False,
        default=TestAssignmentStatus.AWAITING_ANCHOR,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    test_design: Mapped[TestDesign] = relationship(
        back_populates="assignments",
        foreign_keys=[test_design_id],
        overlaps="assignment,assignments",
    )
    test_design_item: Mapped[TestDesignItem] = relationship(
        back_populates="assignment",
        foreign_keys=[test_design_item_id, test_design_id],
        overlaps="assignment,assignments,test_design",
    )
    test_design_group: Mapped[TestDesignGroup] = relationship(
        back_populates="assignments",
        foreign_keys=[test_design_group_id, test_design_id],
        overlaps="assignment,assignments,test_design,test_design_item",
    )
    vocabulary_attempt: Mapped[VocabularyAttempt | None] = relationship(
        back_populates="test_assignment",
        overlaps="attempts,test_design_item",
    )


class VocabularyAttempt(Base):
    __tablename__ = "vocabulary_attempts"
    __table_args__ = (
        ForeignKeyConstraint(
            ["test_assignment_id", "test_design_item_id"],
            ["test_assignments.id", "test_assignments.test_design_item_id"],
            ondelete="CASCADE",
            name="fk_vocabulary_attempts_assignment_same_item",
        ),
        UniqueConstraint("test_assignment_id", name="uq_vocabulary_attempts_test_assignment_id"),
        CheckConstraint("response_time_ms IS NULL OR response_time_ms >= 0", name="response_time_ms_nonnegative"),
        CheckConstraint(
            "actual_retention_seconds IS NULL OR actual_retention_seconds >= 0",
            name="actual_retention_seconds_nonnegative",
        ),
        CheckConstraint(
            "(attempt_type = 'learning_check' AND test_assignment_id IS NULL "
            "AND actual_retention_seconds IS NULL AND is_valid_for_fitting = 0) "
            "OR (attempt_type = 'delayed_recall' AND test_assignment_id IS NOT NULL "
            "AND actual_retention_seconds IS NOT NULL)",
            name="attempt_type_fields_consistent",
        ),
        CheckConstraint(
            "attempt_type != 'delayed_recall' "
            "OR (is_valid_for_fitting = 0 AND exclusion_reason IS NOT NULL) "
            "OR (is_valid_for_fitting = 1 AND exclusion_reason IS NULL)",
            name="delayed_recall_fitting_exclusion_consistent",
        ),
        Index("ix_vocabulary_attempts_test_design_item_id_attempted_at", "test_design_item_id", "attempted_at"),
        Index(
            "ix_vocabulary_attempts_attempt_type_is_valid_for_fitting",
            "attempt_type",
            "is_valid_for_fitting",
        ),
        Index("ix_vocabulary_attempts_attempted_at", "attempted_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    test_design_item_id: Mapped[int] = mapped_column(
        ForeignKey("test_design_items.id", ondelete="CASCADE"), nullable=False
    )
    test_assignment_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    attempt_type: Mapped[VocabularyAttemptType] = mapped_column(
        Enum(
            VocabularyAttemptType,
            values_callable=enum_values,
            native_enum=False,
            create_constraint=True,
            name="vocabulary_attempt_type",
        ),
        nullable=False,
    )
    user_answer: Mapped[str] = mapped_column(String, nullable=False)
    normalized_answer: Mapped[str] = mapped_column(String, nullable=False)
    is_correct: Mapped[bool] = mapped_column(Boolean, nullable=False)
    response_time_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    attempted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    actual_retention_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_valid_for_fitting: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    exclusion_reason: Mapped[str | None] = mapped_column(String, nullable=True)

    test_design_item: Mapped[TestDesignItem] = relationship(
        back_populates="attempts",
        foreign_keys=[test_design_item_id],
        overlaps="vocabulary_attempt",
    )
    test_assignment: Mapped[TestAssignment | None] = relationship(
        back_populates="vocabulary_attempt",
        foreign_keys=[test_assignment_id, test_design_item_id],
        overlaps="test_design_item,attempts",
    )


class CurveModel(Base):
    __tablename__ = "curve_models"
    __table_args__ = (
        ForeignKeyConstraint(
            ["trigger_test_design_id", "participant_id"],
            ["test_designs.id", "test_designs.participant_id"],
            ondelete="RESTRICT",
            name="fk_curve_models_trigger_design_same_participant",
        ),
        UniqueConstraint("participant_id", "version", name="uq_curve_models_participant_version"),
        UniqueConstraint("trigger_test_design_id", name="uq_curve_models_trigger_test_design_id"),
        CheckConstraint("version > 0", name="version_positive"),
        CheckConstraint("T > 0", name="T_positive"),
        CheckConstraint("c > 0", name="c_positive"),
        CheckConstraint("sample_count > 0", name="sample_count_positive"),
        CheckConstraint(
            "complete_time_point_count >= 5", name="complete_time_point_count_minimum"
        ),
        CheckConstraint("model_name = 'exponential_power'", name="model_name_exponential_power"),
        CheckConstraint("fit_method = 'bernoulli_mle'", name="fit_method_bernoulli_mle"),
        Index("ix_curve_models_fitted_at", "fitted_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    participant_id: Mapped[int] = mapped_column(
        ForeignKey("participants.id", ondelete="RESTRICT"), nullable=False
    )
    trigger_test_design_id: Mapped[int] = mapped_column(Integer, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    model_name: Mapped[CurveModelName] = mapped_column(
        Enum(
            CurveModelName,
            values_callable=enum_values,
            native_enum=False,
            create_constraint=True,
            name="curve_model_name",
        ),
        nullable=False,
        default=CurveModelName.EXPONENTIAL_POWER,
    )
    fit_method: Mapped[CurveFitMethod] = mapped_column(
        Enum(
            CurveFitMethod,
            values_callable=enum_values,
            native_enum=False,
            create_constraint=True,
            name="curve_fit_method",
        ),
        nullable=False,
        default=CurveFitMethod.BERNOULLI_MLE,
    )
    T: Mapped[float] = mapped_column(Float, nullable=False)
    c: Mapped[float] = mapped_column(Float, nullable=False)
    log_likelihood: Mapped[float | None] = mapped_column(Float, nullable=True)
    sample_count: Mapped[int] = mapped_column(Integer, nullable=False)
    complete_time_point_count: Mapped[int] = mapped_column(Integer, nullable=False)
    converged: Mapped[bool] = mapped_column(Boolean, nullable=False)
    data_cutoff_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    fitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)

    participant: Mapped[Participant] = relationship(
        back_populates="curve_models",
        overlaps="triggered_curve_model",
    )
    trigger_test_design: Mapped[TestDesign] = relationship(
        back_populates="triggered_curve_model",
        foreign_keys=[trigger_test_design_id, participant_id],
        overlaps="curve_models,participant",
    )
