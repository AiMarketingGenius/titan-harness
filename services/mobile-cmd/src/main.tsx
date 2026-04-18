import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import App from "./App.tsx";


// Service worker registration — iOS 16.4+ requires SW registration BEFORE
// any navigator.credentials.create() call for standalone PWAs.
if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    navigator.serviceWorker
      .register("/sw.js", { scope: "/" })
      .catch((err) => console.warn("[mobile-cmd] sw register failed:", err));
  });
}


createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
