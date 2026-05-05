export default function TranscriptPanel({ transcript }) {
  const lines = transcript?.lines || [];
  const partial = transcript?.partial || "";

  return (
    <div className="flex-1 flex flex-col overflow-hidden border-b border-border">
      <div className="px-4 py-2.5 border-b border-border">
        <span className="text-xs font-mono font-bold tracking-[0.15em] text-text-dim uppercase">
          Transcript log
        </span>
      </div>
      <div className="flex-1 overflow-y-auto px-4 py-3 flex flex-col justify-start">
        <div className="flex flex-col gap-1.5">
          {lines.slice(-12).map((line, i) => (
            <p key={i} className="text-sm text-text-secondary leading-relaxed font-mono">
              {line}
            </p>
          ))}
          {partial && (
            <p className="text-sm text-accent-yellow leading-relaxed font-mono italic animate-slide-up">
              {partial}
            </p>
          )}
          {lines.length === 0 && !partial && (
            <p className="text-sm text-text-dim italic">Waiting for speech...</p>
          )}
        </div>
      </div>
    </div>
  );
}
