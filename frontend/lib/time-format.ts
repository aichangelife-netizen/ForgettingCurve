export function formatDuration(seconds: number): string {
  if (!Number.isFinite(seconds)) return "unknown time";
  const rounded = Math.round(seconds);
  const abs = Math.abs(rounded);
  const units = [
    { seconds: 86400, singular: "day", plural: "days" },
    { seconds: 3600, singular: "hour", plural: "hours" },
    { seconds: 60, singular: "minute", plural: "minutes" },
  ];
  for (const unit of units) {
    if (abs >= unit.seconds && rounded % unit.seconds === 0) {
      const value = rounded / unit.seconds;
      return `${value} ${Math.abs(value) === 1 ? unit.singular : unit.plural}`;
    }
  }
  if (abs >= 3600) return `${(seconds / 3600).toFixed(1)} hours`;
  if (abs >= 60) return `${(seconds / 60).toFixed(1)} minutes`;
  return `${rounded} ${Math.abs(rounded) === 1 ? "second" : "seconds"}`;
}

export function formatDateTime(timestamp: string | null): string {
  if (!timestamp) return "Not scheduled";
  const date = new Date(timestamp);
  if (Number.isNaN(date.getTime())) return "Invalid date";
  return date.toLocaleString();
}

export function formatCountdown(targetTimestamp: string | null, now: Date = new Date()): string {
  if (!targetTimestamp) return "No scheduled test";
  const target = new Date(targetTimestamp);
  if (Number.isNaN(target.getTime())) return "Invalid scheduled time";
  const seconds = Math.max(0, Math.ceil((target.getTime() - now.getTime()) / 1000));
  if (seconds === 0) return "Due now";
  return `${formatDuration(seconds)} remaining`;
}

export function formatPercentage(value: number | null): string {
  if (value === null || !Number.isFinite(value)) return "Not available";
  return `${Math.round(value * 100)}%`;
}
