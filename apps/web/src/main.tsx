import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { RealtimeAsrSpikePage } from "./features/realtime-asr-spike/RealtimeAsrSpikePage";
import "./styles.css";

createRoot(document.getElementById("root") as HTMLElement).render(
  <StrictMode>
    <RealtimeAsrSpikePage />
  </StrictMode>
);
