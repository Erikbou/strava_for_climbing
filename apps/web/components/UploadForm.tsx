"use client";

import { useRef, useState, useTransition } from "react";
import { useRouter } from "next/navigation";

import { COLOR_KEYS, DEFAULT_GYM, lookupGrade } from "@/lib/gym";
import { randomTitle } from "@/lib/titles";

type TitleMode = "auto" | "random" | "custom";

export function UploadForm() {
  const router = useRouter();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [titleMode, setTitleMode] = useState<TitleMode>("auto");
  const [randomName, setRandomName] = useState(() => randomTitle());
  const [customTitle, setCustomTitle] = useState("");
  const [climber, setClimber] = useState("");
  const [color, setColor] = useState(COLOR_KEYS[0]);
  const [gym, setGym] = useState(DEFAULT_GYM);
  const [file, setFile] = useState<File | null>(null);
  const [submitting, startSubmit] = useTransition();
  const [error, setError] = useState<string | null>(null);
  const [warn, setWarn] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);

  const gradePreview = lookupGrade(color, gym);

  function pickFile() {
    fileInputRef.current?.click();
  }

  function onFile(e: React.ChangeEvent<HTMLInputElement>) {
    const f = e.target.files?.[0] ?? null;
    setFile(f);
    if (f && f.size > 25 * 1024 * 1024) {
      setWarn(
        `Your file is ${(f.size / 1024 / 1024).toFixed(0)} MB — large clips are usually >2 min and the tracker fragments. v1 works best on 30–90 second clips of one attempt.`,
      );
    } else {
      setWarn(null);
    }
  }

  function submit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError(null);
    setInfo(null);

    if (!file) return setError("Pick a video file first.");
    if (!climber.trim()) return setError("Climber name is required.");

    const chosenTitle: string | null =
      titleMode === "random"
        ? randomName
        : titleMode === "custom"
          ? customTitle.trim() || null
          : null;

    const fd = new FormData();
    fd.set("file", file);
    fd.set("climber", climber.trim());
    fd.set("color", color);
    fd.set("gym", gym.trim());
    if (chosenTitle) fd.set("title", chosenTitle);

    setInfo("Normalizing video, running pose detection, deriving stats, rendering overlay and highlight…");

    startSubmit(async () => {
      try {
        const res = await fetch("/api/upload", { method: "POST", body: fd });
        if (!res.ok) {
          const data = (await res.json().catch(() => ({}))) as { error?: string };
          throw new Error(data.error ?? `upload failed (${res.status})`);
        }
        const data = (await res.json()) as { attemptId: number | null };
        if (data.attemptId == null) {
          setError(
            "Processing finished but no climber track was found. Try a 30–90 s clip of a single attempt where the climber stays mostly in frame.",
          );
          setInfo(null);
          return;
        }
        router.push(`/post/${data.attemptId}`);
      } catch (err) {
        setError(err instanceof Error ? err.message : String(err));
        setInfo(null);
      }
    });
  }

  return (
    <form onSubmit={submit}>
      <div
        style={{
          display: "flex",
          gap: 6,
          marginBottom: 12,
        }}
      >
        {(["auto", "random", "custom"] as TitleMode[]).map((m) => (
          <button
            key={m}
            type="button"
            className={`btn ${titleMode === m ? "primary" : ""}`.trim()}
            onClick={() => setTitleMode(m)}
            style={{ flex: 1 }}
          >
            {m}
          </button>
        ))}
      </div>

      {titleMode === "random" ? (
        <div style={{ display: "flex", gap: 6, marginBottom: 12 }}>
          <input
            value={randomName}
            disabled
            style={{
              flex: 1,
              borderRadius: 12,
              border: "1px solid var(--hairline)",
              padding: "10px 12px",
              fontFamily: "var(--font)",
              fontSize: 14,
              fontWeight: 600,
              color: "var(--ink)",
              background: "var(--surface)",
            }}
          />
          <button
            type="button"
            className="btn"
            onClick={() => setRandomName(randomTitle())}
            title="Roll a new name"
          >
            ↻
          </button>
        </div>
      ) : null}

      {titleMode === "custom" ? (
        <div className="field" style={{ marginBottom: 12 }}>
          <label>name your climb</label>
          <input
            placeholder="e.g. Wednesday Project, Heel Hook Heaven"
            value={customTitle}
            onChange={(e) => setCustomTitle(e.target.value)}
          />
        </div>
      ) : null}

      {titleMode === "auto" ? (
        <div className="page-sub">
          we&apos;ll name it from the result + grade — e.g. <em>Sent Red · V5-V6</em>.
        </div>
      ) : null}

      <div className="dropzone" onClick={pickFile} role="button" tabIndex={0}>
        <div className="icon">↑</div>
        <div className="t">{file ? "swap clip" : "drop your clip"}</div>
        <div className="s">tap to browse · mp4 / mov / m4v / mkv / webm</div>
        {file ? <div className="picked">{file.name} · {(file.size / 1024 / 1024).toFixed(1)} MB</div> : null}
        <input
          ref={fileInputRef}
          type="file"
          accept="video/mp4,video/quicktime,video/x-m4v,video/x-matroska,video/webm"
          onChange={onFile}
        />
      </div>

      <div className="form-card">
        <div className="grid">
          <div className="field">
            <label>climber name</label>
            <input
              placeholder="e.g. niklavs visockis"
              value={climber}
              onChange={(e) => setClimber(e.target.value)}
            />
          </div>
          <div className="field">
            <label>gym</label>
            <input value={gym} onChange={(e) => setGym(e.target.value)} />
          </div>
          <div className="field">
            <label>hold color · drives the grade</label>
            <select value={color} onChange={(e) => setColor(e.target.value)}>
              {COLOR_KEYS.map((k) => (
                <option key={k} value={k}>{k}</option>
              ))}
            </select>
          </div>
          <div>
            {gradePreview ? (
              <div className="amber-panel" style={{ padding: "12px 14px" }}>
                <div className="eyebrow">inferred grade</div>
                <div
                  style={{
                    fontFamily: "var(--font)",
                    fontSize: 34,
                    fontWeight: 800,
                    letterSpacing: "-0.03em",
                    color: "var(--ink)",
                    lineHeight: 1,
                    marginTop: 4,
                  }}
                >
                  {gradePreview.grade}
                </div>
                <div
                  style={{
                    fontSize: 12,
                    color: "var(--ink-2)",
                    fontWeight: 600,
                    marginTop: 2,
                  }}
                >
                  {color} · {gradePreview.label.toLowerCase()}
                </div>
              </div>
            ) : (
              <div className="page-sub">
                Grade lookup only configured for Klättercentret Akalla in v1.
              </div>
            )}
          </div>
        </div>
      </div>

      {warn ? <div className="alert warn">{warn}</div> : null}
      {error ? <div className="alert error">{error}</div> : null}
      {info ? <div className="alert">{info}</div> : null}

      <div style={{ marginTop: 14 }}>
        <button type="submit" className="btn full" disabled={submitting}>
          {submitting ? "analyzing…" : "analyze climb"}
        </button>
      </div>
    </form>
  );
}
