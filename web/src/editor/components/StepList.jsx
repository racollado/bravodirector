export default function StepList({ steps, selectedIndex, onSelect, onInsertAt, onDelete, onMove }) {
  return (
    <div className="flex-1 flex flex-col overflow-hidden">
      <div className="flex-1 overflow-y-auto">
        {steps.map((step, i) => (
          <StepListItem
            key={step.id || i}
            step={step}
            index={i}
            isSelected={selectedIndex === i}
            onSelect={() => onSelect(i)}
            onInsertAbove={() => onInsertAt(i)}
            onInsertBelow={() => onInsertAt(i + 1)}
            onDelete={() => onDelete(i)}
            onMoveUp={() => onMove(i, i - 1)}
            onMoveDown={() => onMove(i, i + 1)}
            isFirst={i === 0}
            isLast={i === steps.length - 1}
          />
        ))}
        {steps.length === 0 && (
          <div className="p-4 text-center text-xs text-text-dim">
            No steps yet. Use Add Step below.
          </div>
        )}
      </div>
      <div className="p-2 border-t border-border">
        <button
          type="button"
          onClick={() => onInsertAt(steps.length)}
          className="w-full px-3 py-2 text-xs font-mono rounded bg-accent-blue/10 text-accent-blue hover:bg-accent-blue/20 border border-accent-blue/30 transition-colors cursor-pointer"
        >
          + Add Step
        </button>
      </div>
    </div>
  );
}

function StepListItem({
  step,
  index,
  isSelected,
  onSelect,
  onInsertAbove,
  onInsertBelow,
  onDelete,
  onMoveUp,
  onMoveDown,
  isFirst,
  isLast,
}) {
  const triggerType = step.trigger?.type || "auto";
  const captionText = step.caption?.text || "";
  const hasActions = (step.actions?.length || 0) > 0;

  const TRIGGER_COLORS = {
    speech: "text-accent-orange",
    auto: "text-accent-green",
    manual: "text-accent-yellow",
    timer: "text-accent-cyan",
    audio_end: "text-accent-purple",
    video_end: "text-accent-purple",
    await_task: "text-accent-blue",
  };

  return (
    <div
      onClick={onSelect}
      className={`group flex items-start gap-2 px-3 py-2.5 cursor-pointer border-l-2 transition-colors ${
        isSelected
          ? "bg-accent-blue/10 border-accent-blue"
          : "border-transparent hover:bg-bg-hover"
      }`}
    >
      <span className="shrink-0 w-5 text-right font-mono text-[10px] text-text-dim mt-0.5">
        {index + 1}
      </span>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-1.5 mb-0.5">
          <span className={`text-[10px] font-mono ${TRIGGER_COLORS[triggerType] || "text-text-dim"}`}>
            {triggerType}
          </span>
          {hasActions && (
            <span className="text-[9px] font-mono text-accent-cyan">+act</span>
          )}
          {step.mode && (
            <span className="text-[9px] font-mono text-accent-purple">{step.mode}</span>
          )}
        </div>
        <p className="text-xs text-text-primary truncate">
          {captionText || <span className="text-text-dim italic">No caption</span>}
        </p>
        <p className="text-[10px] font-mono text-text-dim truncate">{step.id}</p>
      </div>
      <div className="shrink-0 flex flex-col gap-0.5 opacity-0 group-hover:opacity-100 transition-opacity">
        <button
          type="button"
          title="Insert step above"
          onClick={(e) => {
            e.stopPropagation();
            onInsertAbove();
          }}
          className="w-5 h-5 flex items-center justify-center text-[9px] font-mono text-accent-blue hover:text-accent-blue rounded hover:bg-accent-blue/15 cursor-pointer"
        >
          +↑
        </button>
        <button
          type="button"
          title="Insert step below"
          onClick={(e) => {
            e.stopPropagation();
            onInsertBelow();
          }}
          className="w-5 h-5 flex items-center justify-center text-[9px] font-mono text-accent-blue hover:text-accent-blue rounded hover:bg-accent-blue/15 cursor-pointer"
        >
          +↓
        </button>
        {!isFirst && (
          <button
            onClick={(e) => { e.stopPropagation(); onMoveUp(); }}
            className="w-5 h-5 flex items-center justify-center text-[10px] text-text-dim hover:text-text-primary rounded hover:bg-bg-tertiary cursor-pointer"
          >
            ▲
          </button>
        )}
        {!isLast && (
          <button
            onClick={(e) => { e.stopPropagation(); onMoveDown(); }}
            className="w-5 h-5 flex items-center justify-center text-[10px] text-text-dim hover:text-text-primary rounded hover:bg-bg-tertiary cursor-pointer"
          >
            ▼
          </button>
        )}
        <button
          onClick={(e) => { e.stopPropagation(); onDelete(); }}
          className="w-5 h-5 flex items-center justify-center text-[10px] text-accent-red hover:bg-accent-red/20 rounded cursor-pointer"
        >
          ✕
        </button>
      </div>
    </div>
  );
}
