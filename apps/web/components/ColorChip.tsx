import { COLOR_SWATCHES, lookupGrade } from "@/lib/gym";

interface ColorChipProps {
  color: string | null | undefined;
  size?: 12 | 14 | 16 | 18 | 22 | 24;
}

export function ColorChip({ color, size = 16 }: ColorChipProps) {
  const swatch = COLOR_SWATCHES[(color ?? "").toLowerCase()] ?? "#888";
  const cls =
    size === 16
      ? ""
      : `x${size}`;
  return (
    <span
      className={`chip ${cls}`.trim()}
      style={{
        background: `radial-gradient(circle at 35% 28%, rgba(255,255,255,0.75) 0%, rgba(255,255,255,0) 35%), ${swatch}`,
      }}
    />
  );
}

export function GradeBadge({
  color,
  size = "md",
}: {
  color: string | null | undefined;
  size?: "md" | "lg";
}) {
  const g = lookupGrade(color);
  const grade = g?.grade ?? "—";
  const label = (g?.label ?? "").toLowerCase();
  const chipSize = size === "lg" ? 22 : 16;
  return (
    <span className={`grade ${size === "lg" ? "lg" : ""}`}>
      <ColorChip color={color} size={chipSize} />
      <span className="g">{grade}</span>
      <span className="l">{label}</span>
    </span>
  );
}
