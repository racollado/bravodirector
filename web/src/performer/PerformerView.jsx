import { useEffect, useCallback } from "react";
import { useShowState } from "../api/websocket";
import StatusBar from "./components/StatusBar";
import CurrentLine from "./components/CurrentLine";
import LiveSpeechStrip from "./components/LiveSpeechStrip";
import UpcomingLines from "./components/UpcomingLines";
import TranscriptPanel from "./components/TranscriptPanel";
import TaskPanel from "./components/TaskPanel";
import ControlBar from "./components/ControlBar";
import ScriptStartPicker from "./components/ScriptStartPicker";

export default function PerformerView() {
  const { state, connected, sendCommand } = useShowState();

  const handleKeyDown = useCallback(
    (e) => {
      if (e.target.tagName === "INPUT" || e.target.tagName === "TEXTAREA") return;

      const key = e.key.toUpperCase();
      switch (key) {
        case "P":
          sendCommand("pause");
          break;
        case "F":
          sendCommand("add_failure");
          break;
        case "Q":
          sendCommand("skip_with_failure");
          break;
        case "W":
          sendCommand("skip_clean");
          break;
        case "E":
          sendCommand("go_back");
          break;
        case "S":
          if (state.show_state === "idle") sendCommand("start", { start_index: 0 });
          break;
        case "R":
          if (e.shiftKey) sendCommand("reset");
          break;
        default:
          break;
      }
    },
    [sendCommand, state.show_state]
  );

  useEffect(() => {
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [handleKeyDown]);

  const isIdle = state.show_state === "idle";

  return (
    <div className="h-screen flex flex-col overflow-hidden select-none">
      <StatusBar state={state} connected={connected} />

      <div className="flex-1 min-h-0 grid grid-cols-[1fr_340px] gap-0 overflow-hidden">
        {/* Left: main content */}
        <div className="flex flex-col min-h-0 overflow-hidden border-r border-border">
          {isIdle ? (
            <ScriptStartPicker
              showTitle={state.show_title}
              stepsOutline={state.steps_outline}
              onStartAtIndex={(index) => sendCommand("start", { start_index: index })}
            />
          ) : (
            <>
              <div className="shrink-0">
                <CurrentLine
                  step={state.current_step}
                  showState={state.show_state}
                  displayedCaption={state.displayed_caption}
                  loadingMessage={state.loading_message}
                />
              </div>
              <div className="shrink-0">
                <LiveSpeechStrip transcript={state.transcript} mic={state.mic} />
              </div>
              <UpcomingLines steps={state.upcoming_steps} currentIndex={state.current_index} />
            </>
          )}
        </div>

        {/* Right: sidebar */}
        <div className="flex flex-col min-h-0 overflow-hidden bg-bg-secondary">
          <TranscriptPanel transcript={state.transcript} />
          <TaskPanel tasks={state.tasks} timer={state.timer} audioLayers={state.audio_layers} />
        </div>
      </div>

      <ControlBar
        state={state}
        sendCommand={sendCommand}
      />
    </div>
  );
}
