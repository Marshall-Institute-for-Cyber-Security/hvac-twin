import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "../styles.css";
import DefensesApp from "./DefensesApp";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <DefensesApp />
  </StrictMode>,
);
