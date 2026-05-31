@REM Copyright (c) 2026 Mike McCollum
@REM
@REM Licensed under the Sovereign Shards License.
@REM See LICENSE.md for details.

@echo off
setlocal
cd /d "%~dp0"

echo ══════════════════════════════════════════
echo   SOVEREIGN SHARD — Booting J
echo ══════════════════════════════════════════

:: Use the shard-local Python, never the host
set "SHARD_PYTHON=%~dp0python\python.exe"

if not exist "%SHARD_PYTHON%" (
    echo [ERROR] Shard Python not found at: %SHARD_PYTHON%
    echo         Expected: python\python.exe relative to shard root
    pause
    exit /b 1
)

echo Python: %SHARD_PYTHON%
echo.

"%SHARD_PYTHON%" "%~dp0run.py" %*

pause
