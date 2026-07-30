export const DEVELOPMENT_INTERVALS = [60, 180, 300, 600, 1200];
export const RESEARCH_INTERVALS = [600, 3600, 21600, 86400, 604800];

export type DesignValidationResult = {
  valid: boolean;
  errors: string[];
  intervals: number[];
  requiredItemCount: number;
  groupCount: number;
};

export function parseIntervals(value: string): number[] {
  return value
    .split(/[\s,]+/)
    .map((part) => part.trim())
    .filter(Boolean)
    .map((part) => Number(part));
}

export function validateDesignInput(itemsPerGroup: number, intervalText: string): DesignValidationResult {
  const intervals = parseIntervals(intervalText);
  const errors: string[] = [];
  if (!Number.isInteger(itemsPerGroup) || itemsPerGroup <= 0) {
    errors.push("Items per group must be a positive integer.");
  }
  if (intervals.length === 0) {
    errors.push("At least one retention interval is required.");
  }
  if (intervals.some((interval) => !Number.isInteger(interval) || interval <= 0)) {
    errors.push("Every retention interval must be a positive integer number of seconds.");
  }
  if (new Set(intervals).size !== intervals.length) {
    errors.push("Retention intervals must not contain duplicates.");
  }
  return {
    valid: errors.length === 0,
    errors,
    intervals,
    groupCount: intervals.length,
    requiredItemCount: Number.isInteger(itemsPerGroup) && itemsPerGroup > 0 ? itemsPerGroup * intervals.length : 0,
  };
}
