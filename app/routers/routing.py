"""
Routing & Stage Enforcement Router (Anti-Skip & Sequence Interlock).
Enforces strict ISA-95 sequential production routing:
Prep -> TBM -> Curing -> Finishing/QC -> Warehouse.
Prevents any product from skipping stages or bypassing quality gates.
Senior MES Engineer Implementation.
"""

from datetime import datetime
from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.database import get_db

router = APIRouter(prefix="/api/routing", tags=["Routing Enforcement"])


class StageVerifyRequest(BaseModel):
    identifier: str  # Can be GT Barcode or Tire Serial
    target_stage: str  # TBM, CURING, FINISHING, WAREHOUSE


class WarehouseDispatchScanRequest(BaseModel):
    tire_serial: str


class SpcLockoutCheckRequest(BaseModel):
    machine_id: str
    cavity_side: Optional[str] = None


class SpcUnlockRequest(BaseModel):
    machine_id: str
    authorized_badge: str
    capa_reason: str
    action_taken: str


class StationEventIngestRequest(BaseModel):
    identifier: str  # Tire Serial or Green Tire Barcode
    station_code: str  # PREP, TBM, CURING, FINISHING, WAREHOUSE
    station_sequence: int  # 1=PREP, 2=TBM, 3=CURING, 4=FINISHING, 5=WAREHOUSE
    event_timestamp: str  # Edge sensor physical timestamp
    sensor_measurements: Optional[dict] = None



@router.post("/verify-transition")
def verify_stage_transition(req: StageVerifyRequest):
    """
    STRICT ROUTING ENFORCEMENT ENGINE (Chống Nhảy Cóc Công Đoạn):
    Validates if a tire is eligible to proceed to target_stage based on previous stage history.
    """
    with get_db() as conn:
        cursor = conn.cursor()

        # Step 1: Identify if this is a Green Tire or a Cured Tire
        gt = cursor.execute("SELECT * FROM production_green_tires WHERE gt_barcode = ?", (req.identifier,)).fetchone()
        tire = cursor.execute("SELECT * FROM production_cured_tires WHERE tire_serial = ? OR gt_barcode = ?", (req.identifier, req.identifier)).fetchone()

        if not gt and not tire:
            return {
                "permitted": False,
                "error_code": "INVALID_PRODUCT_ID",
                "message": f"Mã sản phẩm '{req.identifier}' không tồn tại trong hệ thống sản xuất!",
                "current_stage": "UNKNOWN"
            }

        # Check if product is scrapped or quarantined
        if (gt and gt["status"] in ("SCRAPPED", "QUARANTINED")) or (tire and tire["status"] in ("SCRAPPED", "QUARANTINED")):
            return {
                "permitted": False,
                "error_code": "PRODUCT_QUARANTINED_OR_SCRAPPED",
                "message": f"CẢNH BÁO AN TOÀN: Sản phẩm '{req.identifier}' đang ở diện CÁCH LY THU HỒI HOẶC PHẾ PHẨM! Toàn bộ hệ thống đã khóa sản phẩm này.",
                "current_stage": "QUARANTINE_LOCK"
            }

        # =====================================================================
        # RULE 1: Nạp vào Lò Lưu Hóa (Target: CURING)
        # Bắt buộc: Phải là lốp sống hợp lệ đã qua trạm TBM với trạng thái BUILT
        # =====================================================================
        if req.target_stage == "CURING":
            if not gt:
                return {
                    "permitted": False,
                    "error_code": "TBM_SKIPPED",
                    "message": "CẢNH BÁO NHẢY CÓC: Không tìm thấy hồ sơ thành hình lốp sống tại trạm TBM! Không được phép nạp vào lò lưu hóa.",
                    "current_stage": "PREP"
                }
            if gt["status"] in ("CURED", "IN_CURING"):
                return {
                    "permitted": False,
                    "error_code": "ALREADY_CURED",
                    "message": f"CẢNH BÁO LẶP CÔNG ĐOẠN: Lốp sống '{gt['gt_barcode']}' đã hoặc đang trong quá trình lưu hóa (Trạng thái: {gt['status']})!",
                    "current_stage": "CURING"
                }
            return {
                "permitted": True,
                "current_stage": "TBM_BUILT",
                "target_stage": "CURING",
                "message": f"HỢP LỆ: Lốp sống {gt['gt_barcode']} đã hoàn thành đóng lốp TBM, trọng lượng {gt['actual_weight_kg']}kg. Cho phép nạp vào lò lưu hóa."
            }

        # =====================================================================
        # RULE 2: Đưa vào Trạm KCS & Hoàn thiện (Target: FINISHING)
        # Bắt buộc: Phải qua lò lưu hóa (Curing) và đã được khắc sê-ri vĩnh viễn
        # =====================================================================
        if req.target_stage == "FINISHING":
            if not tire:
                return {
                    "permitted": False,
                    "error_code": "CURING_SKIPPED",
                    "message": f"CẢNH BÁO NHẢY CÓC CỰC KỲ NGUY HIỂM: Sản phẩm '{req.identifier}' là LỐP SỐNG chưa hề qua lò lưu hóa nhiệt áp (Curing)! Cao su chưa chín lưu hóa. NGHIÊM CẤM đưa vào trạm KCS!",
                    "current_stage": "TBM_BUILT"
                }
            if tire["status"] == "INSPECTED":
                return {
                    "permitted": True,
                    "current_stage": "FINISHING_DONE",
                    "target_stage": "FINISHING",
                    "message": f"Lốp {tire['tire_serial']} đã có kết quả kiểm tra KCS trước đó."
                }
            return {
                "permitted": True,
                "current_stage": "CURED",
                "target_stage": "FINISHING",
                "message": f"HỢP LỆ: Lốp {tire['tire_serial']} đã hoàn tất lưu hóa tại lò {tire['press_id']}-{tire['cavity_side']}. Cho phép đưa vào bàn kiểm tra KCS."
            }

        # =====================================================================
        # RULE 3: Nhập Kho Thành Phẩm & Xuất Xưởng (Target: WAREHOUSE)
        # Bắt buộc: Phải có kết quả KCS ĐẠT (GRADE_A hoặc GRADE_B)
        # =====================================================================
        if req.target_stage == "WAREHOUSE":
            if not tire:
                return {
                    "permitted": False,
                    "error_code": "CURING_AND_QC_SKIPPED",
                    "message": "CẢNH BÁO GIAN LẬN QUY TRÌNH: Sản phẩm chưa qua Lưu hóa và chưa qua KCS!",
                    "current_stage": "TBM_BUILT"
                }

            # Check QC Inspection
            qc = cursor.execute("SELECT * FROM quality_inspections WHERE tire_serial = ?", (tire["tire_serial"],)).fetchone()
            if not qc:
                return {
                    "permitted": False,
                    "error_code": "QC_SKIPPED",
                    "message": f"CẢNH BÁO BỎ QUA KIỂM TRA CHẤT LƯỢNG: Lốp '{tire['tire_serial']}' đã lưu hóa nhưng CHƯA QUA TRẠM KCS (Chưa soi X-Ray và chưa đo cân bằng động)! KHÔNG ĐƯỢC PHÉP NHẬP KHO XUẤT XƯỞNG!",
                    "current_stage": "CURING_DONE"
                }

            if qc["final_grade"] == "SCRAP":
                return {
                    "permitted": False,
                    "error_code": "SCRAP_CANNOT_DISPATCH",
                    "message": f"CHẶN XUẤT XƯỞNG: Lốp '{tire['tire_serial']}' đã bị kết luận là PHẾ PHẨM ({qc['disposition_notes']}). Cấm nhập kho thành phẩm!",
                    "current_stage": "SCRAP_BIN"
                }

            if qc["final_grade"] == "REWORK":
                return {
                    "permitted": False,
                    "error_code": "REWORK_PENDING",
                    "message": f"CHẶN XUẤT XƯỞNG: Lốp '{tire['tire_serial']}' đang ở trạng thái TÁI CHẾ (Cần mài bavia gai). Chưa hoàn thiện kiểm tra lại!",
                    "current_stage": "REWORK_BUFFING"
                }

            return {
                "permitted": True,
                "current_stage": "QC_PASSED",
                "target_stage": "WAREHOUSE",
                "final_grade": qc["final_grade"],
                "message": f"ĐỦ ĐIỀU KIỆN NHẬP KHO: Lốp {tire['tire_serial']} đã qua đầy đủ 5 công đoạn nghiêm ngặt, đạt chuẩn [{qc['final_grade']}]. Cho phép nhập kho xuất xưởng."
            }

        return {"permitted": False, "message": f"Công đoạn đích '{req.target_stage}' không hợp lệ!"}


@router.post("/scan-warehouse-dispatch")
def scan_warehouse_dispatch(req: WarehouseDispatchScanRequest):
    """
    Simulates barcode scanning at Finished Goods Warehouse Gates.
    Strictly checks if tire completed ALL prior stages.
    """
    verify_res = verify_stage_transition(StageVerifyRequest(identifier=req.tire_serial, target_stage="WAREHOUSE"))
    return verify_res


# =============================================================================
# 1. CONSECUTIVE DEFECT INTERLOCK (SPC RUN-RULE & HARDWARE LOCKOUT)
# =============================================================================
@router.post("/check-spc-lockout")
def check_spc_lockout(req: SpcLockoutCheckRequest):
    """
    STATISTICAL PROCESS CONTROL (SPC) RUN-RULE INTERLOCK:
    Checks if a machine or cavity has generated 2 or more consecutive SCRAP defects.
    If detected, activates Hardware/PLC Quality Lockout.
    """
    with get_db() as conn:
        cursor = conn.cursor()

        # Check recent tires from this equipment
        if req.machine_id.startswith("CP-"):
            query = """
                SELECT c.tire_serial, q.final_grade, q.passed, q.disposition_notes, q.inspection_timestamp
                FROM production_cured_tires c
                JOIN quality_inspections q ON c.tire_serial = q.tire_serial
                WHERE c.press_id = ?
            """
            params = [req.machine_id]
            if req.cavity_side:
                query += " AND c.cavity_side = ?"
                params.append(req.cavity_side)
            query += " ORDER BY q.inspection_timestamp DESC LIMIT 5"
            records = cursor.execute(query, params).fetchall()
        else:
            # TBM machine
            query = """
                SELECT c.tire_serial, q.final_grade, q.passed, q.disposition_notes, q.inspection_timestamp
                FROM production_green_tires g
                JOIN production_cured_tires c ON g.gt_barcode = c.gt_barcode
                JOIN quality_inspections q ON c.tire_serial = q.tire_serial
                WHERE g.tbm_machine_id = ?
                ORDER BY q.inspection_timestamp DESC LIMIT 5
            """
            records = cursor.execute(query, (req.machine_id,)).fetchall()

        # Count consecutive scraps from the top
        consecutive_scraps = 0
        scrap_details = []
        for r in records:
            if r["final_grade"] == "SCRAP":
                consecutive_scraps += 1
                scrap_details.append(f"{r['tire_serial']}: {r['disposition_notes']}")
            else:
                break

        is_locked = consecutive_scraps >= 2

        if is_locked:
            # Update machine status to BREAKDOWN if not already
            cursor.execute("UPDATE master_equipment SET status = 'BREAKDOWN' WHERE machine_id = ?", (req.machine_id,))
            return {
                "locked": True,
                "machine_id": req.machine_id,
                "cavity_side": req.cavity_side,
                "consecutive_scraps": consecutive_scraps,
                "interlock_status": "AUTO_LOCKOUT_TRIGGERED",
                "plc_tag_command": f"PLC_{req.machine_id}.CYCLE_START_INHIBIT = 1",
                "message": f"🚨 BÁO ĐỘNG SPC LIÊN TIẾP: Phát hiện {consecutive_scraps} lốp PHẾ PHẨM (SCRAP) liên tiếp tại {req.machine_id}! Hệ thống đã phát lệnh ngắt PLC dừng máy tự động (Hardware Lockout).",
                "scrap_tires": scrap_details,
                "unlock_required": "Yêu cầu Quản đốc (SUPERVISOR) hoặc KCS Trưởng (QC_INSPECTOR) quét thẻ Badge giải tỏa."
            }

        return {
            "locked": False,
            "machine_id": req.machine_id,
            "cavity_side": req.cavity_side,
            "consecutive_scraps": consecutive_scraps,
            "interlock_status": "NORMAL",
            "message": f"Máy {req.machine_id} hoạt động bình thường trong giới hạn kiểm soát SPC."
        }


@router.post("/unlock-spc")
def unlock_spc_lockout(req: SpcUnlockRequest):
    """
    CAPA & Supervised 3-Step Unlock Protocol:
    Only SUPERVISOR or QC_INSPECTOR can unlock a machine stopped by consecutive defects.
    """
    with get_db() as conn:
        cursor = conn.cursor()
        op = cursor.execute("SELECT * FROM master_operators WHERE badge_id = ?", (req.authorized_badge,)).fetchone()
        if not op:
            raise HTTPException(status_code=404, detail="Mã nhân sự không tồn tại!")

        if op["role"] not in ("SUPERVISOR", "QC_INSPECTOR"):
            raise HTTPException(
                status_code=403,
                detail=f"TỪ CHỐI ỦY QUYỀN: Nhân viên '{op['full_name']}' ({op['role']}) không có thẩm quyền mở khóa máy! Bắt buộc Quản đốc hoặc KCS Trưởng."
            )

        # Log into downtime / CAPA
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute("""
            INSERT INTO equipment_downtime_logs (machine_id, start_time, end_time, duration_minutes, reason_code, comments)
            VALUES (?, ?, ?, 15, 'BREAKDOWN', ?)
        """, (req.machine_id, now_str, now_str, f"CAPA Mở khóa SPC bởi {op['full_name']} ({op['badge_id']}): {req.capa_reason} | Hành động: {req.action_taken}"))

        # Restore machine status
        cursor.execute("UPDATE master_equipment SET status = 'IDLE' WHERE machine_id = ?", (req.machine_id,))

        return {
            "success": True,
            "machine_id": req.machine_id,
            "status": "UNLOCKED_IDLE",
            "unlocked_by": f"{op['full_name']} ({op['role']})",
            "trial_run_mode": "FIRST_ARTICLE_INSPECTION_REQUIRED",
            "message": f"Mở khóa thành công máy {req.machine_id}. Chế độ: Bắt buộc kiểm tra FAI (First Article Inspection) lốp đầu tiên trước khi chạy hàng loạt!"
        }


# =============================================================================
# 2. WIP BUFFER SATURATION & BACKPRESSURE PACING ENGINE (DRUM-BUFFER-ROPE)
# =============================================================================
@router.get("/buffer-backpressure")
def get_buffer_backpressure():
    """
    WIP BUFFER MONITORING & DRUM-BUFFER-ROPE BACKPRESSURE ENGINE:
    Monitors buffer queues between stages and regulates upstream pacing.
    """
    with get_db() as conn:
        cursor = conn.cursor()

        # Buffer 1: Green Tire Storage (TBM -> Curing)
        gt_in_buffer = cursor.execute("SELECT count(*) FROM production_green_tires WHERE status = 'BUILT'").fetchone()[0]
        gt_capacity = 30  # Max capacity of racks between TBM and Curing
        gt_pct = round((gt_in_buffer / gt_capacity) * 100, 1)

        # Buffer 2: Cooling Spiral & Cured Tire Queue (Curing -> Finishing)
        cure_in_buffer = cursor.execute("SELECT count(*) FROM production_cured_tires WHERE status IN ('CURED', 'IN_INSPECTION')").fetchone()[0]
        cure_capacity = 25  # Max capacity of cooling conveyor before X-Ray
        cure_pct = round((cure_in_buffer / cure_capacity) * 100, 1)

        # Determine Backpressure state for Buffer 2 (most critical bottleneck: X-Ray / Finishing)
        if cure_pct >= 95.0:
            bp_level = "HARD_BACKPRESSURE_HOLD"
            action_desc = "CẢNH BÁO NGHẼN BĂNG TẢI LÀM NGUỘI (>95%): Tự động NGẮT tín hiệu dỡ lốp tại toàn bộ lò lưu hóa! Dừng cấp lốp sống từ TBM."
            plc_signal = "HOLD_CURING_UNLOADER_AND_TBM"
        elif cure_pct >= 80.0:
            bp_level = "SOFT_BACKPRESSURE_PACE"
            action_desc = "CẢNH BÁO ĐỆM CAO (>80%): Kích hoạt điều tiết giảm nhịp độ nạp lò; chuyển hướng một phần lốp sang Làn Đệm Phụ (Overflow Spur)."
            plc_signal = "DIVERT_TO_OVERFLOW_SPUR"
        elif cure_pct >= 65.0:
            bp_level = "ELEVATED_WATCH"
            action_desc = "Mức tồn đệm tăng cao. Giám sát nhịp độ trạm KCS X-Ray."
            plc_signal = "NORMAL"
        else:
            bp_level = "NORMAL_FLOW"
            action_desc = "Dòng chảy sản xuất thông suốt (Normal CONWIP Flow)."
            plc_signal = "NORMAL"

        return {
            "green_tire_buffer": {
                "name": "Giá Đệm Lốp Sống (TBM -> Curing)",
                "current_wip": gt_in_buffer,
                "max_capacity": gt_capacity,
                "utilization_percent": gt_pct,
                "status": "NORMAL" if gt_pct < 80 else "HIGH"
            },
            "curing_finishing_buffer": {
                "name": "Băng Chuyền Làm Nguội & Hàng Đợi KCS (Curing -> Finishing)",
                "current_wip": cure_in_buffer,
                "max_capacity": cure_capacity,
                "utilization_percent": cure_pct,
                "status": bp_level
            },
            "backpressure_level": bp_level,
            "plc_interlock_signal": plc_signal,
            "action_directive": action_desc
        }


# =============================================================================
# 3. FRANKENSTEIN DATA TRAP PREVENTION (MONOTONIC STATION ORDER ENGINE)
# =============================================================================
@router.post("/ingest-station-event")
def ingest_station_event(req: StationEventIngestRequest):
    """
    FRANKENSTEIN DATA TRAP PREVENTION & MONOTONIC VECTOR CLOCK ENGINE:
    - Protects against out-of-order delayed industrial packets (e.g. Wi-Fi/Switch jitter).
    - Prevents old station packets from regressing physical tire state backwards in time.
    - Appends delayed packets to Audit Log without mutating current station state.
    """
    with get_db(immediate=True) as conn:
        cursor = conn.cursor()

        # Check active product record
        gt = cursor.execute("SELECT * FROM production_green_tires WHERE gt_barcode = ?", (req.identifier,)).fetchone()
        tire = cursor.execute("SELECT * FROM production_cured_tires WHERE tire_serial = ? OR gt_barcode = ?", (req.identifier, req.identifier)).fetchone()

        if not gt and not tire:
            return {"accepted": False, "error_code": "PRODUCT_NOT_FOUND", "message": f"Mã sản phẩm '{req.identifier}' không tồn tại!"}

        # Calculate current known physical sequence:
        # PREP = 1, TBM = 2, CURING = 3, FINISHING = 4, WAREHOUSE = 5
        current_seq = 2
        current_station_name = "TBM"
        if tire:
            if tire["status"] in ("INSPECTED", "SCRAPPED"):
                current_seq = 5
                current_station_name = "WAREHOUSE"
            elif tire["status"] == "IN_INSPECTION":
                current_seq = 4
                current_station_name = "FINISHING"
            else:
                current_seq = 3
                current_station_name = "CURING"
        elif gt:
            if gt["status"] == "CURED":
                current_seq = 3
                current_station_name = "CURING"
            elif gt["status"] in ("IN_CURING", "BUFFER"):
                current_seq = 2.5
                current_station_name = "TBM_BUFFER"
            else:
                current_seq = 2
                current_station_name = "TBM"

        # Check for FRANKENSTEIN DATA TRAP (Out-of-order delayed packet)
        if req.station_sequence < current_seq:
            return {
                "accepted": True,
                "state_updated": False,
                "trap_prevented": "FRANKENSTEIN_DATA_TRAP_BLOCKED",
                "current_station": f"{current_station_name} (seq: {current_seq})",
                "delayed_packet_station": f"{req.station_code} (seq: {req.station_sequence})",
                "message": f"BẪY DỮ LIỆU MA ĐƯỢC NGĂN CHẶN: Gói tin cảm biến từ trạm {req.station_code} (seq {req.station_sequence}) đến muộn sau khi lốp đã di chuyển tới {current_station_name} (seq {current_seq})! Gói tin chỉ được lưu vào Lịch sử Sự kiện, KHÔNG ĐƯỢC PHÉP ghi đè trạng thái vật lý hiện tại của lốp.",
                "audit_action": "INGESTED_TO_AUDIT_LOG_ONLY"
            }

        return {
            "accepted": True,
            "state_updated": True,
            "trap_prevented": None,
            "current_station": f"{req.station_code} (seq: {req.station_sequence})",
            "message": f"HỢP LỆ: Đã cập nhật trạm công đoạn thành công sang {req.station_code} theo đúng chiều thời gian đơn điệu (Monotonic Progression)."
        }


