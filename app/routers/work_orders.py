"""
Work Orders Router - Production Scheduling, Dispatching & Tracking.
"""

from datetime import datetime
from fastapi import APIRouter, HTTPException
from app.database import get_db
from app.models import WorkOrderCreate, WorkOrderStatusUpdate

router = APIRouter(prefix="/api/work-orders", tags=["Work Orders"])


@router.get("")
def list_work_orders(status: str = None):
    """Lists work orders with calculated completion rates and product details."""
    with get_db() as conn:
        cursor = conn.cursor()
        query = """
            SELECT w.*, p.tire_size, p.pattern_name, p.segment
            FROM work_orders w
            JOIN master_products p ON w.sku = p.sku
        """
        params = []
        if status:
            query += " WHERE w.status = ?"
            params.append(status)
        query += " ORDER BY w.created_at DESC"

        rows = cursor.execute(query, params).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            target = d["target_qty"]
            completed = d["completed_qty"]
            scrap = d["scrap_qty"]
            d["progress_percent"] = round((completed / target * 100), 1) if target > 0 else 0.0
            d["scrap_percent"] = round((scrap / target * 100), 1) if target > 0 else 0.0
            result.append(d)
        return result


@router.post("")
def create_work_order(wo: WorkOrderCreate):
    """Creates a new production work order."""
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with get_db() as conn:
        cursor = conn.cursor()

        # Check if SKU exists
        sku_exists = cursor.execute("SELECT 1 FROM master_products WHERE sku = ?", (wo.sku,)).fetchone()
        if not sku_exists:
            raise HTTPException(status_code=400, detail=f"Mã sản phẩm (SKU) '{wo.sku}' không tồn tại trong hệ thống!")

        # Check if WO ID is duplicate
        dup = cursor.execute("SELECT 1 FROM work_orders WHERE wo_id = ?", (wo.wo_id,)).fetchone()
        if dup:
            raise HTTPException(status_code=400, detail=f"Lệnh sản xuất '{wo.wo_id}' đã tồn tại!")

        cursor.execute("""
            INSERT INTO work_orders (wo_id, sku, target_qty, planned_start, planned_end, priority, assigned_machine, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'RELEASED', ?)
        """, (wo.wo_id, wo.sku, wo.target_qty, wo.planned_start, wo.planned_end, wo.priority, wo.assigned_machine, now_str))

        return {"message": f"Tạo lệnh sản xuất {wo.wo_id} thành công!", "wo_id": wo.wo_id}


@router.get("/{wo_id}")
def get_work_order_detail(wo_id: str):
    """Fetches full details of a specific work order including BOM specs."""
    with get_db() as conn:
        cursor = conn.cursor()
        wo = cursor.execute("""
            SELECT w.*, p.tire_size, p.pattern_name, p.segment, p.standard_weight_kg, p.std_tbm_time_sec, p.std_cure_time_sec
            FROM work_orders w
            JOIN master_products p ON w.sku = p.sku
            WHERE w.wo_id = ?
        """, (wo_id,)).fetchone()

        if not wo:
            raise HTTPException(status_code=404, detail="Không tìm thấy Lệnh sản xuất!")

        # Fetch BOM for this SKU
        boms = cursor.execute("""
            SELECT component_type, spec_code, compound_code, standard_qty, unit
            FROM master_boms
            WHERE sku = ?
        """, (wo["sku"],)).fetchall()

        # Fetch Curing Recipe
        recipe = cursor.execute("""
            SELECT * FROM master_curing_recipes WHERE sku = ?
        """, (wo["sku"],)).fetchone()

        d = dict(wo)
        d["bom_items"] = [dict(b) for b in boms]
        d["curing_recipe"] = dict(recipe) if recipe else None
        return d


@router.put("/{wo_id}/status")
def update_work_order_status(wo_id: str, payload: WorkOrderStatusUpdate):
    """Updates status of a work order (e.g., RELEASED -> IN_PROGRESS -> COMPLETED)."""
    with get_db() as conn:
        cursor = conn.cursor()
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        wo = cursor.execute("SELECT * FROM work_orders WHERE wo_id = ?", (wo_id,)).fetchone()
        if not wo:
            raise HTTPException(status_code=404, detail="Không tìm thấy Lệnh sản xuất!")

        actual_start = wo["actual_start"]
        actual_end = wo["actual_end"]

        if payload.status == "IN_PROGRESS" and not actual_start:
            actual_start = now_str
        elif payload.status == "COMPLETED" and not actual_end:
            actual_end = now_str

        cursor.execute("""
            UPDATE work_orders
            SET status = ?, actual_start = ?, actual_end = ?
            WHERE wo_id = ?
        """, (payload.status, actual_start, actual_end, wo_id))

        return {"message": f"Cập nhật trạng thái lệnh {wo_id} thành {payload.status} thành công!"}
