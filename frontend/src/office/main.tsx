import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "../styles.css";
import OfficeApp from "./OfficeApp";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <OfficeApp />
  </StrictMode>,
);
