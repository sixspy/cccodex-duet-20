"""左轨（渠道回执）装载。"""
from __future__ import annotations
import json, uuid
from app.db import 连接
from app.seed import 此刻
from app.services import 校验

def 装一批(体: dict) -> dict:
    批次 = 体.get("批次编号") or f"左批-{uuid.uuid4().hex[:8]}"
    事件 = 体.get("事件") or []
    报告 = {"批次编号": 批次, "轨别": "左", "入流": 0, "跳过": 0, "驳回": 0, "明细": []}
    for e in 校验.校验批次(体):
        报告["明细"].append({"命运": "批次预检", "说明": e})
    conn = 连接()
    try:
        for ev in 事件:
            行错 = 校验.校验事件(ev)
            if 行错:
                报告["驳回"] += 1
                报告["明细"].append({"命运": "驳回-校验", "说明": ";".join(行错)})
                continue
            编号 = ev.get("事件编号")
            键 = ev.get("业务键")
            if not 编号 or not 键:
                报告["驳回"] += 1
                报告["明细"].append({"命运": "驳回-缺字段", "事件": ev})
                continue
            if conn.execute("SELECT 1 FROM 左轨流水 WHERE 事件编号=?", (编号,)).fetchone():
                报告["跳过"] += 1
                报告["明细"].append({"事件编号": 编号, "命运": "幂等跳过"})
                continue
            源 = ev.get("源键") or "渠甲"
            if not conn.execute("SELECT 1 FROM 源登记 WHERE 源键=? AND 轨别='左'", (源,)).fetchone():
                报告["驳回"] += 1
                报告["明细"].append({"事件编号": 编号, "命运": "驳回-未知左源"})
                continue
            金额 = int(ev.get("金额分", 0))
            事件时 = ev.get("事件时") or 此刻()
            处理时 = ev.get("处理时") or 此刻()
            conn.execute(
                """INSERT INTO 左轨流水(事件编号,业务键,金额分,源键,事件时,处理时,命运,批次编号)
                   VALUES (?,?,?,?,?,?,'已入左',?)""",
                (编号, 键, 金额, 源, 事件时, 处理时, 批次),
            )
            报告["入流"] += 1
            报告["明细"].append({"事件编号": 编号, "业务键": 键, "命运": "已入左"})
        conn.execute(
            "INSERT INTO 装载批次(编号,轨别,时刻,报告) VALUES (?,?,?,?)",
            (批次, "左", 此刻(), json.dumps(报告, ensure_ascii=False)),
        )
        conn.commit()
        return 报告
    finally:
        conn.close()
