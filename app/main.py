"""
FastAPI 应用入口 - 智能销售 AI Agent 后端服务

技术栈：
- FastAPI (异步)
- LangGraph (Agent 编排)
- Pydantic v2 (数据模型)
- OpenAI (LLM)
"""

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse

from app.api.v1 import api_router
from app.core.config import settings
from app.core.logging import get_logger, setup_logging

# 初始化日志
logger = get_logger("main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    应用生命周期管理
    
    启动时执行初始化，关闭时执行清理。
    """
    # ===== 启动时 =====
    logger.info("=" * 50)
    logger.info(f"🚀 启动 {settings.app_name} v{settings.app_version}")
    logger.info(f"📍 环境: {'开发' if settings.debug else '生产'}")
    logger.info(f"🔧 调试模式: {settings.debug}")
    logger.info("=" * 50)
    
    # 确保输出目录存在
    os.makedirs(settings.output_dir, exist_ok=True)
    
    # ═══ 初始化 PostgreSQL 数据库表 ═══
    if settings.database_url:
        from app.agents.graphs.sales_graph import initialize_database
        success = await initialize_database()
        if success:
            logger.info("[Startup] PostgreSQL 持久化初始化完成 ✓")
        else:
            logger.warning("[Startup] PostgreSQL 初始化失败，将使用内存存储")
    
    # ═══ 初始化知识库（强制启动时初始化，修复懒加载问题）═══
    try:
        from app.agents.nodes.knowledge_node import kb_service
        logger.info("[Startup] 正在初始化知识库...")
        success = await kb_service.initialize()
        if success:
            logger.info("[Startup] 知识库初始化完成")
        else:
            logger.warning("[Startup] 知识库初始化失败，将在首次检索时重试")
    except Exception as e:
        logger.error(f"[Startup] 知识库初始化异常: {e}")
        # 不阻断启动，首次检索时会再次尝试初始化
    
    yield
    
    # ===== 关闭时 =====
    logger.info("正在关闭应用...")
    # 清理资源


def create_application() -> FastAPI:
    """
    创建 FastAPI 应用实例
    
    Returns:
        FastAPI 应用实例
    """
    app = FastAPI(
        title=settings.app_name,
        description="""
        智能销售 AI Agent 后端服务
        
        ## 功能特性
        
        - 💬 智能对话：基于 LangGraph 的多轮对话
        - 🔍 知识问答：RAG 检索增强的产品咨询
        - 📄 文档生成：报价单、提案书、合同、报表
        - 💰 销售辅助：价格谈判话术、投诉处理
        - 🔗 微信集成：支持微信小程序接入
        
        ## 技术栈
        
        - FastAPI (异步框架)
        - LangGraph (Agent 工作流)
        - Pydantic v2 (数据验证)
        - OpenAI/Claude (大语言模型)
        """,
        version=settings.app_version,
        docs_url="/docs" if settings.debug else None,
        redoc_url="/redoc" if settings.debug else None,
        lifespan=lifespan,
    )
    
    # ===== 中间件配置 =====
    
    # CORS - 允许微信小程序访问
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Gzip 压缩
    app.add_middleware(GZipMiddleware, minimum_size=1000)
    
    # ===== 异常处理 =====
    
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        """全局异常处理"""
        logger.error(f"未捕获的异常: {str(exc)}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={
                "error": "Internal Server Error",
                "message": "服务器内部错误，请稍后重试",
                "detail": str(exc) if settings.debug else None,
            }
        )
    
    # ===== 路由注册 =====
    
    # API V1 路由
    app.include_router(
        api_router,
        prefix=settings.api_v1_prefix,
    )
    
    # ===== 健康检查端点 =====
    
    @app.get("/health", tags=["健康检查"])
    async def health_check():
        """服务健康检查"""
        return {
            "status": "healthy",
            "app": settings.app_name,
            "version": settings.app_version,
            "debug": settings.debug,
            "persistent": bool(settings.database_url),
        }
    
    @app.get("/", tags=["根路径"])
    async def root():
        """根路径 - API 信息"""
        return {
            "name": settings.app_name,
            "version": settings.app_version,
            "docs": "/docs" if settings.debug else None,
            "api_prefix": settings.api_v1_prefix,
        }
    
    return app


# 创建应用实例
app = create_application()


if __name__ == "__main__":
    import uvicorn
    
    # 开发服务器启动
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_level="info" if settings.debug else "warning",
    )
