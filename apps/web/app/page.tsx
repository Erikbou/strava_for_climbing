import Link from "next/link";

import { Avatar } from "@/components/Avatar";
import { BrandBar } from "@/components/BrandBar";
import { Chumbox } from "@/components/Chumbox";
import { ColorChip, GradeBadge } from "@/components/ColorChip";
import { HeroVideo } from "@/components/HeroVideo";
import { LikeButton } from "@/components/LikeButton";
import { SendPill } from "@/components/Pill";
import { StatTile } from "@/components/StatTile";
import { activityTitle, fmtInt, fmtNumber, formatAge } from "@/lib/format";
import { DEFAULT_GYM, lookupGrade } from "@/lib/gym";
import { feed, kudosCounts, myKudos, type FeedRow } from "@/lib/queries";
import { sessionId } from "@/lib/session";
import { videoSrcFor } from "@/lib/media";

type Scope = "following" | "my gym" | "kc akalla" | "global";
type Mode = "cards" | "list";

interface PageProps {
  searchParams: Promise<{ scope?: string; mode?: string }>;
}

export const dynamic = "force-dynamic";

export default async function FeedPage({ searchParams }: PageProps) {
  const sp = await searchParams;
  const scope: Scope = (["following", "my gym", "kc akalla", "global"].includes(sp.scope ?? "")
    ? sp.scope
    : "following") as Scope;
  const mode: Mode = sp.mode === "list" ? "list" : "cards";

  const rows = await feed();
  const ids = rows.map((r) => r.attempt_id);
  const sid = await sessionId();
  const [counts, liked] = await Promise.all([
    kudosCounts(ids),
    myKudos(ids, sid),
  ]);

  const scopeCounts = {
    following: Math.min(rows.length, 12),
    "my gym": rows.filter((r) => (r.gym_name ?? "") === DEFAULT_GYM).length,
    "kc akalla": rows.filter((r) =>
      (r.gym_name ?? "").toLowerCase().startsWith("klätter"),
    ).length,
    global: rows.length,
  } as const;

  const fastest = rows.find((r) => r.send);
  const fastestColor = fastest?.route_color ?? "red";
  const fastestTime = fastest?.time_seconds
    ? `${fastest.time_seconds.toFixed(1)}s`
    : "—";
  const contenders = fastest
    ? rows.filter((r) => r.route_color === fastestColor).slice(0, 4)
    : [];
  const extra = fastest ? Math.max(0, rows.length - contenders.length) : 0;

  return (
    <div className="app-shell">
      <BrandBar active="feed" />

      <div className="filter-row">
        {(
          [
            ["following", "following"],
            ["my gym", "my gym"],
            ["kc akalla", "kc akalla"],
            ["global", "global"],
          ] as [Scope, string][]
        ).map(([key, label]) => {
          const on = scope === key;
          const n = scopeCounts[key];
          const disp = n >= 1000 ? `${(n / 1000).toFixed(1)}k` : String(n);
          const href = `/?mode=${mode}&scope=${encodeURIComponent(key)}`;
          return (
            <Link key={key} href={href} className={`fp ${on ? "on" : ""}`.trim()}>
              {label}
              <span className="n">{disp}</span>
            </Link>
          );
        })}
      </div>

      {fastest ? (
        <div className="amber-panel" style={{ marginBottom: 14 }}>
          <div className="eyebrow">today · {fastestColor} wall</div>
          <div className="title">
            {contenders.length} climbers chasing {fastestTime}
          </div>
          <div className="ava-stack">
            {contenders.map((c) => (
              <Avatar key={c.attempt_id} name={c.climber_name} size={28} />
            ))}
            {extra > 0 ? <span className="more">+ {extra} more</span> : null}
          </div>
        </div>
      ) : null}

      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 10,
          margin: "14px 0 8px",
        }}
      >
        <div
          style={{
            fontFamily: "var(--font)",
            fontSize: "10.5px",
            fontWeight: 700,
            letterSpacing: "0.12em",
            textTransform: "uppercase",
            color: "var(--muted)",
          }}
        >
          {scope} · recent climbs
        </div>
        <div style={{ flex: 1, height: 1, background: "var(--hairline)" }} />
        <div className="seg">
          <Link
            className={mode === "cards" ? "on" : ""}
            href={`/?mode=cards&scope=${encodeURIComponent(scope)}`}
          >
            cards
          </Link>
          <Link
            className={mode === "list" ? "on" : ""}
            href={`/?mode=list&scope=${encodeURIComponent(scope)}`}
          >
            list
          </Link>
        </div>
      </div>

      {rows.length === 0 ? (
        <div className="amber-panel" style={{ textAlign: "center", padding: "28px 18px" }}>
          <div className="eyebrow">your feed is empty</div>
          <div className="title" style={{ marginTop: 6 }}>
            drop your first clip
          </div>
          <div style={{ fontSize: 12, color: "var(--ink-2)", marginTop: 6 }}>
            tap <strong>+ upload</strong> up top — we&apos;ll detect pose, time the
            send, score smoothness, and cut a highlight.
          </div>
        </div>
      ) : mode === "list" ? (
        <FeedList rows={rows} counts={counts} liked={liked} />
      ) : (
        <FeedCards rows={rows} counts={counts} liked={liked} />
      )}
    </div>
  );
}

function FeedCards({
  rows,
  counts,
  liked,
}: {
  rows: FeedRow[];
  counts: Record<number, number>;
  liked: Set<number>;
}) {
  const cards: React.ReactNode[] = [];
  cards.push(<Chumbox key="chum-0" slot={0} />);
  rows.forEach((r, i) => {
    cards.push(<FeedCard key={r.attempt_id} row={r} kudos={counts[r.attempt_id] ?? 0} isLiked={liked.has(r.attempt_id)} />);
    if ((i + 1) % 2 === 0) {
      cards.push(<Chumbox key={`chum-${i + 1}`} slot={Math.floor(i / 2) + 1} />);
    }
  });
  return <>{cards}</>;
}

function FeedCard({
  row,
  kudos,
  isLiked,
}: {
  row: FeedRow;
  kudos: number;
  isLiked: boolean;
}) {
  const climber = row.climber_name ?? "Unknown climber";
  const gym = row.gym_name ?? "Unknown gym";
  const age = formatAge(row.posted_at);
  const grade = lookupGrade(row.route_color)?.grade ?? null;
  const title = activityTitle(row, grade);
  const first = climber.split(" ")[0] || "—";
  const timeStr = row.time_seconds != null ? `${row.time_seconds.toFixed(1)}s` : "—";
  const src = videoSrcFor(row.highlight_path);
  return (
    <div className="card">
      <div className="card-head">
        <Avatar name={climber} size={36} />
        <div className="meta">
          <div className="name">{climber}</div>
          <div className="sub">
            {age} · {gym}
          </div>
        </div>
        <SendPill sent={!!row.send} />
      </div>
      <div className="card-title">{title}</div>
      <div className="card-chips">
        <GradeBadge color={row.route_color} />
      </div>
      <HeroVideo
        src={src}
        climber={first}
        timeLabel={timeStr}
        sent={!!row.send}
        label="highlight"
        height={300}
      />
      <div className="stat-row">
        <div className="tile">
          <StatTile value={fmtNumber(row.time_seconds, 1)} label="time" unit="s" />
        </div>
        <div className="tile">
          <StatTile value={fmtNumber(row.smoothness_pct, 0)} label="smooth" />
        </div>
        <div className="tile">
          <StatTile value={fmtInt(row.dynamic_moves)} label="dyno" />
        </div>
        <div className="tile">
          <StatTile value={fmtNumber(row.hang_time_seconds, 1)} label="hang" unit="s" />
        </div>
      </div>
      <div className="card-foot">
        <LikeButton attemptId={row.attempt_id} initialCount={kudos} initialLiked={isLiked} />
        <Link href={`/post/${row.attempt_id}`} className="open">
          open ›
        </Link>
      </div>
    </div>
  );
}

function FeedList({
  rows,
  counts,
  liked,
}: {
  rows: FeedRow[];
  counts: Record<number, number>;
  liked: Set<number>;
}) {
  const ranked = [...rows].sort(
    (a, b) => (counts[b.attempt_id] ?? 0) - (counts[a.attempt_id] ?? 0),
  );
  return (
    <div className="hn">
      {ranked.map((r, i) => {
        const grade = lookupGrade(r.route_color)?.grade ?? "—";
        const title = activityTitle(r, grade);
        const climber = r.climber_name ?? "Unknown climber";
        const gym = (r.gym_name ?? "Unknown gym").toLowerCase();
        const age = formatAge(r.posted_at);
        const timeStr = r.time_seconds != null ? `${r.time_seconds.toFixed(1)}s` : "—";
        const rank = i + 1;
        const topCls = rank <= 3 ? ` top${rank}` : "";
        return (
          <div key={r.attempt_id} className={`hn-row${topCls}`}>
            <Link href={`/post/${r.attempt_id}`} className="rank">
              {rank}.
            </Link>
            <Link href={`/post/${r.attempt_id}`}>
              <ColorChip color={r.route_color} size={14} />
            </Link>
            <Link href={`/post/${r.attempt_id}`} style={{ textDecoration: "none", color: "inherit" }}>
              <div className="title">
                {title}
                <span className="grade-inline">{grade}</span>
              </div>
              <div className="meta">
                by{" "}
                {r.climber_id != null ? (
                  <Link
                    href={`/climber/${r.climber_id}`}
                    className="who"
                    style={{ color: "inherit", textDecoration: "none" }}
                  >
                    {climber.toLowerCase()}
                  </Link>
                ) : (
                  <span className="who">{climber.toLowerCase()}</span>
                )}{" "}
                · {gym} · {age} · <span className="mono">{timeStr}</span>
              </div>
            </Link>
            <div className="right">
              <LikeButton
                attemptId={r.attempt_id}
                initialCount={counts[r.attempt_id] ?? 0}
                initialLiked={liked.has(r.attempt_id)}
              />
              <SendPill sent={!!r.send} />
            </div>
          </div>
        );
      })}
    </div>
  );
}
