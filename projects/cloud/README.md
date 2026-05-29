# Sovereign Shards — Cloud Sites Source Code

Full source for all Viktor Space deployments. Edit here, tell Viktor to pull and redeploy.

## Sites

| Site | Directory | Live URL |
|------|-----------|----------|
| J Cloud | `cloud/j-cloud/` | [j-cloud-b5a9dc72.viktor.space](https://j-cloud-b5a9dc72.viktor.space) |
| Landing Page | `cloud/sovereign-shards-landing/` | [sovereign-shards-landing-65396e18.viktor.space](https://sovereign-shards-landing-65396e18.viktor.space) |

## Architecture

Both sites are **Viktor Spaces** apps — full-stack React + Convex (real-time database) deployments.

```
cloud/{site}/
├── convex/          # Backend — database schema, queries, mutations, actions
│   ├── schema.ts    # Database tables
│   ├── llm.ts       # (j-cloud) LLM engine with multi-provider rotation
│   ├── tools.ts     # (j-cloud) 20 dev tools + tool_forge
│   └── ...
├── src/
│   ├── pages/       # Frontend pages (React + Tailwind)
│   ├── components/  # Shared components + shadcn/ui library
│   ├── index.css    # Global styles (B.L.U.E. J. theme)
│   └── App.tsx      # Router
├── index.html       # Entry point
├── package.json     # Dependencies
└── build.mjs        # Vite build config
```

## Key Files to Edit

### J Cloud (`cloud/j-cloud/`)

| File | What It Controls |
|------|-----------------|
| `convex/llm.ts` | LLM engine — system prompt, Five Masters, provider rotation, tool dispatch |
| `convex/tools.ts` | All 20 development tools + tool_forge |
| `convex/schema.ts` | Database tables (conversations, messages, chainLogs, etc.) |
| `src/pages/ChatPage.tsx` | Chat UI, TTS/STT, file upload |
| `src/pages/EditorPage.tsx` | IDE — syntax highlighting, verify, GitHub file browser |
| `src/pages/AdminPage.tsx` | Admin panel — settings, stats, quick actions |
| `src/pages/LandingPage.tsx` | Public landing/login page |
| `src/index.css` | Full B.L.U.E. J. theme + highlight.js syntax colors |

### Landing Page (`cloud/sovereign-shards-landing/`)

| File | What It Controls |
|------|-----------------|
| `src/pages/LandingPage.tsx` | Hero, features, pricing, CTA |
| `src/index.css` | Styles |
| `convex/preorders.ts` | Pre-order form backend |
| `convex/schema.ts` | Database tables |

## Deployment

These sites deploy through Viktor's pipeline. To update a live site:

1. Edit the source files in this directory
2. Push to `main`
3. Ask Viktor to pull and redeploy: _"Vik, pull cloud/{site} changes and redeploy"_

Or ask Viktor to make changes directly — he has full access.

## Excluded from This Directory

- `node_modules/` — installed at deploy time from `package.json`
- `.convex/` — generated Convex internals
- `dist/` — build output
- `.env.local` — contains deployment-specific secrets (managed by Viktor)
- `convex/_generated/` — auto-generated type definitions
- Lock files — regenerated from `package.json`
