@echo off
setlocal enabledelayedexpansion

cd /d "%~dp0"

if not exist .env (
    if exist .env.example (
        copy .env.example .env
        echo Da tao .env tu .env.example.
    )
)

for /f "usebackq tokens=1,* delims==" %%a in (".env") do (
    set "line=%%a"
    if not "!line:~0,1!"=="#" (
        if not "%%b"=="" (
            set "%%a=%%b"
        )
    )
)

echo TeachBack dang chay tai http://localhost:8000
uv run uvicorn app.main:app --reload --port 8000
