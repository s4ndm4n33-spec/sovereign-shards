# Video Demo — Technical Specification

**File:** `assets/j-demo.mp4`
**Duration:** 80 seconds (2,400 frames @ 30fps)
**Resolution:** 1920 × 1080 (Full HD)
**Size:** ~20 MB
**Codec:** H.264 (MP4)

---

## Scene Breakdown

| # | Scene | Frames | Time | Content |
|---|-------|--------|------|---------|
| 1 | **Cold Open** | 0–120 | 0:00–4:00 | J logo reveal, "Plug in. Build." tagline |
| 2 | **The Problem** | 120–405 | 4:00–13:30 | Codex, Claude Code, Cline, Aider — all need cloud. All crossed out |
| 3 | **The Solution** | 405–765 | 13:30–25:30 | J boot sequence terminal animation |
| 4 | **Features** | 765–1260 | 25:30–42:00 | 8 feature cards: DAG planner, router, 17 tools, defence suite, tool forge, 3-tier memory, Five Masters, pre-push sandbox |
| 5 | **Architecture** | 1260–1710 | 42:00–57:00 | Flow diagram: User Input → Router → Tool Execute / LLM → Verify → Done |
| 6 | **Competitive** | 1710–1995 | 57:00–66:30 | Comparison table: J vs Codex vs Claude Code vs Aider |
| 7 | **Closing** | 1995–2400 | 66:30–80:00 | Stats grid (146 files, 13.9K lines, 2 deps, 147+ tests), tagline, CTA |

---

## Audio

| Track | Source | Volume | Notes |
|-------|--------|--------|-------|
| **TTS Narration** | ElevenLabs (Adam voice) | 95% | 7 segments, one per scene |
| **Background Music** | K22 (original, Reed Richards) | 18% | Mixed under narration for energy |

### Narration Segments

| File | Scene | Duration |
|------|-------|----------|
| `01_cold_open.mp3` | Cold Open | ~2.5s |
| `02_problem.mp3` | The Problem | ~7.9s |
| `03_solution.mp3` | The Solution | ~9.7s |
| `04_features.mp3` | Features | ~14.5s |
| `05_arch.mp3` | Architecture | ~13.3s |
| `06_competitive.mp3` | Competitive | ~7.5s |
| `07_closing.mp3` | Closing | ~10.9s |

---

## Visual Design

| Element | Value |
|---------|-------|
| **Background** | `#06060F` (deep space black) |
| **Primary Blue** | `#1E90FF` (arc reactor blue) |
| **Gold** | `#FFD700` (Stark gold) |
| **Red** | `#DC143C` (warning red) |
| **Green** | `#00FF41` (terminal green) |
| **Heading Font** | Orbitron (loaded from Google Fonts) |
| **Body Font** | Inter (loaded from Google Fonts) |

### Visual Effects

- **HUD Corners** — Bracket decorations on cards and panels (Iron Man HUD aesthetic)
- **Scan Lines** — CRT overlay effect at 5% opacity
- **Particle Field** — 30 floating dots with subtle parallax
- **Scene Fades** — Cross-fade transitions between all scenes

---

## Build Tool

Built with [Remotion](https://remotion.dev/) v4.0.461 (React-based programmatic video).

**Render command:**
```bash
cd j-demo
bunx remotion render src/index.ts JDemo out/j-demo.mp4
```

**Source files:**
- `src/JDemo.tsx` — Main composition (all 7 scenes, audio tracks, visual effects)
- `src/index.ts` — Remotion entry point
- `public/` — Audio assets (narration segments + background music)

---

## License

- **Video:** Same license as the Sovereign Shards project
- **Background Music (K22):** Original composition by Reed Richards, used with permission
- **TTS Voice:** Generated via ElevenLabs API (Adam voice)
- **Fonts:** Orbitron (OFL), Inter (OFL) — open-source
