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

const TIMEZONE_SUFFIX_PATTERN = /(Z|[+-]\d{2}:?\d{2})$/i;

export function parseUtcTimestamp(timestamp: string | null): Date | null {
  if (!timestamp) return null;
  const trimmed = timestamp.trim();
  if (!trimmed) return null;
  const normalized = TIMEZONE_SUFFIX_PATTERN.test(trimmed) ? trimmed : `${trimmed}Z`;
  const date = new Date(normalized);
  return Number.isNaN(date.getTime()) ? null : date;
}

export function formatDateTime(
  timestamp: string | null,
  options: { locale?: string; timeZone?: string } = {},
): string {
  const date = parseUtcTimestamp(timestamp);
  if (!timestamp) return "Not scheduled";
  if (!date) return "Invalid date";
  const parts = new Intl.DateTimeFormat(options.locale, {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
    timeZone: options.timeZone,
    timeZoneName: "shortOffset",
  }).formatToParts(date);
  const value = (type: Intl.DateTimeFormatPartTypes) => parts.find((part) => part.type === type)?.value ?? "";
  const zone = value("timeZoneName");
  return `${value("year")}-${value("month")}-${value("day")} ${value("hour")}:${value("minute")}:${value(
    "second",
  )}${zone ? ` ${zone}` : ""}`;
}

export function formatCountdown(targetTimestamp: string | null, now: Date = new Date()): string {
  if (!targetTimestamp) return "No scheduled test";
  const target = parseUtcTimestamp(targetTimestamp);
  if (!target) return "Invalid scheduled time";
  const seconds = Math.max(0, Math.ceil((target.getTime() - now.getTime()) / 1000));
  if (seconds === 0) return "Due now";
  return `${formatDuration(seconds)} remaining`;
}

export function formatPercentage(value: number | null): string {
  if (value === null || !Number.isFinite(value)) return "Not available";
  return `${Math.round(value * 100)}%`;
}
