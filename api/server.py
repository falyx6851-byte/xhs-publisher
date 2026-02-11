"""
小红书发布工具 v2 — FastAPI 后端 API
提供 RESTful API + WebSocket 实时日志，供手机 PWA 调用
"""

import asyncio
import os
import sys
import json
import glob
import re
from pathlib import Path
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import uvicorn

# 添加项目根目录到路径
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, os.path.join(PROJECT_ROOT, "core"))

from core.pipeline import PublishPipeline, Logger
from core.config_manager import ConfigManager
from config import AVAILABLE_MODELS, AVAILABLE_TEMPLATES, PROMPT_STYLES

# ================== FastAPI 应用 ==================
app = FastAPI(title="小红书发布工具 API", version="2.0")

# CORS (允许手机跨域访问)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# 静态文件 (PWA 前端)
STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
os.makedirs(STATIC_DIR, exist_ok=True)

# 图片输出目录
TEMP_OUTPUT_DIR = os.path.join(PROJECT_ROOT, "core", "temp_output")

# ================== 全局状态 ==================
config_manager = ConfigManager()
active_connections: list[WebSocket] = []
current_pipeline: Optional[PublishPipeline] = None


# ================== WebSocket 日志广播 ==================
async def broadcast_log(message: str):
    """向所有连接的客户端广播日志"""
    disconnected = []
    for ws in active_connections:
        try:
            await ws.send_json({"type": "log", "message": message})
        except Exception:
            disconnected.append(ws)
    for ws in disconnected:
        if ws in active_connections:
            active_connections.remove(ws)


async def broadcast_progress(value: float):
    """广播进度"""
    disconnected = []
    for ws in active_connections:
        try:
            await ws.send_json({"type": "progress", "value": value})
        except Exception:
            disconnected.append(ws)
    for ws in disconnected:
        if ws in active_connections:
            active_connections.remove(ws)


def sync_log_callback(msg: str):
    """同步日志回调 - Logger.log() 会调用此函数，安全推送到事件循环"""
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(broadcast_log(msg))
    except RuntimeError:
        print(msg)


def sync_progress_callback(value: float):
    """同步进度回调"""
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(broadcast_progress(value))
    except RuntimeError:
        pass


def create_pipeline(model: str, template: str) -> PublishPipeline:
    """创建 pipeline 实例（复用回调）"""
    config_manager.set_current_model(model)
    logger = Logger(callback=sync_log_callback)
    pipeline = PublishPipeline(config_manager=config_manager, logger=logger)
    pipeline.set_progress_callback(sync_progress_callback)
    pipeline.image_template = template
    return pipeline


# ================== 请求模型 ==================
class GenerateRequest(BaseModel):
    url: str
    model: str = "gemini-3-flash-preview"
    template: str = "breath"
    prompt_style: str = "深度科技主笔"


class PublishRequest(BaseModel):
    auto_publish: bool = True


# ================== API 路由 ==================

@app.get("/")
async def index():
    """返回 PWA 首页"""
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))


@app.get("/api/config")
async def get_config():
    """获取可用配置选项"""
    prompts_data = config_manager.prompts
    prompt_templates = []
    for t in prompts_data.get("templates", []):
        prompt_templates.append({
            "name": t["name"],
            "description": t.get("description", ""),
        })

    return {
        "models": AVAILABLE_MODELS,
        "templates": [{"id": t[0], "name": t[1]} for t in AVAILABLE_TEMPLATES],
        "prompt_styles": prompt_templates or [
            {"name": s[0], "description": s[1]} for s in PROMPT_STYLES
        ],
        "defaults": {
            "model": config_manager.get_current_model(),
            "template": "breath",
            "prompt_style": config_manager.prompts.get("last_used", "深度科技主笔"),
            "api_key_set": bool(config_manager.get_current_api_key()),
        }
    }


@app.post("/api/generate")
async def generate(req: GenerateRequest):
    """手动模式：抓取 + AI 生成 + 渲染图片，返回预览"""
    global current_pipeline

    await broadcast_log("📱 收到手动生成请求")

    # 获取 prompt 模板
    prompt_data = config_manager.get_prompt_by_name(req.prompt_style)
    if not prompt_data:
        return JSONResponse(status_code=400, content={"error": f"找不到提示词模板: {req.prompt_style}"})
    prompt_template = prompt_data["prompt"]

    # 创建 pipeline
    pipeline = create_pipeline(req.model, req.template)
    current_pipeline = pipeline

    try:
        # 1. 抓取
        await broadcast_log(f"🔗 正在抓取: {req.url}")
        result = await pipeline.scrape_lightweight(req.url)
        if not result:
            return JSONResponse(status_code=500, content={"error": "抓取失败"})

        # 2. AI 生成
        await broadcast_log("🧠 AI 正在生成内容...")
        result = pipeline.generate_content(prompt_template)
        if not result:
            return JSONResponse(status_code=500, content={"error": "AI 生成失败"})

        # 3. 渲染图片
        await broadcast_log("🎨 正在渲染图片...")
        image_paths = pipeline.render_images()
        if not image_paths:
            return JSONResponse(status_code=500, content={"error": "渲染失败"})

        await broadcast_log(f"✅ 生成完成！共 {len(image_paths)} 张图片")

        # 返回预览数据
        image_urls = [f"/api/images/{os.path.basename(p)}" for p in image_paths]

        return {
            "success": True,
            "cover_title": pipeline.ai_data.get("cover_title", ""),
            "caption_title": pipeline.ai_data.get("caption_title", ""),
            "content_body": pipeline.ai_data.get("content_body", ""),
            "images": image_urls,
            "image_count": len(image_urls),
        }

    except Exception as e:
        await broadcast_log(f"❌ 生成失败: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.post("/api/publish")
async def publish(req: PublishRequest):
    """手动模式第二步：确认发布到小红书"""
    global current_pipeline

    if not current_pipeline or not current_pipeline.image_paths:
        return JSONResponse(status_code=400, content={"error": "没有可发布的内容，请先生成"})

    await broadcast_log("🚀 开始发布到小红书...")

    try:
        success = await current_pipeline.publish(headless=True, auto_publish=True)
        if success:
            current_pipeline.archive()
            await broadcast_log("✅ 发布成功！")
            return {"success": True, "message": "发布成功"}
        else:
            await broadcast_log("❌ 发布失败")
            return JSONResponse(status_code=500, content={"error": "发布失败"})
    except Exception as e:
        await broadcast_log(f"❌ 发布出错: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.post("/api/auto-publish")
async def auto_publish(req: GenerateRequest):
    """自动模式：全流程一键完成"""
    global current_pipeline

    await broadcast_log("🤖 自动发布模式启动")

    # 获取 prompt 模板
    prompt_data = config_manager.get_prompt_by_name(req.prompt_style)
    if not prompt_data:
        return JSONResponse(status_code=400, content={"error": f"找不到提示词模板: {req.prompt_style}"})
    prompt_template = prompt_data["prompt"]

    # 创建 pipeline
    pipeline = create_pipeline(req.model, req.template)
    current_pipeline = pipeline

    try:
        success = await pipeline.run_full_pipeline(
            url=req.url,
            prompt_template=prompt_template,
            cloud_mode=True
        )

        if success:
            await broadcast_log("✅ 自动发布完成！")
            return {"success": True, "message": "自动发布成功"}
        else:
            await broadcast_log("❌ 自动发布失败")
            return JSONResponse(status_code=500, content={"error": "自动发布失败"})

    except Exception as e:
        await broadcast_log(f"❌ 自动发布出错: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.get("/api/images/{filename}")
async def get_image(filename: str):
    """提供生成图片的访问"""
    file_path = os.path.join(TEMP_OUTPUT_DIR, filename)
    if os.path.exists(file_path):
        return FileResponse(file_path, media_type="image/png")
    return JSONResponse(status_code=404, content={"error": "图片不存在"})


# ================== WebSocket ==================
@app.websocket("/ws/logs")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket 日志实时推送"""
    await websocket.accept()
    active_connections.append(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        if websocket in active_connections:
            active_connections.remove(websocket)


# 挂载静态文件 (放在最后，避免覆盖 API 路由)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


# ================== 启动入口 ==================
if __name__ == "__main__":
    import socket

    hostname = socket.gethostname()
    local_ip = socket.gethostbyname(hostname)

    print("=" * 50)
    print("  小红书发布工具 — 手机 APP 后端")
    print("=" * 50)
    print(f"  本地访问: http://127.0.0.1:8080")
    print(f"  手机访问: http://{local_ip}:8080")
    print(f"  (确保手机和电脑在同一 WiFi)")
    print("=" * 50)

    uvicorn.run(app, host="0.0.0.0", port=8080)
