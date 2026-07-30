export function ProgressMeter({ label, value, total }: { label: string; value: number; total: number }) {
  const safeTotal = Math.max(total, 0);
  const safeValue = Math.min(Math.max(value, 0), safeTotal);
  const percent = safeTotal > 0 ? Math.round((safeValue / safeTotal) * 100) : 0;
  return (
    <div className="meter-block">
      <div className="meter-label">
        <span>{label}</span>
        <span>
          {safeValue} / {safeTotal}
        </span>
      </div>
      <div className="meter-track" aria-hidden="true">
        <div className="meter-fill" style={{ width: `${percent}%` }} />
      </div>
    </div>
  );
}
