# Sovereign Shards — Quick Install

## One-Click Setup (Windows)

1. **Download** the latest release `.zip` from [Releases](https://github.com/s4ndm4n33-spec/sovereign-shards/releases)
2. **Extract** to your USB drive or any folder (e.g. `E:\sovereign-shards\`)
3. **Run `setup.bat`** — it downloads everything automatically:
   - Portable Python 3.11 (no system install needed)
   - llama.cpp server (Vulkan build)
   - Qwen2.5-Coder-7B model (~4.4 GB download)
   - Python dependencies
4. **Done.** Follow the on-screen instructions to start J.

## Starting J

Open two terminals in the shard folder:

```
Terminal 1:  start-server.bat     (starts the LLM server)
Terminal 2:  run-shard.bat        (starts the chat interface)
```

## What You Need

| Requirement | Minimum |
|---|---|
| OS | Windows 10/11 (x64) |
| RAM | 16 GB |
| Disk space | ~8 GB free |
| Internet | Only for first-time setup |
| GPU | Optional (Vulkan-capable recommended) |

## Manual Setup (if `setup.bat` doesn't work)

### 1. Python
Download [Python 3.11 embeddable](https://www.python.org/ftp/python/3.11.9/python-3.11.9-embed-amd64.zip) → extract to `python\` folder.

### 2. llama.cpp
Download from [llama.cpp releases](https://github.com/ggml-org/llama.cpp/releases) → place `server.exe` and `llama.exe` in `model-server\`.

### 3. Model
Download [Qwen2.5-Coder-7B-Instruct Q4_K_M](https://huggingface.co/Qwen/Qwen2.5-Coder-7B-Instruct-GGUF) → place in `models\`.

If on FAT32 (4 GB file limit), split with:
```
model-server\llama.exe --split --split-max-size 3G --input model.gguf --output models\J
```

### 4. Dependencies
```
python\python.exe -m pip install -r requirements.txt
```

### 5. Config
```
copy .env.example .env
```

## Troubleshooting

- **"Python not found"** → Run `setup.bat` or place Python in the `python\` subfolder
- **Server won't start** → Check `model-server\server.exe` exists and the model path in `.env` is correct
- **Out of memory** → Set `GPU_DEVICE=none` and `GPU_LAYERS=0` in `.env`, keep `OLLAMA_NUM_CTX=2048`
- **Chinese/Japanese output** → Pull latest code, verify `prompts/J-system.txt` starts with "Always respond in English"
- **FAT32 file too large** → Split the model (see Manual Setup step 3)

## Docs

- [User Manual](docs/USER_MANUAL.md)
- [Roadmap](docs/ROADMAP.md)
- [Migration Log](docs/MIGRATION_LOG.md)
- [The Five Masters](https://five-masters-b9b95dc3.viktor.space)
