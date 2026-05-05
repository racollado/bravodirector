import { useState, useEffect, useCallback, useRef } from "react";
import StepList from "./components/StepList";
import StepEditor from "./components/StepEditor";
import SettingsPanel from "./components/SettingsPanel";
import PreviewPanel from "./components/PreviewPanel";

const DEFAULT_SETTINGS = {
  osc: { host: "127.0.0.1", port: 9000 },
  speech: { provider: "assemblyai", default_confidence: 0.85, default_cue_words: 4 },
  models: { text: "gemini-2.5-flash", music: "stability-ai/stable-audio-2.5", sfx: "sepal/audiogen", tts: "minimax/speech-2.8-turbo", video: "google/veo-2" },
  audio_layers: ["main", "music", "sfx"],
  performer: { shortcuts: { pause: "P", skip_with_failure: "Q", skip_clean: "W", go_back: "E", start_show: "S" }, pause_caption: "[OFFSCRIPT]" },
  failure: { sfx: "./assets/audio/fail_buzzer.mp3", display_to_audience: true, osc_address: "/failure/increment" },
};

const DEFAULT_STEP = {
  id: "",
  trigger: { type: "speech", phrase: "", confidence: 0.85 },
  caption: { text: "", color: "#ffffff", mode: "advance_on_cue", display: true, clear_delay: 0 },
  actions: [],
  overlays: [],
  performer: { note: "", section_label: "" },
  mode: null,
};

export default function EditorView() {
  const [script, setScript] = useState({
    title: "Untitled Show",
    version: "2.0",
    settings: DEFAULT_SETTINGS,
    segments: [{ id: "segment_1", name: "Segment 1", steps: [] }],
  });
  const [selectedSegment, setSelectedSegment] = useState(0);
  const [selectedStep, setSelectedStep] = useState(null);
  const [activeTab, setActiveTab] = useState("steps"); // steps | settings | preview
  const fileInputRef = useRef(null);

  // Load script from server if available
  useEffect(() => {
    fetch("/api/script")
      .then((r) => r.ok ? r.json() : null)
      .then((data) => { if (data?.segments) setScript(data); })
      .catch(() => {});
  }, []);

  const currentSegment = script.segments[selectedSegment] || script.segments[0];
  const steps = currentSegment?.steps || [];

  const updateStep = useCallback(
    (stepIndex, updates) => {
      setScript((prev) => {
        const next = structuredClone(prev);
        const seg = next.segments[selectedSegment];
        if (seg && seg.steps[stepIndex]) {
          seg.steps[stepIndex] = { ...seg.steps[stepIndex], ...updates };
        }
        return next;
      });
    },
    [selectedSegment]
  );

  /** Insert a new step at `atIndex` (0 = top, steps.length = append). Selects the new step. */
  const insertStepAt = useCallback((atIndex) => {
    setScript((prev) => {
      const next = structuredClone(prev);
      const seg = next.segments[selectedSegment];
      const newStep = {
        ...structuredClone(DEFAULT_STEP),
        id: `step_${Date.now()}`,
      };
      const pos = Math.max(0, Math.min(atIndex, seg.steps.length));
      seg.steps.splice(pos, 0, newStep);
      return next;
    });
    setSelectedStep(atIndex);
  }, [selectedSegment]);

  const deleteStep = useCallback(
    (index) => {
      setScript((prev) => {
        const next = structuredClone(prev);
        next.segments[selectedSegment].steps.splice(index, 1);
        return next;
      });
      setSelectedStep(null);
    },
    [selectedSegment]
  );

  const moveStep = useCallback(
    (from, to) => {
      if (to < 0 || to >= steps.length) return;
      setScript((prev) => {
        const next = structuredClone(prev);
        const seg = next.segments[selectedSegment];
        const [item] = seg.steps.splice(from, 1);
        seg.steps.splice(to, 0, item);
        return next;
      });
      setSelectedStep(to);
    },
    [selectedSegment, steps.length]
  );

  const addSegment = useCallback(() => {
    setScript((prev) => {
      const next = structuredClone(prev);
      next.segments.push({
        id: `segment_${Date.now()}`,
        name: `Segment ${next.segments.length + 1}`,
        steps: [],
      });
      return next;
    });
  }, []);

  const deleteSegment = useCallback(
    (index) => {
      setScript((prev) => {
        if (prev.segments.length <= 1) return prev;
        const next = structuredClone(prev);
        next.segments.splice(index, 1);
        return next;
      });
      setSelectedSegment((s) => Math.min(s, script.segments.length - 2));
      setSelectedStep(null);
    },
    [script.segments.length]
  );

  const moveSegment = useCallback(
    (from, direction) => {
      const to = from + direction;
      setScript((prev) => {
        if (to < 0 || to >= prev.segments.length) return prev;
        const next = structuredClone(prev);
        const [seg] = next.segments.splice(from, 1);
        next.segments.splice(to, 0, seg);
        return next;
      });
      setSelectedSegment(to);
      setSelectedStep(null);
    },
    []
  );

  const updateSegment = useCallback(
    (index, key, value) => {
      setScript((prev) => {
        const next = structuredClone(prev);
        next.segments[index][key] = value;
        return next;
      });
    },
    []
  );

  const updateSettings = useCallback((updates) => {
    setScript((prev) => ({
      ...prev,
      settings: { ...prev.settings, ...updates },
    }));
  }, []);

  const exportJSON = () => {
    const blob = new Blob([JSON.stringify(script, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${script.title.replace(/\s+/g, "_").toLowerCase()}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const importJSON = (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (ev) => {
      try {
        const data = JSON.parse(ev.target.result);
        if (data.segments) {
          setScript(data);
          setSelectedSegment(0);
          setSelectedStep(null);
        }
      } catch {}
    };
    reader.readAsText(file);
  };

  const saveToServer = async () => {
    try {
      await fetch("/api/script", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ script }),
      });
    } catch {}
  };

  return (
    <div className="h-screen flex flex-col overflow-hidden">
      {/* Top bar */}
      <div className="flex items-center justify-between px-5 py-2.5 bg-bg-secondary border-b border-border">
        <div className="flex items-center gap-4">
          <h1 className="text-sm font-bold text-accent-purple tracking-wide">SCRIPT EDITOR</h1>
          <input
            className="bg-transparent text-text-primary text-sm font-medium border-b border-transparent focus:border-accent-blue outline-none px-1 py-0.5"
            value={script.title}
            onChange={(e) => setScript((p) => ({ ...p, title: e.target.value }))}
          />
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => fileInputRef.current?.click()}
            className="px-3 py-1.5 text-xs font-mono rounded bg-bg-tertiary text-text-secondary hover:bg-bg-hover border border-border transition-colors cursor-pointer"
          >
            Import
          </button>
          <input ref={fileInputRef} type="file" accept=".json" onChange={importJSON} className="hidden" />
          <button
            onClick={exportJSON}
            className="px-3 py-1.5 text-xs font-mono rounded bg-accent-blue/10 text-accent-blue hover:bg-accent-blue/20 border border-accent-blue/30 transition-colors cursor-pointer"
          >
            Export JSON
          </button>
          <button
            onClick={saveToServer}
            className="px-3 py-1.5 text-xs font-mono rounded bg-accent-green/10 text-accent-green hover:bg-accent-green/20 border border-accent-green/30 transition-colors cursor-pointer"
          >
            Save
          </button>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex items-center gap-0 px-5 bg-bg-secondary border-b border-border">
        {["steps", "settings", "preview"].map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={`px-4 py-2 text-xs font-mono uppercase tracking-wider transition-colors cursor-pointer ${
              activeTab === tab
                ? "text-accent-blue border-b-2 border-accent-blue"
                : "text-text-dim hover:text-text-secondary"
            }`}
          >
            {tab}
          </button>
        ))}
      </div>

      {/* Content */}
      <div className="flex-1 overflow-hidden">
        {activeTab === "steps" && (
          <div className="h-full grid grid-cols-[320px_1fr] overflow-hidden">
            {/* Step list sidebar */}
            <div className="flex flex-col overflow-hidden border-r border-border bg-bg-secondary">
              {/* Segment selector */}
              <div className="px-3 py-2 border-b border-border">
                <div className="flex items-center gap-2 mb-2">
                  <select
                    value={selectedSegment}
                    onChange={(e) => {
                      setSelectedSegment(Number(e.target.value));
                      setSelectedStep(null);
                    }}
                    className="flex-1 bg-bg-tertiary text-text-primary text-xs font-mono px-2 py-1.5 rounded border border-border outline-none"
                  >
                    {script.segments.map((seg, i) => (
                      <option key={seg.id} value={i}>{seg.name || seg.id}</option>
                    ))}
                  </select>
                  <button
                    onClick={addSegment}
                    className="px-2 py-1.5 text-xs font-mono rounded bg-bg-tertiary text-text-secondary hover:bg-bg-hover border border-border cursor-pointer"
                    title="Add segment"
                  >
                    +
                  </button>
                </div>
                <div className="flex flex-col gap-1.5">
                  <div className="flex items-center gap-1.5">
                    <span className="text-[10px] text-text-dim w-8 shrink-0">Name</span>
                    <input
                      className="flex-1 bg-transparent text-text-secondary text-xs border-b border-transparent focus:border-accent-blue outline-none px-1"
                      value={currentSegment?.name || ""}
                      placeholder="Segment name..."
                      onChange={(e) => updateSegment(selectedSegment, "name", e.target.value)}
                    />
                  </div>
                  <div className="flex items-center gap-1.5">
                    <span className="text-[10px] text-text-dim w-8 shrink-0">ID</span>
                    <input
                      className="flex-1 bg-transparent text-text-secondary text-xs font-mono border-b border-transparent focus:border-accent-blue outline-none px-1"
                      value={currentSegment?.id || ""}
                      placeholder="segment_id"
                      onChange={(e) => updateSegment(selectedSegment, "id", e.target.value)}
                    />
                  </div>
                  <div className="flex items-center gap-1 mt-1">
                    <button
                      onClick={() => moveSegment(selectedSegment, -1)}
                      disabled={selectedSegment === 0}
                      className="px-1.5 py-0.5 text-[10px] font-mono rounded bg-bg-tertiary text-text-dim hover:text-text-primary hover:bg-bg-hover border border-border disabled:opacity-30 disabled:cursor-not-allowed cursor-pointer"
                      title="Move segment up"
                    >
                      ▲ Up
                    </button>
                    <button
                      onClick={() => moveSegment(selectedSegment, 1)}
                      disabled={selectedSegment >= script.segments.length - 1}
                      className="px-1.5 py-0.5 text-[10px] font-mono rounded bg-bg-tertiary text-text-dim hover:text-text-primary hover:bg-bg-hover border border-border disabled:opacity-30 disabled:cursor-not-allowed cursor-pointer"
                      title="Move segment down"
                    >
                      ▼ Down
                    </button>
                    <div className="flex-1" />
                    <button
                      onClick={() => {
                        if (script.segments.length > 1 && confirm(`Delete segment "${currentSegment?.name || currentSegment?.id}"?`)) {
                          deleteSegment(selectedSegment);
                        }
                      }}
                      disabled={script.segments.length <= 1}
                      className="px-1.5 py-0.5 text-[10px] font-mono rounded bg-accent-red/10 text-accent-red hover:bg-accent-red/20 border border-accent-red/30 disabled:opacity-30 disabled:cursor-not-allowed cursor-pointer"
                      title="Delete segment"
                    >
                      ✕ Delete
                    </button>
                  </div>
                </div>
              </div>
              <StepList
                steps={steps}
                selectedIndex={selectedStep}
                onSelect={setSelectedStep}
                onInsertAt={insertStepAt}
                onDelete={deleteStep}
                onMove={moveStep}
              />
            </div>

            {/* Step editor */}
            <div className="overflow-y-auto bg-bg-primary">
              {selectedStep !== null && steps[selectedStep] ? (
                <StepEditor
                  step={steps[selectedStep]}
                  index={selectedStep}
                  onChange={(updates) => updateStep(selectedStep, updates)}
                  settings={script.settings}
                />
              ) : (
                <div className="flex items-center justify-center h-full text-text-dim text-sm">
                  Select a step to edit, or click + to add one
                </div>
              )}
            </div>
          </div>
        )}

        {activeTab === "settings" && (
          <div className="h-full overflow-y-auto bg-bg-primary">
            <SettingsPanel settings={script.settings} onChange={updateSettings} />
          </div>
        )}

        {activeTab === "preview" && (
          <div className="h-full overflow-y-auto bg-bg-primary">
            <PreviewPanel script={script} />
          </div>
        )}
      </div>
    </div>
  );
}
