"use client";

import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";

type Mode = "sign-in" | "sign-up";

interface AuthFormProps {
  mode: Mode;
  next?: string;
}

export function AuthForm({ mode, next = "/" }: AuthFormProps) {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, startSubmit] = useTransition();

  function submit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError(null);
    startSubmit(async () => {
      try {
        const url = mode === "sign-up" ? "/api/auth/register" : "/api/auth/login";
        const body =
          mode === "sign-up" ? { email, password, displayName } : { email, password };
        const res = await fetch(url, {
          method: "POST",
          headers: { "content-type": "application/json" },
          body: JSON.stringify(body),
        });
        if (!res.ok) {
          const data = (await res.json().catch(() => ({}))) as { error?: string };
          throw new Error(data.error ?? `request failed (${res.status})`);
        }
        router.push(next);
        router.refresh();
      } catch (err) {
        setError(err instanceof Error ? err.message : String(err));
      }
    });
  }

  return (
    <form onSubmit={submit} className="form-card">
      {mode === "sign-up" ? (
        <div className="field">
          <label>display name</label>
          <input
            value={displayName}
            onChange={(e) => setDisplayName(e.target.value)}
            placeholder="e.g. niklavs visockis"
            autoComplete="name"
            required
          />
        </div>
      ) : null}
      <div className="field">
        <label>email</label>
        <input
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          autoComplete="email"
          required
        />
      </div>
      <div className="field">
        <label>password</label>
        <input
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          autoComplete={mode === "sign-up" ? "new-password" : "current-password"}
          minLength={8}
          required
        />
      </div>
      {error ? <div className="alert error">{error}</div> : null}
      <div style={{ marginTop: 8 }}>
        <button type="submit" className="btn full" disabled={submitting}>
          {submitting
            ? "one sec…"
            : mode === "sign-up"
              ? "create account"
              : "sign in"}
        </button>
      </div>
    </form>
  );
}
