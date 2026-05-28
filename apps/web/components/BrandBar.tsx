import Link from "next/link";

import type { User } from "@/lib/auth";

import { AccountMenu } from "./AccountMenu";

type Nav = "feed" | "leaderboards" | "profile" | "upload" | "post" | "climber" | "auth";

const NAV_ITEMS: { key: Nav; label: string; href: string; img?: string }[] = [
  { key: "feed", label: "feed", href: "/", img: "/nav/feed_button.png" },
  { key: "leaderboards", label: "boards", href: "/leaderboards", img: "/nav/boards_button.png" },
  { key: "profile", label: "profile", href: "/climber", img: "/nav/profile_button.png" },
];

interface BrandBarProps {
  active: Nav;
  user: User | null;
}

export function BrandBar({ active, user }: BrandBarProps) {
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
          // Signed-in users land directly on their own profile; signed-out
          // users see the picker.
          const href =
            item.key === "profile" && user ? "/climber/me" : item.href;
          return (
            <Link
              key={item.key}
              href={href}
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
        {!user ? (
          <Link href="/sign-in" className="brand-cta">
            sign in
          </Link>
        ) : active === "upload" ? (
          <span className="brand-cta disabled">uploading</span>
        ) : (
          <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
            <Link
              href="/upload"
              className="brand-cta"
              style={{ flex: 1, padding: "0 12px", height: 32 }}
            >
              + upload
            </Link>
            <AccountMenu user={user} />
          </div>
        )}
      </div>
    </div>
  );
}
