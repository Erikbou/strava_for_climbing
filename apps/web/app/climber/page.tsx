import Link from "next/link";

import { Avatar } from "@/components/Avatar";
import { BrandBar } from "@/components/BrandBar";
import { climbers } from "@/lib/queries";

export const dynamic = "force-dynamic";

export default async function ClimberPickerPage() {
  const list = await climbers();
  return (
    <div className="app-shell">
      <BrandBar active="climber" />
      <h1 className="page-h1">climbers</h1>
      <div className="page-sub">
        pick a climber to see their profile, grade pyramid, and recent sends.
      </div>

      {list.length === 0 ? (
        <div
          className="amber-panel"
          style={{ textAlign: "center", padding: "28px 18px" }}
        >
          <div className="eyebrow">no climbers yet</div>
          <div className="title" style={{ marginTop: 6 }}>
            upload your first clip
          </div>
          <div style={{ fontSize: 12, color: "var(--ink-2)", marginTop: 6 }}>
            every uploaded climber gets a profile auto-generated.
          </div>
        </div>
      ) : (
        <div className="climbers-grid">
          {list.map((c) => {
            const sends = Number(c.sends ?? 0);
            const attempts = Number(c.attempts_logged ?? 0);
            const meta = `${sends} send${sends !== 1 ? "s" : ""} · ${attempts} attempt${attempts !== 1 ? "s" : ""}`;
            const pin =
              c.fastest_send_seconds != null
                ? `${c.fastest_send_seconds.toFixed(1)}s`
                : "—";
            return (
              <Link
                key={c.id}
                href={`/climber/${c.id}`}
                className="climber-tile"
              >
                <Avatar name={c.name} size={44} />
                <div className="meta">
                  <div className="n">{c.name}</div>
                  <div className="s">{meta}</div>
                </div>
                <div className="pin">{pin}</div>
              </Link>
            );
          })}
        </div>
      )}
    </div>
  );
}
