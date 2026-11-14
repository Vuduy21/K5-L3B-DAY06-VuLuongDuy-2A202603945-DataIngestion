# Day 06 · Data Ingestion Engineering

**Lab cá nhân** · **4 giờ** · **Dữ liệu tự chọn**

Biến tài liệu thành kho tri thức có thể truy xuất cho AI agent, rồi đo xem cách chuẩn bị dữ liệu nào hiệu quả nhất.

| 📄 Dữ liệu | 🧩 Chiến lược | 🎯 Benchmark |
|---|---|---|
| Tối thiểu **30 trang nội dung** | Tối thiểu **3 cấu hình** | Tối thiểu **20 câu hỏi** |

## Bài làm của học viên (VuLuongDuy · 2A202603945 · L3B)

**Corpus:** Luật Trật tự, an toàn giao thông đường bộ 36/2024/QH15 và Nghị định 168/2024/NĐ-CP, bản gốc đăng Công báo, 209 trang nội dung ([data/manifest.json](data/manifest.json): URL, SHA-256, quy tắc đếm trang). PDF **không commit**, tải bằng lệnh bên dưới. Văn bản là bản gốc, chưa hợp nhất các sửa đổi về sau.
**Model / store:** `baai/bge-m3` qua OpenRouter (1024 chiều); PostgreSQL 16 + pgvector 0.8.7 (cosine, exact search). Python 3.11.9.
**Benchmark:** [benchmark/questions.json](benchmark/questions.json) (20 câu: 15 dev / 5 test, 4 câu filter), tiêu chí chọn chiến lược chốt trước khi chạy: [benchmark/SELECTION_CRITERION.md](benchmark/SELECTION_CRITERION.md).

### Chạy lại (Windows PowerShell, từ thư mục `starter/`)

```powershell
python -m venv .venv; .\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env        # điền OPENROUTER_API_KEY và EMBEDDING_MODEL=baai/bge-m3 (không commit .env)
docker compose -p day6_student_starter up -d --wait
python scripts\check_setup.py
python scripts\build_manifest.py --download   # tải 4 PDF từ Công báo, tạo lại data/manifest.json
python scripts\verify_benchmark.py            # kiểm tra evidence nằm đúng trang gold (20/20)
python -m src.run ingest                      # chunk A và B, embed, lưu pgvector (nạp lại không nhân đôi)
python -m src.run evaluate                    # dev
python -m src.run evaluate --split test       # test: chỉ chạy sau khi đã chốt cấu hình
python scripts\make_audit_sheets.py           # bảng chấm thủ công (đã giấu chiến lược)
python scripts\check_metadata_audit.py --write-scored   # đối chiếu metadata với PDF
python scripts\score_audit.py                 # tổng hợp coherence / metadata / grounding
```

### Cấu hình và kết quả

| | Chunk | Dev Hit@1 / Hit@3 | Test Hit@1 / Hit@3 |
|---|---|---|---|
| A | cố định 500 ký tự, overlap 50 | 10/15 · 12/15 | 3/5 · 3/5 |
| B | theo cấu trúc, tối đa 800 | 11/15 · 12/15 | 3/5 · 4/5 |
| C | như B + filter `document_type` khi câu hỏi có filter | 12/15 · 13/15 | 3/5 · 4/5 |

Mẫu nhỏ (15 dev, 5 test) chỉ để minh họa, không kết luận chiến lược tốt nhất. Trace, thống kê nạp, bảng chấm: `starter/results/` (xem `starter/results/audit/`). Nhật ký thí nghiệm: [artifacts/experiment_log.csv](artifacts/experiment_log.csv). Chi phí embed toàn bộ pipeline dưới $0,01 (lấy từ `usage.cost` do OpenRouter trả về).

## Bắt đầu nhanh

Dùng [starter PostgreSQL + pgvector](starter/README.md) để dựng database và hoàn thiện các hàm TODO, hoặc tự chọn vector store tương đương. Starter chỉ là khung: **bạn tự hiện thực pipeline và benchmark**.

## 1. Xây pipeline

![Đọc tài liệu, chuẩn hóa, chia chunk, tạo vector, lưu và kiểm tra](assets/ingestion-pipeline.svg)

Chọn tài liệu được phép sử dụng; giữ **ID tài liệu, nguồn, trang/vị trí** và metadata phù hợp. Dùng embedding model thật qua API hoặc chạy local; lưu và truy xuất bằng pgvector, Qdrant, Chroma hoặc một store tương đương.

## 2. So sánh và đánh giá

![Ba chiến lược được đánh giá trên cùng corpus và benchmark dev/test](assets/benchmark-workflow.svg)

Dùng cùng dữ liệu, model và câu hỏi cho cả ba cấu hình. Tách **15 câu dev / 5 câu test** trước khi chạy; chọn cấu hình trên dev, rồi đánh giá test sau khi cố định. Mỗi câu hỏi cần có đoạn bằng chứng và trang nguồn; thiết kế bộ câu hỏi và đánh giá theo [BENCHMARK.md](BENCHMARK.md).

Đánh giá theo năm khía cạnh: **độ chính xác truy xuất**, **tính mạch lạc của chunk**, **tính hữu dụng của metadata**, **chất lượng grounding** và **tác động của chiến lược dữ liệu**. Giải thích lựa chọn bằng kết quả, ví dụ lỗi và các đánh đổi.

## 3. Chuẩn bị bài nộp

1. Chạy pipeline và lưu cấu hình, kết quả top-3, trace cùng nhãn đánh giá thủ công.
2. Điền [thông tin học viên](STUDENT.md), [nhật ký thí nghiệm](artifacts/experiment_log.csv) và bản sao [mẫu báo cáo cá nhân](report/individual/MSSV_HoTen.md).
3. Kiểm tra mã nguồn, cách chạy, manifest dữ liệu và checklist trong [SUBMISSION.md](SUBMISSION.md).

## Tài liệu hướng dẫn

| Bạn cần tìm | Tài liệu |
|---|---|
| Setup baseline PostgreSQL + pgvector | [starter/README.md](starter/README.md) |
| Các bước làm và cách tính chỉ số | [GUIDE.md](GUIDE.md) |
| Tiến độ trong 4 giờ | [CHECKPOINTS.md](CHECKPOINTS.md) |
| Năm tiêu chí benchmark và bộ câu hỏi | [BENCHMARK.md](BENCHMARK.md) |
| Tiêu chí chấm điểm | [RUBRIC.md](RUBRIC.md) |
| Quy tắc sử dụng dữ liệu, AI và API | [RULES.md](RULES.md) |
| Cách nộp bài | [SUBMISSION.md](SUBMISSION.md) |

[data/format-example.json](data/format-example.json) chỉ minh họa định dạng, không phải corpus đủ điều kiện. Phần xử lý và benchmark do bạn tự hiện thực; không bắt buộc xây chatbot.
