/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_URL: string;
  readonly VITE_API_USE_PROXY?: string;
  readonly VITE_LEGACY_UPLOAD_BASE_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
