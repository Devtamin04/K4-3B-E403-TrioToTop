# Kịch bản phiên validation — 10 phút/người

In ra hoặc mở trên máy thứ hai. Chữ **in đậm trong ngoặc kép** là đọc gần nguyên văn;
phần còn lại là ghi chú cho người điều phối.

> Luật xuyên suốt: bạn đang **quan sát**, không phải demo. Mỗi lần bạn giải thích giúp
> là một lần mất dữ liệu — vì người dùng thật sẽ không có bạn ngồi cạnh.

---

## Nhịp 1 — Comfort (~1 phút)

> **"Cảm ơn bạn đã dành thời gian. Tụi mình đang đánh giá sản phẩm, không đánh giá bạn —
> không có câu trả lời đúng hay sai. Bạn cứ nói to suy nghĩ của mình ra nhé, kể cả khi
> thấy khó hiểu hay thấy nó dở. Chỗ nào bạn thấy rối thì đó là lỗi của tụi mình, không
> phải của bạn."**

Nếu có ghi màn hình, xin phép ở đây.

---

## Nhịp 2 — Context (~1 phút) · **chưa mở app**

Hỏi chuyện thật trước, để sau còn đối chiếu với hành vi:

> **"Trước khi mở sản phẩm — bạn kể mình nghe lần gần nhất bạn học một khái niệm khó
> trong khoá này đi. Bạn đã làm gì để chắc là mình thật sự hiểu?"**

Nghe và ghi. Nếu họ kể cách họ tự kiểm tra (giảng lại cho bạn bè, viết ra, làm bài tập)
thì ghi lại — sẽ rất đáng giá khi so với lúc họ dùng sản phẩm.

---

## Nhịp 3 — Task (~1 phút)

Mở http://localhost:8000, **đưa chuột cho người thử**, rồi giao task theo *outcome*:

> **"Hãy dùng cái này để dạy lại cho AI một khái niệm mà bạn nghĩ mình đã hiểu.
> Mục tiêu là đến cuối bạn biết được mình hiểu tới đâu."**

Chủ đề có sẵn: Context Window · Cách LLM sinh văn bản · Transformer & Self-Attention ·
Giới hạn của LLM, RAG và Fine-tuning · Kafka Consumer Group · Vòng đời sản phẩm AI ·
Mức tự động hoá · Xác định đúng bài toán.

**Không** nói "bấm nút Bắt đầu", **không** chọn chủ đề giúp, **không** gợi ý nên gõ gì.

---

## Nhịp 4 — Observe (~5 phút) · **IM LẶNG**

Đây là nhịp cho dữ liệu mạnh nhất. Ngồi im, gõ log.

### Cấm

- Thuyết minh màn hình
- Giải thích icon / nút
- Hỏi "bạn có thích không?"
- Trả lời hộ khi AI hỏi ngược

### Kẹt thì chỉ dùng đúng 3 câu này

> **"Cứ nói to suy nghĩ nhé."**
> **"Bạn sẽ làm gì tiếp?"**
> **"Bạn nghĩ nó nên hoạt động thế nào?"**

### Cần bắt được (ghi thẳng vào log)

| Quan sát | Vì sao quan trọng |
|---|---|
| Hành động **đầu tiên** sau khi thấy màn hình | Lộ ngay sản phẩm có tự giải thích được không |
| Chỗ **do dự** > 5 giây | Chỗ đó thiếu chỉ dẫn |
| Chỗ **hiểu sai** | Hiểu sai vai: tưởng AI dạy mình, hay biết mình phải dạy AI? |
| Chỗ phải **gợi ý** | Mỗi lần cứu hộ là một lỗi thiết kế |
| Câu trả lời **cụt dần** | Dấu hiệu bỏ cuộc — hệ thống gọi là `barren_turns` |
| Phản ứng khi **AI hỏi ngược** | Chịu giải thích tiếp, hay khó chịu vì bị vặn? |

### Đọc tín hiệu hành vi (PAIR 5.1) — mỗi hành động có **hai nghĩa**

Ghi cả ngữ cảnh, đừng chỉ ghi hành động:

- **Gõ lại / sửa câu trả lời** → đang đào sâu, hay bực vì AI không hiểu?
- **Hỏi ngược lại AI** → tò mò, hay đang né việc phải giải thích?
- **Trả lời cụt lủn** → đã hết ý, hay chán?
- **Bỏ ngang / đòi dừng** → gần như **luôn tiêu cực**, ghi rõ ngay trước đó màn hình hiện gì

---

## Nhịp 5 — Hỏi sau khi dùng (~2 phút)

Hỏi đủ 4 câu, **log nguyên văn**, không tóm tắt lại bằng lời của bạn:

1. > **"Điều gì khó hiểu hoặc khó chịu nhất?"**
2. > **"Kết quả này bạn có tin không — vì sao?"**
3. > **"Bạn có dùng thật không — vì sao / vì sao chưa?"**
4. > **"Nếu từ mai không được dùng cái này nữa, bạn thấy: rất tiếc / hơi tiếc / không sao?"**

Câu 4 (Disappointment — Sean Ellis) phải đọc đủ cả ba lựa chọn, đừng hỏi trống.

### Nếu còn thời gian, hỏi thêm cho đúng sản phẩm này

> **"Lúc nãy AI hỏi ngược bạn. Câu hỏi đó có trúng chỗ bạn còn mơ hồ không?"**
> **"Sau phiên này bạn có biết rõ hơn mình hiểu tới đâu không?"**

---

## Thang bằng chứng 4 tầng — dùng khi đọc log

```
Mạnh nhất  →  hành vi quan sát được          (họ đã làm gì)
              lời nói trong lúc dùng          (buột miệng)
              giải thích khi được hỏi         (đã kịp hợp lý hoá)
Yếu nhất   →  dự đoán tương lai               ("mình sẽ dùng")
```

**Một hành động thật nặng hơn mười câu nói sẽ-dùng.** Câu "mình sẽ dùng" chỉ coi là gợi ý.

---

## Cảnh báo

> Nếu mọi phản hồi đều là lời khen, **phiên test chưa đạt.**

Người Việt hay ngại chê trực tiếp, nhất là khi biết bạn làm ra nó. Gặp trường hợp này:

- Giao task khó hơn (chủ đề họ chưa chắc: Transformer, Kafka)
- Hỏi lại: **"Nếu phải chọn một chỗ để tụi mình sửa trước, bạn chọn chỗ nào?"**
- Hoặc đổi người thử
