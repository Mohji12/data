import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";
import path from "path";
import { componentTagger } from "lovable-tagger";

const LOCAL_API = "http://127.0.0.1:8000";
const API_PROXY_PREFIXES = [
  "admin",
  "auth",
  "registration",
  "dashboard",
  "exams",
  "videos",
  "certificate",
  "upload",
  "health",
  "events",
  "webhook",
] as const;

function buildDevProxy(proxyTarget: string) {
  const shared = {
    target: proxyTarget,
    changeOrigin: true,
    secure: proxyTarget.startsWith("https://"),
    // Only SPA navigations (GET + HTML). Never bypass POST/PUT API calls.
    bypass: (req: { method?: string; headers?: { accept?: string } }) => {
      if (req.method !== "GET") return undefined;
      const accept = req.headers?.accept ?? "";
      if (accept.includes("text/html")) return "/index.html";
      return undefined;
    },
  };
  return Object.fromEntries(API_PROXY_PREFIXES.map((prefix) => [`/${prefix}`, shared]));
}

// https://vitejs.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  const proxyTarget = (env.VITE_API_URL || LOCAL_API).replace(/\/$/, "");

  return {
    server: {
      host: "localhost",
      port: 8080,
      strictPort: true,
      hmr: {
        host: "localhost",
        port: 8080,
        clientPort: 8080,
        protocol: "ws",
        overlay: false,
      },
      // Dev: browser → localhost:8080 → proxy → VITE_API_URL (or local :8000). Avoids CORS.
      proxy: buildDevProxy(proxyTarget),
    },
    plugins: [react(), mode === "development" && componentTagger()].filter(Boolean),
    resolve: {
      alias: {
        "@": path.resolve(__dirname, "./src"),
      },
    },
  };
});
