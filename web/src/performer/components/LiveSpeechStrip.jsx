export default function LiveSpeechStrip({ transcript, mic }) {
  const partial = transcript?.partial?.trim() || "";
  const level = typeof mic?.level === "number" ? mic.level : 0;
  const streaming = Boolean(mic?.streaming);
  const pct = Math.min(100, Math.round(level * 100));

  return (
    <div className="shrink-0 border-b border-border bg-bg-secondary/60 px-8 py-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between sm:gap-6">
        <div className="flex items-center gap-3 min-w-0 flex-1">
          <span className="shrink-0 text-[10px] font-mono font-bold tracking-[0.2em] text-text-dim uppercase">
            Live transcription
          </span>
          <div
            className="flex-1 h-2.5 rounded-full bg-bg-tertiary overflow-hidden border border-border"
            title="Microphone level (same input sent to AssemblyAI)"
            role="meter"
            aria-valuenow={pct}
            aria-valuemin={0}
            aria-valuemax={100}
            aria-label="Microphone level"
          >
            <div
              className="h-full rounded-full bg-linear-to-r from-accent-cyan to-accent-green transition-[width] duration-75 ease-out"
              style={{ width: `${pct}%` }}
            />
          </div>
          <span className="shrink-0 w-8 text-right font-mono text-xs text-text-dim tabular-nums">
            {pct}%
          </span>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <div
            className={`w-2 h-2 rounded-full ${streaming ? "bg-accent-green" : "bg-text-dim"}`}
          />
          <span className="text-xs font-mono text-text-dim">
            {streaming ? "Mic stream active" : "Mic stream idle"}
          </span>
        </div>
      </div>

      <div className="mt-3 min-h-18 rounded-lg border border-border bg-bg-primary/80 px-4 py-3">
        {partial ? (
          <p className="text-xl md:text-2xl font-mono text-accent-yellow leading-relaxed whitespace-pre-wrap wrap-break-word">
            {partial}
            <span
              className="inline-block w-0.5 ml-0.5 bg-accent-yellow/80 animate-pulse-glow"
              style={{ height: "1.05em", verticalAlign: "-0.1em" }}
            />
          </p>
        ) : (
          <p className="text-sm font-mono text-text-dim italic">
            {streaming
              ? "Speak — partial text from AssemblyAI will appear here."
              : "Start the show to begin the microphone / transcription stream."}
          </p>
        )}
      </div>
    </div>
  );
}
