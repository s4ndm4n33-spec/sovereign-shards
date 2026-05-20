/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_CONVEX_URL: string;
  readonly VITE_IS_PREVIEW: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
