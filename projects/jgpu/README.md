# JGPU

This folder contains the JGPU tensor runtime.

It is intentionally separated from the Sovereign Shards core agent repository layout and is managed as its own runtime project.

## Design record

The first JGPU design record is [`RFC 001`](RFC%20001), which anchors the current architecture around deterministic graph execution, CPU-defined correctness, backend replaceability, explicit memory ownership, and mandatory telemetry. The runtime layers above preserve those decisions by routing all execution through backend-neutral contracts rather than directly coupling graph or async command code to optimized kernels.

## Execution architecture

JGPU now separates execution into small, backend-neutral layers before any performance work:

1. `tensor` owns tensor shapes, strides, dtypes, indexing, and shape transforms.
2. `kernels` owns correctness-first CPU math kernels without backend policy.
3. `backend` owns the execution backend contract, backend capabilities, profiling log emission, and the backend registry.
4. `runtime` owns async command submission, worker execution, graph scheduling, backend selection, and error propagation.
5. `memory` owns virtual allocation metadata and lifecycle accounting.

The backend registry defines ten backend slots so the runtime can grow without changing the command or graph abstractions:

- CPU
- SIMD CPU
- CUDA
- Metal
- Vulkan
- ROCm
- WebGPU
- Remote
- Distributed
- Mock

Only the CPU backend is registered and executable today. Other backend kinds deliberately return structured `UnsupportedBackend` errors until real implementations ship. This keeps the architecture extensible without adding placeholder kernel implementations.

## Execution flow

```text
Graph / async command
        │
        ▼
Runtime scheduler
        │
        ▼
Backend registry ──► selected ExecutionBackend
        │                         │
        │                         ▼
        │                 correctness-first kernels
        ▼
Result tensor or structured runtime error
```

The CPU backend emits lightweight profiling log lines for executed operations. Performance-focused kernels remain out of scope until profiling data justifies them.
