"use client";

import { useRouter } from "next/navigation";
import { useEffect, useRef, useState, useTransition } from "react";

import { Avatar } from "./Avatar";
import type { User } from "@/lib/auth";

export function AccountMenu({ user }: { user: User }) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [pending, startTransition] = useTransition();
  const wrapRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    function onDocClick(e: MouseEvent) {
      if (wrapRef.current && !wrapRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") setOpen(false);
    }
    document.addEventListener("mousedown", onDocClick);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDocClick);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  function signOut() {
    startTransition(async () => {
      await fetch("/api/auth/logout", { method: "POST" });
      router.push("/");
      router.refresh();
    });
  }

  return (
    <div ref={wrapRef} style={{ position: "relative" }}>
      <button
        type="button"
        aria-label="account menu"
        onClick={() => setOpen((v) => !v)}
        style={{
          background: "transparent",
          border: "none",
          cursor: "pointer",
          padding: 0,
          display: "block",
          lineHeight: 0,
        }}
      >
        <Avatar name={user.display_name} size={32} />
      </button>
      {open ? (
        <div
          role="menu"
          style={{
            position: "absolute",
            top: "calc(100% + 6px)",
            right: 0,
            minWidth: 200,
            background: "var(--surface)",
            border: "1px solid var(--hairline)",
            borderRadius: 14,
            boxShadow: "var(--shadow-card)",
            zIndex: 100,
            padding: "6px",
            fontFamily: "var(--font)",
          }}
        >
          <div
            style={{
              padding: "8px 10px 6px",
              borderBottom: "1px solid var(--hairline)",
              marginBottom: 4,
            }}
          >
            <div style={{ fontWeight: 700, fontSize: 13, color: "var(--ink)" }}>
              {user.display_name}
            </div>
            <div style={{ fontSize: 11, color: "var(--muted)" }}>{user.email}</div>
          </div>
          <a
            href="/climber/me"
            style={menuItemStyle}
            onClick={() => setOpen(false)}
          >
            your profile
          </a>
          <button
            type="button"
            onClick={signOut}
            disabled={pending}
            style={{ ...menuItemStyle, width: "100%", textAlign: "left", border: "none", background: "transparent", cursor: "pointer" }}
          >
            {pending ? "signing out…" : "sign out"}
          </button>
        </div>
      ) : null}
    </div>
  );
}

const menuItemStyle: React.CSSProperties = {
  display: "block",
  padding: "8px 10px",
  fontSize: 13,
  fontWeight: 600,
  color: "var(--ink)",
  textDecoration: "none",
  borderRadius: 8,
};
