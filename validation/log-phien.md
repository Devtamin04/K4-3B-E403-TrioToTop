# Log vòng validation

Điền **ngay sau mỗi phiên**, khi còn nhớ nguyên văn. Mỗi người thử một dòng ở bảng tổng,
kèm một khối chi tiết bên dưới.

Mức nghiêm trọng: **Chặn** (không hoàn thành được task) · **Nặng** (làm được nhưng hiểu
sai / mất lòng tin) · **Nhẹ** (khó chịu, vẫn xong việc).

---

## Bảng tổng

| Người thử (tên/vai — willing user?) | Task | Quan sát | Quote nguyên văn | Mức |
|---|---|---|---|---|
| Nguyễn Huy Cương (học viên K4 — có, khai ở CP1) | Dạy lại một khái niệm đã hiểu | Ngồi ~10s ở màn hình đầu, rê chuột tới nút "Bắt đầu phiên mới" đang mờ, bấm 2 lần không ăn, sau đó mới nhìn sang danh sách chủ đề | *"Ủa nút này bấm không được à? Mình tưởng bấm đây trước."* | Nhẹ |
| Lê Nguyễn Trâm Anh (học viên K4 — có, khai ở CP1) | Dạy lại một khái niệm đã hiểu | Lượt đầu gõ một **câu hỏi** cho AI thay vì giải thích; đọc lại câu AI hỏi ngược rồi mới đổi sang giải thích | *"Mình tưởng nó dạy mình chứ, hoá ra mình phải dạy nó à?"* | Nặng |


---

###  Hỏi sau khi dùng (log nguyên văn)

**1. Khó hiểu / khó chịu nhất?**
> *"Lúc đầu không biết bấm gì. Nút thì thấy đó mà bấm không được, cũng không nói vì sao."*

**2. Có tin kết quả không — vì sao?**
> *"Tin, vì nó hỏi đúng chỗ mình nói lơ mơ. Mình không ngờ nó bắt được."*

**3. Có dùng thật không?**
> *"Chắc có, trước kỳ thi. Nhưng ngồi gõ dài cũng hơi mệt, nói thì nhanh hơn."*

**4. Nếu từ mai không được dùng nữa:** ☐ rất tiếc ☑ **hơi tiếc** ☐ không sao

---

## Phiên 2

**Người thử:** Lê Nguyễn Trâm Anh — học viên K4 — willing user đã khai ở CP1: **có**
**Người điều phối:** Đoàn Phương Linh

### Nhịp 2 — Context (trước khi mở app)

> *"Lần gần nhất học một khái niệm khó, bạn làm gì để chắc là mình hiểu?"*

### Observe

| Mốc | Dự đoán |
|---|---|
| Hành động đầu tiên | Đọc dòng chữ ở khung chat rồi chọn chủ đề luôn *(không vấp H1)* |
| Chỗ hiểu sai | **Hiểu ngược vai (H2)** — lượt đầu gõ câu hỏi thay vì giải thích |
| Số lần phải gợi ý | 1–2 lần |
| Câu trả lời có cụt dần không | Có, rõ hơn phiên 1 nếu chủ đề khó |
| Phiên kết thúc thế nào | **HALT (H4)** nếu bí — chỉ hiện "Đã dừng", không giải thích |

**Diễn biến:**

- Chọn chủ đề nhanh, bấm bắt đầu
- Lượt đầu gõ *"Kafka consumer group là gì?"* → sai vai **(H2)**
- AI vẫn hỏi ngược (không trả lời) → khựng lại, đọc lại màn hình
- Nhận ra phải giải thích, đổi cách gõ
- Tới khái niệm chưa nắm → trả lời "không biết" 2–3 lượt
- `barren_turns` chạm ngưỡng → **HALT**, pill hiện "Đã dừng", **không banner giải thích (H4)**
- Ngồi im, không rõ chuyện gì vừa xảy ra

### Nhịp 5 — Hỏi sau khi dùng (log nguyên văn)
**1. Khó hiểu / khó chịu nhất?**
> *"Đoạn cuối nó tự dừng mà mình không biết vì sao. Mình làm sai gì hay là hết lượt?"*

**2. Có tin kết quả không?**
> *"Có, nó hỏi trúng chỗ mình lơ mơ thật. Nhưng lúc dừng thì hơi hụt."*

**3. Có dùng thật không?**
> *"Nếu ôn thi thì có. Mà nó dừng kiểu đó làm mình tưởng mình dốt quá nên nó bỏ."*

**4. Nếu từ mai không được dùng nữa:** ☐ rất tiếc ☑ **hơi tiếc** ☐ không sao

---

# 4 dòng tổng hợp
**1. Chủ đề lặp nhiều nhất**
> Không biết trạng thái hệ thống: đầu phiên không biết bấm gì **(H1)**, cuối phiên không
> biết vì sao dừng **(H4)**. Cùng một gốc — app không nói cho người dùng biết nó đang ở đâu.

**2. 1–2 thay đổi làm TRƯỚC demo**
> a) Thêm banner khi HALT, giải thích đã dừng và gợi ý quay lại — hiện chỉ có banner mừng
> b) Nút "Bắt đầu phiên mới" khi đang khoá thì hiện tooltip *"Chọn một chủ đề trước"*.

**3. Giữ nguyên, có lý do**
> Thanh tiến trình tính theo lượt, không theo khái niệm **(H5)** — cố ý giấu độ phủ để
> học viên không đọc được đáp án trên UI .
> Chờ ~5s mỗi lượt **(H3)** — là chi phí của 2 lần gọi LLM, không sửa được trước demo.

**4. Đưa vào backlog → slide 6**
> Nhập bằng giọng nói · lưu lịch sử phiên · màn hình tổng kết cuối phiên
>

