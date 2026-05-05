/**
 * Preview Panel — shows a read-only timeline of the entire show,
 * visualizing what happens at each step (captions, actions, background tasks).
 */
export default function PreviewPanel({ script }) {
  if (!script?.segments) {
    return <div className="p-6 text-text-dim">No script loaded</div>;
  }

  let globalIndex = 0;

  return (
    <div className="p-6 max-w-4xl">
      <h2 className="text-lg font-bold text-text-primary mb-2">{script.title}</h2>
      <p className="text-xs text-text-dim mb-6">
        Preview of all steps across {script.segments.length} segment(s). This shows the
        flow of the show, including what captions, actions, and OSC messages will fire.
      </p>

      {script.segments.map((seg) => (
        <div key={seg.id} className="mb-8">
          <h3 className="text-sm font-bold text-accent-purple tracking-wide mb-3 uppercase">
            {seg.name || seg.id}
          </h3>
          <div className="flex flex-col gap-0">
            {(seg.steps || []).map((step, i) => {
              globalIndex++;
              return (
                <PreviewStep key={step.id || i} step={step} number={globalIndex} />
              );
            })}
          </div>
        </div>
      ))}
    </div>
  );
}

function PreviewStep({ step, number }) {
  const trigger = step.trigger || {};
  const caption = step.caption || {};
  const actions = step.actions || [];
  const performer = step.performer || {};

  const triggerLabel = {
    speech: `Speech: "${trigger.phrase || "?"}"`,
    auto: trigger.wait_for_voice ? "Auto (voice gate)" : "Auto",
    timer: `Timer: ${trigger.duration || 0}s`,
    manual: "Manual",
    audio_end: "Audio End",
    video_end: "Video End",
    await_task: `Await: ${trigger.task || "?"}`,
  }[trigger.type] || trigger.type || "auto";

  return (
    <div className="flex gap-4 group">
      {/* Timeline */}
      <div className="flex flex-col items-center w-8 shrink-0">
        <div className="w-3 h-3 rounded-full border-2 border-border bg-bg-primary group-hover:border-accent-blue transition-colors" />
        <div className="flex-1 w-px bg-border" />
      </div>

      {/* Content */}
      <div className="flex-1 pb-5">
        <div className="flex items-center gap-2 mb-1">
          <span className="text-xs font-mono text-text-dim">#{number}</span>
          <span className="text-xs font-mono text-accent-blue">{step.id}</span>
          {step.mode && (
            <span className="px-1.5 py-0.5 text-[9px] font-mono rounded bg-accent-purple/20 text-accent-purple">
              {step.mode}
            </span>
          )}
        </div>

        {/* Trigger */}
        <div className="flex items-center gap-2 mb-1">
          <span className="text-[10px] font-mono text-text-dim">TRIGGER:</span>
          <span className="text-xs font-mono text-accent-orange">{triggerLabel}</span>
          {trigger.delay > 0 && (
            <span className="text-[10px] font-mono text-text-dim">+{trigger.delay}s delay</span>
          )}
        </div>

        {/* Caption */}
        {caption.text && (
          <p
            className="text-sm leading-relaxed mb-1"
            style={{ color: caption.display !== false ? (caption.color || "#ffffff") : "#555" }}
          >
            {caption.display === false && <span className="text-text-dim">[hidden] </span>}
            {caption.text}
          </p>
        )}

        {/* Actions summary */}
        {actions.length > 0 && (
          <div className="flex flex-wrap gap-1 mt-1">
            {actions.map((a, i) => (
              <span
                key={i}
                className="px-1.5 py-0.5 text-[10px] font-mono rounded bg-bg-tertiary text-text-secondary border border-border"
              >
                {a.type}
                {a.blocking && " ⏳"}
                {a.task_id && ` → ${a.task_id}`}
              </span>
            ))}
          </div>
        )}

        {/* OSC messages that will be sent */}
        {actions.some((a) => ["show_qr", "hide_qr", "send_osc", "audio_control"].includes(a.type)) && (
          <div className="flex flex-wrap gap-1 mt-1">
            {actions
              .filter((a) => ["show_qr", "hide_qr", "send_osc", "audio_control"].includes(a.type))
              .map((a, i) => (
                <span key={i} className="text-[10px] font-mono text-accent-cyan">
                  OSC: {a.type === "send_osc" ? a.address : `/${a.type.replace("_", "/")}`}
                </span>
              ))}
          </div>
        )}

        {/* Performer note */}
        {performer.note && (
          <p className="text-xs text-text-dim italic mt-1">{performer.note}</p>
        )}
      </div>
    </div>
  );
}
