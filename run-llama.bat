@echo off
setlocal
cd /d "%~dp0"
set "STAMP=%date% %time%"
echo [%STAMP%] Running shard-local llama CLI
"%~dp0model-server\llama.exe" --model "%~dp0models\brain.gguf" --device none --ctx-size 4096 --threads 2 --temp 0.1 --top-p 0.85 --top-k 20 --min-p 0 --chat-template-file "%~dp0prompts\brain-chat-template.jinja" --reasoning-budget 0 --reasoning-format none --simple-io %*
