# MES Engineering Mentorship Log (Nhật ký Huấn luyện Hệ thống MES)

- **Mentor:** 10-Year MES Solution Architect & Factory Specialist
- **Mentee:** System Engineer Trainee
- **Language Mode:** Bilingual (English - Vietnamese)
- **Status:** Active

---

## 1. Master Training Roadmap (Lộ trình Đào tạo Tổng thể)

```
[Phase 1] Shop Floor Mindset & ISA-95 Standards (Tư duy Sàn xưởng & Chuẩn ISA-95)
    ├── Lesson 1: Overview & The Purpose of MES (Tổng quan & Nỗi đau MES giải quyết) [DONE]
    └── Lesson 2: Core Data Models in MES (Mô hình Dữ liệu Cốt lõi) [IN PROGRESS]

[Phase 2] Data Flow & Manufacturing Logic (Dòng chảy Dữ liệu & Nghiệp vụ Sản xuất)
    ├── Lesson 3: Routing Enforcement & Poka-Yoke (Ép buộc Quy trình & Chặn lỗi)
    ├── Lesson 4: Component Traceability & Genealogy (Truy xuất Nguồn gốc 2 chiều)
    └── Lesson 5: WIP Tracking & Scrap Management (Quản lý Bán thành phẩm & Phế phẩm)

[Phase 3] IT & OT System Integration (Tích hợp Hệ thống IT & OT)
    ├── Lesson 6: Lower-layer Integration (PLC, Sensor, Barcode, OPC-UA, MQTT)
    ├── Lesson 7: Upper-layer Integration (ERP/SAP, WMS, PLM via API/Message Queue)
    └── Lesson 8: Database Architecture & High-performance SQL (Thiết kế CSDL & Tối ưu SQL)

[Phase 4] Operations, KPIs & Emergency Troubleshooting (Vận hành & Ứng cứu Sự cố)
    ├── Lesson 9: OEE Calculation & Downtime Tracking (Tính toán OEE & Giám sát Dừng máy) [DONE]
    ├── Lesson 10: Handling Stop-Line Incidents & Disaster Recovery (Cứu dừng chuyền) [DONE]
    └── Lesson 11: Real-world Factory Capstone Project (Dự án Thực tế) [DONE]

[Phase 5] Deep-Dive Mastery of 7 Core MES Modules (Làm Chủ 7 Module Cốt Lõi Chuẩn MESA-11 / ISA-95)
    ├── Module 1: Resource Allocation & Status (Thiết bị, Khuôn gá, Tuổi thọ dao, Ma trận tay nghề) [ACTIVE]
    ├── Module 2: Operations / Detail Scheduling (Điều độ chi tiết, Finite Capacity, Dispatching Rules) [ACTIVE]
    ├── Module 3: Dispatching Production Units (Cấp phát lệnh, Luồng WIP trạm, Queue Management) [ACTIVE]
    ├── Module 4: Document Control (SOP điện tử, Digital Work Instructions, Khóa phiên bản ECN) [ACTIVE]
    ├── Module 5: Data Collection & Acquisition (Thu thập IoT/PLC, Lực/Nhiệt/Áp, Time-series DB) [ACTIVE]
    ├── Module 6: Quality Management & Interlock (IQC/PQC/OQC, Defect Containment, Station Lockout) [ACTIVE]
    └── Module 7: Process Management & As-Built Genealogy (Phả hệ sản phẩm 5M1E, Truy vết 2 chiều) [ACTIVE]
```

---

## 2. Learning Progress Log (Nhật ký Tiến độ Học tập)

### Lesson 1: Overview & The Purpose of MES (Tổng quan & Mục đích)
* **Status:** Completed
* **Core Concepts:**
  * **Shop Floor Pain Points (Nỗi đau xưởng sản xuất):** Information black hole (Hộp đen thông tin), recall disaster (Thảm họa triệu hồi sản phẩm), inaccurate production logs (Số liệu giả mạo).
  * **Role of MES:** Central Nervous System (Hệ thần kinh trung ương) connecting ERP (Brain / Macro planning) and PLC/Machines (Muscle / Real-time physical layer).
* **Hands-on Case 1 Evaluation:**
  * *Question:* How to prevent an uninspected or failed unit from being packed? (Làm sao chặn sản phẩm chưa test hoặc test fail lọt vào khâu đóng thùng?)
  * *Mentee Solution:* Use test machine confirmation; packing checks for test PASS signal; return to rework if not passed.
  * *Expert Feedback:* Spot on! In industrial MES terminology, this is called **Routing Enforcement (Ép buộc quy trình)** and **Station Interlock (Khóa liên động trạm)** using **Poka-Yoke (Mistake-proofing)** logic.

---

### Lesson 2: Core Data Models in MES (Mô hình Dữ liệu Cốt lõi)
* **Status:** Completed
* **Key Entities (Các thực thể chính):**
  1. **Work Order (WO) / Production Order:** Lệnh sản xuất từ ERP.
  2. **BOM (Bill of Materials):** Định mức vật tư, linh kiện cần dùng cho 1 SKU.
  3. **Routing / Process Plan:** Chuỗi công đoạn tuần tự (Step 10 -> Step 20 -> Step 30...).
  4. **UID / Serial Number (Parent & Child):** Định danh duy nhất của sản phẩm và linh kiện.
* **Hands-on Case 2 Evaluation & Key Takeaway:**
  * *Rookie Trap (Cái bẫy kinh điển):* Nghĩ rằng chỉ cần quét 1 mã Serial là đủ.
  * *Industrial Principle - Component Binding (Liên kết Cha - Con):*
    - Bắt buộc phải có **2 mã**: Mã Cha (`Parent_UID` - Khung máy) + Mã Con (`Child_UID` / `Component_Lot` - Pin).
    - Tạo bảng phả hệ: `Product_Genealogy (Parent_SN, Child_SN, Component_Lot, Timestamp, Operator_ID)`.
  * *2-Way Traceability (Truy xuất nguồn gốc 2 chiều):*
    - **Backward Traceability (Truy xuất ngược):** Phone SN $\rightarrow$ Pin $\rightarrow$ Lô vật liệu $\rightarrow$ Nhà cung cấp (Supplier).
    - **Forward Traceability (Truy xuất xuôi):** Lô Pin lỗi $\rightarrow$ Tìm ra tất cả Phone SN đã lắp $\rightarrow$ Chặn xuất kho (Containment / Quarantine).

---

### Lesson 3: Routing Enforcement & State Machine (Ép buộc Quy trình & Máy Trạng thái)
* **Status:** Completed
* **Key Concepts:**
  * **Happy Path vs Edge Cases (Luồng chuẩn vs Trường hợp ngoại lệ):** Trong xưởng thực tế, không bao giờ được phép "mặc định" (Never assume).
  * **The 5-Gate Validation Algorithm (Thuật toán 5 Cổng Kiểm Soát):**
    1. *Gate 1 - Existence Check:* SN có tồn tại trong hệ thống không?
    2. *Gate 2 - Scrap/Hold Check:* Có bị phế phẩm (SCRAP) hoặc QA khóa (ON_HOLD) không?
    3. *Gate 3 - Previous Station Sequence & Result:* Trạm trước (AOI) đã làm chưa và có PASS không? (Chống nhảy cóc / Skip station).
    4. *Gate 4 - Current Station Re-entry:* Đã PASS ở trạm này trước đó chưa? (Chống test trùng lặp / Fraud cycle).
    5. *Gate 5 - Work Order Status:* Lệnh sản xuất còn hiệu lực (ACTIVE) không?
* **Hands-on Case 3 Takeaway:**
  * Logic của học viên `IF AOI_TEST = PASS THEN ALLOW` đúng về bản chất nghiệp vụ (Happy path).
  * Thực tế công nghiệp cần mở rộng sang đầy đủ 5 cổng để chống lỗi thao tác con người (Poka-Yoke).

---

### Lesson 4: WIP Tracking & The Rework Loop (Quản lý Bán thành phẩm & Vòng lặp Sửa chữa)
* **Status:** Completed
* **Hands-on Case 4 Evaluation (Đánh giá Bài tập 4):**
  * *Học viên trả lời xuất sắc:* Nắm đúng bản chất thay thế ID linh kiện, log phế phẩm NG cho linh kiện cũ, và nhận định chính xác tính chất phụ thuộc của trạm quay đầu (AOI vs ICT).
* **Industrial Best Practices (Thực tiễn ngành):**
  1. *Component De-binding & Re-binding:* Không xóa đè dữ liệu cũ. Cũ gán `STATUS = UNBOUND/SCRAP` + `DEFECT_CODE`, mới gán `STATUS = BOUND/ACTIVE`. Dữ liệu này dùng để truy thu bồi thường nhà cung cấp (Supplier Claim).
  2. *Dynamic Re-entry Matrix (Ma trận quay đầu linh hoạt):* Hàn tay thủ công luôn tiềm ẩn rủi ro chập chì/ngược cực $\rightarrow$ Bắt buộc quay lại AOI soi mối hàn rồi mới đo điện tại ICT.
  3. *Max Rework Limit (Luật giới hạn số lần sửa):* Một unit chỉ được sửa tối đa $N$ lần (thường $N \le 2$). Quá giới hạn $\rightarrow$ Bắt buộc `FORCED_SCRAP` do rủi ro giòn mạch (thermal stress).

---

### Lesson 5: IT & OT Integration - Connecting Lower-layer Hardware (Tích hợp IT-OT: Giao tiếp Thiết bị Tầng dưới)
* **Status:** Completed
* **Hands-on Case 5 Evaluation (Đánh giá Bài tập 5):**
  * *Học viên giải quyết rất chuẩn xác:*
    1. Cơ chế Timeout trên PLC để tránh treo máy.
    2. Cơ chế lưu trữ đệm dự phòng (Store-and-Forward / Offline Mode) và cân nhắc đánh đổi giữa Dừng chuyền vs OEE.
* **Industrial Best Practices (Thực tiễn ngành):**
  * *Handshake Timeout & Heartbeat (Nhịp tim):* PLC chạy TON Timer (3-5s). Đồng thời duy trì biến Heartbeat (0-1 toggle liên tục mỗi giây). Mất nhịp tim = Báo động trước khi hàng vào trạm.
  * *Store-and-Forward (Lưu đệm & Đồng bộ sau):* Áp dụng cho các trạm chỉ thu thập dữ liệu (Data Logging).
  * *Quality vs OEE Trade-off (Đánh đổi Chất lượng và Năng suất):* Với các trạm then chốt (Critical Interlock) đòi hỏi kiểm tra 5 cổng (an toàn, y tế, pin) $\rightarrow$ BẮT BUỘC DỪNG CHUYỀN nếu mất kết nối MES để phòng ngừa rủi ro thu hồi sản phẩm.

---

### Lesson 6: Upper-Layer Integration (Tích hợp Tầng trên: MES <-> ERP / SAP)
* **Status:** Completed
* **Hands-on Case 6 Evaluation (Đánh giá Bài tập 6):**
  * *Học viên nhận định:* Sử dụng Traceability để truy vết và đối soát định kỳ (Cycle Count) cùng thủ kho để phát hiện chênh lệch.
  * *Bình luận chuyên gia:* Đối soát định kỳ là cần thiết nhưng mang tính "hậu kiểm" (phát hiện sau khi sự việc đã rồi). Sức mạnh thực sự của MES là **Kiểm soát tại nguồn thời gian thực (Real-time Material Control)**.
* **Industrial Best Practices (Thực tiễn ngành):**
  1. *Material Loading / Kitting (Nạp vật tư vào trạm):* Công nhân phải quét mã thùng/cuộn vật tư trước khi lắp. MES đếm lùi số lượng khả dụng (`Available_Qty`). Hết số lượng thì máy khóa, không thể tự tiện lấy thêm.
  2. *Component Scrap Declaration (Khai báo phế phẩm linh kiện con):* Làm rơi vỡ pin $\rightarrow$ Bắt buộc quét mã khai báo hỏng trên giao diện MES.
  3. *Real-time ERP Movement Types:* MES lập tức bắn bản tin trừ kho phế phẩm lên ERP (ví dụ trong SAP: Movement Type 551 - Scrap issue, thay vì chỉ dùng mvt 261 - Normal consumption). Số sách ERP luôn khớp với sàn xưởng theo từng giây.

---

### Lesson 7: Database Architecture & High-Performance SQL in MES (Kiến trúc CSDL & Tối ưu SQL)
* **Status:** Completed
* **Hands-on Case 7 Evaluation (Đánh giá Bài tập 7):**
  * *Học viên:* Viết đúng hoàn toàn logic SQL (`GROUP BY`, `COUNT(*)`, `ORDER BY DESC LIMIT 3`).
  * *Bình luận chuyên gia (Hiệu năng thực chiến):*
    1. *The SARGability Trap:* Dùng `Date(Test_Time) = CURDATE()` làm vô hiệu hóa Index trên cột `Test_Time`, ép DB phải Full Table Scan 20 triệu dòng, có thể làm treo server MES trong giờ sản xuất.
    2. *Tối ưu SARGable Range:* Viết thành `Test_Time >= CURDATE() AND Test_Time < CURDATE() + INTERVAL 1 DAY` để kích hoạt Index Seek/Range Scan siêu tốc.
    3. *Nghiệp vụ Xưởng:* `COUNT(*)` (tổng số lần test fail) vs `COUNT(DISTINCT Serial_Number)` (tổng số sản phẩm bị lỗi thực tế).

---

### Lesson 8: OEE Calculation & Downtime Tracking (Tính toán OEE & Giám sát Dừng máy)
* **Status:** Completed
* **Hands-on Case 8 Evaluation (Đánh giá Bài tập 8):**
  * *Kết quả thú vị:* Phép nhân OEE triệt tiêu của học viên ra kết quả cuối cùng đúng $342 / 420 \approx 81.43\%$. Tuy nhiên, có sự nhầm lẫn ở từng thành phần $A$ và $P$ do lấy mốc trừ nhầm.
* **Industrial Breakdown (Chuẩn hóa số liệu):**
  1. *Planned Production Time (Thời gian KH sản xuất):* $480 - 60 = 420$ phút (Nghỉ trưa/họp ca không tính vào kế hoạch).
  2. *Operating Time (Thời gian thực chạy):* $420 - 30 = 390$ phút (Không lấy $480 - 30$).
  3. *Availability (A):* $390 / 420 \approx 92.86\%$ (Không thể $> 100\%$).
  4. *Performance (P):* $(360 \times 1) / 390 = 360 / 390 \approx 92.31\%$.
  5. *Quality (Q):* $(360 - 18) / 360 = 342 / 360 = 95.00\%$.
  6. *OEE Tổng thể:* $A \times P \times Q = 81.43\%$.

---

### Lesson 9: Stop-Line Emergency Response & The Final Capstone (Ứng cứu Dừng Chuyền & Tình huống Thực chiến Cuối cùng)
* **Status:** Completed (Graduated!)
* **Hands-on Case 9 Evaluation (Đánh giá Bài thi Tốt nghiệp):**
  * *Học viên xử lý chuẩn mực:*
    1. Check log và tìm mã lỗi (Error Code) để cô lập nguyên nhân (Triage).
    2. Chạy Offline Mode có điều kiện: Chỉ cho phép khi có cơ chế lưu trữ đệm tại PLC/IPC để đồng bộ sau; nếu không thể test hoặc không lưu được dữ liệu thì bắt buộc DỪNG CHUYỀN để bảo toàn chất lượng.
* **Industrial Post-Mortem Playbook (Sổ tay Ứng cứu Ca đêm):**
  1. *Quick Triage in 60s:*
     - Ping Gateway/Server (Loại trừ sự cố mạng).
     - Kiểm tra đầy ổ đĩa (Disk Full / Log File Growth - thủ phạm số 1 khiến DB treo cứng).
     - Kiểm tra Deadlock / Long running query (`sys.dm_exec_requests` hoặc `sp_who2`).
  2. *Controlled Offline Mode:* Khi chạy offline, phải có giám sát trưởng ca và khóa trạm kiểm tra an toàn then chốt.
  3. *Post-Recovery Audit (Đối soát sau phục hồi):* Đối chiếu số đếm cảm biến phần cứng (Hardware Sensor Counter trên PLC) với số bản ghi MES đồng bộ bù lên để đảm bảo không thất thoát 1 sản phẩm nào.

---

## 3. Course Summary & Core Competencies (Tổng kết Năng lực Đạt được)

| Lĩnh vực (Domain) | Trọng tâm Kiến thức (Core Knowledge) |
| :--- | :--- |
| **Tiêu chuẩn Ngành** | Chuẩn ISA-95 (Purdue Model), Poka-Yoke (Mistake-proofing), Lean, OEE. |
| **Dữ liệu Sàn xưởng** | Work Order, BOM, Routing, Parent-Child Binding, 2-Way Traceability (Xuôi & Ngược). |
| **Logic Kiểm soát** | The 5-Gate Validation Algorithm, Máy trạng thái (State Machine), Dynamic Rework Loop. |
| **Tích hợp IT-OT** | Handshake Protocol, OPC-UA/MQTT, Timeout Watchdog, Store-and-Forward Buffering. |
| **Tích hợp ERP** | Master Data vs Transactional Data, Backflushing, Real-time Scrap Movement (SAP mvt 551). |
| **Cơ sở Dữ liệu MES** | Tách bảng Current vs History, SARGable SQL Queries, Smart Indexing, Partitioning. |
| **Xử lý Sự cố Xưởng** | Phản ứng dừng chuyền (Stop-Line Triage), Cách ly lỗi, Quản trị rủi ro Chất lượng vs Năng suất. |

---

## 4. Advanced SQL & Query Optimization Lab (Phòng Luyện SQL Tối ưu Thực chiến)

### Challenge 1: The "Latest Status / Latest Station" Problem (Truy vấn Trạng thái Mới nhất)
* **Status:** Completed
* **Hands-on Evaluation & Trap Analysis:**
  * *Điểm tốt:* Học viên duy trì chuẩn SARGable range date (`>= CURDATE() AND < CURDATE() + 1 DAY`).
  * *Cái bẫy chết người (The Non-aggregated GROUP BY Trap):*
    1. Trong SQL chuẩn (SQL Server, Oracle, PostgreSQL, MySQL Strict Mode): Bị báo lỗi cú pháp ngay lập tức vì `Station_ID` và `Test_Result` không nằm trong `GROUP BY` hay hàm tổng hợp.
    2. Trong MySQL Non-strict: Sinh ra **"Dữ liệu Ma" (Frankenstein Data)**. CSDL lấy `Max(Test_Time)` ở trạm ICT lúc 08:30 nhưng lại bốc ngẫu nhiên `Station_ID = SMT` ở dòng lúc 08:00 $\rightarrow$ Sai lệch dữ liệu nghiêm trọng!
* **The Master Solution (Window Function ROW_NUMBER):**
  ```sql
  WITH Ranked AS (
      SELECT Serial_Number, Station_ID, Test_Result, Test_Time,
             ROW_NUMBER() OVER(PARTITION BY Serial_Number ORDER BY Test_Time DESC) as rn
      FROM tbl_Unit_History
      WHERE Test_Time >= CURDATE() AND Test_Time < CURDATE() + INTERVAL 1 DAY
  )
  SELECT Serial_Number, Station_ID, Test_Result, Test_Time
  FROM Ranked WHERE rn = 1;
  ```

---

### Challenge 2: Calculating First Pass Yield (FPY - Tỷ lệ Đạt Lần Đầu)
* **Scenario:** Phân biệt giữa Final Yield (test FAIL rồi đi sửa xong test lại thành PASS) và First Pass Yield (ngay lần test đầu tiên đã PASS mà không cần sửa).
* **Objective:** Viết truy vấn tính FPY tại trạm `ICT_TEST` trong ngày hôm nay.
* **Status:** In Progress

---

## 5. MES Core Modules Deep-Dive Knowledge Base (Làm Chủ 7 Module Cốt Lõi MES)

### Module Reference Map Across Leading MES Platforms:
| MESA-11 Core Module | Siemens Opcenter | Rockwell FactoryTalk | Dassault DELMIA Apriso | AVEVA / Wonderware | In-House / Custom MES Pattern |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **1. Resource Allocation & Status** | Equipment & Tool Management | Equipment State Model | Machine & Tool Tracking | Entity Model & Util. | `tbl_Resource`, `tbl_Tool_Life` |
| **2. Operations/Detail Scheduling** | Opcenter APS (Preactor) | FactoryTalk Production | Apriso Production Dispatch | Work Task Scheduler | Priority Engine / Dispatch Queue |
| **3. Dispatching Production Units** | Order & WIP Execution | Order Execution / eDHR | Production Run Execution | Job Dispatch & Tracking | `tbl_Work_Order`, `tbl_WIP_Queue` |
| **4. Document Control** | Electronic Work Instructions | FactoryTalk Paperless | Visual Work Instructions | Operator Guidance | `tbl_Document_SOP`, `tbl_ECN` |
| **5. Data Collection & Acquisition** | Opcenter Connect / OPC | FT Live Data / Linx | Apriso Machine Integrator | AVEVA Historian / OI | `tbl_Process_Param_Log`, TimescaleDB |
| **6. Quality Management** | Opcenter Quality / Interlock | FT Quality / Hold-Quarantine | Quality Non-Conformance | MES Quality Module | `tbl_QC_Inspection`, Station Interlock |
| **7. Process Mgmt & Genealogy** | As-Built Genealogy Engine | Product Tracking / Genealogy | Complex Genealogy Tree | Genealogy & Traceability | `tbl_Genealogy_Link`, 5M1E Model |

### Architectural Design Guidelines & Edge Cases:
* **Resource Allocation:** Tool life limit enforcement (Warning vs Lockout threshold), Skill matrix operator check (Level 1-4 vs Operation requirement).
* **Detail Scheduling:** Dynamic dispatching (FIFO, EDD, Critical Ratio, Setup Matrix Optimization).
* **Dispatching Units:** Station WIP Buffer Cap, Backpressure control, Split/Merge lot mechanics.
* **Document Control:** Revision Lock on ECN/ECO, Digital signature (21 CFR Part 11 compliant), Mandatory Read Acknowledgement.
* **Data Collection:** High-frequency time-series segregation (OLTP vs Timescale/Historian), Deadband filtering, Edge Store-and-Forward.
* **Quality Interlock:** 3-tier interlock (UI lock, API route rejection, PLC hardware cylinder clamp), Consecutive NG Rule ($N \ge 3 \rightarrow$ Auto Machine Hold).
* **Genealogy (5M1E):** Backward trace (Parent $\rightarrow$ Component lot $\rightarrow$ Supplier PO) & Forward containment (Defective raw lot $\rightarrow$ All impacted Parent Serial Numbers).

---











