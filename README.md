<p align="center">
  <video src="https://github.com/s4ndm4n33-spec/sovereign-shards/raw/main/assets/j-demo.mp4" width="100%" autoplay muted loop playsinline>
    Your browser does not support the video tag. <a href="assets/j-demo.mp4">Watch the demo →</a>
  </video>
</p>

<p align="center">
  <em>80 seconds. Everything J does. No cloud, no API keys, no internet.</em>
</p>

<p align="center">
  <img src="assets/icon.png" alt="Sovereign Shards" width="120" />
</p>

<p align="center">
  <a href="https://github.com/s4ndm4n33-spec/sovereign-shards/actions/workflows/ci.yml"><img src="https://github.com/s4ndm4n33-spec/sovereign-shards/actions/workflows/ci.yml/badge.svg" alt="CI" /></a>
  <img src="https://img.shields.io/badge/phase_1-CLEARED-brightgreen?style=for-the-badge" alt="Phase 1: Cleared" />
  <img src="https://img.shields.io/badge/runs_on-USB_drive-blue?style=for-the-badge" alt="Runs on USB" />
  <img src="https://img.shields.io/badge/cloud-none-critical?style=for-the-badge" alt="No Cloud" />
  <img src="https://img.shields.io/badge/deps-2-yellow?style=for-the-badge" alt="2 Dependencies" />
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-BSL_1.1-purple?style=for-the-badge" alt="BSL 1.1" /></a>
  <img src="https://img.shields.io/badge/tests-212_passing-success?style=for-the-badge" alt="212 Tests" />
  <img src="https://img.shields.io/badge/security-defence_suite-blueviolet?style=for-the-badge" alt="Defence Suite" />
</p>

# Sovereign Shards — J

A fully local AI developer agent that runs from a USB stick.

---

## Repository Layout

This repository is organized around the Sovereign Shards core agent while keeping separate platform projects isolated in `projects/`.

- `app/`, `core/`, `prompts/`, `tools/`, `docs/`, `tests/`, `memory/`: Sovereign Shards core agent and local runtime.
- `projects/cloud/`: J Cloud web landing pages and related deployment assets.
- `projects/github_agent/`: GitHub Models API integration and Actions-based GitHub agent.
- `projects/jgpu/`: JGPU tensor runtime and experiment code.
- `projects/ide/`: VS Code and IDE integration components.
- `projects/architect/`: architecture research scaffolding and planning helpers.
- `projects/fastapi_app/`: FastAPI application demo.
- `projects/integrations/slack/`: Slack app manifest and integration metadata.
- `examples/`: sample apps, demos, and one-off prototypes.
- `scratch/`: temporary files and scratch notes.

---

## What Is J?

J is a **self-contained, autonomous developer agent** — not a chatbot. It decomposes tasks into dependency graphs, calls tools, verifies results, and self-corrects.
