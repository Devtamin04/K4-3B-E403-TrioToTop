# Log vòng validation

Điền **ngay sau mỗi phiên**, khi còn nhớ nguyên văn. Mỗi người thử một dòng ở bảng tổng,
kèm một khối chi tiết bên dưới.

Mức nghiêm trọng: **Chặn** (không hoàn thành được task) · **Nặng** (làm được nhưng hiểu
sai / mất lòng tin) · **Nhẹ** (khó chịu, vẫn xong việc).

## Các vấn đề theo dõi

| Mã | Vấn đề |
|---|---|
| H1 | Không rõ phải chọn chủ đề trước khi nút "Bắt đầu phiên mới" được mở khoá |
| H2 | Hiểu ngược vai: tưởng AI sẽ dạy thay vì người học dạy lại cho AI |
| H3 | Thời gian chờ phản hồi khoảng 5 giây mỗi lượt |
| H4 | Phiên chuyển sang `HALT` nhưng giao diện không giải thích lý do hoặc bước tiếp theo |
| H5 | Thanh tiến trình thể hiện số lượt, không thể hiện độ phủ khái niệm |

---

## Bảng tổng

| Người thử (tên/vai — willing user?) | Task | Quan sát | Quote nguyên văn | Mức |
|---|---|---|---|---|
| Nguyễn Huy Cương (học viên K4 — có, khai ở CP1) | Dạy lại một khái niệm đã hiểu | Do dự khoảng 10 giây; bấm nút đang khoá 2 lần rồi mới chuyển sang chọn chủ đề (H1) | *"Ủa nút này bấm không được à? Mình tưởng bấm đây trước."* | Nhẹ |
| Lê Nguyễn Trâm Anh (học viên K4 — có, khai ở CP1) | Dạy lại một khái niệm đã hiểu | Ban đầu hỏi AI thay vì giải thích (H2); cuối phiên không hiểu vì sao hệ thống tự dừng (H4) | *"Đoạn cuối nó tự dừng mà mình không biết vì sao. Mình làm sai gì hay là hết lượt?"* | Nặng |

---

## Phiên 1

**Người thử:** Nguyễn Huy Cương — học viên K4 — willing user đã khai ở CP1: **có**

**Người điều phối:** Đoàn Phương Linh

###  Quan sát thực tế

| Mốc | Quan sát |
|---|---|
| Hành động đầu tiên | Ngồi khoảng 10 giây ở màn hình đầu và rê chuột tới nút "Bắt đầu phiên mới" đang bị khoá |
| Chỗ do dự / hiểu sai | Bấm nút bị khoá 2 lần; tưởng phải bắt đầu phiên trước khi chọn chủ đề (H1) |
| Số lần phải gợi ý | Không ghi lại |
| Phản ứng sau đó | Chuyển sự chú ý sang danh sách chủ đề và tiếp tục task |
| Kết thúc phiên | Không ghi lại trạng thái kết thúc |

**Lời nói trong lúc dùng:**

> *"Ủa nút này bấm không được à? Mình tưởng bấm đây trước."*

### Hỏi sau khi dùng (log nguyên văn)

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

### Quan sát thực tế

| Mốc | Quan sát |
|---|---|
| Hành động đầu tiên | Chọn chủ đề nhanh rồi bấm bắt đầu; không gặp H1 |
| Chỗ do dự / hiểu sai | Lượt đầu gõ một câu hỏi cho AI thay vì giải thích; dừng lại đọc màn hình sau khi AI hỏi ngược (H2) |
| Số lần phải gợi ý | Không ghi lại |
| Câu trả lời có cụt dần không | Có; khi tới phần chưa nắm, trả lời "không biết" trong 2–3 lượt |
| Kết thúc phiên | Hệ thống chuyển sang `HALT`; giao diện chỉ hiện "Đã dừng", không giải thích lý do (H4) |

**Diễn biến:**

- Chọn chủ đề nhanh rồi bấm bắt đầu.
- Lượt đầu gõ *"Kafka consumer group là gì?"* — người thử đang hỏi AI thay vì dạy lại (H2).
- AI hỏi ngược thay vì trả lời; người thử khựng lại và đọc lại màn hình.
- Người thử nhận ra vai trò của mình, chuyển sang giải thích.
- Khi tới khái niệm chưa nắm, người thử trả lời "không biết" trong 2–3 lượt.
- `barren_turns` chạm ngưỡng; hệ thống chuyển sang `HALT`, pill chỉ hiện "Đã dừng"
  và không có banner giải thích (H4).
- Người thử ngồi im, không rõ vì sao phiên vừa kết thúc.

**Lời nói trong lúc dùng:**

> *"Mình tưởng nó dạy mình chứ, hoá ra mình phải dạy nó à?"*

### Hỏi sau khi dùng (log nguyên văn)

**1. Khó hiểu / khó chịu nhất?**

> *"Đoạn cuối nó tự dừng mà mình không biết vì sao. Mình làm sai gì hay là hết lượt?"*

**2. Có tin kết quả không — vì sao?**

> *"Có, nó hỏi trúng chỗ mình lơ mơ thật. Nhưng lúc dừng thì hơi hụt."*

**3. Có dùng thật không?**

> *"Nếu ôn thi thì có. Mà nó dừng kiểu đó làm mình tưởng mình dốt quá nên nó bỏ."*

**4. Nếu từ mai không được dùng nữa:** ☐ rất tiếc ☑ **hơi tiếc** ☐ không sao

---

## 4 dòng tổng hợp

**1. Chủ đề lặp nhiều nhất**

> Thiếu chỉ dẫn về trạng thái và bước tiếp theo xuất hiện ở **2/2 phiên**, dưới hai biểu
> hiện khác nhau: đầu phiên không biết vì sao nút bị khoá (H1), cuối phiên không biết vì
> sao hệ thống dừng (H4). Cùng một gốc vấn đề: giao diện chưa nói rõ hệ thống đang ở trạng
> thái nào và người dùng nên làm gì tiếp theo.

**2. 1–2 thay đổi làm trước demo**

> - Khi `HALT`, hiện banner giải thích phiên đã dừng và gợi ý bước tiếp theo.
> - Khi nút "Bắt đầu phiên mới" đang khoá, hiện chỉ dẫn *"Chọn một chủ đề trước"*.

**3. Giữ nguyên, có lý do**

> Giữ thanh tiến trình theo số lượt thay vì độ phủ khái niệm (H5), để không vô tình gợi
> ý nội dung cần trả lời. Tạm chấp nhận thời gian chờ khoảng 5 giây (H3), vì mỗi lượt cần
> hai lần gọi LLM. Đây là các quyết định sản phẩm đã biết, không phải kết luận trực tiếp
> từ hai phiên validation trên.

**4. Đưa vào backlog**

> Ưu tiên nhập bằng giọng nói, dựa trên phản hồi của người thử phiên 1 rằng gõ dài gây
> mệt. Lưu lịch sử phiên và màn hình tổng kết cuối phiên tiếp tục nằm trong backlog sản
> phẩm, nhưng chưa có đủ bằng chứng trực tiếp từ hai phiên này để xếp mức ưu tiên.
