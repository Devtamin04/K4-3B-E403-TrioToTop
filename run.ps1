param (
    [int]$Port = 8000
)

$ErrorActionPreference = "Stop"

Set-Location $PSScriptRoot

if (-not (Test-Path ".env")) {
    if (Test-Path ".env.example") {
        Copy-Item ".env.example" ".env"
        Write-Host "Đã tạo file .env từ .env.example. Vui lòng kiểm tra API key nếu cần." -ForegroundColor Yellow
    } else {
        Write-Error "Không tìm thấy .env hoặc .env.example."
    }
}

# Đọc các biến môi trường từ file .env
Get-Content ".env" | ForEach-Object {
    $line = $_.Trim()
    if ($line -and -not $line.StartsWith("#")) {
        $parts = $line.Split("=", 2)
        if ($parts.Length -eq 2) {
            $name = $parts[0].Trim()
            $value = $parts[1].Trim()
            # Bỏ dấu nháy nếu có
            if (($value.StartsWith('"') -and $value.EndsWith('"')) -or ($value.StartsWith("'") -and $value.EndsWith("'"))) {
                $value = $value.Substring(1, $value.Length - 2)
            }
            [System.Environment]::SetEnvironmentVariable($name, $value, "Process")
        }
    }
}

Write-Host "TeachBack đang chạy ở http://localhost:$Port" -ForegroundColor Green
Write-Host "  provider=$env:LLM_PROVIDER  model=$env:EVALUATOR_MODEL" -ForegroundColor Cyan
Write-Host "  student=$env:STUDENT_BACKEND  prompt=$env:EVALUATOR_PROMPT_VERSION" -ForegroundColor Cyan

uv run uvicorn app.main:app --reload --port $Port
