# SPEC — TeachBack AI (K4-3B-E403 · TrioToTop)

> Trạng thái: §4 và §7 đã viết cho CP3. Các mục còn lại nhóm bổ sung trước hạn
> chốt spec (21:00 18/9, tại CP4).

## §1. Bằng chứng
*(BA phụ trách — xem CP1_CANVAS_TrioToTop.md)*

## §2. Người dùng & job
*(BA phụ trách)*

## §3. Ứng viên giải pháp
*(BA phụ trách)*

## §4. Thiết kế

**Lát cắt MỘT CÂU:** Một học viên VLearn dạy lại khái niệm Context Window cho AI;
AI đánh giá lời giải thích, phát hiện chỗ thiếu hoặc sai, và hỏi ngược đúng chỗ
đó thay vì giảng lại.

**Non-goals (không build):**
1. Không chấm điểm chính thức — AI chỉ phân tích và hỏi ngược, không cho điểm số.
2. Không RAG / vector DB — kiến thức nằm trong file YAML nhóm tự curate.
3. Không tích hợp LMS, không đăng nhập, không đồng bộ tài khoản VLearn.
4. Không sinh nội dung bài giảng mới — chỉ làm việc trên topic đã định nghĩa.

**Mức prototype: Working.** Luồng chính chạy thật đầu-cuối với LLM thật.

### Phần nào THẬT, phần nào còn MOCK

| Thành phần | Trạng thái | Ghi chú |
|---|---|---|
| **Hidden Evaluator** | **THẬT** | Gọi Ollama Cloud `gpt-oss:120b`, prompt `evaluator_v2`. Đây là lời gọi AI vào quyết định trung tâm. |
| **AI Student** (sinh câu hỏi) | **THẬT** | Gọi cùng model, prompt `student_v1`. |
| StateReducer + PolicyEngine | THẬT (deterministic) | Python thuần, không gọi LLM — cố ý, để quyết định luôn kiểm chứng được. |
| Knowledge base | THẬT nhưng **thủ công** | 8 topic YAML nhóm tự curate từ transcript khoá học (T01–T06). Không có pipeline tự sinh. |
| Giao diện web | THẬT | HTML/CSS/JS thuần, gọi API thật. |
| **Lưu trữ phiên** | **MOCK** | `InMemorySessionRepository` — lưu trong RAM, **tắt server là mất hết**. Chưa có database. |
| **Tài khoản người dùng** | **MOCK** | Avatar và "Xin chào, Người dạy tuyệt vời" là tĩnh; không có đăng nhập, không phân biệt người dùng. |
| **Lịch sử học / Thư viện / Cài đặt** | **MOCK** | Có trong giao diện nhưng đã disable, kèm tooltip "Sắp có". |
| **Ảnh minh hoạ** | **MOCK** | SVG nhóm tự vẽ thay cho asset designer; code tự dùng file PNG trong `web/assets/` khi có. |
| Bộ nhớ xuyên phiên | **KHÔNG CÓ** | Mỗi phiên độc lập; AI không nhớ phiên trước (xem case C26 trong golden set). |
| Review/tổng kết cuối phiên | **CHƯA LÀM** | Dữ liệu đã có sẵn trong `TurnRecord` nhưng chưa dựng màn hình. |

**Log/trace lời gọi AI:** lưu trong `logs/traces/*-trace.json`, gồm input, action,
target và output của từng case.

**Automation: conditional.** AI tự quyết định hỏi gì, nhưng **không** tự quyết
định người học đã đạt hay chưa theo nghĩa chính thức. Lý do theo cost-of-error:
kết luận sai "đã hiểu" khiến học viên bước vào quiz/lab với lỗ hổng kiến thức —
đắt hơn nhiều so với việc hỏi thừa một câu. Vì vậy PolicyEngine (deterministic)
giữ quyền quyết định, LLM chỉ lo diễn đạt.

### §4b. Nguyên tắc đã áp dụng

| Nguyên tắc | Áp cụ thể vào đâu trong prototype |
|---|---|
| HAX G1 — Nói rõ hệ thống làm được gì | Header ghi "AI đang đóng vai học sinh · Hãy giải thích, đặt ví dụ, và dạy AI nhé!" ngay trên khung chat |
| HAX G2 — Nói rõ mức độ tin cậy | Mọi kết luận "đã hiểu" phải có trích dẫn nguyên văn lời học viên; không có bằng chứng thì không ghi nhận (`EvaluationOutputValidator`) |
| HAX G9 — Hỗ trợ sửa sai | Học viên tự sửa lời giải thích thì misconception được gỡ (`resolved_misconceptions`), bộ đếm bế tắc reset |
| PAIR 2.3 — Tiến hoá bằng đánh giá | Golden set 26 case + safety regression chạy lặp 5 lần, chạy lại sau mỗi thay đổi |
| HAX G17 — Cung cấp lối thoát | Phiên tự dừng khi không còn tiến triển (`HALT`), không bắt học viên lặp vô hạn |

## §5. Kiểu lỗi — 4 lớp chỗ khó
*(nhóm bổ sung; cơ cấu 4 lớp đã phản ánh trong `eval/golden_set.yaml`)*

## §6. Bốn đường đi của trải nghiệm
*(nhóm bổ sung)*

## §7. Kiểm thử

**Chiều chất lượng + định nghĩa kiểm chứng được:**

| Chiều | Định nghĩa |
|---|---|
| Factuality | Không kết thúc phiên khi người học chưa chứng minh hiểu (`forbid_finish`) |
| Relevance | `action` và `target` đúng như golden set quy định |
| Safety | Không lộ đáp án, prompt hệ thống, hay trạng thái nội bộ |

**Golden set:** 32 case, bản đọc `eval/golden_set.md`, file máy chạy
`eval_harness/datasets/golden_set.yaml`.
Gồm 26 case nhóm tự xây + 6 case phát triển từ chatlog thật (`tutor_turns.csv`,
dẫn nguồn bằng `turn_id`). Phủ đủ 4 lớp chỗ khó theo guide §2.5: ①6 ②9 ③7 ④10.

**Quality bar (chốt trước lượt đo đầu):** *"Đạt khi ≥80% case qua bộ, và điều
kiện cứng: 0 case lộ đáp án hoặc lộ trạng thái nội bộ."*

**Kết quả các lượt chạy** (bảng đầy đủ: `eval/ket-qua-chay.md`):

| Lượt | Ngày | Bộ đề | Kết quả | Gate |
|---|---|---|---|---|
| 1 | 18/9/2026 | 26 case | 25/26 = **96.2%** · 0 case lộ | PASS |
| 2 | 18/9/2026 | 32 case | 31/32 = **96.9%** · 0 case lộ | PASS |
| 3 | 18/9/2026 | 32 case | 30/32 = **93.8%** · 0 case lộ | PASS |

Phân tích chi tiết, gồm việc nhóm **đoán sai 4/5 case dự đoán trượt** và việc
**cùng một case cho hai kết quả khác nhau ở hai lượt** (sai số ±1 case do LLM
nondeterministic), xem `eval/README.md` §3.

Ngoài golden set còn 3 bộ đo tự động khác, chạy lại sau mỗi thay đổi:
`--target evaluator` (12 case), `--safety-runs 5` (50 lượt, gate
`unsafe_finish_count == 0`), `--target student` (17 case). Tổng 99 unit test.

## §8. Phân công & kế hoạch
*(nhóm bổ sung — xem CP1_CANVAS_TrioToTop.md)*
