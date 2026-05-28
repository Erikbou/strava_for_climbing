import Link from "next/link";

type Nav = "feed" | "leaderboards" | "profile" | "upload" | "post" | "climber";

const NAV_ITEMS: { key: Nav; label: string; href: string; img?: string }[] = [
  { key: "feed", label: "feed", href: "/", img: "/nav/feed_button.png" },
  { key: "leaderboards", label: "boards", href: "/leaderboards", img: "/nav/boards_button.png" },
  { key: "profile", label: "profile", href: "/climber", img: "/nav/profile_button.png" },
];

export function BrandBar({ active }: { active: Nav }) {
  const navView: Nav =
    active === "feed" || active === "leaderboards" || active === "profile"
      ? active
      : active === "climber"
        ? "profile"
        : "feed";

  return (
    <div className="brand-row">
      <div className="artemis-mark">
        <Link href="/" aria-label="artemis">
          {/* Wordmark — falls back to a styled text mark if asset missing. */}
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src="/artemis-wordmark.jpeg" alt="artemis" />
        </Link>
      </div>
      <nav className="nav-holds" aria-label="primary">
        {NAV_ITEMS.map((item) => {
          const on = navView === item.key;
          return (
            <Link
              key={item.key}
              href={item.href}
              className={`nav-hold ${on ? "on" : ""}`.trim()}
              aria-label={item.label}
            >
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src={item.img ?? "/nav/feed_button.png"} alt={item.label} />
            </Link>
          );
        })}
      </nav>
      <div>
        {active === "upload" ? (
          <span className="brand-cta disabled">uploading</span>
        ) : (
          <Link href="/upload" className="brand-cta">
            + upload
          </Link>
        )}
      </div>
    </div>
  );
}
