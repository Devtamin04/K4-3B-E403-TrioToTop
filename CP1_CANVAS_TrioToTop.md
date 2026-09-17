# CP1 Canvas — TrioToTop

- **Track/đề:** D3 — Học bằng cách dạy (TeachBack AI).

- **Job executor:** Học viên VLearn vừa học xong một khái niệm AI kỹ thuật và chuẩn bị áp dụng vào quiz/lab/project.

- **Pain:** Học viên thường đánh giá quá cao mức độ hiểu của bản thân sau khi học. Các cách ôn tập hiện tại chủ yếu giúp xem lại kiến thức nhưng chưa chỉ ra phần giải thích còn thiếu hoặc sai, khiến learner chỉ nhận ra knowledge gap khi phải giải thích hoặc áp dụng.

- **Bằng chứng đầu:**

(1) Survey học viên (n=21):
- 13/21 từng gặp knowledge gap sau khi nghĩ rằng đã hiểu.
- 13/21 chỉ nhận ra khi phải giải thích lại cho người khác.
- 14/21 mất >=21 phút để tìm và sửa phần chưa hiểu.

(2) Tutor log:
- 90% interaction là `review_concept`.
- Chỉ 28 lượt sử dụng `ask_probing_question`.
=> Current tutor chủ yếu giải thích lại, chưa tạo cơ chế kiểm tra chiều sâu hiểu biết.

- **Lát cắt:** Một học viên dạy lại Context Window cho AI học trò; AI phát hiện một lỗ hổng quan trọng và hỏi ngược có dẫn nguồn; học viên sửa lời giải thích và trả lời đúng câu vận dụng.

- **Automation + willing users:** AI chỉ phân tích lời giải thích, dẫn nguồn và hỏi ngược; không tự chấm điểm chính thức. Willing users: Trâm Anh, Trọng Đạt, Quang Đạo.

- **Phân công:**
  - Nguyễn Quang Tuấn — 2A202602470 — Đội trưởng; AI/grounding và frontend.
  - Nguyễn Thị Thùy Dương — 2A202602905 — BA; evidence và spec.
  - Đoàn Phương Linh — 2A202602382 — Tester; golden set, evaluation và validation.
