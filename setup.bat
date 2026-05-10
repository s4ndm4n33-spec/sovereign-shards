@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"

echo.
echo  =============================================
echo   SOVEREIGN SHARD — First-Time Setup
echo  =============================================
echo.
echo  This script downloads everything J needs:
echo    1. Embedded Python (portable, no install)
echo    2. llama.cpp server binary (Vulkan build)
echo    3. Qwen2.5-Coder-7B model (split for FAT32)
echo    4. Python dependencies
echo.
echo  Requirements: ~8 GB free space, internet connection
echo  Target: Windows 10/11, FAT32 or NTFS drive
echo.
pause

:: ─── Step 1: Portable Python ───────────────────────────────────────────────
echo.
echo [1/4] Checking Python...
if exist "python\python.exe" (
    echo       Found: python\python.exe — skipping download.
) else (
    echo       Downloading portable Python 3.11.9...
    if not exist "python" mkdir python
    powershell -Command "& {[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri 'https://www.python.org/ftp/python/3.11.9/python-3.11.9-embed-amd64.zip' -OutFile 'python\_tmp_python.zip'}"
    if errorlevel 1 (
        echo [ERROR] Failed to download Python. Check your internet connection.
        pause
        exit /b 1
    )
    powershell -Command "Expand-Archive -Path 'python\_tmp_python.zip' -DestinationPath 'python' -Force"
    del "python\_tmp_python.zip" 2>nul

    :: Enable pip in embedded Python
    echo import site>> "python\python311._pth"

    :: Install pip
    echo       Installing pip...
    powershell -Command "& {[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri 'https://bootstrap.pypa.io/get-pip.py' -OutFile 'python\get-pip.py'}"
    "python\python.exe" "python\get-pip.py" --no-warn-script-location >nul 2>&1
    del "python\get-pip.py" 2>nul
    echo       Done.
)

:: ─── Step 2: llama.cpp server ──────────────────────────────────────────────
echo.
echo [2/4] Checking llama.cpp server...
if exist "model-server\server.exe" (
    echo       Found: model-server\server.exe — skipping download.
) else (
    echo       Downloading llama.cpp b5460 (Vulkan)...
    if not exist "model-server" mkdir model-server
    powershell -Command "& {[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri 'https://github.com/ggml-org/llama.cpp/releases/download/b5460/llama-b5460-bin-win-vulkan-x64.zip' -OutFile 'model-server\_tmp_llama.zip'}"
    if errorlevel 1 (
        echo [ERROR] Failed to download llama.cpp. Check your internet connection.
        echo         You can also download manually from:
        echo         https://github.com/ggml-org/llama.cpp/releases
        pause
        exit /b 1
    )
    powershell -Command "Expand-Archive -Path 'model-server\_tmp_llama.zip' -DestinationPath 'model-server\_tmp' -Force"
    
    :: Move binaries to model-server root
    for /r "model-server\_tmp" %%f in (llama-server.exe) do copy "%%f" "model-server\server.exe" >nul
    for /r "model-server\_tmp" %%f in (llama-cli.exe) do copy "%%f" "model-server\llama.exe" >nul
    for /r "model-server\_tmp" %%f in (*.dll) do copy "%%f" "model-server\" >nul
    
    rd /s /q "model-server\_tmp" 2>nul
    del "model-server\_tmp_llama.zip" 2>nul
    echo       Done.
)

:: ─── Step 3: Model ─────────────────────────────────────────────────────────
echo.
echo [3/4] Checking model...
if exist "models\J-00001-of-00002.gguf" (
    echo       Found: models\J-00001-of-00002.gguf — skipping download.
) else (
    echo       Downloading Qwen2.5-Coder-7B-Instruct Q4_K_M...
    echo       This is ~4.4 GB. Go grab a coffee.
    if not exist "models" mkdir models
    
    echo.
    echo       NOTE: The model is 4.36 GB — too large for FAT32's 4 GB limit.
    echo       If your drive is FAT32, you need to split the model after download.
    echo       This script will attempt to download and split automatically.
    echo.
    
    powershell -Command "& {[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; $ProgressPreference = 'SilentlyContinue'; Invoke-WebRequest -Uri 'https://huggingface.co/Qwen/Qwen2.5-Coder-7B-Instruct-GGUF/resolve/main/qwen2.5-coder-7b-instruct-q4_k_m.gguf' -OutFile 'models\_tmp_model.gguf'}"
    if errorlevel 1 (
        echo [ERROR] Failed to download model. Check your internet connection.
        echo         Manual download:
        echo         https://huggingface.co/Qwen/Qwen2.5-Coder-7B-Instruct-GGUF
        pause
        exit /b 1
    )
    
    :: Check if we need to split (FAT32 = max 4GB per file)
    echo       Splitting model for FAT32 compatibility...
    if exist "model-server\llama.exe" (
        "model-server\llama.exe" --split --split-max-size 3G --input "models\_tmp_model.gguf" --output "models\J" >nul 2>&1
        if exist "models\J-00001-of-00002.gguf" (
            del "models\_tmp_model.gguf" 2>nul
            echo       Split into 2 shards successfully.
        ) else (
            :: Split failed or not supported — try gguf-split
            for /r "model-server" %%f in (llama-gguf-split.exe) do (
                "%%f" --split-max-size 3G "models\_tmp_model.gguf" "models\J" >nul 2>&1
            )
            if exist "models\J-00001-of-00002.gguf" (
                del "models\_tmp_model.gguf" 2>nul
                echo       Split into 2 shards successfully.
            ) else (
                :: Can't split — just rename and hope it's NTFS
                move "models\_tmp_model.gguf" "models\J-00001-of-00001.gguf" >nul
                echo       [WARNING] Could not split model. If on FAT32, split manually.
                echo       See docs/USER_MANUAL.md for instructions.
            )
        )
    ) else (
        move "models\_tmp_model.gguf" "models\J-00001-of-00001.gguf" >nul
        echo       [WARNING] llama.exe not found — could not split model.
    )
    echo       Done.
)

:: ─── Step 4: Python deps ───────────────────────────────────────────────────
echo.
echo [4/4] Installing Python dependencies...
"python\python.exe" -m pip install --no-warn-script-location -r requirements.txt >nul 2>&1
if errorlevel 1 (
    echo       [WARNING] pip install had issues. You may need to run:
    echo       python\python.exe -m pip install -r requirements.txt
) else (
    echo       Done.
)

:: ─── Copy .env ─────────────────────────────────────────────────────────────
echo.
if not exist ".env" (
    echo Creating .env from .env.example...
    copy ".env.example" ".env" >nul
    echo       Done. Edit .env if you need to change settings.
) else (
    echo .env already exists — not overwriting.
)

:: ─── Done ──────────────────────────────────────────────────────────────────
echo.
echo  =============================================
echo   SETUP COMPLETE
echo  =============================================
echo.
echo  To start J:
echo    1. Run start-server.bat  (keep open)
echo    2. Run run-shard.bat     (in another window)
echo.
echo  Or edit .env to customize settings first.
echo  Full docs: docs\USER_MANUAL.md
echo.
pause
