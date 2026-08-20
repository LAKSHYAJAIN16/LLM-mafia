"use client";

import { useEffect, useRef, useState } from "react";
import type { TimelineItem } from "@/lib/transcript";
import { KIND_LABELS } from "@/lib/transcript";

function EntryRow({ item }: { item: Extract<TimelineItem, { type: "entry" }> }) {
  const { entry } = item;
  return (
    <div className={`entry entry-${entry.kind}`}>
      {entry.speaker && <span className="speaker">{entry.speaker}</span>}
      {entry.text}
      <span className="tag">{KIND_LABELS[entry.kind] ?? entry.kind}</span>
    </div>
  );
}

export default function Transcript({ items }: { items: TimelineItem[] }) {
  const [revealed, setRevealed] = useState(items.length);
  const [playing, setPlaying] = useState(false);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    if (!playing) {
      if (intervalRef.current) clearInterval(intervalRef.current);
      return;
    }
    intervalRef.current = setInterval(() => {
      setRevealed((r) => {
        if (r >= items.length) {
          setPlaying(false);
          return r;
        }
        return r + 1;
      });
    }, 1100);
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [playing, items.length]);

  const stepMode = (on: boolean) => {
    setPlaying(false);
    setRevealed(on ? 0 : items.length);
  };
  const stepOnce = () => setRevealed((r) => Math.min(r + 1, items.length));
  const togglePlay = () => {
    if (revealed >= items.length) setRevealed(0);
    setPlaying((p) => !p);
  };

  return (
    <>
      <div className="controls">
        <button onClick={() => stepMode(true)}>Step through</button>
        <button onClick={() => stepMode(false)}>Show full transcript</button>
        <button onClick={togglePlay} className={playing ? "active" : ""}>
          {playing ? "Pause" : "Play"}
        </button>
        <button onClick={stepOnce}>Next</button>
      </div>

      <div>
        {items.slice(0, revealed).map((item) => {
          if (item.type === "heading") {
            return (
              <div className="heading" key={item.key}>
                {item.label}
              </div>
            );
          }
          if (item.type === "summary") {
            return (
              <div className="entry entry-summary" key={item.key}>
                {item.text}
              </div>
            );
          }
          return <EntryRow item={item} key={item.key} />;
        })}
      </div>
    </>
  );
}
