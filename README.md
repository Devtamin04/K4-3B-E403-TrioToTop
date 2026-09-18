# TeachBack AI — K4-3B-E403 · TrioToTop

Học viên **dạy lại** một khái niệm cho AI. AI đóng vai học trò: nghe giải thích,
phát hiện chỗ còn thiếu hoặc sai, rồi **hỏi ngược** đúng chỗ đó — không giảng bài,
không đưa đáp án.

> Track D3 — Học bằng cách dạy (phương pháp Feynman).
> 
> 📊 **Slide thuyết trình (CP5):** [`Học bằng cách dạy (TeachBack AI).pdf`](./Học%20bằng%20cách%20dạy%20(TeachBack%20AI).pdf)


## Chạy thử

```bash
cp .env.example .env     # điền OLLAMA_API_KEY
./run.sh                 # mở http://localhost:8000
```

Cấu hình đọc từ `.env`; dự án không tự nạp file này ở chỗ khác nên `run.sh` là
đường chạy chuẩn.

## Kiến trúc

```
Học viên nói
  → Hidden Evaluator   (LLM)            chấm xem hiểu tới đâu, phải trích dẫn lời học viên
  → StateReducer       (thuần Python)   cộng dồn trạng thái, kiểm chứng mọi kết luận
  → PolicyEngine       (thuần Python)   quyết định hỏi gì: PROBE / CLARIFY / CHALLENGE / FINISH / HALT
  → AI Student         (LLM)            diễn đạt câu hỏi cho tự nhiên
  → Học viên
```

Nguyên tắc xuyên suốt: **LLM không được quyết định**. Hai bước ở giữa là Python
thuần và deterministic, nên việc "đã hiểu hay chưa" luôn kiểm chứng được. LLM chỉ
làm hai việc: đọc hiểu lời học viên, và diễn đạt câu hỏi.

## Thư mục

| Đường dẫn | Nội dung |
|---|---|
| `app/teachback/` | Lõi deterministic: models, state, policy, service |
| `app/adapters/` | Evaluator và Student (bản LLM + bản cố định để test) |
| `app/llm/` | Lớp gọi LLM, không phụ thuộc nhà cung cấp |
| `app/api/`, `web/` | REST API và giao diện chat |
| `knowledge/` | 8 chủ đề dạy học (YAML, curate từ transcript khoá) |
| **`eval/`** | **Golden set + kết quả các lượt đo** (chỗ chấm R4) |
| `logs/traces/` | Trace lời gọi AI từng lượt đo |
| `eval_harness/` | Code chạy đo (đọc dữ liệu từ `eval/`) |
| `tests/` | 100 unit + integration test (chạy offline, không gọi LLM) |

## Đo chất lượng

```bash
set -a; source .env; set +a

uv run python -m eval_harness.runner --mode live --target golden      # 32 case, chấm ĐẠT/KHÔNG
uv run python -m eval_harness.runner --mode live --target evaluator   # 12 case regression
uv run python -m eval_harness.runner --mode live --safety-runs 5      # gate an toàn, chạy lặp
uv run python -m eval_harness.runner --mode live --target student     # 17 case AI Student
```

Hai lượt đo: 96.9% và 93.8% (quality bar 80%, đều PASS) — chênh lệch là nhiễu
của LLM, 30/32 case ổn định.
Bảng mọi lượt chạy: [`eval/ket-qua-chay.md`](eval/ket-qua-chay.md) ·
bộ đề: [`eval/golden_set.md`](eval/golden_set.md).

Thiết kế, phần nào thật phần nào còn mock: [`spec.md`](spec.md).

## Thành viên

| Tên | MSSV | Vai trò |
|---|---|---|
| Nguyễn Quang Tuấn | 2A202602470 | Đội trưởng · AI/grounding · frontend |
| Nguyễn Thị Thùy Dương | 2A202602905 | BA · evidence · spec |
| Đoàn Phương Linh | 2A202602382 | Tester · golden set · evaluation |
