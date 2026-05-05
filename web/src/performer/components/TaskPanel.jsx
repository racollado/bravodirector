const STATUS_STYLES = {
  pending: "text-text-dim",
  running: "text-accent-blue animate-pulse-glow",
  completed: "text-accent-green",
  failed: "text-accent-red",
};

const STATUS_ICONS = {
  pending: "○",
  running: "◉",
  completed: "●",
  failed: "✕",
};

export default function TaskPanel({ tasks, timer, audioLayers }) {
  const taskEntries = Object.entries(tasks || {});
  const hasTimer = timer && timer.total > 0;
  const layers = Object.entries(audioLayers || {}).filter(
    ([, info]) => info.playing || info.paused
  );

  if (taskEntries.length === 0 && !hasTimer && layers.length === 0) {
    return (
      <div className="px-4 py-3">
        <div className="mb-2">
          <span className="text-xs font-mono font-bold tracking-[0.15em] text-text-dim uppercase">
            System
          </span>
        </div>
        <p className="text-xs text-text-dim">No active tasks</p>
      </div>
    );
  }

  return (
    <div className="px-4 py-3 overflow-y-auto">
      <div className="mb-3">
        <span className="text-xs font-mono font-bold tracking-[0.15em] text-text-dim uppercase">
          System
        </span>
      </div>

      {/* Timer */}
      {hasTimer && (
        <div className="mb-3 p-2.5 rounded-lg bg-bg-tertiary">
          <div className="flex items-center justify-between mb-1.5">
            <span className="text-xs font-mono text-accent-cyan">TIMER</span>
            <span className="text-sm font-mono font-bold text-text-primary">
              {Math.ceil(timer.remaining)}s
            </span>
          </div>
          <div className="h-1.5 bg-bg-primary rounded-full overflow-hidden">
            <div
              className="h-full bg-accent-cyan rounded-full transition-all duration-1000"
              style={{ width: `${((timer.total - timer.remaining) / timer.total) * 100}%` }}
            />
          </div>
        </div>
      )}

      {/* Audio layers */}
      {layers.length > 0 && (
        <div className="mb-3">
          {layers.map(([name, info]) => (
            <div key={name} className="flex items-center gap-2 py-1">
              <span
                className={`text-[10px] font-mono ${
                  info.paused ? "text-accent-orange" : "text-accent-green"
                }`}
              >
                ♫
              </span>
              <span className="text-xs font-mono text-text-secondary">{name}</span>
              <span className="text-[10px] font-mono text-text-dim truncate flex-1">
                {info.file?.split("/").pop() || ""}
              </span>
              {info.loop && (
                <span className="text-[9px] font-mono text-accent-purple">LOOP</span>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Background tasks */}
      {taskEntries.length > 0 && (
        <div className="flex flex-col gap-1.5">
          {taskEntries.map(([id, info]) => (
            <div key={id} className="flex items-center gap-2 py-1">
              <span className={`text-xs ${STATUS_STYLES[info.status]}`}>
                {STATUS_ICONS[info.status]}
              </span>
              <span className="text-xs font-mono text-text-secondary flex-1 truncate">
                {id}
              </span>
              <span className={`text-[10px] font-mono ${STATUS_STYLES[info.status]}`}>
                {info.status === "running"
                  ? `${Math.round(info.progress * 100)}%`
                  : info.status}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
