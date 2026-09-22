import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "../styles.css";
import ClosetApp from "./ClosetApp";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <ClosetApp />
  </StrictMode>,
);
