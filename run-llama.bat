@echo off
setlocal
cd /d "%~dp0"

set "STAMP=%date% %time%"
echo [%STAMP%] Running shard-local llama CLI

if not exist "%~dp0model-server\llama.exe" (
  echo [ERROR] Missing runtime: "%~dp0model-server\llama.exe"
  set "EXITCODE=1"
  goto :end
)

if not exist "%~dp0models\J.gguf" (
  echo [ERROR] Missing model: "%~dp0models\J.gguf"
  set "EXITCODE=1"
  goto :end
)

"%~dp0model-server\llama.exe" --model "%~dp0models\J.gguf" --device none --ctx-size 4096 --threads 4 --temp 0.1 --top-p 0.85 --top-k 20 --min-p 0 --chat-template-file "%~dp0prompts\J-chat-template.jinja" --reasoning-budget 0 --reasoning-format none --simple-io %*
set "EXITCODE=%ERRORLEVEL%"

if not "%EXITCODE%"=="0" (
  echo [ERROR] llama.exe exited with code %EXITCODE%.
) else (
  echo [OK] llama.exe exited cleanly.
)

:end
if not defined EXITCODE set "EXITCODE=0"
echo.
echo Press any key to close this window...
pause >nul
exit /b %EXITCODE%
