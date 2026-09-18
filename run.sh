#!/usr/bin/env bash
# Chạy TeachBack kèm giao diện web.
#   ./run.sh              -> cổng 8000
#   ./run.sh 8080         -> cổng khác
#
# Biến môi trường nạp từ .env. App cố tình không có provider mặc định,
# nên thiếu LLM_PROVIDER là nó dừng ngay thay vì chạy bằng evaluator giả.
set -euo pipefail

cd "$(dirname "$0")"

if [[ ! -f .env ]]; then
  echo "Chưa có .env. Chép .env.example thành .env rồi điền OLLAMA_API_KEY." >&2
  exit 1
fi

set -a
# shellcheck disable=SC1091
source .env
set +a

PORT="${1:-8000}"

echo "TeachBack đang chạy ở http://localhost:${PORT}"
echo "  provider=${LLM_PROVIDER:-<chưa đặt>}  model=${EVALUATOR_MODEL:-<chưa đặt>}"
echo "  student=${STUDENT_BACKEND:-deterministic}  prompt=${EVALUATOR_PROMPT_VERSION:-evaluator_v2}"

exec uv run uvicorn app.main:app --reload --port "${PORT}"
