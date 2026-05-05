import { Routes, Route } from "react-router-dom";
import PerformerView from "./performer/PerformerView";
import EditorView from "./editor/EditorView";

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<PerformerView />} />
      <Route path="/editor" element={<EditorView />} />
    </Routes>
  );
}
