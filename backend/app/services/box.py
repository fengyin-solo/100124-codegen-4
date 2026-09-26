"""温控箱体业务规则：状态流转、批量出库/回收与站点盘点口径都收在这里。"""
from __future__ import annotations

from typing import Any

from app.store import store

MODULE = "box"
RECORD_MODULE = "box_records"
REQUIRED_FIELDS = ["箱体编号", "箱体类型", "内部容积"]
OPTIONAL_FIELDS = ["保温材料", "保温材料状态", "温控范围"]
STATUS_ORDER = ["可用", "使用中", "清洗中", "报废"]
ACTION_RULES = {"调度出库": "使用中", "清洗消毒": "清洗中", "申请报废": "报废"}
NEGATIVE_ACTIONS = []
IN_STOCK_STATION = "在库"
DAMAGED_MARK = "受损"


def _sync_status(entry: dict[str, Any]) -> None:
    """台账展示列跟着内部状态走，盘点页和台账看到的才是同一份数据。"""
    entry["箱体状态"] = str(entry.get("status") or STATUS_ORDER[0])


def _item_result(entry: dict[str, Any] | None, entry_id: Any, message: str) -> dict[str, Any]:
    code = str(entry.get("箱体编号")) if entry else f"#{entry_id}"
    return {"entry_id": entry_id, "箱体编号": code, "message": message}


class BoxService:
    def list_entries(
        self,
        *,
        keyword: str | None = None,
        status: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = store.rows(MODULE)
        if keyword:
            rows = [row for row in rows if keyword in str(row.get("箱体编号", ""))]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        total = len(rows)
        start = max(page - 1, 0) * size
        return rows[start:start + size], total

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        return store.find(MODULE, entry_id)

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        missing = [field for field in REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
        if missing:
            return None, missing
        rows = store.rows(MODULE)
        entry = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        entry.update({field: values.get(field) for field in REQUIRED_FIELDS})
        entry.update({field: values.get(field) for field in OPTIONAL_FIELDS if values.get(field)})
        entry["status"] = STATUS_ORDER[0]
        entry["pending"] = True
        entry["abnormal"] = False
        entry.setdefault("保温材料状态", "完好")
        entry["归属站点"] = IN_STOCK_STATION
        entry["出库日期"] = ""
        entry["出库记录"] = []
        _sync_status(entry)
        rows.append(entry)
        return entry, []

    def run_action(self, entry_id: int, action: str) -> tuple[dict[str, Any] | None, str]:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"温控箱体 {entry_id} 不存在或已归档"
        if action not in ACTION_RULES:
            return None, f"动作「{action}」不属于温控箱体可执行范围"
        target = ACTION_RULES[action]
        if target not in STATUS_ORDER:
            return None, f"目标状态「{target}」不在允许的状态序列里"
        entry["status"] = target
        entry["pending"] = target != STATUS_ORDER[-1]
        entry["abnormal"] = action in NEGATIVE_ACTIONS
        _sync_status(entry)
        return entry, f"温控箱体已{action}"

    def batch_checkout(self, checkout_date: str, items: list[dict[str, Any]]) -> dict[str, Any]:
        """整组提交出库：逐条校验、逐条生效，失败的说明原因，成功的不回滚。

        出库单按箱体类型拆分——类型不同的箱体不会合并进同一张出库单；
        温控范围直接取台账数据，保证站点盘点页与箱体台账口径一致。
        """
        checkout_date = (checkout_date or "").strip()
        if not items:
            return {"ok": False, "message": "请先勾选要出库的箱体", "succeeded": [], "failed": [], "records": []}
        if not checkout_date:
            failed = [
                _item_result(None, item.get("entry_id"), "缺少统一出库日期")
                for item in items
            ]
            return {"ok": False, "message": "请先填写统一的出库日期", "succeeded": [], "failed": failed, "records": []}

        succeeded: list[dict[str, Any]] = []
        failed: list[dict[str, Any]] = []
        accepted: list[tuple[dict[str, Any], str]] = []
        seen: set[int] = set()
        for item in items:
            entry_id = item.get("entry_id")
            entry = store.find(MODULE, int(entry_id)) if entry_id is not None else None
            if entry is None:
                failed.append(_item_result(None, entry_id, "箱体不存在或已归档"))
                continue
            if int(entry["id"]) in seen:
                failed.append(_item_result(entry, entry_id, "本次提交中重复勾选，已忽略"))
                continue
            seen.add(int(entry["id"]))
            station = str(item.get("归属站点") or "").strip()
            if not station:
                failed.append(_item_result(entry, entry_id, "缺少归属站点，请逐条填写"))
                continue
            if entry.get("status") != STATUS_ORDER[0]:
                failed.append(_item_result(entry, entry_id, f"当前状态为「{entry.get('status')}」，仅「可用」箱体可出库"))
                continue
            if entry.get("保温材料状态") == DAMAGED_MARK:
                failed.append(_item_result(entry, entry_id, "保温材料受损，需先检修再出库"))
                continue
            accepted.append((entry, station))
            succeeded.append(_item_result(entry, entry_id, "出库成功"))

        records: list[dict[str, Any]] = []
        groups: dict[str, list[tuple[dict[str, Any], str]]] = {}
        for entry, station in accepted:
            groups.setdefault(str(entry.get("箱体类型") or "未分类"), []).append((entry, station))
        seq = len(store.rows(RECORD_MODULE))
        for box_type, members in groups.items():
            seq += 1
            record_no = f"OUT-{checkout_date.replace('-', '')}-{seq:03d}"
            detail = [
                {
                    "箱体编号": entry.get("箱体编号"),
                    "归属站点": station,
                    "温控范围": entry.get("温控范围", ""),
                }
                for entry, station in members
            ]
            ranges = {str(row["温控范围"]) for row in detail}
            record = {
                "出库单号": record_no,
                "出库日期": checkout_date,
                "箱体类型": box_type,
                "温控范围": detail[0]["温控范围"] if len(ranges) == 1 else "见明细",
                "数量": len(members),
                "明细": detail,
            }
            store.rows(RECORD_MODULE).append(record)
            records.append(record)
            for entry, station in members:
                entry["status"] = "使用中"
                entry["pending"] = True
                entry["归属站点"] = station
                entry["出库日期"] = checkout_date
                _sync_status(entry)
                entry.setdefault("出库记录", []).append({
                    "出库单号": record_no,
                    "出库日期": checkout_date,
                    "归属站点": station,
                    "温控范围": entry.get("温控范围", ""),
                })

        if failed:
            message = f"成功出库 {len(succeeded)} 台，{len(failed)} 台未出库，可修正后仅重试失败项"
        else:
            message = f"已出库 {len(succeeded)} 台，生成 {len(records)} 张出库单"
        return {"ok": not failed, "message": message, "succeeded": succeeded, "failed": failed, "records": records}

    def batch_recycle(self, entry_ids: list[int]) -> dict[str, Any]:
        """批量回收：保温材料受损或已报废的箱体单独挑出，只回收还能用的。"""
        if not entry_ids:
            return {"ok": False, "message": "请先勾选要回收的箱体", "succeeded": [], "failed": [], "records": []}
        succeeded: list[dict[str, Any]] = []
        skipped: list[dict[str, Any]] = []
        for entry_id in dict.fromkeys(entry_ids):
            entry = store.find(MODULE, int(entry_id))
            if entry is None:
                skipped.append(_item_result(None, entry_id, "箱体不存在或已归档"))
                continue
            if entry.get("status") == "报废":
                skipped.append(_item_result(entry, entry_id, "已报废，需走报废处置，不参与回收"))
                continue
            if entry.get("保温材料状态") == DAMAGED_MARK:
                skipped.append(_item_result(entry, entry_id, "保温材料受损，需单独检修，不参与本次回收"))
                continue
            if entry.get("status") != "使用中":
                skipped.append(_item_result(entry, entry_id, f"当前状态为「{entry.get('status')}」，不在站点现场，无需回收"))
                continue
            entry["status"] = STATUS_ORDER[0]
            entry["pending"] = True
            entry["归属站点"] = IN_STOCK_STATION
            _sync_status(entry)
            succeeded.append(_item_result(entry, entry_id, "已回收在库"))
        if skipped:
            message = f"已回收 {len(succeeded)} 台，{len(skipped)} 台需单独处理（未回收）"
        else:
            message = f"已回收 {len(succeeded)} 台，全部回到在库状态"
        return {"ok": not skipped, "message": message, "succeeded": succeeded, "failed": skipped, "records": []}

    def station_inventory(self) -> list[dict[str, Any]]:
        """站点盘点：按归属站点分组，温控范围直接取台账数据，不与台账产生口径差。"""
        groups: dict[str, list[dict[str, Any]]] = {}
        for row in store.rows(MODULE):
            station = str(row.get("归属站点") or "").strip() or IN_STOCK_STATION
            groups.setdefault(station, []).append({
                "箱体编号": row.get("箱体编号"),
                "箱体类型": row.get("箱体类型"),
                "温控范围": row.get("温控范围"),
                "出库日期": row.get("出库日期"),
                "箱体状态": row.get("status"),
            })
        return [
            {"归属站点": station, "数量": len(boxes), "箱体列表": boxes}
            for station, boxes in sorted(groups.items())
        ]

    def list_checkout_records(self) -> list[dict[str, Any]]:
        """出库单列表，最新生成的排在前面。"""
        return list(reversed(store.rows(RECORD_MODULE)))
