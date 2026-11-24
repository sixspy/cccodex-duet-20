from app.db import 连接

def 轨规() -> dict:
    conn = 连接()
    rows = conn.execute("SELECT 键, 值 FROM 轨规").fetchall()
    conn.close()
    return {r["键"]: r["值"] for r in rows}

def 改轨规(体: dict) -> dict:
    conn = 连接()
    for k, v in 体.items():
        conn.execute(
            "INSERT INTO 轨规(键, 值) VALUES (?, ?) ON CONFLICT(键) DO UPDATE SET 值=excluded.值",
            (k, str(v)),
        )
    conn.commit()
    conn.close()
    return 轨规()

def 源列表() -> list[dict]:
    conn = 连接()
    rows = conn.execute("SELECT * FROM 源登记 ORDER BY 轨别, 源键").fetchall()
    conn.close()
    return [dict(r) for r in rows]

def 左列表(限制: int = 300) -> list[dict]:
    conn = 连接()
    rows = conn.execute("SELECT * FROM 左轨流水 ORDER BY 处理时 DESC LIMIT ?", (限制,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def 右列表(限制: int = 300) -> list[dict]:
    conn = 连接()
    rows = conn.execute("SELECT * FROM 右轨流水 ORDER BY 处理时 DESC LIMIT ?", (限制,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def 差列表() -> list[dict]:
    conn = 连接()
    rows = conn.execute("SELECT * FROM 对齐差 ORDER BY 编号 DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]

def 悬列表() -> list[dict]:
    conn = 连接()
    rows = conn.execute("SELECT * FROM 悬账单 ORDER BY 编号 DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]

def 结论列表() -> list[dict]:
    conn = 连接()
    rows = conn.execute("SELECT * FROM 对拍结论 ORDER BY 编号 DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]

def 概览() -> dict:
    conn = 连接()
    g = 轨规()
    out = {
        "站名": g.get("站名", "对拍"),
        "骨架": g.get("骨架", ""),
        "皮": g.get("皮", ""),
        "去皮": g.get("去皮", ""),
        "左笔数": conn.execute("SELECT COUNT(*) AS c FROM 左轨流水").fetchone()["c"],
        "右笔数": conn.execute("SELECT COUNT(*) AS c FROM 右轨流水").fetchone()["c"],
        "对齐差数": conn.execute("SELECT COUNT(*) AS c FROM 对齐差").fetchone()["c"],
        "悬账数": conn.execute("SELECT COUNT(*) AS c FROM 悬账单").fetchone()["c"],
        "结论数": conn.execute("SELECT COUNT(*) AS c FROM 对拍结论").fetchone()["c"],
    }
    conn.close()
    return out
