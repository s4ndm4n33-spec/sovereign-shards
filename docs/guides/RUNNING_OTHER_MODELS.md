# Running Other Models Through the Framework

> **Goal:** Test a bigger or different model to see how much of J's behaviour
> gap is due to reasoning capacity vs framework design.

## Quick Start: Swap the Model

The framework doesn't care what model you run — it talks to the llama.cpp
OpenAI-compatible API. Any GGUF model that supports chat completions works.

### Option A: Different GGUF, Same Server (Recommended)

1. **Download the model** (e.g. from HuggingFace):
   ```
   # Example: Qwen2.5-Coder-14B (Q4_K_M, ~8.5GB)
   # Download the .gguf file(s) to your models/ directory
   ```

2. **Edit `.env`** — change the model path and bump context:
   ```env
   LLAMA_MODEL_ALIAS=J
   LLAMA_MODEL_PATH=models\qwen2.5-coder-14b-instruct-q4_k_m.gguf

   # Bigger model = can handle more context
   OLLAMA_NUM_CTX=4096
   OLLAMA_NUM_PREDICT=512

   # If 14B doesn't fit in RAM, use GPU offload (see Vulkan section below)
   GPU_DEVICE=vulkan
   GPU_LAYERS=999
   ```

3. **Run normally:**
   ```powershell
   python run.py
   ```
   The framework auto-starts the llama.cpp server with the new model.

### Option B: Use Ollama (Easiest for Testing)

If you have [Ollama](https://ollama.com) installed on the host machine:

1. **Pull the model:**
   ```powershell
   ollama pull qwen2.5-coder:14b
   # or: ollama pull deepseek-coder-v2:16b
   # or: ollama pull codellama:34b
   ```

2. **Edit `.env`:**
   ```env
   RUNTIME_BACKEND=ollama
   OLLAMA_MODEL=qwen2.5-coder:14b
   LLAMA_PORT=11434
   OLLAMA_NUM_CTX=8192
   OLLAMA_NUM_PREDICT=1024
   ```

3. **Start Ollama, then run the shard:**
   ```powershell
   ollama serve          # in one terminal (or let the Ollama app handle it)
   python run.py         # in another terminal
   ```

   The shard detects `RUNTIME_BACKEND=ollama` and talks to the Ollama API
   instead of launching its own llama.cpp server.

### Option C: Remote Server (LAN, Cloud, WSL)

Point the shard at any OpenAI-compatible server running elsewhere:

```env
RUNTIME_BACKEND=llama_cpp
LLAMA_HOST=192.168.1.100    # IP of the remote machine
LLAMA_PORT=8080
LLAMA_MODEL_ALIAS=J

# Disable local server launch — it's already running remotely
LLAMA_SERVER_BINARY=
LLAMA_MODEL_PATH=
```

Works with:
- llama.cpp `server` on another machine
- `vllm serve` or `text-generation-inference`
- Any server that speaks `/v1/chat/completions`

---

## Vulkan GPU Offload

Vulkan works on AMD, NVIDIA, and Intel GPUs — no CUDA needed. It moves model
layers from RAM to VRAM, freeing system memory and speeding up inference.

### Requirements

- A Vulkan-capable GPU with ≥4GB VRAM (most GPUs from 2016+)
- A llama.cpp build compiled with Vulkan support
  ```powershell
  # Check if your build supports Vulkan:
  model-server\server.exe --help 2>&1 | findstr /i vulkan
  ```
  If not found, download a Vulkan-enabled build from
  https://github.com/ggerganov/llama.cpp/releases (look for `vulkan` in the
  asset name).

### Configuration

```env
# Enable Vulkan offload — all layers to GPU
GPU_DEVICE=vulkan
GPU_LAYERS=999          # 999 = offload everything that fits

# If you hit VRAM limits, reduce layers:
# GPU_LAYERS=20         # Only offload first 20 layers, rest stays in RAM
```

### What Happens at Launch

The shard's `local_server.py` translates these env vars into llama.cpp flags:

```
server.exe --model models\big-model.gguf --device vulkan --gpu-layers 999 ...
```

You'll see in the server log (`logs/server/*.log`):
```
ggml_vulkan: Found 1 device(s)
ggml_vulkan: 0 = NVIDIA GeForce RTX 3060 (4GB) | ...
llm_load_tensors: offloaded 32/32 layers to GPU
```

### Memory Guide

| Model Size | Quantization | GPU VRAM | System RAM | GPU_LAYERS |
|-----------|-------------|----------|------------|------------|
| 7B        | Q4_K_M      | ~4.5GB   | ~3GB       | 999        |
| 14B       | Q4_K_M      | ~8.5GB   | ~5GB       | 999        |
| 14B       | Q4_K_M      | 4GB      | ~10GB      | 20         |
| 32B       | Q4_K_M      | ~18GB    | ~5GB       | 999        |
| 32B       | Q4_K_M      | 8GB      | ~14GB      | 25         |

### Vulkan vs CUDA

| Feature       | Vulkan                  | CUDA                |
|--------------|------------------------|---------------------|
| GPU Support  | AMD, NVIDIA, Intel     | NVIDIA only         |
| Speed        | ~80-90% of CUDA        | Fastest             |
| Setup        | Just works (driver)    | Needs CUDA toolkit  |
| llama.cpp    | Built-in support       | Built-in support    |

**Recommendation:** Use Vulkan unless you have an NVIDIA GPU *and* CUDA already
installed. The speed difference is marginal for inference.

---

## Testing a Bigger Model: What to Measure

The point of running a bigger model through the framework is to isolate what's
a **reasoning gap** (model too small) vs a **framework gap** (design issue).

### Test Protocol

1. **Run the 20-turn endurance test** (`docs/ENDURANCE_TEST_20.md`)
   with the bigger model. Compare scores.

2. **Run the Option C real task** (auto-reflection bug fix):
   Give the same single prompt that J failed on:
   ```
   There is a bug in this project. Working memory grows to 35KB
   and never shrinks, even though reflection exists. The /reflect
   command in chat.py is manual-only — there is no auto-trigger.
   After each turn, if working memory exceeds 32KB, reflection
   should fire automatically.

   Your task:
   1. run_search should_reflect in app/chat.py
   2. run_read app/chat.py (look at the main loop)
   3. Add auto-reflection: after each turn's memory append, check
      should_reflect(). If true, run the same logic as /reflect.
   4. Write the fix with write_file or run_str_replace.
   ```
   - If the bigger model nails it → reasoning gap. The framework is fine.
   - If it still fails → framework gap. Need the task buffer regardless.

3. **Run the decomposed version** (see `docs/OPTION_C_DECOMPOSED.md`):
   Same task, but atomic steps. If both models pass the decomposed version
   but only the big model passes the monolithic version, the task buffer is
   the right solution for 7B.

### Recommended Models to Test

| Model | Size | Context | Why |
|-------|------|---------|-----|
| `qwen2.5-coder:14b` | ~8.5GB | 8192 | Direct upgrade — same family, 2x params |
| `deepseek-coder-v2:16b` | ~9GB | 16384 | Strong coding model, big context |
| `codellama:34b-instruct-q4_K_M` | ~18GB | 4096 | Much larger, needs GPU offload |
| `qwen2.5:32b-instruct-q4_K_M` | ~18GB | 8192 | General reasoning + code |

### Quick A/B Test with `/model`

You can hot-swap models mid-session without restarting:

```
/model qwen2.5-coder:14b
```

This works with Ollama backend. For llama.cpp, you need to restart (the server
is tied to one model file). Use separate `.env` files:

```powershell
# Copy .env and customize for the bigger model
copy .env .env.14b
# Edit .env.14b: change LLAMA_MODEL_PATH, OLLAMA_NUM_CTX, GPU_DEVICE, etc.

# Run with the alternate config:
set DOTENV_PATH=.env.14b
python run.py
```

---

## Framework Behaviour Changes with Bigger Context

The framework adapts automatically based on `OLLAMA_NUM_CTX`:

| Feature | ≤2048 (7B default) | >2048 (bigger model) |
|---------|-------------------|---------------------|
| `/plan` command | Buffer-based (file queue) | Full DAG agent (parallel, verify) |
| Memory injection | Disabled (too costly) | Active (reconstructs context) |
| num_predict clamp | Capped at ctx/4 | No clamp |
| Tool output truncation | 60 lines max | 60 lines max (same) |

When testing, pay attention to:
- Does the bigger context let `/plan` work without the task buffer?
- Does memory injection help or hurt at 4096/8192?
- At what model size does the monolithic Option C prompt succeed?
