import os
from pathlib import Path
_tmp = Path(__file__).resolve().parent / "_tmp"
_tmp.mkdir(exist_ok=True)
os.environ["数据目录"] = str(_tmp)
os.environ["夹具目录"] = str(Path(__file__).resolve().parents[2] / "fixtures")

from app import seed
from app.services import 左装载, 右装载, 对齐, 结论, 目录

def setup_function():
    db = _tmp / "对拍.db"
    if db.exists():
        db.unlink()
    seed.初始化库()

def test_双轨对齐与悬账():
    左装载.装一批({
        "事件": [
            {"事件编号": "a1", "业务键": "K1", "金额分": 100, "源键": "渠甲", "事件时": "2026-11-23T10:00:00Z"},
            {"事件编号": "a2", "业务键": "K2", "金额分": 200, "源键": "渠甲", "事件时": "2026-11-23T10:00:01Z"},
        ]
    })
    右装载.装一批({
        "事件": [
            {"事件编号": "b1", "业务键": "K1", "金额分": 100, "源键": "核乙", "事件时": "2026-11-23T10:00:00Z"},
            {"事件编号": "b2", "业务键": "K3", "金额分": 50, "源键": "核乙", "事件时": "2026-11-23T10:00:02Z"},
        ]
    })
    r = 对齐.跑对齐()
    assert r["对齐"] == 1
    assert r["悬账"] >= 2
    assert len(目录.悬列表()) >= 2
    g = 结论.跑一次()
    assert g["是否通过"] is True

def test_seed():
    assert 目录.概览()["站名"] == "对拍"
    assert len(目录.源列表()) >= 2
