# AGENTS.md

## Repository Working Contract

This repository currently hosts **Sovereign Shards (J)**. A new initiative, **JGPU** (Distributed Virtual Tensor GPU Runtime for Ollama), is now tracked inside this repo as a structured systems program.

### Mission framing for JGPU
- JGPU is a software-defined tensor compute runtime.
- JGPU is not a graphics renderer or gaming GPU emulator.
- Priorities, in order: correctness, profiling, memory efficiency, scheduler stability, modular architecture.
- Never optimize before profiling.

### Delivery requirements for JGPU subsystems
Every subsystem must ship with:
- Unit tests
- Benchmarks
- Profiling hooks
- Logging

No placeholder or stub implementations are allowed in JGPU deliverables.

### Documentation update rule
Any architecture-impacting JGPU change must also update:
- `README.md`
- `PLANS.md`
- `AGENTS.md`

### Current execution scope
The authoritative execution roadmap is documented in `PLANS.md` (Phase 0 through Phase 10), including:
- Tensor runtime foundations
- Kernel scheduling and async execution
- Virtual VRAM and paging
- Graph execution
- llama.cpp backend integration
- Ollama integration
- Distributed tensor execution
- Performance engineering and profiling discipline

### Engineering style
- Prefer small, composable modules with explicit boundaries.
- Keep interfaces stable and test-first for critical math and scheduling components.
- Enforce reproducible benchmarks and profiler traces for kernel work.


### Current implementation note
- A functional Rust workspace now exists at `jgpu/` as the active execution surface for Phases 0-6 foundations, including a dependency-aware graph executor and baseline LLM primitives (`rmsnorm`, `softmax`, `RoPE`, `attention`, `KV cache`).
