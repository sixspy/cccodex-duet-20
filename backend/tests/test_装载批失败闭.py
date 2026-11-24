"""装载批失败闭 · 影子草稿形态收口测试。

覆盖题面验收：
- 纯成功可晋升全入；回执与现行同成。
- 批内前成后败：影子形态现行无本批行（与凭证形态可区分），禁报成功留脏行。
- 失败批键不进对齐编排可读集。
- 同批号重演回旧票；同轨并发不双成功覆盖批界、不留半截现行。
- 装载收口只读接口：批次编号/现行本批行数/凭证或影子键/形态标记/valid。
"""
import os
import threading
from pathlib import Path

_tmp = Path(__file__).resolve().parent / "_tmp"
_tmp.mkdir(exist_ok=True)
os.environ["数据目录"] = str(_tmp)
os.environ["夹具目录"] = str(Path(__file__).resolve().parents[2] / "fixtures")

from app import seed
from app.db import 连接
from app.modules.装载批失败闭 import 收口
from app.services import 左装载, 右装载, 对齐, 目录


def setup_function():
    db = _tmp / "对拍.db"
    if db.exists():
        db.unlink()
    seed.初始化库()


def _左行(编号, 键, 金额=100, 源="渠甲"):
    return {"事件编号": 编号, "业务键": 键, "金额分": 金额, "源键": 源,
            "事件时": "2026-11-24T10:00:00Z"}


def _右行(编号, 键, 金额=100, 源="核乙"):
    return {"事件编号": 编号, "业务键": 键, "金额分": 金额, "源键": 源,
            "事件时": "2026-11-24T10:00:01Z"}


def _左现行数(批次):
    conn = 连接()
    try:
        return conn.execute(
            "SELECT COUNT(*) AS c FROM 左轨流水 WHERE 批次编号=?", (批次,)
        ).fetchone()["c"]
    finally:
        conn.close()


def test_纯成功晋升全入():
    前 = len(目录.左列表())
    r = 左装载.装一批({"批次编号": "左-好批", "事件": [_左行("g1", "K-G1"), _左行("g2", "K-G2", 200), _左行("g3", "K-G3", 300)]})
    assert r["成败"] == "成功"
    assert (r["入流"], r["跳过"], r["驳回"]) == (3, 0, 0)
    assert len(目录.左列表()) == 前 + 3
    assert all(d["命运"] == "已入左" for d in r["明细"])
    v = 收口.查收口("左-好批")
    assert v["形态标记"] == "影子草稿"
    assert v["凭证或影子键"] == "影-左-左-好批"
    assert v["现行本批行数"] == 3 and v["影子行数"] == 3
    assert v["valid"] is True


def test_批内前成后败_影子形态现行无本批行():
    前 = len(目录.左列表())
    r = 左装载.装一批({"批次编号": "左-半截", "事件": [
        _左行("h1", "K-前成"),
        _左行("h2", "K-肇事", 金额=-5),   # 负金额 → 校验驳回
        _左行("h3", "K-后行"),
    ]})
    # 禁止报告成功留脏行：整批失败，一笔都不进现行
    assert r["成败"] == "失败"
    assert r["入流"] == 0 and r["驳回"] == 1
    assert len(目录.左列表()) == 前
    assert _左现行数("左-半截") == 0
    命运 = [d.get("命运") for d in r["明细"]]
    assert 命运.count("影子作废") == 2 and "驳回-校验" in 命运
    # 收口只读视图：失败批现行零行，与凭证形态（现行留前成行）可区分
    v = 收口.查收口("左-半截")
    assert v["成败"] == "失败"
    assert v["现行本批行数"] == 0 and v["valid"] is True
    assert v["影子行数"] == 2  # 前成行只到影子草稿，已作废


def test_失败批键不进对齐编排():
    左装载.装一批({"批次编号": "左-脏批", "事件": [
        _左行("d1", "DIRTY-1"),
        _左行("d2", "DIRTY-2", 金额="非数"),
    ]})
    右装载.装一批({"批次编号": "右-净批", "事件": [_右行("r1", "CLEAN-1")]})
    对齐.跑对齐()
    键集 = {row["业务键"] for row in 目录.差列表()}
    assert "DIRTY-1" not in 键集 and "DIRTY-2" not in 键集
    assert "CLEAN-1" in 键集


def test_批次预检失败也收口():
    前 = len(目录.左列表())
    r = 左装载.装一批({"批次编号": "左-预检", "事件": [_左行("p1", "K-P"), _左行("p1", "K-P2")]})
    assert r["成败"] == "失败" and r["入流"] == 0
    assert len(目录.左列表()) == 前
    v = 收口.查收口("左-预检")
    assert v["成败"] == "失败" and v["现行本批行数"] == 0 and v["valid"] is True


def test_同批号重演回旧票不双成功():
    体 = {"批次编号": "左-重演", "事件": [_左行("m1", "K-M1"), _左行("m2", "K-M2")]}
    r1 = 左装载.装一批(体)
    r2 = 左装载.装一批(体)
    assert r1["成败"] == "成功" and r1["入流"] == 2
    assert r2.get("重复批次") is True
    assert _左现行数("左-重演") == 2
    assert 收口.查收口("左-重演")["valid"] is True


def test_并发两批不留半截现行():
    批A = {"批次编号": "左-并发-A", "事件": [_左行(f"ca{i}", f"K-CA{i}") for i in range(40)]}
    批B = {"批次编号": "左-并发-B", "事件": [_左行(f"cb{i}", f"K-CB{i}") for i in range(40)]}
    结果 = {}

    def 跑(名, 体):
        结果[名] = 左装载.装一批(体)

    线程 = [threading.Thread(target=跑, args=("A", 批A)), threading.Thread(target=跑, args=("B", 批B))]
    for t in 线程:
        t.start()
    for t in 线程:
        t.join()
    assert 结果["A"]["成败"] == "成功" and 结果["B"]["成败"] == "成功"
    for 批 in ("左-并发-A", "左-并发-B"):
        v = 收口.查收口(批)
        # 全入或全不入，绝不留半截
        assert v["现行本批行数"] == 40 and v["valid"] is True


def test_同批号并发只一票算数():
    体 = {"批次编号": "左-并发-同号", "事件": [_左行(f"s{i}", f"K-S{i}") for i in range(5)]}
    票 = []

    def 跑():
        票.append(左装载.装一批(dict(体)))

    线程 = [threading.Thread(target=跑) for _ in range(2)]
    for t in 线程:
        t.start()
    for t in 线程:
        t.join()
    assert sum(1 for r in 票 if r.get("重复批次")) == 1
    assert sum(1 for r in 票 if not r.get("重复批次")) == 1
    # 批界不被覆盖：本批恰好 5 行
    assert _左现行数("左-并发-同号") == 5
    assert 收口.查收口("左-并发-同号")["现行本批行数"] == 5


def test_右轨失败同样收口():
    前 = len(目录.右列表())
    r = 右装载.装一批({"批次编号": "右-坏批", "事件": [
        _右行("w1", "K-W1"),
        _右行("w2", "K-W2", 源="不存在的源"),
    ]})
    assert r["成败"] == "失败" and r["入流"] == 0
    assert len(目录.右列表()) == 前
    v = 收口.查收口("右-坏批")
    assert v["轨别"] == "右" and v["现行本批行数"] == 0 and v["valid"] is True
    assert v["凭证或影子键"] == "影-右-右-坏批"


def test_valid是活探针_现行被改即翻脸():
    左装载.装一批({"批次编号": "左-探针", "事件": [_左行("t1", "K-T1")]})
    assert 收口.查收口("左-探针")["valid"] is True
    conn = 连接()
    conn.execute("UPDATE 左轨流水 SET 命运='已冲正' WHERE 批次编号='左-探针'")
    conn.commit()
    conn.close()
    v = 收口.查收口("左-探针")
    assert v["现行本批行数"] == 0 and v["valid"] is False


def test_未知批次返回空():
    assert 收口.查收口("无此批") is None
    assert 收口.列收口("左") == []


def test_收口只读接口():
    from fastapi.testclient import TestClient
    from app.main import app

    左装载.装一批({"批次编号": "左-接口", "事件": [_左行("a1", "K-A1")]})
    左装载.装一批({"批次编号": "左-接口坏", "事件": [_左行("a2", "K-A2"), _左行("a3", "K-A3", 金额=-1)]})
    with TestClient(app) as c:
        r = c.get("/api/装载收口/左-接口")
        assert r.status_code == 200
        体 = r.json()
        for 字段 in ("批次编号", "现行本批行数", "凭证或影子键", "形态标记", "valid"):
            assert 字段 in 体
        assert 体["形态标记"] == "影子草稿" and 体["valid"] is True and 体["现行本批行数"] == 1
        坏 = c.get("/api/装载收口/左-接口坏").json()
        assert 坏["成败"] == "失败" and 坏["现行本批行数"] == 0 and 坏["valid"] is True
        assert c.get("/api/装载收口/无此批").status_code == 404
        列 = c.get("/api/装载收口", params={"轨别": "左"}).json()
        assert {x["批次编号"] for x in 列} >= {"左-接口", "左-接口坏"}
