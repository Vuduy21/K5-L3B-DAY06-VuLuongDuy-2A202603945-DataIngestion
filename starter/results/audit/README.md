# Hướng dẫn chấm thủ công

Người chấm: tác giả bài lab (không độc lập hoàn toàn: ghi nguy cơ thiên lệch trong báo cáo).
**Không mở `audit_key.json` và không mở `traces_*` cho đến khi chấm xong.** Mỗi dòng có `label_id` ngẫu nhiên, không cho biết chiến lược.
Mở file `.csv` bằng Excel/Google Sheets (đã có BOM UTF-8). Chỉ điền các cột trống.

## 1. `coherence_sheet.csv` — Chunk coherence (20 dòng = 10 vị trí × 2 cách chunk)

Vị trí được chọn theo quy tắc cố định trước khi xem chunk: lấy trang nội dung ở tâm của 10 khoảng chia đều (theo thứ tự manifest), điểm giữa trang. Chiến lược C dùng chung chunk của B nên không chấm riêng.

Cột `score_0_1_2` (xem `source_context_around_position` để hiểu ngữ cảnh gốc):
- **0**: bị cắt giữa ý hoặc thiếu chủ thể khiến không hiểu được.
- **1**: hiểu một phần, thiếu ngữ cảnh (ví dụ không biết đang nói về loại xe nào).
- **2**: tự hiểu được và giữ trọn ý.

Lưu ý: chunk A cắt cứng theo ký tự nên có thể cắt giữa từ; lỗi khoảng trắng như "ng ười" do trích PDF không tính là lỗi của chunking.
Ghi lý do ngắn ở cột `reason` cho mọi dòng.

## 2. `metadata_sheet.csv` — Metadata usefulness (45 dòng = 5 câu test × top-3 × A/B/C)

Với mỗi dòng, mở PDF theo cột `open_pdf` (file trong `starter/data/raw/`, trang vật lý) và đối chiếu chunk với nguồn:
- `source_ok_0_1`: `stored_source_id` đúng với file/phần chứa nội dung chunk.
- `page_ok_0_1`: nội dung chunk thực sự nằm trên `stored_page`.
- `article_ok_0_1`: `stored_article` là Điều đang hiệu lực tại **đầu chunk**.
- `doc_type_ok_0_1`: `stored_document_type` (Luật/Nghị định) đúng.
- `filter_ok_0_1_or_NA`: nếu cột `required_filter` có giá trị thì 1 khi chunk thỏa filter, 0 nếu không; nếu không có yêu cầu filter thì ghi `NA`.
- `complete_and_correct_0_1`: 1 chỉ khi mọi trường trên (và `chapter` nếu bạn kiểm tra) đều đủ và đúng.
- `error_note`: mô tả từng lỗi.

Sau khi chấm, hãy viết ít nhất một ví dụ trường metadata giúp truy vết hoặc lọc, và một hạn chế (ví dụ `article` chỉ phản ánh Điều ở đầu chunk).

## 3. `grounding_sheet.csv` — Grounding quality (15 dòng = 5 câu test × A/B/C)

Chỉ đánh giá **bằng chứng truy xuất** (top-3), không phải chất lượng câu trả lời của LLM. Đọc `question`, `expected_answer` và 3 chunk, rồi chấm `score_0_1_2`:
- **0**: không có bằng chứng.
- **1**: có bằng chứng nhưng thiếu điều kiện/ngữ cảnh cần thiết.
- **2**: đủ để trả lời và truy được nguồn.
Ghi lý do ở cột `reason`.

## 4. Tổng hợp

```powershell
cd starter
.\.venv\Scripts\python.exe scripts\score_audit.py
```

Dòng chưa điền được báo là `unfilled`, không được giả định. Kết quả ghi vào `audit_summary.json`.
