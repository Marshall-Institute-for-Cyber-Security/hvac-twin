import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "../styles.css";
import AttackApp from "./AttackApp";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <AttackApp />
  </StrictMode>,
);
