import { createRoot } from "react-dom/client";
import App from "./App.tsx";
import "./index.css";
import { getResolvedApiBaseForDisplay } from "@/lib/apiBase";

if (import.meta.env.DEV) {
  console.info("[dev] API:", getResolvedApiBaseForDisplay());
}

createRoot(document.getElementById("root")!).render(<App />);
