@echo off
setlocal
cd /d "%~dp0"

set "STAMP=%date% %time%"
echo [%STAMP%] Initializing J - Five Masters Protocol

:: Execute Server — identity is injected by chat.py via J-system.txt
"%~dp0model-server\server.exe" ^
  --model "%~dp0models\J-00001-of-00003.gguf" ^
  --host 127.0.0.1 --port 8080 ^
  --ctx-size 2048 --threads 2 --temp 0.1 ^
  --alias J --jinja ^
  --chat-template-file "%~dp0prompts\J-chat-template.jinja" ^
  --n-predict 256 --no-warmup --no-webui

echo [%date% %time%] J has entered standby.
pause
