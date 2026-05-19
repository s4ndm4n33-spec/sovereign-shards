# JGPU — Full Systems Build Plan

Version: 1.0  
Target Environment: J IDE (`https://j-cloud-b5a9dc72.viktor.space`)  
Primary Language: Rust  
Kernel Optimization Layer: Rust SIMD first, optional C++ later  
Target Outcome: Run Ollama inference through a custom virtual tensor runtime.

---

## System Identity

JGPU is:
- A software-defined tensor compute runtime
- A virtual AI accelerator
- A distributed tensor execution engine
- A virtual GPU-like runtime for LLM inference

JGPU is not:
- A gaming GPU
- A Vulkan renderer
- A DirectX implementation
- A graphics emulator

Primary system goals:
- Create tensor execution infrastructure
- Implement asynchronous kernel scheduling
- Manage virtual VRAM
- Support multithreaded execution
- Support distributed tensor execution
- Integrate with llama.cpp
- Run Ollama inference using JGPU backend

Priority order:
1. Correctness
2. Profiling
3. Memory efficiency
4. Scheduler stability
5. Modular architecture

Rule: never optimize before profiling.

---

## Target Architecture

```text
                  ┌────────────────┐
                  │    Ollama      │
                  └──────┬─────────┘
                         │
                  llama.cpp backend
                         │
               ┌─────────▼─────────┐
               │     JGPU Core     │
               │-------------------│
               │ Tensor Runtime    │
               │ Scheduler         │
               │ Virtual VRAM      │
               │ Graph Executor    │
               │ Kernel Engine     │
               └─────────┬─────────┘
                         │
          ┌──────────────┼──────────────┐
          │              │              │
    ┌─────▼────┐   ┌────▼────┐   ┌────▼────┐
    │ CPU Node │   │ GPU Node│   │ Remote  │
    │ AVX2     │   │ CUDA    │   │ Worker  │
    └──────────┘   └─────────┘   └─────────┘
```

---

## Phased Execution Plan

### Phase 0 — Environment Setup
- Install Rust toolchain and verify `rustc` / `cargo`
- Install build and profiling toolchain
- Create workspace and initialize git
- Create Rust workspace members

### Phase 1 — Tensor System
- Implement core tensor type and dtypes
- Add constructors (`zeros`, `ones`, `random`)
- Implement shape transforms (`reshape`, `flatten`, `transpose`)
- Implement row-major indexing with bounds checking
- Validate with unit tests

### Phase 2 — Matrix Multiplication Engine
- Build naive CPU matmul first
- Add Criterion benchmarks before optimization
- Add threaded execution (row parallelism)
- Add SIMD inner-loop optimization
- Validate correctness and performance deltas

### Phase 3 — Execution Runtime
- Define runtime command model
- Build producer-consumer command queue
- Implement executor and dependency tracking
- Add async futures for non-blocking launches
- Validate synchronization and deadlock safety

### Phase 4 — Virtual VRAM
- Build allocator with tensor IDs and refcounts
- Implement HOT/WARM/COLD classes
- Add paging via mmap or file-backed strategy
- Track memory metrics and fragmentation
- Stress test over physical RAM boundaries

### Phase 5 — Computation Graph Engine
- Implement graph nodes with dependencies
- Build topological scheduler
- Add kernel overlap policy
- Add initial fusion passes
- Validate chained graph execution order

### Phase 6 — LLM Operations
- Implement RMSNorm, Softmax, RoPE, Attention, KV cache
- Add FP16 and INT8 quantization paths
- Validate transformer forward passes locally

### Phase 7 — llama.cpp Backend
- Study ggml backend interfaces
- Implement `ggml-jgpu.c/h`
- Map GGML ops to JGPU runtime commands
- Compile and run TinyLlama inference through backend

### Phase 8 — Ollama Integration
- Integrate JGPU backend detection/loading
- Route Ollama inference through JGPU path
- Validate `ollama run tinyllama`

### Phase 9 — Distributed Execution
- Build node runtime with capability reporting
- Implement transport (QUIC or ZeroMQ)
- Implement RPC for execute/transfer/sync/alloc
- Add tensor sharding and remote references
- Validate multi-node inference

### Phase 10 — Performance Engineering
- Optimize memory movement and alignment
- Add blocked/tiled/fused kernels
- Profile with perf + flamegraphs
- Expand benchmark suite for tokens/sec and latency

---

## Engineering Rules

1. Never optimize unprofiled code.
2. Correctness before speed.
3. Every kernel requires unit tests, benchmarks, and profiler trace coverage.
4. Distributed execution begins only after local stability.

---

## Milestones

### First real target
Correct inference, not fast inference. Even 0.5 tokens/sec is initial success.

### 30-day build target
By day 30, deliver:
- Tensor engine
- Threaded matmul
- Scheduler
- Graph execution
- Transformer primitives
- TinyLlama forward pass
