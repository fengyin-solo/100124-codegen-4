"""温控箱体接口：箱体台账、批量出库/回收、出入库记录与站点盘点。"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.schemas import (
    ActionResult,
    BatchActionResult,
    BatchOutboundPayload,
    BatchReturnPayload,
    EntryPayload,
    PageResult,
)
from app.services.box import BoxService

router = APIRouter(prefix="/api/box", tags=["温控箱体"])

service = BoxService()

LIST_FIELDS = ["箱体编号", "箱体类型", "内部容积", "保温材料", "保温材料状态", "温控范围", "出库日期", "归属站点", "箱体状态"]
STATUSES = ["可用", "使用中", "清洗中", "报废"]


@router.get("", response_model=PageResult[dict])
def list_entries(
    keyword: str | None = Query(default=None, description="按箱体编号或归属站点检索"),
    status: str | None = Query(default=None, description="可用、使用中、清洗中、报废"),
    page: int = 1,
    size: int = 20,
) -> PageResult[dict]:
    """按箱体编号与状态过滤温控箱体列表；没有数据时返回空页，不报错。"""
    if size > 200:
        raise HTTPException(status_code=400, detail="每页最多 200 条，请缩小分页范围")
    items, total = service.list_entries(keyword=keyword, status=status, page=page, size=size)
    return PageResult(items=items, total=total, page=page, size=size)


@router.post("", response_model=ActionResult)
def create_entry(payload: EntryPayload) -> ActionResult:
    """登记一条温控箱体，缺字段时说明原因而不是静默丢弃。"""
    entry, missing = service.create_entry(payload.values)
    if missing:
        return ActionResult(ok=False, message=f"缺少必填字段：{'、'.join(missing)}")
    return ActionResult(ok=True, message="温控箱体已登记", entry=entry)


# ---- 批量动作：字面路径必须声明在 /{entry_id} 之前，否则会被动态路径截走 ----
@router.post("/batch-outbound", response_model=BatchActionResult)
def batch_outbound(payload: BatchOutboundPayload) -> BatchActionResult:
    """批量出库：逐条填写归属站点、统一出库日期。

    逐条独立校验落库，成功的状态切为「使用中」并按箱体类型生成出库记录；
    失败的逐条返回箱体编号与卡住原因，已成功的不回滚，可仅重试失败项。
    """
    if not payload.items:
        return BatchActionResult(ok=False, message="未勾选任何箱体，请先勾选要出库的箱体")
    result = service.batch_outbound(
        [item.model_dump() for item in payload.items], payload.出库日期
    )
    return BatchActionResult(**result)


@router.post("/batch-return/preview")
def batch_return_preview(payload: BatchReturnPayload) -> dict[str, Any]:
    """批量回收预览：把保温材料受损或已报废的箱体单独挑出来，只留下还能用的。"""
    return service.return_preview([item.id for item in payload.items])


@router.post("/batch-return", response_model=BatchActionResult)
def batch_return(payload: BatchReturnPayload) -> BatchActionResult:
    """批量回收：只回收还能用的箱体；成功的回库为「可用」，失败逐条说明不回滚。"""
    if not payload.items:
        return BatchActionResult(ok=False, message="没有可回收的箱体（受损与报废箱体已自动剔除）")
    result = service.batch_return(
        [item.model_dump() for item in payload.items], payload.回收日期 or ""
    )
    return BatchActionResult(**result)


@router.get("/records", response_model=PageResult[dict])
def list_records(
    keyword: str | None = Query(default=None, description="按记录编号或箱体编号检索"),
    box_type: str | None = Query(default=None, description="按箱体类型过滤"),
    page: int = 1,
    size: int = 20,
) -> PageResult[dict]:
    """出入库记录列表：一条记录对应同一种箱体类型，不跨类型合并。"""
    if size > 200:
        raise HTTPException(status_code=400, detail="每页最多 200 条，请缩小分页范围")
    items, total = service.list_records(keyword=keyword, box_type=box_type, page=page, size=size)
    return PageResult(items=items, total=total, page=page, size=size)


@router.get("/records/by-box/{box_code}")
def list_records_by_box(box_code: str) -> dict[str, Any]:
    """出库记录挂在箱体编号下面：按箱体编号查看它的全部出入库记录。"""
    return {"箱体编号": box_code, "items": service.list_records_by_box(box_code)}


@router.get("/station-inventory")
def station_inventory() -> dict[str, Any]:
    """站点盘点：按归属站点汇总；温控范围逐箱取自箱体台账，两处口径必然一致。"""
    groups = service.station_inventory()
    return {"total_stations": len(groups), "items": groups}


@router.get("/export")
def export_entries() -> dict[str, Any]:
    """导出温控箱体清单：返回当前过滤条件下的全量数据。"""
    items, total = service.list_entries(page=1, size=10000)
    return {"module": "box", "total": total, "items": items}


@router.get("/{entry_id}", response_model=dict)
def get_entry(entry_id: int) -> dict:
    """读取单条温控箱体明细；不存在时给出可读的错误说明。"""
    entry = service.get_entry(entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"温控箱体 {entry_id} 不存在或已归档")
    return entry


@router.post("/{entry_id}/actions", response_model=ActionResult)
def run_action(entry_id: int, payload: EntryPayload) -> ActionResult:
    """对单条温控箱体执行调度出库、清洗消毒、申请报废、保温材料标记等动作。"""
    action = str(payload.values.get("action") or "").strip()
    entry, message = service.run_action(entry_id, action, payload.values)
    if entry is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message=message, entry=entry)
