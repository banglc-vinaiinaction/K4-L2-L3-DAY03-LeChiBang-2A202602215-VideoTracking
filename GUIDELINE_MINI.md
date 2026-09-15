# Mini annotation guideline — Ngày 3 (tracking)

> Điền file này **trong lúc gán nhãn**, không phải sau khi xong. Mỗi lần bạn dừng
> lại nghĩ "cái này tính sao nhỉ?" thì đó là một dòng phải ghi vào đây.
>
> Đây là tài liệu mà người gán nhãn tiếp theo sẽ đọc để làm giống bạn. Nếu hai
> người trong nhóm gán khác nhau, gần như luôn là vì file này chưa nói rõ — chứ
> không phải vì ai kém.

Nhóm / tên: `Lê Chí Bằng — solo`
Clip: `clip_01`, `clip_02`

---

## 1. Phạm vi: gán cái gì, không gán cái gì

Một lớp duy nhất: **`vehicle`** — xe bốn bánh (xe con, van, xe buýt, xe tải).

| Gán | Không gán |
| --- | --- |
| xe con, SUV, taxi, xe bán tải | người đi bộ |
| van, minivan | xe đạp |
| xe buýt, minibus | **xe máy / mô tô** |
| xe tải, xe đầu kéo | xe trong ảnh quảng cáo, trong gương, dưới bóng nước |

Bổ sung của nhóm (nếu có): Không gán các phương tiện 2 bánh (xe máy, xe đạp) kể cả khi đi sát xe bốn bánh; không gán các vật thể tĩnh ven đường như quầy hàng, biển hiệu, bóng đổ của xe.

## 2. Luật ID — phần quan trọng nhất

| Tình huống | Luật của nhóm | Vì sao |
| --- | --- | --- |
| Xe bị che một phần rồi hiện lại | Giữ nguyên ID nếu bị che **dưới 25 frame** (~2 giây @ 12.5 fps) | Xe chỉ tạm thời bị che khuất (occlusion), bản chất danh tính (identity) của xe không đổi |
| Xe bị che lâu hơn ngưỡng trên | Khởi tạo track mới với ID mới | Quá 2 giây không thấy đối tượng, độ tin cậy liên tục bị suy giảm mạnh |
| Xe rời khung hình rồi quay lại | Mặc định: **track mới** | Khi đã ra khỏi khung nhìn camera, track cũ coi như kết thúc hoàn toàn |
| Hai xe cắt nhau / chồng lên nhau | Giữ nguyên ID của từng xe trước, trong và sau khi cắt nhau | Đảm bảo tính nhất quán của ID xuyên suốt hành trình di chuyển |

## 3. Luật bbox

| Tình huống | Luật của nhóm |
| --- | --- |
| Xe bị cắt bởi rìa ảnh | Bbox chạm đúng rìa ảnh, không đoán phần ngoài ảnh |
| Xe bị xe khác che một phần | Bbox ôm phần **nhìn thấy được** (visible area), không vẽ trùm phần bị che |
| Xe vừa xuất hiện, còn rất nhỏ / rất mờ | Bắt đầu track từ frame đầu tiên xác định được là xe bốn bánh (tối thiểu ~15x15 pixel, thấy rõ cấu trúc cabin/thân xe) |
| Xe đang đỗ, không di chuyển | Vẫn gán là `vehicle` và duy trì track suốt thời gian xe nằm trong khung hình |
| Keyframe đặt dày ở đâu | Đặt dày (3–5 frame) tại các đoạn xe tăng/giảm tốc độ, vào cua rẽ hoặc lúc bị che khuất / cắt nhau; đặt thưa (15–25 frame) khi xe chạy thẳng đều |

## 4. Ít nhất ba ca mơ hồ đã gặp thật

Ghi **frame cụ thể** và **ID cụ thể**, không ghi chung chung.

### Ca 1
- Clip / frame / ID: `clip_01 / frame 85–100 / ID 6` (tương ứng Gold track 6)
- Tình huống: Xe xuất hiện từ góc xa phía trên bên phải của khung hình, kích thước rất nhỏ và mờ trong nền đường.
- Quyết định: Bắt đầu vẽ track từ frame 85 khi phát hiện khối chuyển động có đặc trưng nóc và đèn xe bốn bánh.
- Lý do: Đảm bảo phát hiện xe sớm nhất có thể, tránh lỗi bỏ sót (FN), dù ở khoảng cách xa độ tự tin về ranh giới bbox thấp hơn.

### Ca 2
- Clip / frame / ID: `clip_01 / frame 105–130 / ID 4 và ID 5` (tương ứng Gold track 4 và 5)
- Tình huống: Hai xe di chuyển chéo làn nhau, xe ID 4 che khuất một phần thân xe ID 5 ở phía sau.
- Quyết định: Duy trì liên tục ID 4 và ID 5; tại các frame giao cắt, bbox của xe ID 5 thu hẹp lại ôm khít phần thân xe lộ diện, không vẽ đè lên phần thân bị xe ID 4 che khuất.
- Lý do: Tuân thủ quy tắc visible bounding box và tránh hiện tượng ID switch hay gộp track.

### Ca 3
- Clip / frame / ID: `clip_01 / frame 13–15 / ID 1` (Gold track 2) và `frame 44–47 / ID 2` (Gold track 3)
- Tình huống: Xe di chuyển nhanh và thoát dần ra khỏi cạnh dưới / phải của khung hình, chỉ còn một phần mép đuôi/thân xe.
- Quyết định: Kéo bbox chạm sát mép biên ảnh đến frame cuối cùng còn thấy một phần xe, sau đó bấm `Outside` (`O`) ngay tại frame xe hoàn toàn khuất khỏi tầm nhìn.
- Lý do: Tránh lỗi bbox treo (ghost track) sau khi xe đã hoàn toàn rời khỏi vùng nhìn thấy của camera.

## 5. Sửa gì sau khi chấm với gold và sau khi kiểm chéo

Luật nào trong file này hoá ra còn thiếu hoặc còn mơ hồ? Viết lại cho rõ:

- Làm rõ quy chuẩn kích thước tối thiểu khi bắt đầu track xe ở rất xa: chỉ vẽ bbox khi diện tích nhìn thấy >= 20x20 pixel và nhận diện rõ 2/3 cấu trúc xe để tránh lệch frame bắt đầu với teaching reference (giảm FP ở các frame đầu).
- Bổ sung quy tắc bấm `Outside`: ngay khi xe chỉ còn dưới 10% diện tích ở rìa biên ảnh hoặc không còn phân biệt được với lề đường thì kết thúc track ngay, tránh kéo dài thêm 1–3 frame dư thừa.
