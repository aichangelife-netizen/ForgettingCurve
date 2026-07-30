"""database foundation

Revision ID: 20260731_0001
Revises:
Create Date: 2026-07-31
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260731_0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "participants",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("participant_code", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("length(trim(participant_code)) > 0", name="ck_participants_participant_code_nonblank"),
        sa.PrimaryKeyConstraint("id", name="pk_participants"),
        sa.UniqueConstraint("participant_code", name="uq_participants_participant_code"),
    )

    op.create_table(
        "vocabulary_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("korean", sa.String(), nullable=False),
        sa.Column("english_answer", sa.String(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("length(trim(korean)) > 0", name="ck_vocabulary_items_korean_nonblank"),
        sa.CheckConstraint("length(trim(english_answer)) > 0", name="ck_vocabulary_items_english_answer_nonblank"),
        sa.PrimaryKeyConstraint("id", name="pk_vocabulary_items"),
        sa.UniqueConstraint("korean", name="uq_vocabulary_items_korean"),
    )
    op.create_index("ix_vocabulary_items_is_active", "vocabulary_items", ["is_active"])

    op.create_table(
        "test_designs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("participant_id", sa.Integer(), nullable=False),
        sa.Column("items_per_group", sa.Integer(), nullable=False),
        sa.Column("group_count", sa.Integer(), nullable=False),
        sa.Column("random_seed", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=17), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("learning_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("activation_review_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("items_per_group > 0", name="ck_test_designs_items_per_group_positive"),
        sa.CheckConstraint("group_count > 0", name="ck_test_designs_group_count_positive"),
        sa.CheckConstraint(
            "status IN ('draft', 'learning', 'assigning', 'activation_review', 'active', 'completed', 'cancelled')",
            name="ck_test_designs_test_design_status",
        ),
        sa.ForeignKeyConstraint(
            ["participant_id"], ["participants.id"], name="fk_test_designs_participant_id_participants", ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_test_designs"),
        sa.UniqueConstraint("id", "participant_id", name="uq_test_designs_id_participant_id"),
    )
    op.create_index("ix_test_designs_participant_id_status", "test_designs", ["participant_id", "status"])
    op.create_index("ix_test_designs_participant_id_created_at", "test_designs", ["participant_id", "created_at"])
    op.create_index(
        "uq_test_designs_one_non_terminal_per_participant",
        "test_designs",
        ["participant_id"],
        unique=True,
        sqlite_where=sa.text("status IN ('draft', 'learning', 'assigning', 'activation_review', 'active')"),
    )

    op.create_table(
        "test_design_groups",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("test_design_id", sa.Integer(), nullable=False),
        sa.Column("group_index", sa.Integer(), nullable=False),
        sa.Column("interval_seconds", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=9), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("group_index > 0", name="ck_test_design_groups_group_index_positive"),
        sa.CheckConstraint("interval_seconds > 0", name="ck_test_design_groups_interval_seconds_positive"),
        sa.CheckConstraint(
            "status IN ('pending', 'completed', 'cancelled')",
            name="ck_test_design_groups_test_design_group_status",
        ),
        sa.ForeignKeyConstraint(
            ["test_design_id"], ["test_designs.id"], name="fk_test_design_groups_test_design_id_test_designs", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_test_design_groups"),
        sa.UniqueConstraint("test_design_id", "group_index", name="uq_test_design_groups_design_group_index"),
        sa.UniqueConstraint(
            "test_design_id", "interval_seconds", name="uq_test_design_groups_design_interval_seconds"
        ),
        sa.UniqueConstraint("id", "test_design_id", name="uq_test_design_groups_id_test_design_id"),
    )
    op.create_index("ix_test_design_groups_test_design_id_status", "test_design_groups", ["test_design_id", "status"])

    op.create_table(
        "test_design_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("test_design_id", sa.Integer(), nullable=False),
        sa.Column("vocabulary_item_id", sa.Integer(), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("correct_count", sa.Integer(), nullable=False),
        sa.Column("consecutive_correct_count", sa.Integer(), nullable=False),
        sa.Column("is_mastered", sa.Boolean(), nullable=False),
        sa.Column("mastered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("attempt_count >= 0", name="ck_test_design_items_attempt_count_nonnegative"),
        sa.CheckConstraint("correct_count >= 0", name="ck_test_design_items_correct_count_nonnegative"),
        sa.CheckConstraint(
            "consecutive_correct_count >= 0",
            name="ck_test_design_items_consecutive_correct_count_nonnegative",
        ),
        sa.CheckConstraint(
            "correct_count <= attempt_count", name="ck_test_design_items_correct_count_not_above_attempt_count"
        ),
        sa.CheckConstraint(
            "consecutive_correct_count <= correct_count",
            name="ck_test_design_items_consecutive_correct_count_not_above_correct_count",
        ),
        sa.CheckConstraint(
            "(is_mastered = 1 AND mastered_at IS NOT NULL AND consecutive_correct_count >= 2) "
            "OR (is_mastered = 0 AND mastered_at IS NULL AND consecutive_correct_count < 2)",
            name="ck_test_design_items_mastery_state_consistent",
        ),
        sa.ForeignKeyConstraint(
            ["test_design_id"], ["test_designs.id"], name="fk_test_design_items_test_design_id_test_designs", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["vocabulary_item_id"],
            ["vocabulary_items.id"],
            name="fk_test_design_items_vocabulary_item_id_vocabulary_items",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_test_design_items"),
        sa.UniqueConstraint("test_design_id", "vocabulary_item_id", name="uq_test_design_items_design_vocabulary_item"),
        sa.UniqueConstraint("id", "test_design_id", name="uq_test_design_items_id_test_design_id"),
    )
    op.create_index(
        "ix_test_design_items_test_design_id_is_mastered",
        "test_design_items",
        ["test_design_id", "is_mastered"],
    )
    op.create_index("ix_test_design_items_vocabulary_item_id", "test_design_items", ["vocabulary_item_id"])

    op.create_table(
        "test_assignments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("test_design_id", sa.Integer(), nullable=False),
        sa.Column("test_design_item_id", sa.Integer(), nullable=False),
        sa.Column("test_design_group_id", sa.Integer(), nullable=False),
        sa.Column("assignment_order", sa.Integer(), nullable=False),
        sa.Column("anchor_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=15), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("assignment_order > 0", name="ck_test_assignments_assignment_order_positive"),
        sa.CheckConstraint(
            "(status = 'awaiting_anchor' AND anchor_at IS NULL AND scheduled_at IS NULL AND completed_at IS NULL) "
            "OR (status = 'pending' AND anchor_at IS NOT NULL AND scheduled_at IS NOT NULL AND completed_at IS NULL) "
            "OR (status = 'completed' AND anchor_at IS NOT NULL AND scheduled_at IS NOT NULL AND completed_at IS NOT NULL) "
            "OR status = 'cancelled'",
            name="ck_test_assignments_status_timestamps_consistent",
        ),
        sa.CheckConstraint(
            "status IN ('awaiting_anchor', 'pending', 'completed', 'cancelled')",
            name="ck_test_assignments_test_assignment_status",
        ),
        sa.ForeignKeyConstraint(
            ["test_design_id"], ["test_designs.id"], name="fk_test_assignments_test_design_id_test_designs", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["test_design_item_id", "test_design_id"],
            ["test_design_items.id", "test_design_items.test_design_id"],
            name="fk_test_assignments_item_same_design",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["test_design_group_id", "test_design_id"],
            ["test_design_groups.id", "test_design_groups.test_design_id"],
            name="fk_test_assignments_group_same_design",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_test_assignments"),
        sa.UniqueConstraint("test_design_id", "test_design_item_id", name="uq_test_assignments_design_item"),
        sa.UniqueConstraint("test_design_group_id", "assignment_order", name="uq_test_assignments_group_order"),
        sa.UniqueConstraint("id", "test_design_item_id", name="uq_test_assignments_id_test_design_item_id"),
    )
    op.create_index("ix_test_assignments_status_scheduled_at", "test_assignments", ["status", "scheduled_at"])
    op.create_index(
        "ix_test_assignments_test_design_id_status_scheduled_at",
        "test_assignments",
        ["test_design_id", "status", "scheduled_at"],
    )

    op.create_table(
        "vocabulary_attempts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("test_design_item_id", sa.Integer(), nullable=False),
        sa.Column("test_assignment_id", sa.Integer(), nullable=True),
        sa.Column("attempt_type", sa.String(length=14), nullable=False),
        sa.Column("user_answer", sa.String(), nullable=False),
        sa.Column("normalized_answer", sa.String(), nullable=False),
        sa.Column("is_correct", sa.Boolean(), nullable=False),
        sa.Column("response_time_ms", sa.Integer(), nullable=True),
        sa.Column("attempted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("actual_retention_seconds", sa.Integer(), nullable=True),
        sa.Column("is_valid_for_fitting", sa.Boolean(), nullable=False),
        sa.Column("exclusion_reason", sa.String(), nullable=True),
        sa.CheckConstraint(
            "response_time_ms IS NULL OR response_time_ms >= 0",
            name="ck_vocabulary_attempts_response_time_ms_nonnegative",
        ),
        sa.CheckConstraint(
            "actual_retention_seconds IS NULL OR actual_retention_seconds >= 0",
            name="ck_vocabulary_attempts_actual_retention_seconds_nonnegative",
        ),
        sa.CheckConstraint(
            "attempt_type IN ('learning_check', 'delayed_recall')",
            name="ck_vocabulary_attempts_vocabulary_attempt_type",
        ),
        sa.CheckConstraint(
            "(attempt_type = 'learning_check' AND test_assignment_id IS NULL "
            "AND actual_retention_seconds IS NULL AND is_valid_for_fitting = 0) "
            "OR (attempt_type = 'delayed_recall' AND test_assignment_id IS NOT NULL "
            "AND actual_retention_seconds IS NOT NULL)",
            name="ck_vocabulary_attempts_attempt_type_fields_consistent",
        ),
        sa.CheckConstraint(
            "attempt_type != 'delayed_recall' "
            "OR (is_valid_for_fitting = 0 AND exclusion_reason IS NOT NULL) "
            "OR (is_valid_for_fitting = 1 AND exclusion_reason IS NULL)",
            name="ck_vocabulary_attempts_delayed_recall_fitting_exclusion_consistent",
        ),
        sa.ForeignKeyConstraint(
            ["test_design_item_id"],
            ["test_design_items.id"],
            name="fk_vocabulary_attempts_test_design_item_id_test_design_items",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["test_assignment_id", "test_design_item_id"],
            ["test_assignments.id", "test_assignments.test_design_item_id"],
            name="fk_vocabulary_attempts_assignment_same_item",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_vocabulary_attempts"),
        sa.UniqueConstraint("test_assignment_id", name="uq_vocabulary_attempts_test_assignment_id"),
    )
    op.create_index(
        "ix_vocabulary_attempts_test_design_item_id_attempted_at",
        "vocabulary_attempts",
        ["test_design_item_id", "attempted_at"],
    )
    op.create_index(
        "ix_vocabulary_attempts_attempt_type_is_valid_for_fitting",
        "vocabulary_attempts",
        ["attempt_type", "is_valid_for_fitting"],
    )
    op.create_index("ix_vocabulary_attempts_attempted_at", "vocabulary_attempts", ["attempted_at"])

    op.create_table(
        "curve_models",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("participant_id", sa.Integer(), nullable=False),
        sa.Column("trigger_test_design_id", sa.Integer(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("model_name", sa.String(length=17), nullable=False),
        sa.Column("fit_method", sa.String(length=13), nullable=False),
        sa.Column("T", sa.Float(), nullable=False),
        sa.Column("c", sa.Float(), nullable=False),
        sa.Column("log_likelihood", sa.Float(), nullable=True),
        sa.Column("sample_count", sa.Integer(), nullable=False),
        sa.Column("complete_time_point_count", sa.Integer(), nullable=False),
        sa.Column("converged", sa.Boolean(), nullable=False),
        sa.Column("data_cutoff_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("fitted_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("version > 0", name="ck_curve_models_version_positive"),
        sa.CheckConstraint("T > 0", name="ck_curve_models_T_positive"),
        sa.CheckConstraint("c > 0", name="ck_curve_models_c_positive"),
        sa.CheckConstraint("sample_count > 0", name="ck_curve_models_sample_count_positive"),
        sa.CheckConstraint(
            "complete_time_point_count >= 5",
            name="ck_curve_models_complete_time_point_count_minimum",
        ),
        sa.CheckConstraint("model_name = 'exponential_power'", name="ck_curve_models_model_name_exponential_power"),
        sa.CheckConstraint("fit_method = 'bernoulli_mle'", name="ck_curve_models_fit_method_bernoulli_mle"),
        sa.CheckConstraint("model_name IN ('exponential_power')", name="ck_curve_models_curve_model_name"),
        sa.CheckConstraint("fit_method IN ('bernoulli_mle')", name="ck_curve_models_curve_fit_method"),
        sa.ForeignKeyConstraint(
            ["participant_id"],
            ["participants.id"],
            name="fk_curve_models_participant_id_participants",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["trigger_test_design_id", "participant_id"],
            ["test_designs.id", "test_designs.participant_id"],
            name="fk_curve_models_trigger_design_same_participant",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_curve_models"),
        sa.UniqueConstraint("participant_id", "version", name="uq_curve_models_participant_version"),
        sa.UniqueConstraint("trigger_test_design_id", name="uq_curve_models_trigger_test_design_id"),
    )
    op.create_index("ix_curve_models_fitted_at", "curve_models", ["fitted_at"])


def downgrade() -> None:
    op.drop_index("ix_curve_models_fitted_at", table_name="curve_models")
    op.drop_table("curve_models")
    op.drop_index("ix_vocabulary_attempts_attempted_at", table_name="vocabulary_attempts")
    op.drop_index(
        "ix_vocabulary_attempts_attempt_type_is_valid_for_fitting",
        table_name="vocabulary_attempts",
    )
    op.drop_index(
        "ix_vocabulary_attempts_test_design_item_id_attempted_at",
        table_name="vocabulary_attempts",
    )
    op.drop_table("vocabulary_attempts")
    op.drop_index("ix_test_assignments_test_design_id_status_scheduled_at", table_name="test_assignments")
    op.drop_index("ix_test_assignments_status_scheduled_at", table_name="test_assignments")
    op.drop_table("test_assignments")
    op.drop_index("ix_test_design_items_vocabulary_item_id", table_name="test_design_items")
    op.drop_index("ix_test_design_items_test_design_id_is_mastered", table_name="test_design_items")
    op.drop_table("test_design_items")
    op.drop_index("ix_test_design_groups_test_design_id_status", table_name="test_design_groups")
    op.drop_table("test_design_groups")
    op.drop_index("uq_test_designs_one_non_terminal_per_participant", table_name="test_designs")
    op.drop_index("ix_test_designs_participant_id_created_at", table_name="test_designs")
    op.drop_index("ix_test_designs_participant_id_status", table_name="test_designs")
    op.drop_table("test_designs")
    op.drop_index("ix_vocabulary_items_is_active", table_name="vocabulary_items")
    op.drop_table("vocabulary_items")
    op.drop_table("participants")
