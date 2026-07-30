from dataclasses import dataclass
import math

import numpy as np
from scipy.optimize import minimize

from app.services.exceptions import ValidationServiceError


C_LOWER_BOUND = 0.05
C_UPPER_BOUND = 5.0
C_STARTING_VALUES = (0.3, 0.5, 1.0, 2.0)
PREDICTED_POINT_COUNT = 100


@dataclass(frozen=True)
class CurveFitResult:
    T: float
    c: float
    log_likelihood: float
    sample_count: int
    converged: bool
    warnings: list[str]


def _validate_observations(times: np.ndarray, outcomes: np.ndarray) -> None:
    if times.size == 0:
        raise ValidationServiceError("no_valid_observations", "No valid delayed-recall observations are available.")
    if not np.all(np.isfinite(times)) or not np.all(np.isfinite(outcomes)):
        raise ValidationServiceError("non_finite_observation", "Observation data contains non-finite values.")
    if np.any(times <= 0):
        raise ValidationServiceError("nonpositive_retention_time", "All actual retention times must be positive.")
    if len(np.unique(times)) < 2:
        raise ValidationServiceError("insufficient_distinct_times", "At least two distinct retention times are required.")
    correct_count = int(np.sum(outcomes))
    if correct_count == 0:
        raise ValidationServiceError("all_results_incorrect", "At least one correct result is required.")
    if correct_count == outcomes.size:
        raise ValidationServiceError("all_results_correct", "At least one incorrect result is required.")


def log_likelihood(times: np.ndarray, outcomes: np.ndarray, T: float, c: float) -> float:
    if T <= 0 or c <= 0:
        return -math.inf
    z = np.power(times / T, c)
    if not np.all(np.isfinite(z)) or np.any(z <= 0):
        return -math.inf
    log_p = -z
    log_one_minus_p = np.log(-np.expm1(-z))
    values = outcomes * log_p + (1.0 - outcomes) * log_one_minus_p
    total = float(np.sum(values))
    return total if math.isfinite(total) else -math.inf


def negative_log_likelihood(log_params: np.ndarray, times: np.ndarray, outcomes: np.ndarray) -> float:
    log_T, log_c = log_params
    T = float(np.exp(log_T))
    c = float(np.exp(log_c))
    likelihood = log_likelihood(times, outcomes, T, c)
    if not math.isfinite(likelihood):
        return math.inf
    return -likelihood


def parameter_bounds(times: np.ndarray) -> tuple[list[tuple[float, float]], tuple[float, float, float, float]]:
    minimum_time = float(np.min(times))
    maximum_time = float(np.max(times))
    T_lower = max(minimum_time / 100.0, 1e-6)
    T_upper = max(maximum_time * 100.0, T_lower * 10.0)
    return (
        [(math.log(T_lower), math.log(T_upper)), (math.log(C_LOWER_BOUND), math.log(C_UPPER_BOUND))],
        (T_lower, T_upper, C_LOWER_BOUND, C_UPPER_BOUND),
    )


def fit_exponential_power_curve(times_seconds: list[float], outcomes_binary: list[int]) -> CurveFitResult:
    times = np.asarray(times_seconds, dtype=np.float64)
    outcomes = np.asarray(outcomes_binary, dtype=np.float64)
    _validate_observations(times, outcomes)

    bounds, plain_bounds = parameter_bounds(times)
    T_lower, T_upper, c_lower, c_upper = plain_bounds
    median_time = float(np.median(times))
    geometric_mean_time = float(np.exp(np.mean(np.log(times))))
    T_starts = sorted({median_time, geometric_mean_time, float(np.min(times)), float(np.max(times))})

    best_result = None
    for T_start in T_starts:
        bounded_T_start = min(max(T_start, T_lower), T_upper)
        for c_start in C_STARTING_VALUES:
            result = minimize(
                negative_log_likelihood,
                x0=np.asarray([math.log(bounded_T_start), math.log(c_start)], dtype=np.float64),
                args=(times, outcomes),
                method="L-BFGS-B",
                bounds=bounds,
            )
            if not result.success or not np.all(np.isfinite(result.x)):
                continue
            T = float(np.exp(result.x[0]))
            c = float(np.exp(result.x[1]))
            likelihood = log_likelihood(times, outcomes, T, c)
            if not math.isfinite(likelihood):
                continue
            if best_result is None or likelihood > best_result[2]:
                best_result = (T, c, likelihood)

    if best_result is None:
        raise ValidationServiceError("optimizer_convergence_failure", "Curve optimizer did not converge.")

    T, c, likelihood = best_result
    bound_tolerance = 1e-9
    if not (
        T_lower * (1.0 - bound_tolerance) <= T <= T_upper * (1.0 + bound_tolerance)
        and c_lower * (1.0 - bound_tolerance) <= c <= c_upper * (1.0 + bound_tolerance)
    ):
        raise ValidationServiceError("optimizer_convergence_failure", "Curve parameters violated optimizer bounds.")
    T = min(max(T, T_lower), T_upper)
    c = min(max(c, c_lower), c_upper)
    warnings = fitting_warnings(T, c, times, plain_bounds)
    return CurveFitResult(
        T=T,
        c=c,
        log_likelihood=likelihood,
        sample_count=int(times.size),
        converged=True,
        warnings=warnings,
    )


def fitting_warnings(T: float, c: float, times: np.ndarray, bounds: tuple[float, float, float, float]) -> list[str]:
    T_lower, T_upper, c_lower, c_upper = bounds
    warnings: list[str] = []
    tolerance = 0.02
    if T <= T_lower * (1.0 + tolerance):
        warnings.append("optimum_near_T_lower_bound")
    if T >= T_upper * (1.0 - tolerance):
        warnings.append("optimum_near_T_upper_bound")
    if c <= c_lower * (1.0 + tolerance):
        warnings.append("optimum_near_c_lower_bound")
    if c >= c_upper * (1.0 - tolerance):
        warnings.append("optimum_near_c_upper_bound")
    if float(np.max(times) / np.min(times)) < 2.0:
        warnings.append("limited_time_range")
    if times.size < 30:
        warnings.append("low_sample_count")
    return warnings


def predict_retention(time_seconds: float, T: float, c: float) -> float:
    value = math.exp(-((time_seconds / T) ** c))
    if not math.isfinite(value):
        raise ValidationServiceError("non_finite_prediction", "Predicted retention was non-finite.")
    return min(1.0, max(0.0, value))


def predicted_points(min_time: float, max_time: float, T: float, c: float) -> list[dict]:
    if min_time <= 0 or max_time <= 0 or not math.isfinite(min_time) or not math.isfinite(max_time):
        raise ValidationServiceError("nonpositive_retention_time", "Predicted point range must be positive and finite.")
    if max_time < min_time:
        min_time, max_time = max_time, min_time
    if math.isclose(min_time, max_time):
        lower = min_time
        upper = min_time * 1.01
        times = np.linspace(lower, upper, PREDICTED_POINT_COUNT, dtype=np.float64)
        times[0] = min_time
    else:
        times = np.geomspace(min_time, max_time, PREDICTED_POINT_COUNT, dtype=np.float64)
        times[0] = min_time
        times[-1] = max_time
    return [
        {"time_seconds": float(time_value), "predicted_retention": predict_retention(float(time_value), T, c)}
        for time_value in times
    ]
