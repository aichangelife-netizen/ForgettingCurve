import type { ObservedPoint, PredictedPoint } from "@/lib/api/types";
import { formatDuration, formatPercentage } from "@/lib/time-format";

const WIDTH = 760;
const HEIGHT = 360;
const PADDING = { left: 70, right: 26, top: 30, bottom: 58 };

export function logXPosition(timeSeconds: number, minTime: number, maxTime: number): number {
  const left = PADDING.left;
  const right = WIDTH - PADDING.right;
  if (timeSeconds <= 0 || minTime <= 0 || maxTime <= 0 || minTime === maxTime) return (left + right) / 2;
  const minLog = Math.log10(minTime);
  const maxLog = Math.log10(maxTime);
  const ratio = (Math.log10(timeSeconds) - minLog) / (maxLog - minLog);
  return left + Math.min(1, Math.max(0, ratio)) * (right - left);
}

function yPosition(probability: number): number {
  const top = PADDING.top;
  const bottom = HEIGHT - PADDING.bottom;
  const clamped = Math.min(1, Math.max(0, probability));
  return bottom - clamped * (bottom - top);
}

function observedTimes(points: ObservedPoint[]): number[] {
  return points
    .map((point) => point.mean_actual_retention_seconds)
    .filter((value) => Number.isFinite(value) && value > 0);
}

function predictedTimes(points: PredictedPoint[]): number[] {
  return points.map((point) => point.time_seconds).filter((value) => Number.isFinite(value) && value > 0);
}

export function curvePath(points: PredictedPoint[], minTime: number, maxTime: number): string {
  return points
    .filter((point) => point.time_seconds > 0 && Number.isFinite(point.predicted_retention))
    .map((point, index) => {
      const command = index === 0 ? "M" : "L";
      return `${command} ${logXPosition(point.time_seconds, minTime, maxTime).toFixed(2)} ${yPosition(
        point.predicted_retention,
      ).toFixed(2)}`;
    })
    .join(" ");
}

export function CurveChart({
  observedPoints,
  predictedPoints,
}: {
  observedPoints: ObservedPoint[];
  predictedPoints: PredictedPoint[];
}) {
  const allTimes = [...observedTimes(observedPoints), ...predictedTimes(predictedPoints)];
  if (allTimes.length === 0) {
    return (
      <section className="panel">
        <h2>Personal Curve</h2>
        <p>No curve data is available yet.</p>
      </section>
    );
  }
  const minTime = Math.min(...allTimes);
  const maxTime = Math.max(...allTimes);
  const path = curvePath(predictedPoints, minTime, maxTime);

  return (
    <section className="panel">
      <h2>Personal Curve</h2>
      <figure className="chart-figure">
        <svg role="img" aria-labelledby="curve-title curve-desc" viewBox={`0 0 ${WIDTH} ${HEIGHT}`}>
          <title id="curve-title">Official personal forgetting curve</title>
          <desc id="curve-desc">
            Observed retention markers are plotted against actual retention time, and the fitted curve is drawn from
            backend predicted points.
          </desc>
          <line x1={PADDING.left} y1={HEIGHT - PADDING.bottom} x2={WIDTH - PADDING.right} y2={HEIGHT - PADDING.bottom} />
          <line x1={PADDING.left} y1={PADDING.top} x2={PADDING.left} y2={HEIGHT - PADDING.bottom} />
          {[0, 0.25, 0.5, 0.75, 1].map((tick) => (
            <g key={tick}>
              <line
                className="grid-line"
                x1={PADDING.left}
                y1={yPosition(tick)}
                x2={WIDTH - PADDING.right}
                y2={yPosition(tick)}
              />
              <text x={PADDING.left - 14} y={yPosition(tick) + 5} textAnchor="end">
                {tick.toFixed(2)}
              </text>
            </g>
          ))}
          <text x={WIDTH / 2} y={HEIGHT - 16} textAnchor="middle">
            Actual retention time
          </text>
          <text transform={`translate(18 ${HEIGHT / 2}) rotate(-90)`} textAnchor="middle">
            Retention probability
          </text>
          {path ? <path className="curve-line" d={path} fill="none" /> : null}
          {observedPoints.map((point) => {
            const x = logXPosition(point.mean_actual_retention_seconds, minTime, maxTime);
            const y = yPosition(point.observed_accuracy);
            return (
              <g key={`${point.test_design_id}-${point.test_design_group_id}`} tabIndex={0} aria-label={`${formatDuration(
                point.target_interval_seconds,
              )}: ${point.correct_count} of ${point.total_count} correct, ${formatPercentage(point.observed_accuracy)}`}>
                <circle className="observed-point" cx={x} cy={y} r="6" />
                <title>
                  {formatDuration(point.target_interval_seconds)} target, mean {formatDuration(point.mean_actual_retention_seconds)},{" "}
                  {point.correct_count}/{point.total_count} correct
                </title>
              </g>
            );
          })}
          <g className="legend">
            <line x1={PADDING.left} y1={18} x2={PADDING.left + 34} y2={18} className="curve-line" />
            <text x={PADDING.left + 44} y={23}>
              Fitted personal curve
            </text>
            <circle cx={PADDING.left + 245} cy={18} r="6" className="observed-point" />
            <text x={PADDING.left + 258} y={23}>
              Observed retention
            </text>
          </g>
        </svg>
      </figure>
    </section>
  );
}
