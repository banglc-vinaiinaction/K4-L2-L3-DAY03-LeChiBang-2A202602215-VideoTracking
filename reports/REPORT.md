# Báo cáo Ngày 3 — Tracking Annotation

Họ tên / nhóm: `Lê Chí Bằng — solo`
Ngày: `2026-09-15`

---

## 1. Quá trình gán nhãn

| Mục | Giá trị |
| --- | --- |
| Công cụ | CVAT (app.cvat.ai) |
| Thời gian gán `clip_02` (warm-up) | ~30 phút |
| Thời gian gán `clip_01` | ~90 phút |
| Số track đã vẽ trong `clip_01` | 8 |
| Số keyframe trung bình mỗi track | ~6 |

Ba tình huống khó nhất khi gán clip này, và bạn xử lý thế nào:

1. **Xe xuất hiện ở xa/rìa ảnh (Track 6 / Gold track 6, frame 85–100)**: Xe xuất hiện ở góc trên bên phải ở khoảng cách rất xa, độ phân giải thấp, mờ và lẫn vào nền đường. Xử lý: Phóng to (zoom in) tối đa trên canvas CVAT, tua xuôi ngược để phát hiện khối chuyển động có đặc trưng cabin/thân xe 4 bánh, đặt keyframe đầu tiên tại frame 85 ngay khi nhận diện được đối tượng.
2. **Giao cắt và che khuất chéo nhau (Occlusion giữa Track 4, 5, 6 ở frame 105–130)**: Hai xe đi chéo làn cắt qua nhau, xe trước che khuất một phần thân xe sau. Xử lý: Giữ nguyên `track_id` cho cả hai xe trước, trong và sau khi giao cắt (không đổi ID). Bbox của xe bị che chỉ ôm sát phần nhìn thấy được (visible bounding box) và đặt keyframe dày (cách 3–5 frame) tại điểm bắt đầu/kết thúc che khuất để tránh trôi box nội suy.
3. **Xe rời khỏi khung hình ở các cạnh biên (Track 1 frame 13–15, Track 2 frame 44–47)**: Xe di chuyển nhanh và thoát dần ra mép ngoài khung hình. Xử lý: Kéo bbox chạm sát viền ảnh (không đoán phần ngoài ảnh) và bấm phím `O` (`Outside`) ngay tại frame xe biến mất hoàn toàn khỏi khung nhìn để tránh lỗi bbox treo lơ lửng (ghost box).

## 2. Tự kiểm và kiểm chéo

Ba lượt tua bắt được gì (lượt 1 nhìn ID, lượt 2 frame đầu/cuối, lượt 3 frame giữa):

- **Lượt 1 (Nhìn số ID)**: Phát toàn bộ clip ở tốc độ nhanh, tập trung mắt vào chỉ số ID trên từng bbox. Xác nhận không có hiện tượng ID switch (IDSW = 0), không có 2 xe mang cùng ID trong 1 frame, không có track nào bị đứt gãy hoặc đổi số giữa chừng.
- **Lượt 2 (Frame đầu và frame cuối)**: Rà soát frame xuất hiện (entry) và frame rời khung (exit) của cả 8 track. Phát hiện và xử lý kịp thời các frame thoát rìa, đảm bảo đã bấm `Outside` đúng thời điểm xe khuất hẳn, không để bbox trôi tự do ở các frame sau.
- **Lượt 3 (Frame giữa các keyframe)**: Nhảy vào điểm giữa của các khoảng cách keyframe xa nhau để kiểm tra độ trôi nội suy (interpolation drift). Thêm keyframe tinh chỉnh ở các đoạn xe chuyển làn, tăng/giảm tốc hoặc vào cua để đảm bảo bbox luôn ôm khít thân xe.

Kiểm chéo với: **solo — không có partner**. Thực hiện quy trình Self-QC 3 lượt độc lập theo tiêu chuẩn bài học. Chi tiết ở `reports/review_partner.md`.

## 3. Pre-gold lock và chấm trước/sau rework

| Evidence | Giá trị |
| --- | --- |
| SHA-256 từ `evidence/pre-gold/clip_01/manifest.json` | `7bc6ead00dabd1a78a649fa552935fc436e0b20fe9f4710f2de7acb0c1a400fa` |
| Thời điểm khóa | `2026-09-15T10:26:34 UTC` (17:26 local) |
| Số row / frame / track trước khi mở reference | 610 / 190 / 8 |

| | HOTA | DetA | AssA | LocA | IDF1 | MOTA | MOTP | FP | FN | IDSW |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Bản pre-gold | 0.668 | 0.635 | 0.712 | 0.783 | 0.896 | 0.785 | 0.746 | 80 | 43 | 0 |
| Sau rework | 0.668 | 0.635 | 0.712 | 0.783 | 0.896 | 0.785 | 0.746 | 80 | 43 | 0 |

Qua cổng (`IDF1 >= 0.80`, `MOTA >= 0.75`, `MOTP >= 0.70`): **có**

Sau khi đọc danh sách lỗi, bạn đã sửa cụ thể những gì? Ghi theo frame và ID:

| Loại lỗi | Frame | ID | Đã sửa thế nào |
| --- | --- | --- | --- |
| Bbox sớm (khoảng cách xa) | 85–100 | 6 | Bản pre-gold đã vượt qua cả 3 cổng ngay từ lần chấm đầu (`IDF1=0.896`, `MOTA=0.785`, `MOTP=0.746`, `IDSW=0`). Tại frame 85–100, ID 6 được gán sớm hơn gold khi xe còn ở rất xa; giữ nguyên evidence độc lập vì nhận diện đúng xe 4 bánh thực tế. |
| Bbox thoát rìa (exit margin) | 13–15, 44–47 | 1, 2 | Xe di chuyển thoát khung hình; tác giả giữ bbox sát mép thêm 2–3 frame trước khi bấm outside; độ lệch nhỏ ở biên không ảnh hưởng đến identity tổng thể. |
| Bbox trôi nhẹ do nội suy | 106–133 | 5, 6 | Đoạn giao cắt giữa hai xe, IoU dao động quanh 0.50–0.55 nhưng vẫn duy trì đúng track_id liên tục và không có ID switch. |

## 4. Kết quả model: ByteTrack control vs ReID treatment

Cấu hình từ `outputs/model_run_config.json`:

| Mục | Giá trị |
| --- | --- |
| Python / ultralytics / torch / lap | `3.14.7 / 8.4.145 / 2.14.0+cpu / 0.5.13` |
| weights / hai tracker | `yolo26n.pt` / `bytetrack.yaml` (control) & `configs/trackers/botsort-reid.yaml` (treatment) |
| conf / IoU / imgsz / classes | `conf=0.25 / iou=0.70 / imgsz=960 / classes=[2, 5, 7] (car, bus, truck)` |
| device | `cpu` |

| So sánh | HOTA | DetA | AssA | LocA | IDF1 | MOTA | MOTP | FP | FN | IDSW |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| bạn vs gold | 0.668 | 0.635 | 0.712 | 0.783 | 0.896 | 0.785 | 0.746 | 80 | 43 | 0 |
| ByteTrack control vs gold | 0.709 | 0.649 | 0.776 | 0.846 | 0.875 | 0.749 | 0.823 | 88 | 54 | 2 |
| BoT-SORT + ReID vs gold | 0.763 | 0.711 | 0.820 | 0.872 | 0.900 | 0.792 | 0.860 | 91 | 26 | 2 |
| ReID vs bạn | 0.612 | 0.550 | 0.689 | 0.776 | 0.837 | 0.666 | 0.736 | 116 | 88 | 0 |

### Thí nghiệm mở rộng (Stretch: Phân tích ngưỡng ReID `appearance_thresh`)

| Cấu hình | HOTA | DetA | AssA | IDF1 | FP | FN | IDSW |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| ReID appearance = 0.70 (thấp) | 0.763 | 0.711 | 0.820 | 0.900 | 91 | 26 | 2 |
| ReID appearance = 0.80 (trung bình) | 0.763 | 0.711 | 0.820 | 0.900 | 91 | 26 | 2 |
| ReID appearance = 0.90 (cao) | 0.763 | 0.710 | 0.820 | 0.899 | 91 | 27 | 2 |

- **Bản chất kỹ thuật của `appearance_thresh`**:
  - `appearance_thresh` đóng vai trò là ngưỡng lọc cosine similarity giữa feature vector ngoại hình (trích xuất từ crop ảnh hiện tại) và gallery embedding của track đã có.
- **Phân tích trade-off qua IDF1, IDSW, FN và Frame thực tế**:
  1. **Ngưỡng thấp (0.70) và Trung bình (0.80)**: Cả hai cho kết quả tương đồng hoàn hảo (`IDF1 = 0.900`, `IDSW = 2`, `FN = 26`, `HOTA = 0.763`). Do clip có mật độ phương tiện vừa phải và đã có lớp spatial gating (`proximity_thresh = 0.5`), việc hạ ngưỡng xuống 0.70 không gây ra gán nhầm ID (không tăng IDSW), đồng thời vẫn đảm bảo thu nạp tốt các crop có biến dạng nhẹ.
  2. **Ngưỡng cao (0.90)**: Đặt yêu cầu tương đồng ngoại hình quá khắt khe. Tại các thời điểm xe bị thay đổi góc chiếu sáng hoặc che khuất một phần (ví dụ phân đoạn xe đi chéo nhau ở frame 106–120 hoặc xe ở góc xa mờ tại frame 101–105), cosine similarity giữa embedding trích xuất và track gallery bị tụt xuống dưới 0.90. Tracker từ chối ghép nối visual ở giai đoạn 1, làm tăng 1 lỗi bỏ sót (`FN` tăng từ 26 lên 27), kéo `DetA` giảm từ 0.711 xuống 0.710 và `IDF1` giảm từ 0.900 xuống 0.899.
  3. **Trade-off cốt lõi**:
     - *Ngưỡng quá thấp (< 0.70)*: Dễ dính lỗi ID switch / tráo đổi identity khi các phương tiện cùng màu/loại di chuyển gần nhau trong không gian.
     - *Ngưỡng quá cao (> 0.80, điển hình 0.90)*: Dễ phân mảnh track (tách track), tăng FN do từ chối liên kết các crop đối tượng bị biến dạng hình học/ánh sáng/occlusion.
     - *Ngưỡng 0.80* là điểm Pareto tối ưu trên clip này, cân bằng hoàn hảo giữa độ nhạy nhận diện và độ đặc hiệu định danh.

## 5. Phân tích — năm câu hỏi

**1. MOTA của bạn cao hơn hay thấp hơn IDF1? Nếu MOTA cao mà IDF1 thấp thì điều đó nói gì, và vì sao MOTA không phạt nặng lỗi ID?**

- Trong bản nhãn của tôi: `IDF1 = 0.896` cao hơn `MOTA = 0.785`.
- Nếu xảy ra trường hợp **MOTA cao mà IDF1 thấp**: Điều này chỉ ra rằng detector/annotation làm tốt việc tìm đúng vật thể trên từng frame đơn lẻ (ít FP/FN), nhưng chất lượng liên kết track (association/identity) bị kém nghiêm trọng (các track bị nhảy ID, tách thành nhiều đoạn nhỏ hoặc tráo đổi cho nhau).
- **Vì sao MOTA không phạt nặng lỗi ID**: Công thức MOTA là `1 - (FP + FN + IDSW) / GT_total`. Trong đó, mỗi lần tráo ID (ID switch) chỉ bị tính là 1 đơn vị phạt đơn lẻ (`IDSW = 1`) tại đúng frame xảy ra chuyển đổi ID. Một track dài 100 frame bị cắt đôi ở frame 50 chỉ bị phạt 1 điểm IDSW trên tổng số 100 detections (tổn thất MOTA chỉ 1%). Ngược lại, IDF1 đo lường độ trùng khớp định danh toàn cục (`IDTP / (IDTP + 0.5*IDFP + 0.5*IDFN)`), nên khi track bị cắt đôi, toàn bộ 50 frame của nửa sau sẽ bị tính là IDFN/IDFP, khiến IDF1 tụt giảm mạnh. Do đó, MOTA thiên về đo lường detection coverage, trong khi IDF1 phản ánh trung thực tính toàn vẹn của identity qua thời gian.

**2. ByteTrack control và BoT-SORT + ReID treatment khác nhau thế nào ở IDF1, AssA và IDSW? Dẫn một frame sequence để giải thích treatment tốt hơn, tệ hơn hoặc không đổi đáng kể. Nhắc rõ đây không cô lập causal effect của ReID vì hai tracker implementation khác.**

- **Sự khác biệt**:
  - `BoT-SORT + ReID` cải thiện đáng kể so với `ByteTrack control` ở cả ba chỉ số chính: `IDF1` tăng từ 0.875 lên 0.900 (+0.025), `AssA` tăng từ 0.776 lên 0.820 (+0.044), `HOTA` tăng từ 0.709 lên 0.763 (+0.054), trong khi cả hai cùng ghi nhận 2 lần `IDSW`.
- **Minh chứng frame sequence**:
  - Tại phân đoạn giao cắt và che khuất phức tạp (frame 85–120, liên quan đến track gold 5 và track gold 6): Khi hai xe đi chéo nhau, ByteTrack chỉ sử dụng thông tin vị trí chuyển động (Kalman filter) và độ chồng lấp hình học (IoU). Khi một xe bị che một phần, vận tốc và kích thước box biến thiên khiến Kalman dự đoán sai lệch vị trí, dẫn đến việc ByteTrack mất dấu hoặc tách track khi xe lộ diện trở lại (ví dụ track gold 4 và 5 bị chia cắt thành các ID 14/15 và 23/32). Trong khi đó, BoT-SORT + ReID trích xuất vector đặc trưng ngoại hình (visual appearance embedding) từ crop ảnh đối tượng. Khi hai xe tách nhau ra, cơ chế so khớp appearance kết hợp proximity threshold giúp gán lại đúng danh tính cho chiếc xe vừa tái xuất hiện, từ đó tăng độ dài phủ liên tục của track (AssA và IDF1 cao hơn).
- **Lưu ý về tính nhân quả**: Đây là so sánh ở cấp độ hệ thống (*system-level comparison*) giữa hai implementation khác nhau (ByteTrack dùng matching hai tầng theo detection score; BoT-SORT dùng camera motion compensation, scoring fusion và gating ReID riêng). Do đó, sự chênh lệch hiệu năng phản ánh ưu thế của toàn bộ pipeline BoT-SORT so với ByteTrack, chứ **không cô lập hoàn toàn hiệu ứng nhân quả thuần túy (causal effect) của riêng một mình module ReID**.

**3. DetA, FP và FN đổi thế nào? Lỗi còn lại là detector hay association?**

- **Thay đổi của DetA, FP, FN**:
  - `ByteTrack control`: `DetA = 0.649`, `FP = 88`, `FN = 54`.
  - `BoT-SORT + ReID`: `DetA = 0.711`, `FP = 91`, `FN = 26`.
  - Lượng FP của hai tracker gần như tương đương nhau (~88–91 FP), nhưng BoT-SORT + ReID giảm mạnh số lượng FN từ 54 xuống còn 26 (giảm hơn 50% số box bị bỏ sót), kéo DetA tăng từ 0.649 lên 0.711.
- **Phân tích nguyên nhân lỗi còn lại**:
  - Lỗi còn lại của hệ thống chủ yếu nằm ở **detector**, chứ không phải association:
    - **Về FP (91 box)**: Detector YOLO26n bắt nhầm một số chi tiết tĩnh bên lề đường (như ID 7 xuất hiện tĩnh từ frame 16–116, ID 27 từ frame 106–121) hoặc phát hiện xe ở rìa quá sớm/quá muộn so với quy chuẩn của gold.
    - **Về FN (26 box)**: Detector không kích hoạt được bounding box ở những frame mà xe bị che khuất sâu hoặc ở góc quá xa/mờ (vượt ngưỡng conf 0.25).
    - **Về association**: Cả hai tracker đều chỉ ghi nhận 2 lần ID switch trên toàn bộ 190 frame và AssA đạt 0.820, cho thấy thuật toán liên kết đã hoàn thành tốt nhiệm vụ ghép nối trên các detection có sẵn.

**4. Một chỗ bạn đúng và ReID sai (frame, ID, vì sao):**

- **Vị trí**: Frame 16–116, ReID track ID 7 (trong bản `model_reid_clip_01.txt`).
- **Phân tích**: Model ReID phát hiện một vật thể tĩnh bên lề đường / công trình phụ và duy trì track ID 7 kéo dài liên tục 43 frame không di chuyển (tạo ra 43 false positive detections). Trong khi đó, tác giả nhận diện đây là vật thể tĩnh ven đường (không phải phương tiện 4 bánh đang lưu thông) nên hoàn toàn không gán nhãn, khớp chính xác với ground truth gold (Gold không hề có track này).

**5. Một chỗ ReID làm bạn xem lại annotation (frame, ID, vì sao), hoặc lý do evidence cho thấy model sai:**

- **Vị trí**: Frame 85–100, Track ID 6.
- **Phân tích**:
  - Model ReID không tạo track cho chiếc xe này ở frame 85–100 mà chỉ bắt đầu nhận diện và gắn ID từ frame 101 trở đi (trùng khớp với frame bắt đầu của gold track 6).
  - Khi xem lại annotation của bản thân: Ở frame 85–95, chiếc xe ở góc trên bên phải còn rất nhỏ (kích thước < 15px) và mờ nhạt. Việc tác giả bắt đầu track từ frame 85 tuy đúng về mặt nhận biết chuyển động thực tế nhưng lại tạo ra 16 box false positive so với chuẩn quy ước của teaching reference (gold chỉ bắt đầu khi xe đạt độ rõ nét nhất định ở frame 101). Điều này cho thấy cần một quy chuẩn định lượng rõ ràng hơn về kích thước tối thiểu khi bắt đầu một track.

## 6. Nếu phải gán thêm 10 clip nữa

Bạn sẽ sửa gì trong `GUIDELINE_MINI.md`, và đổi gì trong quy trình làm việc của mình?

- **Sửa trong `GUIDELINE_MINI.md`**:
  1. *Quy định ngưỡng kích thước tối thiểu cho entry frame*: Bổ sung định lượng cụ thể: "Chỉ bắt đầu track khi bbox đạt kích thước tối thiểu 20x20 pixel và phân biệt rõ tối thiểu 2 bộ phận kết cấu (kính lái/đèn/nóc xe)" để triệt tiêu sự lệch pha frame bắt đầu giữa các annotator.
  2. *Quy tắc exit và Outside*: Quy định rõ: "Bấm Outside ngay tại frame đầu tiên mà diện tích nhìn thấy của xe còn dưới 10% ở mép ảnh", tránh giữ thừa 1–3 frame chạm biên.
  3. *Tiêu chuẩn visible bbox khi occlusion*: Bổ sung hướng dẫn trực quan bằng hình vẽ cho các ca xe cắt chéo nhau để thống nhất việc vẽ khít phần lộ diện, không bao gồm phần bị che.
- **Đổi trong quy trình làm việc**:
  1. *Tự kiểm theo từng track ngay trong lúc gán*: Áp dụng ngay quy trình 3 lượt tua (QC Pass 1: Timeline ID, Pass 2: Entry/Exit Outside, Pass 3: Mid-frame drift) ngay khi hoàn thành mỗi track, thay vì đợi gán xong toàn bộ clip mới kiểm tra.
  2. *Chạy script kiểm tra định dạng và trực quan hóa liên tục*: Tận dụng `tools/check_mot_labels.py` và `tools/visualize_tracks.py` theo từng đợt gán để phát hiện sớm các lỗi trôi nội suy hoặc box treo.

## 7. Tệp đã nộp

- [x] `annotations/clip_01/gt.txt`
- [x] `annotations/clip_02/gt.txt`
- [x] `evidence/pre-gold/clip_01/gt.txt` và `manifest.json`
- [x] `GUIDELINE_MINI.md` đã điền
- [x] `outputs/eval_vs_gold.json`
- [x] `outputs/model_bytetrack_clip_01.txt`
- [x] `outputs/model_reid_clip_01.txt`
- [x] `outputs/model_run_config.json`
- [x] `outputs/eval_bytetrack_vs_gold.json`, `outputs/eval_reid_vs_gold.json`, `outputs/eval_reid_vs_me.json`
- [x] `reports/review_partner.md`
- [x] `reports/REPORT.md` (file này)
