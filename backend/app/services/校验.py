"""装载字段校验：左/右轨入流前的结构与业务键卫生检查。"""
from __future__ import annotations

必填 = ("事件编号", "业务键", "金额分", "事件时")
可选字 = ("币种", "渠道码", "备注")


def 校验事件(ev: dict) -> list[str]:
    if not isinstance(ev, dict):
        return ["事件不是对象"]
    错: list[str] = []
    for k in 必填:
        if ev.get(k) in (None, ""):
            错.append(f"缺字段:{k}")
    金额 = ev.get("金额分", 0)
    try:
        n = int(金额)
        if n < 0:
            错.append("金额分不可为负")
    except (TypeError, ValueError):
        错.append("金额分非整数")
    键 = str(ev.get("业务键") or "").strip()
    if 键 and (" " in 键 or "\t" in 键):
        错.append("业务键含空白")
    if 键 and len(键) > 128:
        错.append("业务键过长")
    return 错


def 校验批次(体: dict) -> list[str]:
    if not isinstance(体, dict):
        return ["体须为对象"]
    事件 = 体.get("事件")
    if not isinstance(事件, list) or not 事件:
        return ["事件列表为空"]
    if len(事件) > 5000:
        return ["单批事件过多"]
    错: list[str] = []
    见: set[str] = set()
    for i, ev in enumerate(事件):
        for e in 校验事件(ev or {}):
            错.append(f"[{i}]{e}")
        编号 = str((ev or {}).get("事件编号", ""))
        if 编号 and 编号 in 见:
            错.append(f"[{i}]事件编号重复")
        if 编号:
            见.add(编号)
    return 错


def 摘要校验(错: list[str], 上限: int = 8) -> dict:
    """页面装载回执用的短摘要，避免把整批明细塞进顶栏。"""
    总 = len(错 or [])
    头 = list(错 or [])[: max(1, 上限)]
    return {"条数": 总, "截断": 总 > len(头), "样例": 头}
