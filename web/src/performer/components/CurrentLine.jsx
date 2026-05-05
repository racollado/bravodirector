export default function CurrentLine({ step, showState, displayedCaption, loadingMessage }) {
  const isLoading = showState === "waiting_for_ai";

  if (!step) {
    return (
      <div className="flex items-center justify-center py-16 px-8 bg-bg-primary">
        <p className="text-2xl text-text-dim font-light">
          {showState === "idle" ? "Press S to start the show" : "No current step"}
        </p>
      </div>
    );
  }

  const stepCaption = step.caption;
  const stepCaptionText = stepCaption?.text || "";
  const stepCaptionColor = stepCaption?.color || "#ffffff";

  const captionUsesRuntimeResolve =
    !!stepCaption?.text_append_task ||
    (typeof stepCaption?.text === "string" && stepCaption.text.startsWith("$"));

  const hasStepCaption = !!stepCaptionText;
  const captionText = captionUsesRuntimeResolve
    ? displayedCaption?.text || stepCaptionText || ""
    : stepCaptionText || displayedCaption?.text || "";
  const captionColor = hasStepCaption ? stepCaptionColor : (displayedCaption?.color || "#ffffff");
  const captionSource = hasStepCaption ? null : (captionText ? "audience" : null);

  const isAI = step.is_ai_generated;
  const performer = step.performer || {};
  const cuePhrase = step.trigger?.phrase?.trim();

  return (
    <div className="flex flex-col px-8 py-6 bg-bg-primary border-b border-border gap-6">
      {performer.section_label && (
        <div>
          <span className="text-xs font-mono font-bold tracking-[0.2em] text-accent-purple uppercase">
            {performer.section_label}
          </span>
        </div>
      )}

      {isLoading && (
        <div className="flex items-center gap-3 px-5 py-4 rounded-xl border border-accent-purple/35 bg-accent-purple/5">
          <span className="inline-block w-3 h-3 rounded-full bg-accent-purple animate-pulse-glow" />
          <span className="text-lg font-mono text-accent-purple font-semibold">
            {loadingMessage || "Generating..."}
          </span>
        </div>
      )}

      {/* Full caption — primary readable line */}
      <div>
        <div className="flex items-center gap-2 mb-2">
          {isAI && (
            <span className="shrink-0 px-2 py-0.5 text-[10px] font-mono font-bold rounded bg-accent-red/20 text-accent-red tracking-wider">
              AI
            </span>
          )}
          <span className="text-[10px] font-mono font-bold tracking-[0.2em] text-text-dim uppercase">
            {captionSource === "audience" ? "On screen now" : "Your line"}
          </span>
        </div>
        <p
          className="text-2xl md:text-3xl lg:text-4xl font-medium leading-[1.35] whitespace-pre-wrap wrap-break-word max-w-5xl"
          style={{ color: captionColor }}
        >
          {captionText || (
            <span className="text-text-dim italic">No caption for this step</span>
          )}
        </p>
      </div>

      {/* Cue phrase — full width, easy to read alongside the line */}
      {cuePhrase && (
        <div className="rounded-xl border border-accent-orange/35 bg-bg-secondary/90 px-5 py-4 max-w-5xl">
          <p className="text-[10px] font-mono font-bold tracking-[0.2em] text-accent-orange uppercase mb-2">
            Cue — say to advance
          </p>
          <p className="text-xl md:text-2xl font-mono text-text-primary leading-snug whitespace-pre-wrap wrap-break-word">
            &ldquo;{cuePhrase}&rdquo;
          </p>
        </div>
      )}

      {performer.note && (
        <div className="px-3 py-2 rounded bg-bg-tertiary border-l-2 border-accent-blue max-w-5xl">
          <p className="text-sm text-text-secondary italic">{performer.note}</p>
        </div>
      )}

      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs font-mono text-text-dim">
        <span>ID: {step.id}</span>
        <span>Trigger: {step.trigger?.type || "auto"}</span>
        {step.has_actions && <span className="text-accent-cyan">HAS ACTIONS</span>}
        {step.mode && <span className="text-accent-purple">{step.mode.toUpperCase()}</span>}
      </div>
    </div>
  );
}
