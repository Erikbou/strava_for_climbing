"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { SendPill } from "./Pill";

interface HeroVideoProps {
  src: string | null;
  climber: string;
  timeLabel: string;
  sent: boolean | null;
  label?: string;
  height?: number;
}

export function HeroVideo({
  src,
  climber,
  timeLabel,
  sent,
  label = "highlight",
  height = 300,
}: HeroVideoProps) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const [open, setOpen] = useState(false);

  const close = useCallback(() => {
    setOpen(false);
  }, []);

  useEffect(() => {
    if (!open) return;
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") close();
    }
    document.addEventListener("keydown", onKey);
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = "";
    };
  }, [open, close]);

  const pop = useCallback(() => {
    if (videoRef.current) {
      try {
        videoRef.current.pause();
      } catch {
        /* noop */
      }
    }
    setOpen(true);
  }, []);

  return (
    <>
      <div className="hero" style={{ height }}>
        {src ? (
          <video
            ref={videoRef}
            preload="metadata"
            muted
            playsInline
            controls
            onDoubleClick={pop}
            style={{
              height: `${height}px`,
              width: "100%",
              objectFit: "cover",
              background: "#1A1A1A",
            }}
          >
            <source src={src} type="video/mp4" />
          </video>
        ) : (
          <div style={{ height: `${height}px`, background: "#1A1A1A" }} />
        )}
        <div className="overlay-top">
          <span className="glass">
            <span className="live" />
            {climber} · <span className="mono">{timeLabel}</span>
          </span>
          {sent === true ? <SendPill sent /> : sent === false ? <SendPill sent={false} /> : null}
        </div>
        <div className="overlay-bot">
          <span className="glass">
            <span className="caps">{label}</span>
          </span>
          <span className="glass">
            ▶ <span className="mono">0:00 / {timeLabel}</span>
          </span>
        </div>
        <button type="button" className="play" aria-label="open fullscreen" onClick={pop}>
          ▶
        </button>
      </div>

      {open && src ? (
        <div className="artemis-modal">
          <div className="artemis-modal-backdrop" onClick={close} />
          <div className="artemis-modal-frame">
            <button
              type="button"
              className="artemis-modal-close"
              aria-label="close"
              onClick={close}
            >
              ×
            </button>
            <video
              className="artemis-modal-video"
              controls
              autoPlay
              playsInline
              src={src}
            />
          </div>
        </div>
      ) : null}
    </>
  );
}
