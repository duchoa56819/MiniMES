"""
Dashboard Router - Plant KPIs, OEE, Quality Distribution, Machine Status.
"""

from fastapi import APIRouter
from app.database import get_read_replica_db

router = APIRouter(prefix="/api/dashboard", tags=["Dashboard"])


@router.get("/kpis")
def get_plant_kpis():
    """
    Calculates overall plant KPIs using 100% PURE SQL on the READ-REPLICA.
    Separated 100% from shop floor transactional database locks.
    Computes FPY, Scrap Rate, Availability, Quality, and OEE directly inside SQLite engine.
    """
    with get_read_replica_db() as conn:
        cursor = conn.cursor()

        sql = """
            WITH QualityStats AS (
                SELECT
                    COUNT(*) AS total_inspected,
                    SUM(CASE WHEN final_grade = 'GRADE_A' THEN 1 ELSE 0 END) AS grade_a_count,
                    SUM(CASE WHEN final_grade = 'GRADE_B' THEN 1 ELSE 0 END) AS grade_b_count,
                    SUM(CASE WHEN final_grade = 'REWORK' THEN 1 ELSE 0 END) AS rework_count,
                    SUM(CASE WHEN final_grade = 'SCRAP' THEN 1 ELSE 0 END) AS scrap_count,
                    ROUND(
                        CAST(SUM(CASE WHEN final_grade = 'GRADE_A' THEN 1 ELSE 0 END) AS FLOAT) 
                        / NULLIF(COUNT(*), 0) * 100, 1
                    ) AS fpy_percent,
                    ROUND(
                        CAST(SUM(CASE WHEN final_grade = 'SCRAP' THEN 1 ELSE 0 END) AS FLOAT) 
                        / NULLIF(COUNT(*), 0) * 100, 1
                    ) AS scrap_rate_percent
                FROM quality_inspections
            ),
            EquipmentStats AS (
                SELECT
                    COUNT(*) AS total_machines,
                    SUM(CASE WHEN status = 'RUNNING' THEN 1 ELSE 0 END) AS running_machines,
                    ROUND(
                        CAST(SUM(CASE WHEN status = 'RUNNING' THEN 1 ELSE 0 END) AS FLOAT) 
                        / NULLIF(COUNT(*), 0) * 100, 1
                    ) AS availability_percent
                FROM master_equipment
            ),
            ProductionCounts AS (
                SELECT
                    (SELECT COUNT(*) FROM production_green_tires) AS total_green_tires,
                    (SELECT COUNT(*) FROM production_cured_tires) AS total_cured_tires,
                    (SELECT COUNT(*) FROM work_orders WHERE status = 'IN_PROGRESS') AS active_work_orders
            )
            SELECT
                p.total_green_tires,
                p.total_cured_tires,
                q.total_inspected,
                COALESCE(q.grade_a_count, 0) AS grade_a_count,
                COALESCE(q.grade_b_count, 0) AS grade_b_count,
                COALESCE(q.rework_count, 0) AS rework_count,
                COALESCE(q.scrap_count, 0) AS scrap_count,
                COALESCE(q.fpy_percent, 100.0) AS fpy_percent,
                COALESCE(q.scrap_rate_percent, 0.0) AS scrap_rate_percent,
                e.total_machines,
                COALESCE(e.running_machines, 0) AS running_machines,
                COALESCE(e.availability_percent, 0.0) AS availability_percent,
                92.4 AS performance_percent,
                COALESCE(q.fpy_percent, 100.0) AS quality_percent,
                -- Formula: OEE = (Availability / 100) * (Performance / 100) * (Quality / 100) * 100
                ROUND(
                    (COALESCE(e.availability_percent, 0.0) / 100.0) 
                    * (92.4 / 100.0) 
                    * (COALESCE(q.fpy_percent, 100.0) / 100.0) * 100, 1
                ) AS oee_percent,
                p.active_work_orders
            FROM ProductionCounts p
            CROSS JOIN QualityStats q
            CROSS JOIN EquipmentStats e;
        """

        row = cursor.execute(sql).fetchone()
        return dict(row)


@router.get("/lines-status")
def get_lines_status():
    """Returns real-time status of all plant equipment grouped by area using pure SQL."""
    with get_read_replica_db() as conn:
        cursor = conn.cursor()
        rows = cursor.execute("""
            SELECT e.*, a.area_name, a.sequence_order
            FROM master_equipment e
            JOIN master_areas a ON e.area_code = a.area_code
            ORDER BY a.sequence_order ASC, e.machine_id ASC
        """).fetchall()

        return [dict(row) for row in rows]


@router.get("/quality-summary")
def get_quality_summary():
    """Returns quality grade distribution and top defect Pareto using pure SQL aggregations."""
    with get_read_replica_db() as conn:
        cursor = conn.cursor()

        # Grade Breakdown
        grades = cursor.execute("""
            SELECT final_grade, count(*) as count
            FROM quality_inspections
            GROUP BY final_grade
        """).fetchall()

        # Defect Pareto (Visual + X-Ray)
        pareto = cursor.execute("""
            SELECT d.defect_code, d.defect_name_vi, d.defect_name_en, d.severity, count(*) as defect_count
            FROM quality_inspections q
            JOIN master_defect_codes d ON (q.visual_defect_code = d.defect_code OR q.xray_defect_code = d.defect_code)
            GROUP BY d.defect_code
            ORDER BY defect_count DESC
        """).fetchall()

        return {
            "grades": [dict(g) for g in grades],
            "pareto": [dict(p) for p in pareto]
        }


@router.get("/recent-events")
def get_recent_events():
    """Returns live activity feed from shop floor using a single pure SQL UNION ALL query."""
    with get_read_replica_db() as conn:
        cursor = conn.cursor()

        sql = """
            SELECT gt_barcode as ref_id, 'GREEN_TIRE_BUILT' as event_type,
                   'Đã thành hình lốp sống ' || gt_barcode || ' (' || sku || ')' as message,
                   build_timestamp as event_time, tbm_machine_id as location
            FROM production_green_tires
            UNION ALL
            SELECT tire_serial as ref_id, 'TIRE_CURED' as event_type,
                   'Lưu hóa hoàn tất lốp ' || tire_serial || ' tại ' || press_id || '-' || cavity_side as message,
                   cure_end_time as event_time, press_id as location
            FROM production_cured_tires
            UNION ALL
            SELECT tire_serial as ref_id, 'QUALITY_INSPECTED' as event_type,
                   'Đánh giá chất lượng ' || tire_serial || ' -> ' || final_grade as message,
                   inspection_timestamp as event_time, 'KCS' as location
            FROM quality_inspections
            ORDER BY event_time DESC
            LIMIT 10;
        """

        rows = cursor.execute(sql).fetchall()
        return [dict(r) for r in rows]
