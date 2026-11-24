from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from app import seed
from app.routers import 路由

app = FastAPI(title="对拍", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
_STATIC = Path(__file__).resolve().parent / "static"

@app.on_event("startup")
def _启动():
    seed.初始化库()

app.include_router(路由)

@app.get("/login", response_class=HTMLResponse)
def 登录页():
    p = _STATIC / "login.html"
    return HTMLResponse(p.read_text(encoding="utf-8"))

if _STATIC.is_dir():
    app.mount("/", StaticFiles(directory=str(_STATIC), html=True), name="static")
