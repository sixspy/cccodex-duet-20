"""对拍统计。"""
from __future__ import annotations
from app.db import 连接

def 左命运() -> dict:
    conn = 连接()
    rows = conn.execute("SELECT 命运, COUNT(*) AS c FROM 左轨流水 GROUP BY 命运").fetchall()
    conn.close()
    return {r["命运"]: r["c"] for r in rows}

def 右命运() -> dict:
    conn = 连接()
    rows = conn.execute("SELECT 命运, COUNT(*) AS c FROM 右轨流水 GROUP BY 命运").fetchall()
    conn.close()
    return {r["命运"]: r["c"] for r in rows}

def 差型分布() -> dict:
    conn = 连接()
    rows = conn.execute("SELECT 差型, COUNT(*) AS c FROM 对齐差 GROUP BY 差型").fetchall()
    conn.close()
    return {r["差型"]: r["c"] for r in rows}

def 悬边分布() -> dict:
    conn = 连接()
    rows = conn.execute("SELECT 悬边, COUNT(*) AS c FROM 悬账单 GROUP BY 悬边").fetchall()
    conn.close()
    return {r["悬边"]: r["c"] for r in rows}
