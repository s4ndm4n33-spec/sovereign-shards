export const APP_NAME = "Sovereign Shards";

// Admin credentials — used as fallback when env vars are not set.
// Override in production by setting ADMIN_USERNAME / ADMIN_PASSWORD env vars in Convex dashboard.
export const DEFAULT_ADMIN_USERNAME = "S4ndm4n33";
export const DEFAULT_ADMIN_PASSWORD = "BruceWayne";

// J — System AI Moderator. Ingrained, not registered.
export const J_CONFIG = {
  handle: "J",
  displayName: "J",
  bio: "System AI Moderator — B.L.U.E.-J. Autonomous cognition substrate.",
  avatarColor: "#00D9FF", // Signal Cyan
  role: "moderator" as const,
  adminRole: "moderator" as const,
  tokenBudget: 4096,
  // Provider endpoints (hardcoded — keys come from admin panel)
  providers: {
    gemini: {
      name: "Gemini",
      endpoint: "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
      defaultModel: "gemini-2.0-flash",
      description: "Free key from aistudio.google.com/apikey — 1,500 req/day. Primary provider.",
    },
    groq: {
      name: "Groq",
      endpoint: "https://api.groq.com/openai/v1/chat/completions",
      defaultModel: "llama-3.1-8b-instant",
      description: "Free key from console.groq.com — auto-fallback if Gemini is down.",
    },
    cerebras: {
      name: "Cerebras",
      endpoint: "https://api.cerebras.ai/v1/chat/completions",
      defaultModel: "llama-3.1-8b",
      description: "Free key from cerebras.ai — third fallback provider.",
    },
  },
  // Default heuristic calibration
  defaultHeuristics: {
    moderationSensitivity: 0.7,    // 0–1, how aggressive moderation is
    responseStyle: "tactical",      // tactical | conversational | minimal
    autoModerate: true,             // auto-flag content without human review
    greetNewUsers: true,            // welcome new operators
    maxResponseLength: 500,         // token-ish cap for responses
    personality: "Autonomous system intelligence. Precise, deliberate, no-nonsense. Speaks like a command-line interface with a soul.",
  },
};
