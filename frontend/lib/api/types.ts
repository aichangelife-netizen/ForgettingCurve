export type DesignStatus =
  | "draft"
  | "learning"
  | "assigning"
  | "activation_review"
  | "active"
  | "completed"
  | "cancelled";

export type Participant = {
  id: number;
  participant_code: string;
  created_at: string;
};

export type TestDesignGroup = {
  id: number;
  group_index: number;
  interval_seconds: number;
  status: string;
  completed_at: string | null;
};

export type TestDesign = {
  id: number;
  participant_id: number;
  items_per_group: number;
  group_count: number;
  required_item_count: number;
  random_seed: number;
  status: DesignStatus;
  groups: TestDesignGroup[];
  created_at: string;
  learning_started_at: string | null;
  activation_review_started_at: string | null;
  activated_at: string | null;
  completed_at: string | null;
};

export type LearningMaterial = {
  test_design_item_id: number;
  vocabulary_item_id: number;
  korean: string;
  english_answer: string;
  is_mastered: boolean;
};

export type LearningMaterials = {
  test_design_id: number;
  required_item_count: number;
  mastered_item_count: number;
  remaining_item_count: number;
  items: LearningMaterial[];
};

export type NextLearningCheck = {
  test_design_item_id: number;
  vocabulary_item_id: number;
  korean: string;
  attempt_count: number;
  consecutive_correct_count: number;
};

export type LearningAttempt = {
  attempt_id: number;
  test_design_item_id: number;
  is_correct: boolean;
  canonical_answer: string;
  attempt_count: number;
  correct_count: number;
  consecutive_correct_count: number;
  is_mastered: boolean;
  mastered_at: string | null;
  mastered_item_count: number;
  required_item_count: number;
  remaining_item_count: number;
  design_status: DesignStatus;
};

export type LearningProgress = {
  test_design_id: number;
  status: DesignStatus;
  required_item_count: number;
  pool_item_count: number;
  mastered_item_count: number;
  remaining_item_count: number;
  total_attempt_count: number;
  correct_attempt_count: number;
  learning_started_at: string | null;
};

export type AssignmentInitialization = {
  test_design_id: number;
  status: DesignStatus;
  assignment_count: number;
  group_count: number;
  items_per_group: number;
  random_seed: number;
  groups: {
    test_design_group_id: number;
    group_index: number;
    interval_seconds: number;
    assignment_count: number;
  }[];
  activation_review_started_at: string;
};

export type ActivationProgress = {
  test_design_id: number;
  status: DesignStatus;
  total_assignment_count: number;
  anchored_assignment_count: number;
  remaining_activation_count: number;
  activation_review_started_at: string | null;
  activated_at: string | null;
};

export type ActivationNext = {
  assignment_id: number;
  assignment_order: number;
  total_assignment_count: number;
  completed_activation_count: number;
  remaining_activation_count: number;
  vocabulary_item_id: number;
  korean: string;
  english_answer: string;
  group_index: number;
  interval_seconds: number;
};

export type ActivationCompletion = {
  assignment_id: number;
  anchor_at: string;
  scheduled_at: string;
  interval_seconds: number;
  remaining_activation_count: number;
  design_status: DesignStatus;
  activated_at: string | null;
};

export type NextDelayedRecall = {
  available: boolean;
  server_time: string;
  due_count: number;
  pending_count: number;
  assignment: {
    assignment_id: number;
    test_design_item_id: number;
    vocabulary_item_id: number;
    korean: string;
    group_index: number;
    target_interval_seconds: number;
    scheduled_at: string;
  } | null;
  next_scheduled_at: string | null;
};

export type DelayedRecallSubmission = {
  attempt_id: number;
  assignment_id: number;
  attempted_at: string;
  actual_retention_seconds: number;
  target_interval_seconds: number;
  lateness_seconds: number;
  assignment_status: string;
  group_index: number;
  group_completed_count: number;
  group_assignment_count: number;
  group_status: string;
  overall_completed_count: number;
  overall_assignment_count: number;
  design_status: DesignStatus;
};

export type DelayedRecallProgress = {
  test_design_id: number;
  status: DesignStatus;
  total_assignment_count: number;
  completed_assignment_count: number;
  pending_assignment_count: number;
  due_assignment_count: number;
  completed_group_count: number;
  total_group_count: number;
  next_scheduled_at: string | null;
  activated_at: string | null;
  completed_at: string | null;
};

export type RetentionSummaryGroup = {
  test_design_group_id: number;
  group_index: number;
  target_interval_seconds: number;
  status: string;
  assignment_count: number;
  completed_count: number;
  valid_result_count: number;
  correct_count: number | null;
  incorrect_count: number | null;
  observed_accuracy: number | null;
  mean_actual_retention_seconds: number | null;
  minimum_actual_retention_seconds: number | null;
  maximum_actual_retention_seconds: number | null;
};

export type RetentionSummary = {
  test_design_id: number;
  status: DesignStatus;
  complete_time_point_count: number;
  required_time_point_count_for_curve: number;
  curve_available: boolean;
  groups: RetentionSummaryGroup[];
};

export type ParticipantRetentionDesign = {
  test_design_id: number;
  status: DesignStatus;
  created_at: string;
  activated_at: string | null;
  completed_at: string | null;
  complete_time_point_count: number;
  required_time_point_count_for_curve: number;
  curve_available: boolean;
  groups: RetentionSummaryGroup[];
};

export type ParticipantRetentionHistory = {
  participant_id: number;
  designs: ParticipantRetentionDesign[];
};

export type CurveEligibility = {
  test_design_id: number;
  participant_id: number;
  design_status: DesignStatus;
  eligible: boolean;
  complete_time_point_count: number;
  sample_count: number;
  correct_count: number;
  incorrect_count: number;
  has_existing_curve: boolean;
  next_version: number;
  reasons: string[];
};

export type CurveMetadata = {
  id: number;
  participant_id: number;
  trigger_test_design_id: number;
  version: number;
  display_name: string;
  model_name: string;
  fit_method: string;
  T_seconds: number;
  c: number;
  log_likelihood: number | null;
  sample_count: number;
  complete_time_point_count: number;
  converged: boolean;
  data_cutoff_at: string;
  fitted_at: string;
};

export type ObservedPoint = {
  test_design_id: number;
  test_design_group_id: number;
  group_index: number;
  target_interval_seconds: number;
  mean_actual_retention_seconds: number;
  minimum_actual_retention_seconds: number;
  maximum_actual_retention_seconds: number;
  correct_count: number;
  total_count: number;
  observed_accuracy: number;
};

export type PredictedPoint = {
  time_seconds: number;
  predicted_retention: number;
};

export type CurveDetail = {
  curve: CurveMetadata;
  observed_points: ObservedPoint[];
  predicted_points: PredictedPoint[];
  warnings: string[];
};

export type CurveCreateResponse = CurveDetail & {
  created: boolean;
};

export type CurveList = {
  participant_id: number;
  curves: CurveMetadata[];
};
