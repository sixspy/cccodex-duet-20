"""右轨（核心记账）装载：主链已并入「装载批失败闭」影子草稿收口。

整批先落影子草稿：纯成功原子晋升入流；中途失败草稿作废、本批键不进现行。
"""
from __future__ import annotations
from app.modules.装载批失败闭 import 收口

def 装一批(体: dict) -> dict:
    return 收口.装一批(体, "右")
