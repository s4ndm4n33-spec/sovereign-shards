```bat
@echo off
setlocal
cd /d "%~dp0"

set "STAMP=%date% %time%"
echo [%STAMP%] Initializing J - Five Masters Protocol

if not exist "%~dp0model-server\server.exe" (
  echo [ERROR] Missing runtime: "%~dp0model-server\server.exe"
  set "EXITCODE=1"
  goto :end
)

if not exist "%~dp0models\J.gguf" (
  echo [ERROR] Missing model: "%~dp0models\J.gguf"
  set "EXITCODE=1"
  goto :end
)

if not exist "%~dp0prompts\J-chat-template.jinja" (
  echo [ERROR] Missing template: "%~dp0prompts\J-chat-template.jinja"
  set "EXITCODE=1"
  goto :end
)

"%~dp0model-server\server.exe" ^
  --model "%~dp0models\J.gguf" ^
  --host 127.0.0.1 ^
  --port 8080 ^
  --ctx-size 2048 ^
  --threads 4 ^
  --temp 0.1 ^
  --top-p 0.85 ^
  --top-k 20 ^
  --min-p 0 ^
  --alias J ^ 
  --no-warmup ^
  --no-webui

set "EXITCODE=%ERRORLEVEL%"

if not "%EXITCODE%"=="0" (
  echo [ERROR] server.exe exited with code %EXITCODE%.
) else (
  echo [OK] J server exited cleanly.
)

:end
if not defined EXITCODE set "EXITCODE=0"

echo [%date% %time%] J has entered standby.
echo.
echo Press any key to close this window...
pause >nul
exit /b %EXITCODE%
```
