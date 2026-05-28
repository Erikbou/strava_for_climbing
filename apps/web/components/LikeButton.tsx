"use client";

import { useState, useTransition } from "react";

interface LikeButtonProps {
  attemptId: number;
  initialCount: number;
  initialLiked: boolean;
}

export function LikeButton({ attemptId, initialCount, initialLiked }: LikeButtonProps) {
  const [count, setCount] = useState(initialCount);
  const [liked, setLiked] = useState(initialLiked);
  const [pending, startTransition] = useTransition();

  function toggle() {
    startTransition(async () => {
      const optimisticLiked = !liked;
      setLiked(optimisticLiked);
      setCount((c) => c + (optimisticLiked ? 1 : -1));
      try {
        const res = await fetch("/api/kudos", {
          method: "POST",
          headers: { "content-type": "application/json" },
          body: JSON.stringify({ attemptId }),
        });
        if (!res.ok) throw new Error("kudos failed");
        const data = (await res.json()) as { count: number };
        setCount(data.count);
      } catch {
        // Revert on failure — kudos are best-effort.
        setLiked(!optimisticLiked);
        setCount((c) => c + (optimisticLiked ? -1 : 1));
      }
    });
  }

  return (
    <button
      type="button"
      className={`like ${liked ? "on" : ""}`.trim()}
      aria-label={liked ? `unlike climb ${attemptId}` : `like climb ${attemptId}`}
      onClick={toggle}
      disabled={pending}
    >
      <span className="heart">{liked ? "♥" : "♡"}</span>
      <span className="n">{count}</span>
    </button>
  );
}
