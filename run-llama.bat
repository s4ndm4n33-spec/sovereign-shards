@REM Copyright (c) 2026 Mike McCollum
@REM
@REM Licensed under the Sovereign Shards License.
@REM See LICENSE.md for details.

@echo off
setlocal
cd /d "%~dp0"
set "STAMP=%date% %time%"
echo [%STAMP%] Running shard-local llama CLI
"%~dp0model-server\llama.exe" --model "%~dp0models\J-00001-of-00003.gguf" --device none --ctx-size 2048 --threads 2 --temp 0.1 --top-p 0.85 --top-k 20 --min-p 0 --chat-template-file "%~dp0prompts\J-chat-template.jinja" --simple-io %*
