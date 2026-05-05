import { useMemo, useState } from "react";

/** Stable label for grouping (matches outline `segment_name` fallback). */
function segmentLabel(s) {
  const n = (s.segment_name || "").trim();
  return n || "(Unnamed segment)";
}

/**
 * Idle-only: first pick a script segment (section), then pick the step to start from.
 */
export default function ScriptStartPicker({ showTitle, stepsOutline, onStartAtIndex }) {
  const [pickedSection, setPickedSection] = useState(null);

  const sections = useMemo(() => {
    if (!stepsOutline?.length) return [];
    const order = [];
    const counts = new Map();
    const seen = new Set();
    for (const step of stepsOutline) {
      const label = segmentLabel(step);
      counts.set(label, (counts.get(label) || 0) + 1);
      if (!seen.has(label)) {
        seen.add(label);
        order.push(label);
      }
    }
    return order.map((label) => ({ label, count: counts.get(label) || 0 }));
  }, [stepsOutline]);

  const stepsInSection = useMemo(() => {
    if (!pickedSection || !stepsOutline?.length) return [];
    return stepsOutline.filter((s) => segmentLabel(s) === pickedSection);
  }, [stepsOutline, pickedSection]);

  if (!stepsOutline?.length) {
    return (
      <div className="flex flex-col items-center justify-center h-full min-h-[200px] gap-2 text-text-dim">
        <p className="text-lg">No steps loaded</p>
        <p className="text-sm font-mono">Check that the script is available on the server.</p>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full min-h-0 bg-bg-primary">
      <div className="shrink-0 px-6 py-4 border-b border-border">
        <h2 className="text-xl font-semibold text-text-primary tracking-tight">
          {showTitle || "Show"}
        </h2>
        {!pickedSection ? (
          <p className="text-sm text-text-secondary mt-2 max-w-3xl leading-relaxed">
            Choose a <strong className="text-text-primary">section</strong> (script segment), then pick
            the step to start from. Or use{" "}
            <kbd className="px-1.5 py-0.5 rounded bg-bg-tertiary border border-border text-[11px] font-mono text-text-primary">
              S
            </kbd>{" "}
            / <span className="text-accent-green font-medium">Start from beginning</span> for step 0.
          </p>
        ) : (
          <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1">
            <button
              type="button"
              onClick={() => setPickedSection(null)}
              className="text-sm font-mono text-accent-blue hover:underline cursor-pointer"
            >
              ← All sections
            </button>
            <span className="text-text-dim">·</span>
            <p className="text-sm text-text-secondary">
              Section:{" "}
              <span className="text-accent-purple font-mono font-semibold">{pickedSection}</span>
              <span className="text-text-dim ml-2">
                ({stepsInSection.length} step{stepsInSection.length === 1 ? "" : "s"})
              </span>
            </p>
          </div>
        )}
      </div>

      {!pickedSection ? (
        <div className="flex-1 min-h-0 overflow-y-auto overscroll-contain px-4 py-4 pb-6">
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3 max-w-5xl mx-auto">
            {sections.map(({ label, count }) => (
              <button
                key={label}
                type="button"
                onClick={() => setPickedSection(label)}
                className="text-left px-4 py-4 rounded-xl border border-border/70 bg-bg-secondary/50 hover:bg-bg-hover hover:border-border-active transition-colors cursor-pointer"
              >
                <div className="text-[11px] font-mono font-bold tracking-[0.12em] text-accent-purple uppercase line-clamp-2">
                  {label}
                </div>
                <div className="text-xs text-text-dim mt-2 font-mono">{count} step{count === 1 ? "" : "s"}</div>
              </button>
            ))}
          </div>
        </div>
      ) : (
        <div className="flex-1 min-h-0 overflow-y-auto overscroll-contain px-4 py-3 pb-6">
          {stepsInSection.map((s) => (
            <button
              key={`${s.id}-${s.index}`}
              type="button"
              onClick={() => onStartAtIndex(s.index)}
              className="w-full text-left px-3 py-3 rounded-lg border border-border/70 bg-bg-secondary/40 hover:bg-bg-hover hover:border-border-active transition-colors mb-1.5 cursor-pointer group"
            >
              <div className="flex items-start gap-3">
                <span className="text-xs font-mono text-text-dim w-9 shrink-0 tabular-nums pt-0.5">
                  #{s.index}
                </span>
                <div className="min-w-0 flex-1">
                  <div className="text-[11px] font-mono text-accent-blue truncate">{s.id}</div>
                  {s.caption_preview ? (
                    <p className="text-sm md:text-base text-text-primary leading-snug mt-1 line-clamp-4">
                      {s.caption_preview}
                    </p>
                  ) : (
                    <p className="text-sm text-text-dim italic mt-1">No caption</p>
                  )}
                  <div className="flex flex-wrap items-center gap-x-2 gap-y-0.5 mt-2 text-[10px] font-mono text-text-dim">
                    <span className="text-text-secondary">{s.trigger_type}</span>
                    {s.trigger_phrase && (
                      <span className="text-accent-orange truncate max-w-full">
                        &ldquo;{s.trigger_phrase}&rdquo;
                      </span>
                    )}
                  </div>
                </div>
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
