import Link from "next/link";
import { notFound } from "next/navigation";

import { Avatar } from "@/components/Avatar";
import { BrandBar } from "@/components/BrandBar";
import { ColorChip } from "@/components/ColorChip";
import { Pill, SendPill } from "@/components/Pill";
import { SectionHead } from "@/components/SectionHead";
import { StatTile } from "@/components/StatTile";
import { fmtInt, fmtNumber, formatAge } from "@/lib/format";
import {
  COLOR_SWATCHES,
  DEFAULT_GYM,
  lookupGrade,
} from "@/lib/gym";
import { climber, climberAttempts, type ClimberAttemptRow } from "@/lib/queries";

export const dynamic = "force-dynamic";

interface PageProps {
  params: Promise<{ climberId: string }>;
}

export default async function ClimberPage({ params }: PageProps) {
  const { climberId: raw } = await params;
  const climberId = Number(raw);
  if (!Number.isFinite(climberId) || climberId <= 0) notFound();

  const c = await climber(climberId);
  if (!c) notFound();

  const rows = await climberAttempts(climberId);
  const sends = Number(c.sends ?? 0);
  const attempts = Number(c.attempts_logged ?? 0);
  const fastest = c.fastest_send_seconds;
  const pyramid = pyramidData(rows);

  return (
    <div className="app-shell">
      <BrandBar active="climber" />
      <Link href="/" className="back-link">
        ‹ back to feed
      </Link>

      <div className="amber-panel" style={{ padding: "20px 16px 16px", marginBottom: 14 }}>
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 14,
            marginBottom: 14,
          }}
        >
          <Avatar name={c.name} size={64} />
          <div>
            <div
              style={{
                fontFamily: "var(--font)",
                fontSize: 22,
                fontWeight: 800,
                letterSpacing: "-0.025em",
                lineHeight: 1.1,
                color: "var(--ink)",
              }}
            >
              {c.name}
            </div>
            <div
              style={{
                fontFamily: "var(--font)",
                fontSize: 12,
                color: "var(--muted)",
                fontWeight: 600,
                marginTop: 2,
              }}
            >
              indoor boulderer · {DEFAULT_GYM.toLowerCase()}
            </div>
            <div
              style={{
                marginTop: 6,
                display: "flex",
                gap: 6,
                flexWrap: "wrap",
              }}
            >
              <Pill size="sm" tone="amber">⌃ {sends * 17} kudos</Pill>
              <Pill size="sm" tone="neutral">personal best</Pill>
            </div>
          </div>
        </div>
        <div
          className="stat-grid"
          style={{
            gridTemplateColumns: "repeat(3, 1fr)",
            borderRadius: 18,
            border: "1px solid var(--hairline)",
          }}
        >
          <div className="tile">
            <StatTile value={fmtInt(sends, "0")} label="sends · 30d" big />
          </div>
          <div className="tile">
            <StatTile value={fmtInt(attempts, "0")} label="attempts" big />
          </div>
          <div className="tile">
            <StatTile
              value={fmtNumber(fastest, 1, "—")}
              label="fastest send"
              unit={fastest != null ? "s" : undefined}
              big
            />
          </div>
        </div>
      </div>

      <SectionHead action="all time">grade pyramid · 30d</SectionHead>
      <div className="card pyramid">
        {pyramid.map((d) => {
          const swatch = COLOR_SWATCHES[d.color] ?? "#888";
          const pct = d.max ? (d.n / d.max) * 100 : 0;
          return (
            <div className="row" key={d.grade}>
              <div className="label">
                <ColorChip color={d.color} size={12} />
                {d.grade}
              </div>
              <div className="bar">
                <div
                  className="fill"
                  style={{
                    width: `${pct.toFixed(0)}%`,
                    background: `linear-gradient(180deg, ${swatch}DD, ${swatch})`,
                  }}
                />
              </div>
              <div className="n">{d.n}</div>
            </div>
          );
        })}
      </div>

      <SectionHead>recent climbs</SectionHead>
      {rows.length === 0 ? (
        <div className="alert">No climbs logged yet.</div>
      ) : (
        <div className="row-list">
          {rows.map((r) => {
            const grade = lookupGrade(r.route_color)?.grade ?? "—";
            const gym = (r.gym_name ?? "—").toLowerCase();
            const age = formatAge(r.posted_at);
            const timeStr =
              r.time_seconds != null ? `${r.time_seconds.toFixed(1)}s` : "—";
            return (
              <Link
                key={r.attempt_id}
                className="row"
                href={`/post/${r.attempt_id}`}
              >
                <ColorChip color={r.route_color} size={18} />
                <div className="body">
                  <div className="t">
                    {grade} · climb #{r.attempt_id}
                  </div>
                  <div className="s">
                    {age} · {gym}
                  </div>
                </div>
                <div className="time">{timeStr}</div>
                <SendPill sent={!!r.send} />
              </Link>
            );
          })}
        </div>
      )}
    </div>
  );
}

interface PyramidRow {
  grade: string;
  color: string;
  n: number;
  max: number;
}

function pyramidData(rows: ClimberAttemptRow[]): PyramidRow[] {
  const gradeRows: { grade: string; color: string }[] = [
    { grade: "V7-V8", color: "black" },
    { grade: "V6-V7", color: "purple" },
    { grade: "V5-V6", color: "red" },
    { grade: "V4-V5", color: "blue" },
    { grade: "V3-V4", color: "green" },
    { grade: "V1",    color: "yellow" },
  ];
  const counts: Record<string, number> = {};
  for (const g of gradeRows) counts[g.grade] = 0;
  for (const r of rows) {
    const g = lookupGrade(r.route_color);
    if (g && counts[g.grade] !== undefined) counts[g.grade] += 1;
  }
  const max = Math.max(1, ...Object.values(counts));
  return gradeRows.map((g) => ({ ...g, n: counts[g.grade], max }));
}
