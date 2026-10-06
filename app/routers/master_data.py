"""
Master Data Router - Products, BOMs, Recipes, Equipment, Operators, Defects.
Also provides a Demo Reset endpoint.
"""

from fastapi import APIRouter, HTTPException
from app.database import get_db
from app.seed_data import seed_database
from app.models import MachineStatusUpdate

router = APIRouter(prefix="/api/master", tags=["Master Data"])


@router.get("/products")
def list_products():
    """Returns catalog of tire SKUs."""
    with get_db() as conn:
        cursor = conn.cursor()
        rows = cursor.execute("SELECT * FROM master_products ORDER BY segment, sku").fetchall()
        return [dict(r) for r in rows]


@router.get("/equipment")
def list_equipment():
    """Returns plant equipment hierarchy."""
    with get_db() as conn:
        cursor = conn.cursor()
        rows = cursor.execute("""
            SELECT e.*, a.area_name
            FROM master_equipment e
            JOIN master_areas a ON e.area_code = a.area_code
            ORDER BY a.sequence_order, e.machine_id
        """).fetchall()
        return [dict(r) for r in rows]


@router.put("/equipment/{machine_id}/status")
def update_machine_status(machine_id: str, payload: MachineStatusUpdate):
    """Updates machine operational status (RUNNING, IDLE, BREAKDOWN, MAINTENANCE)."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE master_equipment
            SET status = ?
            WHERE machine_id = ?
        """, (payload.status, machine_id))

        if payload.status in ("BREAKDOWN", "CHANGEOVER", "MAINTENANCE") and payload.reason_code:
            cursor.execute("""
                INSERT INTO equipment_downtime_logs (machine_id, start_time, reason_code, comments)
                VALUES (?, datetime('now', 'localtime'), ?, ?)
            """, (machine_id, payload.reason_code, payload.comments))

        return {"message": f"Cập nhật trạng thái máy {machine_id} thành {payload.status} thành công!"}


@router.get("/boms/{sku}")
def get_bom(sku: str):
    """Returns Bill of Materials for a specific tire SKU."""
    with get_db() as conn:
        cursor = conn.cursor()
        rows = cursor.execute("SELECT * FROM master_boms WHERE sku = ?", (sku,)).fetchall()
        return [dict(r) for r in rows]


@router.get("/recipes/{sku}")
def get_recipe(sku: str):
    """Returns Curing Recipe for a specific tire SKU."""
    with get_db() as conn:
        cursor = conn.cursor()
        row = cursor.execute("SELECT * FROM master_curing_recipes WHERE sku = ?", (sku,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Không tìm thấy đơn công nghệ lưu hóa!")
        return dict(row)


@router.get("/operators")
def list_operators():
    """Returns certified operators."""
    with get_db() as conn:
        cursor = conn.cursor()
        rows = cursor.execute("SELECT * FROM master_operators ORDER BY role, badge_id").fetchall()
        return [dict(r) for r in rows]


@router.get("/defects")
def list_defects():
    """Returns defect catalog."""
    with get_db() as conn:
        cursor = conn.cursor()
        rows = cursor.execute("SELECT * FROM master_defect_codes ORDER BY defect_code").fetchall()
        return [dict(r) for r in rows]


@router.get("/documents")
def list_documents(category: str = None):
    """Returns list of controlled SOPs, drawings, and work instructions (Module 4)."""
    with get_db() as conn:
        cursor = conn.cursor()
        query = "SELECT * FROM master_documents"
        params = []
        if category:
            query += " WHERE category = ?"
            params.append(category)
        query += " ORDER BY category, doc_code"
        rows = cursor.execute(query, params).fetchall()
        return [dict(r) for r in rows]


@router.get("/documents/{doc_id}")
def get_document_detail(doc_id: str):
    """Returns detailed content of a controlled document."""
    with get_db() as conn:
        cursor = conn.cursor()
        row = cursor.execute("SELECT * FROM master_documents WHERE doc_id = ?", (doc_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Không tìm thấy tài liệu điều khiển!")
        return dict(row)


@router.post("/reset-demo")
def reset_demo_database():
    """Re-initializes and seeds the database to initial clean state."""
    seed_database()
    return {"message": "Hệ thống cơ sở dữ liệu MES đã được tái khởi tạo và nạp dữ liệu chuẩn thành công!"}
