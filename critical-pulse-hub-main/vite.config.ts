import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";
import path from "path";
import { componentTagger } from "lovable-tagger";

const LOCAL_API = "http://127.0.0.1:8000";
const API_PROXY_PATTERN =
  "^/(admin|auth|registration|dashboard|exams|videos|certificate|upload|health|events)";

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
      proxy: {
        [API_PROXY_PATTERN]: {
          target: proxyTarget,
          changeOrigin: true,
          secure: proxyTarget.startsWith("https://"),
          bypass: (req) => {
            if (req.headers.accept?.includes("html")) {
              return "/index.html";
            }
          },
        },
      },
    },
    plugins: [react(), mode === "development" && componentTagger()].filter(Boolean),
    resolve: {
      alias: {
        "@": path.resolve(__dirname, "./src"),
      },
    },
  };
});
