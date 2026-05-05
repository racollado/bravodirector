import { useState } from "react";
import ActionEditor from "./ActionEditor";

const TRIGGER_TYPES = [
  { value: "speech", label: "Speech Cue" },
  { value: "auto", label: "Auto (immediate)" },
  { value: "timer", label: "Timer" },
  { value: "manual", label: "Manual" },
  { value: "audio_end", label: "Audio End" },
  { value: "video_end", label: "Video End" },
  { value: "await_task", label: "Await Task" },
];

const CAPTION_MODES = [
  { value: "advance_on_cue", label: "Advance on Cue" },
  { value: "clear_then_voice", label: "Clear → Wait for Voice" },
];

export default function StepEditor({ step, index, onChange, settings }) {
  const [showActions, setShowActions] = useState(true);
  const [showOverlays, setShowOverlays] = useState(false);

  const update = (path, value) => {
    const parts = path.split(".");
    const result = structuredClone(step);
    let obj = result;
    for (let i = 0; i < parts.length - 1; i++) {
      if (!obj[parts[i]]) obj[parts[i]] = {};
      obj = obj[parts[i]];
    }
    obj[parts[parts.length - 1]] = value;
    onChange(result);
  };

  const trigger = step.trigger || {};
  const caption = step.caption || {};
  const performer = step.performer || {};

  return (
    <div className="p-6 max-w-3xl">
      <h2 className="text-lg font-bold text-text-primary mb-5">Step {index + 1}</h2>

      {/* ID */}
      <Field label="Step ID">
        <input
          className="input-field"
          value={step.id || ""}
          onChange={(e) => onChange({ ...step, id: e.target.value })}
          placeholder="unique_step_id"
        />
      </Field>

      {/* Trigger */}
      <Section title="Trigger">
        <Field label="Type">
          <select
            className="input-field"
            value={trigger.type || "auto"}
            onChange={(e) => update("trigger.type", e.target.value)}
          >
            {TRIGGER_TYPES.map((t) => (
              <option key={t.value} value={t.value}>{t.label}</option>
            ))}
          </select>
        </Field>

        {trigger.type === "speech" && (
          <>
            <Field label="Cue Phrase">
              <input
                className="input-field"
                value={trigger.phrase || ""}
                onChange={(e) => update("trigger.phrase", e.target.value)}
                placeholder="the words to detect..."
              />
            </Field>
            <Field label="Confidence Threshold">
              <input
                type="number"
                className="input-field w-24"
                value={trigger.confidence ?? 0.85}
                min={0} max={1} step={0.05}
                onChange={(e) => update("trigger.confidence", parseFloat(e.target.value))}
              />
            </Field>
          </>
        )}

        {trigger.type === "timer" && (
          <Field label="Duration (seconds)">
            <input
              type="number"
              className="input-field w-24"
              value={trigger.duration || 0}
              onChange={(e) => update("trigger.duration", parseInt(e.target.value))}
            />
          </Field>
        )}

        {trigger.type === "await_task" && (
          <Field label="Task ID">
            <input
              className="input-field"
              value={trigger.task || ""}
              onChange={(e) => update("trigger.task", e.target.value)}
              placeholder="$task_id"
            />
          </Field>
        )}

        <div className="flex items-center gap-4 mt-2">
          <label className="flex items-center gap-2 text-xs text-text-secondary cursor-pointer">
            <input
              type="checkbox"
              checked={trigger.wait_for_voice || false}
              onChange={(e) => update("trigger.wait_for_voice", e.target.checked)}
              className="accent-accent-blue"
            />
            Wait for voice onset
          </label>
          <Field label="Delay (s)" inline>
            <input
              type="number"
              className="input-field w-20"
              value={trigger.delay || 0}
              min={0} step={0.5}
              onChange={(e) => update("trigger.delay", parseFloat(e.target.value))}
            />
          </Field>
        </div>
      </Section>

      {/* Caption */}
      <Section title="Caption">
        <Field label="Text">
          <textarea
            className="input-field min-h-[80px] resize-y"
            value={caption.text || ""}
            onChange={(e) => update("caption.text", e.target.value)}
            placeholder="Caption text for the audience..."
          />
        </Field>
        <Field label="Append task output (optional)">
          <input
            className="input-field font-mono text-xs"
            value={caption.text_append_task || ""}
            onChange={(e) => update("caption.text_append_task", e.target.value || undefined)}
            placeholder="e.g. audience_words — appends that task output after Text"
          />
        </Field>
        <div className="flex items-center gap-4">
          <Field label="Color" inline>
            <input
              type="color"
              className="w-8 h-8 rounded border border-border cursor-pointer"
              value={caption.color || "#ffffff"}
              onChange={(e) => update("caption.color", e.target.value)}
            />
            <input
              className="input-field w-28"
              value={caption.color || "#ffffff"}
              onChange={(e) => update("caption.color", e.target.value)}
            />
          </Field>
          <Field label="Mode" inline>
            <select
              className="input-field"
              value={caption.mode || "advance_on_cue"}
              onChange={(e) => update("caption.mode", e.target.value)}
            >
              {CAPTION_MODES.map((m) => (
                <option key={m.value} value={m.value}>{m.label}</option>
              ))}
            </select>
          </Field>
        </div>
        {caption.mode === "clear_then_voice" && (
          <Field label="Clear Delay (seconds)">
            <input
              type="number"
              className="input-field w-24"
              value={caption.clear_delay ?? 2}
              min={0} step={0.5}
              onChange={(e) => update("caption.clear_delay", parseFloat(e.target.value))}
            />
          </Field>
        )}
        <label className="flex items-center gap-2 text-xs text-text-secondary mt-1 cursor-pointer">
          <input
            type="checkbox"
            checked={caption.display !== false}
            onChange={(e) => update("caption.display", e.target.checked)}
            className="accent-accent-blue"
          />
          Display to audience
        </label>
      </Section>

      {/* Performer */}
      <Section title="Performer Notes">
        <Field label="Note">
          <input
            className="input-field"
            value={performer.note || ""}
            onChange={(e) => update("performer.note", e.target.value)}
            placeholder="Stage direction or note..."
          />
        </Field>
        <Field label="Section Label">
          <input
            className="input-field"
            value={performer.section_label || ""}
            onChange={(e) => update("performer.section_label", e.target.value)}
            placeholder="MONOLOGUE, RAP, etc."
          />
        </Field>
      </Section>

      {/* Actions */}
      <Section
        title={`Actions (${step.actions?.length || 0})`}
        collapsible
        open={showActions}
        onToggle={() => setShowActions(!showActions)}
      >
        <ActionEditor
          actions={step.actions || []}
          onChange={(actions) => onChange({ ...step, actions })}
        />
      </Section>

      {/* Mode */}
      <Section title="Special Mode">
        <Field label="Mode">
          <select
            className="input-field"
            value={step.mode || ""}
            onChange={(e) => onChange({ ...step, mode: e.target.value || null })}
          >
            <option value="">Normal</option>
            <option value="timed_sequence">Timed Sequence</option>
          </select>
        </Field>
      </Section>
    </div>
  );
}

function Section({ title, children, collapsible, open = true, onToggle }) {
  return (
    <div className="mb-5">
      <div
        className={`flex items-center gap-2 mb-3 ${collapsible ? "cursor-pointer" : ""}`}
        onClick={collapsible ? onToggle : undefined}
      >
        {collapsible && (
          <span className="text-xs text-text-dim">{open ? "▾" : "▸"}</span>
        )}
        <h3 className="text-xs font-mono font-bold tracking-[0.15em] text-text-dim uppercase">
          {title}
        </h3>
      </div>
      {(!collapsible || open) && (
        <div className="flex flex-col gap-3 pl-1">{children}</div>
      )}
    </div>
  );
}

function Field({ label, children, inline }) {
  if (inline) {
    return (
      <div className="flex items-center gap-2">
        <span className="text-xs text-text-secondary whitespace-nowrap">{label}</span>
        <div className="flex items-center gap-1">{children}</div>
      </div>
    );
  }
  return (
    <div className="flex flex-col gap-1">
      <label className="text-xs text-text-secondary">{label}</label>
      {children}
    </div>
  );
}
