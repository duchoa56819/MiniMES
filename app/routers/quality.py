"""
Quality Inspection Router - Station 3: Finishing & Quality Gate (KCS & Kiểm tra hoàn thiện).
Visual, X-Ray, and Uniformity (RFV/LFV/Balance) inspection with automated grading rules.
"""

from datetime import datetime
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.database import get_db
from app.models import QualityInspectionRequest

router = APIRouter(prefix="/api/quality", tags=["Quality Inspection"])


class ReworkActionRequest(BaseModel):
    tire_serial: str
    operator_id: str
    action_type: str  # TRIM_VENT_SPEW, BALANCE_BUFFING, BEAD_TOUCHUP
    notes: str = ""



@router.get("/queue")
def get_inspection_queue():
    """Lists cured tires waiting in the inspection queue."""
    with get_db() as conn:
        cursor = conn.cursor()
        rows = cursor.execute("""
            SELECT c.*, p.tire_size, p.pattern_name, p.segment,
                   gt.build_timestamp, gt.tbm_machine_id
            FROM production_cured_tires c
            JOIN master_products p ON c.sku = p.sku
            JOIN production_green_tires gt ON c.gt_barcode = gt.gt_barcode
            WHERE c.status IN ('CURED', 'IN_INSPECTION')
            ORDER BY c.cure_end_time DESC
        """).fetchall()
        return [dict(r) for r in rows]


@router.get("/defects-catalog")
def get_defects_catalog():
    """Returns the standardized tire defect catalog."""
    with get_db() as conn:
        cursor = conn.cursor()
        rows = cursor.execute("SELECT * FROM master_defect_codes ORDER BY defect_code ASC").fetchall()
        return [dict(r) for r in rows]


@router.post("/inspect")
def inspect_tire(req: QualityInspectionRequest):
    """
    Submits full quality inspection record and applies automated grading logic:
    - Critical defect / Belt crossing / Under-cure -> SCRAP
    - Major defect / RFV > 75N -> GRADE_B
    - Minor defect (excess flash) -> REWORK
    - Flawless & within OE specs -> GRADE_A
    """
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with get_db() as conn:
        cursor = conn.cursor()

        # Check tire
        tire = cursor.execute("SELECT * FROM production_cured_tires WHERE tire_serial = ?", (req.tire_serial,)).fetchone()
        if not tire:
            raise HTTPException(status_code=404, detail="Không tìm thấy sê-ri lốp!")

        # Automated Grading Decision Tree
        final_grade = "GRADE_A"
        passed = 1
        disposition_reason = []

        # 1. Visual Defect Check
        if req.visual_result == "FAIL" and req.visual_defect_code:
            v_def = cursor.execute("SELECT * FROM master_defect_codes WHERE defect_code = ?", (req.visual_defect_code,)).fetchone()
            if v_def:
                disposition_reason.append(f"Ngoại quan: {v_def['defect_name_vi']}")
                if v_def["severity"] == "CRITICAL" or v_def["default_disposition"] == "SCRAP":
                    final_grade = "SCRAP"
                    passed = 0
                elif v_def["default_disposition"] == "GRADE_B" and final_grade != "SCRAP":
                    final_grade = "GRADE_B"
                elif v_def["default_disposition"] == "REWORK" and final_grade == "GRADE_A":
                    final_grade = "REWORK"

        # 2. X-Ray Defect Check
        if req.xray_result == "FAIL" and req.xray_defect_code:
            x_def = cursor.execute("SELECT * FROM master_defect_codes WHERE defect_code = ?", (req.xray_defect_code,)).fetchone()
            if x_def:
                disposition_reason.append(f"X-Ray: {x_def['defect_name_vi']}")
                if x_def["severity"] == "CRITICAL" or x_def["default_disposition"] == "SCRAP":
                    final_grade = "SCRAP"
                    passed = 0
                elif x_def["default_disposition"] == "GRADE_B" and final_grade != "SCRAP":
                    final_grade = "GRADE_B"

        # 3. Uniformity & Balance Threshold Check (RFV > 80N or Balance > 35g)
        if final_grade not in ("SCRAP", "GRADE_B"):
            if req.uniformity_rfv_n > 80.0:
                final_grade = "GRADE_B"
                disposition_reason.append(f"Lực RFV ({req.uniformity_rfv_n} N) vượt ngưỡng OE (< 80 N)")
            elif req.dynamic_balance_g > 35.0:
                final_grade = "REWORK"
                disposition_reason.append(f"Cân bằng động ({req.dynamic_balance_g} g) cần cân mài lại")

        if final_grade == "GRADE_A":
            disposition_reason.append("Đạt tiêu chuẩn chất lượng Hạng A (OE First Class). Cho phép dán nhãn xuất khẩu.")

        notes = req.disposition_notes or " | ".join(disposition_reason)

        # Check existing inspection or insert
        existing = cursor.execute("SELECT 1 FROM quality_inspections WHERE tire_serial = ?", (req.tire_serial,)).fetchone()
        if existing:
            cursor.execute("""
                UPDATE quality_inspections
                SET inspection_timestamp = ?, inspector_id = ?,
                    visual_result = ?, visual_defect_code = ?, defect_location = ?,
                    xray_result = ?, xray_defect_code = ?, belt_alignment_mm = ?,
                    uniformity_rfv_n = ?, uniformity_lfv_n = ?, dynamic_balance_g = ?,
                    final_grade = ?, passed = ?, disposition_notes = ?
                WHERE tire_serial = ?
            """, (
                now_str, req.inspector_id, req.visual_result, req.visual_defect_code, req.defect_location,
                req.xray_result, req.xray_defect_code, req.belt_alignment_mm,
                req.uniformity_rfv_n, req.uniformity_lfv_n, req.dynamic_balance_g,
                final_grade, passed, notes, req.tire_serial
            ))
        else:
            cursor.execute("""
                INSERT INTO quality_inspections (
                    tire_serial, inspection_timestamp, inspector_id,
                    visual_result, visual_defect_code, defect_location,
                    xray_result, xray_defect_code, belt_alignment_mm,
                    uniformity_rfv_n, uniformity_lfv_n, dynamic_balance_g,
                    final_grade, passed, disposition_notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                req.tire_serial, now_str, req.inspector_id,
                req.visual_result, req.visual_defect_code, req.defect_location,
                req.xray_result, req.xray_defect_code, req.belt_alignment_mm,
                req.uniformity_rfv_n, req.uniformity_lfv_n, req.dynamic_balance_g,
                final_grade, passed, notes
            ))

        # Update tire status
        tire_new_status = "SCRAPPED" if final_grade == "SCRAP" else "INSPECTED"
        cursor.execute("UPDATE production_cured_tires SET status = ? WHERE tire_serial = ?", (tire_new_status, req.tire_serial))

        # If SCRAP, also update Green Tire and increment WO scrap qty
        if final_grade == "SCRAP":
            cursor.execute("UPDATE production_green_tires SET status = 'SCRAPPED' WHERE gt_barcode = ?", (tire["gt_barcode"],))
            # Find work order
            gt = cursor.execute("SELECT wo_id FROM production_green_tires WHERE gt_barcode = ?", (tire["gt_barcode"],)).fetchone()
            if gt:
                cursor.execute("UPDATE work_orders SET scrap_qty = scrap_qty + 1 WHERE wo_id = ?", (gt["wo_id"],))

        return {
            "success": True,
            "tire_serial": req.tire_serial,
            "final_grade": final_grade,
            "passed": bool(passed),
            "disposition_notes": notes,
            "message": f"Kiểm tra hoàn tất: Cấp phân loại [{final_grade}]!"
        }


@router.get("/history")
def get_inspection_history(limit: int = 50):
    """Returns recent quality inspection records with full defect names."""
    with get_db() as conn:
        cursor = conn.cursor()
        rows = cursor.execute("""
            SELECT q.*, c.sku, p.tire_size, p.pattern_name, o.full_name as inspector_name,
                   dv.defect_name_vi as visual_defect_name,
                   dx.defect_name_vi as xray_defect_name
            FROM quality_inspections q
            JOIN production_cured_tires c ON q.tire_serial = c.tire_serial
            JOIN master_products p ON c.sku = p.sku
            LEFT JOIN master_operators o ON q.inspector_id = o.badge_id
            LEFT JOIN master_defect_codes dv ON q.visual_defect_code = dv.defect_code
            LEFT JOIN master_defect_codes dx ON q.xray_defect_code = dx.defect_code
            ORDER BY q.inspection_timestamp DESC LIMIT ?
        """, (limit,)).fetchall()
        return [dict(r) for r in rows]


@router.post("/rework-action")
def execute_rework_action(req: ReworkActionRequest):
    """
    IATF 16949 REWORK CONTROL & ANTI-INFINITE-LOOP INTERLOCK:
    - Enforces maximum 2 rework attempts per tire.
    - Prevents excessive buffing/grinding that weakens tire structure.
    - Preserves genealogy audit trail in tire_rework_history.
    """
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with get_db() as conn:
        cursor = conn.cursor()

        # Check tire and inspection status
        qc = cursor.execute("SELECT * FROM quality_inspections WHERE tire_serial = ?", (req.tire_serial,)).fetchone()
        if not qc:
            raise HTTPException(status_code=404, detail="Không tìm thấy phiếu kiểm định KCS của lốp này!")

        if qc["final_grade"] != "REWORK":
            raise HTTPException(
                status_code=400,
                detail=f"Lốp '{req.tire_serial}' không ở trạng thái REWORK (Trạng thái hiện tại: {qc['final_grade']})!"
            )

        # Check existing rework count
        existing_reworks = cursor.execute(
            "SELECT count(*) FROM tire_rework_history WHERE tire_serial = ?", (req.tire_serial,)
        ).fetchone()[0]

        if existing_reworks >= 2:
            # FORCE SCRAP - IATF 16949 Section 8.7 Violation Prevention
            cursor.execute("""
                UPDATE quality_inspections
                SET final_grade = 'SCRAP', passed = 0,
                    disposition_notes = 'CƯỠNG CHẾ HỦY PHẾ PHẨM: Đã vượt quá giới hạn 2 lần sửa chữa cho phép theo tiêu chuẩn IATF 16949! Nguy cơ mỏng cao su mặt lốp.'
                WHERE tire_serial = ?
            """, (req.tire_serial,))
            cursor.execute("UPDATE production_cured_tires SET status = 'SCRAPPED' WHERE tire_serial = ?", (req.tire_serial,))

            return {
                "success": False,
                "tire_serial": req.tire_serial,
                "rework_count": existing_reworks + 1,
                "final_grade": "SCRAP",
                "interlock_code": "REWORK_LIMIT_EXCEEDED",
                "message": "CƯỠNG CHẾ HỦY PHẾ PHẨM (SCRAP): Chiếc lốp này đã sửa 2 lần nhưng vẫn không đạt. Cấm sửa tiếp để tránh mỏng cao su nguy hiểm!"
            }

        # Valid rework attempt (Count 1 or 2)
        new_count = existing_reworks + 1
        cursor.execute("""
            INSERT INTO tire_rework_history (
                tire_serial, rework_count, rework_timestamp, operator_id,
                action_type, action_description, pre_rework_grade, post_rework_status
            ) VALUES (?, ?, ?, ?, ?, ?, 'REWORK', 'READY_FOR_REINSPECTION')
        """, (req.tire_serial, new_count, now_str, req.operator_id, req.action_type, req.notes))

        # Reset tire status to IN_INSPECTION so it re-enters KCS queue
        cursor.execute("UPDATE production_cured_tires SET status = 'IN_INSPECTION' WHERE tire_serial = ?", (req.tire_serial,))

        return {
            "success": True,
            "tire_serial": req.tire_serial,
            "rework_count": new_count,
            "final_grade": "REWORK_COMPLETED",
            "next_stage": "RE_INSPECTION_GATE",
            "message": f"Sửa hàng lần {new_count}/2 hoàn tất ({req.action_type}). Lốp được chuyển lại hàng đợi KCS để tái kiểm định."
        }

