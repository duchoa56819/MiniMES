"""
Pydantic Data Models & Validation Schemas for Tire MES.
Ensures rigorous data integrity for shop-floor transactions.
"""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


# -----------------------------------------------------------------------------
# WORK ORDERS
# -----------------------------------------------------------------------------
class WorkOrderCreate(BaseModel):
    wo_id: str = Field(..., example="WO-2026-006")
    sku: str = Field(..., example="PCR-205-55R16-91V")
    target_qty: int = Field(..., gt=0, example=200)
    planned_start: str = Field(..., example="2026-10-06 08:00")
    planned_end: str = Field(..., example="2026-10-06 16:00")
    priority: str = Field(default="NORMAL", example="HIGH")
    assigned_machine: Optional[str] = Field(default="TBM-01")


class WorkOrderStatusUpdate(BaseModel):
    status: str = Field(..., example="IN_PROGRESS")


# -----------------------------------------------------------------------------
# TBM / GREEN TIRE BUILDING (POKA-YOKE)
# -----------------------------------------------------------------------------
class GreenTireBuildRequest(BaseModel):
    wo_id: str = Field(..., example="WO-2026-001")
    sku: str = Field(..., example="PCR-205-55R16-91V")
    tbm_machine_id: str = Field(..., example="TBM-01")
    operator_id: str = Field(..., example="OP-1001")
    actual_weight_kg: float = Field(..., gt=0.0, example=9.32)
    tread_lot: str = Field(..., example="LOT-TRD-202610-01")
    sidewall_lot: str = Field(..., example="LOT-SW-202610-01")
    belt1_lot: str = Field(..., example="LOT-BLT1-202610-01")
    belt2_lot: str = Field(..., example="LOT-BLT2-202610-01")
    ply_lot: str = Field(..., example="LOT-PLY-202610-01")
    bead_lot: str = Field(..., example="LOT-BD-202610-01")
    innerliner_lot: str = Field(..., example="LOT-INL-202610-01")
    override_poka_yoke: bool = Field(default=False)


# -----------------------------------------------------------------------------
# CURING / VULCANIZATION (LƯU HÓA)
# -----------------------------------------------------------------------------
class CuringLoadRequest(BaseModel):
    press_id: str = Field(..., example="CP-01")
    cavity_side: str = Field(..., example="L")
    gt_barcode: str = Field(..., example="GT-202610-0001")
    mold_id: Optional[str] = Field(default=None)


class CuringStartRequest(BaseModel):
    press_id: str = Field(..., example="CP-01")
    cavity_side: str = Field(..., example="L")


class CuringUnloadRequest(BaseModel):
    press_id: str = Field(..., example="CP-01")
    cavity_side: str = Field(..., example="L")


# -----------------------------------------------------------------------------
# QUALITY INSPECTION & DISPOSITION (KCS)
# -----------------------------------------------------------------------------
class QualityInspectionRequest(BaseModel):
    tire_serial: str = Field(..., example="VN-T-202610-00101")
    inspector_id: str = Field(..., example="OP-3001")
    visual_result: str = Field(..., example="PASS")
    visual_defect_code: Optional[str] = Field(default=None, example="DEF-VIS-01")
    defect_location: Optional[str] = Field(default=None, example="Sidewall 45 deg")
    xray_result: str = Field(..., example="PASS")
    xray_defect_code: Optional[str] = Field(default=None)
    belt_alignment_mm: float = Field(default=0.0, example=0.4)
    uniformity_rfv_n: float = Field(default=42.0, example=45.0)
    uniformity_lfv_n: float = Field(default=20.0, example=18.5)
    dynamic_balance_g: float = Field(default=15.0, example=20.0)
    disposition_notes: Optional[str] = Field(default=None)


# -----------------------------------------------------------------------------
# EQUIPMENT STATUS & DOWNTIME
# -----------------------------------------------------------------------------
class MachineStatusUpdate(BaseModel):
    machine_id: str = Field(..., example="TBM-01")
    status: str = Field(..., example="RUNNING")
    reason_code: Optional[str] = Field(default=None)
    comments: Optional[str] = Field(default=None)


# -----------------------------------------------------------------------------
# INVENTORY LOT REGISTRATION
# -----------------------------------------------------------------------------
class ComponentLotCreate(BaseModel):
    lot_id: str
    component_type: str
    spec_code: str
    compound_code: str
    expiry_time: str
    remaining_qty: int = 50
    storage_location: str
    raw_batch_ref: str
