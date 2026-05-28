import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "path";
import { componentTagger } from "lovable-tagger";

const LOCAL_API = "http://127.0.0.1:8000";

// https://vitejs.dev/config/
export default defineConfig(({ mode }) => ({
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
    // Dev: browser calls http://localhost:8080/admin/... → proxied to uvicorn :8000
    proxy: {
      "^/(admin|auth|registration|dashboard|exams|videos|certificate|upload|health|events)": {
        target: LOCAL_API,
        changeOrigin: true,
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
}));
