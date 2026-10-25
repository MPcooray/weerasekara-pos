import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { App } from "./App";
import "./styles.css";
import "./pos.css";
import "./payments.css";
import "./adjustments.css";
import "./printing.css";
import "./reporting.css";
import "./orders.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);

