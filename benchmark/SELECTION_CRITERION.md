# Tiêu chí chọn chiến lược (chốt trước khi chạy retrieval)

Chốt ngày 2026-11-14, trước khi chạy ingest hay evaluate lần nào và trước khi xem bất kỳ kết quả test nào.

1. Chọn trên **tập dev (15 câu)**, không dùng test để chọn.
2. Thứ tự ưu tiên: **Evidence Hit@3 dev** cao hơn; nếu bằng nhau thì **Hit@1 dev**; nếu vẫn bằng nhau thì chiến lược **ít tài nguyên hơn** (ít chunk, ít token embed).
3. Cấu hình đã chọn được **đóng băng** (tham số chunk, filter, model) rồi mới chạy `python -m src.run evaluate --split test`. Kết quả test chỉ để báo cáo, không dùng để chỉnh.
4. Nếu sau khi xem test vẫn sửa pipeline hoặc câu hỏi, phải ghi rõ trong báo cáo và không coi test đó là kiểm tra độc lập.
5. Coherence, metadata và grounding được chấm thủ công riêng, không dùng để thay thế Hit@3 trong tiêu chí trên.
