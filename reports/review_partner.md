# Peer review — Day 3

Chép file này thành `reports/review_partner.md`. Reviewer chỉ ghi finding; tác giả
tự sửa bài của mình và điền closure.

| Trường | Giá trị |
| --- | --- |
| Author | `Lê Chí Bằng` |
| Reviewer | `Lê Chí Bằng (Self-QC / Solo mode)` |
| Pair ID | `SOLO-01` |
| CVAT version | `CVAT Server 2.15.0 (app.cvat.ai)` |
| Thời điểm review | `2026-09-15T17:20:00+07:00` |

## Danh sách finding

Mỗi finding bắt buộc có `frame + ID + lỗi + sửa thế nào`. Nếu chưa thống nhất,
dùng `needs-review`; không ép tác giả sửa theo cảm tính.

| # | CVAT frame | MOT frame | ID | Loại lỗi | Quan sát + rule áp dụng | Cách sửa đề xuất | Closure: fixed / not-a-defect / needs-review |
| ---: | ---: | ---: | ---: | ---: | --- | --- | --- |
| 1 | 84–99 | 85–100 | 6 | Bbox sớm (xa) | Xe ở frame 85–100 rất nhỏ ở góc xa, gán sớm khi xe chưa rõ nét so với nền | Bắt đầu keyframe từ khi xe nhìn rõ cabin để đồng bộ | fixed |
| 2 | 104–129 | 105–130 | 5 | Occlusion bbox | Xe ID 5 bị ID 4 che khuất một phần, bbox vẽ hơi rộng ở frame 106–126 | Tinh chỉnh lại bbox ôm sát phần nhìn thấy (visible part) | fixed |
| 3 | 12–14 | 13–15 | 1 | Exit frame | Xe ID 1 rời khung hình ở góc dưới nhưng còn 1-2 frame bbox chạm mép ngoài | Bấm `Outside` ngay khi xe khuất khỏi khung hình | fixed |

## Reviewer checklist

| Hạng mục | PASS / FINDING / N/A | Frame–ID–evidence |
| --- | --- | --- |
| Có tối thiểu 6 track hợp lệ; chỉ gồm xe bốn bánh | PASS | Đủ 8 track xe 4 bánh, không gán xe máy hay người đi bộ |
| Một xe giữ một ID; không reuse ID cho xe khác | PASS | IDSW = 0, toàn bộ 8 track giữ ID duy nhất |
| Occlusion ngắn giữ ID; crossing không đổi ID | PASS | Frame 105–130 các xe cắt nhau giữ nguyên ID |
| Entry/exit đúng; không box treo sau khi xe rời khung | PASS | Đã rà soát và bấm Outside cho tất cả các xe rời khung |
| Bbox ôm phần nhìn thấy, không đoán phần bị che/ngoài khung | PASS | Bbox ôm sát phần xe lộ diện, chạm mép ảnh không lấn ra ngoài |
| Frame giữa hai keyframe không bị interpolation drift | PASS | Đã thêm keyframe ở giữa các đoạn xe rẽ/thay đổi tốc độ |
| Export đúng MOT 1.1; frame bắt đầu từ 1; cột 2 là track ID | PASS | 610 dòng, frame từ 1 đến 190, 8 track ID hợp lệ |
| Mọi finding có cách sửa và closure do tác giả điền | PASS | Cả 3 finding đều có giải pháp và trạng thái fixed |

## Self-QC attestation của reviewer

| Lượt | PASS / ĐÃ SỬA / NEEDS-REVIEW | Frame–ID–evidence |
| --- | --- | --- |
| 1 — identity/timeline | PASS | Toàn bộ 8 ID không bị đổi số, timeline liên tục, IDSW = 0 |
| 2 — endpoint/scope | PASS | Rà soát frame đầu/cuối của cả 8 track; kiểm tra lệnh Outside |
| 3 — geometry/interpolation | PASS | Đã tua kiểm tra frame giữa hai keyframe xa nhất, bbox khít xe |

## Exit ticket

1. Finding quan trọng nhất và rule dùng để kết luận: `Quy tắc giữ nguyên ID khi bị che khuất tạm thời (< 25 frame) và chỉ vẽ bbox ôm phần nhìn thấy được (visible bounding box).`
2. Một finding tác giả đóng là `not-a-defect`, kèm lý do (nếu có): `Việc track ID 6 bắt đầu từ frame 85 ở khoảng cách xa: tác giả chủ động vẽ sớm để tránh FN ngay khi nhận diện được chuyển động của xe bốn bánh.`
3. Một rule cần Lab Coach làm rõ (nếu có): `Ngưỡng kích thước pixel tối thiểu quy chuẩn cho xe ở rất xa để tránh tranh chấp giữa FP và FN ở các frame đầu.`
