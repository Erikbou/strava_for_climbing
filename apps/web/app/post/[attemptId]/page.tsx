import Link from "next/link";
import { notFound } from "next/navigation";

import { Avatar } from "@/components/Avatar";
import { BrandBar } from "@/components/BrandBar";
import { GradeBadge } from "@/components/ColorChip";
import { HeroVideo } from "@/components/HeroVideo";
import { Pill } from "@/components/Pill";
import { SectionHead } from "@/components/SectionHead";
import { StatTile } from "@/components/StatTile";
import { activityTitle, fmtInt, fmtNumber, formatAge } from "@/lib/format";
import { lookupGrade } from "@/lib/gym";
import { videoSrcFor } from "@/lib/media";
import { attempt } from "@/lib/queries";

export const dynamic = "force-dynamic";

interface PageProps {
  params: Promise<{ attemptId: string }>;
}

export default async function PostPage({ params }: PageProps) {
  const { attemptId: raw } = await params;
  const attemptId = Number(raw);
  if (!Number.isFinite(attemptId) || attemptId <= 0) notFound();

  const a = await attempt(attemptId);
  if (!a) notFound();

  const climber = a.climber_name ?? "Unknown climber";
  const gym = a.gym_name ?? "Unknown gym";
  const age = formatAge(a.posted_at);
  const grade = lookupGrade(a.route_color)?.grade ?? null;
  const title = activityTitle(a, grade);
  const first = climber.split(" ")[0] || "—";
  const timeStr = a.time_seconds != null ? `${a.time_seconds.toFixed(1)}s` : "—";

  const highlightSrc = videoSrcFor(a.highlight_path);
  const overlaySrc = videoSrcFor(a.overlay_path);

  return (
    <div className="app-shell">
      <BrandBar active="post" />
      <Link href="/" className="back-link">
        ‹ back to feed
      </Link>

      {highlightSrc ? (
        <div className="card" style={{ marginBottom: 14 }}>
          <HeroVideo
            src={highlightSrc}
            climber={first}
            timeLabel={timeStr}
            sent={!!a.send}
            label="highlight"
            height={360}
          />
        </div>
      ) : null}

      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 12,
          padding: "0 2px 6px",
          marginBottom: 8,
        }}
      >
        {a.climber_id != null ? (
          <Link
            href={`/climber/${a.climber_id}`}
            style={{
              textDecoration: "none",
              color: "inherit",
              display: "flex",
              alignItems: "center",
              gap: 12,
              flex: 1,
            }}
          >
            <Avatar name={climber} size={44} />
            <div>
              <div
                style={{
                  fontFamily: "var(--font)",
                  fontWeight: 800,
                  fontSize: 16,
                  letterSpacing: "-0.02em",
                  color: "var(--ink)",
                }}
              >
                {climber}
              </div>
              <div
                style={{
                  fontFamily: "var(--font)",
                  fontSize: 12,
                  color: "var(--muted)",
                  fontWeight: 600,
                }}
              >
                {age} · {gym}
              </div>
            </div>
          </Link>
        ) : (
          <>
            <Avatar name={climber} size={44} />
            <div style={{ flex: 1 }}>
              <div style={{ fontWeight: 800, fontSize: 16 }}>{climber}</div>
              <div style={{ fontSize: 12, color: "var(--muted)" }}>
                {age} · {gym}
              </div>
            </div>
          </>
        )}
        <Pill tone="neutral">follow</Pill>
      </div>

      <h1 className="page-h1" style={{ fontSize: "clamp(22px, 6vw, 26px)", margin: "6px 0 10px" }}>
        {title}
      </h1>
      <div
        style={{
          display: "flex",
          gap: 10,
          flexWrap: "wrap",
          alignItems: "center",
          marginBottom: 18,
        }}
      >
        <GradeBadge color={a.route_color} size="lg" />
      </div>

      <SectionHead>stats</SectionHead>
      <div className="stat-grid" style={{ marginBottom: 18 }}>
        <div className="tile">
          <StatTile value={fmtNumber(a.time_seconds, 1)} label="time to top" unit="s" big />
        </div>
        <div className="tile">
          <StatTile value={fmtNumber(a.smoothness_pct, 0)} label="smoothness" big />
        </div>
        <div className="tile">
          <StatTile value={fmtInt(a.dynamic_moves)} label="dyno moves" big />
        </div>
        <div className="tile">
          <StatTile value={fmtNumber(a.longest_reach_px, 0)} label="longest reach" unit="px" big />
        </div>
        <div className="tile">
          <StatTile value={fmtNumber(a.hang_time_seconds, 1)} label="hang · hardest" unit="s" big />
        </div>
        <div className="tile">
          <StatTile value={fmtNumber(a.idle_seconds, 1)} label="idle / rest" unit="s" big />
        </div>
      </div>

      {overlaySrc ? (
        <>
          <SectionHead>full climb · route overlay</SectionHead>
          <div className="card" style={{ marginBottom: 10 }}>
            <HeroVideo
              src={overlaySrc}
              climber={first}
              timeLabel={timeStr}
              sent={!!a.send}
              label={`route overlay · ${timeStr}`}
              height={320}
            />
          </div>
          <div
            style={{
              display: "flex",
              gap: 8,
              margin: "10px 0 6px",
              flexWrap: "wrap",
            }}
          >
            <Pill size="sm" tone="neutral">
              <span className="dot" />
              route overlay on
            </Pill>
            <Pill size="sm" tone="neutral">holds off</Pill>
            <Pill size="sm" tone="neutral">0.5×</Pill>
            <Pill size="sm" tone="neutral">1×</Pill>
            <Pill size="sm" tone="ink">2×</Pill>
          </div>
        </>
      ) : null}

      <SectionHead>movement timeline</SectionHead>
      <div className="card timeline-card">
        <Sparkline />
        <div className="timeline-x">
          <span>0s</span>
          <span>10s</span>
          <span>20s</span>
          <span>30s</span>
          <span>{timeStr}</span>
        </div>
        <div className="move-chips">
          <span className="at">0:04</span>
          <span className="pill sm neutral">start</span>
          <span className="at">0:09</span>
          <span className="pill sm amber">dyno</span>
          <span className="at">0:18</span>
          <span className="pill sm neutral">heel hook</span>
          <span className="at">0:24</span>
          <span className="pill sm neutral">rest 4.1s</span>
          <span className="at">0:33</span>
          <span className="pill sm send">top-out</span>
        </div>
      </div>

      {!highlightSrc && !overlaySrc ? (
        <div className="alert">No video available for this attempt yet.</div>
      ) : null}
    </div>
  );
}

function Sparkline() {
  // Static jerk-over-time sparkline — port of _sparkline_svg() in views.py.
  const pts: [number, number][] = [
    [0, 40], [20, 38], [40, 32], [60, 30], [80, 12],
    [100, 28], [120, 30], [140, 28], [160, 22], [180, 24],
    [200, 30], [220, 40], [240, 38], [260, 18], [280, 24],
    [300, 28], [320, 30],
  ];
  const dLine = "M " + pts.map(([x, y]) => `${x} ${y}`).join(" L ");
  const dArea = `${dLine} L 320 56 L 0 56 Z`;
  return (
    <svg viewBox="0 0 320 56" width="100%" height="56" preserveAspectRatio="none">
      <defs>
        <linearGradient id="sg" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#FF9A1F" stopOpacity={0.25} />
          <stop offset="100%" stopColor="#FF9A1F" stopOpacity={0} />
        </linearGradient>
      </defs>
      <path d={dArea} fill="url(#sg)" />
      <path d={dLine} stroke="#F47A00" strokeWidth={1.6} fill="none" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}
