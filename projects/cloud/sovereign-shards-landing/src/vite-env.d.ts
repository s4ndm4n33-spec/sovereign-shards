// Copyright (c) 2026 Mike McCollum
//
// Licensed under the Sovereign Shards License.
// See LICENSE.md for details.

/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_CONVEX_URL: string;
  readonly VITE_IS_PREVIEW: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
