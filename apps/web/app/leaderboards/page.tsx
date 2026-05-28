import Link from "next/link";

import { Avatar } from "@/components/Avatar";
import { BrandBar } from "@/components/BrandBar";
import { ColorChip } from "@/components/ColorChip";
import { SectionHead } from "@/components/SectionHead";
import { currentUser } from "@/lib/auth";
import { lookupGrade } from "@/lib/gym";
import { feed, type FeedRow } from "@/lib/queries";

export const dynamic = "force-dynamic";

const MEDALS = ["", "🥇", "🥈", "🥉"];

export default async function LeaderboardsPage() {
  const [user, rows] = await Promise.all([currentUser(), feed()]);
  const sends = rows
    .filter((r) => r.send && r.time_seconds != null)
    .sort((a, b) => (a.time_seconds ?? 0) - (b.time_seconds ?? 0));
  const colorsWithSends = new Set(sends.map((r) => r.route_color ?? "—"));

  return (
    <div className="app-shell">
      <BrandBar active="leaderboards" user={user} />
      <h1 className="page-h1">leaderboards</h1>
      <div className="page-sub">
        {sends.length} sends across {colorsWithSends.size}{" "}
        route{colorsWithSends.size !== 1 ? "s" : ""} — fastest first, updated as
        climbs come in.
      </div>

      {sends.length === 0 ? (
        <div
          className="amber-panel"
          style={{ textAlign: "center", padding: "32px 18px" }}
        >
          <div className="eyebrow">no sends logged yet</div>
          <div className="title" style={{ marginTop: 6 }}>
            be the first one up
          </div>
          <div style={{ fontSize: 12, color: "var(--ink-2)", marginTop: 6 }}>
            upload a clip of a clean topout — fastest time per route claims #1.
          </div>
        </div>
      ) : (
        <>
          <Podium top3={sends.slice(0, 3)} />

          <PerRouteBoards rows={sends} />
        </>
      )}
    </div>
  );
}

function Podium({ top3 }: { top3: FeedRow[] }) {
  const padded: (FeedRow | null)[] = [top3[0] ?? null, top3[1] ?? null, top3[2] ?? null];
  // Render order: #2 left, #1 centre taller, #3 right (classic Olympic podium).
  const order: { rank: 1 | 2 | 3; row: FeedRow | null }[] = [
    { rank: 2, row: padded[1] },
    { rank: 1, row: padded[0] },
    { rank: 3, row: padded[2] },
  ];
  const leader = padded[0];
  const title = leader?.climber_name ?? "—";
  const fastest = leader?.time_seconds
    ? `${leader.time_seconds.toFixed(1)}s`
    : "—";

  return (
    <div className="podium-wrap">
      <div className="eyebrow">fastest sends · top 3</div>
      <div className="super-title">
        {title} leads · {fastest}
      </div>
      <div className="podium-row">
        {order.map(({ rank, row }) =>
          row ? <PodiumCol key={rank} rank={rank} row={row} /> : <EmptyCol key={rank} rank={rank} />,
        )}
      </div>
    </div>
  );
}

function PodiumCol({ rank, row }: { rank: 1 | 2 | 3; row: FeedRow }) {
  const name = row.climber_name ?? "Unknown";
  const first = name.split(" ")[0] || "—";
  const grade = lookupGrade(row.route_color)?.grade ?? "—";
  const time = (row.time_seconds ?? 0).toFixed(1);
  const avaSize = rank === 1 ? 56 : 44;
  return (
    <Link className={`podium-col rank-${rank}`} href={`/post/${row.attempt_id}`}>
      <div className="medal">{MEDALS[rank]}</div>
      <Avatar name={name} size={avaSize} />
      <div className="name">{first}</div>
      <div className="time">
        {time}
        <span className="u">s</span>
      </div>
      <div className="grade-row">
        <ColorChip color={row.route_color} size={12} />
        <span>{grade}</span>
      </div>
    </Link>
  );
}

function EmptyCol({ rank }: { rank: 1 | 2 | 3 }) {
  return (
    <div className={`podium-col rank-${rank} empty`}>
      <div className="medal" style={{ opacity: 0.5 }}>
        {MEDALS[rank]}
      </div>
      <div
        style={{
          fontSize: 12,
          fontWeight: 700,
          color: "var(--muted)",
          letterSpacing: "0.04em",
          textTransform: "uppercase",
        }}
      >
        open slot
      </div>
    </div>
  );
}

function PerRouteBoards({ rows }: { rows: FeedRow[] }) {
  const byColor = new Map<string, FeedRow[]>();
  for (const r of rows) {
    const c = r.route_color ?? "—";
    if (!byColor.has(c)) byColor.set(c, []);
    byColor.get(c)!.push(r);
  }
  const sortedColors = [...byColor.keys()].sort(
    (a, b) => (byColor.get(a)![0].time_seconds ?? 0) - (byColor.get(b)![0].time_seconds ?? 0),
  );

  return (
    <>
      <SectionHead>per-route boards</SectionHead>
      {sortedColors.map((color) => (
        <PerRouteCard key={color} color={color} entries={byColor.get(color)!.slice(0, 5)} />
      ))}
    </>
  );
}

function PerRouteCard({ color, entries }: { color: string; entries: FeedRow[] }) {
  const g = lookupGrade(color);
  const grade = g?.grade ?? "—";
  const label = (g?.label ?? "").toLowerCase();
  return (
    <div className="lb-card">
      <div className="head">
        <ColorChip color={color} size={16} />
        <div className="title">
          {color} · {grade}
        </div>
        <span className="label">{label}</span>
        <span className="right">top {entries.length}</span>
      </div>
      {entries.map((r, i) => {
        const rank = i + 1;
        const topCls = rank <= 3 ? ` top${rank}` : "";
        const name = r.climber_name ?? "Unknown";
        const parts = name.split(" ");
        const first = parts[0] || "—";
        const last = parts.slice(1).join(" ");
        const t = `${(r.time_seconds ?? 0).toFixed(1)}s`;
        return (
          <Link key={r.attempt_id} className={`lb-row${topCls}`} href={`/post/${r.attempt_id}`}>
            <div className="rank">{rank}.</div>
            <Avatar name={name} size={24} />
            <div className="who">
              {first}
              {last ? <span className="last">{last}</span> : null}
            </div>
            <div className="t">{t}</div>
          </Link>
        );
      })}
    </div>
  );
}
