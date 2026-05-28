interface StatTileProps {
  value: string;
  label: string;
  unit?: string;
  big?: boolean;
}

export function StatTile({ value, label, unit, big }: StatTileProps) {
  return (
    <div className={`stat-tile ${big ? "big" : ""}`.trim()}>
      <div className="value">
        {value}
        {unit ? <span className="u">{unit}</span> : null}
      </div>
      <div className="label">{label}</div>
    </div>
  );
}
