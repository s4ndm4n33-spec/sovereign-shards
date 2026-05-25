# Local CI — mirrors .github/workflows/ci.yml
# Run before every push: powershell -ExecutionPolicy Bypass -File scripts/local-ci.ps1

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

Write-Host "=== Ruff ===" -ForegroundColor Cyan
python -m ruff check . --output-format=github
if ($LASTEXITCODE -ne 0) { Write-Host "FAIL: ruff" -ForegroundColor Red; exit 1 }

Write-Host "=== Pytest ===" -ForegroundColor Cyan
python -m pytest tests/ -v --tb=short
if ($LASTEXITCODE -ne 0) { Write-Host "FAIL: pytest" -ForegroundColor Red; exit 1 }

Write-Host "=== Bandit ===" -ForegroundColor Cyan
python -m bandit -r app/ tools/run/ github_agent/ `
    --severity-level medium `
    --confidence-level medium `
    --skip B310,B602,B603,B607 `
    --format txt
if ($LASTEXITCODE -ne 0) { Write-Host "FAIL: bandit" -ForegroundColor Red; exit 1 }

Write-Host "=== Smoke imports ===" -ForegroundColor Cyan
python -c "from app.router import RouteResult"
python -c "from app.agent.circuit_breaker import CircuitBreaker"
python -c "from app.agent import working_memory"
python -c "from app.agent.planner import build_plan_prompt"
python -c "from app.agent.retriever import Retriever"
python -c "from app.agent.sandbox import validate_before_push"
python -c "import app.agent.task_buffer"
python -c "from app.personality import ready, tool_narrate"
python -c "from app.errors import ShardRuntimeError, TransportError"
if ($LASTEXITCODE -ne 0) { Write-Host "FAIL: smoke imports" -ForegroundColor Red; exit 1 }

Write-Host "=== Registry ===" -ForegroundColor Cyan
python -c "import json,pathlib; reg=json.loads(pathlib.Path('tools/run/registry.json').read_text()); assert len(reg)>0"
if ($LASTEXITCODE -ne 0) { Write-Host "FAIL: registry" -ForegroundColor Red; exit 1 }

Write-Host ""
Write-Host "Local CI passed." -ForegroundColor Green
