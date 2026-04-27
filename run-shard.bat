```bat id="0m72md"
@echo off
setlocal
cd /d "%~dp0"

set "STAMP=%date% %time%"
echo [%STAMP%] Starting Sovereign Shard

if not exist "%~dp0python\python.exe" (
  echo [ERROR] Missing embedded Python runtime: "%~dp0python\python.exe"
  set "EXITCODE=1"
  goto :end
)

if not exist "%~dp0run.py" (
  echo [ERROR] Missing entrypoint: "%~dp0run.py"
  set "EXITCODE=1"
  goto :end
)

"%~dp0python\python.exe" run.py %*
set "EXITCODE=%ERRORLEVEL%"

if not "%EXITCODE%"=="0" (
  echo [ERROR] run.py exited with code %EXITCODE%.
) else (
  echo [OK] Sovereign Shard exited cleanly.
)

:end
if not defined EXITCODE set "EXITCODE=0"

echo.
echo Press any key to close this window...
pause >nul
exit /b %EXITCODE%
```
