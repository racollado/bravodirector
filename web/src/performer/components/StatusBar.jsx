const STATE_STYLES = {
  idle: { bg: "bg-bg-tertiary", text: "text-text-secondary", label: "IDLE" },
  running: { bg: "bg-accent-green/10", text: "text-accent-green", label: "RUNNING" },
  paused: { bg: "bg-accent-orange/10", text: "text-accent-orange", label: "PAUSED" },
  waiting_for_ai: { bg: "bg-accent-purple/10", text: "text-accent-purple", label: "GENERATING..." },
  error: { bg: "bg-accent-red/10", text: "text-accent-red", label: "ERROR" },
};

export default function StatusBar({ state, connected }) {
  const style = STATE_STYLES[state.show_state] || STATE_STYLES.idle;

  return (
    <div className={`flex items-center justify-between px-5 py-2.5 ${style.bg} border-b border-border`}>
      <div className="flex items-center gap-4">
        {/* Connection dot */}
        <div className="flex items-center gap-2">
          <div
            className={`w-2 h-2 rounded-full ${
              connected ? "bg-accent-green" : "bg-accent-red animate-pulse-glow"
            }`}
          />
          <span className="text-xs font-mono text-text-dim">
            {connected ? "CONNECTED" : "DISCONNECTED"}
          </span>
        </div>

        {/* Show state */}
        <div className={`px-3 py-1 rounded font-mono text-sm font-bold tracking-wider ${style.text}`}>
          {style.label}
        </div>

        {/* Show title */}
        <span className="text-sm text-text-secondary">{state.show_title}</span>
      </div>

      <div className="flex items-center gap-5">
        {/* Step counter */}
        <div className="flex items-center gap-2">
          <span className="text-xs font-mono text-text-dim">STEP</span>
          <span className="font-mono text-sm text-text-primary">
            {state.current_index + 1} / {state.total_steps}
          </span>
        </div>

        {/* Failure counter */}
        <div className="flex items-center gap-2">
          <span className="text-xs font-mono text-text-dim">FAILS</span>
          <span
            className={`font-mono text-sm font-bold ${
              state.failure_count > 0 ? "text-accent-red" : "text-text-secondary"
            }`}
          >
            {state.failure_count}
          </span>
        </div>
      </div>
    </div>
  );
}
