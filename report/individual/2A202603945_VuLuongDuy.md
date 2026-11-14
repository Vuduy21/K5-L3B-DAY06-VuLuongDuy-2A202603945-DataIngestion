# Báo cáo cá nhân — Day 6

MSSV 2A202603945 · VuLuongDuy · Lớp L3B · Chủ đề: giao thông đường bộ Việt Nam. Mọi số liệu lấy từ `starter/results/` và `artifacts/experiment_log.csv`; lần chạy ingest và test cùng ngày 2026-11-14.

## Dữ liệu và pipeline
- **Chủ đề, nguồn/quyền, số trang và quy tắc tính trang:** Hai văn bản gốc đăng Công báo: Luật Trật tự, an toàn giao thông đường bộ số 36/2024/QH15 (Điều 1–89) và Nghị định 168/2024/NĐ-CP (Điều 1–55). Mỗi văn bản được Công báo chia thành hai file PDF, nên có 4 nguồn (`LUAT-36-2024-P1/P2`, `ND-168-2024-P1/P2`) với tổng 211 trang vật lý; **209 trang được tính là nội dung**. Quy tắc: trang được tính nếu còn ít nhất 200 ký tự sau khi chuẩn hóa NFC và bỏ dòng header "CÔNG BÁO/Số…"; hai trang bị loại là trang cuối trống (`LUAT-36-2024-P1` trang 21 và `ND-168-2024-P1` trang 95, 0 ký tự). `page` luôn là số trang vật lý trong từng file PDF, không phải số trang in trên Công báo. Nguồn, URL, SHA-256, số ký tự từng trang: [data/manifest.json](../../data/manifest.json); PDF không commit, tải lại bằng `build_manifest.py --download`. Về quyền sử dụng: đây là văn bản quy phạm pháp luật nên tôi hiểu là không thuộc đối tượng bảo hộ quyền tác giả (Điều 15 Luật Sở hữu trí tuệ); đây là hiểu biết của tôi, chưa được xác nhận bởi nguồn nào khác. Corpus là **bản gốc, chưa hợp nhất các sửa đổi về sau** (một số văn bản đã được sửa đổi sau thời điểm đăng); mọi câu hỏi và evidence chỉ dựa trên text của bản gốc, tôi không suy đoán ngày hiệu lực hay tình trạng hiện hành.
- **Chuẩn hóa, lỗi và giới hạn:** Dùng `pypdf`; chuẩn hóa NFC, bỏ header Công báo, nối các dòng bị ngắt cứng nhưng giữ ngắt dòng tại Chương/Mục/Điều/khoản/điểm. Không có lỗi trích xuất; 2 trang trống đã được ghi vào `ingest_stats.json`. Lỗi còn lại: `pypdf` chèn khoảng trắng thừa trong từ tiếng Việt ("ng ười", "bi ển số"); tôi không sửa vì không có cách an toàn, nên mọi chiến lược chịu ảnh hưởng như nhau, và các phép so khớp evidence bỏ hết khoảng trắng. Chunk không đi qua ranh giới trang nên điều khoản kéo dài sang trang sau bị cắt.
- **Embedding model/provider/version/số chiều, vector store/version, metric, lệnh chạy và chi phí:** `baai/bge-m3` qua API OpenRouter, 1024 chiều, không dùng tiền tố; cùng một vector query cho A, B và C. PostgreSQL 16.16 + pgvector 0.8.7 (image `pgvector/pgvector:0.8.7-pg16`), cosine (`<=>`), tìm **exact**, không dùng index xấp xỉ. Python 3.11.9; `psycopg` 3.3.8, `pypdf` 6.21.4, `python-dotenv` 1.2.4, `requests` 2.34.2. Lệnh chạy: xem mục "Chạy lại" trong [README.md](../../README.md). Chi phí embed toàn bộ corpus: 253.365 token, 57 request, 134 s, **$0,00253** (theo `usage.cost` do OpenRouter trả về); A $0,00133 và B $0,00120. Chi phí query rất nhỏ (lượt dev: 357 token, $3,57×10⁻⁶); tôi không lưu số usage của lượt test.
- **Metadata bắt buộc, trường lọc bổ sung, nguồn giá trị và lý do chọn:** Mỗi chunk có `document_id`, `source_id` (file nguồn), `source_url`, `page` (int, trang vật lý) và các trường bổ sung `document_type` (Luật/Nghị định, lấy từ tiêu đề văn bản trong manifest), `chapter` (số La Mã, lấy từ dòng "Chương X") và `article` (int, lấy từ dòng "Điều N."). Trường lọc là **`document_type`**: hai văn bản cùng bàn về nồng độ cồn, giấy phép lái xe, trừ điểm nên lọc phân biệt thật sự. `article` và `chapter` được lấy theo vị trí **đầu chunk**; hạn chế là chunk dài có thể chứa tiêu đề Điều ở phía sau (không xảy ra trong 45 chunk đã kiểm nhưng vẫn có thể xảy ra ở chunk khác).

## Cấu hình và benchmark
- **A / B / C (tham số cụ thể, khác biệt duy nhất B–C):**
  - A: cắt cứng theo ký tự, 500 ký tự, overlap 50, không lọc (1.022 chunk).
  - B: theo cấu trúc, gộp khoản/điểm tối đa 800 ký tự, luôn bắt đầu chunk mới tại Chương/Mục/Điều, không lọc (767 chunk).
  - C: dùng **cùng index với B**; khác duy nhất là lọc SQL theo `document_type` khi câu hỏi mang filter (4 câu), các câu còn lại chạy không lọc.
  - Lưu ý: A–B khác nhau cả cách cắt lẫn kích thước tối đa (500 so với 800), nên A–B không thay đúng một yếu tố như B–C.
- **≥20 câu: phân chia ≥15 dev / ≥5 test, câu metadata filter và cách kiểm chứng evidence:** [benchmark/questions.json](../../benchmark/questions.json): 20 câu, 15 dev và 5 test, chia trước khi chạy retrieval. Có 4 câu filter (Q06, Q07, Q08 ở dev; Q16 ở test); giá trị filter được coi là input giả định cung cấp trước (ngữ cảnh tra cứu quy định hay thủ tục xử phạt), không lấy từ gold. Mỗi câu có đáp án, `gold_source_id`, `gold_page`, `gold_article` và `evidence_quote`; `verify_benchmark.py` xác nhận 20/20 quote nằm đúng trang gold. Câu hỏi được soạn (có AI hỗ trợ) sau khi đọc các điều khoản liên quan trên PDF; [CẦN BẠN XÁC NHẬN: bạn đã tự đọc lại và hiểu từng câu, đặc biệt 5 câu test chưa?]. Một câu (Q20) bị gõ nhầm tên một khóa JSON sau khi tạo file; tôi chỉ sửa tên khóa trước khi chạy test, không đổi nội dung.
- **Tiêu chí chọn chiến lược đã chốt trước khi xem test:** [benchmark/SELECTION_CRITERION.md](../../benchmark/SELECTION_CRITERION.md): chọn trên dev theo Evidence Hit@3, rồi Hit@1, rồi tài nguyên; sau đó đóng băng cấu hình và chạy test một lần. Tôi không đổi pipeline, tham số hay câu hỏi sau khi xem test.

## Kết quả
| Strategy | Split | Hit@1 (n/N) | Evidence Hit@3 (n/N) | Chunk count | Thời gian | Chi phí |
|---|---|---|---|---|---|---|
| A | dev | 10/15 | 12/15 | 1.022 | embed 79,8 s | $0,00133 |
| A | test | 3/5 | 3/5 | 1.022 | (cùng index) | (cùng index) |
| B | dev | 11/15 | 12/15 | 767 | embed 53,8 s | $0,00120 |
| B | test | 3/5 | 4/5 | 767 | (cùng index) | (cùng index) |
| C | dev | 12/15 | 13/15 | 767 (dùng index B) | 0 s thêm | $0 thêm |
| C | test | 3/5 | 4/5 | 767 (dùng index B) | 0 s thêm | $0 thêm |

Thời gian là thời gian gọi API embed (gồm độ trễ mạng), không phải thời gian tính toán thuần.

| Strategy | Coherence trung bình /2 (n) | Metadata đủ và đúng (n/N) | Filter tuân thủ (n/N hoặc N/A) | Grounding 0/1/2 (số câu) và trung bình /2 |
|---|---|---|---|---|
| A | 0,4 (10) | 15/15 | N/A | 1 / 1 / 3 → 1,4 |
| B | 1,3 (10) | 15/15 | N/A | 0 / 1 / 4 → 1,8 |
| C | 1,3 (10, dùng chunk của B) | 15/15 | 3/3 (dev: 3/3; test: 1/1) | 0 / 1 / 4 → 1,8 |

Đường dẫn: trace `starter/results/traces_{A,B,C}_{dev,test}.jsonl`; tóm tắt `summary_{dev,test}.json`; thống kê nạp `ingest_stats*.json`; nhãn thủ công và quy trình `starter/results/audit/` (`coherence_scored.md`, `metadata_scored.md`, `grounding_scored.md`, `audit_summary.json`).
**Cách chọn mẫu:** coherence dùng 10 vị trí cố định trước khi xem chunk (trang ở tâm của 10 khoảng chia đều theo thứ tự manifest, tại điểm giữa trang), cùng vị trí cho A và B. Metadata và grounding dùng 5 câu test × top-3 (metadata: 45 bản ghi; grounding: 15 cặp câu–chiến lược). Bảng chấm được xáo trộn và giấu chiến lược. Tôi chấm coherence và grounding; **tôi là tác giả bài nên có nguy cơ thiên lệch**, và không có người chấm độc lập. Nhãn metadata lần đầu của tôi (A 8/15, B 7/14, C 8/15) bị lẫn giữa "chunk có liên quan không" và "metadata có đúng không"; tôi giữ bản đó ở `metadata_scored_author_v1.md` và chấm lại bằng `check_metadata_audit.py`, đọc lại PDF bằng regex riêng và đối chiếu từng bản ghi (45/45 đúng nguồn, trang, Điều, chương, loại văn bản). Do đó nhãn metadata cuối cùng do script gán, không phải đánh giá thủ công hoàn toàn; [CẦN BẠN XÁC NHẬN: bạn đã tự mở PDF đối chiếu một số dòng chưa? Nếu có thì ghi rõ số dòng đã kiểm, nếu chưa thì giữ nguyên câu này không có vế này.]

## Phân tích và kết luận
- **So sánh A–B và B–C; 2 ví dụ sai có ID câu và nguồn:**
  - **A→B:** coherence tăng 0,4 → 1,3 (A có 6/10 mẫu bị cắt giữa ý, B không có mẫu điểm 0); grounding 1,4 → 1,8; số chunk giảm 25% (1.022 → 767), token embed giảm khoảng 9,4% (132.958 → 120.401), thời gian embed giảm khoảng 33%. Retrieval chỉ nhích nhẹ: dev Hit@1 10 → 11 và Hit@3 12 → 12; test Hit@3 3 → 4 (Q16: A không tìm được Điều 9 vì ba kết quả đầu đều là điều khoản phạt nồng độ cồn của Nghị định). Vì A–B đổi cả kích thước, chênh lệch này không quy riêng cho cách cắt.
  - **B→C:** thay đúng một yếu tố (filter). Dev tăng Hit@1 11 → 12 và Hit@3 12 → 13; test không đổi (3/5 và 4/5). Câu được cứu là Q06 (dev): không lọc thì top-3 toàn là Điều 51 Nghị định về phục hồi điểm, lọc `Luật` thì top-1 là Điều 58 của Luật (`LUAT-36-2024-P2` trang 33). Filter không tốn thêm chi phí nạp nhưng chỉ dùng được khi filter biết trước.
  - **Ví dụ sai 1 — Q11 (dev, gold `ND-168-2024-P1` trang 22, Điều 7):** sai ở cả A, B và C. Top-1 của B là một khoản về nồng độ cồn 50–80 mg ở trang 32 (Điều 9, loại xe khác); hai kết quả sau là Điều 18 (trang 51). Loại phương tiện (mô tô) chỉ có trong tiêu đề Điều 7 ở trang 18, không nằm trong chunk evidence, nên chunk không đủ ngữ cảnh phân biệt. Mô hình không bị lỗi mà **chunk thiếu ngữ cảnh**.
  - **Ví dụ sai 2 — Q20 (test, gold `LUAT-36-2024-P1` trang 13, Điều 12):** Evidence Hit@3 tự động = 0 ở cả ba cấu hình vì phần dẫn nhập ("phải quan sát, giảm tốc độ…") và điểm e (khu vực trường học, bệnh viện…) nằm ở hai chunk khác nhau. Cả hai chunk đều nằm trong top-3 của B và C, nên tôi chấm grounding là 2, nhưng chỉ số chính (đòi đủ evidence trong một chunk) là sai. Đây là điểm yếu của chunking theo cấu trúc với danh sách dài.
  - Các lỗi khác đáng ghi: Q14 (dev) sai ở cả ba cấu hình; top-1 của B là chunk của Nghị định (trang 26, Điều 8) có lặp lại đúng con số 20 m/40 m; tôi chưa ghi nguồn đó là evidence hợp lệ thay thế trong gold, và không sửa gold sau khi xem kết quả. Q17 (test): B và C có gold ở top-2 nhưng top-1 là đoạn cồn 50–80 mg của loại xe khác.
- **Chiến lược chọn, đánh đổi, điều kiện áp dụng:** Theo tiêu chí đã chốt (dev Hit@3 trước), **chọn C** (13/15 so với 12/15 của A và B). Trên test, C bằng B (4/5) và hơn A (3/5). Cần lưu ý chênh lệch giữa B và C chỉ là một câu; không đủ để kết luận C tốt hơn B nói chung. Đánh đổi: C chỉ có ích khi `document_type` được biết trước (từ ngữ cảnh người dùng); nếu không thì B là lựa chọn hợp lý. A rẻ để triển khai nhưng có coherence thấp nhất và nhiều chunk nhất, nên tôi không chọn A.
- **Hạn chế của dữ liệu, nhãn, test nhỏ, đo thời gian/chi phí:**
  - Chỉ có 15 câu dev và 5 câu test; mỗi câu chiếm 7–20% số điểm nên mọi chênh lệch 1 câu đều nằm trong sai số.
  - Mỗi câu test cùng chủ đề với ít nhất một câu dev (cồn, điểm GPLX, dừng đỗ xe): rò rỉ chủ đề.
  - Mỗi câu chỉ có một đoạn evidence gold; Q14 cho thấy gold còn thiếu evidence thay thế.
  - Corpus nhỏ (hai văn bản, một lĩnh vực); không suy rộng sang nội dung khác.
  - Tác giả vừa viết câu hỏi vừa chấm; coherence và grounding không có người chấm độc lập; nhãn metadata cuối do script gán.
  - Chunk theo trang, không đi qua ranh giới trang; lỗi khoảng trắng của `pypdf` chưa được sửa.
  - Thời gian đo qua API (có độ trễ mạng) và chi phí lấy từ `usage.cost` của OpenRouter; model ở phía nhà cung cấp có thể thay đổi nên kết quả có thể không tái lập đúng từng chữ số sau này.
- **Nếu làm lại hoặc mở rộng, cải tiến gì?** (1) Thêm ngữ cảnh vào chunk (tiêu đề Điều và loại phương tiện) như một thí nghiệm riêng để xử lý lỗi kiểu Q11; (2) cho chunk đi qua ranh giới trang và chia danh sách dài có kèm câu dẫn nhập để xử lý Q20; (3) tách A–B thành hai bước (đổi kích thước, rồi đổi cách cắt) để so sánh sạch hơn; (4) ghi nhiều evidence thay thế và tăng benchmark lên 50–100 câu có người chấm thứ hai; (5) thử hybrid với BM25.

## Công cụ AI và cách kiểm tra
Tôi dùng Claude Code (Claude Sonnet 5.5) để viết mã pipeline, soạn nháp benchmark, sinh bảng chấm và script kiểm tra. Cách kiểm tra: `verify_benchmark.py` xác nhận 20/20 evidence nằm đúng trang gold; số liệu trong báo cáo lấy trực tiếp từ file kết quả do pipeline sinh ra; nhãn coherence và grounding do tôi chấm; nhãn metadata đối chiếu với PDF bằng script đọc lại nguồn. [CẦN BẠN BỔ SUNG nếu có: các bước kiểm tra thủ công khác mà bạn đã tự làm.]
