from enum import Enum


class TestDesignStatus(str, Enum):
    DRAFT = "draft"
    LEARNING = "learning"
    ASSIGNING = "assigning"
    ACTIVATION_REVIEW = "activation_review"
    ACTIVE = "active"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class TestDesignGroupStatus(str, Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class TestAssignmentStatus(str, Enum):
    AWAITING_ANCHOR = "awaiting_anchor"
    PENDING = "pending"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class VocabularyAttemptType(str, Enum):
    LEARNING_CHECK = "learning_check"
    DELAYED_RECALL = "delayed_recall"


class CurveModelName(str, Enum):
    EXPONENTIAL_POWER = "exponential_power"


class CurveFitMethod(str, Enum):
    BERNOULLI_MLE = "bernoulli_mle"


NON_TERMINAL_TEST_DESIGN_STATUSES = (
    TestDesignStatus.DRAFT.value,
    TestDesignStatus.LEARNING.value,
    TestDesignStatus.ASSIGNING.value,
    TestDesignStatus.ACTIVATION_REVIEW.value,
    TestDesignStatus.ACTIVE.value,
)
