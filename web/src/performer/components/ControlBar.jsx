export default function ControlBar({ state, sendCommand }) {
  const isIdle = state.show_state === "idle";
  const isPaused = state.show_state === "paused";
  const isRunning = ["running", "waiting_for_ai"].includes(state.show_state);

  return (
    <div className="flex items-center justify-between px-5 py-3 bg-bg-secondary border-t border-border">
      {/* Left: main controls */}
      <div className="flex items-center gap-2">
        {isIdle ? (
          <ControlButton
            label="Start from beginning"
            shortcut="S"
            onClick={() => sendCommand("start", { start_index: 0 })}
            variant="green"
          />
        ) : (
          <>
            <ControlButton
              label={isPaused ? "Resume" : "Pause"}
              shortcut="P"
              onClick={() => sendCommand("pause")}
              variant={isPaused ? "green" : "orange"}
            />
            <ControlButton
              label="Stop"
              onClick={() => sendCommand("stop")}
              variant="red"
            />
          </>
        )}
      </div>

      {/* Center: navigation */}
      {isRunning && (
        <div className="flex items-center gap-2">
          <ControlButton
            label="← Back"
            shortcut="E"
            onClick={() => sendCommand("go_back")}
            variant="default"
          />
          <ControlButton
            label="Skip"
            shortcut="W"
            onClick={() => sendCommand("skip_clean")}
            variant="default"
          />
          <ControlButton
            label="Skip + Fail"
            shortcut="Q"
            onClick={() => sendCommand("skip_with_failure")}
            variant="red"
          />
        </div>
      )}

      {/* Right: reset + shortcuts hint */}
      <div className="flex items-center gap-3">
        {!isIdle && (
          <ControlButton
            label="Reset"
            shortcut="⇧R"
            onClick={() => sendCommand("reset")}
            variant="default"
          />
        )}
        <div className="text-[10px] font-mono text-text-dim leading-tight">
          <span className="text-text-secondary">P</span> pause{" "}
          <span className="text-text-secondary">W</span> skip{" "}
          <span className="text-text-secondary">Q</span> skip+fail{" "}
          <span className="text-text-secondary">E</span> back
        </div>
      </div>
    </div>
  );
}

const VARIANTS = {
  default:
    "bg-bg-tertiary text-text-primary hover:bg-bg-hover border-border",
  green:
    "bg-accent-green/10 text-accent-green hover:bg-accent-green/20 border-accent-green/30",
  red:
    "bg-accent-red/10 text-accent-red hover:bg-accent-red/20 border-accent-red/30",
  orange:
    "bg-accent-orange/10 text-accent-orange hover:bg-accent-orange/20 border-accent-orange/30",
};

function ControlButton({ label, shortcut, onClick, variant = "default" }) {
  return (
    <button
      onClick={onClick}
      className={`flex items-center gap-2 px-3.5 py-2 rounded-lg border text-sm font-medium transition-all duration-150 active:scale-95 cursor-pointer ${VARIANTS[variant]}`}
    >
      {label}
      {shortcut && (
        <kbd className="px-1.5 py-0.5 text-[10px] font-mono rounded bg-bg-primary/50 text-text-dim">
          {shortcut}
        </kbd>
      )}
    </button>
  );
}
