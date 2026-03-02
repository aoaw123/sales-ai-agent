"""
API V1 模块 - 版本 1 的 API 路由
"""

from fastapi import APIRouter

from app.api.v1 import chat, documents

api_router = APIRouter()

# 注册子路由
api_router.include_router(chat.router, tags=["聊天"])
api_router.include_router(documents.router, prefix="/docs", tags=["文档"])

__all__ = ["api_router"]
