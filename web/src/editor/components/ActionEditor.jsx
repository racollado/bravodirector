import { useState } from "react";

const MUSIC_MODELS = [
  {
    value: "stability-ai/stable-audio-2.5",
    label: "Stable Audio 2.5 — duration, steps, CFG",
  },
  {
    value: "google/lyria-3",
    label: "Google Lyria 3 — ~30s clips (prompt / optional images)",
  },
  {
    value: "google/lyria-3-pro",
    label: "Google Lyria 3 Pro — up to ~3 min (prompt / optional images)",
  },
];

const ACTION_TYPES = [
  { value: "play_audio", label: "Play Audio" },
  { value: "play_video", label: "Show Media" },
  { value: "generate_text", label: "Generate Text (Gemini)" },
  { value: "generate_music", label: "Generate Music" },
  { value: "generate_sfx", label: "Generate SFX (AudioGen)" },
  { value: "generate_tts", label: "Generate TTS Voice" },
  { value: "generate_video", label: "Generate Video" },
  { value: "generate_image", label: "Generate Image" },
  { value: "fetch_submissions", label: "Fetch Submissions (DynamoDB)" },
  { value: "show_qr", label: "Show QR Code" },
  { value: "hide_qr", label: "Hide QR Code" },
  { value: "start_timer", label: "Start Timer" },
  { value: "audio_control", label: "Audio Control" },
  { value: "send_osc", label: "Send OSC" },
];

export default function ActionEditor({ actions, onChange }) {
  const addAction = () => {
    onChange([...actions, { type: "play_audio", blocking: false, volume: 1 }]);
  };

  const updateAction = (index, updates) => {
    const next = [...actions];
    next[index] = { ...next[index], ...updates };
    onChange(next);
  };

  const removeAction = (index) => {
    onChange(actions.filter((_, i) => i !== index));
  };

  const moveAction = (from, to) => {
    if (to < 0 || to >= actions.length) return;
    const next = [...actions];
    const [item] = next.splice(from, 1);
    next.splice(to, 0, item);
    onChange(next);
  };

  return (
    <div className="flex flex-col gap-2">
      {actions.map((action, i) => (
        <ActionItem
          key={i}
          action={action}
          index={i}
          total={actions.length}
          onUpdate={(updates) => updateAction(i, updates)}
          onRemove={() => removeAction(i)}
          onMoveUp={() => moveAction(i, i - 1)}
          onMoveDown={() => moveAction(i, i + 1)}
        />
      ))}
      <button
        onClick={addAction}
        className="px-3 py-2 text-xs font-mono rounded border border-dashed border-border text-text-dim hover:text-text-secondary hover:border-border-active transition-colors cursor-pointer"
      >
        + Add Action
      </button>
    </div>
  );
}

function ActionItem({ action, index, total, onUpdate, onRemove, onMoveUp, onMoveDown }) {
  const [expanded, setExpanded] = useState(true);

  return (
    <div className="rounded-lg border border-border bg-bg-tertiary overflow-hidden">
      {/* Header */}
      <div
        className="flex items-center gap-2 px-3 py-2 cursor-pointer hover:bg-bg-hover"
        onClick={() => setExpanded(!expanded)}
      >
        <span className="text-xs text-text-dim">{expanded ? "▾" : "▸"}</span>
        <select
          className="bg-transparent text-xs font-mono text-text-primary outline-none cursor-pointer"
          value={action.type || ""}
          onClick={(e) => e.stopPropagation()}
          onChange={(e) => onUpdate({ type: e.target.value })}
        >
          {ACTION_TYPES.map((t) => (
            <option key={t.value} value={t.value}>{t.label}</option>
          ))}
        </select>
        <div className="flex-1" />
        <label className="flex items-center gap-1 text-[10px] text-text-dim" onClick={(e) => e.stopPropagation()}>
          <input
            type="checkbox"
            checked={action.blocking || false}
            onChange={(e) => onUpdate({ blocking: e.target.checked })}
            className="accent-accent-blue"
          />
          blocking
        </label>
        <div className="flex gap-0.5">
          {index > 0 && (
            <button onClick={(e) => { e.stopPropagation(); onMoveUp(); }} className="text-[10px] text-text-dim hover:text-text-primary px-1 cursor-pointer">▲</button>
          )}
          {index < total - 1 && (
            <button onClick={(e) => { e.stopPropagation(); onMoveDown(); }} className="text-[10px] text-text-dim hover:text-text-primary px-1 cursor-pointer">▼</button>
          )}
          <button onClick={(e) => { e.stopPropagation(); onRemove(); }} className="text-[10px] text-accent-red hover:text-accent-red px-1 cursor-pointer">✕</button>
        </div>
      </div>

      {/* Body */}
      {expanded && (
        <div className="px-3 pb-3 flex flex-col gap-2 border-t border-border pt-2">
          <ActionFields action={action} onUpdate={onUpdate} />
        </div>
      )}
    </div>
  );
}

function ActionFields({ action, onUpdate }) {
  const type = action.type;

  const field = (key, label, inputType = "text", placeholder = "") => (
    <div className="flex flex-col gap-1">
      <label className="text-[10px] text-text-dim">{label}</label>
      {inputType === "textarea" ? (
        <textarea
          className="input-field min-h-[60px] resize-y text-xs"
          value={action[key] || ""}
          onChange={(e) => onUpdate({ [key]: e.target.value })}
          placeholder={placeholder}
        />
      ) : (
        <input
          type={inputType}
          className="input-field text-xs"
          value={action[key] ?? ""}
          onChange={(e) =>
            onUpdate({ [key]: inputType === "number" ? parseFloat(e.target.value) : e.target.value })
          }
          placeholder={placeholder}
        />
      )}
    </div>
  );

  switch (type) {
    case "play_audio":
      return (
        <>
          {field("file", "File Path", "text", "./assets/audio/file.wav")}
          {field("source", "Or Task Source", "text", "$task_id")}
          {field("layer", "Layer", "text", "main")}
          <div className="flex flex-col gap-1">
            <label className="text-[10px] text-text-dim">Linear gain (0–10, 1 = unity, 10 ≈ +20 dB)</label>
            <input
              type="number"
              min="0"
              max="10"
              step="0.05"
              className="input-field text-xs w-24"
              value={action.volume ?? 1}
              onChange={(e) => onUpdate({ volume: parseFloat(e.target.value) || 0 })}
            />
            <p className="text-[10px] text-text-dim leading-relaxed">
              Amplitude multiplier vs the file: below 1 attenuates; above 1 applies boost (pydub), up to ~+20 dB at 10.
            </p>
          </div>
          <label className="flex items-center gap-2 text-xs text-text-secondary cursor-pointer">
            <input type="checkbox" checked={action.loop || false} onChange={(e) => onUpdate({ loop: e.target.checked })} className="accent-accent-blue" />
            Loop indefinitely
          </label>
        </>
      );
    case "play_video":
      return (
        <>
          {field("file", "File Path", "text", "./assets/video/file.mp4")}
          <div className="flex flex-col gap-1">
            <label className="text-[10px] text-text-dim">Media Volume (0–1)</label>
            <input
              type="number"
              min="0"
              max="1"
              step="0.05"
              className="input-field text-xs w-24"
              value={action.volume ?? 1}
              onChange={(e) => onUpdate({ volume: parseFloat(e.target.value) || 0 })}
            />
          </div>
        </>
      );
    case "generate_text":
      return (
        <>
          {field("task_id", "Task ID", "text", "monologue")}
          {field("prompt", "Prompt", "textarea", "Generate a monologue...")}
          {field("prompt_source", "Prompt Source (file or $task)", "text", "$audience_words or ./assets/text/lyrics.txt")}
          {field("prompt_append_task", "Append Task Output", "text", "audience_words")}
          {field("output_file", "Output File", "text", "./assets/text/monologue.txt")}
          <InjectConfig action={action} onUpdate={onUpdate} />
        </>
      );
    case "generate_music": {
      const model = action.model || "stability-ai/stable-audio-2.5";
      const isLyria = typeof model === "string" && model.includes("lyria");
      const presetIds = MUSIC_MODELS.map((m) => m.value);
      const modelUnknown = !presetIds.includes(model);
      return (
        <>
          {field("task_id", "Task ID", "text", "rap_beat")}
          <div className="flex flex-col gap-1">
            <label className="text-[10px] text-text-dim">Model</label>
            <select
              className="input-field text-xs"
              value={model}
              onChange={(e) => onUpdate({ model: e.target.value })}
            >
              {modelUnknown && (
                <option value={model}>{model} (from script)</option>
              )}
              {MUSIC_MODELS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </div>
          {field("prompt", "Prompt", "textarea", "boom-bap beat...")}
          {field("prompt_source", "Prompt Source (file or $task)", "text", "$task_id or ./path/to/prompt.txt")}
          {field("prompt_append_task", "Append Task Output", "text", "audience_words")}
          {isLyria ? (
            <>
              <p className="text-[10px] text-text-dim leading-relaxed">
                Lyria uses only the prompt (and optional images). Duration is fixed by the model
                (~30s for Lyria 3, up to ~3 min for Pro). Put timing hints in the prompt if needed.
              </p>
              {field(
                "images",
                "Image URLs or paths (optional, comma-separated)",
                "text",
                "https://... or ./assets/images/ref.png"
              )}
            </>
          ) : (
            <>
              {field("duration", "Duration (sec)", "number")}
              {field("steps", "Steps (diffusion)", "number")}
              {field("cfg_scale", "CFG scale", "number")}
              {field("seed", "Seed (optional, integer)", "text")}
            </>
          )}
          {field("output_file", "Output File", "text", "./assets/audio/rap_beat.wav")}
          {field("fallback", "Fallback File", "text", "./assets/audio/fallback.mp3")}
        </>
      );
    }
    case "generate_sfx":
      return (
        <>
          {field("task_id", "Task ID", "text", "sfx_hit")}
          {field("model", "Model", "text", "sepal/audiogen")}
          {field("prompt", "Prompt", "textarea", "Short glass breaking sound")}
          {field("prompt_source", "Prompt Source (file or $task)", "text", "")}
          {field("prompt_append_task", "Append Task Output", "text", "")}
          {field("duration", "Duration (sec, 1–10)", "number")}
          {field("output_file", "Output File", "text", "./assets/audio/generated_sfx.wav")}
          {field("layer", "Play on layer", "text", "sfx")}
          <div className="flex flex-col gap-1">
            <label className="text-[10px] text-text-dim">Linear gain (0–10, 1 = unity, 10 ≈ +20 dB)</label>
            <input
              type="number"
              min="0"
              max="10"
              step="0.05"
              className="input-field text-xs w-24"
              value={action.volume ?? 1}
              onChange={(e) => onUpdate({ volume: parseFloat(e.target.value) || 0 })}
            />
          </div>
          <label className="flex items-center gap-2 text-xs text-text-secondary cursor-pointer">
            <input
              type="checkbox"
              checked={action.play_immediately !== false}
              onChange={(e) => onUpdate({ play_immediately: e.target.checked })}
              className="accent-accent-blue"
            />
            Play immediately after generation
          </label>
          {field("temperature", "Temperature (optional)", "number")}
          {field("classifier_free_guidance", "Classifier-free guidance (optional)", "number")}
          {field("output_format", "Output format (wav or mp3)", "text", "wav")}
          {field("fallback", "Fallback File", "text", "./assets/audio/fallback.mp3")}
        </>
      );
    case "generate_tts":
      return (
        <>
          {field("task_id", "Task ID", "text", "tts_audio")}
          {field("model", "Model", "text", "minimax/speech-2.8-turbo")}
          {field("text", "Text (prefix)", "text", "Say this first...")}
          {field("text_append_task", "Append Task Output", "text", "audience_words")}
          {field("text_source", "Text Source (task)", "text", "$generated_text")}
          {field("voice", "Voice", "text", "narrator")}
          {field("output_file", "Output File", "text", "./assets/audio/tts_output.wav")}
          <InjectConfig action={action} onUpdate={onUpdate} />
        </>
      );
    case "generate_video":
      return (
        <>
          {field("task_id", "Task ID", "text", "visual_1")}
          {field("model", "Model", "text", "google/veo-2")}
          {field("prompt", "Prompt", "textarea", "Surreal dreamscape...")}
          {field("prompt_source", "Prompt Source (file or $task)", "text", "$task_id or ./path/to/prompt.txt")}
          {field("prompt_append_task", "Append Task Output", "text", "audience_words")}
          {field("duration", "Duration (sec)", "number")}
          {field("output_file", "Output File", "text", "./assets/video/generated.mp4")}
        </>
      );
    case "generate_image":
      return (
        <>
          {field("task_id", "Task ID", "text", "wordcloud")}
          {field("model", "Model", "text", "google/imagen-4")}
          {field("prompt", "Prompt", "textarea", "A word cloud image...")}
          {field("prompt_source", "Prompt Source (file or $task)", "text", "$audience_words or ./assets/text/words.txt")}
          {field("prompt_append_task", "Append Task Output", "text", "audience_words")}
          {field("aspect_ratio", "Aspect Ratio", "text", "16:9")}
          {field("output_file", "Output File", "text", "./assets/images/wordcloud.png")}
        </>
      );
    case "fetch_submissions":
      return (
        <>
          {field("task_id", "Task ID", "text", "audience_words")}
          {field("table", "DynamoDB Table", "text", "audience_lyrics")}
        </>
      );
    case "show_qr":
      return field("url", "URL", "text", "https://your-site.com/submit");
    case "start_timer":
      return (
        <>
          {field("duration", "Duration (sec)", "number")}
          <label className="flex items-center gap-2 text-xs text-text-secondary cursor-pointer">
            <input type="checkbox" checked={action.display !== false} onChange={(e) => onUpdate({ display: e.target.checked })} className="accent-accent-blue" />
            Show to audience
          </label>
        </>
      );
    case "audio_control":
      return (
        <>
          {field("layer", "Layer", "text", "music")}
          <div className="flex flex-col gap-1">
            <label className="text-[10px] text-text-dim">Command</label>
            <select
              className="input-field text-xs"
              value={action.command || ""}
              onChange={(e) => onUpdate({ command: e.target.value })}
            >
              <option value="set_volume">Set Volume</option>
              <option value="set_speed">Set Speed</option>
              <option value="set_pitch">Set Pitch</option>
              <option value="fade_out">Fade Out</option>
              <option value="fade_in">Fade In</option>
              <option value="stop">Stop</option>
            </select>
          </div>
          {field("value", "Value", "number")}
          {field("duration", "Duration (sec)", "number")}
          <p className="text-[10px] text-text-dim leading-relaxed mt-1">
            <span className="font-mono text-text-secondary">Set volume</span>: same linear gain as Play Audio (0–10; fades only when both start and end are ≤ 1).{" "}
            <span className="font-mono text-text-secondary">Set speed</span> / <span className="font-mono text-text-secondary">Set pitch</span>:{" "}
            <strong>multipliers</strong> (1 = no change). Speed = playback rate (scipy resample). Pitch = frequency multiplier, 2 ≈ one octave (length-preserving resample).{" "}
            Processed in Python and re-decoded to pygame; <strong>restarts the clip from the start</strong>. Duration ramp not implemented yet.
          </p>
        </>
      );
    case "send_osc":
      return (
        <>
          {field("address", "Address", "text", "/custom/message")}
          {field("args", "Args (JSON array)", "text", '[1.0, "hello"]')}
        </>
      );
    default:
      return <p className="text-xs text-text-dim">Select an action type</p>;
  }
}

function InjectConfig({ action, onUpdate }) {
  const inject = action.inject || {};

  const updateInject = (key, value) => {
    onUpdate({ inject: { ...inject, [key]: value } });
  };

  return (
    <div className="mt-2 p-2 rounded border border-border bg-bg-secondary">
      <p className="text-[10px] font-mono text-text-dim mb-2">INJECT CONFIG</p>
      <div className="flex flex-col gap-2">
        <div className="flex flex-col gap-1">
          <label className="text-[10px] text-text-dim">Mode</label>
          <select
            className="input-field text-xs"
            value={inject.mode || "per_sentence"}
            onChange={(e) => updateInject("mode", e.target.value)}
          >
            <option value="per_sentence">Per Sentence</option>
            <option value="per_line">Per Line</option>
            <option value="tts_driven">TTS Driven</option>
          </select>
        </div>
        <div className="flex items-center gap-2">
          <label className="text-[10px] text-text-dim">Caption Color</label>
          <input
            type="color"
            className="w-6 h-6 rounded border border-border cursor-pointer"
            value={inject.caption_color || "#ff4444"}
            onChange={(e) => updateInject("caption_color", e.target.value)}
          />
          <input
            className="input-field text-xs w-24"
            value={inject.caption_color || "#ff4444"}
            onChange={(e) => updateInject("caption_color", e.target.value)}
          />
        </div>
        <div className="flex flex-col gap-1">
          <label className="text-[10px] text-text-dim">Trigger Mode</label>
          <select
            className="input-field text-xs"
            value={inject.trigger_mode || "speech"}
            onChange={(e) => updateInject("trigger_mode", e.target.value)}
          >
            <option value="speech">Speech</option>
            <option value="auto">Auto</option>
          </select>
        </div>
        <div className="flex flex-col gap-1">
          <label className="text-[10px] text-text-dim">Overlay Media (optional)</label>
          <div className="flex items-center gap-2">
            <input
              className="input-field text-xs flex-1"
              placeholder="e.g. ./assets/images/disclaimer.png"
              value={inject.overlay?.file || ""}
              onChange={(e) => {
                if (e.target.value) {
                  updateInject("overlay", {
                    type: "show_image",
                    id: inject.overlay?.id || "inject_overlay",
                    file: e.target.value,
                    position: inject.overlay?.position || "corner",
                  });
                } else {
                  const { overlay, ...rest } = inject;
                  onUpdate({ inject: rest });
                }
              }}
            />
            {inject.overlay && (
              <button
                className="text-[10px] text-red-400 hover:text-red-300 shrink-0"
                onClick={() => {
                  const { overlay, ...rest } = inject;
                  onUpdate({ inject: rest });
                }}
              >
                Remove
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
