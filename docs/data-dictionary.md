# Data Dictionary

This dictionary covers research-relevant persisted fields. Units are listed where applicable. `Raw` means directly stored from configuration, workflow state, or participant response. `Derived` means calculated by application logic and stored. `Fitted` means produced by curve optimization.

## participants

| Field | Meaning | Unit | Nullable | Type | Used for fitting |
| --- | --- | --- | --- | --- | --- |
| `id` | Internal participant identifier | none | no | Raw | yes, joins source data |
| `participant_code` | Generated anonymous participant code | none | no | Raw | no |
| `created_at` | Participant creation time | UTC timestamp | no | Raw | no |

## vocabulary_items

| Field | Meaning | Unit | Nullable | Type | Used for fitting |
| --- | --- | --- | --- | --- | --- |
| `id` | Internal vocabulary identifier | none | no | Raw | yes, through design item linkage |
| `korean` | Korean prompt | text | no | Raw | no |
| `english_answer` | Canonical English answer | text | no | Raw | no |
| `is_active` | Whether the item can be selected for new learning pools | boolean | no | Raw | no |
| `created_at` | Vocabulary row creation time | UTC timestamp | no | Raw | no |

## test_designs

| Field | Meaning | Unit | Nullable | Type | Used for fitting |
| --- | --- | --- | --- | --- | --- |
| `id` | Internal design identifier | none | no | Raw | yes, source cutoff and joins |
| `participant_id` | Owner participant | none | no | Raw | yes |
| `items_per_group` | Number of assigned words per retention group | count | no | Raw | indirectly, complete time-point checks |
| `group_count` | Number of retention groups | count | no | Raw | indirectly |
| `random_seed` | Stored deterministic seed | integer | no | Raw | no |
| `status` | Workflow status | enum | no | Derived | yes, only completed designs fit |
| `created_at` | Design creation time | UTC timestamp | no | Raw | no |
| `learning_started_at` | Learning start time | UTC timestamp | yes | Derived | no |
| `activation_review_started_at` | Assignment initialization time | UTC timestamp | yes | Derived | no |
| `activated_at` | Active delayed-test start time | UTC timestamp | yes | Derived | no |
| `completed_at` | Design completion time | UTC timestamp | yes | Derived | yes, chronological source ordering |

## test_design_groups

| Field | Meaning | Unit | Nullable | Type | Used for fitting |
| --- | --- | --- | --- | --- | --- |
| `id` | Internal group identifier | none | no | Raw | yes, observed point grouping |
| `test_design_id` | Parent design | none | no | Raw | yes |
| `group_index` | Ordered group number | count | no | Raw | no |
| `interval_seconds` | Target delayed recall interval | seconds | no | Raw | no, returned for context only |
| `status` | Group status | enum | no | Derived | yes, only completed groups are complete time points |
| `completed_at` | Group completion time | UTC timestamp | yes | Derived | no |

## test_design_items

| Field | Meaning | Unit | Nullable | Type | Used for fitting |
| --- | --- | --- | --- | --- | --- |
| `id` | Internal selected item identifier | none | no | Raw | yes, joins attempts |
| `test_design_id` | Parent design | none | no | Raw | yes |
| `vocabulary_item_id` | Selected vocabulary item | none | no | Raw | yes, item identity |
| `attempt_count` | Learning-check attempts for this item | count | no | Derived | no |
| `correct_count` | Correct learning-check attempts | count | no | Derived | no |
| `consecutive_correct_count` | Current consecutive correct learning-check streak | count | no | Derived | no |
| `is_mastered` | Whether mastery threshold was reached | boolean | no | Derived | no |
| `mastered_at` | Time item became mastered | UTC timestamp | yes | Derived | no |
| `created_at` | Learning-pool insertion time | UTC timestamp | no | Raw | no |
| `updated_at` | Learning item state update time | UTC timestamp | no | Derived | no |

## test_assignments

| Field | Meaning | Unit | Nullable | Type | Used for fitting |
| --- | --- | --- | --- | --- | --- |
| `id` | Internal assignment identifier | none | no | Raw | yes, joins delayed attempt |
| `test_design_id` | Parent design | none | no | Raw | yes |
| `test_design_item_id` | Assigned design item | none | no | Raw | yes |
| `test_design_group_id` | Assigned group | none | no | Raw | yes |
| `assignment_order` | Deterministic activation order | count | no | Derived | no |
| `anchor_at` | Per-item memory-time anchor | UTC timestamp | yes | Derived | yes, used to calculate actual retention |
| `scheduled_at` | Due time | UTC timestamp | yes | Derived | no |
| `status` | Assignment status | enum | no | Derived | yes, only completed assignments fit |
| `created_at` | Assignment creation time | UTC timestamp | no | Derived | no |
| `completed_at` | Delayed recall completion time | UTC timestamp | yes | Derived | no |

## vocabulary_attempts

| Field | Meaning | Unit | Nullable | Type | Used for fitting |
| --- | --- | --- | --- | --- | --- |
| `id` | Internal attempt identifier | none | no | Raw | no |
| `test_design_item_id` | Attempted design item | none | no | Raw | yes |
| `test_assignment_id` | Delayed assignment, null for learning checks | none | yes | Raw | yes, delayed recall only |
| `attempt_type` | `learning_check` or `delayed_recall` | enum | no | Raw | yes, delayed recall only |
| `user_answer` | Raw submitted answer | text | no | Raw | no |
| `normalized_answer` | Normalized submitted answer | text | no | Derived | no |
| `is_correct` | Exact-match correctness | boolean | no | Derived | yes, fitted item-level outcome |
| `response_time_ms` | Client-measured response duration | milliseconds | yes | Raw | no |
| `attempted_at` | Server attempt timestamp | UTC timestamp | no | Raw | yes, data cutoff |
| `actual_retention_seconds` | Actual elapsed time from anchor | seconds | yes | Derived | yes, fitted time value |
| `is_valid_for_fitting` | Whether delayed attempt can enter official fitting | boolean | no | Derived | yes |
| `exclusion_reason` | Reason a delayed attempt is invalid for fitting | text | yes | Derived | yes, excludes when present |

## curve_models

| Field | Meaning | Unit | Nullable | Type | Used for fitting |
| --- | --- | --- | --- | --- | --- |
| `id` | Internal curve identifier | none | no | Raw | no |
| `participant_id` | Owner participant | none | no | Raw | no |
| `trigger_test_design_id` | Completed design that triggered this version | none | no | Raw | no |
| `version` | Participant curve version number | count | no | Derived | no |
| `model_name` | Official model name, `exponential_power` | enum | no | Derived | no |
| `fit_method` | Official fit method, `bernoulli_mle` | enum | no | Derived | no |
| `T` | Fitted time-scale parameter | seconds | no | Fitted | output |
| `c` | Fitted shape parameter | unitless | no | Fitted | output |
| `log_likelihood` | Maximized Bernoulli log likelihood | log likelihood | yes | Fitted | output |
| `sample_count` | Number of item-level observations fitted | count | no | Derived | no |
| `complete_time_point_count` | Completed groups included | count | no | Derived | no |
| `converged` | Whether optimizer converged | boolean | no | Fitted | no |
| `data_cutoff_at` | Latest included attempt timestamp | UTC timestamp | no | Derived | no |
| `fitted_at` | Curve row creation time | UTC timestamp | no | Derived | no |
