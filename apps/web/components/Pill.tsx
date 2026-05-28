import type { ReactNode } from "react";

type Tone = "send" | "attempt" | "amber" | "neutral" | "ink";
type Size = "sm" | "md" | "lg";

export function Pill({
  children,
  tone = "neutral",
  size = "md",
}: {
  children: ReactNode;
  tone?: Tone;
  size?: Size;
}) {
  return <span className={`pill ${size} ${tone}`}>{children}</span>;
}

export function SendPill({ sent }: { sent: boolean }) {
  if (sent) {
    return (
      <span className="pill md send">
        <span className="dot" />
        Send
      </span>
    );
  }
  return <span className="pill md attempt">Attempt</span>;
}
