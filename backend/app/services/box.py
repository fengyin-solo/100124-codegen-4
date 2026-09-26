"""温控箱体业务规则：状态流转、批量出库/回收、出入库记录与站点盘点口径都收在这里。

关键约定：
- status（流程字段）与「箱体状态」（展示字段）始终同步，列表筛选与页面展示不会对不上；
- 批量动作逐条独立成败，成功即落库并生成记录，任何一条失败都不回滚其它箱体；
- 出入库记录按箱体类型分组，不同箱体类型绝不合并成同一条记录；
- 站点盘点的温控范围直接取自箱体台账，不另存副本，从源头避免两处口径不一致。
"""
from __future__ import annotations

from datetime import date
from typing import Any

from app.store import store

MODULE = "box"
RECORD_MODULE = "box_record"
REQUIRED_FIELDS = ["箱体编号", "箱体类型", "内部容积"]
STATUS_ORDER = ["可用", "使用中", "清洗中", "报废"]
ACTION_RULES = {"调度出库": "使用中", "清洗消毒": "清洗中", "申请报废": "报废"}
# 保温材料相关动作只翻转移损标记，不改变箱体状态。
DAMAGE_ACTIONS = {"标记保温材料受损": "受损", "保温材料修复": "正常"}
NEGATIVE_ACTIONS = []

OUTBOUND_PREFIX = "OUT"
RETURN_PREFIX = "IN"
IN_STATION_LABEL = "在库未出库"


def _today() -> str:
    return date.today().isoformat()


def is_valid_date(value: str) -> bool:
    """只认 YYYY-MM-DD 且必须是真实日期，挡住 2026-02-30 这种值。"""
    try:
        date.fromisoformat(value)
    except ValueError:
        return False
    return True


def _sync_status(entry: dict[str, Any]) -> None:
    """让流程字段与展示字段、待办/异常标记保持一致。"""
    status = str(entry.get("status") or STATUS_ORDER[0])
    entry["箱体状态"] = status
    entry["pending"] = status != STATUS_ORDER[-1]
    entry["abnormal"] = entry.get("保温材料状态") == "受损" or status == STATUS_ORDER[-1]


class BoxService:
    # ------------------------------------------------------------------ 查询
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
            rows = [
                row
                for row in rows
                if keyword in str(row.get("箱体编号", ""))
                or keyword in str(row.get("归属站点", ""))
            ]
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
        entry["保温材料"] = values.get("保温材料") or ""
        entry["保温材料状态"] = "正常"
        entry["温控范围"] = values.get("温控范围") or ""
        entry["出库日期"] = ""
        entry["归属站点"] = ""
        entry["最近记录编号"] = ""
        entry["status"] = STATUS_ORDER[0]
        _sync_status(entry)
        rows.append(entry)
        return entry, []

    # ------------------------------------------------------------ 单条动作
    def run_action(
        self, entry_id: int, action: str, values: dict[str, Any] | None = None
    ) -> tuple[dict[str, Any] | None, str]:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"温控箱体 {entry_id} 不存在或已归档"

        if action in DAMAGE_ACTIONS:
            entry["保温材料状态"] = DAMAGE_ACTIONS[action]
            _sync_status(entry)
            return entry, f"箱体 {entry.get('箱体编号')} 已{action}"

        if action not in ACTION_RULES:
            return None, f"动作「{action}」不属于温控箱体可执行范围"
        target = ACTION_RULES[action]
        if target not in STATUS_ORDER:
            return None, f"目标状态「{target}」不在允许的状态序列里"

        if action == "调度出库":
            message = self._check_outboundable(entry)
            if message:
                return None, message
            station = str((values or {}).get("归属站点") or "").strip()
            if not station:
                return None, "归属站点不能为空"
            outbound_date = str((values or {}).get("出库日期") or "").strip() or _today()
            if not is_valid_date(outbound_date):
                return None, f"出库日期 {outbound_date} 不是合法日期（YYYY-MM-DD）"
            entry["归属站点"] = station
            entry["出库日期"] = outbound_date
            entry["status"] = target
            _sync_status(entry)
            record = self._group_and_save_records("出库", [entry], outbound_date, "")
            entry["最近记录编号"] = record[0]["记录编号"]
            return entry, f"温控箱体 {entry['箱体编号']} 已出库到 {station}"

        if target == "报废":
            # 报废前若已出库，保留归属站点与日期，只切状态，便于台账追溯。
            entry["status"] = target
            _sync_status(entry)
            return entry, f"温控箱体 {entry.get('箱体编号')} 已申请报废"

        entry["status"] = target
        _sync_status(entry)
        return entry, f"温控箱体已{action}"

    @staticmethod
    def _check_outboundable(entry: dict[str, Any]) -> str:
        """出库前的统一卡口；返回非空字符串即为卡住原因。"""
        if entry.get("status") == "报废":
            return "箱体已报废，不能再出库，需走报废核销流程"
        if entry.get("status") != "可用":
            return f"当前状态为「{entry.get('status')}」，仅「可用」箱体可出库"
        if entry.get("保温材料状态") == "受损":
            return "保温材料受损，修复前不允许出库"
        return ""

    @staticmethod
    def _check_returnable(entry: dict[str, Any]) -> str:
        """回收前的统一卡口：受损与已报废的箱体要被单独挑出来。"""
        if entry.get("status") == "报废":
            return "箱体已报废，不能回收，需走报废核销流程"
        if entry.get("保温材料状态") == "受损":
            return "保温材料受损，需先维修鉴定，不纳入本次回收"
        if entry.get("status") == "可用":
            return "箱体已在库（可用），无需重复回收"
        if entry.get("status") == "清洗中":
            return "箱体清洗中，需完成清洗消毒后再回收入库"
        return ""

    # ------------------------------------------------------------ 批量出库
    def batch_outbound(
        self, items: list[dict[str, Any]], outbound_date: str
    ) -> dict[str, Any]:
        """勾选多个箱体整组出库：逐条填站点、统一出库日期。

        逐条校验、逐条落库：成功的立即切换为「使用中」，失败的带原因返回供修复后
        仅重试失败项；已经成功的不会因为同组其它箱体失败而回滚。
        """
        outbound_date = (outbound_date or "").strip()
        if not is_valid_date(outbound_date):
            return {
                "ok": False,
                "message": f"统一出库日期 {outbound_date} 不是合法日期（YYYY-MM-DD）",
                "items": [],
                "records": [],
            }

        result_items: list[dict[str, Any]] = []
        succeeded: list[dict[str, Any]] = []
        seen_ids: set[int] = set()

        for item in items:
            raw_id = item.get("id")
            code = str(item.get("箱体编号") or "").strip()
            try:
                entry_id = int(raw_id)
            except (TypeError, ValueError):
                result_items.append({
                    "id": raw_id, "箱体编号": code, "ok": False,
                    "reason": "缺少有效的箱体编号，未提交到服务端",
                })
                continue
            if entry_id in seen_ids:
                result_items.append({
                    "id": entry_id, "箱体编号": code, "ok": False,
                    "reason": "同一箱体在本次提交中重复出现",
                })
                continue
            seen_ids.add(entry_id)

            entry = store.find(MODULE, entry_id)
            if entry is None:
                result_items.append({
                    "id": entry_id, "箱体编号": code or str(entry_id), "ok": False,
                    "reason": "温控箱体不存在或已归档",
                })
                continue
            code = str(entry.get("箱体编号") or code)

            reason = self._check_outboundable(entry)
            station = str(item.get("归属站点") or "").strip()
            if not reason and not station:
                reason = "归属站点未填写"
            if reason:
                result_items.append({
                    "id": entry_id, "箱体编号": code, "归属站点": station,
                    "ok": False, "reason": reason,
                })
                continue

            entry["归属站点"] = station
            entry["出库日期"] = outbound_date
            entry["status"] = "使用中"
            _sync_status(entry)
            succeeded.append(entry)
            result_items.append({
                "id": entry_id, "箱体编号": code, "归属站点": station,
                "ok": True, "reason": "",
            })

        # 同一次提交内按箱体类型分组：每种类型一条出库记录，绝不跨类型合并。
        records = self._group_and_save_records("出库", succeeded, outbound_date, "")
        ok_count = sum(1 for item in result_items if item["ok"])
        fail_count = len(result_items) - ok_count
        if fail_count and ok_count:
            message = f"成功出库 {ok_count} 个，{fail_count} 个被卡住，可修复后仅重试失败项"
        elif fail_count:
            message = f"{fail_count} 个箱体全部出库失败，未生成出库记录"
        else:
            message = f"{ok_count} 个箱体全部出库成功，按箱体类型生成 {len(records)} 条出库记录"
        return {"ok": fail_count == 0, "message": message, "items": result_items, "records": records}

    # ------------------------------------------------------------ 批量回收
    def return_preview(self, ids: list[int]) -> dict[str, Any]:
        """回收前把箱体分成「可回收」与「剔除」两组，并给出剔除原因。"""
        reusable: list[dict[str, Any]] = []
        excluded: list[dict[str, Any]] = []
        seen: set[int] = set()
        for raw_id in ids:
            try:
                entry_id = int(raw_id)
            except (TypeError, ValueError):
                excluded.append({"id": raw_id, "箱体编号": str(raw_id), "reason": "箱体编号无效"})
                continue
            if entry_id in seen:
                continue
            seen.add(entry_id)
            entry = store.find(MODULE, entry_id)
            if entry is None:
                excluded.append({"id": entry_id, "箱体编号": str(entry_id), "reason": "温控箱体不存在或已归档"})
                continue
            reason = self._check_returnable(entry)
            target = reusable if not reason else excluded
            target.append({
                "id": entry_id,
                "箱体编号": entry.get("箱体编号"),
                "箱体类型": entry.get("箱体类型"),
                "温控范围": entry.get("温控范围"),
                "归属站点": entry.get("归属站点"),
                "箱体状态": entry.get("status"),
                "保温材料状态": entry.get("保温材料状态"),
                **({"reason": reason} if reason else {}),
            })
        return {"reusable": reusable, "excluded": excluded}

    def batch_return(self, items: list[dict[str, Any]], return_date: str) -> dict[str, Any]:
        """批量回收：只处理还能用的箱体，成功的回库为「可用」，失败不影响其它。"""
        return_date = (return_date or "").strip() or _today()
        if not is_valid_date(return_date):
            return {
                "ok": False,
                "message": f"回收日期 {return_date} 不是合法日期（YYYY-MM-DD）",
                "items": [],
                "records": [],
            }

        result_items: list[dict[str, Any]] = []
        succeeded: list[dict[str, Any]] = []
        seen_ids: set[int] = set()

        for item in items:
            raw_id = item.get("id")
            code = str(item.get("箱体编号") or "").strip()
            try:
                entry_id = int(raw_id)
            except (TypeError, ValueError):
                result_items.append({
                    "id": raw_id, "箱体编号": code, "ok": False,
                    "reason": "缺少有效的箱体编号，未提交到服务端",
                })
                continue
            if entry_id in seen_ids:
                result_items.append({
                    "id": entry_id, "箱体编号": code, "ok": False,
                    "reason": "同一箱体在本次提交中重复出现",
                })
                continue
            seen_ids.add(entry_id)

            entry = store.find(MODULE, entry_id)
            if entry is None:
                result_items.append({
                    "id": entry_id, "箱体编号": code or str(entry_id), "ok": False,
                    "reason": "温控箱体不存在或已归档",
                })
                continue
            code = str(entry.get("箱体编号") or code)
            reason = self._check_returnable(entry)
            if reason:
                result_items.append({
                    "id": entry_id, "箱体编号": code, "ok": False, "reason": reason,
                })
                continue

            entry["status"] = "可用"
            entry["归属站点"] = ""
            entry["出库日期"] = ""
            _sync_status(entry)
            succeeded.append(entry)
            result_items.append({
                "id": entry_id, "箱体编号": code, "ok": True, "reason": "",
            })

        records = self._group_and_save_records("回收", succeeded, "", return_date)
        ok_count = sum(1 for item in result_items if item["ok"])
        fail_count = len(result_items) - ok_count
        if fail_count and ok_count:
            message = f"成功回收 {ok_count} 个，{fail_count} 个被卡住，可修复后仅重试失败项"
        elif fail_count:
            message = f"{fail_count} 个箱体全部回收失败，未生成回收记录"
        else:
            message = f"{ok_count} 个箱体全部回收成功，按箱体类型生成 {len(records)} 条回收记录"
        return {"ok": fail_count == 0, "message": message, "items": result_items, "records": records}

    # ------------------------------------------------------------ 出入库记录
    def _next_record_no(self, prefix: str) -> str:
        rows = store.rows(RECORD_MODULE)
        seq = 0
        for row in rows:
            no = str(row.get("记录编号") or "")
            if no.startswith(f"{prefix}-"):
                try:
                    seq = max(seq, int(no.split("-", 1)[1]))
                except ValueError:
                    continue
        return f"{prefix}-{seq + 1:04d}"

    def _group_and_save_records(
        self,
        kind: str,
        entries: list[dict[str, Any]],
        outbound_date: str,
        return_date: str,
    ) -> list[dict[str, Any]]:
        """按箱体类型分组落记录；同类型一条，不同类型绝不合并。"""
        groups: dict[str, list[dict[str, Any]]] = {}
        for entry in entries:
            groups.setdefault(str(entry.get("箱体类型") or "未分类"), []).append(entry)

        prefix = OUTBOUND_PREFIX if kind == "出库" else RETURN_PREFIX
        records: list[dict[str, Any]] = []
        rows = store.rows(RECORD_MODULE)
        # 同一次提交里类型的先后按编号排序，保证记录顺序稳定。
        for box_type in sorted(groups):
            group = groups[box_type]
            record = {
                "id": max((int(row.get("id", 0)) for row in rows), default=0) + 1,
                "记录编号": self._next_record_no(prefix),
                "记录类型": kind,
                "箱体类型": box_type,
                # 同类型理论上温控范围一致；取首箱口径，箱体台账仍是唯一事实来源。
                "温控范围": group[0].get("温控范围") or "",
                "出库日期": outbound_date,
                "回收日期": return_date,
                "数量": len(group),
                "箱体编号": [str(box.get("箱体编号")) for box in group],
                "归属站点": "、".join(dict.fromkeys(
                    str(box.get("归属站点") or "") for box in group if box.get("归属站点")
                )),
                "明细": [
                    {"箱体编号": str(box.get("箱体编号")), "归属站点": str(box.get("归属站点") or "")}
                    for box in group
                ],
            }
            rows.append(record)
            for box in group:
                box["最近记录编号"] = record["记录编号"]
            records.append(record)
        return records

    def list_records(
        self,
        *,
        keyword: str | None = None,
        box_type: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = store.rows(RECORD_MODULE)
        if keyword:
            rows = [
                row
                for row in rows
                if keyword in str(row.get("记录编号", ""))
                or any(keyword in str(code) for code in row.get("箱体编号", []))
            ]
        if box_type:
            rows = [row for row in rows if row.get("箱体类型") == box_type]
        rows = sorted(rows, key=lambda row: int(row.get("id", 0)), reverse=True)
        total = len(rows)
        start = max(page - 1, 0) * size
        return rows[start:start + size], total

    def list_records_by_box(self, box_code: str) -> list[dict[str, Any]]:
        """出库记录挂在箱体编号下面：按箱体编号反查全部出入库记录。"""
        rows = store.rows(RECORD_MODULE)
        return [
            row for row in rows
            if box_code in [str(code) for code in row.get("箱体编号", [])]
        ]

    # ------------------------------------------------------------ 站点盘点
    def station_inventory(self) -> list[dict[str, Any]]:
        """站点盘点：按归属站点汇总箱体，温控范围逐箱取自台账，不另存副本。"""
        groups: dict[str, list[dict[str, Any]]] = {}
        for row in store.rows(MODULE):
            station = str(row.get("归属站点") or "").strip() or IN_STATION_LABEL
            groups.setdefault(station, []).append(row)

        result: list[dict[str, Any]] = []
        for station in sorted(groups, key=lambda name: (name == IN_STATION_LABEL, name)):
            boxes = groups[station]
            result.append({
                "归属站点": station,
                "箱体数量": len(boxes),
                "使用中": sum(1 for box in boxes if box.get("status") == "使用中"),
                "清洗中": sum(1 for box in boxes if box.get("status") == "清洗中"),
                "可用": sum(1 for box in boxes if box.get("status") == "可用"),
                "报废": sum(1 for box in boxes if box.get("status") == "报废"),
                "保温材料受损": sum(1 for box in boxes if box.get("保温材料状态") == "受损"),
                # 温控范围汇总与逐箱明细都来自箱体台账本身，站点页不可能和台账对不上。
                "温控范围汇总": list(dict.fromkeys(
                    str(box.get("温控范围") or "") for box in boxes if box.get("温控范围")
                )),
                "明细": [
                    {
                        "箱体编号": box.get("箱体编号"),
                        "箱体类型": box.get("箱体类型"),
                        "温控范围": box.get("温控范围"),
                        "保温材料状态": box.get("保温材料状态"),
                        "箱体状态": box.get("status"),
                        "最近记录编号": box.get("最近记录编号") or "",
                    }
                    for box in boxes
                ],
            })
        return result
