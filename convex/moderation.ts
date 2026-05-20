// Content moderation - explicit content filter
// This is a basic word filter. For production, consider integrating an AI moderation API.

const BLOCKED_PATTERNS: RegExp[] = [
  // Slurs and hate speech patterns
  /\bn[i1][g9]{1,2}[e3]r/i,
  /\bf[a@]g{1,2}[o0]t/i,
  /\bk[i1]k[e3]/i,
  /\bsp[i1]c/i,
  /\bch[i1]nk/i,
  /\btr[a@]nn/i,
  /\br[e3]t[a@]rd/i,

  // Extreme explicit content
  /\bp[o0]rn/i,
  /\bhent[a@][i1]/i,
  /\bx{2,}[- ]?r[a@]t[e3]d/i,

  // Threats
  /\bk[i1]ll\s+y[o0]u(rself)?/i,
  /\bdie\s+in\s+a/i,
  /\bd[o0]x{1,2}(ing|ed)?/i,

  // Spam patterns
  /(.)\1{10,}/i, // Excessive character repetition
];

export interface ModerationResult {
  isClean: boolean;
  reason?: string;
}

export function moderateContent(content: string): ModerationResult {
  const normalized = content.toLowerCase().trim();

  for (const pattern of BLOCKED_PATTERNS) {
    if (pattern.test(normalized)) {
      return {
        isClean: false,
        reason: "Content flagged by automated filter. You may appeal this decision.",
      };
    }
  }

  return { isClean: true };
}
