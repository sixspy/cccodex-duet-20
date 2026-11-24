"""装载批失败闭 · 影子草稿形态主链。

题面择定形态：**影子草稿整批暂存**（非独立凭证冻结）。
- 本批先写影子草稿；失败则草稿作废不进现行，成功再原子晋升。
- 现行（对齐编排可读集）在晋升前读不到本批键；失败批现行零本批行——
  与凭证形态（现行留前成行）在「现行本批行数」上可区分。

硬约束落法：
- 收口回执与可读流水同成败：成功票 ⟺ 本批行全数在现行；失败票 ⟺ 现行零本批行。
  只读接口的 valid 是活探针，按现行库表现场复核，不是回放存根。
- 第二批同轨并发：整批装载包在 BEGIN IMMEDIATE 单事务里，同轨写者串行；
  同批号重演在事务内先查旧票直接回票，不会双成功覆盖批界，也不得半截现行。
- 禁止报告成功留脏行：晋升、回执、收口同一事务；失败批只落作废草稿，现行零行。
"""
from __future__ import annotations

import json
import uuid

from app.db import 连接
from app.seed import 此刻
from app.services import 校验

形态 = "影子草稿"

# 模块自管表（不用 executescript：Connection.executescript 会先隐式提交，
# 会把外层 BEGIN IMMEDIATE 事务冲掉；逐条 execute 才留在事务里）。
建表语句 = (
    """
    CREATE TABLE IF NOT EXISTS 影子草稿 (
      影子键 TEXT NOT NULL,
      轨别 TEXT NOT NULL,
      批次编号 TEXT NOT NULL,
      事件编号 TEXT NOT NULL,
      业务键 TEXT NOT NULL,
      金额分 INTEGER NOT NULL,
      源键 TEXT NOT NULL,
      事件时 TEXT NOT NULL,
      处理时 TEXT NOT NULL,
      状态 TEXT NOT NULL DEFAULT '暂存',
      PRIMARY KEY (影子键, 事件编号)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS 装载收口 (
      批次编号 TEXT PRIMARY KEY,
      轨别 TEXT NOT NULL,
      形态 TEXT NOT NULL,
      影子键 TEXT NOT NULL,
      成败 TEXT NOT NULL,
      入流 INTEGER NOT NULL DEFAULT 0,
      跳过 INTEGER NOT NULL DEFAULT 0,
      驳回 INTEGER NOT NULL DEFAULT 0,
      现行行数 INTEGER NOT NULL DEFAULT 0,
      时刻 TEXT NOT NULL,
      说明 TEXT NOT NULL DEFAULT ''
    )
    """,
)

轨参 = {
    "左": {"表": "左轨流水", "命运": "已入左", "默认源": "渠甲", "拒源": "驳回-未知左源"},
    "右": {"表": "右轨流水", "命运": "已入右", "默认源": "核乙", "拒源": "驳回-未知右源"},
}


def 确保表(conn) -> None:
    for 句 in 建表语句:
        conn.execute(句)


def 装一批(体: dict, 轨别: str) -> dict:
    """整批影子暂存 → 纯成功原子晋升 / 中途失败整批作废，回执与现行同成败。"""
    p = 轨参[轨别]
    批次 = 体.get("批次编号") or f"{轨别}批-{uuid.uuid4().hex[:8]}"
    事件 = 体.get("事件") or []
    影子键 = f"影-{轨别}-{批次}"
    报告 = {
        "批次编号": 批次,
        "轨别": 轨别,
        "形态": 形态,
        "影子键": 影子键,
        "入流": 0,
        "跳过": 0,
        "驳回": 0,
        "明细": [],
    }
    conn = 连接()
    conn.isolation_level = None  # 手动事务，只影响本连接
    try:
        # 同轨写锁：第二批并发在此串行，批界不互踩、不留半截现行。
        conn.execute("BEGIN IMMEDIATE")
        确保表(conn)

        旧 = conn.execute(
            "SELECT 报告 FROM 装载批次 WHERE 编号=?", (批次,)
        ).fetchone()
        if 旧:
            conn.execute("COMMIT")
            旧报告 = json.loads(旧["报告"])
            旧报告["重复批次"] = True
            return 旧报告

        预检 = 校验.校验批次(体)
        for e in 预检:
            报告["明细"].append({"命运": "批次预检", "说明": e})

        暂存: list[tuple[dict, tuple]] = []  # (明细条目, 行参数)
        见: set[str] = set()
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
            if 编号 in 见:
                报告["驳回"] += 1
                报告["明细"].append({"事件编号": 编号, "命运": "驳回-批内重复"})
                continue
            见.add(编号)
            if conn.execute(
                f"SELECT 1 FROM {p['表']} WHERE 事件编号=?", (编号,)
            ).fetchone():
                报告["跳过"] += 1
                报告["明细"].append({"事件编号": 编号, "命运": "幂等跳过"})
                continue
            源 = ev.get("源键") or p["默认源"]
            if not conn.execute(
                "SELECT 1 FROM 源登记 WHERE 源键=? AND 轨别=?", (源, 轨别)
            ).fetchone():
                报告["驳回"] += 1
                报告["明细"].append({"事件编号": 编号, "命运": p["拒源"]})
                continue
            行 = (
                编号,
                键,
                int(ev.get("金额分", 0)),
                源,
                ev.get("事件时") or 此刻(),
                ev.get("处理时") or 此刻(),
            )
            条目 = {"事件编号": 编号, "业务键": 键, "命运": "暂存"}
            报告["明细"].append(条目)
            暂存.append((条目, 行))

        成败 = "成功" if (报告["驳回"] == 0 and not 预检) else "失败"
        时刻 = 此刻()
        if 成败 == "成功":
            # 纯成功：影子与现行同一事务原子晋升，回执才许报成。
            for 条目, 行 in 暂存:
                conn.execute(
                    f"""INSERT INTO {p['表']}(事件编号,业务键,金额分,源键,事件时,处理时,命运,批次编号)
                        VALUES (?,?,?,?,?,?,?,?)""",
                    (*行, p["命运"], 批次),
                )
                conn.execute(
                    """INSERT INTO 影子草稿(影子键,轨别,批次编号,事件编号,业务键,金额分,源键,事件时,处理时,状态)
                       VALUES (?,?,?,?,?,?,?,?,?,'已晋升')""",
                    (影子键, 轨别, 批次, *行),
                )
                条目["命运"] = p["命运"]
            报告["入流"] = len(暂存)
            说明 = "整批原子晋升入流，回执与现行同成"
        else:
            # 中途失败：已暂存行只落作废草稿，一笔都不进现行。
            for 条目, 行 in 暂存:
                conn.execute(
                    """INSERT OR IGNORE INTO 影子草稿(影子键,轨别,批次编号,事件编号,业务键,金额分,源键,事件时,处理时,状态)
                       VALUES (?,?,?,?,?,?,?,?,?,'已作废')""",
                    (影子键, 轨别, 批次, *行),
                )
                条目["命运"] = "影子作废"
            报告["入流"] = 0
            说明 = "批内校验失败，影子草稿整批作废，未进现行"
        报告["成败"] = 成败

        现行 = conn.execute(
            f"SELECT COUNT(*) AS c FROM {p['表']} WHERE 批次编号=? AND 命运=?",
            (批次, p["命运"]),
        ).fetchone()["c"]

        conn.execute(
            "INSERT INTO 装载批次(编号,轨别,时刻,报告) VALUES (?,?,?,?)",
            (批次, 轨别, 时刻, json.dumps(报告, ensure_ascii=False)),
        )
        conn.execute(
            """INSERT INTO 装载收口(批次编号,轨别,形态,影子键,成败,入流,跳过,驳回,现行行数,时刻,说明)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (批次, 轨别, 形态, 影子键, 成败, 报告["入流"], 报告["跳过"], 报告["驳回"], 现行, 时刻, 说明),
        )
        conn.execute("COMMIT")
        return 报告
    except BaseException:
        if conn.in_transaction:
            conn.execute("ROLLBACK")
        raise
    finally:
        conn.close()


def _收口视图(conn, row) -> dict:
    """收口只读视图：valid 现场复核「回执成败 ⟺ 可读流水」，不是回放存根。"""
    p = 轨参[row["轨别"]]
    现行 = conn.execute(
        f"SELECT COUNT(*) AS c FROM {p['表']} WHERE 批次编号=? AND 命运=?",
        (row["批次编号"], p["命运"]),
    ).fetchone()["c"]
    if row["成败"] == "成功":
        valid = 现行 == row["入流"]
    else:
        valid = 现行 == 0
    影子行数 = conn.execute(
        "SELECT COUNT(*) AS c FROM 影子草稿 WHERE 影子键=?", (row["影子键"],)
    ).fetchone()["c"]
    return {
        "批次编号": row["批次编号"],
        "轨别": row["轨别"],
        "形态标记": row["形态"],
        "凭证或影子键": row["影子键"],
        "影子键": row["影子键"],
        "影子行数": 影子行数,
        "现行本批行数": 现行,
        "成败": row["成败"],
        "入流": row["入流"],
        "跳过": row["跳过"],
        "驳回": row["驳回"],
        "时刻": row["时刻"],
        "说明": row["说明"],
        "valid": bool(valid),
    }


def 查收口(批次编号: str) -> dict | None:
    conn = 连接()
    try:
        确保表(conn)
        conn.commit()
        row = conn.execute(
            "SELECT * FROM 装载收口 WHERE 批次编号=?", (批次编号,)
        ).fetchone()
        if not row:
            return None
        return _收口视图(conn, row)
    finally:
        conn.close()


def 列收口(轨别: str = "", 上限: int = 100) -> list[dict]:
    conn = 连接()
    try:
        确保表(conn)
        conn.commit()
        sql = "SELECT * FROM 装载收口"
        args: tuple = ()
        if 轨别:
            sql += " WHERE 轨别=?"
            args = (轨别,)
        sql += " ORDER BY 时刻 DESC, 批次编号 DESC LIMIT ?"
        rows = conn.execute(sql, (*args, 上限)).fetchall()
        return [_收口视图(conn, r) for r in rows]
    finally:
        conn.close()
