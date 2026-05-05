export default function SettingsPanel({ settings, onChange }) {
  const update = (section, key, value) => {
    onChange({
      [section]: { ...settings[section], [key]: value },
    });
  };

  const osc = settings.osc || {};
  const speech = settings.speech || {};
  const models = settings.models || {};
  const failure = settings.failure || {};
  const performer = settings.performer || {};
  const generation = settings.generation || {};

  return (
    <div className="p-6 max-w-2xl">
      <h2 className="text-lg font-bold text-text-primary mb-6">Show Settings</h2>

      {/* OSC */}
      <Section title="OSC (TouchDesigner)">
        <div className="grid grid-cols-2 gap-4">
          <Field label="Host">
            <input className="input-field" value={osc.host || ""} onChange={(e) => update("osc", "host", e.target.value)} />
          </Field>
          <Field label="Port">
            <input type="number" className="input-field" value={osc.port || 9000} onChange={(e) => update("osc", "port", parseInt(e.target.value))} />
          </Field>
        </div>
      </Section>

      {/* Speech */}
      <Section title="Speech Recognition">
        <Field label="Provider">
          <input className="input-field" value={speech.provider || "assemblyai"} onChange={(e) => update("speech", "provider", e.target.value)} />
        </Field>
        <div className="grid grid-cols-2 gap-4">
          <Field label="Default Confidence">
            <input type="number" className="input-field" value={speech.default_confidence ?? 0.85} min={0} max={1} step={0.05} onChange={(e) => update("speech", "default_confidence", parseFloat(e.target.value))} />
          </Field>
          <Field label="Default Cue Words">
            <input type="number" className="input-field" value={speech.default_cue_words || 4} onChange={(e) => update("speech", "default_cue_words", parseInt(e.target.value))} />
          </Field>
        </div>
      </Section>

      {/* Models */}
      <Section title="AI Models">
        <Field label="Text (Gemini)">
          <input className="input-field" value={models.text || ""} onChange={(e) => update("models", "text", e.target.value)} />
        </Field>
        <Field label="Music">
          <input className="input-field" value={models.music || ""} onChange={(e) => update("models", "music", e.target.value)} />
        </Field>
        <Field label="SFX (AudioGen)">
          <input className="input-field" value={models.sfx || ""} onChange={(e) => update("models", "sfx", e.target.value)} placeholder="sepal/audiogen" />
        </Field>
        <Field label="TTS">
          <input className="input-field" value={models.tts || ""} onChange={(e) => update("models", "tts", e.target.value)} />
        </Field>
        <Field label="Video">
          <input className="input-field" value={models.video || ""} onChange={(e) => update("models", "video", e.target.value)} />
        </Field>
      </Section>

      {/* Failure */}
      <Section title="Failure Counter">
        <Field label="Sound Effect Path">
          <input className="input-field" value={failure.sfx || ""} onChange={(e) => update("failure", "sfx", e.target.value)} />
        </Field>
        <Field label="OSC Address">
          <input className="input-field" value={failure.osc_address || ""} onChange={(e) => update("failure", "osc_address", e.target.value)} />
        </Field>
        <label className="flex items-center gap-2 text-xs text-text-secondary mt-1 cursor-pointer">
          <input
            type="checkbox"
            checked={failure.display_to_audience !== false}
            onChange={(e) => update("failure", "display_to_audience", e.target.checked)}
            className="accent-accent-blue"
          />
          Show to audience
        </label>
      </Section>

      {/* Generation SFX */}
      <Section title="Generation Sound Effects">
        <Field label="Loading SFX (loops during generation)">
          <input className="input-field" value={generation.loading_sfx || ""} onChange={(e) => update("generation", "loading_sfx", e.target.value)} placeholder="./assets/audio/loading_loop.wav" />
        </Field>
        <Field label="Complete SFX (plays when generation finishes)">
          <input className="input-field" value={generation.complete_sfx || ""} onChange={(e) => update("generation", "complete_sfx", e.target.value)} placeholder="./assets/audio/generation_complete.wav" />
        </Field>
      </Section>

      {/* Performer */}
      <Section title="Performer">
        <Field label="Pause Caption">
          <input className="input-field" value={performer.pause_caption || "[OFFSCRIPT]"} onChange={(e) => update("performer", "pause_caption", e.target.value)} />
        </Field>
      </Section>
    </div>
  );
}

function Section({ title, children }) {
  return (
    <div className="mb-6">
      <h3 className="text-xs font-mono font-bold tracking-[0.15em] text-text-dim uppercase mb-3">{title}</h3>
      <div className="flex flex-col gap-3 pl-1">{children}</div>
    </div>
  );
}

function Field({ label, children }) {
  return (
    <div className="flex flex-col gap-1">
      <label className="text-xs text-text-secondary">{label}</label>
      {children}
    </div>
  );
}
