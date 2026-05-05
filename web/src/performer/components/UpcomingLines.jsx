export default function UpcomingLines({ steps, currentIndex }) {
  if (!steps || steps.length === 0) {
    return (
      <div className="flex-1 flex items-center justify-center px-8 py-6 overflow-hidden">
        <p className="text-text-dim text-sm">No upcoming steps</p>
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-y-auto px-6 py-4">
      <div className="mb-3">
        <span className="text-xs font-mono font-bold tracking-[0.15em] text-text-dim uppercase">
          Upcoming
        </span>
      </div>
      <div className="flex flex-col gap-1">
        {steps.map((step, i) => (
          <UpcomingStep key={step.id || i} step={step} relativeIndex={i + 1} />
        ))}
      </div>
    </div>
  );
}

function UpcomingStep({ step, relativeIndex }) {
  const caption = step.caption;
  const text = caption?.text || "";
  const color = caption?.color || "#ffffff";
  const isAI = step.is_ai_generated;

  return (
    <div className="flex items-start gap-3 px-3 py-2.5 rounded-lg hover:bg-bg-hover transition-colors">
      {/* Index */}
      <span className="shrink-0 w-6 text-right font-mono text-xs text-text-dim mt-0.5">
        +{relativeIndex}
      </span>

      {/* Content */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-0.5">
          {isAI && (
            <span className="px-1.5 py-0 text-[9px] font-mono font-bold rounded bg-accent-red/20 text-accent-red">
              AI
            </span>
          )}
          {step.trigger?.type === "speech" && (
            <span className="text-[10px] font-mono text-accent-orange">
              cue: "{step.trigger.phrase}"
            </span>
          )}
          {step.trigger?.type === "auto" && (
            <span className="text-[10px] font-mono text-accent-green">auto</span>
          )}
          {step.trigger?.type === "manual" && (
            <span className="text-[10px] font-mono text-accent-yellow">manual</span>
          )}
          {step.trigger?.type === "timer" && (
            <span className="text-[10px] font-mono text-accent-cyan">timer</span>
          )}
          {step.mode && (
            <span className="text-[10px] font-mono text-accent-purple">{step.mode}</span>
          )}
          {step.has_actions && (
            <span className="text-[10px] font-mono text-text-dim">+ actions</span>
          )}
        </div>
        <p
          className="text-sm leading-relaxed truncate"
          style={{ color: text ? color : undefined }}
          title={text}
        >
          {text || <span className="text-text-dim italic">No caption</span>}
        </p>
        {step.performer?.note && (
          <p className="text-xs text-text-dim mt-0.5 truncate italic">
            {step.performer.note}
          </p>
        )}
      </div>
    </div>
  );
}
