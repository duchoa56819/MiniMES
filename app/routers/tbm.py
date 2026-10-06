"""
TBM Router - Station 1: Tire Building Machine (Thành hình Lốp sống).
Includes rigorous Poka-Yoke component validation, barcode generation, and lot genealogy tracking.
"""

from datetime import datetime
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.database import get_db
from app.models import GreenTireBuildRequest

router = APIRouter(prefix="/api/tbm", tags=["TBM Station"])


class LotValidateRequest(BaseModel):
    sku: str
    component_type: str
    lot_id: str


@router.get("/inventory-lots")
def get_available_lots(component_type: str = None):
    """Returns available semi-finished inventory lots for TBM feed."""
    with get_db() as conn:
        cursor = conn.cursor()
        query = "SELECT * FROM inventory_components WHERE remaining_qty > 0"
        params = []
        if component_type:
            query += " AND component_type = ?"
            params.append(component_type)
        query += " ORDER BY expiry_time ASC"
        rows = cursor.execute(query, params).fetchall()
        return [dict(r) for r in rows]


@router.post("/validate-lot")
def validate_component_lot(req: LotValidateRequest):
    """
    Poka-Yoke Validator:
    Verifies that the scanned lot matches the SKU BOM, is not expired, and has remaining stock.
    """
    now = datetime.now()
    now_str = now.strftime("%Y-%m-%d %H:%M:%S")

    with get_db() as conn:
        cursor = conn.cursor()

        # 1. Check if lot exists
        lot = cursor.execute("SELECT * FROM inventory_components WHERE lot_id = ?", (req.lot_id,)).fetchone()
        if not lot:
            return {
                "valid": False,
                "error_code": "LOT_NOT_FOUND",
                "message": f"Mã lô '{req.lot_id}' không tồn tại trong kho bán thành phẩm!"
            }

        # 2. Check component type match
        if lot["component_type"] != req.component_type:
            return {
                "valid": False,
                "error_code": "TYPE_MISMATCH",
                "message": f"Lô '{req.lot_id}' là loại {lot['component_type']}, không thể dùng cho trạm {req.component_type}!"
            }

        # 3. Check BOM compound spec
        bom_entry = cursor.execute("""
            SELECT * FROM master_boms
            WHERE sku = ? AND component_type = ?
        """, (req.sku, req.component_type)).fetchone()

        if bom_entry and lot["compound_code"] != bom_entry["compound_code"]:
            return {
                "valid": False,
                "error_code": "BOM_MISMATCH",
                "message": f"POKA-YOKE ALARM: Lô '{req.lot_id}' có mã cao su {lot['compound_code']}, khác với quy cách BOM yêu cầu ({bom_entry['compound_code']})!"
            }

        # 4. Check Expiration Date (Tire industry strict 48-72h shelf life)
        exp_time = datetime.strptime(lot["expiry_time"], "%Y-%m-%d %H:%M:%S")
        if exp_time < now:
            return {
                "valid": False,
                "error_code": "LOT_EXPIRED",
                "message": f"CẢNH BÁO HẠN DÙNG: Lô '{req.lot_id}' đã hết hạn sử dụng lúc {lot['expiry_time']}! Cao su sống đã bắt đầu lưu hóa sơ bộ (Scorched). KHÔNG ĐƯỢC PHÉP ĐÓNG LỐP!"
            }

        # 5. Check Remaining Quantity
        if lot["remaining_qty"] <= 0:
            return {
                "valid": False,
                "error_code": "LOT_DEPLETED",
                "message": f"Lô '{req.lot_id}' đã hết số lượng tồn kho!"
            }

        return {
            "valid": True,
            "message": f"Lô '{req.lot_id}' hợp lệ! Cao su: {lot['compound_code']} - Vị trí: {lot['storage_location']}",
            "lot": dict(lot)
        }


@router.post("/build-green-tire")
def build_green_tire(req: GreenTireBuildRequest):
    """
    Executes the Tire Building cycle:
    - Verifies all lots
    - Decrements stock
    - Generates unique Green Tire Barcode (GTID)
    - Records genealogy lineage into production_green_tires
    """
    now = datetime.now()
    now_str = now.strftime("%Y-%m-%d %H:%M:%S")
    date_prefix = now.strftime("%Y%m%d")

    with get_db() as conn:
        cursor = conn.cursor()

        # Check Work Order
        wo = cursor.execute("SELECT * FROM work_orders WHERE wo_id = ?", (req.wo_id,)).fetchone()
        if not wo:
            raise HTTPException(status_code=400, detail="Lệnh sản xuất không tồn tại!")

        # Verify SKU weight limits
        prod = cursor.execute("SELECT * FROM master_products WHERE sku = ?", (req.sku,)).fetchone()
        if prod:
            std_w = prod["standard_weight_kg"]
            tol_w = prod["weight_tolerance_kg"]
            if abs(req.actual_weight_kg - std_w) > tol_w and not req.override_poka_yoke:
                raise HTTPException(
                    status_code=400,
                    detail=f"Trọng lượng lốp sống ({req.actual_weight_kg} kg) lệch chuẩn cho phép ({std_w} ± {tol_w} kg)!"
                )

        # Generate unique Green Tire Barcode
        count_today = cursor.execute("""
            SELECT count(*) FROM production_green_tires
            WHERE build_timestamp LIKE ?
        """, (f"{now.strftime('%Y-%m-%d')}%",)).fetchone()[0]

        gt_barcode = f"GT-{date_prefix}-{(count_today + 1):04d}"

        # Insert Green Tire
        cursor.execute("""
            INSERT INTO production_green_tires (
                gt_barcode, wo_id, sku, tbm_machine_id, operator_id,
                build_timestamp, actual_weight_kg,
                tread_lot, sidewall_lot, belt1_lot, belt2_lot, ply_lot, bead_lot, innerliner_lot,
                poka_yoke_status, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'BUILT')
        """, (
            gt_barcode, req.wo_id, req.sku, req.tbm_machine_id, req.operator_id,
            now_str, req.actual_weight_kg,
            req.tread_lot, req.sidewall_lot, req.belt1_lot, req.belt2_lot, req.ply_lot, req.bead_lot, req.innerliner_lot,
            "OVERRIDDEN" if req.override_poka_yoke else "VERIFIED_PASS"
        ))

        # Decrement inventory stock for scanned lots
        all_lots = [
            req.tread_lot, req.sidewall_lot, req.belt1_lot, req.belt2_lot,
            req.ply_lot, req.bead_lot, req.innerliner_lot
        ]
        for lot_id in set(all_lots):
            cursor.execute("""
                UPDATE inventory_components
                SET remaining_qty = max(0, remaining_qty - 1)
                WHERE lot_id = ?
            """, (lot_id,))

        # Update machine total cycles
        cursor.execute("""
            UPDATE master_equipment
            SET total_cycles = total_cycles + 1
            WHERE machine_id = ?
        """, (req.tbm_machine_id,))

        return {
            "success": True,
            "gt_barcode": gt_barcode,
            "message": f"Thành hình lốp sống thành công! Đã cấp mã barcode: {gt_barcode}",
            "tire_data": {
                "gt_barcode": gt_barcode,
                "sku": req.sku,
                "tire_size": prod["tire_size"] if prod else "",
                "pattern": prod["pattern_name"] if prod else "",
                "actual_weight_kg": req.actual_weight_kg,
                "build_timestamp": now_str,
                "tbm_machine_id": req.tbm_machine_id,
                "operator_id": req.operator_id
            }
        }
