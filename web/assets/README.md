# Asset cho giao diện TeachBack

Thả file PNG vào thư mục này. Giao diện tự nhận ảnh khi file tồn tại, và tự
dùng lại hình SVG dựng sẵn khi thiếu file — nên không cần đủ bộ mới chạy được.

## Tên file giao diện đang tìm

| Tên file | Dùng ở đâu |
|---|---|
| `logo_robot.png` | logo góc trái + avatar AI trong khung chat |
| `avatar_user.png` | avatar người dạy trong khung chat và ở panel phải |
| `robot_teach.png` | linh vật robot ôm sách ở panel phải |
| `empty_chat.png` | hình minh hoạ khi chưa có cuộc trò chuyện |
| `kafka.png` | icon chủ đề Kafka |
| `database.png` | icon chủ đề SQL / database |
| `docker.png` | icon chủ đề Docker |
| `kubernates.png` | icon chủ đề Kubernetes (giữ nguyên cách viết trong bộ asset) |

Các chủ đề chưa có icon riêng sẽ dùng icon mặc định. Muốn thêm, sửa hàm
`topicIconFile` trong `web/app.js`.

## Ghi chú

- Nền ảnh nên trong suốt để hợp với nền kính mờ của giao diện.
- Avatar hiển thị ở 46×46 px, nên xuất tối thiểu 96×96 để không bị vỡ.
- Linh vật hiển thị rộng khoảng 230 px, nên xuất tối thiểu 460 px.
