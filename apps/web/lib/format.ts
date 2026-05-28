export function formatAge(posted: Date | string | null | undefined): string {
  if (!posted) return "";
  const d = typeof posted === "string" ? new Date(posted) : posted;
  if (isNaN(d.getTime())) return "";
  const secs = Math.floor((Date.now() - d.getTime()) / 1000);
  if (secs < 60) return "just now";
  if (secs < 3600) return `${Math.floor(secs / 60)}m ago`;
  if (secs < 86400) return `${Math.floor(secs / 3600)}h ago`;
  return `${Math.floor(secs / 86400)}d ago`;
}

export function fmtNumber(
  v: number | null | undefined,
  digits: number = 1,
  fallback: string = "—",
): string {
  if (v === null || v === undefined || Number.isNaN(v)) return fallback;
  return Number(v).toFixed(digits);
}

export function fmtInt(
  v: number | null | undefined,
  fallback: string = "—",
): string {
  if (v === null || v === undefined || Number.isNaN(v)) return fallback;
  return String(Math.round(Number(v)));
}

export function initials(name: string | null | undefined): string {
  if (!name) return "?";
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return "?";
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}

export function hueFor(name: string | null | undefined): number {
  const s = name ?? "?";
  let sum = 0;
  for (let i = 0; i < s.length; i++) sum += s.charCodeAt(i);
  return sum % 360;
}

/** Mirror of strava_climbing.titles.display_title for feed/post titles. */
export function activityTitle(row: {
  title?: string | null;
  send?: boolean | null;
  route_color?: string | null;
  climber_name?: string | null;
}, gradeLabel?: string | null): string {
  if (row.title && row.title.trim()) return row.title;
  const verb = row.send ? "Sent" : "Worked";
  const color = (row.route_color ?? "").trim();
  const colorTitle = color ? color[0].toUpperCase() + color.slice(1) : "Boulder";
  const grade = gradeLabel ? ` · ${gradeLabel}` : "";
  return `${verb} ${colorTitle}${grade}`;
}
